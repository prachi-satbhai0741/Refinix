"""Bounded filesystem access on Windows, through pinned handles.

`repo.py` keeps a connected folder bounded on POSIX with `dir_fd`: every
component is opened relative to the previous one, and `O_NOFOLLOW` refuses a
link at each step, so the answer cannot stop being true between the check and
the open. Windows has no `openat`, so that whole surface — reading as much as
writing — was refused there and the Code surface was simply unavailable.

This module is the Windows half of the same guarantee, built from two
documented Win32 behaviours rather than from a weaker re-reading of paths:

* **`FILE_FLAG_OPEN_REPARSE_POINT` opens the link, not its target.** Whatever
  a name refers to at the instant of the open, that object is what the handle
  holds. `FILE_ATTRIBUTE_REPARSE_POINT` on the resulting handle is then
  checked, so a symlink, a junction, a mount point or any other reparse tag is
  refused — including one substituted a microsecond before the open, because
  the handle already names the substituted object.
* **A handle opened without `FILE_SHARE_DELETE` blocks rename and delete.**
  Every ancestor's handle is held open for the whole operation, so no
  component of the prefix can be swapped while it is in use. That is what
  makes opening the next component *by full path* equivalent to `openat`:
  the path Windows walks is pinned by handles the walker already holds.

Neither behaviour is a workaround. Both are the documented semantics, and
together they give the same property as the POSIX path: **the object operated
on is the object that was checked.**

**No fallback.** Where the Win32 surface cannot be bound — a non-Windows
interpreter, a stripped runtime — `Unavailable` is raised and `repo.py` keeps
Code switched off. Resolving the path and opening it normally would be the
time-of-check/time-of-use hole the whole design exists to avoid, so it is not
offered.

**Evidence state: source-present, not device-observed.** The call sequence,
every refusal and the handle lifetime are exercised here through an injected
API (see `test_repo_windows.py`), exactly as the Windows credential backend
is. That proves the logic, not the real `kernel32`. A Windows profile has to
observe it before any support claim is made.

Standard library only. `ctypes` binds what the standard library does not
expose; the data transfer itself goes through ordinary `os` calls on a
descriptor adopted from the handle, so the amount of native code stays small
enough to read.
"""

from __future__ import annotations

import os
import sys
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass

# --- CreateFileW ---------------------------------------------------------
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
# Enough to open a handle and read its metadata, and nothing else. Used for
# every directory in the chain: a handle with no access still takes part in
# share-mode arbitration, so it pins the name just as well, while
# `FILE_FLAG_BACKUP_SEMANTICS` — which a directory open requires — cannot
# override a single file permission on the way.
METADATA_ONLY = 0
# Deliberately without FILE_SHARE_DELETE: that omission is what stops another
# process renaming or deleting a component while Refinix is inside it.
SHARE_READ_WRITE = 0x00000001 | 0x00000002
CREATE_NEW = 1
OPEN_EXISTING = 3
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000        # required to open a directory
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000      # do not follow the final link
FILE_ATTRIBUTE_DIRECTORY = 0x00000010
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
FILE_ATTRIBUTE_READONLY = 0x00000001


def invalid_handle(ctypes) -> int:
    """`CreateFileW`'s failure value, at the pointer width ctypes is using.

    The documented sentinel is `(HANDLE)-1`, but `HANDLE` is `c_void_p` and
    ctypes returns a `c_void_p` result as a Python int of pointer width —
    *unsigned*. So a failed open arrives as 0xFFFFFFFFFFFFFFFF on a 64-bit
    build, and comparing it against a literal `-1` never matches: every
    refusal would be read as a success, and the next call would fail with a
    confusing "invalid handle" instead of "the file is not there".

    Computed rather than written down, so the constant cannot drift from the
    width of the interpreter that is actually running.
    """
    return ctypes.c_void_p(-1).value

# --- the handful of error codes that need their own reason ---------------
ERROR_FILE_NOT_FOUND = 2
ERROR_PATH_NOT_FOUND = 3
ERROR_ACCESS_DENIED = 5
ERROR_SHARING_VIOLATION = 32
ERROR_FILE_EXISTS = 80
ERROR_INVALID_NAME = 123
ERROR_DIRECTORY = 267
ERROR_ALREADY_EXISTS = 183

# Mapped to the same refusal codes `repo.py` already returns on POSIX, so the
# interface shows one vocabulary regardless of which backend answered.
_REASONS = {
    ERROR_FILE_NOT_FOUND: "missing",
    ERROR_PATH_NOT_FOUND: "missing",
    ERROR_ACCESS_DENIED: "unreadable",
    ERROR_SHARING_VIOLATION: "unreadable",
    ERROR_INVALID_NAME: "bad_path",
    ERROR_DIRECTORY: "bad_path",
    ERROR_FILE_EXISTS: "exists",
    ERROR_ALREADY_EXISTS: "exists",
}

# Permission bits Python itself synthesises for a Windows file, reproduced so a
# `FileIdentity` carries the same shape on both backends. Windows has no POSIX
# mode; presenting one as if it had been read would be a fabricated fact.
MODE_READ_ONLY = 0o444
MODE_READ_WRITE = 0o666

# The only flag `_open_osfhandle` needs from Refinix, and the one it must never
# be without: in text mode the C runtime rewrites line endings on the way
# through, which would change the bytes a hash was taken over. Read and write
# access come from the handle itself, so no access flag is passed — the
# documented flag set does not include one.
_BINARY = getattr(os, "O_BINARY", 0)


class Unavailable(RuntimeError):
    """The Win32 surface could not be bound, so containment is not available."""


class WindowsError_(OSError):
    """A Win32 failure carrying the refusal code `repo.py` should report."""

    def __init__(self, code: int, reason: str, message: str):
        super().__init__(message)
        self.code = code
        self.reason = reason


@dataclass(frozen=True)
class Entry:
    """One object's identity, read from the handle that is already open.

    The Windows counterpart of `os.fstat` on a POSIX descriptor: it describes
    the object the handle holds, not whatever the name means now.
    """

    attributes: int
    device: int          # dwVolumeSerialNumber
    inode: int           # nFileIndexHigh/Low, joined
    size: int
    links: int

    @property
    def is_directory(self) -> bool:
        return bool(self.attributes & FILE_ATTRIBUTE_DIRECTORY)

    @property
    def is_reparse_point(self) -> bool:
        """True for a symlink, a junction, a mount point or any other tag.

        Checked by attribute rather than by reparse tag on purpose: Refinix
        follows none of them, so enumerating the tags it knows about would
        only create a list to be absent from.
        """
        return bool(self.attributes & FILE_ATTRIBUTE_REPARSE_POINT)

    @property
    def mode(self) -> int:
        return (MODE_READ_ONLY if self.attributes & FILE_ATTRIBUTE_READONLY
                else MODE_READ_WRITE)


# --------------------------------------------------------------------------
# The bound Win32 surface
# --------------------------------------------------------------------------

class Api:
    """`kernel32`, bound on demand and never at import.

    Lazy so this module stays importable on macOS and on the Linux worker, and
    so a capability probe costs nothing until something actually opens a file.
    """

    def __init__(self):
        # Every failure mode of binding a Windows-only API from a module that
        # has to stay importable elsewhere: `ctypes.wintypes` imports on some
        # non-Windows builds and `ctypes.WinDLL` then does not exist at all,
        # so an import that succeeds is not evidence the rest will work.
        try:
            import ctypes                                     # noqa: PLC0415
            from ctypes import wintypes                       # noqa: PLC0415
            import msvcrt                                     # noqa: PLC0415
        except (ImportError, ValueError, AttributeError) as exc:
            raise Unavailable(
                "This computer does not expose the Windows file API.") from exc
        try:
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        except (AttributeError, OSError) as exc:
            raise Unavailable(
                "Windows kernel32 could not be loaded on this computer.") from exc

        class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
            _fields_ = [("dwFileAttributes", wintypes.DWORD),
                        ("ftCreationTime", wintypes.FILETIME),
                        ("ftLastAccessTime", wintypes.FILETIME),
                        ("ftLastWriteTime", wintypes.FILETIME),
                        ("dwVolumeSerialNumber", wintypes.DWORD),
                        ("nFileSizeHigh", wintypes.DWORD),
                        ("nFileSizeLow", wintypes.DWORD),
                        ("nNumberOfLinks", wintypes.DWORD),
                        ("nFileIndexHigh", wintypes.DWORD),
                        ("nFileIndexLow", wintypes.DWORD)]

        kernel.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.GetFileInformationByHandle.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(BY_HANDLE_FILE_INFORMATION)]
        kernel.GetFileInformationByHandle.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL

        self._ctypes = ctypes
        self._kernel = kernel
        self._msvcrt = msvcrt
        self._information = BY_HANDLE_FILE_INFORMATION
        self._invalid = invalid_handle(ctypes)

    def open(self, path: str, *, access: int, share: int, disposition: int,
             flags: int) -> int:
        handle = self._kernel.CreateFileW(path, access, share, None,
                                          disposition, flags, None)
        # `None` is a NULL return; `self._invalid` is `(HANDLE)-1` as ctypes
        # actually hands it back. See `invalid_handle` for why a literal -1
        # would silently match nothing.
        if handle is None or handle == self._invalid:
            code = self._ctypes.get_last_error()
            raise WindowsError_(code, _REASONS.get(code, "unreadable"),
                                f"Windows error {code}")
        return handle

    def information(self, handle: int) -> Entry:
        record = self._information()
        if not self._kernel.GetFileInformationByHandle(
                handle, self._ctypes.byref(record)):
            code = self._ctypes.get_last_error()
            raise WindowsError_(code, _REASONS.get(code, "unreadable"),
                                f"Windows error {code}")
        return Entry(
            attributes=int(record.dwFileAttributes),
            device=int(record.dwVolumeSerialNumber),
            inode=(int(record.nFileIndexHigh) << 32) | int(record.nFileIndexLow),
            size=(int(record.nFileSizeHigh) << 32) | int(record.nFileSizeLow),
            links=int(record.nNumberOfLinks))

    def close(self, handle: int) -> None:
        self._kernel.CloseHandle(handle)

    def descriptor(self, handle: int, flags: int) -> int:
        """Adopt a handle as a C-runtime descriptor.

        After this succeeds the descriptor owns the handle: closing the
        descriptor closes it, and closing the handle separately would be a
        double free. Every caller therefore closes exactly one of the two.
        """
        return self._msvcrt.open_osfhandle(handle, flags)

    # The three operations that act on a name rather than on a handle. They
    # are on the API object, not called directly, so that the whole platform
    # surface stays in one injectable place — and so a check can prove no
    # other path reaches the filesystem. Each is safe only because the
    # directory holding the name is pinned by a handle for the call.
    def replace(self, source: str, target: str) -> None:
        os.replace(source, target)

    def unlink(self, path: str) -> None:
        os.unlink(path)

    def entries(self, path: str) -> list[tuple[str, int, int, int]]:
        """(name, attributes, size, links) for each immediate child."""
        found = []
        with os.scandir(path) as scan:
            for item in scan:
                try:
                    info = item.stat(follow_symlinks=False)
                except OSError:
                    continue
                found.append((item.name, getattr(info, "st_file_attributes", 0),
                              info.st_size, getattr(info, "st_nlink", 1) or 1))
        return found


def supported() -> bool:
    """Whether this computer can give the containment guarantee.

    An observation, not a platform name: a Windows build without the API is
    reported the same way a non-Windows one is, because the consequence for
    the user is identical.
    """
    if sys.platform != "win32":
        return False
    try:
        Api()
    except Unavailable:
        return False
    return True


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

def extended(path: str) -> str:
    """The `\\\\?\\` form of an absolute path.

    Two reasons, both load-bearing. It lifts the 260-character limit, and it
    turns off Win32 path normalisation — so a component is used exactly as
    `repo.normalise_relative` validated it, and cannot be re-interpreted into
    a different one by a trailing dot, a trailing space or a device name.
    """
    text = str(path)
    if text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text[2:]
    return "\\\\?\\" + text


def join(parent: str, name: str) -> str:
    return parent.rstrip("\\") + "\\" + name


# --------------------------------------------------------------------------
# Pinned traversal
# --------------------------------------------------------------------------

class Directory:
    """A directory held open, and the operations allowed inside it.

    While this object lives, its directory cannot be renamed or deleted, so
    the full paths built from `path` keep naming the objects they named when
    each handle in the chain was checked.
    """

    def __init__(self, path: str, entry: Entry, api: Api):
        self.path = path
        self.entry = entry
        self._api = api

    # -- reads
    def open_file(self, name: str) -> tuple[int, Entry]:
        """Open one child for reading, refusing a link or a directory.

        Returns a descriptor the caller must close and the identity read from
        the handle *before* the descriptor was adopted.
        """
        # Deliberately without FILE_FLAG_BACKUP_SEMANTICS. A file open does not
        # need it, and it is the flag that lets a process holding backup
        # privilege read a file its permissions forbid — which would quietly
        # widen what a connected folder exposes. The cost is that opening a
        # *directory* by this path fails with access denied rather than
        # reporting "not an ordinary file"; the refusal is the same, only its
        # wording differs from the POSIX backend.
        handle = self._api.open(join(self.path, name), access=GENERIC_READ,
                                share=SHARE_READ_WRITE,
                                disposition=OPEN_EXISTING,
                                flags=FILE_FLAG_OPEN_REPARSE_POINT)
        return self._adopt(handle, _BINARY)

    def create_file(self, name: str) -> tuple[int, Entry]:
        """Create one child exclusively, for the temporary file a write uses.

        `CREATE_NEW` fails when the name exists, which is the same refusal
        `O_CREAT | O_EXCL` gives on POSIX: a temporary file is never allowed
        to land on top of something already there.
        """
        handle = self._api.open(join(self.path, name), access=GENERIC_WRITE,
                                share=SHARE_READ_WRITE,
                                disposition=CREATE_NEW,
                                flags=FILE_FLAG_OPEN_REPARSE_POINT)
        return self._adopt(handle, _BINARY)

    def _adopt(self, handle: int, flags: int) -> tuple[int, Entry]:
        try:
            entry = self._api.information(handle)
            if entry.is_reparse_point:
                raise WindowsError_(
                    0, "symlink", "the name is a link, which Refinix does not follow")
            if entry.is_directory:
                raise WindowsError_(0, "not_regular", "the name is a folder")
        except BaseException:
            self._api.close(handle)
            raise
        try:
            descriptor = self._api.descriptor(handle, flags)
        except BaseException:
            # The handle is still ours until `descriptor` succeeds.
            self._api.close(handle)
            raise
        return descriptor, entry

    def stat(self, name: str) -> Entry:
        """One child's identity, read through a handle rather than a path."""
        handle = self._api.open(
            join(self.path, name), access=METADATA_ONLY, share=SHARE_READ_WRITE,
            disposition=OPEN_EXISTING,
            flags=FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS)
        try:
            return self._api.information(handle)
        finally:
            self._api.close(handle)

    # -- writes
    def replace(self, source: str, target: str) -> None:
        """Move `source` over `target` inside this pinned directory.

        `os.replace` is `MoveFileExW(..., MOVEFILE_REPLACE_EXISTING)`, which
        acts on the destination *name*: a link left in place of the target is
        replaced rather than followed. It is used by full path because this
        directory is pinned, so the prefix cannot have changed underneath it.
        """
        self._api.replace(join(self.path, source), join(self.path, target))

    def unlink(self, name: str) -> None:
        try:
            self._api.unlink(join(self.path, name))
        except OSError:
            pass                      # cleaning up a temporary file is best effort

    def entries(self) -> list[tuple[str, Entry]]:
        """Immediate children, with the attributes each one reported.

        The scan reaches the directory this object holds open, so no name can
        be redirected while it is read. The per-entry values come from the
        directory scan Windows already performed, which is why a listing is
        only an *offer*: `open_file` verifies identity, links and size through
        a handle before one byte is read.
        """
        return [(name, Entry(attributes=attributes, device=0, inode=0,
                             size=size, links=links))
                for name, attributes, size, links in self._api.entries(self.path)]

    @contextmanager
    def child(self, name: str):
        """Descend into one subdirectory while this one stays pinned.

        The step a walk takes. `self` is still held for the whole body, so the
        prefix the child's full path is built from cannot be renamed or
        deleted underneath it — which is what makes opening the child by name
        equivalent to `openat` on POSIX.
        """
        with _directory(self._api, join(self.path, name),
                        symlink_reason="symlink",
                        symlink_message=f"{name} is a link, which Refinix does "
                                        "not follow",
                        not_directory_reason="bad_path",
                        not_directory_message=f"{name} is not a folder") as folder:
            yield folder


@contextmanager
def _directory(api: Api, path: str, *, symlink_reason: str,
               symlink_message: str, not_directory_reason: str,
               not_directory_message: str):
    """Open one directory, refuse a link, hold it, and release it after.

    The single place a directory handle is taken, so the root and every
    component below it are opened with identical flags and checked in the
    same order — the two differ only in the words their refusals use.
    """
    handle = api.open(path, access=METADATA_ONLY, share=SHARE_READ_WRITE,
                      disposition=OPEN_EXISTING,
                      flags=FILE_FLAG_BACKUP_SEMANTICS
                      | FILE_FLAG_OPEN_REPARSE_POINT)
    try:
        entry = api.information(handle)
        if entry.is_reparse_point:
            raise WindowsError_(0, symlink_reason, symlink_message)
        if not entry.is_directory:
            raise WindowsError_(0, not_directory_reason, not_directory_message)
        yield Directory(path, entry, api)
    finally:
        try:
            api.close(handle)
        except Exception:                                  # noqa: BLE001
            pass


@contextmanager
def root_directory(root, *, api: Api | None = None):
    """Open a connected folder itself, and hold it for the body."""
    api = api if api is not None else Api()
    with _directory(api, extended(os.path.abspath(str(root))),
                    symlink_reason="symlinked_root",
                    symlink_message="the connected folder is a link",
                    not_directory_reason="not_a_directory",
                    not_directory_message="the connected folder is not a folder"
                    ) as folder:
        yield folder


@contextmanager
def pinned(root, parts, *, api: Api | None = None):
    """Hold `root` and every name in `parts` open, and yield the last one.

    The whole chain stays open for the body: pinning only the final directory
    would leave every directory above it free to be swapped for a junction
    while the operation ran, which is exactly the substitution this prevents.
    `ExitStack` is what keeps that true — every handle taken on the way down is
    released on the way out, including after a refusal partway through.
    """
    with ExitStack() as stack:
        folder = stack.enter_context(root_directory(root, api=api))
        for part in parts:
            folder = stack.enter_context(folder.child(part))
        yield folder
