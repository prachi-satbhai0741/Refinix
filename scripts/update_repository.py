#!/usr/bin/env python3
"""Create and sign Refinix update metadata (TUF) for one channel.

Release tooling, never shipped in a package.

**Internal channel** (test keys; unchanged layout so installed internal builds
keep updating):

    python scripts/update_repository.py init --channel internal \\
        --keys ~/refinix-keys/internal --repo ~/refinix-repo/internal
    python scripts/update_repository.py publish --keys ... --repo ... \\
        --channel internal --notes "What changed" out/Refinix-0.1.1-internal.1-*.zip
    python scripts/update_repository.py bundle --channel internal --repo ... \\
        --lane macos-arm64 --output ~/"Refinix Updates"

Internal signing uses securesystemslib's bundled pure-Python Ed25519 (not
constant time): acceptable for locally held test keys only.

**Beta channel** (public trust root; `cryptography` from
scripts/requirements-release.lock; every key an encrypted PEM file whose
passphrase is typed, or given to a workflow as `REFINIX_KEY_PASSPHRASE_<ROLE>`):

    init           root/targets keys (offline) and snapshot/timestamp keys (online)
    stage          offline: add packages `v<version>/<asset>` and the lanes' signed
                   pointers, signed with the targets key; nothing is offered yet
    advance        online: check the staged targets, optionally the released assets,
                   then sign snapshot and timestamp — the feed now offers them
    refresh        online, daily: re-sign timestamp (and snapshot when it has
                   under 14 days left)
    renew-targets  offline: same targets, new expiry (when 60 days or fewer remain)
    rotate-root    offline: next root version, optionally replacing role keys
    withdraw       offline: point a lane's pointer back at an earlier published build
    verify         the real client against the folder or the live URL; with
                   --monitor, fail when a role is close to expiring; with
                   --expect, fail unless it serves exactly the expected feed
    expected       what a feed folder (a signed commit) should serve: metadata
                   versions and hashes and every lane's offers, for --expect
    preview        what the staged targets change, without changing anything
    bundle         one offline-import file from the current feed

The feed folder is what the distribution site serves at `.../updates/beta/`:

    metadata/<v>.root.json      every root version (immutable)
    metadata/<N>.targets.json   immutable; package targets and pointers
    metadata/<N>.snapshot.json  immutable
    metadata/timestamp.json     the only file that changes
    targets/beta/<lane>/<sha256>.latest.json           Beta / final pointer
    targets/beta/<lane>/<sha256>.latest-preview.json   tester-preview pointer

Packages are not in the folder: they are release assets fetched from
`<packages_url>v<version>/<asset>` and authenticated by their signed target.
No file is ever overwritten with different bytes; only `timestamp.json` is
replaced. Versions only go up, and a failure is fixed forward with newer
metadata, never by restoring older files.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import secrets
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.coordinator import release  # noqa: E402

ROLES = ("root", "targets", "snapshot", "timestamp")
OFFLINE_ROLES = ("root", "targets")
ONLINE_ROLES = ("snapshot", "timestamp")
EXPIRY_DAYS = {"root": 365, "targets": 180, "snapshot": 30, "timestamp": 7}
LANES = ("macos-arm64", "windows-x64", "linux-x64")
# Re-sign the snapshot during a refresh once it has less than this left.
SNAPSHOT_REFRESH_DAYS = 14
# The live-feed monitor fails below these (days left).
MONITOR_DAYS = {"timestamp": 3, "snapshot": 7, "targets": 45, "root": 90}
# Offline renewal is due at or below these (days left).
RENEW_DAYS = {"targets": 60, "root": 120}
PASSPHRASE_VARIABLE = "REFINIX_KEY_PASSPHRASE_{role}"
# What a staged Beta package may claim it can do with its own updates.
CAPABILITIES_FOR = {"preview": ("preview-test", "provisional", "unavailable"),
                    "beta": ("provisional", "qualified", "unavailable"),
                    "final": ("qualified", "unavailable")}
# The signing a staged package of each lane may carry. Unsigned macOS and
# Windows packages are published as the Beta; their signing is recorded in
# the signed target, never hidden.
SIGNING_ALLOWED = {"macos-arm64": ("developer-id", "unsigned"),
                   "windows-x64": ("authenticode", "unsigned"),
                   "linux-x64": ("unsigned",)}


class PublishError(RuntimeError):
    pass


def _now(now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)).replace(microsecond=0)


def _expires(role: str, now: datetime | None = None, days: dict | None = None) -> datetime:
    return _now(now) + timedelta(days=(days or EXPIRY_DAYS)[role])


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _outside_repository(folder: Path) -> None:
    folder = Path(folder).resolve()
    if folder == ROOT or ROOT in folder.parents:
        raise SystemExit("refusing to keep signing keys inside the repository")


# ==========================================================================
# Internal channel (test keys, original layout)
# ==========================================================================

def _ed25519():
    from securesystemslib._vendor.ed25519 import ed25519
    return ed25519


def new_key() -> tuple[bytes, "object"]:
    """A fresh Ed25519 seed and its public `SSlibKey`."""
    from securesystemslib.signer import SSlibKey
    seed = secrets.token_bytes(32)
    public = _ed25519().publickey_unsafe(seed)
    key = SSlibKey.from_dict(
        hashlib.sha256(public).hexdigest(),
        {"keytype": "ed25519", "scheme": "ed25519", "keyval": {"public": public.hex()}})
    return seed, key


def signer(seed: bytes, key):
    from securesystemslib.signer import Signature, Signer

    class PurePythonEd25519(Signer):
        def __init__(self):
            self._seed, self._key = seed, key
            self._public = bytes.fromhex(key.keyval["public"])

        @property
        def public_key(self):
            return self._key

        @classmethod
        def from_priv_key_uri(cls, *args, **kwargs):     # pragma: no cover
            raise NotImplementedError

        def sign(self, payload: bytes):
            raw = _ed25519().signature_unsafe(payload, self._seed, self._public)
            return Signature(self._key.keyid, raw.hex())

    return PurePythonEd25519()


def init(keys_dir: Path, repo: Path, *, check_location: bool = True) -> dict:
    """Internal channel: one test key per role, 1.root.json; returns its identity."""
    from tuf.api.metadata import Metadata, Root
    if check_location:
        _outside_repository(keys_dir)
    keys_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    (repo / "metadata").mkdir(parents=True, exist_ok=True)
    (repo / "targets").mkdir(parents=True, exist_ok=True)
    root = Root(expires=_expires("root"), consistent_snapshot=False)
    secrets_out = {}
    for role in ROLES:
        seed, key = new_key()
        root.add_key(key, role)
        secrets_out[role] = {"seed": seed.hex(), "key": key.to_dict(), "keyid": key.keyid}
    path = keys_dir / "keys.json"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(secrets_out, handle, indent=2)
    metadata = Metadata(root)
    metadata.sign(load_signer(keys_dir, "root"))
    metadata.to_file(str(repo / "metadata" / "1.root.json"))
    shutil.copyfile(repo / "metadata" / "1.root.json", repo / "trust-root.json")
    digest = hashlib.sha256((repo / "trust-root.json").read_bytes()).hexdigest()
    return {"trust_root": str(repo / "trust-root.json"), "sha256": digest}


def load_signer(keys_dir: Path, role: str):
    from securesystemslib.signer import SSlibKey
    data = json.loads((keys_dir / "keys.json").read_text(encoding="utf-8"))[role]
    key = SSlibKey.from_dict(data["keyid"], dict(data["key"]))
    return signer(bytes.fromhex(data["seed"]), key)


def _copy_new(source: Path, destination: Path) -> None:
    """Place a target; an existing one may only ever hold the same bytes."""
    if destination.exists():
        if _sha256_file(destination) != _sha256_file(source):
            raise PublishError(f"{destination.name} is already published with other "
                               "bytes; a published file is never replaced")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def publish(keys_dir: Path, repo: Path, *, channel: str, packages: list[dict],
            notes: str = "", now: datetime | None = None, expiry: dict | None = None) -> dict:
    """Internal channel: add packages and per-lane `latest.json`, sign all roles.

    Each package dict: path, lane, version, build_set, min_os, schema_version,
    engine_release. Versions of the metadata files increase on every publish.
    """
    from tuf.api.metadata import (MetaFile, Metadata, Snapshot, TargetFile, Targets,
                                  Timestamp)
    if channel != "internal":
        raise PublishError("publish is the internal channel's command; the Beta "
                           "channel uses stage and advance")
    metadata_dir = repo / "metadata"
    targets_path = metadata_dir / "targets.json"
    targets = (Metadata.from_file(str(targets_path)) if targets_path.exists()
               else Metadata(Targets(expires=_expires("targets", now, expiry))))
    targets.signed.version += 1 if targets_path.exists() else 0
    targets.signed.expires = _expires("targets", now, expiry)
    for package in packages:
        source = Path(package["path"])
        name = f"{channel}/{package['lane']}/{source.name}"
        _copy_new(source, repo / "targets" / name)
        custom = {"version": package["version"], "lane": package["lane"],
                  "channel": channel, "build_set": package.get("build_set")}
        target = TargetFile.from_file(name, str(repo / "targets" / name), ["sha256"])
        target.unrecognized_fields["custom"] = custom
        targets.signed.targets[name] = target
        latest = {"version": package["version"], "build_set": package.get("build_set"),
                  "lane": package["lane"], "channel": channel, "artifact": name,
                  "min_os": package.get("min_os"),
                  "schema_version": package.get("schema_version"),
                  "engine_release": package.get("engine_release"), "notes": notes,
                  "prerequisites": package.get("prerequisites", []),
                  # Data-format moves this release's app can perform and the
                  # team has qualified, as [from, to] pairs; none by default.
                  "qualified_migrations": package.get("qualified_migrations", [])}
        latest_name = f"{channel}/{package['lane']}/latest.json"
        latest_path = repo / "targets" / latest_name
        latest_path.write_text(json.dumps(latest, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
        targets.signed.targets[latest_name] = TargetFile.from_file(
            latest_name, str(latest_path), ["sha256"])
    targets.signatures.clear()
    targets.sign(load_signer(keys_dir, "targets"))
    targets.to_file(str(targets_path))

    snapshot_path = metadata_dir / "snapshot.json"
    snapshot = (Metadata.from_file(str(snapshot_path)) if snapshot_path.exists()
                else Metadata(Snapshot(expires=_expires("snapshot", now, expiry))))
    if snapshot_path.exists():
        snapshot.signed.version += 1
    snapshot.signed.expires = _expires("snapshot", now, expiry)
    snapshot.signed.meta["targets.json"] = MetaFile(version=targets.signed.version)
    snapshot.signatures.clear()
    snapshot.sign(load_signer(keys_dir, "snapshot"))
    snapshot.to_file(str(snapshot_path))

    timestamp_path = metadata_dir / "timestamp.json"
    timestamp = (Metadata.from_file(str(timestamp_path)) if timestamp_path.exists()
                 else Metadata(Timestamp(expires=_expires("timestamp", now, expiry))))
    if timestamp_path.exists():
        timestamp.signed.version += 1
    timestamp.signed.expires = _expires("timestamp", now, expiry)
    timestamp.signed.snapshot_meta = MetaFile(version=snapshot.signed.version)
    timestamp.signatures.clear()
    timestamp.sign(load_signer(keys_dir, "timestamp"))
    timestamp.to_file(str(timestamp_path))
    return {"targets": targets.signed.version, "snapshot": snapshot.signed.version,
            "timestamp": timestamp.signed.version}


def bundle_name(version: str, lane: str) -> str:
    return f"Refinix-{version}-{lane}-update.zip"


def bundle(repo: Path, output: Path, *, channel: str, lane: str) -> Path:
    """Internal channel: one zip with the metadata and the lane's offered package."""
    if channel != "internal":
        raise PublishError("use beta_bundle for the Beta channel")
    latest_name = f"{channel}/{lane}/latest.json"
    latest = json.loads((repo / "targets" / latest_name).read_text(encoding="utf-8"))
    output = Path(output)
    if output.is_dir():
        output = output / bundle_name(latest["version"], lane)
    partial = output.with_name(f".{output.name}.partial")
    with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted((repo / "metadata").glob("*.json")):
            archive.write(path, f"metadata/{path.name}")
        for name in (latest_name, latest["artifact"]):
            archive.write(repo / "targets" / name, f"targets/{name}")
    # Complete before it appears under its final name, so a folder check never
    # reads half a bundle.
    os.replace(partial, output)
    return output


def _package_from_record(path: Path, fixture: bool = False) -> dict:
    """Read lane/version details from the build driver's external manifest.

    A Beta-channel package must be a public build (never `--scratch`) and,
    when it offers Install and restart, carry its lane's native qualification
    record beside it, bound to these exact bytes.
    """
    manifest = json.loads(Path(f"{path}.manifest.json").read_text(encoding="utf-8"))
    identity = manifest["embedded_identity"]
    if _sha256_file(path) != manifest["sha256"]:
        raise SystemExit(f"{path.name} does not match its manifest")
    if identity.get("channel") == "beta" and fixture:
        # Qualification only: private test builds into a throwaway feed whose
        # keys never sign anything public (scripts/qualify_update_journey.py).
        if identity.get("publishable") is not False:
            raise SystemExit(f"{path.name} is a public build; --fixture stages only "
                             "private test builds into a throwaway feed")
    elif identity.get("channel") == "beta":
        if identity.get("publishable") is not True:
            raise SystemExit(f"{path.name} is a private test build (--scratch); it is "
                             "never staged")
        if identity.get("install_capability") in ("provisional", "qualified"):
            from scripts import qualification_record
            report = Path(path).parent / qualification_record.REPORT_NAME[manifest["lane"]]
            try:
                qualification_record.check(report, manifest["lane"], Path(path), manifest)
            except qualification_record.QualificationError as exc:
                raise SystemExit(f"{path.name}: no passing qualification record bound to "
                                 f"these bytes ({exc})") from exc
    # Numeric minimums the client can compare; the manifest's text says more.
    minimum = {"windows-x64": "10.0.22000",
               "linux-x64": "24.04"}.get(manifest["lane"], manifest.get("minimum_os"))
    return {"path": str(path), "lane": manifest["lane"], "version": identity["version"],
            "channel": identity.get("channel"), "maturity": identity.get("maturity"),
            "build_set": identity["build_set"], "min_os": minimum,
            "schema_version": identity.get("schema_version"),
            "qualified_migrations": identity.get("qualified_migrations") or [],
            "engine_release": (identity.get("engines") or [{}])[0].get("release"),
            "public_build": identity.get("bundle_build"),
            "signing": identity.get("signing"),
            "publishable": identity.get("publishable"),
            "install_capability": identity.get("install_capability"),
            "trust_root": identity.get("trust_root"),
            "shared_snapshot_digest": identity.get("shared_snapshot_digest"),
            "identity": identity, "manifest_sha256": manifest["sha256"],
            "size": manifest["size"]}


# ==========================================================================
# Beta channel
# ==========================================================================

def _passphrase(role: str, passphrases: dict | None, *, confirm: bool = False) -> bytes:
    if passphrases and role in passphrases:
        return passphrases[role].encode("utf-8")
    variable = PASSPHRASE_VARIABLE.format(role=role.upper())
    if os.environ.get(variable):
        return os.environ[variable].encode("utf-8")
    first = getpass.getpass(f"Passphrase for the {role} key: ")
    if confirm and getpass.getpass(f"Repeat the {role} passphrase: ") != first:
        raise PublishError("the passphrases did not match")
    if len(first) < 12:
        raise PublishError("use a passphrase of at least 12 characters")
    return first.encode("utf-8")


def _write_key(keys_dir: Path, role: str, passphrase: bytes):
    from cryptography.hazmat.primitives import serialization
    from securesystemslib.signer import CryptoSigner
    signer_ = CryptoSigner.generate_ed25519()
    pem = signer_._private_key.private_bytes(            # noqa: SLF001
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(passphrase))
    path = keys_dir / f"{role}.pem"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(pem)
    return signer_


def load_role(keys_dir: Path, role: str, passphrases: dict | None = None):
    """The encrypted key for one role, as a signer."""
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    from securesystemslib.signer import CryptoSigner
    path = Path(keys_dir) / f"{role}.pem"
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise PublishError(f"the {role} key is not in {keys_dir}") from exc
    try:
        key = load_pem_private_key(data, _passphrase(role, passphrases))
    except (TypeError, ValueError) as exc:
        raise PublishError(f"the {role} key could not be opened: wrong passphrase or "
                           "not a key") from exc
    return CryptoSigner(key)


class Feed:
    """The local feed folder: versions are read from the files themselves."""

    def __init__(self, repo: Path):
        self.repo = Path(repo)
        self.metadata = self.repo / "metadata"
        self.targets_dir = self.repo / "targets"

    # -- reading --------------------------------------------------------------
    def _versions(self, role: str) -> list[int]:
        found = []
        for path in self.metadata.glob(f"*.{role}.json"):
            match = re.fullmatch(rf"(\d+)\.{role}\.json", path.name)
            if match:
                found.append(int(match.group(1)))
        return sorted(found)

    def load(self, role: str, version: int | None = None):
        from tuf.api.metadata import Metadata
        if role == "timestamp":
            path = self.metadata / "timestamp.json"
        else:
            versions = self._versions(role)
            if not versions:
                raise PublishError(f"the feed has no {role} metadata yet")
            path = self.metadata / f"{version or versions[-1]}.{role}.json"
        try:
            return Metadata.from_bytes(path.read_bytes())
        except OSError as exc:
            raise PublishError(f"{path.name} is missing") from exc

    def root(self):
        return self.load("root")

    def roots(self) -> dict[int, bytes]:
        return {v: (self.metadata / f"{v}.root.json").read_bytes()
                for v in self._versions("root")}

    def root_hashes(self) -> set[str]:
        return {_sha256(data) for data in self.roots().values()}

    def has_timestamp(self) -> bool:
        return (self.metadata / "timestamp.json").is_file()

    def current_targets_version(self) -> int | None:
        """The targets version clients are offered now (via snapshot)."""
        if not self.has_timestamp():
            return None
        timestamp = self.load("timestamp")
        snapshot = self.load("snapshot", timestamp.signed.snapshot_meta.version)
        return snapshot.signed.meta["targets.json"].version

    def staged_targets_version(self) -> int | None:
        versions = self._versions("targets")
        current = self.current_targets_version() or 0
        staged = [v for v in versions if v > current]
        if len(staged) > 1:
            raise PublishError(f"more than one staged targets version: {staged}")
        return staged[0] if staged else None

    # -- writing --------------------------------------------------------------
    def write_new(self, path: Path, data: bytes) -> None:
        """Immutable files: written once; an identical rewrite is a no-op."""
        if path.exists():
            if path.read_bytes() != data:
                raise PublishError(f"{path.relative_to(self.repo)} already exists with "
                                   "other bytes; published files are never replaced")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.partial")
        temporary.write_bytes(data)
        os.replace(temporary, path)

    def write_timestamp(self, data: bytes) -> None:
        path = self.metadata / "timestamp.json"
        temporary = path.with_name(".timestamp.json.partial")
        temporary.write_bytes(data)
        os.replace(temporary, path)


def _verify_role(root, metadata, role: str) -> None:
    try:
        root.signed.verify_delegate(role, metadata.signed_bytes, metadata.signatures)
    except Exception as exc:                               # noqa: BLE001
        raise PublishError(f"{role} metadata is not signed by the current root's "
                           f"{role} keys: {exc}") from exc


def beta_init(keys_dir: Path, repo: Path, *, passphrases: dict | None = None,
              check_location: bool = True, now: datetime | None = None) -> dict:
    """Beta channel: four encrypted keys and 1.root.json with consistent snapshots."""
    from tuf.api.metadata import Metadata, Root
    keys_dir = Path(keys_dir)
    if check_location:
        _outside_repository(keys_dir)
    feed = Feed(repo)
    if feed._versions("root"):
        raise PublishError(f"{repo} already holds a feed")
    keys_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    root = Root(expires=_expires("root", now), consistent_snapshot=True)
    signers = {}
    for role in ROLES:
        signers[role] = _write_key(keys_dir, role,
                                   _passphrase(role, passphrases, confirm=True))
        root.add_key(signers[role].public_key, role)
    metadata = Metadata(root)
    metadata.sign(signers["root"])
    data = metadata.to_bytes(_serializer())
    feed.write_new(feed.metadata / "1.root.json", data)
    (feed.targets_dir).mkdir(parents=True, exist_ok=True)
    public = {role: signers[role].public_key.keyid for role in ROLES}
    (keys_dir / "public.json").write_text(json.dumps(public, indent=2) + "\n",
                                          encoding="utf-8")
    return {"trust_root": str(feed.metadata / "1.root.json"), "sha256": _sha256(data),
            "keyids": public}


def _serializer():
    from tuf.api.serialization.json import JSONSerializer
    return JSONSerializer(compact=False)


def _published_packages(targets) -> list[dict]:
    found = []
    for name, info in targets.signed.targets.items():
        custom = (info.custom or {}) if hasattr(info, "custom") else {}
        if name.startswith("v") and custom.get("version"):
            found.append({"name": name, **custom})
    return found


def _check_package(package: dict, feed: Feed, maturity: str) -> str:
    """One Beta package may be staged; returns its install format."""
    path = Path(package["path"])
    name = path.name
    fmt = release.format_of(name)
    if fmt is None:
        raise PublishError(f"{name}: a DMG (or another installer) is never an update "
                           "payload; stage the ZIP, EXE, DEB or AppImage")
    try:
        label = release.check_identity(package["version"], package.get("channel"),
                                       package.get("maturity"))
    except release.LabelError as exc:
        raise PublishError(f"{name}: {exc}") from exc
    if label.maturity != maturity:
        raise PublishError(f"{name} is a {label.maturity} build, not {maturity}")
    if name != release.asset_name(package["version"], package["lane"], fmt):
        raise PublishError(f"{name} is not named "
                           f"{release.asset_name(package['version'], package['lane'], fmt)}")
    if package.get("trust_root") not in feed.root_hashes():
        raise PublishError(f"{name} trusts a root that is not in this feed; publish the "
                           "root first, then build with it")
    if package.get("signing") not in SIGNING_ALLOWED.get(package["lane"], ()):
        raise PublishError(f"{name} is signed {package.get('signing')!r}; a "
                           f"{package['lane']} package may be "
                           f"{' or '.join(SIGNING_ALLOWED.get(package['lane'], ()))}")
    if package.get("publishable") is False:
        raise PublishError(f"{name} is a private test build (--scratch)")
    if package.get("install_capability") not in CAPABILITIES_FOR[maturity]:
        raise PublishError(f"{name}: install capability "
                           f"{package.get('install_capability')!r} is not allowed for "
                           f"a {maturity} build")
    if not isinstance(package.get("public_build"), int):
        raise PublishError(f"{name} records no public build number")
    return fmt


def stage(keys_dir: Path, repo: Path, *, maturity: str, packages: list[dict],
          notes: str = "", passphrases: dict | None = None, now: datetime | None = None,
          expiry: dict | None = None, every_lane: bool = True) -> dict:
    """Offline: add packages and pointers in the next targets version, signed.

    Clients see nothing until `advance` signs a snapshot naming it. Beta and
    final releases must carry every lane at one version; a tester preview may
    carry the lanes that are ready.
    """
    from tuf.api.metadata import Metadata, TargetFile, Targets
    feed = Feed(repo)
    if maturity not in release.MATURITIES:
        raise PublishError(f"unknown maturity {maturity!r}")
    if not packages:
        raise PublishError("nothing to stage")
    if feed.staged_targets_version() is not None:
        raise PublishError("a staged targets version is already waiting; advance it "
                           "(or remove that unreferenced file) first")
    versions = {p["version"] for p in packages}
    builds = {p.get("public_build") for p in packages}
    sources = {p.get("shared_snapshot_digest") for p in packages}
    if len(versions) != 1 or len(builds) != 1:
        raise PublishError("every package in one release has the same version and "
                           "public build number")
    if len(sources) != 1:
        raise PublishError("the packages were built from different sources")
    version, build = versions.pop(), builds.pop()
    formats = {}
    for package in packages:
        formats[(package["lane"], _check_package(package, feed, maturity))] = package
    lanes = {lane for lane, _fmt in formats}
    if maturity != "preview" and every_lane and lanes != set(LANES):
        raise PublishError(f"an {maturity} release carries every lane; missing "
                           f"{sorted(set(LANES) - lanes)}")
    root = feed.root()
    try:
        previous = feed.load("targets")
        _verify_role(root, previous, "targets")
    except PublishError:
        if feed._versions("targets"):
            raise
        previous = None
    published = _published_packages(previous) if previous else []
    key = release.key(version)
    for earlier in published:
        if release.key(earlier["version"]) >= key:
            raise PublishError(f"{version} is not newer than already published "
                               f"{earlier['version']}; the public history only moves "
                               "forward")
        if int(earlier.get("public_build") or 0) >= build:
            raise PublishError(f"public build {build} is not above {earlier['public_build']}"
                               f" ({earlier['version']})")
    targets = previous.signed if previous else Targets(expires=_expires("targets", now, expiry))
    targets.version = (previous.signed.version + 1) if previous else 1
    targets.expires = _expires("targets", now, expiry)
    pointer = release.POINTERS[maturity]
    for lane in sorted(lanes):
        payloads = {}
        first = None
        for (item_lane, fmt), package in sorted(formats.items()):
            if item_lane != lane:
                continue
            first = first or package
            name = release.package_target(version, lane, fmt)
            if name in targets.targets:
                raise PublishError(f"{name} is already a published target")
            target = TargetFile.from_file(name, package["path"], ["sha256"])
            target.unrecognized_fields["custom"] = {
                "version": version, "lane": lane, "channel": "beta", "maturity": maturity,
                "format": fmt, "build_set": package.get("build_set"),
                "public_build": build, "schema_version": package.get("schema_version"),
                "signing": package.get("signing")}
            targets.targets[name] = target
            payloads[fmt] = name
        latest = {"version": version, "channel": "beta", "maturity": maturity,
                  "lane": lane, "public_build": build,
                  "build_set": first.get("build_set"), "min_os": first.get("min_os"),
                  "schema_version": first.get("schema_version"),
                  "engine_release": first.get("engine_release"), "notes": notes,
                  "prerequisites": first.get("prerequisites", []),
                  "qualified_migrations": first.get("qualified_migrations", []),
                  "payloads": payloads}
        data = (json.dumps(latest, indent=2, sort_keys=True) + "\n").encode("utf-8")
        target_name = f"beta/{lane}/{pointer}"
        feed.write_new(feed.targets_dir / "beta" / lane / f"{_sha256(data)}.{pointer}", data)
        info = TargetFile.from_data(target_name, data, ["sha256"])
        targets.targets[target_name] = info
    metadata = Metadata(targets)
    metadata.sign(load_role(keys_dir, "targets", passphrases))
    data = metadata.to_bytes(_serializer())
    feed.write_new(feed.metadata / f"{targets.version}.targets.json", data)
    return {"staged_targets": targets.version, "version": version, "maturity": maturity,
            "lanes": sorted(lanes), "public_build": build}


def _check_staged(feed: Feed, root, staged) -> None:
    """The staged targets follow the current ones: signed, newer, nothing removed."""
    _verify_role(root, staged, "targets")
    current = feed.current_targets_version()
    if current is not None:
        before = feed.load("targets", current)
        for name, info in before.signed.targets.items():
            after = staged.signed.targets.get(name)
            if name.startswith("v") and (after is None or after.to_dict() != info.to_dict()):
                raise PublishError(f"the staged targets change or drop published "
                                   f"package {name}")
    for name, info in staged.signed.targets.items():
        if name.startswith("beta/"):
            lane, pointer = name.split("/")[1:3]
            stored = feed.targets_dir / "beta" / lane / f"{info.hashes['sha256']}.{pointer}"
            try:
                info.verify_length_and_hashes(stored.read_bytes())
            except Exception as exc:                       # noqa: BLE001
                raise PublishError(f"{name} is not in the feed as signed") from exc
            latest = json.loads(stored.read_bytes())
            if not release.pointer_allows(pointer, latest.get("maturity"), "beta"):
                raise PublishError(f"{name} names a {latest.get('maturity')} build")
            for fmt, package in (latest.get("payloads") or {}).items():
                entry = staged.signed.targets.get(package)
                if entry is None or (entry.custom or {}).get("format") != fmt \
                        or (entry.custom or {}).get("version") != latest.get("version"):
                    raise PublishError(f"{name} offers {package}, which is not a signed "
                                       f"{fmt} package of {latest.get('version')}")


def check_assets(staged, packages_url: str, names, fetch=None,
                 hosts: tuple[str, ...] | None = None) -> list[str]:
    """Download released assets anonymously; each must match its signed target.

    With `hosts` (the feed's `package_hosts`), the download must also end on
    one of them: an installed client refuses any other redirect host, so a
    feed that offers packages it cannot fetch is refused here, before it goes
    live.
    """
    from urllib.parse import urlsplit
    fetch = fetch or _anonymous_download
    checked = []
    for name in sorted(names):
        info = staged.signed.targets[name]
        url = packages_url.rstrip("/") + "/" + name
        fetched = fetch(url, info.length)
        data_path, final = fetched if isinstance(fetched, tuple) else (fetched, None)
        if hosts is not None:
            host = urlsplit(final or "").hostname
            if final is None or host not in hosts:
                Path(data_path).unlink(missing_ok=True)
                raise PublishError(f"{name} downloads from {host!r}, which installed "
                                   f"clients do not accept ({', '.join(hosts)})")
        try:
            with open(data_path, "rb") as handle:
                info.verify_length_and_hashes(handle)
        except Exception as exc:                           # noqa: BLE001
            raise PublishError(f"the released {name} does not match its signed target") \
                from exc
        finally:
            Path(data_path).unlink(missing_ok=True)
        checked.append(name)
    return checked


def _anonymous_download(url: str, limit: int) -> tuple[str, str]:
    """No credentials; HTTPS redirects (GitHub's asset hosts) are followed.
    Returns the downloaded file and the final URL it came from."""
    import urllib3
    pool = urllib3.PoolManager(headers={"User-Agent": "refinix-release-check"})
    response = pool.request("GET", url, preload_content=False, redirect=True, retries=3)
    if response.status != 200 or not response.geturl().startswith("https://"):
        raise PublishError(f"{url} answered {response.status}")
    handle, path = tempfile.mkstemp(prefix="refinix-asset-")
    seen = 0
    with os.fdopen(handle, "wb") as out:
        for block in response.stream(1024 * 1024):
            seen += len(block)
            if seen > limit:
                raise PublishError(f"{url} is longer than its signed length")
            out.write(block)
    final = response.geturl()
    response.release_conn()
    return path, final


def _sign_snapshot_and_timestamp(feed: Feed, targets_version: int, signers: dict, *,
                                 now: datetime | None, expiry: dict | None,
                                 new_snapshot: bool = True) -> dict:
    from tuf.api.metadata import MetaFile, Metadata, Snapshot, Timestamp
    targets_bytes = (feed.metadata / f"{targets_version}.targets.json").read_bytes()
    try:
        previous = feed.load("snapshot")
        snapshot_version = previous.signed.version + 1
    except PublishError:
        snapshot_version = 1
    snapshot = Snapshot(version=snapshot_version, expires=_expires("snapshot", now, expiry))
    snapshot.meta["targets.json"] = MetaFile(
        version=targets_version, length=len(targets_bytes),
        hashes={"sha256": _sha256(targets_bytes)})
    snapshot_metadata = Metadata(snapshot)
    snapshot_metadata.sign(signers["snapshot"])
    snapshot_bytes = snapshot_metadata.to_bytes(_serializer())
    feed.write_new(feed.metadata / f"{snapshot_version}.snapshot.json", snapshot_bytes)
    return _sign_timestamp(feed, snapshot_version, snapshot_bytes, signers["timestamp"],
                           now=now, expiry=expiry) | {"snapshot": snapshot_version,
                                                      "targets": targets_version}


def _sign_timestamp(feed: Feed, snapshot_version: int, snapshot_bytes: bytes, signer_, *,
                    now, expiry) -> dict:
    from tuf.api.metadata import MetaFile, Metadata, Timestamp
    version = feed.load("timestamp").signed.version + 1 if feed.has_timestamp() else 1
    timestamp = Timestamp(version=version, expires=_expires("timestamp", now, expiry),
                          snapshot_meta=MetaFile(version=snapshot_version,
                                                 length=len(snapshot_bytes),
                                                 hashes={"sha256": _sha256(snapshot_bytes)}))
    metadata = Metadata(timestamp)
    metadata.sign(signer_)
    feed.write_timestamp(metadata.to_bytes(_serializer()))
    return {"timestamp": version}


def advance(keys_dir: Path, repo: Path, *, packages_url: str | None = None,
            fetch=None, passphrases: dict | None = None, now: datetime | None = None,
            expiry: dict | None = None, package_hosts: tuple[str, ...] | None = None) -> dict:
    """Online: make the staged targets current (snapshot, then timestamp)."""
    feed = Feed(repo)
    staged_version = feed.staged_targets_version()
    if staged_version is None:
        raise PublishError("nothing is staged")
    root = feed.root()
    staged = feed.load("targets", staged_version)
    _check_staged(feed, root, staged)
    current = feed.current_targets_version()
    before = set(feed.load("targets", current).signed.targets) if current else set()
    added = [n for n in staged.signed.targets if n.startswith("v") and n not in before]
    checked = []
    if packages_url:
        checked = check_assets(staged, packages_url, added, fetch, hosts=package_hosts)
    signers = {role: load_role(keys_dir, role, passphrases) for role in ONLINE_ROLES}
    for role in ONLINE_ROLES:
        if signers[role].public_key.keyid not in root.signed.roles[role].keyids:
            raise PublishError(f"the {role} key is not the current root's {role} key")
    result = _sign_snapshot_and_timestamp(feed, staged_version, signers, now=now,
                                          expiry=expiry)
    return {**result, "added": sorted(added), "assets_checked": checked}


def refresh(keys_dir: Path, repo: Path, *, passphrases: dict | None = None,
            now: datetime | None = None, expiry: dict | None = None) -> dict:
    """Online, daily: a fresh timestamp; a fresh snapshot when it runs low."""
    feed = Feed(repo)
    if not feed.has_timestamp():
        raise PublishError("the feed has never been advanced")
    root = feed.root()
    timestamp = feed.load("timestamp")
    snapshot = feed.load("snapshot", timestamp.signed.snapshot_meta.version)
    signers = {role: load_role(keys_dir, role, passphrases) for role in ONLINE_ROLES}
    left = snapshot.signed.expires - _now(now)
    signed_by_current = True
    try:
        _verify_role(root, snapshot, "snapshot")
    except PublishError:
        signed_by_current = False                     # the snapshot key was rotated
    if left < timedelta(days=SNAPSHOT_REFRESH_DAYS) or not signed_by_current:
        targets_version = snapshot.signed.meta["targets.json"].version
        return {**_sign_snapshot_and_timestamp(feed, targets_version, signers, now=now,
                                               expiry=expiry), "snapshot_renewed": True}
    data = (feed.metadata / f"{snapshot.signed.version}.snapshot.json").read_bytes()
    return {**_sign_timestamp(feed, snapshot.signed.version, data, signers["timestamp"],
                              now=now, expiry=expiry), "snapshot_renewed": False}


def renew_targets(keys_dir: Path, repo: Path, *, passphrases: dict | None = None,
                  now: datetime | None = None, expiry: dict | None = None) -> dict:
    """Offline: the current targets again, as the next version with a new expiry."""
    from tuf.api.metadata import Metadata
    feed = Feed(repo)
    if feed.staged_targets_version() is not None:
        raise PublishError("advance the staged targets before renewing")
    current = feed.current_targets_version()
    if current is None:
        raise PublishError("the feed has no current targets")
    targets = feed.load("targets", current).signed
    targets.version = current + 1
    targets.expires = _expires("targets", now, expiry)
    metadata = Metadata(targets)
    metadata.sign(load_role(keys_dir, "targets", passphrases))
    feed.write_new(feed.metadata / f"{targets.version}.targets.json",
                   metadata.to_bytes(_serializer()))
    return {"staged_targets": targets.version, "expires": targets.expires.isoformat()}


def withdraw(keys_dir: Path, repo: Path, *, lane: str, pointer: str, to_version: str,
             passphrases: dict | None = None, now: datetime | None = None,
             expiry: dict | None = None) -> dict:
    """Offline: point a lane's pointer back at an earlier published build.

    Installations then see "not newer". Already installed copies of the
    withdrawn build are fixed by a newer release, never by older metadata.
    """
    from tuf.api.metadata import Metadata, TargetFile
    feed = Feed(repo)
    if feed.staged_targets_version() is not None:
        raise PublishError("advance the staged targets before withdrawing")
    current = feed.current_targets_version()
    targets = feed.load("targets", current).signed
    name = f"beta/{lane}/{pointer}"
    if name not in targets.targets:
        raise PublishError(f"{name} has never been published")
    candidates = [p for p in _published_packages(Metadata(targets))
                  if p["version"] == to_version and p["lane"] == lane]
    if not candidates:
        raise PublishError(f"{to_version} was never published for {lane}")
    maturity = candidates[0]["maturity"]
    if not release.pointer_allows(pointer, maturity, "beta"):
        raise PublishError(f"{pointer} cannot name a {maturity} build")
    old = targets.targets[name]
    stored = feed.targets_dir / "beta" / lane / f"{old.hashes['sha256']}.{pointer}"
    latest = json.loads(stored.read_bytes())
    latest.update({"version": to_version, "maturity": maturity,
                   "public_build": candidates[0].get("public_build"),
                   "build_set": candidates[0].get("build_set"),
                   "payloads": {p["format"]: p["name"] for p in candidates},
                   "notes": f"The newer version was withdrawn; {to_version} is offered."})
    data = (json.dumps(latest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    feed.write_new(feed.targets_dir / "beta" / lane / f"{_sha256(data)}.{pointer}", data)
    targets.targets[name] = TargetFile.from_data(name, data, ["sha256"])
    targets.version = current + 1
    targets.expires = _expires("targets", now, expiry)
    metadata = Metadata(targets)
    metadata.sign(load_role(keys_dir, "targets", passphrases))
    feed.write_new(feed.metadata / f"{targets.version}.targets.json",
                   metadata.to_bytes(_serializer()))
    return {"staged_targets": targets.version, "lane": lane, "pointer": pointer,
            "to_version": to_version}


def rotate_root(keys_dir: Path, repo: Path, *, new_keys_dir: Path | None = None,
                replace: tuple[str, ...] = (), passphrases: dict | None = None,
                new_passphrases: dict | None = None, now: datetime | None = None,
                check_location: bool = True) -> dict:
    """Offline: the next root version, signed by the old and the new root keys.

    `replace` names roles whose keys are replaced with fresh ones written to
    `new_keys_dir` (encrypted). Without it the root is only renewed. After
    replacing snapshot/timestamp keys, run `refresh` with the new keys:
    installed clients re-check their cached metadata against the newest root
    and drop anything the revoked keys signed.
    """
    from tuf.api.metadata import Metadata
    feed = Feed(repo)
    current = feed.root()
    root = current.signed
    old_root_signer = load_role(keys_dir, "root", passphrases)
    if old_root_signer.public_key.keyid not in root.roles["root"].keyids:
        raise PublishError("the given root key is not the current root key")
    root.version += 1
    root.expires = _expires("root", now)
    new_signers = {}
    if replace:
        if new_keys_dir is None:
            raise PublishError("replacing keys needs --new-keys")
        new_keys_dir = Path(new_keys_dir)
        if check_location:
            _outside_repository(new_keys_dir)
        new_keys_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    for role in replace:
        if role not in ROLES:
            raise PublishError(f"unknown role {role}")
        for keyid in list(root.roles[role].keyids):
            root.revoke_key(keyid, role)
        new_signers[role] = _write_key(new_keys_dir, role,
                                       _passphrase(role, new_passphrases, confirm=True))
        root.add_key(new_signers[role].public_key, role)
    metadata = Metadata(root)
    metadata.sign(old_root_signer, append=True)
    if "root" in new_signers:
        metadata.sign(new_signers["root"], append=True)
    data = metadata.to_bytes(_serializer())
    feed.write_new(feed.metadata / f"{root.version}.root.json", data)
    return {"root_version": root.version, "sha256": _sha256(data),
            "replaced": sorted(replace), "expires": root.expires.isoformat()}


# -- reading the feed as a client does ------------------------------------------

def _folder_fetcher(base: Path):
    from tuf.api import exceptions
    from tuf.ngclient import FetcherInterface

    class FolderFetcher(FetcherInterface):
        def _fetch(self, url: str):
            prefix = "refinix-feed:///"
            if not url.startswith(prefix):
                raise exceptions.DownloadError(url)
            path = base / url[len(prefix):]
            if not path.is_file():
                raise exceptions.DownloadHTTPError("not found", 404)
            return iter([path.read_bytes()])

    return FolderFetcher()


def expected(repo: Path) -> dict:
    """What this feed folder serves once deployed, exactly.

    Read from a checkout of the signed commit and given to `verify --expect`,
    so a live check passes only on this deployment: the newest root, the
    current timestamp, snapshot and targets (versions and SHA-256 of their
    exact bytes) and every lane's offers. A previous feed that is still
    validly signed does not match.
    """
    feed = Feed(repo)
    timestamp_bytes = (feed.metadata / "timestamp.json").read_bytes()
    timestamp = feed.load("timestamp")
    snapshot_version = timestamp.signed.snapshot_meta.version
    snapshot_bytes = (feed.metadata / f"{snapshot_version}.snapshot.json").read_bytes()
    snapshot = feed.load("snapshot", snapshot_version)
    targets_version = snapshot.signed.meta["targets.json"].version
    targets_bytes = (feed.metadata / f"{targets_version}.targets.json").read_bytes()
    root_version = max(feed._versions("root"))
    root_bytes = (feed.metadata / f"{root_version}.root.json").read_bytes()
    targets = feed.load("targets", targets_version).signed.targets
    offers = {}
    for name, info in sorted(targets.items()):
        if not name.startswith("beta/"):
            continue
        lane, pointer = name.split("/")[1:3]
        stored = feed.targets_dir / "beta" / lane / f"{info.hashes['sha256']}.{pointer}"
        latest = json.loads(stored.read_bytes())
        offers[f"{lane}/{pointer}"] = {"version": latest["version"],
                                       "payloads": latest.get("payloads")}
    return {"versions": {"root": root_version, "targets": targets_version,
                         "snapshot": snapshot_version,
                         "timestamp": timestamp.signed.version},
            "sha256": {"root": _sha256(root_bytes), "targets": _sha256(targets_bytes),
                       "snapshot": _sha256(snapshot_bytes),
                       "timestamp": _sha256(timestamp_bytes)},
            "offers": offers}


def verify(repo: Path | None = None, *, url: str | None = None, now: datetime | None = None,
           monitor: bool = False, pool=None, trust_root: Path | None = None,
           expect: dict | None = None) -> dict:
    """The real client reads the feed; with `monitor`, near expiry is an error.

    The client starts from a root it already trusts: `trust_root`, or the
    feed folder's first root. A live check never trusts what the server says
    its first root is. With `expect` (from `expected` on the signed commit),
    anything but exactly that feed is a problem: a CDN still serving the
    previous, validly signed feed fails.
    """
    from tuf.ngclient import Updater
    if trust_root is not None:
        bootstrap = Path(trust_root).read_bytes()
    elif repo is not None:
        bootstrap = (Feed(repo).metadata / "1.root.json").read_bytes()
    else:
        raise PublishError("a live check needs --trust-root or --repo")
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        if url:
            from backend.coordinator.updates import _fetcher_classes
            HttpsFetcher, _ = _fetcher_classes()
            fetcher = HttpsFetcher(pool)
            base = url.rstrip("/") + "/"
            metadata_url, targets_url = base + "metadata/", base + "targets/"
        else:
            feed = Feed(repo)
            fetcher = _folder_fetcher(feed.repo)
            metadata_url, targets_url = "refinix-feed:///metadata/", "refinix-feed:///targets/"
        (work / "metadata").mkdir()
        updater = Updater(str(work / "metadata"), metadata_url, str(work / "targets"),
                          targets_url, fetcher=fetcher, bootstrap=bootstrap)
        updater.refresh()
        trusted = updater._trusted_set                     # noqa: SLF001
        offers = {}
        for lane in LANES:
            for pointer in ("latest.json", "latest-preview.json"):
                info = updater.get_targetinfo(f"beta/{lane}/{pointer}")
                if info is None:
                    continue
                path = updater.download_target(info, str(work / f"{lane}-{pointer}"))
                latest = json.loads(Path(path).read_text(encoding="utf-8"))
                if not release.pointer_allows(pointer, latest.get("maturity"), "beta"):
                    raise PublishError(f"beta/{lane}/{pointer} names a "
                                       f"{latest.get('maturity')} build")
                for fmt, name in (latest.get("payloads") or {}).items():
                    package = updater.get_targetinfo(name)
                    if package is None or (package.custom or {}).get("format") != fmt:
                        raise PublishError(f"{lane}/{pointer} offers an unsigned {name}")
                offers[f"{lane}/{pointer}"] = {"version": latest["version"],
                                               "payloads": latest.get("payloads")}
        when = _now(now)
        left = {"root": trusted.root.expires - when,
                "targets": trusted.targets.expires - when,
                "snapshot": trusted.snapshot.expires - when,
                "timestamp": trusted.timestamp.expires - when}
        # The exact bytes the client accepted and kept.
        served = {}
        for role in ROLES:
            try:
                served[role] = _sha256((work / "metadata" / f"{role}.json").read_bytes())
            except OSError:
                served[role] = None
    days = {role: round(value.total_seconds() / 86400, 2) for role, value in left.items()}
    problems = [f"{role} expires in {days[role]} days (alert below {limit})"
                for role, limit in MONITOR_DAYS.items() if days[role] < limit] if monitor else []
    due = [f"renew-{role} is due ({days[role]} days left)"
           for role, limit in RENEW_DAYS.items() if days[role] <= limit]
    versions = {"root": trusted.root.version, "targets": trusted.targets.version,
                "snapshot": trusted.snapshot.version, "timestamp": trusted.timestamp.version}
    if expect is not None:
        if versions != expect.get("versions"):
            problems.append(f"the feed serves versions {versions}, not the expected "
                            f"{expect.get('versions')}")
        if served != expect.get("sha256"):
            differ = sorted(r for r in ROLES if served.get(r) != (expect.get("sha256") or {})
                            .get(r))
            problems.append(f"the feed serves other {differ} metadata bytes than the "
                            "signed commit")
        if offers != expect.get("offers"):
            problems.append(f"the feed offers {offers}, not the expected "
                            f"{expect.get('offers')}")
    return {"versions": versions, "sha256": served, "days_left": days, "offers": offers,
            "problems": problems, "renewals_due": due,
            "matches_expected": None if expect is None else not any(
                p.startswith("the feed serves") or p.startswith("the feed offers")
                for p in problems)}


def preview(repo: Path) -> dict:
    """What advancing would change: packages added and pointers moved."""
    feed = Feed(repo)
    staged_version = feed.staged_targets_version()
    if staged_version is None:
        return {"staged": None}
    staged = feed.load("targets", staged_version)
    current = feed.current_targets_version()
    before = feed.load("targets", current).signed.targets if current else {}
    added = sorted(n for n in staged.signed.targets if n.startswith("v") and n not in before)
    moved = {}
    for name, info in staged.signed.targets.items():
        if name.startswith("beta/") and (name not in before
                                         or before[name].hashes != info.hashes):
            lane, pointer = name.split("/")[1:3]
            stored = feed.targets_dir / "beta" / lane / f"{info.hashes['sha256']}.{pointer}"
            moved[name] = json.loads(stored.read_bytes())["version"]
    return {"staged": staged_version, "current": current, "packages_added": added,
            "pointers": moved, "expires": staged.signed.expires.isoformat()}


def beta_bundle(repo: Path, packages: Path, output: Path, *, lane: str, fmt: str,
                maturity: str = "preview", recovery_versions: tuple[str, ...] = ()) -> Path:
    """One offline-import file from the current feed, for one lane and format.

    It holds every root version, the current timestamp, snapshot and targets,
    the lane's pointer(s), the offered package and, for a `.deb`, any listed
    earlier versions' packages as recovery copies. It expires with the
    timestamp, so it is made on demand and never published.
    """
    feed = Feed(repo)
    timestamp = feed.load("timestamp")
    snapshot_version = timestamp.signed.snapshot_meta.version
    snapshot = feed.load("snapshot", snapshot_version)
    targets_version = snapshot.signed.meta["targets.json"].version
    targets = feed.load("targets", targets_version).signed.targets
    members = {}
    for version in feed._versions("root"):
        members[f"metadata/{version}.root.json"] = feed.metadata / f"{version}.root.json"
    members["metadata/timestamp.json"] = feed.metadata / "timestamp.json"
    members[f"metadata/{snapshot_version}.snapshot.json"] = \
        feed.metadata / f"{snapshot_version}.snapshot.json"
    members[f"metadata/{targets_version}.targets.json"] = \
        feed.metadata / f"{targets_version}.targets.json"
    offered = None
    for pointer in release.pointers_for(maturity):
        info = targets.get(f"beta/{lane}/{pointer}")
        if info is None:
            continue
        digest = info.hashes["sha256"]
        stored = feed.targets_dir / "beta" / lane / f"{digest}.{pointer}"
        members[f"targets/beta/{lane}/{digest}.{pointer}"] = stored
        latest = json.loads(stored.read_bytes())
        if offered is None or release.key(latest["version"]) > release.key(offered["version"]):
            offered = latest
    if offered is None or fmt not in (offered.get("payloads") or {}):
        raise PublishError(f"the feed offers no {fmt} package for {lane}")
    names = [offered["payloads"][fmt]]
    names += [release.package_target(v, lane, fmt) for v in recovery_versions]
    for name in names:
        if name not in targets:
            raise PublishError(f"{name} is not a signed target")
        source = Path(packages) / Path(name).name
        info = targets[name]
        with open(source, "rb") as handle:
            info.verify_length_and_hashes(handle)
        members[f"targets/{name}"] = source
    output = Path(output)
    if output.is_dir():
        output = output / f"Refinix-{offered['version']}-{lane}-{fmt}-update.zip"
    partial = output.with_name(f".{output.name}.partial")
    with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_STORED) as archive:
        for member, source in sorted(members.items()):
            archive.write(source, member)
    os.replace(partial, output)
    return output


# ==========================================================================
# Command line
# ==========================================================================

def _manifest_packages(paths, fixture: bool = False) -> list[dict]:
    return [_package_from_record(Path(path), fixture) for path in paths]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("init")
    one.add_argument("--channel", choices=["internal", "beta"], default="internal")
    one.add_argument("--keys", type=Path, required=True)
    one.add_argument("--repo", type=Path, required=True)
    two = sub.add_parser("publish", help="internal channel only")
    two.add_argument("--keys", type=Path, required=True)
    two.add_argument("--repo", type=Path, required=True)
    two.add_argument("--channel", required=True, choices=["internal"])
    two.add_argument("--notes", default="")
    two.add_argument("packages", nargs="+", type=Path)
    three = sub.add_parser("stage")
    three.add_argument("--keys", type=Path, required=True)
    three.add_argument("--repo", type=Path, required=True)
    three.add_argument("--maturity", required=True, choices=release.MATURITIES)
    three.add_argument("--notes", default="")
    three.add_argument("--notes-file", type=Path)
    three.add_argument("--fixture", action="store_true",
                       help="qualification only: stage private (--scratch) test builds "
                            "into a throwaway feed")
    three.add_argument("packages", nargs="+", type=Path)
    four = sub.add_parser("advance")
    four.add_argument("--keys", type=Path, required=True)
    four.add_argument("--repo", type=Path, required=True)
    four.add_argument("--packages-url", help="check each new released asset, "
                                             "downloaded anonymously from here")
    four.add_argument("--feed-config", type=Path,
                      help="the build's feed file (desktop/updates/beta-feed.json): "
                           "downloads must end on its package_hosts")
    for name in ("refresh", "renew-targets"):
        item = sub.add_parser(name)
        item.add_argument("--keys", type=Path, required=True)
        item.add_argument("--repo", type=Path, required=True)
    five = sub.add_parser("rotate-root")
    five.add_argument("--keys", type=Path, required=True)
    five.add_argument("--repo", type=Path, required=True)
    five.add_argument("--new-keys", type=Path)
    five.add_argument("--replace", default="", help="comma-separated roles to re-key")
    six = sub.add_parser("withdraw")
    six.add_argument("--keys", type=Path, required=True)
    six.add_argument("--repo", type=Path, required=True)
    six.add_argument("--lane", required=True, choices=LANES)
    six.add_argument("--pointer", required=True, choices=["latest.json", "latest-preview.json"])
    six.add_argument("--to-version", required=True)
    seven = sub.add_parser("verify")
    seven.add_argument("--repo", type=Path)
    seven.add_argument("--url")
    seven.add_argument("--monitor", action="store_true")
    seven.add_argument("--trust-root", type=Path)
    seven.add_argument("--expect", type=Path,
                       help="JSON from `expected` on the signed commit; anything else fails")
    ten = sub.add_parser("expected")
    ten.add_argument("--repo", type=Path, required=True)
    eight = sub.add_parser("preview")
    eight.add_argument("--repo", type=Path, required=True)
    nine = sub.add_parser("bundle")
    nine.add_argument("--channel", required=True, choices=["internal", "beta"])
    nine.add_argument("--repo", type=Path, required=True)
    nine.add_argument("--lane", required=True, choices=LANES)
    nine.add_argument("--output", type=Path, required=True)
    nine.add_argument("--format", choices=sorted(release.FORMAT_SUFFIX))
    nine.add_argument("--maturity", choices=release.MATURITIES, default="preview")
    nine.add_argument("--packages", type=Path, help="folder holding the released assets")
    nine.add_argument("--recovery-version", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = (init(args.keys, args.repo) if args.channel == "internal"
                      else beta_init(args.keys, args.repo))
        elif args.command == "publish":
            _outside_repository(args.keys)
            packages = _manifest_packages(args.packages)
            for path, package in zip(args.packages, packages):
                # Internal test packages never reach the Beta feed, and the reverse.
                if package["channel"] != args.channel:
                    raise SystemExit(f"{path.name} was built for the {package['channel']} "
                                     f"channel, not {args.channel}")
            result = publish(args.keys, args.repo, channel=args.channel, packages=packages,
                             notes=args.notes)
        elif args.command == "stage":
            _outside_repository(args.keys)
            notes = (args.notes_file.read_text(encoding="utf-8") if args.notes_file
                     else args.notes)
            packages = _manifest_packages(args.packages, fixture=args.fixture)
            if args.fixture:
                for package in packages:
                    package["publishable"] = None   # private by construction, checked above
            # A throwaway qualification feed holds one lane's test builds.
            result = stage(args.keys, args.repo, maturity=args.maturity,
                           packages=packages, notes=notes, every_lane=not args.fixture)
        elif args.command == "advance":
            hosts = None
            if args.feed_config:
                config = json.loads(args.feed_config.read_text(encoding="utf-8"))
                hosts = tuple(config.get("package_hosts") or ())
                if args.packages_url and args.packages_url != config.get("packages_url"):
                    raise PublishError("--packages-url differs from the feed's packages_url")
            result = advance(args.keys, args.repo, packages_url=args.packages_url,
                             package_hosts=hosts)
        elif args.command == "refresh":
            result = refresh(args.keys, args.repo)
        elif args.command == "renew-targets":
            result = renew_targets(args.keys, args.repo)
        elif args.command == "rotate-root":
            replace = tuple(r for r in args.replace.split(",") if r)
            result = rotate_root(args.keys, args.repo, new_keys_dir=args.new_keys,
                                 replace=replace)
        elif args.command == "withdraw":
            result = withdraw(args.keys, args.repo, lane=args.lane, pointer=args.pointer,
                              to_version=args.to_version)
        elif args.command == "verify":
            if not (args.repo or args.url):
                raise PublishError("give --repo or --url")
            wanted = (json.loads(args.expect.read_text(encoding="utf-8"))
                      if args.expect else None)
            result = verify(args.repo, url=args.url, monitor=args.monitor,
                            trust_root=args.trust_root, expect=wanted)
            print(json.dumps(result, indent=2))
            return 1 if result["problems"] else 0
        elif args.command == "preview":
            result = preview(args.repo)
        elif args.command == "expected":
            result = expected(args.repo)
        elif args.channel == "internal":
            result = str(bundle(args.repo, args.output, channel="internal", lane=args.lane))
        else:
            if not (args.format and args.packages):
                raise PublishError("a Beta bundle needs --format and --packages")
            result = str(beta_bundle(args.repo, args.packages, args.output, lane=args.lane,
                                     fmt=args.format, maturity=args.maturity,
                                     recovery_versions=tuple(args.recovery_version)))
    except PublishError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2) if not isinstance(result, str) else result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
