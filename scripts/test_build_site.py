"""Offline checks for the public website export boundary."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("build-site.sh")


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

    def test_existing_destination_is_preserved(self):
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("existing work", encoding="utf-8")
        self.assertNotEqual(self.export().returncode, 0)
        self.assertEqual(sentinel.read_text(), "existing work")


if __name__ == "__main__":
    unittest.main()
