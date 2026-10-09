#!/usr/bin/env python3
"""Native qualification of one Windows setup program, bound to its exact bytes.

Runs only on a disposable Windows machine (a GitHub-hosted runner) with
REFINIX_QUALIFY_DISPOSABLE=1, because it installs and removes Refinix for the
current account. With the exact setup a release would publish:

    setup installs silently for this account      inside the real kill-on-close
                                                    job the update helper uses
    installed program matches its file list        desktop/install_check
    uninstall registration names this version      HKCU uninstall entry
    packaged app starts on scratch data only       scripts/qualify_package_launch.py
    setup uninstalls silently and leaves no registration

    set REFINIX_QUALIFY_DISPOSABLE=1
    python scripts/qualify_windows.py --setup out\\Refinix-0.1.0-beta.1-windows-x64-setup.exe ^
        --report out\\windows-qualification.json

The report is a release-bytes record (scripts/qualification_record.py): the
setup's name, size, SHA-256 and embedded identity, every check and what was
observed, and the host. It is hosted Windows Server evidence, not a Windows 11
desktop observation (SmartScreen and Smart App Control are not exercised).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import qualification_record, qualify_package_launch  # noqa: E402


class Report:
    def __init__(self):
        self.checks = []

    def record(self, name, passed, observed):
        self.checks.append({"check": name, "passed": bool(passed), "observed": observed})
        print(f"{'PASS' if passed else 'FAIL'}  {name}: {observed}", flush=True)


def host() -> dict:
    return {"platform": platform.platform(), "version": platform.version(),
            "release": platform.release(), "python": platform.python_version(),
            "runner_image": "/".join(filter(None, (os.environ.get("ImageOS"),
                                                   os.environ.get("ImageVersion")))) or None}


def qualify(report: Report, setup: Path, manifest: dict | None, work: Path) -> dict:
    """Run every check; returns the build identity (from the manifest, or read
    from the installed package when the setup was downloaded without one)."""
    from desktop import install_check, update_windows
    identity = (manifest or {}).get("embedded_identity") or {}
    app = work / "Refinix"
    log = work / "setup.log"
    if update_windows.registry_snapshot() is not None:
        report.record("setup installs silently for this account", False,
                      "Refinix is already registered for this account; not a clean host")
        return identity
    job = update_windows.Job()
    started = {}
    try:
        code = update_windows.run_installer(setup, app, log, job=job,
                                            record=started.update, seconds=900)
    finally:
        job.close()
    report.record("setup installs silently for this account", code == 0,
                  {"exit": code, "pid": started.get("pid"),
                   "job_limits": started.get("job_limits"),
                   "kill_on_close": bool((started.get("job_limits") or 0)
                                         & update_windows.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)})
    if code != 0:
        return identity
    installed = install_check.installed_identity(app) or {}
    if not identity:
        identity = installed
    version = identity.get("version")
    report.record("installed program is this setup's build", installed == identity,
                  {"version": installed.get("version"),
                   "source_commit": installed.get("source_commit")})
    problem = update_windows.completeness_problem(app, version)
    report.record("installed program matches its file list", problem is None, problem)
    snapshot = update_windows.registry_snapshot()
    problem = update_windows.registration_problem(snapshot, version, app)
    report.record("uninstall registration names this version", problem is None,
                  problem or {"DisplayVersion": version, "InstallLocation": str(app)})
    launched = qualify_package_launch.launch_check(
        app / "Refinix.exe", work / "scratch-data", expect_version=version,
        watch=[Path(os.environ.get("LOCALAPPDATA", work)) / "Refinix"])
    report.record(launched["check"], launched["passed"], launched["observed"])
    uninstaller = app / "unins000.exe"
    result = subprocess.run([str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES",
                             "/NORESTART"], capture_output=True, text=True, timeout=600,
                            check=False) if uninstaller.is_file() else None
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline and (update_windows.registry_snapshot() is not None
                                           or (app / "Refinix.exe").exists()):
        time.sleep(1)
    left = update_windows.registry_snapshot()
    report.record("setup uninstalls silently and leaves no registration",
                  result is not None and result.returncode == 0 and left is None
                  and not (app / "Refinix.exe").exists(),
                  {"exit": None if result is None else result.returncode,
                   "registration_left": left is not None,
                   "program_left": (app / "Refinix.exe").exists()})
    return identity


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--setup", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--commit-tested", default=os.environ.get("GITHUB_SHA"))
    args = parser.parse_args(argv)
    if sys.platform != "win32" or os.environ.get("REFINIX_QUALIFY_DISPOSABLE") != "1":
        print("refused: run on a throwaway Windows machine with "
              "REFINIX_QUALIFY_DISPOSABLE=1", file=sys.stderr)
        return 2
    beside = Path(f"{args.setup}.manifest.json")
    manifest = json.loads(beside.read_text(encoding="utf-8")) if beside.is_file() else None
    report = Report()
    work = Path(tempfile.mkdtemp(prefix="refinix-qualify-"))
    identity = (manifest or {}).get("embedded_identity") or {}
    try:
        identity = qualify(report, args.setup.resolve(), manifest, work)
    except Exception as exc:                               # noqa: BLE001
        report.record("qualification ran to the end", False, f"{type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    record = qualification_record.build(
        lane="windows-x64", host=host(),
        packages=[qualification_record.package_entry(args.setup, identity=identity)],
        checks=report.checks, commit_tested=args.commit_tested)
    args.report.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"{'all passed' if record['passed'] else 'FAILED'} — {args.report}")
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
