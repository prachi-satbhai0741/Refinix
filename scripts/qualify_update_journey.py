#!/usr/bin/env python3
"""A packaged Refinix updates itself from N to N+1 on a disposable machine, for real.

The real installed package, the real coordinator, the real update helper and
the operating system's real install path (macOS app swap in /Applications,
Windows per-user setup inside a kill-on-close job, Ubuntu `.deb` through
pkexec and the root step), with synthetic saved work on a scratch data folder.
Only on a throwaway runner (REFINIX_QUALIFY_DISPOSABLE=1).

The two packages are private test builds of the commit under test
(`desktop/build.py --scratch`, never publishable) trusting a throwaway update
root; N+1 arrives as a signed offline bundle. The journey presses Import and
Install and restart through desktop/qualify_control.py, which only such a
private build accepts. On Ubuntu, a test-only polkit rule on the runner answers
the administrator prompt; the real prompt on a person's desktop stays pending.

Journeys (each starts from a fresh install of N and fresh data):

    update      N -> N+1: relaunch, the new window confirms, the update commits,
                the saved work is still there
    rollback    N+1 stops right after starting (before its window can confirm):
                the helper puts N back, with the data as it was
    interrupt   the helper is killed while it replaces the app: the next launch
                finishes or undoes it, never leaves a mixed install

    python scripts/qualify_update_journey.py --lane linux-x64 --old <N package> \\
        --new-bundle <N+1 bundle> --old-version 0.1.0-beta.901 \\
        --new-version 0.1.0-beta.902 --report journey.json [--journey update ...]

The report lists every check and what was observed. It is hosted-runner
evidence about the update mechanism of this commit, not the release packages'
bytes and not a person's computer.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PORTS = tuple(range(8770, 8778))
LOCAL = Path(os.environ.get("LOCALAPPDATA", "C:/")) / "Programs" / "Refinix"
INSTALL = {"macos-arm64": Path("/Applications/Refinix.app"), "windows-x64": LOCAL,
           "linux-x64": Path("/opt/refinix")}
IDENTITY = {"macos-arm64": "Contents/Resources/refinix-build.json",
            "windows-x64": "_internal/refinix-build.json",
            "linux-x64": "_internal/refinix-build.json"}
PROGRAM = {"macos-arm64": "Contents/MacOS/Refinix", "windows-x64": "Refinix.exe",
           "linux-x64": "Refinix"}
POLKIT_RULE = Path("/etc/polkit-1/rules.d/49-refinix-qualification.rules")


class Report:
    def __init__(self):
        self.checks = []

    def record(self, name, passed, observed):
        self.checks.append({"check": name, "passed": bool(passed), "observed": observed})
        print(f"{'PASS' if passed else 'FAIL'}  {name}: {observed}", flush=True)


def run(argv, **kwargs):
    return subprocess.run(argv, capture_output=True, text=True, check=False, **kwargs)


def installed_version(lane: str) -> str | None:
    try:
        return json.loads((INSTALL[lane] / IDENTITY[lane]).read_text(encoding="utf-8"))[
            "version"]
    except (OSError, ValueError, KeyError):
        return None


# --------------------------------------------------------------------------
# Installing N the way a person would, on this runner
# --------------------------------------------------------------------------

def install_old(lane: str, package: Path, work: Path) -> None:
    if lane == "macos-arm64":
        unpacked = work / "old-app"
        shutil.rmtree(unpacked, ignore_errors=True)
        subprocess.run(["/usr/bin/ditto", "-x", "-k", str(package), str(unpacked)], check=True)
        shutil.rmtree(INSTALL[lane], ignore_errors=True)
        subprocess.run(["/usr/bin/ditto", str(unpacked / "Refinix.app"), str(INSTALL[lane])],
                       check=True)
    elif lane == "windows-x64":
        uninstaller = INSTALL[lane] / "unins000.exe"
        if uninstaller.is_file():
            run([str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"])
            time.sleep(5)
        result = run([str(package), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                      "/CURRENTUSER"], timeout=900)
        if result.returncode != 0:
            raise RuntimeError(f"setup of N failed ({result.returncode})")
    else:
        run(["sudo", "dpkg", "--purge", "refinix"])
        run(["sudo", "rm", "-rf", "/var/lib/refinix"])
        result = run(["sudo", "apt-get", "install", "-y", "--allow-downgrades",
                      "--no-install-recommends", str(package.resolve())], timeout=900)
        if result.returncode != 0:
            raise RuntimeError(f"apt could not install N: {result.stderr[-600:]}")


def allow_refinix_prompts_for_this_runner() -> None:
    """Ubuntu only: answer Refinix's own polkit actions for this account, here.

    A rule file on a throwaway runner, so the real pkexec and polkit decide
    and the real root step runs; on a person's desktop the administrator
    prompt is shown instead. Nothing else is allowed by it.
    """
    user = os.environ.get("USER") or run(["id", "-un"]).stdout.strip()
    rule = ("polkit.addRule(function(action, subject) {\n"
            "  if (action.id.indexOf(\"com.refinix.desktop.deb-\") == 0 &&\n"
            f"      subject.user == \"{user}\") {{ return polkit.Result.YES; }}\n"
            "});\n")
    staged = Path(tempfile.mkdtemp()) / POLKIT_RULE.name
    staged.write_text(rule, encoding="utf-8")
    subprocess.run(["sudo", "install", "-m", "0644", str(staged), str(POLKIT_RULE)], check=True)
    run(["sudo", "systemctl", "restart", "polkit"])


# --------------------------------------------------------------------------
# Talking to the running app
# --------------------------------------------------------------------------

def http(port: int, method: str, path: str, body: dict | None = None, timeout=10):
    data = json.dumps(body or {}).encode() if method == "POST" else None
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data,
                                     method=method,
                                     headers={"Host": f"127.0.0.1:{port}",
                                              "Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        return json.load(response)


def find(data_root: Path) -> tuple[int | None, dict | None]:
    for port in PORTS:
        try:
            status = http(port, "GET", "/v1/status", timeout=10)
        except (OSError, ValueError):
            continue
        if Path((status.get("process") or {}).get("data_root") or "").resolve() == data_root:
            return port, status
    return None, None


def wait_for_app(data_root: Path, seconds: float, version: str | None = None):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        port, status = find(data_root)
        if status and (version is None or (status.get("build") or {}).get("version")
                       == version):
            return port, status
        time.sleep(1)
    return None, None


class App:
    def __init__(self, lane: str, data_root: Path, env: dict):
        self.lane, self.data_root, self.env = lane, data_root, env

    def launch(self) -> None:
        program = INSTALL[self.lane] / PROGRAM[self.lane]
        env = dict(os.environ, **self.env)
        self.log = open(self.data_root.parent / "app.log", "ab")
        flags = {"start_new_session": True} if sys.platform != "win32" else {}
        subprocess.Popen([str(program)], env=env, stdin=subprocess.DEVNULL,
                         stdout=self.log, stderr=subprocess.STDOUT, **flags)

    def ask(self, action: str, seconds: float = 120, **fields) -> dict | None:
        request_id = secrets.token_hex(4)
        result = self.data_root / "qualify-result.json"
        result.unlink(missing_ok=True)
        temporary = self.data_root / ".qualify-request.tmp"
        temporary.write_text(json.dumps({"token": self.env["REFINIX_QUALIFY_TOKEN"],
                                         "id": request_id, "action": action, **fields}))
        os.replace(temporary, self.data_root / "qualify-request.json")
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                answer = json.loads(result.read_text(encoding="utf-8"))
                if answer.get("id") == request_id:
                    return answer.get("result")
            except (OSError, ValueError):
                pass
            time.sleep(0.5)
        return None


def journal(data_root: Path) -> dict:
    try:
        return json.loads((data_root / "updates" / "install-journal.json").read_text(
            encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def stop_everything(lane: str) -> None:
    import psutil
    for process in psutil.process_iter(["pid", "exe", "cmdline"]):
        try:
            text = " ".join(process.info.get("cmdline") or [])
            if str(INSTALL[lane]) in text or (process.info.get("exe") or "").startswith(
                    str(INSTALL[lane])):
                process.kill()
        except (psutil.Error, OSError):
            continue
    time.sleep(2)


def seed(port: int) -> list[dict]:
    """Synthetic saved work the update must keep."""
    for title in ("Inspection summary (synthetic)", "Code review notes (synthetic)"):
        http(port, "POST", "/v1/chats", {"title": title})
    return sorted((c["chat_id"], c.get("title")) for c in http(port, "GET", "/v1/chats")[
        "chats"])


def saved(port: int) -> list:
    return sorted((c["chat_id"], c.get("title")) for c in http(port, "GET", "/v1/chats")[
        "chats"])


# --------------------------------------------------------------------------
# The journeys
# --------------------------------------------------------------------------

def start_update(report: Report, app: App, args, name: str) -> tuple[int | None, list]:
    app.launch()
    port, status = wait_for_app(app.data_root, 180, args.old_version)
    report.record(f"{name}: N starts on scratch data", status is not None,
                  {"port": port, "version": (status or {}).get("build", {}).get("version")})
    if status is None:
        return None, []
    work = seed(port)
    imported = app.ask("import", path=str(args.new_bundle.resolve()))
    state = ((imported or {}).get("updates") or {}).get("download") or {}
    report.record(f"{name}: the signed bundle for N+1 is verified", state.get("state")
                  == "verified", imported)
    if state.get("state") != "verified":
        return None, work
    http(port, "POST", "/v1/updates/prepare")
    deadline, install = time.monotonic() + 600, {}
    while time.monotonic() < deadline:
        install = http(port, "GET", "/v1/updates").get("install") or {}
        if install.get("state") in ("ready", "failed"):
            break
        time.sleep(1)
    report.record(f"{name}: prepared for Install and restart", install.get("state") == "ready",
                  {k: install.get(k) for k in ("state", "error", "method", "version")})
    if install.get("state") != "ready":
        return None, work
    return port, work


def journey_update(report: Report, app: App, args) -> None:
    port, work = start_update(report, app, args, "update")
    if port is None:
        return
    answer = app.ask("install", seconds=60)
    report.record("update: Install and restart hands over to the helper",
                  isinstance(answer, dict) and not answer.get("error"), answer)
    port, status = wait_for_app(app.data_root, 600, args.new_version)
    report.record("update: N+1 opens on the same data", status is not None,
                  {"version": (status or {}).get("build", {}).get("version")})
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline and journal(app.data_root).get("state") != "committed":
        time.sleep(2)
    final = journal(app.data_root)
    report.record("update: the new window confirms and the update commits",
                  final.get("state") == "committed", {"state": final.get("state"),
                                                      "reason": final.get("reason")})
    report.record("update: the installed package is N+1",
                  installed_version(args.lane) == args.new_version,
                  installed_version(args.lane))
    if port:
        after = saved(port)
        report.record("update: the saved work is unchanged", after == work,
                      {"before": len(work), "after": len(after)})


def journey_rollback(report: Report, app: App, args) -> None:
    app.env["REFINIX_QUALIFY_FAIL_START"] = args.new_version
    port, work = start_update(report, app, args, "rollback")
    if port is None:
        return
    app.ask("install", seconds=60)
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline and journal(app.data_root).get("state") not in (
            "rolled_back", "blocked"):
        time.sleep(2)
    final = journal(app.data_root)
    report.record("rollback: a new version that never confirms is undone by the helper",
                  final.get("state") == "rolled_back", {"state": final.get("state"),
                                                        "reason": final.get("reason")})
    report.record("rollback: the installed package is N again",
                  installed_version(args.lane) == args.old_version,
                  installed_version(args.lane))
    port, status = wait_for_app(app.data_root, 180, args.old_version)
    report.record("rollback: N reopens with the saved work unchanged",
                  status is not None and saved(port) == work,
                  {"reopened": status is not None})


# Where each install method is stopped: macOS after the app was swapped and
# before the new one opened; Windows while the setup runs inside its job (the
# helper's death ends the job, and the setup with it); Ubuntu after root
# installed the package and before the new version opened. Real dpkg kills in
# the middle of unpacking are qualified separately (scripts/qualify_deb.py).
PAUSE_AT = {"macos-arm64": "swapped", "windows-x64": "installer_running",
            "linux-x64": "swapped"}


def journey_interrupt(report: Report, app: App, args) -> None:
    import psutil
    from desktop import update_apply
    system = update_apply.System()
    app.env["REFINIX_QUALIFY_PAUSE_AT"] = PAUSE_AT[args.lane]
    app.env["REFINIX_QUALIFY_PAUSE_SECONDS"] = "120"
    port, work = start_update(report, app, args, "interrupt")
    if port is None:
        return
    app.ask("install", seconds=60)
    deadline, seen, killed = time.monotonic() + 600, None, []
    while time.monotonic() < deadline:
        seen = journal(app.data_root).get("state")
        if seen == PAUSE_AT[args.lane]:
            time.sleep(2)
            helper = journal(app.data_root).get("helper")
            if system.same(helper):
                try:
                    process = psutil.Process(helper["pid"])
                    process.kill()
                    process.wait(timeout=10)
                    killed.append(helper["pid"])
                except psutil.Error:
                    pass
            break
        if seen in ("committed", "rolled_back", "cancelled", "discarded", "blocked"):
            break
        time.sleep(0.2)
    report.record("interrupt: the helper was stopped while replacing the app", bool(killed),
                  {"state_when_stopped": seen, "helpers": killed,
                   "recorded_helper": journal(app.data_root).get("helper")})
    if not killed:
        return
    time.sleep(3)
    stop_everything(args.lane)
    app.env.pop("REFINIX_QUALIFY_PAUSE_AT")
    program = INSTALL[args.lane] / PROGRAM[args.lane]
    report.record("interrupt: the installed Refinix can still be opened",
                  program.exists(), {"program": str(program)})
    app.launch()       # the person opens Refinix again, the usual way
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline and journal(app.data_root).get("state") not in (
            "committed", "rolled_back", "cancelled", "discarded", "blocked"):
        time.sleep(2)
    final = journal(app.data_root).get("state")
    expected = {"committed": args.new_version, "rolled_back": args.old_version,
                "cancelled": args.old_version, "discarded": args.old_version}.get(final)
    report.record("interrupt: the next launch finishes or undoes it, never a mixed install",
                  expected is not None and installed_version(args.lane) == expected,
                  {"state": final, "installed": installed_version(args.lane),
                   "reason": journal(app.data_root).get("reason"),
                   "helper": journal(app.data_root).get("helper"),
                   "resume_count": journal(app.data_root).get("resume_count")})
    if expected is not None and args.lane in ("windows-x64", "linux-x64"):
        from desktop import install_check, update_windows
        extras = update_windows.INNO_EXTRAS if args.lane == "windows-x64" else frozenset()
        problem = install_check.completeness_problem(INSTALL[args.lane], expected, extras)
        report.record("interrupt: the restored or completed tree matches its file list",
                      problem is None, problem)
    port, status = wait_for_app(app.data_root, 300, expected)
    report.record("interrupt: the saved work is unchanged",
                  status is not None and saved(port) == work, {"reopened": status is not None})


JOURNEYS = {"update": journey_update, "rollback": journey_rollback,
            "interrupt": journey_interrupt}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lane", required=True, choices=sorted(INSTALL))
    parser.add_argument("--old", type=Path, required=True,
                        help="N: the ZIP (macOS), setup (Windows) or .deb (Ubuntu)")
    parser.add_argument("--new-bundle", type=Path, required=True)
    parser.add_argument("--old-version", required=True)
    parser.add_argument("--new-version", required=True)
    parser.add_argument("--journey", action="append", choices=sorted(JOURNEYS))
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    if os.environ.get("REFINIX_QUALIFY_DISPOSABLE") != "1":
        print("refused: only on a throwaway machine (REFINIX_QUALIFY_DISPOSABLE=1)",
              file=sys.stderr)
        return 2
    report = Report()
    # The real Ubuntu root step accepts requests only inside the caller's home.
    work = Path(tempfile.mkdtemp(prefix="refinix-journey-",
                                dir=Path.home() if args.lane == "linux-x64" else None))
    if args.lane == "linux-x64":
        allow_refinix_prompts_for_this_runner()
    for name in args.journey or list(JOURNEYS):
        try:
            stop_everything(args.lane)
            install_old(args.lane, args.old, work)
            report.record(f"{name}: N is installed the standard way",
                          installed_version(args.lane) == args.old_version,
                          installed_version(args.lane))
            data_root = (work / f"data-{name}").resolve()
            data_root.mkdir()
            app = App(args.lane, data_root,
                      {"REFINIX_DATA_ROOT": str(data_root),
                       "REFINIX_QUALIFY_TOKEN": secrets.token_hex(24)})
            JOURNEYS[name](report, app, args)
        except Exception as exc:                           # noqa: BLE001
            report.record(f"{name}: ran to the end", False, f"{type(exc).__name__}: {exc}")
        finally:
            stop_everything(args.lane)
    # Retain only synthetic-run logs/status, never the data store or signed bundles.
    for path in [work / "app.log", *work.glob("data-*/updates/install/*/helper.log"),
                 *work.glob("data-*/updates/install/*/helper.json")]:
        if path.is_file():
            target = args.report.parent / "journey-debug" / path.relative_to(work)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    record = {"kind": "update-journey", "lane": args.lane, "old": args.old_version,
              "new": args.new_version, "commit_tested": os.environ.get("GITHUB_SHA"),
              "host": {"platform": platform.platform(), "python": platform.python_version(),
                       "runner_image": "/".join(filter(None, (os.environ.get("ImageOS"),
                                                              os.environ.get("ImageVersion"))))},
              "checks": report.checks,
              "passed": bool(report.checks) and all(c["passed"] for c in report.checks)}
    args.report.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"{'all passed' if record['passed'] else 'FAILED'} — {args.report}")
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
