"""Code validation on this Ubuntu computer: a transient systemd user service.

Profile `ubuntu-systemd-landlock`. Generated code runs only when every control
below is in force; otherwise nothing runs and the reason is reported. There
is never a fallback to running code directly on the computer.

    storage     a fixed-size ext4 image (bytes and file count capped by the
                filesystem itself), mounted nosuid,nodev through udisks
                (`udisksctl --no-user-interaction`) or, where udisks would ask
                for a password, through `fuse2fs`;
    service     `systemd-run --user` with no socket address families, a
                system-call filter (no sockets, signals, tracing, io_uring,
                BPF, keyrings, namespaces or mounts), no new privileges, and
                memory, process, CPU, run-time, file-size and descriptor limits;
    launcher    Ubuntu's `/usr/bin/python3` runs `sandbox_launcher.py`, which
                closes inherited descriptors, cleans the environment, applies
                Landlock and checks every control from the inside before the
                tests run, and hashes the staged copies first.

Every run is journalled. A run's record is dropped only once its service is
confirmed stopped and its storage confirmed detached; otherwise the record is
kept with what failed, cleanup is retried at the next start and before the
next run, and no new validation starts while a workspace is still mounted.

Cancel and the deadline do not wait for the tests to print anything: output is
read on its own thread while a short loop watches for Cancel and the deadline,
then stops the whole service. A pass needs the launcher's closing report,
marked with this run's own code, and the service to have ended normally.

The profile is **provisional** until the device qualification on a real
Ubuntu 24.04 desktop passes (plan v4.3 W2.3); results say so.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.coordinator import sandbox_probe

PROFILE = "ubuntu-systemd-landlock"
PROFILE_VERSION = 1
QUALIFICATION = "provisional"          # until the Ubuntu device check passes
PYTHON = "/usr/bin/python3"
IMAGE_BYTES = 256 * 1024 ** 2
IMAGE_INODES = 4096
DEADLINE_SECONDS = 300
OUTPUT_LIMIT = 128 * 1024
LIMITS = {"MemoryMax": "1073741824", "MemorySwapMax": "0", "TasksMax": "64",
          "CPUQuota": "100%", "RuntimeMaxSec": str(DEADLINE_SECONDS + 30),
          "LimitFSIZE": str(64 * 1024 ** 2), "LimitNOFILE": "256", "LimitCORE": "0"}
# What the launcher reads back from its own cgroup.
CGROUP_LIMITS = {"memory.max": LIMITS["MemoryMax"], "memory.swap.max": "0",
                 "pids.max": LIMITS["TasksMax"]}
DENIED_CALLS = ("socket socketpair kill tkill tgkill pidfd_open pidfd_send_signal "
                "pidfd_getfd ptrace process_vm_readv process_vm_writev io_uring_setup "
                "io_uring_enter io_uring_register bpf keyctl add_key request_key unshare "
                "setns mount umount2 pivot_root chroot open_tree move_mount fsopen fsmount "
                "fsconfig fspick perf_event_open userfaultfd")
PROPERTIES = [
    "RestrictAddressFamilies=none",
    "SystemCallFilter=@system-service",
    f"SystemCallFilter=~{DENIED_CALLS}",
    "SystemCallErrorNumber=EPERM",
    "SystemCallArchitectures=native",
    "NoNewPrivileges=yes", "RestrictNamespaces=yes", "LockPersonality=yes",
    "RestrictRealtime=yes", "RestrictSUIDSGID=yes", "UMask=0077",
] + [f"{key}={value}" for key, value in LIMITS.items()]
UNIT_PREFIX = "refinix-sandbox-"
REPORT_MARK = "REFINIX-SANDBOX-REPORT "
POLL_SECONDS = 0.1
STOP_SECONDS = 10.0


class SandboxError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def launcher_path() -> Path:
    """The launcher as a plain file Ubuntu's Python can run (shipped beside
    the packaged app, or from the source tree)."""
    candidates = [Path(__file__).with_name("sandbox_launcher.py")]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.insert(0, Path(meipass) / "sandbox" / "sandbox_launcher.py")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SandboxError("launcher_missing", "The sandbox launcher is missing from this "
                                           "installation.")


def inputs_digest(files: list[dict]) -> str:
    """The digest the launcher recomputes from the staged copies."""
    return hashlib.sha256(json.dumps(sorted([f["path"], f["sha256"]] for f in files))
                          .encode()).hexdigest()


class Host:
    """The operating system side; tests replace it."""

    def run(self, argv, *, timeout=120, input_text=None):
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                              check=False, input=input_text,
                              stdin=None if input_text is not None else subprocess.DEVNULL)

    def which(self, name):
        return shutil.which(name)

    def popen(self, argv):
        return subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)

    def monotonic(self):
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def mounted(self, target: str) -> bool:
        """Whether a mount point or device is still mounted (mountinfo)."""
        try:
            lines = Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
        except OSError:
            return False
        for line in lines:
            fields = line.split()
            source = fields[fields.index("-") + 2] if "-" in fields else ""
            if len(fields) > 4 and (fields[4] == target or source == target):
                return True
        return False

    def loop_backing(self, device: str) -> str | None:
        """The file a loop device is attached to, or None when it is free."""
        name = Path(device).name
        try:
            return Path(f"/sys/block/{name}/loop/backing_file").read_text(
                encoding="utf-8").strip() or None
        except OSError:
            return None


class LocalSandbox:
    def __init__(self, data_root: Path, *, host: Host | None = None, probe=None,
                 platform: str | None = None):
        self.home = Path(data_root) / "sandbox"
        self.host = host or Host()
        self._probe = probe or sandbox_probe.probe
        self.platform = platform or sys.platform
        # The parent's own limit, beyond the service's RuntimeMaxSec.
        self.deadline_seconds = DEADLINE_SECONDS + 60
        self._active: set[str] = set()
        self._guard = threading.Lock()

    # -- what can run here ---------------------------------------------------
    def status(self) -> dict:
        """Controls observed on this computer, and whether validation may run."""
        observed = self._probe(platform=self.platform)
        if not self.platform.startswith("linux"):
            return {**observed, "available": False}
        controls = [c for c in observed.get("controls") or []
                    if c["name"] != "aggregate temporary-storage limit"]
        storage = self.storage_method()
        controls.append({"name": "aggregate temporary-storage limit",
                         "ok": storage is not None, "observed": storage,
                         "detail": "a fixed-size ext4 image (bytes and files capped) "
                                   "mounted through udisks or fuse2fs"})
        missing = [c["name"] for c in controls if not c["ok"]]
        stuck = self.stuck_runs()
        if stuck:
            missing.append("cleanup of an earlier sandbox run (" + "; ".join(stuck) + ")")
        for tool in ("systemd-run", "mkfs.ext4"):
            if not self.host.which(tool):
                missing.append(tool)
        if not Path(PYTHON).is_file():
            missing.append(PYTHON)
        available = not missing
        return {"available": available, "profile": PROFILE,
                "profile_version": PROFILE_VERSION, "qualification": QUALIFICATION,
                "controls": controls, "missing": missing, "storage": storage,
                "kernel": observed.get("kernel"),
                "detail": (f"Code validation runs in a {QUALIFICATION} Ubuntu sandbox: no "
                           "network, no access outside its workspace, and capped memory, "
                           "processes, CPU, time, disk and output." if available else
                           "Code validation in a sandbox is not available on this computer: "
                           "missing " + ", ".join(missing) + ". Proposals, review and the "
                           "labelled local Apply/Undo still work.")}

    def storage_method(self) -> str | None:
        if self.host.which("udisksctl"):
            return "udisks"
        if self.host.which("fuse2fs") and self.host.which("fusermount3"):
            return "fuse2fs"
        return None

    # -- the journal ----------------------------------------------------------
    def _journal(self) -> dict:
        try:
            return json.loads((self.home / "journal.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"runs": {}}

    def _save(self, journal: dict) -> None:
        self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.home / ".journal.json.tmp"
        temporary.write_text(json.dumps(journal, indent=2), encoding="utf-8")
        os.replace(temporary, self.home / "journal.json")

    def _note(self, run_id: str, **fields) -> None:
        journal = self._journal()
        journal["runs"].setdefault(run_id, {}).update(fields)
        self._save(journal)

    def cleanup_leftovers(self) -> list[str]:
        """At startup and before each run: finish cleaning up earlier runs.

        A run's record is removed only when its cleanup is confirmed;
        otherwise it stays, with what failed, for the next attempt. Runs in
        progress in this process are never touched.
        """
        cleaned = []
        with self._guard:
            active = set(self._active)
        journal = self._journal()
        for run_id, run in list(journal["runs"].items()):
            if run_id in active:
                continue
            problems = self._teardown(run)
            if problems:
                run["cleanup_problems"] = problems
                run["cleanup_attempts"] = int(run.get("cleanup_attempts") or 0) + 1
                run["cleanup_failed_at"] = _stamp()
            else:
                cleaned.append(run_id)
                del journal["runs"][run_id]
        self._save(journal)
        return cleaned

    def stuck_runs(self) -> list[str]:
        """Earlier runs whose workspace could not be detached yet."""
        with self._guard:
            active = set(self._active)
        return [f"{run_id}: {', '.join(run.get('cleanup_problems') or [])}"
                for run_id, run in self._journal()["runs"].items()
                if run_id not in active and run.get("cleanup_problems")]

    def _teardown(self, run: dict) -> list[str]:
        """Stop the service and detach the storage; what could not be done.

        Each step is checked rather than assumed, and the backing image is
        removed only once nothing uses it. Only this run's own unit, mount and
        loop device (as journalled) are touched.
        """
        problems = []
        unit = run.get("unit")
        if unit and unit.startswith(UNIT_PREFIX):
            self.host.run(["systemctl", "--user", "stop", unit], timeout=60)
            shown = self.host.run(["systemctl", "--user", "show", "-p", "ActiveState",
                                   "--value", unit], timeout=30)
            state = (getattr(shown, "stdout", "") or "").strip()
            if state in ("active", "activating", "deactivating", "reloading"):
                problems.append(f"service {unit} is still {state}")
            else:
                self.host.run(["systemctl", "--user", "reset-failed", unit], timeout=30)
        mount, device = run.get("mount"), run.get("device")
        image = str(Path(run["folder"]) / "workspace.img") if run.get("folder") else None
        if run.get("method") == "udisks" and device:
            if mount and self.host.mounted(mount) or self.host.mounted(device):
                self.host.run(["udisksctl", "unmount", "--no-user-interaction", "-b", device],
                              timeout=60)
            if (mount and self.host.mounted(mount)) or self.host.mounted(device):
                problems.append(f"{device} is still mounted")
            else:
                backing = self.host.loop_backing(device)
                if backing and image and Path(backing) == Path(image):
                    self.host.run(["udisksctl", "loop-delete", "--no-user-interaction",
                                   "-b", device], timeout=60)
                    backing = self.host.loop_backing(device)
                    if backing and Path(backing) == Path(image):
                        problems.append(f"{device} is still attached")
        elif run.get("method") == "fuse2fs" and mount:
            if self.host.mounted(mount):
                self.host.run(["fusermount3", "-u", mount], timeout=60)
            if self.host.mounted(mount):
                problems.append(f"{mount} is still mounted")
        folder = run.get("folder")
        if not problems and folder and Path(folder).parent == self.home / "runs":
            shutil.rmtree(folder, ignore_errors=True)
        return problems

    # -- one validation ----------------------------------------------------------
    def _mount(self, run_id: str, folder: Path, method: str) -> tuple[Path, str | None]:
        image = folder / "workspace.img"
        with open(image, "wb") as handle:
            handle.truncate(IMAGE_BYTES)
        made = self.host.run(["mkfs.ext4", "-q", "-F", "-N", str(IMAGE_INODES), "-m", "0",
                              "-O", "^has_journal", "-E",
                              f"root_owner={os.getuid()}:{os.getgid()}", str(image)],
                             timeout=120)
        if made.returncode != 0:
            raise SandboxError("storage", f"The sandbox workspace could not be made: "
                                          f"{(made.stderr or '').strip()[-300:]}")
        if method == "udisks":
            loop = self.host.run(["udisksctl", "loop-setup", "--no-user-interaction",
                                  "-f", str(image)], timeout=60)
            match = re.search(r"as (/dev/loop\d+)", loop.stdout or "")
            if loop.returncode != 0 or not match:
                raise SandboxError("storage", "udisks did not attach the workspace image "
                                   "without asking for a password: "
                                   + (loop.stderr or loop.stdout or "").strip()[-300:])
            device = match.group(1)
            self._note(run_id, device=device)
            mounted = self.host.run(["udisksctl", "mount", "--no-user-interaction", "-b",
                                     device, "-o", "nosuid,nodev"], timeout=60)
            found = re.search(r" at (/\S.*?)\.?\s*$", (mounted.stdout or "").strip())
            if mounted.returncode != 0 or not found:
                raise SandboxError("storage", "udisks did not mount the workspace: "
                                   + (mounted.stderr or "").strip()[-300:])
            return Path(found.group(1)), device
        mount = folder / "workspace"
        mount.mkdir(mode=0o700)
        mounted = self.host.run(["fuse2fs", str(image), str(mount), "-o",
                                 "rw,nosuid,nodev"], timeout=60)
        if mounted.returncode != 0:
            raise SandboxError("storage", "fuse2fs did not mount the workspace: "
                               + (mounted.stderr or "").strip()[-300:])
        return mount, None

    def validate(self, files: list[dict], *, cancel=None) -> dict:
        """Stage `files` ({path, text, sha256}) and run the approved command.

        Returns the launcher's report plus the binding facts: profile,
        controls, limits and the staged-input digest. Raises SandboxError when
        validation could not run at all; a run that ran and failed is a result.
        """
        self.cleanup_leftovers()
        status = self.status()
        if not status["available"]:
            raise SandboxError("no_sandbox", status["detail"])
        method = status["storage"]
        run_id = uuid.uuid4().hex[:12]
        nonce = secrets.token_hex(16)
        folder = self.home / "runs" / run_id
        folder.mkdir(parents=True, mode=0o700)
        unit = f"{UNIT_PREFIX}{run_id}"
        with self._guard:
            self._active.add(run_id)
        self._note(run_id, unit=unit, method=method, folder=str(folder), started_at=_stamp())
        try:
            mount, device = self._mount(run_id, folder, method)
            self._note(run_id, mount=str(mount))
            staged = []
            for item in files:
                relative = Path(item["path"])
                if relative.is_absolute() or ".." in relative.parts:
                    raise SandboxError("inputs", f"{item['path']} is not a relative path")
                target = mount / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(item["text"], encoding="utf-8")
                staged.append({"path": str(relative), "sha256": item["sha256"]})
            manifest = folder / "manifest.json"
            manifest.write_text(json.dumps({"files": staged, "seconds": DEADLINE_SECONDS,
                                            "cgroup_limits": CGROUP_LIMITS,
                                            "outside_probe": "/etc/hostname",
                                            "report_code": nonce}),
                                encoding="utf-8")
            argv = (["systemd-run", "--user", "--wait", "--collect", "--pipe", "--quiet",
                     f"--unit={unit}", f"--working-directory={mount}"]
                    + [f"--property={p}" for p in PROPERTIES]
                    + ["--", PYTHON, "-I", "-S", str(launcher_path()), str(mount),
                       str(manifest)])
            report, output = self._run(argv, unit, cancel, nonce)
            report.update(profile=PROFILE, profile_version=PROFILE_VERSION,
                          qualification=QUALIFICATION, storage=method, unit=unit,
                          limits_requested=LIMITS, expected_inputs_sha256=inputs_digest(staged))
            if report.get("ran") and report.get("inputs_sha256") != \
                    report["expected_inputs_sha256"]:
                report.update(ran=False, refused="inputs",
                              error="The staged inputs do not match what was reviewed.")
            report["output"] = output
            return report
        finally:
            with self._guard:
                self._active.discard(run_id)
            run = self._journal()["runs"].get(run_id, {})
            problems = self._teardown(run)
            journal = self._journal()
            if problems:
                # Kept, with what failed, so the next start or run retries it.
                journal["runs"].setdefault(run_id, run).update(
                    cleanup_problems=problems, cleanup_attempts=1,
                    cleanup_failed_at=_stamp())
            else:
                journal["runs"].pop(run_id, None)
            self._save(journal)

    def _stop_unit(self, unit: str, process) -> None:
        """Stop the whole service now, then make sure our client has ended."""
        self.host.run(["systemctl", "--user", "kill", "--signal=SIGKILL", unit], timeout=30)
        self.host.run(["systemctl", "--user", "stop", unit], timeout=30)
        ends = self.host.monotonic() + STOP_SECONDS
        while process.poll() is None and self.host.monotonic() < ends:
            self.host.sleep(POLL_SECONDS)
        if process.poll() is None:
            process.kill()
            try:
                process.wait(timeout=STOP_SECONDS)
            except subprocess.TimeoutExpired:
                pass

    def _run(self, argv, unit: str, cancel, nonce: str = "") -> tuple[dict, str]:
        """Run the unit; keep at most OUTPUT_LIMIT of output, and always the
        launcher's closing report line.

        Output is read on its own thread, so a quiet test cannot hold up
        Cancel or the deadline: those are checked every POLL_SECONDS whatever
        the tests print, and stop the whole service.
        """
        process = self.host.popen(argv)
        state = {"collected": bytearray(), "tail": b"", "flooded": False}

        def read():
            try:
                for block in iter(lambda: process.stdout.read(8192), b""):
                    room = OUTPUT_LIMIT - len(state["collected"])
                    state["collected"].extend(block[:max(room, 0)])
                    state["flooded"] = state["flooded"] or len(block) > room
                    state["tail"] = (state["tail"] + block)[-16384:]
            except (OSError, ValueError):
                pass
        reader = threading.Thread(target=read, name="sandbox-output", daemon=True)
        reader.start()
        deadline = self.host.monotonic() + self.deadline_seconds
        stopped = None
        while process.poll() is None:
            if cancel is not None and cancel.is_set():
                stopped = "cancelled"
            elif self.host.monotonic() > deadline:
                stopped = "deadline"
            if stopped:
                self._stop_unit(unit, process)
                break
            self.host.sleep(POLL_SECONDS)
        if cancel is not None and cancel.is_set() and not stopped:
            # Cancelled as it ended: a cancelled validation is never a pass.
            stopped = "cancelled"
        # Stopping the service ends everything holding its output; the wait
        # after a stop is short so Cancel is never held up by a stuck pipe.
        reader.join(2.0 if stopped else STOP_SECONDS)
        text = bytes(state["collected"]).decode("utf-8", errors="replace")
        ending = bytes(state["tail"]).decode("utf-8", errors="replace")
        report = {"ran": False, "refused": "launcher",
                  "error": "The sandbox ended without a report."}
        mark = f"{REPORT_MARK}{nonce} " if nonce else REPORT_MARK
        if mark in ending:
            line = ending[ending.rindex(mark) + len(mark):].splitlines()[0]
            try:
                report = json.loads(line)
            except ValueError:
                pass
        if stopped == "cancelled":
            report.update(ran=False, refused="cancelled", error="Validation was cancelled.")
        elif stopped == "deadline":
            report.update(ran=False, refused="deadline",
                          error="Validation ran out of time and was stopped.")
        if state["flooded"]:
            report["output_truncated"] = True
        report["service_exit"] = process.returncode
        if REPORT_MARK in text:
            text = text[:text.rindex(REPORT_MARK)]
        return report, text


def passed(report: dict) -> bool:
    """A pass is observed, never inferred: it ran confined, every check held,
    the inputs matched, at least one test ran with exit status 0, the closing
    report carried this run's code and the service itself ended normally."""
    return (report.get("ran") is True and not report.get("refused")
            and report.get("service_exit") == 0
            and report.get("exit_status") == 0 and (report.get("tests_run") or 0) >= 1
            and report.get("inputs_sha256") == report.get("expected_inputs_sha256")
            and {"no sockets", "Landlock", "no signals"} <= set(report.get("controls") or []))
