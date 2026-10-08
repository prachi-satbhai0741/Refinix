"""The public Beta feed: real publisher, real client, throwaway keys.

Consistent snapshots, separate preview and accepted pointers, packages fetched
as release assets through allow-listed redirects, recovery packages for the
`.deb` route, offline bundles, freshness and key rotation. The "network" is a
dictionary of the feed folder plus a release-asset host; nothing is fetched,
installed or signed with a real key.

    python3 -m unittest backend.coordinator.test_updates_beta -v
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.coordinator import release, updates
from scripts import update_repository as repository

REPO = Path(__file__).resolve().parents[2]
SITE = "https://refinix.example/updates/beta/"
RELEASES = "https://github.example/owner/repo/releases/download/"
ASSETS_HOST = "assets.example"
FEED = {"metadata_url": SITE + "metadata/", "targets_url": SITE + "targets/",
        "packages_url": RELEASES, "package_hosts": [ASSETS_HOST]}
PASS = {role: f"throwaway {role} passphrase" for role in repository.ROLES}
NEW_PASS = {role: f"replacement {role} passphrase" for role in repository.ROLES}
SOURCE = "s" * 64


class Response:
    def __init__(self, status, body=b"", headers=None):
        self.status, self.body, self.headers = status, body, headers or {}

    def stream(self, size):
        for start in range(0, len(self.body), size):
            yield self.body[start:start + size]

    def release_conn(self):
        pass


class Network:
    """The site serves the feed folder; release URLs redirect to the asset host."""

    def __init__(self, feed: Path, assets: Path):
        self.feed, self.assets, self.requests = feed, assets, []
        self.redirect_to = f"https://{ASSETS_HOST}/blob/"
        self.metadata_redirect = False

    def request(self, method, url, preload_content=False, redirect=False):
        self.requests.append(url)
        if url.startswith(SITE):
            if self.metadata_redirect:
                return Response(302, headers={"Location": "https://elsewhere.example/"})
            path = self.feed / url[len(SITE):]
            return Response(200, path.read_bytes()) if path.is_file() else Response(404)
        if url.startswith(RELEASES):
            return Response(302, headers={"Location": self.redirect_to + url[len(RELEASES):]})
        prefix = f"https://{ASSETS_HOST}/blob/"
        if url.startswith(prefix):
            path = self.assets / Path(url[len(prefix):]).name
            return Response(200, path.read_bytes()) if path.is_file() else Response(404)
        return Response(404)


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        base = Path(self.dir.name)
        self.keys, self.feed, self.assets = base / "keys", base / "feed", base / "assets"
        self.assets.mkdir()
        repository.beta_init(self.keys, self.feed, passphrases=PASS, check_location=False)
        self.root = (self.feed / "metadata" / "1.root.json").read_bytes()
        self.root_sha = hashlib.sha256(self.root).hexdigest()
        self.network = Network(self.feed, self.assets)
        self.data = base / "data"
        self.build = 0

    def package(self, version, lane="linux-x64", fmt="deb", *, content=None, build=None,
                **overrides):
        label = release.parse(version)
        name = release.asset_name(version, lane, fmt)
        path = self.assets / name
        path.write_bytes(content or f"{name} bytes".encode())
        signing = repository.SIGNED_LANES.get(lane, "unsigned")
        package = {"path": str(path), "lane": lane, "version": version, "channel": "beta",
                   "maturity": label.maturity, "build_set": "bs", "min_os": "24.04",
                   "schema_version": 15, "engine_release": "b1",
                   "public_build": build or self.build, "signing": signing,
                   "install_capability": ("preview-test" if label.maturity == "preview"
                                          else "unavailable"),
                   "trust_root": self.root_sha, "shared_snapshot_digest": SOURCE}
        package.update(overrides)
        return package

    def release(self, version, lanes=(("linux-x64", "deb"),), **kwargs):
        self.build += 1
        maturity = release.parse(version).maturity
        packages = [self.package(version, lane, fmt, build=self.build, **kwargs)
                    for lane, fmt in lanes]
        repository.stage(self.keys, self.feed, maturity=maturity, packages=packages,
                         notes=f"{version} notes", passphrases=PASS)
        return repository.advance(self.keys, self.feed, passphrases=PASS)

    def service(self, version="0.1.0-preview.1", fmt="deb", lane="linux-x64", **kwargs):
        label = release.parse(version)
        identity = {"version": version, "channel": "beta", "maturity": label.maturity,
                    "lane": lane, "install_capability": "preview-test",
                    "trust_root": self.root_sha}
        values = dict(identity=identity, trust_root=self.root, feed=dict(FEED),
                      schema_version=15, os_version="24.04", pool=self.network,
                      install_format=fmt, platform="linux")
        values.update(kwargs)
        return updates.UpdateService(self.data, **values)

    def staged(self, service):
        service.check()
        service.start_download()
        service.wait(20)
        download = service.describe()["download"]
        self.assertEqual(download["state"], "verified", download)
        return service


class TestPublisher(Base):
    def test_a_preview_may_carry_only_the_ready_lanes(self):
        result = self.release("0.1.0-preview.1")
        self.assertEqual(result["targets"], 1)
        offers = repository.verify(self.feed)["offers"]
        self.assertEqual(list(offers), ["linux-x64/latest-preview.json"])

    def test_an_accepted_release_carries_every_lane(self):
        with self.assertRaises(repository.PublishError):
            self.release("0.1.0-beta.1")

    def test_unsigned_macos_or_windows_packages_are_never_published(self):
        for lane, fmt in (("macos-arm64", "zip"), ("windows-x64", "exe")):
            with self.subTest(lane=lane), self.assertRaises(repository.PublishError) as caught:
                self.release("0.1.0-preview.1", lanes=((lane, fmt),), signing="unsigned")
            self.assertIn("unavailable", str(caught.exception))

    def test_a_dmg_is_never_an_update_payload(self):
        package = self.package("0.1.0-preview.1", "macos-arm64", "zip", build=1)
        dmg = Path(package["path"]).with_name(release.dmg_name("0.1.0-preview.1"))
        dmg.write_bytes(b"dmg")
        with self.assertRaises(repository.PublishError):
            repository.stage(self.keys, self.feed, maturity="preview",
                             packages=[{**package, "path": str(dmg)}], passphrases=PASS)

    def test_labels_must_match_maturity_and_trust_this_feeds_root(self):
        bad = [{"maturity": "accepted"}, {"trust_root": "0" * 64},
               {"install_capability": "internal-test"}, {"channel": "internal"}]
        for overrides in bad:
            with self.subTest(overrides=overrides), \
                    self.assertRaises(repository.PublishError):
                repository.stage(self.keys, self.feed, maturity="preview",
                                 packages=[self.package("0.1.0-preview.1", build=1,
                                                        **overrides)], passphrases=PASS)

    def test_the_public_history_only_moves_forward(self):
        self.release("0.1.0-preview.2")
        for version in ("0.1.0-preview.1", "0.1.0-preview.2"):
            with self.subTest(version=version), self.assertRaises(repository.PublishError):
                self.release(version)
        self.build = 0                                  # a reused public build number
        with self.assertRaises(repository.PublishError):
            self.release("0.1.0-preview.3")

    def test_published_files_are_never_replaced_and_staging_waits_for_advance(self):
        self.release("0.1.0-preview.1")
        before = {p: p.read_bytes() for p in (self.feed / "metadata").glob("[0-9]*.json")}
        repository.stage(self.keys, self.feed, maturity="preview",
                         packages=[self.package("0.1.0-preview.2", build=9)],
                         passphrases=PASS)
        with self.assertRaises(repository.PublishError):
            repository.stage(self.keys, self.feed, maturity="preview",
                             packages=[self.package("0.1.0-preview.3", build=10)],
                             passphrases=PASS)
        for path, data in before.items():
            self.assertEqual(path.read_bytes(), data)
        feed = repository.Feed(self.feed)
        with self.assertRaises(repository.PublishError):
            feed.write_new(self.feed / "metadata" / "1.targets.json", b"other bytes")
        # Until advanced, clients still see preview.1 only.
        self.assertEqual(repository.verify(self.feed)["offers"]["linux-x64/latest-preview.json"]
                         ["version"], "0.1.0-preview.1")

    def test_advancing_checks_the_released_assets_anonymously(self):
        repository.stage(self.keys, self.feed, maturity="preview",
                         packages=[self.package("0.1.0-preview.1", build=1)],
                         passphrases=PASS)
        fetched = []

        def fetch(url, limit):
            fetched.append(url)
            path = Path(self.dir.name) / "download"
            path.write_bytes(b"something else")
            return str(path)
        with self.assertRaises(repository.PublishError):
            repository.advance(self.keys, self.feed, packages_url=RELEASES, fetch=fetch,
                               passphrases=PASS)
        self.assertFalse((self.feed / "metadata" / "timestamp.json").exists())

        def good(url, limit):
            path = Path(self.dir.name) / "download"
            shutil.copyfile(self.assets / Path(url).name, path)
            return str(path)
        result = repository.advance(self.keys, self.feed, packages_url=RELEASES, fetch=good,
                                    passphrases=PASS)
        self.assertEqual(result["assets_checked"],
                         [release.package_target("0.1.0-preview.1", "linux-x64", "deb")])
        self.assertEqual(fetched, [RELEASES + release.package_target(
            "0.1.0-preview.1", "linux-x64", "deb")])

    def test_the_monitor_fails_close_to_expiry_and_lists_renewals(self):
        self.release("0.1.0-preview.1")
        later = datetime.now(timezone.utc) + timedelta(days=5)
        report = repository.verify(self.feed, now=later, monitor=True)
        self.assertTrue(any("timestamp" in p for p in report["problems"]))
        quiet = repository.verify(self.feed, monitor=True)
        self.assertEqual(quiet["problems"], [])


class TestClient(Base):
    def test_a_preview_install_is_offered_the_newest_preview_through_its_pointer(self):
        self.release("0.1.0-preview.1")
        self.release("0.1.0-preview.2")
        offer = self.service().check()["offer"]
        self.assertEqual((offer["version"], offer["maturity"], offer["format"]),
                         ("0.1.0-preview.2", "preview", "deb"))
        self.assertEqual(offer["latest_target"], "beta/linux-x64/latest-preview.json")
        self.assertFalse(any(RELEASES in url for url in self.network.requests),
                         "checking fetches signed metadata only")

    def test_a_preview_install_moves_on_to_an_accepted_build(self):
        self.release("0.1.0-preview.1")
        lanes = (("linux-x64", "deb"), ("macos-arm64", "zip"), ("windows-x64", "exe"))
        self.release("0.1.0-beta.1", lanes=lanes)
        offer = self.service().check()["offer"]
        self.assertEqual((offer["version"], offer["latest_target"]),
                         ("0.1.0-beta.1", "beta/linux-x64/latest.json"))
        self.release("0.1.1-preview.1")
        self.assertEqual(self.service().check()["offer"]["version"], "0.1.1-preview.1")

    def test_an_accepted_install_never_takes_a_preview(self):
        lanes = (("linux-x64", "deb"), ("macos-arm64", "zip"), ("windows-x64", "exe"))
        self.release("0.1.0-beta.1", lanes=lanes)
        self.release("0.1.1-preview.1")
        service = self.service("0.1.0-beta.1")
        self.assertIsNone(service.check()["offer"])
        self.assertFalse(any("latest-preview" in url for url in self.network.requests))

    def test_a_package_for_another_install_format_is_never_offered(self):
        self.release("0.1.0-preview.2", lanes=(("linux-x64", "appimage"),))
        with self.assertRaises(updates.UpdateError) as caught:
            self.service().check()
        self.assertEqual(caught.exception.code, "format")

    def test_packages_follow_only_allow_listed_redirects_and_are_verified(self):
        self.release("0.1.0-preview.1")
        self.release("0.1.0-preview.2")
        service = self.staged(self.service())
        package = Path(service.describe()["download"]["path"])
        self.assertEqual(package.read_bytes(), (self.assets / package.name).read_bytes())
        self.assertTrue(any(url.startswith(f"https://{ASSETS_HOST}/")
                            for url in self.network.requests))
        # The installed version's own package is kept for going back.
        recovery = package.parent / "recovery" / release.asset_name(
            "0.1.0-preview.1", "linux-x64", "deb")
        self.assertTrue(recovery.is_file())
        verified = service.admit_staged()
        self.assertEqual(verified["recovery"]["version"], "0.1.0-preview.1")
        self.assertEqual(verified["maturity"], "preview")

    def test_a_redirect_elsewhere_or_on_metadata_is_refused(self):
        self.release("0.1.0-preview.2")
        self.network.redirect_to = "https://evil.example/blob/"
        service = self.service()
        service.check()
        service.start_download()
        service.wait(10)
        download = service.describe()["download"]
        self.assertEqual(download["state"], "failed")
        self.assertIn("not one of this channel's download hosts", download["error"])
        self.network.metadata_redirect = True
        with self.assertRaises(updates.UpdateError):
            self.service().check()

    def test_a_changed_release_asset_is_discarded(self):
        self.release("0.1.0-preview.2")
        name = release.asset_name("0.1.0-preview.2", "linux-x64", "deb")
        data = (self.assets / name).read_bytes()
        (self.assets / name).write_bytes(data[:-1] + b"X")
        service = self.service()
        service.check()
        service.start_download()
        service.wait(10)
        self.assertEqual(service.describe()["download"]["state"], "failed")

    def test_an_already_verified_download_installs_after_its_metadata_expires(self):
        self.release("0.1.0-preview.1")
        self.release("0.1.0-preview.2")
        service = self.staged(self.service())
        # Let every role expire, then admit offline: the clock is not judged again.
        repository.stage(self.keys, self.feed, maturity="preview",
                         packages=[self.package("0.1.0-preview.3", build=30)],
                         passphrases=PASS)
        repository.advance(self.keys, self.feed, passphrases=PASS,
                           now=datetime.now(timezone.utc) - timedelta(days=400),
                           expiry={"targets": 1, "snapshot": 1, "timestamp": 1, "root": 1})
        self.assertEqual(service.admit_staged()["version"], "0.1.0-preview.2")
        with self.assertRaises(updates.UpdateError):
            self.service().check()                 # a fresh check refuses expired metadata

    def test_a_staged_preview_is_refused_by_an_accepted_install(self):
        self.release("0.1.0-preview.2")
        self.staged(self.service())
        # The same data folder opened by an accepted build finds the staged
        # preview and refuses to install it.
        accepted = self.service("0.0.9-beta.1")
        self.assertIsNotNone(accepted.staged_folder())
        with self.assertRaises(updates.UpdateError) as caught:
            accepted.admit_staged()
        self.assertIn("preview", str(caught.exception))


class TestOffline(Base):
    def bundle(self, *, recovery=("0.1.0-preview.1",), fmt="deb"):
        output = Path(self.dir.name) / "bundles"
        output.mkdir(exist_ok=True)
        return repository.beta_bundle(self.feed, self.assets, output, lane="linux-x64",
                                      fmt=fmt, maturity="preview",
                                      recovery_versions=recovery)

    def test_a_bundle_imports_with_its_recovery_package_without_any_network(self):
        self.release("0.1.0-preview.1")
        self.release("0.1.0-preview.2")
        path = self.bundle()
        state = self.service(pool=None, feed=None).import_bundle(path)
        self.assertEqual(state["download"]["state"], "verified")
        self.assertEqual(state["offer"]["recovery"]["version"], "0.1.0-preview.1")

    def test_a_bundle_without_the_recovery_package_still_imports_without_it(self):
        self.release("0.1.0-preview.1")
        self.release("0.1.0-preview.2")
        state = self.service(pool=None, feed=None).import_bundle(self.bundle(recovery=()))
        self.assertIsNone(state["offer"]["recovery"])

    def test_an_expired_bundle_is_refused(self):
        self.release("0.1.0-preview.1")
        self.build += 1
        repository.stage(self.keys, self.feed, maturity="preview",
                         packages=[self.package("0.1.0-preview.2", build=self.build)],
                         passphrases=PASS)
        repository.advance(self.keys, self.feed, passphrases=PASS,
                           expiry={**repository.EXPIRY_DAYS, "timestamp": -1})
        with self.assertRaises(updates.UpdateError):
            self.service(pool=None, feed=None).import_bundle(self.bundle(recovery=()))


class TestFreshness(Base):
    def test_refresh_renews_the_timestamp_and_a_low_snapshot(self):
        self.release("0.1.0-preview.1")
        first = repository.refresh(self.keys, self.feed, passphrases=PASS)
        self.assertFalse(first["snapshot_renewed"])
        later = repository.refresh(self.keys, self.feed, passphrases=PASS,
                                   now=datetime.now(timezone.utc) + timedelta(days=20))
        self.assertTrue(later["snapshot_renewed"])
        self.assertEqual(self.service().check()["last_check"]["result"], "up_to_date")

    def test_renewed_targets_keep_every_published_package(self):
        self.release("0.1.0-preview.1")
        repository.renew_targets(self.keys, self.feed, passphrases=PASS)
        repository.advance(self.keys, self.feed, passphrases=PASS)
        self.assertIn("linux-x64/latest-preview.json", repository.verify(self.feed)["offers"])

    def test_withdrawing_points_back_and_installs_see_not_newer(self):
        self.release("0.1.0-preview.1")
        self.release("0.1.0-preview.2")
        repository.withdraw(self.keys, self.feed, lane="linux-x64",
                            pointer="latest-preview.json", to_version="0.1.0-preview.1",
                            passphrases=PASS)
        repository.advance(self.keys, self.feed, passphrases=PASS)
        self.assertIsNone(self.service().check()["offer"])

    def test_rotating_online_keys_recovers_from_a_fast_forward_attack(self):
        self.release("0.1.0-preview.1")
        self.release("0.1.0-preview.2")
        service = self.service()
        service.check()
        # Someone holding the online keys pushes the versions far ahead.
        from tuf.api.metadata import Metadata
        stolen = Metadata.from_bytes((self.feed / "metadata" / "timestamp.json").read_bytes())
        stolen.signed.version = 10_000
        stolen.signatures.clear()
        stolen.sign(repository.load_role(self.keys, "timestamp", PASS))
        good = (self.feed / "metadata" / "timestamp.json").read_bytes()
        (self.feed / "metadata" / "timestamp.json").write_bytes(stolen.to_bytes())
        service.check()
        (self.feed / "metadata" / "timestamp.json").write_bytes(good)
        with self.assertRaises(updates.UpdateError):
            self.service().check()                     # legitimate metadata now refused
        new_keys = Path(self.dir.name) / "new-keys"
        repository.rotate_root(self.keys, self.feed, new_keys_dir=new_keys,
                               replace=("snapshot", "timestamp"), passphrases=PASS,
                               new_passphrases=NEW_PASS, check_location=False)
        repository.refresh(new_keys, self.feed, passphrases=NEW_PASS)
        self.assertEqual(self.service().check()["offer"]["version"], "0.1.0-preview.2")


class TestInternalCompatibility(unittest.TestCase):
    """The client from e234a0a (shipped in internal.6), unchanged, still reads
    what the new publisher writes for the internal channel."""

    def old_updates(self):
        try:
            source = subprocess.run(["git", "show", "e234a0a:backend/coordinator/updates.py"],
                                    cwd=REPO, capture_output=True, text=True, check=True,
                                    timeout=30).stdout
        except (OSError, subprocess.SubprocessError):
            self.skipTest("the e234a0a source is not in this checkout")
        module = types.ModuleType("refinix_internal6_updates")
        module.__file__ = "e234a0a:backend/coordinator/updates.py"
        sys.modules[module.__name__] = module
        self.addCleanup(sys.modules.pop, module.__name__, None)
        exec(compile(source, module.__file__, "exec"), module.__dict__)  # noqa: S102
        return module

    def test_internal6_client_checks_and_downloads_from_the_new_publisher(self):
        old = self.old_updates()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repository.init(base / "keys", base / "repo", check_location=False)
            package = base / "Refinix-0.1.0-internal.7-macos-arm64.zip"
            package.write_bytes(b"internal.7 bytes")
            repository.publish(base / "keys", base / "repo", channel="internal", packages=[
                {"path": str(package), "lane": "macos-arm64", "version": "0.1.0-internal.7",
                 "build_set": "bs", "min_os": "26.0", "schema_version": 15,
                 "engine_release": "b1"}])
            output = base / "bundle.zip"
            repository.bundle(base / "repo", output, channel="internal", lane="macos-arm64")
            service = old.UpdateService(
                base / "data", identity={"version": "0.1.0-internal.6", "channel": "internal",
                                         "lane": "macos-arm64"},
                trust_root=(base / "repo" / "trust-root.json").read_bytes(), feed=None,
                schema_version=15, os_version="26.7", pool=None)
            state = service.import_bundle(output)
            self.assertEqual(state["download"]["state"], "verified")
            self.assertEqual(state["offer"]["version"], "0.1.0-internal.7")


if __name__ == "__main__":
    unittest.main(verbosity=2)
