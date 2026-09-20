"""AF-013 checks: approval binding, and a final write that survives a restart.

The interesting cases are the ones that used to be impossible to test, because
the failure only appeared when the process stopped at exactly the wrong moment.
A durable write record makes them ordinary: a "crash" here is simply not
calling `_run_operation`, and a "restart" is constructing a second
`Coordinator` over the same database.

Standard library only. No model, no worker, no network.
"""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.coordinator import code_service, db, policy, repo
from backend.coordinator.server import Coordinator


ORIGINAL = {
    "alpha.py": "value = 1\n",
    "beta.py": "value = 2\n",
    "gamma.py": "value = 3\n",
}
REPLACEMENT = {
    "alpha.py": "value = 10\n",
    "beta.py": "value = 20\n",
    "gamma.py": "value = 30\n",
}


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Base(unittest.TestCase):
    def setUp(self):
        if not repo.containment_supported():
            self.skipTest("this platform cannot contain repository access")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "state" / "refinix.sqlite3"
        self.project = Path(self.tmp.name) / "project"
        self.project.mkdir()
        for name, text in ORIGINAL.items():
            (self.project / name).write_text(text)
        self.c = Coordinator(self.state)
        self.addCleanup(self.c.conn.close)
        self.repo = self.c.code.connect(str(self.project))
        self.repo_id = self.repo["repo_id"]

    def restart(self) -> Coordinator:
        """A second coordinator over the same database, as a relaunch would be.

        Startup resumes outstanding writes on its own, so the result of that
        recovery is `resumed_writes` on the returned object; calling
        `resume_writes()` again would correctly find nothing left to do.
        """
        self.c.conn.close()
        self.c = Coordinator(self.state)
        self.addCleanup(self.c.conn.close)
        return self.c

    def proposal(self, paths=("alpha.py", "beta.py", "gamma.py")):
        edits = [{"path": name, "base_sha256": digest(ORIGINAL[name]),
                  "after_sha256": digest(REPLACEMENT[name]),
                  "content": REPLACEMENT[name],
                  "diff": f"--- a/{name}\n+++ b/{name}\n"} for name in paths]
        from backend.coordinator import codeflow
        record = db.create_proposal(
            self.c.conn, workspace_id=self.c.workspace_id, repo_id=self.repo_id,
            job_id=None, attempt_id=None, request="raise the values",
            summary="raise the values",
            digest=codeflow.action_digest(self.repo_id, edits), edits=edits)
        self.record_passing_validation(record)
        return record

    def record_passing_validation(self, proposal):
        db.record_validation(
            self.c.conn, workspace_id=self.c.workspace_id,
            proposal_id=proposal["proposal_id"], job_id=None, attempt_id=None,
            node_id="test-sandbox", patch_sha256=proposal["digest"], result={
                "observed": True, "job_state": "succeeded", "passed": True,
                "result": {"command": list(code_service.VALIDATION_COMMAND),
                           "exit_status": 0, "stdout": "", "stderr": "Ran 1 test\nOK",
                           "tests_run": 1, "passed": True,
                           "result_sha256": "a" * 64}})

    def unvalidated_proposal(self):
        edits = [{"path": "alpha.py", "base_sha256": digest(ORIGINAL["alpha.py"]),
                  "after_sha256": digest(REPLACEMENT["alpha.py"]),
                  "content": REPLACEMENT["alpha.py"], "diff": "d"}]
        from backend.coordinator import codeflow
        return db.create_proposal(
            self.c.conn, workspace_id=self.c.workspace_id, repo_id=self.repo_id,
            job_id=None, attempt_id=None, request="raise alpha", summary="raise alpha",
            digest=codeflow.action_digest(self.repo_id, edits), edits=edits)

    def ask(self, proposal):
        """Drive `apply` to the point where an approval is waiting."""
        with self.assertRaises(code_service.ApprovalNeeded) as caught:
            self.c.code.apply(self.repo_id, proposal["proposal_id"])
        return caught.exception.approval

    def on_disk(self) -> dict:
        return {name: (self.project / name).read_text()
                for name in ORIGINAL if (self.project / name).exists()}


# --------------------------------------------------------------------------
# Binding
# --------------------------------------------------------------------------

class TestApprovalBinding(Base):
    def test_apply_refuses_a_proposal_without_current_passing_validation(self):
        proposal = self.unvalidated_proposal()
        with self.assertRaises(code_service.CodeError) as caught:
            self.c.code.apply(self.repo_id, proposal["proposal_id"])
        self.assertEqual(caught.exception.code, "validation_required")
        self.assertEqual(self.on_disk(), ORIGINAL)

    def test_an_approval_records_the_exact_target_and_digest(self):
        proposal = self.proposal()
        approval = self.ask(proposal)
        self.assertEqual(approval["action"], policy.ACTION_WRITE)
        self.assertEqual(approval["action_sha256"], proposal["digest"])
        self.assertEqual(approval["proposal_id"], proposal["proposal_id"])
        self.assertEqual(approval["decision"], "pending")

    def test_the_client_decision_carries_only_an_id_boolean_and_conversation(self):
        """Nothing about the target may come from the decision request."""
        import inspect
        signature = inspect.signature(self.c.code.decide)
        self.assertEqual(list(signature.parameters),
                         ["approval_id", "approved", "conversation_id"])
        with self.assertRaises(code_service.CodeError):
            self.c.code.decide("not-a-uuid", "yes")          # not a boolean

    def test_a_changed_output_digest_needs_a_new_approval(self):
        first = self.proposal(("alpha.py",))
        approval = self.ask(first)
        self.c.code.decide(approval["approval_id"], True)
        second = self.proposal(("alpha.py", "beta.py"))
        # The first approval was for a different set of bytes.
        with self.assertRaises(code_service.CodeError) as caught:
            self.c.code.apply(self.repo_id, second["proposal_id"],
                              approval_id=approval["approval_id"])
        self.assertEqual(caught.exception.code, "mismatch")
        self.assertEqual(self.on_disk(), ORIGINAL)

    def test_an_approval_for_another_proposal_is_refused(self):
        first = self.proposal(("alpha.py",))
        approval = self.ask(first)
        self.c.code.decide(approval["approval_id"], True)
        other = self.proposal(("alpha.py",))
        with self.assertRaises(code_service.CodeError):
            self.c.code.apply(self.repo_id, other["proposal_id"],
                              approval_id=approval["approval_id"])
        self.assertEqual(self.on_disk(), ORIGINAL)

    def test_denial_writes_nothing(self):
        proposal = self.proposal()
        approval = self.ask(proposal)
        self.c.code.decide(approval["approval_id"], False)
        with self.assertRaises(code_service.CodeError) as caught:
            self.c.code.apply(self.repo_id, proposal["proposal_id"],
                              approval_id=approval["approval_id"])
        self.assertEqual(caught.exception.code, "denied")
        self.assertEqual(self.on_disk(), ORIGINAL)
        self.assertIsNone(db.operation_for_approval(
            self.c.conn, approval["approval_id"], self.c.workspace_id))

    def test_expiry_writes_nothing(self):
        proposal = self.proposal()
        approval = self.ask(proposal)
        with self.c.conn:
            self.c.conn.execute(
                "UPDATE approvals SET expires_at='2000-01-01T00:00:00Z'"
                " WHERE approval_id=?", (approval["approval_id"],))
        with self.assertRaises(code_service.CodeError) as caught:
            self.c.code.apply(self.repo_id, proposal["proposal_id"],
                              approval_id=approval["approval_id"])
        self.assertEqual(caught.exception.code, "expired")
        self.assertEqual(self.on_disk(), ORIGINAL)

    def test_an_approval_is_consumed_exactly_once(self):
        proposal = self.proposal()
        approval = self.ask(proposal)
        self.c.code.decide(approval["approval_id"], True)
        first = self.c.code.apply(self.repo_id, proposal["proposal_id"],
                                  approval_id=approval["approval_id"])
        self.assertEqual(first["state"], "applied")
        # The proposal is now applied, so a replay is refused before the gate.
        with self.assertRaises(code_service.CodeError) as caught:
            self.c.code.apply(self.repo_id, proposal["proposal_id"],
                              approval_id=approval["approval_id"])
        self.assertEqual(caught.exception.code, "not_pending")

    def test_two_concurrent_approvals_never_cross(self):
        """C10 runs two workflows at once, and `apply` writes files.

        An earlier version stashed the claimed write record on the service, so
        two simultaneous approvals could have one thread pick up the other's
        authorised operation and apply the wrong change. The claim now lives in
        each call's own local; this drives both at once and asserts each
        operation wrote only its own file.
        """
        second_project = Path(self.tmp.name) / "second"
        second_project.mkdir()
        for name, text in ORIGINAL.items():
            (second_project / name).write_text(text)
        other_id = self.c.code.connect(str(second_project))["repo_id"]

        first = self.proposal(("alpha.py",))
        approval_one = self.ask(first)
        self.c.code.decide(approval_one["approval_id"], True)

        edits = [{"path": "beta.py", "base_sha256": digest(ORIGINAL["beta.py"]),
                  "after_sha256": digest(REPLACEMENT["beta.py"]),
                  "content": REPLACEMENT["beta.py"], "diff": "d"}]
        from backend.coordinator import codeflow
        second = db.create_proposal(
            self.c.conn, workspace_id=self.c.workspace_id, repo_id=other_id,
            job_id=None, attempt_id=None, request="raise beta",
            summary="raise beta",
            digest=codeflow.action_digest(other_id, edits), edits=edits)
        self.record_passing_validation(second)
        with self.assertRaises(code_service.ApprovalNeeded) as caught:
            self.c.code.apply(other_id, second["proposal_id"])
        approval_two = caught.exception.approval
        self.c.code.decide(approval_two["approval_id"], True)

        import threading
        start = threading.Barrier(3, timeout=10)
        results, errors = {}, []

        def go(key, repo_id, proposal_id, approval_id):
            try:
                start.wait()
                results[key] = self.c.code.apply(repo_id, proposal_id,
                                                 approval_id=approval_id)
            except Exception as exc:                       # noqa: BLE001
                errors.append(exc)

        threads = [
            threading.Thread(target=go, args=("one", self.repo_id,
                                              first["proposal_id"],
                                              approval_one["approval_id"])),
            threading.Thread(target=go, args=("two", other_id,
                                              second["proposal_id"],
                                              approval_two["approval_id"])),
        ]
        for thread in threads:
            thread.start()
        start.wait(timeout=10)
        for thread in threads:
            thread.join(timeout=10)

        self.assertEqual(errors, [])
        self.assertEqual(results["one"]["state"], "applied")
        self.assertEqual(results["two"]["state"], "applied")
        # Each operation touched only its own project and its own file.
        self.assertEqual((self.project / "alpha.py").read_text(),
                         REPLACEMENT["alpha.py"])
        self.assertEqual((self.project / "beta.py").read_text(), ORIGINAL["beta.py"])
        self.assertEqual((second_project / "beta.py").read_text(),
                         REPLACEMENT["beta.py"])
        self.assertEqual((second_project / "alpha.py").read_text(),
                         ORIGINAL["alpha.py"])
        self.assertNotEqual(results["one"]["operation_id"],
                            results["two"]["operation_id"])

    def test_the_service_keeps_no_shared_claim_between_calls(self):
        """The shape of the fix, not only its effect: a per-call local."""
        self.assertFalse(hasattr(self.c.code, "_claimed"),
                         "a claimed write record must not live on the service")

    def test_a_double_submission_produces_one_operation_not_two(self):
        """Two clicks race into `claim_approval_for_write`; one record results."""
        proposal = self.proposal()
        approval = self.ask(proposal)
        self.c.code.decide(approval["approval_id"], True)
        plan = [{"path": e["path"], "edit_id": e["edit_id"],
                 "base_sha256": e["base_sha256"], "after_sha256": e["after_sha256"]}
                for e in db.proposal_edit_contents(self.c.conn,
                                                   proposal["proposal_id"])]
        first = db.claim_approval_for_write(
            self.c.conn, approval["approval_id"], self.c.workspace_id,
            action=policy.ACTION_WRITE, action_sha256=proposal["digest"],
            repo_id=self.repo_id, proposal_id=proposal["proposal_id"], edits=plan)
        second = db.claim_approval_for_write(
            self.c.conn, approval["approval_id"], self.c.workspace_id,
            action=policy.ACTION_WRITE, action_sha256=proposal["digest"],
            repo_id=self.repo_id, proposal_id=proposal["proposal_id"], edits=plan)
        self.assertEqual(first["operation_id"], second["operation_id"])
        rows = self.c.conn.execute(
            "SELECT COUNT(*) AS n FROM write_operations WHERE approval_id=?",
            (approval["approval_id"],)).fetchone()["n"]
        self.assertEqual(rows, 1)


# --------------------------------------------------------------------------
# Durable recovery
# --------------------------------------------------------------------------

class TestWriteRecovery(Base):
    def approved_operation(self, paths=("alpha.py", "beta.py", "gamma.py")):
        """Consume an approval and create the record, WITHOUT writing anything.

        This is the crash-after-claim state: the decision is spent and no file
        has been touched.
        """
        proposal = self.proposal(paths)
        approval = self.ask(proposal)
        self.c.code.decide(approval["approval_id"], True)
        plan = [{"path": e["path"], "edit_id": e["edit_id"],
                 "base_sha256": e["base_sha256"], "after_sha256": e["after_sha256"]}
                for e in db.proposal_edit_contents(self.c.conn,
                                                   proposal["proposal_id"])]
        operation = db.claim_approval_for_write(
            self.c.conn, approval["approval_id"], self.c.workspace_id,
            action=policy.ACTION_WRITE, action_sha256=proposal["digest"],
            repo_id=self.repo_id, proposal_id=proposal["proposal_id"], edits=plan)
        return proposal, approval, operation

    def test_a_crash_after_claiming_leaves_a_resumable_record(self):
        _proposal, _approval, operation = self.approved_operation()
        self.assertEqual(self.on_disk(), ORIGINAL)
        self.assertEqual(operation["state"], "pending")
        resumed = self.restart().resumed_writes
        self.assertEqual([item["state"] for item in resumed], ["applied"])
        self.assertEqual(self.on_disk(), REPLACEMENT)

    def test_a_crash_after_one_of_several_files_finishes_the_rest(self):
        _proposal, _approval, operation = self.approved_operation()
        # Simulate the first file having been written before the stop.
        (self.project / "alpha.py").write_text(REPLACEMENT["alpha.py"])
        db.set_operation_file(self.c.conn, operation["operation_id"],
                              "alpha.py", "applied")
        db.set_operation_state(self.c.conn, operation["operation_id"], "applying")
        self.assertEqual([item["state"] for item in self.restart().resumed_writes],
                         ["applied"])
        self.assertEqual(self.on_disk(), REPLACEMENT)

    def test_a_file_already_at_its_after_hash_is_not_written_again(self):
        """The idempotence that stops a restart producing a duplicate write."""
        _proposal, _approval, operation = self.approved_operation(("alpha.py",))
        (self.project / "alpha.py").write_text(REPLACEMENT["alpha.py"])
        written = []
        real = repo.replace_text_file

        def watch(*args, **kwargs):                        # pragma: no cover
            written.append(args[1])
            return real(*args, **kwargs)

        with patch.object(code_service.repo, "replace_text_file", watch):
            resumed = self.restart().resumed_writes
        self.assertEqual(written, [])
        self.assertEqual(resumed[0]["state"], "applied")
        self.assertEqual((self.project / "alpha.py").read_text(),
                         REPLACEMENT["alpha.py"])

    def test_a_third_party_edit_during_recovery_stops_that_file(self):
        _proposal, _approval, _operation = self.approved_operation()
        (self.project / "beta.py").write_text("someone else was here\n")
        resumed = self.restart().resumed_writes
        states = {item["path"]: item["state"] for item in resumed[0]["results"]}
        self.assertEqual(states["beta.py"], "rejected_stale")
        self.assertEqual((self.project / "beta.py").read_text(),
                         "someone else was here\n")
        self.assertEqual(resumed[0]["state"], "partially_applied")

    def test_recovery_resumes_only_the_approved_operation(self):
        _proposal, _approval, _operation = self.approved_operation(("alpha.py",))
        # A second proposal that was never approved must not be touched.
        untouched = self.proposal(("gamma.py",))
        self.restart()
        self.assertEqual((self.project / "alpha.py").read_text(),
                         REPLACEMENT["alpha.py"])
        self.assertEqual((self.project / "gamma.py").read_text(),
                         ORIGINAL["gamma.py"])
        self.assertEqual(
            db.get_proposal(self.c.conn, untouched["proposal_id"],
                            self.c.workspace_id)["state"], "proposed")

    def test_an_operation_reaches_exactly_one_terminal_state(self):
        _proposal, _approval, operation = self.approved_operation(("alpha.py",))
        self.restart()
        record = db.write_operation(self.c.conn, operation["operation_id"],
                                    self.c.workspace_id)
        self.assertEqual(record["state"], "applied")
        self.assertIsNotNone(record["finished_at"])
        # A second sweep finds nothing left to do and writes nothing twice.
        self.assertEqual(self.c.code.resume_writes(), [])

    def test_a_restart_with_nothing_outstanding_does_nothing(self):
        self.assertEqual(self.restart().resumed_writes, [])
        self.assertEqual(self.on_disk(), ORIGINAL)

    def test_startup_resumes_without_being_asked(self):
        self.approved_operation(("alpha.py",))
        fresh = self.restart()
        self.assertEqual([item["state"] for item in fresh.resumed_writes],
                         ["applied"])

    def test_a_full_access_write_is_also_recorded_durably(self):
        """Full access skips the approval, not the record."""
        self.c.code.set_mode(self.repo_id, "full")
        proposal = self.proposal(("alpha.py",))
        result = self.c.code.apply(self.repo_id, proposal["proposal_id"])
        self.assertEqual(result["state"], "applied")
        record = db.write_operation(self.c.conn, result["operation_id"],
                                    self.c.workspace_id)
        self.assertIsNone(record["approval_id"])
        self.assertEqual(record["state"], "applied")


if __name__ == "__main__":                                    # pragma: no cover
    unittest.main()
