"""SQLite state for the coordinator.

The coordinator owns canonical state. Everything a surface displays comes from
here, so a restart cannot lose a job's history or invent one.

Records are validated through the shared contract in `backend.contracts.v1`
before they are written, which is what makes this a real contract consumer
rather than a parallel schema.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from unicodedata import category

from backend.contracts import v1
from backend.coordinator import build_info, ownership

SCHEMA_VERSION = 14

# SQLite's header field for "which application owns this file" (offset 68).
# "RFNX". Written on every open from now on; a legacy Refinix store still has 0
# and is recognised by its `meta` table instead. Any other nonzero value is a
# file that belongs to some other program.
APPLICATION_ID = 0x52464E58

# ponytail: one coordinator database; use per-database locks if hosting several.
LOCK = threading.RLock()


def serialized(operation):
    @wraps(operation)
    def call(*args, **kwargs):
        with LOCK:
            return operation(*args, **kwargs)
    return call


# --------------------------------------------------------------------------
# Admission: may this build open this store at all?
# --------------------------------------------------------------------------
#
# Opening an SQLite file is not a neutral read. A read-only connection to a WAL
# database may still create or update the `-shm` and `-wal` files, and
# `connect` below changes permissions, the journal mode and the schema. So the
# decision is made first, on a coherent private copy, while the caller owns the
# workspace and no writer can run. The canonical main, `-wal`, `-shm` and
# `-journal` files are only ever read here; a refusal leaves each of them with
# its existence, size, modification time and bytes unchanged.

ADMISSION_DIRECTORY = "tmp"
_ADMISSION_PREFIX = "admission-"


class AdmissionRefused(RuntimeError):
    """This build must not open the store. Nothing was changed."""

    def __init__(self, code: str, message: str, detail: str = ""):
        super().__init__(message)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class Admission:
    """The outcome of checking one store before it is opened for writing."""

    path: Path
    kind: str                         # "new" | "existing"
    schema_version: int | None
    workspace_id: str | None
    application_id: int | None
    fingerprint: tuple


def _sidecars(path: Path) -> dict[str, Path]:
    return {"wal": Path(f"{path}-wal"), "shm": Path(f"{path}-shm"),
            "journal": Path(f"{path}-journal")}


def _stat(path: Path):
    try:
        status = path.stat()
    except FileNotFoundError:
        return None
    return (status.st_size, status.st_mtime_ns)


def _fingerprint(path: Path) -> tuple:
    files = _sidecars(path)
    return (_stat(path), _stat(files["wal"]), _stat(files["journal"]))


def _recovery_pending(root: Path) -> str | None:
    """An unfinished update recovery owns the store; no ordinary open may run."""
    journal = root / "recovery" / "update-journal.json"
    try:
        record = json.loads(journal.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return "the update journal could not be read"
    state = record.get("state") if isinstance(record, dict) else None
    if state in (None, "staged", "committed", "rolled_back",
                 "rolled_back_with_data", "discarded"):
        return None
    if state in ("set_aside", "verifying") \
            and record.get("to_version") == build_info.describe()["version"]:
        return None              # the version being verified opens its own update
    if state == "recovery_blocked":
        return ("an update recovery stopped before it could finish safely: "
                f"{record.get('blocked') or 'no reason was recorded'}")
    return f"an update or recovery step is still in progress ({state})"


def clear_stale_admissions(root: Path) -> None:
    """Remove private copies left by an admission that was interrupted."""
    folder = Path(root) / ADMISSION_DIRECTORY
    try:
        entries = list(folder.iterdir())
    except OSError:
        return
    import shutil
    for entry in entries:
        if entry.name.startswith(_ADMISSION_PREFIX) and entry.is_dir() \
                and not entry.is_symlink():
            shutil.rmtree(entry, ignore_errors=True)


def admit(path: Path, *, owner=None) -> Admission:
    """Decide from a private copy whether this build may open `path`.

    `owner`, when given, must be the lock that guards `path`; production entry
    points always pass it. Raises `AdmissionRefused` with a code the interface
    can explain: `recovery_pending`, `alias`, `ambiguous`, `hot_journal`,
    `insufficient_space`, `active_writer`, `corrupt`, `foreign`, `metadata` or
    `schema_newer`.

    `path` is reduced to the real database first, so the copy, the sidecars and
    the returned `Admission.path` all name the file SQLite will open.
    """
    import shutil
    import tempfile

    path = ownership.canonical_database(path)
    if owner is not None:
        ownership.require(owner, path)
    root = path.parent
    files = _sidecars(path)
    pending = _recovery_pending(root)
    if pending:
        blocked = pending.startswith("an update recovery stopped")
        raise AdmissionRefused(
            "recovery_blocked" if blocked else "recovery_pending",
            ("An update recovery for this workspace stopped before it could finish."
             if blocked else
             "Refinix is finishing an update recovery for this workspace."),
            f"Nothing was opened: {pending}. " + (
                "The previous and the newer data are both kept in the workspace's "
                "recovery folder; nothing will open this workspace until that is "
                "resolved." if blocked else
                "Open Refinix again to let the recovery finish, or restart the "
                "computer if it does not."))
    try:
        links = path.stat().st_nlink
    except FileNotFoundError:
        links = 1
    if links > 1:
        # A hard link is a second name with its own folder and its own lock.
        # Nothing can tell which name another writer is using, so neither is
        # opened.
        raise AdmissionRefused(
            "alias",
            "The workspace database is reachable under more than one name.",
            f"It has {links} hard links, so another copy of Refinix could open it "
            "under a different name at the same time. Keep one copy of the file "
            "and remove the other names. Nothing was changed.")

    if not path.exists() or path.stat().st_size == 0:
        stray = [name for name in ("wal", "journal")
                 if files[name].exists() and files[name].stat().st_size > 0]
        if stray:
            raise AdmissionRefused(
                "ambiguous",
                "The workspace database is missing but its write log is not.",
                "Refinix will not start a new workspace over a "
                f"{' and '.join(stray)} file that belongs to a store it cannot "
                "see. Nothing was changed.")
        return Admission(path, "new", None, None, None, _fingerprint(path))

    journal = files["journal"]
    if journal.exists() and journal.stat().st_size > 0:
        raise AdmissionRefused(
            "hot_journal",
            "The workspace database has an unfinished write from another program.",
            "A rollback journal is next to it, which Refinix itself never "
            "creates. Nothing was changed.")

    before = _fingerprint(path)
    wal = files["wal"]
    wal_size = wal.stat().st_size if wal.exists() else 0
    needed = path.stat().st_size + wal_size
    staging_root = root / ADMISSION_DIRECTORY
    try:
        free = shutil.disk_usage(root).free
    except OSError:
        free = 0
    if free < needed * 2 + 16 * 1024 * 1024:
        raise AdmissionRefused(
            "insufficient_space",
            "There is not enough free disk space to check the workspace safely.",
            f"About {(needed * 2) // (1024 * 1024) + 16} MB is needed beside the "
            "workspace. Nothing was changed.")

    staging_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    workdir = Path(tempfile.mkdtemp(prefix=_ADMISSION_PREFIX, dir=staging_root))
    try:
        copy = workdir / path.name
        shutil.copyfile(path, copy)
        if wal_size:
            shutil.copyfile(wal, Path(f"{copy}-wal"))
        if _fingerprint(path) != before:
            raise AdmissionRefused(
                "active_writer",
                "Another program changed the workspace while Refinix checked it.",
                "Close any other copy of Refinix or tool using this folder, then "
                "open Refinix again. Nothing was changed.")
        try:
            conn = sqlite3.connect(copy, timeout=5)
        except sqlite3.Error as exc:
            raise AdmissionRefused("corrupt", "The workspace database cannot be read.",
                                   str(exc)) from exc
        try:
            try:
                check = conn.execute("PRAGMA quick_check").fetchone()
                objects = conn.execute(
                    "SELECT type, name FROM sqlite_master").fetchall()
                application_id = conn.execute("PRAGMA application_id").fetchone()[0]
                user_version = conn.execute("PRAGMA user_version").fetchone()[0]
            except sqlite3.DatabaseError as exc:
                raise AdmissionRefused(
                    "corrupt", "The workspace database is not a readable SQLite "
                    "database.", str(exc)) from exc
            if not check or check[0] != "ok":
                raise AdmissionRefused(
                    "corrupt", "The workspace database failed its integrity check.",
                    str(check[0] if check else "no result"))
            if application_id not in (0, APPLICATION_ID):
                raise AdmissionRefused(
                    "foreign", "This file belongs to another application.",
                    f"Its SQLite application id is {application_id:#x}. "
                    "Nothing was changed.")
            tables = {name for kind, name in objects if kind == "table"}
            if not objects and application_id == 0:
                # Empty is new only when nothing else has claimed the file: a
                # versioned empty database was made by some other program.
                if user_version != 0:
                    raise AdmissionRefused(
                        "foreign", "This file belongs to another application.",
                        f"It is an empty SQLite database marked with format "
                        f"{user_version} by another program. Nothing was changed.")
                return Admission(path, "new", None, None, application_id, before)
            if "meta" not in tables:
                raise AdmissionRefused(
                    "foreign", "This file is not a Refinix workspace database.",
                    "It has no Refinix metadata. Nothing was changed.")
            try:
                meta = {str(key): value for key, value in conn.execute(
                    "SELECT key, value FROM meta").fetchall()}
            except sqlite3.Error as exc:
                raise AdmissionRefused(
                    "metadata", "The workspace database's Refinix metadata cannot "
                    "be read.", f"{exc}. Nothing was changed.") from exc
        finally:
            conn.close()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    raw = meta.get("schema_version")
    try:
        version = int(raw)
    except (TypeError, ValueError):
        version = None
    if version is None or version < 1:
        raise AdmissionRefused(
            "metadata", "The workspace database has no valid format version.",
            f"Recorded value: {raw!r}. Nothing was changed.")
    if version > SCHEMA_VERSION:
        raise AdmissionRefused(
            "schema_newer",
            "This workspace was saved by a newer version of Refinix.",
            f"Its data format is {version}; this version reads up to "
            f"{SCHEMA_VERSION}. Nothing was changed. Open it with the newer "
            "version, or use its Settings → Updates to restore the previous "
            "version together with its saved data.")
    return Admission(path, "existing", version, meta.get("workspace_id"),
                     application_id, before)

# WAL lets the event reader see committed writes while a generation is running.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chats (
    chat_id      TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    title        TEXT NOT NULL,
    pinned       INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    open_path    TEXT
);
-- Unsent drafts are workspace-owned local state, never model input and never
-- part of search or export. The NEW_CHAT_DRAFT slot holds a draft typed before
-- a conversation exists.
CREATE TABLE IF NOT EXISTS drafts (
    chat_id    TEXT PRIMARY KEY,
    text       TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    chat_id    TEXT NOT NULL REFERENCES chats(chat_id),
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    text       TEXT NOT NULL,
    created_at TEXT NOT NULL,
    job_id     TEXT
);
CREATE INDEX IF NOT EXISTS messages_by_chat ON messages(chat_id, created_at);
CREATE TABLE IF NOT EXISTS jobs (
    job_id            TEXT PRIMARY KEY,
    workspace_id      TEXT NOT NULL,
    workflow_id       TEXT NOT NULL,
    chat_id           TEXT NOT NULL REFERENCES chats(chat_id),
    state             TEXT NOT NULL,
    active_attempt_id TEXT,
    original_request  TEXT NOT NULL,
    task_type         TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_by_chat ON jobs(chat_id, created_at);
CREATE TABLE IF NOT EXISTS attempts (
    attempt_id   TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    job_id       TEXT NOT NULL REFERENCES jobs(job_id),
    step_id      TEXT NOT NULL,
    retry_of     TEXT,
    node_id      TEXT NOT NULL,
    model_json   TEXT,
    state        TEXT NOT NULL,
    route_reason TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    started_at   TEXT,
    finished_at  TEXT,
    queue_ms     INTEGER,
    runtime_ms   INTEGER,
    metrics_json TEXT,
    selection_json TEXT,
    requested_inference_json TEXT,
    actual_profile_json TEXT,
    error_json   TEXT,
    output_text  TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS attempts_by_job ON attempts(job_id, created_at);
CREATE TABLE IF NOT EXISTS events (
    event_id         TEXT PRIMARY KEY,
    workspace_id     TEXT NOT NULL,
    job_id           TEXT NOT NULL REFERENCES jobs(job_id),
    attempt_id       TEXT,
    sequence         INTEGER NOT NULL,
    producer_node_id TEXT NOT NULL,
    producer         TEXT NOT NULL,
    occurred_at      TEXT NOT NULL,
    data_json        TEXT NOT NULL,
    UNIQUE (job_id, sequence)
);
CREATE INDEX IF NOT EXISTS events_by_job ON events(job_id, sequence);
-- Files the user selected for a request. Intake stores them as `received`;
-- a request-scoped local reader may later extract them.
-- chat_id carries the NEW_CHAT_DRAFT slot before a conversation exists, so it
-- deliberately has no foreign key.
CREATE TABLE IF NOT EXISTS attachments (
    attachment_id TEXT PRIMARY KEY,
    workspace_id  TEXT NOT NULL,
    chat_id       TEXT NOT NULL,
    message_id    TEXT,
    filename      TEXT NOT NULL,
    media_type    TEXT NOT NULL,
    byte_size     INTEGER NOT NULL,
    sha256        TEXT NOT NULL,
    stored_name   TEXT NOT NULL,
    state         TEXT NOT NULL CHECK (state IN ('received', 'sent')),
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS attachments_by_chat ON attachments(chat_id, created_at);
-- Execution 2 -------------------------------------------------------------
-- Per-model reasoning choice. Coordinator-owned so it survives a restart and a
-- fallback port, unlike origin-scoped browser storage.
CREATE TABLE IF NOT EXISTS model_prefs (
    model      TEXT PRIMARY KEY,
    reasoning  INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS model_selections (
    scope      TEXT PRIMARY KEY,
    model      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
-- One capability self-test result per model and workflow. `digest` is the
-- manifest the result was observed against: replacing a model's bytes under
-- the same tag must not inherit its pass, and the row stays so the fact that a
-- check was once run is not lost either.
CREATE TABLE IF NOT EXISTS model_selftests (
    model           TEXT NOT NULL,
    scope           TEXT NOT NULL,
    state           TEXT NOT NULL,
    detail          TEXT NOT NULL,
    digest          TEXT,
    runtime_version TEXT,
    ran_at          TEXT NOT NULL,
    PRIMARY KEY (model, scope)
);
-- A folder the user connected through the native picker. `root` is the
-- canonical absolute path and never leaves the coordinator: the page and the
-- model see `repo_id` and relative paths only.
CREATE TABLE IF NOT EXISTS repositories (
    repo_id       TEXT PRIMARY KEY,
    workspace_id  TEXT NOT NULL,
    name          TEXT NOT NULL,
    root          TEXT NOT NULL,
    identity_json TEXT NOT NULL,
    mode          TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS proposals (
    proposal_id  TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    repo_id      TEXT NOT NULL,
    job_id       TEXT,
    attempt_id   TEXT,
    request      TEXT NOT NULL,
    summary      TEXT NOT NULL,
    digest       TEXT NOT NULL,
    selection_json TEXT NOT NULL DEFAULT '[]',
    state        TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
-- AF-011. One row per validation attempt against a proposal. `passed` is
-- written only from a validation result the sandbox actually returned; a
-- Kubernetes error, a deadline or an unreadable log leaves it 0 with the
-- reason recorded, never absent-and-assumed.
CREATE TABLE IF NOT EXISTS proposal_validations (
    validation_id   TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    proposal_id     TEXT NOT NULL,
    job_id          TEXT,
    attempt_id      TEXT,
    node_id         TEXT,
    passed          INTEGER NOT NULL DEFAULT 0,
    observed        INTEGER NOT NULL DEFAULT 0,
    command_json    TEXT NOT NULL,
    exit_status     INTEGER,
    stdout          TEXT NOT NULL DEFAULT '',
    stderr          TEXT NOT NULL DEFAULT '',
    job_name        TEXT,
    job_uid         TEXT,
    pod_json        TEXT,
    image_digest    TEXT,
    patch_sha256    TEXT,
    result_sha256   TEXT,
    tests_run       INTEGER,
    detail          TEXT,
    started_at      TEXT,
    finished_at     TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS validations_by_proposal
    ON proposal_validations(proposal_id, created_at);
CREATE TABLE IF NOT EXISTS proposal_edits (
    edit_id      TEXT PRIMARY KEY,
    proposal_id  TEXT NOT NULL REFERENCES proposals(proposal_id),
    rel_path     TEXT NOT NULL,
    base_sha256  TEXT NOT NULL,
    after_sha256 TEXT NOT NULL,
    after_text   TEXT NOT NULL,
    diff_text    TEXT NOT NULL,
    state        TEXT NOT NULL,
    detail       TEXT,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS edits_by_proposal ON proposal_edits(proposal_id);
-- Mirrors the shared Approval record, plus the local payload needed to carry
-- the decision out. No client-supplied target, digest, mode or content is
-- accepted on the decision route; everything comes from this row.
CREATE TABLE IF NOT EXISTS approvals (
    approval_id   TEXT PRIMARY KEY,
    workspace_id  TEXT NOT NULL,
    repo_id       TEXT NOT NULL,
    conversation_id TEXT,
    proposal_id   TEXT,
    action        TEXT NOT NULL,
    target        TEXT NOT NULL,
    action_sha256 TEXT NOT NULL,
    payload_json  TEXT NOT NULL,
    decision      TEXT NOT NULL,
    actor_id      TEXT,
    requested_at  TEXT NOT NULL,
    expires_at    TEXT NOT NULL,
    decided_at    TEXT,
    consumed_at   TEXT
);
CREATE INDEX IF NOT EXISTS approvals_by_repo ON approvals(repo_id, requested_at);
-- AF-013. One durable record per approved final write, created in the SAME
-- transaction that claims the approval.
--
-- Consuming an approval and then writing files is two steps, and a coordinator
-- that stopped between them left an approved multi-file change half applied
-- with nothing left to resume from: the approval was spent, so a retry could
-- not re-authorise it, and nothing recorded which files had already landed.
-- This table is what a restart resumes. `approval_id` is UNIQUE, so a
-- double-click or a retried request cannot create a second operation for one
-- decision.
-- Execution 4C. One row per original file kept before a local, unvalidated
-- write, so Undo can restore exactly what was there. Bound to the proposal
-- digest as well as the path: a backup must never be usable to restore a
-- file that some other proposal changed.
CREATE TABLE IF NOT EXISTS write_backups (
    backup_id     TEXT PRIMARY KEY,
    workspace_id  TEXT NOT NULL,
    repo_id       TEXT NOT NULL,
    conversation_id TEXT,
    proposal_id   TEXT NOT NULL,
    proposal_digest TEXT NOT NULL,
    operation_id  TEXT,
    path          TEXT NOT NULL,
    original_sha256 TEXT NOT NULL,
    proposed_sha256 TEXT NOT NULL,
    stored_name   TEXT NOT NULL,
    byte_size     INTEGER NOT NULL,
    state         TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    UNIQUE(proposal_id, path)
);
CREATE INDEX IF NOT EXISTS backups_by_proposal
    ON write_backups(proposal_id, state);
CREATE TABLE IF NOT EXISTS write_operations (
    operation_id  TEXT PRIMARY KEY,
    workspace_id  TEXT NOT NULL,
    -- NULL for a Full-access write, which the mode allows without asking. The
    -- record is still durable and still resumable; UNIQUE keeps one approval
    -- from ever producing two operations, and SQLite permits repeated NULLs.
    approval_id   TEXT UNIQUE,
    repo_id       TEXT NOT NULL,
    proposal_id   TEXT NOT NULL,
    action        TEXT NOT NULL,
    action_sha256 TEXT NOT NULL,
    state         TEXT NOT NULL,
    detail        TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    finished_at   TEXT
);
CREATE INDEX IF NOT EXISTS operations_by_state ON write_operations(state, created_at);
-- Per-file progress. `base_sha256` and `after_sha256` are what recovery
-- compares against, which is how it can tell "already applied" from "someone
-- else edited this file" without ever overwriting unknown content.
CREATE TABLE IF NOT EXISTS write_operation_files (
    operation_id TEXT NOT NULL REFERENCES write_operations(operation_id),
    rel_path     TEXT NOT NULL,
    edit_id      TEXT NOT NULL,
    base_sha256  TEXT NOT NULL,
    after_sha256 TEXT NOT NULL,
    state        TEXT NOT NULL,
    detail       TEXT,
    position     INTEGER NOT NULL,
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (operation_id, rel_path)
);
-- One row per attempted repository operation. A policy allow is recorded as
-- `allowed_automatically` with the mode that allowed it, never as a human
-- approval the person did not give.
CREATE TABLE IF NOT EXISTS code_audit (
    audit_id     TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    repo_id      TEXT,
    conversation_id TEXT,
    action       TEXT NOT NULL,
    outcome      TEXT NOT NULL,
    mode         TEXT,
    approval_id  TEXT,
    detail_json  TEXT NOT NULL,
    occurred_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_by_repo ON code_audit(repo_id, occurred_at);
-- Execution 3 -------------------------------------------------------------
-- One row per attachment that a document skill actually read, with the digest
-- that was verified at read time. `page_count` stays NULL when the format
-- states none rather than being filled in with a guess.
CREATE TABLE IF NOT EXISTS document_sources (
    source_id    TEXT PRIMARY KEY,          -- the attachment id
    workspace_id TEXT NOT NULL,
    chat_id      TEXT NOT NULL,
    message_id   TEXT,
    job_id       TEXT,
    filename     TEXT NOT NULL,
    media_type   TEXT NOT NULL,
    sha256       TEXT NOT NULL,
    byte_size    INTEGER NOT NULL,
    method       TEXT NOT NULL,
    page_count   INTEGER,
    uncertain_json TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sources_by_chat ON document_sources(chat_id, created_at);
-- Extracted text stays split by page so a citation can point at one.
CREATE TABLE IF NOT EXISTS document_pages (
    workspace_id TEXT NOT NULL,
    source_id    TEXT NOT NULL REFERENCES document_sources(source_id),
    filename     TEXT NOT NULL,
    page         INTEGER NOT NULL,
    text         TEXT NOT NULL,
    confidence   REAL,
    note         TEXT,
    PRIMARY KEY (source_id, page)
);
-- Generated documents. They live in coordinator-owned storage until an export
-- is approved; `state` never says exported without an approval row.
-- OD-06 relationships. NON-SECRET METADATA ONLY.
-- The credential lives in the macOS Keychain (see coordinator/pairing.py) and
-- must never be written here: this file is copied, backed up and inspected, and
-- a bearer token in it would travel with every copy. The columns are chosen so
-- that the whole row can be shown in the UI without redaction.
CREATE TABLE IF NOT EXISTS relationships (
    relationship_id TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    node_id         TEXT NOT NULL,
    display_name    TEXT NOT NULL,
    address         TEXT NOT NULL,
    port            INTEGER NOT NULL,
    fingerprint     TEXT NOT NULL,
    certificate_pem TEXT NOT NULL,
    state           TEXT NOT NULL CHECK (state IN ('paired', 'revoked')),
    paired_at       TEXT NOT NULL,
    revoked_at      TEXT
);
CREATE INDEX IF NOT EXISTS relationships_by_workspace
    ON relationships(workspace_id, state);
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id  TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    chat_id      TEXT NOT NULL,
    job_id       TEXT,
    attempt_id   TEXT,
    workflow     TEXT NOT NULL,
    filename     TEXT NOT NULL,
    stored_name  TEXT NOT NULL,
    media_type   TEXT NOT NULL,
    byte_size    INTEGER NOT NULL,
    sha256       TEXT NOT NULL,
    validation_json TEXT NOT NULL,
    citations_json  TEXT NOT NULL,
    state        TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS artifacts_by_chat ON artifacts(chat_id, created_at);
-- Schema 13: models installed for the managed engine. One row per catalogue
-- entry; the files live content-addressed under the data root's `models/`
-- folder and are never inside the application package. A row is written only
-- after every file was hashed and matched the catalogue.
CREATE TABLE IF NOT EXISTS model_installs (
    model_id        TEXT PRIMARY KEY,
    manifest_sha256 TEXT NOT NULL,
    engine          TEXT NOT NULL,
    files_json      TEXT NOT NULL,
    source          TEXT NOT NULL,
    installed_at    TEXT NOT NULL,
    verified_at     TEXT NOT NULL
);
"""


def now() -> str:
    """Contract timestamps are fixed-width UTC seconds."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id() -> str:
    return str(uuid.uuid4())


def connect(path: Path, *, owner=None,
            admitted: Admission | None = None) -> sqlite3.Connection:
    """Open the canonical store for writing, after admission.

    `admitted` lets a caller that has just admitted this path under the same
    ownership skip a second copy; it is re-checked against the files'
    fingerprint so a store that changed since is admitted again.
    """
    path = ownership.canonical_database(path)
    if owner is not None:
        ownership.require(owner, path)
    if (admitted is None or Path(admitted.path) != path
            or admitted.fingerprint != _fingerprint(path)):
        admitted = admit(path, owner=owner)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.executescript(_SCHEMA)
    previous = conn.execute(
        "SELECT value FROM meta WHERE key='schema_version'").fetchone()
    previous_version = int(previous["value"]) if previous else 0
    # Additive upgrades: existing history keeps its unknown stopping reason,
    # and older attempts simply have no recorded context selection.
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(attempts)")}
    if "metrics_json" not in existing:
        conn.execute("ALTER TABLE attempts ADD COLUMN metrics_json TEXT")
    if "selection_json" not in existing:
        conn.execute("ALTER TABLE attempts ADD COLUMN selection_json TEXT")
    chat_columns = {r["name"] for r in conn.execute("PRAGMA table_info(chats)")}
    if "kind" not in chat_columns:
        # Which surface a conversation belongs to. Everything that existed
        # before this column was an ordinary Chat, except the one workspace
        # Code conversation, which is relabelled below by its recorded id
        # rather than by matching its title.
        conn.execute("ALTER TABLE chats ADD COLUMN kind TEXT NOT NULL"
                     " DEFAULT 'chat'")
        recorded = conn.execute(
            "SELECT value FROM meta WHERE key='code_chat_id'").fetchone()
        if recorded:
            conn.execute("UPDATE chats SET kind='code' WHERE chat_id=?",
                         (recorded["value"],))
    if "repo_id" not in chat_columns:
        # The project a Code conversation was working in, when there was one.
        # Older Code history keeps NULL: nothing recorded a project for it, so
        # nothing is guessed now.
        conn.execute("ALTER TABLE chats ADD COLUMN repo_id TEXT")
    if "open_path" not in chat_columns:
        conn.execute("ALTER TABLE chats ADD COLUMN open_path TEXT")

    job_columns = {r["name"] for r in conn.execute("PRAGMA table_info(jobs)")}
    if "skill_id" not in job_columns:
        # Which capability a request ran under. Older jobs keep NULL, meaning
        # ordinary Chat, rather than being relabelled.
        conn.execute("ALTER TABLE jobs ADD COLUMN skill_id TEXT")
    if "output_format" not in job_columns:
        # Which file a Write Document request asked for. NULL means the job
        # predates the choice; the reader treats that as the docx default
        # rather than claiming a PDF was ever offered.
        conn.execute("ALTER TABLE jobs ADD COLUMN output_format TEXT")
    if "doc_workflow" not in job_columns:
        # General document, or the fixed inspection approval note. NULL means
        # the job predates the choice, and those jobs all ran the fixed
        # workflow, so that is what a reopened conversation reports.
        conn.execute("ALTER TABLE jobs ADD COLUMN doc_workflow TEXT")
    if "reuse_sources_json" not in job_columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN reuse_sources_json TEXT")
    if "relationship_id" not in existing:
        # Which paired relationship an attempt ran through. NULL means local,
        # which is what every attempt before C06 actually was.
        conn.execute("ALTER TABLE attempts ADD COLUMN relationship_id TEXT")
    if "reasoning_json" not in existing:
        # The model and reasoning value a request actually ran with. Older
        # attempts keep NULL rather than being back-filled with a guess.
        conn.execute("ALTER TABLE attempts ADD COLUMN reasoning_json TEXT")
    if "requested_inference_json" not in existing:
        # The exact requested profile and actual request semantics. Historical
        # attempts remain NULL rather than being assigned a profile they never
        # carried.
        conn.execute(
            "ALTER TABLE attempts ADD COLUMN requested_inference_json TEXT")
    if "network_json" not in existing:
        # What Refinix's own processes connected to while this attempt ran
        # (`observer.Window`). NULL means nothing observed it, which is what
        # every attempt before the observer was.
        conn.execute("ALTER TABLE attempts ADD COLUMN network_json TEXT")
    if "actual_profile_json" not in existing:
        # Snapshot the profile actually used; do not resolve a mutable current
        # registry when auditing an old attempt.
        conn.execute("ALTER TABLE attempts ADD COLUMN actual_profile_json TEXT")
    proposal_columns = {r["name"] for r in conn.execute("PRAGMA table_info(proposals)")}
    if "execution_target" not in proposal_columns:
        # Where this proposal was generated and where it may be applied. Rows
        # written before the choice existed all came from the distributed
        # path, and that is the strict one, so defaulting them there fails
        # closed: an old proposal can never become locally applicable by
        # having no recorded target.
        conn.execute(
            "ALTER TABLE proposals ADD COLUMN execution_target TEXT NOT NULL"
            " DEFAULT 'distributed'")
    if "selection_json" not in proposal_columns:
        conn.execute(
            "ALTER TABLE proposals ADD COLUMN selection_json TEXT NOT NULL DEFAULT '[]'")
    validation_columns = {
        r["name"] for r in conn.execute("PRAGMA table_info(proposal_validations)")}
    if "tests_run" not in validation_columns:
        conn.execute("ALTER TABLE proposal_validations ADD COLUMN tests_run INTEGER")
    if "pinned" not in {r["name"] for r in conn.execute("PRAGMA table_info(chats)")}:
        conn.execute("ALTER TABLE chats ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
    # AF-013: bind a workflow approval to the exact attempt that produced the
    # output. Additive and nullable, so every approval written before C10 stays
    # readable and simply records no workflow binding — which is the truth
    # about it, rather than a back-filled guess.
    approval_columns = {r["name"] for r in conn.execute("PRAGMA table_info(approvals)")}
    for column in ("workflow_id", "job_id", "step_id", "attempt_id",
                   "conversation_id"):
        if column not in approval_columns:
            conn.execute(f"ALTER TABLE approvals ADD COLUMN {column} TEXT")
    audit_columns = {r["name"] for r in conn.execute("PRAGMA table_info(code_audit)")}
    if "conversation_id" not in audit_columns:
        conn.execute("ALTER TABLE code_audit ADD COLUMN conversation_id TEXT")
    # Whether a model may be chosen for new work. Everything that existed
    # before this column was choosable, so the default is on: a migration must
    # not silently disable a model somebody is already using.
    pref_columns = {r["name"] for r in conn.execute("PRAGMA table_info(model_prefs)")}
    if "enabled" not in pref_columns:
        conn.execute("ALTER TABLE model_prefs ADD COLUMN enabled INTEGER NOT NULL"
                     " DEFAULT 1")
    # Schema 14: the settings a self-test actually exercised (profile, check
    # definition and render settings, `admission.check_fingerprint`). Older
    # results keep NULL: nothing recorded what they ran with, so they are shown
    # as history and never count as a current check.
    selftest_columns = {r["name"] for r in conn.execute(
        "PRAGMA table_info(model_selftests)")}
    if "check_fingerprint" not in selftest_columns:
        conn.execute("ALTER TABLE model_selftests ADD COLUMN check_fingerprint TEXT")
    # Full-text search is created only where this SQLite build has FTS5. Its
    # absence disables document search and says so; it never fails a startup.
    try:
        conn.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS document_pages_fts
                USING fts5(text, content='document_pages', content_rowid='rowid');
            CREATE TRIGGER IF NOT EXISTS document_pages_ai AFTER INSERT ON document_pages BEGIN
              INSERT INTO document_pages_fts(rowid, text) VALUES (new.rowid, new.text);
            END;
            CREATE TRIGGER IF NOT EXISTS document_pages_ad AFTER DELETE ON document_pages BEGIN
              INSERT INTO document_pages_fts(document_pages_fts, rowid, text)
                   VALUES ('delete', old.rowid, old.text);
            END;
            CREATE TRIGGER IF NOT EXISTS document_pages_au AFTER UPDATE ON document_pages BEGIN
              INSERT INTO document_pages_fts(document_pages_fts, rowid, text)
                   VALUES ('delete', old.rowid, old.text);
              INSERT INTO document_pages_fts(rowid, text) VALUES (new.rowid, new.text);
            END;
        """)
        if previous_version < 6:
            conn.execute(
                "INSERT INTO document_pages_fts(document_pages_fts) VALUES ('rebuild')")
    except sqlite3.Error:
        pass
    # Never lowered: admission has already refused a newer store, and this
    # keeps the rule true even if a caller reached here some other way.
    conn.execute(
        "INSERT INTO meta(key, value) VALUES ('schema_version', ?)"
        " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(max(previous_version, SCHEMA_VERSION)),),
    )
    conn.execute(
        "INSERT INTO meta(key, value) VALUES ('app_version', ?)"
        " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (build_info.APP_VERSION,),
    )
    conn.execute(f"PRAGMA application_id = {APPLICATION_ID}")
    conn.execute(f"PRAGMA user_version = {max(previous_version, SCHEMA_VERSION)}")
    conn.execute(
        "INSERT INTO meta(key, value) VALUES ('contract_version', ?)"
        " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (v1.CONTRACT_VERSION,),
    )
    conn.commit()
    return conn


# --------------------------------------------------------------------------
# Contract-validated writes. Each helper builds the shared record first, so an
# illegal state transition or malformed field fails here rather than reaching a
# surface as a plausible-looking lie.
# --------------------------------------------------------------------------

def _job_record(row: dict) -> v1.Job:
    return v1.Job(
        contract_version=v1.CONTRACT_VERSION,
        workspace_id=row["workspace_id"], workflow_id=row["workflow_id"],
        job_id=row["job_id"], chat_id=row["chat_id"], state=row["state"],
        active_attempt_id=row["active_attempt_id"],
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


def _attempt_record(row: dict) -> v1.Attempt:
    return v1.Attempt(
        contract_version=v1.CONTRACT_VERSION,
        workspace_id=row["workspace_id"], job_id=row["job_id"],
        step_id=row["step_id"], attempt_id=row["attempt_id"],
        retry_of=row["retry_of"], node_id=row["node_id"],
        model=json.loads(row["model_json"]) if row["model_json"] else None,
        state=row["state"], route_reason=row["route_reason"],
        created_at=row["created_at"], started_at=row["started_at"],
        finished_at=row["finished_at"], queue_ms=row["queue_ms"],
        runtime_ms=row["runtime_ms"],
        error=json.loads(row["error_json"]) if row["error_json"] else None,
        artifacts=[],
    )


@serialized
def create_chat(conn, workspace_id: str, title: str) -> str:
    chat_id, stamp = new_id(), now()
    with conn:
        conn.execute(
            "INSERT INTO chats(chat_id, workspace_id, title, created_at, updated_at)"
            " VALUES (?,?,?,?,?)",
            (chat_id, workspace_id, title[:120], stamp, stamp),
        )
    return chat_id


TITLE_MAX = 120
NEW_CHAT_DRAFT = "__new__"          # draft typed before a conversation exists


def clean_title(raw: str) -> str:
    """Same rule as creation: trimmed, non-empty, bounded."""
    title = (raw or "").strip()[:TITLE_MAX]
    if not title:
        raise ValueError("a chat title cannot be empty")
    return title


def rename_chat(conn, chat_id: str, title: str) -> str:
    """Title only. Messages and the chat ID are untouched."""
    clean = clean_title(title)
    with LOCK, conn:
        changed = conn.execute("UPDATE chats SET title=? WHERE chat_id=?",
                               (clean, chat_id)).rowcount
    if not changed:
        raise KeyError(chat_id)
    return clean


def set_pinned(conn, chat_id: str, pinned: bool) -> None:
    """Pinning is ordering only; unpinning preserves every message."""
    with LOCK, conn:
        changed = conn.execute("UPDATE chats SET pinned=? WHERE chat_id=?",
                               (1 if pinned else 0, chat_id)).rowcount
    if not changed:
        raise KeyError(chat_id)


class ChatBusyError(ValueError):
    pass


def delete_chat(conn, chat_id: str, attachment_root: Path | None = None,
                artifact_root: Path | None = None) -> None:
    """Remove a chat with its messages, jobs, attempts, events, draft and files."""
    with LOCK, conn:
        if not conn.execute("SELECT 1 FROM chats WHERE chat_id=?", (chat_id,)).fetchone():
            raise KeyError(chat_id)
        if any(r["state"] not in v1.TERMINAL_JOB_STATES | {"interrupted"}
               for r in conn.execute("SELECT state FROM jobs WHERE chat_id=?", (chat_id,))):
            # The same lock covers Coordinator.submit, including job creation.
            raise ChatBusyError("Stop the response before deleting this chat.")
        jobs = [r["job_id"] for r in
                conn.execute("SELECT job_id FROM jobs WHERE chat_id=?", (chat_id,))]
        artifact_rows = conn.execute(
            "SELECT artifact_id, stored_name FROM artifacts WHERE chat_id=?",
            (chat_id,)).fetchall()
        for row in artifact_rows:
            if artifact_root is not None:
                _unlink_stored(artifact_root, row["stored_name"])
            conn.execute("DELETE FROM approvals WHERE repo_id=?", (row["artifact_id"],))
            conn.execute("DELETE FROM code_audit WHERE repo_id=?", (row["artifact_id"],))
        conn.execute("DELETE FROM artifacts WHERE chat_id=?", (chat_id,))
        source_ids = [r["source_id"] for r in conn.execute(
            "SELECT source_id FROM document_sources WHERE chat_id=?", (chat_id,))]
        for source_id in source_ids:
            conn.execute("DELETE FROM document_pages WHERE source_id=?", (source_id,))
        conn.execute("DELETE FROM document_sources WHERE chat_id=?", (chat_id,))
        for job_id in jobs:
            conn.execute("DELETE FROM events WHERE job_id=?", (job_id,))
            conn.execute("DELETE FROM attempts WHERE job_id=?", (job_id,))
        conn.execute("DELETE FROM jobs WHERE chat_id=?", (chat_id,))
        conn.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
        conn.execute("DELETE FROM drafts WHERE chat_id=?", (chat_id,))
        if attachment_root is not None:
            for row in conn.execute(
                    "SELECT stored_name FROM attachments WHERE chat_id=?", (chat_id,)):
                _unlink_stored(attachment_root, row["stored_name"])
        conn.execute("DELETE FROM attachments WHERE chat_id=?", (chat_id,))
        conn.execute("DELETE FROM chats WHERE chat_id=?", (chat_id,))


# SQLite LIKE treats % and _ as wildcards. A literal search must escape them,
# or typing "100%" would silently match everything.
def _literal(term: str) -> str:
    return (term.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_"))


def search(conn, term: str, limit: int = 40) -> list[dict]:
    """Literal, case-insensitive search over titles and message text.

    Covers every saved chat, not just the sidebar's first page. Drafts are
    excluded: an unsent draft is not conversation content.
    """
    term = (term or "").strip()
    if not term:
        return []
    pattern = f"%{_literal(term)}%"
    rows = conn.execute(
        """
        SELECT c.chat_id, c.title, c.pinned, c.updated_at,
               'title' AS field, c.title AS snippet, NULL AS message_id
          FROM chats c
         WHERE c.title LIKE ? ESCAPE '\\' AND c.kind = 'chat'
        UNION ALL
        SELECT c.chat_id, c.title, c.pinned, m.created_at,
               m.role AS field, m.text AS snippet, m.message_id
          FROM messages m JOIN chats c ON c.chat_id = m.chat_id
         WHERE m.text LIKE ? ESCAPE '\\' AND c.kind = 'chat'
         ORDER BY updated_at DESC
         LIMIT ?
        """,
        (pattern, pattern, limit),
    ).fetchall()

    lowered = term.lower()
    results = []
    for row in rows:
        text = row["snippet"] or ""
        at = text.lower().find(lowered)
        start = max(0, at - 40)
        snippet = text[start:at + len(term) + 60].replace("\n", " ")
        results.append({
            "chat_id": row["chat_id"], "title": row["title"],
            "pinned": bool(row["pinned"]), "field": row["field"],
            "message_id": row["message_id"], "updated_at": row["updated_at"],
            "snippet": ("…" if start else "") + snippet.strip()
                       + ("…" if at + len(term) + 60 < len(text) else ""),
        })
    return results


@serialized
def get_draft(conn, chat_id: str) -> str:
    row = conn.execute("SELECT text FROM drafts WHERE chat_id=?", (chat_id,)).fetchone()
    return row["text"] if row else ""


def set_draft(conn, chat_id: str, text: str) -> None:
    """A delayed save must never resurrect a deleted chat."""
    with LOCK, conn:
        if chat_id != NEW_CHAT_DRAFT and not conn.execute(
                "SELECT 1 FROM chats WHERE chat_id=?", (chat_id,)).fetchone():
            return
        if text:
            conn.execute(
                "INSERT INTO drafts(chat_id, text, updated_at) VALUES (?,?,?)"
                " ON CONFLICT(chat_id) DO UPDATE SET text=excluded.text,"
                " updated_at=excluded.updated_at",
                (chat_id, text[:16_384], now()))
        else:
            conn.execute("DELETE FROM drafts WHERE chat_id=?", (chat_id,))


def clear_draft_if_matches(conn, chat_id: str, submitted: str) -> None:
    """Clear only the version that was sent, so newer typing survives."""
    with LOCK, conn:
        conn.execute("DELETE FROM drafts WHERE chat_id=? AND text=?",
                     (chat_id, submitted))


@serialized
def export_chat(conn, chat_id: str, fmt: str = "md") -> tuple[str, str]:
    """Return (filename, body) for a saved snapshot of one chat.

    Uses the complete saved history, not whatever the interface happened to be
    showing. Drafts and other chats are excluded, and nothing is mutated.
    """
    chat = conn.execute("SELECT * FROM chats WHERE chat_id=?", (chat_id,)).fetchone()
    if chat is None:
        raise KeyError(chat_id)
    messages = conn.execute(
        "SELECT * FROM messages WHERE chat_id=? ORDER BY created_at, rowid",
        (chat_id,)).fetchall()
    notices = {}
    for row in conn.execute(
            "SELECT j.job_id, a.metrics_json, a.selection_json FROM jobs j"
            " JOIN attempts a ON a.job_id = j.job_id WHERE j.chat_id=?", (chat_id,)):
        notes = []
        metrics = json.loads(row["metrics_json"]) if row["metrics_json"] else {}
        if metrics.get("done_reason") == "length":
            limit = metrics.get("limit_reason")
            notes.append("context window and output token limits both reached" if limit == "context_and_output"
                         else "reply stopped at the context window limit" if limit == "context"
                         else "reply stopped at the output token limit" if limit == "output"
                         else "reply stopped at a runtime length limit")
        selection = json.loads(row["selection_json"]) if row["selection_json"] else {}
        if selection.get("omitted_count"):
            notes.append(f"{selection['omitted_count']} earlier message(s) were "
                         "left out of this request")
        if notes:
            notices[row["job_id"]] = notes

    markdown = fmt != "txt"
    lines = [f"# {chat['title']}", "", f"Exported {now()} from Refinix.",
             "Saved conversation only; unsent drafts are not included.", ""]
    if not markdown:
        lines = [chat["title"], "=" * len(chat["title"]), "",
                 f"Exported {now()} from Refinix.",
                 "Saved conversation only; unsent drafts are not included.", ""]
    files = {}
    for row in conn.execute(
            "SELECT a.message_id, a.filename, a.byte_size, d.method"
            " FROM attachments a LEFT JOIN document_sources d"
            " ON d.source_id = a.attachment_id"
            " WHERE a.chat_id=? AND a.message_id IS NOT NULL"
            " ORDER BY a.created_at, a.rowid",
            (chat_id,)):
        files.setdefault(row["message_id"], []).append(
            f"{row['filename']} ({row['byte_size']} bytes) — "
            + (f"read as {row['method']}" if row["method"] else "received but not read"))

    for m in messages:
        who = "You" if m["role"] == "user" else "Assistant"
        lines.append(f"## {who}" if markdown else f"--- {who} ---")
        lines.append("")
        # Markdown keeps the model's own formatting; plain text stays literal.
        lines.append(m["text"])
        lines.append("")
        attached = files.get(m["message_id"])
        if attached:
            note = "Files attached to this request: " + "; ".join(attached)
            lines.append(f"> {note}" if markdown else f"[{note}]")
            lines.append("")
        for note in notices.get(m["job_id"] or "", []):
            lines.append(f"> Note: {note}" if markdown else f"[Note: {note}]")
            lines.append("")

    safe = "".join(ch if ch.isalnum() or category(ch).startswith("M") or ch in " -_" else "-"
                   for ch in chat["title"]).strip()[:60] or "conversation"
    return f"{safe}.{'md' if markdown else 'txt'}", "\n".join(lines)


# --------------------------------------------------------------------------
# Attachments
#
# Intake stores the bytes; request-scoped document readers decide whether they
# can extract them. `received` never by itself means understood.
# --------------------------------------------------------------------------

MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024
MAX_ATTACHMENTS_PER_REQUEST = 10

# Extension -> media type. An intake allowlist, not a capability claim: every
# one of these is still `received` until a reader exists for it.
ATTACHMENT_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".tif": "image/tiff", ".tiff": "image/tiff",
    ".heic": "image/heic",
    ".webp": "image/webp",
    ".txt": "text/plain", ".md": "text/markdown", ".csv": "text/csv",
    ".json": "application/json",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


class AttachmentRejected(ValueError):
    """Intake refused the file, with a reason the user can act on."""


def attachments_root(state_path: Path) -> Path:
    return state_path.parent / "attachments"


def safe_attachment_name(raw: str) -> str:
    """A display filename with no directory, no traversal and no control bytes.

    The stored name never comes from here — it is the attachment id — so this
    only has to be safe to render and to echo back.
    """
    if not isinstance(raw, str):
        raise AttachmentRejected("The file name was not text.")
    name = raw.replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if ch.isprintable() and ch not in '\\/:*?"<>|')
    name = name.strip().strip(".")
    if not name:
        raise AttachmentRejected("The file name was empty after removing unsafe characters.")
    return name[:120]


def classify_attachment(filename: str) -> tuple[str, str]:
    """(safe name, media type). Raises AttachmentRejected for anything else."""
    name = safe_attachment_name(filename)
    suffix = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    media = ATTACHMENT_TYPES.get(suffix)
    if media is None:
        allowed = ", ".join(sorted({k.lstrip(".") for k in ATTACHMENT_TYPES}))
        raise AttachmentRejected(
            f"Refinix does not accept {suffix or 'files without an extension'}. "
            f"Accepted: {allowed}.")
    return name, media


@serialized
def add_attachment(conn, root: Path, *, workspace_id: str, chat_id: str,
                   filename: str, data: bytes) -> dict:
    """Store one selected file. Bounded, typed, and written only inside `root`."""
    name, media = classify_attachment(filename)
    if not data:
        raise AttachmentRejected(f"{name} is empty.")
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise AttachmentRejected(
            f"{name} is {len(data) // (1024 * 1024)} MB. The limit is "
            f"{MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB per file.")
    pending = conn.execute(
        "SELECT COUNT(*) AS n FROM attachments WHERE chat_id=? AND state='received'",
        (chat_id,)).fetchone()["n"]
    if pending >= MAX_ATTACHMENTS_PER_REQUEST:
        raise AttachmentRejected(
            f"A request can carry {MAX_ATTACHMENTS_PER_REQUEST} files. "
            "Remove one before adding another.")

    attachment_id, stamp = new_id(), now()
    stored = f"{attachment_id}{('.' + name.rsplit('.', 1)[-1].lower()) if '.' in name else ''}"
    root = root.resolve()
    target = (root / stored).resolve()
    if target.parent != root:
        raise AttachmentRejected("Refused to write outside the attachment folder.")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    target.write_bytes(data)
    try:
        target.chmod(0o600)
    except OSError:
        pass

    record = dict(attachment_id=attachment_id, workspace_id=workspace_id,
                  chat_id=chat_id, message_id=None, filename=name, media_type=media,
                  byte_size=len(data), sha256=hashlib.sha256(data).hexdigest(),
                  stored_name=stored, state="received", created_at=stamp)
    try:
        with conn:
            conn.execute(
                "INSERT INTO attachments(attachment_id, workspace_id, chat_id,"
                " message_id, filename, media_type, byte_size, sha256, stored_name,"
                " state, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                tuple(record[k] for k in (
                    "attachment_id", "workspace_id", "chat_id", "message_id",
                    "filename", "media_type", "byte_size", "sha256", "stored_name",
                    "state", "created_at")))
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return record


@serialized
def list_attachments(conn, chat_id=None, message_id=None) -> list[dict]:
    if message_id is not None:
        rows = conn.execute(
            "SELECT * FROM attachments WHERE message_id=? ORDER BY created_at, rowid",
            (message_id,))
    else:
        rows = conn.execute(
            "SELECT * FROM attachments WHERE chat_id=? AND state='received'"
            " ORDER BY created_at, rowid", (chat_id,))
    return [{k: r[k] for k in r.keys() if k != "stored_name"} for r in rows]


@serialized
def attachments_by_message(conn, chat_id: str) -> dict[str, list[dict]]:
    """Every sent attachment in one chat, grouped by the request it went with."""
    grouped: dict[str, list[dict]] = {}
    for row in conn.execute(
            "SELECT * FROM attachments WHERE chat_id=? AND message_id IS NOT NULL"
            " ORDER BY created_at, rowid", (chat_id,)):
        grouped.setdefault(row["message_id"], []).append(
            {k: row[k] for k in row.keys() if k != "stored_name"})
    return grouped


@serialized
def delete_attachment(conn, root: Path, attachment_id: str) -> None:
    row = conn.execute("SELECT * FROM attachments WHERE attachment_id=?",
                       (attachment_id,)).fetchone()
    if row is None:
        raise KeyError(attachment_id)
    if row["state"] != "received":
        raise AttachmentRejected("A file that was already sent cannot be removed here.")
    _unlink_stored(root, row["stored_name"])
    with conn:
        conn.execute("DELETE FROM attachments WHERE attachment_id=?", (attachment_id,))


def _unlink_stored(root: Path, stored_name: str) -> None:
    """Delete one stored file, refusing any name that escapes the folder."""
    root = root.resolve()
    target = root / stored_name
    if target.parent == root and Path(stored_name).name == stored_name:
        target.unlink(missing_ok=True)


@serialized
def bind_attachments(conn, draft_chat_id: str, chat_id: str, message_id: str) -> list[dict]:
    """Attach the pending selection to the request that was just sent."""
    stamp = now()
    with conn:
        conn.execute(
            "UPDATE attachments SET state='sent', message_id=?, chat_id=?"
            " WHERE chat_id=? AND state='received'",
            (message_id, chat_id, draft_chat_id))
        conn.execute("UPDATE chats SET updated_at=? WHERE chat_id=?", (stamp, chat_id))
    return list_attachments(conn, message_id=message_id)


@serialized
def add_message(conn, chat_id: str, role: str, text: str, job_id=None) -> str:
    message_id, stamp = new_id(), now()
    with conn:
        conn.execute(
            "INSERT INTO messages(message_id, chat_id, role, text, created_at, job_id)"
            " VALUES (?,?,?,?,?,?)",
            (message_id, chat_id, role, text, stamp, job_id),
        )
        conn.execute("UPDATE chats SET updated_at=? WHERE chat_id=?", (stamp, chat_id))
    return message_id


# --------------------------------------------------------------------------
# Execution 2: reasoning preference, repositories, proposals, approvals, audit
# --------------------------------------------------------------------------

# Reasoning stays off by default, which is the behaviour Execution 1 was
# accepted with. It is a safe default the user can change, not a prohibition:
# see docs/model-catalog.md for the measurement behind it.
DEFAULT_REASONING = False

APPROVAL_TTL_SECONDS = 15 * 60


@serialized
def get_reasoning(conn, model: str) -> bool:
    row = conn.execute("SELECT reasoning FROM model_prefs WHERE model=?",
                       (model,)).fetchone()
    return bool(row["reasoning"]) if row else DEFAULT_REASONING


@serialized
def set_reasoning(conn, model: str, enabled: bool) -> bool:
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise ValueError("a model name is required")
    if not isinstance(enabled, bool):
        raise ValueError("reasoning must be true or false")
    with conn:
        conn.execute(
            "INSERT INTO model_prefs(model, reasoning, updated_at) VALUES (?,?,?)"
            " ON CONFLICT(model) DO UPDATE SET reasoning=excluded.reasoning,"
            " updated_at=excluded.updated_at",
            (model, int(enabled), now()))
    return enabled


@serialized
def get_model_enabled(conn, model: str) -> bool:
    """Whether this model may be chosen for new work.

    Absent means enabled. Disabling is an explicit act, so a model nobody has
    touched must not arrive switched off.
    """
    row = conn.execute("SELECT enabled FROM model_prefs WHERE model=?",
                       (model,)).fetchone()
    return bool(row["enabled"]) if row else True


@serialized
def set_model_enabled(conn, model: str, enabled: bool) -> bool:
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise ValueError("a model name is required")
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be true or false")
    with conn:
        conn.execute(
            "INSERT INTO model_prefs(model, reasoning, enabled, updated_at)"
            " VALUES (?,?,?,?)"
            " ON CONFLICT(model) DO UPDATE SET enabled=excluded.enabled,"
            " updated_at=excluded.updated_at",
            (model, int(DEFAULT_REASONING), int(enabled), now()))
    return enabled


@serialized
def model_enablement(conn) -> dict:
    """Every explicit enable/disable decision, for one read instead of many."""
    return {row["model"]: bool(row["enabled"])
            for row in conn.execute("SELECT model, enabled FROM model_prefs")}


@serialized
def record_selftest(conn, *, model: str, scope: str, state: str, detail: str,
                    digest: str | None, runtime_version: str | None,
                    check_fingerprint: str | None = None) -> dict:
    """Store one capability check against the manifest and settings it ran on."""
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise ValueError("a model name is required")
    if not isinstance(scope, str) or not scope or len(scope) > 64:
        raise ValueError("a model scope is required")
    if check_fingerprint is not None and (
            not isinstance(check_fingerprint, str) or len(check_fingerprint) != 64):
        raise ValueError("a check fingerprint is a SHA-256 hex digest")
    ran_at = now()
    with conn:
        conn.execute(
            "INSERT INTO model_selftests(model, scope, state, detail, digest,"
            " runtime_version, ran_at, check_fingerprint) VALUES (?,?,?,?,?,?,?,?)"
            " ON CONFLICT(model, scope) DO UPDATE SET state=excluded.state,"
            " detail=excluded.detail, digest=excluded.digest,"
            " runtime_version=excluded.runtime_version, ran_at=excluded.ran_at,"
            " check_fingerprint=excluded.check_fingerprint",
            (model, scope, state, detail[:2000], digest, runtime_version, ran_at,
             check_fingerprint))
    return {"model": model, "scope": scope, "state": state,
            "detail": detail[:2000], "digest": digest,
            "runtime_version": runtime_version, "ran_at": ran_at,
            "check_fingerprint": check_fingerprint}


@serialized
def selftests(conn) -> list[dict]:
    return [dict(row) for row in conn.execute(
        "SELECT model, scope, state, detail, digest, runtime_version, ran_at,"
        " check_fingerprint FROM model_selftests ORDER BY model, scope")]


@serialized
def model_pref(conn, model: str) -> dict | None:
    """One stored preference row, or None when nothing was ever stored for it."""
    row = conn.execute("SELECT model, reasoning, enabled FROM model_prefs WHERE model=?",
                       (model,)).fetchone()
    return dict(row) if row else None


@serialized
def model_selections(conn) -> dict:
    """Every stored per-workflow selection, including legacy bare names."""
    return {row["scope"]: row["model"]
            for row in conn.execute("SELECT scope, model FROM model_selections")}


@serialized
def get_model_selection(conn, scope: str, default: str) -> str:
    row = conn.execute("SELECT model FROM model_selections WHERE scope=?",
                       (scope,)).fetchone()
    return row["model"] if row else default


@serialized
def set_model_selection(conn, scope: str, model: str) -> str:
    if not isinstance(scope, str) or not scope or len(scope) > 64:
        raise ValueError("a model scope is required")
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise ValueError("a model name is required")
    with conn:
        conn.execute(
            "INSERT INTO model_selections(scope, model, updated_at) VALUES (?,?,?)"
            " ON CONFLICT(scope) DO UPDATE SET model=excluded.model,"
            " updated_at=excluded.updated_at", (scope, model, now()))
    return model


@serialized
def set_attempt_reasoning(conn, attempt_id: str, model: str, enabled: bool) -> None:
    """Snapshot what this attempt actually ran with.

    Changing the switch afterwards cannot reach back into a recorded attempt.
    """
    with conn:
        conn.execute("UPDATE attempts SET reasoning_json=? WHERE attempt_id=?",
                     (json.dumps({"model": model, "reasoning_enabled": bool(enabled)}),
                      attempt_id))


@serialized
def set_attempt_network(conn, attempt_id: str, observation: dict) -> None:
    """Record one bounded observation window against one attempt."""
    with conn:
        conn.execute("UPDATE attempts SET network_json=? WHERE attempt_id=?",
                     (json.dumps(observation, sort_keys=True), attempt_id))


@serialized
def set_job_network(conn, job_id: str, node_id: str, observation: dict) -> None:
    """Record a job's observation window against its attempts on this computer."""
    with conn:
        conn.execute("UPDATE attempts SET network_json=? WHERE job_id=? AND node_id=?"
                     " AND network_json IS NULL",
                     (json.dumps(observation, sort_keys=True), job_id, node_id))


@serialized
def set_attempt_inference(conn, attempt_id: str, request: dict,
                          actual_profile: dict | None = None) -> None:
    """Persist requested semantics and the immutable profile actually used."""
    with conn:
        conn.execute(
            "UPDATE attempts SET requested_inference_json=?, actual_profile_json=?"
            " WHERE attempt_id=?",
            (json.dumps(request),
             json.dumps(actual_profile) if actual_profile is not None else None,
             attempt_id))


@serialized
def set_attempt_actual_profile(conn, attempt_id: str, profile: dict) -> None:
    with conn:
        conn.execute("UPDATE attempts SET actual_profile_json=? WHERE attempt_id=?",
                     (json.dumps(profile), attempt_id))


# ---- repositories ---------------------------------------------------------

@serialized
def register_repository(conn, *, workspace_id: str, name: str, root: str,
                        identity: dict, mode: str) -> dict:
    """Record a natively selected folder. Reconnecting the same root reuses its id."""
    stamp = now()
    existing = conn.execute(
        "SELECT * FROM repositories WHERE workspace_id=? AND root=?",
        (workspace_id, root)).fetchone()
    if existing:
        with conn:
            conn.execute("UPDATE repositories SET name=?, identity_json=?, updated_at=?"
                         " WHERE repo_id=?",
                         (name, json.dumps(identity), stamp, existing["repo_id"]))
        return public_repository(conn, existing["repo_id"], workspace_id)
    repo_id = new_id()
    with conn:
        conn.execute(
            "INSERT INTO repositories(repo_id, workspace_id, name, root, identity_json,"
            " mode, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (repo_id, workspace_id, name, root, json.dumps(identity), mode, stamp, stamp))
    return public_repository(conn, repo_id, workspace_id)


def _repository_row(conn, repo_id: str, workspace_id: str):
    if not isinstance(repo_id, str) or not repo_id:
        return None
    return conn.execute(
        "SELECT * FROM repositories WHERE repo_id=? AND workspace_id=?",
        (repo_id, workspace_id)).fetchone()


@serialized
def repository_root(conn, repo_id: str, workspace_id: str) -> tuple[Path, dict] | None:
    """The absolute root, for coordinator use only. Never returned to a surface."""
    row = _repository_row(conn, repo_id, workspace_id)
    if row is None:
        return None
    return Path(row["root"]), json.loads(row["identity_json"])


@serialized
def public_repository(conn, repo_id: str, workspace_id: str) -> dict | None:
    """What a surface may see: identity, display name, mode. Never the root."""
    row = _repository_row(conn, repo_id, workspace_id)
    if row is None:
        return None
    return {"repo_id": row["repo_id"], "name": row["name"], "mode": row["mode"],
            "connected_at": row["created_at"], "updated_at": row["updated_at"]}


@serialized
def list_repositories(conn, workspace_id: str) -> list[dict]:
    return [{"repo_id": r["repo_id"], "name": r["name"], "mode": r["mode"],
             "connected_at": r["created_at"], "updated_at": r["updated_at"]}
            for r in conn.execute(
                "SELECT * FROM repositories WHERE workspace_id=?"
                " ORDER BY updated_at DESC LIMIT 20", (workspace_id,))]


@serialized
def set_repository_mode(conn, repo_id: str, workspace_id: str, mode: str) -> dict | None:
    row = _repository_row(conn, repo_id, workspace_id)
    if row is None:
        return None
    with conn:
        conn.execute("UPDATE repositories SET mode=?, updated_at=? WHERE repo_id=?",
                     (mode, now(), repo_id))
    return public_repository(conn, repo_id, workspace_id)


@serialized
def forget_repository(conn, repo_id: str, workspace_id: str) -> bool:
    row = _repository_row(conn, repo_id, workspace_id)
    if row is None:
        return False
    with conn:
        conn.execute(
            "UPDATE approvals SET decision='denied', actor_id='coordinator',"
            " decided_at=? WHERE repo_id=? AND workspace_id=?"
            " AND decision='pending'", (now(), repo_id, workspace_id))
        conn.execute("DELETE FROM repositories WHERE repo_id=?", (repo_id,))
    return True


CODE_CHAT_TITLE = "Code activity"
CHAT_KIND = "chat"
CODE_KIND = "code"


@serialized
def create_code_conversation(conn, workspace_id: str, *, title: str,
                             repo_id: str | None = None) -> dict:
    """One durable Code conversation.

    Code work is no longer poured into a single workspace-level conversation.
    Each one owns its own jobs, attempts, proposals and approvals through the
    ordinary `chat_id` foreign key, so isolation between conversations is the
    same isolation the rest of the system already has, not a second mechanism
    that could disagree with it.
    """
    chat_id, stamp = new_id(), now()
    clean = (title or "").strip()[:120] or "Code conversation"
    with conn:
        conn.execute(
            "INSERT INTO chats(chat_id, workspace_id, title, pinned, created_at,"
            " updated_at, kind, repo_id) VALUES (?,?,?,?,?,?,?,?)",
            (chat_id, workspace_id, clean, 0, stamp, stamp, CODE_KIND, repo_id))
    return {"chat_id": chat_id, "title": clean, "repo_id": repo_id,
            "created_at": stamp, "updated_at": stamp}


def code_conversations(conn, workspace_id: str, limit: int = 100) -> list[dict]:
    """Code conversations only, newest first.

    A project that was disconnected stays named as unavailable rather than
    being resolved or dropped: the conversation really did happen in it, and
    reopening the history must not quietly reconnect the folder.
    """
    rows = conn.execute(
        "SELECT c.chat_id, c.title, c.repo_id, c.open_path, c.created_at, c.updated_at,"
        "       r.name AS repo_name"
        "  FROM chats c LEFT JOIN repositories r"
        "    ON r.repo_id = c.repo_id AND r.workspace_id = c.workspace_id"
        " WHERE c.workspace_id = ? AND c.kind = ?"
        " ORDER BY c.updated_at DESC LIMIT ?",
        (workspace_id, CODE_KIND, limit)).fetchall()
    return [{
        "chat_id": row["chat_id"], "title": row["title"],
        "repo_id": row["repo_id"], "open_path": row["open_path"],
        "repo_name": row["repo_name"],
        "project_available": bool(row["repo_id"]) and row["repo_name"] is not None,
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    } for row in rows]


@serialized
def code_conversation(conn, chat_id: str, workspace_id: str) -> dict | None:
    row = conn.execute(
        "SELECT c.chat_id, c.title, c.repo_id, c.open_path, c.created_at,"
        " c.updated_at, r.name AS repo_name FROM chats c"
        " LEFT JOIN repositories r ON r.repo_id=c.repo_id"
        " AND r.workspace_id=c.workspace_id WHERE c.chat_id=?"
        " AND c.workspace_id=? AND c.kind=?",
        (chat_id, workspace_id, CODE_KIND)).fetchone()
    if row is None:
        return None
    return {"chat_id": row["chat_id"], "title": row["title"],
            "repo_id": row["repo_id"], "open_path": row["open_path"],
            "repo_name": row["repo_name"],
            "project_available": bool(row["repo_id"]) and row["repo_name"] is not None,
            "created_at": row["created_at"], "updated_at": row["updated_at"]}


def set_conversation_repo(conn, chat_id: str, workspace_id: str,
                          repo_id: str | None) -> None:
    """Bind a Code conversation to the project it is working in."""
    with conn:
        conn.execute(
            "UPDATE chats SET repo_id=?, open_path=NULL, updated_at=? WHERE chat_id=? AND"
            " workspace_id=? AND kind=?",
            (repo_id, now(), chat_id, workspace_id, CODE_KIND))


@serialized
def set_conversation_open_path(conn, chat_id: str, workspace_id: str,
                               open_path: str | None) -> None:
    """Remember only the relative file shown in one Code conversation."""
    with conn:
        conn.execute(
            "UPDATE chats SET open_path=?, updated_at=? WHERE chat_id=? AND"
            " workspace_id=? AND kind=?",
            (open_path, now(), chat_id, workspace_id, CODE_KIND))


@serialized
def code_chat(conn, workspace_id: str) -> str:
    """The legacy workspace Code conversation, created on first use.

    Named Code conversations own new work. This one remains as the truthful
    owner for jobs and approvals created before that choice existed, rather
    than back-filling old history with a conversation it never recorded.
    """
    row = conn.execute("SELECT value FROM meta WHERE key='code_chat_id'").fetchone()
    if row:
        existing = conn.execute(
            "SELECT chat_id FROM chats WHERE chat_id=? AND workspace_id=?",
            (row["value"], workspace_id)).fetchone()
        if existing:
            return existing["chat_id"]
    chat_id, stamp = new_id(), now()
    with conn:
        conn.execute(
            "INSERT INTO chats(chat_id, workspace_id, title, pinned, created_at,"
            " updated_at, kind) VALUES (?,?,?,?,?,?,?)",
            (chat_id, workspace_id, CODE_CHAT_TITLE, 0, stamp, stamp, CODE_KIND))
        conn.execute(
            "INSERT INTO meta(key, value) VALUES ('code_chat_id', ?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value", (chat_id,))
    return chat_id


# ---- proposals ------------------------------------------------------------

@serialized
def create_proposal(conn, *, workspace_id, repo_id, job_id, attempt_id,
                    request: str, summary: str, digest: str, edits: list[dict],
                    selection: list[dict] | None = None,
                    execution_target: str = "distributed") -> dict:
    """One reviewable proposal. `execution_target` is recorded, never inferred:
    a proposal generated here may only be applied here, and one generated for
    the worker keeps the sandbox requirement it was made under."""
    proposal_id, stamp = new_id(), now()
    with conn:
        conn.execute(
            "INSERT INTO proposals(proposal_id, workspace_id, repo_id, job_id,"
            " attempt_id, request, summary, digest, selection_json, state, created_at,"
            " execution_target) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (proposal_id, workspace_id, repo_id, job_id, attempt_id, request[:4000],
             summary, digest, json.dumps(selection or []), "proposed", stamp,
             execution_target))
        for edit in edits:
            conn.execute(
                "INSERT INTO proposal_edits(edit_id, proposal_id, rel_path, base_sha256,"
                " after_sha256, after_text, diff_text, state, detail, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (new_id(), proposal_id, edit["path"], edit["base_sha256"],
                 edit["after_sha256"], edit["content"], edit["diff"], "proposed",
                 None, stamp))
    return get_proposal(conn, proposal_id, workspace_id)


@serialized
def get_proposal(conn, proposal_id: str, workspace_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM proposals WHERE proposal_id=? AND workspace_id=?",
                       (proposal_id, workspace_id)).fetchone()
    if row is None:
        return None
    edits = [{"edit_id": e["edit_id"], "path": e["rel_path"],
              "base_sha256": e["base_sha256"], "after_sha256": e["after_sha256"],
              "diff": e["diff_text"], "state": e["state"], "detail": e["detail"]}
             for e in conn.execute(
                 "SELECT * FROM proposal_edits WHERE proposal_id=? ORDER BY rowid",
                 (proposal_id,))]
    return {"proposal_id": row["proposal_id"], "repo_id": row["repo_id"],
            "job_id": row["job_id"], "attempt_id": row["attempt_id"],
            "summary": row["summary"], "digest": row["digest"],
            "selection": json.loads(row["selection_json"] or "[]"),
            "state": row["state"], "created_at": row["created_at"], "edits": edits,
            # Recorded on the row, so a caller cannot decide it later. Missing
            # means the strict distributed gate, never the local one.
            "execution_target": (row["execution_target"] if "execution_target"
                                 in row.keys() else None) or "distributed"}


@serialized
def proposal_edit_contents(conn, proposal_id: str) -> list[dict]:
    """The replacement text, for the apply step only. Not sent to a surface."""
    return [{"edit_id": e["edit_id"], "path": e["rel_path"],
             "base_sha256": e["base_sha256"], "after_sha256": e["after_sha256"],
             "content": e["after_text"], "state": e["state"]}
            for e in conn.execute(
                "SELECT * FROM proposal_edits WHERE proposal_id=? ORDER BY rowid",
                (proposal_id,))]


@serialized
def set_edit_result(conn, edit_id: str, state: str, detail: str | None = None) -> None:
    with conn:
        conn.execute("UPDATE proposal_edits SET state=?, detail=? WHERE edit_id=?",
                     (state, detail, edit_id))


@serialized
def set_proposal_state(conn, proposal_id: str, state: str) -> None:
    with conn:
        conn.execute("UPDATE proposals SET state=? WHERE proposal_id=?",
                     (state, proposal_id))


@serialized
def reject_proposal(conn, proposal_id: str, workspace_id: str,
                    conversation_id: str, actor_id: str) -> bool:
    """Reject one still-pending proposal and its unused write approvals."""
    row = conn.execute(
        "SELECT p.state FROM proposals p JOIN jobs j ON j.job_id=p.job_id"
        " WHERE p.proposal_id=? AND p.workspace_id=? AND j.chat_id=?",
        (proposal_id, workspace_id, conversation_id)).fetchone()
    if row is None or row["state"] != "proposed":
        return False
    if conn.execute(
            "SELECT 1 FROM write_operations WHERE proposal_id=? AND workspace_id=?"
            " AND state IN ('pending','applying','applied','partially_applied')",
            (proposal_id, workspace_id)).fetchone():
        return False
    stamp = now()
    with conn:
        conn.execute("UPDATE proposals SET state='rejected' WHERE proposal_id=?",
                     (proposal_id,))
        conn.execute(
            "UPDATE proposal_edits SET state='rejected' WHERE proposal_id=?"
            " AND state='proposed'", (proposal_id,))
        conn.execute(
            "UPDATE approvals SET decision='denied', actor_id=?, decided_at=?"
            " WHERE proposal_id=? AND workspace_id=? AND conversation_id=?"
            " AND decision='pending'", (actor_id, stamp, proposal_id,
                                         workspace_id, conversation_id))
    return True


@serialized
def latest_proposal(conn, repo_id: str, workspace_id: str,
                    conversation_id: str | None = None) -> dict | None:
    """The newest proposal for a project, optionally within one conversation.

    Scoping matters: without it, opening a fresh Code conversation showed the
    project's previous proposal as though it belonged there, and a refresh
    could paint one conversation's work into another.
    """
    if conversation_id:
        row = conn.execute(
            "SELECT p.proposal_id FROM proposals p"
            "  JOIN jobs j ON j.job_id = p.job_id"
            " WHERE p.repo_id=? AND p.workspace_id=? AND j.chat_id=?"
            " ORDER BY p.created_at DESC, p.rowid DESC LIMIT 1",
            (repo_id, workspace_id, conversation_id)).fetchone()
    else:
        row = conn.execute(
            "SELECT proposal_id FROM proposals WHERE repo_id=? AND workspace_id=?"
            " ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (repo_id, workspace_id)).fetchone()
    return get_proposal(conn, row["proposal_id"], workspace_id) if row else None


# ---- approvals ------------------------------------------------------------

def _expiry(seconds: int = APPROVAL_TTL_SECONDS) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


@serialized
def request_approval(conn, *, workspace_id, repo_id, proposal_id, action, target,
                     action_sha256, payload: dict, conversation_id: str | None = None,
                     ttl_seconds: int = APPROVAL_TTL_SECONDS,
                     workflow_id: str | None = None, job_id: str | None = None,
                     step_id: str | None = None,
                     attempt_id: str | None = None) -> dict:
    # Asking again for the same thing must not pile up approvals. An existing
    # pending, unexpired request for this exact action and digest IS the
    # request; returning it keeps the decision one-shot and the card single.
    existing = conn.execute(
        "SELECT approval_id FROM approvals WHERE workspace_id=? AND repo_id=?"
        " AND conversation_id IS ? AND proposal_id IS ? AND action=?"
        " AND action_sha256=? AND decision='pending'"
        " AND attempt_id IS ? AND expires_at > ? ORDER BY requested_at DESC LIMIT 1",
        (workspace_id, repo_id, conversation_id, proposal_id, action,
         action_sha256, attempt_id, now())).fetchone()
    if existing:
        return public_approval(conn, existing["approval_id"], workspace_id)

    approval_id, stamp = new_id(), now()
    expires = _expiry(ttl_seconds)
    with conn:
        conn.execute(
            "INSERT INTO approvals(approval_id, workspace_id, repo_id, conversation_id, proposal_id,"
            " action, target, action_sha256, payload_json, decision, actor_id,"
            " requested_at, expires_at, decided_at, consumed_at,"
            " workflow_id, job_id, step_id, attempt_id)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (approval_id, workspace_id, repo_id, conversation_id, proposal_id, action, target,
             action_sha256, json.dumps(payload), "pending", None, stamp, expires,
             None, None, workflow_id, job_id, step_id, attempt_id))
    return public_approval(conn, approval_id, workspace_id)


def _decide_expiry(row) -> str:
    """`expired` is an observation of coordinator time, not a user decision."""
    if row["decision"] == "pending" and now() >= row["expires_at"]:
        return "expired"
    return row["decision"]


@serialized
def public_approval(conn, approval_id: str, workspace_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM approvals WHERE approval_id=? AND workspace_id=?",
        (approval_id, workspace_id)).fetchone()
    if row is None:
        return None
    payload = json.loads(row["payload_json"])
    keys = row.keys()
    return {"approval_id": row["approval_id"], "repo_id": row["repo_id"],
            "conversation_id": (row["conversation_id"]
                                if "conversation_id" in keys else None),
            "proposal_id": row["proposal_id"], "action": row["action"],
            "target": row["target"], "action_sha256": row["action_sha256"],
            "decision": _decide_expiry(row), "requested_at": row["requested_at"],
            "expires_at": row["expires_at"], "decided_at": row["decided_at"],
            "consumed": row["consumed_at"] is not None,
            # NULL on approvals written before C10. Absent binding is reported
            # as absent rather than filled in.
            "workflow_id": row["workflow_id"] if "workflow_id" in keys else None,
            "job_id": row["job_id"] if "job_id" in keys else None,
            "step_id": row["step_id"] if "step_id" in keys else None,
            "attempt_id": row["attempt_id"] if "attempt_id" in keys else None,
            # Display-only detail; never the absolute root.
            "detail": {k: payload.get(k) for k in ("paths", "summary", "mode", "repo_name")}}


@serialized
def pending_approvals(conn, workspace_id: str, repo_id: str | None = None,
                      conversation_id: str | None = None) -> list[dict]:
    sql = "SELECT approval_id FROM approvals WHERE workspace_id=? AND decision='pending'"
    args = [workspace_id]
    if repo_id:
        sql += " AND repo_id=?"
        args.append(repo_id)
    if conversation_id:
        sql += " AND conversation_id=?"
        args.append(conversation_id)
    sql += " ORDER BY requested_at LIMIT 20"
    rows = [r["approval_id"] for r in conn.execute(sql, tuple(args))]
    return [a for a in (public_approval(conn, r, workspace_id) for r in rows)
            if a and a["decision"] == "pending"]


class ApprovalError(ValueError):
    """A decision that cannot be applied. Always fails closed."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@serialized
def decide_approval(conn, approval_id: str, workspace_id: str, *, approved: bool,
                    actor_id: str) -> dict:
    """Record one decision. One-shot, expiry-checked, no client-supplied target.

    Everything executed later comes from this row, never from the request that
    carried the decision.
    """
    row = conn.execute(
        "SELECT * FROM approvals WHERE approval_id=? AND workspace_id=?",
        (approval_id, workspace_id)).fetchone()
    if row is None:
        raise ApprovalError("unknown", "That approval no longer exists.")
    if row["decision"] != "pending":
        raise ApprovalError("already_decided",
                            f"That request was already {row['decision']}.")
    stamp = now()
    if stamp >= row["expires_at"]:
        with conn:
            conn.execute("UPDATE approvals SET decision='expired', decided_at=?"
                         " WHERE approval_id=?", (row["expires_at"], approval_id))
        raise ApprovalError("expired", "That request expired. Ask for it again.")
    with conn:
        conn.execute("UPDATE approvals SET decision=?, actor_id=?, decided_at=?"
                     " WHERE approval_id=?",
                     ("approved" if approved else "denied", actor_id, stamp, approval_id))
    return public_approval(conn, approval_id, workspace_id)


@serialized
def claim_approval(conn, approval_id: str, workspace_id: str, action: str,
                   action_sha256: str, *, repo_id: str | None = None,
                   proposal_id: str | None = None,
                   conversation_id: str | None = None) -> dict:
    """Consume an approved decision exactly once, for exactly its own action."""
    row = conn.execute(
        "SELECT * FROM approvals WHERE approval_id=? AND workspace_id=?",
        (approval_id, workspace_id)).fetchone()
    if row is None:
        raise ApprovalError("unknown", "That approval no longer exists.")
    if row["action"] != action or row["action_sha256"] != action_sha256:
        raise ApprovalError("mismatch",
                            "That approval was for a different change. Ask again.")
    if repo_id is not None and row["repo_id"] != repo_id:
        raise ApprovalError("mismatch",
                            "That approval was for a different target. Ask again.")
    if proposal_id is not None and row["proposal_id"] != proposal_id:
        raise ApprovalError("mismatch",
                            "That approval was for a different proposal. Ask again.")
    if conversation_id is not None and row["conversation_id"] != conversation_id:
        raise ApprovalError("mismatch",
                            "That approval belongs to another conversation. Ask again.")
    if row["consumed_at"] is not None:
        raise ApprovalError("used", "That approval was already used.")
    decision = _decide_expiry(row)
    if decision == "expired":
        with conn:
            conn.execute("UPDATE approvals SET decision='expired', decided_at=?"
                         " WHERE approval_id=?", (row["expires_at"], approval_id))
        raise ApprovalError("expired", "That approval expired before it was used.")
    if decision != "approved":
        raise ApprovalError(decision, f"That request was {decision}.")
    with conn:
        conn.execute("UPDATE approvals SET consumed_at=? WHERE approval_id=?",
                     (now(), approval_id))
    return json.loads(row["payload_json"])


# ---- durable final writes (AF-013) ----------------------------------------

OPERATION_OPEN_STATES = ("pending", "applying")


@serialized
def claim_approval_for_write(conn, approval_id: str, workspace_id: str, *,
                             action: str, action_sha256: str, repo_id: str,
                             proposal_id: str, edits: list[dict],
                             conversation_id: str | None = None) -> dict:
    """Consume the approval and create the write record in ONE transaction.

    This is the whole point of the function. Consuming the approval first and
    creating the record afterwards leaves a window where the decision is spent
    and nothing records what it authorised — which is exactly the state a crash
    used to produce. Either both exist or neither does.

    A second call for the same approval finds it already consumed and returns
    the operation that consumed it, so a double-click resumes one operation
    rather than starting a second.
    """
    row = conn.execute(
        "SELECT * FROM approvals WHERE approval_id=? AND workspace_id=?",
        (approval_id, workspace_id)).fetchone()
    if row is None:
        raise ApprovalError("unknown", "That approval no longer exists.")
    if row["action"] != action or row["action_sha256"] != action_sha256:
        raise ApprovalError("mismatch",
                            "That approval was for a different change. Ask again.")
    if row["repo_id"] != repo_id or row["proposal_id"] != proposal_id:
        raise ApprovalError("mismatch",
                            "That approval was for a different target. Ask again.")
    if conversation_id is not None and row["conversation_id"] != conversation_id:
        raise ApprovalError("mismatch",
                            "That approval belongs to another conversation. Ask again.")
    if row["consumed_at"] is not None:
        existing = conn.execute(
            "SELECT operation_id FROM write_operations WHERE approval_id=?",
            (approval_id,)).fetchone()
        if existing:
            return write_operation(conn, existing["operation_id"], workspace_id)
        raise ApprovalError("used", "That approval was already used.")
    decision = _decide_expiry(row)
    if decision == "expired":
        with conn:
            conn.execute("UPDATE approvals SET decision='expired', decided_at=?"
                         " WHERE approval_id=?", (row["expires_at"], approval_id))
        raise ApprovalError("expired", "That approval expired before it was used.")
    if decision != "approved":
        raise ApprovalError(decision, f"That request was {decision}.")

    operation_id, stamp = new_id(), now()
    with conn:
        conn.execute("UPDATE approvals SET consumed_at=? WHERE approval_id=?"
                     " AND consumed_at IS NULL", (stamp, approval_id))
        # If another caller consumed it between the read and here, its row won
        # and this one must not create a second operation.
        if conn.execute("SELECT consumed_at FROM approvals WHERE approval_id=?",
                        (approval_id,)).fetchone()["consumed_at"] != stamp:
            raise ApprovalError("used", "That approval was already used.")
        conn.execute(
            "INSERT INTO write_operations(operation_id, workspace_id, approval_id,"
            " repo_id, proposal_id, action, action_sha256, state, detail,"
            " created_at, updated_at, finished_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (operation_id, workspace_id, approval_id, repo_id, proposal_id, action,
             action_sha256, "pending", None, stamp, stamp, None))
        for position, edit in enumerate(edits):
            conn.execute(
                "INSERT INTO write_operation_files(operation_id, rel_path, edit_id,"
                " base_sha256, after_sha256, state, detail, position, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (operation_id, edit["path"], edit["edit_id"], edit["base_sha256"],
                 edit["after_sha256"], "pending", None, position, stamp))
    return write_operation(conn, operation_id, workspace_id)


@serialized
def create_write_operation(conn, *, workspace_id, repo_id, proposal_id, action,
                           action_sha256, edits: list[dict]) -> dict:
    """A durable record for a write the access mode allowed without asking.

    Full access skips the approval, not the record: a crash mid-write must be
    resumable in that mode too. An operation already open for this proposal is
    returned rather than duplicated, so a retried request resumes one write.
    """
    existing = conn.execute(
        "SELECT operation_id FROM write_operations WHERE workspace_id=?"
        " AND proposal_id=? AND action_sha256=? AND state IN ('pending','applying')"
        " ORDER BY created_at DESC LIMIT 1",
        (workspace_id, proposal_id, action_sha256)).fetchone()
    if existing:
        return write_operation(conn, existing["operation_id"], workspace_id)
    operation_id, stamp = new_id(), now()
    with conn:
        conn.execute(
            "INSERT INTO write_operations(operation_id, workspace_id, approval_id,"
            " repo_id, proposal_id, action, action_sha256, state, detail,"
            " created_at, updated_at, finished_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (operation_id, workspace_id, None, repo_id, proposal_id, action,
             action_sha256, "pending", None, stamp, stamp, None))
        for position, edit in enumerate(edits):
            conn.execute(
                "INSERT INTO write_operation_files(operation_id, rel_path, edit_id,"
                " base_sha256, after_sha256, state, detail, position, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (operation_id, edit["path"], edit["edit_id"], edit["base_sha256"],
                 edit["after_sha256"], "pending", None, position, stamp))
    return write_operation(conn, operation_id, workspace_id)


@serialized
def write_operation(conn, operation_id: str, workspace_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM write_operations WHERE operation_id=? AND workspace_id=?",
        (operation_id, workspace_id)).fetchone()
    if row is None:
        return None
    files = conn.execute(
        "SELECT * FROM write_operation_files WHERE operation_id=? ORDER BY position",
        (operation_id,))
    return {
        "operation_id": row["operation_id"], "approval_id": row["approval_id"],
        "repo_id": row["repo_id"], "proposal_id": row["proposal_id"],
        "action": row["action"], "action_sha256": row["action_sha256"],
        "state": row["state"], "detail": row["detail"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
        "finished_at": row["finished_at"],
        "files": [{"path": f["rel_path"], "edit_id": f["edit_id"],
                   "base_sha256": f["base_sha256"],
                   "after_sha256": f["after_sha256"], "state": f["state"],
                   "detail": f["detail"]} for f in files],
    }


@serialized
def set_operation_file(conn, operation_id: str, rel_path: str, state: str,
                       detail: str | None = None) -> None:
    with conn:
        conn.execute(
            "UPDATE write_operation_files SET state=?, detail=?, updated_at=?"
            " WHERE operation_id=? AND rel_path=?",
            (state, detail, now(), operation_id, rel_path))


@serialized
def set_operation_state(conn, operation_id: str, state: str,
                        detail: str | None = None) -> None:
    terminal = state in ("applied", "partially_applied", "failed")
    stamp = now()
    with conn:
        conn.execute(
            "UPDATE write_operations SET state=?, detail=?, updated_at=?,"
            " finished_at=? WHERE operation_id=?",
            (state, detail, stamp, stamp if terminal else None, operation_id))


@serialized
def unfinished_operations(conn, workspace_id: str) -> list[dict]:
    """Operations a restart must resume. Never anything already terminal."""
    rows = conn.execute(
        "SELECT operation_id FROM write_operations WHERE workspace_id=?"
        " AND state IN ('pending', 'applying') ORDER BY created_at",
        (workspace_id,))
    found = [write_operation(conn, row["operation_id"], workspace_id) for row in rows]
    return [item for item in found if item]


@serialized
def operation_for_approval(conn, approval_id: str, workspace_id: str) -> dict | None:
    row = conn.execute(
        "SELECT operation_id FROM write_operations WHERE approval_id=?"
        " AND workspace_id=?", (approval_id, workspace_id)).fetchone()
    return write_operation(conn, row["operation_id"], workspace_id) if row else None


# ---- AF-011 validation results --------------------------------------------

@serialized
def record_validation(conn, *, workspace_id, proposal_id, job_id, attempt_id,
                      node_id, result: dict, patch_sha256: str,
                      detail: str | None = None) -> dict:
    """Store exactly what the sandbox returned. `passed` is never inferred."""
    inner = (result or {}).get("result") or {}
    observed = bool((result or {}).get("observed"))
    tests_run = inner.get("tests_run")
    if isinstance(tests_run, bool) or not isinstance(tests_run, int):
        tests_run = None
    passed = (observed and (result or {}).get("job_state") == "succeeded"
              and (result or {}).get("passed") is True
              and inner.get("passed") is True
              and inner.get("exit_status") == 0
              and (tests_run or 0) >= 1)
    validation_id, stamp = new_id(), now()
    pod = (result or {}).get("pod") or None
    with conn:
        conn.execute(
            "INSERT INTO proposal_validations(validation_id, workspace_id,"
            " proposal_id, job_id, attempt_id, node_id, passed, observed,"
            " command_json, exit_status, stdout, stderr, job_name, job_uid,"
            " pod_json, image_digest, patch_sha256, result_sha256, detail,"
            " tests_run, started_at, finished_at, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (validation_id, workspace_id, proposal_id, job_id, attempt_id, node_id,
             1 if passed else 0,
             1 if observed else 0,
             json.dumps(inner.get("command") or []),
             inner.get("exit_status"), (inner.get("stdout") or "")[:16000],
             (inner.get("stderr") or "")[:16000],
             (result or {}).get("job_name"), (result or {}).get("job_uid"),
             json.dumps(pod) if pod else None,
             (pod or {}).get("image_digest"), patch_sha256,
             inner.get("result_sha256"), detail, tests_run,
             inner.get("started_at"), inner.get("finished_at"), stamp))
    return public_validation(conn, validation_id, workspace_id)


@serialized
def public_validation(conn, validation_id: str, workspace_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM proposal_validations WHERE validation_id=? AND workspace_id=?",
        (validation_id, workspace_id)).fetchone()
    return _validation_row(row) if row else None


@serialized
def latest_validation(conn, proposal_id: str, workspace_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM proposal_validations WHERE proposal_id=? AND workspace_id=?"
        " ORDER BY created_at DESC, rowid DESC LIMIT 1",
        (proposal_id, workspace_id)).fetchone()
    return _validation_row(row) if row else None


def validation_row(row) -> dict:
    """Public shape of one validation row, for readers outside this module."""
    return _validation_row(row)


def _validation_row(row) -> dict:
    return {"validation_id": row["validation_id"], "proposal_id": row["proposal_id"],
            "job_id": row["job_id"], "attempt_id": row["attempt_id"],
            "node_id": row["node_id"], "passed": bool(row["passed"]),
            "observed": bool(row["observed"]),
            "command": json.loads(row["command_json"]),
            "exit_status": row["exit_status"], "stdout": row["stdout"],
            "stderr": row["stderr"], "job_name": row["job_name"],
            "job_uid": row["job_uid"],
            "pod": json.loads(row["pod_json"]) if row["pod_json"] else None,
            "image_digest": row["image_digest"],
            "patch_sha256": row["patch_sha256"],
            "result_sha256": row["result_sha256"], "detail": row["detail"],
            "tests_run": row["tests_run"],
            "started_at": row["started_at"], "finished_at": row["finished_at"],
            "created_at": row["created_at"]}


# ---- audit ----------------------------------------------------------------

@serialized
def record_audit(conn, *, workspace_id, repo_id, action, outcome, mode=None,
                 approval_id=None, conversation_id: str | None = None,
                 detail: dict | None = None) -> str:
    audit_id = new_id()
    with conn:
        conn.execute(
            "INSERT INTO code_audit(audit_id, workspace_id, repo_id, conversation_id,"
            " action, outcome, mode, approval_id, detail_json, occurred_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (audit_id, workspace_id, repo_id, conversation_id, action, outcome,
             mode, approval_id, json.dumps(detail or {}), now()))
    return audit_id


@serialized
def recent_audit(conn, workspace_id: str, repo_id: str | None = None,
                 limit: int = 40,
                 conversation_id: str | None = None) -> list[dict]:
    sql = "SELECT * FROM code_audit WHERE workspace_id=?"
    args = [workspace_id]
    if repo_id:
        sql += " AND repo_id=?"
        args.append(repo_id)
    if conversation_id:
        sql += " AND conversation_id=?"
        args.append(conversation_id)
    sql += " ORDER BY occurred_at DESC, rowid DESC LIMIT ?"
    args.append(limit)
    return [{"audit_id": r["audit_id"],
             "conversation_id": (r["conversation_id"]
                                 if "conversation_id" in r.keys() else None),
             "action": r["action"], "outcome": r["outcome"],
             "mode": r["mode"], "approval_id": r["approval_id"],
             "detail": json.loads(r["detail_json"]), "occurred_at": r["occurred_at"]}
            for r in conn.execute(sql, tuple(args))]


# --------------------------------------------------------------------------
# Execution 3: document sources, extracted pages, generated artifacts
# --------------------------------------------------------------------------

def artifacts_root(state_path: Path) -> Path:
    """Coordinator-owned storage. Generated documents never leave it without
    an approved export."""
    return state_path.parent / "artifacts"


def models_root(state_path: Path) -> Path:
    """Where managed-engine model files live, outside any application package."""
    return Path(state_path).parent / "models"


@serialized
def record_model_install(conn, *, model_id: str, manifest_sha256: str, engine: str,
                         files: list[dict], source: str) -> dict:
    """Record a model whose every file was already verified on disk.

    `files` holds role, name, path (relative to the models root), size and
    sha256 for each file. Replaces an earlier record for the same model.
    """
    now_ = now()
    with conn:
        conn.execute(
            "INSERT INTO model_installs(model_id, manifest_sha256, engine, files_json,"
            " source, installed_at, verified_at) VALUES (?,?,?,?,?,?,?)"
            " ON CONFLICT(model_id) DO UPDATE SET manifest_sha256=excluded.manifest_sha256,"
            " engine=excluded.engine, files_json=excluded.files_json,"
            " source=excluded.source, verified_at=excluded.verified_at",
            (model_id, manifest_sha256, engine, json.dumps(files, sort_keys=True),
             source, now_, now_))
    return get_model_install(conn, model_id)


def _model_install(row) -> dict:
    record = dict(row)
    record["files"] = json.loads(record.pop("files_json"))
    return record


@serialized
def get_model_install(conn, model_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM model_installs WHERE model_id=?",
                       (model_id,)).fetchone()
    return None if row is None else _model_install(row)


@serialized
def model_installs(conn, engine: str | None = None) -> list[dict]:
    rows = conn.execute("SELECT * FROM model_installs ORDER BY model_id").fetchall()
    records = [_model_install(row) for row in rows]
    return [r for r in records if engine is None or r["engine"] == engine]


@serialized
def delete_model_install(conn, model_id: str) -> None:
    with conn:
        conn.execute("DELETE FROM model_installs WHERE model_id=?", (model_id,))


def backups_root(state_path: Path) -> Path:
    """Where originals are kept before a local write.

    Coordinator-owned, and deliberately **not** inside the connected project:
    a backup written into the repository would show up as a change the person
    never asked for, could be picked up by their own tools, and would be
    destroyed by the very edit it exists to undo.
    """
    return state_path.parent / "backups"


# Retention: enough to serve the visible Undo, not a second history of the
# project. A proposal's backups are removed once its Undo is used or once the
# newest allowance pushes it out.
MAX_BACKUP_PROPOSALS = 20


def verify_backup(root: Path, row: dict) -> bytes:
    """Prove one stored backup is still the file its row describes.

    A row is not a backup. Between the row being written and the write loop
    running — a restart, a cleaner, a person tidying a directory — the copy can
    vanish or change, and the only way to know is to open it and check. The
    file must still be an ordinary private file of the recorded size whose
    contents hash to the recorded digest.
    """
    root = Path(root).resolve()
    stored_name = row["stored_name"]
    if (not isinstance(stored_name, str)
            or Path(stored_name).name != stored_name):
        raise BackupError(
            f"the stored original for {row['path']} has an unsafe name.")
    stored = root / stored_name
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise BackupError("this computer cannot safely open stored originals.")
    descriptor = None
    try:
        descriptor = os.open(stored, os.O_RDONLY | nofollow)
        info = os.fstat(descriptor)
    except OSError as exc:
        raise BackupError(
            f"the stored original for {row['path']} is missing: {exc}") from exc
    try:
        if not stat.S_ISREG(info.st_mode):
            raise BackupError(
                f"the stored original for {row['path']} is not an ordinary file.")
        if stat.S_IMODE(info.st_mode) & 0o077:
            raise BackupError(
                f"the stored original for {row['path']} is not private.")
        if info.st_size != row["byte_size"]:
            raise BackupError(
                f"the stored original for {row['path']} changed size since it was "
                "written.")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            data = handle.read(int(row["byte_size"]) + 1)
    except OSError as exc:
        raise BackupError(
            f"the stored original for {row['path']} could not be read: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if len(data) != row["byte_size"] \
            or hashlib.sha256(data).hexdigest() != row["original_sha256"]:
        raise BackupError(
            f"the stored original for {row['path']} no longer matches what was "
            "backed up.")
    return data


@serialized
def record_backup(conn, root: Path, *, workspace_id, repo_id, conversation_id,
                  proposal_id, proposal_digest, path, original: bytes,
                  original_sha256, proposed_sha256) -> dict:
    """Store one original file and its binding, flushed before it counts.

    Returns only after the bytes are on disk and read back, because "the
    backup exists" is the fact the write that follows depends on.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    backup_id, stamp = new_id(), now()
    stored = root / f"{backup_id}.bak"
    temporary = root / f".{backup_id}.tmp"
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                             0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(original)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, stored)
        temporary = None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
    try:
        stored.chmod(0o600)
    except OSError as exc:
        stored.unlink(missing_ok=True)
        raise BackupError(f"The backup of {path} could not be made private.") from exc
    # Read back before the row is written. A backup that cannot be re-read is
    # not a backup, and the caller must be able to trust the row it sees.
    verification_row = {"stored_name": stored.name, "path": path,
                        "byte_size": len(original),
                        "original_sha256": original_sha256}
    try:
        verify_backup(root, verification_row)
    except BackupError:
        stored.unlink(missing_ok=True)
        raise
    try:
        with conn:
            conn.execute(
                "INSERT INTO write_backups(backup_id, workspace_id, repo_id,"
                " conversation_id, proposal_id, proposal_digest, operation_id, path,"
                " original_sha256, proposed_sha256, stored_name, byte_size, state,"
                " created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (backup_id, workspace_id, repo_id, conversation_id, proposal_id,
                 proposal_digest, None, path, original_sha256, proposed_sha256,
                 stored.name, len(original), "stored", stamp))
    except sqlite3.IntegrityError:
        # UNIQUE(proposal_id, path). Two applies raced for the same file. The
        # winner's copy is the one that counts, so this one's file is removed
        # and the existing row is reused — but only after it is verified, so a
        # race can never be the reason an unverified backup is trusted. If the
        # existing row is unusable this raises BackupError, which stops the
        # write, instead of escaping as an unhandled database error.
        stored.unlink(missing_ok=True)
        existing = conn.execute(
            "SELECT * FROM write_backups WHERE proposal_id=? AND path=?"
            " AND workspace_id=?", (proposal_id, path, workspace_id)).fetchone()
        if existing is None:
            raise BackupError(
                f"the backup of {path} could not be recorded.") from None
        row = dict(existing)
        if row["original_sha256"] != original_sha256 \
                or row["proposal_digest"] != proposal_digest:
            raise BackupError(
                f"a different original is already stored for {path}.") from None
        verify_backup(root, row)
        return {"backup_id": row["backup_id"], "path": path,
                "byte_size": row["byte_size"],
                "original_sha256": row["original_sha256"],
                "proposed_sha256": row["proposed_sha256"],
                "stored_name": row["stored_name"], "reused": True}
    return {"backup_id": backup_id, "path": path, "byte_size": len(original),
            "original_sha256": original_sha256,
            "proposed_sha256": proposed_sha256, "stored_name": stored.name,
            "reused": False}


class BackupError(RuntimeError):
    """A backup could not be made or verified. Nothing may be written."""


def proposal_backups(conn, proposal_id: str, workspace_id: str) -> list[dict]:
    return [dict(row) for row in conn.execute(
        "SELECT * FROM write_backups WHERE proposal_id=? AND workspace_id=?"
        " AND state='stored' ORDER BY path", (proposal_id, workspace_id))]


@serialized
def consume_backups(conn, root: Path, proposal_id: str, workspace_id: str) -> int:
    """Mark a proposal's backups used and remove their files.

    Called after a successful Undo. The row is kept, with its state changed,
    so the audit still shows a restore happened; only the copy goes.
    """
    rows = proposal_backups(conn, proposal_id, workspace_id)
    for row in rows:
        _unlink_stored(root, row["stored_name"])
    with conn:
        conn.execute(
            "UPDATE write_backups SET state='used' WHERE proposal_id=? AND"
            " workspace_id=?", (proposal_id, workspace_id))
    return len(rows)


@serialized
def prune_backups(conn, root: Path, workspace_id: str,
                  keep: int = MAX_BACKUP_PROPOSALS) -> int:
    """Bounded retention. The backup store serves Undo, not project history."""
    proposals = [row["proposal_id"] for row in conn.execute(
        "SELECT proposal_id, MAX(created_at) AS newest FROM write_backups"
        " WHERE workspace_id=? AND state='stored' GROUP BY proposal_id"
        " ORDER BY newest DESC", (workspace_id,))]
    removed = 0
    for proposal_id in proposals[keep:]:
        for row in proposal_backups(conn, proposal_id, workspace_id):
            _unlink_stored(root, row["stored_name"])
            removed += 1
        with conn:
            conn.execute(
                "UPDATE write_backups SET state='expired' WHERE proposal_id=?"
                " AND workspace_id=?", (proposal_id, workspace_id))
    return removed


@serialized
def attachment_record(conn, attachment_id: str, workspace_id: str) -> dict | None:
    """The full row, stored name included. Coordinator use only."""
    row = conn.execute(
        "SELECT * FROM attachments WHERE attachment_id=? AND workspace_id=?",
        (attachment_id, workspace_id)).fetchone()
    return dict(row) if row else None


@serialized
def save_extraction(conn, *, workspace_id, chat_id, message_id, job_id,
                    extraction: dict) -> dict:
    """Record one read document and its pages, and index them for search.

    Re-reading the same source replaces its rows, so a corrected extraction
    never leaves stale pages behind for a citation to resolve against.
    """
    stamp = now()
    with conn:
        conn.execute("DELETE FROM document_pages WHERE source_id=?",
                     (extraction["source_id"],))
        conn.execute(
            "INSERT INTO document_sources(source_id, workspace_id, chat_id,"
            " message_id, job_id, filename, media_type, sha256, byte_size, method,"
            " page_count, uncertain_json, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(source_id) DO UPDATE SET message_id=excluded.message_id,"
            " job_id=excluded.job_id, sha256=excluded.sha256, method=excluded.method,"
            " page_count=excluded.page_count, uncertain_json=excluded.uncertain_json",
            (extraction["source_id"], workspace_id, chat_id, message_id, job_id,
             extraction["filename"], extraction["media_type"], extraction["sha256"],
             extraction["byte_size"], extraction["method"], extraction["page_count"],
             json.dumps(extraction["uncertain"]), stamp))
        for page in extraction["pages"]:
            conn.execute(
                "INSERT INTO document_pages(workspace_id, source_id, filename, page,"
                " text, confidence, note) VALUES (?,?,?,?,?,?,?)",
                (workspace_id, extraction["source_id"], extraction["filename"],
                 page["number"], page["text"], page["confidence"], page["note"]))
    return extraction


@serialized
def get_sources(conn, workspace_id: str, source_ids: list[str]) -> list[dict]:
    """Extractions plus their pages, for citation resolution and prompting."""
    if not source_ids:
        return []
    placeholders = ",".join("?" for _ in source_ids)
    rows = conn.execute(
        f"SELECT * FROM document_sources WHERE workspace_id=?"
        f" AND source_id IN ({placeholders}) ORDER BY created_at, rowid",
        (workspace_id, *source_ids)).fetchall()
    found = []
    for row in rows:
        pages = [{"number": p["page"], "text": p["text"],
                  "confidence": p["confidence"], "note": p["note"]}
                 for p in conn.execute(
                     "SELECT * FROM document_pages WHERE source_id=? ORDER BY page",
                     (row["source_id"],))]
        found.append({"source_id": row["source_id"], "filename": row["filename"],
                      "media_type": row["media_type"], "sha256": row["sha256"],
                      "byte_size": row["byte_size"], "method": row["method"],
                      "page_count": row["page_count"],
                      "uncertain": json.loads(row["uncertain_json"]),
                      "pages": pages})
    return found


# ---- artifacts ------------------------------------------------------------

@serialized
def record_artifact(conn, *, workspace_id, chat_id, job_id, attempt_id, workflow,
                    filename, stored_name, media_type, byte_size, sha256,
                    validation: dict, citations: list) -> dict:
    artifact_id, stamp = new_id(), now()
    citations = [{**citation, "citation_id": citation.get("citation_id") or new_id()}
                 for citation in citations]
    with conn:
        conn.execute(
            "INSERT INTO artifacts(artifact_id, workspace_id, chat_id, job_id,"
            " attempt_id, workflow, filename, stored_name, media_type, byte_size,"
            " sha256, validation_json, citations_json, state, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (artifact_id, workspace_id, chat_id, job_id, attempt_id, workflow,
             filename, stored_name, media_type, byte_size, sha256,
             json.dumps(validation), json.dumps(citations), "stored", stamp))
    return public_artifact(conn, artifact_id, workspace_id)


@serialized
def delete_artifact(conn, root: Path, artifact_id: str, workspace_id: str) -> None:
    row = conn.execute(
        "SELECT stored_name FROM artifacts WHERE artifact_id=? AND workspace_id=?",
        (artifact_id, workspace_id)).fetchone()
    if row is None:
        return
    _unlink_stored(root, row["stored_name"])
    with conn:
        conn.execute("DELETE FROM approvals WHERE repo_id=?", (artifact_id,))
        conn.execute("DELETE FROM code_audit WHERE repo_id=?", (artifact_id,))
        conn.execute("DELETE FROM artifacts WHERE artifact_id=?", (artifact_id,))


@serialized
def public_artifact(conn, artifact_id: str, workspace_id: str) -> dict | None:
    """What a surface may see. The stored name stays inside the coordinator."""
    row = conn.execute(
        "SELECT * FROM artifacts WHERE artifact_id=? AND workspace_id=?",
        (artifact_id, workspace_id)).fetchone()
    if row is None:
        return None
    return {"artifact_id": row["artifact_id"], "chat_id": row["chat_id"],
            "job_id": row["job_id"], "attempt_id": row["attempt_id"],
            "workflow": row["workflow"], "filename": row["filename"],
            "media_type": row["media_type"], "byte_size": row["byte_size"],
            "sha256": row["sha256"],
            "validation": json.loads(row["validation_json"]),
            "citations": json.loads(row["citations_json"]),
            "state": row["state"], "created_at": row["created_at"]}


@serialized
def artifacts_for_chat(conn, workspace_id: str, chat_id: str) -> list[dict]:
    ids = [r["artifact_id"] for r in conn.execute(
        "SELECT artifact_id FROM artifacts WHERE workspace_id=? AND chat_id=?"
        " ORDER BY created_at, rowid", (workspace_id, chat_id))]
    return [public_artifact(conn, i, workspace_id) for i in ids]


@serialized
def artifact_path(conn, root: Path, artifact_id: str, workspace_id: str) -> Path | None:
    """Resolve one artifact inside its own folder, or nowhere at all."""
    row = conn.execute(
        "SELECT stored_name FROM artifacts WHERE artifact_id=? AND workspace_id=?",
        (artifact_id, workspace_id)).fetchone()
    if row is None:
        return None
    root = Path(root).resolve()
    target = root / row["stored_name"]
    if (target.parent != root or Path(row["stored_name"]).name != row["stored_name"]
            or target.is_symlink() or not target.is_file()):
        return None
    return target


@serialized
def set_artifact_state(conn, artifact_id: str, workspace_id: str, state: str) -> None:
    with conn:
        conn.execute("UPDATE artifacts SET state=? WHERE artifact_id=? AND workspace_id=?",
                     (state, artifact_id, workspace_id))


@serialized
def create_job(conn, *, workspace_id, chat_id, request, task_type="chat",
               skill_id=None, output_format=None, doc_workflow=None, reuse_source_ids=None) -> str:
    """One job row. The document choices travel with the request that made
    them, so a reopened conversation reports what actually ran rather than
    whatever the composer happens to be showing now."""
    job_id, stamp = new_id(), now()
    row = dict(workspace_id=workspace_id, workflow_id=new_id(), job_id=job_id,
               chat_id=chat_id, state="created", active_attempt_id=None,
               created_at=stamp, updated_at=stamp)
    _job_record(row)                       # contract check before the write
    with conn:
        conn.execute(
            "INSERT INTO jobs(job_id, workspace_id, workflow_id, chat_id, state,"
            " active_attempt_id, original_request, task_type, created_at, updated_at,"
            " skill_id, output_format, doc_workflow, reuse_sources_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (job_id, workspace_id, row["workflow_id"], chat_id, "created", None,
             request, task_type, stamp, stamp, skill_id, output_format,
             doc_workflow, json.dumps(reuse_source_ids or [])),
        )
    return job_id


def latest_completed_answer(conn, chat_id: str, *, before_job_id: str | None = None):
    """The most recent assistant reply in this chat that actually finished.

    "Finished" means the job that produced it reached `completed`. A cancelled,
    failed or still-running turn left text on screen that a person can see, and
    converting that into a document would save a fragment as though it were the
    answer. A message with no job at all is history from before jobs were
    recorded and is not offered either, because nothing can establish that it
    completed.

    `before_job_id` excludes the request currently being served, which is a
    user turn with no answer yet and must never select itself.
    """
    row = conn.execute(
        "SELECT m.message_id, m.text, m.job_id, m.created_at"
        " FROM messages m JOIN jobs j ON j.job_id = m.job_id"
        " WHERE m.chat_id = ? AND m.role = 'assistant' AND j.state = 'completed'"
        "   AND (? IS NULL OR m.job_id <> ?) AND TRIM(m.text) <> ''"
        " ORDER BY m.created_at DESC, m.rowid DESC LIMIT 1",
        (chat_id, before_job_id, before_job_id)).fetchone()
    if row is None:
        return None
    return {"message_id": row["message_id"], "text": row["text"],
            "job_id": row["job_id"], "created_at": row["created_at"]}


@serialized
def set_job_state(conn, job_id: str, following: str) -> None:
    row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    if row is None:
        raise KeyError(job_id)
    v1.require_transition(row["state"], following)   # contract state machine
    with conn:
        conn.execute("UPDATE jobs SET state=?, updated_at=? WHERE job_id=?",
                     (following, now(), job_id))


@serialized
def create_attempt(conn, *, job_id, node_id, route_reason, model=None) -> str:
    job = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    attempt_id, stamp = new_id(), now()
    row = dict(workspace_id=job["workspace_id"], job_id=job_id, step_id=new_id(),
               attempt_id=attempt_id, retry_of=None, node_id=node_id,
               model_json=json.dumps(model) if model else None, state="queued",
               route_reason=route_reason, created_at=stamp, started_at=None,
               finished_at=None, queue_ms=None, runtime_ms=None, error_json=None)
    _attempt_record(row)
    with conn:
        conn.execute(
            "INSERT INTO attempts(attempt_id, workspace_id, job_id, step_id, retry_of,"
            " node_id, model_json, state, route_reason, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (attempt_id, job["workspace_id"], job_id, row["step_id"], None, node_id,
             row["model_json"], "queued", route_reason, stamp),
        )
        conn.execute("UPDATE jobs SET active_attempt_id=?, updated_at=? WHERE job_id=?",
                     (attempt_id, stamp, job_id))
    return attempt_id


@serialized
def set_attempt_state(conn, attempt_id: str, following: str, *, error=None,
                      queue_ms=None, runtime_ms=None, metrics=None) -> None:
    row = dict(conn.execute("SELECT * FROM attempts WHERE attempt_id=?",
                            (attempt_id,)).fetchone())
    v1.require_transition(row["state"], following, attempt=True)
    stamp = now()
    row["state"] = following
    if following == "running" and row["started_at"] is None:
        row["started_at"] = stamp
    if following in v1.TERMINAL_ATTEMPT_STATES:
        row["finished_at"] = stamp
    row["error_json"] = json.dumps(error) if error else None
    if queue_ms is not None:
        row["queue_ms"] = queue_ms
    if runtime_ms is not None:
        row["runtime_ms"] = runtime_ms
    if metrics is not None:
        row["metrics_json"] = json.dumps(metrics)
    _attempt_record(row)                   # rejects an inconsistent lifecycle
    with conn:
        conn.execute(
            "UPDATE attempts SET state=?, started_at=?, finished_at=?, error_json=?,"
            " queue_ms=?, runtime_ms=?, metrics_json=? WHERE attempt_id=?",
            (following, row["started_at"], row["finished_at"], row["error_json"],
             row["queue_ms"], row["runtime_ms"], row["metrics_json"], attempt_id),
        )


@serialized
def set_attempt_selection(conn, attempt_id: str, selection: dict) -> None:
    """Persist the context choice that ran, so reopening a job shows the policy
    that applied then rather than today's settings."""
    with LOCK, conn:
        conn.execute("UPDATE attempts SET selection_json=? WHERE attempt_id=?",
                     (json.dumps(selection), attempt_id))


@serialized
def set_attempt_metrics(conn, attempt_id: str, metrics: dict) -> None:
    """Retain diagnostics even when generation never reaches validation."""
    with conn:
        conn.execute("UPDATE attempts SET metrics_json=? WHERE attempt_id=?",
                     (json.dumps(metrics), attempt_id))


@serialized
def set_attempt_runtime_ms(conn, attempt_id: str, runtime_ms: int | None) -> None:
    """Persist a measured generation duration on its own.

    The Chat path records this on a lifecycle transition, but a Code proposal
    can measure a duration and then fail without one, which left the column
    empty while `metrics_json` held the number. A surface reading the column
    then said "not measured" about something the runtime had measured.

    `None` is left alone rather than written: not measuring is a real state
    and must not be overwritten by a later call that also did not measure.
    """
    if runtime_ms is None:
        return
    with conn:
        conn.execute("UPDATE attempts SET runtime_ms=? WHERE attempt_id=?",
                     (runtime_ms, attempt_id))


@serialized
def append_output(conn, attempt_id: str, text: str) -> None:
    with conn:
        conn.execute(
            "UPDATE attempts SET output_text = output_text || ? WHERE attempt_id=?",
            (text, attempt_id),
        )


@serialized
def append_event(conn, *, job_id, attempt_id, node_id, data: dict) -> dict:
    with conn:
        seq = conn.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM events WHERE job_id=?",
            (job_id,),
        ).fetchone()[0]
        job = conn.execute("SELECT workspace_id FROM jobs WHERE job_id=?",
                           (job_id,)).fetchone()
        event = v1.Event(
            contract_version=v1.CONTRACT_VERSION,
            workspace_id=job["workspace_id"], job_id=job_id, attempt_id=attempt_id,
            event_id=new_id(), sequence=seq, producer_node_id=node_id,
            producer="coordinator", occurred_at=now(), data=data,
        )
        conn.execute(
            "INSERT INTO events(event_id, workspace_id, job_id, attempt_id, sequence,"
            " producer_node_id, producer, occurred_at, data_json) VALUES (?,?,?,?,?,?,?,?,?)",
            (event.event_id, event.workspace_id, job_id, attempt_id, seq, node_id,
             "coordinator", event.occurred_at, event.data.model_dump_json()),
        )
    return json.loads(event.model_dump_json())


# --------------------------------------------------------------------------
# OD-06 relationships. Metadata only — the credential is in the Keychain.
# --------------------------------------------------------------------------

@serialized
def record_relationship(conn, *, relationship_id, workspace_id, node_id,
                        display_name, address, port, fingerprint,
                        certificate_pem) -> str:
    """Store the non-secret half of a completed pairing.

    The ID is supplied, not generated: the worker minted its credential against
    the ID the coordinator sent it, so a locally generated second ID would not
    match the one the credential authorises.

    Called only after the worker has returned a credential and that credential
    has been stored in the Keychain. Recording first would leave a row claiming
    a pairing that has no usable credential behind it.
    """
    with conn:
        conn.execute(
            "INSERT INTO relationships(relationship_id, workspace_id, node_id,"
            " display_name, address, port, fingerprint, certificate_pem, state,"
            " paired_at, revoked_at) VALUES (?,?,?,?,?,?,?,?, 'paired', ?, NULL)",
            (relationship_id, workspace_id, node_id, display_name, address,
             int(port), fingerprint, certificate_pem, now()))
    return relationship_id


def active_relationship(conn, workspace_id: str) -> dict | None:
    """The paired worker for this workspace, or None.

    One active relationship per workspace: C06 pairs two devices, and a chooser
    between several workers is post-C11 scope. The newest paired row wins so a
    re-pair after a worker rebuild takes effect without a manual cleanup.
    """
    row = conn.execute(
        "SELECT * FROM relationships WHERE workspace_id=? AND state='paired'"
        " ORDER BY paired_at DESC LIMIT 1", (workspace_id,)).fetchone()
    return dict(row) if row else None


def get_relationship(conn, relationship_id: str, workspace_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM relationships WHERE relationship_id=? AND workspace_id=?",
        (relationship_id, workspace_id)).fetchone()
    return dict(row) if row else None


def list_relationships(conn, workspace_id: str) -> list[dict]:
    return [dict(row) for row in conn.execute(
        "SELECT * FROM relationships WHERE workspace_id=? ORDER BY paired_at DESC",
        (workspace_id,)).fetchall()]


@serialized
def revoke_relationship(conn, relationship_id: str, workspace_id: str) -> bool:
    """Mark revoked; never delete.

    The row is history: attempts reference it, and deleting it would make a
    completed job look as if it had run nowhere.
    """
    with conn:
        changed = conn.execute(
            "UPDATE relationships SET state='revoked', revoked_at=?"
            " WHERE relationship_id=? AND workspace_id=? AND state='paired'",
            (now(), relationship_id, workspace_id)).rowcount
    return bool(changed)


@serialized
def set_attempt_relationship(conn, attempt_id: str, relationship_id: str) -> None:
    with conn:
        conn.execute("UPDATE attempts SET relationship_id=? WHERE attempt_id=?",
                     (relationship_id, attempt_id))


@serialized
def fence_relationship_attempts(conn, relationship_id: str, node_id: str) -> list[str]:
    """Stop work in flight for a revoked relationship.

    `security.md` 4.1 requires revocation to fence running attempts rather than
    only refusing new ones. Each is moved to `interrupted` with a typed reason
    and its job follows, so the canonical history says what happened instead of
    leaving a job that claims to still be running.
    """
    stopped = []
    rows = conn.execute(
        "SELECT attempt_id, job_id, state FROM attempts"
        " WHERE relationship_id=? AND state IN ('queued','running','validating')",
        (relationship_id,)).fetchall()
    for row in rows:
        error = {"code": "permission_denied",
                 "message": "the pairing was revoked while this attempt was running",
                 "retryable": False}
        set_attempt_state(conn, row["attempt_id"], "interrupted", error=error)
        append_event(conn, job_id=row["job_id"], attempt_id=row["attempt_id"],
                     node_id=node_id,
                     data={"kind": "attempt.state", "previous": row["state"],
                           "current": "interrupted"})
        job = conn.execute("SELECT state FROM jobs WHERE job_id=?",
                           (row["job_id"],)).fetchone()
        if job and job["state"] not in v1.TERMINAL_JOB_STATES | {"interrupted"}:
            following = ("interrupted" if "interrupted" in
                         v1.JOB_TRANSITIONS.get(job["state"], set()) else "failed")
            set_job_state(conn, row["job_id"], following)
            append_event(conn, job_id=row["job_id"], attempt_id=None,
                         node_id=node_id,
                         data={"kind": "job.state", "previous": job["state"],
                               "current": following})
        stopped.append(row["attempt_id"])
    return stopped


@serialized
def reconcile_on_start(conn, node_id: str) -> list[str]:
    """A restart cannot leave a job claiming to be running.

    Any attempt still executing belonged to a process that is gone. It becomes
    `interrupted` with a typed reason, and its job follows. Returns the job IDs
    that were repaired so the startup log can state a number instead of a claim.
    """
    repaired = []
    stale = conn.execute(
        "SELECT attempt_id, job_id, state FROM attempts"
        " WHERE state IN ('queued','running','validating')"
    ).fetchall()
    for row in stale:
        error = {"code": "internal_error",
                 "message": "coordinator restarted while this attempt was executing",
                 "retryable": True}
        set_attempt_state(conn, row["attempt_id"], "interrupted", error=error)
        append_event(conn, job_id=row["job_id"], attempt_id=row["attempt_id"],
                     node_id=node_id,
                     data={"kind": "attempt.state", "previous": row["state"],
                           "current": "interrupted"})
    # A crash can precede attempt creation or follow its final write. Inspect
    # every unfinished job, not just jobs with an unfinished attempt.
    for job in conn.execute("SELECT job_id, state FROM jobs").fetchall():
        if job["state"] in v1.TERMINAL_JOB_STATES or job["state"] == "interrupted":
            continue
        following = ("interrupted" if "interrupted" in
                     v1.JOB_TRANSITIONS.get(job["state"], set()) else "failed")
        set_job_state(conn, job["job_id"], following)
        append_event(conn, job_id=job["job_id"], attempt_id=None, node_id=node_id,
                     data={"kind": "job.state", "previous": job["state"],
                           "current": following})
        repaired.append(job["job_id"])
    return repaired
