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
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from unicodedata import category

from backend.contracts import v1

SCHEMA_VERSION = 6

# ponytail: one coordinator database; use per-database locks if hosting several.
LOCK = threading.RLock()


def serialized(operation):
    @wraps(operation)
    def call(*args, **kwargs):
        with LOCK:
            return operation(*args, **kwargs)
    return call

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
    updated_at   TEXT NOT NULL
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
-- Files the user selected for a request. Execution 1 stores and describes them;
-- nothing reads their contents, so `state` never claims more than `received`.
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
    state        TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
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
-- One row per attempted repository operation. A policy allow is recorded as
-- `allowed_automatically` with the mode that allowed it, never as a human
-- approval the person did not give.
CREATE TABLE IF NOT EXISTS code_audit (
    audit_id     TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    repo_id      TEXT,
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
"""


def now() -> str:
    """Contract timestamps are fixed-width UTC seconds."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id() -> str:
    return str(uuid.uuid4())


def connect(path: Path) -> sqlite3.Connection:
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
    if "skill_id" not in {r["name"] for r in conn.execute("PRAGMA table_info(jobs)")}:
        # Which capability a request ran under. Older jobs keep NULL, meaning
        # ordinary Chat, rather than being relabelled.
        conn.execute("ALTER TABLE jobs ADD COLUMN skill_id TEXT")
    if "reasoning_json" not in existing:
        # The model and reasoning value a request actually ran with. Older
        # attempts keep NULL rather than being back-filled with a guess.
        conn.execute("ALTER TABLE attempts ADD COLUMN reasoning_json TEXT")
    if "pinned" not in {r["name"] for r in conn.execute("PRAGMA table_info(chats)")}:
        conn.execute("ALTER TABLE chats ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
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
    conn.execute(
        "INSERT INTO meta(key, value) VALUES ('schema_version', ?)"
        " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(SCHEMA_VERSION),),
    )
    conn.execute(
        "INSERT OR IGNORE INTO meta(key, value) VALUES ('contract_version', ?)",
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
         WHERE c.title LIKE ? ESCAPE '\\'
        UNION ALL
        SELECT c.chat_id, c.title, c.pinned, m.created_at,
               m.role AS field, m.text AS snippet, m.message_id
          FROM messages m JOIN chats c ON c.chat_id = m.chat_id
         WHERE m.text LIKE ? ESCAPE '\\'
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
# Execution 1 establishes intake only. The bytes are stored so a later
# execution has something real to read, and nothing in this file or in the
# runtime path opens them. An attachment is described to the user as
# `received`, never as understood.
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
def clear_attachments(conn, root: Path, chat_id: str) -> int:
    rows = conn.execute(
        "SELECT attachment_id, stored_name FROM attachments"
        " WHERE chat_id=? AND state='received'", (chat_id,)).fetchall()
    for row in rows:
        _unlink_stored(root, row["stored_name"])
    with conn:
        conn.execute("DELETE FROM attachments WHERE chat_id=? AND state='received'",
                     (chat_id,))
    return len(rows)


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
def set_attempt_reasoning(conn, attempt_id: str, model: str, enabled: bool) -> None:
    """Snapshot what this attempt actually ran with.

    Changing the switch afterwards cannot reach back into a recorded attempt.
    """
    with conn:
        conn.execute("UPDATE attempts SET reasoning_json=? WHERE attempt_id=?",
                     (json.dumps({"model": model, "reasoning_enabled": bool(enabled)}),
                      attempt_id))


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
        conn.execute("DELETE FROM repositories WHERE repo_id=?", (repo_id,))
    return True


# ---- proposals ------------------------------------------------------------

@serialized
def create_proposal(conn, *, workspace_id, repo_id, job_id, attempt_id,
                    request: str, summary: str, digest: str, edits: list[dict]) -> dict:
    proposal_id, stamp = new_id(), now()
    with conn:
        conn.execute(
            "INSERT INTO proposals(proposal_id, workspace_id, repo_id, job_id,"
            " attempt_id, request, summary, digest, state, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (proposal_id, workspace_id, repo_id, job_id, attempt_id, request[:4000],
             summary, digest, "proposed", stamp))
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
            "state": row["state"], "created_at": row["created_at"], "edits": edits}


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
def latest_proposal(conn, repo_id: str, workspace_id: str) -> dict | None:
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
                     action_sha256, payload: dict,
                     ttl_seconds: int = APPROVAL_TTL_SECONDS) -> dict:
    # Asking again for the same thing must not pile up approvals. An existing
    # pending, unexpired request for this exact action and digest IS the
    # request; returning it keeps the decision one-shot and the card single.
    existing = conn.execute(
        "SELECT approval_id FROM approvals WHERE workspace_id=? AND repo_id=?"
        " AND proposal_id IS ? AND action=? AND action_sha256=? AND decision='pending'"
        " AND expires_at > ? ORDER BY requested_at DESC LIMIT 1",
        (workspace_id, repo_id, proposal_id, action, action_sha256, now())).fetchone()
    if existing:
        return public_approval(conn, existing["approval_id"], workspace_id)

    approval_id, stamp = new_id(), now()
    expires = _expiry(ttl_seconds)
    with conn:
        conn.execute(
            "INSERT INTO approvals(approval_id, workspace_id, repo_id, proposal_id,"
            " action, target, action_sha256, payload_json, decision, actor_id,"
            " requested_at, expires_at, decided_at, consumed_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (approval_id, workspace_id, repo_id, proposal_id, action, target,
             action_sha256, json.dumps(payload), "pending", None, stamp, expires,
             None, None))
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
    return {"approval_id": row["approval_id"], "repo_id": row["repo_id"],
            "proposal_id": row["proposal_id"], "action": row["action"],
            "target": row["target"], "action_sha256": row["action_sha256"],
            "decision": _decide_expiry(row), "requested_at": row["requested_at"],
            "expires_at": row["expires_at"], "decided_at": row["decided_at"],
            "consumed": row["consumed_at"] is not None,
            # Display-only detail; never the absolute root.
            "detail": {k: payload.get(k) for k in ("paths", "summary", "mode", "repo_name")}}


@serialized
def pending_approvals(conn, workspace_id: str, repo_id: str | None = None) -> list[dict]:
    sql = "SELECT approval_id FROM approvals WHERE workspace_id=? AND decision='pending'"
    args = [workspace_id]
    if repo_id:
        sql += " AND repo_id=?"
        args.append(repo_id)
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
                   proposal_id: str | None = None) -> dict:
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


# ---- audit ----------------------------------------------------------------

@serialized
def record_audit(conn, *, workspace_id, repo_id, action, outcome, mode=None,
                 approval_id=None, detail: dict | None = None) -> str:
    audit_id = new_id()
    with conn:
        conn.execute(
            "INSERT INTO code_audit(audit_id, workspace_id, repo_id, action, outcome,"
            " mode, approval_id, detail_json, occurred_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (audit_id, workspace_id, repo_id, action, outcome, mode, approval_id,
             json.dumps(detail or {}), now()))
    return audit_id


@serialized
def recent_audit(conn, workspace_id: str, repo_id: str | None = None,
                 limit: int = 40) -> list[dict]:
    sql = "SELECT * FROM code_audit WHERE workspace_id=?"
    args = [workspace_id]
    if repo_id:
        sql += " AND repo_id=?"
        args.append(repo_id)
    sql += " ORDER BY occurred_at DESC, rowid DESC LIMIT ?"
    args.append(limit)
    return [{"audit_id": r["audit_id"], "action": r["action"], "outcome": r["outcome"],
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


@serialized
def sources_for_message(conn, workspace_id: str, message_id: str) -> list[dict]:
    rows = [r["source_id"] for r in conn.execute(
        "SELECT source_id FROM document_sources WHERE workspace_id=? AND message_id=?"
        " ORDER BY created_at, rowid", (workspace_id, message_id))]
    return get_sources(conn, workspace_id, rows)


# ---- artifacts ------------------------------------------------------------

class ArtifactRejected(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@serialized
def record_artifact(conn, *, workspace_id, chat_id, job_id, attempt_id, workflow,
                    filename, stored_name, media_type, byte_size, sha256,
                    validation: dict, citations: list) -> dict:
    artifact_id, stamp = new_id(), now()
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
               skill_id=None) -> str:
    job_id, stamp = new_id(), now()
    row = dict(workspace_id=workspace_id, workflow_id=new_id(), job_id=job_id,
               chat_id=chat_id, state="created", active_attempt_id=None,
               created_at=stamp, updated_at=stamp)
    _job_record(row)                       # contract check before the write
    with conn:
        conn.execute(
            "INSERT INTO jobs(job_id, workspace_id, workflow_id, chat_id, state,"
            " active_attempt_id, original_request, task_type, created_at, updated_at,"
            " skill_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (job_id, workspace_id, row["workflow_id"], chat_id, "created", None,
             request, task_type, stamp, stamp, skill_id),
        )
    return job_id


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
