"""Who may write one workspace's canonical store, for as long as it writes.

One process owns one data root at a time. The owner holds an operating-system
lock on a file beside the database it is about to open, takes it *before* any
SQLite access to that database, and keeps it until the coordinator using that
database has closed. Every entry point that can open a workspace — the desktop
window, the packaged application, `python -m desktop --no-window` and
`python -m backend.coordinator` — goes through this one rule.

The lock follows the database actually selected, including an explicit
`--state`. It used to be fixed to the default root's `desktop.lock`, so a run
against another database was guarded by a lock over the wrong data and a second
run against the same explicit path was not guarded at all.

Every spelling of one store meets the same lock. A path is reduced to its
canonical form (`canonical_database`) before anything is derived from it: a
symbolic link to the database, a linked parent folder or `..` all lead to the
real file, which is also where SQLite itself keeps the write log. Without that,
`other/state.sqlite3 -> root/state.sqlite3` took `other/desktop.lock` and a
second writer opened the same database beside the first. A hard link cannot be
reduced to one spelling, so admission refuses a database that has more than one
(`db.admit`, code `alias`).

The file keeps its historical name, `desktop.lock`, so an older build sharing
the default root still excludes a newer one. The OS releases the lock when the
holding process dies, so a crash never leaves a workspace permanently owned.

Standard library only.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

LOCK_NAME = "desktop.lock"


class OwnershipError(RuntimeError):
    """The caller does not own the workspace it is about to open."""


def canonical_database(state_path) -> Path:
    """The one spelling of a store: absolute, with every symbolic link resolved.

    The lock, the admission copy, SQLite's own sidecar files and the
    workspace's attachment, artifact and model folders are all derived from
    this path, so two spellings of one database are one workspace.
    """
    return Path(os.path.realpath(os.path.abspath(os.fspath(state_path))))


def lock_path(state_path) -> Path:
    """The lock file that guards `state_path`: beside the real database."""
    return canonical_database(state_path).parent / LOCK_NAME


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


class WorkspaceLock:
    """An exclusive, crash-safe lock over one data root.

    `acquire` returns None when this process now owns the root, or the
    metadata the current owner recorded (possibly empty) when another process
    does. `record` publishes small facts about the owner, such as its port, for
    a second launch to read.
    """

    def __init__(self, path: Path):
        self.path = canonical_database(path)
        self._handle = None
        # Windows byte locks also deny reads. Keep JSON after the locked byte.
        self._metadata_offset = 1 if sys.platform == "win32" else 0

    @classmethod
    def for_database(cls, state_path) -> "WorkspaceLock":
        return cls(lock_path(state_path))

    @property
    def held(self) -> bool:
        return self._handle is not None

    @property
    def root(self) -> Path:
        return self.path.parent

    def covers(self, state_path) -> bool:
        """Whether this lock is the one that guards `state_path`.

        Compared by file identity as well as by spelling: on a case-insensitive
        volume two spellings of one folder name the same lock file.
        """
        expected = lock_path(state_path)
        if expected == self.path:
            return True
        try:
            return os.path.samefile(expected, self.path)
        except OSError:
            return False

    def acquire(self) -> dict | None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
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


def require(owner, state_path) -> None:
    """Refuse unless `owner` currently holds the lock guarding `state_path`."""
    if owner is None or not getattr(owner, "held", False) \
            or not owner.covers(state_path):
        raise OwnershipError(
            f"This process does not own the workspace at {Path(state_path).parent}; "
            "it must take that workspace's lock before opening its database.")
