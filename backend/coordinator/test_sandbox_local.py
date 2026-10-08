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


class FakeHost(sandbox_local.Host):
    """Answers like Ubuntu's tools; records every command."""

    def __init__(self, report=None, udisks=True, flood=0):
        self.commands, self.report, self.udisks, self.flood = [], report, udisks, flood
        self.mounted = None

    def which(self, name):
        if name == "udisksctl":
            return "/usr/bin/udisksctl" if self.udisks else None
        return f"/usr/bin/{name}"

    def run(self, argv, *, timeout=120, input_text=None):
        self.commands.append(list(argv))
        out = ""
        if argv[0] == "udisksctl" and argv[1] == "loop-setup":
            out = f"Mapped file {argv[-1]} as /dev/loop9.\n"
        elif argv[0] == "udisksctl" and argv[1] == "mount":
            self.mounted = Path(tempfile.mkdtemp())
            out = f"Mounted /dev/loop9 at {self.mounted}\n"
        return type("R", (), {"returncode": 0, "stdout": out, "stderr": ""})()

    def popen(self, argv):
        self.commands.append(list(argv))
        report = dict(self.report or {})
        mount = Path(argv[-2])
        manifest = json.loads(Path(argv[-1]).read_text())
        if report.get("ran"):
            report.setdefault("inputs_sha256", sandbox_local.inputs_digest(manifest["files"]))
        body = b"x" * self.flood + b"Ran 2 tests\n\nREFINIX-SANDBOX-REPORT " + \
            json.dumps(report).encode() + b"\n"
        return type("P", (), {"stdout": io.BytesIO(body), "returncode": 0,
                              "wait": lambda self: 0})()


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
            sandbox._note("old", unit="refinix-sandbox-old", method="udisks",
                          device="/dev/loop4", folder=str(Path(folder) / "sandbox" / "runs"
                                                           / "old"))
            self.assertEqual(sandbox.cleanup_leftovers(), ["old"])
            self.assertIn(["systemctl", "--user", "stop", "refinix-sandbox-old"],
                          host.commands)
            self.assertIn(["udisksctl", "loop-delete", "--no-user-interaction", "-b",
                           "/dev/loop4"], host.commands)

    def test_the_launcher_ships_beside_the_package(self):
        self.assertTrue(sandbox_local.launcher_path().is_file())


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
