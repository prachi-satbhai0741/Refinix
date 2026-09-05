"""Local coordinator: HTTP API, SSE event stream and static UI.

Standard library only. `backend/requirements.txt` pins pydantic for the shared
contract and nothing else; FastAPI is not installed, and installing it would be
a setup checkpoint rather than C03 implementation. FastAPI remains the recorded
direction for the worker API at C04, where a pinned install is part of the
image build.

Binds loopback only, per the offline-runtime invariant.
"""

from __future__ import annotations

import base64
import binascii
import http.client
import json
import queue
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from backend.contracts import v1
from backend.coordinator import (code_service, context, db, dispatch, docflow,
                                 docgen, documents, pairing, policy, repo,
                                 retrieval, runtime)

repo_errors = repo.RepositoryError

REPO = Path(__file__).resolve().parents[2]


def static_root() -> Path:
    """Where the frontend actually lives.

    In a packaged application the Python modules are inside a zip, so the
    repository layout cannot be derived from `__file__`. py2app puts bundled
    resources under `sys.prefix`, which is `Refinix.app/Contents/Resources`.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.prefix) / "frontend" / "app"
    return REPO / "frontend" / "app"


STATIC = static_root()
BIND_HOST = "127.0.0.1"
DEFAULT_PORT = 8770          # not 8443/30443 (worker contract) and not 8080 (Jenkins)

MEDIA = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml",
         ".png": "image/png", ".webmanifest": "application/manifest+json",
         ".ico": "image/x-icon"}

# An attachment upload carries a whole file, so it needs its own bound. The
# contract's MAX_REQUEST_BYTES still governs every contract route.
MAX_UPLOAD_BYTES = 28 * 1024 * 1024

# What this build can actually do, with the reason when it cannot. Nothing here
# is inferred from configuration; `chat` is the only entry that becomes
# available, and only when the runtime and the model were both observed.
CAPABILITIES = (
    {"id": "chat", "name": "Chat", "icon": "chat", "kind": "default",
     "needs_runtime": True,
     "summary": "Ask a question or describe a task in plain language."},
    {"id": "read-document", "name": "Read a document", "icon": "document",
     "kind": "document", "needs_runtime": True, "needs_documents": True,
     "summary": "Read the files you attach and answer from them, citing pages.",
     "detail_available": "Attach files with +, then ask. Only the files on that "
                         "one request are read."},
    {"id": "write-document", "name": "Write a document", "icon": "compose",
     "kind": "document", "needs_runtime": True, "needs_documents": True,
     "needs_docx": True,
     "summary": "Draft an approval note from an inspection report and its SOPs.",
     "detail_available": "Attach the report first, then any supporting "
                         "documents. The draft is a Word file kept on this "
                         "computer until you approve an export."},
    {"id": "search-documents", "name": "Search my documents", "icon": "search",
     "kind": "document", "needs_runtime": False, "needs_documents": True,
     "needs_search": True,
     "summary": "Find wording across the files you attach, with the page it came from.",
     "detail_available": "Attach files with +, then say what to look for. "
                         "Matching is by words, not meaning."},
    {"id": "code", "name": "Work in a repository", "icon": "code",
     "kind": "surface", "needs_runtime": True,
     "summary": "Edit existing text files in a folder you connect, with a diff "
                "you review and an access mode Refinix enforces.",
     "detail_available": "Open Code to connect a folder. Creating, deleting and "
                         "renaming files, project commands and Git are not "
                         "available."},
)


def _as_payload(query: dict) -> dict:
    """One-value view of a query string, so `_text` validates GET the same way."""
    return {key: values[0] for key, values in query.items() if values}


def docgen_available() -> bool:
    """Writing a .docx needs only the standard library here, but the check is
    real rather than assumed: it is what the capability row reports."""
    return hasattr(docgen, "write_docx") and hasattr(docgen, "validate")


class RequestError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class Hub:
    """Fan-out of coordinator events to connected SSE readers."""

    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers: dict[int, queue.Queue] = {}
        self._next = 0

    def subscribe(self):
        q = queue.Queue(maxsize=1024)
        with self._lock:
            self._next += 1
            key = self._next
            self._subscribers[key] = q
        return key, q

    def unsubscribe(self, key):
        with self._lock:
            self._subscribers.pop(key, None)

    def publish(self, event: dict):
        with self._lock:
            targets = list(self._subscribers.values())
        for q in targets:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass          # a stalled reader must not block generation


class Coordinator:
    def __init__(self, state_path: Path, node_id: str | None = None):
        self.state_path = state_path
        self.attachments_root = db.attachments_root(state_path)
        self.conn = db.connect(state_path)
        self.node_id = node_id or self._identity("node_id")
        self.hub = Hub()
        self.workspace_id = self._identity("workspace_id")
        self._cancelled: set[str] = set()
        self._cancel_lock = threading.Lock()
        # Set on Ctrl+C so streaming loops leave promptly instead of holding
        # the process open.
        self.stopping = threading.Event()
        # Set when a second launch asks the running copy to come forward.
        self.focus_requested = threading.Event()
        # Filled in by the desktop shell; empty when the coordinator was
        # started from the command line.
        self.desktop: dict = {}
        # The Code surface's backend. Every repository operation goes through
        # its single policy gate; no HTTP handler evaluates an access mode.
        self.code = code_service.CodeService(self)
        self.repaired = db.reconcile_on_start(self.conn, self.node_id)

    def _identity(self, key) -> str:
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        if row:
            return row["value"]
        workspace_id = db.new_id()
        with self.conn:
            self.conn.execute("INSERT INTO meta(key, value) VALUES (?, ?)",
                              (key, workspace_id))
        return workspace_id

    @db.serialized
    def request_cancel(self, job_id: str):
        row = self.conn.execute("SELECT state FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row:
            raise RequestError("unknown job", 404)
        if row["state"] in v1.TERMINAL_JOB_STATES or row["state"] == "interrupted":
            raise RequestError("job has already stopped", 409)
        with self._cancel_lock:
            self._cancelled.add(job_id)

    def is_cancelled(self, job_id: str) -> bool:
        with self._cancel_lock:
            return job_id in self._cancelled

    def _emit(self, job_id, attempt_id, data):
        event = db.append_event(self.conn, job_id=job_id, attempt_id=attempt_id,
                                node_id=self.node_id, data=data)
        self.hub.publish(event)

    @db.serialized
    def submit(self, chat_id: str, text: str, draft_id: str | None = None,
               skill_id: str | None = None) -> str:
        """Persist the job before any work starts, so a crash leaves a record."""
        if not self.conn.execute("SELECT 1 FROM chats WHERE chat_id=? AND workspace_id=?",
                                 (chat_id, self.workspace_id)).fetchone():
            raise RequestError("unknown conversation", 404)
        if any(j["state"] not in v1.TERMINAL_JOB_STATES | {"interrupted"}
               for j in self.jobs(chat_id, limit=-1)):
            raise RequestError("wait for this conversation's reply or cancel it first", 409)
        # The skill is chosen before the request is sent and is stored with the
        # job, so a reopened conversation and an export both say which
        # capability read which files. It is not UI-only state.
        if skill_id is not None:
            known = {row["id"]: row for row in self.capabilities()}
            row = known.get(skill_id)
            if row is None or row.get("kind") not in ("document",):
                raise RequestError("that skill is not available on this computer", 400)
            if row["state"] != "available":
                raise RequestError(row["detail"], 409)
        job_id = db.create_job(self.conn, workspace_id=self.workspace_id,
                               chat_id=chat_id, request=text, skill_id=skill_id)
        message_id = db.add_message(self.conn, chat_id, "user", text, job_id=job_id)
        # The selection travels with the request it was made for. Nothing reads
        # the files, and the reply is produced from the typed text alone.
        db.bind_attachments(self.conn, draft_id or chat_id, chat_id, message_id)
        self._emit(job_id, None, {"kind": "job.state", "previous": None,
                                  "current": "created"})
        threading.Thread(target=self._run, args=(job_id, chat_id, skill_id),
                         daemon=True).start()
        return job_id

    def _advance_job(self, job_id, following, previous):
        db.set_job_state(self.conn, job_id, following)
        self._emit(job_id, None, {"kind": "job.state", "previous": previous,
                                  "current": following})

    def _run(self, job_id: str, chat_id: str, skill_id: str | None = None):
        attempt_id = None
        try:
            for previous, following in (("created", "context_preparing"),
                                        ("context_preparing", "queued")):
                self._advance_job(job_id, following, previous)

            history = self.chat_messages(chat_id)
            # Saved history stays whole; only the request is bounded.
            messages, selection = context.select(
                history, window=runtime.NUM_CTX,
                output_allowance=runtime.NUM_PREDICT)

            # AF-006. The route is decided before the attempt is created, so
            # the reason is part of the canonical record from the first write
            # rather than being back-filled once something has already run.
            route = self.choose_route()
            attempt_id = db.create_attempt(
                self.conn, job_id=job_id,
                node_id=route.node_id or self.node_id,
                route_reason=route.reason,
                model=route.model,
            )
            if route.remote:
                db.set_attempt_relationship(self.conn, attempt_id,
                                            route.relationship_id)
            # Read once, here. A later change to the switch cannot reach an
            # attempt that has already recorded what it runs with.
            reasoning = db.get_reasoning(self.conn, runtime.MODEL)
            db.set_attempt_reasoning(self.conn, attempt_id, runtime.MODEL, reasoning)
            self._emit(job_id, attempt_id, {"kind": "attempt.state",
                                            "previous": None, "current": "queued"})
            db.set_attempt_selection(self.conn, attempt_id, selection.as_dict())
            if not selection.newest_fits:
                raise runtime.RuntimeUnavailable(selection.note)
            self._advance_job(job_id, "routing", "queued")
            self._advance_job(job_id, "running", "routing")
            db.set_attempt_state(self.conn, attempt_id, "running")
            self._emit(job_id, attempt_id, {"kind": "attempt.state",
                                            "previous": "queued", "current": "running"})

            if self.is_cancelled(job_id):
                self._stop(job_id, attempt_id, "cancelled", "running", {
                    "code": "cancelled_by_user",
                    "message": "cancelled before the model was called",
                    "retryable": True})
                return

            if route.kind == "identity-mismatch":
                # Pinning refused the worker. There is no fallback here by
                # design: the operator must see that the identity changed.
                self._stop(job_id, attempt_id, "failed", "running", {
                    "code": "permission_denied", "message": route.reason[:256],
                    "retryable": False})
                return
            if route.remote and skill_id is None:
                # Ordinary chat goes to the paired worker. Document and Code
                # skills stay local: their workflows are C08/C09 and the worker
                # advertises neither capability, so dispatching them would be a
                # promise this build cannot keep.
                request_text = self.conn.execute(
                    "SELECT original_request FROM jobs WHERE job_id=?",
                    (job_id,)).fetchone()["original_request"]
                handled, attempt_id = self._run_remote(
                    job_id, chat_id, attempt_id, route, text=request_text)
                if handled:
                    return
                # Fell back: continue below on this computer, with the new
                # attempt the fallback opened. The context selection and the
                # reasoning choice are re-recorded against it, so the local
                # attempt states what it actually ran with rather than
                # inheriting the remote attempt's record by implication.
                db.set_attempt_reasoning(self.conn, attempt_id, runtime.MODEL,
                                         reasoning)
                db.set_attempt_selection(self.conn, attempt_id,
                                         selection.as_dict())

            if skill_id in docflow.DOCUMENT_SKILLS:
                # A document skill replaces the ordinary chat turn: it reads
                # this request's attachments, then answers or writes from them.
                messages, prepared, extra = self._document_stage(
                    job_id, chat_id, skill_id, messages)
                if messages is None:
                    # The skill produced its own answer without the model.
                    self._finish_document(job_id, chat_id, attempt_id, extra,
                                          reasoning)
                    return
            else:
                prepared, extra = None, {}

            collected, metrics = [], {}
            thinking_seen = False
            for kind, payload in runtime.stream_chat(
                    messages, think=reasoning,
                    should_cancel=lambda: self.is_cancelled(job_id)
                    or self.stopping.is_set()):
                if kind == "thinking":
                    # Progress only. Never collected, never persisted, never
                    # shown as the reply.
                    thinking_seen = True
                elif kind == "delta":
                    collected.append(payload)
                    # Document replies use strict JSON internally. Never save
                    # or publish that implementation format as the answer.
                    if skill_id not in docflow.DOCUMENT_SKILLS:
                        db.append_output(self.conn, attempt_id, payload)
                        # The contract caps a delta at 2048 characters.
                        for i in range(0, len(payload), 2048):
                            self._emit(job_id, attempt_id,
                                       {"kind": "output.delta", "text": payload[i:i + 2048]})
                elif kind == "cancelled":
                    self._stop(job_id, attempt_id, "cancelled", "running", {
                        "code": "cancelled_by_user",
                        "message": "cancelled from the local interface",
                        "retryable": True})
                    return
                elif kind == "done":
                    metrics = payload

            db.set_attempt_state(self.conn, attempt_id, "validating",
                                 runtime_ms=metrics.get("total_ms"), metrics=metrics)
            self._emit(job_id, attempt_id, {"kind": "attempt.state",
                                            "previous": "running", "current": "validating"})
            self._advance_job(job_id, "validating", "running")

            answer = "".join(collected)
            reason = metrics.get("done_reason")
            if skill_id in docflow.DOCUMENT_SKILLS and reason != "stop":
                self._stop(job_id, attempt_id, "failed", "validating", {
                    "code": "validation_failed",
                    "message": ("The document reply was incomplete and was discarded; "
                                f"runtime stop reason: {reason or 'not reported'}."),
                    "retryable": True})
                return
            if skill_id in docflow.DOCUMENT_SKILLS and answer.strip():
                try:
                    answer = self._document_answer(
                        job_id, chat_id, attempt_id, skill_id, answer, prepared,
                        extra)
                except docflow.Cancelled:
                    self._stop(job_id, attempt_id, "cancelled", "running", {
                        "code": "cancelled_by_user",
                        "message": "cancelled while the document was being prepared",
                        "retryable": True})
                    return
                except docflow.WorkflowError as exc:
                    self._stop(job_id, attempt_id, "failed", "running", {
                        "code": "validation_failed",
                        "message": str(exc)[:256], "retryable": True})
                    return
            if not answer.strip():
                # An empty answer is a failure, not a successful blank reply.
                if thinking_seen and reasoning:
                    raise runtime.RuntimeUnavailable(
                        "Reasoning used the reply budget before producing an "
                        "answer. Turn Reasoning off or shorten the request.")
                raise runtime.RuntimeUnavailable(
                    "the runtime returned no visible output")

            with db.LOCK:
                if self.is_cancelled(job_id):
                    artifact = extra.get("_artifact")
                    if artifact:
                        db.delete_artifact(self.conn, db.artifacts_root(self.state_path),
                                           artifact["artifact_id"], self.workspace_id)
                    self._stop(job_id, attempt_id, "cancelled", "validating", {
                        "code": "cancelled_by_user",
                        "message": "cancelled before the response was saved",
                        "retryable": True})
                    return
                if reason != "stop":
                    if reason == "length":
                        # Keep the partial reply in history so the user can continue it.
                        db.add_message(self.conn, chat_id, "assistant", answer, job_id=job_id)
                        limit = metrics.get("limit_reason")
                        if limit in ("context", "context_and_output"):
                            explanation = (f"context window reached "
                                           f"({metrics.get('context_window', runtime.NUM_CTX)} tokens)")
                            if limit == "context_and_output":
                                explanation += (f"; output limit also reached "
                                                f"({metrics.get('output_token_limit', runtime.NUM_PREDICT)} tokens)")
                        elif limit == "output":
                            explanation = (f"output limit reached "
                                           f"({metrics.get('output_token_limit', runtime.NUM_PREDICT)} tokens)")
                        else:
                            explanation = "runtime length limit reached (which limit was not reported)"
                        next_step = ("Partial text saved; start a new chat with the relevant excerpt."
                                     if limit in ("context", "context_and_output") else
                                     "Partial text saved; ask to continue from the last sentence.")
                        message = f"Incomplete reply: {explanation}. {next_step}"
                    else:
                        message = f"Completion unverified: runtime stop reason {reason or 'not reported'}"
                    self._stop(job_id, attempt_id, "failed", "validating", {
                        "code": "validation_failed", "message": message[:256],
                        "retryable": True})
                    return
                if skill_id in docflow.DOCUMENT_SKILLS:
                    db.append_output(self.conn, attempt_id, answer)
                    for i in range(0, len(answer), 2048):
                        self._emit(job_id, attempt_id,
                                   {"kind": "output.delta", "text": answer[i:i + 2048]})
                    artifact = extra.get("_artifact")
                    if artifact:
                        self._emit(job_id, attempt_id, {
                            "kind": "artifact.created",
                            "artifact": {"resource_id": artifact["artifact_id"],
                                         "sha256": artifact["sha256"],
                                         "size_bytes": artifact["byte_size"],
                                         "media_type": artifact["media_type"]}})
                db.add_message(self.conn, chat_id, "assistant", answer, job_id=job_id)
                db.set_attempt_state(self.conn, attempt_id, "completed",
                                     runtime_ms=metrics.get("total_ms"))
                self._emit(job_id, attempt_id, {"kind": "attempt.state",
                                                "previous": "validating", "current": "completed"})
                self._advance_job(job_id, "completed", "validating")
        except docflow.Cancelled:
            self._stop(job_id, attempt_id, "cancelled", None, {
                "code": "cancelled_by_user",
                "message": "cancelled while the documents were being prepared",
                "retryable": True})
        except docflow.WorkflowError as exc:
            # A refusal the person can act on, not an internal error.
            self._stop(job_id, attempt_id, "failed", None, {
                "code": "validation_failed", "message": str(exc)[:256],
                "retryable": True})
        except runtime.RuntimeUnavailable as exc:
            self._stop(job_id, attempt_id, "failed", None, {
                "code": "unavailable", "message": str(exc)[:256], "retryable": True})
        except Exception as exc:                       # noqa: BLE001
            traceback.print_exc()
            self._stop(job_id, attempt_id, "failed", None, {
                "code": "internal_error",
                "message": f"{type(exc).__name__}: {exc}"[:256], "retryable": False})
        finally:
            with self._cancel_lock:
                self._cancelled.discard(job_id)

    # ---- context estimate -----------------------------------------------

    def context_estimate(self, chat_id: str | None, draft: str = "") -> dict:
        """What the next request would cost, from the one estimator we have.

        `context.select` is the single source of truth — the same code that
        decides what actually gets sent. The page renders this; it never counts
        tokens of its own, so the indicator and the request can never disagree.
        """
        history = self.chat_messages(chat_id) if chat_id else []
        draft = draft if isinstance(draft, str) else ""
        # The draft is the message that would be sent next, so it belongs in
        # the estimate: an indicator that ignored what you are typing would be
        # wrong exactly when it matters.
        pending = list(history)
        if draft.strip():
            pending.append({"message_id": "__draft__", "role": "user", "text": draft})
        _messages, selection = context.select(
            pending, window=runtime.NUM_CTX, output_allowance=runtime.NUM_PREDICT)
        used = selection.estimated_input_tokens
        budget = selection.input_budget_tokens
        share = (used / budget) if budget else 0.0
        if not selection.newest_fits:
            level = "over"
        elif selection.omitted_count:
            level = "omitting"
        elif share >= 0.8:
            level = "near"
        else:
            level = "ok"
        return {
            "used_tokens": used,
            "budget_tokens": budget,
            "context_window": selection.context_window,
            "reply_allowance": selection.output_allowance,
            "omitted_count": selection.omitted_count,
            "newest_fits": selection.newest_fits,
            "level": level,
            "counting_method": selection.counting_method,
            "estimate": True,
            "note": selection.note,
            "draft_counted": bool(draft.strip()),
            "policy": ("Older complete exchanges are left out of a request when "
                       "it will not fit. Saved history is never changed."),
        }

    # ---- artifacts --------------------------------------------------------

    def request_export(self, artifact_id: str) -> dict:
        """Ask for permission to copy a generated document out of storage.

        Nothing leaves coordinator-owned storage on the strength of having been
        generated: the export is a separate, recorded decision bound to this
        exact artifact's digest.
        """
        artifact = db.public_artifact(self.conn, artifact_id, self.workspace_id)
        if artifact is None:
            raise RequestError("that document no longer exists", 404)
        approval = db.request_approval(
            self.conn, workspace_id=self.workspace_id, repo_id=artifact_id,
            proposal_id=None, action="artifact.export",
            target=artifact["filename"], action_sha256=artifact["sha256"],
            payload={"artifact_id": artifact_id, "summary":
                     f"Save {artifact['filename']} outside Refinix's storage.",
                     "paths": [artifact["filename"]],
                     "repo_name": artifact["filename"]})
        return {"needs_approval": approval, "artifact": artifact}

    # ---- documents ------------------------------------------------------

    def _request_sources(self, chat_id: str, job_id: str):
        """The attachments that travelled with this one request, and only those.

        Ordinary Chat reads nothing. A document skill reads exactly the files
        bound to its own message — not the conversation's earlier files, and
        never anything else on the computer.
        """
        message = self.conn.execute(
            "SELECT message_id FROM messages WHERE job_id=? AND role='user'"
            " ORDER BY created_at, rowid LIMIT 1", (job_id,)).fetchone()
        if message is None:
            return None, []
        return message["message_id"], db.list_attachments(
            self.conn, message_id=message["message_id"])

    def _document_stage(self, job_id, chat_id, skill_id, messages):
        """Extract, then either build a prompt or answer without the model."""
        cancel = lambda: self.is_cancelled(job_id) or self.stopping.is_set()
        message_id, attachments = self._request_sources(chat_id, job_id)
        prepared = docflow.prepare_sources(
            self, chat_id=chat_id, message_id=message_id, job_id=job_id,
            attachments=attachments, should_cancel=cancel)
        if not attachments:
            raise docflow.WorkflowError(
                "no_attachments",
                "Attach the files to read with the + button, then send the "
                "request again. This skill only reads files you send with it.")
        if not prepared.usable:
            reasons = "; ".join(f"{s['filename']}: {s['reason']}"
                                for s in prepared.skipped) or "no readable text was found"
            raise docflow.WorkflowError("unreadable", f"Nothing could be read — {reasons}.")

        question = self.conn.execute(
            "SELECT original_request FROM jobs WHERE job_id=?", (job_id,)).fetchone()[0]

        if skill_id == docflow.SEARCH_SKILL:
            # Search needs no model: it answers from the index directly.
            try:
                passages = retrieval.search(
                    self.conn, workspace_id=self.workspace_id,
                    source_ids=[s["source_id"] for s in prepared.sources],
                    question=question)
            except retrieval.RetrievalError as exc:
                raise docflow.WorkflowError(exc.code, str(exc)) from exc
            return None, prepared, {"answer": docflow.search_answer(
                question, passages, prepared), "prepared": prepared}

        if skill_id == docflow.READ_SKILL:
            built, notes, citation_sources = docflow.read_messages(
                question, prepared.sources)
            return built, prepared, {"notes": notes, "prepared": prepared,
                                     "citation_sources": citation_sources}

        # write-document: the report is the first attachment, the rest are SOPs.
        report, *supporting = prepared.sources
        passages = []
        if supporting:
            try:
                passages = retrieval.search(
                    self.conn, workspace_id=self.workspace_id,
                    source_ids=[s["source_id"] for s in supporting],
                    question=question)
            except retrieval.RetrievalError:
                passages = []          # no passages is a truthful outcome
        budget = docflow.MAX_CONTEXT_CHARS
        pages, _trimmed = docflow.bounded_pages(report, budget)
        built = docflow.approval_note_messages(
            question, passages, [(report, pages)])
        allowed_pages = {report["source_id"]: {p["number"] for p in pages}}
        for passage in passages:
            allowed_pages.setdefault(passage.source_id, set()).add(passage.page)
        citation_sources = [
            {**source, "pages": [page for page in source["pages"]
                                  if page["number"] in allowed_pages[source["source_id"]]]}
            for source in prepared.sources if source["source_id"] in allowed_pages]
        return built, prepared, {"passages": passages, "report": report,
                                 "prepared": prepared,
                                 "citation_sources": citation_sources}

    def _document_answer(self, job_id, chat_id, attempt_id, skill_id, answer,
                         prepared, extra):
        """Turn the model's reply into the skill's real result."""
        if self.is_cancelled(job_id) or self.stopping.is_set():
            raise docflow.Cancelled()
        if skill_id == docflow.READ_SKILL:
            parsed = docflow.parse_read_answer(
                answer, extra.get("citation_sources", []))
            return docflow.read_answer(parsed, prepared, extra.get("notes", []))

        note = docflow.parse_approval_note(
            answer, extra.get("citation_sources", []))
        if self.is_cancelled(job_id) or self.stopping.is_set():
            raise docflow.Cancelled()

        root = db.artifacts_root(self.state_path)
        stored = f"{db.new_id()}.docx"
        blocks = docflow.note_blocks(note, prepared.sources, extra.get("passages", []))
        try:
            written = docgen.write_docx(root / stored,
                                        title=note["title"], blocks=blocks)
        except docgen.ArtifactError as exc:
            raise docflow.WorkflowError(exc.code, str(exc)) from exc
        validation = docgen.validate(root / stored)
        if not validation["readable"]:
            (root / stored).unlink(missing_ok=True)
            raise docflow.WorkflowError(
                "unreadable_artifact",
                "The generated document did not pass its structure check, so it "
                "was discarded: " + "; ".join(validation["problems"])[:200])
        if self.is_cancelled(job_id) or self.stopping.is_set():
            # Cancelled after writing: the file is removed rather than left as
            # a result nobody asked to keep.
            (root / stored).unlink(missing_ok=True)
            raise docflow.Cancelled()

        try:
            artifact = db.record_artifact(
                self.conn, workspace_id=self.workspace_id, chat_id=chat_id,
                job_id=job_id, attempt_id=attempt_id, workflow=docflow.WORKFLOW,
                filename=docgen.safe_filename(note["title"]), stored_name=stored,
                media_type=written["media_type"], byte_size=written["byte_size"],
                sha256=written["sha256"], validation=validation,
                citations=docflow.citation_list(note))
        except Exception:
            (root / stored).unlink(missing_ok=True)
            raise
        if self.is_cancelled(job_id) or self.stopping.is_set():
            db.delete_artifact(self.conn, root, artifact["artifact_id"],
                               self.workspace_id)
            raise docflow.Cancelled()
        extra["_artifact"] = artifact
        return docflow.artifact_answer(note, artifact, prepared,
                                       extra.get("passages", []))

    def _finish_document(self, job_id, chat_id, attempt_id, extra, reasoning):
        """Complete a skill that answered without calling the model."""
        answer = extra["answer"]
        with db.LOCK:
            if self.is_cancelled(job_id):
                self._stop(job_id, attempt_id, "cancelled", "running", {
                    "code": "cancelled_by_user",
                    "message": "cancelled from the local interface",
                    "retryable": True})
                return
            db.append_output(self.conn, attempt_id, answer)
            db.add_message(self.conn, chat_id, "assistant", answer, job_id=job_id)
            db.set_attempt_state(self.conn, attempt_id, "validating")
            self._emit(job_id, attempt_id, {"kind": "attempt.state",
                                            "previous": "running",
                                            "current": "validating"})
            self._advance_job(job_id, "validating", "running")
            db.set_attempt_state(self.conn, attempt_id, "completed")
            self._emit(job_id, attempt_id, {"kind": "attempt.state",
                                            "previous": "validating",
                                            "current": "completed"})
            self._advance_job(job_id, "completed", "validating")

    # ---- AF-006 pairing and remote routing --------------------------------

    def worker_state(self) -> dict:
        """What the UI may display about the paired worker.

        Every measurement is either observed now or reported as unavailable.
        There is no cached "last known healthy": a stale number shown as
        current is exactly the fabricated health AF-007 forbids.
        """
        relationship = self.paired_worker()
        state = {
            "paired": relationship is not None,
            "keychain_available": pairing.keychain_available(),
            "relationship": pairing.describe(relationship) if relationship else None,
            "node": None, "health": "unavailable", "identity_mismatch": None,
            "route_reason": None,
        }
        if relationship is None:
            state["health"] = "unknown"
            state["route_reason"] = "local coordinator: no paired worker"
            return state
        try:
            node = self.preflight(relationship)
        except pairing.IdentityMismatch as exc:
            state["identity_mismatch"] = str(exc)
            state["route_reason"] = f"refused: {exc}"
            return state
        route = dispatch.choose_route(relationship=relationship, node=node,
                                      required=["text.generate"],
                                      model_id=runtime.MODEL)
        state["node"] = node
        state["health"] = (node or {}).get("health", "unavailable")
        state["route_reason"] = route.reason
        state["would_dispatch"] = route.remote
        return state

    # The Pod's readiness is a Kubernetes fact, and Refinix has no Kubernetes
    # credential. Granting one to populate a UI row would hand the desktop app
    # cluster access it needs for nothing else, so the row stays unavailable
    # and says why. The worker's own /v1/health is the observation we DO have.
    POD_READINESS_UNAVAILABLE = (
        "not observed — Refinix has no Kubernetes access, and asking for it to "
        "fill in a row would be a larger permission than the feature needs. "
        "Check it on the worker with: kubectl -n aegisforge get pods")

    SELFTEST_TITLE = "Connection self-test"
    SELFTEST_PROMPT = ("Reply with exactly: distributed self-test ok. "
                       "Do not add anything else.")

    def selftest_chat(self) -> str:
        """The conversation self-tests are recorded in.

        A real chat, not a hidden channel: the self-test runs the ordinary
        request path, so its result is an ordinary job with an ordinary
        history. Hiding it would mean a second path, and a second path is
        exactly what a self-test must not exercise.
        """
        row = self.conn.execute(
            "SELECT chat_id FROM chats WHERE workspace_id=? AND title=?"
            " ORDER BY created_at DESC LIMIT 1",
            (self.workspace_id, self.SELFTEST_TITLE)).fetchone()
        if row:
            return row["chat_id"]
        return db.create_chat(self.conn, self.workspace_id, self.SELFTEST_TITLE)

    def run_selftest(self) -> dict:
        """Send one real request down the real path, and say where it went.

        No bypass and no special-case dispatch: this calls `submit`, which
        chooses a route, builds a validated envelope, authenticates to the
        worker over the pinned channel, waits on the durable receipt and
        replays the executor's events. A self-test that skipped any of that
        would pass while the thing it claims to test was broken.

        It is never triggered automatically — it invokes the model, which costs
        real time on the worker — so there is no polling or startup call. Only
        the button in the Control Center starts it.
        """
        relationship = self.paired_worker()
        if relationship is None:
            raise RequestError("No computer is connected, so there is nothing "
                               "to test.", 409)
        chat_id = self.selftest_chat()
        job_id = self.submit(chat_id, self.SELFTEST_PROMPT)
        return {"job_id": job_id, "chat_id": chat_id,
                "expected": "the reply arrives from the connected computer, "
                            "and the route reason names it"}

    def selftest_result(self, job_id: str) -> dict:
        """What the self-test actually did: route reason and terminal state.

        Read from the canonical record rather than from anything the self-test
        kept in memory, so it reports what a restart would also report.
        """
        job = self.conn.execute(
            "SELECT job_id, state, chat_id FROM jobs WHERE job_id=?",
            (job_id,)).fetchone()
        if job is None:
            raise RequestError("unknown self-test", 404)
        attempts = [dict(row) for row in self.conn.execute(
            "SELECT attempt_id, node_id, state, route_reason, error_json,"
            " relationship_id FROM attempts WHERE job_id=? ORDER BY created_at",
            (job_id,)).fetchall()]
        finished = job["state"] in v1.TERMINAL_JOB_STATES or job["state"] == "interrupted"
        return {
            "job_id": job_id, "chat_id": job["chat_id"], "state": job["state"],
            "finished": finished,
            # A DISTRIBUTED pass requires a relationship-bound attempt to have
            # reached `completed` itself. The job reaching `completed` is not
            # enough: an interrupted remote attempt followed by a successful
            # local fallback completes the job while proving only that the
            # fallback works, which is the opposite of what this tests.
            "passed": job["state"] == "completed" and any(
                a["relationship_id"] and a["state"] == "completed"
                for a in attempts),
            "fell_back": any(a["relationship_id"] for a in attempts) and any(
                not a["relationship_id"] and a["state"] == "completed"
                for a in attempts),
            # Every attempt, so a fallback shows both halves rather than only
            # the one that answered.
            "attempts": [{
                "state": a["state"], "route_reason": a["route_reason"],
                "ran_remotely": bool(a["relationship_id"]),
                "error": json.loads(a["error_json"]) if a["error_json"] else None,
            } for a in attempts],
            "pod_readiness": None,
            "pod_readiness_note": self.POD_READINESS_UNAVAILABLE,
        }

    def paired_worker(self) -> dict | None:
        return db.active_relationship(self.conn, self.workspace_id)

    def worker_client(self, relationship: dict) -> dispatch.WorkerClient:
        """Build a client bound to this relationship's pin and credential.

        The credential is read from the Keychain on every use rather than being
        cached on the object: a revoked relationship must stop working at the
        next request, not when the process restarts.
        """
        return dispatch.WorkerClient(
            address=relationship["address"], port=relationship["port"],
            fingerprint=relationship["fingerprint"],
            certificate_pem=relationship["certificate_pem"],
            credential=pairing.load_credential(relationship["relationship_id"]))

    def preflight(self, relationship: dict | None = None) -> dict | None:
        """Observe the paired worker, or return None.

        An identity mismatch is deliberately allowed to propagate: it must reach
        the operator as a changed-worker error, not be flattened into "the
        worker is unavailable" and answered locally.
        """
        relationship = relationship or self.paired_worker()
        if relationship is None:
            return None
        try:
            return self.worker_client(relationship).health()
        except pairing.IdentityMismatch:
            raise
        except (dispatch.DispatchUnavailable, pairing.PairingError):
            return None

    def choose_route(self) -> dispatch.Route:
        relationship = self.paired_worker()
        if relationship is None:
            return dispatch.Route("local", "local coordinator: no paired worker")
        try:
            node = self.preflight(relationship)
        except pairing.IdentityMismatch as exc:
            # Not a fallback. The attempt records the refusal and stops.
            return dispatch.Route("identity-mismatch", f"refused: {exc}")
        return dispatch.choose_route(relationship=relationship, node=node,
                                     required=["text.generate"],
                                     model_id=runtime.MODEL)

    def pair(self, *, address: str, port: int, fingerprint: str,
             certificate_pem: str, pairing_code: str) -> dict:
        """Complete OD-06 against a worker whose fingerprint a human confirmed.

        Order matters and is not an implementation detail: pin, verify the
        presented certificate, redeem the code, store the credential in the
        Keychain, and only then record the relationship. A row written before
        the Keychain write would describe a pairing with no usable credential.
        """
        fingerprint = pairing.normalise_fingerprint(fingerprint)
        if not pairing.keychain_available():
            raise RequestError(
                "Pairing needs the macOS Keychain to hold the worker credential. "
                "Storing it in the database is not permitted.", 501)
        relationship_id = db.new_id()
        body = json.dumps({"relationship_id": relationship_id,
                           "workspace_id": self.workspace_id,
                           "pairing_code": pairing_code}).encode("utf-8")
        context = pairing.pinned_context(certificate_pem)
        connection = http.client.HTTPSConnection(address, int(port), timeout=15,
                                                 context=context)
        try:
            connection.connect()
            pairing.verify_presented(connection.sock, fingerprint)
            connection.request("POST", "/v1/pairing/confirm", body=body, headers={
                "Content-Type": "application/json",
                "X-AegisForge-Contract": v1.CONTRACT_VERSION,
                "Content-Length": str(len(body))})
            response = connection.getresponse()
            payload = response.read(v1.MAX_REQUEST_BYTES)
            if response.status != 201:
                raise RequestError(
                    "The worker refused the pairing code. Generate a fresh one "
                    "on the worker host and try again.", 403)
            answer = json.loads(payload)
            credential = answer["credential"]
        except pairing.IdentityMismatch as exc:
            raise RequestError(str(exc), 409)
        except (OSError, ValueError, KeyError) as exc:
            raise RequestError(f"Could not reach the worker to pair: {exc}", 502)
        finally:
            connection.close()

        # The only write of the plaintext, and it goes to the OS store.
        pairing.store_credential(relationship_id, credential)
        del credential
        db.record_relationship(
            self.conn, relationship_id=relationship_id,
            workspace_id=self.workspace_id, node_id=answer["node_id"],
            display_name=answer.get("display_name") or address, address=address,
            port=int(port), fingerprint=fingerprint,
            certificate_pem=certificate_pem)
        return pairing.describe(db.get_relationship(self.conn, relationship_id,
                                                    self.workspace_id))

    def revoke_pairing(self, relationship_id: str) -> dict:
        """Revoke locally whatever the worker says.

        The remote delete is attempted first so the worker drops its hash, but a
        worker that is switched off must not be able to keep a relationship
        alive on this side: the local revocation and the Keychain deletion run
        regardless, and the attempts in flight are fenced.
        """
        relationship = db.get_relationship(self.conn, relationship_id,
                                           self.workspace_id)
        if relationship is None:
            raise RequestError("unknown relationship", 404)
        reached = False
        try:
            client = self.worker_client(relationship)
            connection = client._connect()
            try:
                connection.request("DELETE", f"/v1/pairing/{relationship_id}",
                                   headers=client._headers())
                reached = connection.getresponse().status in (204, 200)
            finally:
                connection.close()
        except Exception:                              # noqa: BLE001
            reached = False
        pairing.delete_credential(relationship_id)
        db.revoke_relationship(self.conn, relationship_id, self.workspace_id)
        fenced = db.fence_relationship_attempts(self.conn, relationship_id,
                                                self.node_id)
        return {"relationship_id": relationship_id, "worker_notified": reached,
                "attempts_fenced": len(fenced)}

    def _run_remote(self, job_id, chat_id, attempt_id, route, *, text: str):
        """Dispatch one attempt and turn the worker's stream into our events.

        Returns `(handled, attempt_id)`. `handled` is False only when the worker
        could not take the work and the caller should continue locally with the
        returned replacement attempt — that is the truthful fallback, and it
        leaves the remote attempt in history with its own typed reason.

        Nothing here writes canonical state directly: it uses the same
        `_emit`/`db` path a local attempt uses, so a remote answer and a local
        one are indistinguishable to every reader — including a restart.
        """
        job = dict(self.conn.execute("SELECT * FROM jobs WHERE job_id=?",
                                     (job_id,)).fetchone())
        step = self.conn.execute("SELECT step_id FROM attempts WHERE attempt_id=?",
                                 (attempt_id,)).fetchone()["step_id"]
        relationship = db.get_relationship(self.conn, route.relationship_id,
                                           self.workspace_id)
        if relationship is None or relationship["state"] != "paired":
            # Revoked between choosing the route and dispatching. Fall back
            # rather than dereferencing a row that is no longer there.
            return False, self._fallback(
                job_id, attempt_id, "the pairing was revoked before dispatch")
        try:
            envelope = dispatch.build_envelope(
                job=job, attempt_id=attempt_id, step_id=step, route=route,
                coordinator_node_id=self.node_id, request_text=text)
            client = self.worker_client(relationship)
            # One key per attempt, reused by any retry of it. A fresh key on a
            # retry would create a second remote attempt instead of replaying
            # the first, which is the opposite of what idempotency is for.
            client.submit(envelope, dispatch.idempotency_key_for(attempt_id))
        except dispatch.ReceiptUnknown as exc:
            # The request was sent and no answer came back, so the worker may
            # be running this attempt right now. Running it locally as well
            # would produce two answers to one request, so this does NOT fall
            # back: the attempt is interrupted and the operator is told why.
            self._stop(job_id, attempt_id, "interrupted", "running", {
                "code": "worker_lost",
                "message": ("the worker did not confirm the request; it may be "
                            "running there, so this was not re-run here. "
                            f"{exc}")[:256],
                "retryable": True})
            return True, attempt_id
        except pairing.IdentityMismatch as exc:
            # No fallback. A changed worker identity is the event pinning
            # exists to surface, and answering locally would bury it.
            self._stop(job_id, attempt_id, "failed", "running", {
                "code": "permission_denied", "message": str(exc)[:256],
                "retryable": False})
            return True, attempt_id
        except (dispatch.DispatchUnavailable, pairing.PairingError) as exc:
            # Truthful fallback: the worker could not take the work, so this
            # runs locally and the record says so.
            return False, self._fallback(job_id, attempt_id, str(exc))

        collected = []

        def keep(event):
            if event.data.kind == "output.delta":
                collected.append(event.data.text)
                db.append_output(self.conn, attempt_id, event.data.text)
                self._emit(job_id, attempt_id,
                           {"kind": "output.delta", "text": event.data.text})

        def cancelling() -> bool:
            if not (self.is_cancelled(job_id) or self.stopping.is_set()):
                return False
            try:
                # Reaches the worker API, which sets the Redis cancellation key
                # the executor polls. Both boundaries, one call.
                client.cancel(job_id, attempt_id)
            except Exception:                          # noqa: BLE001
                pass
            return True

        outcome = dispatch.consume(client, envelope, on_event=keep,
                                   should_cancel=cancelling)

        if outcome.state == "completed":
            db.set_attempt_state(self.conn, attempt_id, "validating",
                                 runtime_ms=outcome.runtime_ms,
                                 queue_ms=outcome.queue_ms)
            self._emit(job_id, attempt_id, {"kind": "attempt.state",
                                            "previous": "running",
                                            "current": "validating"})
            self._advance_job(job_id, "validating", "running")
            answer = "".join(collected)
            db.add_message(self.conn, chat_id, "assistant", answer, job_id=job_id)
            db.set_attempt_state(self.conn, attempt_id, "completed")
            self._emit(job_id, attempt_id, {"kind": "attempt.state",
                                            "previous": "validating",
                                            "current": "completed"})
            self._advance_job(job_id, "completed", "validating")
            return True, attempt_id
        if outcome.state == "cancelled":
            self._stop(job_id, attempt_id, "cancelled", "running", outcome.failure)
            return True, attempt_id
        # interrupted or failed: the workspace and history stay usable, and the
        # partial text that did arrive is already persisted. This is worker or
        # cluster loss, not a reason to silently re-run the same request.
        self._stop(job_id, attempt_id, "failed" if outcome.state == "failed"
                   else "interrupted", "running", outcome.failure)
        return True, attempt_id

    def _fallback(self, job_id, attempt_id, detail: str) -> str:
        """Record why the worker was not used and open a fresh local attempt.

        A new attempt rather than a reused one: the interrupted remote attempt
        keeps its own typed reason, which is what makes "the worker was tried
        first" visible in history instead of erased.
        """
        db.set_attempt_state(self.conn, attempt_id, "interrupted", error={
            "code": "unavailable",
            "message": f"the paired worker could not accept this work: {detail}"[:256],
            "retryable": True})
        self._emit(job_id, attempt_id, {"kind": "attempt.state",
                                        "previous": "running",
                                        "current": "interrupted"})
        self._advance_job(job_id, "interrupted", "running")
        self._advance_job(job_id, "queued", "interrupted")
        self._advance_job(job_id, "routing", "queued")
        local = db.create_attempt(
            self.conn, job_id=job_id, node_id=self.node_id,
            route_reason="local coordinator: the paired worker was unavailable, "
                         "so this ran on this computer")
        self._emit(job_id, local, {"kind": "attempt.state", "previous": None,
                                   "current": "queued"})
        self._advance_job(job_id, "running", "routing")
        db.set_attempt_state(self.conn, local, "running")
        self._emit(job_id, local, {"kind": "attempt.state",
                                   "previous": "queued", "current": "running"})
        return local

    @db.serialized
    def _stop(self, job_id, attempt_id, state, previous, error):
        """One typed reason per stopped attempt, as the contract requires."""
        try:
            if attempt_id:
                row = self.conn.execute("SELECT state FROM attempts WHERE attempt_id=?",
                                        (attempt_id,)).fetchone()
                db.set_attempt_state(self.conn, attempt_id, state, error=error)
                self._emit(job_id, attempt_id,
                           {"kind": "attempt.state", "previous": previous or row["state"],
                            "current": state})
            job = self.conn.execute("SELECT state FROM jobs WHERE job_id=?",
                                    (job_id,)).fetchone()
            job_state = "cancelled" if state == "cancelled" else "failed"
            db.set_job_state(self.conn, job_id, job_state)
            self._emit(job_id, None, {"kind": "job.state", "previous": job["state"],
                                      "current": job_state})
        except Exception:                              # noqa: BLE001
            traceback.print_exc()

    # ---- reads -----------------------------------------------------------

    @db.serialized
    def search(self, term):
        return db.search(self.conn, term)

    def export(self, chat_id, fmt):
        return db.export_chat(self.conn, chat_id, fmt)

    @db.serialized
    def chats(self):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM chats ORDER BY pinned DESC, updated_at DESC LIMIT 100")]

    @db.serialized
    def chat_messages(self, chat_id, with_attachments=False):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT m.*, a.error_json FROM messages m"
            " LEFT JOIN jobs j ON j.job_id=m.job_id AND m.role='assistant'"
            " LEFT JOIN attempts a ON a.attempt_id=j.active_attempt_id"
            " WHERE m.chat_id=? ORDER BY m.created_at, m.rowid",
            (chat_id,))]
        if with_attachments:
            by_message = db.attachments_by_message(self.conn, chat_id)
            # A reopened conversation and an export both need to say which
            # skill read which files, so the skill travels with the message.
            skills = {r["job_id"]: r["skill_id"] for r in self.conn.execute(
                "SELECT job_id, skill_id FROM jobs WHERE chat_id=?", (chat_id,))}
            artifacts = {}
            for artifact in db.artifacts_for_chat(self.conn, self.workspace_id, chat_id):
                artifacts.setdefault(artifact["job_id"], []).append(artifact)
            for row in rows:
                row["attachments"] = by_message.get(row["message_id"], [])
                row["skill_id"] = skills.get(row["job_id"])
                row["artifacts"] = artifacts.get(row["job_id"], [])
        return rows

    @db.serialized
    def jobs(self, chat_id=None, limit=50):
        sql = "SELECT * FROM jobs"
        args = ()
        if chat_id:
            sql += " WHERE chat_id=?"
            args = (chat_id,)
        sql += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
        return [dict(r) for r in self.conn.execute(sql, args + (limit,))]

    def active_jobs(self):
        # Include older running jobs even after fifty newer jobs have finished.
        stopped = v1.TERMINAL_JOB_STATES | {"interrupted"}
        return [job for job in self.jobs(limit=-1) if job["state"] not in stopped]

    @db.serialized
    def job_detail(self, job_id):
        job = self.conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if job is None:
            return None
        attempts = [dict(r) for r in self.conn.execute(
            "SELECT * FROM attempts WHERE job_id=? ORDER BY created_at", (job_id,))]
        for a in attempts:
            raw = a.pop("selection_json", None)
            a["selection"] = json.loads(raw) if raw else None
        events = [dict(r) for r in self.conn.execute(
            "SELECT * FROM events WHERE job_id=? ORDER BY sequence", (job_id,))]
        for e in events:
            e["data"] = json.loads(e.pop("data_json"))
        return {"job": dict(job), "attempts": attempts, "events": events}

    def capabilities(self, runtime_state: dict | None = None) -> list[dict]:
        """Observed capability state. `available` requires every observation.

        A document skill is available only when the parsers it needs exist on
        this computer. A missing parser, OCR engine or search index disables
        that one skill and nothing else — Chat and Code stay usable.
        """
        state = runtime_state if runtime_state is not None else runtime.probe()
        model_installed = runtime.MODEL in (state.get("models") or [])
        reading = documents.capability_summary()
        searchable = retrieval.fts_available(self.conn)
        rows = []
        for entry in CAPABILITIES:
            row = dict(entry)
            if entry.get("implemented") is False:
                row["state"] = "unavailable"
                row["detail"] = entry["setup"]
            elif entry.get("kind") == "document":
                blocked = self._document_blockers(entry, reading, searchable,
                                                  state, model_installed)
                row["formats"] = reading["supported"]
                row["unavailable_reasons"] = reading["unavailable"]
                row["state"] = "blocked" if blocked else "available"
                row["detail"] = blocked[0] if blocked else entry["detail_available"]
                if blocked:
                    row["setup"] = blocked[0]
            elif entry.get("kind") == "surface":
                # Implemented, but it needs the runtime like everything else.
                row["state"] = "available" if state.get("reachable") and model_installed else "blocked"
                row["detail"] = (entry["detail_available"] if row["state"] == "available"
                                 else "The AI engine or the configured model is not "
                                      "ready, so Code cannot propose changes yet.")
            elif not state.get("reachable"):
                row["state"] = "blocked"
                row["detail"] = ("The AI engine on this computer did not answer, "
                                 "so nothing can run yet.")
                row["setup"] = "Open Settings to see what this computer needs."
            elif not model_installed:
                row["state"] = "blocked"
                row["detail"] = (f"The configured model {runtime.MODEL} is not "
                                 "installed on this computer.")
                row["setup"] = f"ollama pull {runtime.MODEL}"
            else:
                row["state"] = "available"
                row["detail"] = "Runs on this computer."
            rows.append(row)
        return rows

    @staticmethod
    def _document_blockers(entry, reading, searchable, state, model_installed) -> list[str]:
        """Every reason this one skill cannot run, in the order to show them."""
        blocked = []
        if entry.get("needs_runtime") and not state.get("reachable"):
            blocked.append("The AI engine on this computer did not answer.")
        elif entry.get("needs_runtime") and not model_installed:
            blocked.append(f"The configured model {runtime.MODEL} is not installed "
                           "on this computer.")
        if entry.get("needs_search") and not searchable:
            blocked.append("This computer's SQLite build has no full-text search, "
                           "so documents cannot be searched.")
        if entry.get("needs_documents") and not reading["supported"]:
            blocked.append("No document format can be read on this computer.")
        if entry.get("needs_docx") and not docgen_available():
            blocked.append("Word documents cannot be written on this computer.")
        return blocked

    def status(self):
        with db.LOCK:
            counts = {row["state"]: row["n"] for row in self.conn.execute(
                "SELECT state, COUNT(*) AS n FROM jobs GROUP BY state")}
        runtime_state = runtime.probe()
        return {
            "product": {"name": "Refinix", "surface": "local"},
            "desktop": dict(self.desktop),
            "node_id": self.node_id,
            "workspace_id": self.workspace_id,
            "contract_version": v1.CONTRACT_VERSION,
            "contract_status": "reviewed draft; not frozen, integration pending C05",
            "bind": f"{BIND_HOST}",
            "runtime": runtime_state,
            "model_configured": runtime.MODEL,
            "model_installed": runtime.MODEL in (runtime_state.get("models") or []),
            # The approved model, and the reasoning choice that applies to it.
            # Only models this build actually supports are offered; a name in
            # the runtime's tag list is not approval to use it.
            "models": [{
                "id": runtime.MODEL,
                "reasoning": db.get_reasoning(self.conn, runtime.MODEL),
                "installed": runtime.MODEL in (runtime_state.get("models") or []),
                "reasoning_note": "Reasoning gives the model room to work through "
                                  "a problem before answering. It is slower and "
                                  "can use the whole reply budget.",
            }],
            "capabilities": self.capabilities(runtime_state),
            "attachments": {
                "max_bytes": db.MAX_ATTACHMENT_BYTES,
                "max_files": db.MAX_ATTACHMENTS_PER_REQUEST,
                "accepted": sorted({k.lstrip(".") for k in db.ATTACHMENT_TYPES}),
                # Plain Chat still reads nothing. A document skill reads only
                # the files sent with its own request.
                "processing": "Plain Chat does not read attachments. Choose a "
                              "document skill with + to have the files on that "
                              "request read.",
            },
            "documents": {
                **documents.capability_summary(),
                "search": retrieval.METHOD if retrieval.fts_available(self.conn)
                          else None,
                "search_note": retrieval.METHOD_NOTE,
                "generates": ["docx"] if docgen_available() else [],
                "workflow": docflow.WORKFLOW,
            },
            "bounded": {"num_ctx": runtime.NUM_CTX,
                        "num_predict": runtime.NUM_PREDICT,
                        "think": runtime.THINK},
            "context": {
                "window_tokens": runtime.NUM_CTX,
                "reply_allowance_tokens": runtime.NUM_PREDICT,
                "conversation_budget_tokens": context.input_budget(
                    runtime.NUM_CTX, runtime.NUM_PREDICT),
                "counting_method": context.Selection().counting_method,
                "policy": "Older complete exchanges are left out of a request "
                          "when it will not fit. Saved history is never changed.",
            },
            "jobs_by_state": counts,
            "repaired_on_start": len(self.repaired),
            "surfaces": {"chat": "available", "settings": "available",
                         "code": "available"},
            # Every value below needs evidence this chunk cannot produce.
            "unavailable": {
                "workers": "no worker is paired; C06 establishes pairing",
                "cluster": "no cluster is deployed; C05 provisions it",
                "approvals": "the approval path is implemented at C10",
                "proof": "Proof Cards are produced at C10",
                "egress": "zero-egress evidence is collected at C11",
            },
        }


class Handler(BaseHTTPRequestHandler):
    server_version = "AegisForgeCoordinator/0.1"
    protocol_version = "HTTP/1.1"
    coordinator: Coordinator = None      # injected by serve()

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, BrokenPipeError):
            # Closing a browser connection does not cancel its persisted job.
            self.close_connection = True

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}", flush=True)

    # -- helpers
    def _json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self, limit=None):
        lengths = self.headers.get_all("Content-Length", [])
        if self.headers.get("Transfer-Encoding") or len(lengths) != 1:
            raise RequestError("one Content-Length is required")
        if self.headers.get_content_type() != "application/json":
            raise RequestError("Content-Type must be application/json", 415)
        if not lengths[0].isascii() or not lengths[0].isdigit():
            raise RequestError("invalid Content-Length")
        length = int(lengths[0])
        if length > (limit or v1.MAX_REQUEST_BYTES):
            raise RequestError("request is too large", 413)
        # A whole file needs longer than a contract-sized body, but only the
        # route that actually carries one gets the longer window.
        self.connection.settimeout(30 if limit else 10)
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("incomplete body")
            body = json.loads(raw)
        except (ValueError, OSError) as exc:
            raise RequestError("invalid JSON body") from exc
        if not isinstance(body, dict):
            raise RequestError("JSON body must be an object")
        return body

    def _local_request(self):
        hosts = {f"127.0.0.1:{self.server.server_port}",
                 f"localhost:{self.server.server_port}"}
        host = self.headers.get("Host")
        if len(self.headers.get_all("Host", [])) != 1 or host not in hosts:
            raise RequestError("local Host required", 403)
        origins = self.headers.get_all("Origin", [])
        if (origins and origins != [f"http://{host}"]) or self.headers.get(
                "Sec-Fetch-Site") == "cross-site":
            raise RequestError("same-origin access required", 403)

    @staticmethod
    def _text(payload, key, maximum=16_384):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise RequestError(f"{key} must be nonempty text of at most {maximum} characters")
        return value.strip()

    def _export(self, c, query):
        """A download the user explicitly asked for, of saved history only."""
        fmt = (query.get("format") or ["md"])[0]
        if fmt not in ("md", "txt"):
            raise RequestError("format must be md or txt")
        name, body = c.export(query["chat_id"][0], fmt)
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type",
                         f"text/{'markdown' if fmt == 'md' else 'plain'}; charset=utf-8")
        fallback = name.encode("ascii", "replace").decode().replace("?", "_")
        self.send_header("Content-Disposition",
                         f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{quote(name, safe="")}')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _artifact_export(self, c, payload):
        """Send a generated document only after an approval was recorded.

        The approval is claimed here, one-shot and bound to this artifact's
        digest, so a request that was approved once cannot be replayed and an
        artifact that was never approved cannot be downloaded at all.
        """
        artifact_id = self._text(payload, "artifact_id", 36)
        approval_id = self._text(payload, "approval_id", 36)
        artifact = db.public_artifact(c.conn, artifact_id, c.workspace_id)
        if artifact is None:
            raise RequestError("that document no longer exists", 404)
        root = db.artifacts_root(c.state_path)
        path = db.artifact_path(c.conn, root, artifact_id, c.workspace_id)
        if path is None:
            raise RequestError("that document is no longer stored", 404)
        data = path.read_bytes()
        # The digest is re-checked at the moment of sending, so a file that
        # changed under the record is not exported as though it had not.
        import hashlib
        if hashlib.sha256(data).hexdigest() != artifact["sha256"]:
            raise RequestError("that document changed on disk and was not sent", 409)
        try:
            db.claim_approval(c.conn, approval_id, c.workspace_id,
                              "artifact.export", artifact["sha256"],
                              repo_id=artifact_id)
        except db.ApprovalError as exc:
            raise RequestError(str(exc), 409) from exc
        self.send_response(200)
        self.send_header("Content-Type", artifact["media_type"])
        fallback = artifact["filename"].encode("ascii", "replace").decode().replace("?", "_")
        self.send_header(
            "Content-Disposition",
            f'attachment; filename="{fallback}"; '
            f"filename*=UTF-8''{quote(artifact['filename'], safe='')}")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)
        self.wfile.flush()
        db.set_artifact_state(c.conn, artifact_id, c.workspace_id, "exported")
        db.record_audit(c.conn, workspace_id=c.workspace_id, repo_id=artifact_id,
                        action="artifact.export", outcome="approved",
                        approval_id=approval_id,
                        detail={"filename": artifact["filename"],
                                "sha256": artifact["sha256"]})

    def _code(self, operation):
        """Run one Code operation, turning a pending approval into a 202.

        The handler carries no policy of its own: `CodeService` decides, and
        this only translates the outcome into a response.
        """
        try:
            self._json(operation())
        except code_service.ApprovalNeeded as pending:
            self._json({"needs_approval": pending.approval}, 202)
        except repo_errors as exc:                     # noqa: B902
            self._json({"error": str(exc), "code": exc.code}, 400)

    def _attach(self, c, payload):
        """Take one selected file into local storage. Nothing reads it.

        The bytes arrive base64-encoded over loopback from either the native
        file dialog or the browser file input, so there is one intake path and
        no route that accepts a filesystem path from the page.
        """
        filename = payload.get("filename")
        chat_id = self._text(payload, "chat_id", 36)
        if chat_id != db.NEW_CHAT_DRAFT and not c.conn.execute(
                "SELECT 1 FROM chats WHERE chat_id=? AND workspace_id=?",
                (chat_id, c.workspace_id)).fetchone():
            raise RequestError("unknown conversation", 404)
        encoded = payload.get("data")
        if not isinstance(encoded, str) or not encoded:
            raise RequestError("data must be base64 text")
        if len(encoded) > MAX_UPLOAD_BYTES:
            raise RequestError("request is too large", 413)
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise RequestError("data was not valid base64") from exc
        record = db.add_attachment(c.conn, c.attachments_root,
                                   workspace_id=c.workspace_id, chat_id=chat_id,
                                   filename=filename, data=raw)
        record.pop("stored_name", None)
        return {"attachment": record}

    def _static(self, path):
        name = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (STATIC / unquote(name)).resolve()
        if not target.is_relative_to(STATIC.resolve()) or not target.is_file():
            self._json({"error": "not found"}, 404)
            return
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MEDIA.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    # -- routes
    def do_GET(self):
        parsed = urlparse(self.path)
        route, query = parsed.path, parse_qs(parsed.query)
        c = self.coordinator
        try:
            self._local_request()
            if route == "/v1/status":
                self._json(c.status())
            elif route == "/v1/chats":
                self._json({"chats": c.chats()})
            elif route == "/v1/messages":
                self._json({"messages": c.chat_messages(query["chat_id"][0],
                                                        with_attachments=True)})
            elif route == "/v1/capabilities":
                self._json({"capabilities": c.capabilities()})
            elif route == "/v1/attachments":
                self._json({"attachments": db.list_attachments(
                    c.conn, chat_id=query["chat_id"][0])})
            elif route == "/v1/desktop/focus":
                # Polled by the desktop shell; a second launch sets the flag.
                wanted = c.focus_requested.is_set()
                c.focus_requested.clear()
                self._json({"focus": wanted})
            elif route == "/v1/artifacts":
                self._json({"artifacts": db.artifacts_for_chat(
                    c.conn, c.workspace_id, query["chat_id"][0])})
            elif route == "/v1/code/state":
                self._json(c.code.state((query.get("repo_id") or [None])[0]))
            elif route == "/v1/code/files":
                self._code(lambda: c.code.files(
                    self._text(_as_payload(query), "repo_id", 36),
                    (query.get("approval_id") or [None])[0]))
            elif route == "/v1/worker/selftest":
                self._json(c.selftest_result(
                    self._text(_as_payload(query), "job_id", 36)))
            elif route == "/v1/worker":
                # Preflight for the Control Center. Every field is either an
                # observation or explicitly unavailable; nothing is inferred
                # from the fact that a relationship row exists.
                self._json(c.worker_state())
            elif route == "/v1/jobs/active":
                self._json({"jobs": c.active_jobs()})
            elif route == "/v1/jobs":
                self._json({"jobs": c.jobs((query.get("chat_id") or [None])[0])})
            elif route == "/v1/job":
                detail = c.job_detail(query["job_id"][0])
                self._json(detail or {"error": "not found"}, 200 if detail else 404)
            elif route == "/v1/search":
                self._json({"results": c.search((query.get("q") or [""])[0])})
            elif route == "/v1/draft":
                self._json({"text": db.get_draft(c.conn, query["chat_id"][0])})
            elif route == "/v1/export":
                self._export(c, query)
            elif route == "/v1/events":
                self._sse()
            else:
                self._static(route)
        # Ordered most specific first. RequestError and CodeError both subclass
        # ValueError, so a bare `except ValueError` above them would swallow
        # their status — a 403 would answer 400 and a 404 would answer 400.
        except code_service.CodeError as exc:
            self._json({"error": str(exc), "code": exc.code}, exc.status)
        except RequestError as exc:
            self.close_connection = True
            self._json({"error": str(exc)}, exc.status)
        except ValueError as exc:
            self._json({"error": str(exc)}, 400)
        except KeyError as exc:
            self._json({"error": f"missing parameter {exc}"}, 400)
        except (ConnectionResetError, BrokenPipeError):
            raise  # handled once at the connection boundary
        except Exception as exc:                       # noqa: BLE001
            traceback.print_exc()
            self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)

    def do_POST(self):
        route = urlparse(self.path).path
        c = self.coordinator
        try:
            self._local_request()
            payload = self._body(MAX_UPLOAD_BYTES if route == "/v1/attachments" else None)
            if route == "/v1/chats":
                chat_id = db.create_chat(c.conn, c.workspace_id,
                                         self._text(payload, "title", 120)
                                         if "title" in payload else "New chat")
                self._json({"chat_id": chat_id}, 201)
            elif route == "/v1/messages":
                text = self._text(payload, "text")
                chat_id = self._text(payload, "chat_id", 36)
                draft_id = payload.get("draft_id", chat_id)
                draft_text = payload.get("draft_text", text)
                if (draft_id not in (chat_id, db.NEW_CHAT_DRAFT)
                        or not isinstance(draft_text, str) or len(draft_text) > 16_384
                        or draft_text.strip() != text):
                    raise RequestError("invalid submitted draft")
                skill_id = payload.get("skill_id") or None
                if skill_id is not None and (not isinstance(skill_id, str)
                                             or len(skill_id) > 40):
                    raise RequestError("invalid skill")
                job_id = c.submit(chat_id, text, draft_id=draft_id, skill_id=skill_id)
                # Clear only the version that was sent; newer typing survives.
                db.clear_draft_if_matches(c.conn, draft_id, draft_text)
                self._json({"job_id": job_id}, 202)
            elif route == "/v1/chat/rename":
                chat_id = self._text(payload, "chat_id", 36)
                title = db.rename_chat(c.conn, chat_id, payload.get("title", ""))
                self._json({"chat_id": chat_id, "title": title})
            elif route == "/v1/chat/pin":
                chat_id = self._text(payload, "chat_id", 36)
                pinned = bool(payload.get("pinned"))
                db.set_pinned(c.conn, chat_id, pinned)
                self._json({"chat_id": chat_id, "pinned": pinned})
            elif route == "/v1/chat/delete":
                chat_id = self._text(payload, "chat_id", 36)
                db.delete_chat(c.conn, chat_id, c.attachments_root,
                               db.artifacts_root(c.state_path))
                self._json({"deleted": chat_id})
            elif route == "/v1/context":
                chat_id = payload.get("chat_id") or None
                if chat_id is not None:
                    chat_id = self._text(payload, "chat_id", 36)
                    if not c.conn.execute(
                            "SELECT 1 FROM chats WHERE chat_id=? AND workspace_id=?",
                            (chat_id, c.workspace_id)).fetchone():
                        raise RequestError("unknown conversation", 404)
                draft = payload.get("draft", "")
                if not isinstance(draft, str) or len(draft) > 16_384:
                    raise RequestError("draft must be text of at most 16384 characters")
                self._json(c.context_estimate(chat_id, draft))
            elif route == "/v1/attachments":
                self._json(self._attach(c, payload), 201)
            elif route == "/v1/attachment/delete":
                db.delete_attachment(c.conn, c.attachments_root,
                                     self._text(payload, "attachment_id", 36))
                self._json({"removed": payload["attachment_id"]})
            elif route == "/v1/desktop/focus":
                # A second launch asks the copy already running to come forward.
                c.focus_requested.set()
                self._json({"focus_requested": True}, 202)
            elif route == "/v1/model/reasoning":
                # Request-scoped switch, stored per model by the coordinator so
                # it survives a restart and a fallback port.
                model = self._text(payload, "model", 200)
                if model != runtime.MODEL:
                    raise RequestError("that model is not configured on this computer", 404)
                enabled = payload.get("enabled")
                if not isinstance(enabled, bool):
                    raise RequestError("enabled must be true or false")
                db.set_reasoning(c.conn, model, enabled)
                self._json({"model": model, "reasoning": enabled})
            elif route == "/v1/code/mode":
                self._code(lambda: c.code.set_mode(
                    self._text(payload, "repo_id", 36),
                    self._text(payload, "mode", 20)))
            elif route == "/v1/code/forget":
                self._code(lambda: c.code.forget(self._text(payload, "repo_id", 36)))
            elif route == "/v1/code/propose":
                self._code(lambda: c.code.propose(
                    self._text(payload, "repo_id", 36),
                    self._text(payload, "request", 4000),
                    payload.get("paths") or [],
                    payload.get("approval_id") or None))
            elif route == "/v1/code/apply":
                self._code(lambda: c.code.apply(
                    self._text(payload, "repo_id", 36),
                    self._text(payload, "proposal_id", 36),
                    payload.get("approval_id") or None))
            elif route == "/v1/code/decision":
                # Only an opaque id and a yes/no. No target, digest, mode,
                # path or replacement content is accepted here.
                self._code(lambda: c.code.decide(
                    self._text(payload, "approval_id", 36),
                    payload.get("approved")))
            elif route == "/v1/artifact/approve-export":
                self._json(c.request_export(self._text(payload, "artifact_id", 36)),
                           202)
            elif route == "/v1/artifact/export":
                self._artifact_export(c, payload)
            elif route == "/v1/code/cancel":
                self._json({"cancelled": c.code.cancel(
                    self._text(payload, "repo_id", 36))}, 202)
            elif route == "/v1/draft":
                db.set_draft(c.conn, self._text(payload, "chat_id", 36),
                             str(payload.get("text", ""))[:16384])
                self._json({"saved": True})
            elif route == "/v1/cancel":
                c.request_cancel(self._text(payload, "job_id", 36))
                self._json({"cancel_requested": payload["job_id"]}, 202)
            elif route == "/v1/pair":
                # The fingerprint and the code arrived out of band, read by a
                # human. Neither is stored here: the code is spent by the
                # worker and the credential goes straight to the Keychain.
                self._json(c.pair(
                    address=self._text(payload, "address", 255),
                    port=int(payload.get("port") or v1.WORKER_NODE_PORT),
                    fingerprint=self._text(payload, "fingerprint", 128),
                    certificate_pem=self._text(payload, "certificate_pem", 16384),
                    pairing_code=self._text(payload, "pairing_code", 256)), 201)
            elif route == "/v1/worker/selftest":
                # Explicitly started, never automatic: it invokes the model.
                self._json(c.run_selftest(), 202)
            elif route == "/v1/pair/revoke":
                self._json(c.revoke_pairing(
                    self._text(payload, "relationship_id", 36)), 200)
            else:
                self._json({"error": "not found"}, 404)
        except db.ChatBusyError as exc:
            self._json({"error": str(exc)}, 409)
        except db.AttachmentRejected as exc:
            self._json({"error": str(exc)}, 422)
        except code_service.CodeError as exc:
            self._json({"error": str(exc), "code": exc.code}, exc.status)
        except RequestError as exc:
            self.close_connection = True
            self._json({"error": str(exc)}, exc.status)
        except ValueError as exc:
            self._json({"error": str(exc)}, 400)
        except KeyError as exc:
            self._json({"error": f"missing field {exc}"}, 400)
        except (ConnectionResetError, BrokenPipeError):
            raise  # handled once at the connection boundary
        except Exception as exc:                       # noqa: BLE001
            traceback.print_exc()
            self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)

    def _sse(self):
        key, q = self.coordinator.hub.subscribe()
        stopping = self.coordinator.stopping
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            idle = 0
            while not stopping.is_set():
                try:
                    # A short wait keeps shutdown responsive; the keep-alive
                    # frame still only goes out every ~15s.
                    event = q.get(timeout=1)
                    frame = f"data: {json.dumps(event)}\n\n"
                    idle = 0
                except queue.Empty:
                    idle += 1
                    if idle < 15:
                        continue
                    idle = 0
                    frame = ": keep-alive\n\n"
                self.wfile.write(frame.encode())
                self.wfile.flush()
        finally:
            self.coordinator.hub.unsubscribe(key)


def build_server(state_path: Path, port: int = DEFAULT_PORT):
    """Create the coordinator and its listener without serving.

    The desktop shell serves this on a background thread; `serve()` below runs
    it in the foreground exactly as before. A port already in use raises
    OSError here, which is what lets a caller choose another one.
    """
    # Bind first: an occupied port must fail before any state is opened.
    httpd = ThreadingHTTPServer((BIND_HOST, port), Handler)
    coordinator = Coordinator(state_path)
    Handler.coordinator = coordinator
    httpd.daemon_threads = True
    # ThreadingMixIn.block_on_close defaults to True, which makes server_close()
    # join every handler thread. A held-open SSE connection never returns, so
    # Ctrl+C would hang the process instead of stopping it.
    httpd.block_on_close = False
    return httpd, coordinator


def shutdown_server(httpd, coordinator) -> None:
    """Release streaming loops first, then stop the listener."""
    coordinator.stopping.set()
    httpd.shutdown()
    httpd.server_close()


def serve(state_path: Path, port: int = DEFAULT_PORT):
    httpd, coordinator = build_server(state_path, port)
    # flush=True: the operator must see this even when stdout is a pipe.
    banner = [
        "Refinix coordinator",
        f"  contract   {v1.CONTRACT_VERSION} (reviewed draft, not frozen)",
        f"  state      {state_path}",
        f"  node       {coordinator.node_id}",
        f"  repaired   {len(coordinator.repaired)} interrupted job(s) on start",
        f"  listening  http://{BIND_HOST}:{port}  (loopback only)",
    ]
    print("\n".join(banner), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping", flush=True)
    finally:
        shutdown_server(httpd, coordinator)
        # Daemon generation threads may still be leaving a blocked runtime read.
        # Process exit closes SQLite; closing it under those threads is unsafe.
        print("stopped", flush=True)
