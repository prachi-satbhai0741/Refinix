#!/usr/bin/env python3
"""Start a packaged Refinix on scratch data only, and prove that is what ran.

The packaged entry point (desktop/refinix.py) takes no options. The only
supported way to point it at other data is an absolute `REFINIX_DATA_ROOT`
(backend/coordinator/paths.py). This check:

1. refuses unless the scratch folder is absolute and new or empty;
2. records the metadata (path, size, modification time — never contents) of
   any `--watch` folder, for example the person's real data folder;
3. confirms that the old development options are now refused by the
   packaged entry before anything opens (`--no-window`);
4. starts the real packaged program with no options and the scratch root,
   waits for its loopback coordinator (the port it records in its instance
   lock beside the scratch database), and reads `/v1/status`: the data root
   must be the scratch folder, the process the one started, and the build the
   expected version;
5. stops it, and checks that the watched folders are exactly as before.

    python scripts/qualify_package_launch.py --program <packaged executable> \\
        --data-root <new absolute folder> [--watch ~/.aegisforge] \\
        [--expect-version 0.1.0-beta.1] [--report launch.json]

On Linux the caller supplies a display (xvfb-run). Exit status 0 only when
every check passed. The result is a list of checks in the shape
scripts/qualification_record.py records.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

CHECK = "packaged app starts on scratch data only"
LOCK_NAME = "desktop.lock"          # backend/coordinator/ownership.py
DATABASE = "coordinator.sqlite3"
# desktop/lifecycle.py PORT_CANDIDATES: where the coordinator may listen.
PORTS = tuple(range(8770, 8778))


def snapshot(folder: Path) -> dict | None:
    """Metadata of every entry under `folder`; None when it does not exist."""
    folder = Path(folder)
    if not folder.exists():
        return None
    seen = {}
    for path in sorted(folder.rglob("*")):
        try:
            info = path.lstat()
        except OSError:
            continue
        seen[str(path.relative_to(folder))] = [info.st_size, info.st_mtime_ns, info.st_mode]
    return seen


def _status(port: int, timeout: float = 3.0) -> dict | None:
    request = urllib.request.Request(f"http://127.0.0.1:{port}/v1/status",
                                     headers={"Host": f"127.0.0.1:{port}"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            return json.load(response)
    except (OSError, ValueError):
        return None


def _find(root: Path) -> tuple[int | None, dict | None]:
    """The port and status of the coordinator serving `root`, if it is up.

    The instance lock beside the database records the port, but Windows
    locks that file's bytes against reading, so the candidate ports are
    also asked; only a status naming this exact data root counts.
    """
    ports = list(PORTS)
    try:
        data = json.loads((root / LOCK_NAME).read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("port"), int):
            ports.insert(0, data["port"])
    except (OSError, ValueError):
        pass
    for port in ports:
        status = _status(port, timeout=1.5)
        reported = ((status or {}).get("process") or {}).get("data_root")
        if reported and Path(reported).resolve() == root:
            return port, status
    return None, None


def _stop(process: subprocess.Popen, grace: float = 20.0) -> int | None:
    """Stop the program and everything it started (its own process group)."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T"], capture_output=True,
                       check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except OSError:
            pass
    try:
        return process.wait(grace)
    except subprocess.TimeoutExpired:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, check=False)
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
        return process.wait(10)


def launch_check(program: Path, data_root: Path, *, watch=(), expect_version=None,
                 environ=None, timeout: float = 180.0, prefix=(), owner=None) -> dict:
    """One check record: {"check", "passed", "observed"}.

    `prefix` runs the program through another command (for example
    `runuser -u <account> -- env REFINIX_DATA_ROOT=<root> xvfb-run -a`);
    `owner` is the (uid, gid) the scratch folder is given to before launch.
    """
    observed: dict = {"program": str(program), "data_root": str(data_root)}
    data_root = Path(data_root)
    problems = []
    if not data_root.is_absolute():
        return {"check": CHECK, "passed": False,
                "observed": {**observed, "problem": "the scratch folder is not absolute"}}
    if data_root.exists() and any(data_root.iterdir()):
        return {"check": CHECK, "passed": False,
                "observed": {**observed, "problem": "the scratch folder is not empty"}}
    data_root.mkdir(parents=True, exist_ok=True)
    if owner is not None:
        os.chown(data_root, *owner)
    real_root = data_root.resolve()
    before = {str(w): snapshot(Path(w)) for w in watch}
    env = dict(os.environ if environ is None else environ)
    env["REFINIX_DATA_ROOT"] = str(real_root)
    env.pop("REFINIX_STATE", None)

    refused = subprocess.run([*prefix, str(program), "--no-window"], env=env,
                             capture_output=True, text=True, timeout=60, check=False)
    observed["old_option_exit"] = refused.returncode
    if refused.returncode == 0:
        problems.append("the packaged entry accepted --no-window")
    if any(real_root.iterdir()):
        problems.append("the refused launch wrote into the scratch folder")

    # Output goes to a file, never a pipe: a leftover child holding a pipe open
    # could otherwise stall this check after the program has stopped.
    log = tempfile.TemporaryFile()
    process = subprocess.Popen([*prefix, str(program)], env=env, stdout=log,
                               stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                               **({} if sys.platform == "win32"
                                  else {"start_new_session": True}))
    status, port = None, None
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline and process.poll() is None:
            port, status = _find(real_root)
            if status:
                break
            time.sleep(1)
        observed["port"] = port
        if status is None:
            problems.append("no coordinator on loopback reported the scratch folder "
                            "as its data root" if process.poll() is None
                            else f"the program exited early ({process.returncode})")
        else:
            reported = (status.get("process") or {})
            observed["reported_data_root"] = reported.get("data_root")
            observed["reported_pid"] = reported.get("pid")
            observed["version"] = (status.get("build") or {}).get("version")
            if Path(reported.get("data_root") or "").resolve() != real_root:
                problems.append(f"it used {reported.get('data_root')!r}, not the scratch "
                                "folder")
            if expect_version and observed["version"] != expect_version:
                problems.append(f"it reports version {observed['version']!r}, not "
                                f"{expect_version}")
    finally:
        observed["exit"] = _stop(process)
        log.seek(0)
        observed["output_tail"] = log.read().decode("utf-8", errors="replace")[-1500:]
        log.close()
    if not (real_root / DATABASE).is_file():
        problems.append("no workspace database was created in the scratch folder")
    after = {str(w): snapshot(Path(w)) for w in watch}
    changed = [w for w in before if before[w] != after[w]]
    observed["watched"] = {w: ("absent" if before[w] is None else f"{len(before[w])} entries")
                           for w in before}
    if changed:
        problems.append(f"watched folders changed: {changed}")
    observed["problems"] = problems
    return {"check": CHECK, "passed": not problems, "observed": observed}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--program", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--watch", type=Path, action="append", default=[])
    parser.add_argument("--expect-version")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args(argv)
    result = launch_check(args.program, args.data_root, watch=args.watch,
                          expect_version=args.expect_version, timeout=args.timeout)
    text = json.dumps(result, indent=2)
    if args.report:
        args.report.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
