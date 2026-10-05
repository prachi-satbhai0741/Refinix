"""Keeping and restoring the previous version's data around an update.

Real SQLite stores in a temporary folder, under a real workspace lock. A crash
is simulated by making one move fail part-way; resuming must finish from what
is on disk. Blocked cases must leave every canonical file byte-for-byte as it
was.

    python3 -m unittest backend.coordinator.test_recovery -v
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.coordinator import build_info, db, ownership, recovery

OLD, NEW = "0.1.0-internal.1", "0.1.1-internal.1"


def fingerprint(path: Path) -> dict:
    out = {}
    for suffix in ("", "-wal", "-shm", "-journal"):
        p = Path(f"{path}{suffix}")
        out[suffix] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
    return out


def running(version):
    return patch.object(build_info, "describe", return_value={"version": version})


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = ownership.canonical_database(Path(self.dir.name) / "root" / "coordinator.sqlite3")
        conn = db.connect(self.path)
        conn.execute("INSERT INTO meta(key, value) VALUES ('marker', 'before update')")
        conn.commit()
        conn.close()
        self.lock = ownership.WorkspaceLock.for_database(self.path)
        self.assertIsNone(self.lock.acquire())
        self.addCleanup(self.lock.release)
        self.before = fingerprint(self.path)

    def recovery(self):
        return recovery.Recovery(self.lock, self.path)

    def newer_version_writes(self):
        """What the newer version left: a change still in its WAL, with an SHM.

        Made on a copy with a live connection and copied over the workspace,
        because closing the last connection would checkpoint and delete the WAL.
        """
        import shutil
        live = Path(self.dir.name) / "live.sqlite3"
        shutil.copyfile(self.path, live)
        conn = sqlite3.connect(live)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA wal_autocheckpoint=0")
        conn.execute("UPDATE meta SET value='after update' WHERE key='marker'")
        conn.commit()
        for suffix in ("", "-wal", "-shm"):
            shutil.copyfile(f"{live}{suffix}", f"{self.path}{suffix}")
        return conn

    def marker(self):
        conn = sqlite3.connect(self.path)
        try:
            return conn.execute("SELECT value FROM meta WHERE key='marker'").fetchone()[0]
        finally:
            conn.close()


class TestSetAside(Base):
    def test_the_database_is_kept_with_its_hash_and_the_old_version_is_held_back(self):
        record = self.recovery().set_aside(from_version=OLD, to_version=NEW)
        self.assertEqual(record["state"], "set_aside")
        kept = Path(record["set_aside"]) / self.path.name
        self.assertEqual(hashlib.sha256(kept.read_bytes()).hexdigest(), self.before[""])
        self.assertTrue(all(item["done"] for item in record["files"]))
        with running(OLD):
            with self.assertRaises(db.AdmissionRefused) as caught:
                db.admit(self.path, owner=self.lock)
            self.assertEqual(caught.exception.code, "recovery_pending")
        with running(NEW):
            self.assertEqual(db.admit(self.path, owner=self.lock).kind, "existing")
        self.assertEqual(fingerprint(self.path), self.before)

    def test_an_interrupted_set_aside_is_finished_from_disk(self):
        real = recovery._copy_durably
        calls = []

        def crash_on_second(source, target):
            calls.append(source)
            if len(calls) == 2:
                raise OSError("power lost")
            real(source, target)

        wal = self.newer_version_writes()                  # a WAL to keep as well
        self.addCleanup(wal.close)
        with patch.object(recovery, "_copy_durably", side_effect=crash_on_second):
            with self.assertRaises(OSError):
                self.recovery().set_aside(from_version=OLD, to_version=NEW)
        self.assertEqual(self.recovery().read()["state"], "setting_aside")
        record = self.recovery().resume()
        self.assertEqual(record["state"], "set_aside")
        self.assertTrue(all(item["done"] for item in record["files"]))

    def test_a_hot_rollback_journal_is_not_copied(self):
        Path(f"{self.path}-journal").write_bytes(b"x" * 512)
        with self.assertRaises(recovery.RecoveryError) as caught:
            self.recovery().set_aside(from_version=OLD, to_version=NEW)
        self.assertEqual(caught.exception.code, "hot_journal")

    def test_only_the_owner_of_the_workspace_may_run_a_step(self):
        other = ownership.WorkspaceLock.for_database(Path(self.dir.name) / "else" / "c.sqlite3")
        self.assertIsNone(other.acquire())
        self.addCleanup(other.release)
        for owner in (None, other):
            with self.assertRaises(ownership.OwnershipError):
                recovery.Recovery(owner, self.path)


class TestRestore(Base):
    def test_going_back_restores_the_old_data_and_keeps_the_newer_files(self):
        self.recovery().set_aside(from_version=OLD, to_version=NEW)
        conn = self.newer_version_writes()
        # Read before anything opens the workspace: closing a connection
        # there would checkpoint the WAL away.
        newer = fingerprint(self.path)
        conn.close()
        self.assertIsNotNone(newer["-wal"])
        record = self.recovery().restore()
        self.assertEqual(record["state"], "rolled_back_with_data")
        self.assertEqual(self.marker(), "before update")
        attempted = Path(record["attempted"])
        kept = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in attempted.iterdir()}
        name = self.path.name
        self.assertEqual(kept, {name: newer[""], f"{name}-wal": newer["-wal"],
                                f"{name}-shm": newer["-shm"]})
        self.assertFalse(Path(f"{self.path}-shm").exists(),
                         "the newer version's SHM was left beside the old database")
        with running(OLD):
            self.assertEqual(db.admit(self.path, owner=self.lock).kind, "existing")

    def test_a_crash_after_each_move_is_finished_by_resume(self):
        self.recovery().set_aside(from_version=OLD, to_version=NEW)
        conn = self.newer_version_writes()
        conn.close()
        real = os.replace
        moved = []

        def crash_after_first(source, target, *a, **k):
            if str(target).find("attempted") >= 0:
                moved.append(source)
                if len(moved) == 2:
                    raise OSError("power lost")
            return real(source, target, *a, **k)

        with patch.object(recovery.os, "replace", side_effect=crash_after_first):
            with self.assertRaises(OSError):
                self.recovery().restore()
        self.assertEqual(self.recovery().read()["state"], "restoring")
        with running(OLD):
            with self.assertRaises(db.AdmissionRefused):
                db.admit(self.path, owner=self.lock)
        record = self.recovery().resume()
        self.assertEqual(record["state"], "rolled_back_with_data")
        self.assertEqual(self.marker(), "before update")

    def test_a_changed_kept_copy_blocks_and_changes_nothing(self):
        record = self.recovery().set_aside(from_version=OLD, to_version=NEW)
        conn = self.newer_version_writes()
        conn.close()
        newer = fingerprint(self.path)
        kept = Path(record["set_aside"]) / self.path.name
        kept.write_bytes(kept.read_bytes()[:-1] + b"\x00")
        result = self.recovery().restore()
        self.assertEqual(result["state"], "recovery_blocked")
        self.assertIn("missing or changed", result["blocked"])
        self.assertEqual(fingerprint(self.path), newer)
        with self.assertRaises(db.AdmissionRefused) as caught:
            db.admit(self.path, owner=self.lock)
        self.assertEqual(caught.exception.code, "recovery_blocked")
        self.assertIn("could finish safely", caught.exception.detail)
        self.assertNotIn("Open Refinix again", caught.exception.detail)

    def test_a_database_file_appearing_mid_restore_blocks_it(self):
        self.recovery().set_aside(from_version=OLD, to_version=NEW)
        real = os.replace

        def appear_after_moves(source, target, *a, **k):
            result = real(source, target, *a, **k)
            if "attempted" in str(target):
                Path(f"{self.path}-journal").write_bytes(b"late writer")
            return result

        with patch.object(recovery.os, "replace", side_effect=appear_after_moves):
            result = self.recovery().restore()
        self.assertEqual(result["state"], "recovery_blocked")
        self.assertIn("-journal", result["blocked"])
        self.assertEqual(Path(f"{self.path}-journal").read_bytes(), b"late writer")


class TestStartup(Base):
    def test_the_previous_version_goes_back_before_it_opens(self):
        self.recovery().set_aside(from_version=OLD, to_version=NEW)
        conn = self.newer_version_writes()
        conn.close()
        record = recovery.at_startup(self.lock, self.path, OLD)
        self.assertEqual(record["state"], "rolled_back_with_data")
        self.assertEqual(self.marker(), "before update")

    def test_the_new_version_opens_then_commits(self):
        self.recovery().set_aside(from_version=OLD, to_version=NEW)
        self.assertEqual(recovery.at_startup(self.lock, self.path, NEW)["state"], "set_aside")
        self.assertEqual(recovery.after_startup(self.lock, self.path, NEW)["state"],
                         "committed")
        with running(OLD):
            self.assertEqual(db.admit(self.path, owner=self.lock).kind, "existing")

    def test_another_version_is_refused_and_told_why(self):
        self.recovery().set_aside(from_version=OLD, to_version=NEW)
        with running("0.0.9"):
            with self.assertRaises(db.AdmissionRefused) as caught:
                db.admit(self.path, owner=self.lock)
        self.assertIn("in progress (set_aside)", caught.exception.detail)

    def test_desktop_startup_finishes_an_interrupted_restore_first(self):
        from desktop import lifecycle
        self.recovery().set_aside(from_version=OLD, to_version=NEW)
        conn = self.newer_version_writes()
        conn.close()
        journal = self.recovery().read()
        journal["state"] = "restoring"
        journal["attempted"] = str(self.path.parent / "recovery" / "attempted" / "x")
        journal["moves"] = []
        journal["restores"] = [{"name": i["name"], "done": False} for i in journal["files"]]
        (self.path.parent / "recovery" / "update-journal.json").write_text(json.dumps(journal))
        for suffix in ("-wal", "-shm"):                     # what the newer version left
            Path(f"{self.path}{suffix}").unlink(missing_ok=True)
        with running(OLD), patch.object(lifecycle, "choose_port",
                                        return_value=lifecycle.PortChoice(8770, False, "free")):
            lifecycle.run_startup(
                lifecycle.Progress(), state_path=self.path, owner=self.lock,
                start_server=lambda *_a: ("server", "coordinator"),
                supervisor=lifecycle.EngineSupervisor(
                    probe=lambda: {"reachable": False, "models": []},
                    locate=lambda: None))
        self.assertEqual(self.recovery().read()["state"], "rolled_back_with_data")
        self.assertEqual(self.marker(), "before update")


if __name__ == "__main__":
    unittest.main(verbosity=2)
