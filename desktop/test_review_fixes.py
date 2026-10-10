"""Regression checks for Execution 1 review findings; no native dependencies."""

import json
import os
import runpy
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.coordinator import ownership
from desktop import lifecycle, refinix, shell


class TestDesktopReviewFixes(unittest.TestCase):
    def test_interrupted_setup_recovers_before_importing_application_dependencies(self):
        script = '''
import importlib.abc, json, sys
from pathlib import Path
from backend.coordinator import ownership
from desktop import refinix, update_apply as ua

class MissingApplication(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if (fullname.startswith(("pydantic", "backend.contracts")) or fullname in
                ("backend.coordinator.db", "desktop.lifecycle", "desktop.shell")):
            raise ImportError("setup has not copied " + fullname)
sys.meta_path.insert(0, MissingApplication())
from backend.coordinator import paths
state = ownership.canonical_database(paths.select_root().database)
helper = ua.attempt_folder(state, "interrupted") / "helper" / "Refinix"
helper.mkdir(parents=True)
(helper / "Refinix.exe").write_bytes(b"known-good helper fixture")
ua._atomic_json(ua.journal_file(state), {
    "update_id": "interrupted", "state": "installer_running",
    "from_version": "0.1.0-beta.901", "to_version": "0.1.0-beta.902",
    "data_root": str(state.parent), "install_path": str(state.parent / "partial"),
    "incoming": str(state.parent / "setup.exe"), "method": "windows-setup",
    "helper_bundle": str(helper), "resume_count": 0,
})
class System(ua.System):
    def spawn(self, argv, environment, log):
        assert argv == [str(helper / "Refinix.exe"), "--resume", str(state)], argv
        return {"pid": 123, "create_time": 1, "exe": argv[0]}
    def tell(self, title, text):
        raise AssertionError(text)
ua.System = System
sys.argv = ["Refinix"]
assert refinix.main() == 0
assert ua.read_journal(state)["resume_count"] == 1
assert not state.exists(), "recovery must precede database admission"
lock = ownership.WorkspaceLock.for_database(state)
assert lock.acquire() is None, "the entry releases the lock for its helper"
lock.release()
'''
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run([sys.executable, "-c", script],
                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
                env=dict(os.environ, REFINIX_DATA_ROOT=folder), timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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

        # Both entries take the lock beside the database they will open.
        lock_class = Mock(return_value=instance)
        lock_class.for_state.return_value = instance
        lock_class.for_database.return_value = instance
        with patch.object(lifecycle, "SingleInstance", lock_class), \
                patch.object(ownership, "WorkspaceLock", lock_class), \
                patch.object(shell, "run", run):
            with patch.object(sys, "argv", ["Refinix"]):
                self.assertEqual(refinix.main(), 0)
            with patch.object(sys, "argv", ["desktop"]), self.assertRaises(SystemExit) as exit:
                runpy.run_module("desktop", run_name="__main__")
            self.assertEqual(exit.exception.code, 0)
        self.assertEqual(records, [None, 8771, None, 8771])

    def test_the_packaged_entry_refuses_options_before_opening_any_workspace(self):
        # Silently ignoring development options once opened a person's real data
        # during a smoke check; now they are refused before the lock or the
        # workspace is touched. Finder's own -psn_ argument is not an option.
        lock_class = Mock()
        with patch.object(lifecycle, "SingleInstance", lock_class), \
                patch.object(ownership, "WorkspaceLock", lock_class), \
                patch.object(shell, "run") as started:
            for argv in (["Refinix", "--no-window"], ["Refinix", "--port", "9000"],
                         ["Refinix", "--state", "/tmp/x"]):
                with self.subTest(argv=argv), patch.object(sys, "argv", argv):
                    self.assertEqual(refinix.main(), 2)
            lock_class.for_state.assert_not_called()
            lock_class.for_database.assert_not_called()
            started.assert_not_called()
        self.assertEqual(refinix.unsupported_arguments(["-psn_0_12345"]), [])

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


class TestPinnedToolkit(unittest.TestCase):
    """K19: a packaged build pins its renderer and checks it before starting."""

    def test_packaged_builds_pin_the_renderer_per_os(self):
        self.assertEqual(shell.pinned_gui(None, frozen=True, platform="win32"), "edgechromium")
        self.assertEqual(shell.pinned_gui(None, frozen=True, platform="darwin"), "cocoa")
        self.assertEqual(shell.pinned_gui(None, frozen=True, platform="linux"), "gtk")
        self.assertIsNone(shell.pinned_gui(None, frozen=False, platform="win32"))
        self.assertEqual(shell.pinned_gui("qt", frozen=True, platform="win32"), "qt")

    def _registry(self, values):
        class Key:
            def __init__(self, path): self.path = path
            def __enter__(self): return self
            def __exit__(self, *a): return False

        class Registry:
            HKEY_LOCAL_MACHINE, HKEY_CURRENT_USER = "HKLM", "HKCU"

            def OpenKey(self, hive, path):
                if (hive, path) not in values:
                    raise OSError("absent")
                return Key((hive, path))

            def QueryValueEx(self, key, name):
                return values[key.path], 1
        return Registry()

    def test_missing_webview2_is_explained_not_bypassed(self):
        problem = shell.toolkit_problem("win32", registry=self._registry({}))
        self.assertIn("WebView2", problem)

    def test_a_zeroed_registration_counts_as_absent(self):
        hive, path = shell.WEBVIEW2_KEYS[0]
        registry = self._registry({("HKLM", path): "0.0.0.0"})
        self.assertIsNotNone(shell.toolkit_problem("win32", registry=registry))

    def test_an_installed_runtime_passes(self):
        hive, path = shell.WEBVIEW2_KEYS[2]
        registry = self._registry({("HKCU", path): "141.0.3537.71"})
        self.assertIsNone(shell.toolkit_problem("win32", registry=registry))

    def test_linux_without_webkitgtk_is_explained(self):
        problem = shell.toolkit_problem("linux", gtk_probe=lambda: False)
        self.assertIn("WebKitGTK 4.1", problem)
        self.assertIsNone(shell.toolkit_problem("linux", gtk_probe=lambda: True))

    def test_linux_messages_reach_the_person_without_gtk(self):
        calls = []

        def run(argv, **kwargs):
            calls.append(argv)
            return type("R", (), {"returncode": 0})()
        # GTK first; zenity when GTK is the missing piece; stderr last.
        self.assertEqual(shell._native_message("T", "x", platform="linux",
                                               gtk=lambda t, m: True, run=run), "gtk")
        self.assertEqual(shell._native_message("T", "x", platform="linux",
                                               gtk=lambda t, m: False,
                                               which=lambda n: "/usr/bin/zenity", run=run),
                         "zenity")
        self.assertEqual(calls[-1][:2], ["/usr/bin/zenity", "--error"])
        self.assertIn("--no-markup", calls[-1])
        self.assertEqual(shell._native_message("T", "x", platform="linux",
                                               gtk=lambda t, m: False,
                                               which=lambda n: None, run=run), "stderr")
