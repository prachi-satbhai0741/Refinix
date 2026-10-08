"""Install and restart: replace Refinix.app with a verified update and open it again.

The running app prepares everything it can while it still owns the workspace
(the verified package is expanded beside the installation by
`backend.coordinator.updates`; work is drained, the database is closed and set
aside by `backend.coordinator.recovery`). It then starts this module as a
helper — from a clone of its own, known-good app — and exits. The helper:

    1. waits for the old app to exit and takes the workspace lock;
    2. swaps the new app into the recorded install path in one atomic rename
       and keeps the previous app (hidden, never indexed) for going back;
    3. opens the new app at the recorded path with the recorded data root;
    4. waits for the new app to commit — which it does only once its window
       has loaded — and otherwise stops that app (and only processes provably
       its own), swaps the previous app back and restores the set-aside data,
       keeping the newer files.

Every step is journalled in `<data root>/updates/install-journal.json`, written
only by a process holding the workspace lock. A launch that finds an
unfinished journal and no live helper starts a helper again (`--resume`) before
anything opens the database; the decisions about committing, discarding and
restoring belong to the helper alone. Which data record belongs to which
attempt is decided by the update id, both versions and the data root, so an
earlier update's finished record is never mistaken for the current one.

Processes are stopped only when Refinix provably started them: the
supervised app by its recorded process id, start time, program and bundle;
its engine through `engine.reap_recorded_process`. Any other process running
from the app blocks the replacement and is never signalled.

Three install methods share that journal, supervision, commit and data
recovery (`journal["method"]`; a journal without one is macOS):

    mac-app        the atomic swap above;
    windows-setup  the helper sets `{app}` aside (recording the uninstall
                   registration), runs the verified setup silently inside a
                   kill-on-close job created before the installer's first
                   instruction (`desktop/update_windows.py`), and accepts the
                   result only when every packaged file is present and
                   unchanged. A crash before `install_verified` always goes
                   back, even when the new version's identity file exists;
    deb            the helper asks for the administrator password and root
                   installs the package it admitted earlier
                   (`desktop/deb_root.py`); going back and finishing an
                   interrupted install are root steps too.

Standard library and psutil only; nothing here runs repository scripts.
"""

from __future__ import annotations

import ctypes
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from backend.coordinator import ownership, recovery

JOURNAL = "install-journal.json"
PRE_SWAP = ("ready", "quiescing", "snapshot_taken", "handed_off")
SWAP_STATES = ("swapping", "swapped", "relaunching", "committing", "rolling_back",
               # windows-setup
               "app_setting_aside", "app_set_aside", "installer_starting",
               "installer_running", "installer_exited", "install_verified",
               # deb
               "deb_installing")
WINDOWS_UNDO = ("app_set_aside", "installer_starting", "installer_running",
                "installer_exited")
# Refusals from the root step that come before anything was changed.
DEB_REFUSED = ("busy", "unfinished", "prerequisites", "plan", "changed", "not_authorised",
               "state", "evidence", "not_admitted", "expired", "not_healthy", "package",
               "channel", "not_newer", "bad_request", "not_root", "not_pkexec",
               "not_installed", "usage")
FINAL = ("committed", "cancelled", "discarded", "rolled_back", "blocked")
MAX_RESUMES = 2
OLD_OWNER_SECONDS = 60.0
LOCK_SECONDS = 60.0
COMMIT_SECONDS = 180.0
TERM_SECONDS = 15.0
POLL_SECONDS = 0.25
# Variables a relaunch must carry so the app opens the same data and install root.
CARRIED = ("REFINIX_DATA_ROOT", "REFINIX_TEST_INSTALL_ROOT")
MANUAL = ("Nothing more was changed automatically. Your data and the previous app are "
          "kept in the 'updates' and 'recovery' folders inside Refinix's data folder "
          "({root}). Keep them, and ask for help before removing "
          "updates/install-journal.json.")


class InstallError(RuntimeError):
    pass


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def home(database) -> Path:
    return ownership.canonical_database(database).parent / "updates"


def journal_file(database) -> Path:
    return home(database) / JOURNAL


def attempt_folder(database, update_id: str) -> Path:
    return home(database) / "install" / update_id


def _atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    for attempt in range(20):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            # Windows refuses to replace a file another process has open for a
            # moment (a reader, an indexer); try again briefly.
            if sys.platform != "win32" or attempt == 19:
                raise
            time.sleep(0.1)


def _read(path: Path, *, strict: bool = False) -> dict | None:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        if strict:
            raise InstallError(f"The update journal cannot be read ({path}): {exc}") from exc
        return None
    if strict and not isinstance(value, dict):
        raise InstallError(f"The update journal is not a record ({path}).")
    return value if isinstance(value, dict) else None


def read_journal(database) -> dict | None:
    path = journal_file(database)
    record = _read(path, strict=True)
    if record is None:
        data = _data_journal(database)
        if data is not None and data.get("state") not in recovery.FINAL:
            raise InstallError("The install journal is missing while data recovery is "
                               "unfinished. " + MANUAL.format(root=path.parent.parent))
        return None
    required = ("update_id", "state", "from_version", "to_version", "data_root",
                "install_path", "incoming")
    if (not all(isinstance(record.get(key), str) and record[key] for key in required)
            or record["state"] not in PRE_SWAP + SWAP_STATES + FINAL):
        raise InstallError(f"The install journal is incomplete or invalid ({path}).")
    return record


def write_journal(owner, database, record: dict, **changes) -> dict:
    """Only the owner of the workspace lock writes the install journal."""
    ownership.require(owner, ownership.canonical_database(database))
    record = {**record, **changes, "updated_at": _stamp()}
    _atomic_json(journal_file(database), record)
    return record


def _data_journal(database) -> dict | None:
    """The data recovery journal, read without changing anything."""
    return _read(ownership.canonical_database(database).parent / "recovery"
                 / recovery.JOURNAL, strict=True)


def _same_attempt(first: dict, second: dict) -> bool:
    return all(first.get(key) == second.get(key)
               for key in ("update_id", "from_version", "to_version", "data_root"))


def _matching(rec: recovery.Recovery, journal: dict) -> dict | None:
    return rec.matches(update_id=journal["update_id"],
                       from_version=journal["from_version"],
                       to_version=journal["to_version"],
                       data_root=journal.get("data_root"))


def method_of(journal: dict | None) -> str:
    return (journal or {}).get("method") or "mac-app"


def installed_version(path, method: str = "mac-app") -> str | None:
    """The version of the Refinix installed at `path`, read from its identity."""
    if not path or not Path(path).is_dir():
        return None
    if method == "mac-app":
        from backend.coordinator import app_archive
        identity = app_archive.bundle_identity(Path(path))
    else:
        from desktop import install_check
        identity = install_check.installed_identity(Path(path))
    return identity.get("version") if identity else None


def _installed(journal: dict, path=None) -> str | None:
    return installed_version(path or journal["install_path"], method_of(journal))


HELPER_LAYOUT = {"mac-app": ("Refinix.app", ("Contents", "MacOS", "Refinix")),
                 "windows-setup": ("Refinix", ("Refinix.exe",)),
                 "deb": ("refinix", ("Refinix",))}


def helper_program(folder: Path, method: str) -> Path:
    return Path(folder).joinpath(*HELPER_LAYOUT[method][1])


# --------------------------------------------------------------------------
# Everything that touches processes, renames apps or opens them
# --------------------------------------------------------------------------

class System:
    """The operating-system side of installing; tests replace it."""

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def monotonic(self) -> float:
        return time.monotonic()

    def identity(self, pid: int | None = None) -> dict | None:
        try:
            import psutil
            process = psutil.Process(os.getpid() if pid is None else pid)
            return {"pid": process.pid, "create_time": process.create_time(),
                    "exe": process.exe()}
        except Exception:                                  # noqa: BLE001
            return None

    def same(self, record: dict | None) -> bool:
        """Whether the process `record` names is still that very process."""
        if not record or not record.get("pid"):
            return False
        current = self.identity(int(record["pid"]))
        if current is None:
            return False
        return (abs(current["create_time"] - float(record.get("create_time") or 0)) < 0.01
                and Path(current["exe"]) == Path(record.get("exe") or ""))

    def processes_in(self, bundle) -> list[dict]:
        """This user's processes whose program lies inside `bundle`."""
        import psutil
        root = os.path.realpath(bundle) + os.sep
        found = []
        for process in psutil.process_iter(["pid", "exe", "create_time", "username"]):
            try:
                exe = process.info.get("exe")
                if exe and os.path.realpath(exe).startswith(root):
                    found.append({"pid": process.info["pid"], "exe": exe,
                                  "create_time": process.info["create_time"]})
            except Exception:                              # noqa: BLE001
                continue
        return found

    def terminate(self, record: dict, grace: float) -> bool:
        """Stop exactly the recorded process: asked first, then forced. True when gone."""
        import psutil
        for forced in (False, True):
            if not self.same(record):
                return True
            try:
                process = psutil.Process(int(record["pid"]))
                if sys.platform == "win32":
                    process.kill() if forced else process.terminate()
                else:
                    process.send_signal(signal.SIGKILL if forced else signal.SIGTERM)
            except psutil.NoSuchProcess:
                return True
            except Exception:                              # noqa: BLE001
                return False
            deadline = self.monotonic() + grace
            while self.monotonic() < deadline and self.same(record):
                self.sleep(POLL_SECONDS)
        return not self.same(record)

    def reap_engine(self, record_path: Path) -> None:
        from backend.coordinator import engine
        engine.reap_recorded_process(record_path)

    def swap(self, first: Path, second: Path) -> None:
        """Exchange two paths in one step (APFS `renamex_np(RENAME_SWAP)`)."""
        libc = ctypes.CDLL(None, use_errno=True)
        function = libc.renamex_np
        function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        if function(os.fsencode(first), os.fsencode(second), 0x2) != 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error), str(first))

    def clone(self, source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            function = libc.clonefile
            function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
            if function(os.fsencode(source), os.fsencode(target), 0) == 0:
                return
        except (AttributeError, OSError):
            pass
        shutil.copytree(source, target, symlinks=True)

    def spawn(self, argv: list[str], environment: dict, log: Path) -> dict | None:
        log.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        env = {key: value for key, value in os.environ.items()
               if key not in CARRIED}
        env.update(environment)
        with open(log, "ab") as handle:
            process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=handle,
                                       stderr=handle, close_fds=True,
                                       start_new_session=True, env=env)
        return self.identity(process.pid) or {"pid": process.pid}

    def open_app(self, path: Path, environment: dict) -> None:
        if sys.platform == "win32":
            from desktop import update_windows
            update_windows.open_program(Path(path) / "Refinix.exe", environment)
            return
        if sys.platform.startswith("linux"):
            env = {key: value for key, value in os.environ.items() if key not in CARRIED}
            env.update(environment)
            subprocess.Popen([str(Path(path) / "Refinix")], env=env, close_fds=True,
                             start_new_session=True, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        argv = ["/usr/bin/open"]
        for key, value in sorted(environment.items()):
            argv += ["--env", f"{key}={value}"]
        subprocess.run(argv + [str(path)], check=False, timeout=60,
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)

    # -- windows-setup -------------------------------------------------------
    def rename(self, source: Path, target: Path) -> None:
        Path(target).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.rename(source, target)

    def make_job(self):
        from desktop import update_windows
        return update_windows.Job()

    def run_installer(self, setup: Path, app: Path, log: Path, job, record) -> int | None:
        from desktop import update_windows
        return update_windows.run_installer(setup, app, log, job=job, record=record)

    def registry_snapshot(self) -> dict | None:
        from desktop import update_windows
        return update_windows.registry_snapshot()

    def registry_restore(self, snapshot: dict | None) -> None:
        from desktop import update_windows
        update_windows.registry_restore(snapshot)

    def windows_problem(self, app: Path, version: str) -> str | None:
        from desktop import update_windows
        return (update_windows.completeness_problem(app, version)
                or update_windows.registration_problem(self.registry_snapshot(), version,
                                                       app))

    # -- deb -----------------------------------------------------------------
    def privileged(self, mode: str, folder: Path) -> dict:
        from backend.coordinator import install_methods
        try:
            return install_methods.run_privileged(mode, folder)
        except install_methods.MethodError as exc:
            return {"error": str(exc), "code": exc.code}

    def deb_problem(self, version: str) -> str | None:
        """Why /opt/refinix is not exactly `version`, checked as the person."""
        from backend.coordinator import install_methods, release
        from desktop import install_check
        installed = install_methods.installed_deb_version()
        if installed != release.parse(version).debian():
            return f"Ubuntu records version {installed or 'none'}"
        return install_check.completeness_problem(install_methods.DEB_PREFIX, version)

    def verify_incoming(self, app: Path, journal: dict) -> None:
        from backend.coordinator import app_archive
        app_archive.verify_bundle(app, version=journal["to_version"], lane=journal["lane"],
                                  channel=journal["channel"],
                                  trust_roots=journal.get("trust_roots")
                                  or [journal.get("trust_root")],
                                  publisher=journal.get("publisher"))

    def tell(self, title: str, text: str) -> None:
        """A message for the person, without waiting for it to be read."""
        if sys.platform == "darwin":
            script = (f'display dialog {json.dumps(text)} with title {json.dumps(title)} '
                      'buttons {"OK"} default button "OK" with icon caution')
            argv = ["/usr/bin/osascript", "-e", script]
        elif sys.platform == "win32":
            argv = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                    "Add-Type -AssemblyName PresentationFramework; "
                    "[System.Windows.MessageBox]::Show($env:REFINIX_TEXT, $env:REFINIX_TITLE)"]
        else:
            zenity = shutil.which("zenity")
            if not zenity:
                print(f"{title}: {text}", file=sys.stderr)
                return
            argv = [zenity, "--warning", "--title", title, "--text", text, "--no-markup"]
        try:
            subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True,
                             env=dict(os.environ, REFINIX_TEXT=text, REFINIX_TITLE=title))
        except OSError:
            pass


# --------------------------------------------------------------------------
# The running app's side (it holds the workspace lock throughout)
# --------------------------------------------------------------------------

def plan_attempt(owner, database, *, update_id: str, from_version: str, to_version: str,
                 install_path: Path, incoming: Path, lane: str, channel: str,
                 trust_root: str | None, environment: dict,
                 system: System | None = None, method: str = "mac-app",
                 extra: dict | None = None) -> dict:
    """Record the attempt before anything changes. Refuses over an unfinished one."""
    system = system or System()
    ownership.require(owner, ownership.canonical_database(database))
    current = read_journal(database)
    if current and (current.get("state") not in FINAL or system.same(current.get("helper"))):
        raise InstallError("Another update is still being finished.")
    if current:
        if current["state"] == "committed":
            _succeeded(owner, database, current)
        history = home(database) / "history"
        history.mkdir(parents=True, exist_ok=True, mode=0o700)
        _atomic_json(history / f"install-journal-{current.get('update_id')}.json", current)
    data_root = str(ownership.canonical_database(database).parent)
    return write_journal(owner, database, {
        "update_id": update_id, "state": "quiescing", "from_version": from_version,
        "to_version": to_version, "install_path": str(install_path),
        "incoming": str(incoming), "lane": lane, "channel": channel,
        "trust_root": trust_root, "data_root": data_root, "method": method,
        "environment": dict(environment), "old_process": system.identity(),
        "resume_count": 0, "started_at": _stamp(), **(extra or {})})


def mark(owner, database, journal: dict, state: str, **extra) -> dict:
    return write_journal(owner, database, journal, state=state, **extra)


def hand_off(owner, database, journal: dict, *, bundle: Path, mode: str = "--apply-update",
             system: System | None = None) -> dict:
    """Start the helper from a clone of this (known-good) app, then let this app exit."""
    system = system or System()
    attempt = attempt_folder(database, journal["update_id"])
    method = method_of(journal)
    clone = attempt / "helper" / HELPER_LAYOUT[method][0]
    if not clone.exists():
        system.clone(Path(bundle), clone)
    executable = helper_program(clone, method)
    helper = system.spawn([str(executable), mode, str(ownership.canonical_database(database))],
                          journal.get("environment") or {}, attempt / "helper.log")
    state = "handed_off" if mode == "--apply-update" else journal["state"]
    return write_journal(owner, database, journal, state=state, helper=helper,
                         helper_bundle=str(clone))


def cancel_attempt(owner, database, journal: dict, reason: str) -> dict:
    """Before any data was set aside: close the attempt; nothing changed."""
    data = _data_journal(database)
    if data and data.get("update_id") == journal["update_id"]:
        raise InstallError("This attempt has kept data; the helper must finish it.")
    return write_journal(owner, database, journal, state="cancelled", reason=reason,
                         reported=False)


# --------------------------------------------------------------------------
# A launch, before anything opens the database
# --------------------------------------------------------------------------

@dataclass
class Gate:
    proceed: bool = True
    supervised: dict | None = None
    message: str | None = None
    notice: dict | None = None
    details: dict = field(default_factory=dict)


def _notice(journal: dict, running: str) -> dict | None:
    state = journal.get("state")
    if state == "committed" and running == journal.get("to_version"):
        return {"kind": "updated", "from": journal.get("from_version"),
                "to": journal.get("to_version")}
    if state == "rolled_back":
        return {"kind": "rolled_back", "to": journal.get("to_version"),
                "detail": f"The update to {journal.get('to_version')} did not complete: "
                          f"{journal.get('reason') or 'it did not start correctly'}. "
                          f"Version {journal.get('from_version')} and your data were "
                          "restored; nothing was deleted, and anything the newer version "
                          "wrote is kept in the recovery folder."}
    if state in ("cancelled", "discarded"):
        return {"kind": "not_installed", "to": journal.get("to_version"),
                "detail": f"The update to {journal.get('to_version')} was not installed: "
                          f"{journal.get('reason') or 'it stopped before anything changed'}. "
                          "Nothing was changed."}
    return None


def on_launch(owner, database, running_version: str, *, bundle: Path | None = None,
              system: System | None = None) -> Gate:
    """What this launch may do about an install journal, before admission."""
    system = system or System()
    journal = read_journal(database)
    if journal is None:
        return Gate()
    state = journal.get("state")
    root = str(ownership.canonical_database(database).parent)
    if state == "blocked":
        return Gate(proceed=False, message=(
            f"An update to Refinix {journal.get('to_version')} stopped safely before it "
            f"could finish: {journal.get('reason') or 'the reason was not recorded'}. "
            + MANUAL.format(root=root)))
    if state in FINAL:
        if state == "committed":
            _succeeded(owner, database, journal)
        gate = Gate()
        if not journal.get("reported"):
            gate.notice = _notice(journal, running_version)
            write_journal(owner, database, journal, reported=True)
        _sweep(database, journal, system)
        return gate
    if system.same(journal.get("helper")):
        if (state == "relaunching" and running_version == journal.get("to_version")
                and os.path.realpath(journal.get("data_root") or "") == os.path.realpath(root)):
            app = {**(system.identity() or {}), "bundle": str(bundle) if bundle else None,
                   "version": running_version}
            _atomic_json(attempt_folder(database, journal["update_id"]) / "app.json", app)
            return Gate(supervised=journal)
        return Gate(proceed=False)
    count = int(journal.get("resume_count") or 0)
    if count >= MAX_RESUMES:
        journal = write_journal(owner, database, journal, state="blocked",
                                reason="the update helper stopped before finishing, twice")
        return Gate(proceed=False, message=(
            "An update to Refinix stopped safely before it could finish. "
            + MANUAL.format(root=root)))
    journal = write_journal(owner, database, journal, resume_count=count + 1)
    source = _helper_source(database, journal, bundle)
    if source is None:
        write_journal(owner, database, journal, state="blocked",
                      reason="no copy of Refinix was available to finish the update")
        return Gate(proceed=False, message="An update to Refinix stopped safely. "
                                           + MANUAL.format(root=root))
    hand_off(owner, database, journal, bundle=source, mode="--resume", system=system)
    return Gate(proceed=False)


def _helper_source(database, journal: dict, bundle: Path | None) -> Path | None:
    method = method_of(journal)
    for candidate in (journal.get("helper_bundle"), journal.get("previous_app"),
                      str(bundle) if bundle else None):
        if candidate and helper_program(Path(candidate), method).is_file():
            return Path(candidate)
    return None


def commit_if_supervised(owner, database, supervised: dict) -> dict | None:
    """The new version's window has loaded: finish the update, unless the helper gave up."""
    journal = read_journal(database)
    if not journal or journal.get("update_id") != supervised.get("update_id") \
            or journal.get("state") != "relaunching":
        return None
    if (attempt_folder(database, journal["update_id"]) / "abort").exists():
        return None
    rec = recovery.Recovery(owner, database)
    if _matching(rec, journal) is None:
        return None
    journal = write_journal(owner, database, journal, state="committing")
    rec.commit(journal["update_id"])
    _succeeded(owner, database, journal)
    journal = write_journal(owner, database, journal, state="committed",
                            committed_at=_stamp(), reported=True)
    return journal


# --------------------------------------------------------------------------
# The helper
# --------------------------------------------------------------------------

def _status(database, journal: dict | None, state: str, **extra) -> None:
    if not journal:
        return
    _atomic_json(attempt_folder(database, journal["update_id"]) / "helper.json",
                 {"state": state, "at": _stamp(), "pid": os.getpid(), **extra})


def _wait(condition, seconds: float, system: System) -> bool:
    deadline = system.monotonic() + seconds
    while True:
        if condition():
            return True
        if system.monotonic() >= deadline:
            return False
        system.sleep(POLL_SECONDS)


def _take_lock(database, system: System, seconds: float = LOCK_SECONDS,
                *, expected: dict | None = None):
    """The workspace lock, for the helper; it then records itself as the live helper."""
    lock = ownership.WorkspaceLock.for_database(ownership.canonical_database(database))
    if not _wait(lambda: lock.acquire() is None, seconds, system):
        return None
    lock.record(mode="update-helper")
    try:
        journal = read_journal(database)
        if expected is not None and not _same_attempt(journal or {}, expected):
            raise InstallError("This helper's update is no longer the current attempt.")
    except Exception:
        lock.release()
        raise
    me = system.identity()
    if journal and journal.get("state") not in FINAL and me \
            and journal.get("helper") != me:
        write_journal(lock, database, journal, helper=me)
    return lock


def helper_main(argv: list[str], system: System | None = None) -> int:
    """`Refinix --apply-update|--resume <database>`: run as the update helper."""
    system = system or System()
    if len(argv) != 2 or argv[0] not in ("--apply-update", "--resume"):
        print("usage: Refinix --apply-update|--resume <database>", file=sys.stderr)
        return 64
    database = ownership.canonical_database(Path(argv[1]))
    journal = read_journal(database)
    if journal is None:
        return 0
    _status(database, journal, "started", mode=argv[0])
    try:
        if argv[0] == "--apply-update" and journal.get("state") == "handed_off":
            return _apply(database, journal, system)
        lock = _take_lock(database, system, expected=journal)
        if lock is None:
            _status(database, journal, "lock_timeout")
            return 1
        return _drive(lock, database, system)
    except Exception as exc:                               # noqa: BLE001
        _status(database, journal, "error", error=f"{type(exc).__name__}: {exc}")
        raise


def _apply(database, journal: dict, system: System) -> int:
    if not _wait(lambda: not system.same(journal.get("old_process")), OLD_OWNER_SECONDS,
                 system):
        # Without the lock nothing protected is touched; the next launch resumes.
        _status(database, journal, "old_owner_timeout")
        return 1
    lock = _take_lock(database, system, expected=journal)
    if lock is None:
        _status(database, journal, "lock_timeout")
        return 1
    journal = read_journal(database)
    rec = recovery.Recovery(lock, database)
    data = _current_data(rec, journal)
    install = Path(journal["install_path"])
    if not (journal["state"] == "handed_off" and data and data["state"] == "set_aside"
            and _installed(journal) == journal["from_version"]):
        return _drive(lock, database, system)
    foreign = system.processes_in(install)
    if foreign:
        where = "Refinix.app" if method_of(journal) == "mac-app" else str(install)
        return _not_installed(lock, database, journal, rec, system,
                              f"another program is running from {where} (process "
                              f"{foreign[0]['pid']}); quit it and try again")
    if method_of(journal) == "windows-setup":
        return _apply_windows(lock, database, journal, rec, system)
    if method_of(journal) == "deb":
        return _apply_deb(lock, database, journal, rec, system)
    try:
        system.verify_incoming(Path(journal["incoming"]), journal)
    except Exception as exc:                               # noqa: BLE001
        return _not_installed(lock, database, journal, rec, system,
                              f"the new version did not verify: {exc}")
    journal = write_journal(lock, database, journal, state="swapping")
    system.swap(Path(journal["incoming"]), install)
    journal = write_journal(lock, database, journal, state="swapped")
    return _relaunch_new(lock, database, journal, system)


def _not_installed(lock, database, journal, rec, system, reason: str) -> int:
    """Before the swap: release the kept copy (data unchanged) and reopen the old app."""
    try:
        rec.discard(journal["update_id"])
    except recovery.RecoveryError as exc:
        return _block(lock, database, journal, system, f"{reason}; and {exc}")
    journal = write_journal(lock, database, journal, state="discarded", reason=reason,
                            reported=False)
    _status(database, journal, "not_installed", reason=reason)
    _drop_incoming(journal)
    lock.release()
    system.open_app(Path(journal["install_path"]), journal.get("environment") or {})
    return 0


def _drop_incoming(journal: dict) -> None:
    """The expanded new app of an attempt that will not be installed."""
    incoming = Path(journal.get("incoming") or "")
    if incoming.name == "Refinix.app" and incoming.is_dir() and not incoming.is_symlink():
        shutil.rmtree(incoming, ignore_errors=True)


def _current_data(rec: recovery.Recovery, journal: dict) -> dict | None:
    """This attempt's data record, after finishing any interrupted copy."""
    data = _matching(rec, journal)
    if data and data.get("state") in ("setting_aside", "restoring"):
        rec.resume()
        data = _matching(rec, journal)
    return data


def _previous_path(database, journal: dict) -> Path:
    return home(database) / "previous" / f"{journal['from_version']}-{journal['update_id']}" \
        / HELPER_LAYOUT[method_of(journal)][0]


def _relaunch_new(lock, database, journal: dict, system: System) -> int:
    """After the swap: keep the previous app aside, open the new one and supervise it."""
    previous = journal.get("previous_app")
    if method_of(journal) == "mac-app":
        # After the swap the expanded folder holds the previous app.
        incoming = Path(journal["incoming"])
        previous = _previous_path(database, journal)
        if incoming.exists() and not previous.exists():
            previous.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            (home(database) / "previous" / ".metadata_never_index").touch(exist_ok=True)
            os.replace(incoming, previous)
        previous = str(previous)
    journal = write_journal(lock, database, journal, state="relaunching",
                            previous_app=previous, relaunched_at=_stamp())
    (attempt_folder(database, journal["update_id"]) / "app.json").unlink(missing_ok=True)
    lock.release()
    system.open_app(Path(journal["install_path"]), journal.get("environment") or {})
    return _supervise(database, journal, system)


def _committed(database, journal: dict) -> bool:
    data = _data_journal(database) or {}
    current = read_journal(database) or {}
    return ((_same_attempt(data, journal) and data.get("state") == "committed")
            or (_same_attempt(current, journal) and current.get("state") == "committed"))


def _supervise(database, journal: dict, system: System) -> int:
    attempt = attempt_folder(database, journal["update_id"])
    app = None
    deadline = system.monotonic() + COMMIT_SECONDS
    while system.monotonic() < deadline:
        if not _same_attempt(read_journal(database) or {}, journal):
            return 0
        if _committed(database, journal):
            _status(database, journal, "done")
            return 0
        app = _read(attempt / "app.json") or app
        if app and not system.same(app):
            if _committed(database, journal):
                _status(database, journal, "done")
                return 0
            break
        system.sleep(POLL_SECONDS)
    return _give_up(database, journal, app, system,
                    "the new version did not start correctly" if app else
                    "the new version did not open in time")


def _give_up(database, journal: dict, app: dict | None, system: System, reason: str) -> int:
    if not _same_attempt(read_journal(database) or {}, journal):
        return 0
    if _committed(database, journal):
        _status(database, journal, "done")
        return 0
    attempt = attempt_folder(database, journal["update_id"])
    attempt.mkdir(parents=True, exist_ok=True, mode=0o700)
    (attempt / "abort").write_text(_stamp(), encoding="utf-8")
    if app and system.same(app):
        if Path(os.path.realpath(app.get("exe") or "")).is_relative_to(
                os.path.realpath(journal["install_path"])):
            system.terminate(app, TERM_SECONDS)
    problem = None
    try:
        system.reap_engine(Path(journal["data_root"]) / "engine" / "engine-process.json")
    except Exception as exc:                               # noqa: BLE001
        problem = str(exc)
    lock = _take_lock(database, system, expected=journal)
    if lock is None:
        _status(database, journal, "lock_timeout")
        return 1
    journal = read_journal(database)
    if _committed(database, journal) or journal.get("state") == "committing":
        return _finish_commit(lock, database, journal, system)
    foreign = system.processes_in(Path(journal["install_path"]))
    if foreign or problem:
        return _block(lock, database, journal, system,
                      f"{reason}, and " + (problem or
                                           f"another program (process {foreign[0]['pid']}) "
                                           "is still running from Refinix.app"))
    journal = write_journal(lock, database, journal, state="rolling_back", reason=reason)
    rec = recovery.Recovery(lock, database)
    return _roll_back(lock, database, journal, rec, system)


def _finish_commit(lock, database, journal: dict, system: System) -> int:
    rec = recovery.Recovery(lock, database)
    data = _current_data(rec, journal)
    if _new_problem(journal, system):
        return _block(lock, database, journal, system, "the update was finished but the "
                      "installed app is not the new version")
    if data and data["state"] in ("set_aside", "verifying"):
        rec.commit(journal["update_id"])
    elif not (data and data["state"] == "committed"):
        return _block(lock, database, journal, system, "the update's data record is "
                      "missing or belongs to another update")
    journal = write_journal(lock, database, journal, state="committing")
    _succeeded(lock, database, journal)
    journal = write_journal(lock, database, journal, state="committed",
                            committed_at=_stamp(), reported=False)
    (attempt_folder(database, journal["update_id"]) / "abort").unlink(missing_ok=True)
    lock.release()
    system.open_app(Path(journal["install_path"]), journal.get("environment") or {})
    return 0


def _roll_back(lock, database, journal: dict, rec: recovery.Recovery, system: System) -> int:
    install = Path(journal["install_path"])
    journal, problem = _restore_app(lock, database, journal, system)
    if problem:
        return _block(lock, database, journal, system, problem)
    data = _current_data(rec, journal)
    if data is None:
        return _block(lock, database, journal, system, "the update's data record is "
                      "missing or belongs to another update")
    if data["state"] in ("set_aside", "verifying"):
        data = rec.restore()
    if data["state"] == "recovery_blocked":
        return _block(lock, database, journal, system,
                      f"the data could not be restored safely: {data.get('blocked')}")
    if data["state"] != "rolled_back_with_data":
        return _block(lock, database, journal, system,
                      f"the kept data is in an unexpected state ({data['state']})")
    journal = write_journal(lock, database, journal, state="rolled_back", reported=False,
                            rolled_back_at=_stamp())
    _status(database, journal, "rolled_back", reason=journal.get("reason"))
    lock.release()
    system.open_app(install, journal.get("environment") or {})
    return 0


def _block(lock, database, journal: dict, system: System, reason: str) -> int:
    """Stop safely: record why, change nothing more, open nothing."""
    try:
        rec = recovery.Recovery(lock, database)
        data = _matching(rec, journal)
        if data and data.get("state") not in recovery.FINAL + ("recovery_blocked",):
            rec.block(reason)
    except recovery.RecoveryError:
        pass
    write_journal(lock, database, journal, state="blocked", reason=reason)
    _status(database, journal, "blocked", reason=reason)
    lock.release()
    system.tell("Refinix update stopped safely",
                f"The update to Refinix {journal.get('to_version')} stopped safely: "
                f"{reason}. " + MANUAL.format(root=journal.get("data_root")))
    return 2


def _drive(lock, database, system: System) -> int:
    """Resume an interrupted attempt from what is on disk, under the lock.

    Rules, in order: a committed (or committing) attempt is finished; a
    rollback in progress is continued; before the swap, with the old app
    intact, an attempt without its own data record is cancelled and one with a
    completed, unchanged set-aside copy is discarded; after the swap began,
    missing or mismatched evidence blocks, and otherwise the new app is opened
    and supervised again.
    """
    journal = read_journal(database)
    if journal is None or journal.get("state") in FINAL:
        lock.release()
        if journal and journal.get("state") != "blocked":
            system.open_app(Path(journal["install_path"]), journal.get("environment") or {})
        return 0
    rec = recovery.Recovery(lock, database)
    data = _current_data(rec, journal)
    state = journal["state"]
    installed = _installed(journal)
    if (data and data["state"] == "committed") or state == "committing":
        return _finish_commit(lock, database, journal, system)
    if state == "rolling_back":
        return _roll_back(lock, database, journal, rec, system)
    if method_of(journal) == "windows-setup":
        return _drive_windows(lock, database, journal, rec, data, system)
    if method_of(journal) == "deb":
        return _drive_deb(lock, database, journal, rec, data, system)
    if state in PRE_SWAP + ("swapping",) and installed == journal["from_version"]:
        return _pre_swap(lock, database, journal, rec, data, system)
    return _drive_mac(lock, database, journal, rec, data, system)


def _pre_swap(lock, database, journal: dict, rec, data, system: System) -> int:
    """Nothing of the app was replaced: close the attempt and reopen the old app."""
    install = Path(journal["install_path"])
    if data is None:
        journal = write_journal(lock, database, journal, state="cancelled", reported=False,
                                reason="it stopped before Refinix's data was set aside")
        _drop_incoming(journal)
        lock.release()
        system.open_app(install, journal.get("environment") or {})
        return 0
    if data["state"] in ("set_aside", "verifying"):
        return _not_installed(lock, database, journal, rec, system,
                              "it stopped before the app was replaced")
    if data["state"] == "discarded":
        journal = write_journal(lock, database, journal, state="discarded",
                                reported=False, reason="it stopped before the app "
                                                       "was replaced")
        lock.release()
        system.open_app(install, journal.get("environment") or {})
        return 0
    return _block(lock, database, journal, system,
                  f"the kept data is in an unexpected state ({data['state']})")


def _drive_mac(lock, database, journal: dict, rec, data, system: System) -> int:
    install = Path(journal["install_path"])
    installed = _installed(journal)
    if data is None:
        return _block(lock, database, journal, system, "the app was being replaced but "
                      "the update's data record is missing or belongs to another update")
    if installed == journal["to_version"]:
        journal = write_journal(lock, database, journal, state="swapped",
                                resume_round=int(journal.get("resume_round") or 0) + 1)
        return _relaunch_new(lock, database, journal, system)
    previous = Path(journal.get("previous_app") or _previous_path(database, journal))
    if installed is None and _installed(journal, previous) == journal["from_version"]:
        if install.exists() or install.is_symlink():
            aside = attempt_folder(database, journal["update_id"]) / "damaged" / "Refinix.app"
            aside.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.replace(install, aside)
        os.replace(previous, install)
        journal = write_journal(lock, database, journal, state="rolling_back",
                                apps_restored=True,
                                reason="the installed app was missing or damaged")
        return _roll_back(lock, database, journal, rec, system)
    return _block(lock, database, journal, system, "the installed app is not a version "
                  "this update knows")


# --------------------------------------------------------------------------
# What each install method checks and restores
# --------------------------------------------------------------------------

def _new_problem(journal: dict, system: System) -> str | None:
    """Why the new version is not completely installed; None when it is."""
    method, to = method_of(journal), journal["to_version"]
    if method == "windows-setup":
        return system.windows_problem(Path(journal["install_path"]), to)
    if method == "deb":
        return system.deb_problem(to)
    installed = _installed(journal)
    return None if installed == to else f"the installed version is {installed}"


def _restore_app(lock, database, journal: dict, system: System) -> tuple[dict, str | None]:
    """Put the previous version back; (journal, why not) — None when it is back."""
    method = method_of(journal)
    install = Path(journal["install_path"])
    if method == "deb":
        if system.deb_problem(journal["from_version"]) is None:
            return journal, None
        answer = system.privileged("--deb-rollback", Path(journal["incoming"]))
        if answer.get("state") == "from":
            return write_journal(lock, database, journal, apps_restored=True), None
        detail = answer.get("problem") or answer.get("error") or "it did not finish"
        if answer.get("recovery_package"):
            detail += (f". Reinstall {answer['recovery_package']} (SHA-256 "
                       f"{answer.get('recovery_sha256')}) with App Center, or the same "
                       "version from the Refinix website, then open Refinix")
        return journal, f"the previous package could not be reinstalled: {detail}"
    previous = Path(journal.get("previous_app") or _previous_path(database, journal))
    if method == "windows-setup":
        if previous.exists():
            if install.exists():
                damaged = attempt_folder(database, journal["update_id"]) / "damaged"
                damaged = damaged / f"Refinix-{_stamp().replace(':', '')}"
                system.rename(install, damaged)
            system.rename(previous, install)
        if _installed(journal) != journal["from_version"]:
            return journal, "the previous version is not where it was kept"
        system.registry_restore(journal.get("registry"))
        return write_journal(lock, database, journal, apps_restored=True), None
    installed = _installed(journal)
    if installed == journal["to_version"]:
        if _installed(journal, previous) != journal["from_version"]:
            return journal, "the previous version is not where it was kept"
        system.swap(previous, install)
        journal = write_journal(lock, database, journal, apps_restored=True)
    elif installed != journal["from_version"]:
        return journal, "the installed app is neither the previous nor the new version"
    return journal, None


# -- windows-setup ------------------------------------------------------------

def _sha256(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _apply_windows(lock, database, journal: dict, rec, system: System) -> int:
    """Set {app} aside, run the setup inside the job, accept only a complete install."""
    install, setup = Path(journal["install_path"]), Path(journal["incoming"])
    try:
        intact = _sha256(setup) == journal.get("installer_sha256")
    except OSError:
        intact = False
    if not intact:
        return _not_installed(lock, database, journal, rec, system,
                              "the prepared setup program changed")
    previous = _previous_path(database, journal)
    journal = write_journal(lock, database, journal, state="app_setting_aside",
                            registry=system.registry_snapshot(), previous_app=str(previous))
    try:
        job = system.make_job()
    except Exception as exc:                               # noqa: BLE001
        return _not_installed(lock, database, journal, rec, system,
                              f"the setup program could not be contained ({exc})")
    reason = None
    try:
        try:
            (home(database) / "previous").mkdir(parents=True, exist_ok=True, mode=0o700)
            system.rename(install, previous)
        except OSError as exc:
            return _not_installed(lock, database, journal, rec, system,
                                  f"the current version could not be set aside ({exc})")
        journal = write_journal(lock, database, journal, state="app_set_aside")
        log = attempt_folder(database, journal["update_id"]) / "setup.log"
        journal = write_journal(lock, database, journal, state="installer_starting",
                                installer_log=str(log))
        holder = {"journal": journal}

        def started(info: dict) -> None:
            holder["journal"] = write_journal(lock, database, holder["journal"],
                                              state="installer_running", installer=info)
        try:
            code = system.run_installer(setup, install, log, job, started)
        except Exception as exc:                           # noqa: BLE001
            code, reason = None, f"the setup program could not run ({exc})"
        journal = holder["journal"]
    finally:
        job.close()
    journal = write_journal(lock, database, journal, state="installer_exited",
                            installer_exit=code)
    if code != 0:
        reason = reason or ("the setup program did not finish in time" if code is None
                            else f"the setup program failed (exit code {code})")
        return _windows_undo(lock, database, journal, rec, system, reason)
    problem = system.windows_problem(install, journal["to_version"])
    if problem:
        return _windows_undo(lock, database, journal, rec, system,
                             f"the new version was not completely installed: {problem}")
    journal = write_journal(lock, database, journal, state="install_verified")
    journal = write_journal(lock, database, journal, state="swapped")
    return _relaunch_new(lock, database, journal, system)


def _windows_undo(lock, database, journal: dict, rec, system: System, reason: str) -> int:
    """The new version never ran: put the app and its registration back."""
    journal, problem = _restore_app(lock, database, journal, system)
    if problem:
        return _block(lock, database, journal, system, f"{reason}; and {problem}")
    return _not_installed(lock, database, journal, rec, system, reason)


def _drive_windows(lock, database, journal: dict, rec, data, system: System) -> int:
    state = journal["state"]
    install = Path(journal["install_path"])
    previous = Path(journal.get("previous_app") or _previous_path(database, journal))
    if state in PRE_SWAP or state == "app_setting_aside":
        if _installed(journal) == journal["from_version"] and not previous.exists():
            return _pre_swap(lock, database, journal, rec, data, system)
        if _installed(journal, previous) == journal["from_version"]:
            journal, problem = _restore_app(lock, database, journal, system)
            if problem:
                return _block(lock, database, journal, system, problem)
            return _pre_swap(lock, database, journal, rec, data, system)
        return _block(lock, database, journal, system, "the installed app is not a version "
                      "this update knows")
    if data is None:
        return _block(lock, database, journal, system, "the app was being replaced but "
                      "the update's data record is missing or belongs to another update")
    if state in WINDOWS_UNDO:
        # The helper stopped while the setup ran; its job ended the setup with
        # it. Whatever the setup wrote is not trusted, even a new identity file.
        return _windows_undo(lock, database, journal, rec, system,
                             "the update stopped while the setup program was running")
    if state in ("install_verified", "swapped", "relaunching"):
        problem = system.windows_problem(install, journal["to_version"])
        if problem is None:
            journal = write_journal(lock, database, journal, state="swapped",
                                    resume_round=int(journal.get("resume_round") or 0) + 1)
            return _relaunch_new(lock, database, journal, system)
        journal = write_journal(lock, database, journal, state="rolling_back",
                                reason=f"the new version is incomplete: {problem}")
        return _roll_back(lock, database, journal, rec, system)
    return _block(lock, database, journal, system, f"the update stopped in an unexpected "
                  f"state ({state})")


# -- deb ---------------------------------------------------------------------

def _apply_deb(lock, database, journal: dict, rec, system: System) -> int:
    """Root installs the package it admitted; this helper only asks and watches."""
    journal = write_journal(lock, database, journal, state="deb_installing")
    answer = system.privileged("--deb-install", Path(journal["incoming"]))
    if answer.get("error"):
        if answer.get("code") in DEB_REFUSED and \
                system.deb_problem(journal["from_version"]) is None:
            return _not_installed(lock, database, journal, rec, system, answer["error"])
        return _deb_resume(lock, database, journal, rec, system)
    if answer.get("state") == "to":
        journal = write_journal(lock, database, journal, state="swapped")
        return _relaunch_new(lock, database, journal, system)
    return _deb_back(lock, database, journal, rec, system,
                     answer.get("problem") or "the package did not install completely")


def _deb_resume(lock, database, journal: dict, rec, system: System) -> int:
    """Ask root to finish or undo what an interrupted install left."""
    answer = system.privileged("--deb-recover", Path(journal["incoming"]))
    state = answer.get("state")
    if state == "to":
        journal = write_journal(lock, database, journal, state="swapped",
                                resume_round=int(journal.get("resume_round") or 0) + 1)
        return _relaunch_new(lock, database, journal, system)
    if state == "from":
        return _not_installed(lock, database, journal, rec, system,
                              "the package install was interrupted and the previous "
                              "version is installed")
    if state == "incomplete":
        return _deb_back(lock, database, journal, rec, system,
                         answer.get("problem") or "the package did not install completely")
    if answer.get("code") == "not_authorised":
        # Nothing was decided: the next launch asks again.
        _status(database, journal, "needs_password")
        lock.release()
        system.tell("Refinix update needs your password",
                    "An update to Refinix did not finish. Open Refinix again and give "
                    "the administrator password to finish or undo it.")
        return 1
    return _block(lock, database, journal, system,
                  answer.get("problem") or answer.get("error") or "recovery did not finish")


def _deb_back(lock, database, journal: dict, rec, system: System, reason: str) -> int:
    """The new version never opened: reinstall the previous package, data unchanged."""
    journal, problem = _restore_app(lock, database, journal, system)
    if problem:
        return _block(lock, database, journal, system, f"{reason}; and {problem}")
    return _not_installed(lock, database, journal, rec, system, reason)


def _drive_deb(lock, database, journal: dict, rec, data, system: System) -> int:
    state = journal["state"]
    if state in PRE_SWAP:
        if system.deb_problem(journal["from_version"]) is None:
            return _pre_swap(lock, database, journal, rec, data, system)
        return _deb_resume(lock, database, journal, rec, system)
    if data is None:
        return _block(lock, database, journal, system, "the app was being replaced but "
                      "the update's data record is missing or belongs to another update")
    if state == "deb_installing":
        return _deb_resume(lock, database, journal, rec, system)
    if state in ("swapped", "relaunching"):
        if system.deb_problem(journal["to_version"]) is None:
            journal = write_journal(lock, database, journal, state="swapped",
                                    resume_round=int(journal.get("resume_round") or 0) + 1)
            return _relaunch_new(lock, database, journal, system)
        journal = write_journal(lock, database, journal, state="rolling_back",
                                reason="the new version is not completely installed")
        return _roll_back(lock, database, journal, rec, system)
    return _block(lock, database, journal, system, f"the update stopped in an unexpected "
                  f"state ({state})")


# --------------------------------------------------------------------------
# Keeping exactly one way back
# --------------------------------------------------------------------------

def _succeeded(owner, database, journal: dict) -> None:
    """After a commit: drop staging copies, keep one previous app and its data copy."""
    ownership.require(owner, ownership.canonical_database(database))
    current = read_journal(database) or {}
    if (not _same_attempt(current, journal)
            or current.get("state") not in ("committing", "committed")):
        return
    data = _data_journal(database) or {}
    if not _same_attempt(data, journal) or data.get("state") != "committed":
        raise InstallError("The committed update's data journal is missing or mismatched.")
    way_back = journal.get("previous_app") or journal.get("recovery_copy")
    if not way_back or not data.get("set_aside"):
        raise InstallError("The committed update's rollback locations are missing.")
    updates = home(database)
    shutil.rmtree(updates / "staging" / journal["to_version"], ignore_errors=True)
    incoming = Path(journal.get("incoming") or "")
    if incoming.name == "Refinix.app" and incoming.exists():
        shutil.rmtree(incoming, ignore_errors=True)
    if journal.get("previous_app"):
        keep_app = Path(journal["previous_app"]).parent
        for folder in (updates / "previous").glob("*"):
            if folder.is_dir() and folder != keep_app:
                shutil.rmtree(folder, ignore_errors=True)
    keep_data = Path(data.get("set_aside") or "")
    set_aside = ownership.canonical_database(database).parent / "recovery" / "set-aside"
    for folder in set_aside.glob("*"):
        if folder.is_dir() and folder != keep_data:
            shutil.rmtree(folder, ignore_errors=True)
    _status(database, journal, "done")


def _sweep(database, journal: dict, system: System) -> None:
    """With no helper running: remove finished attempts' working folders."""
    if system.same(journal.get("helper")):
        return
    for folder in (home(database) / "install").glob("*"):
        if folder.is_dir() and folder.name != journal.get("update_id"):
            shutil.rmtree(folder, ignore_errors=True)
    # The finished attempt keeps only its small logs; its helper clone and any
    # expanded app that was never installed go.
    current = attempt_folder(database, journal.get("update_id") or "-")
    shutil.rmtree(current / "helper", ignore_errors=True)
    if journal.get("state") != "rolled_back":
        _drop_incoming(journal)
