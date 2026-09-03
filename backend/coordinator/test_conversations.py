"""Offline checks for rename, search, drafts, pin, delete and export."""

import tempfile
import unittest
from pathlib import Path

from backend.coordinator import db


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.conn = db.connect(Path(self.dir.name) / "s.sqlite3")
        self.ws = db.new_id()

    def tearDown(self):
        self.conn.close()
        self.dir.cleanup()

    def chat(self, title):
        return db.create_chat(self.conn, self.ws, title)


class TestRename(Base):
    def test_trims_and_persists(self):
        c = self.chat("old")
        self.assertEqual(db.rename_chat(self.conn, c, "  new title  "), "new title")
        row = self.conn.execute("SELECT title FROM chats WHERE chat_id=?", (c,)).fetchone()
        self.assertEqual(row["title"], "new title")

    def test_empty_title_rejected(self):
        c = self.chat("keep me")
        with self.assertRaises(ValueError):
            db.rename_chat(self.conn, c, "   ")
        self.assertEqual(
            self.conn.execute("SELECT title FROM chats WHERE chat_id=?", (c,)).fetchone()["title"],
            "keep me")

    def test_bounded_to_120(self):
        c = self.chat("x")
        self.assertEqual(len(db.rename_chat(self.conn, c, "y" * 400)), 120)

    def test_unknown_chat(self):
        with self.assertRaises(KeyError):
            db.rename_chat(self.conn, db.new_id(), "nope")

    def test_messages_untouched(self):
        c = self.chat("a")
        db.add_message(self.conn, c, "user", "content stays")
        db.rename_chat(self.conn, c, "b")
        rows = self.conn.execute("SELECT text FROM messages WHERE chat_id=?", (c,)).fetchall()
        self.assertEqual([r["text"] for r in rows], ["content stays"])


class TestSearch(Base):
    def test_finds_titles_and_messages(self):
        c = self.chat("Pump inspection")
        db.add_message(self.conn, c, "user", "the bearing is worn")
        self.assertTrue(db.search(self.conn, "Pump"))
        self.assertTrue(db.search(self.conn, "bearing"))

    def test_percent_is_literal_not_a_wildcard(self):
        self.chat("100% throughput")
        self.chat("unrelated conversation")
        hits = db.search(self.conn, "100%")
        self.assertEqual([h["title"] for h in hits], ["100% throughput"],
                         "% must not behave as a LIKE wildcard")

    def test_underscore_is_literal(self):
        self.chat("snake_case name")
        self.chat("snakeXcase name")
        hits = db.search(self.conn, "snake_case")
        self.assertEqual([h["title"] for h in hits], ["snake_case name"])

    def test_unicode(self):
        self.chat("मराठी तपासणी")
        self.assertTrue(db.search(self.conn, "तपासणी"))

    def test_case_insensitive(self):
        self.chat("Valve Report")
        self.assertTrue(db.search(self.conn, "valve"))

    def test_empty_query_returns_nothing(self):
        self.chat("something")
        self.assertEqual(db.search(self.conn, "   "), [])

    def test_reaches_beyond_the_sidebar_page(self):
        """Search must cover chats outside the sidebar's first 100 rows."""
        for i in range(120):
            self.chat(f"conversation {i}")
        self.chat("needle in the haystack")
        self.assertTrue(any("needle" in h["title"] for h in db.search(self.conn, "needle")))

    def test_drafts_are_not_searchable(self):
        c = self.chat("a chat")
        db.set_draft(self.conn, c, "secret unsent draft")
        self.assertEqual(db.search(self.conn, "unsent"), [])


class TestDrafts(Base):
    def test_round_trip_and_isolation(self):
        a, b = self.chat("a"), self.chat("b")
        db.set_draft(self.conn, a, "draft for a")
        self.assertEqual(db.get_draft(self.conn, a), "draft for a")
        self.assertEqual(db.get_draft(self.conn, b), "")

    def test_new_chat_slot(self):
        db.set_draft(self.conn, db.NEW_CHAT_DRAFT, "typed before a chat existed")
        self.assertEqual(db.get_draft(self.conn, db.NEW_CHAT_DRAFT),
                         "typed before a chat existed")

    def test_only_the_submitted_version_is_cleared(self):
        c = self.chat("a")
        db.set_draft(self.conn, c, "newer typing")
        db.clear_draft_if_matches(self.conn, c, "what was sent")
        self.assertEqual(db.get_draft(self.conn, c), "newer typing",
                         "newer typing must survive a submit of an older version")

    def test_matching_version_is_cleared(self):
        c = self.chat("a")
        db.set_draft(self.conn, c, "sent this")
        db.clear_draft_if_matches(self.conn, c, "sent this")
        self.assertEqual(db.get_draft(self.conn, c), "")

    def test_delayed_save_cannot_resurrect_a_deleted_chat(self):
        c = self.chat("doomed")
        db.delete_chat(self.conn, c)
        db.set_draft(self.conn, c, "late save")
        self.assertEqual(db.get_draft(self.conn, c), "")
        self.assertIsNone(
            self.conn.execute("SELECT 1 FROM chats WHERE chat_id=?", (c,)).fetchone())


class TestPin(Base):
    def test_persists_and_unpin_keeps_history(self):
        c = self.chat("a")
        db.add_message(self.conn, c, "user", "kept")
        db.set_pinned(self.conn, c, True)
        self.assertEqual(
            self.conn.execute("SELECT pinned FROM chats WHERE chat_id=?", (c,)).fetchone()["pinned"], 1)
        db.set_pinned(self.conn, c, False)
        self.assertEqual(
            len(self.conn.execute("SELECT 1 FROM messages WHERE chat_id=?", (c,)).fetchall()), 1)

    def test_pinned_sort_before_unpinned(self):
        old = self.chat("older")
        new = self.chat("newer")
        db.set_pinned(self.conn, old, True)
        rows = self.conn.execute(
            "SELECT chat_id FROM chats ORDER BY pinned DESC, updated_at DESC").fetchall()
        self.assertEqual(rows[0]["chat_id"], old)
        self.assertIn(new, [r["chat_id"] for r in rows])


class TestDelete(Base):
    def test_removes_chat_and_its_records(self):
        c = self.chat("gone")
        db.add_message(self.conn, c, "user", "hi")
        job = db.create_job(self.conn, workspace_id=self.ws, chat_id=c, request="hi")
        db.delete_chat(self.conn, c)
        for table, column in (("chats", "chat_id"), ("messages", "chat_id"),
                              ("jobs", "chat_id"), ("drafts", "chat_id")):
            self.assertEqual(
                self.conn.execute(f"SELECT COUNT(*) n FROM {table} WHERE {column}=?",
                                  (c,)).fetchone()["n"], 0, table)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) n FROM events WHERE job_id=?",
                              (job,)).fetchone()["n"], 0)

    def test_other_chats_survive(self):
        keep, drop = self.chat("keep"), self.chat("drop")
        db.add_message(self.conn, keep, "user", "mine")
        db.delete_chat(self.conn, drop)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) n FROM messages WHERE chat_id=?",
                              (keep,)).fetchone()["n"], 1)


class TestExport(Base):
    def test_markdown_and_text(self):
        c = self.chat("Report")
        db.add_message(self.conn, c, "user", "question?")
        db.add_message(self.conn, c, "assistant", "**answer** with `code`")
        name, body = db.export_chat(self.conn, c, "md")
        self.assertTrue(name.endswith(".md"))
        self.assertIn("**answer**", body, "Markdown formatting is preserved")
        self.assertIn("question?", body)
        name_txt, body_txt = db.export_chat(self.conn, c, "txt")
        self.assertTrue(name_txt.endswith(".txt"))
        self.assertIn("question?", body_txt)

    def test_excludes_drafts_and_other_chats(self):
        c, other = self.chat("Mine"), self.chat("Theirs")
        db.add_message(self.conn, c, "user", "in scope")
        db.add_message(self.conn, other, "user", "OUT OF SCOPE")
        db.set_draft(self.conn, c, "UNSENT DRAFT")
        _, body = db.export_chat(self.conn, c, "md")
        self.assertIn("in scope", body)
        self.assertNotIn("OUT OF SCOPE", body)
        self.assertNotIn("UNSENT DRAFT", body)

    def test_filename_is_safe(self):
        c = self.chat("../../etc/passwd  weird:name")
        name, _ = db.export_chat(self.conn, c, "md")
        for bad in ("/", "\\", ":", ".."):
            self.assertNotIn(bad, name.replace(".md", ""), f"{bad!r} in {name!r}")

    def test_unknown_chat(self):
        with self.assertRaises(KeyError):
            db.export_chat(self.conn, db.new_id(), "md")

    def test_export_does_not_mutate(self):
        c = self.chat("Stable")
        db.add_message(self.conn, c, "user", "one")
        before = self.conn.execute("SELECT COUNT(*) n FROM messages").fetchone()["n"]
        db.export_chat(self.conn, c, "md")
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) n FROM messages").fetchone()["n"], before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
