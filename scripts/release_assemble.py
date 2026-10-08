#!/usr/bin/env python3
"""Assemble one public Refinix release candidate, locally, before anything is published.

Inputs: the packages and build records of every lane — the Windows and Ubuntu
lanes from one `Beta packages` workflow run (downloaded with `gh run download`),
the macOS lane from the release Mac — and that run's details, saved with

    gh run view <id> --json headSha,event,workflowName,conclusion > run.json

    python scripts/release_assemble.py --version 0.1.0-preview.1 \\
        --commit <designated main commit> --run run.json \\
        --inputs ci-artifacts/ mac-out/ --out candidate/

Checks, all of which must hold:

* the run built the designated commit, was started by hand from the Beta
  packages workflow, and succeeded;
* every lane's embedded identity agrees: version, channel `beta`, maturity,
  public build number, source commit, shared snapshot digest (which ties the
  locally built Mac package to the CI lanes), update trust root and feed,
  data format;
* the final bytes hash to what each record says;
* macOS (when signed): Developer ID from the expected Team ID, a stapled
  notarisation ticket, and Gatekeeper's assessment of a copy marked as
  downloaded; Windows (when signed): the Authenticode result recorded on the
  signing host (re-checked natively at acceptance);
* the Ubuntu lane carries its native .deb qualification report, all passed.

A platform whose package is not signed (macOS, Windows) is **not** part of the
publishable set: it is listed as unavailable, with the reason, never published
unsigned. Linux packages have no platform signature; they are authenticated by
HTTPS, the published SHA-256 and, for updates, the Beta TUF root.

Outputs, in `--out`: the publishable files, `SHA256SUMS`, `release.json` (what
the website's download cards show), `publication-preview.json`, draft release
notes, and the exact commands each repository owner runs at publication.
Nothing here signs metadata, uploads, tags or publishes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
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

SOURCE_REPOSITORY = "prachi-satbhai0741/Refinix"
SITE_REPOSITORY = "vedantsur09/refinix-site"
DOWNLOADS = f"https://github.com/{SOURCE_REPOSITORY}/releases/download/"
WORKFLOW = "Beta packages"
LANES = ("macos-arm64", "windows-x64", "linux-x64")
# The files a lane publishes, by maturity of the build, in display order.
PUBLISHED = {"macos-arm64": ("dmg", "zip"), "windows-x64": ("exe",), "linux-x64": ("deb",)}
REQUIRED_SIGNING = {"macos-arm64": "developer-id", "windows-x64": "authenticode"}
AGREE = ("version", "channel", "maturity", "bundle_build", "source_commit",
         "shared_snapshot_digest", "trust_root", "update_feed", "schema_version")
LABELS = {"macos-arm64": ("macOS", "Apple silicon (M1 or later)"),
          "windows-x64": ("Windows", "x64"), "linux-x64": ("Ubuntu", "x86_64 (amd64)")}
FORMAT_LABEL = {"dmg": "DMG — drag to Applications", "zip": "ZIP (update payload)",
                "exe": "Setup (per user)", "deb": ".deb — App Center"}


class AssemblyError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def mac_signature_problem(app_container: Path, team: str, run=subprocess.run) -> str | None:
    """Developer ID from `team`, stapled, and accepted by Gatekeeper as a download."""
    with tempfile.TemporaryDirectory() as folder:
        copy = Path(folder) / app_container.name
        shutil.copyfile(app_container, copy)
        run(["/usr/bin/xattr", "-w", "com.apple.quarantine",
             "0081;00000000;Refinix release check;", str(copy)], check=False)
        if copy.suffix == ".dmg":
            checks = [["/usr/bin/codesign", "--verify", "--strict",
                       f'-R=anchor apple generic and certificate leaf[subject.OU] = "{team}"',
                       str(copy)],
                      ["/usr/bin/xcrun", "stapler", "validate", str(copy)],
                      ["/usr/sbin/spctl", "--assess", "--type", "open",
                       "--context", "context:primary-signature", "-v", str(copy)]]
        else:
            unpacked = Path(folder) / "app"
            run(["/usr/bin/ditto", "-x", "-k", str(copy), str(unpacked)], check=True)
            app = unpacked / "Refinix.app"
            checks = [["/usr/bin/codesign", "--verify", "--deep", "--strict",
                       f'-R=anchor apple generic and certificate leaf[subject.OU] = "{team}"',
                       str(app)],
                      ["/usr/bin/xcrun", "stapler", "validate", str(app)],
                      ["/usr/sbin/spctl", "--assess", "--type", "execute", "-v", str(app)]]
        for argv in checks:
            result = run(argv, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                return f"{Path(argv[0]).name} {argv[1]}: {(result.stderr or '').strip()[-300:]}"
    return None


def assemble(*, version: str, commit: str, run: dict, inputs: list[Path], out: Path,
             notes: str = "", mac_check=mac_signature_problem) -> dict:
    check_run(run, commit)
    packages = find_packages(inputs, version)
    agreed = check_agreement(packages, version, commit)
    label = release.parse(version)
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise AssemblyError(f"{out} is not empty")
    out.mkdir(parents=True, exist_ok=True)
    lanes, publish = {}, []
    for lane in LANES:
        files = {}
        for fmt in PUBLISHED[lane]:
            name = (release.dmg_name(version) if fmt == "dmg"
                    else release.asset_name(version, lane, fmt))
            if name in packages:
                files[fmt] = packages[name]
        status, reason = "available", None
        if not files:
            status, reason = "unavailable", "not built for this release"
        else:
            signing = {item["record"]["embedded_identity"].get("signing")
                       for item in files.values()}
            wanted = REQUIRED_SIGNING.get(lane)
            if wanted and signing != {wanted}:
                status = "unavailable"
                reason = ("not yet signed: a macOS download needs Developer ID signing and "
                          "Apple notarisation" if lane == "macos-arm64" else
                          "not yet signed: a Windows download needs an Authenticode "
                          "signature")
            elif lane == "macos-arm64":
                team = next(iter(files.values()))["record"]["embedded_identity"].get(
                    "publisher")
                for item in files.values():
                    problem = mac_check(item["path"], team)
                    if problem:
                        raise AssemblyError(f"{item['path'].name}: {problem}")
            if lane == "linux-x64" and status == "available":
                report = files["deb"]["path"].parent / "deb-qualification.json"
                if not report.is_file() or not json.loads(report.read_text()).get("passed"):
                    raise AssemblyError("the Ubuntu lane has no passing native .deb "
                                        "qualification report")
        lane_entry = {"platform": LABELS[lane][0], "architecture": LABELS[lane][1],
                      "status": status, "reason": reason, "files": []}
        for fmt, item in files.items():
            record = item["record"]
            entry = {"format": fmt, "label": FORMAT_LABEL[fmt], "name": item["path"].name,
                     "size": record["size"], "sha256": record["sha256"],
                     "minimum_os": record.get("minimum_os"),
                     "url": f"{DOWNLOADS}v{label}/{item['path'].name}",
                     "update_payload": fmt != "dmg"}
            lane_entry["files"].append(entry)
            if status == "available":
                shutil.copyfile(item["path"], out / item["path"].name)
                # Kept beside the file for offline staging; never uploaded.
                shutil.copyfile(f"{item['path']}.manifest.json",
                                out / f"{item['path'].name}.manifest.json")
                publish.append(entry)
        lanes[lane] = lane_entry
    if not publish:
        raise AssemblyError("nothing in this release can be published")
    (out / "SHA256SUMS").write_text("".join(f"{e['sha256']}  {e['name']}\n"
                                            for e in sorted(publish, key=lambda e: e["name"])),
                                    encoding="utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    site = {"version": str(label), "maturity": label.maturity, "public_build":
            agreed["bundle_build"], "source_commit": commit, "assembled_at": stamp,
            "release_page": f"https://github.com/{SOURCE_REPOSITORY}/releases/tag/v{label}",
            "checksums": f"{DOWNLOADS}v{label}/SHA256SUMS",
            "device_testing": "pending" if label.maturity == "preview" else "accepted",
            "lanes": lanes}
    (out / "release.json").write_text(json.dumps(site, indent=2) + "\n", encoding="utf-8")
    preview = {"version": str(label), "commit": commit, "run": run,
               "agreed_identity": agreed, "publish": [e["name"] for e in publish]
               + ["SHA256SUMS"], "unavailable": {lane: entry["reason"]
                                                  for lane, entry in lanes.items()
                                                  if entry["status"] != "available"}}
    (out / "publication-preview.json").write_text(json.dumps(preview, indent=2) + "\n",
                                                  encoding="utf-8")
    (out / "RELEASE-NOTES.md").write_text(release_notes(site, notes), encoding="utf-8")
    (out / "PUBLISH-COMMANDS.md").write_text(commands(site, publish), encoding="utf-8")
    return site


def release_notes(site: dict, notes: str) -> str:
    preview = site["maturity"] == "preview"
    lines = [f"# Refinix {site['version']}" + (" — tester preview" if preview else ""), ""]
    if preview:
        lines += ["**Tester preview, pending device testing.** Not an accepted Beta "
                  "release. Install it only to test, and report what you see with the "
                  "package's SHA-256.", ""]
    if notes:
        lines += [notes.strip(), ""]
    lines += ["## Downloads", "", "| Platform | File | SHA-256 | Status |", "|---|---|---|---|"]
    for lane in site["lanes"].values():
        if lane["status"] != "available":
            lines.append(f"| {lane['platform']} ({lane['architecture']}) | — | — | "
                         f"Unavailable: {lane['reason']} |")
            continue
        for item in lane["files"]:
            lines.append(f"| {lane['platform']} ({lane['architecture']}) | `{item['name']}` "
                         f"| `{item['sha256']}` | {item['label']} |")
    lines += ["", "Check a download with `shasum -a 256 <file>` (macOS), `sha256sum <file>` "
              "(Ubuntu) or `Get-FileHash <file>` (Windows) against `SHA256SUMS`.",
              "", "Ubuntu packages carry no platform signature: they are authenticated by "
              "HTTPS from this release page and the SHA-256 above, and in-app updates by "
              "Refinix's signed update metadata.", ""]
    return "\n".join(lines)


def commands(site: dict, publish: list[dict]) -> str:
    tag = f"v{site['version']}"
    files = " ".join(e["name"] for e in publish) + " SHA256SUMS"
    return f"""# Publishing {site['version']} — run these yourself (CP-B)

## Source repository ({SOURCE_REPOSITORY}): the immutable prerelease

```bash
gh release create {tag} --repo {SOURCE_REPOSITORY} --draft --prerelease \\
  --target {site['source_commit']} --title "Refinix {site['version']}" \\
  --notes-file RELEASE-NOTES.md {files}
gh release view {tag} --repo {SOURCE_REPOSITORY} --json assets --jq '.assets[] | [.name, .size] | @tsv'
gh release edit {tag} --repo {SOURCE_REPOSITORY} --draft=false
```

## Release Mac: sign the targets for the feed (offline key)

```bash
python scripts/update_repository.py stage --keys <offline keys folder> \\
  --repo <refinix-site checkout>/updates/beta --maturity {site['maturity']} \\
  --notes-file RELEASE-NOTES.md {" ".join(e["name"] for e in publish if e["update_payload"])}
# (run in the candidate folder: each package's .manifest.json is beside it)
```

## Website repository ({SITE_REPOSITORY}): owner commits, then the reviewed advance

The download cards are rendered from `release.json` by the source repository's site
exporter (from a checkout of the designated commit), then copied over the website tree.

```bash
sh scripts/build-site.sh <new site folder> <candidate folder>/release.json
cp -R <new site folder>/. <refinix-site checkout>/
git -C <refinix-site checkout> add index.html docs.html site.css docs.css assets CNAME .nojekyll release.json updates/beta
git -C <refinix-site checkout> commit -m "Stage Refinix {site['version']}"
git -C <refinix-site checkout> push origin main
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
