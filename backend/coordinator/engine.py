"""Refinix's own inference engine: which one, whether it is intact, who runs it.

An installed Refinix uses one pinned, integrity-verified **managed engine**
(`llama-server` from llama.cpp) shipped inside the package. It never looks the
engine up through `PATH`, never adopts a process that happens to listen on a
port, and never talks to a system Ollama. That is what keeps an external
runtime update from disabling the installed application.

Two modes:

* **managed** — always in a packaged build. The engine files listed in the
  generated `engine-manifest.json` are re-hashed before every launch; the
  process is started from its absolute path with a minimal environment on a
  Refinix-chosen loopback port and a per-launch API key, with every qualified
  setting given explicitly and the engine's own automatic fitting turned off.
  It is accepted only after it proves it enforces that key.
* **developer** — a source checkout with no managed engine fetched (or with
  `REFINIX_ENGINE=ollama`). The existing external Ollama path keeps working for
  contributors and as the parity baseline, and is labelled as such.

Model weights are separate, explicitly provisioned files; they are never inside
the application package. This module starts the engine for one verified model
at a time; resource admission decides when.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform as _platform
import secrets
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from backend.coordinator import build_info

MANAGED = "managed"
DEVELOPER = "developer"
LLAMA_CPP = "llama.cpp"
OLLAMA = "ollama"

MANIFEST_NAME = "engine-manifest.json"
REPO = Path(__file__).resolve().parents[2]
SOURCE_DIST = REPO / "desktop" / "engine" / "dist"

# A private loopback range, away from Ollama (11434), the coordinator (8770+),
# the worker contract (8443/30443) and common development servers.
PORT_RANGE = range(39400, 39500)
READY_SECONDS = 180.0
STOP_SECONDS = 5.0
# Matches the previous `keep_alive` of ten minutes: after that much idleness the
# engine releases the model's memory and reloads it on the next request.
IDLE_SLEEP_SECONDS = 600


class EngineError(RuntimeError):
    """The managed engine is missing, modified, failed to start or is not ours."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------
# Which build lane applies to this computer
# --------------------------------------------------------------------------

def lane_candidates(platform: str | None = None,
                    machine: str | None = None) -> list[str]:
    """Pinned engine lanes for this OS/architecture, most capable first."""
    platform = sys.platform if platform is None else platform
    machine = (_platform.machine() if machine is None else machine).lower()
    if platform == "darwin" and machine in ("arm64", "aarch64"):
        return ["macos-arm64"]
    if platform == "win32" and machine in ("amd64", "x86_64"):
        return ["windows-x64-vulkan", "windows-x64-cpu"]
    if platform.startswith("linux") and machine in ("x86_64", "amd64"):
        return ["linux-x64-vulkan", "linux-x64-cpu"]
    return []


def _resource_engine_roots() -> list[Path]:
    roots = []
    for root in build_info._resource_roots():
        roots.append(root / "engine")
        roots.extend(sorted((root / "engine").glob("*")) if (root / "engine").is_dir() else [])
    return roots


def engine_roots(*, frozen: bool | None = None) -> list[Path]:
    """Folders that may hold a managed engine, in preference order.

    The order is this computer's lane order (GPU build first), never the
    alphabetical order of folder names.
    """
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    lanes = lane_candidates()
    if frozen:
        found = {r.name: r for r in _resource_engine_roots() if (r / MANIFEST_NAME).is_file()}
        return [found[lane] for lane in lanes if lane in found]
    return [SOURCE_DIST / lane for lane in lanes
            if (SOURCE_DIST / lane / MANIFEST_NAME).is_file()]


# --------------------------------------------------------------------------
# Integrity
# --------------------------------------------------------------------------

def load_manifest(root: Path) -> dict:
    try:
        manifest = json.loads((Path(root) / MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EngineError("engine_missing", f"The engine manifest could not be read: {exc}")
    for key in ("kind", "release", "backend", "executable", "files", "lane"):
        if key not in manifest:
            raise EngineError("engine_unverified", f"The engine manifest has no {key!r}.")
    return manifest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(root: Path, manifest: dict) -> list[str]:
    """Every listed engine file, byte for byte. Empty when the engine is intact."""
    root = Path(root)
    problems = []
    for entry in manifest["files"]:
        path = root.joinpath(*entry["path"].split("/"))
        if "link" in entry:
            if not path.is_symlink() or os.readlink(path) != entry["link"]:
                problems.append(f"{entry['path']} is not the expected link")
            continue
        if path.is_symlink() or not path.is_file():
            problems.append(f"{entry['path']} is missing")
            continue
        if path.stat().st_size != entry["size"] or _sha256(path) != entry["sha256"]:
            problems.append(f"{entry['path']} does not match the shipped engine")
    executable = root.joinpath(*manifest["executable"].split("/"))
    if not executable.is_file():
        problems.append("the engine program is missing")
    return problems


def runtime_version(manifest: dict) -> str:
    """The exact identity qualification records bind to, e.g. `b11390-metal`."""
    return f"{manifest['release']}-{manifest['backend']}"


@dataclass
class Selection:
    mode: str
    kind: str
    label: str
    root: Path | None = None
    manifest: dict | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.mode == DEVELOPER or (self.manifest is not None and not self.problems)

    @property
    def runtime_version(self) -> str | None:
        return runtime_version(self.manifest) if self.manifest else None

    def describe(self) -> dict:
        return {"mode": self.mode, "kind": self.kind, "label": self.label,
                "release": (self.manifest or {}).get("release"),
                "backend": (self.manifest or {}).get("backend"),
                "lane": (self.manifest or {}).get("lane"),
                "runtime_version": self.runtime_version,
                "verified": self.mode == MANAGED and not self.problems
                            and self.manifest is not None,
                "problems": list(self.problems)}


GPU_BACKENDS = ("vulkan", "cuda")


def _verified(root: Path) -> Selection:
    try:
        manifest = load_manifest(root)
    except EngineError as exc:
        return Selection(MANAGED, LLAMA_CPP, "Refinix engine", root, None, [str(exc)])
    return Selection(MANAGED, LLAMA_CPP, "Refinix engine", root, manifest,
                     verify(root, manifest))


def select(environ=None, *, frozen: bool | None = None, roots=None,
           devices=None) -> Selection:
    """Decide which engine this process uses. Never searches `PATH`.

    When a package ships a GPU build and a CPU build, the GPU build is used
    only if it verifies and reports a device of its backend. A GPU build that
    fails verification is reported as modified; it is never silently replaced
    by the CPU build, because a changed file is a problem to repair, not a
    preference.
    """
    environ = os.environ if environ is None else environ
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if not frozen and environ.get("REFINIX_ENGINE", "").strip().lower() == OLLAMA:
        return Selection(DEVELOPER, OLLAMA, "Developer engine: external Ollama")
    roots = engine_roots(frozen=frozen) if roots is None else roots
    devices = list_devices if devices is None else devices
    candidates = [_verified(root) for root in roots]
    for index, candidate in enumerate(candidates):
        if candidate.problems or candidate.manifest is None:
            return candidate
        backend = candidate.manifest.get("backend")
        later = candidates[index + 1:]
        if backend in GPU_BACKENDS and later:
            found = devices(candidate) or []
            if not any(str(d.get("id", "")).upper().startswith(backend.upper())
                       for d in found):
                continue          # no usable device for this build; try the next
        return candidate
    if candidates:
        return candidates[-1]
    if frozen:
        return Selection(MANAGED, LLAMA_CPP, "Refinix engine", None, None,
                         ["The engine is not part of this installation."])
    return Selection(DEVELOPER, OLLAMA, "Developer engine: external Ollama")


# --------------------------------------------------------------------------
# Launch settings
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class LaunchSettings:
    """Everything that changes engine behaviour, given explicitly.

    Comes from the reviewed preset for this model and hardware tier. Nothing is
    left for the engine to fill in on its own.
    """

    context_tokens: int
    slots: int = 1
    gpu_layers: int | str = "all"
    cache_type_k: str = "f16"
    cache_type_v: str = "f16"
    flash_attention: str = "auto"
    threads: int | None = None
    reasoning_format: str = "deepseek"
    idle_sleep_seconds: int = IDLE_SLEEP_SECONDS
    # Admission, not engine arguments: below these, the engine is not started
    # for this model (`local_engine.LocalEngine.stream_chat`).
    min_available_memory_bytes: int = 0
    min_free_disk_bytes: int = 0

    def arguments(self) -> list[str]:
        args = ["-c", str(self.context_tokens * self.slots), "-np", str(self.slots),
                "-ngl", str(self.gpu_layers), "-ctk", self.cache_type_k,
                "-ctv", self.cache_type_v, "-fa", self.flash_attention,
                "--fit", "off", "--reasoning-format", self.reasoning_format,
                "--sleep-idle-seconds", str(self.idle_sleep_seconds)]
        if self.threads:
            args += ["-t", str(self.threads)]
        return args


@dataclass(frozen=True)
class ModelFiles:
    """One verified model as the engine loads it."""

    model_id: str
    weights: Path
    projector: Path | None = None


@dataclass(frozen=True)
class Endpoint:
    host: str
    port: int
    api_key: str
    model_id: str
    runtime_version: str

    @property
    def base(self) -> str:
        return f"http://{self.host}:{self.port}"


# --------------------------------------------------------------------------
# The supervisor
# --------------------------------------------------------------------------

def _free_port(candidates=PORT_RANGE, host="127.0.0.1") -> int:
    for port in candidates:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind((host, port))
            except OSError:
                continue
        return port
    raise EngineError("engine_no_port", "No private local port was free for the engine.")


def _http(url: str, *, key: str | None = None, timeout: float = 3.0):
    """One GET to the engine on loopback: (status, parsed JSON) or (None, None).

    `http.client` rather than urllib: no proxy handling to disable, no redirect
    following, and the socket is always closed, including on a refused connect.
    """
    import http.client
    from urllib.parse import urlsplit
    parts = urlsplit(url)
    if parts.hostname != "127.0.0.1":
        return None, None
    connection = http.client.HTTPConnection(parts.hostname, parts.port, timeout=timeout)
    try:
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        connection.request("GET", parts.path or "/", headers=headers)
        response = connection.getresponse()
        raw = response.read(1024 * 1024)
        try:
            body = json.loads(raw or b"null")
        except ValueError:
            body = None
        return response.status, body
    except (OSError, http.client.HTTPException):
        return None, None
    finally:
        connection.close()


def minimal_environment(root: Path, home: Path, platform: str | None = None) -> dict:
    """Only what the engine needs; nothing inherited that could redirect it."""
    platform = sys.platform if platform is None else platform
    if platform == "win32":
        system_root = os.environ.get("SYSTEMROOT", r"C:\Windows")
        env = {"SYSTEMROOT": system_root, "WINDIR": os.environ.get("WINDIR", system_root),
               "PATH": f"{root};{system_root}\\System32",
               "TEMP": str(home), "TMP": str(home)}
        for key in ("NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "SystemDrive"):
            if key in os.environ:
                env[key] = os.environ[key]
        return env
    env = {"PATH": "/usr/bin:/bin", "HOME": str(home), "TMPDIR": str(home),
           "LANG": "C.UTF-8"}
    if platform.startswith("linux"):
        env["LD_LIBRARY_PATH"] = str(root)
    return env


class ManagedEngine:
    """Starts, proves, watches and stops Refinix's own engine process."""

    def __init__(self, selection: Selection, data_root: Path, *,
                 spawn=subprocess.Popen, http=_http, sleep=time.sleep,
                 clock=time.monotonic, ports=PORT_RANGE):
        if selection.mode != MANAGED:
            raise ValueError("a managed engine needs a managed selection")
        self.selection = selection
        self.data_root = Path(data_root)
        self._spawn, self._http, self._sleep, self._clock = spawn, http, sleep, clock
        self._ports = ports
        self._lock = threading.RLock()
        self.process = None
        self.endpoint: Endpoint | None = None
        self.model: ModelFiles | None = None
        self.settings: LaunchSettings | None = None
        self.last_error: EngineError | None = None

    # -- paths
    @property
    def home(self) -> Path:
        return self.data_root / "engine"

    @property
    def record_path(self) -> Path:
        return self.home / "engine-process.json"

    @property
    def log_path(self) -> Path:
        return self.data_root / "logs" / "engine.log"

    @property
    def executable(self) -> Path:
        manifest = self.selection.manifest
        return self.selection.root.joinpath(*manifest["executable"].split("/"))

    # -- state
    @property
    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def describe(self) -> dict:
        return {**self.selection.describe(), "running": self.running,
                "model": self.model.model_id if self.model and self.running else None,
                "error": str(self.last_error) if self.last_error else None,
                "error_code": self.last_error.code if self.last_error else None}

    # -- lifecycle
    def ensure(self, model: ModelFiles, settings: LaunchSettings, *,
               cancelled=None) -> Endpoint:
        """The endpoint serving exactly this model with exactly these settings."""
        with self._lock:
            if self.running and self.model == model and self.settings == settings:
                return self.endpoint
            try:
                # A replacement starts only after the previous engine, and any
                # engine a crashed run recorded, is confirmed gone.
                self.stop()
                self.reap_orphan()
                return self._start(model, settings, cancelled=cancelled)
            except EngineError as exc:
                self.last_error = exc
                raise

    def _start(self, model: ModelFiles, settings: LaunchSettings, *, cancelled=None) -> Endpoint:
        manifest = self.selection.manifest
        if manifest is None:
            raise EngineError("engine_missing", "The Refinix engine is not installed.")
        # Re-verified before every launch, not only at startup: the files can
        # change while Refinix runs, and a modified engine must never start.
        problems = verify(self.selection.root, manifest)
        if problems:
            self.selection.problems = problems
            raise EngineError("engine_unverified",
                              "The Refinix engine files were changed: " + "; ".join(problems[:3]))
        for path in [model.weights] + ([model.projector] if model.projector else []):
            if not Path(path).is_file():
                raise EngineError("model_missing", f"{Path(path).name} is not installed.")
        self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.log_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        port = _free_port(self._ports)
        key = secrets.token_hex(24)
        args = [str(self.executable), "--host", "127.0.0.1", "--port", str(port),
                "--api-key", key, "-m", str(model.weights), "--alias", model.model_id,
                "--offline", "--no-webui", "--no-webui-mcp-proxy", "--no-slots",
                "--jinja", *settings.arguments()]
        if model.projector:
            args += ["--mmproj", str(model.projector)]
        else:
            args += ["--no-mmproj"]
        kwargs = {"cwd": str(self.selection.root),
                  "env": minimal_environment(self.selection.root, self.home),
                  "stdin": subprocess.DEVNULL, "stderr": subprocess.STDOUT}
        if sys.platform == "win32":
            kwargs["creationflags"] = (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
                                       | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
        else:
            kwargs["start_new_session"] = True
        with open(self.log_path, "wb") as log:
            try:
                self.process = self._spawn(args, stdout=log, **kwargs)
            except OSError as exc:
                raise EngineError("engine_failed", f"The Refinix engine would not start: {exc}")
        self._record_process()
        endpoint = Endpoint("127.0.0.1", port, key, model.model_id,
                            runtime_version(manifest))
        try:
            self._await_ready(endpoint, model, cancelled=cancelled)
        except BaseException as failure:
            try:
                self.stop()
            except EngineError as blocked:
                # The process that failed to load is still running: that, not
                # the load failure, is what the next step has to deal with.
                raise blocked from failure
            raise
        self.endpoint, self.model, self.settings, self.last_error = endpoint, model, settings, None
        return endpoint

    def _await_ready(self, endpoint: Endpoint, model: ModelFiles, *, cancelled=None) -> None:
        deadline = self._clock() + READY_SECONDS
        while self._clock() < deadline:
            if cancelled is not None and cancelled():
                raise EngineError("engine_cancelled", "Starting the engine was cancelled.")
            if self.process.poll() is not None:
                raise EngineError(
                    "engine_failed",
                    f"The Refinix engine stopped while loading {model.model_id} "
                    f"(exit code {self.process.returncode}). See {self.log_path.name}.")
            status, _body = self._http(f"{endpoint.base}/health", timeout=2.0)
            if status == 200:
                self._prove_ownership(endpoint, model)
                return
            self._sleep(0.25)
        raise EngineError("engine_failed",
                          f"The Refinix engine did not finish loading {model.model_id} in time.")

    def _prove_ownership(self, endpoint: Endpoint, model: ModelFiles) -> None:
        """Only the process started with this launch's secret is accepted."""
        status, props = self._http(f"{endpoint.base}/props", key=endpoint.api_key)
        anonymous, _ = self._http(f"{endpoint.base}/props")
        if status != 200 or not isinstance(props, dict) or anonymous != 401:
            raise EngineError(
                "engine_foreign",
                "The program answering on the engine's port is not the engine "
                "Refinix just started, so it was not used.")
        build = str(props.get("build_info", ""))
        expected = str(self.selection.manifest["release"]).lstrip("b")
        if expected and expected not in build:
            raise EngineError("engine_unverified",
                              f"The engine reported build {build!r}, not the shipped "
                              f"{self.selection.manifest['release']}.")
        loaded = props.get("model_path")
        if loaded and Path(loaded) != Path(model.weights):
            raise EngineError("engine_foreign", "The engine loaded a different model file.")

    def stop(self) -> bool:
        """Stop the engine this object started.

        False when none was running; True once its exit is confirmed. The
        process and its durable record are forgotten only after that
        confirmation. A process that survives terminate and kill stays
        recorded, `last_error` says so, and `EngineError("engine_stop_blocked")`
        is raised, so no replacement is started beside it.
        """
        with self._lock:
            process = self.process
            self.endpoint = self.model = self.settings = None
            if process is None:
                return False
            if not self._end(process):
                self.last_error = EngineError(
                    "engine_stop_blocked",
                    f"The Refinix engine (process {process.pid}) did not stop when "
                    "asked, so a new one was not started beside it. Quit Refinix, "
                    "or end that process, then try again.")
                raise self.last_error
            self.process = None
            self._forget_record()
            return True

    @staticmethod
    def _end(process) -> bool:
        """Terminate, then kill; True only once the process has exited."""
        if process.poll() is not None:
            return True
        for request in (process.terminate, process.kill):
            try:
                request()
            except OSError:
                pass           # already gone, or refused: waiting decides which
            try:
                process.wait(timeout=STOP_SECONDS)
                return True
            except subprocess.TimeoutExpired:
                continue
            except OSError:
                break
        return process.poll() is not None

    # -- orphans
    def _record_process(self) -> None:
        try:
            import psutil
            created = psutil.Process(self.process.pid).create_time()
        except Exception:                                  # noqa: BLE001
            created = None
        record = {"pid": self.process.pid, "create_time": created,
                  "executable": str(self.executable)}
        tmp = self.record_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record), encoding="utf-8")
        os.replace(tmp, self.record_path)

    def _forget_record(self) -> None:
        try:
            self.record_path.unlink()
        except FileNotFoundError:
            pass

    def _blocked(self, record: dict, why: str) -> EngineError:
        self.last_error = EngineError(
            "engine_stop_blocked",
            f"An engine an earlier Refinix started (process {record.get('pid')}) "
            f"may still be running and {why}, so a new engine was not started. "
            "Restart the computer if this does not clear after quitting Refinix.")
        return self.last_error

    def reap_orphan(self) -> bool:
        """Stop an engine a crashed Refinix left behind, only if provably ours.

        The record names a PID, its start time and the executable. True when
        that process was ours and its exit is confirmed; False when there was
        nothing to stop, because no record exists or the PID now belongs to a
        process started at another time (a live PID names one process, so
        ours has exited). A recycled PID is never signalled.

        Raises `EngineError("engine_stop_blocked")` and keeps the record when
        the process cannot be identified or did not exit: an uncertain
        survivor is never treated as gone.
        """
        try:
            text = self.record_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return False
        try:
            record = json.loads(text)
            pid = int(record["pid"])
            recorded_start = record.get("create_time")
            recorded_start = None if recorded_start is None else float(recorded_start)
            executable = Path(record["executable"])
        except (ValueError, TypeError, KeyError, AttributeError):
            # Written atomically, so this is not a crash mid-write. It names no
            # process that could be checked or signalled; keep it for anyone
            # investigating and continue.
            aside = self.record_path.with_name(
                f"engine-process.unreadable-{int(time.time())}.json")
            os.replace(self.record_path, aside)
            return False
        try:
            import psutil
        except ImportError:
            raise self._blocked(record, "this installation cannot inspect processes")
        try:
            process = psutil.Process(pid)
            started = process.create_time()
        except psutil.NoSuchProcess:
            self._forget_record()
            return False
        except Exception:                                  # noqa: BLE001
            raise self._blocked(record, "this computer did not let Refinix inspect it")
        if recorded_start is not None and abs(started - recorded_start) >= 0.01:
            self._forget_record()
            return False
        try:
            same_program = Path(process.exe()) == executable
        except psutil.NoSuchProcess:
            self._forget_record()
            return False
        except Exception:                                  # noqa: BLE001
            raise self._blocked(record, "this computer did not let Refinix inspect it")
        if recorded_start is None:
            # Without a start time the PID could have been reused by another
            # copy of the same engine, for example another workspace's.
            if not same_program:
                self._forget_record()
                return False
            raise self._blocked(record, "it cannot be told apart from another program")
        if not same_program:
            raise self._blocked(record, "it is now running a different program")
        for request in (process.terminate, process.kill):
            try:
                request()
            except psutil.NoSuchProcess:
                break
            except Exception:                              # noqa: BLE001
                raise self._blocked(record, "Refinix was not allowed to stop it")
            try:
                process.wait(timeout=STOP_SECONDS)
                break
            except psutil.TimeoutExpired:
                continue
        else:
            raise self._blocked(record, "it did not stop when asked")
        self._forget_record()
        return True


def list_devices(selection: Selection, *, run=subprocess.run, timeout: float = 20.0) -> list[dict] | None:
    """The backend devices this engine build can use, as the engine reports them.

    `None` when it could not be asked: the engine is missing or modified, or
    did not answer. Unknown is never reported as "no GPU".
    """
    if selection.mode != MANAGED or not selection.manifest or selection.problems:
        return None
    exe = selection.root.joinpath(*selection.manifest["executable"].split("/"))
    try:
        result = run([str(exe), "--list-devices"], capture_output=True, text=True,
                     timeout=timeout, cwd=str(selection.root),
                     env=minimal_environment(selection.root, selection.root))
    except (OSError, subprocess.SubprocessError):
        return None
    devices = []
    for line in (result.stdout + "\n" + result.stderr).splitlines():
        line = line.strip()
        # "MTL0: Apple M5 (12124 MiB, 12123 MiB free)"
        if ":" not in line or "MiB" not in line:
            continue
        name, _, rest = line.partition(":")
        label, _, numbers = rest.rpartition("(")
        try:
            total = int(numbers.split("MiB")[0].strip())
            free = int(numbers.split(",")[1].split("MiB")[0].strip())
        except (IndexError, ValueError):
            total = free = None
        devices.append({"id": name.strip(), "name": label.strip(),
                        "memory_mib": total, "free_mib": free})
    return devices
