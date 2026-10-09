"""The only part of Refinix that runs as root: Ubuntu `.deb` updates.

Started only through polkit, as `pkexec /opt/refinix/Refinix <mode> <folder>`,
and dispatched by `desktop/refinix.py` before anything else is imported. As
root it never starts the window, the coordinator or a model runtime, and never
reads or writes the person's data. Every step is one administrator prompt
(`auth_admin`; nothing is remembered).

    --deb-admit     after "Download and prepare": copy the package, the
                    installed version's package and the signed metadata out of
                    the person's request folder into root-owned storage, then
                    authenticate the copies with the full TUF client, expiry
                    and rollback included, against the installed trust root and
                    root's own trust state. Record the admission.
    --deb-install   install an admitted package (normal install)
    --deb-recover   finish or undo an install that was interrupted
    --deb-rollback  reinstall the exact previous package the admission recorded

What the caller may give is one absolute path to a request folder in their own
home, owned by them and writable by nobody else. Each path component is opened
without following links, only fixed file names inside it are read, sizes are
bounded, and nothing the caller supplies is trusted after it is copied — the
copies are authenticated. Install, recovery and rollback act only on root's own
admission record and its copies, re-verified without a clock: an update
interrupted today can still be recovered later.

There is one Refinix installation, whichever account asks, so root keeps one
*current attempt* for the whole computer. Only that attempt, asked for by the
account that prepared it, may install, recover or roll back, and only while
the installed Refinix is its from- or to-version. An unfinished attempt is
never replaced: any new preparation is refused until it is finished or undone.
An attempt that ended is concluded by the next preparation and can never act
again. Every attempt records its direction (install or rollback) before any
dpkg step, and recovery continues in that direction.

Package work uses Debian's own tools under dpkg's front-end lock, held for the
whole transaction (Ubuntu's resolver decides; nothing here resolves
dependencies itself):

    normal install  `dpkg --audit` clean and no pending triggers on the packages
                    this update triggers; `apt-get --simulate --no-download
                    --no-remove install <copy>` plans exactly `Inst refinix`
                    and `Conf refinix` at the admitted version for amd64;
                    then `DPKG_FRONTEND_LOCKED=1 dpkg -i <copy>`.
    recovery        only `refinix` itself and the recorded trigger packages may
                    be unfinished; repair by state (reinstall the same copy,
                    `dpkg --configure refinix`, `dpkg --triggers-only` for the
                    recorded packages), or go back to the recorded previous copy.

After every change the installed tree is checked against the package's file
list before the person's workspace may open again.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import pwd
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from backend.coordinator import release, tuf_offline

MODES = ("--deb-admit", "--deb-install", "--deb-recover", "--deb-rollback")
PACKAGE = "refinix"
ARCH = "amd64"
LANE = "linux-x64"
# The only control fields a Refinix package may carry.
ALLOWED_FIELDS = ("Package", "Version", "Architecture", "Maintainer", "Installed-Size",
                  "Section", "Priority", "Homepage", "Description", "Depends")
MAX_PACKAGE = 2 * 1024 ** 3
MAX_JSON = 1024 ** 2
MAX_METADATA_FILES = 64
LOCK_SECONDS = 120
KEEP_RECORDS = 6
METADATA_NAME = re.compile(r"(?:\d+\.root|\d+\.snapshot|\d+\.targets|timestamp)\.json")
POINTER_NAME = re.compile(r"[0-9a-f]{64}\.latest(?:-preview)?\.json")
POINTER_TARGET = re.compile(r"beta/linux-x64/latest(?:-preview)?\.json")
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
       "DEBIAN_FRONTEND": "noninteractive"}
# dpkg's "state" word for a package with nothing left to do.
SETTLED = ("installed", "not-installed", "config-files")
LOCAL = "refinix-root"


class RootError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class Context:
    """Paths and the operating system; tests replace them."""

    def __init__(self, *, prefix=Path("/opt/refinix"), state=Path("/var/lib/refinix"),
                 dpkg_lock=Path("/var/lib/dpkg/lock-frontend"),
                 triggers_index=Path("/var/lib/dpkg/triggers/File"),
                 environ=None, geteuid=os.geteuid, home_of=None, run=subprocess.run,
                 executable=None, lock_seconds=LOCK_SECONDS):
        self.prefix, self.state = Path(prefix), Path(state)
        self.dpkg_lock, self.triggers_index = Path(dpkg_lock), Path(triggers_index)
        self.environ = os.environ if environ is None else environ
        self.geteuid, self._run = geteuid, run
        self.home_of = home_of or (lambda uid: Path(pwd.getpwuid(uid).pw_dir))
        self.executable = Path(executable or sys.executable)
        self.lock_seconds = lock_seconds

    @property
    def updates(self) -> Path:
        return self.state / "update"

    @property
    def trust(self) -> Path:
        return self.state / "trust" / "beta"

    @property
    def packages(self) -> Path:
        return self.state / "packages"

    @property
    def internal(self) -> Path:
        return self.prefix / "_internal"

    def run(self, argv, *, extra_env=None, timeout=1800):
        env = dict(ENV, **(extra_env or {}))
        return self._run(argv, capture_output=True, text=True, env=env, timeout=timeout,
                         check=False, stdin=subprocess.DEVNULL)


# --------------------------------------------------------------------------
# The caller's request folder
# --------------------------------------------------------------------------

def _caller(ctx: Context) -> tuple[int, Path]:
    if ctx.geteuid() != 0:
        raise RootError("not_root", "This step runs only through its administrator prompt.")
    try:
        uid = int(ctx.environ["PKEXEC_UID"])
    except (KeyError, ValueError) as exc:
        raise RootError("not_pkexec", "This step runs only through pkexec.") from exc
    if uid == 0:
        raise RootError("not_pkexec", "The request must come from a person's account.")
    if Path(os.path.realpath(ctx.executable)) != ctx.prefix / "Refinix":
        raise RootError("not_installed", "This step runs only from the installed package.")
    return uid, ctx.home_of(uid)


def _open_folder(path_text: str, uid: int, home: Path) -> int:
    """A directory descriptor for the request folder, reached without links."""
    path = Path(path_text)
    if not path.is_absolute() or str(path) != os.path.normpath(path_text) \
            or any(part in ("", ".", "..") for part in path.parts[1:]):
        raise RootError("bad_request", "The request folder must be a plain absolute path.")
    home_parts = Path(home).parts
    if len(path.parts) <= len(home_parts) or path.parts[:len(home_parts)] != home_parts:
        raise RootError("bad_request", "The request folder must be inside your home folder.")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            try:
                child = os.open(part, flags, dir_fd=fd)
            except OSError as exc:
                raise RootError("bad_request", f"The request folder cannot be opened safely "
                                               f"({part}: {exc.strerror}).") from exc
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if info.st_uid != uid or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise RootError("bad_request", "The request folder must be yours and writable "
                                           "by nobody else.")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _subfolder(fd: int, name: str, uid: int) -> int:
    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
    info = os.fstat(child)
    if info.st_uid != uid or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        os.close(child)
        raise RootError("bad_request", f"{name} in the request must be yours alone.")
    return child


def _copy_in(fd: int, name: str, target: Path, uid: int, limit: int) -> Path:
    """Copy one fixed-name regular file out of the request, bounded."""
    try:
        source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
    except OSError as exc:
        raise RootError("bad_request", f"{name} is missing from the request.") from exc
    try:
        info = os.fstat(source)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != uid or info.st_size > limit:
            raise RootError("bad_request", f"{name} is not a plain file of a usable size.")
        out = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        written = 0
        with os.fdopen(out, "wb") as handle:
            while True:
                block = os.read(source, 1024 * 1024)
                if not block:
                    break
                written += len(block)
                if written > limit:
                    raise RootError("bad_request", f"{name} grew while it was copied.")
                handle.write(block)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(source)
    return target


def copy_request(ctx: Context, path_text: str, uid: int, home: Path, destination: Path) -> dict:
    """Everything root will use from the request, copied into `destination`."""
    fd = _open_folder(path_text, uid, home)
    try:
        request_path = _copy_in(fd, "request.json", destination / "request.json", uid,
                                MAX_JSON)
        try:
            request = json.loads(request_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise RootError("bad_request", "request.json cannot be read.") from exc
        pointer = request.get("pointer") if isinstance(request, dict) else None
        if not isinstance(pointer, str) or not POINTER_TARGET.fullmatch(pointer):
            raise RootError("bad_request", "The request names no Refinix offer.")
        _copy_in(fd, "package.deb", destination / "package.deb", uid, MAX_PACKAGE)
        _copy_in(fd, "recovery.deb", destination / "recovery.deb", uid, MAX_PACKAGE)
        (destination / "metadata").mkdir(mode=0o700)
        metadata = _subfolder(fd, "metadata", uid)
        try:
            names = sorted(os.listdir(metadata))
            if len(names) > MAX_METADATA_FILES or not all(METADATA_NAME.fullmatch(n)
                                                          for n in names):
                raise RootError("bad_request", "The request's metadata folder holds "
                                               "unexpected files.")
            for name in names:
                _copy_in(metadata, name, destination / "metadata" / name, uid, MAX_JSON)
        finally:
            os.close(metadata)
        folders = []
        try:
            current = fd
            for part in ("targets", *Path(pointer).parent.parts):
                current = _subfolder(current, part, uid)
                folders.append(current)
            leaf = current
            names = [n for n in os.listdir(leaf) if POINTER_NAME.fullmatch(n)
                     and n.endswith(Path(pointer).name)]
            if len(names) != 1:
                raise RootError("bad_request", "The request must hold exactly one offer.")
            target = destination / "targets" / Path(pointer).parent
            target.mkdir(parents=True, mode=0o700)
            _copy_in(leaf, names[0], target / names[0], uid, MAX_JSON)
        finally:
            for item in folders:
                os.close(item)
        return {"pointer": pointer, "target": request.get("target"),
                "recovery_target": request.get("recovery_target")}
    finally:
        os.close(fd)


# --------------------------------------------------------------------------
# What is installed, and what the packages say
# --------------------------------------------------------------------------

def dpkg_status(ctx: Context, package: str = PACKAGE) -> tuple[str | None, str | None]:
    """(dpkg's status words, version) for one package, or (None, None)."""
    result = ctx.run(["dpkg-query", "-W", "-f=${Status}\t${Version}", package], timeout=60)
    if result.returncode != 0 or "\t" not in (result.stdout or ""):
        return None, None
    status, version = result.stdout.split("\t", 1)
    return status.strip(), version.strip() or None


def unfinished_packages(ctx: Context) -> dict[str, str]:
    """Every package dpkg has not finished with, and its status."""
    result = ctx.run(["dpkg-query", "-W", "-f=${Package}\t${Status}\n"], timeout=120)
    if result.returncode != 0:
        raise RootError("dpkg", "Ubuntu's package records cannot be read.")
    found = {}
    for line in (result.stdout or "").splitlines():
        name, _, status = line.partition("\t")
        words = status.split()
        if len(words) == 3 and (words[2] not in SETTLED or words[1] != "ok"):
            found[name.split(":")[0]] = status
    return found


def installed_identity(ctx: Context) -> dict | None:
    try:
        data = json.loads((ctx.internal / "refinix-build.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def installed_version(ctx: Context) -> tuple[str, str | None]:
    """The healthy installed Refinix: dpkg and the identity file must agree."""
    status, deb_version = dpkg_status(ctx)
    identity = installed_identity(ctx) or {}
    if status != "install ok installed":
        raise RootError("not_healthy", "Refinix's package is not fully installed.")
    try:
        label = release.check_identity(identity.get("version"), identity.get("channel"),
                                       identity.get("maturity"))
    except release.LabelError as exc:
        raise RootError("not_healthy", f"The installed identity is not usable: {exc}") from exc
    if label.debian() != deb_version or identity.get("lane") != LANE:
        raise RootError("not_healthy", "Ubuntu's package records and the installed Refinix "
                                       "disagree about its version.")
    return str(label), label.maturity


def control_fields(ctx: Context, deb: Path) -> dict:
    result = ctx.run(["dpkg-deb", "-f", str(deb)], timeout=120)
    if result.returncode != 0:
        raise RootError("package", "The package's control information cannot be read.")
    fields, current = {}, None
    for line in (result.stdout or "").splitlines():
        if line[:1] in (" ", "\t") and current:
            fields[current] += "\n" + line
            continue
        name, _, value = line.partition(":")
        current = name.strip()
        fields[current] = value.strip()
    extra = sorted(set(fields) - set(ALLOWED_FIELDS))
    if extra:
        raise RootError("package", f"The package carries fields Refinix never uses: {extra}.")
    return fields


def check_package(ctx: Context, deb: Path, version: str) -> None:
    fields = control_fields(ctx, deb)
    wanted = {"Package": PACKAGE, "Architecture": ARCH,
              "Version": release.parse(version).debian()}
    for name, value in wanted.items():
        if fields.get(name) != value:
            raise RootError("package", f"The package's {name} is {fields.get(name)!r}, "
                                       f"not {value!r}.")


def trigger_packages(ctx: Context, deb: Path) -> list[str]:
    """Packages whose file triggers this package's files set off."""
    result = ctx.run(["dpkg-deb", "-c", str(deb)], timeout=120)
    if result.returncode != 0:
        raise RootError("package", "The package's file list cannot be read.")
    paths = []
    for line in (result.stdout or "").splitlines():
        name = line.split()[-1] if line.split() else ""
        if " -> " in line:
            name = line.split(" -> ")[0].split()[-1]
        if name.startswith("./"):
            paths.append("/" + name[2:].rstrip("/"))
    try:
        index = ctx.triggers_index.read_text(encoding="utf-8").splitlines()
    except OSError:
        index = []
    found = set()
    for line in index:
        interest, _, package = line.partition(" ")
        package = package.strip().split("/")[0].split(":")[0]
        if not interest or not package:
            continue
        if any(p == interest or p.startswith(interest.rstrip("/") + "/") for p in paths):
            found.add(package)
    return sorted(found)


# --------------------------------------------------------------------------
# Full TUF admission (with expiry) and the later offline re-check (without)
# --------------------------------------------------------------------------

def _local_fetcher(base: Path):
    from tuf.api import exceptions
    from tuf.ngclient import FetcherInterface

    class Local(FetcherInterface):
        def _fetch(self, url: str):
            prefix = f"{LOCAL}:///"
            if not url.startswith(prefix):
                raise exceptions.DownloadError(f"not a local URL: {url}")
            relative = url[len(prefix):]
            if ".." in relative.split("/"):
                raise exceptions.DownloadError("unsafe path")
            path = base / relative
            if not path.is_file():
                raise exceptions.DownloadHTTPError("not found", 404)
            return iter([path.read_bytes()])

    return Local()


def _installed_root(ctx: Context) -> bytes:
    try:
        return (ctx.internal / "refinix-update-root.json").read_bytes()
    except OSError as exc:
        raise RootError("not_healthy", "The installed update trust root is missing.") from exc


def tuf_admit(ctx: Context, copy: Path, request: dict, anchor: bytes) -> dict:
    """The full client over root's copies: signatures, expiry, rollback."""
    from tuf.ngclient import Updater
    ctx.trust.mkdir(parents=True, exist_ok=True, mode=0o700)
    work = copy / "client"
    work.mkdir(mode=0o700)
    updater = Updater(str(ctx.trust), f"{LOCAL}:///metadata/", str(work),
                      f"{LOCAL}:///targets/", fetcher=_local_fetcher(copy), bootstrap=anchor)
    try:
        updater.refresh()
        info = updater.get_targetinfo(request["pointer"])
        if info is None:
            raise RootError("evidence", "The offer is not in the signed metadata.")
        pointer = json.loads(Path(updater.download_target(info, str(work / "pointer.json")))
                             .read_text(encoding="utf-8"))
        name = (pointer.get("payloads") or {}).get("deb")
        package = updater.get_targetinfo(name) if name else None
        recovery = (updater.get_targetinfo(request["recovery_target"])
                    if request.get("recovery_target") else None)
    except RootError:
        raise
    except Exception as exc:                               # noqa: BLE001
        text = str(exc) or type(exc).__name__
        if "Expired" in type(exc).__name__:
            raise RootError("expired", "The update information has expired; check for "
                                       "updates again (or import a fresh bundle).") from exc
        raise RootError("evidence", f"The update information failed verification: "
                                    f"{text}") from exc
    if package is None or recovery is None:
        raise RootError("evidence", "The package or its recovery package is not signed.")
    trusted = updater._trusted_set                         # noqa: SLF001
    return {"pointer": pointer, "package": package, "recovery": recovery,
            "versions": {"timestamp": trusted.timestamp.version,
                         "snapshot": trusted.snapshot.version,
                         "targets": trusted.targets.version}}


def offline_check(ctx: Context, record: dict, folder: Path) -> None:
    """Re-authenticate an admission from root's copies, without the clock.

    The anchor is the trust root installed at admission. From there the roots
    must reach, version by version, the newest root root's own trust state
    holds (`ctx.trust/root.json`): links come from root's kept history first
    (trust changes this computer already knows about), then from the admitted
    copy. A missing or damaged link refuses before any package change, so a
    damaged history can never leave older, perhaps revoked, keys in charge.
    """
    anchor = (folder / "anchor.json").read_bytes()
    if hashlib.sha256(anchor).hexdigest() != record["anchor_sha256"]:
        raise RootError("evidence", "The recorded trust root changed.")
    try:
        trusted = (ctx.trust / "root.json").read_bytes()
    except OSError as exc:
        raise RootError("evidence", "Refinix's record of the update keys this computer "
                                    "trusts is missing, so the prepared update cannot "
                                    "be checked again. Nothing was changed.") from exc

    def kept(version: int) -> bytes | None:
        for path in (ctx.trust / "root_history" / f"{version}.root.json",
                     folder / "metadata" / f"{version}.root.json"):
            if path.is_file():
                return path.read_bytes()
        return None

    versions = record["versions"]
    try:
        root, _seen = tuf_offline.walk_roots(anchor, [])
        root, _added = tuf_offline.continue_to(root, trusted, kept)
        _t, _s, targets = tuf_offline.verify_roles(
            root, (folder / "metadata" / "timestamp.json").read_bytes(),
            (folder / "metadata" / f"{versions['snapshot']}.snapshot.json").read_bytes(),
            (folder / "metadata" / f"{versions['targets']}.targets.json").read_bytes())
    except (OSError, tuf_offline.OfflineError) as exc:
        raise RootError("evidence", f"The admitted update no longer verifies: {exc}") from exc
    entries = targets.signed.targets
    for key, path in (("target", folder / "package.deb"),
                      ("recovery_target", folder / "recovery.deb")):
        entry = entries.get(record[key])
        if entry is None:
            raise RootError("evidence", f"{record[key]} is no longer signed.")
        with open(path, "rb") as handle:
            try:
                entry.verify_length_and_hashes(handle)
            except Exception as exc:                       # noqa: BLE001
                raise RootError("evidence", f"Root's copy of {record[key]} changed.") from exc


# --------------------------------------------------------------------------
# Records, the current attempt and the locks
# --------------------------------------------------------------------------
#
# Ubuntu has one Refinix installation, whichever account asks. Root therefore
# keeps one *current attempt* for the whole computer (`current.json`), and
# only that attempt, asked for by the account that prepared it, may install,
# recover or roll back. An unfinished attempt is never replaced: another
# preparation, from any account, is refused until it is finished or undone.
# An attempt that ended (installed or rolled back) is concluded by the next
# preparation and can never act again, so an old request cannot revive it.

UNFINISHED = ("installing", "failed", "recovering", "rolling_back", "blocked")
ENDED = ("installed", "rolled_back")
FINAL = ("withdrawn", "concluded")


def _write_record(folder: Path, record: dict) -> dict:
    record = {**record, "updated_at": _stamp()}
    temporary = folder / ".record.json.tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, folder / "record.json")
    return record


def _read_record(folder: Path) -> dict | None:
    try:
        record = json.loads((folder / "record.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def _current(ctx: Context) -> tuple[Path, dict] | None:
    """The computer's current attempt: its folder and record, or None."""
    try:
        pointer = json.loads((ctx.state / "current.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    admission = pointer.get("admission") if isinstance(pointer, dict) else None
    if not isinstance(admission, str) or not admission.isalnum():
        return None
    folder = ctx.updates / admission
    record = _read_record(folder)
    if record is None or record.get("admission") != admission:
        return None
    return folder, record


def _set_current(ctx: Context, record: dict) -> None:
    temporary = ctx.state / ".current.json.tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump({"admission": record["admission"], "uid": record["uid"],
                   "set_at": _stamp()}, handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, ctx.state / "current.json")


def find_record(ctx: Context, request: str, uid: int) -> tuple[Path, dict]:
    best = None
    for path in ctx.updates.glob("*/record.json"):
        record = _read_record(path.parent)
        if record is None:
            continue
        if record.get("request") == request and record.get("uid") == uid:
            if best is None or record.get("admitted_at", "") > best[1].get("admitted_at", ""):
                best = (path.parent, record)
    if best is None:
        raise RootError("not_admitted", "This update was not prepared; download and "
                                        "prepare it again.")
    return best


def _bound(ctx: Context, request: str, uid: int) -> tuple[Path, dict]:
    """The caller's attempt, only while it is this computer's current one."""
    folder, record = find_record(ctx, request, uid)
    current = _current(ctx)
    if record.get("state") in FINAL or current is None \
            or current[1]["admission"] != record["admission"]:
        raise RootError("superseded", "This update is not the current one on this "
                                      "computer any more, so it can no longer change "
                                      "Refinix. Nothing was changed.")
    return folder, record


def _versions_allowed(ctx: Context, record: dict) -> tuple[str | None, str | None]:
    """dpkg's status and version for refinix, refusing a version this attempt
    does not know: only its from- or to-version may be on the system."""
    status, version = dpkg_status(ctx)
    allowed = {release.parse(record["from_version"]).debian(),
               release.parse(record["to_version"]).debian()}
    if status is None or version not in allowed:
        raise RootError("superseded", f"Refinix {version or '(not installed)'} is on this "
                                      "computer now, which this update did not install "
                                      "or replace, so it changes nothing.")
    return status, version


class RootLock:
    """Root's own lock: one Refinix root step at a time, before dpkg's lock."""

    def __init__(self, ctx: Context):
        self.ctx, self.fd = ctx, None

    def __enter__(self):
        self.ctx.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.fd = os.open(self.ctx.state / "root.lock",
                          os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        deadline = time.monotonic() + self.ctx.lock_seconds
        while True:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    os.close(self.fd)
                    raise RootError("busy", "Another Refinix update step is running; let "
                                            "it finish, then try again. Nothing was "
                                            "changed.")
                time.sleep(0.5)

    def __exit__(self, *exc):
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        os.close(self.fd)


class FrontendLock:
    """dpkg's front-end lock, held for one whole transaction."""

    def __init__(self, ctx: Context):
        self.ctx, self.fd = ctx, None

    def __enter__(self):
        self.fd = os.open(self.ctx.dpkg_lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o640)
        deadline = time.monotonic() + self.ctx.lock_seconds
        while True:
            try:
                fcntl.lockf(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    os.close(self.fd)
                    raise RootError("busy", "Another program is installing software; let it "
                                            "finish, then try again. Nothing was changed.")
                time.sleep(1)

    def __exit__(self, *exc):
        fcntl.lockf(self.fd, fcntl.LOCK_UN)
        os.close(self.fd)


SIMULATED = re.compile(r"^(Inst|Conf|Remv|Purg) (\S+)(?: \[([^\]]*)\])?(?: \((\S+) .*\[(\S+)\]\))?")


def simulate(ctx: Context, deb: Path, version: str, *, reinstall: bool = False) -> None:
    """Ubuntu's resolver must plan exactly unpack + configure of Refinix."""
    argv = ["apt-get", "--simulate", "--no-download", "--no-remove"]
    if reinstall:
        argv.append("--reinstall")
    result = ctx.run(argv + ["install", str(deb)], timeout=600)
    if result.returncode != 0:
        raise RootError("prerequisites", "Ubuntu cannot install this update without other "
                        "changes (a missing prerequisite or a download): "
                        + (result.stderr or result.stdout or "").strip()[-600:])
    steps = []
    for line in (result.stdout or "").splitlines():
        match = SIMULATED.match(line)
        if match:
            action, name, _old, new, arch = match.groups()
            steps.append((action, name.split(":")[0], new, arch))
    expected = [("Inst", PACKAGE, release.parse(version).debian(), ARCH),
                ("Conf", PACKAGE, release.parse(version).debian(), ARCH)]
    if steps != expected:
        raise RootError("plan", f"Ubuntu planned other changes ({steps}); nothing was "
                                "installed.")


def _dpkg_install(ctx: Context, deb: Path) -> bool:
    result = ctx.run(["dpkg", "-i", str(deb)], extra_env={"DPKG_FRONTEND_LOCKED": "1"})
    return result.returncode == 0


def _healthy_at(ctx: Context, version: str) -> str | None:
    """Why the installed Refinix is not exactly `version`; None when it is."""
    from desktop import install_check
    try:
        installed, _maturity = installed_version(ctx)
    except RootError as exc:
        return str(exc)
    if installed != version:
        return f"the installed version is {installed}, not {version}"
    return install_check.completeness_problem(ctx.prefix, version)


def _manual(ctx: Context, record: dict) -> str:
    name = Path(record["recovery_target"]).name
    return (f"Reinstall {ctx.packages / name} (SHA-256 {record['recovery_sha256']}) with "
            "App Center, or the same version from the Refinix website.")


def _admission_allowed(ctx: Context, uid: int) -> tuple[Path, dict, str] | None:
    """Whether a new preparation may become current; what the old one becomes."""
    current = _current(ctx)
    if current is None:
        return None
    folder, record = current
    state = record.get("state")
    if state in FINAL:
        return None
    if state in UNFINISHED:
        whose = "this account" if record.get("uid") == uid else "the account that started it"
        raise RootError("busy_other_update",
                        f"An earlier Refinix update ({record['from_version']} → "
                        f"{record['to_version']}) is unfinished. Open Refinix in {whose} "
                        "to finish or undo it first. " + _manual(ctx, record)
                        + " Nothing was changed.")
    # Not started yet (no package change), or ended: either way it can never
    # act again once another preparation is current.
    return folder, record, ("withdrawn" if state == "admitted" else "concluded")


def _keep_packages(ctx: Context, keep_records: list[dict]) -> None:
    """Public package bytes for manual recovery: readable by everyone. Kept for
    the current attempt and the one before it, never for older ones."""
    ctx.packages.mkdir(parents=True, exist_ok=True, mode=0o755)
    os.chmod(ctx.packages, 0o755)
    keep = set()
    for record in keep_records:
        folder = ctx.updates / record["admission"]
        for source, target in ((folder / "package.deb", record["target"]),
                               (folder / "recovery.deb", record["recovery_target"])):
            name = Path(target).name
            keep.add(name)
            destination = ctx.packages / name
            if not source.is_file():
                continue
            if not destination.is_file() or _sha256(destination) != _sha256(source):
                temporary = ctx.packages / f".{name}.tmp"
                shutil.copyfile(source, temporary)
                os.chmod(temporary, 0o644)
                os.replace(temporary, destination)
    for path in ctx.packages.glob("*.deb"):
        if path.name not in keep:
            path.unlink(missing_ok=True)


def _prune(ctx: Context, keep: set[Path]) -> None:
    """Remove old, finished admissions and leftovers of interrupted ones.

    Called with root's lock held, so a folder without a record is an
    admission that was interrupted before it was recorded: nothing uses it.
    A record that is not withdrawn or concluded is never removed.
    """
    finished = []
    for folder in ctx.updates.iterdir():
        if not folder.is_dir() or folder in keep:
            continue
        record = _read_record(folder)
        if record is None:
            shutil.rmtree(folder, ignore_errors=True)
        elif record.get("state") in FINAL:
            finished.append(folder)
    finished.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for old in finished[KEEP_RECORDS:]:
        shutil.rmtree(old, ignore_errors=True)


# --------------------------------------------------------------------------
# The four steps
# --------------------------------------------------------------------------

def admit(ctx: Context, request_path: str) -> dict:
    uid, home = _caller(ctx)
    with RootLock(ctx):
        # An unfinished attempt is reported as such before anything else.
        replaced = _admission_allowed(ctx, uid)
        from_version, from_maturity = installed_version(ctx)
        if from_maturity is None:
            raise RootError("channel", "Internal builds are not updated this way.")
        ctx.updates.mkdir(parents=True, exist_ok=True, mode=0o700)
        admission = secrets.token_hex(8)
        folder = ctx.updates / admission
        folder.mkdir(mode=0o700)
        try:
            record = _admit_into(ctx, folder, admission, request_path, uid, home,
                                 from_version, from_maturity)
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        # The new attempt is complete on disk before it becomes current; the
        # old one can never act again from this moment.
        _set_current(ctx, record)
        keep_records = [record]
        if replaced is not None:
            old_folder, old_record, old_state = replaced
            old_record = _write_record(old_folder, {**old_record, "state": old_state,
                                                    "replaced_by": admission})
            if old_state == "concluded":
                keep_records.append(old_record)
        _keep_packages(ctx, keep_records)
        _prune(ctx, keep={ctx.updates / r["admission"] for r in keep_records})
        return {"admission": admission, "state": "admitted",
                "to_version": record["to_version"], "from_version": from_version}


def _admit_into(ctx: Context, folder: Path, admission: str, request_path: str, uid: int,
                home: Path, from_version: str, from_maturity: str) -> dict:
    request = copy_request(ctx, request_path, uid, home, folder)
    anchor = _installed_root(ctx)
    (folder / "anchor.json").write_bytes(anchor)
    checked = tuf_admit(ctx, folder, request, anchor)
    pointer = checked["pointer"]
    try:
        label = release.check_identity(pointer.get("version"), "beta",
                                       pointer.get("maturity"))
    except release.LabelError as exc:
        raise RootError("evidence", f"The offer is mislabelled: {exc}") from exc
    if pointer.get("lane") != LANE or not release.pointer_allows(
            Path(request["pointer"]).name, label.maturity, "beta"):
        raise RootError("evidence", "The offer is not for this kind of installation.")
    package, recovery = checked["package"], checked["recovery"]
    custom = package.custom or {}
    if (custom.get("version"), custom.get("format"), custom.get("lane"),
            custom.get("maturity")) != (str(label), "deb", LANE, label.maturity):
        raise RootError("evidence", "The package's signed details do not match the offer.")
    rcustom = recovery.custom or {}
    if (rcustom.get("version"), rcustom.get("format"), rcustom.get("lane")) != (
            from_version, "deb", LANE) or recovery.path != release.package_target(
            from_version, LANE, "deb"):
        raise RootError("evidence", "The recovery package is not the installed version's.")
    for info, path in ((package, folder / "package.deb"),
                       (recovery, folder / "recovery.deb")):
        with open(path, "rb") as handle:
            try:
                info.verify_length_and_hashes(handle)
            except Exception as exc:                       # noqa: BLE001
                raise RootError("evidence", f"{path.name} does not match its signed "
                                            "size and SHA-256.") from exc
    if not release.offered_to(from_maturity, label.maturity):
        raise RootError("channel", f"A {from_maturity} installation does not take "
                                   f"{label.maturity} builds.")
    if label.key <= release.key(from_version):
        raise RootError("not_newer", f"{label} is not newer than {from_version}.")
    check_package(ctx, folder / "package.deb", str(label))
    check_package(ctx, folder / "recovery.deb", from_version)
    return _write_record(folder, {
        "admission": admission, "state": "admitted", "direction": "install", "uid": uid,
        "request": request_path, "from_version": from_version,
        "from_maturity": from_maturity, "to_version": str(label),
        "to_maturity": label.maturity, "format": "deb",
        "target": package.path, "recovery_target": recovery.path,
        "package_sha256": package.hashes["sha256"], "package_length": package.length,
        "recovery_sha256": recovery.hashes["sha256"],
        "recovery_length": recovery.length,
        "anchor_sha256": hashlib.sha256(anchor).hexdigest(),
        "versions": checked["versions"],
        "triggers": trigger_packages(ctx, folder / "package.deb"),
        "admitted_at": _stamp()})


def install(ctx: Context, request_path: str) -> dict:
    uid, _home = _caller(ctx)
    with RootLock(ctx):
        folder, record = _bound(ctx, request_path, uid)
        if record["state"] != "admitted":
            raise RootError("state", f"This update is {record['state']}; it is not "
                                     "installed twice.")
        offline_check(ctx, record, folder)
        with FrontendLock(ctx):
            installed, maturity = installed_version(ctx)
            if (installed, maturity) != (record["from_version"], record["from_maturity"]):
                raise RootError("changed", "The installed Refinix changed since this update "
                                           "was prepared; prepare it again.")
            audit = ctx.run(["dpkg", "--audit"], timeout=300)
            if audit.returncode != 0 or (audit.stdout or "").strip():
                raise RootError("unfinished", "Ubuntu's package system has unfinished work; "
                                              "finish it in Software Updater first. Nothing "
                                              "was changed.")
            pending = {name: status for name, status in unfinished_packages(ctx).items()
                       if name in record["triggers"]}
            if pending:
                raise RootError("unfinished", f"Packages Refinix's install would trigger "
                                              f"have unfinished work ({sorted(pending)}); "
                                              "finish it in Software Updater first.")
            simulate(ctx, folder / "package.deb", record["to_version"])
            record = _write_record(folder, {**record, "state": "installing",
                                            "direction": "install",
                                            "install_started_at": _stamp()})
            ok = _dpkg_install(ctx, folder / "package.deb")
            problem = None if ok else "dpkg could not install the package"
            problem = problem or _healthy_at(ctx, record["to_version"])
            state = "installed" if problem is None else "failed"
            record = _write_record(folder, {**record, "state": state, "problem": problem})
    return {"admission": record["admission"], "state": "to" if state == "installed"
            else "incomplete", "problem": problem}


def _settle_triggers(ctx: Context, record: dict) -> list[str]:
    pending = [name for name in record["triggers"] if name in unfinished_packages(ctx)]
    if pending:
        ctx.run(["dpkg", "--triggers-only", *pending],
                extra_env={"DPKG_FRONTEND_LOCKED": "1"})
    return [name for name in record["triggers"] if name in unfinished_packages(ctx)]


def _repair_towards(ctx: Context, folder: Path, record: dict, direction: str,
                    status: str | None, dpkg_version: str | None) -> None:
    """Finish an interrupted package change in the direction it was going:
    the new package for an install, the recorded previous one for a rollback."""
    wanted = record["to_version"] if direction == "install" else record["from_version"]
    copy = folder / ("package.deb" if direction == "install" else "recovery.deb")
    words = (status or "").split()
    state_word = words[2] if len(words) == 3 else None
    same = dpkg_version == release.parse(wanted).debian()
    if state_word == "half-installed" or (len(words) == 3 and words[1] == "reinstreq") \
            or (state_word in ("unpacked", "half-configured") and not same):
        _dpkg_install(ctx, copy)
    elif state_word in ("unpacked", "half-configured"):
        ctx.run(["dpkg", "--configure", PACKAGE], extra_env={"DPKG_FRONTEND_LOCKED": "1"})
    elif state_word == "installed" and not same:
        # Settled on the other version: carry on the way this attempt was going.
        _dpkg_install(ctx, copy)


def recover(ctx: Context, request_path: str) -> dict:
    """Finish what an interrupted install or rollback left, in its own direction;
    never touches anything unrelated, never a version this attempt did not know."""
    uid, _home = _caller(ctx)
    with RootLock(ctx):
        folder, record = _bound(ctx, request_path, uid)
        if record["state"] not in ("installing", "installed", "failed", "recovering",
                                   "rolling_back", "rolled_back"):
            raise RootError("state", f"This update is {record['state']}; there is nothing "
                                     "to recover.")
        offline_check(ctx, record, folder)
        with FrontendLock(ctx):
            _only_ours_unfinished(ctx, record)
            status, dpkg_version = _versions_allowed(ctx, record)
            # The direction is the attempt's own, recorded before any dpkg step.
            direction = record.get("direction") or (
                "rollback" if record["state"] in ("rolling_back", "rolled_back")
                else "install")
            # Already where this attempt was going: only unfinished triggers remain.
            arrived = _healthy_at(ctx, record["to_version" if direction == "install"
                                              else "from_version"]) is None
            record = _write_record(folder, {**record, "direction": direction,
                                            "state": "recovering" if direction == "install"
                                            else "rolling_back"})
            if not arrived:
                _repair_towards(ctx, folder, record, direction, status, dpkg_version)
            still = _settle_triggers(ctx, record)
            if still:
                record = _write_record(folder, {**record, "state": "blocked",
                                                "problem": f"triggers still pending: {still}"})
                return {"state": "blocked", "problem": record["problem"]}
            if direction == "rollback":
                problem = _healthy_at(ctx, record["from_version"])
                _write_record(folder, {**record, "state": "rolled_back" if problem is None
                                       else "blocked", "problem": problem})
                if problem:
                    return {"state": "blocked", "problem": problem,
                            "recovery_package": str(ctx.packages
                                                    / Path(record["recovery_target"]).name),
                            "recovery_sha256": record["recovery_sha256"]}
                return {"state": "from"}
            for wanted, label, state in ((record["to_version"], "to", "installed"),
                                         (record["from_version"], "from", "rolled_back")):
                if _healthy_at(ctx, wanted) is None:
                    _write_record(folder, {**record, "state": state, "problem": None})
                    return {"state": label}
            problem = _healthy_at(ctx, record["to_version"])
            _write_record(folder, {**record, "state": "failed", "problem": problem})
            # The helper goes back to the recorded previous package next.
            return {"state": "incomplete", "problem": problem}


def rollback(ctx: Context, request_path: str) -> dict:
    """Reinstall the exact previous package this admission recorded."""
    uid, _home = _caller(ctx)
    with RootLock(ctx):
        folder, record = _bound(ctx, request_path, uid)
        if record["state"] not in ("installing", "installed", "failed", "recovering",
                                   "rolling_back"):
            raise RootError("state", f"This update is {record['state']}; there is nothing "
                                     "to go back from.")
        offline_check(ctx, record, folder)
        with FrontendLock(ctx):
            _only_ours_unfinished(ctx, record)
            _versions_allowed(ctx, record)
            record = _write_record(folder, {**record, "state": "rolling_back",
                                            "direction": "rollback"})
            _dpkg_install(ctx, folder / "recovery.deb")
            _settle_triggers(ctx, record)
            problem = _healthy_at(ctx, record["from_version"])
            record = _write_record(folder, {**record, "state": "rolled_back"
                                            if problem is None else "blocked",
                                            "problem": problem})
    if problem:
        return {"state": "blocked", "problem": problem,
                "recovery_package": str(ctx.packages / Path(record["recovery_target"]).name),
                "recovery_sha256": record["recovery_sha256"]}
    return {"state": "from"}


def _only_ours_unfinished(ctx: Context, record: dict) -> None:
    allowed = {PACKAGE, *record["triggers"]}
    others = sorted(set(unfinished_packages(ctx)) - allowed)
    if others:
        raise RootError("unfinished", f"Other packages have unfinished work ({others}); "
                                      "Refinix only repairs its own package. Finish them "
                                      "in Software Updater, then open Refinix again.")


STEPS = {"--deb-admit": admit, "--deb-install": install, "--deb-recover": recover,
         "--deb-rollback": rollback}


def main(argv: list[str], ctx: Context | None = None) -> int:
    """One JSON line on standard output; exit 0 only when the step succeeded."""
    ctx = ctx or Context()
    previous_umask = os.umask(0o077)
    try:
        if len(argv) != 2 or argv[0] not in STEPS:
            raise RootError("usage", "usage: Refinix --deb-admit|--deb-install|"
                                     "--deb-recover|--deb-rollback <request folder>")
        result = STEPS[argv[0]](ctx, argv[1])
        code = 0
    except RootError as exc:
        result, code = {"error": str(exc), "code": exc.code}, 3
    except Exception as exc:                               # noqa: BLE001
        result, code = {"error": f"{type(exc).__name__}: {exc}", "code": "failed"}, 3
    finally:
        os.umask(previous_umask)
    print(json.dumps(result, sort_keys=True), flush=True)
    return code
