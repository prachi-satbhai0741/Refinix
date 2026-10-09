"""Requested public versions must agree with the website and packaged identities."""
import contextlib
import io
import json
import os
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch
from types import SimpleNamespace

from scripts import (qualification_record, qualify_macos, qualify_package_launch,
                     qualify_update_journey, qualify_windows, verify_public)


class TestPublicVersion(unittest.TestCase):
    def test_ubuntu_journeys_place_their_requests_inside_the_users_home(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder).resolve()
            home, elsewhere = base / "home", base / "system-temp"
            home.mkdir()
            elsewhere.mkdir()
            roots = []
            mkdtemp = tempfile.mkdtemp
            def make_work(**kwargs):
                return mkdtemp(prefix=kwargs["prefix"], dir=kwargs.get("dir") or elsewhere)
            def observe(report, app, args):
                roots.append(app.data_root)
                (app.data_root.parent / "app.log").write_text("synthetic startup diagnostic")
                helper = app.data_root / "updates" / "install" / "fixture"
                helper.mkdir(parents=True)
                (helper / "helper.json").write_text('{"state":"error"}')
                (app.data_root / "state.sqlite3").write_text("must not upload")
                report.record("fixture journey", True, None)
            with patch.dict(os.environ, REFINIX_QUALIFY_DISPOSABLE="1"), \
                    patch.object(Path, "home", return_value=home), \
                    patch.object(qualify_update_journey.tempfile, "mkdtemp", side_effect=make_work), \
                    patch.object(qualify_update_journey, "allow_refinix_prompts_for_this_runner"), \
                    patch.object(qualify_update_journey, "stop_everything"), \
                    patch.object(qualify_update_journey, "install_old"), \
                    patch.object(qualify_update_journey, "installed_version", return_value="old"), \
                    patch.dict(qualify_update_journey.JOURNEYS, update=observe), \
                    contextlib.redirect_stdout(io.StringIO()):
                result = qualify_update_journey.main([
                    "--lane", "linux-x64", "--old", "old.deb", "--new-bundle", "bundle.zip",
                    "--old-version", "old", "--new-version", "new", "--journey", "update",
                    "--report", str(base / "report.json")])
            self.assertEqual(result, 0)
            self.assertEqual(len(roots), 1)
            self.assertTrue(roots[0].is_relative_to(home))
            self.assertFalse(any(elsewhere.iterdir()))
            debug = base / "journey-debug"
            self.assertEqual((debug / "app.log").read_text(), "synthetic startup diagnostic")
            self.assertEqual({p.name for p in debug.rglob("*") if p.is_file()},
                             {"app.log", "helper.json"})

    def test_journeys_stop_when_bundle_import_or_preparation_fails(self):
        for download, install in (("failed", "ready"), ("verified", "failed"),
                                   ("verified", "ready")):
            with self.subTest(download=download, install=install), \
                    tempfile.TemporaryDirectory() as folder:
                app = Mock(data_root=Path(folder))
                app.ask.return_value = {"updates": {"download": {"state": download}}}
                args = SimpleNamespace(old_version="old", new_bundle=Path("bundle.zip"))
                report = qualify_update_journey.Report()
                with patch.object(qualify_update_journey, "wait_for_app", return_value=(1, {})), \
                        patch.object(qualify_update_journey, "seed", return_value=["saved"]), \
                        patch.object(qualify_update_journey, "http", return_value={
                            "install": {"state": install}}) as http, \
                        contextlib.redirect_stdout(io.StringIO()):
                    port, work = qualify_update_journey.start_update(report, app, args, "update")
                success = download == "verified" and install == "ready"
                self.assertEqual(port, 1 if success else None)
                self.assertEqual(work, ["saved"])
                self.assertEqual(all(c["passed"] for c in report.checks), success)
                if download == "failed":
                    http.assert_not_called()

    def test_an_interrupted_setup_may_discard_the_update_only_with_the_old_tree_intact(self):
        for version, problem, matches, success in (("old", None, True, True),
                ("new", None, True, False), ("old", "missing shipped file", True, False),
                ("old", None, False, False)):
            with self.subTest(version=version, problem=problem, matches=matches), \
                    tempfile.TemporaryDirectory() as folder:
                base = Path(folder)
                (base / "Refinix.exe").touch()
                args = SimpleNamespace(lane="windows-x64", old_version="old", new_version="new")
                app = Mock(data_root=base, env={})
                helper = {"pid": 123, "create_time": 42, "exe": "private helper"}
                process = Mock()
                report = qualify_update_journey.Report()
                with patch.dict(qualify_update_journey.INSTALL, {args.lane: base}), \
                        patch.object(qualify_update_journey, "start_update", return_value=(1, [])), \
                        patch.object(qualify_update_journey, "journal", side_effect=[
                            {"state": "installer_running", "helper": helper},
                            {"state": "installer_running", "helper": helper},
                            {"state": "installer_running", "helper": helper},
                            {"state": "discarded"}, {"state": "discarded"},
                            {"state": "discarded"}, {"state": "discarded"},
                            {"state": "discarded"}]), \
                        patch.object(qualify_update_journey, "installed_version", return_value=version), \
                        patch.object(qualify_update_journey, "wait_for_app", return_value=(1, {})), \
                        patch.object(qualify_update_journey, "saved", return_value=[]), \
                        patch.object(qualify_update_journey, "stop_everything"), \
                        patch.object(qualify_update_journey.time, "sleep"), \
                        patch("desktop.update_apply.System.same", return_value=matches), \
                        patch("psutil.Process", return_value=process) as process_for_pid, \
                        patch("desktop.install_check.completeness_problem", return_value=problem), \
                        contextlib.redirect_stdout(io.StringIO()):
                    qualify_update_journey.journey_interrupt(report, app, args)
                self.assertEqual(all(c["passed"] for c in report.checks), success)
                if matches:
                    process_for_pid.assert_called_once_with(helper["pid"])
                    process.kill.assert_called_once()
                    process.wait.assert_called_once_with(timeout=10)
                else:
                    process_for_pid.assert_not_called()

    def test_launch_and_journey_wait_for_a_slow_status_but_require_the_scratch_root(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            status = {"process": {"data_root": str(root)}, "build": {"version": "fixture"}}
            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    time.sleep(2)
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(json.dumps(status).encode())
                def log_message(self, *args):
                    pass
            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_port
                for module, find in ((qualify_package_launch, qualify_package_launch._find),
                                     (qualify_update_journey, qualify_update_journey.find)):
                    with self.subTest(module=module.__name__), \
                            patch.object(module, "PORTS", (port,)):
                        self.assertEqual(find(root), (port, status))
                        self.assertEqual(find(root / "other"), (None, None))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(5)

    def test_an_older_self_consistent_website_fails_the_requested_version(self):
        release = {"version": "0.1.0-beta.1", "checksums": "https://example.test/SHA256SUMS",
                   "lanes": {}}
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(verify_public, "fetch", side_effect=[
                    (b"<html></html>", ""), (json.dumps(release).encode(), ""), (b"", "")]), \
                contextlib.redirect_stdout(io.StringIO()):
            result = verify_public.check("https://example.test", None, Path(folder),
                                         "0.1.0-beta.2")
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"][0]["passed"])

    def test_native_qualifiers_refuse_an_older_embedded_version(self):
        for module, lane, platform in ((qualify_macos, "macos-arm64", "darwin"),
                                       (qualify_windows, "windows-x64", "win32")):
            for wanted, success in (("0.1.0-beta.1", True), ("0.1.0-beta.2", False)):
                with self.subTest(lane=lane, wanted=wanted), \
                        tempfile.TemporaryDirectory() as folder:
                    base = Path(folder)
                    identity = {"version": "0.1.0-beta.1"}
                    package = base / "package"
                    package.write_bytes(b"stand-in package")
                    Path(f"{package}.manifest.json").write_text(json.dumps(
                        {"embedded_identity": identity}))
                    report_path = base / "report.json"

                    def qualify(report, *args):
                        for name in qualification_record.REQUIRED[lane]:
                            report.record(name, True, "simulated native check")
                        return identity

                    args = (["--dmg", str(package), "--zip", str(package)]
                            if lane == "macos-arm64" else ["--setup", str(package)])
                    args += ["--expect-version", wanted, "--report", str(report_path)]
                    with patch.object(module.sys, "platform", platform), \
                            patch.dict(os.environ, REFINIX_QUALIFY_DISPOSABLE="1"), \
                            patch.object(module, "qualify", side_effect=qualify), \
                            patch.object(module, "host", return_value={}), \
                            patch.object(module.subprocess, "run"), \
                            contextlib.redirect_stdout(io.StringIO()):
                        code = module.main(args)
                    self.assertEqual(code, 0 if success else 1)
                    record = json.loads(report_path.read_text())
                    version_check = next(c for c in record["checks"]
                                         if c["check"] == "package is the requested public version")
                    self.assertEqual(version_check["passed"], success)
