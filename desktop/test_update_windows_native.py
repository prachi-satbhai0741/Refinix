"""The Windows install helper with the real Win32 job, processes and registry.

desktop/test_update_methods.py checks the helper's decisions with fakes; this
file runs the same functions against Windows itself, on a disposable runner
only (REFINIX_NATIVE_WINDOWS=1 on a GitHub-hosted Windows machine):

* the installer and every process it starts are inside the kill-on-close job
  from their first instruction, and closing the job ends all of them;
* a helper that dies takes the whole installer tree with it;
* the time limit ends the whole tree;
* when the job cannot be attached, nothing starts at all;
* the uninstall registration is snapshotted and restored exactly.

    set REFINIX_NATIVE_WINDOWS=1 && python -m unittest desktop.test_update_windows_native -v

Hosted Windows Server evidence; not a Windows 11 desktop observation.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

NATIVE = sys.platform == "win32" and os.environ.get("REFINIX_NATIVE_WINDOWS") == "1"

# An "installer" that starts two children, writes every pid it owns, then waits.
FIXTURE = textwrap.dedent("""
    import subprocess, sys, time
    out = sys.argv[1]
    children = [subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
                for _ in range(2)]
    with open(out, "w") as handle:
        handle.write(" ".join(str(p) for p in [__import__("os").getpid(),
                                                *[c.pid for c in children]]))
    time.sleep(120)
""")


def alive(pid: int) -> bool:
    import psutil
    try:
        return psutil.Process(pid).is_running() and \
            psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def wait_until(condition, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.2)
    return condition()


@unittest.skipUnless(NATIVE, "native Windows qualification (REFINIX_NATIVE_WINDOWS=1)")
class TestRealJob(unittest.TestCase):
    def setUp(self):
        from desktop import update_windows
        self.w = update_windows
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.base = Path(self.dir.name)
        self.script = self.base / "fixture.py"
        self.script.write_text(FIXTURE, encoding="utf-8")
        self.pids_file = self.base / "pids.txt"

    def pids(self) -> list[int]:
        assert wait_until(lambda: self.pids_file.is_file()
                          and len(self.pids_file.read_text().split()) == 3, 30), \
            "the fixture did not start its children"
        return [int(p) for p in self.pids_file.read_text().split()]

    def start(self, job):
        return self.w.start_in_job(job, Path(sys.executable),
                                   [str(self.script), str(self.pids_file)], self.base)

    def test_the_tree_lives_in_a_kill_on_close_job_and_ends_with_it(self):
        job = self.w.Job()
        self.start(job)
        pids = self.pids()
        self.assertEqual(job.active(), 3)
        limits = job.limits()
        self.assertTrue(limits & self.w.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
        self.assertFalse(limits & (self.w.JOB_OBJECT_LIMIT_BREAKAWAY_OK
                                   | self.w.JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK))
        job.close()
        self.assertTrue(wait_until(lambda: not any(alive(p) for p in pids), 10), pids)

    def test_a_helper_that_dies_takes_the_installer_tree_with_it(self):
        helper = subprocess.Popen(
            [sys.executable, "-c",
             "import sys, time; from pathlib import Path; "
             "from desktop import update_windows as w; job = w.Job(); "
             "w.start_in_job(job, Path(sys.executable), [sys.argv[1], sys.argv[2]], "
             "Path(sys.argv[3])); print('started', flush=True); time.sleep(120)",
             str(self.script), str(self.pids_file), str(self.base)],
            cwd=str(Path(__file__).resolve().parents[1]), stdout=subprocess.PIPE, text=True)
        self.addCleanup(helper.kill)
        self.assertEqual(helper.stdout.readline().strip(), "started")
        pids = self.pids()
        helper.kill()            # TerminateProcess: no cleanup code runs in the helper
        helper.wait(30)
        self.assertTrue(wait_until(lambda: not any(alive(p) for p in pids), 10), pids)

    def test_the_time_limit_ends_the_whole_tree(self):
        job = self.w.Job()
        process = self.start(job)
        pids = self.pids()
        began = time.monotonic()
        self.assertIsNone(self.w.wait_for(job, process, 1.0))
        self.assertLess(time.monotonic() - began, 10)
        job.terminate()
        self.assertTrue(wait_until(lambda: not any(alive(p) for p in pids), 10), pids)
        job.close()

    def test_without_the_job_attached_nothing_starts(self):
        job = self.w.Job()
        real = job.api["k"]

        class Refusing:
            def __getattr__(self, name):
                if name == "UpdateProcThreadAttribute":
                    return lambda *args: 0
                return getattr(real, name)
        job.api = {**job.api, "k": Refusing()}
        with self.assertRaises(self.w.WindowsInstallError):
            self.start(job)
        time.sleep(3)
        self.assertFalse(self.pids_file.exists(), "the uncontained installer ran")
        job.api["k"] = real
        job.close()

    def test_the_uninstall_registration_is_restored_exactly(self):
        import winreg
        before = self.w.registry_snapshot()
        self.addCleanup(self.w.registry_restore, before)
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.w.UNINSTALL_KEY)
        with key:
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, "0.1.0")
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(self.base))
            winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, 1234)
            winreg.SetValueEx(key, "Blob", 0, winreg.REG_BINARY, b"\x00\x01")
        snapshot = self.w.registry_snapshot()
        self.assertIsNone(self.w.registration_problem(snapshot, "0.1.0", self.base))
        self.w.registry_restore(None)
        self.assertIsNone(self.w.registry_snapshot())
        self.w.registry_restore(snapshot)
        self.assertEqual(self.w.registry_snapshot(), snapshot)
        self.assertIn("version", self.w.registration_problem(snapshot, "0.2.0", self.base))


if __name__ == "__main__":
    unittest.main(verbosity=2)
