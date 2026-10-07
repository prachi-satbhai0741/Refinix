"""The window's Install and restart: refuse early, or drain, close, set aside, hand off.

A real coordinator and listener, a real workspace lock and recovery journal.
Only the helper launch and the native window are replaced.

    python3 -m unittest desktop.test_install_flow -v
"""

from __future__ import annotations

import socket
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.coordinator import ownership, recovery, server, updates
from desktop import lifecycle, shell, update_apply
from desktop.test_update_apply import FakeSystem, make_app

N, N1 = "0.1.0-internal.1", "0.1.0-internal.2"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        base = Path(self.dir.name)
        self.db = ownership.canonical_database(base / "data" / "coordinator.sqlite3")
        self.lock = ownership.WorkspaceLock.for_database(self.db)
        self.assertIsNone(self.lock.acquire())
        self.addCleanup(self.lock.release)
        self.httpd, self.c = server.build_server(self.db, free_port(), owner=self.lock)
        threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True).start()
        self.addCleanup(self.cleanup)
        self.install = make_app(base / "Applications" / "Refinix.app", N)
        self.incoming = make_app(base / "data" / "updates" / "install" / "u1" / "Refinix.app",
                                 N1)
        u = self.c.updates
        u.identity = {"version": N, "lane": "macos-arm64", "channel": "internal",
                      "trust_root": "t"}
        u.install = {"state": "ready", "update_id": "u1", "version": N1,
                     "incoming": str(self.incoming), "install_path": str(self.install)}
        self.app = shell.DesktopApp(state_path=self.db, owner=self.lock)
        self.app.window = Mock()
        self.app.window.create_confirmation_dialog.return_value = True
        self.engine = Mock()
        self.app.startup = lifecycle.Startup(self.httpd.server_port, "http://x/", False,
                                             server=self.httpd, coordinator=self.c,
                                             engine_supervisor=self.engine)
        self.handed = []
        patches = [
            patch.object(updates.UpdateService, "install_location",
                         return_value=(self.install, None)),
            patch.object(updates, "running_bundle", return_value=self.install),
            patch.object(update_apply, "hand_off",
                         side_effect=lambda *a, **k: self.handed.append(k) or a[2]),
            patch.object(shell.threading, "Timer"),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def cleanup(self):
        if not self.c.stopping.is_set():
            server.shutdown_server(self.httpd, self.c)
        if not self.c.closed:
            self.c.conn.close()

    def data_journal(self):
        return update_apply._data_journal(self.db)


class TestRefusals(Base):
    def test_nothing_happens_unless_a_verified_update_is_ready(self):
        self.c.updates.install = {"state": "idle"}
        self.assertIn("not ready", self.app.install_update()["error"])
        self.assertFalse(self.c.installing.is_set())
        self.assertIsNone(update_apply.read_journal(self.db))

    def test_a_model_download_in_progress_is_not_cancelled_silently(self):
        with patch.object(self.c.provisioner, "active", return_value=["qwen"]):
            result = self.app.install_update()
        self.assertIn("Settings → Models", result["error"])
        self.assertIsNone(update_apply.read_journal(self.db))

    def test_running_replies_need_the_persons_yes(self):
        self.app.window.create_confirmation_dialog.return_value = False
        with patch.object(self.app, "active_jobs", return_value=[{"job_id": "j"}]):
            self.assertEqual(self.app.install_update(), {"cancelled": True})
        self.assertFalse(self.c.installing.is_set())
        self.assertIsNone(update_apply.read_journal(self.db))

    def test_a_writer_that_does_not_finish_changes_nothing_and_keeps_refinix_running(self):
        held = self.c.writers.hold("a running reply")
        held.__enter__()
        self.addCleanup(held.__exit__, None, None, None)
        with patch.object(self.c.writers, "wait_idle", return_value=["a running reply"]):
            result = self.app.install_update()
        self.assertIn("did not finish", result["error"])
        self.assertFalse(self.c.installing.is_set())
        self.assertEqual(update_apply.read_journal(self.db)["state"], "cancelled")
        self.assertIsNone(self.data_journal())
        self.c.conn.execute("SELECT 1").fetchone()        # still open
        self.assertFalse(self.c.stopping.is_set())
        self.assertEqual(self.handed, [])


class TestInstall(Base):
    def test_the_data_is_closed_set_aside_and_the_helper_takes_over(self):
        self.assertEqual(self.app.install_update(), {"installing": True})
        self.assertTrue(self.c.stopping.is_set())
        self.assertTrue(self.c.closed)
        self.engine.stop.assert_called()
        data = self.data_journal()
        self.assertEqual((data["state"], data["update_id"], data["to_version"]),
                         ("set_aside", "u1", N1))
        self.assertEqual(update_apply.read_journal(self.db)["state"], "snapshot_taken")
        self.assertEqual(self.handed[-1]["mode"], "--apply-update")
        shell.threading.Timer.assert_called()

    def test_a_reader_that_will_not_leave_hands_off_without_a_snapshot(self):
        with patch.object(self.c, "close_for_install", return_value=["a request"]):
            self.app.install_update()
        self.assertIsNone(self.data_journal())
        self.assertEqual(self.handed[-1]["mode"], "--resume")

    def test_a_failed_snapshot_is_left_for_the_helper_to_finish_or_discard(self):
        with patch.object(recovery.Recovery, "set_aside", side_effect=OSError("disk")):
            self.app.install_update()
        self.assertEqual(update_apply.read_journal(self.db)["state"], "quiescing")
        self.assertEqual(self.handed[-1]["mode"], "--resume")


class TestCommitAndStop(Base):
    def test_the_new_version_commits_only_from_its_loaded_window(self):
        journal = update_apply.plan_attempt(
            self.lock, self.db, update_id="u1", from_version=N, to_version=N1,
            install_path=self.install, incoming=self.incoming, lane="macos-arm64",
            channel="internal", trust_root="t", environment={})
        recovery.Recovery(self.lock, self.db).set_aside(
            from_version=N, to_version=N1, update_id="u1", data_root=str(self.db.parent))
        FakeSystem(self).swap(self.incoming, self.install)
        previous = update_apply._previous_path(self.db, journal)
        previous.parent.mkdir(parents=True)
        self.incoming.rename(previous)
        journal = update_apply.write_journal(self.lock, self.db, journal, state="relaunching",
                                            previous_app=str(previous))
        self.app.update_gate = update_apply.Gate(supervised=journal)
        self.assertEqual(self.app.ui_ready(), {"committed": True})
        self.assertEqual(self.data_journal()["state"], "committed")
        self.assertEqual(self.c.updates.notice, {"kind": "updated", "from": N, "to": N1})
        self.assertEqual(self.app.ui_ready(), {"committed": False})

    def test_sigterm_stops_like_quit_without_asking(self):
        self.app.terminate()
        self.assertTrue(self.c.stopping.is_set())
        self.engine.stop.assert_called()
        self.app.window.destroy.assert_called_once()
        self.app.window.create_confirmation_dialog.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
