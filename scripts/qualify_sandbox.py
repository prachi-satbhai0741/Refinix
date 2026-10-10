#!/usr/bin/env python3
"""The Ubuntu Code sandbox, for real, on a throwaway machine.

Runs as an ordinary account with its own systemd user manager (a GitHub-hosted
Ubuntu runner with lingering enabled) and REFINIX_QUALIFY_DISPOSABLE=1. It uses
the application's own LocalSandbox — the same systemd-run service, storage
image and launcher Code validation uses — and records what was observed:

    the sandbox reports every control available here
    an ordinary passing test passes
    the network, files outside the workspace and signals are denied inside
    a test that prints nothing is cancelled promptly, and nothing passes
    a test that prints nothing is stopped at the deadline
    a flood of output is capped
    afterwards no Refinix service, mount or record is left behind

    REFINIX_QUALIFY_DISPOSABLE=1 python scripts/qualify_sandbox.py --report sandbox.json

The profile stays provisional: a hosted runner is not a person's Ubuntu
desktop session. If a control is missing here, that is reported, and the
sandbox stays unavailable rather than running code without it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.coordinator import sandbox_local  # noqa: E402

PASSING = ("import unittest\nfrom module import double\n\n"
           "class T(unittest.TestCase):\n"
           "    def test_double(self):\n        self.assertEqual(double(2), 4)\n")
MODULE = "def double(x):\n    return 2 * x\n"
HOSTILE = ("import os, socket, unittest\n\n"
           "class Confined(unittest.TestCase):\n"
           "    def test_no_network(self):\n"
           "        with self.assertRaises(OSError):\n"
           "            socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
           "    def test_no_files_outside(self):\n"
           "        with self.assertRaises(OSError):\n"
           "            open('/etc/hostname').read()\n"
           "        with self.assertRaises(OSError):\n"
           "            open(os.path.expanduser('~/../escape.txt'), 'w')\n"
           "    def test_no_signals(self):\n"
           "        with self.assertRaises(OSError):\n"
           "            os.kill(1, 0)\n")
QUIET = ("import time, unittest\n\n"
         "class T(unittest.TestCase):\n"
         "    def test_waits(self):\n        time.sleep(600)\n")
FLOOD = ("import sys, unittest\n\n"
         "class T(unittest.TestCase):\n"
         "    def test_prints(self):\n        sys.stdout.write('y' * 2_000_000)\n")


class Report:
    def __init__(self):
        self.checks = []

    def record(self, name, passed, observed):
        self.checks.append({"check": name, "passed": bool(passed), "observed": observed})
        print(f"{'PASS' if passed else 'FAIL'}  {name}: {observed}", flush=True)


def files(**named) -> list[dict]:
    return [{"path": path, "text": text,
             "sha256": hashlib.sha256(text.encode()).hexdigest()}
            for path, text in named.items()]


def summary(report: dict) -> dict:
    return {k: report.get(k) for k in ("ran", "refused", "error", "exit_status",
                                       "tests_run", "service_exit", "output_truncated",
                                       "landlock_abi", "controls")}


def leftovers(home: Path) -> dict:
    units = subprocess.run(["systemctl", "--user", "list-units", "--all", "--plain",
                            "--no-legend", "refinix-sandbox-*"], capture_output=True,
                           text=True, check=False).stdout.split()
    mounts = [line for line in Path("/proc/self/mountinfo").read_text().splitlines()
              if str(home) in line]
    journal = json.loads((home / "sandbox" / "journal.json").read_text()) \
        if (home / "sandbox" / "journal.json").is_file() else {"runs": {}}
    return {"units": units, "mounts": mounts, "records": list(journal["runs"])}


def qualify(report: Report, home: Path) -> None:
    sandbox = sandbox_local.LocalSandbox(home)
    status = sandbox.status()
    report.record("the sandbox reports every control available here", status["available"],
                  {"missing": status.get("missing"), "storage": status.get("storage"),
                   "kernel": status.get("kernel")})
    if not status["available"]:
        return
    result = sandbox.validate(files(**{"module.py": MODULE, "test_module.py": PASSING}))
    report.record("an ordinary passing test passes", sandbox_local.passed(result),
                  summary(result))
    result = sandbox.validate(files(**{"test_confined.py": HOSTILE}))
    report.record("the network, files outside the workspace and signals are denied inside",
                  sandbox_local.passed(result) and result.get("tests_run") == 3,
                  {**summary(result), "output": (result.get("output") or "")[-800:]})
    cancel = threading.Event()
    threading.Timer(3.0, cancel.set).start()
    began = time.monotonic()
    result = sandbox.validate(files(**{"test_quiet.py": QUIET}), cancel=cancel)
    took = round(time.monotonic() - began, 1)
    report.record("a test that prints nothing is cancelled promptly, and nothing passes",
                  took < 3.0 + sandbox_local.STOP_SECONDS + 15
                  and result.get("refused") == "cancelled"
                  and not sandbox_local.passed(result), {**summary(result), "seconds": took})
    sandbox.deadline_seconds = 8
    began = time.monotonic()
    result = sandbox.validate(files(**{"test_quiet.py": QUIET}))
    took = round(time.monotonic() - began, 1)
    report.record("a test that prints nothing is stopped at the deadline",
                  took < 8 + sandbox_local.STOP_SECONDS + 15
                  and result.get("refused") == "deadline"
                  and not sandbox_local.passed(result), {**summary(result), "seconds": took})
    sandbox.deadline_seconds = sandbox_local.DEADLINE_SECONDS + 60
    result = sandbox.validate(files(**{"test_flood.py": FLOOD}))
    report.record("a flood of output is capped",
                  sandbox_local.passed(result) and result.get("output_truncated") is True
                  and len(result.get("output") or "") <= sandbox_local.OUTPUT_LIMIT,
                  summary(result))
    sandbox.cleanup_leftovers()
    left = leftovers(home)
    report.record("afterwards no Refinix service, mount or record is left behind",
                  not any(left.values()), left)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    if os.environ.get("REFINIX_QUALIFY_DISPOSABLE") != "1" or not sys.platform.startswith(
            "linux") or os.geteuid() == 0:
        print("refused: run as an ordinary account on a throwaway Ubuntu machine with "
              "REFINIX_QUALIFY_DISPOSABLE=1", file=sys.stderr)
        return 2
    report = Report()
    home = Path(tempfile.mkdtemp(prefix="refinix-sandbox-qualify-"))
    try:
        qualify(report, home)
    except Exception as exc:                               # noqa: BLE001
        report.record("qualification ran to the end", False, f"{type(exc).__name__}: {exc}")
    record = {"kind": "sandbox", "profile": sandbox_local.PROFILE,
              "qualification": sandbox_local.QUALIFICATION,
              "commit_tested": os.environ.get("GITHUB_SHA"),
              "host": {"platform": platform.platform(), "kernel": platform.release(),
                       "runner_image": os.environ.get("ImageVersion")},
              "checks": report.checks,
              "passed": bool(report.checks) and all(c["passed"] for c in report.checks)}
    args.report.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"{'all passed' if record['passed'] else 'FAILED'} — {args.report}")
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
