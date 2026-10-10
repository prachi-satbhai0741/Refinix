"""Inside the Code-validation sandbox: confine this process, check, then run the tests.

Started by `sandbox_local.py` as the only program of a transient systemd user
service (no sockets of any family, a system-call filter, no new privileges,
memory/process/CPU/time/file-size limits), with Ubuntu's own
`/usr/bin/python3`. Standard library only, so it never loads anything from
the workspace before it is confined.

In order, before any staged code runs:

1. close every inherited file descriptor except the configured stdin, stdout
   and stderr;
2. replace the environment with a minimal one (`HOME` is the workspace; no
   D-Bus, display, XDG or credential variables);
3. apply Landlock: read-only access to the interpreter, the standard library
   and the shared libraries it needs; read and write access to the workspace
   only; with ABI 6 and later, abstract Unix sockets and signals to processes
   outside the sandbox are scoped away as well;
4. check itself: creating a socket must fail, reading a path outside the
   allowed ones must fail, and the kernel must report the Landlock restriction;
5. hash the staged copies inside the workspace and compare them with the
   manifest written before the service started;
6. run exactly `python3 -m unittest` in the workspace and report.

If any step fails nothing is run, and the report says which control failed.
The report is one JSON line on standard output, written by this launcher
after the tests have exited, marked with the run's own code from the
manifest (which the tests cannot read); the tests' own output is size-capped
and read on its own thread, so the time limit holds even when the tests print
nothing. Signals are denied inside the service, so at the time limit the
launcher reports and exits, and systemd ends everything left in the service.
"""

from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import platform
import resource
import socket
import subprocess
import sys
import threading

# Landlock (include/uapi/linux/landlock.h).
SYS = {"x86_64": {"create": 444, "add_rule": 445, "restrict": 446},
       "aarch64": {"create": 444, "add_rule": 445, "restrict": 446}}
CREATE_RULESET_VERSION = 1 << 0
RULE_PATH_BENEATH = 1
FS = {"EXECUTE": 1 << 0, "WRITE_FILE": 1 << 1, "READ_FILE": 1 << 2, "READ_DIR": 1 << 3,
      "REMOVE_DIR": 1 << 4, "REMOVE_FILE": 1 << 5, "MAKE_CHAR": 1 << 6,
      "MAKE_DIR": 1 << 7, "MAKE_REG": 1 << 8, "MAKE_SOCK": 1 << 9, "MAKE_FIFO": 1 << 10,
      "MAKE_BLOCK": 1 << 11, "MAKE_SYM": 1 << 12, "REFER": 1 << 13, "TRUNCATE": 1 << 14,
      "IOCTL_DEV": 1 << 15}
SCOPE_ABSTRACT_UNIX_SOCKET, SCOPE_SIGNAL = 1 << 0, 1 << 1
PR_SET_NO_NEW_PRIVS = 38
READ_ONLY = ("EXECUTE", "READ_FILE", "READ_DIR")
OUTPUT_LIMIT = 64 * 1024
COMMAND = ("-m", "unittest")


class Refused(RuntimeError):
    def __init__(self, control: str, detail: str):
        super().__init__(detail)
        self.control = control


def _fs_mask(abi: int) -> int:
    names = list(FS)
    if abi < 2:
        names.remove("REFER")
    if abi < 3:
        names.remove("TRUNCATE")
    if abi < 5:
        names.remove("IOCTL_DEV")
    return sum(FS[name] for name in names)


class _RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64),
                ("handled_access_net", ctypes.c_uint64),
                ("scoped", ctypes.c_uint64)]


class _PathBeneath(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


def close_inherited(keep=(0, 1, 2)) -> None:
    highest = max(keep) + 1
    try:
        os.closerange(highest, resource.getrlimit(resource.RLIMIT_NOFILE)[0])
    except (OSError, ValueError):
        os.closerange(highest, 65536)


def clean_environment(workspace: str) -> dict:
    return {"HOME": workspace, "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0", "TMPDIR": os.path.join(workspace, ".tmp")}


def landlock(read_only: list[str], read_write: list[str]) -> int:
    """Confine this process and its children; returns the ABI used."""
    numbers = SYS.get(platform.machine())
    if numbers is None:
        raise Refused("Landlock", f"no Landlock system calls known for {platform.machine()}")
    libc = ctypes.CDLL(None, use_errno=True)
    abi = libc.syscall(numbers["create"], None, ctypes.c_size_t(0),
                       ctypes.c_uint32(CREATE_RULESET_VERSION))
    if abi < 1:
        raise Refused("Landlock", "the kernel has no Landlock support enabled")
    handled = _fs_mask(abi)
    attr = _RulesetAttr(handled, 0, (SCOPE_ABSTRACT_UNIX_SOCKET | SCOPE_SIGNAL)
                        if abi >= 6 else 0)
    size = ctypes.sizeof(_RulesetAttr) if abi >= 6 else 8 if abi < 4 else 16
    ruleset = libc.syscall(numbers["create"], ctypes.byref(attr), ctypes.c_size_t(size),
                           ctypes.c_uint32(0))
    if ruleset < 0:
        raise Refused("Landlock", f"creating a ruleset failed (errno {ctypes.get_errno()})")
    try:
        for paths, allowed in ((read_only, sum(FS[n] for n in READ_ONLY)),
                               (read_write, handled)):
            for path in paths:
                try:
                    fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
                except OSError:
                    continue                      # an absent library folder is fine
                try:
                    rights = allowed
                    if not os.path.isdir(path):
                        # A file rule may only carry file rights.
                        rights &= (FS["EXECUTE"] | FS["READ_FILE"] | FS["WRITE_FILE"]
                                   | FS["TRUNCATE"])
                    rule = _PathBeneath(rights & handled, fd)
                    if libc.syscall(numbers["add_rule"], ruleset,
                                    ctypes.c_int(RULE_PATH_BENEATH), ctypes.byref(rule),
                                    ctypes.c_uint32(0)) != 0:
                        raise Refused("Landlock", f"adding {path} failed "
                                                  f"(errno {ctypes.get_errno()})")
                finally:
                    os.close(fd)
        if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
            raise Refused("no new privileges", "prctl(PR_SET_NO_NEW_PRIVS) failed")
        if libc.syscall(numbers["restrict"], ruleset, ctypes.c_uint32(0)) != 0:
            raise Refused("Landlock", f"restricting failed (errno {ctypes.get_errno()})")
    finally:
        os.close(ruleset)
    return abi


def self_check(workspace: str, outside: str) -> list[str]:
    """Each confinement this launcher relies on, observed from the inside."""
    observed = []
    for family in (socket.AF_INET, socket.AF_INET6, socket.AF_UNIX):
        try:
            probe = socket.socket(family, socket.SOCK_STREAM)
        except OSError as exc:
            if exc.errno not in (errno.EAFNOSUPPORT, errno.EPERM, errno.EACCES):
                raise Refused("no sockets", f"socket({family}) failed oddly: {exc}") from exc
            continue
        probe.close()
        raise Refused("no sockets", f"a socket of family {int(family)} could be created")
    observed.append("no sockets")
    try:
        with open(outside, "rb"):
            pass
    except PermissionError:
        observed.append("Landlock")
    except OSError as exc:
        raise Refused("Landlock", f"the outside check path is unusable: {exc}") from exc
    else:
        raise Refused("Landlock", f"{outside} could be read from inside the sandbox")
    # The system-call filter: signalling (even to itself) and io_uring fail.
    try:
        os.kill(os.getpid(), 0)
    except PermissionError:
        observed.append("no signals")
    else:
        raise Refused("system-call filter", "kill() is allowed inside the sandbox")
    libc = ctypes.CDLL(None, use_errno=True)
    number = {"x86_64": 425, "aarch64": 425}.get(platform.machine())
    if number is not None:
        params = ctypes.create_string_buffer(120)
        if libc.syscall(number, ctypes.c_uint32(1), params) >= 0:
            raise Refused("system-call filter", "io_uring_setup() is allowed")
        observed.append("no io_uring")
    marker = os.path.join(workspace, ".refinix-write-check")
    with open(marker, "w", encoding="utf-8") as handle:
        handle.write("ok")
    os.unlink(marker)
    observed.append("workspace writable")
    return observed


def check_limits(expected: dict) -> list[str]:
    """The cgroup this process runs in carries the requested limits."""
    try:
        with open("/proc/self/cgroup", encoding="utf-8") as handle:
            relative = handle.read().strip().split("::", 1)[1]
    except (OSError, IndexError) as exc:
        raise Refused("resource limits", "this process's cgroup cannot be read") from exc
    folder = "/sys/fs/cgroup" + relative
    found = []
    for name, wanted in expected.items():
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as handle:
                value = handle.read().strip()
        except OSError as exc:
            raise Refused("resource limits", f"{name} cannot be read") from exc
        if value != str(wanted):
            raise Refused("resource limits", f"{name} is {value}, not {wanted}")
        found.append(name)
    return found


def check_inputs(workspace: str, manifest: dict) -> str:
    """The staged copies are exactly what was reviewed; returns their digest."""
    entries = []
    for item in manifest["files"]:
        path = os.path.join(workspace, item["path"])
        if os.path.islink(path) or not os.path.isfile(path):
            raise Refused("inputs", f"{item['path']} is not a staged file")
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != item["sha256"]:
            raise Refused("inputs", f"{item['path']} changed after it was staged")
        entries.append([item["path"], item["sha256"]])
    return hashlib.sha256(json.dumps(sorted(entries)).encode()).hexdigest()


def run_tests(workspace: str, environment: dict, seconds: int) -> dict:
    os.makedirs(environment["TMPDIR"], exist_ok=True)
    process = subprocess.Popen([sys.executable, "-I", *COMMAND], cwd=workspace,
                               env=environment, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               close_fds=True)
    output, state = bytearray(), {"truncated": False, "tail": b""}

    def read():
        try:
            for block in iter(lambda: process.stdout.read(8192), b""):
                room = OUTPUT_LIMIT - len(output)
                if room > 0:
                    output.extend(block[:room])
                if len(block) > room:
                    state["truncated"] = True
                state["tail"] = (state["tail"] + block)[-16384:]
        except (OSError, ValueError):
            pass
    # A daemon thread: a descendant still holding the pipe at the time limit
    # must not keep this launcher (and so the service) alive.
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    timed_out = False
    try:
        status = process.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        # kill() is denied by the service's system-call filter; ending this
        # launcher ends the service, and systemd stops what is left in it.
        status, timed_out = None, True
    reader.join(2.0)
    truncated = state["truncated"]
    text = bytes(output).decode("utf-8", errors="replace")
    tests_run = None
    for line in state["tail"].decode("utf-8", errors="replace").splitlines():
        if line.startswith("Ran ") and " test" in line:
            try:
                tests_run = int(line.split()[1])
            except (IndexError, ValueError):
                pass
    return {"exit_status": status, "tests_run": tests_run, "output": text,
            "output_truncated": truncated, "timed_out": timed_out}


def main(argv: list[str]) -> int:
    report = {"command": [os.path.basename(sys.executable), *COMMAND], "ran": False}
    manifest = None
    try:
        if len(argv) != 2:
            raise Refused("usage", "launcher <workspace> <manifest>")
        workspace, manifest_path = os.path.realpath(argv[0]), argv[1]
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        close_inherited()
        environment = clean_environment(workspace)
        os.environ.clear()
        os.environ.update(environment)
        base = os.path.realpath(sys.base_prefix)
        read_only = [os.path.realpath(sys.executable), base, "/usr/lib", "/lib", "/lib64",
                     "/usr/lib64", "/etc/ld.so.cache", "/usr/share/zoneinfo",
                     os.path.dirname(os.path.realpath(__file__))]
        read_only += ["/dev/urandom", "/proc/self/cgroup", "/sys/fs/cgroup"]
        abi = landlock(read_only, [workspace, "/dev/null"])
        report["landlock_abi"] = abi
        report["controls"] = self_check(workspace, manifest.get("outside_probe",
                                                                "/etc/hostname"))
        report["limits"] = check_limits(manifest.get("cgroup_limits") or {})
        report["inputs_sha256"] = check_inputs(workspace, manifest)
        report.update(run_tests(workspace, environment, int(manifest.get("seconds", 300))))
        report["ran"] = True
        code = 0
    except Refused as exc:
        report.update(refused=exc.control, error=str(exc))
        code = 3
    except Exception as exc:                                # noqa: BLE001
        report.update(refused="launcher", error=f"{type(exc).__name__}: {exc}")
        code = 3
    code_word = str(manifest.get("report_code") or "") if isinstance(manifest, dict) else ""
    # Keep bounded user output outside the closing record, which the parent retains separately.
    sys.stdout.write(report.pop("output", ""))
    sys.stdout.write(f"\nREFINIX-SANDBOX-REPORT {code_word} "
                     + json.dumps(report, sort_keys=True) + "\n")
    sys.stdout.flush()
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
