"""Update checks, downloads and offline import against a real signed repository.

A throwaway TUF repository is created in a temporary folder with throwaway
keys (`scripts/update_repository.py`); the network is a dictionary of those
files. Nothing is fetched, installed or signed with a real key.

    python3 -m unittest backend.coordinator.test_updates -v
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from backend.coordinator import updates
from scripts import update_repository as repository

FEED = {"metadata_url": "https://updates.example/metadata/",
        "targets_url": "https://updates.example/targets/"}
IDENTITY = {"version": "0.1.0-internal.1", "channel": "internal", "lane": "macos-arm64"}


class Response:
    def __init__(self, status, body=b""):
        self.status, self.body = status, body

    def stream(self, size):
        for start in range(0, len(self.body), size):
            yield self.body[start:start + size]

    def release_conn(self):
        pass


class Server:
    """Serves the repository folder at the feed URLs; records every request."""

    def __init__(self, repo: Path):
        self.repo, self.requests = repo, []

    def request(self, method, url, preload_content=False, redirect=False):
        self.requests.append(url)
        for prefix, folder in ((FEED["metadata_url"], "metadata"),
                               (FEED["targets_url"], "targets")):
            if url.startswith(prefix):
                path = self.repo / folder / url[len(prefix):]
                if path.is_file():
                    return Response(200, path.read_bytes())
        return Response(404)


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        base = Path(self.dir.name)
        self.keys, self.repo = base / "keys", base / "repo"
        repository.init(self.keys, self.repo, check_location=False)
        self.root = (self.repo / "trust-root.json").read_bytes()
        self.data = base / "data"
        self.server = Server(self.repo)

    def package(self, version="0.1.1-internal.1", lane="macos-arm64", schema=13,
                content=b"new package bytes"):
        path = Path(self.dir.name) / f"Refinix-{version}-{lane}.zip"
        path.write_bytes(content)
        return {"path": str(path), "lane": lane, "version": version, "build_set": "bs-2",
                "min_os": "13.3", "schema_version": schema, "engine_release": "b11390"}

    def publish(self, *packages, **kwargs):
        return repository.publish(self.keys, self.repo, channel="internal",
                                  packages=list(packages), notes="Fixes things.", **kwargs)

    def service(self, **kwargs):
        values = dict(identity=dict(IDENTITY), trust_root=self.root, feed=dict(FEED),
                      schema_version=13, os_version="26.7", pool=self.server)
        values.update(kwargs)
        return updates.UpdateService(self.data, **values)


class TestCheck(Base):
    def test_a_newer_signed_version_for_this_lane_is_offered(self):
        self.publish(self.package())
        state = self.service().check()
        self.assertEqual(state["last_check"]["result"], "update_available")
        offer = state["offer"]
        self.assertEqual((offer["version"], offer["size"]), ("0.1.1-internal.1", 17))
        self.assertEqual(offer["notes"], "Fixes things.")
        self.assertFalse(state["install_supported"])

    def test_only_signed_metadata_is_fetched_when_checking(self):
        self.publish(self.package())
        self.service().check()
        self.assertFalse(any(url.endswith(".zip") for url in self.server.requests))
        self.assertTrue(all(url.startswith("https://updates.example/")
                            for url in self.server.requests))

    def test_the_same_or_an_older_version_is_up_to_date(self):
        self.publish(self.package(version="0.1.0-internal.1"))
        state = self.service().check()
        self.assertEqual(state["last_check"]["result"], "up_to_date")
        self.assertIsNone(state["offer"])

    def test_another_platforms_update_is_not_offered(self):
        self.publish(self.package(lane="windows-x64"))
        self.assertIsNone(self.service().check()["offer"])

    def test_an_offer_that_reads_an_older_data_format_is_refused(self):
        self.publish(self.package(schema=12))
        with self.assertRaises(updates.UpdateError) as caught:
            self.service().check()
        self.assertEqual(caught.exception.code, "incompatible")

    def test_expired_metadata_is_not_trusted(self):
        self.publish(self.package(), expiry={"targets": 10, "snapshot": 10,
                                             "timestamp": -1})
        service = self.service()
        with self.assertRaises(updates.UpdateError) as caught:
            service.check()
        self.assertIn("expired", str(caught.exception))
        self.assertEqual(service.describe()["last_check"]["result"], "failed")
        self.assertIsNone(service.describe()["offer"])

    def test_metadata_signed_by_another_publisher_is_refused(self):
        self.publish(self.package())
        other = Path(self.dir.name) / "other"
        repository.init(other / "keys", other / "repo", check_location=False)
        with self.assertRaises(updates.UpdateError):
            self.service(trust_root=(other / "repo" / "trust-root.json").read_bytes()).check()

    def test_an_older_metadata_version_is_refused_after_a_newer_was_seen(self):
        self.publish(self.package())
        saved = {p.name: p.read_bytes() for p in (self.repo / "metadata").glob("*.json")}
        self.publish(self.package(version="0.1.2-internal.1"))
        self.assertEqual(self.service().check()["offer"]["version"], "0.1.2-internal.1")
        for name, data in saved.items():                    # replay the older set
            (self.repo / "metadata" / name).write_bytes(data)
        with self.assertRaises(updates.UpdateError):
            self.service().check()

    def test_a_source_checkout_or_a_package_without_a_trust_root_cannot_check(self):
        for kwargs in ({"identity": {}}, {"trust_root": b""}):
            with self.subTest(kwargs=kwargs):
                state = self.service(**kwargs).describe()
                self.assertFalse(state["can_check"])
                self.assertTrue(state["unavailable"])
        with self.assertRaises(updates.UpdateError):
            self.service(trust_root=b"").check()

    def test_a_computer_below_the_minimum_os_is_not_offered_the_update(self):
        self.publish(self.package())
        with self.assertRaises(updates.UpdateError) as caught:
            self.service(os_version="13.2").check()
        self.assertEqual(caught.exception.code, "incompatible")

    def test_a_descriptive_minimum_is_not_misread_as_a_version(self):
        package = dict(self.package(), min_os="Ubuntu 24.04 or later (glibc 2.39)")
        self.publish(package)
        self.assertIsNotNone(self.service(os_version="ubuntu 24.04").check()["offer"])

    def test_a_plain_http_feed_is_refused(self):
        self.publish(self.package())
        feed = {"metadata_url": "http://updates.example/metadata/",
                "targets_url": "http://updates.example/targets/"}
        with self.assertRaises(updates.UpdateError):
            self.service(feed=feed).check()


class TestDownload(Base):
    def test_a_verified_package_is_staged_and_its_location_shown(self):
        self.publish(self.package())
        service = self.service()
        service.check()
        service.start_download()
        service.wait(10)
        download = service.describe()["download"]
        self.assertEqual(download["state"], "verified", download)
        self.assertEqual(Path(download["path"]).read_bytes(), b"new package bytes")

    def test_a_package_changed_on_the_server_is_discarded_never_staged(self):
        self.publish(self.package())
        service = self.service()
        service.check()
        target = next((self.repo / "targets" / "internal" / "macos-arm64").glob("*.zip"))
        target.write_bytes(b"new package BYTES")             # same size, other bytes
        service.start_download()
        service.wait(10)
        download = service.describe()["download"]
        self.assertEqual(download["state"], "failed")
        self.assertIsNone(download["path"])
        self.assertFalse((self.data / "updates" / "staging" / "0.1.1-internal.1").exists())

    def test_downloading_needs_an_offer(self):
        with self.assertRaises(updates.UpdateError) as caught:
            self.service().start_download()
        self.assertEqual(caught.exception.code, "no_offer")


class TestOfflineImport(Base):
    def bundle(self, **package):
        self.publish(self.package(**package))
        return repository.bundle(self.repo, Path(self.dir.name) / "update.zip",
                                 channel="internal", lane=package.get("lane", "macos-arm64"))

    def test_a_verified_bundle_is_staged_without_any_network(self):
        path = self.bundle()
        service = self.service(feed=None, pool=None)
        state = service.import_bundle(path)
        self.assertEqual(state["download"]["state"], "verified")
        self.assertEqual(state["last_check"]["result"], "imported")

    def test_a_tampered_bundle_is_refused(self):
        path = self.bundle()
        rebuilt = Path(self.dir.name) / "tampered.zip"
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(rebuilt, "w") as target:
            for item in source.infolist():
                data = source.read(item)
                if item.filename.endswith(".zip"):
                    data = data.replace(b"new", b"bad")
                target.writestr(item, data)
        with self.assertRaises(updates.UpdateError):
            self.service(feed=None, pool=None).import_bundle(rebuilt)

    def test_a_bundle_that_is_not_newer_is_refused(self):
        path = self.bundle(version="0.1.0-internal.1")
        with self.assertRaises(updates.UpdateError) as caught:
            self.service(feed=None, pool=None).import_bundle(path)
        self.assertEqual(caught.exception.code, "not_newer")

    def test_a_bundle_with_an_escaping_path_is_refused(self):
        path = Path(self.dir.name) / "evil.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("../outside.json", "{}")
        with self.assertRaises(updates.UpdateError) as caught:
            self.service(feed=None, pool=None).import_bundle(path)
        self.assertEqual(caught.exception.code, "bad_bundle")


class TestVersions(unittest.TestCase):
    def test_versions_order_releases_after_their_prereleases(self):
        order = ["0.1.0-internal.1", "0.1.0-internal.2", "0.1.0", "0.1.1-beta.1", "0.2.0"]
        self.assertEqual(sorted(order, key=updates.version_key), order)
        with self.assertRaises(ValueError):
            updates.version_key("latest")


if __name__ == "__main__":
    unittest.main(verbosity=2)
