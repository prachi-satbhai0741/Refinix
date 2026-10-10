#!/usr/bin/env python3
"""One native qualification record, bound to the exact package bytes it checked.

Every published package carries one: the Ubuntu `.deb` (scripts/qualify_deb.py
--real), the Windows setup (scripts/qualify_windows.py) and the macOS DMG and
ZIP (scripts/qualify_macos.py). The release assembler and the feed's `stage`
step refuse a package unless a record here names its exact name, size,
SHA-256 and embedded build identity, says `passed: true` as a JSON boolean,
and carries every check its lane requires — each one passed.

A record says what was observed on which host. It is not device acceptance:
hosted runners are not people's own computers, and that stays pending.

    {"schema": "refinix-native-qualification/1", "kind": "release-bytes",
     "lane": "linux-x64", "host": {...}, "commit_tested": "<sha>",
     "packages": [{"name", "size", "sha256", "embedded_identity_sha256",
                   "version", "source_commit", "shared_snapshot_digest"}],
     "required": [...], "checks": [{"check", "passed", "observed"}],
     "passed": true, "created_at": "..."}

Standard library only.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "refinix-native-qualification/1"
KIND = "release-bytes"
REPORT_NAME = {"linux-x64": "deb-qualification.json",
               "windows-x64": "windows-qualification.json",
               "macos-arm64": "macos-qualification.json"}

# The checks a lane's release-bytes record must contain, each passed. Names
# are the exact `check` strings the qualification scripts record.
REQUIRED = {
    "linux-x64": (
        "real package carries only supported control fields",
        "real package ships ./opt/refinix/Refinix",
        "real package ships ./opt/refinix/_internal/refinix-build.json",
        "real package ships ./opt/refinix/_internal/refinix-files.json",
        "real package ships ./usr/share/polkit-1/actions/com.refinix.desktop.policy",
        "real package ships ./usr/share/applications/refinix.desktop",
        "real package installs with its dependencies",
        "installed tree matches its file list",
        "root entry refuses without pkexec",
        "packaged app starts on scratch data only",
    ),
    "windows-x64": (
        "setup installs silently for this account",
        "installed program is this setup's build",
        "installed program matches its file list",
        "uninstall registration names this version",
        "packaged app starts on scratch data only",
        "setup uninstalls silently and leaves no registration",
    ),
    "macos-arm64": (
        "DMG verifies",
        "app in the DMG passes the strict ad-hoc seal check",
        "app in the ZIP passes the strict ad-hoc seal check",
        "DMG and ZIP carry the same app",
        "every shipped binary's minimum macOS is at or below the declared minimum",
        "packaged app starts on scratch data only",
        "packaged app starts on the oldest supported macOS runner",
    ),
}


class QualificationError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_digest(value) -> str:
    """The same digest desktop/build.py writes as `embedded_identity_sha256`."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def package_entry(path: Path, manifest: dict | None = None,
                  identity: dict | None = None) -> dict:
    """What a record says about one package: its bytes and its build identity.

    `manifest` is the build's `<artifact>.manifest.json`; without it, the
    manifest beside the file is read — or, for a downloaded public file that
    has none, `identity` is the build identity read out of the package itself
    (the same JSON the manifest records, so the digests agree).
    """
    path = Path(path)
    if identity is None:
        if manifest is None:
            manifest = json.loads(Path(f"{path}.manifest.json").read_text(encoding="utf-8"))
        identity = manifest.get("embedded_identity") or {}
    return {"name": path.name, "size": path.stat().st_size, "sha256": _sha256(path),
            "embedded_identity_sha256": canonical_digest(identity),
            "version": identity.get("version"),
            "source_commit": identity.get("source_commit"),
            "shared_snapshot_digest": identity.get("shared_snapshot_digest")}


def build(*, lane: str, host: dict, packages: list[dict], checks: list[dict],
          commit_tested: str | None) -> dict:
    """A complete record; `passed` is True only when every check passed and
    every required check is present."""
    names = {c.get("check") for c in checks}
    missing = [name for name in REQUIRED[lane] if name not in names]
    passed = bool(checks) and not missing and all(c.get("passed") is True for c in checks)
    return {"schema": SCHEMA, "kind": KIND, "lane": lane, "host": host,
            "commit_tested": commit_tested, "packages": packages,
            "required": list(REQUIRED[lane]), "missing": missing, "checks": checks,
            "passed": passed,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def check(record, lane: str, artifact: Path, manifest: dict) -> None:
    """The record qualifies exactly this artifact; QualificationError otherwise."""
    if isinstance(record, (str, Path)):
        try:
            record = json.loads(Path(record).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise QualificationError(f"the qualification report is unreadable: {exc}") \
                from exc
    if not isinstance(record, dict):
        raise QualificationError("the qualification report is not a record")
    problems = []
    if record.get("schema") != SCHEMA or record.get("kind") != KIND:
        raise QualificationError("the qualification report is not a "
                                 f"{SCHEMA} release-bytes record")
    if record.get("lane") != lane:
        problems.append(f"it is for {record.get('lane')!r}, not {lane}")
    if record.get("passed") is not True:
        problems.append(f"it says passed={record.get('passed')!r}")
    checks = record.get("checks")
    if not isinstance(checks, list) or not checks:
        problems.append("it has no checks")
        checks = []
    results = {}
    for item in checks:
        if not isinstance(item, dict):
            problems.append("a check is malformed")
            continue
        results.setdefault(item.get("check"), []).append(item.get("passed"))
    failed = sorted(str(name) for name, values in results.items()
                    if any(value is not True for value in values))
    if failed:
        problems.append(f"these checks did not pass: {failed}")
    missing = [name for name in REQUIRED[lane] if name not in results]
    if missing:
        problems.append(f"these required checks are missing: {missing}")
    wanted = package_entry(artifact, manifest)
    entries = [p for p in record.get("packages") or [] if isinstance(p, dict)
               and p.get("name") == wanted["name"]]
    if not entries:
        problems.append(f"it does not name {wanted['name']}")
    elif entries[0] != wanted:
        differ = sorted(k for k in wanted if entries[0].get(k) != wanted[k])
        problems.append(f"it describes other bytes or another build of "
                        f"{wanted['name']} ({differ})")
    if problems:
        raise QualificationError(f"{Path(artifact).name}: " + "; ".join(problems))
