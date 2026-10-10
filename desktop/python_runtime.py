#!/usr/bin/env python3
"""Install the pinned, verified Python a release lane builds with, and record it.

macOS and Windows packages carry the interpreter they are built with, so that
interpreter is chosen here, not whatever a runner happens to have:

    macOS    python.org's 3.13 universal2 framework installer
    Windows  python.org's 3.13 amd64 installer, installed for this account only
    Ubuntu   the distribution's own python3.12, kept current by Ubuntu's security
             updates (its GTK/WebKitGTK bindings come from the same packages)

Each installer is fetched from the URL in desktop/packaging-tools.json and must
match its pinned size and SHA-256 before anything runs; then its publisher
signature is checked on the host (pkgutil for the Developer ID Installer
signature and notarisation, Authenticode for Windows). The pins themselves were
taken from files whose Sigstore signatures were verified against the release
manager's identity; that verification is recorded beside each pin.

    python desktop/python_runtime.py install --lane macos-arm64 \\
        --cache "$RUNNER_TEMP/python" --github-env "$GITHUB_ENV"
    python desktop/python_runtime.py record --lane linux-x64 --python /usr/bin/python3 \\
        --out provenance.json

`install` (a disposable build host only) installs the interpreter and writes a
provenance record; with --github-env it exports REFINIX_PYTHON (the
interpreter) and REFINIX_PYTHON_PROVENANCE (the record) for later steps. The
record travels in the build identity (desktop/build.py interpreter_provenance).
Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

DESKTOP = Path(__file__).resolve().parent
TOOLS = DESKTOP / "packaging-tools.json"
PINS = {"macos-arm64": "python_runtime_macos", "windows-x64": "python_runtime_windows"}
MAC_TEAM = "Python Software Foundation (BMM5U3QVKW)"
WINDOWS_PUBLISHER = "Python Software Foundation"


class RuntimeError_(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def pin(lane: str) -> dict:
    return json.loads(TOOLS.read_text(encoding="utf-8"))[PINS[lane]]


def obtain(lane: str, cache: Path) -> Path:
    """The pinned installer, downloaded once and always re-checked."""
    sys.path.insert(0, str(DESKTOP / "engine"))
    import fetch  # noqa: PLC0415
    wanted = pin(lane)
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{wanted['sha256']}-{Path(wanted['url']).name}"
    if not (path.is_file() and _sha256(path) == wanted["sha256"]):
        fetch._download(wanted["url"], path)
    if path.stat().st_size != wanted["size"] or _sha256(path) != wanted["sha256"]:
        path.unlink(missing_ok=True)
        raise RuntimeError_(f"{path.name} does not match its pinned size and SHA-256")
    return path


def check_mac_signature(pkg: Path, run=subprocess.run) -> str:
    result = run(["/usr/sbin/pkgutil", "--check-signature", str(pkg)],
                 capture_output=True, text=True, check=False)
    text = result.stdout or ""
    if result.returncode != 0 or f"Developer ID Installer: {MAC_TEAM}" not in text \
            or "Notarization: trusted by the Apple notary service" not in text:
        raise RuntimeError_(f"{pkg.name} is not the notarised Developer ID package of "
                            f"{MAC_TEAM}: {text.strip()[-400:]}")
    return text


WINDOWS_SIGNATURE = (
    "$s = Get-AuthenticodeSignature -LiteralPath $env:REFINIX_SIGNED_FILE; "
    "$subject = if ($s.SignerCertificate) { $s.SignerCertificate.Subject } else { '' }; "
    "Write-Output ($s.Status.ToString() + '|' + $subject)")


def check_windows_signature(setup: Path, run=subprocess.run) -> str:
    env = dict(os.environ, REFINIX_SIGNED_FILE=str(setup.resolve()))
    result = run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                  WINDOWS_SIGNATURE], capture_output=True, text=True, env=env, check=False)
    status, _, subject = (result.stdout or "").strip().partition("|")
    if result.returncode != 0 or status != "Valid" or f"O={WINDOWS_PUBLISHER}" not in subject:
        raise RuntimeError_(f"{setup.name} is not validly signed by {WINDOWS_PUBLISHER} "
                            f"({status or (result.stderr or '').strip()[-200:]}; {subject!r})")
    return f"{status}|{subject}"


def _version_of(python: Path) -> str:
    return subprocess.run([str(python), "-c", "import platform; "
                           "print(platform.python_version())"], capture_output=True,
                          text=True, check=True).stdout.strip()


def install(lane: str, cache: Path, target: Path | None = None) -> tuple[Path, dict]:
    """Install the pinned interpreter on this disposable host; its path and record."""
    if os.environ.get("CI") != "true" and os.environ.get("REFINIX_DISPOSABLE_HOST") != "1":
        raise RuntimeError_("install runs only on a disposable build host (CI, or "
                            "REFINIX_DISPOSABLE_HOST=1)")
    wanted = pin(lane)
    installer = obtain(lane, cache)
    short = ".".join(wanted["version"].split(".")[:2])
    if lane == "macos-arm64":
        signature = check_mac_signature(installer)
        subprocess.run(["sudo", "/usr/sbin/installer", "-pkg", str(installer), "-target", "/"],
                       check=True)
        python = Path(f"/Library/Frameworks/Python.framework/Versions/{short}/bin/python{short}")
    elif lane == "windows-x64":
        signature = check_windows_signature(installer)
        target = Path(target or (cache / f"python-{wanted['version']}"))
        subprocess.run([str(installer), "/quiet", "InstallAllUsers=0", f"TargetDir={target}",
                        "Include_launcher=0", "Include_test=0", "Include_doc=0",
                        "Include_tcltk=0", "Shortcuts=0", "PrependPath=0",
                        "AssociateFiles=0", "Include_pip=1"], check=True)
        python = target / "python.exe"
    else:
        raise RuntimeError_(f"{lane} builds with the distribution's Python; use `record`")
    version = _version_of(python)
    if version != wanted["version"]:
        raise RuntimeError_(f"installed Python reports {version}, not {wanted['version']}")
    record = {"version": version, "lane": lane, "source": "python.org installer",
              "url": wanted["url"], "size": wanted["size"], "sha256": wanted["sha256"],
              "publisher_signature": signature.strip().splitlines()[:6],
              "sigstore": wanted.get("sigstore"), "bundled": wanted.get("bundled"),
              "licence": wanted.get("licence"), "reason": wanted.get("reason"),
              "interpreter": str(python),
              "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    return python, record


def record_system(lane: str, python: Path) -> dict:
    """What the distribution's interpreter is (Ubuntu)."""
    packages = {}
    for name in ("python3.12", "libpython3.12", "libpython3.12-stdlib", "libssl3t64"):
        result = subprocess.run(["dpkg-query", "-W", "-f=${Version}", name],
                                capture_output=True, text=True, check=False)
        packages[name] = result.stdout.strip() or None
    return {"version": _version_of(python), "lane": lane,
            "source": "Ubuntu package (kept current by Ubuntu security updates)",
            "packages": packages, "interpreter": str(python),
            "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("install")
    one.add_argument("--lane", required=True, choices=sorted(PINS))
    one.add_argument("--cache", type=Path, default=Path(tempfile.gettempdir()) / "refinix-python")
    one.add_argument("--target", type=Path)
    one.add_argument("--github-env", type=Path)
    two = sub.add_parser("record")
    two.add_argument("--lane", required=True)
    two.add_argument("--python", type=Path, required=True)
    two.add_argument("--out", type=Path, required=True)
    two.add_argument("--github-env", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "install":
            python, record = install(args.lane, args.cache, args.target)
            out = args.cache / "python-provenance.json"
        else:
            python, record = args.python, record_system(args.lane, args.python)
            out = args.out
    except (RuntimeError_, subprocess.CalledProcessError, OSError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    if args.github_env:
        with open(args.github_env, "a", encoding="utf-8") as handle:
            handle.write(f"REFINIX_PYTHON={python}\nREFINIX_PYTHON_PROVENANCE={out}\n")
    print(json.dumps({"python": str(python), "provenance": str(out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
