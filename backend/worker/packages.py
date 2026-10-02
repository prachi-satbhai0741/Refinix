"""AF-010 resource packages: the only way repository bytes reach the worker.

The C06 worker refused every envelope carrying `context` or `attachments`,
because there was nowhere safe to put the bytes. This is that place, and it is
deliberately the smallest thing that can hold a Code workflow's input.

**It is not a remote filesystem.** A package is one idempotent JSON upload,
bound to one attempt, holding a handful of small UTF-8 text files. There is no
listing route, no read route, no delete route, no path the caller chooses and
no way to reach a file that belongs to another attempt. The executor resolves a
`ResourceRef` inside the package assigned to the attempt it is running, or it
resolves nothing.

**Nothing is unpacked, only written.** There is no archive format here — no
tar, no zip, no multipart. Each entry is base64 of a UTF-8 string, decoded,
digest-checked and written with `O_CREAT|O_EXCL` under a name the coordinator
never chose. Symlinks, hard links, FIFOs, device files, absolute paths, `..`
and shell expansion have no representation in this format at all, which is
stronger than filtering them out.

ponytail: streamed archives are the upgrade path, and only once measured real
workloads exceed the ceiling below. Until then a bounded JSON body is smaller,
easier to make idempotent, and has no decompression surface.

**The store is separate from pairing state.** It lives under its own root so
the executor can be given the job volume without ever being given the
relationship credentials.

Standard library only.
"""

from __future__ import annotations

import base64
import binascii
import errno
import hashlib
import json
import os
import shutil
import stat
import time
from pathlib import Path

from backend.contracts import v1

# The prototype ceiling. Small on purpose: C09 sends the handful of files a
# person selected, not a repository.
MAX_FILES = 32
MAX_TOTAL_BYTES = 2 * 1024 * 1024
MAX_FILE_BYTES = 256 * 1024
MAX_PATH_LENGTH = 200
MAX_COMPONENT_LENGTH = 100
MAX_DEPTH = 12
MAX_BODY_BYTES = 4 * 1024 * 1024        # base64 inflates by ~4/3

# How long an unused package may sit before cleanup reclaims it.
RETENTION_SECONDS = 3600

DEFAULT_ROOT = "/var/lib/aegisforge-jobs/packages"


class PackageError(Exception):
    """Carries the contract failure code the route should return."""

    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _reject(message: str, status: int = 422) -> PackageError:
    return PackageError("invalid_request", message, status)


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def normalise_relative(raw) -> str:
    """A relative POSIX path with nothing clever in it, or a refusal.

    Every rejection below describes a real escape: an absolute path, a parent
    reference, a Windows drive, a NUL byte, a name that normalises onto another
    name. The check is on the *string*, before anything touches a filesystem,
    so it does not depend on the host's resolution rules.
    """
    if not isinstance(raw, str) or not raw:
        raise _reject("each package entry needs a relative path")
    if len(raw) > MAX_PATH_LENGTH:
        raise _reject("a package path is too long")
    if "\x00" in raw or any(ord(ch) < 0x20 for ch in raw):
        raise _reject("a package path contains control characters")
    if raw != raw.strip():
        raise _reject("a package path has leading or trailing whitespace")
    if "\\" in raw:
        raise _reject("a package path must use forward slashes")
    if raw.startswith("/") or (len(raw) > 1 and raw[1] == ":"):
        raise _reject("a package path must be relative")
    parts = raw.split("/")
    for part in parts:
        if not part:
            raise _reject("a package path has an empty component")
        if part in (".", ".."):
            raise _reject("a package path may not traverse directories")
        if len(part) > MAX_COMPONENT_LENGTH:
            raise _reject("a package path component is too long")
        if part.endswith((".", " ")):
            # Trailing dots and spaces collapse on some filesystems, which is
            # how two distinct entries become one file.
            raise _reject("a package path component ends with a dot or space")
    if len(parts) > MAX_DEPTH:
        raise _reject("a package path is nested too deeply")
    return raw


def _collision_key(path: str) -> str:
    """What two paths must not share once the filesystem has its way.

    macOS and many Linux mounts are case-insensitive, and Unicode gives more
    than one spelling of the same name. Two entries that land on one file would
    make the package's own digest a lie about what was written.
    """
    import unicodedata
    return unicodedata.normalize("NFC", path).casefold()


def validate(payload: dict) -> dict:
    """Check one upload body completely before a single byte is written.

    Returns the decoded entries plus the package digest. Raising here means
    nothing was created, which is what makes a rejected upload leave no trace.
    """
    if not isinstance(payload, dict):
        raise _reject("the package body must be a JSON object")
    if payload.get("contract_version") != v1.CONTRACT_VERSION:
        raise _reject("the package contract version is not supported")
    unknown = set(payload) - {"contract_version", "workspace_id", "relationship_id",
                              "attempt_id", "package_sha256", "files"}
    if unknown:
        raise _reject("the package body had unexpected fields")
    entries = payload.get("files")
    if not isinstance(entries, list) or not entries:
        raise _reject("a package needs at least one file")
    if len(entries) > MAX_FILES:
        raise _reject(f"a package holds at most {MAX_FILES} files")

    decoded, total = [], 0
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise _reject("a package entry was not an object")
        if set(entry) != {"resource_id", "path", "media_type", "size_bytes",
                          "sha256", "content_base64"}:
            raise _reject("a package entry did not have exactly the required fields")
        resource_id = entry["resource_id"]
        if not isinstance(resource_id, str) or not _is_uuid4(resource_id):
            raise _reject("a package entry needs a UUIDv4 resource id")
        if resource_id in seen_ids:
            raise _reject("a package repeated a resource id")
        seen_ids.add(resource_id)

        path = normalise_relative(entry["path"])
        key = _collision_key(path)
        if key in seen_paths:
            raise _reject("two package entries name the same file")
        seen_paths.add(key)

        media_type = entry["media_type"]
        if not isinstance(media_type, str) or not 3 <= len(media_type) <= 128:
            raise _reject("a package entry needs a media type")

        raw = entry["content_base64"]
        if not isinstance(raw, str):
            raise _reject("package content must be base64 text")
        try:
            # `validate=True`: a body with stray characters is a malformed
            # upload, not something to silently strip and accept.
            content = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise _reject("a package entry was not valid base64") from exc
        if len(content) > MAX_FILE_BYTES:
            raise _reject(f"a package file exceeds {MAX_FILE_BYTES} bytes")
        total += len(content)
        if total > MAX_TOTAL_BYTES:
            raise _reject(f"a package exceeds {MAX_TOTAL_BYTES} bytes in total")

        size = entry["size_bytes"]
        if not isinstance(size, int) or isinstance(size, bool) or size != len(content):
            raise _reject("a package entry's declared size did not match its content")
        digest = entry["sha256"]
        if not isinstance(digest, str) or len(digest) != 64:
            raise _reject("a package entry needs a SHA-256 digest")
        if hashlib.sha256(content).hexdigest() != digest.lower():
            raise _reject("a package entry did not match its digest")
        try:
            # Text only. A binary blob has no place in a Code package and
            # would be written unchecked into the validation workspace.
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise _reject("package files must be UTF-8 text") from exc

        decoded.append({"resource_id": resource_id, "path": path,
                        "media_type": media_type, "size_bytes": len(content),
                        "sha256": digest.lower(), "content": content})

    computed = package_digest(decoded)
    declared = payload.get("package_sha256")
    if not isinstance(declared, str) or declared.lower() != computed:
        raise _reject("the package digest did not match its contents")
    return {"files": decoded, "package_sha256": computed,
            "total_bytes": total, "file_count": len(decoded)}


def package_digest(files: list[dict]) -> str:
    """One digest over exactly what a package contains.

    Every entry carries its own content digest, so hashing the manifest binds
    the content too — and the same selection always produces the same value,
    which is what makes an identical retry idempotent.
    """
    material = json.dumps(
        sorted(({"resource_id": item["resource_id"], "path": item["path"],
                 "media_type": item["media_type"],
                 "size_bytes": item["size_bytes"], "sha256": item["sha256"]}
                for item in files), key=lambda item: item["resource_id"]),
        sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _is_uuid4(value: str) -> bool:
    import re
    return bool(re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        value))


# --------------------------------------------------------------------------
# The store
# --------------------------------------------------------------------------

class PackageStore:
    """Packages on disk, one directory per attempt, owner-readable only.

    The directory name is derived from validated opaque IDs and nothing else:
    the coordinator's absolute repository path is never sent, never stored and
    cannot be reconstructed from anything here.
    """

    def __init__(self, root: str | os.PathLike | None = None):
        self.root = Path(root or os.environ.get("AEGIS_PACKAGE_ROOT", DEFAULT_ROOT))

    # -- layout ----------------------------------------------------------
    def _attempt_dir(self, relationship_id: str, workspace_id: str,
                     attempt_id: str) -> Path:
        for value in (relationship_id, workspace_id, attempt_id):
            if not _is_uuid4(value):
                raise _reject("a package is addressed by UUIDv4 identifiers")
        # Relationship first: one relationship's packages can never be reached
        # through another's identifiers, even if an attempt id were guessed.
        return self.root / relationship_id / workspace_id / attempt_id

    # -- writing ---------------------------------------------------------
    def store(self, *, relationship_id: str, workspace_id: str, attempt_id: str,
              validated: dict) -> dict:
        """Write one package, or replay the identical one already stored.

        Three outcomes, and only three: stored, replayed, conflict. A retry of
        the identical package is safe because the digest is over the content;
        a different package for the same attempt is a conflict, because the
        attempt has already been told what it is running against.
        """
        target = self._attempt_dir(relationship_id, workspace_id, attempt_id)
        manifest_path = target / "manifest.json"
        existing = self._read_manifest(manifest_path)
        if existing is not None:
            if existing.get("package_sha256") == validated["package_sha256"]:
                return {**existing, "replayed": True}
            raise PackageError(
                "idempotency_conflict",
                "a different package is already stored for this attempt",
                409)

        staging = target.parent / f".{attempt_id}.staging-{os.getpid()}-{time.time_ns()}"
        try:
            self._write_tree(staging, validated["files"])
            manifest = {
                "relationship_id": relationship_id, "workspace_id": workspace_id,
                "attempt_id": attempt_id,
                "package_sha256": validated["package_sha256"],
                "file_count": validated["file_count"],
                "total_bytes": validated["total_bytes"],
                "stored_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "resources": [
                    {"resource_id": item["resource_id"], "path": item["path"],
                     "media_type": item["media_type"],
                     "size_bytes": item["size_bytes"], "sha256": item["sha256"]}
                    for item in validated["files"]],
            }
            self._write_bytes(staging / "manifest.json",
                              json.dumps(manifest, sort_keys=True).encode("utf-8"))
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                # One rename publishes the whole package. A reader never sees a
                # half-written tree, and a lost race is a conflict, not a merge.
                os.rename(staging, target)
            except OSError as exc:
                if exc.errno not in (errno.ENOTEMPTY, errno.EEXIST):
                    raise
                shutil.rmtree(staging, ignore_errors=True)
                concurrent = self._read_manifest(manifest_path)
                if concurrent is not None and \
                        concurrent.get("package_sha256") == validated["package_sha256"]:
                    return {**concurrent, "replayed": True}
                raise PackageError(
                    "idempotency_conflict",
                    "a different package is already stored for this attempt",
                    409) from exc
        except PackageError:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        except OSError as exc:
            shutil.rmtree(staging, ignore_errors=True)
            raise PackageError("internal_error",
                               "the package could not be stored", 500) from exc
        return {**manifest, "replayed": False}

    def _write_tree(self, staging: Path, files: list[dict]) -> None:
        staging.mkdir(parents=True, exist_ok=False, mode=0o700)
        for item in files:
            destination = staging / "files" / item["path"]
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self._write_bytes(destination, item["content"])

    @staticmethod
    def _write_bytes(path: Path, data: bytes) -> None:
        """Create a new owner-only file, or fail.

        `O_EXCL` and `O_NOFOLLOW` together mean this cannot land on an existing
        file and cannot follow a link that someone else placed in the way. The
        write loop exists because a short write is silent data loss.
        """
        flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL
                 | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
                 | getattr(os, "O_BINARY", 0))
        handle = os.open(path, flags, 0o600)
        try:
            info = os.fstat(handle)
            if not stat.S_ISREG(info.st_mode):
                raise OSError("not a regular file")
            written = 0
            while written < len(data):
                written += os.write(handle, data[written:])
        finally:
            os.close(handle)

    @staticmethod
    def _read_manifest(path: Path) -> dict | None:
        try:
            with open(path, "rb") as handle:
                return json.loads(handle.read(MAX_BODY_BYTES))
        except (OSError, ValueError):
            return None

    # -- reading ---------------------------------------------------------
    def manifest(self, *, relationship_id: str, workspace_id: str,
                 attempt_id: str) -> dict | None:
        target = self._attempt_dir(relationship_id, workspace_id, attempt_id)
        return self._read_manifest(target / "manifest.json")

    def resolve(self, *, relationship_id: str, workspace_id: str, attempt_id: str,
                resource_id: str) -> dict | None:
        """One resource, inside this attempt's package, verified on read.

        The `resource_id` is looked up in the stored manifest rather than used
        as a path, so a caller cannot address a file the package does not
        describe. The digest is re-checked because the bytes on disk are what
        the sandbox will actually receive.
        """
        stored = self.manifest(relationship_id=relationship_id,
                               workspace_id=workspace_id, attempt_id=attempt_id)
        if stored is None:
            return None
        for entry in stored.get("resources", []):
            if entry.get("resource_id") != resource_id:
                continue
            base = self._attempt_dir(relationship_id, workspace_id,
                                     attempt_id) / "files"
            path = base / entry["path"]
            try:
                data = path.read_bytes()
            except OSError:
                return None
            if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                return None
            return {**entry, "content": data, "path_on_disk": str(path)}
        return None

    def files_dir(self, *, relationship_id: str, workspace_id: str,
                  attempt_id: str) -> Path:
        return self._attempt_dir(relationship_id, workspace_id,
                                 attempt_id) / "files"

    # -- cleanup ---------------------------------------------------------
    def purge(self, *, relationship_id: str, workspace_id: str,
              attempt_id: str) -> bool:
        """Remove exactly one attempt's package. Never a wider tree."""
        target = self._attempt_dir(relationship_id, workspace_id, attempt_id)
        if not target.is_dir():
            return False
        shutil.rmtree(target, ignore_errors=True)
        return not target.exists()

    def purge_expired(self, *, older_than: int = RETENTION_SECONDS) -> list[str]:
        """Reclaim packages nothing came back for. Bounded, and never canonical.

        A package is coordination state: the coordinator holds the canonical
        proposal. Deleting an abandoned one loses nothing that matters and is
        what keeps unused repository text from accumulating on the worker.
        """
        removed, cutoff = [], time.time() - max(0, older_than)
        if not self.root.is_dir():
            return removed
        for relationship in _safe_listdir(self.root):
            for workspace in _safe_listdir(relationship):
                for attempt in _safe_listdir(workspace):
                    try:
                        if attempt.stat().st_mtime > cutoff:
                            continue
                    except OSError:
                        continue
                    shutil.rmtree(attempt, ignore_errors=True)
                    removed.append(attempt.name)
        return removed


def _safe_listdir(path: Path) -> list[Path]:
    try:
        return [child for child in path.iterdir() if child.is_dir()
                and not child.is_symlink()]
    except OSError:
        return []
