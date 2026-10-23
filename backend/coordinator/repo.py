"""Repository containment: path validation, bounded reads and atomic writes.

Execution 2's filesystem boundary. Everything the Code surface touches on disk
goes through here, and nothing here trusts a string from the page or the model.

Three rules shape the whole module:

* A root enters only through a native user gesture and is canonicalised once.
  After that the page and the model see an opaque repository id and validated
  *relative* paths — never the absolute root.
* Traversal refuses to follow a link at every step, and the object operated on
  is always the object that was checked. `Path.resolve()` followed by an
  ordinary `open()` is a time-of-check / time-of-use hole: the resolved answer
  can stop being true before the open. Where a platform cannot give that
  guarantee, the whole Code surface is disabled rather than run on a weaker
  one.
* Identity is verified twice — once when a proposal is built, once immediately
  before the replacement lands. A file that changed underneath is stale, not
  something to overwrite.

**Two backends, one guarantee.** POSIX gets it from `dir_fd` and `O_NOFOLLOW`:
each component is opened relative to the previous handle, so no resolved path
is ever re-walked. Windows has no `openat`, and until now that meant Code was
simply unavailable there. `winfs` supplies the same property from documented
Win32 behaviour — `FILE_FLAG_OPEN_REPARSE_POINT` opens the link rather than its
target, and a handle held without `FILE_SHARE_DELETE` pins every ancestor
against rename and delete for the whole operation. The bounds, the refusals and
the identity checks below are shared: only the way a name becomes an open
object differs.

The Windows backend is **source-present, not device-observed**. It is exercised
through an injected API, which proves the sequence and every refusal but not
the real `kernel32`.

Standard library only.
"""

from __future__ import annotations

import errno
import hashlib
import os
import stat
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from backend.coordinator import winfs

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

# Roots a person can select by accident and never means as a project. The
# Windows names are the same idea in that platform's spelling; a drive root is
# caught separately by the anchor comparison, which needs no list.
_FORBIDDEN_ROOTS = ("/", "/Users", "/home", "/etc", "/var", "/usr", "/System",
                    "/Library", "/private", "/tmp", "/opt", "/bin", "/sbin")

_FORBIDDEN_WINDOWS_NAMES = frozenset({
    "windows", "program files", "program files (x86)", "programdata",
    "system32", "users", "$recycle.bin", "perflogs"})


class RepositoryError(ValueError):
    """A refusal with a code the interface can show and a test can assert."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------
# Platform capability
# --------------------------------------------------------------------------

POSIX_BACKEND = "descriptor-relative"
WINDOWS_BACKEND = "pinned-handle"


def descriptor_traversal_supported() -> bool:
    """True when POSIX can open a path component-by-component safely.

    One of the two ways the containment guarantee can be obtained, not the
    question the Code surface should ask — use `containment_supported`.
    """
    # POSIX exposes the capability under `rename`; `os.replace` is the same
    # renameat call with the overwrite semantics we want.
    return (os.open in os.supports_dir_fd and os.stat in os.supports_dir_fd
            and os.rename in os.supports_dir_fd and os.unlink in os.supports_dir_fd
            and hasattr(os, "O_NOFOLLOW"))


def containment_backend() -> str | None:
    """Which backend can bound a connected folder here, or None for neither.

    Checked in this order because `dir_fd` is the stronger, already-observed
    path: a POSIX computer never reaches the Windows probe, and a Windows one
    never pretends to have `dir_fd`.
    """
    if descriptor_traversal_supported():
        return POSIX_BACKEND
    if winfs.supported():
        return WINDOWS_BACKEND
    return None


def containment_supported() -> bool:
    """The one question the Code surface asks about this computer.

    Reported honestly rather than worked around: without a way to open each
    component without following a link that appeared between the check and the
    open, there is no bounded folder. Every operation here depends on it —
    reading as much as writing — so the whole surface is gated on this one
    answer rather than only the write.
    """
    return containment_backend() is not None


PLATFORM_NOTE = (
    "This computer cannot open files inside a connected folder without the risk "
    "of following a link that changed underneath, so Refinix cannot keep the "
    "folder safely bounded here. Code is unavailable on this computer: nothing "
    "is listed, read, proposed or written. Chat is unaffected."
)


def _require_platform() -> str:
    """Fail closed everywhere, not only on the write, and say which backend.

    Reading through a resolved path and an ordinary `open()` would be a
    weaker guarantee wearing the same words, so it is refused instead.
    """
    backend = containment_backend()
    if backend is None:
        raise RepositoryError("platform", PLATFORM_NOTE)
    return backend


# --------------------------------------------------------------------------
# Roots and relative paths
# --------------------------------------------------------------------------

def _is_reparse_point(path: Path) -> bool:
    """True for a Windows junction, mount point or symlink; False elsewhere.

    `Path.is_symlink()` answers for POSIX links and for Windows symlinks, but
    not for a junction — which redirects just as effectively. The attribute is
    the reliable answer and is simply absent on POSIX.
    """
    try:
        info = os.lstat(path)
    except OSError:
        return False
    return bool(getattr(info, "st_file_attributes", 0)
                & winfs.FILE_ATTRIBUTE_REPARSE_POINT)


def _is_windows_system_folder(root: Path) -> bool:
    """A Windows folder nobody means as a project.

    Matched by name under a drive root rather than by absolute string, because
    the system drive letter is not always `C:` and the profile directory is
    not always `Users`.
    """
    if sys.platform != "win32":
        return False
    parts = root.parts
    if len(parts) != 2:                 # anchor plus one name
        return False
    return parts[1].casefold() in _FORBIDDEN_WINDOWS_NAMES


def canonical_root(selected: str | os.PathLike, *, state_dir: Path) -> Path:
    """Canonicalise a natively selected folder once, or refuse it."""
    if not isinstance(selected, (str, os.PathLike)) or not str(selected).strip():
        raise RepositoryError("no_selection", "No folder was selected.")
    root = Path(selected).expanduser()
    # A junction or a mount point is a link Windows does not report as one, so
    # the attribute is read as well. Checked before `resolve`, which would
    # follow it and leave nothing to refuse.
    if root.is_symlink() or _is_reparse_point(root):
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
    if str(root) in _FORBIDDEN_ROOTS or root == Path(root.anchor) \
            or _is_windows_system_folder(root):
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


def _check_bounds(name: str, *, links: int, size: int) -> None:
    """The limits both backends enforce, on the object already open.

    Separate from the type checks because those are expressed differently on
    each platform — `S_ISLNK` there, a reparse attribute here — while a hard
    link and an oversized file mean exactly the same thing on both.
    """
    if links > 1:
        raise RepositoryError("hard_link", f"{name} has more than one name on disk.")
    if size > MAX_FILE_BYTES:
        raise RepositoryError(
            "too_large", f"{name} is larger than {MAX_FILE_BYTES // 1024} KB.")


def _check_regular(info: os.stat_result, name: str) -> None:
    if stat.S_ISLNK(info.st_mode):
        raise RepositoryError("symlink", f"{name} is a link, which Refinix does not follow.")
    if not stat.S_ISREG(info.st_mode):
        raise RepositoryError("not_regular", f"{name} is not an ordinary file.")
    _check_bounds(name, links=info.st_nlink, size=info.st_size)


@dataclass(frozen=True)
class _Opened:
    """What a backend observed about the object it just opened.

    The two backends read different structures; everything past the open is
    written once against this one.
    """

    device: int
    inode: int
    size: int
    mode: int


def _decoded(relative: str, data: bytes, info: _Opened) -> tuple[str, FileIdentity]:
    """The checks and the identity that follow any successful read."""
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
    return text, FileIdentity(device=info.device, inode=info.inode, size=info.size,
                              mode=info.mode, sha256=hashlib.sha256(data).hexdigest())


def read_text_file(root: Path, relative: str) -> tuple[str, FileIdentity]:
    """Read one bounded UTF-8 file from inside `root`, refusing anything else."""
    backend = _require_platform()
    relative = normalise_relative(relative)
    if backend == WINDOWS_BACKEND:
        return _decoded(relative, *_windows_read(root, relative))
    return _decoded(relative, *_posix_read(root, relative))


def _posix_read(root: Path, relative: str) -> tuple[bytes, _Opened]:
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
    return data, _Opened(device=info.st_dev, inode=info.st_ino,
                         size=info.st_size, mode=stat.S_IMODE(info.st_mode))


def _windows_read(root: Path, relative: str) -> tuple[bytes, _Opened]:
    """The same read, with every ancestor pinned by an open handle.

    `winfs.pinned` refuses a reparse point at each step and `open_file`
    refuses one on the final name, so the descriptor adopted here holds the
    object that was checked — the property `O_NOFOLLOW` gives above.
    """
    parts = relative.split("/")
    with _windows_errors(relative), winfs.pinned(root, parts[:-1]) as folder:
        descriptor, entry = folder.open_file(parts[-1])
        try:
            _check_bounds(relative, links=entry.links, size=entry.size)
            data = _read_all(descriptor, MAX_FILE_BYTES)
        finally:
            os.close(descriptor)
    return data, _Opened(device=entry.device, inode=entry.inode,
                         size=entry.size, mode=entry.mode)


@contextmanager
def _windows_errors(relative: str):
    """Turn a Win32 failure into the refusal vocabulary POSIX already uses.

    One place, so a Windows user sees "is not in the connected folder" rather
    than an error number, and a test can assert the same codes on both
    backends.
    """
    try:
        yield
    except winfs.Unavailable as exc:
        raise RepositoryError("platform", PLATFORM_NOTE) from exc
    except winfs.WindowsError_ as exc:
        message = {
            "missing": f"{relative} is not in the connected folder.",
            "symlink": f"{relative} is a link, which Refinix does not follow.",
            "symlinked_root": "The connected folder is a link.",
            "not_a_directory": "The connected folder is not a folder.",
            "not_regular": f"{relative} is not an ordinary file.",
            "bad_path": f"{relative} could not be opened as a path.",
            "exists": f"{relative} could not be written: the name already exists.",
        }.get(exc.reason, f"{relative} could not be read: {exc}")
        raise RepositoryError(exc.reason, message) from exc
    except OSError as exc:
        raise RepositoryError(
            "unreadable",
            f"{relative} could not be used: {exc.strerror or exc}") from exc


def list_text_files(root: Path, *, limit: int = MAX_LIST_ENTRIES) -> list[dict]:
    """Bounded listing of candidate files. Excluded trees are never entered."""
    if _require_platform() == WINDOWS_BACKEND:
        return _windows_list(root, limit=limit)
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


def _windows_list(root: Path, *, limit: int) -> list[dict]:
    """The same listing, descending only through pinned directories.

    The walk descends with `folder.child`, which keeps every directory above
    it open, rather than reopening the chain from the root for each folder —
    the same shape the POSIX walk has, and the reason a deep tree costs one
    open per directory instead of one per level per directory.

    A listing offers candidates; it is not the read. Every name is opened and
    re-verified by `read_text_file` before a byte of it is used, so a folder
    that disappears mid-walk is skipped rather than failing the listing.
    """
    found: list[dict] = []

    def walk(folder, prefix: str, depth: int) -> None:
        if len(found) >= limit or depth > MAX_DEPTH:
            return
        for name, entry in sorted(folder.entries(), key=lambda item: item[0]):
            if len(found) >= limit:
                return
            if entry.is_reparse_point:
                continue
            if entry.is_directory:
                if name in EXCLUDED_DIRECTORIES:
                    continue
                try:
                    with folder.child(name) as inner:
                        walk(inner, f"{prefix}{name}/", depth + 1)
                except (winfs.WindowsError_, OSError):
                    continue
                continue
            if name in EXCLUDED_FILENAMES \
                    or PurePosixPath(name).suffix.lower() in EXCLUDED_SUFFIXES:
                continue
            if entry.size > MAX_FILE_BYTES or entry.links > 1:
                continue
            found.append({"path": f"{prefix}{name}", "bytes": entry.size})

    with _windows_errors(str(root)), winfs.root_directory(root) as folder:
        walk(folder, "", 0)
    return found[:limit]


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
    backend = _require_platform()
    relative = normalise_relative(relative)
    if not isinstance(text, str):
        raise RepositoryError("bad_content", "The replacement must be text.")
    data = text.encode("utf-8")
    if len(data) > MAX_FILE_BYTES:
        raise RepositoryError(
            "too_large", f"The replacement for {relative} is larger than "
                         f"{MAX_FILE_BYTES // 1024} KB.")
    if backend == WINDOWS_BACKEND:
        return _windows_replace(root, relative, expected_sha256=expected_sha256,
                                data=data)

    parts = relative.split("/")
    root_fd = _open_directory(root)
    temporary = None
    try:
        parent_fd = _descend(root_fd, parts[:-1])
        try:
            info, current = _posix_target(parent_fd, parts[-1], relative)
            if hashlib.sha256(current).hexdigest() != expected_sha256:
                raise RepositoryError(
                    "stale", f"{relative} changed on disk after the preview was made. "
                             "Nothing was written.")

            mode = stat.S_IMODE(info.st_mode)
            temporary = _temporary_name()
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
            final, current = _posix_target(parent_fd, parts[-1], relative)
            if ((final.st_dev, final.st_ino) != (info.st_dev, info.st_ino)
                    or hashlib.sha256(current).hexdigest() != expected_sha256):
                raise RepositoryError(
                    "stale", f"{relative} changed while the replacement was being "
                             "prepared. Nothing was written.")
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


def _temporary_name() -> str:
    return f".refinix-{os.getpid()}-{os.urandom(6).hex()}.tmp"


def _posix_target(parent_fd: int, name: str, relative: str):
    """Read one no-follow target for the initial and final stale checks."""
    flags = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
             | getattr(os, "O_NONBLOCK", 0))
    try:
        handle = os.open(name, flags, dir_fd=parent_fd)
    except OSError as exc:
        raise RepositoryError(
            "stale", f"{relative} could not be reopened: {exc.strerror}") from exc
    try:
        info = os.fstat(handle)
        _check_regular(info, relative)
        return info, _read_all(handle, MAX_FILE_BYTES)
    finally:
        os.close(handle)


def _windows_replace(root: Path, relative: str, *, expected_sha256: str,
                     data: bytes) -> FileIdentity:
    """The same replacement, inside a directory pinned for its whole duration.

    The order is the one the POSIX path uses, for the same reasons: reopen and
    re-hash the target through a fresh handle, write the replacement to a
    temporary file beside it, flush, and only then move it over the name. A
    failure at any point leaves the original untouched and removes the
    temporary file.

    The target is checked again under an exclusive handle after the temporary
    file is durable. Windows requires that handle to close before the move;
    the remaining close-to-rename boundary is one syscall-sized window rather
    than the whole temporary-file write.
    """
    parts = relative.split("/")
    with _windows_errors(relative), winfs.pinned(root, parts[:-1]) as folder:
        try:
            descriptor, entry = folder.open_file(parts[-1])
        except winfs.WindowsError_ as exc:
            raise RepositoryError(
                "stale", f"{relative} could not be reopened: {exc}") from exc
        try:
            _check_bounds(relative, links=entry.links, size=entry.size)
            current = _read_all(descriptor, MAX_FILE_BYTES)
        finally:
            os.close(descriptor)
        if hashlib.sha256(current).hexdigest() != expected_sha256:
            raise RepositoryError(
                "stale", f"{relative} changed on disk after the preview was made. "
                         "Nothing was written.")

        # `temporary` names a file that must not survive this block unless it
        # was promoted over the target, and `out` must be closed however the
        # block ends. Both are cleaned in one `finally` rather than at each
        # raise, so a failure this code does not anticipate — not only an
        # `OSError` — still leaves the folder as it was found. The POSIX path
        # is built the same way, for the same reason.
        temporary, out, promoted = _temporary_name(), None, False
        created = False
        try:
            try:
                out, _entry = folder.create_file(temporary)
            except winfs.WindowsError_ as exc:
                # `CREATE_NEW` fails without creating anything when the name
                # already exists, and that name is then somebody else's file —
                # so nothing is cleaned up for it. Every *other* outcome, a
                # success or any other failure, may have left the name behind:
                # the file is created before the handle is inspected.
                created = exc.reason != "exists"
                raise
            except BaseException:
                created = True
                raise
            else:
                created = True
            _write_all(out, data)
            os.fsync(out)
            if os.fstat(out).st_size != len(data):
                raise OSError(errno.EIO, "the replacement was written short")
            os.close(out)
            out = None
            try:
                locked, final = folder.open_file_locked(parts[-1])
            except winfs.WindowsError_ as exc:
                raise RepositoryError(
                    "stale", f"{relative} could not be rechecked: {exc}") from exc
            try:
                current = _read_all(locked, MAX_FILE_BYTES)
            finally:
                os.close(locked)
            if ((final.device, final.inode) != (entry.device, entry.inode)
                    or hashlib.sha256(current).hexdigest() != expected_sha256):
                raise RepositoryError(
                    "stale", f"{relative} changed while the replacement was being "
                             "prepared. Nothing was written.")
            # The bytes are already flushed, so the content is durable before
            # the name changes. Windows offers no directory fsync; NTFS
            # journals the rename itself, and `os.replace` is the same
            # `MoveFileExW` the POSIX `renameat` mirrors.
            folder.replace(temporary, parts[-1])
            promoted = True
        except RepositoryError:
            raise
        except (OSError, winfs.WindowsError_) as exc:
            if isinstance(exc, winfs.WindowsError_) and exc.reason == "exists":
                raise
            raise RepositoryError(
                "write_failed",
                f"{relative} could not be written ({getattr(exc, 'strerror', None) or exc}). "
                "The original file was not changed.") from exc
        finally:
            if out is not None:
                try:
                    os.close(out)
                except OSError:
                    pass
            if created and not promoted:
                folder.unlink(temporary)
        written = folder.stat(parts[-1])

    return FileIdentity(device=written.device, inode=written.inode,
                        size=written.size, mode=written.mode,
                        sha256=hashlib.sha256(data).hexdigest())


def root_is_intact(root: Path, identity: dict | None) -> bool:
    """True when the connected folder is still the same directory it was."""
    try:
        info = os.stat(root, follow_symlinks=False)
    except OSError:
        return False
    if not stat.S_ISDIR(info.st_mode):
        return False
    # A junction put in place of the folder keeps `S_ISDIR` true while sending
    # every name somewhere else, so the reparse attribute is checked as well.
    if getattr(info, "st_file_attributes", 0) & winfs.FILE_ATTRIBUTE_REPARSE_POINT:
        return False
    if not identity:
        return True
    return (info.st_dev == identity.get("device")
            and info.st_ino == identity.get("inode"))


def root_identity(root: Path) -> dict:
    info = os.stat(root, follow_symlinks=False)
    return {"device": info.st_dev, "inode": info.st_ino}
