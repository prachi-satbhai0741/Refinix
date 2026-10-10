#!/usr/bin/env python3
"""Assemble one public Refinix release candidate, locally, before anything is published.

Inputs: the packages, build records and native qualification reports of every
lane from one `Beta packages` workflow run (downloaded with `gh run download`),
and that run's details, saved with

    gh run view <id> --json headSha,event,workflowName,conclusion > run.json

    python scripts/release_assemble.py --version 0.1.0-beta.1 \\
        --commit <designated main commit> --run run.json \\
        --inputs ci-artifacts/ --out candidate/

Checks, all of which must hold:

* the run built the designated commit, was started by hand from the Beta
  packages workflow, and succeeded;
* every lane's embedded identity agrees: version, channel `beta`, maturity,
  public build number, source commit, shared snapshot digest, update trust
  root and feed, data format; every one is a public build (`publishable`),
  never a private `--scratch` test build;
* the final bytes hash to what each record says, and every published file
  name is plain (letters, digits, `.`, `_`, `-`), so the signed target, the
  download URL and the uploaded asset are the same name;
* each platform's signing is one its lane allows, and is reported as it is:
  macOS Developer ID (with Team ID, stapled ticket and Gatekeeper on a
  quarantined copy) or unsigned with an ad-hoc seal (strict `codesign`
  verification of the app in the ZIP and in the DMG, and `hdiutil verify`);
  Windows Authenticode or unsigned; Ubuntu has no platform signature;
* every published file is named, with its exact size, SHA-256 and embedded
  identity, by a passing native qualification record of its lane
  (scripts/qualification_record.py).

Unsigned macOS and Windows packages are published as the public Beta when
their checks pass, with the operating system's warning shown before the
download. A qualification record is evidence from hosted test machines, not
device acceptance: every platform's device testing stays `pending` here.

Outputs, in `--out`: the publishable files, `SHA256SUMS`, `release.json` (what
the website's download cards show), `publication-preview.json`, draft release
notes, and the exact publication commands. Nothing here signs metadata,
uploads, tags or publishes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.coordinator import release  # noqa: E402
from scripts import qualification_record  # noqa: E402

SOURCE_REPOSITORY = "prachi-satbhai0741/Refinix"
SITE_REPOSITORY = "vedantsur09/refinix-site"
DOWNLOADS = f"https://github.com/{SOURCE_REPOSITORY}/releases/download/"
WORKFLOW = "Beta packages"
LANES = ("macos-arm64", "windows-x64", "linux-x64")
# The files a lane publishes, in display order.
PUBLISHED = {"macos-arm64": ("dmg", "zip"), "windows-x64": ("exe",), "linux-x64": ("deb",)}
# A first install downloads these; the macOS ZIP is the in-app update payload.
FIRST_INSTALL = {"dmg", "exe", "deb"}
# The signing each lane may be published with.
SIGNING_ALLOWED = {"macos-arm64": ("developer-id", "unsigned"),
                   "windows-x64": ("authenticode", "unsigned"),
                   "linux-x64": ("unsigned",)}
# The install capabilities each maturity may be published with (as the feed's
# `stage` step: scripts/update_repository.py CAPABILITIES_FOR).
CAPABILITIES = {"preview": ("preview-test", "provisional", "unavailable"),
                "beta": ("provisional", "qualified", "unavailable"),
                "final": ("qualified", "unavailable")}
AGREE = ("version", "channel", "maturity", "bundle_build", "source_commit",
         "shared_snapshot_digest", "trust_root", "update_feed", "schema_version")
LABELS = {"macos-arm64": ("macOS", "Apple silicon (M1 or later)"),
          "windows-x64": ("Windows", "x64"), "linux-x64": ("Ubuntu", "x86_64 (amd64)")}
FORMAT_LABEL = {"dmg": "DMG — drag to Applications", "zip": "ZIP (update payload)",
                "exe": "Setup (per user)", "deb": ".deb — App Center"}
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
# What the operating system does with this package the first time, shown
# before the download button. Restrained and specific: no claim that the
# package is approved by Apple or Microsoft, or safe by assertion.
OS_WARNING = {
    ("macos-arm64", "unsigned"):
        "Not signed or notarised by Apple. macOS blocks the first open: open System "
        "Settings → Privacy & Security, choose Open Anyway for Refinix, then confirm. "
        "Check the SHA-256 first.",
    ("macos-arm64", "developer-id"):
        "Signed with Developer ID and notarised by Apple.",
    ("windows-x64", "unsigned"):
        "Not code-signed. Microsoft Defender SmartScreen may warn: choose More info → "
        "Run anyway. With Smart App Control on, Windows 11 blocks unsigned programs and "
        "this setup cannot be installed; Refinix does not ask you to turn that off. "
        "Check the SHA-256 first.",
    ("windows-x64", "authenticode"):
        "Authenticode signed.",
    ("linux-x64", "unsigned"):
        "Ubuntu packages carry no platform signature: check the SHA-256. App Center "
        "asks for your password to install it.",
}


class AssemblyError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def display_name(label) -> str:
    """`Refinix Beta 0.1` for a Beta, `Refinix 0.1.0` for a final, the label otherwise."""
    if label.maturity == "beta":
        return f"Refinix Beta {label.major}.{label.minor}"
    if label.maturity == "final":
        return f"Refinix {label.core}"
    return f"Refinix {label} — tester preview"


def check_run(run: dict, commit: str) -> None:
    problems = []
    if run.get("headSha") != commit:
        problems.append(f"the run built {run.get('headSha')}, not {commit}")
    if run.get("event") != "workflow_dispatch":
        problems.append(f"the run was started by {run.get('event')}, not by hand")
    if run.get("workflowName") != WORKFLOW:
        problems.append(f"the run is {run.get('workflowName')!r}, not {WORKFLOW!r}")
    if run.get("conclusion") != "success":
        problems.append(f"the run concluded {run.get('conclusion')!r}")
    if problems:
        raise AssemblyError("; ".join(problems))


def find_packages(inputs: list[Path], version: str) -> dict[str, dict]:
    """Every package of `version` with its external manifest, by file name."""
    found = {}
    for folder in inputs:
        for manifest in Path(folder).rglob("*.manifest.json"):
            artifact = manifest.with_name(manifest.name[:-len(".manifest.json")])
            record = json.loads(manifest.read_text(encoding="utf-8"))
            if record.get("embedded_identity", {}).get("version") != version:
                continue
            if not artifact.is_file():
                raise AssemblyError(f"{artifact.name} is missing beside its manifest")
            if artifact.name in found:
                raise AssemblyError(f"{artifact.name} appears twice in the inputs")
            found[artifact.name] = {"path": artifact, "record": record}
    return found


def find_reports(inputs: list[Path]) -> dict[str, list[Path]]:
    """Every lane's qualification reports in the inputs."""
    found = {lane: [] for lane in LANES}
    for folder in inputs:
        for lane, name in qualification_record.REPORT_NAME.items():
            found[lane].extend(sorted(Path(folder).rglob(name)))
    return found


def check_agreement(packages: dict[str, dict], version: str, commit: str) -> dict:
    """One release: every identity agrees on everything but its lane."""
    label = release.parse(version)
    if label.channel != "beta":
        raise AssemblyError(f"{version} is not a public label")
    reference = None
    for name, item in sorted(packages.items()):
        identity = item["record"]["embedded_identity"]
        if identity.get("source_commit") != commit:
            raise AssemblyError(f"{name} was built from {identity.get('source_commit')}")
        if identity.get("maturity") != label.maturity or identity.get("channel") != "beta":
            raise AssemblyError(f"{name} is not a {label.maturity} Beta build")
        if identity.get("publishable") is not True:
            raise AssemblyError(f"{name} is a private test build (--scratch), never "
                                "published")
        if not SAFE_NAME.fullmatch(name):
            raise AssemblyError(f"{name} is not a plain file name a release asset keeps")
        values = {key: identity.get(key) for key in AGREE}
        if reference is None:
            reference = values
        elif values != reference:
            differ = [k for k in AGREE if values[k] != reference[k]]
            raise AssemblyError(f"{name} disagrees with the other packages about {differ}")
        digest = _sha256(item["path"])
        if digest != item["record"]["sha256"] or \
                item["path"].stat().st_size != item["record"]["size"]:
            raise AssemblyError(f"{name} does not match its recorded size and SHA-256")
    if reference is None:
        raise AssemblyError(f"no package of {version} was found")
    return reference


def _run(argv, run=subprocess.run, **kwargs):
    return run(argv, capture_output=True, text=True, check=False, **kwargs)


def mac_signature_problem(app_container: Path, team: str | None, signing: str,
                          run=subprocess.run) -> str | None:
    """Developer ID: Team ID, stapled ticket, Gatekeeper on a quarantined copy.
    Unsigned: the app's ad-hoc seal verifies strictly, and a DMG verifies."""
    with tempfile.TemporaryDirectory() as folder:
        copy = Path(folder) / app_container.name
        shutil.copyfile(app_container, copy)
        if signing == "developer-id":
            run(["/usr/bin/xattr", "-w", "com.apple.quarantine",
                 "0081;00000000;Refinix release check;", str(copy)], check=False)
        requirement = ([f'-R=anchor apple generic and certificate leaf[subject.OU] = "{team}"']
                       if signing == "developer-id" else [])
        if copy.suffix == ".dmg":
            checks = [["/usr/bin/hdiutil", "verify", str(copy)]]
            if signing == "developer-id":
                checks += [["/usr/bin/codesign", "--verify", "--strict", *requirement,
                            str(copy)],
                           ["/usr/bin/xcrun", "stapler", "validate", str(copy)],
                           ["/usr/sbin/spctl", "--assess", "--type", "open",
                            "--context", "context:primary-signature", "-v", str(copy)]]
            for argv in checks:
                result = _run(argv, run)
                if result.returncode != 0:
                    return f"{Path(argv[0]).name} {argv[1]}: {(result.stderr or '').strip()[-300:]}"
            mount = Path(folder) / "mount"
            mount.mkdir()
            attached = _run(["/usr/bin/hdiutil", "attach", "-readonly", "-nobrowse",
                             "-noautoopen", "-mountpoint", str(mount), str(copy)], run)
            if attached.returncode != 0:
                return f"hdiutil attach: {(attached.stderr or '').strip()[-300:]}"
            try:
                app = mount / "Refinix.app"
                result = _run(["/usr/bin/codesign", "--verify", "--deep", "--strict",
                               *requirement, str(app)], run)
                if result.returncode != 0:
                    return f"codesign --verify (DMG app): {(result.stderr or '').strip()[-300:]}"
            finally:
                _run(["/usr/bin/hdiutil", "detach", str(mount)], run)
            return None
        unpacked = Path(folder) / "app"
        expanded = _run(["/usr/bin/ditto", "-x", "-k", str(copy), str(unpacked)], run)
        if expanded.returncode != 0:
            return f"ditto: {(expanded.stderr or '').strip()[-300:]}"
        app = unpacked / "Refinix.app"
        checks = [["/usr/bin/codesign", "--verify", "--deep", "--strict", *requirement,
                   str(app)]]
        if signing == "developer-id":
            checks += [["/usr/bin/xcrun", "stapler", "validate", str(app)],
                       ["/usr/sbin/spctl", "--assess", "--type", "execute", "-v", str(app)]]
        for argv in checks:
            result = _run(argv, run)
            if result.returncode != 0:
                return f"{Path(argv[0]).name} {argv[1]}: {(result.stderr or '').strip()[-300:]}"
    return None


def assemble(*, version: str, commit: str, run: dict, inputs: list[Path], out: Path,
             notes: str = "", mac_check=mac_signature_problem) -> dict:
    check_run(run, commit)
    packages = find_packages(inputs, version)
    agreed = check_agreement(packages, version, commit)
    reports = find_reports(inputs)
    label = release.parse(version)
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise AssemblyError(f"{out} is not empty")
    lanes, publish, matched = {}, [], []
    for lane in LANES:
        files = {}
        for fmt in PUBLISHED[lane]:
            name = (release.dmg_name(version) if fmt == "dmg"
                    else release.asset_name(version, lane, fmt))
            if name in packages:
                files[fmt] = packages[name]
        if not files:
            lanes[lane] = {"platform": LABELS[lane][0], "architecture": LABELS[lane][1],
                           "status": "unavailable", "reason": "not built for this release",
                           "files": []}
            continue
        missing = [fmt for fmt in PUBLISHED[lane] if fmt not in files]
        if missing:
            raise AssemblyError(f"{lane} is missing its {missing} package(s)")
        identities = [item["record"]["embedded_identity"] for item in files.values()]
        signing = {i.get("signing") for i in identities}
        if len(signing) != 1 or next(iter(signing)) not in SIGNING_ALLOWED[lane]:
            raise AssemblyError(f"{lane} packages are signed {sorted(map(str, signing))}; "
                                f"allowed: {SIGNING_ALLOWED[lane]}")
        signing = next(iter(signing))
        capability = {i.get("install_capability") for i in identities}
        if len(capability) != 1 or next(iter(capability)) not in CAPABILITIES[label.maturity]:
            raise AssemblyError(f"{lane} install capability {sorted(map(str, capability))} "
                                f"is not allowed for a {label.maturity} release")
        if lane == "macos-arm64":
            team = identities[0].get("publisher")
            for item in files.values():
                problem = mac_check(item["path"], team, signing)
                if problem:
                    raise AssemblyError(f"{item['path'].name}: {problem}")
        # Every file is named, byte for byte, by a passing native record.
        for item in files.values():
            errors = []
            for report in reports[lane]:
                try:
                    qualification_record.check(report, lane, item["path"], item["record"])
                    if report not in matched:
                        matched.append(report)
                    break
                except qualification_record.QualificationError as exc:
                    errors.append(str(exc))
            else:
                raise AssemblyError(
                    f"{item['path'].name} has no passing native qualification record "
                    f"bound to its bytes" + (f": {errors[-1]}" if errors else ""))
        seal = {item["record"].get("seal") for item in files.values()}
        if lane == "macos-arm64" and signing == "unsigned" and seal != {"ad-hoc"}:
            raise AssemblyError("unsigned macOS packages must record their ad-hoc seal")
        lane_entry = {"platform": LABELS[lane][0], "architecture": LABELS[lane][1],
                      "status": "available", "reason": None, "signing": signing,
                      "notarized": signing == "developer-id",
                      "seal": next(iter(seal)) if len(seal) == 1 else None,
                      "install_capability": next(iter(capability)),
                      "os_warning": OS_WARNING[(lane, signing)],
                      "device_testing": "pending", "files": []}
        for fmt, item in files.items():
            record = item["record"]
            entry = {"format": fmt, "label": FORMAT_LABEL[fmt], "name": item["path"].name,
                     "size": record["size"], "sha256": record["sha256"],
                     "minimum_os": record.get("minimum_os"),
                     "url": f"{DOWNLOADS}v{label}/{item['path'].name}",
                     "first_install": fmt in FIRST_INSTALL,
                     "update_payload": fmt != "dmg"}
            lane_entry["files"].append(entry)
            publish.append((entry, item))
        lanes[lane] = lane_entry
    if not publish:
        raise AssemblyError("nothing in this release can be published")
    out.mkdir(parents=True, exist_ok=True)
    for entry, item in publish:
        shutil.copyfile(item["path"], out / item["path"].name)
        # Kept beside the file for offline staging; never uploaded.
        shutil.copyfile(f"{item['path']}.manifest.json",
                        out / f"{item['path'].name}.manifest.json")
    for report in matched:
        if (out / report.name).exists():
            raise AssemblyError(f"two {report.name} records qualified this release")
        shutil.copyfile(report, out / report.name)
    entries = [entry for entry, _item in publish]
    (out / "SHA256SUMS").write_text("".join(f"{e['sha256']}  {e['name']}\n"
                                            for e in sorted(entries, key=lambda e: e["name"])),
                                    encoding="utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    site = {"version": str(label), "name": display_name(label), "maturity": label.maturity,
            "public_build": agreed["bundle_build"], "source_commit": commit,
            "assembled_at": stamp,
            "release_page": f"https://github.com/{SOURCE_REPOSITORY}/releases/tag/v{label}",
            "checksums": f"{DOWNLOADS}v{label}/SHA256SUMS",
            # Hosted runners are not people's computers: device testing stays
            # pending until it is observed and recorded.
            "device_testing": "pending",
            "lanes": lanes}
    (out / "release.json").write_text(json.dumps(site, indent=2) + "\n", encoding="utf-8")
    preview = {"version": str(label), "name": site["name"], "commit": commit, "run": run,
               "agreed_identity": agreed, "publish": sorted(e["name"] for e in entries)
               + ["SHA256SUMS"], "unavailable": {lane: entry["reason"]
                                                  for lane, entry in lanes.items()
                                                  if entry["status"] != "available"}}
    (out / "publication-preview.json").write_text(json.dumps(preview, indent=2) + "\n",
                                                  encoding="utf-8")
    (out / "RELEASE-NOTES.md").write_text(release_notes(site, notes), encoding="utf-8")
    (out / "PUBLISH-COMMANDS.md").write_text(commands(site, entries), encoding="utf-8")
    return site


def release_notes(site: dict, notes: str) -> str:
    preview = site["maturity"] == "preview"
    lines = [f"# {site['name']}", "", f"Version `{site['version']}`, build "
             f"{site['public_build']}, from commit `{site['source_commit']}`.", ""]
    if preview:
        lines += ["**Tester preview, pending device testing.** Install it only to test, "
                  "and report what you see with the package's SHA-256.", ""]
    else:
        lines += ["Every package was built from the commit above and checked on hosted "
                  "test machines (Windows Server, Ubuntu 24.04 and macOS runners). "
                  "**Testing on people's own computers is still pending.** Please report "
                  "what you see, with your operating system, the Refinix version and the "
                  "message shown.", ""]
    if notes:
        lines += [notes.strip(), ""]
    lines += ["## Downloads", "",
              "| Platform | File | Minimum | SHA-256 |", "|---|---|---|---|"]
    for lane in site["lanes"].values():
        if lane["status"] != "available":
            lines.append(f"| {lane['platform']} ({lane['architecture']}) | — | — | "
                         f"Unavailable: {lane['reason']} |")
            continue
        for item in lane["files"]:
            lines.append(f"| {lane['platform']} ({lane['architecture']}) | `{item['name']}` "
                         f"({item['label']}) | {item.get('minimum_os') or '—'} | "
                         f"`{item['sha256']}` |")
    lines += ["", "## Before you install", ""]
    for lane in site["lanes"].values():
        if lane["status"] == "available":
            lines.append(f"- **{lane['platform']}:** {lane['os_warning']}")
    lines += ["", "Check a download with `shasum -a 256 <file>` (macOS), `sha256sum <file>` "
              "(Ubuntu) or `Get-FileHash <file>` (Windows) against `SHA256SUMS`.",
              "", "In-app updates are verified with Refinix's signed update metadata "
              "before anything is installed; your saved work and the previous version "
              "are kept for going back.", ""]
    return "\n".join(lines)


def commands(site: dict, entries: list[dict]) -> str:
    tag = f"v{site['version']}"
    files = " ".join(e["name"] for e in entries) + " SHA256SUMS"
    prerelease = " --prerelease" if site["maturity"] == "preview" else ""
    names = sorted([e["name"] for e in entries] + ["SHA256SUMS"])
    return f"""# Publishing {site['name']} ({site['version']}) — CP-B

## Source repository ({SOURCE_REPOSITORY}): the release

```bash
gh release create {tag} --repo {SOURCE_REPOSITORY} --draft{prerelease} \\
  --target {site['source_commit']} --title "{site['name']}" \\
  --notes-file RELEASE-NOTES.md {files}
# The uploaded names must be exactly these, byte sizes as in SHA256SUMS:
#   {' '.join(names)}
gh release view {tag} --repo {SOURCE_REPOSITORY} --json assets --jq '.assets[] | [.name, .size] | @tsv'
gh release edit {tag} --repo {SOURCE_REPOSITORY} --draft=false
```

## Release Mac: sign the targets for the feed (offline key)

```bash
python scripts/update_repository.py stage --keys <offline keys folder> \\
  --repo <refinix-site checkout>/updates/beta --maturity {site['maturity']} \\
  --notes-file RELEASE-NOTES.md {" ".join(e["name"] for e in entries if e["update_payload"])}
# (run in the candidate folder: each package's .manifest.json and its lane's
#  qualification record are beside it)
```

## Website repository ({SITE_REPOSITORY}): reviewed PR, then the feed advance

The download cards are rendered from `release.json` by the source repository's site
exporter (from a checkout of the designated commit), then copied over the website tree.

```bash
sh scripts/build-site.sh <new site folder> <candidate folder>/release.json
cp -R <new site folder>/. <refinix-site checkout>/
git -C <refinix-site checkout> add index.html docs.html site.css docs.css assets CNAME .nojekyll release.json updates/beta
git -C <refinix-site checkout> commit -m "Stage {site['name']}"
# push to a branch and open a PR; after it is merged:
gh workflow run advance-feed.yml --repo {SITE_REPOSITORY}
```
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--run", type=Path, required=True,
                        help="gh run view <id> --json headSha,event,workflowName,conclusion")
    parser.add_argument("--inputs", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--notes", default="")
    args = parser.parse_args(argv)
    try:
        site = assemble(version=args.version, commit=args.commit,
                        run=json.loads(args.run.read_text(encoding="utf-8")),
                        inputs=args.inputs, out=args.out, notes=args.notes)
    except AssemblyError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({lane: entry["status"] for lane, entry in site["lanes"].items()},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
