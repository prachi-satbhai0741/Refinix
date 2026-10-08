"""Offline checks on the packaging inputs.

These check what can be checked without installing a build toolchain: that the
bundle would carry the frontend the coordinator actually serves, that the
resource lookup works from a bundle layout, that the icon assets exist and are
real, and that the bundle metadata names the product correctly.

Building the bundle itself needs py2app, which is a device checkpoint. Nothing
here claims the bundle was built.

    python3 -m unittest desktop.test_packaging -v
"""

import plistlib
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from backend.coordinator import paths, server
from desktop import packaging_plan

REPO = Path(__file__).resolve().parents[1]
ICONS = REPO / "desktop" / "icons"
ASSETS = REPO / "frontend" / "app" / "assets"


def setup_module_namespace():
    """Read setup_py2app.py without importing setuptools, which is not pinned.

    `desktop` goes on the path because the setup command runs the file as a
    script, so that directory — not the repository root — is what resolves its
    sibling imports. Reading it from the repository root instead would resolve
    imports this build never gets; the check that the script's own path really
    is enough runs out of process, below.
    """
    source = (REPO / "desktop" / "setup_py2app.py").read_text()
    namespace = {"__name__": "not_main", "__file__": str(REPO / "desktop" / "setup_py2app.py")}
    # The import line is the only part that needs a build dependency.
    source = source.replace("from setuptools import setup", "setup = None")
    sys.path.insert(0, str(REPO / "desktop"))
    try:
        exec(compile(source, "setup_py2app.py", "exec"), namespace)  # noqa: S102
    finally:
        sys.path.remove(str(REPO / "desktop"))
    return namespace


class TestBundleContents(unittest.TestCase):
    def setUp(self):
        self.ns = setup_module_namespace()

    def test_every_file_the_coordinator_serves_is_shipped(self):
        shipped = {Path(f).resolve()
                   for _dest, files in self.ns["frontend_data_files"]()
                   for f in files}
        development_only = {"fixture.html", "fixture.js"}
        for path in server.STATIC.rglob("*"):
            if not path.is_file() or path.name.startswith("."):
                continue
            if path.name in development_only or path.suffix == ".cjs":
                self.assertNotIn(path.resolve(), shipped,
                                 f"{path.name} is a development tool and must "
                                 "not be in the bundle")
                continue
            self.assertIn(path.resolve(), shipped,
                          f"{path.name} is served but would not be in the bundle")

    def test_the_frontend_lands_where_the_coordinator_looks_for_it(self):
        destinations = {dest for dest, _files in self.ns["frontend_data_files"]()}
        self.assertIn("frontend/app", destinations)
        self.assertIn("frontend/app/assets", destinations)

    def test_a_frozen_process_resolves_resources_from_the_bundle(self):
        with tempfile.TemporaryDirectory() as scratch:
            resources = Path(scratch) / "Contents" / "Resources"
            (resources / "frontend" / "app").mkdir(parents=True)
            with patch.object(sys, "frozen", True, create=True), \
                 patch.object(sys, "prefix", str(resources)):
                self.assertEqual(server.static_root(),
                                 resources / "frontend" / "app")
        # Outside a bundle it still resolves to the working tree.
        self.assertEqual(server.static_root(), REPO / "frontend" / "app")

    def test_staging_contains_only_application_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            sources = self.ns["stage_application_sources"](Path(folder))
            files = {p.relative_to(sources).as_posix()
                     for p in sources.rglob("*") if p.is_file()}
            self.assertTrue({"backend/__init__.py", "backend/coordinator/server.py",
                             "backend/contracts/v1.py", "desktop/shell.py"} <= files)
            self.assertTrue(all(p.endswith(".py") for p in files))
            self.assertFalse(any("test_" in p or "setup_" in p or "worker" in p for p in files))

    def test_bundle_check_catches_loose_and_zipped_repository_files(self):
        verify = self.ns["verify_application_contents"]
        with tempfile.TemporaryDirectory() as folder:
            bundle = Path(folder) / "Refinix.app"
            library = bundle / "Contents" / "Resources" / "lib"
            library.mkdir(parents=True)
            archive = library / "python312.zip"
            with zipfile.ZipFile(archive, "w") as files:
                for name in ("backend/coordinator/server.pyc", "backend/contracts/v1.pyc", "desktop/shell.pyc"):
                    files.writestr(name, b"synthetic")
            verify(bundle)
            leaked = library / "python3.12" / "backend" / "worker" / "app.py"
            leaked.parent.mkdir(parents=True)
            leaked.write_text("# synthetic unwanted worker")
            with self.assertRaisesRegex(RuntimeError, "backend/worker/app.py"):
                verify(bundle)
            leaked.unlink()
            with zipfile.ZipFile(archive, "a") as files:
                files.writestr("backend/coordinator/__pycache__/runtime.cpython-314.pyc", b"synthetic")
            with self.assertRaisesRegex(RuntimeError, "__pycache__"):
                verify(bundle)

    def test_the_new_c08_and_c10_modules_are_shipped(self):
        """A module the coordinator imports but the bundle omits would make the
        packaged app behave differently from a source run."""
        self.assertIn("backend/coordinator", self.ns["APPLICATION_PACKAGES"])
        for name in ("pdfrender.py", "ocr.py", "proof.py"):
            with self.subTest(module=name):
                self.assertTrue(
                    (REPO / "backend" / "coordinator" / name).exists(),
                    f"{name} must exist to be staged")

    def test_quartz_is_named_explicitly_because_it_is_imported_lazily(self):
        """`pdfrender` imports Quartz inside a function so the module stays
        importable without PyObjC. modulegraph therefore cannot follow it, and
        an unnamed dependency would ship an app that reports PDF unavailable on
        a Mac that has PyObjC installed."""
        includes = self.ns["OPTIONS"]["includes"]
        self.assertIn("Quartz", includes)
        self.assertIn("objc", includes)
        source = (REPO / "backend" / "coordinator" / "pdfrender.py").read_text()
        self.assertNotIn("\nimport Quartz", source,
                         "a top-level import would break the Ubuntu worker")
        self.assertNotIn("\nimport pypdfium2", source,
                         "a top-level import would break an install without it")

    def test_the_portable_renderer_is_bundled_whole_not_merely_imported(self):
        """pypdfium2 ships the PDFium binary as package data. modulegraph
        follows imports and not data files, so the package has to be copied or
        the bundle reports PDF unavailable on a Mac that has the renderer."""
        packages = self.ns["OPTIONS"]["packages"]
        self.assertIn("pypdfium2", packages)
        self.assertIn("pypdfium2_raw", packages,
                      "the PDFium binary lives in pypdfium2_raw")

    def test_the_desktop_lock_includes_the_existing_backend_versions(self):
        lock = (REPO / "desktop" / "requirements-macos.lock").read_text()
        for pin in (REPO / "backend" / "requirements.txt").read_text().splitlines():
            if pin and not pin.startswith("#"):
                self.assertIn(pin + " --hash=sha256:", lock)

    def test_the_bundle_cannot_enable_host_site_packages(self):
        self.assertFalse(self.ns["OPTIONS"]["site_packages"])

    def test_the_packaged_entry_does_not_modify_the_bundle_on_launch(self):
        source = (REPO / "desktop" / "refinix.py").read_text()
        self.assertLess(source.index("sys.dont_write_bytecode = True"),
                        source.index("from desktop import lifecycle, shell"))


class TestBundleMetadata(unittest.TestCase):
    def setUp(self):
        self.plist = setup_module_namespace()["PLIST"]

    def test_the_application_is_actually_named_refinix(self):
        self.assertEqual(self.plist["CFBundleName"], "Refinix")
        self.assertEqual(self.plist["CFBundleDisplayName"], "Refinix")
        self.assertEqual(self.plist["CFBundleExecutable"], "Refinix")

    def test_the_plist_is_serialisable_as_a_real_plist(self):
        plistlib.loads(plistlib.dumps(self.plist))

    def test_local_networking_is_allowed_and_arbitrary_loads_are_not(self):
        ats = self.plist["NSAppTransportSecurity"]
        self.assertTrue(ats["NSAllowsLocalNetworking"])
        self.assertNotIn("NSAllowsArbitraryLoads", ats)

    def test_opening_the_application_twice_is_prevented_by_the_bundle(self):
        self.assertTrue(self.plist["LSMultipleInstancesProhibited"])

    def test_the_icon_file_the_build_points_at_exists(self):
        options = setup_module_namespace()["OPTIONS"]
        self.assertTrue(Path(options["iconfile"]).is_file())


class TestTheSharedBoundary(unittest.TestCase):
    """One application boundary, used by every platform's package step.

    The macOS build owned these answers privately, inside a script that exits
    on anything but Darwin, so a Windows or Linux step had to restate them and
    would drift. These checks are what stop the shared version drifting
    instead.
    """

    def test_the_three_platforms_share_one_module_list(self):
        modules = packaging_plan.application_module_names()
        for platform in ("macos", "windows", "linux"):
            with self.subTest(platform=platform):
                self.assertEqual(set(packaging_plan.plan(platform)["modules"]),
                                 modules)

    def test_the_build_path_imports_the_third_party_packaging_package(self):
        check = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, 'desktop'); "
             "import packaging, packaging.utils; print(packaging.__file__)"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertNotEqual(Path(check.stdout.strip()).resolve(),
                            REPO / "desktop" / "packaging.py")

    def test_the_setup_entry_imports_the_way_the_setup_command_runs_it(self):
        """The setup command executes setup_py2app.py; it does not import it.

        Running a file by path puts that file's directory on sys.path and
        leaves the repository root off it, so a `from desktop import ...` line
        raises before the build begins — which importing the file as
        `desktop.setup_py2app` cannot show, because that mode has the
        repository root on the path and the script never does. `-P` keeps the
        working directory off sys.path so this is that environment rather than
        a friendlier one, and setuptools is stubbed for the same reason the
        helper above replaces it: it is a build dependency, not the subject.
        """
        probe = ("import runpy, sys, types\n"
                 "sys.path.insert(0, 'desktop')\n"
                 "stub = types.ModuleType('setuptools'); stub.setup = None\n"
                 "sys.modules['setuptools'] = stub\n"
                 "ns = runpy.run_path('desktop/setup_py2app.py', run_name='not_main')\n"
                 "print(ns['packaging_plan'].__file__)\n"
                 "print(ns['BUNDLE_ID'])\n"
                 "print(ns['OPTIONS']['iconfile'])\n")
        check = subprocess.run([sys.executable, "-P", "-c", probe],
                               cwd=REPO, capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        plan, bundle_id, iconfile = check.stdout.splitlines()
        # The boundary it resolved is this repository's, and the whole module
        # body ran: the icon comes from the last statement that consults it.
        self.assertEqual(Path(plan).resolve(),
                         REPO / "desktop" / "packaging_plan.py")
        self.assertEqual(bundle_id, packaging_plan.BUNDLE_ID)
        self.assertTrue(Path(iconfile).is_file())

    def test_no_test_fixture_or_build_module_is_inside_the_boundary(self):
        for name in packaging_plan.application_module_names():
            with self.subTest(module=name):
                self.assertFalse(Path(name).name.startswith(("test_", "setup_")))
                self.assertNotIn("worker", name)

    def test_the_worker_and_the_repository_tooling_are_excluded_by_name(self):
        excluded = packaging_plan.plan("windows")["excludes"]["packages"]
        for name in ("backend/worker", "deploy", "fixtures", "scripts", "docs"):
            self.assertIn(name, excluded)

    def test_a_new_coordinator_module_joins_the_boundary_automatically(self):
        """A per-file list would have to be edited; a rule does not."""
        for name in ("models.py", "device.py", "winfs.py", "paths.py"):
            with self.subTest(module=name):
                self.assertIn(f"backend/coordinator/{name}",
                              packaging_plan.application_module_names())

    def test_each_platform_selects_its_own_icon_and_they_all_exist(self):
        for platform in ("macos", "windows", "linux"):
            with self.subTest(platform=platform):
                for asset in packaging_plan.platform_assets(platform):
                    self.assertTrue(asset.is_file(), f"{asset} is missing")

    def test_linux_ships_every_launcher_size_not_only_one(self):
        self.assertEqual(len(packaging_plan.platform_assets("linux")),
                         len(packaging_plan.LINUX_ICON_SIZES))

    def test_an_unpackaged_platform_is_refused_rather_than_guessed(self):
        with self.assertRaises(ValueError):
            packaging_plan.icon_for("solaris")

    def test_windows_and_linux_build_only_on_their_own_native_host(self):
        """Buildable means pinned tools and a driver, not a produced package.

        PyInstaller cannot cross-build, so the plan must say the package comes
        from a native host or runner, and that a produced package is test
        evidence rather than a release."""
        self.assertTrue(packaging_plan.plan("macos")["buildable"])
        for platform in ("windows", "linux"):
            with self.subTest(platform=platform):
                plan = packaging_plan.plan(platform)
                self.assertTrue(plan["buildable"])
                self.assertIn("native", plan["checkpoint"])
                self.assertIn("cannot cross-build", plan["checkpoint"])
                self.assertIn("internal test evidence", plan["checkpoint"])

    def test_the_build_driver_is_never_shipped_but_build_info_is(self):
        names = packaging_plan.application_module_names()
        self.assertNotIn("desktop/build.py", names)
        self.assertIn("backend/coordinator/build_info.py", names)
        for prefix in ("fake_", "check_"):
            self.assertFalse(any(Path(n).name.startswith(prefix) for n in names))

    def test_every_platform_names_the_native_prerequisites_it_imposes(self):
        for platform in ("macos", "windows", "linux"):
            with self.subTest(platform=platform):
                self.assertTrue(packaging_plan.plan(platform)["native_prerequisites"])

    def test_no_platform_data_root_lands_inside_an_application_package(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            for platform in ("darwin", "win32", "linux"):
                with self.subTest(platform=platform):
                    root = paths.platform_root(platform=platform, environ={},
                                               home=home)
                    self.assertTrue(packaging_plan.runtime_data_is_external(root))
        # The check is real: a root inside a bundle is refused.
        self.assertFalse(packaging_plan.runtime_data_is_external(
            Path("/Applications/Refinix.app/Contents/Resources/data")))

    def test_the_frontend_group_is_the_same_for_every_platform(self):
        destinations = [destination for destination, _f
                        in packaging_plan.frontend_data_files()]
        self.assertIn("frontend/app", destinations)
        for platform in ("macos", "windows", "linux"):
            self.assertEqual(packaging_plan.plan(platform)["frontend"], destinations)

    def test_a_shipped_package_carrying_something_else_is_reported(self):
        shipped = set(packaging_plan.application_module_names())
        self.assertEqual(packaging_plan.unexpected_shipped_files(shipped), [])
        shipped.add("backend/worker/app.py")
        self.assertEqual(packaging_plan.unexpected_shipped_files(shipped),
                         ["backend/worker/app.py"])

    def test_a_missing_required_module_is_reported_by_name(self):
        self.assertEqual(
            packaging_plan.missing_shipped_files({"desktop/shell.pyc"},
                                                 ("desktop/shell.py",
                                                  "backend/coordinator/server.py")),
            ["backend/coordinator/server.py"])

    def test_prerequisites_are_probed_rather_than_named_from_the_platform(self):
        observed = packaging_plan.prerequisites()
        for key in ("credential_store", "pdf_reading", "word_writing",
                    "code_containment"):
            with self.subTest(key=key):
                self.assertIn("available", observed[key])
                self.assertIsInstance(observed[key]["available"], bool)
        self.assertEqual(observed["platform"]["platform"], sys.platform)


class TestIconAssets(unittest.TestCase):
    def test_the_macos_icon_is_a_real_icns(self):
        data = (ICONS / "Refinix.icns").read_bytes()
        self.assertEqual(data[:4], b"icns")
        self.assertEqual(struct.unpack(">I", data[4:8])[0], len(data),
                         "the icns header length must match the file")

    def test_the_windows_icon_carries_the_usual_sizes(self):
        data = (ICONS / "Refinix.ico").read_bytes()
        reserved, kind, count = struct.unpack("<HHH", data[:6])
        self.assertEqual((reserved, kind), (0, 1))
        self.assertGreaterEqual(count, 6)

    def test_linux_sizes_are_present_and_square(self):
        for size in (16, 32, 48, 64, 128, 256, 512):
            path = ICONS / f"refinix-{size}.png"
            self.assertTrue(path.is_file(), f"{path.name} is missing")
            width, height = struct.unpack(">II", path.read_bytes()[16:24])
            self.assertEqual((width, height), (size, size))

    def test_the_header_logo_and_mark_are_pngs_the_frontend_can_serve(self):
        for name in ("refinix-wordmark.png", "refinix-mark.png"):
            data = (ASSETS / name).read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        # The header logo is wider than it is tall: it is the horizontal
        # symbol-and-name lockup, not the stacked one.
        width, height = struct.unpack(">II", (ASSETS / "refinix-wordmark.png")
                                      .read_bytes()[16:24])
        self.assertGreater(width, height * 3)

    def test_the_originals_are_untouched(self):
        brand = REPO / "frontend" / "design" / "assets" / "Brand"
        for name in ("refinix-logo-stacked.jpeg", "refinix-logo-horizontal.jpeg"):
            self.assertTrue((brand / name).is_file())
            self.assertEqual((brand / name).read_bytes()[:2], b"\xff\xd8")


if __name__ == "__main__":
    unittest.main(verbosity=2)
