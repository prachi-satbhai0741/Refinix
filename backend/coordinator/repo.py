"""Repository containment: path validation, bounded reads and atomic writes.

Execution 2's filesystem boundary. Everything the Code surface touches on disk
goes through here, and nothing here trusts a string from the page or the model.

Three rules shape the whole module:

* A root enters only through a native user gesture and is canonicalised once.
  After that the page and the model see an opaque repository id and validated
  *relative* paths — never the absolute root.
* Traversal is descriptor-relative and refuses to follow links at every step.
  `Path.resolve()` followed by an ordinary `open()` is a time-of-check /
  time-of-use hole: the resolved answer can stop being true before the open.
  Where the platform cannot give us `dir_fd`, canonical writes are disabled
  rather than performed on a weaker guarantee.
* Identity is verified twice — once when a proposal is built, once immediately
  before the replacement lands. A file that changed underneath is stale, not
  something to overwrite.

Standard library only.
"""

from __future__ import annotations

import errno
import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# Conservative bounds. They are visible in the errors, so a refusal explains
# itself instead of looking arbitrary.
MAX_FILE_BYTES = 256 * 1024
MAX_SELECTED_FILES = 20
MAX_TOTAL_BYTES = 512 * 1024
MAX_LIST_ENTRIES = 2000
MAX_RELATIVE_LENGTH = 512
MAX_COMPONENT_LENGTH = 255
MAX_DEPTH = 24

# Directories that are never entered. A small, documented deny list: it stops
# the obvious version-control internals, dependency trees and build output. It
# is NOT a secret scanner and does not claim to find every credential.
EXCLUDED_DIRECTORIES = frozenset({
    ".git", ".hg", ".svn", ".bzr", "_darcs", "CVS",
    ".aegisforge", ".refinix",
    "node_modules", "bower_components", "vendor",
    ".venv", "venv", "virtualenv", "env", ".env.d",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox",
    "build", "dist", "target", "out", ".next", ".nuxt", ".parcel-cache",
    ".gradle", ".m2", ".cargo", ".stack-work",
    ".cache", ".idea", ".vscode", ".terraform", ".serverless",
    "DerivedData", ".Trash",
})

# Filenames that commonly hold credentials. Same caveat: a deny list, not proof.
EXCLUDED_FILENAMES = frozenset({
    ".env", ".env.local", ".env.production", ".env.development",
    ".netrc", "_netrc", ".npmrc", ".pypirc", ".dockercfg", ".git-credentials",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "credentials", "secrets.yaml",
    "secrets.yml", ".htpasswd", ".DS_Store",
})

EXCLUDED_SUFFIXES = frozenset({
    ".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".asc", ".gpg",
    ".kdbx", ".ppk",
})

# Roots a person can select by accident and never means as a project.
_FORBIDDEN_ROOTS = ("/", "/Users", "/home", "/etc", "/var", "/usr", "/System",
                    "/Library", "/private", "/tmp", "/opt", "/bin", "/sbin")


class RepositoryError(ValueError):
    """A refusal with a code the interface can show and a test can assert."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------
# Platform capability
# --------------------------------------------------------------------------

def descriptor_traversal_supported() -> bool:
    """True when the OS can give the containment guarantee this module needs.

    Reported honestly rather than worked around: without `dir_fd` there is no
    way to open a path component-by-component without following a link that
    appeared between the check and the open. Every operation here depends on
    it — reading as much as writing — so the whole Code surface is gated on
    this one answer rather than only the write.
    """
    # POSIX exposes the capability under `rename`; `os.replace` is the same
    # renameat call with the overwrite semantics we want.
    return (os.open in os.supports_dir_fd and os.stat in os.supports_dir_fd
            and os.rename in os.supports_dir_fd and os.unlink in os.supports_dir_fd
            and hasattr(os, "O_NOFOLLOW"))


PLATFORM_NOTE = (
    "This computer cannot open files relative to a directory handle, so Refinix "
    "cannot keep a connected folder safely bounded here. Code is unavailable on "
    "this computer: nothing is listed, read, proposed or written. Chat is "
    "unaffected."
)


def _require_platform() -> None:
    """Fail closed everywhere, not only on the write.

    Reading through a resolved path and an ordinary `open()` would be a
    weaker guarantee wearing the same words, so it is refused instead.
    """
    if not descriptor_traversal_supported():
        raise RepositoryError("platform", PLATFORM_NOTE)


# --------------------------------------------------------------------------
# Roots and relative paths
# --------------------------------------------------------------------------

def canonical_root(selected: str | os.PathLike, *, state_dir: Path) -> Path:
    """Canonicalise a natively selected folder once, or refuse it."""
    if not isinstance(selected, (str, os.PathLike)) or not str(selected).strip():
        raise RepositoryError("no_selection", "No folder was selected.")
    root = Path(selected).expanduser()
    if root.is_symlink():
        raise RepositoryError("symlinked_root", "A linked folder cannot be connected.")
    try:
        root = root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise RepositoryError("missing_root", f"That folder could not be opened: {exc}") from exc
    if not root.is_dir():
        raise RepositoryError("not_a_directory", "That selection is not a folder.")

    home = Path.home().resolve()
    state = Path(state_dir).expanduser().resolve()
    # Ordered deliberately, so each refusal gives the most specific reason.
    if str(root) in _FORBIDDEN_ROOTS or root == Path(root.anchor):
        raise RepositoryError(
            "system_root", "Connect a project folder, not a system folder.")
    if root == home:
        raise RepositoryError(
            "home_root", "Connect a project folder, not your whole home folder.")
    if root == state or state in root.parents:
        raise RepositoryError(
            "state_root", "That folder holds Refinix's own data and cannot be connected.")
    if root in state.parents:
        raise RepositoryError(
            "contains_state",
            "That folder contains Refinix's own data and cannot be connected.")
    return root


def normalise_relative(raw) -> str:
    """Return a strict relative POSIX path, or refuse it.

    Refuses absolute paths, drive and UNC forms, `.`/`..`, empty components,
    NUL, backslash separators used for traversal, excluded names, and anything
    too long or too deep.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise RepositoryError("bad_path", "A file path is required.")
    if "\x00" in raw:
        raise RepositoryError("bad_path", "That path contains an invalid character.")
    if len(raw) > MAX_RELATIVE_LENGTH:
        raise RepositoryError("bad_path", f"That path is longer than {MAX_RELATIVE_LENGTH} characters.")
    if raw.startswith(("/", "\\")) or raw.startswith("~"):
        raise RepositoryError("absolute_path", "Use a path relative to the connected folder.")
    if len(raw) > 1 and raw[1] == ":":
        raise RepositoryError("absolute_path", "Use a path relative to the connected folder.")

    parts = [p for p in raw.replace("\\", "/").split("/")]
    if any(p == "" for p in parts):
        raise RepositoryError("bad_path", "That path has an empty folder name.")
    if len(parts) > MAX_DEPTH:
        raise RepositoryError("bad_path", f"That path is deeper than {MAX_DEPTH} folders.")
    for part in parts:
        if part in (".", ".."):
            raise RepositoryError("traversal", "That path tries to leave the connected folder.")
        if len(part) > MAX_COMPONENT_LENGTH:
            raise RepositoryError("bad_path", "One folder or file name is too long.")
        if part in EXCLUDED_DIRECTORIES:
            raise RepositoryError("excluded", f"{part} is not available to Refinix.")
    name = parts[-1]
    if name in EXCLUDED_FILENAMES or PurePosixPath(name).suffix.lower() in EXCLUDED_SUFFIXES:
        raise RepositoryError("excluded", f"{name} is not available to Refinix.")
    return "/".join(parts)


def is_excluded_directory(name: str) -> bool:
    return name in EXCLUDED_DIRECTORIES or name.startswith(".") and name in EXCLUDED_DIRECTORIES


# --------------------------------------------------------------------------
# Descriptor-relative traversal
# --------------------------------------------------------------------------

def _open_directory(path: Path):
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    return os.open(path, flags)


def _read_all(handle: int, limit: int) -> bytes:
    """Read until end of file or `limit` bytes.

    `os.read` is allowed to return fewer bytes than asked for. A single call
    would silently produce a short prefix, which would then be hashed and
    compared as though it were the whole file.
    """
    chunks, total = [], 0
    while total <= limit:
        chunk = os.read(handle, min(1 << 16, limit + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks)


def _write_all(handle: int, data: bytes) -> None:
    """Write every byte, or raise.

    `os.write` may write fewer bytes than requested — on a full disk, for
    instance. Ignoring the count would promote a truncated temporary file over
    the real one while the recorded hash described the complete content.
    """
    written = 0
    while written < len(data):
        count = os.write(handle, data[written:])
        if count <= 0:
            raise OSError(errno.EIO,
                          f"wrote {written} of {len(data)} bytes and then stalled")
        written += count


def _is_link(name: str, dir_fd: int) -> bool:
    try:
        return stat.S_ISLNK(os.lstat(name, dir_fd=dir_fd).st_mode)
    except OSError:
        return False


def _descend(root_fd: int, parts) -> int:
    """Open each intermediate directory relative to the last, never following links."""
    current = os.dup(root_fd)
    try:
        for part in parts:
            flags = (os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                     | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
            try:
                nxt = os.open(part, flags, dir_fd=current)
            except OSError as exc:
                # macOS answers ENOTDIR where Linux answers ELOOP for
                # O_NOFOLLOW|O_DIRECTORY on a symlinked directory, so the
                # reason comes from what the entry actually is.
                if exc.errno in (errno.ELOOP, errno.EMLINK, errno.ENOTDIR):
                    if _is_link(part, current):
                        raise RepositoryError(
                            "symlink",
                            f"{part} is a link, which Refinix does not follow.") from exc
                    if exc.errno == errno.ENOTDIR:
                        raise RepositoryError("bad_path", f"{part} is not a folder.") from exc
                    raise RepositoryError(
                        "symlink", f"{part} is a link, which Refinix does not follow.") from exc
                if exc.errno == errno.ENOENT:
                    raise RepositoryError("missing", f"{part} is not in the connected folder.") from exc
                raise RepositoryError("unreadable", f"{part} could not be opened: {exc.strerror}") from exc
            os.close(current)
            current = nxt
        return current
    except BaseException:
        os.close(current)
        raise


@dataclass(frozen=True)
class FileIdentity:
    """What must still be true when a replacement lands."""

    device: int
    inode: int
    size: int
    mode: int
    sha256: str

    def as_dict(self) -> dict:
        return {"device": self.device, "inode": self.inode, "size": self.size,
                "mode": self.mode, "sha256": self.sha256}


def _check_regular(info: os.stat_result, name: str) -> None:
    if stat.S_ISLNK(info.st_mode):
        raise RepositoryError("symlink", f"{name} is a link, which Refinix does not follow.")
    if not stat.S_ISREG(info.st_mode):
        raise RepositoryError("not_regular", f"{name} is not an ordinary file.")
    if info.st_nlink > 1:
        raise RepositoryError("hard_link", f"{name} has more than one name on disk.")
    if info.st_size > MAX_FILE_BYTES:
        raise RepositoryError(
            "too_large", f"{name} is larger than {MAX_FILE_BYTES // 1024} KB.")


def read_text_file(root: Path, relative: str) -> tuple[str, FileIdentity]:
    """Read one bounded UTF-8 file from inside `root`, refusing anything else."""
    _require_platform()
    relative = normalise_relative(relative)
    parts = relative.split("/")
    root_fd = _open_directory(root)
    try:
        parent_fd = _descend(root_fd, parts[:-1])
        try:
            # O_NONBLOCK matters as much as O_NOFOLLOW here: opening a FIFO
            # for reading otherwise blocks until a writer appears, which would
            # hang the coordinator on a named pipe sitting in a project folder.
            flags = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                     | getattr(os, "O_NONBLOCK", 0))
            try:
                handle = os.open(parts[-1], flags, dir_fd=parent_fd)
            except OSError as exc:
                if exc.errno in (errno.ELOOP, errno.EMLINK):
                    raise RepositoryError(
                        "symlink", f"{parts[-1]} is a link, which Refinix does not follow.") from exc
                if exc.errno == errno.ENOENT:
                    raise RepositoryError(
                        "missing", f"{relative} is not in the connected folder.") from exc
                if exc.errno == errno.ENXIO:
                    raise RepositoryError(
                        "not_regular", f"{relative} is not an ordinary file.") from exc
                raise RepositoryError(
                    "unreadable", f"{relative} could not be read: {exc.strerror}") from exc
            try:
                info = os.fstat(handle)
                _check_regular(info, relative)
                data = _read_all(handle, MAX_FILE_BYTES)
            finally:
                os.close(handle)
        finally:
            os.close(parent_fd)
    finally:
        os.close(root_fd)

    if len(data) > MAX_FILE_BYTES:
        raise RepositoryError("too_large", f"{relative} is larger than {MAX_FILE_BYTES // 1024} KB.")
    if b"\x00" in data:
        raise RepositoryError("binary", f"{relative} is not a text file.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RepositoryError(
            "encoding",
            f"{relative} is not UTF-8 text. Refinix only reads UTF-8 files in this version."
        ) from exc
    identity = FileIdentity(device=info.st_dev, inode=info.st_ino, size=info.st_size,
                            mode=stat.S_IMODE(info.st_mode),
                            sha256=hashlib.sha256(data).hexdigest())
    return text, identity


def list_text_files(root: Path, *, limit: int = MAX_LIST_ENTRIES) -> list[dict]:
    """Bounded listing of candidate files. Excluded trees are never entered."""
    _require_platform()
    found: list[dict] = []
    truncated = False

    def walk(directory_fd: int, prefix: str, depth: int) -> None:
        nonlocal truncated
        if truncated or depth > MAX_DEPTH:
            return
        try:
            with os.scandir(directory_fd) as entries:
                names = sorted(entry.name for entry in entries)
        except OSError:
            return
        for name in names:
            if len(found) >= limit:
                truncated = True
                return
            try:
                info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            except OSError:
                continue
            if stat.S_ISLNK(info.st_mode):
                continue
            if stat.S_ISDIR(info.st_mode):
                if name in EXCLUDED_DIRECTORIES:
                    continue
                flags = (os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                         | getattr(os, "O_NOFOLLOW", 0)
                         | getattr(os, "O_NONBLOCK", 0))
                try:
                    child = os.open(name, flags, dir_fd=directory_fd)
                except OSError:
                    continue
                try:
                    walk(child, f"{prefix}{name}/", depth + 1)
                finally:
                    os.close(child)
                continue
            if not stat.S_ISREG(info.st_mode):
                continue
            if name in EXCLUDED_FILENAMES or PurePosixPath(name).suffix.lower() in EXCLUDED_SUFFIXES:
                continue
            if info.st_size > MAX_FILE_BYTES or info.st_nlink > 1:
                continue
            found.append({"path": f"{prefix}{name}", "bytes": info.st_size})

    root_fd = _open_directory(root)
    try:
        walk(root_fd, "", 0)
    finally:
        os.close(root_fd)
    return found if not truncated else found[:limit]


# --------------------------------------------------------------------------
# Atomic replacement
# --------------------------------------------------------------------------

def replace_text_file(root: Path, relative: str, *, expected_sha256: str,
                      text: str) -> FileIdentity:
    """Replace one existing file atomically, or refuse and change nothing.

    The target must still be the same regular file with the same content it had
    when the proposal was built. The new bytes are written to a same-directory
    temporary file, flushed, and moved over the target in one `os.replace`, so
    a reader never sees a half-written file and a failure leaves the original.
    """
    _require_platform()
    relative = normalise_relative(relative)
    if not isinstance(text, str):
        raise RepositoryError("bad_content", "The replacement must be text.")
    data = text.encode("utf-8")
    if len(data) > MAX_FILE_BYTES:
        raise RepositoryError(
            "too_large", f"The replacement for {relative} is larger than "
                         f"{MAX_FILE_BYTES // 1024} KB.")

    parts = relative.split("/")
    root_fd = _open_directory(root)
    temporary = None
    try:
        parent_fd = _descend(root_fd, parts[:-1])
        try:
            # Re-verify the target through a fresh no-follow handle: whatever
            # was checked at proposal time may have changed since.
            flags = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                     | getattr(os, "O_NONBLOCK", 0))
            try:
                handle = os.open(parts[-1], flags, dir_fd=parent_fd)
            except OSError as exc:
                raise RepositoryError(
                    "stale", f"{relative} could not be reopened: {exc.strerror}") from exc
            try:
                info = os.fstat(handle)
                _check_regular(info, relative)
                current = _read_all(handle, MAX_FILE_BYTES)
            finally:
                os.close(handle)
            if hashlib.sha256(current).hexdigest() != expected_sha256:
                raise RepositoryError(
                    "stale", f"{relative} changed on disk after the preview was made. "
                             "Nothing was written.")

            mode = stat.S_IMODE(info.st_mode)
            temporary = f".refinix-{os.getpid()}-{os.urandom(6).hex()}.tmp"
            create = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            out = os.open(temporary, create, mode, dir_fd=parent_fd)
            try:
                _write_all(out, data)
                os.fsync(out)
                # Preserve the original permission bits exactly; the creation
                # mode is filtered by umask.
                os.fchmod(out, mode)
                # Confirm the bytes really landed before anything is promoted.
                if os.fstat(out).st_size != len(data):
                    raise OSError(errno.EIO, "the replacement was written short")
            except OSError as exc:
                os.close(out)
                # `temporary` is still set, so the finally below removes it and
                # the original file is untouched.
                raise RepositoryError(
                    "write_failed",
                    f"{relative} could not be written ({exc.strerror or exc}). "
                    "The original file was not changed.") from exc
            else:
                os.close(out)
            os.replace(temporary, parts[-1], src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            temporary = None
            try:
                os.fsync(parent_fd)
            except OSError:
                pass                       # directory fsync is best effort
            written = os.stat(parts[-1], dir_fd=parent_fd, follow_symlinks=False)
        finally:
            if temporary is not None:
                try:
                    os.unlink(temporary, dir_fd=parent_fd)
                except OSError:
                    pass
            os.close(parent_fd)
    finally:
        os.close(root_fd)

    return FileIdentity(device=written.st_dev, inode=written.st_ino,
                        size=written.st_size, mode=stat.S_IMODE(written.st_mode),
                        sha256=hashlib.sha256(data).hexdigest())


def root_is_intact(root: Path, identity: dict | None) -> bool:
    """True when the connected folder is still the same directory it was."""
    try:
        info = os.stat(root, follow_symlinks=False)
    except OSError:
        return False
    if not stat.S_ISDIR(info.st_mode):
        return False
    if not identity:
        return True
    return (info.st_dev == identity.get("device")
            and info.st_ino == identity.get("inode"))


def root_identity(root: Path) -> dict:
    info = os.stat(root, follow_symlinks=False)
    return {"device": info.st_dev, "inode": info.st_ino}
