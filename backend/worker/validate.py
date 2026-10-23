"""AF-011 validation runner — the process inside the restricted Job Pod.

It does five things and has no way to do a sixth:

1. copy the attempt's original files out of the read-only package;
2. verify every original digest;
3. overwrite exactly the files the reviewed proposal replaces, and verify
   every replacement digest;
4. run **one command that came from the approved plan**, with `argv`, a
   stripped environment, a working directory inside the temporary workspace
   and hard resource limits;
5. print one strict JSON result and exit with the command's status.

**The command is configuration, never model output.** It is compared against
`ALLOWED_COMMANDS` before it runs, so a plan carrying anything else fails
without executing. There is no shell: `subprocess.run` receives a list and
`shell=True` appears nowhere, so `;`, `|`, `$(…)` and `&&` are characters in an
argument rather than syntax.

**No patch is applied here.** The reviewed proposal already contains complete
replacement contents, so a diff applicator — with its fuzz, its offsets and its
partial-hunk failure modes — would be a second implementation of something the
coordinator already did exactly.

**Nothing here can reach the network.** The Job has default-deny egress with no
exception, no ServiceAccount token, a read-only root filesystem and no
credentials mounted. This module also opens no socket, which is the smaller of
the two guarantees.

Run inside the Job as:

    python -m backend.worker.validate /package /workspace

The package is mounted read-only and holds `files/plan.json`,
`files/original/**` and `files/replacement/**`.

Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    import resource
except ImportError:  # Windows has no POSIX per-process rlimit surface.
    resource = None

# The only commands a plan may name. C07 approved exactly one; adding to this
# table is a reviewed decision, not something a plan or a model can do.
ALLOWED_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("python3", "-m", "unittest"),
    ("python3", "-m", "unittest", "discover"),
)

MAX_OUTPUT_BYTES = 64 * 1024
MAX_FILES = 64
MAX_FILE_BYTES = 256 * 1024
DEFAULT_RUNTIME_SECONDS = 120
DEFAULT_CPU_SECONDS = 60
DEFAULT_ADDRESS_SPACE = 1024 * 1024 * 1024
DEFAULT_PROCESSES = 32

RESULT_VERSION = "af-011-validation-result-v1"

# The package's two halves. `original/` becomes the workspace; `replacement/`
# overwrites exactly the files the reviewed proposal changed. Keeping them
# apart means the runner never has to guess which of two files is which.
ORIGINAL_DIR = "original"
REPLACEMENT_DIR = "replacement"
PLAN_NAME = "plan.json"


class PlanError(Exception):
    """The plan could not be carried out. Never a pass."""


def load_plan(package: Path) -> dict:
    """Read and check the plan, which travelled INSIDE the package.

    Putting it in the package rather than writing it alongside means the
    command and every digest below are covered by the package digest the
    coordinator computed and the worker verified. Nothing between the two can
    change what will run without changing that digest.
    """
    try:
        plan = json.loads((package / "files" / "plan.json").read_text())
    except (OSError, ValueError) as exc:
        raise PlanError("the validation plan could not be read") from exc
    if not isinstance(plan, dict):
        raise PlanError("the validation plan was not an object")
    command = plan.get("command")
    if not isinstance(command, list) or not all(isinstance(part, str)
                                                for part in command):
        raise PlanError("the validation plan has no command")
    if tuple(command) not in ALLOWED_COMMANDS:
        # The whole point of the table: a command nobody approved never runs,
        # whatever produced it.
        raise PlanError("the validation plan named a command that is not approved")
    replacements = plan.get("replacements")
    if not isinstance(replacements, list) or len(replacements) > MAX_FILES:
        raise PlanError("the validation plan has no usable replacement list")
    for item in replacements:
        if not isinstance(item, dict) or set(item) != {"path", "base_sha256",
                                                       "after_sha256"}:
            raise PlanError("a replacement entry was not in the expected shape")
    minimum_tests = plan.get("minimum_tests", 1)
    if not isinstance(minimum_tests, int) or isinstance(minimum_tests, bool) \
            or minimum_tests < 1 or minimum_tests > 10_000:
        raise PlanError("the validation plan has no usable minimum test count")
    return plan


def _safe_relative(root: Path, relative: str) -> Path:
    """Resolve one relative path strictly inside `root`."""
    if not relative or relative.startswith("/") or "\\" in relative:
        raise PlanError("a plan path was not relative")
    candidate = (root / relative)
    try:
        resolved = candidate.resolve()
        base = root.resolve()
    except OSError as exc:
        raise PlanError("a plan path could not be resolved") from exc
    if resolved != base and base not in resolved.parents:
        raise PlanError("a plan path escaped the workspace")
    return candidate


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(package: Path, workspace: Path, plan: dict) -> list[str]:
    """Build the workspace from the read-only package, verifying as it goes."""
    source = package / "files" / ORIGINAL_DIR
    if not source.is_dir():
        raise PlanError("the package holds no original files")
    workspace.mkdir(parents=True, exist_ok=True)
    copied = 0
    for item in sorted(source.rglob("*")):
        if item.is_symlink():
            # Nothing in the package format can create one; refusing here means
            # a link that arrived some other way still never gets followed.
            raise PlanError("the package contains a symbolic link")
        if not item.is_file():
            continue
        copied += 1
        if copied > MAX_FILES:
            raise PlanError("the package holds more files than validation copies")
        if item.stat().st_size > MAX_FILE_BYTES:
            raise PlanError("a package file is larger than validation copies")
        target = _safe_relative(workspace, str(item.relative_to(source)))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(item, target)

    applied: list[str] = []
    after_root = package / "files" / REPLACEMENT_DIR
    for entry in plan["replacements"]:
        target = _safe_relative(workspace, entry["path"])
        if not target.is_file():
            raise PlanError("a replaced file was not in the package")
        # The base digest proves the replacement is being applied to the same
        # bytes the proposal was reviewed against.
        if _digest(target) != entry["base_sha256"]:
            raise PlanError("a package file did not match its recorded base digest")
        replacement = _safe_relative(after_root, entry["path"])
        if not replacement.is_file():
            raise PlanError("a replacement file was missing from the plan")
        shutil.copyfile(replacement, target)
        if _digest(target) != entry["after_sha256"]:
            raise PlanError("a replacement did not match its recorded digest")
        applied.append(entry["path"])
    return applied


def _limits(plan: dict):
    """Apply per-process ceilings in the child, before `exec`.

    These are belt to the Pod's braces: the container already has CPU, memory
    and PID limits. Setting them here as well bounds a runaway before the
    kubelet has to, and makes the same runner safe to exercise outside a Pod.
    """
    if resource is None:
        raise PlanError(
            "the qualified POSIX resource-limit sandbox is unavailable on "
            "this platform")
    cpu = int(plan.get("cpu_seconds") or DEFAULT_CPU_SECONDS)
    address = int(plan.get("address_space_bytes") or DEFAULT_ADDRESS_SPACE)
    processes = int(plan.get("processes") or DEFAULT_PROCESSES)
    output = int(plan.get("output_bytes") or MAX_OUTPUT_BYTES)

    wanted = [
        ("RLIMIT_CPU", (cpu, cpu)),
        ("RLIMIT_AS", (address, address)),
        ("RLIMIT_NPROC", (processes, processes)),
        # A file-size ceiling, so a test that writes forever stops.
        ("RLIMIT_FSIZE", (max(output, MAX_OUTPUT_BYTES) * 16,) * 2),
        ("RLIMIT_CORE", (0, 0)),
    ]

    def apply():                                          # pragma: no cover
        # Each limit is set on its own. A host that refuses one — RLIMIT_AS
        # and RLIMIT_NPROC are not settable everywhere — must not abort the
        # run in `preexec_fn`, which would report a sandbox failure for a
        # portability difference. The Pod's cgroup limits are the enforced
        # boundary either way; these narrow the process further where they can.
        for name, values in wanted:
            limit = getattr(resource, name, None)
            if limit is None:
                continue
            try:
                resource.setrlimit(limit, values)
            except (ValueError, OSError, resource.error):
                continue

    return apply


def run(package: Path, workspace: Path, *, runner=subprocess.run) -> dict:
    """Prepare, run the approved command once, and report exactly what happened."""
    plan = load_plan(package)
    applied = prepare(package, workspace, plan)
    command = list(plan["command"])
    timeout = int(plan.get("runtime_seconds") or DEFAULT_RUNTIME_SECONDS)
    cap = int(plan.get("output_bytes") or MAX_OUTPUT_BYTES)

    # A stripped environment: no inherited credentials, no proxy, no PYTHONPATH
    # that could import something from outside the workspace.
    environment = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(workspace),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8",
    }
    started = _now()
    begin = time.monotonic()
    timed_out = False
    try:
        completed = runner(
            command, cwd=str(workspace), env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, preexec_fn=_limits(plan), close_fds=True,
            shell=False)
        stdout, stderr = completed.stdout or b"", completed.stderr or b""
        status = completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout or b""
        stderr = (exc.stderr or b"") + b"\nvalidation exceeded its time limit"
        status = 124
    except (OSError, ValueError) as exc:
        stdout, stderr = b"", f"validation could not start: {type(exc).__name__}".encode()
        status = 126
    runtime_ms = int((time.monotonic() - begin) * 1000)
    summary = re.search(
        r"(?:^|\n)Ran\s+(\d+)\s+tests?\s+in\s+[0-9.]+s\n\n"
        r"OK(?:\s+\([^\n]*\))?\n?\Z",
        stderr.decode("utf-8", "replace")) if status == 0 else None
    tests_run = int(summary.group(1)) if summary else 0

    result = {
        "result_version": RESULT_VERSION,
        "command": command,
        "exit_status": status,
        "timed_out": timed_out,
        "stdout": _cap(stdout, cap),
        "stderr": _cap(stderr, cap),
        "stdout_truncated": len(stdout) > cap,
        "stderr_truncated": len(stderr) > cap,
        "replaced": applied,
        "started_at": started,
        "finished_at": _now(),
        "runtime_ms": runtime_ms,
        "tests_run": tests_run,
        # A clean exit with zero discovered tests is not evidence that the
        # reviewed change works. The approved plan sets the minimum.
        "passed": (status == 0 and not timed_out
                   and tests_run >= plan.get("minimum_tests", 1)),
    }
    result["result_sha256"] = result_digest(result)
    return result


def result_digest(result: dict) -> str:
    """Binds a result to its own content, so a truncated or edited copy shows."""
    material = {key: value for key, value in sorted(result.items())
                if key != "result_sha256"}
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False).encode("utf-8")).hexdigest()


def _cap(data: bytes, limit: int) -> str:
    return data[:limit].decode("utf-8", "replace")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        sys.stderr.write("usage: python -m backend.worker.validate <package> <workspace>\n")
        return 2
    package, workspace = Path(argv[0]), Path(argv[1])
    try:
        result = run(package, workspace)
    except PlanError as exc:
        failure = {"result_version": RESULT_VERSION, "passed": False,
                   "exit_status": 125, "error": str(exc),
                   "finished_at": _now()}
        failure["result_sha256"] = result_digest(failure)
        sys.stdout.write(json.dumps(failure, sort_keys=True) + "\n")
        return 125
    # One line, so the executor can read it out of bounded Pod logs.
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    return 0 if result["passed"] else 1


if __name__ == "__main__":                                    # pragma: no cover
    raise SystemExit(main())
