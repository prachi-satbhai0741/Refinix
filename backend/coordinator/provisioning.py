"""Putting a catalogued model's exact files on this computer, and taking them off.

Three operations, each started by the person in Settings → Models and each
ending in the same verified install record (`db.record_model_install`):

* **Download** fetches the catalogue's pinned HTTPS files. Bytes are hashed as
  they arrive into a staging folder beside the models; a file is moved into
  place only when its size and SHA-256 match the pin. An interrupted download
  resumes from the staged bytes, which are re-hashed first, and never touches
  an installed file.
* **Import** copies files the person already has — from removable media or
  another computer — and accepts each one only if it hashes to one of the
  entry's pinned files. A name is never trusted; the bytes decide the role.
* **Removal** unloads the model, forgets its record and deletes its folder.
  Chats, documents and history are workspace data and are never touched.

Nothing here runs on its own: no startup check, no background refresh, no
automatic retry. Only HTTPS is followed, including every redirect. The person
sees source, licence, revision, size and SHA-256 before confirming (the
catalogue's `as_dict`).

One operation runs at a time. Downloads and imports run on a background thread
and report through `state()`, which the status read includes.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import ssl
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from backend.coordinator import db, models

STAGING = ".partial"
CHUNK = 1024 * 1024
# Room left free beyond the files themselves, so a download never fills the
# disk the workspace database and logs live on.
DISK_MARGIN_BYTES = 1024 ** 3
MAX_REDIRECTS = 10
ENGINE = "llama.cpp"

# The operating system's own root certificate files. A packaged Python's
# OpenSSL may look for certificates in a folder that only exists on the build
# computer; these are maintained by the OS and its updates.
SYSTEM_CA_FILES = ("/etc/ssl/cert.pem",                     # macOS, Alpine
                   "/etc/ssl/certs/ca-certificates.crt",    # Debian, Ubuntu
                   "/etc/pki/tls/certs/ca-bundle.crt")      # Fedora, RHEL


class ProvisioningError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class Operation:
    """One download or import, as the interface shows it."""

    model_id: str
    kind: str                                  # "download" | "import"
    state: str = "running"                     # running | done | failed | cancelled
    bytes_done: int = 0
    bytes_total: int = 0
    file: str | None = None
    error: str | None = None
    error_code: str | None = None
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    def as_dict(self) -> dict:
        return {"model_id": self.model_id, "kind": self.kind, "state": self.state,
                "bytes_done": self.bytes_done, "bytes_total": self.bytes_total,
                "file": self.file, "error": self.error, "error_code": self.error_code,
                "started_at": self.started_at, "finished_at": self.finished_at}


def tls_context() -> ssl.SSLContext:
    """Certificate-verifying TLS, with the OS root file when Python has none."""
    context = ssl.create_default_context()
    if not context.cert_store_stats().get("x509_ca"):
        for candidate in SYSTEM_CA_FILES:
            if os.path.isfile(candidate):
                context.load_verify_locations(cafile=candidate)
                break
    return context


def _pool():
    """An urllib3 pool that honours an explicit HTTPS proxy setting only."""
    import urllib3
    timeout = urllib3.Timeout(connect=20, read=60)
    retries = urllib3.Retry(total=3, connect=3, read=3, redirect=False,
                            backoff_factor=1.0, status_forcelist=(502, 503, 504),
                            raise_on_status=False)
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        return urllib3.ProxyManager(proxy, ssl_context=tls_context(),
                                    timeout=timeout, retries=retries)
    return urllib3.PoolManager(ssl_context=tls_context(), timeout=timeout,
                               retries=retries)


def _sha256_of(path: Path, digest=None, cancelled=None) -> "hashlib._Hash | None":
    digest = digest or hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            if cancelled is not None and cancelled():
                return None
            digest.update(block)
    return digest


def _durable_replace(source: Path, target: Path) -> None:
    """Move a verified file into place so a crash leaves old or new, not half."""
    with open(source, "rb") as handle:
        os.fsync(handle.fileno())
    os.replace(source, target)
    if sys.platform != "win32":
        descriptor = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


class Provisioner:
    """Download, import and removal for one workspace's managed models."""

    def __init__(self, conn, state_path: Path, *, unload=None, busy=None,
                 pool=None, disk_usage=shutil.disk_usage):
        self.conn = conn
        self.root = db.models_root(state_path)
        self.unload = unload or (lambda model_id: None)    # stop an engine serving it
        self.busy = busy or (lambda: False)                # True while jobs are running
        self._pool = pool
        self._disk_usage = disk_usage
        self._lock = threading.Lock()
        self._operations: dict[str, Operation] = {}
        self._thread: threading.Thread | None = None
        # Entries resolved from a repository this session (Browse), pinned to
        # a revision, files, sizes and SHA-256 before any byte is fetched.
        self._plans: dict[str, models.Entry] = {}

    # -- resolved entries --------------------------------------------------
    def add_plan(self, entry: models.Entry) -> models.Entry:
        """Remember a pinned entry resolved from a repository, for download."""
        if entry.engine != ENGINE or not entry.files:
            raise ProvisioningError("unknown_model", "That is not a downloadable model.")
        for item in entry.files:
            if urlsplit(item.url).scheme != "https" or len(item.sha256) != 64:
                raise ProvisioningError("unsafe_source",
                                        f"{item.name} has no pinned HTTPS source and SHA-256.")
        with self._lock:
            self._plans[entry.id] = entry
        folder = self.root / STAGING / entry.id
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = folder / "plan.json.part"
        temporary.write_text(models.record_source(entry, "download from"), encoding="utf-8")
        os.replace(temporary, folder / "plan.json")
        return entry

    def known_ids(self) -> set[str]:
        with self._lock:
            planned = set(self._plans)
        return planned | {r["model_id"] for r in db.model_installs(self.conn)}

    # -- what the interface reads ------------------------------------------
    def state(self) -> dict:
        with self._lock:
            return {k: v.as_dict() for k, v in self._operations.items()}

    def plan(self, model_id: str) -> dict:
        """What a download of `model_id` would do, for the confirmation step."""
        entry = self._entry(model_id)
        missing = [f for f in entry.files if not self._installed_file_ok(entry, f)]
        staged = sum(self._staged_size(entry, f) for f in missing)
        needed = sum(f.size for f in missing) - staged
        try:
            free = int(self._disk_usage(self.root if self.root.exists()
                                        else self.root.parent).free)
        except OSError:
            free = None
        return {"model_id": entry.id, "display_name": entry.display_name or entry.id,
                "source": entry.source, "licence": entry.licence,
                "revision": entry.revision, "manifest_sha256": entry.manifest_sha256,
                "files": [f.as_dict() for f in entry.files],
                "download_bytes": max(0, needed), "already_staged_bytes": staged,
                "storage_bytes": sum(f.size for f in entry.files),
                "free_bytes": free,
                "enough_space": free is None or free >= needed + DISK_MARGIN_BYTES,
                "location": str(self.root / entry.id)}

    # -- starting work -----------------------------------------------------
    def start_download(self, model_id: str) -> dict:
        entry = self._entry(model_id)
        for item in entry.files:
            if urlsplit(item.url).scheme != "https":
                raise ProvisioningError("unsafe_source",
                                        f"{item.name} is not served over HTTPS.")
        plan = self.plan(model_id)
        if not plan["enough_space"]:
            raise ProvisioningError(
                "insufficient_space",
                f"About {(plan['download_bytes'] + DISK_MARGIN_BYTES) // 1024 ** 2} MB "
                f"of free space is needed; {plan['free_bytes'] // 1024 ** 2} MB is free.")
        operation = Operation(entry.id, "download", bytes_total=plan["storage_bytes"])
        self._begin(operation, lambda: self._download(entry, operation))
        return operation.as_dict()

    def start_import(self, model_id: str, paths: list[Path]) -> dict:
        entry = self._entry(model_id)
        candidates = []
        sizes = {f.size for f in entry.files}
        unmatched = []
        for path in paths:
            path = Path(path)
            if path.is_symlink() or not path.is_file():
                raise ProvisioningError("not_a_file",
                                        f"{path.name} is not an ordinary file.")
            # A file whose size matches no pinned file cannot be one of them,
            # so it is refused before a single byte is copied.
            if path.stat().st_size not in sizes:
                unmatched.append(path.name)
                continue
            candidates.append(path)
        if not candidates:
            raise ProvisioningError(
                "no_files", ("None of the chosen files is one of this model's files"
                             + (f" ({', '.join(unmatched)})" if unmatched else "") + "."
                             if unmatched else "No files were chosen."))
        total = sum(p.stat().st_size for p in candidates)
        try:
            free = int(self._disk_usage(self.root if self.root.exists()
                                        else self.root.parent).free)
        except OSError:
            free = None
        if free is not None and free < total + DISK_MARGIN_BYTES:
            raise ProvisioningError(
                "insufficient_space",
                f"About {(total + DISK_MARGIN_BYTES) // 1024 ** 2} MB of free space is "
                f"needed to import; {free // 1024 ** 2} MB is free.")
        operation = Operation(entry.id, "import", bytes_total=total)
        self._begin(operation, lambda: self._import(entry, candidates, operation,
                                                    rejected=unmatched))
        return operation.as_dict()

    def cancel(self, model_id: str) -> dict:
        with self._lock:
            operation = self._operations.get(model_id)
        if operation is None or operation.state != "running":
            return {"model_id": model_id, "cancelled": False}
        operation.cancel.set()
        return {"model_id": model_id, "cancelled": True}

    def wait(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    # -- removal -----------------------------------------------------------
    def remove(self, model_id: str) -> dict:
        """Forget and delete one installed model, after it is unloaded."""
        with self._lock:
            running = self._operations.get(model_id)
            if running is not None and running.state == "running":
                raise ProvisioningError("in_progress",
                                        "Cancel the download or import first.")
        if self.busy():
            raise ProvisioningError(
                "in_use", "Work is running. Remove the model when it has finished.")
        self._entry(model_id)
        folder = self.root / model_id
        if db.get_model_install(self.conn, model_id) is None and not folder.exists():
            raise ProvisioningError("not_installed", f"{model_id} is not installed.")
        try:
            self.unload(model_id)
        except Exception as exc:                           # noqa: BLE001
            # Removing files from under an engine that would not stop would
            # report a removal that did not happen. Nothing is changed.
            raise ProvisioningError(
                "unload_failed",
                f"{model_id} could not be unloaded, so nothing was removed: {exc}") from exc
        # Record first: a crash after this leaves an unreferenced folder, which
        # removing the model again deletes; never a record without its files.
        # Nothing deletes model folders on its own: a folder without a record
        # may hold verified files from an interrupted download, and the next
        # download reuses them after re-reading them.
        db.delete_model_install(self.conn, model_id)
        shutil.rmtree(folder, ignore_errors=True)
        shutil.rmtree(self.root / STAGING / model_id, ignore_errors=True)
        with self._lock:
            self._operations.pop(model_id, None)
        return {"model_id": model_id, "removed": True,
                "files_left": folder.exists()}

    # -- internals ---------------------------------------------------------
    def _entry(self, model_id: str) -> models.Entry:
        """A catalogue entry, a plan resolved this session, or a recorded one."""
        entry = models.entry_for(model_id)
        if entry is None:
            with self._lock:
                entry = self._plans.get(model_id)
        if entry is None:
            entry = models.entry_from_record(db.get_model_install(self.conn, model_id))
        if entry is None:
            entry = self._staged_plan(model_id)
        if entry is None or entry.engine != ENGINE or not entry.files:
            raise ProvisioningError("unknown_model",
                                    f"{model_id} is not a model Refinix can install.")
        return entry

    def _staged_plan(self, model_id: str) -> models.Entry | None:
        """A resolved plan kept beside its partial download, after a restart."""
        if not model_id or any(c in model_id for c in "/\\") or model_id.startswith("."):
            return None
        path = self.root / STAGING / model_id / "plan.json"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None
        entry = models.entry_from_record({"model_id": model_id, "source": text,
                                          "manifest_sha256": None})
        if entry is None:
            return None
        manifest = models.manifest_digest(model_id, entry.revision, entry.files)
        from dataclasses import replace
        return replace(entry, manifest_sha256=manifest)

    def _begin(self, operation: Operation, work) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise ProvisioningError("busy", "Another model is being set up. "
                                                "Wait for it to finish or cancel it.")
            self._operations[operation.model_id] = operation

            def run():
                try:
                    work()
                    if operation.cancel.is_set():
                        operation.state = "cancelled"
                    else:
                        operation.state = "done"
                except ProvisioningError as exc:
                    operation.state = "failed"
                    operation.error, operation.error_code = str(exc), exc.code
                except Exception as exc:                   # noqa: BLE001
                    operation.state = "failed"
                    operation.error = f"{type(exc).__name__}: {exc}"
                    operation.error_code = "failed"
                finally:
                    operation.finished_at = time.time()

            self._thread = threading.Thread(target=run, name="refinix-provisioning",
                                            daemon=True)
            self._thread.start()

    def _final(self, entry: models.Entry, item: models.ModelFile) -> Path:
        return self.root / entry.id / item.name

    def _staged(self, entry: models.Entry, item: models.ModelFile) -> Path:
        return self.root / STAGING / entry.id / (item.name + ".part")

    def _staged_size(self, entry, item) -> int:
        try:
            size = self._staged(entry, item).stat().st_size
        except OSError:
            return 0
        return size if size <= item.size else 0

    def _installed_file_ok(self, entry, item, cancelled=None) -> bool:
        """True when the final file exists with the pinned size (bytes checked later)."""
        path = self._final(entry, item)
        try:
            info = path.lstat()
        except OSError:
            return False
        return path.is_file() and not path.is_symlink() and info.st_size == item.size

    def _verified_in_place(self, entry, item, operation) -> bool:
        """An already-installed file counts only after its bytes are re-read."""
        if not self._installed_file_ok(entry, item):
            return False
        digest = _sha256_of(self._final(entry, item), cancelled=operation.cancel.is_set)
        if digest is None:
            return False
        if digest.hexdigest() == item.sha256:
            return True
        self._final(entry, item).unlink()
        return False

    def _record(self, entry: models.Entry, source: str) -> None:
        # Every file, in recorded order: a split model's parts are all kept,
        # and the first `weights` file is the one the engine is given.
        files = [{"role": f.role, "name": f.name, "path": f"{entry.id}/{f.name}",
                  "size": f.size, "sha256": f.sha256, "order": index}
                 for index, f in enumerate(entry.files)]
        if models.entry_for(entry.id) is None:
            # A resolved entry keeps its metadata in the same column, as
            # versioned JSON; older plain-text rows stay readable as before.
            source = models.record_source(entry, source)
        db.record_model_install(self.conn, model_id=entry.id,
                                manifest_sha256=entry.manifest_sha256, engine=ENGINE,
                                files=files, source=source)
        shutil.rmtree(self.root / STAGING / entry.id, ignore_errors=True)

    def _download(self, entry: models.Entry, operation: Operation) -> None:
        (self.root / entry.id).mkdir(parents=True, exist_ok=True, mode=0o700)
        for item in entry.files:
            operation.file = item.name
            if self._verified_in_place(entry, item, operation):
                operation.bytes_done += item.size
                continue
            if operation.cancel.is_set():
                return
            staged = self._staged(entry, item)
            staged.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not self._fetch(item, staged, operation):
                return                                     # cancelled; staged bytes kept
            _durable_replace(staged, self._final(entry, item))
        operation.file = None
        self._record(entry, f"download from {entry.source}")

    def _fetch(self, item: models.ModelFile, staged: Path, operation: Operation) -> bool:
        """Stream one pinned file into `staged`; True when complete and verified."""
        base = operation.bytes_done
        have = staged.stat().st_size if staged.exists() else 0
        if have > item.size:
            staged.unlink()
            have = 0
        digest = hashlib.sha256()
        if have:
            # Resume only from bytes re-read now, never from a remembered state.
            if _sha256_of(staged, digest, cancelled=operation.cancel.is_set) is None:
                return False
        operation.bytes_done = base + have
        if have == item.size:
            return self._check(item, staged, digest, have)
        pool = self._pool or _pool()
        url, response = item.url, None
        headers = {"Range": f"bytes={have}-"} if have else {}
        for _ in range(MAX_REDIRECTS + 1):
            response = pool.request("GET", url, headers=headers, redirect=False,
                                    preload_content=False)
            if response.status in (301, 302, 303, 307, 308):
                location = response.headers.get("Location")
                response.drain_conn()
                response.release_conn()
                if not location:
                    raise ProvisioningError("bad_response", "A redirect had no target.")
                url = urljoin(url, location)
                if urlsplit(url).scheme != "https":
                    raise ProvisioningError("unsafe_source",
                                            "The download was redirected away from HTTPS.")
                continue
            break
        else:
            raise ProvisioningError("bad_response", "Too many redirects.")
        try:
            if have and response.status == 200:
                # The server ignored the range: start this file again.
                staged.unlink()
                have, digest = 0, hashlib.sha256()
                operation.bytes_done = base
            elif have and response.status != 206:
                raise ProvisioningError("bad_response",
                                        f"The server answered {response.status}.")
            elif not have and response.status != 200:
                raise ProvisioningError("bad_response",
                                        f"The server answered {response.status}.")
            with open(staged, "ab") as handle:
                for block in response.stream(CHUNK):
                    if operation.cancel.is_set():
                        return False
                    have += len(block)
                    if have > item.size:
                        raise ProvisioningError("size_mismatch",
                                                f"{item.name} is larger than its pin.")
                    handle.write(block)
                    digest.update(block)
                    operation.bytes_done = base + have
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            response.release_conn()
        return self._check(item, staged, digest, have)

    @staticmethod
    def _check(item, staged: Path, digest, have: int) -> bool:
        if have != item.size or digest.hexdigest() != item.sha256:
            staged.unlink(missing_ok=True)
            raise ProvisioningError(
                "integrity_mismatch",
                f"{item.name} did not match its pinned SHA-256 and was discarded.")
        return True

    def _import(self, entry: models.Entry, paths: list[Path], operation: Operation,
                rejected: list[str] | None = None) -> None:
        """Copy chosen files in, keeping each only if it is one of the pinned files."""
        (self.root / entry.id).mkdir(parents=True, exist_ok=True, mode=0o700)
        by_hash = {f.sha256: f for f in entry.files}
        staging = self.root / STAGING / entry.id
        staging.mkdir(parents=True, exist_ok=True, mode=0o700)
        unmatched, placed = list(rejected or ()), set()
        for path in paths:
            operation.file = path.name
            temporary = staging / (f"import-{os.getpid()}-{path.name}.part")
            digest = hashlib.sha256()
            try:
                with open(path, "rb") as source, open(temporary, "wb") as target:
                    for block in iter(lambda: source.read(CHUNK), b""):
                        if operation.cancel.is_set():
                            return
                        target.write(block)
                        digest.update(block)
                        operation.bytes_done += len(block)
                    target.flush()
                    os.fsync(target.fileno())
                item = by_hash.get(digest.hexdigest())
                if item is None or temporary.stat().st_size != item.size:
                    unmatched.append(path.name)
                    continue
                _durable_replace(temporary, self._final(entry, item))
                placed.add(item.name)
            finally:
                temporary.unlink(missing_ok=True)
        operation.file = None
        # Files copied now were hashed on the way in; any others must already
        # be installed, and are re-read rather than assumed.
        missing = [f.name for f in entry.files if f.name not in placed
                   and not self._verified_in_place(entry, f, operation)]
        if operation.cancel.is_set():
            return
        if missing:
            raise ProvisioningError(
                "incomplete",
                ("These files did not match any pinned file and were not kept: "
                 + ", ".join(unmatched) + ". " if unmatched else "")
                + "Still needed: " + ", ".join(missing) + ".")
        self._record(entry, "imported from files chosen on this computer")
