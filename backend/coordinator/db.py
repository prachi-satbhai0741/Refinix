"""SQLite state for the coordinator.

The coordinator owns canonical state. Everything a surface displays comes from
here, so a restart cannot lose a job's history or invent one.

Records are validated through the shared contract in `backend.contracts.v1`
before they are written, which is what makes this a real contract consumer
rather than a parallel schema.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from backend.contracts import v1

SCHEMA_VERSION = 2

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
"""


def now() -> str:
    """Contract timestamps are fixed-width UTC seconds."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id() -> str:
    return str(uuid.uuid4())


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.executescript(_SCHEMA)
    # Additive upgrades: existing history keeps its unknown stopping reason,
    # and older attempts simply have no recorded context selection.
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(attempts)")}
    if "metrics_json" not in existing:
        conn.execute("ALTER TABLE attempts ADD COLUMN metrics_json TEXT")
    if "selection_json" not in existing:
        conn.execute("ALTER TABLE attempts ADD COLUMN selection_json TEXT")
    if "pinned" not in {r["name"] for r in conn.execute("PRAGMA table_info(chats)")}:
        conn.execute("ALTER TABLE chats ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
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


def delete_chat(conn, chat_id: str) -> None:
    """Remove a chat with its messages, jobs, attempts, events and draft."""
    with LOCK, conn:
        jobs = [r["job_id"] for r in
                conn.execute("SELECT job_id FROM jobs WHERE chat_id=?", (chat_id,))]
        for job_id in jobs:
            conn.execute("DELETE FROM events WHERE job_id=?", (job_id,))
            conn.execute("DELETE FROM attempts WHERE job_id=?", (job_id,))
        conn.execute("DELETE FROM jobs WHERE chat_id=?", (chat_id,))
        conn.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
        conn.execute("DELETE FROM drafts WHERE chat_id=?", (chat_id,))
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
            notes.append("reply stopped at the configured token limit")
        selection = json.loads(row["selection_json"]) if row["selection_json"] else {}
        if selection.get("omitted_count"):
            notes.append(f"{selection['omitted_count']} earlier message(s) were "
                         "left out of this request")
        if notes:
            notices[row["job_id"]] = notes

    markdown = fmt != "txt"
    lines = [f"# {chat['title']}", "", f"Exported {now()} from AegisForge.",
             "Saved conversation only; unsent drafts are not included.", ""]
    if not markdown:
        lines = [chat["title"], "=" * len(chat["title"]), "",
                 f"Exported {now()} from AegisForge.",
                 "Saved conversation only; unsent drafts are not included.", ""]
    for m in messages:
        who = "You" if m["role"] == "user" else "Assistant"
        lines.append(f"## {who}" if markdown else f"--- {who} ---")
        lines.append("")
        # Markdown keeps the model's own formatting; plain text stays literal.
        lines.append(m["text"])
        lines.append("")
        for note in notices.get(m["job_id"] or "", []):
            lines.append(f"> Note: {note}" if markdown else f"[Note: {note}]")
            lines.append("")

    safe = "".join(ch if ch.isalnum() or ch in " -_" else "-"
                   for ch in chat["title"]).strip()[:60] or "conversation"
    return f"{safe}.{'md' if markdown else 'txt'}", "\n".join(lines)


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


@serialized
def create_job(conn, *, workspace_id, chat_id, request, task_type="chat") -> str:
    job_id, stamp = new_id(), now()
    row = dict(workspace_id=workspace_id, workflow_id=new_id(), job_id=job_id,
               chat_id=chat_id, state="created", active_attempt_id=None,
               created_at=stamp, updated_at=stamp)
    _job_record(row)                       # contract check before the write
    with conn:
        conn.execute(
            "INSERT INTO jobs(job_id, workspace_id, workflow_id, chat_id, state,"
            " active_attempt_id, original_request, task_type, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (job_id, workspace_id, row["workflow_id"], chat_id, "created", None,
             request, task_type, stamp, stamp),
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
