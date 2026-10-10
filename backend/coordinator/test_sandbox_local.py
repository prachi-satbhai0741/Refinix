"""Code validation on this computer's own sandbox, and the Apply rules around it.

The runner is driven with a simulated host (systemd-run, udisks, mkfs) so the
order of operations, the requested controls, the journal and the cleanup are
checked here; the launcher's confinement runs natively on Linux (Landlock was
observed enforced in a container) and the whole profile stays provisional
until the Ubuntu device qualification (plan v4.3 W2.3).

    python3 -m unittest backend.coordinator.test_sandbox_local -v
"""

from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.coordinator import code_service, db, sandbox_local
from backend.coordinator.code_service import CodeError
from backend.coordinator.test_execution4c import ORIGINAL, REPAIRED, Base


class FakeProcess:
    """A systemd-run client: output, then an exit status. `quiet` keeps it
    running without printing anything until its service is stopped; `hold`
    keeps the pipe open (a descendant holding stdout) even after that."""

    def __init__(self, body: bytes, *, quiet=False, hold=False, returncode=0):
        self.body, self.quiet, self.hold = body, quiet, hold
        self.stopped = threading.Event()
        self.released = threading.Event()
        self._returncode, self.returncode = returncode, None
        self.stdout = self
        self.sent = False

    def read(self, size):
        if not self.sent and not self.quiet:
            self.sent = True
            return self.body
        if self.quiet or self.hold:
            # Nothing to say until the service is stopped (or, held, ever).
            (self.released if self.hold else self.stopped).wait(30)
        return b""

    def poll(self):
        if self.returncode is None and (not self.quiet or self.stopped.is_set()):
            self.returncode = self._returncode if not self.stopped.is_set() else -9
        return self.returncode

    def wait(self, timeout=None):
        return self.poll()

    def kill(self):
        self.stopped.set()


class FakeHost(sandbox_local.Host):
    """Answers like Ubuntu's tools; records every command."""

    def __init__(self, report=None, udisks=True, flood=0, *, quiet=False, hold=False,
                 returncode=0, busy=False, stuck_unit=False, stuck_loop=False, fuse=None):
        self.commands, self.report, self.udisks, self.flood = [], report, udisks, flood
        self.fuse = not udisks if fuse is None else fuse
        self.quiet, self.hold, self.returncode = quiet, hold, returncode
        self.busy, self.stuck_unit, self.stuck_loop = busy, stuck_unit, stuck_loop
        self.mounts, self.loops, self.process = set(), {}, None

    def which(self, name):
        if name == "udisksctl":
            return "/usr/bin/udisksctl" if self.udisks else None
        if name in ("fuse2fs", "fusermount3") and not self.fuse:
            return None
        return f"/usr/bin/{name}"

    def mounted(self, target):
        return target in self.mounts

    def loop_backing(self, device):
        return self.loops.get(device)

    def sleep(self, seconds):
        import time
        time.sleep(min(seconds, 0.01))

    def run(self, argv, *, timeout=120, input_text=None):
        self.commands.append(list(argv))
        out = ""
        if argv[0] == "udisksctl" and argv[1] == "loop-setup":
            self.loops["/dev/loop9"] = argv[-1]
            out = f"Mapped file {argv[-1]} as /dev/loop9.\n"
        elif argv[0] == "udisksctl" and argv[1] == "mount":
            mounted = Path(tempfile.mkdtemp())
            self.mounts |= {str(mounted), "/dev/loop9"}
            out = f"Mounted /dev/loop9 at {mounted}\n"
        elif argv[0] == "udisksctl" and argv[1] == "unmount" and not self.busy:
            self.mounts.clear()
        elif argv[0] == "udisksctl" and argv[1] == "loop-delete" and not self.stuck_loop:
            self.loops.pop(argv[-1], None)
        elif argv[0] == "fuse2fs":
            self.mounts.add(argv[2])
        elif argv[:2] == ["fusermount3", "-u"] and not self.busy:
            self.mounts.discard(argv[-1])
        elif argv[:3] == ["systemctl", "--user", "show"]:
            out = "active\n" if self.stuck_unit else "inactive\n"
        elif argv[:3] == ["systemctl", "--user", "kill"] and self.process:
            self.process.stopped.set()
        return type("R", (), {"returncode": 0, "stdout": out, "stderr": ""})()

    def popen(self, argv):
        self.commands.append(list(argv))
        report = dict(self.report or {})
        manifest = json.loads(Path(argv[-1]).read_text())
        if report.get("ran"):
            report.setdefault("inputs_sha256", sandbox_local.inputs_digest(manifest["files"]))
        code = manifest.get("report_code", "")
        body = b"x" * self.flood + b"Ran 2 tests\n\nREFINIX-SANDBOX-REPORT " + \
            f"{code} ".encode() + json.dumps(report).encode() + b"\n"
        self.process = FakeProcess(body, quiet=self.quiet, hold=self.hold,
                                   returncode=self.returncode)
        return self.process


PASS = {"ran": True, "exit_status": 0, "tests_run": 2, "landlock_abi": 6,
        "controls": ["no sockets", "Landlock", "no signals", "no io_uring",
                     "workspace writable"], "limits": ["memory.max", "pids.max"]}


def available_probe(platform=None):
    names = ("systemd user manager", "systemd 255 or later", "seccomp", "Landlock",
             "delegated memory, process and CPU limits", "aggregate temporary-storage limit")
    return {"available": False, "kernel": "6.8.0",
            "controls": [{"name": n, "ok": True, "observed": True, "detail": ""}
                         for n in names]}


class TestRunner(unittest.TestCase):
    def sandbox(self, host, folder):
        return sandbox_local.LocalSandbox(folder, host=host, probe=available_probe,
                                          platform="linux")

    def test_the_service_carries_every_control_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(sandbox_local.Path, "is_file", return_value=True):
            host = FakeHost(PASS)
            report = self.sandbox(host, Path(folder)).validate(
                [{"path": "test_x.py", "text": "x", "sha256": "a" * 64}])
            self.assertTrue(sandbox_local.passed(report), report)
            run = next(c for c in host.commands if c[0] == "systemd-run")
            for wanted in ("--user", "--wait", "--collect",
                           "--property=RestrictAddressFamilies=none",
                           "--property=NoNewPrivileges=yes",
                           "--property=SystemCallErrorNumber=EPERM",
                           "--property=TasksMax=64", "--property=MemorySwapMax=0"):
                self.assertIn(wanted, run)
            denied = next(p for p in run if p.startswith("--property=SystemCallFilter=~"))
            for call in ("socket", "kill", "ptrace", "io_uring_setup", "bpf", "keyctl",
                         "unshare", "mount"):
                self.assertIn(f" {call} ", f" {denied.split('~', 1)[1]} ")
            self.assertEqual(run[-6:-3], ["/usr/bin/python3", "-I", "-S"])
            self.assertIn(["udisksctl", "loop-delete", "--no-user-interaction", "-b",
                           "/dev/loop9"], host.commands)
            self.assertEqual(report["qualification"], "provisional")
            self.assertEqual(json.loads((Path(folder) / "sandbox" / "journal.json")
                                        .read_text())["runs"], {})

    def test_no_udisks_falls_back_to_fuse2fs_and_none_means_nothing_runs(self):
        with tempfile.TemporaryDirectory() as folder:
            host = FakeHost(PASS, udisks=False)
            self.assertEqual(self.sandbox(host, Path(folder)).storage_method(), "fuse2fs")
            host.which = lambda name: None
            sandbox = self.sandbox(host, Path(folder))
            self.assertFalse(sandbox.status()["available"])
            with self.assertRaises(sandbox_local.SandboxError):
                sandbox.validate([{"path": "a.py", "text": "x", "sha256": "a" * 64}])
            self.assertFalse(any(c[0] == "systemd-run" for c in host.commands))

    def test_fuse_is_preferred_with_both_tools_and_cleanup_is_confirmed(self):
        for busy in (False, True):
            with self.subTest(busy=busy), tempfile.TemporaryDirectory() as folder, \
                    patch.object(sandbox_local.Path, "is_file", return_value=True):
                host = FakeHost(PASS, fuse=True, busy=busy)
                sandbox = self.sandbox(host, Path(folder))
                self.assertEqual(sandbox.storage_method(), "fuse2fs")
                report = sandbox.validate(
                    [{"path": "test_x.py", "text": "x", "sha256": "a" * 64}])
                mount = next(c for c in host.commands if c[0] == "fuse2fs")
                self.assertEqual(mount[-2:], ["-o", "rw,nosuid,nodev"])
                self.assertIn(["fusermount3", "-u", mount[2]], host.commands)
                self.assertFalse(any(c[0] == "udisksctl" for c in host.commands))
                self.assertTrue(sandbox_local.passed(report))
                self.assertEqual(bool(sandbox.stuck_runs()), busy)
                self.assertEqual(Path(mount[1]).exists(), busy)
                self.assertEqual(sandbox.status()["available"], not busy)
                host.busy = False
                sandbox.cleanup_leftovers()
                self.assertFalse(Path(mount[1]).exists())

    def test_fuse_mount_is_journalled_before_an_interrupted_mount_command(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(sandbox_local.Path, "is_file", return_value=True):
            host = FakeHost(PASS, fuse=True)
            original = host.run

            def interrupted(argv, **kwargs):
                result = original(argv, **kwargs)
                if argv[0] == "fuse2fs":
                    raise OSError("mount succeeded, but its client stopped")
                return result

            host.run = interrupted
            sandbox = self.sandbox(host, Path(folder))
            with self.assertRaises(OSError):
                sandbox.validate([{"path": "a.py", "text": "x", "sha256": "a" * 64}])
            self.assertFalse(host.mounts)
            self.assertEqual(sandbox._journal()["runs"], {})
            self.assertFalse(any((Path(folder) / "sandbox" / "runs").iterdir()))

    def test_a_refused_control_or_changed_inputs_is_never_a_pass(self):
        for report in ({**PASS, "ran": False, "refused": "Landlock",
                        "error": "kernel too old"},
                       {**PASS, "inputs_sha256": "0" * 64},
                       {**PASS, "tests_run": 0},
                       {**PASS, "controls": ["no sockets", "Landlock"]}):
            with self.subTest(report=report), tempfile.TemporaryDirectory() as folder, \
                    patch.object(sandbox_local.Path, "is_file", return_value=True):
                result = self.sandbox(FakeHost(report), Path(folder)).validate(
                    [{"path": "test_x.py", "text": "x", "sha256": "a" * 64}])
                self.assertFalse(sandbox_local.passed(result))

    def test_output_is_capped_but_the_report_is_kept(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(sandbox_local.Path, "is_file", return_value=True):
            report = self.sandbox(FakeHost(PASS, flood=400_000), Path(folder)).validate(
                [{"path": "test_x.py", "text": "x", "sha256": "a" * 64}])
            self.assertTrue(report["output_truncated"])
            self.assertLessEqual(len(report["output"]), sandbox_local.OUTPUT_LIMIT)
            self.assertTrue(sandbox_local.passed(report))

    def test_leftovers_are_removed_at_the_next_start(self):
        with tempfile.TemporaryDirectory() as folder:
            host = FakeHost(PASS)
            sandbox = self.sandbox(host, Path(folder))
            old = Path(folder) / "sandbox" / "runs" / "old"
            host.loops["/dev/loop4"] = str(old / "workspace.img")
            host.mounts.add("/dev/loop4")
            sandbox._note("old", unit="refinix-sandbox-old", method="udisks",
                          device="/dev/loop4", folder=str(old))
            self.assertEqual(sandbox.cleanup_leftovers(), ["old"])
            self.assertIn(["systemctl", "--user", "stop", "refinix-sandbox-old"],
                          host.commands)
            self.assertIn(["udisksctl", "loop-delete", "--no-user-interaction", "-b",
                           "/dev/loop4"], host.commands)

    def run_with(self, host, folder, cancel=None, deadline=None):
        sandbox = self.sandbox(host, Path(folder))
        if deadline is not None:
            sandbox.deadline_seconds = deadline
        return sandbox, sandbox.validate(
            [{"path": "test_x.py", "text": "x", "sha256": "a" * 64}], cancel=cancel)

    def test_a_silent_run_is_cancelled_promptly(self):
        import time
        for hold in (False, True):
            with self.subTest(descendant_holds_stdout=hold), \
                    tempfile.TemporaryDirectory() as folder, \
                    patch.object(sandbox_local.Path, "is_file", return_value=True):
                host = FakeHost(PASS, quiet=True, hold=hold)
                cancel = threading.Event()
                threading.Timer(0.3, cancel.set).start()
                began = time.monotonic()
                _sandbox, report = self.run_with(host, folder, cancel=cancel)
                self.assertLess(time.monotonic() - began, 4)
                self.assertFalse(sandbox_local.passed(report))
                self.assertEqual(report["refused"], "cancelled")
                run = next(c for c in host.commands if c[0] == "systemd-run")
                unit = next(a for a in run if a.startswith("--unit="))[len("--unit="):]
                self.assertIn(["systemctl", "--user", "kill", "--signal=SIGKILL", unit],
                              host.commands)

    def test_a_silent_run_stops_at_the_deadline(self):
        import time
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(sandbox_local.Path, "is_file", return_value=True):
            began = time.monotonic()
            _sandbox, report = self.run_with(FakeHost(PASS, quiet=True), folder,
                                             deadline=0.3)
            self.assertLess(time.monotonic() - began, 5)
            self.assertEqual(report["refused"], "deadline")
            self.assertFalse(sandbox_local.passed(report))

    def test_a_report_without_this_runs_code_or_a_failed_service_never_passes(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(sandbox_local.Path, "is_file", return_value=True):
            host = FakeHost(PASS)
            original = host.popen

            def forged(argv):
                process = original(argv)
                code = json.loads(Path(argv[-1]).read_text())["report_code"]
                process.body = process.body.replace(code.encode(), b"0" * 32)
                return process
            host.popen = forged
            _sandbox, report = self.run_with(host, folder)
            self.assertFalse(sandbox_local.passed(report))
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(sandbox_local.Path, "is_file", return_value=True):
            _sandbox, report = self.run_with(FakeHost(PASS, returncode=1), folder)
            self.assertEqual(report["service_exit"], 1)
            self.assertFalse(sandbox_local.passed(report))

    def test_failed_cleanup_keeps_its_record_until_it_succeeds(self):
        for failure in ("busy", "stuck_unit", "stuck_loop"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder, \
                    patch.object(sandbox_local.Path, "is_file", return_value=True):
                host = FakeHost(PASS, **{failure: True})
                sandbox, report = self.run_with(host, folder)
                runs = sandbox._journal()["runs"]
                self.assertEqual(len(runs), 1, failure)
                run_id, run = next(iter(runs.items()))
                self.assertTrue(run["cleanup_problems"])
                self.assertTrue(Path(run["folder"]).is_dir(), "the image is kept")
                if failure != "stuck_unit":
                    # A workspace still attached: no new validation starts.
                    self.assertFalse(sandbox.status()["available"])
                # The next start retries, exactly once successfully.
                setattr(host, failure, False)
                deletes = sum(1 for c in host.commands if c[:2] == ["udisksctl", "loop-delete"])
                self.assertEqual(sandbox.cleanup_leftovers(), [run_id])
                self.assertEqual(sandbox._journal()["runs"], {})
                self.assertFalse(Path(run["folder"]).exists())
                self.assertEqual(sandbox.cleanup_leftovers(), [])
                after = sum(1 for c in host.commands if c[:2] == ["udisksctl", "loop-delete"])
                self.assertLessEqual(after - deletes, 1)

    def test_cleanup_touches_only_this_runs_own_unit_and_device(self):
        with tempfile.TemporaryDirectory() as folder:
            host = FakeHost(PASS)
            sandbox = self.sandbox(host, Path(folder))
            host.loops["/dev/loop2"] = "/var/lib/other/disk.img"
            host.mounts.add("/dev/loop2")
            sandbox._note("odd", unit="someone-elses.service", method="udisks",
                          device="/dev/loop2",
                          folder=str(Path(folder) / "sandbox" / "runs" / "odd"))
            sandbox.cleanup_leftovers()
            self.assertFalse(any("someone-elses.service" in c for c in host.commands))
            self.assertFalse(any(c[:2] == ["udisksctl", "loop-delete"] for c in host.commands))
            self.assertFalse(any(c[:2] == ["udisksctl", "unmount"] for c in host.commands))
            self.assertIn("/dev/loop2", host.mounts)
            self.assertEqual(host.loops["/dev/loop2"], "/var/lib/other/disk.img")

    def test_the_launcher_ships_beside_the_package(self):
        self.assertTrue(sandbox_local.launcher_path().is_file())


class TestLauncherTimeLimit(unittest.TestCase):
    """The launcher's own limit holds when the tests print nothing, and it
    never relies on kill(), which the service's filter denies."""

    def run_tests(self, body, seconds):
        import sys
        import time
        from backend.coordinator import sandbox_launcher
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "test_quiet.py").write_text(body, encoding="utf-8")
            environment = {"PATH": "/usr/bin:/bin", "HOME": folder,
                           "TMPDIR": str(Path(folder) / "tmp"), "PYTHONDONTWRITEBYTECODE": "1"}
            began = time.monotonic()
            with patch.object(sandbox_launcher.subprocess.Popen, "kill",
                              side_effect=AssertionError("kill() is denied in the service")):
                result = sandbox_launcher.run_tests(folder, environment, seconds)
            return result, time.monotonic() - began

    def test_a_silent_test_run_is_reported_at_the_time_limit(self):
        quiet = ("import time, unittest\n"
                 "class T(unittest.TestCase):\n"
                 "    def test_waits(self):\n"
                 "        time.sleep(30)\n")
        result, took = self.run_tests(quiet, 1)
        self.assertLess(took, 6)
        self.assertTrue(result["timed_out"])
        self.assertIsNone(result["exit_status"])

    def test_a_noisy_run_is_capped_and_finishes(self):
        noisy = ("import sys, unittest\n"
                 "class T(unittest.TestCase):\n"
                 "    def test_prints(self):\n"
                 "        sys.stdout.write('y' * 300000)\n")
        result, _took = self.run_tests(noisy, 60)
        self.assertEqual(result["exit_status"], 0)
        self.assertTrue(result["output_truncated"])
        self.assertFalse(result["timed_out"])


class TestCodeWorkflow(Base):
    def use_sandbox(self, report):
        host = FakeHost(report)
        sandbox = sandbox_local.LocalSandbox(self.state.parent, host=host,
                                             probe=available_probe, platform="linux")
        self.c.local_sandbox = sandbox
        self.patcher = patch.object(sandbox_local.Path, "is_file", return_value=True)
        return host

    def validate(self, proposal):
        with patch.object(sandbox_local.Path, "is_file", return_value=True), \
                patch.object(self.c, "choose_route") as route:
            record = self.c.code.validate(self.repo_id, proposal["proposal_id"])
        route.assert_not_called()
        return record

    def test_a_passing_local_validation_is_bound_and_lets_apply_proceed(self):
        proposal = self.propose_local()
        self.use_sandbox(PASS)
        record = self.validate(proposal)
        self.assertTrue(record["passed"])
        self.assertEqual(record["node_id"], code_service.LOCAL_SANDBOX_NODE)
        self.assertEqual(record["pod"]["qualification"], "provisional")
        state = self.c.code.state(self.repo_id)
        self.assertTrue(state["validation"]["matches"])
        self.assertIsNone(state["validation_note"])
        result = self.c.code.apply(self.repo_id, proposal["proposal_id"])
        self.assertEqual(result["state"], "applied")
        self.assertEqual(self.disk(), REPAIRED)
        modes = [a for a in db.recent_audit(self.c.conn, self.c.workspace_id, self.repo_id)
                 if a["action"] == "code.apply_mode"]
        self.assertEqual(modes[0]["detail"]["mode"], "sandbox_validated")

    def test_after_a_failed_validation_apply_needs_the_explicit_choice(self):
        proposal = self.propose_local()
        self.use_sandbox({**PASS, "exit_status": 1})
        record = self.validate(proposal)
        self.assertFalse(record["passed"])
        with self.assertRaises(CodeError) as caught:
            self.c.code.apply(self.repo_id, proposal["proposal_id"])
        self.assertEqual(caught.exception.code, "validation_failed")
        self.assertEqual(self.disk(), ORIGINAL)
        with self.assertRaises(CodeError):
            self.c.code.apply(self.repo_id, proposal["proposal_id"],
                              mode="sandbox_validated")
        result = self.c.code.apply(self.repo_id, proposal["proposal_id"], mode="unsandboxed")
        self.assertEqual(result["state"], "applied")
        modes = [a for a in db.recent_audit(self.c.conn, self.c.workspace_id, self.repo_id)
                 if a["action"] == "code.apply_mode"]
        self.assertEqual(modes[0]["detail"]["mode"], "unsandboxed")
        self.assertEqual(modes[0]["detail"]["validation"], record["validation_id"])

    def test_a_pass_for_other_inputs_does_not_count(self):
        proposal = self.propose_local()
        self.use_sandbox({**PASS, "inputs_sha256": "0" * 64})
        record = self.validate(proposal)
        self.assertFalse(record["passed"])
        with self.assertRaises(CodeError):
            self.c.code.apply(self.repo_id, proposal["proposal_id"])

    def test_without_a_sandbox_local_apply_keeps_its_label(self):
        proposal = self.propose_local()
        self.c.local_sandbox.status = lambda: {"available": False, "detail": "none here"}
        with self.assertRaises(CodeError) as caught:
            self.c.code.validate(self.repo_id, proposal["proposal_id"])
        self.assertEqual(caught.exception.code, "no_sandbox")
        state = self.c.code.state(self.repo_id)
        self.assertEqual(state["validation_note"], code_service.LOCAL_VALIDATION_NOTE)
        self.assertEqual(self.c.code.apply(self.repo_id, proposal["proposal_id"])["state"],
                         "applied")

    def validated_with_a_test_file(self):
        (self.project / "test_limits.py").write_text(
            "import unittest\nfrom limits import exceeds\n", encoding="utf-8")
        proposal = self.propose_local(paths=["limits.py", "test_limits.py"])
        self.use_sandbox(PASS)
        self.assertTrue(self.validate(proposal)["passed"])
        return proposal

    def test_a_changed_untouched_test_file_voids_the_sandbox_pass(self):
        # The selected test file is not edited, yet the pass was about it.
        changes = {
            "changed": lambda path: path.write_text("import unittest\n# edited\n",
                                                    encoding="utf-8"),
            "deleted": lambda path: path.unlink(),
            "replaced by a link": lambda path: (path.unlink(),
                                                path.symlink_to(self.project / "notes.md")),
        }
        for name, change in changes.items():
            with self.subTest(change=name):
                self.setUp()
                proposal = self.validated_with_a_test_file()
                change(self.project / "test_limits.py")
                for mode in (None, "sandbox_validated"):
                    with self.assertRaises(CodeError) as caught:
                        self.c.code.apply(self.repo_id, proposal["proposal_id"], mode=mode)
                    self.assertEqual(caught.exception.code, "validation_stale")
                    self.assertIn("test_limits.py", str(caught.exception))
                self.assertEqual(self.disk(), ORIGINAL)
                # Going ahead without the sandbox stays a deliberate, recorded choice.
                result = self.c.code.apply(self.repo_id, proposal["proposal_id"],
                                           mode="unsandboxed")
                self.assertEqual(result["state"], "applied")
                modes = [a for a in db.recent_audit(self.c.conn, self.c.workspace_id,
                                                    self.repo_id)
                         if a["action"] == "code.apply_mode"]
                self.assertEqual(modes[0]["detail"]["mode"], "unsandboxed")

    def test_unchanged_selected_inputs_keep_the_sandbox_pass(self):
        proposal = self.validated_with_a_test_file()
        result = self.c.code.apply(self.repo_id, proposal["proposal_id"])
        self.assertEqual(result["state"], "applied")
        modes = [a for a in db.recent_audit(self.c.conn, self.c.workspace_id, self.repo_id)
                 if a["action"] == "code.apply_mode"]
        self.assertEqual(modes[0]["detail"]["mode"], "sandbox_validated")

    def test_a_validation_can_be_cancelled_from_the_code_surface(self):
        proposal = self.propose_local()
        host = self.use_sandbox(PASS)
        started = threading.Event()
        original = host.popen

        def slow(argv):
            started.set()
            self.c.code.cancel(self.repo_id)
            return original(argv)
        host.popen = slow
        record = self.validate(proposal)
        self.assertTrue(started.is_set())
        self.assertFalse(record["passed"])
        self.assertIn("cancel", (record["detail"] or "").lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
