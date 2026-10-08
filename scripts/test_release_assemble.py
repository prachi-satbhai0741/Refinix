"""Release assembly: one commit, agreeing identities, unsigned platforms unavailable.

    python3 -m unittest scripts.test_release_assemble -v
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from backend.coordinator import release
from scripts import release_assemble as assembly

COMMIT = "c" * 40
VERSION = "0.1.0-preview.1"
RUN = {"headSha": COMMIT, "event": "workflow_dispatch", "workflowName": "Beta packages",
       "conclusion": "success"}


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.base = Path(self.dir.name)
        self.ci, self.mac = self.base / "ci", self.base / "mac"
        self.ci.mkdir()
        self.mac.mkdir()

    def package(self, folder, lane, fmt, *, signing="unsigned", **identity):
        name = (release.dmg_name(VERSION) if fmt == "dmg"
                else release.asset_name(VERSION, lane, fmt))
        path = folder / name
        path.write_bytes(f"{name} bytes".encode())
        embedded = {"version": VERSION, "channel": "beta", "maturity": "preview",
                    "bundle_build": 4, "source_commit": COMMIT,
                    "shared_snapshot_digest": "s" * 64, "trust_root": "r" * 64,
                    "update_feed": "f" * 64, "schema_version": 15, "lane": lane,
                    "signing": signing, "publisher": "ABCDE12345" if signing ==
                    "developer-id" else None, **identity}
        record = {"artifact": name, "size": path.stat().st_size,
                  "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "lane": lane,
                  "minimum_os": "x", "embedded_identity": embedded}
        Path(f"{path}.manifest.json").write_text(json.dumps(record))
        return path

    def linux(self, passed=True):
        path = self.package(self.ci, "linux-x64", "deb")
        (self.ci / "deb-qualification.json").write_text(json.dumps({"passed": passed}))
        return path

    def assemble(self, **kwargs):
        values = dict(version=VERSION, commit=COMMIT, run=dict(RUN),
                      inputs=[self.ci, self.mac], out=self.base / "out",
                      mac_check=lambda path, team: None)
        values.update(kwargs)
        return assembly.assemble(**values)


class TestAssembly(Base):
    def test_unsigned_mac_and_windows_are_unavailable_and_never_copied(self):
        self.linux()
        self.package(self.ci, "windows-x64", "exe")
        self.package(self.mac, "macos-arm64", "zip")
        self.package(self.mac, "macos-arm64", "dmg")
        site = self.assemble()
        self.assertEqual({k: v["status"] for k, v in site["lanes"].items()},
                         {"macos-arm64": "unavailable", "windows-x64": "unavailable",
                          "linux-x64": "available"})
        self.assertIn("Developer ID", site["lanes"]["macos-arm64"]["reason"])
        out = self.base / "out"
        published = sorted(p.name for p in out.iterdir()
                           if not p.name.endswith(".manifest.json"))
        self.assertIn(release.asset_name(VERSION, "linux-x64", "deb"), published)
        self.assertFalse(any(name.endswith((".exe", ".dmg", ".zip")) for name in published))
        sums = (out / "SHA256SUMS").read_text()
        self.assertEqual(len(sums.splitlines()), 1)
        self.assertEqual(site["device_testing"], "pending")
        notes = (out / "RELEASE-NOTES.md").read_text()
        self.assertIn("pending device testing", notes)
        self.assertIn("Unavailable: not yet signed", notes)

    def test_signed_mac_packages_are_published_after_their_checks(self):
        self.linux()
        for fmt in ("zip", "dmg"):
            self.package(self.mac, "macos-arm64", fmt, signing="developer-id")
        checked = []
        site = self.assemble(mac_check=lambda path, team: checked.append((path.suffix, team)))
        self.assertEqual(site["lanes"]["macos-arm64"]["status"], "available")
        self.assertEqual(sorted(checked), [(".dmg", "ABCDE12345"), (".zip", "ABCDE12345")])
        with self.assertRaises(assembly.AssemblyError):
            self.assemble(out=self.base / "out2",
                          mac_check=lambda path, team: "spctl: rejected")

    def test_the_run_must_be_the_designated_manual_successful_one(self):
        self.linux()
        for change in ({"headSha": "d" * 40}, {"event": "push"},
                       {"workflowName": "Main CI"}, {"conclusion": "failure"}):
            with self.subTest(change=change), self.assertRaises(assembly.AssemblyError):
                self.assemble(run={**RUN, **change}, out=self.base / f"o{len(change)}")

    def test_identities_must_agree_and_bytes_must_match(self):
        self.linux()
        self.package(self.mac, "macos-arm64", "zip", signing="developer-id",
                     shared_snapshot_digest="t" * 64)
        with self.assertRaises(assembly.AssemblyError) as caught:
            self.assemble()
        self.assertIn("shared_snapshot_digest", str(caught.exception))

    def test_tampered_bytes_and_a_missing_qualification_are_refused(self):
        path = self.linux()
        path.write_bytes(b"changed")
        with self.assertRaises(assembly.AssemblyError):
            self.assemble()
        self.setUp()
        self.linux(passed=False)
        with self.assertRaises(assembly.AssemblyError):
            self.assemble()

    def test_publication_commands_never_run_and_name_both_owners(self):
        self.linux()
        self.assemble()
        text = (self.base / "out" / "PUBLISH-COMMANDS.md").read_text()
        self.assertIn("--draft --prerelease", text)
        self.assertIn(assembly.SITE_REPOSITORY, text)
        self.assertIn(f"--target {COMMIT}", text)
        self.assertIn("sh scripts/build-site.sh", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
