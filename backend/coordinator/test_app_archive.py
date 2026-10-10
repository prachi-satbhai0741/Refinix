"""Expanding an update package: accepted only as a plain, self-contained Refinix app.

    python3 -m unittest backend.coordinator.test_app_archive -v
"""

from __future__ import annotations

import hashlib
import json
import shutil
import os
import plistlib
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from backend.coordinator import app_archive

REPO = Path(__file__).resolve().parents[2]
REAL_7G = REPO / "desktop" / "out" / "local-review-20261007g" / "Refinix-0.1.0-macos-arm64.zip"
# The update trust root an app ships, and its identity's record of it.
ROOT_BYTES = b'{"signed": {"_type": "root", "version": 1}}'
ROOT_SHA = hashlib.sha256(ROOT_BYTES).hexdigest()
IDENTITY = {"version": "0.1.1-internal.2", "lane": "macos-arm64", "channel": "internal",
            "trust_root": ROOT_SHA, "schema_version": 15, "engines": []}


class Writer:
    def __init__(self, path: Path):
        self.archive = zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED)

    def file(self, name, data=b"x", mode=0o644, kind=stat.S_IFREG):
        info = zipfile.ZipInfo(name)
        info.external_attr = (kind | mode) << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        self.archive.writestr(info, data)

    def link(self, name, target):
        self.file(name, target.encode(), 0o755, stat.S_IFLNK)

    def folder(self, name):
        info = zipfile.ZipInfo(name.rstrip("/") + "/")
        info.external_attr = (stat.S_IFDIR | 0o755) << 16
        self.archive.writestr(info, b"")

    def close(self):
        self.archive.close()


def write_app(path: Path, *, identity=None, bundle_id="com.refinix.desktop", extra=None,
              root=ROOT_BYTES):
    w = Writer(path)
    w.folder("Refinix.app/Contents")
    w.file("Refinix.app/Contents/Info.plist", plistlib.dumps(
        {"CFBundleIdentifier": bundle_id, "CFBundleExecutable": "Refinix"}))
    w.file("Refinix.app/Contents/MacOS/Refinix", b"#!/bin/sh\nexit 0\n", 0o755)
    w.file("Refinix.app/Contents/Resources/refinix-build.json",
           json.dumps(identity or IDENTITY).encode())
    if root is not None:
        w.file("Refinix.app/Contents/Resources/refinix-update-root.json", root)
    # The two-link chain the real app carries: Python -> Versions/Current/Python,
    # with Versions/Current -> 3.12.
    w.file("Refinix.app/Contents/Frameworks/Python.framework/Versions/3.12/Python",
           b"\xcf\xfa\xed\xfe library", 0o755)
    w.link("Refinix.app/Contents/Frameworks/Python.framework/Versions/Current", "3.12")
    w.link("Refinix.app/Contents/Frameworks/Python.framework/Python",
           "Versions/Current/Python")
    w.file("Refinix.app/Contents/._Info.plist", b"\x00\x05\x16\x07 apple double")
    for step in extra or ():
        step(w)
    w.close()
    return path


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.base = Path(self.dir.name)

    def app(self, name="app.zip", **kwargs):
        return write_app(self.base / name, **kwargs)

    def refused(self, path, code=None):
        with self.assertRaises(app_archive.ArchiveError) as caught:
            app_archive.inspect(path)
        if code:
            self.assertEqual(caught.exception.code, code, str(caught.exception))
        return caught.exception


class TestInspect(Base):
    def test_a_plain_app_with_internal_link_chains_is_accepted(self):
        listing = app_archive.inspect(self.app())
        links = {n: e.target for n, e in listing.entries.items() if e.kind == "link"}
        self.assertEqual(len(links), 2)
        self.assertEqual(app_archive.resolve_link(
            listing, "Refinix.app/Contents/Frameworks/Python.framework/Python"),
            "Refinix.app/Contents/Frameworks/Python.framework/Versions/3.12/Python")
        self.assertFalse(any("._" in n for n in listing.entries), "AppleDouble kept")

    @unittest.skipUnless(REAL_7G.is_file(), "the 7g review package is not on this computer")
    def test_the_real_review_package_is_accepted(self):
        listing = app_archive.inspect(REAL_7G)
        links = [e for e in listing.entries.values() if e.kind == "link"]
        self.assertEqual(len(links), 24)
        self.assertGreater(len(listing.entries), 600)

    def test_links_that_escape_loop_dangle_or_chain_too_far_are_refused(self):
        cases = {
            "escape": lambda w: w.link("Refinix.app/Contents/out", "../../../etc/passwd"),
            "absolute": lambda w: w.link("Refinix.app/Contents/abs", "/etc/passwd"),
            "dangling": lambda w: w.link("Refinix.app/Contents/gone", "nowhere"),
            "loop": lambda w: (w.link("Refinix.app/Contents/a", "b"),
                               w.link("Refinix.app/Contents/b", "a")),
            "long": lambda w: [w.link(f"Refinix.app/Contents/l{i}",
                                      f"l{i + 1}" if i < 9 else "Info.plist")
                               for i in range(10)],
        }
        for label, step in cases.items():
            with self.subTest(label):
                self.refused(self.app(f"{label}.zip", extra=[step]), "unsafe_link")

    def test_writing_through_a_link_is_refused(self):
        step = lambda w: w.file(  # noqa: E731
            "Refinix.app/Contents/Frameworks/Python.framework/Versions/Current/evil", b"x")
        self.refused(self.app(extra=[step]), "unsafe_name")

    def test_unsafe_names_duplicates_and_special_files_are_refused(self):
        cases = {
            "unsafe_name": [lambda w: w.file("Refinix.app/../x", b"x"),
                            lambda w: w.file("Refinix.app/Contents\\x", b"x")],
            "not_refinix": [lambda w: w.file("Other.app/x", b"x")],
            "duplicate": [lambda w: w.file("Refinix.app/Contents/info.plist", b"x")],
            "special_mode": [lambda w: w.file("Refinix.app/Contents/MacOS/su", b"x", 0o4755)],
            "special_file": [lambda w: w.file("Refinix.app/Contents/dev", b"", 0o644,
                                              stat.S_IFCHR)],
        }
        for code, steps in cases.items():
            for index, step in enumerate(steps):
                with self.subTest(code=code, index=index):
                    self.refused(self.app(f"{code}{index}.zip", extra=[step]), code)

    def test_an_expansion_bomb_is_refused(self):
        step = lambda w: w.file("Refinix.app/Contents/zeros", b"\0" * (4 * 1024 * 1024))  # noqa: E731
        self.refused(self.app(extra=[step]), "ratio")


class TestExtract(Base):
    def test_permissions_links_and_the_tree_match_the_listing(self):
        path = self.app()
        listing = app_archive.inspect(path)
        app = app_archive.extract(path, listing, self.base / "out")
        app_archive.check_tree(self.base / "out", listing)
        mode = lambda p: stat.S_IMODE(os.lstat(p).st_mode)  # noqa: E731
        self.assertEqual(mode(app / "Contents"), 0o755)
        self.assertEqual(mode(app / "Contents" / "MacOS" / "Refinix"), 0o755)
        self.assertEqual(mode(app / "Contents" / "Info.plist"), 0o644)
        python = app / "Contents" / "Frameworks" / "Python.framework" / "Python"
        self.assertTrue(python.is_symlink())
        self.assertEqual(python.read_bytes(), b"\xcf\xfa\xed\xfe library")
        self.assertFalse((app / "Contents" / "._Info.plist").exists())

    def test_an_extra_file_after_expansion_is_noticed(self):
        path = self.app()
        listing = app_archive.inspect(path)
        app = app_archive.extract(path, listing, self.base / "out")
        (app / "Contents" / "MacOS" / "intruder").write_bytes(b"x")
        with self.assertRaises(app_archive.ArchiveError):
            app_archive.check_tree(self.base / "out", listing)

    def test_an_existing_destination_is_never_written_into(self):
        path = self.app()
        (self.base / "out").mkdir()
        with self.assertRaises(app_archive.ArchiveError):
            app_archive.extract(path, app_archive.inspect(path), self.base / "out")


class TestVerifyBundle(Base):
    def expand(self, **kwargs):
        path = self.app(**kwargs)
        return app_archive.extract(path, app_archive.inspect(path), self.base / "out")

    def verify(self, app, **overrides):
        values = dict(version="0.1.1-internal.2", lane="macos-arm64", channel="internal",
                      trust_root=ROOT_SHA, codesign=lambda _app: None)
        values.update(overrides)
        return app_archive.verify_bundle(app, **values)

    def test_the_offered_app_is_accepted(self):
        self.assertEqual(self.verify(self.expand())["version"], "0.1.1-internal.2")

    def test_another_app_version_root_or_a_broken_seal_is_refused(self):
        app = self.expand()
        for overrides in ({"version": "0.1.1-internal.3"}, {"lane": "linux-x64"},
                          {"channel": "beta"}, {"trust_root": "other"},
                          {"codesign": lambda _app: "a sealed resource is missing"}):
            with self.subTest(overrides=list(overrides)):
                with self.assertRaises(app_archive.ArchiveError):
                    self.verify(app, **overrides)

    def test_a_newer_root_authenticated_from_this_one_is_accepted(self):
        newer = b'{"signed": {"_type": "root", "version": 2}}'
        newer_sha = hashlib.sha256(newer).hexdigest()
        app = self.expand(identity={**IDENTITY, "trust_root": newer_sha}, root=newer)
        accepted = self.verify(app, trust_root=None, trust_roots={ROOT_SHA, newer_sha})
        self.assertEqual(accepted["trust_root"], newer_sha)
        with self.assertRaises(app_archive.ArchiveError) as caught:
            self.verify(app, trust_root=None, trust_roots={ROOT_SHA})
        self.assertEqual(caught.exception.code, "identity")

    def test_a_shipped_root_file_that_is_not_the_named_one_is_refused(self):
        for root in (None, b"another root"):
            with self.subTest(root=root):
                shutil.rmtree(self.base / "out", ignore_errors=True)
                with self.assertRaises(app_archive.ArchiveError) as caught:
                    self.verify(self.expand(root=root))
                self.assertEqual(caught.exception.code, "identity")

    def test_a_signed_beta_build_must_come_from_the_expected_team(self):
        app = self.expand()
        calls = []
        self.verify(app, publisher="TEAM123456",
                    team_check=lambda path, team: calls.append(team))
        self.assertEqual(calls, ["TEAM123456"])
        with self.assertRaises(app_archive.ArchiveError) as caught:
            self.verify(app, publisher="TEAM123456",
                        team_check=lambda path, team: "signed by OTHERTEAM")
        self.assertEqual(caught.exception.code, "publisher")

    def test_an_app_with_another_bundle_identifier_is_refused(self):
        with self.assertRaises(app_archive.ArchiveError) as caught:
            self.verify(self.expand(bundle_id="com.example.other"))
        self.assertEqual(caught.exception.code, "not_refinix")


if __name__ == "__main__":
    unittest.main(verbosity=2)
