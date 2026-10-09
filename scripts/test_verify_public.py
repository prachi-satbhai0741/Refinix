"""Requested public versions must agree with the website and packaged identities."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import qualification_record, qualify_macos, qualify_windows, verify_public


class TestPublicVersion(unittest.TestCase):
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
