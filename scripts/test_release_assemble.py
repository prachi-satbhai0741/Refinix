"""Release assembly: one commit, agreeing identities, unsigned Beta with truthful fields,
every published file bound to a passing native qualification record.

    python3 -m unittest scripts.test_release_assemble -v
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from backend.coordinator import release
from scripts import qualification_record
from scripts import release_assemble as assembly

COMMIT = "c" * 40
VERSION = "0.1.0-beta.1"
RUN = {"headSha": COMMIT, "event": "workflow_dispatch", "workflowName": "Beta packages",
       "conclusion": "success"}
LANE_FILES = {"macos-arm64": ("dmg", "zip"), "windows-x64": ("exe",), "linux-x64": ("deb",)}


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.base = Path(self.dir.name)
        self.ci = self.base / "ci"
        self.ci.mkdir()
        self.mac_checks = []

    def package(self, lane, fmt, *, signing="unsigned", seal=None, name=None, **identity):
        lane_folder = self.ci / lane
        lane_folder.mkdir(exist_ok=True)
        name = name or (release.dmg_name(VERSION) if fmt == "dmg"
                        else release.asset_name(VERSION, lane, fmt))
        path = lane_folder / name
        path.write_bytes(f"{name} bytes".encode())
        embedded = {"version": VERSION, "channel": "beta", "maturity": "beta",
                    "bundle_build": 8, "source_commit": COMMIT,
                    "shared_snapshot_digest": "s" * 64, "trust_root": "r" * 64,
                    "update_feed": "f" * 64, "schema_version": 15, "lane": lane,
                    "signing": signing, "publishable": True,
                    "install_capability": "provisional",
                    "publisher": "ABCDE12345" if signing == "developer-id" else None,
                    **identity}
        if seal is None and lane == "macos-arm64" and signing == "unsigned":
            seal = "ad-hoc"
        record = {"artifact": name, "size": path.stat().st_size,
                  "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "lane": lane,
                  "minimum_os": "x", "seal": seal, "signing": signing,
                  "embedded_identity": embedded}
        Path(f"{path}.manifest.json").write_text(json.dumps(record))
        return path

    def qualify(self, lane, paths=None, **changes):
        """A passing release-bytes record for `lane`'s files, as they are now."""
        folder = self.ci / lane
        paths = paths or sorted(p for p in folder.iterdir()
                                if not p.name.endswith(".json"))
        checks = [{"check": name, "passed": True, "observed": "ok"}
                  for name in qualification_record.REQUIRED[lane]]
        record = qualification_record.build(
            lane=lane, host={"os": "test"}, checks=checks, commit_tested=COMMIT,
            packages=[qualification_record.package_entry(p) for p in paths])
        record.update(changes)
        (folder / qualification_record.REPORT_NAME[lane]).write_text(json.dumps(record))
        return record

    def full_set(self, **kwargs):
        for lane, formats in LANE_FILES.items():
            for fmt in formats:
                self.package(lane, fmt, **kwargs.get(lane, {}))
            self.qualify(lane)

    def rebuild(self, path):
        """New bytes with a matching build record: what a later build leaves
        beside an earlier build's qualification report."""
        path.write_bytes(b"rebuilt " + path.read_bytes())
        manifest = Path(f"{path}.manifest.json")
        record = json.loads(manifest.read_text())
        record.update(size=path.stat().st_size,
                      sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        manifest.write_text(json.dumps(record))

    def mac_check(self, path, team, signing):
        self.mac_checks.append((path.suffix, team, signing))
        return None

    def assemble(self, **kwargs):
        values = dict(version=VERSION, commit=COMMIT, run=dict(RUN), inputs=[self.ci],
                      out=self.base / "out", mac_check=self.mac_check)
        values.update(kwargs)
        return assembly.assemble(**values)


class TestUnsignedBeta(Base):
    def test_a_consistent_unsigned_beta_set_is_publishable_and_truthful(self):
        self.full_set()
        site = self.assemble()
        self.assertEqual(site["name"], "Refinix Beta 0.1")
        self.assertEqual(site["device_testing"], "pending")
        for lane, entry in site["lanes"].items():
            with self.subTest(lane=lane):
                self.assertEqual(entry["status"], "available")
                self.assertEqual(entry["signing"], "unsigned")
                self.assertFalse(entry["notarized"])
                self.assertEqual(entry["device_testing"], "pending")
                self.assertEqual(entry["install_capability"], "provisional")
                self.assertTrue(entry["os_warning"])
        self.assertIn("Open Anyway", site["lanes"]["macos-arm64"]["os_warning"])
        self.assertIn("Smart App Control", site["lanes"]["windows-x64"]["os_warning"])
        self.assertEqual(site["lanes"]["macos-arm64"]["seal"], "ad-hoc")
        firsts = {f["name"]: f["first_install"] for lane in site["lanes"].values()
                  for f in lane["files"]}
        self.assertEqual(firsts, {release.dmg_name(VERSION): True,
                                  release.asset_name(VERSION, "macos-arm64", "zip"): False,
                                  release.asset_name(VERSION, "windows-x64", "exe"): True,
                                  release.asset_name(VERSION, "linux-x64", "deb"): True})
        out = self.base / "out"
        self.assertEqual(len((out / "SHA256SUMS").read_text().splitlines()), 4)
        for name in qualification_record.REPORT_NAME.values():
            self.assertTrue((out / name).is_file(), name)
        self.assertEqual(sorted(self.mac_checks),
                         [(".dmg", None, "unsigned"), (".zip", None, "unsigned")])
        notes = (out / "RELEASE-NOTES.md").read_text()
        self.assertIn("# Refinix Beta 0.1", notes)
        self.assertIn("Testing on people's own computers is still pending", notes)
        self.assertIn("Open Anyway", notes)
        self.assertNotIn("tester preview", notes.lower())
        self.assertNotIn("accepted", notes.lower())
        commands = (out / "PUBLISH-COMMANDS.md").read_text()
        self.assertIn("--draft \\", commands)
        self.assertNotIn("--prerelease", commands)
        self.assertIn(f"--target {COMMIT}", commands)

    def test_changed_bytes_mismatched_identity_or_private_builds_are_refused(self):
        cases = {
            "changed bytes": lambda: (self.ci / "linux-x64" /
                                      release.asset_name(VERSION, "linux-x64", "deb")
                                      ).write_bytes(b"changed"),
            "another source": lambda: self.package("windows-x64", "exe",
                                                   shared_snapshot_digest="t" * 64),
            "a scratch build": lambda: self.package("windows-x64", "exe", publishable=False),
            "an older identity without publishable": lambda: self.package(
                "windows-x64", "exe", publishable=None),
            "a signing its lane cannot carry": lambda: self.package(
                "linux-x64", "deb", signing="developer-id"),
            "an unsealed unsigned mac": lambda: [self.package("macos-arm64", fmt, seal="none")
                                                 for fmt in ("dmg", "zip")],
            "a capability the maturity forbids": lambda: self.package(
                "windows-x64", "exe", install_capability="preview-test"),
        }
        for name, change in cases.items():
            with self.subTest(case=name):
                self.setUp()
                self.full_set()
                change()
                with self.assertRaises(assembly.AssemblyError):
                    self.assemble()

    def test_a_broken_ad_hoc_seal_is_refused(self):
        self.full_set()
        with self.assertRaises(assembly.AssemblyError) as caught:
            self.assemble(mac_check=lambda path, team, signing:
                          "codesign --verify: invalid signature")
        self.assertIn("codesign", str(caught.exception))

    def test_a_name_a_release_asset_may_rewrite_is_refused(self):
        self.full_set()
        self.package("linux-x64", "deb", name="refinix_0.1.0~2.1_amd64.deb")
        with self.assertRaises(assembly.AssemblyError):
            self.assemble()


class TestBoundQualification(Base):
    def test_every_published_file_needs_a_record_bound_to_its_bytes(self):
        deb_name = release.asset_name(VERSION, "linux-x64", "deb")
        cases = {
            "an old report beside new bytes": lambda: self.rebuild(
                self.ci / "linux-x64" / deb_name),
            "a fixture-only report": lambda: (
                self.ci / "linux-x64" / "deb-qualification.json").write_text(json.dumps(
                    {"kind": "fixture", "passed": True, "checks": []})),
            "passed as a string": lambda: self.qualify("linux-x64", passed="true"),
            "passed false": lambda: self.qualify("linux-x64", passed=False),
            "a missing required check": lambda: self.qualify(
                "linux-x64", checks=[{"check": "installed tree matches its file list",
                                      "passed": True}]),
            "a failed check": lambda: self.qualify(
                "linux-x64", checks=[{"check": n, "passed": n != "root entry refuses "
                                      "without pkexec"} for n in
                                     qualification_record.REQUIRED["linux-x64"]]),
            "malformed json": lambda: (self.ci / "linux-x64" /
                                       "deb-qualification.json").write_text("{not json"),
            "a record for another build": lambda: self.qualify(
                "linux-x64", packages=[{**qualification_record.package_entry(
                    self.ci / "linux-x64" / deb_name), "embedded_identity_sha256": "0" * 64}]),
            "no record at all": lambda: (self.ci / "linux-x64" /
                                         "deb-qualification.json").unlink(),
            "the mac record misses the zip": lambda: self.qualify(
                "macos-arm64", paths=[self.ci / "macos-arm64" / release.dmg_name(VERSION)]),
        }
        for name, change in cases.items():
            with self.subTest(case=name):
                self.setUp()
                self.full_set()
                change()
                with self.assertRaises(assembly.AssemblyError):
                    self.assemble()

    def test_the_signed_mac_path_is_kept_for_later(self):
        self.full_set(**{"macos-arm64": {"signing": "developer-id"}})
        self.qualify("macos-arm64")
        site = self.assemble()
        self.assertEqual(site["lanes"]["macos-arm64"]["signing"], "developer-id")
        self.assertTrue(site["lanes"]["macos-arm64"]["notarized"])
        self.assertEqual(sorted(self.mac_checks),
                         [(".dmg", "ABCDE12345", "developer-id"),
                          (".zip", "ABCDE12345", "developer-id")])


class TestRun(Base):
    def test_the_run_must_be_the_designated_manual_successful_one(self):
        self.full_set()
        for change in ({"headSha": "d" * 40}, {"event": "push"},
                       {"workflowName": "Main CI"}, {"conclusion": "failure"}):
            with self.subTest(change=change), self.assertRaises(assembly.AssemblyError):
                self.assemble(run={**RUN, **change}, out=self.base / f"o{len(change)}")


class TestRecordFormat(unittest.TestCase):
    def test_a_record_passes_only_with_every_required_check_passed(self):
        names = qualification_record.REQUIRED["windows-x64"]
        ok = qualification_record.build(
            lane="windows-x64", host={}, packages=[], commit_tested=COMMIT,
            checks=[{"check": n, "passed": True} for n in names])
        self.assertIs(ok["passed"], True)
        missing = qualification_record.build(
            lane="windows-x64", host={}, packages=[], commit_tested=COMMIT,
            checks=[{"check": n, "passed": True} for n in names[1:]])
        self.assertIs(missing["passed"], False)
        self.assertEqual(missing["missing"], [names[0]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
