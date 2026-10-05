"""Workspace ownership and schema admission (approved execution addendum).

Every refusal case builds the bad store first and asserts that the canonical
main, `-wal`, `-shm` and `-journal` files keep their existence, size,
modification time and bytes, and that no `-shm` appears. That is the defect the
old open path had: `connect` changed the journal mode, ran DDL and rewrote the
stored schema version before it ever asked whether it should.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.coordinator import db, ownership


def _record(path: Path) -> dict:
    out = {}
    for suffix in ("", "-wal", "-shm", "-journal"):
        p = Path(f"{path}{suffix}")
        if p.exists():
            data = p.read_bytes()
            out[suffix] = (p.stat().st_size, p.stat().st_mtime_ns,
                           hashlib.sha256(data).hexdigest())
        else:
            out[suffix] = None
    return out


def _sqlite(path: Path, statements: list[str], *, wal: bool = False) -> None:
    conn = sqlite3.connect(path)
    if wal:
        conn.execute("PRAGMA journal_mode=WAL")
    for statement in statements:
        conn.execute(statement)
    conn.commit()
    conn.close()


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name) / "root"
        self.root.mkdir()
        self.path = self.root / "coordinator.sqlite3"

    def tearDown(self):
        self.dir.cleanup()

    def assertRefusedUnchanged(self, code: str, *, owner=None):
        before = _record(self.path)
        with self.assertRaises(db.AdmissionRefused) as caught:
            db.admit(self.path, owner=owner)
        self.assertEqual(caught.exception.code, code, caught.exception.detail)
        self.assertEqual(_record(self.path), before)
        # connect() must refuse the same store without touching it either.
        with self.assertRaises(db.AdmissionRefused):
            db.connect(self.path, owner=owner)
        self.assertEqual(_record(self.path), before)
        if before["-shm"] is None:
            self.assertFalse(Path(f"{self.path}-shm").exists(),
                             "admission created a -shm file")
        # The private copy is always removed.
        leftovers = list((self.root / db.ADMISSION_DIRECTORY).glob("admission-*")) \
            if (self.root / db.ADMISSION_DIRECTORY).exists() else []
        self.assertEqual(leftovers, [])
        return caught.exception


class TestRefusals(Base):
    def test_foreign_sqlite_with_a_nonzero_user_version_is_refused(self):
        _sqlite(self.path, ["PRAGMA user_version = 99",
                            "CREATE TABLE notes(id INTEGER PRIMARY KEY, body TEXT)",
                            "INSERT INTO notes(body) VALUES ('someone else')"])
        self.assertRefusedUnchanged("foreign")

    def test_another_applications_id_is_refused_even_with_a_meta_table(self):
        _sqlite(self.path, ["PRAGMA application_id = 1234",
                            "CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)",
                            "INSERT INTO meta VALUES ('schema_version', '3')"])
        self.assertRefusedUnchanged("foreign")

    def test_a_newer_schema_without_a_wal_is_refused(self):
        conn = db.connect(self.path)
        conn.execute("UPDATE meta SET value=? WHERE key='schema_version'",
                     (str(db.SCHEMA_VERSION + 1),))
        conn.commit()
        conn.close()
        self.assertFalse(Path(f"{self.path}-wal").exists())
        refused = self.assertRefusedUnchanged("schema_newer")
        self.assertIn(str(db.SCHEMA_VERSION + 1), refused.detail)

    def test_a_newer_schema_held_only_in_a_non_empty_wal_is_refused(self):
        """The main file still says the old version; only the WAL knows."""
        source = Path(self.dir.name) / "live.sqlite3"
        conn = db.connect(source)
        conn.execute("PRAGMA wal_autocheckpoint=0")
        conn.execute("UPDATE meta SET value=? WHERE key='schema_version'",
                     (str(db.SCHEMA_VERSION + 1),))
        conn.commit()
        # A crash leaves the committed version in the WAL, not the main file.
        for suffix in ("", "-wal", "-shm"):
            shutil.copyfile(f"{source}{suffix}", f"{self.path}{suffix}")
        conn.close()
        self.assertGreater(Path(f"{self.path}-wal").stat().st_size, 32)
        self.assertRefusedUnchanged("schema_newer")

    def test_an_empty_database_another_program_versioned_is_refused(self):
        """No tables and no application id, but someone set a format version."""
        _sqlite(self.path, ["PRAGMA user_version = 7"])
        self.assertGreater(self.path.stat().st_size, 0)
        refused = self.assertRefusedUnchanged("foreign")
        self.assertIn("format 7", refused.detail)

    def test_an_empty_versioned_database_with_a_wal_is_refused(self):
        _sqlite(self.path, ["PRAGMA user_version = 3",
                            "CREATE TABLE t(x)", "DROP TABLE t"], wal=True)
        self.assertRefusedUnchanged("foreign")

    def test_metadata_that_cannot_be_read_is_a_typed_refusal(self):
        _sqlite(self.path, ["CREATE TABLE meta(k TEXT, v TEXT)",
                            "INSERT INTO meta VALUES ('schema_version', '3')"])
        refused = self.assertRefusedUnchanged("metadata")
        self.assertIn("no such column", refused.detail)

    def test_missing_metadata_is_refused(self):
        _sqlite(self.path, ["CREATE TABLE chats(chat_id TEXT)"])
        self.assertRefusedUnchanged("foreign")

    def test_an_invalid_format_version_is_refused(self):
        _sqlite(self.path, ["CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)",
                            "INSERT INTO meta VALUES ('schema_version', 'twelve')"])
        self.assertRefusedUnchanged("metadata")

    def test_a_corrupt_file_is_refused(self):
        self.path.write_bytes(b"SQLite format 3\x00" + os.urandom(4096))
        self.assertRefusedUnchanged("corrupt")

    def test_a_wal_without_its_database_is_ambiguous(self):
        Path(f"{self.path}-wal").write_bytes(b"x" * 64)
        self.assertRefusedUnchanged("ambiguous")
        self.assertFalse(self.path.exists(), "a new store was started anyway")

    def test_a_zero_length_database_beside_a_wal_is_ambiguous(self):
        self.path.write_bytes(b"")
        Path(f"{self.path}-wal").write_bytes(b"x" * 64)
        self.assertRefusedUnchanged("ambiguous")

    def test_a_hot_rollback_journal_is_refused(self):
        _sqlite(self.path, ["CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)",
                            "INSERT INTO meta VALUES ('schema_version', '12')"])
        Path(f"{self.path}-journal").write_bytes(b"journal" * 64)
        self.assertRefusedUnchanged("hot_journal")

    def test_too_little_space_for_the_private_copy_is_refused(self):
        db.connect(self.path).close()
        usage = shutil.disk_usage(self.root)._replace(free=1024)
        with patch("shutil.disk_usage", return_value=usage):
            self.assertRefusedUnchanged("insufficient_space")

    def test_a_writer_changing_the_store_during_the_copy_is_refused(self):
        db.connect(self.path).close()
        real_copy = shutil.copyfile
        changed = {"done": False}

        def copy_while_written(src, dst, *args, **kwargs):
            result = real_copy(src, dst, *args, **kwargs)
            if not changed["done"] and os.path.samefile(src, self.path):
                changed["done"] = True
                with open(self.path, "ab") as handle:   # another writer
                    handle.write(b"\0" * 1024)
            return result

        with patch("shutil.copyfile", side_effect=copy_while_written):
            with self.assertRaises(db.AdmissionRefused) as caught:
                db.admit(self.path)
        self.assertEqual(caught.exception.code, "active_writer")

    def test_an_unfinished_update_recovery_blocks_every_open(self):
        db.connect(self.path).close()
        journal = self.root / "recovery" / "update-journal.json"
        journal.parent.mkdir()
        journal.write_text(json.dumps({"state": "swapping"}), encoding="utf-8")
        self.assertRefusedUnchanged("recovery_pending")


class TestAdmitted(Base):
    def test_a_missing_store_is_new_and_nothing_is_created(self):
        admission = db.admit(self.path)
        self.assertEqual(admission.kind, "new")
        self.assertFalse(self.path.exists())
        self.assertFalse(Path(f"{self.path}-shm").exists())

    def test_a_legacy_store_without_an_application_id_is_admitted_then_marked(self):
        conn = db.connect(self.path)
        conn.execute("PRAGMA application_id = 0")
        conn.execute("UPDATE meta SET value='11' WHERE key='schema_version'")
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('workspace_id', 'w-legacy')")
        conn.commit()
        conn.close()
        admission = db.admit(self.path)
        self.assertEqual((admission.kind, admission.schema_version,
                          admission.workspace_id), ("existing", 11, "w-legacy"))
        conn = db.connect(self.path, admitted=admission)
        self.assertEqual(conn.execute("PRAGMA application_id").fetchone()[0],
                         db.APPLICATION_ID)
        self.assertEqual(conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],
            str(db.SCHEMA_VERSION))
        conn.close()

    def test_an_empty_unversioned_database_is_new(self):
        _sqlite(self.path, ["CREATE TABLE t(x)", "DROP TABLE t"])
        self.assertGreater(self.path.stat().st_size, 0)
        self.assertEqual(db.admit(self.path).kind, "new")

    def test_the_stored_version_is_never_lowered(self):
        conn = db.connect(self.path)
        version = conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
        conn.close()
        self.assertEqual(int(version), db.SCHEMA_VERSION)
        conn = db.connect(self.path)
        self.assertEqual(int(conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]),
            db.SCHEMA_VERSION)
        conn.close()


class TestOwnership(Base):
    def test_two_launches_on_one_explicit_state_path_exclude_each_other(self):
        first = ownership.WorkspaceLock.for_database(self.path)
        second = ownership.WorkspaceLock.for_database(self.path)
        try:
            self.assertIsNone(first.acquire())
            first.record(port=8771)
            self.assertEqual(second.acquire().get("port"), 8771)
            self.assertFalse(second.held)
        finally:
            first.release()
            second.release()

    def test_different_roots_stay_isolated(self):
        other = Path(self.dir.name) / "other" / "coordinator.sqlite3"
        a = ownership.WorkspaceLock.for_database(self.path)
        b = ownership.WorkspaceLock.for_database(other)
        try:
            self.assertIsNone(a.acquire())
            self.assertIsNone(b.acquire())
        finally:
            a.release()
            b.release()

    def test_a_lock_over_another_root_does_not_authorise_this_store(self):
        other = ownership.WorkspaceLock.for_database(
            Path(self.dir.name) / "other" / "coordinator.sqlite3")
        try:
            self.assertIsNone(other.acquire())
            with self.assertRaises(ownership.OwnershipError):
                db.admit(self.path, owner=other)
            with self.assertRaises(ownership.OwnershipError):
                db.connect(self.path, owner=other)
            self.assertFalse(self.path.exists())
        finally:
            other.release()

    def test_an_unheld_lock_does_not_authorise_anything(self):
        lock = ownership.WorkspaceLock.for_database(self.path)
        with self.assertRaises(ownership.OwnershipError):
            db.admit(self.path, owner=lock)

    def test_the_headless_coordinator_refuses_a_workspace_another_process_owns(self):
        from backend.coordinator import server
        holder = ownership.WorkspaceLock.for_database(self.path)
        try:
            self.assertIsNone(holder.acquire())
            with patch.object(server, "_serve_owned",
                              side_effect=AssertionError("served anyway")):
                with self.assertRaises(SystemExit) as caught:
                    server.serve(self.path, 0)
            self.assertIn("already owns", str(caught.exception))
        finally:
            holder.release()

    def test_the_headless_coordinator_holds_the_lock_while_it_serves(self):
        from backend.coordinator import server
        seen = {}

        def owned(state_path, port, owner):
            probe = ownership.WorkspaceLock.for_database(state_path)
            seen["other"] = probe.acquire()
            seen["held"] = owner.held
            probe.release()

        with patch.object(server, "_serve_owned", side_effect=owned):
            server.serve(self.path, 0)
        self.assertTrue(seen["held"])
        self.assertIsNotNone(seen["other"], "a second owner was allowed in")
        again = ownership.WorkspaceLock.for_database(self.path)
        self.assertIsNone(again.acquire(), "the lock was not released on exit")
        again.release()


class TestAliases(Base):
    """One actual store is one workspace, however its path is spelled."""

    def setUp(self):
        super().setUp()
        db.connect(self.path).close()
        self.elsewhere = Path(self.dir.name) / "elsewhere"
        self.elsewhere.mkdir()

    def _excluded(self, alias: Path):
        first = ownership.WorkspaceLock.for_database(self.path)
        second = ownership.WorkspaceLock.for_database(alias)
        try:
            self.assertIsNone(first.acquire())
            self.assertIsNotNone(second.acquire(), "a second writer got its own lock")
            self.assertFalse(second.held)
            self.assertTrue(first.covers(alias))
        finally:
            first.release()
            second.release()

    @unittest.skipUnless(hasattr(os, "symlink"), "needs symbolic links")
    def test_a_linked_database_file_meets_the_real_database_lock(self):
        alias = self.elsewhere / "coordinator.sqlite3"
        alias.symlink_to(self.path)
        self.assertEqual(ownership.lock_path(alias), ownership.lock_path(self.path))
        self.assertEqual(ownership.lock_path(alias).name, "desktop.lock")
        self._excluded(alias)

    @unittest.skipUnless(hasattr(os, "symlink"), "needs symbolic links")
    def test_a_linked_folder_meets_the_real_database_lock(self):
        linked = Path(self.dir.name) / "linked-root"
        linked.symlink_to(self.root, target_is_directory=True)
        self._excluded(linked / "coordinator.sqlite3")

    @unittest.skipUnless(hasattr(os, "symlink"), "needs symbolic links")
    def test_opening_through_a_link_keeps_every_file_beside_the_real_store(self):
        alias = self.elsewhere / "coordinator.sqlite3"
        alias.symlink_to(self.path)
        owner = ownership.WorkspaceLock.for_database(alias)
        self.assertIsNone(owner.acquire())
        try:
            admission = db.admit(alias, owner=owner)
            self.assertEqual(admission.path, ownership.canonical_database(self.path))
            conn = db.connect(alias, owner=owner, admitted=admission)
            conn.execute("INSERT OR REPLACE INTO meta VALUES ('probe', 'x')")
            conn.commit()
            self.assertTrue(Path(f"{self.path}-wal").exists())
            conn.close()
        finally:
            owner.release()
        # Nothing but the link itself exists in the other folder.
        self.assertEqual(sorted(p.name for p in self.elsewhere.iterdir()),
                         ["coordinator.sqlite3"])

    @unittest.skipUnless(hasattr(os, "link"), "needs hard links")
    def test_a_hard_linked_database_is_refused_unchanged_under_either_name(self):
        other = self.elsewhere / "coordinator.sqlite3"
        os.link(self.path, other)
        self.assertNotEqual(ownership.lock_path(other), ownership.lock_path(self.path))
        refused = self.assertRefusedUnchanged("alias")
        self.assertIn("2 hard links", refused.detail)
        before = _record(other)
        with self.assertRaises(db.AdmissionRefused) as caught:
            db.connect(other)
        self.assertEqual(caught.exception.code, "alias")
        self.assertEqual(_record(other), before)

    def test_the_default_root_keeps_its_historical_lock(self):
        from desktop import lifecycle
        self.assertEqual(lifecycle.LOCK_FILE.name, "desktop.lock")
        self.assertEqual(lifecycle.LOCK_FILE, ownership.lock_path(lifecycle.STATE_DB))


class TestStartup(Base):
    def test_startup_refuses_a_newer_store_before_anything_starts(self):
        from desktop import lifecycle
        conn = db.connect(self.path)
        conn.execute("UPDATE meta SET value=? WHERE key='schema_version'",
                     (str(db.SCHEMA_VERSION + 1),))
        conn.commit()
        conn.close()
        before = _record(self.path)
        owner = lifecycle.SingleInstance.for_state(self.path)
        self.assertIsNone(owner.acquire())
        try:
            with self.assertRaises(lifecycle.StartupError) as caught:
                lifecycle.run_startup(
                    lifecycle.Progress(), state_path=self.path, owner=owner,
                    start_server=lambda *_a: self.fail("started anyway"),
                    supervisor=lifecycle.EngineSupervisor(
                        probe=lambda: self.fail("engine reached"),
                        locate=lambda: None))
            self.assertIn("newer version", str(caught.exception))
        finally:
            owner.release()
        self.assertEqual(_record(self.path), before)

    def test_startup_refuses_an_owner_for_a_different_database(self):
        from desktop import lifecycle
        other = lifecycle.SingleInstance.for_state(
            Path(self.dir.name) / "else" / "coordinator.sqlite3")
        self.assertIsNone(other.acquire())
        try:
            with self.assertRaises(lifecycle.StartupError):
                lifecycle.run_startup(
                    lifecycle.Progress(), state_path=self.path, owner=other,
                    start_server=lambda *_a: self.fail("started anyway"))
        finally:
            other.release()


if __name__ == "__main__":
    unittest.main(verbosity=2)
