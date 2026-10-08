"""Offline checks for the public website export boundary."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("build-site.sh")
REPOSITORY = "https://github.com/prachi-satbhai0741/Refinix"


class SiteExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        scripts = self.root / "scripts"
        scripts.mkdir()
        self.script = scripts / SCRIPT.name
        shutil.copyfile(SCRIPT, self.script)
        self.source = self.root / "frontend/design"
        assets = self.source / "assets"
        assets.mkdir(parents=True)
        self.video = b"unchanged video bytes\x00"
        (assets / "intro video.mp4").write_bytes(self.video)
        (assets / "deity.png").write_bytes(b"unchanged artwork")
        (self.source / "site.html").write_text(
            '<video src="assets/intro%20video.mp4"></video>'
            '<a href="docs.html#about">About</a>'
            '<img src="assets/refinix-lockup-h.png" onerror="this.remove()">',
            encoding="utf-8")
        (self.source / "docs.html").write_text(
            '<a href="site.html#get">Launch</a>', encoding="utf-8")
        (self.source / "site.css").write_text(
            ':root { --deity: url("assets/deity.png"); }', encoding="utf-8")
        (self.source / "docs.css").write_text("/* Docs */", encoding="utf-8")
        (self.root / "private.txt").write_text("must not publish", encoding="utf-8")
        self.output = self.root / "public-site"

    def export(self):
        return subprocess.run(["sh", str(self.script), str(self.output)],
                              cwd=self.root, capture_output=True, text=True)

    def test_public_layout_and_media_preservation(self):
        result = self.export()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.output / "index.html").read_bytes(),
                         (self.source / "site.html").read_bytes())
        self.assertIn('href="index.html#get"',
                      (self.output / "docs.html").read_text(encoding="utf-8"))
        self.assertEqual((self.output / "assets/intro video.mp4").read_bytes(), self.video)
        self.assertEqual((self.output / "CNAME").read_text(), "refinix.runs-on.dev\n")
        self.assertEqual({str(p.relative_to(self.output)) for p in self.output.rglob("*")
                          if p.is_file()},
                         {"index.html", "docs.html", "site.css", "docs.css", "CNAME",
                          ".nojekyll", "assets/intro video.mp4", "assets/deity.png"})

    def test_missing_required_asset_stops_export(self):
        (self.source / "assets/intro video.mp4").unlink()
        self.assertNotEqual(self.export().returncode, 0)
        self.assertFalse(self.output.exists())

    def test_asset_cannot_escape_public_assets_folder(self):
        (self.source / "docs.html").write_text(
            '<img src="assets/../../../private.txt">', encoding="utf-8")
        self.assertNotEqual(self.export().returncode, 0)
        self.assertFalse(self.output.exists())

    def release(self, **changes):
        version = "0.1.0-preview.1"
        folder = f"{REPOSITORY}/releases/download/v{version}/"
        deb = "refinix_0.1.0~1.1_amd64.deb"
        data = {"version": version, "maturity": "preview", "public_build": 1,
                "release_page": f"{REPOSITORY}/releases/tag/v{version}",
                "checksums": folder + "SHA256SUMS", "device_testing": "pending",
                "lanes": {
                    "macos-arm64": {"platform": "macOS", "architecture": "Apple silicon",
                                    "status": "unavailable",
                                    "reason": "not yet signed: <Developer ID>", "files": []},
                    "linux-x64": {"platform": "Ubuntu", "architecture": "x86_64 (amd64)",
                                  "status": "available", "reason": None, "files": [{
                                      "format": "deb", "label": ".deb — App Center",
                                      "name": deb, "size": 151_000_000, "sha256": "a" * 64,
                                      "url": folder + deb}]}}}
        data.update(changes)
        path = self.root / "release.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path, data

    def export_with(self, release):
        (self.source / "site.html").write_text(
            '<main><!-- refinix-downloads --><p>none yet</p><!-- /refinix-downloads --></main>',
            encoding="utf-8")
        return subprocess.run(["sh", str(self.script), str(self.output), str(release)],
                              cwd=self.root, capture_output=True, text=True)

    def test_release_cards_offer_only_available_files_with_their_sha256(self):
        path, _data = self.release()
        result = self.export_with(path)
        self.assertEqual(result.returncode, 0, result.stderr)
        page = (self.output / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("none yet", page)
        self.assertIn(f'href="{REPOSITORY}/releases/download/v0.1.0-preview.1/'
                      'refinix_0.1.0~1.1_amd64.deb"', page)
        self.assertIn("SHA-256 " + "a" * 64, page)
        self.assertIn("Tester preview — device testing pending", page)
        # The unsigned platform keeps a card with its reason, escaped, and no link.
        self.assertIn("Unavailable: not yet signed: &lt;Developer ID&gt;", page)
        self.assertEqual(page.count("releases/download/"), 2)   # the .deb and SHA256SUMS
        self.assertEqual((self.output / "release.json").read_bytes(), path.read_bytes())

    def test_a_file_from_anywhere_else_stops_the_export(self):
        path, data = self.release()
        data["lanes"]["linux-x64"]["files"][0]["url"] = "https://example.invalid/refinix.deb"
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertNotEqual(self.export_with(path).returncode, 0)
        self.assertFalse(self.output.exists())

    def test_a_release_with_nothing_available_stops_the_export(self):
        path, data = self.release()
        data["lanes"]["linux-x64"]["status"] = "unavailable"
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertNotEqual(self.export_with(path).returncode, 0)
        self.assertFalse(self.output.exists())

    def test_the_real_page_has_one_download_section_and_no_countdown(self):
        page = (Path(__file__).resolve().parents[1] / "frontend/design/site.html").read_text(
            encoding="utf-8")
        self.assertEqual(page.count("<!-- refinix-downloads -->"), 1)
        self.assertEqual(page.count("<!-- /refinix-downloads -->"), 1)
        self.assertNotIn("countdown", page.lower())
        self.assertNotIn("private for now", page)

    def test_existing_destination_is_preserved(self):
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("existing work", encoding="utf-8")
        self.assertNotEqual(self.export().returncode, 0)
        self.assertEqual(sentinel.read_text(), "existing work")


if __name__ == "__main__":
    unittest.main()
