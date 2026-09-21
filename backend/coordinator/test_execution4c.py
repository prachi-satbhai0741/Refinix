"""Offline checks for Execution 4C — local apply, backups and Undo.

Synthetic repositories in a temporary directory, temporary databases, and a
fake model. No live model call, no worker contact, no Kubernetes, no network.

    python3 -m unittest backend.coordinator.test_execution4c -v
"""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.contracts import profiles
from backend.coordinator import (code_service, codeflow, db, models, policy, repo,
                                 runtime)
from backend.coordinator.code_service import (CodeError, TARGET_DISTRIBUTED,
                                              TARGET_LOCAL)
from backend.coordinator.server import Coordinator

ORIGINAL = "def exceeds(value, limit):\n    return value >= limit\n"
REPAIRED = "def exceeds(value, limit):\n    return value > limit\n"


class TestProposalEnvelope(unittest.TestCase):
    def selection(self, size):
        return [{"path": "large.py", "sha256": "a" * 64,
                 "text": "x" * size}]

    def test_output_scales_when_a_whole_file_replacement_fits(self):
        selected = self.selection(9_000)
        messages = codeflow.build_messages("change one line", selected)
        self.assertGreater(
            code_service.CodeService._proposal_output_limit(
                messages, selected, profiles.PROFILES[1]),
            code_service.PROPOSAL_NUM_PREDICT)

    def test_an_impossible_selection_fails_before_generation(self):
        selected = self.selection(30_000)
        messages = codeflow.build_messages("change one line", selected)
        with self.assertRaisesRegex(CodeError, "Select fewer or smaller files"):
            code_service.CodeService._proposal_output_limit(
                messages, selected, profiles.PROFILES[1])

    def test_format_repair_does_not_resend_the_selected_source(self):
        messages = codeflow.repair_messages('{"summary":"wrapped","edits":[]}')
        self.assertEqual([item["role"] for item in messages], ["system", "user"])
        self.assertNotIn("--- FILE", "\n".join(item["content"] for item in messages))


@unittest.skipUnless(repo.containment_supported(),
                     "this platform cannot contain repository access")
class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.home = Path(self.dir.name)
        self.state = self.home / "state" / "coordinator.sqlite3"
        self.state.parent.mkdir(parents=True)
        self.runtime_probe = patch.object(runtime, "probe", return_value={
            "reachable": True, "server_version": "0.32.14",
            "models": [runtime.MODEL],
            "digests": {runtime.MODEL:
                        models.entry_for(runtime.MODEL).manifest_sha256},
            "loaded": None, "error": None})
        self.runtime_probe.start()
        self.addCleanup(self.runtime_probe.stop)
        self.c = Coordinator(self.state)
        self.c.target_profile_id = profiles.MAC_M5_16GB
        self.addCleanup(self.c.conn.close)
        self.project = self.home / "project"
        self.project.mkdir()
        (self.project / "limits.py").write_text(ORIGINAL)
        (self.project / "notes.md").write_text("# notes\n")
        self.repo_id = self.c.code.connect(str(self.project))["repo_id"]
        self.set_mode("full")

    def set_mode(self, mode):
        self.c.conn.execute("UPDATE repositories SET mode=? WHERE repo_id=?",
                            (mode, self.repo_id))
        self.c.conn.commit()

    def disk(self, name="limits.py"):
        return (self.project / name).read_text()

    def reply(self, edits):
        """One model reply in the shape the parser expects.

        The base hash is part of the reply, which is what makes an edit
        against a stale read refusable rather than merely unlikely.
        """
        return json.dumps({
            "summary": "Fix the comparison.",
            "edits": [{
                "path": path,
                "base_sha256": hashlib.sha256(
                    (self.project / path).read_bytes()).hexdigest(),
                "content": content,
            } for path, content in edits],
        })

    def propose_local(self, edits=(("limits.py", REPAIRED),), paths=None,
                      conversation_id=None):
        """A local proposal, with the model faked and the worker unreachable."""
        with patch.object(code_service.CodeService, "_ask_model",
                          return_value=(self.reply(edits), False)):
            return self.c.code.propose(
                self.repo_id, "fix the comparison",
                list(paths or [p for p, _ in edits]),
                execution_target=TARGET_LOCAL,
                conversation_id=conversation_id)


class TestLocalGenerationIsExplicit(Base):
    def test_a_local_request_never_contacts_the_worker(self):
        with patch.object(self.c, "preflight") as preflight, \
                patch.object(self.c, "choose_route") as route, \
                patch.object(self.c, "worker_client") as client:
            proposal = self.propose_local()
        preflight.assert_not_called()
        route.assert_not_called()
        client.assert_not_called()
        self.assertEqual(proposal["execution_target"], TARGET_LOCAL)

    def test_a_local_proposal_owns_a_job_in_a_code_conversation(self):
        """Corrected after review: the local path used to leave job_id NULL,
        so the conversation id was accepted and silently dropped."""
        conversation = self.c.code.new_conversation("Fix the limits")
        proposal = self.propose_local(conversation_id=conversation["chat_id"])
        job_id = self.c.conn.execute(
            "SELECT job_id FROM proposals WHERE proposal_id=?",
            (proposal["proposal_id"],)).fetchone()["job_id"]
        self.assertIsNotNone(job_id)
        job = self.c.conn.execute(
            "SELECT chat_id, state FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        self.assertEqual(job["chat_id"], conversation["chat_id"])
        self.assertEqual(job["state"], "completed")
        attempt = self.c.conn.execute(
            "SELECT route_reason, relationship_id, state FROM attempts"
            " WHERE job_id=?", (job_id,)).fetchone()
        self.assertIn("this device", attempt["route_reason"])
        self.assertIsNone(attempt["relationship_id"])
        self.assertEqual(attempt["state"], "completed")

    def test_the_request_and_result_are_visible_in_that_conversation(self):
        conversation = self.c.code.new_conversation("Fix the limits")
        self.propose_local(conversation_id=conversation["chat_id"])
        rows = self.c.conn.execute(
            "SELECT role, text FROM messages WHERE chat_id=? ORDER BY created_at,"
            " rowid", (conversation["chat_id"],)).fetchall()
        self.assertEqual([r["role"] for r in rows], ["user", "assistant"])
        self.assertIn("fix the comparison", rows[0]["text"])

    def test_an_unreadable_model_reply_leaves_no_running_job(self):
        conversation = self.c.code.new_conversation("Bad reply", self.repo_id)
        with patch.object(code_service.CodeService, "_ask_model",
                          return_value=("not json", False)):
            with self.assertRaises(CodeError):
                self.c.code.propose(
                    self.repo_id, "fix it", ["limits.py"],
                    execution_target=TARGET_LOCAL,
                    conversation_id=conversation["chat_id"])
        rows = self.c.conn.execute(
            "SELECT state FROM jobs WHERE chat_id=?", (conversation["chat_id"],))
        self.assertEqual([row["state"] for row in rows], ["failed"])
        attempts = self.c.conn.execute(
            "SELECT state FROM attempts WHERE job_id IN"
            " (SELECT job_id FROM jobs WHERE chat_id=?)",
            (conversation["chat_id"],))
        self.assertEqual([row["state"] for row in attempts], ["failed"])

    def test_work_does_not_leak_between_conversations(self):
        first = self.c.code.new_conversation("First")
        second = self.c.code.new_conversation("Second")
        self.propose_local(conversation_id=first["chat_id"])
        owned = lambda chat: [r["job_id"] for r in self.c.conn.execute(
            "SELECT job_id FROM jobs WHERE chat_id=?", (chat,))]
        self.assertEqual(len(owned(first["chat_id"])), 1)
        self.assertEqual(owned(second["chat_id"]), [])

    def test_an_unknown_target_is_refused_rather_than_guessed(self):
        with self.assertRaises(CodeError) as caught:
            self.c.code.propose(self.repo_id, "x", ["limits.py"],
                                execution_target="somewhere_else")
        self.assertEqual(caught.exception.code, "unknown_target")

    def test_a_proposal_with_no_recorded_target_is_treated_as_distributed(self):
        """Fails closed: nothing written before 4C becomes locally applicable
        just because its target is missing."""
        proposal = self.propose_local()
        self.c.conn.execute("UPDATE proposals SET execution_target='distributed'"
                            " WHERE proposal_id=?", (proposal["proposal_id"],))
        self.c.conn.commit()
        with self.assertRaises(CodeError) as caught:
            self.c.code.apply(self.repo_id, proposal["proposal_id"])
        self.assertEqual(caught.exception.code, "validation_required")
        self.assertEqual(self.disk(), ORIGINAL)


class TestLocalValidationTruth(Base):
    def test_no_validation_row_is_written_for_a_local_proposal(self):
        proposal = self.propose_local()
        self.c.code.apply(self.repo_id, proposal["proposal_id"])
        rows = self.c.conn.execute(
            "SELECT COUNT(*) c FROM proposal_validations WHERE proposal_id=?",
            (proposal["proposal_id"],)).fetchone()
        self.assertEqual(rows["c"], 0)

    def test_the_state_says_not_sandbox_tested(self):
        self.propose_local()
        state = self.c.code.state(self.repo_id)
        self.assertEqual(state["execution_target"], TARGET_LOCAL)
        self.assertIsNone(state["validation"])
        self.assertEqual(state["validation_note"],
                         code_service.LOCAL_VALIDATION_NOTE)
        self.assertIn("Not sandbox tested", state["validation_note"])

    def test_a_borrowed_passing_validation_is_refused(self):
        """A passing row against a local proposal means a digest came from
        somewhere it did not belong."""
        proposal = self.propose_local()
        db.record_validation(
            self.c.conn, workspace_id=self.c.workspace_id,
            proposal_id=proposal["proposal_id"], job_id=None, attempt_id=None,
            node_id="fake", patch_sha256=proposal["digest"],
            # Every field `record_validation` requires before it will write a
            # passing row, so this really is the hostile case.
            result={"observed": True, "job_state": "succeeded", "passed": True,
                    "result": {"passed": True, "tests_run": 3, "exit_status": 0}},
            detail="borrowed")
        with self.assertRaises(CodeError) as caught:
            self.c.code.apply(self.repo_id, proposal["proposal_id"])
        self.assertEqual(caught.exception.code, "validation_mismatch")
        self.assertEqual(self.disk(), ORIGINAL)


class TestBackupsBeforeAnyWrite(Base):
    def test_every_backup_exists_before_the_first_file_is_replaced(self):
        seen = {}
        real = repo.replace_text_file

        def watched(root, relative, **kwargs):
            seen[relative] = len(db.proposal_backups(
                self.c.conn, self.proposal_id, self.c.workspace_id))
            return real(root, relative, **kwargs)

        proposal = self.propose_local(
            (("limits.py", REPAIRED), ("notes.md", "# changed\n")))
        self.proposal_id = proposal["proposal_id"]
        with patch.object(repo, "replace_text_file", watched):
            self.c.code.apply(self.repo_id, self.proposal_id)
        # Both backups were already stored when the first write happened.
        self.assertEqual(set(seen), {"limits.py", "notes.md"})
        self.assertTrue(all(count == 2 for count in seen.values()), seen)

    def test_a_failed_backup_writes_nothing_and_keeps_the_proposal(self):
        proposal = self.propose_local()
        with patch.object(db, "record_backup",
                          side_effect=db.BackupError("disk full")):
            with self.assertRaises(CodeError) as caught:
                self.c.code.apply(self.repo_id, proposal["proposal_id"])
        self.assertEqual(caught.exception.code, "backup_failed")
        self.assertEqual(self.disk(), ORIGINAL)
        state = db.get_proposal(self.c.conn, proposal["proposal_id"],
                                self.c.workspace_id)["state"]
        self.assertNotEqual(state, "applied")

    def test_a_restart_cannot_write_a_file_whose_original_was_never_copied(self):
        """The hole this guards: `resume_writes` reaches the write path
        directly, so a crash between creating the operation and taking the
        backup must not let recovery replace an uncopied file."""
        proposal = self.propose_local()
        # An authorised operation exists, and no backup has been taken.
        operation = db.create_write_operation(
            self.c.conn, workspace_id=self.c.workspace_id, repo_id=self.repo_id,
            proposal_id=proposal["proposal_id"], action=policy.ACTION_WRITE,
            action_sha256=proposal["digest"],
            edits=[{"path": e["path"], "edit_id": e["edit_id"],
                    "base_sha256": e["base_sha256"],
                    "after_sha256": e["after_sha256"]}
                   for e in db.proposal_edit_contents(
                       self.c.conn, proposal["proposal_id"])])
        self.assertEqual(db.proposal_backups(
            self.c.conn, proposal["proposal_id"], self.c.workspace_id), [])

        with patch.object(db, "record_backup",
                          side_effect=db.BackupError("store unavailable")):
            resumed = self.c.code.resume_writes()
        # Nothing was written, and the operation ended rather than retrying
        # forever against a store that is not working.
        self.assertEqual(self.disk(), ORIGINAL)
        self.assertTrue(any(r.get("state") == "failed" for r in resumed), resumed)
        self.assertEqual(operation["proposal_id"], proposal["proposal_id"])

    def test_a_recovered_operation_backs_up_before_it_writes(self):
        proposal = self.propose_local()
        db.create_write_operation(
            self.c.conn, workspace_id=self.c.workspace_id, repo_id=self.repo_id,
            proposal_id=proposal["proposal_id"], action=policy.ACTION_WRITE,
            action_sha256=proposal["digest"],
            edits=[{"path": e["path"], "edit_id": e["edit_id"],
                    "base_sha256": e["base_sha256"],
                    "after_sha256": e["after_sha256"]}
                   for e in db.proposal_edit_contents(
                       self.c.conn, proposal["proposal_id"])])
        self.assertEqual(db.proposal_backups(
            self.c.conn, proposal["proposal_id"], self.c.workspace_id), [])
        self.c.code.resume_writes()
        self.assertEqual(self.disk(), REPAIRED)
        self.assertEqual([row["path"] for row in db.proposal_backups(
            self.c.conn, proposal["proposal_id"], self.c.workspace_id)],
            ["limits.py"])

    def test_backups_are_never_written_inside_the_project(self):
        proposal = self.propose_local()
        self.c.code.apply(self.repo_id, proposal["proposal_id"])
        inside = [p.name for p in self.project.rglob("*") if p.is_file()]
        self.assertEqual(sorted(inside), ["limits.py", "notes.md"])
        store = db.backups_root(self.state)
        self.assertTrue(any(store.glob("*.bak")))
        self.assertNotIn(str(self.project), str(store))

    def test_only_the_proposal_s_own_files_are_backed_up(self):
        proposal = self.propose_local()
        self.c.code.apply(self.repo_id, proposal["proposal_id"])
        paths = [row["path"] for row in db.proposal_backups(
            self.c.conn, proposal["proposal_id"], self.c.workspace_id)]
        self.assertEqual(paths, ["limits.py"])


class TestApplyingLocally(Base):
    def test_the_applied_file_is_exactly_what_was_reviewed(self):
        proposal = self.propose_local()
        reviewed = db.proposal_edit_contents(
            self.c.conn, proposal["proposal_id"])[0]["content"]
        result = self.c.code.apply(self.repo_id, proposal["proposal_id"])
        self.assertEqual(result["state"], "applied")
        self.assertEqual(self.disk(), reviewed)
        self.assertEqual(self.disk(), REPAIRED)

    def test_a_file_changed_since_review_is_left_alone(self):
        proposal = self.propose_local()
        (self.project / "limits.py").write_text("someone else edited this\n")
        with self.assertRaises(CodeError) as caught:
            self.c.code.apply(self.repo_id, proposal["proposal_id"])
        self.assertEqual(caught.exception.code, "backup_failed")
        self.assertEqual(self.disk(), "someone else edited this\n")

    def test_partial_mode_requires_an_approval_before_writing(self):
        self.set_mode("partial")
        proposal = self.propose_local()
        with self.assertRaises(code_service.ApprovalNeeded):
            self.c.code.apply(self.repo_id, proposal["proposal_id"])
        self.assertEqual(self.disk(), ORIGINAL)

    def test_rejecting_writes_nothing(self):
        self.set_mode("partial")
        proposal = self.propose_local()
        try:
            self.c.code.apply(self.repo_id, proposal["proposal_id"])
        except code_service.ApprovalNeeded as needed:
            self.c.code.decide(needed.approval["approval_id"], False,
                               needed.approval["conversation_id"])
        self.assertEqual(self.disk(), ORIGINAL)
        self.assertEqual(list(db.backups_root(self.state).glob("*.bak")), [])

    def test_reject_marks_the_proposal_and_blocks_apply(self):
        conversation = self.c.code.new_conversation("Reject this", self.repo_id)
        proposal = self.propose_local(conversation_id=conversation["chat_id"])
        result = self.c.code.reject(
            self.repo_id, proposal["proposal_id"], conversation["chat_id"])
        self.assertEqual(result["state"], "rejected")
        with self.assertRaises(CodeError) as caught:
            self.c.code.apply(self.repo_id, proposal["proposal_id"])
        self.assertEqual(caught.exception.code, "not_pending")
        self.assertEqual(self.disk(), ORIGINAL)

    def test_a_model_proposed_unselected_path_is_refused(self):
        with self.assertRaises(CodeError):
            self.propose_local(edits=(("notes.md", "sneaky\n"),),
                               paths=["limits.py"])
        self.assertEqual(self.disk("notes.md"), "# notes\n")

    def test_a_later_file_failing_is_reported_honestly(self):
        proposal = self.propose_local(
            (("limits.py", REPAIRED), ("notes.md", "# changed\n")))
        real = repo.replace_text_file

        def fail_second(root, relative, **kwargs):
            if relative == "notes.md":
                raise repo.RepositoryError("unreadable", "device error")
            return real(root, relative, **kwargs)

        with patch.object(repo, "replace_text_file", fail_second):
            result = self.c.code.apply(self.repo_id, proposal["proposal_id"])
        self.assertEqual(result["applied"], 1)
        self.assertEqual(result["total"], 2)
        self.assertNotEqual(result["state"], "applied")
        self.assertEqual(self.disk(), REPAIRED)
        self.assertEqual(self.disk("notes.md"), "# notes\n")


class TestUndo(Base):
    def applied(self, edits=(("limits.py", REPAIRED),)):
        proposal = self.propose_local(edits)
        self.c.code.apply(self.repo_id, proposal["proposal_id"])
        return proposal

    def test_undo_restores_the_exact_original_bytes(self):
        before = (self.project / "limits.py").read_bytes()
        proposal = self.applied()
        self.assertEqual(self.disk(), REPAIRED)
        result = self.c.code.undo(self.repo_id, proposal["proposal_id"])
        self.assertTrue(result["complete"])
        self.assertEqual((self.project / "limits.py").read_bytes(), before)

    def test_undo_refuses_to_discard_a_later_human_change(self):
        proposal = self.applied()
        (self.project / "limits.py").write_text("a person edited this after\n")
        result = self.c.code.undo(self.repo_id, proposal["proposal_id"])
        self.assertFalse(result["complete"])
        self.assertEqual(result["files"][0]["state"], "rejected_stale")
        self.assertEqual(self.disk(), "a person edited this after\n")

    def test_a_partially_applied_change_can_still_be_undone(self):
        """Some files really did change. Those are exactly the ones a person
        needs back, and a file that was never written is reported as such
        rather than blamed on a later edit."""
        proposal = self.propose_local(
            (("limits.py", REPAIRED), ("notes.md", "# changed\n")))
        real = repo.replace_text_file

        def fail_second(root, relative, **kwargs):
            if relative == "notes.md":
                raise repo.RepositoryError("unreadable", "device error")
            return real(root, relative, **kwargs)

        with patch.object(repo, "replace_text_file", fail_second):
            outcome = self.c.code.apply(self.repo_id, proposal["proposal_id"])
        self.assertEqual(outcome["state"], "partially_applied")
        self.assertTrue(self.c.code.state(self.repo_id)["can_undo"])

        result = self.c.code.undo(self.repo_id, proposal["proposal_id"])
        by_path = {f["path"]: f["state"] for f in result["files"]}
        self.assertEqual(by_path["limits.py"], "restored")
        self.assertEqual(by_path["notes.md"], "unchanged")
        self.assertEqual(self.disk(), ORIGINAL)
        self.assertEqual(self.disk("notes.md"), "# notes\n")

    def test_undo_restores_only_this_proposal_s_files(self):
        proposal = self.applied()
        (self.project / "notes.md").write_text("# untouched by the proposal\n")
        self.c.code.undo(self.repo_id, proposal["proposal_id"])
        self.assertEqual(self.disk("notes.md"), "# untouched by the proposal\n")

    def test_undo_is_recorded_and_survives_a_restart(self):
        proposal = self.applied()
        self.c.code.undo(self.repo_id, proposal["proposal_id"])
        self.c.conn.close()
        with patch("backend.coordinator.runtime.probe",
                   return_value={"reachable": True, "models": []}):
            reopened = Coordinator(self.state)
        self.addCleanup(reopened.conn.close)
        rows = reopened.conn.execute(
            "SELECT detail_json FROM code_audit WHERE action=? ORDER BY occurred_at",
            (policy.ACTION_WRITE,)).fetchall()
        blob = " ".join(row["detail_json"] or "" for row in rows)
        self.assertIn("undo", blob)
        self.assertIn(proposal["proposal_id"], blob)

    def test_a_distributed_proposal_is_not_undoable_here(self):
        proposal = self.propose_local()
        self.c.conn.execute("UPDATE proposals SET execution_target='distributed'"
                            " WHERE proposal_id=?", (proposal["proposal_id"],))
        self.c.conn.commit()
        with self.assertRaises(CodeError) as caught:
            self.c.code.undo(self.repo_id, proposal["proposal_id"])
        self.assertEqual(caught.exception.code, "not_local")

    def test_undo_never_shells_out_to_git(self):
        source = Path("backend/coordinator/code_service.py").read_text()
        self.assertNotIn("subprocess", source)
        self.assertNotIn("git ", source.lower().split("undo")[-1][:2000])


class TestDistributedPathUnchanged(Base):
    def test_a_distributed_proposal_still_needs_an_observed_pass(self):
        proposal = self.propose_local()
        self.c.conn.execute("UPDATE proposals SET execution_target=? WHERE proposal_id=?",
                            (TARGET_DISTRIBUTED, proposal["proposal_id"]))
        self.c.conn.commit()
        with self.assertRaises(CodeError) as caught:
            self.c.code.apply(self.repo_id, proposal["proposal_id"])
        self.assertEqual(caught.exception.code, "validation_required")
        self.assertEqual(self.disk(), ORIGINAL)

    def test_an_unobserved_or_failing_validation_still_blocks(self):
        proposal = self.propose_local()
        self.c.conn.execute("UPDATE proposals SET execution_target=? WHERE proposal_id=?",
                            (TARGET_DISTRIBUTED, proposal["proposal_id"]))
        self.c.conn.commit()
        for observed, passed in ((False, False), (True, False)):
            with self.subTest(observed=observed, passed=passed):
                db.record_validation(
                    self.c.conn, workspace_id=self.c.workspace_id,
                    proposal_id=proposal["proposal_id"], job_id=None,
                    attempt_id=None, node_id="fake",
                    patch_sha256=proposal["digest"],
                    result={"observed": observed,
                            "result": {"passed": passed, "tests_run": 0,
                                       "exit_status": 1}})
                with self.assertRaises(CodeError):
                    self.c.code.apply(self.repo_id, proposal["proposal_id"])
                self.assertEqual(self.disk(), ORIGINAL)

    def test_sandbox_validation_still_requires_the_paired_worker(self):
        proposal = self.propose_local()
        with patch.object(self.c, "choose_route") as route:
            with self.assertRaises(CodeError) as caught:
                self.c.code.validate(self.repo_id, proposal["proposal_id"])
        self.assertEqual(caught.exception.code, "not_distributed")
        route.assert_not_called()


class TestDeniedActionsUnchanged(unittest.TestCase):
    def test_full_access_still_denies_everything_it_always_did(self):
        for action in ("file.create", "file.delete", "file.rename", "file.chmod",
                       "command.run", "git.write", "package.install",
                       "network.enable", "path.outside_root"):
            with self.subTest(action=action):
                self.assertTrue(policy.decide("full", action).denied)

    def test_full_carries_the_warning_that_names_the_missing_sandbox(self):
        full = next(m for m in policy.mode_options() if m["id"] == "full")
        self.assertTrue(full["confirm"])
        self.assertIn("sandbox tests do not run", full["confirm_note"])
        self.assertIn("undo", full["confirm_note"].lower())


if __name__ == "__main__":
    unittest.main()


# --------------------------------------------------------------------------
# Review corrections
# --------------------------------------------------------------------------

class TestCorruptedTargetFailsClosed(Base):
    def corrupt(self, proposal, value="somewhere_else"):
        self.c.conn.execute("UPDATE proposals SET execution_target=?"
                            " WHERE proposal_id=?", (value, proposal["proposal_id"]))
        self.c.conn.commit()

    def test_an_unrecognised_target_stops_before_anything_happens(self):
        """It used to slip between two comparisons: not `distributed`, so no
        sandbox validation; not `this_device`, so no backup; and still able to
        reach the write loop."""
        proposal = self.propose_local()
        self.corrupt(proposal)
        with self.assertRaises(CodeError) as caught:
            self.c.code.apply(self.repo_id, proposal["proposal_id"])
        self.assertEqual(caught.exception.code, "unknown_target")
        self.assertEqual(self.disk(), ORIGINAL)
        self.assertEqual(db.proposal_backups(
            self.c.conn, proposal["proposal_id"], self.c.workspace_id), [])
        self.assertEqual(self.c.conn.execute(
            "SELECT COUNT(*) c FROM write_operations").fetchone()["c"], 0)

    def test_a_resumed_operation_with_a_corrupted_target_writes_nothing(self):
        proposal = self.propose_local()
        db.create_write_operation(
            self.c.conn, workspace_id=self.c.workspace_id, repo_id=self.repo_id,
            proposal_id=proposal["proposal_id"], action=policy.ACTION_WRITE,
            action_sha256=proposal["digest"],
            edits=[{"path": e["path"], "edit_id": e["edit_id"],
                    "base_sha256": e["base_sha256"],
                    "after_sha256": e["after_sha256"]}
                   for e in db.proposal_edit_contents(
                       self.c.conn, proposal["proposal_id"])])
        self.corrupt(proposal)
        resumed = self.c.code.resume_writes()
        self.assertEqual(self.disk(), ORIGINAL)
        self.assertTrue(any(r.get("state") == "failed" for r in resumed), resumed)

    def test_undo_refuses_a_corrupted_target(self):
        proposal = self.propose_local()
        self.corrupt(proposal)
        with self.assertRaises(CodeError) as caught:
            self.c.code.undo(self.repo_id, proposal["proposal_id"])
        self.assertEqual(caught.exception.code, "unknown_target")

    def test_validation_refuses_a_corrupted_target_before_worker_routing(self):
        proposal = self.propose_local()
        self.corrupt(proposal)
        with patch.object(self.c, "choose_route") as route:
            with self.assertRaises(CodeError) as caught:
                self.c.code.validate(self.repo_id, proposal["proposal_id"])
        self.assertEqual(caught.exception.code, "unknown_target")
        route.assert_not_called()

    def test_the_surface_still_loads_and_says_the_change_is_unusable(self):
        proposal = self.propose_local()
        self.corrupt(proposal)
        state = self.c.code.state(self.repo_id)
        self.assertIsNone(state["execution_target"])
        self.assertIsNone(state["validation"])
        self.assertIn("does not recognise", state["target_note"])
        self.assertFalse(state["can_undo"])


class TestBackupsAreProvedNotAssumed(Base):
    def prepared(self):
        proposal = self.propose_local()
        db.create_write_operation(
            self.c.conn, workspace_id=self.c.workspace_id, repo_id=self.repo_id,
            proposal_id=proposal["proposal_id"], action=policy.ACTION_WRITE,
            action_sha256=proposal["digest"],
            edits=[{"path": e["path"], "edit_id": e["edit_id"],
                    "base_sha256": e["base_sha256"],
                    "after_sha256": e["after_sha256"]}
                   for e in db.proposal_edit_contents(
                       self.c.conn, proposal["proposal_id"])])
        self.c.code.resume_writes()          # takes the backup and writes
        return proposal

    def stored_file(self, proposal):
        row = db.proposal_backups(self.c.conn, proposal["proposal_id"],
                                  self.c.workspace_id)[0]
        return db.backups_root(self.state) / row["stored_name"], row

    def test_a_deleted_backup_file_stops_a_resumed_write(self):
        """A row is not a backup. The file has to still be there."""
        proposal = self.propose_local()
        edits = db.proposal_edit_contents(self.c.conn, proposal["proposal_id"])
        db.record_backup(
            self.c.conn, db.backups_root(self.state),
            workspace_id=self.c.workspace_id, repo_id=self.repo_id,
            conversation_id=None, proposal_id=proposal["proposal_id"],
            proposal_digest=proposal["digest"], path="limits.py",
            original=ORIGINAL.encode(),
            original_sha256=edits[0]["base_sha256"],
            proposed_sha256=edits[0]["after_sha256"])
        stored, _row = self.stored_file(proposal)
        stored.unlink()
        with self.assertRaises(CodeError) as caught:
            self.c.code.apply(self.repo_id, proposal["proposal_id"])
        self.assertEqual(caught.exception.code, "backup_failed")
        self.assertEqual(self.disk(), ORIGINAL)

    def test_a_corrupted_backup_file_stops_a_resumed_write(self):
        proposal = self.propose_local()
        edits = db.proposal_edit_contents(self.c.conn, proposal["proposal_id"])
        db.record_backup(
            self.c.conn, db.backups_root(self.state),
            workspace_id=self.c.workspace_id, repo_id=self.repo_id,
            conversation_id=None, proposal_id=proposal["proposal_id"],
            proposal_digest=proposal["digest"], path="limits.py",
            original=ORIGINAL.encode(),
            original_sha256=edits[0]["base_sha256"],
            proposed_sha256=edits[0]["after_sha256"])
        stored, _row = self.stored_file(proposal)
        stored.write_bytes(b"not the original at all, and a different length")
        with self.assertRaises(CodeError) as caught:
            self.c.code.apply(self.repo_id, proposal["proposal_id"])
        self.assertEqual(caught.exception.code, "backup_failed")
        self.assertEqual(self.disk(), ORIGINAL)

    def test_a_racing_second_backup_is_a_clean_outcome_not_a_crash(self):
        """UNIQUE(proposal_id, path). The loser reuses the winner's copy, but
        only after verifying it — never an unhandled database error."""
        proposal = self.propose_local()
        edits = db.proposal_edit_contents(self.c.conn, proposal["proposal_id"])
        args = dict(workspace_id=self.c.workspace_id, repo_id=self.repo_id,
                    conversation_id=None, proposal_id=proposal["proposal_id"],
                    proposal_digest=proposal["digest"], path="limits.py",
                    original=ORIGINAL.encode(),
                    original_sha256=edits[0]["base_sha256"],
                    proposed_sha256=edits[0]["after_sha256"])
        store = db.backups_root(self.state)
        first = db.record_backup(self.c.conn, store, **args)
        second = db.record_backup(self.c.conn, store, **args)
        self.assertFalse(first.get("reused"))
        self.assertTrue(second["reused"])
        self.assertEqual(second["backup_id"], first["backup_id"])
        self.assertEqual(len(list(store.glob("*.bak"))), 1)

    def test_a_race_against_an_unusable_copy_fails_closed(self):
        proposal = self.propose_local()
        edits = db.proposal_edit_contents(self.c.conn, proposal["proposal_id"])
        args = dict(workspace_id=self.c.workspace_id, repo_id=self.repo_id,
                    conversation_id=None, proposal_id=proposal["proposal_id"],
                    proposal_digest=proposal["digest"], path="limits.py",
                    original=ORIGINAL.encode(),
                    original_sha256=edits[0]["base_sha256"],
                    proposed_sha256=edits[0]["after_sha256"])
        store = db.backups_root(self.state)
        db.record_backup(self.c.conn, store, **args)
        self.stored_file(proposal)[0].unlink()
        with self.assertRaises(db.BackupError):
            db.record_backup(self.c.conn, store, **args)

    def test_backup_names_symlinks_and_public_modes_fail_closed(self):
        proposal = self.prepared()
        stored, row = self.stored_file(proposal)
        outside = self.home / "outside.bak"
        outside.write_bytes(ORIGINAL.encode())
        with self.subTest("traversal"):
            hostile = {**row, "stored_name": "../outside.bak"}
            with self.assertRaises(db.BackupError):
                db.verify_backup(stored.parent, hostile)
        with self.subTest("permissions"):
            stored.chmod(0o644)
            with self.assertRaises(db.BackupError):
                db.verify_backup(stored.parent, row)
            stored.chmod(0o600)
        with self.subTest("symlink"):
            stored.unlink()
            stored.symlink_to(outside)
            with self.assertRaises(db.BackupError):
                db.verify_backup(stored.parent, row)

    def test_undo_and_cleanup_never_follow_a_corrupt_backup_path(self):
        proposal = self.prepared()
        stored, row = self.stored_file(proposal)
        outside = self.home / "outside.bak"
        outside.write_bytes(ORIGINAL.encode())
        stored.unlink()
        stored.symlink_to(outside)
        result = self.c.code.undo(self.repo_id, proposal["proposal_id"])
        self.assertEqual(result["files"][0]["state"], "failed")
        self.assertEqual(outside.read_bytes(), ORIGINAL.encode())
        self.c.conn.execute(
            "UPDATE write_backups SET stored_name='../outside.bak'"
            " WHERE backup_id=?", (row["backup_id"],))
        self.c.conn.commit()
        db.consume_backups(self.c.conn, stored.parent, proposal["proposal_id"],
                           self.c.workspace_id)
        self.assertTrue(outside.exists())


class TestProjectRemovalLocking(Base):
    def test_removal_closes_a_pending_project_approval(self):
        self.set_mode("ask")
        with self.assertRaises(code_service.ApprovalNeeded) as pending:
            self.c.code.view(self.repo_id, "limits.py")
        approval_id = pending.exception.approval["approval_id"]
        self.c.code.forget(self.repo_id)
        approval = db.public_approval(
            self.c.conn, approval_id, self.c.workspace_id)
        self.assertEqual(approval["decision"], "denied")

    def test_removal_is_refused_while_a_write_is_unfinished(self):
        proposal = self.propose_local()
        db.create_write_operation(
            self.c.conn, workspace_id=self.c.workspace_id, repo_id=self.repo_id,
            proposal_id=proposal["proposal_id"], action=policy.ACTION_WRITE,
            action_sha256=proposal["digest"],
            edits=[{"path": e["path"], "edit_id": e["edit_id"],
                    "base_sha256": e["base_sha256"],
                    "after_sha256": e["after_sha256"]}
                   for e in db.proposal_edit_contents(
                       self.c.conn, proposal["proposal_id"])])
        with self.assertRaises(CodeError) as caught:
            self.c.code.forget(self.repo_id)
        self.assertEqual(caught.exception.code, "busy")
        # Still connected, and the folder is untouched either way.
        self.assertTrue(self.c.code.repositories())
        self.assertEqual(self.disk(), ORIGINAL)

    def test_removal_reports_how_much_undo_it_puts_out_of_reach(self):
        proposal = self.propose_local()
        self.c.code.apply(self.repo_id, proposal["proposal_id"])
        first = self.c.code.forget(self.repo_id)
        self.assertTrue(first["confirmation_required"])
        self.assertTrue(self.c.code.repositories())
        result = self.c.code.forget(self.repo_id, discard_undo=True)
        self.assertEqual(result["undo_lost"], 1)
        self.assertTrue((self.project / "limits.py").exists())

    def test_removal_is_refused_while_undo_is_running(self):
        proposal = self.propose_local()
        with patch.object(self.c.code, "_undo") as undo:
            def during_undo(*_args):
                with self.assertRaises(CodeError) as caught:
                    self.c.code.forget(self.repo_id)
                self.assertEqual(caught.exception.code, "busy")
                return {"complete": False}
            undo.side_effect = during_undo
            self.c.code.undo(self.repo_id, proposal["proposal_id"])


class TestConversionKeepsEveryWord(unittest.TestCase):
    def test_a_long_line_becomes_several_paragraphs_rather_than_being_cut(self):
        from backend.coordinator import docflow
        line = " ".join(f"word{n}" for n in range(4000))
        blocks = docflow.conversion_blocks(line)
        self.assertGreater(len(blocks), 1)
        rejoined = " ".join(b.text for b in blocks)
        self.assertEqual(rejoined.split(), line.split())

    def test_an_answer_too_long_is_refused_rather_than_shortened(self):
        from backend.coordinator import docflow, docgen
        answer = "\n\n".join(f"paragraph {n}"
                             for n in range(docgen.MAX_PARAGRAPHS + 5))
        with self.assertRaises(docflow.WorkflowError) as caught:
            docflow.conversion_blocks(answer)
        self.assertEqual(caught.exception.code, "too_long")
