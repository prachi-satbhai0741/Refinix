#!/usr/bin/env python3
"""Native qualification of one macOS DMG and ZIP, bound to their exact bytes.

Runs on a disposable Mac (a GitHub-hosted runner) with
REFINIX_QUALIFY_DISPOSABLE=1. With the exact files a release would publish:

    DMG verifies                                   hdiutil verify
    app in the DMG passes the strict ad-hoc seal check
    app in the ZIP passes the strict ad-hoc seal check
                                                   codesign --verify --deep --strict
                                                   (Developer ID builds: with the Team
                                                   ID requirement)
    DMG and ZIP carry the same app                 every file's SHA-256
    every shipped binary's minimum macOS is at or below the declared minimum
                                                   LSMinimumSystemVersion vs each Mach-O
    packaged app starts on scratch data only       scripts/qualify_package_launch.py

The app is run from a copy in a temporary folder, never /Applications.

    python scripts/qualify_macos.py --dmg out/Refinix-0.1.0-beta.1-macos-arm64.dmg \\
        --zip out/Refinix-0.1.0-beta.1-macos-arm64.zip --report partial.json

Then, on the oldest arm64 macOS runner available, the same bytes once more:

    python scripts/qualify_macos.py --dmg ... --zip ... --floor --merge partial.json \\
        --report macos-qualification.json

which adds "packaged app starts on the oldest supported macOS runner" (naming
that runner's macOS version) and writes the release-bytes record
(scripts/qualification_record.py). Gatekeeper's first-open decision on a
person's Mac (quarantine, Open Anyway) is not exercised here and stays pending.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT, ROOT / "desktop"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from scripts import qualification_record, qualify_package_launch  # noqa: E402

FLOOR_CHECK = "packaged app starts on the oldest supported macOS runner"


class Report:
    def __init__(self, checks=None):
        self.checks = list(checks or [])

    def record(self, name, passed, observed):
        self.checks.append({"check": name, "passed": bool(passed), "observed": observed})
        print(f"{'PASS' if passed else 'FAIL'}  {name}: {observed}", flush=True)


def run(argv) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def host() -> dict:
    return {"platform": platform.platform(), "macos": platform.mac_ver()[0],
            "build": run(["sw_vers", "-buildVersion"]).stdout.strip(),
            "machine": platform.machine(), "python": platform.python_version(),
            "runner_image": "/".join(filter(None, (os.environ.get("ImageOS"),
                                                   os.environ.get("ImageVersion")))) or None}


def packaged_identity(zip_path: Path) -> dict:
    """The build identity inside a downloaded ZIP, read without running it."""
    import zipfile
    with zipfile.ZipFile(zip_path) as archive:
        return json.loads(archive.read("Refinix.app/Contents/Resources/refinix-build.json"))


def tree(app: Path) -> dict:
    found = {}
    for path in sorted(app.rglob("*")):
        relative = str(path.relative_to(app))
        if path.is_symlink():
            found[relative] = "link:" + os.readlink(path)
        elif path.is_file():
            digest = hashlib.sha256()
            with open(path, "rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            found[relative] = digest.hexdigest()
    return found


def seal_check(app: Path, identity: dict) -> tuple[bool, str]:
    argv = ["/usr/bin/codesign", "--verify", "--deep", "--strict"]
    if identity.get("signing") == "developer-id":
        argv.append(f'-R=anchor apple generic and certificate leaf[subject.OU] = '
                    f'"{identity.get("publisher")}"')
    result = run(argv + [str(app)])
    detail = run(["/usr/bin/codesign", "-dv", str(app)]).stderr
    signature = next((line for line in detail.splitlines()
                      if line.startswith("Signature=")), "")
    return result.returncode == 0, (result.stderr.strip()[-300:] or signature or "ok")


def launch(report: Report, app_source: Path, work: Path, version: str, name: str) -> None:
    copy = work / "run" / "Refinix.app"
    copy.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["/usr/bin/ditto", str(app_source), str(copy)], check=True)
    launched = qualify_package_launch.launch_check(
        copy / "Contents" / "MacOS" / "Refinix", work / "scratch-data",
        expect_version=version)
    observed = {**launched["observed"], "macos": platform.mac_ver()[0]}
    report.record(name, launched["passed"], observed)


def qualify(report: Report, dmg: Path, zip_path: Path, identity: dict, work: Path,
            floor: bool) -> None:
    version = identity["version"]
    if not floor:
        result = run(["/usr/bin/hdiutil", "verify", str(dmg)])
        report.record("DMG verifies", result.returncode == 0,
                      (result.stderr or result.stdout).strip()[-200:])
    mount = work / "mount"
    mount.mkdir()
    attached = run(["/usr/bin/hdiutil", "attach", "-readonly", "-nobrowse", "-noautoopen",
                    "-mountpoint", str(mount), str(dmg)])
    if attached.returncode != 0:
        report.record("app in the DMG passes the strict ad-hoc seal check", False,
                      attached.stderr.strip()[-300:])
        return
    try:
        dmg_app = mount / "Refinix.app"
        if floor:
            launch(report, dmg_app, work, version, FLOOR_CHECK)
            return
        ok, detail = seal_check(dmg_app, identity)
        report.record("app in the DMG passes the strict ad-hoc seal check", ok, detail)
        unpacked = work / "zip"
        subprocess.run(["/usr/bin/ditto", "-x", "-k", str(zip_path), str(unpacked)],
                       check=True)
        zip_app = unpacked / "Refinix.app"
        ok, detail = seal_check(zip_app, identity)
        report.record("app in the ZIP passes the strict ad-hoc seal check", ok, detail)
        dmg_tree, zip_tree = tree(dmg_app), tree(zip_app)
        differ = sorted(set(dmg_tree) ^ set(zip_tree)
                        | {k for k in set(dmg_tree) & set(zip_tree)
                           if dmg_tree[k] != zip_tree[k]})
        report.record("DMG and ZIP carry the same app", not differ,
                      {"files": len(dmg_tree), "differ": differ[:10]})
        import build  # noqa: PLC0415 - desktop/build.py, for the Mach-O floor
        info = plistlib.loads((zip_app / "Contents" / "Info.plist").read_bytes())
        declared = info.get("LSMinimumSystemVersion", "")
        floor_found, which = build.bundle_floor(zip_app)
        declared_key = build._version(declared) if declared else (0,)
        report.record("every shipped binary's minimum macOS is at or below the declared "
                      "minimum", bool(declared) and floor_found <= declared_key,
                      {"declared": declared,
                       "highest_binary_minimum": ".".join(map(str, floor_found)),
                       "binary": which})
        launch(report, zip_app, work, version, "packaged app starts on scratch data only")
    finally:
        run(["/usr/bin/hdiutil", "detach", str(mount)])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dmg", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--floor", action="store_true",
                        help="only launch the DMG's app here, the oldest macOS runner")
    parser.add_argument("--merge", type=Path,
                        help="the first run's partial record, to complete")
    parser.add_argument("--commit-tested", default=os.environ.get("GITHUB_SHA"))
    parser.add_argument("--expect-version")
    args = parser.parse_args(argv)
    if sys.platform != "darwin" or os.environ.get("REFINIX_QUALIFY_DISPOSABLE") != "1":
        print("refused: run on a throwaway Mac with REFINIX_QUALIFY_DISPOSABLE=1",
              file=sys.stderr)
        return 2
    manifests = {}
    for path in (args.dmg, args.zip):
        beside = Path(f"{path}.manifest.json")
        manifests[path] = json.loads(beside.read_text(encoding="utf-8")) \
            if beside.is_file() else None
    identity = (manifests[args.zip] or {}).get("embedded_identity") or packaged_identity(
        args.zip)
    earlier = json.loads(args.merge.read_text(encoding="utf-8")) if args.merge else {}
    report = Report(earlier.get("checks"))
    if args.expect_version is not None:
        report.record("package is the requested public version",
                      identity.get("version") == args.expect_version,
                      {"expected": args.expect_version, "observed": identity.get("version")})
    work = Path(tempfile.mkdtemp(prefix="refinix-qualify-"))
    try:
        qualify(report, args.dmg.resolve(), args.zip.resolve(), identity, work, args.floor)
    except Exception as exc:                               # noqa: BLE001
        report.record("qualification ran to the end", False, f"{type(exc).__name__}: {exc}")
    finally:
        subprocess.run(["/usr/bin/hdiutil", "detach", str(work / "mount")],
                       capture_output=True, check=False)
        shutil.rmtree(work, ignore_errors=True)
    hosts = {**({"first": earlier.get("host")} if earlier else {}),
             ("floor" if args.floor else "first"): host()}
    record = qualification_record.build(
        lane="macos-arm64", host=hosts,
        packages=[qualification_record.package_entry(p, m, None if m else identity)
                  for p, m in manifests.items()],
        checks=report.checks, commit_tested=args.commit_tested)
    if not args.floor:
        # A first run alone is never the release record: the floor check is
        # required, so `passed` stays False until the floor run completes it.
        record["host"] = host()
    args.report.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"{'all passed' if record['passed'] else 'incomplete or FAILED'} — {args.report}")
    if args.floor or args.merge:
        return 0 if record["passed"] else 1
    failed = [c for c in report.checks if c["passed"] is not True]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
