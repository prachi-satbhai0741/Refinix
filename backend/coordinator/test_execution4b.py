"""Offline checks for Execution 4B — the local Code workbench.

Synthetic repositories in a temporary directory, and a temporary database. No
model is called, no worker is contacted, and nothing outside the test's own
directory is read or written.

    python3 -m unittest backend.coordinator.test_execution4b -v
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.coordinator import db, policy, repo
from backend.coordinator.code_service import CodeError
from backend.coordinator.server import Coordinator


class TestViewPolicy(unittest.TestCase):
    def test_viewing_is_its_own_action(self):
        self.assertIn(policy.ACTION_VIEW, policy.SUPPORTED_ACTIONS)
        self.assertNotEqual(policy.ACTION_VIEW, policy.ACTION_READ)

    def test_partial_and_full_view_without_asking(self):
        for mode in ("partial", "full"):
            with self.subTest(mode=mode):
                self.assertEqual(policy.decide(mode, policy.ACTION_VIEW).outcome,
                                 policy.AUTOMATIC)

    def test_ask_requires_approval_and_says_it_is_not_a_send(self):
        decision = policy.decide("ask", policy.ACTION_VIEW)
        self.assertEqual(decision.outcome, policy.APPROVAL_REQUIRED)
        self.assertIn("does not send it to the model", decision.reason)

    def test_the_label_distinguishes_the_screen_from_the_model(self):
        self.assertIn("screen", policy.ACTION_LABELS[policy.ACTION_VIEW])
        self.assertIn("model", policy.ACTION_LABELS[policy.ACTION_READ])


@unittest.skipUnless(repo.descriptor_traversal_supported(),
                     "this platform cannot contain repository access")
class TestViewingThroughTheCoordinator(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.home = Path(self.dir.name)
        state = self.home / "state" / "coordinator.sqlite3"
        state.parent.mkdir(parents=True)
        with patch("backend.coordinator.runtime.probe",
                   return_value={"reachable": True, "models": []}):
            self.c = Coordinator(state)
        self.addCleanup(self.c.conn.close)
        self.project = self.home / "project"
        (self.project / "pkg").mkdir(parents=True)
        (self.project / "README.md").write_text("one\ntwo\nthree\n")
        (self.project / "pkg" / "limits.py").write_text("VALUE = 7.1\n")
        self.repo_id = self.c.code.connect(str(self.project))["repo_id"]

    def set_mode(self, mode):
        self.c.conn.execute("UPDATE repositories SET mode=? WHERE repo_id=?",
                            (mode, self.repo_id))
        self.c.conn.commit()

    def test_a_file_is_returned_as_lines_with_no_absolute_path(self):
        self.set_mode("partial")
        result = self.c.code.view(self.repo_id, "README.md")
        self.assertEqual(result["lines"][:3], ["one", "two", "three"])
        self.assertEqual(result["path"], "README.md")
        blob = repr(result)
        self.assertNotIn(str(self.project), blob)
        self.assertNotIn(str(self.home), blob)

    def test_the_reply_states_that_nothing_was_sent_to_the_model(self):
        self.set_mode("partial")
        result = self.c.code.view(self.repo_id, "pkg/limits.py")
        self.assertFalse(result["sent_to_model"])
        self.assertIn("has not been sent to the model", result["note"])

    def test_ask_mode_asks_before_the_file_is_returned(self):
        self.set_mode("ask")
        from backend.coordinator import code_service
        with self.assertRaises(code_service.ApprovalNeeded) as caught:
            self.c.code.view(self.repo_id, "README.md")
        self.assertEqual(caught.exception.approval["action"], policy.ACTION_VIEW)

    def test_a_path_outside_the_project_is_refused(self):
        self.set_mode("full")
        for path in ("../secret.txt", "/etc/passwd", "pkg/../../outside.txt"):
            with self.subTest(path=path):
                with self.assertRaises((CodeError, repo.RepositoryError)):
                    self.c.code.view(self.repo_id, path)

    def test_binary_and_missing_files_fail_with_their_own_reasons(self):
        self.set_mode("full")
        (self.project / "blob.bin").write_bytes(b"\x00\x01\x02")
        with self.assertRaises(CodeError) as binary:
            self.c.code.view(self.repo_id, "blob.bin")
        self.assertEqual(binary.exception.code, "binary")
        with self.assertRaises(CodeError) as missing:
            self.c.code.view(self.repo_id, "nope.md")
        self.assertEqual(missing.exception.code, "missing")

    def test_the_listing_returns_relative_paths_only(self):
        """The Explorer groups these into folders in the page. Nothing here
        may hand it a real location to group."""
        self.set_mode("full")
        listing = self.c.code.files(self.repo_id)
        for entry in listing["files"]:
            self.assertFalse(entry["path"].startswith("/"), entry["path"])
            self.assertNotIn(str(self.project), entry["path"])
            self.assertNotIn("..", entry["path"].split("/"))

    def test_removing_a_project_leaves_every_file_on_disk(self):
        before = {p.name: p.read_bytes() for p in self.project.rglob("*")
                  if p.is_file()}
        self.c.code.forget(self.repo_id)
        after = {p.name: p.read_bytes() for p in self.project.rglob("*")
                 if p.is_file()}
        self.assertEqual(before, after)
        self.assertTrue(self.project.exists())
        # Only the connection is gone.
        with self.assertRaises(CodeError) as caught:
            self.c.code.view(self.repo_id, "README.md")
        self.assertEqual(caught.exception.code, "unknown_repository")


class TestCodeConversations(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        state = Path(self.dir.name) / "state" / "coordinator.sqlite3"
        state.parent.mkdir(parents=True)
        with patch("backend.coordinator.runtime.probe",
                   return_value={"reachable": True, "models": []}):
            self.c = Coordinator(state)
        self.addCleanup(self.c.conn.close)

    def test_a_new_conversation_is_durable_and_identified(self):
        made = self.c.code.new_conversation("Fix the limits")
        self.assertTrue(made["chat_id"])
        self.assertEqual(made["title"], "Fix the limits")
        listed = self.c.code.conversations()
        self.assertIn(made["chat_id"], [c["chat_id"] for c in listed])

    def test_code_conversations_never_appear_in_ordinary_chat_history(self):
        self.c.code.new_conversation("Code work")
        db.create_chat(self.c.conn, self.c.workspace_id, "Ordinary chat")
        titles = [row["title"] for row in self.c.chats()]
        self.assertIn("Ordinary chat", titles)
        self.assertNotIn("Code work", titles)
        self.assertNotIn(db.CODE_CHAT_TITLE, titles)

    def test_code_conversations_are_absent_from_chat_search(self):
        self.c.code.new_conversation("Vibration limits")
        db.create_chat(self.c.conn, self.c.workspace_id, "Vibration notes")
        found = [row["title"] for row in
                 db.search(self.c.conn, "Vibration")]
        self.assertIn("Vibration notes", found)
        self.assertNotIn("Vibration limits", found)

    def test_a_job_belongs_to_exactly_one_conversation(self):
        first = self.c.code.new_conversation("First")
        second = self.c.code.new_conversation("Second")
        job_a = self.c.code._code_job("do a", first["chat_id"])
        job_b = self.c.code._code_job("do b", second["chat_id"])
        owner = lambda job: self.c.conn.execute(
            "SELECT chat_id FROM jobs WHERE job_id=?", (job,)).fetchone()["chat_id"]
        self.assertEqual(owner(job_a), first["chat_id"])
        self.assertEqual(owner(job_b), second["chat_id"])
        self.assertNotEqual(owner(job_a), owner(job_b))

    def test_an_ordinary_chat_id_is_refused_as_a_code_conversation(self):
        """Otherwise code jobs would land in the person's Chat history."""
        chat = db.create_chat(self.c.conn, self.c.workspace_id, "Ordinary")
        with self.assertRaises(CodeError) as caught:
            self.c.code.conversation(chat)
        self.assertEqual(caught.exception.code, "unknown_conversation")

    def test_history_reports_a_disconnected_project_as_unavailable(self):
        self.c.conn.execute(
            "INSERT INTO chats(chat_id, workspace_id, title, pinned, created_at,"
            " updated_at, kind, repo_id) VALUES ('c1',?,?,0,'t','t',?,'gone')",
            (self.c.workspace_id, "Old work", db.CODE_KIND))
        self.c.conn.commit()
        entry = next(c for c in self.c.code.conversations() if c["chat_id"] == "c1")
        self.assertEqual(entry["repo_id"], "gone")
        self.assertIsNone(entry["repo_name"])
        self.assertFalse(entry["project_available"])

    def test_history_that_predates_conversations_still_resolves(self):
        """The workspace conversation is used when none is named, so old jobs
        keep working rather than being back-filled with a guess."""
        job = self.c.code._code_job("legacy request")
        chat_id = self.c.conn.execute(
            "SELECT chat_id FROM jobs WHERE job_id=?", (job,)).fetchone()["chat_id"]
        kind = self.c.conn.execute(
            "SELECT kind FROM chats WHERE chat_id=?", (chat_id,)).fetchone()["kind"]
        self.assertEqual(kind, db.CODE_KIND)


class TestMigrationIsAdditive(unittest.TestCase):
    def test_an_existing_database_gains_the_columns_without_losing_history(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        state = Path(directory.name) / "state" / "coordinator.sqlite3"
        state.parent.mkdir(parents=True)
        with patch("backend.coordinator.runtime.probe",
                   return_value={"reachable": True, "models": []}):
            first = Coordinator(state)
        chat = db.create_chat(first.conn, first.workspace_id, "Existing history")
        db.add_message(first.conn, chat, "user", "an existing message")
        legacy_code = db.code_chat(first.conn, first.workspace_id)
        first.conn.close()

        # Reopening runs the migration again; nothing is rewritten or guessed.
        with patch("backend.coordinator.runtime.probe",
                   return_value={"reachable": True, "models": []}):
            second = Coordinator(state)
        self.addCleanup(second.conn.close)
        titles = [row["title"] for row in second.chats()]
        self.assertIn("Existing history", titles)
        self.assertNotIn(db.CODE_CHAT_TITLE, titles)
        kind = second.conn.execute(
            "SELECT kind FROM chats WHERE chat_id=?", (legacy_code,)).fetchone()["kind"]
        self.assertEqual(kind, db.CODE_KIND)
        rows = second.conn.execute(
            "SELECT COUNT(*) c FROM messages WHERE chat_id=?", (chat,)).fetchone()
        self.assertEqual(rows["c"], 1)


class TestNoLocalWriteWasAdded(unittest.TestCase):
    def test_applying_still_requires_a_passing_sandbox_validation(self):
        source = Path("backend/coordinator/code_service.py").read_text()
        self.assertIn("validation_required", source)
        self.assertIn("Run sandbox validation and get a current passing result",
                      source)

    def test_no_mode_enables_a_write_without_review(self):
        for mode in policy.MODES:
            with self.subTest(mode=mode):
                self.assertIn(policy.decide(mode, policy.ACTION_WRITE).outcome,
                              (policy.AUTOMATIC, policy.APPROVAL_REQUIRED))
        # Creating, deleting and renaming stay refused in every mode.
        for action in ("file.create", "file.delete", "file.rename"):
            with self.subTest(action=action):
                self.assertTrue(policy.decide("full", action).denied)


if __name__ == "__main__":
    unittest.main()


# --------------------------------------------------------------------------
# Review corrections
# --------------------------------------------------------------------------

class TestConversationScoping(TestCodeConversations):
    def test_a_fresh_conversation_does_not_inherit_the_project_s_proposal(self):
        """Unscoped state showed the project's last proposal in a brand new
        conversation, and a refresh could cross conversations."""
        import tempfile
        from pathlib import Path as _Path
        project = _Path(tempfile.mkdtemp()) / "project"
        project.mkdir()
        (project / "a.py").write_text("value = 1\n")
        repo_id = self.c.code.connect(str(project))["repo_id"]
        self.c.conn.execute("UPDATE repositories SET mode='full' WHERE repo_id=?",
                            (repo_id,))
        self.c.conn.commit()

        first = self.c.code.new_conversation("First")
        second = self.c.code.new_conversation("Second")
        job = self.c.code._code_job("do something", first["chat_id"])
        db.create_proposal(
            self.c.conn, workspace_id=self.c.workspace_id, repo_id=repo_id,
            job_id=job, attempt_id=None, request="do something",
            summary="s", digest="d" * 64,
            edits=[{"path": "a.py", "base_sha256": "b" * 64,
                    "after_sha256": "c" * 64, "content": "value = 2\n",
                    "diff": "-1\n+2"}],
            execution_target="this_device")

        self.assertIsNotNone(
            self.c.code.state(repo_id, first["chat_id"])["proposal"])
        self.assertIsNone(
            self.c.code.state(repo_id, second["chat_id"])["proposal"])

    def test_an_ordinary_chat_id_cannot_scope_code_state(self):
        chat = db.create_chat(self.c.conn, self.c.workspace_id, "Ordinary")
        with self.assertRaises(CodeError) as caught:
            self.c.code.state(None, chat)
        self.assertEqual(caught.exception.code, "unknown_conversation")

    def test_approvals_and_audit_stay_in_their_own_conversation(self):
        from backend.coordinator import code_service
        project = Path(self.dir.name) / "project"
        project.mkdir()
        (project / "a.py").write_text("value = 1\n")
        repo_id = self.c.code.connect(str(project))["repo_id"]
        self.c.conn.execute("UPDATE repositories SET mode='ask' WHERE repo_id=?",
                            (repo_id,))
        self.c.conn.commit()
        first = self.c.code.new_conversation("First", repo_id)
        second = self.c.code.new_conversation("Second", repo_id)
        approvals = []
        for conversation in (first, second):
            with self.assertRaises(code_service.ApprovalNeeded) as caught:
                self.c.code.view(repo_id, "a.py",
                                 conversation_id=conversation["chat_id"])
            approvals.append(caught.exception.approval["approval_id"])
        with self.assertRaises(CodeError) as missing:
            self.c.code.decide(approvals[0], True)
        self.assertEqual(missing.exception.code, "missing_conversation")
        with self.assertRaises(CodeError) as crossed:
            self.c.code.decide(approvals[0], True, second["chat_id"])
        self.assertEqual(crossed.exception.code, "mismatch")
        first_state = self.c.code.state(repo_id, first["chat_id"])
        second_state = self.c.code.state(repo_id, second["chat_id"])
        self.assertEqual([a["approval_id"] for a in first_state["pending_approvals"]],
                         approvals[:1])
        self.assertEqual([a["approval_id"] for a in second_state["pending_approvals"]],
                         approvals[1:])
        self.assertTrue(first_state["audit"])
        self.assertTrue(all(row["conversation_id"] == first["chat_id"]
                            for row in first_state["audit"]))

    def test_project_and_open_file_are_restored_without_a_fallback(self):
        project = Path(self.dir.name) / "project"
        project.mkdir()
        (project / "a.py").write_text("value = 1\n")
        repo_id = self.c.code.connect(str(project))["repo_id"]
        conversation = self.c.code.new_conversation("Work")
        saved = self.c.code.update_conversation(
            conversation["chat_id"], repo_id, "a.py")
        self.assertEqual(saved["open_path"], "a.py")
        state = self.c.code.state(None, conversation["chat_id"])
        self.assertEqual(state["active"], repo_id)
        self.assertEqual(state["conversation"]["open_path"], "a.py")
        self.c.code.forget(repo_id)
        unavailable = self.c.code.state(None, conversation["chat_id"])
        self.assertIsNone(unavailable["active"])
