"""Offline checks for the shared build driver (`desktop/build.py`).

No package is built here and nothing is downloaded. These check the decisions
the driver makes: which lane a host may build, when inputs count as unchanged,
when a retained artifact may be reused, what is shipped from the engine, that
the embedded identity never carries the package's own hash, and that a bundle
whose binaries need a newer macOS than it declares is refused.
"""

from __future__ import annotations

import json
import plistlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

DESKTOP = Path(__file__).resolve().parent
sys.path.insert(0, str(DESKTOP))
import build  # noqa: E402
import packaging_plan  # noqa: E402


class TestLane(unittest.TestCase):
    def test_each_host_builds_only_its_own_lane(self):
        self.assertEqual(build.detect_lane("darwin", "arm64"), "macos-arm64")
        self.assertEqual(build.detect_lane("win32", "AMD64"), "windows-x64")
        self.assertEqual(build.detect_lane("linux", "x86_64"), "linux-x64")

    def test_no_lane_means_no_cross_build(self):
        with self.assertRaises(build.BuildError) as caught:
            build.detect_lane("darwin", "x86_64")
        self.assertIn("cross-build", str(caught.exception))


class TestInputs(unittest.TestCase):
    TOOLCHAIN = {"python": "3.12.0"}

    def test_the_same_inputs_give_the_same_digest(self):
        first = build.input_identity("linux-x64", toolchain=self.TOOLCHAIN)
        second = build.input_identity("linux-x64", toolchain=self.TOOLCHAIN)
        self.assertEqual(first["input_digest"], second["input_digest"])

    def test_a_changed_toolchain_is_a_new_input(self):
        first = build.input_identity("linux-x64", toolchain=self.TOOLCHAIN)
        second = build.input_identity("linux-x64", toolchain={"python": "3.12.1"})
        self.assertNotEqual(first["input_digest"], second["input_digest"])

    def test_a_changed_lock_is_a_new_input(self):
        original = build.sha256_file
        target = str(build.REPO / "desktop" / "requirements-linux.lock")

        def changed(path):
            return "0" * 64 if str(path) == target else original(path)

        first = build.input_identity("linux-x64", toolchain=self.TOOLCHAIN)
        with patch.object(build, "sha256_file", side_effect=changed):
            second = build.input_identity("linux-x64", toolchain=self.TOOLCHAIN)
        self.assertNotEqual(first["input_digest"], second["input_digest"])

    def test_the_data_format_version_is_part_of_the_input(self):
        components = build.input_identity("linux-x64", toolchain=self.TOOLCHAIN)["components"]
        self.assertEqual(components["schema_version"], build.schema_version())
        self.assertGreaterEqual(build.schema_version(), 13)

    def test_update_files_must_be_a_tuf_root_and_an_https_feed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "root.json"
            feed = Path(folder) / "feed.json"
            root.write_text(json.dumps({"signed": {"_type": "targets"}}), encoding="utf-8")
            with self.assertRaises(build.BuildError):
                build.update_files(root, None)
            root.write_text(json.dumps({"signed": {"_type": "root"}}), encoding="utf-8")
            feed.write_text(json.dumps({"metadata_url": "http://x/", "targets_url": "https://x/"}),
                            encoding="utf-8")
            with self.assertRaises(build.BuildError):
                build.update_files(root, feed)
            feed.write_text(json.dumps({"metadata_url": "https://x/m/",
                                        "targets_url": "https://x/t/"}), encoding="utf-8")
            found = build.update_files(root, feed)
            self.assertEqual(found["trust_root"]["name"], "refinix-update-root.json")
            self.assertEqual(found["update_feed"]["sha256"], build.sha256_file(feed))
            self.assertEqual(build.update_files(None, None),
                             {"trust_root": None, "update_feed": None})

    def test_a_package_missing_its_update_root_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "refinix-update-root.json"
            source.write_text("{}", encoding="utf-8")
            resources = Path(folder) / "Resources"
            resources.mkdir()
            with patch.dict(build.os.environ, {"REFINIX_UPDATE_ROOT": str(source)}):
                with self.assertRaises(build.BuildError):
                    build.verify_update_files(resources)
                (resources / source.name).write_text("{}", encoding="utf-8")
                build.verify_update_files(resources)

    def test_a_requested_trust_root_is_part_of_the_input(self):
        first = build.input_identity("linux-x64", toolchain=self.TOOLCHAIN,
                                     trust_root="internal-root-a")
        second = build.input_identity("linux-x64", toolchain=self.TOOLCHAIN,
                                      trust_root="internal-root-b")
        self.assertNotEqual(first["input_digest"], second["input_digest"])
        args = type("A", (), {"version": "0.1.0-internal.1", "build_set": "bs-1",
                              "source_commit": None, "trust_root": "ignored"})()
        self.assertEqual(build.build_identity(args, "linux-x64", first, [])["trust_root"],
                         "internal-root-a")

    def test_the_interpreter_bytes_are_part_of_the_toolchain(self):
        identity = build.toolchain_identity(build.detect_lane())
        interpreter = identity["interpreter"]
        self.assertRegex(interpreter["executable"]["sha256"], r"^[0-9a-f]{64}$")
        self.assertIn("origin", interpreter)
        self.assertIn("macos_deployment_target", interpreter)
        changed = json.loads(json.dumps(identity))
        changed["interpreter"]["executable"]["sha256"] = "0" * 64
        self.assertNotEqual(
            build.input_identity("linux-x64", toolchain=identity)["input_digest"],
            build.input_identity("linux-x64", toolchain=changed)["input_digest"])

    def test_inno_setup_stubs_are_part_of_the_windows_toolchain(self):
        with tempfile.TemporaryDirectory() as folder:
            inno = Path(folder)
            (inno / "ISCC.exe").write_bytes(b"compiler")
            (inno / "Setup.e32").write_bytes(b"setup stub")
            with patch.object(build, "find_iscc", return_value=str(inno / "ISCC.exe")):
                first = build.toolchain_identity("windows-x64")["tools"]["inno_setup"]
                (inno / "Setup.e32").write_bytes(b"another stub")
                second = build.toolchain_identity("windows-x64")["tools"]["inno_setup"]
        self.assertEqual(first["files"], 2)
        self.assertNotEqual(first["digest"], second["digest"])

    def test_the_lanes_share_one_application_snapshot(self):
        shared = {build.input_identity(lane, toolchain=self.TOOLCHAIN)
                  ["components"]["shared_snapshot_digest"]
                  for lane in packaging_plan.LANES}
        self.assertEqual(len(shared), 1)


class TestReuse(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = Path(self.dir.name)
        self.artifact = self.store / "Refinix-0.1.0-internal.1-linux-x86_64.AppImage"
        self.artifact.write_bytes(b"retained bytes")
        self.deb = self.store / "refinix_0.1.0~internal.1_amd64.deb"
        self.deb.write_bytes(b"retained package")
        self.records = [{"build_set": "bs-1", "lane": "linux-x64", "input_digest": "d",
                         "artifacts": [{"name": path.name, "size": path.stat().st_size,
                                        "sha256": build.sha256_file(path)}
                                       for path in (self.artifact, self.deb)]}]

    def tearDown(self):
        self.dir.cleanup()

    def test_matching_inputs_and_intact_bytes_are_reused(self):
        found = build.find_reuse(self.records, lane="linux-x64", input_digest="d",
                                 store=self.store)
        self.assertTrue(found["reuse"])

    def test_a_missing_retained_artifact_is_never_reused(self):
        self.artifact.unlink()
        found = build.find_reuse(self.records, lane="linux-x64", input_digest="d",
                                 store=self.store)
        self.assertFalse(found["reuse"])
        self.assertIn("missing or changed", found["reason"])

    def test_changed_retained_bytes_are_never_reused(self):
        self.artifact.write_bytes(b"different bytes")
        found = build.find_reuse(self.records, lane="linux-x64", input_digest="d",
                                 store=self.store)
        self.assertFalse(found["reuse"])

    def test_without_a_store_the_bytes_cannot_be_checked_so_nothing_is_reused(self):
        found = build.find_reuse(self.records, lane="linux-x64", input_digest="d",
                                 store=None)
        self.assertFalse(found["reuse"])

    def test_an_empty_artifact_list_is_never_reused(self):
        for artifacts in ([], None):
            with self.subTest(artifacts=artifacts):
                record = dict(self.records[0], artifacts=artifacts)
                found = build.find_reuse([record], lane="linux-x64", input_digest="d",
                                         store=self.store)
                self.assertFalse(found["reuse"])
                self.assertIn("lists no artifacts", found["reason"])

    def test_a_record_missing_one_of_the_lanes_packages_is_not_reused(self):
        record = dict(self.records[0], artifacts=self.records[0]["artifacts"][:1])
        found = build.find_reuse([record], lane="linux-x64", input_digest="d",
                                 store=self.store)
        self.assertFalse(found["reuse"])
        self.assertIn(".deb", found["reason"])

    def test_an_artifact_name_with_a_folder_is_not_reused(self):
        bad = dict(self.records[0]["artifacts"][0], name="../elsewhere.AppImage")
        record = dict(self.records[0], artifacts=[bad, self.records[0]["artifacts"][1]])
        found = build.find_reuse([record], lane="linux-x64", input_digest="d",
                                 store=self.store)
        self.assertFalse(found["reuse"])
        self.assertIn("plain file name", found["reason"])

    def test_a_record_without_a_valid_hash_is_not_reused(self):
        bad = dict(self.records[0]["artifacts"][0], sha256="")
        record = dict(self.records[0], artifacts=[bad, self.records[0]["artifacts"][1]])
        self.assertFalse(build.find_reuse([record], lane="linux-x64", input_digest="d",
                                          store=self.store)["reuse"])

    def test_different_inputs_find_nothing(self):
        self.assertIsNone(build.find_reuse(self.records, lane="linux-x64",
                                           input_digest="other", store=self.store))


class TestEngineTrim(unittest.TestCase):
    def test_only_the_server_its_libraries_and_the_licence_ship(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("llama-server", "llama-cli", "llama-bench", "LICENSE",
                         "libllama.0.dylib", "libggml.so.1", "ggml-base.dll",
                         "rpc-server", "engine-manifest.json"):
                (root / name).write_text("x", encoding="utf-8")
            build.trim_engine(root)
            self.assertEqual(sorted(p.name for p in root.iterdir()),
                             ["LICENSE", "engine-manifest.json", "ggml-base.dll",
                              "libggml.so.1", "libllama.0.dylib", "llama-server"])


class TestIdentity(unittest.TestCase):
    def test_the_embedded_identity_never_holds_the_package_hash(self):
        args = type("A", (), {"version": "0.1.0-internal.1", "build_set": "bs-1",
                              "source_commit": None, "trust_root": None})()
        inputs = build.input_identity("linux-x64", toolchain={"python": "3.12"})
        identity = build.build_identity(args, "linux-x64", inputs, [])
        text = json.dumps(identity)
        self.assertNotIn("artifact", text)
        self.assertEqual((identity["channel"], identity["signing"]),
                         ("internal", "unsigned"))

    def test_a_windows_installer_is_never_run_on_an_ordinary_host(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(build, "_check", side_effect=AssertionError("ran it")):
            with self.assertRaises(build.BuildError) as caught:
                build.extract_identity(Path(folder) / "Refinix-setup.exe", Path(folder))
        self.assertIn("disposable", str(caught.exception))

    def test_a_host_with_refinix_registered_is_not_disposable(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(build, "_check", side_effect=AssertionError("ran it")):
            with self.assertRaises(build.BuildError) as caught:
                build.extract_identity(
                    Path(folder) / "Refinix-setup.exe", Path(folder), disposable_host=True,
                    registration=lambda: ["HKCU\\Software\\...\\Uninstall\\{id}_is1"])
        self.assertIn("already registered", str(caught.exception))

    def test_the_installer_app_id_is_read_from_the_script(self):
        self.assertRegex(build.WINDOWS_APP_ID, r"^[0-9A-F]{8}-[0-9A-F-]{27}$")

    def test_a_finished_zip_whose_identity_differs_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            artifact = work / "Refinix-0.1.0-internal.1-macos-arm64.zip"
            with zipfile.ZipFile(artifact, "w") as bundle:
                bundle.writestr("Refinix.app/Contents/Resources/refinix-build.json",
                                json.dumps({"version": "old"}))
            with self.assertRaises(build.BuildError):
                build.finalize(artifact, {"version": "new"}, lane="macos-arm64",
                               min_os="13.3", work=work)

    def test_a_finished_zip_gets_its_external_records(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            identity = {"version": "0.1.0-internal.1", "build_set": "bs-1",
                        "channel": "internal", "signing": "unsigned",
                        "shared_snapshot_digest": "s" * 64,
                        "engines": [{"release": "b11390", "backend": "metal"}]}
            artifact = work / "Refinix-0.1.0-internal.1-macos-arm64.zip"
            with zipfile.ZipFile(artifact, "w") as bundle:
                bundle.writestr("Refinix.app/Contents/Resources/refinix-build.json",
                                json.dumps(identity))
            record = build.finalize(artifact, identity, lane="macos-arm64",
                                    min_os="13.3", work=work)
            self.assertEqual(record["sha256"], build.sha256_file(artifact))
            self.assertTrue((work / f"{artifact.name}.sha256").is_file())
            manifest = json.loads((work / f"{artifact.name}.manifest.json").read_text())
            self.assertEqual(manifest["embedded_identity"], identity)
            notes = (work / f"{artifact.name}.TESTING.md").read_text()
            self.assertIn(record["sha256"], notes)
            self.assertIn("Open Anyway", notes)


@unittest.skipUnless(sys.platform == "darwin", "Mach-O inspection needs macOS")
class TestMacFloor(unittest.TestCase):
    def test_todays_bundle_declares_a_minimum_its_binaries_do_not_meet(self):
        """K17: the existing prototype bundle says 12.0 and needs 26.0."""
        app = DESKTOP / "dist" / "Refinix.app"
        if not app.is_dir():
            self.skipTest("no locally built prototype bundle to inspect")
        declared = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
        declared = build._version(declared["LSMinimumSystemVersion"])
        actual, which = build.bundle_floor(app)
        self.assertGreater(actual, declared, f"{which} unexpectedly within the floor")

    def test_the_pinned_engine_needs_13_3(self):
        engine = DESKTOP / "engine" / "dist" / "macos-arm64" / "llama-server"
        if not engine.is_file():
            self.skipTest("engine not fetched")
        self.assertEqual(build.macho_minos(engine), (13, 3))



class TestWebView2InTheWindowsSetup(unittest.TestCase):
    """The Windows setup installs WebView2 itself, from a pinned file, only
    when this computer lacks it, and never downloads during installation."""

    def setUp(self):
        self.tools = json.loads(build.TOOLS.read_text(encoding="utf-8"))
        self.iss = (DESKTOP / "windows" / "refinix.iss").read_text(encoding="utf-8")

    def test_the_offline_installer_is_pinned_by_size_and_sha256(self):
        pin = self.tools["webview2_standalone_x64"]
        self.assertTrue(pin["url"].startswith("https://"))
        self.assertTrue(pin["url"].endswith("MicrosoftEdgeWebView2RuntimeInstallerX64.exe"))
        self.assertRegex(pin["sha256"], r"^[0-9a-f]{64}$")
        self.assertGreater(pin["size"], 100 * 1024 * 1024)
        self.assertTrue(pin["shipped"])
        self.assertIn("licence", pin)

    def test_the_setup_runs_it_only_when_webview2_is_missing(self):
        self.assertIn('Parameters: "/silent /install"', self.iss)
        self.assertIn("StatusMsg:", self.iss)
        run = [line for line in self.iss.splitlines()
               if "MicrosoftEdgeWebView2RuntimeInstallerX64.exe" in line]
        self.assertTrue(run and all("Check: NeedsWebView2" in line for line in run))
        self.assertIn("UpdateReadyMemo", self.iss, "the Ready page says what is installed")
        self.assertIn("PrivilegesRequired=lowest", self.iss, "per-user, no administrator")
        self.assertNotIn("fwlink", self.iss, "nothing is downloaded during installation")

    def test_the_build_passes_the_verified_file_to_inno_setup(self):
        source = (DESKTOP / "build.py").read_text(encoding="utf-8")
        self.assertIn('obtain_tool("webview2_standalone_x64", cache)', source)
        self.assertIn("verify_microsoft_signature(webview2)", source)
        self.assertIn("/DWebView2Installer=", source)

    def run_signature(self, stdout, returncode=0):
        calls = []

        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs))
            return SimpleNamespace(returncode=returncode, stdout=stdout, stderr="")
        return calls, fake_run

    def test_the_path_reaches_powershell_through_the_environment(self):
        """Review finding: trailing arguments after -Command are joined into
        the command text, so `$args[0]` was never the installer path."""
        calls, fake_run = self.run_signature(
            "Valid|CN=Microsoft Corporation, O=Microsoft Corporation, C=US")
        build.verify_microsoft_signature(Path("C:/x/setup.exe"), run=fake_run)
        (argv, kwargs), = calls
        self.assertEqual(argv[:4], ["powershell", "-NoProfile", "-NonInteractive", "-Command"])
        self.assertEqual(len(argv), 5, "the script is the last argument; no path after it")
        self.assertIn("$env:" + build.SIGNATURE_PATH_VARIABLE, argv[4])
        self.assertNotIn("$args", argv[4])
        self.assertTrue(kwargs["env"][build.SIGNATURE_PATH_VARIABLE].endswith("setup.exe"))

    def test_an_invalid_or_foreign_signature_is_refused(self):
        for stdout in ("NotSigned|", "HashMismatch|CN=Microsoft Corporation, O=Microsoft Corporation",
                       "Valid|CN=Someone Else, O=Someone Else", ""):
            with self.subTest(stdout=stdout):
                _calls, fake_run = self.run_signature(stdout)
                with self.assertRaises(build.BuildError):
                    build.verify_microsoft_signature(Path("setup.exe"), run=fake_run)
        _calls, failing = self.run_signature("Valid|O=Microsoft Corporation", returncode=1)
        with self.assertRaises(build.BuildError):
            build.verify_microsoft_signature(Path("setup.exe"), run=failing)

    def test_a_tampered_download_is_refused(self):
        with tempfile.TemporaryDirectory() as scratch:
            cache = Path(scratch)
            pin = self.tools["webview2_standalone_x64"]

            def fake_download(_url, path):
                Path(path).write_bytes(b"not the pinned installer")

            with patch.object(build.engine_fetch, "_download", side_effect=fake_download):
                with self.assertRaises(build.BuildError) as caught:
                    build.obtain_tool("webview2_standalone_x64", cache)
            self.assertIn("pinned SHA-256", str(caught.exception))
            self.assertFalse((cache / f"{pin['sha256']}-{Path(pin['url']).name}").exists())



class TestChannelsAndLabels(unittest.TestCase):
    """W1: channel, label, build number and install capability are the package's identity."""

    def feed(self, folder, data):
        path = Path(folder) / "feed.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def root(self, folder):
        path = Path(folder) / "root.json"
        path.write_text(json.dumps({"signed": {"_type": "root"}}), encoding="utf-8")
        return path

    def test_a_local_folder_is_for_the_internal_channel_only(self):
        with tempfile.TemporaryDirectory() as folder:
            local = self.feed(folder, {"local_folder": "~/Refinix Updates"})
            found = build.update_files(self.root(folder), local, "internal")
            self.assertEqual(found["update_feed"]["name"], build.UPDATE_FEED_NAME)
            with self.assertRaises(build.BuildError):
                build.update_files(self.root(folder), local, "beta")

    def test_beta_needs_its_own_root_and_an_https_feed(self):
        with tempfile.TemporaryDirectory() as folder:
            https = self.feed(folder, {"metadata_url": "https://u.example/m/",
                                       "targets_url": "https://u.example/t/"})
            build.update_files(self.root(folder), https, "beta")
            with self.assertRaises(build.BuildError):
                build.update_files(None, https, "beta")
            with self.assertRaises(build.BuildError):
                build.update_files(self.root(folder), None, "beta")
            plain = self.feed(folder, {"metadata_url": "http://u.example/m/",
                                       "targets_url": "http://u.example/t/"})
            with self.assertRaises(build.BuildError):
                build.update_files(self.root(folder), plain, "internal")

    def test_labels_follow_the_application_version_and_numbers_only_increase(self):
        base = build.app_version()
        self.assertEqual(build.label_number(f"{base}-internal.7", "internal"), 7)
        self.assertIsNone(build.label_number(base, "beta"))
        for bad, channel in ((base, "internal"), (f"{base}-beta.1", "internal"),
                             ("9.9.9-internal.1", "internal"), (f"{base}-internal.x",
                                                                "internal")):
            with self.subTest(bad), self.assertRaises(build.BuildError):
                build.label_number(bad, channel)
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            (out / "set-a").mkdir()
            (out / "set-a" / "build-record-macos-arm64.json").write_text(json.dumps(
                {"lane": "macos-arm64", "version": f"{base}-internal.3"}))
            self.assertEqual(build.bundle_build(f"{base}-internal.4", "internal", None,
                                                "macos-arm64", [], out), 4)
            with self.assertRaises(build.BuildError):
                build.bundle_build(f"{base}-internal.3", "internal", None,
                                   "macos-arm64", [], out)
            # Another lane's numbers do not count, and a release names its number.
            self.assertEqual(build.bundle_build(f"{base}-internal.1", "internal", None,
                                                "linux-x64", [], out), 1)
            with self.assertRaises(build.BuildError):
                build.bundle_build(base, "beta", None, "macos-arm64", [], out)
            self.assertEqual(build.bundle_build(base, "beta", 9, "macos-arm64", [], out), 9)

    def test_install_capability_is_never_assumed(self):
        cap = build.install_capability
        self.assertEqual(cap("macos-arm64", "internal", None, None)["capability"],
                         "internal-test")
        self.assertEqual(cap("windows-x64", "internal", None, None)["capability"],
                         "unavailable")
        self.assertEqual(cap("macos-arm64", "beta", None, None)["capability"],
                         "unavailable")
        with self.assertRaises(build.BuildError):
            cap("linux-x64", "internal", "internal-test", None)
        with self.assertRaises(build.BuildError):
            cap("macos-arm64", "beta", "qualified", None)
        with tempfile.TemporaryDirectory() as folder:
            evidence = Path(folder) / "accepted.json"
            evidence.write_text("{}", encoding="utf-8")
            record = cap("macos-arm64", "beta", "qualified", evidence)
            self.assertRegex(record["evidence_sha256"], r"^[0-9a-f]{64}$")

    def test_channel_label_and_capability_are_bound_into_the_input_digest(self):
        toolchain = {"python": "3.12"}
        one = build.input_identity("linux-x64", toolchain=toolchain, channel="internal",
                                   version="0.1.0-internal.1", capability=None)
        for change in ({"channel": "beta"}, {"version": "0.1.0-internal.2"},
                       {"capability": {"capability": "internal-test",
                                       "evidence_sha256": None}}):
            values = {"channel": "internal", "version": "0.1.0-internal.1",
                      "capability": None, **change}
            other = build.input_identity("linux-x64", toolchain=toolchain, **values)
            self.assertNotEqual(one["input_digest"], other["input_digest"], change)
        args = type("A", (), {"version": "0.1.0-internal.1", "build_set": "bs-1",
                              "source_commit": None, "bundle_build": 1})()
        beta = build.input_identity("linux-x64", toolchain=toolchain, channel="beta",
                                    capability={"capability": "unavailable",
                                                "evidence_sha256": None})
        identity = build.build_identity(args, "linux-x64", beta, [])
        self.assertEqual((identity["channel"], identity["install_capability"],
                          identity["bundle_build"]), ("beta", "unavailable", 1))

    def test_the_mac_archive_carries_no_finder_metadata(self):
        text = Path(build.__file__).read_text(encoding="utf-8")
        self.assertIn('"--norsrc", "--noextattr"', text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
