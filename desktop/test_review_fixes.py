"""Regression checks for Execution 1 review findings; no native dependencies."""

import json
import os
import runpy
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from desktop import lifecycle, refinix, shell


class TestDesktopReviewFixes(unittest.TestCase):
    def test_windows_launches_lock_the_same_byte_and_can_read_metadata(self):
        offsets = []

        def locking(fd, _mode, _length):
            offset = os.lseek(fd, 0, os.SEEK_CUR)
            offsets.append(offset)
            if offset in offsets[:-1]:
                raise OSError("locked")

        with tempfile.TemporaryDirectory() as folder, \
                patch.object(lifecycle.sys, "platform", "win32"), \
                patch.dict(sys.modules, {"msvcrt": SimpleNamespace(
                    locking=locking, LK_NBLCK=2)}):
            path = Path(folder) / "desktop.lock"
            first, second = lifecycle.SingleInstance(path), lifecycle.SingleInstance(path)
            try:
                self.assertIsNone(first.acquire())
                first.record(port=8771)
                self.assertEqual(second.acquire()["port"], 8771)
                self.assertEqual(offsets, [0, 0])
                # Windows prohibits reading another process's locked byte.
                self.assertEqual(json.loads(path.read_bytes()[1:])["port"], 8771)
            finally:
                first.release()
                second.release()

    def test_both_native_entries_publish_the_selected_port_only_after_startup(self):
        records = []
        instance = Mock()
        instance.acquire.return_value = None
        instance.record.side_effect = lambda **fields: records.append(fields["port"])

        def run(**kwargs):
            self.assertEqual(records[-1], None)
            choice = lifecycle.choose_port(8770, free=lambda port: port == 8771,
                                           identify=lambda port: None)
            kwargs["on_started"](SimpleNamespace(port=choice.port))
            return 0

        with patch.object(lifecycle, "SingleInstance", return_value=instance), \
                patch.object(shell, "run", run):
            self.assertEqual(refinix.main(), 0)
            with patch.object(sys, "argv", ["desktop"]), self.assertRaises(SystemExit) as exit:
                runpy.run_module("desktop", run_name="__main__")
            self.assertEqual(exit.exception.code, 0)
        self.assertEqual(records, [None, 8771, None, 8771])

    def test_late_startup_is_disposed_instead_of_started_after_close(self):
        entered, release = threading.Event(), threading.Event()
        startup = lifecycle.Startup(8771, "http://127.0.0.1:8771/", False,
            server=Mock(), coordinator=Mock(), engine_supervisor=Mock())
        app = shell.DesktopApp()

        def delayed(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(3))
            return startup

        with patch.object(lifecycle, "run_startup", delayed), \
                patch.object(app, "_serve") as serve:
            worker = threading.Thread(target=app._startup_thread)
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                app.shutdown()
            finally:
                release.set()
                worker.join(3)
            self.assertFalse(worker.is_alive())
            serve.assert_not_called()
        startup.server.server_close.assert_called_once()
        startup.coordinator.conn.close.assert_called_once()
        startup.engine_supervisor.stop.assert_called_once()

    def test_cancelled_startup_releases_listener_and_owned_engine(self):
        cancel = threading.Event()
        server, coordinator, engine = Mock(), Mock(), Mock()

        def ensure(**kwargs):
            cancel.set()
            raise lifecycle.StartupCancelled()

        engine.ensure.side_effect = ensure
        with patch.object(lifecycle, "choose_port", return_value=lifecycle.PortChoice(8771, False, "free")), \
                tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(lifecycle.StartupCancelled):
                lifecycle.run_startup(lifecycle.Progress(), state_path=Path(folder) / "state.sqlite3",
                    start_server=lambda *args: (server, coordinator), supervisor=engine, cancelled=cancel)
        server.server_close.assert_called_once()
        server.shutdown.assert_not_called()
        coordinator.conn.close.assert_called_once()
        engine.stop.assert_called_once()

    def test_native_quit_waits_for_startup_cleanup_before_destroying_the_window(self):
        entered, release, destroyed = threading.Event(), threading.Event(), threading.Event()
        app = shell.DesktopApp()
        app.window = Mock()
        app.window.destroy.side_effect = destroyed.set

        def delayed(*args, **kwargs):
            entered.set()
            release.wait(3)
            raise lifecycle.StartupCancelled()

        with patch.object(lifecycle, "run_startup", delayed):
            worker = threading.Thread(target=app._startup_thread)
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                self.assertFalse(app.on_closing())
                self.assertFalse(destroyed.is_set())
            finally:
                release.set()
                worker.join(3)
            self.assertTrue(destroyed.wait(2))
            self.assertTrue(app.on_closing())

    def test_reused_coordinator_is_queried_confirmed_and_cancelled_but_not_shutdown(self):
        app = shell.DesktopApp()
        app.window = Mock()
        app.window.create_confirmation_dialog.return_value = True
        app.startup = lifecycle.Startup(8771, "http://127.0.0.1:8771/", True,
                                        engine_supervisor=Mock())
        running = [{"job_id": "synthetic-job", "state": "running"}]
        with patch.object(lifecycle, "get_json", side_effect=[({}, {"jobs": running}),
                ({}, {"jobs": []}), ({}, {"jobs": []})]) as get, \
                patch.object(app, "_post", return_value={"cancel_requested": True}) as post, \
                patch.object(shell, "shutdown_server") as shutdown:
            self.assertTrue(app.on_closing())
        self.assertIn("/v1/jobs/active", get.call_args.args[0])
        app.window.create_confirmation_dialog.assert_called_once()
        post.assert_called_once_with("/v1/cancel", {"job_id": "synthetic-job"})
        shutdown.assert_not_called()

    def test_unknown_workspace_is_never_reused(self):
        choice = lifecycle.choose_port(8770, workspace_id=None,
            free=lambda port: port == 8771,
            identify=lambda port: {"workspace_id": "other"})
        self.assertFalse(choice.reused)
        self.assertEqual(choice.port, 8771)


if __name__ == "__main__":
    unittest.main()
