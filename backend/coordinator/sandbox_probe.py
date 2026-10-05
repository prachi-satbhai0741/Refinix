"""Which of the Code-validation sandbox's required controls this computer has.

Read-only: it reads `/proc`, `/sys` and `systemctl --version`, and asks the
kernel for its Landlock ABI. It starts nothing, installs nothing and changes
no setting.

Generated code is never run on this computer in this build, whatever this
reports. The approved Ubuntu profile (a systemd user service with seccomp,
Landlock and delegated cgroup limits) also needs a hard limit on the total
bytes and files its temporary workspace may use, and no mechanism for that
limit has been qualified without a host change. `available` is therefore
always False here, and the result names each control that is present or
missing, so a person testing on Ubuntu sees the computer's actual state
instead of a single "not available".

Windows (AppContainer and Jobs) is the later candidate; macOS validation is
not offered in Beta.
"""

from __future__ import annotations

import os
import platform as _platform
import subprocess
import sys

REQUIRED_CGROUP_CONTROLLERS = ("memory", "pids", "cpu")
MIN_SYSTEMD = 255                  # RestrictAddressFamilies=none, delegated limits
MIN_LANDLOCK_ABI = 1

NOT_OFFERED = {
    "darwin": ("Code validation in a sandbox is not offered on macOS in this build. "
               "Proposals, review and the labelled local Apply/Undo still work."),
    "win32": ("Code validation in a sandbox is not available on Windows yet. "
              "Proposals, review and the labelled local Apply/Undo still work."),
}
STORAGE_GAP = ("No hard limit on the sandbox's total temporary disk use (bytes and "
               "files) is in place yet. Until one is qualified, generated code is "
               "not run on this computer.")


def _read(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return None


def _systemd_version(run=subprocess.run) -> int | None:
    try:
        first = run(["systemctl", "--version"], capture_output=True, text=True,
                    timeout=5, check=False).stdout.splitlines()[0]
        return int(first.split()[1])
    except (OSError, subprocess.SubprocessError, IndexError, ValueError):
        return None


def _landlock_abi() -> int | None:
    """The kernel's Landlock ABI version, or None when it is absent or disabled."""
    if not sys.platform.startswith("linux"):
        return None
    try:
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        number = {"x86_64": 444, "aarch64": 444}.get(_platform.machine())
        if number is None:
            return None
        # landlock_create_ruleset(NULL, 0, LANDLOCK_CREATE_RULESET_VERSION)
        abi = libc.syscall(number, None, ctypes.c_size_t(0), ctypes.c_uint32(1))
    except (OSError, AttributeError):
        return None
    return abi if abi > 0 else None


def probe(*, platform: str | None = None, read=_read, exists=os.path.exists,
          systemd_version=None, landlock_abi=None, uid: int | None = None,
          environ=None) -> dict:
    """The required controls and whether each was observed here."""
    platform = sys.platform if platform is None else platform
    if not platform.startswith("linux"):
        key = "win32" if platform == "win32" else "darwin"
        return {"available": False, "profile": None, "controls": [],
                "detail": NOT_OFFERED[key]}
    environ = os.environ if environ is None else environ
    uid = os.getuid() if uid is None else uid
    systemd = systemd_version() if systemd_version else _systemd_version()
    abi = landlock_abi() if landlock_abi else _landlock_abi()
    status = read("/proc/self/status") or ""
    seccomp = any(line.startswith("Seccomp:") for line in status.splitlines())
    manager = f"/sys/fs/cgroup/user.slice/user-{uid}.slice/user@{uid}.service"
    delegated = (read(f"{manager}/cgroup.subtree_control") or "").split()
    io_uring = read("/proc/sys/kernel/io_uring_disabled")
    runtime_dir = environ.get("XDG_RUNTIME_DIR") or f"/run/user/{uid}"
    user_bus = exists(f"{runtime_dir}/systemd/private")

    def control(name, ok, observed, detail):
        return {"name": name, "ok": bool(ok), "observed": observed, "detail": detail}

    controls = [
        control("systemd user manager", user_bus, user_bus,
                "runs the sandbox as a transient user service"),
        control(f"systemd {MIN_SYSTEMD} or later", systemd is not None and systemd >= MIN_SYSTEMD,
                systemd, "address-family, syscall and delegated resource controls"),
        control("seccomp", seccomp, seccomp, "system-call filtering, including io_uring"),
        control("Landlock", abi is not None and abi >= MIN_LANDLOCK_ABI, abi,
                "file access limited to the interpreter, inputs and workspace"),
        control("delegated memory, process and CPU limits",
                all(c in delegated for c in REQUIRED_CGROUP_CONTROLLERS), delegated,
                "aggregate memory, process count and CPU for the whole sandbox"),
        control("aggregate temporary-storage limit", False, None, STORAGE_GAP),
    ]
    missing = [c["name"] for c in controls if not c["ok"]]
    return {"available": False, "profile": "ubuntu-systemd-landlock",
            "controls": controls, "missing": missing,
            "io_uring_disabled_sysctl": io_uring,
            "kernel": _platform.release(),
            "detail": ("Code validation in a sandbox is not available on this computer "
                       "yet. Missing: " + ", ".join(missing) + ". Proposals, review "
                       "and the labelled local Apply/Undo still work.")}
