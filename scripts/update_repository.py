#!/usr/bin/env python3
"""Create and sign Refinix update metadata (TUF) for one channel.

Release tooling, never shipped in a package. Three steps, run by the person who
holds the channel's keys:

    # once per channel: keys go to a private folder OUTSIDE the repository
    python scripts/update_repository.py init --keys ~/refinix-keys/internal \\
        --repo ~/refinix-repo/internal

    # per release: publish finished packages and their build records
    python scripts/update_repository.py publish --keys ... --repo ... \\
        --channel internal --notes "What changed" out/Refinix-0.1.1-internal.1-*.zip ...

    # optional: one file for offline import (USB or an internal host)
    python scripts/update_repository.py bundle --repo ... --lane macos-arm64 \\
        --channel internal --output Refinix-0.1.1-update.zip

`init` prints the trust root's SHA-256; pass the root file to
`desktop/build.py --trust-root` so packages accept only this channel's
metadata. Internal channel keys are test keys: keep them apart from any
production root, and never publish internal metadata to a Beta feed.

Signing uses securesystemslib's bundled pure-Python Ed25519 (not constant
time). That is acceptable for locally held internal test keys only; a
production root needs a hardware or audited signer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ROLES = ("root", "targets", "snapshot", "timestamp")
EXPIRY_DAYS = {"root": 365, "targets": 180, "snapshot": 30, "timestamp": 7}
LANES = ("macos-arm64", "windows-x64", "linux-x64")


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


def _expires(role: str, now: datetime | None = None, days: dict | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return (now + timedelta(days=(days or EXPIRY_DAYS)[role])).replace(microsecond=0)


def _outside_repository(folder: Path) -> None:
    folder = folder.resolve()
    if folder == ROOT or ROOT in folder.parents:
        raise SystemExit("refusing to keep signing keys inside the repository")


def init(keys_dir: Path, repo: Path, *, check_location: bool = True) -> dict:
    """Generate one key per role, write 1.root.json, return its identity."""
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


def publish(keys_dir: Path, repo: Path, *, channel: str, packages: list[dict],
            notes: str = "", now: datetime | None = None, expiry: dict | None = None) -> dict:
    """Add packages and per-lane `latest.json`, then sign targets/snapshot/timestamp.

    Each package dict: path, lane, version, build_set, min_os, schema_version,
    engine_release. Versions of the metadata files increase on every publish.
    """
    from tuf.api.metadata import (MetaFile, Metadata, Snapshot, TargetFile, Targets,
                                  Timestamp)
    metadata_dir = repo / "metadata"
    targets_path = metadata_dir / "targets.json"
    targets = (Metadata.from_file(str(targets_path)) if targets_path.exists()
               else Metadata(Targets(expires=_expires("targets", now, expiry))))
    targets.signed.version += 1 if targets_path.exists() else 0
    targets.signed.expires = _expires("targets", now, expiry)
    for package in packages:
        source = Path(package["path"])
        name = f"{channel}/{package['lane']}/{source.name}"
        destination = repo / "targets" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        custom = {"version": package["version"], "lane": package["lane"],
                  "channel": channel, "build_set": package.get("build_set")}
        target = TargetFile.from_file(name, str(destination), ["sha256"])
        target.unrecognized_fields["custom"] = custom
        targets.signed.targets[name] = target
        latest = {"version": package["version"], "build_set": package.get("build_set"),
                  "lane": package["lane"], "channel": channel, "artifact": name,
                  "min_os": package.get("min_os"),
                  "schema_version": package.get("schema_version"),
                  "engine_release": package.get("engine_release"), "notes": notes,
                  "prerequisites": package.get("prerequisites", [])}
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


def bundle(repo: Path, output: Path, *, channel: str, lane: str) -> Path:
    """One zip with the metadata and the lane's offered package, for offline import."""
    latest_name = f"{channel}/{lane}/latest.json"
    latest = json.loads((repo / "targets" / latest_name).read_text(encoding="utf-8"))
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted((repo / "metadata").glob("*.json")):
            archive.write(path, f"metadata/{path.name}")
        for name in (latest_name, latest["artifact"]):
            archive.write(repo / "targets" / name, f"targets/{name}")
    return output


def _package_from_record(path: Path) -> dict:
    """Read lane/version details from the build driver's external manifest."""
    manifest = json.loads(Path(f"{path}.manifest.json").read_text(encoding="utf-8"))
    identity = manifest["embedded_identity"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["sha256"]:
        raise SystemExit(f"{path.name} does not match its manifest")
    # Numeric minimums the client can compare; the manifest's text says more.
    minimum = {"windows-x64": "10.0.22000",
               "linux-x64": "24.04"}.get(manifest["lane"], manifest.get("minimum_os"))
    return {"path": str(path), "lane": manifest["lane"], "version": identity["version"],
            "build_set": identity["build_set"], "min_os": minimum,
            "schema_version": identity.get("schema_version"),
            "engine_release": (identity.get("engines") or [{}])[0].get("release")}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("init")
    one.add_argument("--keys", type=Path, required=True)
    one.add_argument("--repo", type=Path, required=True)
    two = sub.add_parser("publish")
    two.add_argument("--keys", type=Path, required=True)
    two.add_argument("--repo", type=Path, required=True)
    two.add_argument("--channel", required=True, choices=["internal", "beta"])
    two.add_argument("--notes", default="")
    two.add_argument("packages", nargs="+", type=Path)
    three = sub.add_parser("bundle")
    three.add_argument("--repo", type=Path, required=True)
    three.add_argument("--channel", required=True)
    three.add_argument("--lane", required=True, choices=LANES)
    three.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "init":
        print(json.dumps(init(args.keys, args.repo), indent=2))
    elif args.command == "publish":
        _outside_repository(args.keys)
        packages = [_package_from_record(path) for path in args.packages]
        print(json.dumps(publish(args.keys, args.repo, channel=args.channel,
                                 packages=packages, notes=args.notes), indent=2))
    else:
        print(bundle(args.repo, args.output, channel=args.channel, lane=args.lane))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
