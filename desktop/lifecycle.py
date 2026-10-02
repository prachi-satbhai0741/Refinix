"""Startup and shutdown lifecycle for the Refinix desktop shell.

Standard library only, and deliberately free of any window toolkit so the whole
sequence can be exercised offline with synthetic probes. `desktop.shell` adds
the window on top of this.

Rules this module enforces, because they are product requirements rather than
implementation detail:

* Nothing is downloaded or installed. A missing runtime or model produces an
  actionable setup need with the exact command, never a silent fetch.
* Docker is never started. Ordinary Chat needs the local model runtime only.
* An occupied port is never assumed to be ours. The occupant must answer as
  this workspace's coordinator before it is reused; otherwise a different free
  port is chosen and no unrelated service is attached to.
* Only processes this application actually started are stopped on quit.
* Every step is bounded, so a failure surfaces as a readable error with a retry
  rather than an endless loading screen.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath

from backend.coordinator import paths, runtime

# Which root this installation uses is a platform decision, and
# `backend.coordinator.paths` owns it: the OS-native location, the existing
# `.aegisforge` store when one is already there, or an explicit portable profile.
# Resolved once at import because these constants are the defaults every entry
# point passes down. Resolution only reads directory names — it creates nothing,
# moves nothing and never raises, so an ambiguous store still yields usable
# constants and is reported by `run_startup` instead.
DATA_ROOT = paths.select_root()
STATE_DIR = DATA_ROOT.path
STATE_DB = DATA_ROOT.database
# One lock per store, so two different roots are two different applications
# rather than one lock silently guarding the wrong data.
LOCK_FILE = STATE_DIR / "desktop.lock"

DEFAULT_PORT = 8770
# Bounded and explicit. 8443/30443 belong to the worker contract and 8080 to
# Jenkins on the Ubuntu host, so none of them appears here.
PORT_CANDIDATES = (8770, 8771, 8772, 8773, 8774, 8775, 8776, 8777)

SERVER_PREFIX = "AegisForgeCoordinator/"
STARTUP_BUDGET_SECONDS = 60.0
RUNTIME_START_SECONDS = 40.0


def _windows_ollama_paths() -> tuple[str, ...]:
    """Where the Windows installer puts the engine, when that is knowable.

    `LOCALAPPDATA` becomes a candidate only when it is actually set and
    actually absolute: an unset or relative value would otherwise produce a
    relative path, which `find_ollama` would then test against whatever
    directory Refinix happened to be launched from.

    Absoluteness is judged with Windows' rules rather than the host's, for the
    same reason `backend.coordinator.paths` does — `C:\…` is meaningless to a
    POSIX `Path`, and these candidates can only be checked from another
    computer before a Windows device is available.
    """
    local = os.environ.get("LOCALAPPDATA", "").strip()
    per_user = ()
    if local and PureWindowsPath(local).is_absolute():
        per_user = (str(PureWindowsPath(local, "Programs", "Ollama",
                                        "ollama.exe")),)
    return ("ollama.exe", *per_user, r"C:\Program Files\Ollama\ollama.exe")


OLLAMA_BINARIES = {
    "darwin": ("ollama", "/opt/homebrew/bin/ollama", "/usr/local/bin/ollama",
               "/Applications/Ollama.app/Contents/Resources/ollama"),
    "linux": ("ollama", "/usr/local/bin/ollama", "/usr/bin/ollama",
              str(Path.home() / ".local/bin/ollama")),
    "win32": _windows_ollama_paths(),
}

# One sentence, not three identical ones. The download page covers all three
# platforms, and Refinix installs nothing on any of them.
INSTALL_HINT = ("Install Ollama from https://ollama.com/download, then open "
                "Refinix again.")


# --------------------------------------------------------------------------
# Progress reporting
# --------------------------------------------------------------------------

@dataclass
class Step:
    """One line of startup progress, in the words the user reads."""

    key: str
    label: str
    state: str = "pending"       # pending | running | ok | attention | failed
    detail: str = ""
    action: dict | None = None   # {"kind": ..., "label": ..., "command": ...}

    def as_dict(self) -> dict:
        return {"key": self.key, "label": self.label, "state": self.state,
                "detail": self.detail, "action": self.action}


class Progress:
    """Thread-safe ordered step list the window polls while starting."""

    ORDER = (
        ("window", "Opening Refinix"),
        ("instance", "Checking for another open copy"),
        ("port", "Reserving a local address"),
        ("coordinator", "Starting the local coordinator"),
        ("engine", "Checking the AI engine"),
        ("model", "Checking the configured model"),
    )

    def __init__(self):
        self._lock = threading.Lock()
        self._steps = {key: Step(key, label) for key, label in self.ORDER}
        self.phase = "starting"          # starting | ready | attention | failed
        self.message = "Starting Refinix…"
        self.url: str | None = None

    def set(self, key, state, detail="", action=None):
        with self._lock:
            step = self._steps[key]
            step.state, step.detail, step.action = state, detail, action

    def finish(self, phase, message):
        with self._lock:
            self.phase, self.message = phase, message

    def snapshot(self) -> dict:
        with self._lock:
            return {"phase": self.phase, "message": self.message, "url": self.url,
                    "steps": [self._steps[k].as_dict() for k, _ in self.ORDER]}


class StartupError(RuntimeError):
    """A startup step failed in a way the user has to act on."""

    def __init__(self, message, detail="", action=None):
        super().__init__(message)
        self.detail = detail
        self.action = action


class StartupCancelled(Exception):
    """The window closed before startup finished."""


def _check_cancelled(cancelled):
    if cancelled is not None and cancelled.is_set():
        raise StartupCancelled()


# --------------------------------------------------------------------------
# Single instance
# --------------------------------------------------------------------------

def _lock_exclusive(handle) -> bool:
    """True when this process took the lock; False when another holds it."""
    try:
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


class SingleInstance:
    """One Refinix per user account, enforced by an OS lock, not a PID guess.

    A stale lock from a crash is reclaimed automatically: the lock is released
    by the operating system when the holding process dies.
    """

    def __init__(self, path: Path = LOCK_FILE):
        self.path = path
        self._handle = None
        # Windows byte locks also deny reads. Keep JSON after the locked byte.
        self._metadata_offset = 1 if sys.platform == "win32" else 0

    def acquire(self) -> dict | None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+", encoding="utf-8")
        # Windows locks a byte range from the current offset, unlike flock.
        # Every process must lock byte zero, including when metadata exists.
        handle.seek(0)
        if not _lock_exclusive(handle):
            handle.seek(self._metadata_offset)
            try:
                existing = json.loads(handle.read() or "{}")
            except ValueError:
                existing = {}
            handle.close()
            return existing if isinstance(existing, dict) else {}
        self._handle = handle
        return None

    def record(self, **fields) -> None:
        if self._handle is None:
            return
        self._handle.seek(self._metadata_offset)
        self._handle.truncate()
        json.dump({"pid": os.getpid(), **fields}, self._handle)
        self._handle.flush()
        os.fsync(self._handle.fileno())

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            self._handle.seek(self._metadata_offset)
            self._handle.truncate()
            self._handle.flush()
            self._handle.close()
        except OSError:
            pass
        self._handle = None


# --------------------------------------------------------------------------
# Ports
# --------------------------------------------------------------------------

def port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def get_json(url: str, timeout: float):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(url, headers={"Host": url.split("//", 1)[1].split("/", 1)[0]})
    with opener.open(request, timeout=timeout) as response:
        return response.headers, json.load(response)


def identify_occupant(port: int, timeout: float = 2.0) -> dict | None:
    """Return the coordinator identity behind `port`, or None for anything else.

    Anything that is not a coordinator — another application, a proxy, a stale
    listener — returns None so the caller moves to a different port instead of
    talking to it.
    """
    try:
        headers, body = get_json(f"http://127.0.0.1:{port}/v1/status", timeout)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None
    if not str(headers.get("Server", "")).startswith(SERVER_PREFIX):
        return None
    if not isinstance(body, dict) or not {"node_id", "workspace_id", "contract_version"} <= body.keys():
        return None
    return body


def check_data_root(state_path: Path = STATE_DB,
                    root: paths.DataRoot | None = None) -> None:
    """Refuse to start when two roots each hold a canonical store.

    Only when the caller is actually about to use the ambiguous path: a test
    database or an explicitly chosen root is the user's answer to the question,
    so it starts normally even while two other stores exist on the computer.
    """
    root = DATA_ROOT if root is None else root
    if root.conflict is None or Path(state_path) != root.database:
        return
    raise StartupError(
        "Refinix found workspace data in two places and will not choose for you.",
        str(root.conflict))


def read_workspace_id(state_path: Path = STATE_DB) -> str | None:
    """Read the saved workspace identity without creating or upgrading a file."""
    if not state_path.is_file():
        return None
    import sqlite3
    try:
        conn = sqlite3.connect(f"file:{state_path}?mode=ro", uri=True, timeout=5)
        try:
            row = conn.execute("SELECT value FROM meta WHERE key='workspace_id'").fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    return row[0] if row else None


@dataclass
class PortChoice:
    port: int
    reused: bool
    detail: str
    occupant: dict | None = None


def choose_port(preferred: int = DEFAULT_PORT, *, workspace_id: str | None = None,
                candidates=PORT_CANDIDATES, identify=identify_occupant,
                free=port_free) -> PortChoice:
    """Pick a port, reusing our own coordinator but never an unrelated service."""
    order = [preferred] + [p for p in candidates if p != preferred]
    first_conflict = None
    for port in order:
        if free(port):
            return PortChoice(port, False, f"port {port} is free")
        occupant = identify(port)
        if occupant is None:
            if first_conflict is None:
                first_conflict = port
            continue
        if not workspace_id or occupant.get("workspace_id") != workspace_id:
            # A coordinator, but not this workspace's. Leave it alone.
            if first_conflict is None:
                first_conflict = port
            continue
        return PortChoice(port, True, f"reusing the coordinator already on port {port}",
                          occupant)
    raise StartupError(
        "No local address was available.",
        f"Ports {order[0]}–{order[-1]} are all in use by other software"
        + (f" (first conflict on {first_conflict})." if first_conflict else "."),
        {"kind": "retry", "label": "Try again"})


# --------------------------------------------------------------------------
# Model runtime (Ollama)
# --------------------------------------------------------------------------

def find_ollama(which=None) -> str | None:
    """The engine binary on this computer, or None. Never installs anything.

    A bare name goes through `PATH`; anything else is used only when it is an
    absolute path that exists and can be executed. A relative candidate is
    skipped rather than resolved, because resolving one would test the
    directory Refinix was launched from.
    """
    import shutil
    which = which or shutil.which
    for candidate in OLLAMA_BINARIES.get(sys.platform, OLLAMA_BINARIES["linux"]):
        if os.path.isabs(candidate):
            if Path(candidate).is_file() and os.access(candidate, os.X_OK):
                return candidate
        elif os.sep not in candidate and (os.altsep or os.sep) not in candidate:
            found = which(candidate)
            if found:
                return found
    return None


def _detached() -> dict:
    """Start the engine so it outlives the console Refinix was launched from.

    `start_new_session` is POSIX-only; on Windows it is accepted and ignored,
    which left the engine in Refinix's process group where closing a console
    would take it down with the application. The Windows equivalent is a
    detached process in its own group, which also means no console window
    appears.
    """
    if sys.platform == "win32":
        return {"creationflags": (getattr(subprocess, "DETACHED_PROCESS", 0x8)
                                  | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP",
                                            0x200))}
    return {"start_new_session": True}


class EngineSupervisor:
    """Detects the local model runtime, starts it when it is installed, and
    stops only the copy this application started."""

    def __init__(self, *, probe=runtime.probe, locate=find_ollama,
                 spawn=subprocess.Popen, sleep=time.sleep, clock=time.monotonic):
        self._probe = probe
        self._locate = locate
        self._spawn = spawn
        self._sleep = sleep
        self._clock = clock
        self.process = None
        self.owned = False
        self.last = {}

    def ready(self, state: dict) -> bool:
        """Real readiness: the server answered *and* listed its models."""
        return bool(state.get("reachable")) and isinstance(state.get("models"), list) \
            and state.get("error") is None

    def ensure(self, *, budget: float = RUNTIME_START_SECONDS, cancelled=None) -> dict:
        _check_cancelled(cancelled)
        state = self.last = self._probe()
        _check_cancelled(cancelled)
        if self.ready(state):
            state["started_by_refinix"] = False
            return state
        if state.get("reachable"):
            # Answering but not listing models: report it, do not restart a
            # service this application does not own.
            state["started_by_refinix"] = False
            return state

        binary = self._locate()
        if not binary:
            raise StartupError(
                "The AI engine is not installed on this computer.",
                "Refinix does not download or install software. Ollama provides the "
                "local model runtime that ordinary Chat needs.",
                {"kind": "install", "label": "How to install Ollama",
                 "command": INSTALL_HINT})

        try:
            _check_cancelled(cancelled)
            self.process = self._spawn(
                [binary, "serve"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL, env=dict(os.environ), **_detached())
        except OSError as exc:
            raise StartupError(
                "The AI engine would not start.", f"{binary}: {exc}",
                {"kind": "retry", "label": "Try again"}) from exc
        self.owned = True

        deadline = self._clock() + budget
        while self._clock() < deadline:
            _check_cancelled(cancelled)
            if self.process.poll() is not None:
                self.owned = False
                raise StartupError(
                    "The AI engine stopped immediately after starting.",
                    f"{binary} serve exited with code {self.process.returncode}. "
                    "Another copy may already be running under a different account.",
                    {"kind": "retry", "label": "Try again"})
            state = self.last = self._probe()
            _check_cancelled(cancelled)
            if self.ready(state):
                state["started_by_refinix"] = True
                return state
            if cancelled is None:
                self._sleep(0.5)
            else:
                cancelled.wait(0.5)
        raise StartupError(
            "The AI engine did not become ready in time.",
            f"{binary} was started but did not answer within {int(budget)} seconds.",
            {"kind": "retry", "label": "Try again"})

    def stop(self, timeout: float = 5.0) -> bool:
        """Stop the engine only when Refinix started it. Returns True if stopped."""
        if not self.owned or self.process is None:
            return False
        try:
            self.process.terminate()
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()
        except OSError:
            return False
        finally:
            self.owned = False
        return True


def model_status(state: dict, model: str = runtime.MODEL) -> dict:
    """Whether the configured model is installed. Never triggers a download."""
    models = state.get("models") or []
    if not state.get("reachable"):
        return {"state": "unavailable", "model": model, "installed": None,
                "detail": "The AI engine did not answer, so its models are unknown.",
                "action": None}
    # Ollama reports "name:tag"; an exact match is required, no fuzzy fallback.
    if model in models:
        return {"state": "ok", "model": model, "installed": models,
                "detail": "Installed on this computer.", "action": None}
    return {"state": "attention", "model": model, "installed": models,
            "detail": f"{model} is not installed. Refinix does not download models.",
            "action": {"kind": "command", "label": "Download it yourself",
                       "command": f"ollama pull {model}"}}


# --------------------------------------------------------------------------
# The sequence
# --------------------------------------------------------------------------

@dataclass
class Startup:
    """Everything the window needs after a successful start."""

    port: int
    url: str
    reused_coordinator: bool
    engine: dict = field(default_factory=dict)
    model: dict = field(default_factory=dict)
    server: object | None = None
    coordinator: object | None = None
    engine_supervisor: EngineSupervisor | None = None


def run_startup(progress: Progress, *, state_path: Path = STATE_DB,
                preferred_port: int = DEFAULT_PORT, start_server=None,
                supervisor: EngineSupervisor | None = None,
                budget: float = STARTUP_BUDGET_SECONDS,
                clock=time.monotonic, cancelled=None) -> Startup:
    """Bring the local services up, reporting each step as it happens.

    The caller must already hold the SingleInstance lock; that is what the
    `instance` step reports.

    Raises StartupError with a readable message and an action. It never returns
    a half-started state, and never leaves the caller without an answer.
    """
    deadline = clock() + budget
    _check_cancelled(cancelled)
    progress.set("window", "ok", "Window open.")
    # Callers take the SingleInstance lock before reaching here, so arriving at
    # all is the evidence that no other copy holds it.
    progress.set("instance", "ok", "This is the only copy of Refinix running.")

    # Before anything opens the database: two occupied roots have no safe
    # automatic answer, and `docs/PROJECT.md` 12.5 forbids running both at once.
    # Refusing here is what keeps a workspace's chats, approvals and artifacts
    # from being stranded in a store nothing opens again.
    check_data_root(state_path)

    def remaining(minimum=1.0):
        return max(minimum, deadline - clock())

    progress.set("port", "running")
    workspace_id = read_workspace_id(state_path)
    choice = choose_port(preferred_port, workspace_id=workspace_id)
    progress.set("port", "ok", choice.detail)

    progress.set("coordinator", "running")
    server = coordinator = None
    supervisor = supervisor or EngineSupervisor()
    try:
        _check_cancelled(cancelled)
        if choice.reused:
            progress.set("coordinator", "ok",
                         "Reusing the coordinator that is already running.")
        else:
            if start_server is None:
                from backend.coordinator.server import build_server
                start_server = build_server
            try:
                server, coordinator = start_server(state_path, choice.port)
            except OSError as exc:
                raise StartupError("The local coordinator would not start.",
                                   str(exc), {"kind": "retry", "label": "Try again"}) from exc
            progress.set("coordinator", "ok",
                         f"Listening on 127.0.0.1:{choice.port} (this computer only).")

        _check_cancelled(cancelled)
        url = f"http://127.0.0.1:{choice.port}/"
        progress.url = url

        progress.set("engine", "running")
        engine_error = None
        try:
            engine = supervisor.ensure(budget=min(RUNTIME_START_SECONDS, remaining()),
                                       cancelled=cancelled)
        except StartupError as exc:
            supervisor.stop()
            # Chat cannot run without the engine, but the window must still open
            # with a readable explanation instead of a spinner.
            engine = dict(supervisor.last or {})
            engine_error = exc
            progress.set("engine", "attention", f"{exc} {exc.detail}".strip(), exc.action)
        else:
            started = (" Refinix started it." if engine.get("started_by_refinix")
                       else " It was already running.")
            progress.set("engine", "ok",
                         f"Ollama {engine.get('server_version') or 'unknown version'} answered."
                         + started)

        progress.set("model", "running")
        model = model_status(engine)
        progress.set("model", "ok" if model["state"] == "ok" else "attention",
                     model["detail"], model["action"])

        if engine_error is not None or model["state"] != "ok":
            progress.finish("attention",
                            "Refinix is open. Chat needs one more step on this computer.")
        else:
            progress.finish("ready", "Refinix is ready.")

        _check_cancelled(cancelled)
        return Startup(port=choice.port, url=url, reused_coordinator=choice.reused,
                       engine=engine, model=model, server=server,
                       coordinator=coordinator, engine_supervisor=supervisor)
    except BaseException:
        # This listener has not entered serve_forever yet: shutdown() would wait
        # forever. Close it directly and release every resource we created.
        if server is not None:
            server.server_close()
        if coordinator is not None:
            coordinator.conn.close()
        supervisor.stop()
        raise
