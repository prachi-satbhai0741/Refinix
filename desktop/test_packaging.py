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
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.coordinator import server

REPO = Path(__file__).resolve().parents[1]
ICONS = REPO / "desktop" / "icons"
ASSETS = REPO / "frontend" / "app" / "assets"


def setup_module_namespace():
    """Read setup_py2app.py without importing setuptools, which is not pinned."""
    source = (REPO / "desktop" / "setup_py2app.py").read_text()
    namespace = {"__name__": "not_main", "__file__": str(REPO / "desktop" / "setup_py2app.py")}
    # The import line is the only part that needs a build dependency.
    source = source.replace("from setuptools import setup", "setup = None")
    exec(compile(source, "setup_py2app.py", "exec"), namespace)  # noqa: S102
    return namespace


class TestBundleContents(unittest.TestCase):
    def setUp(self):
        self.ns = setup_module_namespace()

    def test_every_file_the_coordinator_serves_is_shipped(self):
        shipped = {Path(f).resolve()
                   for _dest, files in self.ns["frontend_data_files"]()
                   for f in files}
        development_only = {"fixture.html", "fixture.js", "test-conversations.cjs"}
        for path in server.STATIC.rglob("*"):
            if not path.is_file() or path.name.startswith("."):
                continue
            if path.name in development_only:
                self.assertNotIn(path.resolve(), shipped)
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

    def test_modulegraph_receives_only_application_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            sources = self.ns["stage_application_sources"](Path(folder))
            files = {str(p.relative_to(sources)) for p in sources.rglob("*") if p.is_file()}
            self.assertTrue({"backend/__init__.py", "backend/coordinator/server.py",
                             "backend/contracts/v1.py", "desktop/shell.py"} <= files)
            self.assertTrue(all(p.endswith(".py") for p in files))
            self.assertFalse(any("test_" in p or "setup_" in p or "worker" in p for p in files))

    def test_the_desktop_lock_includes_the_existing_backend_versions(self):
        lock = (REPO / "desktop" / "requirements-macos.lock").read_text()
        for pin in (REPO / "backend" / "requirements.txt").read_text().splitlines():
            if pin and not pin.startswith("#"):
                self.assertIn(pin + " --hash=sha256:", lock)

    def test_the_bundle_cannot_enable_host_site_packages(self):
        self.assertFalse(self.ns["OPTIONS"]["site_packages"])


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
