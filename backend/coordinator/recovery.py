"""Keeping the previous version's data so an update can be undone.

The data side of update and rollback recovery, run only by a process that
holds the workspace lock for the whole operation (`ownership.require`). That
lock is what every writer of the workspace database must hold, so holding it
proves no other Refinix is writing; the engine never writes the database.

    set_aside   before a newer version first opens the workspace: copy the
                database and its write-ahead log (never the -shm, which SQLite
                rebuilds) into recovery/set-aside/<version>[-<update id>]/, each
                file journalled with its size and SHA-256 and flushed to disk.
                The journal names the update attempt (`update_id`), both
                versions and the data root, so a later attempt can tell its own
                record from an earlier update's. A finished earlier journal is
                kept beside that update's set-aside copy before it is replaced.
    commit      the newer version started and checked itself: the update is
                finished; the set-aside copy is kept until the next update.
    discard     the attempt stopped before the newer version ran: when the
                workspace still matches the set-aside copy byte for byte, the
                attempt is closed with nothing restored.
    restore     going back: move the attempted version's database files into
                recovery/attempted/<version>-<time>/ (nothing is deleted), then
                put each verified set-aside file back through a temporary file
                in the same folder and an atomic replace.
    resume      after a crash: finish an interrupted set-aside or restore from
                what is on disk, checked by location and hash.

Which of commit, discard or restore follows an attempt is decided by the
update helper (`desktop/update_apply.py`) while it holds the workspace lock,
never by an ordinary launch: a launch only finishes an interrupted copy.

Every step is written to recovery/update-journal.json before and after it
happens. `db.admit` refuses to open the workspace while the journal is in a
non-final state, so an ordinary launch cannot write in the middle. When a
step cannot be completed safely — a copy no longer matches its hash, or a
database file appears that should not exist — the journal records
`recovery_blocked` and nothing further is changed.

Attachments, artifacts, models and Code backups are files the database rows
refer to; they stay where they are, so work created by the newer version is
not deleted by going back.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from backend.coordinator import ownership

JOURNAL = "update-journal.json"
FINAL = ("staged", "committed", "rolled_back", "rolled_back_with_data", "discarded")
SIDECARS = ("-wal", "-shm", "-journal")
CHUNK = 4 * 1024 * 1024


class RecoveryError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def _fsync_dir(folder: Path) -> None:
    if sys.platform == "win32":
        return
    descriptor = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _copy_durably(source: Path, target: Path) -> None:
    """Copy through a temporary file beside `target`, then replace atomically."""
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    shutil.copyfile(source, temporary)
    with open(temporary, "rb") as handle:
        os.fsync(handle.fileno())
    os.replace(temporary, target)
    _fsync_dir(target.parent)


class Recovery:
    """The journalled data steps for one workspace database."""

    def __init__(self, owner, database: Path):
        self.database = ownership.canonical_database(database)
        ownership.require(owner, self.database)
        self.owner = owner
        self.root = self.database.parent / "recovery"
        self.journal_path = self.root / JOURNAL

    # -- the journal -------------------------------------------------------
    def read(self) -> dict | None:
        try:
            return json.loads(self.journal_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as exc:
            raise RecoveryError("unreadable_journal",
                                f"The update journal cannot be read: {exc}") from exc

    def _write(self, record: dict) -> dict:
        ownership.require(self.owner, self.database)       # still ours, every step
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        record = {**record, "updated_at": _stamp()}
        temporary = self.journal_path.with_name(JOURNAL + ".tmp")
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.journal_path)
        _fsync_dir(self.root)
        return record

    def _block(self, record: dict, why: str) -> dict:
        return self._write({**record, "state": "recovery_blocked", "blocked": why})

    def block(self, why: str) -> dict:
        """Stop this journal where it is, saying why; nothing else changes."""
        record = self.read()
        if not record:
            raise RecoveryError("nothing_to_block", "There is no update journal.")
        return self._block(record, why)

    def _canonical(self) -> list[Path]:
        return [self.database] + [Path(f"{self.database}{s}") for s in SIDECARS]

    # -- set aside ---------------------------------------------------------
    def set_aside(self, *, from_version: str, to_version: str,
                  update_id: str | None = None, data_root: str | None = None) -> dict:
        """Copy the current database and WAL before a newer version opens them."""
        current = self.read()
        if current and current.get("state") not in FINAL:
            raise RecoveryError("in_progress", "An update step is already in progress.")
        journal = Path(f"{self.database}-journal")
        if journal.exists() and journal.stat().st_size:
            raise RecoveryError("hot_journal", "The database has an unfinished write "
                                               "and cannot be copied safely.")
        name = f"{from_version}-{update_id}" if update_id else from_version
        folder = self.root / "set-aside" / name
        files = []
        for source in (self.database, Path(f"{self.database}-wal")):
            if source.exists():
                files.append({"name": source.name, "size": source.stat().st_size,
                              "sha256": _sha256(source), "done": False})
        if not files:
            raise RecoveryError("no_database", "There is no workspace database to keep.")
        if current:
            self._keep_previous(current)
        record = self._write({"state": "setting_aside", "from_version": from_version,
                              "to_version": to_version, "set_aside": str(folder),
                              "update_id": update_id, "data_root": data_root,
                              "files": files, "started_at": _stamp()})
        return self._finish_set_aside(record)

    def _keep_previous(self, record: dict) -> None:
        """Keep a finished journal beside its own set-aside copy before replacing it."""
        folder = Path(record["set_aside"]) if record.get("set_aside") else None
        if folder is None or not folder.is_dir():
            folder = self.root / "history"
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        stamp = str(record.get("update_id") or record.get("updated_at") or _stamp())
        target = folder / f"update-journal-{stamp.replace(':', '')}.json"
        if target.exists():
            return
        _copy_durably(self.journal_path, target)

    def matches(self, *, update_id: str, from_version: str, to_version: str,
                data_root: str | None = None) -> dict | None:
        """The journal, when it belongs to exactly this update attempt."""
        record = self.read()
        if not record or not update_id or record.get("update_id") != update_id:
            return None
        if (record.get("from_version"), record.get("to_version")) != (from_version,
                                                                      to_version):
            return None
        if data_root is not None and record.get("data_root") not in (None, data_root):
            return None
        return record

    def _finish_set_aside(self, record: dict) -> dict:
        folder = Path(record["set_aside"])
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        for item in record["files"]:
            source = self.database.parent / item["name"]
            target = folder / item["name"]
            if target.exists() and target.stat().st_size == item["size"] \
                    and _sha256(target) == item["sha256"]:
                item["done"] = True
                continue
            if not source.exists() or _sha256(source) != item["sha256"]:
                return self._block(record, f"{item['name']} changed while it was being "
                                           "kept, so the copy could not be completed")
            _copy_durably(source, target)
            if _sha256(target) != item["sha256"]:
                return self._block(record, f"the kept copy of {item['name']} does not "
                                           "match the original")
            item["done"] = True
            record = self._write(record)
        return self._write({**record, "state": "set_aside"})

    # -- after the newer version ran ---------------------------------------
    def commit(self, update_id: str | None = None) -> dict:
        record = self.read()
        if not record or record.get("state") not in ("set_aside", "verifying"):
            raise RecoveryError("nothing_to_commit", "There is no update to finish.")
        if update_id is not None and record.get("update_id") != update_id:
            raise RecoveryError("not_this_update", "The kept data belongs to another "
                                                   "update, so nothing was finished.")
        return self._write({**record, "state": "committed", "committed_at": _stamp()})

    def unchanged(self, record: dict | None = None) -> bool:
        """Whether the workspace is still exactly what was set aside."""
        record = record or self.read() or {}
        kept = {item["name"]: item["sha256"] for item in record.get("files") or []}
        for path in self._canonical():
            if path.name.endswith("-shm"):
                continue                       # rebuilt by SQLite, never kept
            present = path.exists() and (path.stat().st_size > 0
                                         or path.name in kept)
            if path.name not in kept:
                if present:
                    return False
            elif not path.exists() or _sha256(path) != kept[path.name]:
                return False
        return True

    def discard(self, update_id: str | None = None) -> dict:
        """Close an attempt the newer version never ran, when nothing changed."""
        record = self.read()
        if not record or record.get("state") not in ("set_aside", "verifying"):
            raise RecoveryError("nothing_to_discard", "There is no kept copy to release.")
        if update_id is not None and record.get("update_id") != update_id:
            raise RecoveryError("not_this_update", "The kept data belongs to another "
                                                   "update, so it was left alone.")
        if not self.unchanged(record):
            raise RecoveryError("changed", "The workspace changed after it was set "
                                           "aside, so the attempt was not discarded.")
        return self._write({**record, "state": "discarded", "discarded_at": _stamp()})

    # -- going back --------------------------------------------------------
    def restore(self) -> dict:
        """Put the kept database back, keeping the attempted version's files aside."""
        record = self.read()
        if not record or record.get("state") not in ("set_aside", "verifying",
                                                     "committed", "restoring"):
            raise RecoveryError("nothing_to_restore",
                                "There is no kept copy of the previous version's data.")
        if record.get("state") != "restoring":
            folder = Path(record["set_aside"])
            for item in record["files"]:
                kept = folder / item["name"]
                if not kept.exists() or _sha256(kept) != item["sha256"]:
                    return self._block(record, f"the kept copy of {item['name']} is "
                                               "missing or changed, so nothing was restored")
            attempted = self.root / "attempted" / \
                f"{record['to_version']}-{int(time.time())}"
            moves = [{"name": path.name, "size": path.stat().st_size,
                      "sha256": _sha256(path), "done": False}
                     for path in self._canonical() if path.exists()]
            record = self._write({**record, "state": "restoring",
                                  "attempted": str(attempted), "moves": moves,
                                  "restores": [{"name": i["name"], "done": False}
                                               for i in record["files"]]})
        return self._finish_restore(record)

    def _finish_restore(self, record: dict) -> dict:
        attempted = Path(record["attempted"])
        attempted.mkdir(parents=True, exist_ok=True, mode=0o700)
        # 1. The attempted version's files, moved (same volume) and kept.
        for move in record["moves"]:
            if move["done"]:
                continue
            source = self.database.parent / move["name"]
            target = attempted / move["name"]
            if target.exists() and _sha256(target) == move["sha256"]:
                move["done"] = True
            elif source.exists() and _sha256(source) == move["sha256"]:
                os.replace(source, target)
                _fsync_dir(attempted)
                _fsync_dir(self.database.parent)
                move["done"] = True
            else:
                return self._block(record, f"{move['name']} is neither in place nor kept "
                                           "with its recorded hash")
            record = self._write(record)
        # 2. Nothing the previous version did not write may remain beside it.
        restoring = {item["name"] for item in record["files"]}
        stray = [path.name for path in self._canonical()
                 if path.exists() and path.name not in restoring]
        if stray:
            return self._block(record, "these files appeared during the restore and "
                                       "were left untouched: " + ", ".join(stray))
        # 3. The kept files, back through a temporary file and an atomic replace.
        folder = Path(record["set_aside"])
        hashes = {item["name"]: item["sha256"] for item in record["files"]}
        for step in record["restores"]:
            if step["done"]:
                continue
            target = self.database.parent / step["name"]
            if not (target.exists() and _sha256(target) == hashes[step["name"]]):
                kept = folder / step["name"]
                if not kept.exists() or _sha256(kept) != hashes[step["name"]]:
                    return self._block(record, f"the kept copy of {step['name']} "
                                               "changed during the restore")
                _copy_durably(kept, target)
            step["done"] = True
            record = self._write(record)
        return self._write({**record, "state": "rolled_back_with_data",
                            "restored_at": _stamp()})

    # -- after a crash -------------------------------------------------------
    def resume(self) -> dict | None:
        """Finish an interrupted step from what is on disk, or report why not."""
        record = self.read()
        if not record or record.get("state") in FINAL:
            return record
        if record["state"] == "setting_aside":
            return self._finish_set_aside(record)
        if record["state"] == "restoring":
            return self._finish_restore(record)
        return record                                      # set_aside / verifying / blocked


def at_startup(owner, database: Path, running_version: str) -> dict | None:
    """What a launch does with an update journal before opening the workspace.

    Only an interrupted copy is finished here: a set-aside or a restore that a
    crash stopped is completed from what is on disk. A launch never starts a
    restore and never commits; the update helper decides those while it holds
    the workspace lock. Any other unfinished state is left for the admission
    check to refuse and explain.
    """
    recovery = Recovery(owner, database)
    record = recovery.read()
    if not record or record.get("state") in FINAL:
        return record
    if record["state"] in ("setting_aside", "restoring"):
        return recovery.resume()
    return record
