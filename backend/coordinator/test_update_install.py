"""The internal update folder, kept signed evidence and offline install admission.

Real signed repositories (scripts/update_repository.py) and real app-shaped
packages; nothing touches the network.

    python3 -m unittest backend.coordinator.test_update_install -v
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.coordinator import updates
from backend.coordinator.test_app_archive import IDENTITY as APP_IDENTITY, write_app
from scripts import update_repository as repository

RUNNING = "0.1.0-internal.1"


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        base = Path(self.dir.name)
        self.keys, self.repo = base / "keys", base / "repo"
        repository.init(self.keys, self.repo, check_location=False)
        self.root = (self.repo / "trust-root.json").read_bytes()
        self.root_sha = hashlib.sha256(self.root).hexdigest()
        self.data = base / "data"
        self.data.mkdir()
        self.folder = base / "Refinix Updates"
        self.folder.mkdir()
        self.apps = base / "apps"
        (self.apps / "Refinix.app" / "Contents" / "MacOS").mkdir(parents=True)
        (self.apps / "Refinix.app" / "Contents" / "MacOS" / "Refinix").write_bytes(b"old")

    def package(self, version="0.1.0-internal.2", schema=15, **identity):
        path = Path(self.dir.name) / f"Refinix-{version}-macos-arm64.zip"
        write_app(path, identity={**APP_IDENTITY, "version": version,
                                  "trust_root": self.root_sha, "schema_version": schema,
                                  **identity}, root=self.root)
        return {"path": str(path), "lane": "macos-arm64", "version": version,
                "build_set": "bs", "min_os": "26.0", "schema_version": schema,
                "engine_release": "b1"}

    def publish(self, *packages, **kwargs):
        return repository.publish(self.keys, self.repo, channel="internal",
                                  packages=list(packages), notes="Fixes things.", **kwargs)

    def bundle(self, *packages, folder=None, **kwargs):
        self.publish(*packages, **kwargs)
        return repository.bundle(self.repo, folder or self.folder, channel="internal",
                                 lane="macos-arm64")

    def service(self, **kwargs):
        values = dict(
            identity={"version": RUNNING, "channel": "internal", "lane": "macos-arm64",
                      "install_capability": "internal-test", "trust_root": self.root_sha},
            trust_root=self.root, feed={"local_folder": str(self.folder)},
            schema_version=15, os_version="26.7", pool=None,
            bundle=self.apps / "Refinix.app", platform="darwin",
            environ={updates.TEST_INSTALL_ROOT: str(self.apps)},
            codesign=lambda _app: None)
        values.update(kwargs)
        return updates.UpdateService(self.data, **values)

    def staged(self, service=None, *packages):
        self.bundle(*(packages or (self.package(),)))
        service = service or self.service()
        service.check()
        service.start_download()
        service.wait(20)
        self.assertEqual(service.describe()["download"]["state"], "verified",
                         service.describe()["download"])
        return service

    def rotate(self, role="timestamp"):
        """Root version + 1 with a new key for `role`, signed by the root key."""
        from tuf.api.metadata import Metadata
        current = Metadata.from_file(str(self.repo / "metadata" / "root.json")) \
            if (self.repo / "metadata" / "root.json").exists() else \
            Metadata.from_file(str(self.repo / "metadata" / "1.root.json"))
        root = current.signed
        for keyid in list(root.roles[role].keyids):
            root.revoke_key(keyid, role)
        seed, key = repository.new_key()
        root.add_key(key, role)
        root.version += 1
        current.signatures.clear()
        current.sign(repository.load_signer(self.keys, "root"))
        current.to_file(str(self.repo / "metadata" / f"{root.version}.root.json"))
        current.to_file(str(self.repo / "metadata" / "root.json"))
        stored = json.loads((self.keys / "keys.json").read_text())
        stored[role] = {"seed": seed.hex(), "key": key.to_dict(), "keyid": key.keyid}
        (self.keys / "keys.json").write_text(json.dumps(stored))


class TestFolder(Base):
    def test_the_newest_verified_bundle_is_offered_from_the_folder(self):
        self.bundle(self.package())
        state = self.service().check()
        self.assertEqual(state["source"], "folder")
        self.assertTrue(state["header_eligible"])
        self.assertEqual(state["offer"]["version"], "0.1.0-internal.2")
        self.assertEqual(state["offer"]["source"]["kind"], "bundle")
        self.assertEqual(state["last_check"]["result"], "update_available")

    def test_an_empty_or_older_folder_is_up_to_date_and_says_where(self):
        state = self.service().check()
        self.assertEqual(state["last_check"]["result"], "up_to_date")
        self.assertIn("No newer verified update in", state["last_check"]["detail"])
        self.bundle(self.package(version=RUNNING))
        state = self.service().check()
        self.assertEqual(state["last_check"]["result"], "up_to_date")
        self.assertIsNone(state["offer"])

    def test_more_bundles_than_are_checked_is_incomplete_never_up_to_date(self):
        for index in range(updates.MAX_FOLDER_FILES + 1):
            (self.folder / f"Refinix-0.0.{index}-macos-arm64-update.zip").write_bytes(b"x")
        state = self.service().check()
        self.assertEqual(state["last_check"]["result"], "incomplete")
        self.assertIsNone(state["offer"])

    def test_a_rejected_bundle_is_not_reopened_until_trust_changes(self):
        bad = self.folder / "Refinix-0.1.0-internal.9-macos-arm64-update.zip"
        bad.write_bytes(b"not a zip")
        service = self.service()
        real = service._bundle_offer
        calls = []

        def counted(path):
            calls.append(path)
            return real(path)

        with patch.object(service, "_bundle_offer", side_effect=counted):
            service.check()
            service.check()
            self.assertEqual(len(calls), 1)
            self.bundle(self.package())          # a newer verified bundle arrives
            service.check()                      # trust state moves on
            service.check()
        self.assertIn(bad, calls[1:])

    def test_expired_metadata_in_the_folder_is_rejected(self):
        self.bundle(self.package(), expiry={"targets": 10, "snapshot": 10, "timestamp": -1})
        state = self.service().check()
        self.assertIsNone(state["offer"])
        self.assertIn("expired", state["last_check"]["detail"])

    def test_a_bundle_changed_after_the_check_is_not_copied(self):
        path = self.bundle(self.package())
        service = self.service()
        service.check()
        with open(path, "ab") as handle:
            handle.write(b"tail")
        with self.assertRaises(updates.UpdateError) as caught:
            service.start_download()
        self.assertEqual(caught.exception.code, "changed")

    def test_the_folder_exists_only_on_the_internal_channel(self):
        identity = {"version": RUNNING, "channel": "beta", "lane": "macos-arm64",
                    "install_capability": "internal-test"}
        state = self.service(identity=identity).describe()
        self.assertIsNone(state["folder"])
        self.assertFalse(state["header_eligible"])

    def test_the_header_needs_capability_and_a_helper_for_this_computer(self):
        unavailable = {"version": RUNNING, "channel": "internal", "lane": "macos-arm64"}
        self.assertFalse(self.service(identity=unavailable).describe()["header_eligible"])
        self.assertFalse(self.service(platform="linux").describe()["header_eligible"])
        self.assertFalse(self.service(trust_root=b"").describe()["header_eligible"])


class TestEvidence(Base):
    def test_a_staged_package_keeps_the_signed_metadata_that_verified_it(self):
        service = self.staged()
        folder = service.staged_folder()
        evidence = folder / updates.EVIDENCE
        names = sorted(p.name for p in evidence.iterdir())
        self.assertEqual(names, ["latest.json", "record.json", "root", "snapshot.json",
                                 "targets.json", "timestamp.json"])
        verified = updates.verify_evidence(folder, anchor=self.root,
                                           local_metadata=self.data / "updates" / "metadata")
        self.assertEqual(verified["version"], "0.1.0-internal.2")

    def test_it_installs_offline_after_its_metadata_has_since_expired(self):
        service = self.staged()
        from tuf.api.metadata import Signed
        with patch.object(Signed, "is_expired", return_value=True):
            self.assertEqual(service.admit_staged()["version"], "0.1.0-internal.2")

    def test_a_new_import_with_expired_metadata_is_refused(self):
        self.bundle(self.package(), expiry={"targets": 10, "snapshot": 10, "timestamp": -1})
        path = next(self.folder.glob("*.zip"))
        with self.assertRaises(updates.UpdateError):
            self.service().import_bundle(path)

    def test_substituted_bytes_record_offer_or_missing_evidence_are_refused(self):
        def tamper_package(folder):
            package = next(folder.glob("*.zip"))
            data = bytearray(package.read_bytes())
            data[len(data) // 2] ^= 0xFF
            package.write_bytes(bytes(data))

        def tamper_record(folder):
            path = folder / updates.EVIDENCE / updates.RECORD
            record = json.loads(path.read_text())
            record["sha256"] = "0" * 64
            path.write_text(json.dumps(record))

        def tamper_latest(folder):
            path = folder / updates.EVIDENCE / updates.LATEST
            path.write_text(path.read_text().replace("0.1.0-internal.2", "0.1.0-internal.3"))

        def remove_targets(folder):
            (folder / updates.EVIDENCE / "targets.json").unlink()

        for label, step in {"package": tamper_package, "record": tamper_record,
                            "latest": tamper_latest, "targets": remove_targets}.items():
            with self.subTest(label):
                service = self.staged()
                step(service.staged_folder())
                with self.assertRaises(updates.UpdateError) as caught:
                    service.admit_staged()
                self.assertEqual(caught.exception.code, "evidence")
                shutil.rmtree(self.data / "updates")
                for path in self.folder.iterdir():
                    path.unlink()

    def test_rotated_roots_are_followed_and_must_be_consecutive(self):
        self.rotate("timestamp")
        service = self.staged()
        folder = service.staged_folder()
        kept = folder / updates.EVIDENCE / "root" / "2.root.json"
        self.assertTrue(kept.is_file())
        self.assertEqual(service.admit_staged()["version"], "0.1.0-internal.2")
        shutil.copyfile(kept, kept.with_name("4.root.json"))     # a repeated version
        with self.assertRaises(updates.UpdateError) as caught:
            updates.verify_evidence(folder, anchor=self.root, local_metadata=None)
        self.assertIn("consecutive", str(caught.exception))
        kept.with_name("4.root.json").unlink()
        kept.unlink()                                             # the rotation is lost
        with self.assertRaises(updates.UpdateError):
            updates.verify_evidence(folder, anchor=self.root, local_metadata=None)

    def test_keys_rotated_after_verification_invalidate_the_kept_evidence(self):
        service = self.staged()
        self.rotate("timestamp")
        self.bundle(self.package())              # re-signed with the new timestamp key
        self.service().check()                   # the client now trusts root 2
        self.assertTrue((self.data / "updates" / "metadata" / "root_history"
                         / "2.root.json").is_file())
        with self.assertRaises(updates.UpdateError) as caught:
            service.admit_staged()
        self.assertEqual(caught.exception.code, "evidence")

    def test_missing_local_root_history_cannot_fall_back_to_revoked_keys(self):
        service = self.staged()
        for _ in range(2):
            self.rotate("timestamp")
            self.bundle(self.package())
            self.service().check()
        metadata = self.data / "updates" / "metadata"
        self.assertTrue((metadata / "root_history" / "3.root.json").is_file())
        (metadata / "root_history" / "2.root.json").unlink()
        with self.assertRaises(updates.UpdateError) as caught:
            service.admit_staged()
        self.assertEqual(caught.exception.code, "evidence")
        self.assertIn("root 2", str(caught.exception))

    def test_unreadable_latest_local_root_refuses_kept_evidence(self):
        service = self.staged()
        path = self.data / "updates" / "metadata" / "root.json"
        path.unlink()
        for content in (None, b"{broken", b"[]"):
            with self.subTest(content=content):
                if content is not None:
                    path.write_bytes(content)
                with self.assertRaises(updates.UpdateError) as caught:
                    service.admit_staged()
                self.assertEqual(caught.exception.code, "evidence")

    def test_not_newer_other_lane_or_unsupported_data_format_is_refused(self):
        service = self.staged()
        running = service.identity
        service.identity = dict(running, version="0.1.0-internal.5")
        with self.assertRaises(updates.UpdateError) as caught:
            service.admit_staged()
        self.assertEqual(caught.exception.code, "not_newer")
        service.identity = running
        other = dict(service.identity, lane="linux-x64")
        with self.assertRaises(updates.UpdateError):
            self.service(identity=other).admit_staged()
        with self.assertRaises(updates.UpdateError) as caught:
            self.service(schema_version=14).admit_staged()
        self.assertEqual(caught.exception.code, "incompatible")

    def test_a_higher_data_format_needs_a_declared_qualified_migration(self):
        self.assertIsNone(updates.compatible_schema(15, 15, []))
        self.assertIsNotNone(updates.compatible_schema(15, 16, []))
        self.assertIsNone(updates.compatible_schema(15, 16, [[15, 16]]))
        self.assertIsNotNone(updates.compatible_schema(15, 14, [[15, 14]]))
        self.bundle(self.package(schema=16))
        state = self.service().check()
        self.assertIsNone(state["offer"])
        self.assertIn("qualified migration", state["last_check"]["detail"])

    def test_a_staged_package_is_found_again_after_a_restart(self):
        self.staged()
        later = self.service()
        self.assertEqual(later.describe()["download"]["state"], "verified")
        self.assertEqual(later.admit_staged()["version"], "0.1.0-internal.2")


class TestPrepare(Base):
    def test_repeated_preparation_reuses_one_verified_incoming_app(self):
        service = self.staged()
        first = service.prepare_install(wait=True)["install"]
        self.assertEqual(first["state"], "ready")
        for _ in range(20):
            self.assertEqual(service.prepare_install(wait=True)["install"], first)
        self.assertEqual([p.name for p in (service.home / "install").iterdir()],
                         [first["update_id"]])
        package = Path(service.download.path)
        original = package.read_bytes()
        package.write_bytes(b"tampered")
        with self.assertRaises(updates.UpdateError):
            service.prepare_install()
        self.assertEqual(service.install, first, "refusal cannot discard the prepared app")
        package.write_bytes(original)
        identity = Path(first["incoming"]) / "Contents" / "Resources" / "refinix-build.json"
        value = json.loads(identity.read_text())
        value["version"] = "0.1.0-internal.99"
        identity.write_text(json.dumps(value))
        with self.assertRaises(updates.UpdateError):
            service.prepare_install()
        self.assertEqual(service.install, first)

    def test_preparation_excludes_other_update_work_until_it_finishes(self):
        from backend.coordinator import app_archive
        service = self.staged()
        entered, release = threading.Event(), threading.Event()
        extract = app_archive.extract
        def paused(*args):
            entered.set()
            if not release.wait(5):
                raise AssertionError("test preparation was not released")
            return extract(*args)
        with patch.object(app_archive, "extract", side_effect=paused) as expansion:
            service.prepare_install()
            try:
                self.assertTrue(entered.wait(2))
                for action in (service.prepare_install, service.start_download, service.check):
                    for _ in range(5):
                        with self.assertRaises(updates.UpdateError) as caught:
                            action()
                        self.assertEqual(caught.exception.code, "busy")
            finally:
                release.set()
                service._install_thread.join(10)
            self.assertEqual(expansion.call_count, 1)
            self.assertEqual(service.install["state"], "ready")
        self.assertEqual(service.prepare_install(wait=True)["install"], service.install)

    def test_the_verified_app_is_expanded_beside_the_installation(self):
        service = self.staged()
        state = service.prepare_install(wait=True)
        self.assertEqual(state["install"]["state"], "ready", state["install"])
        incoming = Path(state["install"]["incoming"])
        self.assertTrue((incoming / "Contents" / "Frameworks" / "Python.framework"
                         / "Python").is_symlink())
        self.assertEqual(state["install"]["install_path"],
                         str(self.apps / "Refinix.app"))
        service.cancel_install()
        self.assertFalse(incoming.exists())

    def test_an_app_outside_applications_cannot_be_replaced(self):
        service = self.staged()
        elsewhere = self.service(bundle=Path(self.dir.name) / "Downloads" / "Refinix.app",
                                 environ={})
        reason = elsewhere.describe()["install_reason"]
        self.assertIn("only when it is in Applications", reason)
        with self.assertRaises(updates.UpdateError):
            elsewhere.prepare_install()
        translocated = self.service(
            bundle=Path("/private/var/folders/x/AppTranslocation/y/d/Refinix.app"))
        self.assertIn("temporary copy", translocated.describe()["install_reason"])
        self.assertIsNotNone(service)

    def test_too_little_disk_space_changes_nothing(self):
        service = self.staged()
        usage = shutil.disk_usage(self.data)
        with patch.object(updates.shutil, "disk_usage",
                          return_value=usage._replace(free=1024)):
            state = service.prepare_install(wait=True)
        self.assertEqual(state["install"]["code"], "disk")
        self.assertFalse(any((self.data / "updates" / "install").glob("*")))

    def test_an_app_that_disagrees_with_its_signed_offer_is_refused(self):
        service = self.staged(None, self.package(version="0.1.0-internal.2",
                                                 schema=15, channel="beta"))
        state = service.prepare_install(wait=True)
        self.assertEqual(state["install"]["state"], "failed")
        self.assertIn("channel", state["install"]["error"])
        self.assertFalse(any((self.data / "updates" / "install").glob("*")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
