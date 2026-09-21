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

from backend.contracts import profiles as inference_profiles
from backend.contracts import v1
from backend.coordinator import (code_service, codeflow, context, db, device, dispatch,
                                 docflow, docgen, documents, identity, models,
                                 pairing, pdfgen, policy, proof, repo,
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

MODEL_DEFAULTS = {
    "chat": runtime.MODEL,
    "code": runtime.MODEL,
    "documents.generate": runtime.MODEL,
    "documents.ocr": runtime.OCR_MODEL,
}

# What this build can actually do, with the reason when it cannot. Nothing here
# is inferred from configuration; each entry becomes available only after its
# runtime, model and local parser requirements are observed.
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
     "summary": "Create a Word or PDF document from your request, files, or prior answer.",
     "detail_available": "Choose a general document or the fixed inspection "
                         "approval note. The result stays on this computer "
                         "until you approve an export."},
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


# Which self-test answers for which capability. Only the capabilities whose
# smallest representative check exists are listed; the rest simply carry no
# self-test rather than an invented "passed".
CAPABILITY_SELFTEST_SCOPE = {
    "chat": models.CHAT,
    "code": models.CODE,
    "write-document": models.DOCUMENTS_GENERATE,
    "read-document": models.DOCUMENTS_OCR,
}

def _as_payload(query: dict) -> dict:
    """One-value view of a query string, so `_text` validates GET the same way."""
    return {key: values[0] for key, values in query.items() if values}


def docgen_available() -> bool:
    """Whether real Word output works on this computer.

    An observation, not a guess about the platform: `docgen.probe` writes a
    small document to a temporary folder and reopens it once per process. A
    computer that cannot do that reports Documents as blocked rather than
    failing at the end of somebody's work.
    """
    return docgen.available()


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
        # A stable measured target identity, never the node UUID or a volatile
        # memory/health reading.  Unknown hardware intentionally has no local
        # production profile until it is qualified.
        self.target_profile_id = device.qualified_target_profile()
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
        # AF-013. An approved write that a stop interrupted is finished here,
        # before anything else runs. Recovery compares each file against its
        # recorded before/after digests, so a file already written is recorded
        # rather than written twice and a file someone else changed is left
        # alone.
        self.resumed_writes = self.code.resume_writes()

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

    def model_for(self, scope: str, *, new_work: bool = False) -> str:
        if scope not in MODEL_DEFAULTS:
            raise RequestError("that model scope does not exist")
        model = db.get_model_selection(self.conn, scope, MODEL_DEFAULTS[scope])
        if new_work and not db.get_model_enabled(self.conn, model):
            raise RequestError(
                f"The selected model {model} is switched off for new work.", 409)
        return model

    def enabled_model_for(self, scope: str) -> str | None:
        """The selected model only when it may receive a new request."""
        model = self.model_for(scope)
        return model if db.get_model_enabled(self.conn, model) else None

    def local_model_ref(self, model: str,
                        runtime_state: dict | None = None) -> dict | None:
        state = runtime_state if runtime_state is not None else runtime.probe()
        digest = (state.get("digests") or {}).get(model) or ""
        if (not state.get("reachable") or len(digest) != 64
                or not models.digest_eligible(model, digest)):
            return None
        return {"model_id": model, "manifest_sha256": digest,
                "runtime": "ollama",
                "runtime_version": state.get("server_version") or "unknown"}

    def local_profiles(self, runtime_state: dict | None = None) \
            -> list[v1.ExecutionProfile]:
        state = runtime_state if runtime_state is not None else runtime.probe()
        refs = []
        for model, digest in (state.get("digests") or {}).items():
            if model and isinstance(digest, str) and len(digest) == 64:
                try:
                    refs.append(v1.ModelRef(
                        model_id=model, manifest_sha256=digest,
                        runtime="ollama",
                        runtime_version=state.get("server_version") or "unknown"))
                except ValueError:
                    continue
        return inference_profiles.for_observation(
            target_profile_id=self.target_profile_id, models=refs)

    def local_profile(self, *, workflow: str, model_id: str, reasoning: str,
                      decoder: str, runtime_state: dict | None = None,
                      output_allowance: int | None = None,
                      context_window: int | None = None) \
            -> v1.ExecutionProfile | None:
        return next((profile for profile in self.local_profiles(runtime_state)
                     if inference_profiles.compatible(
                         profile, model_id=model_id, workflow=workflow,
                         reasoning=reasoning, decoder=decoder,
                         output_allowance=output_allowance,
                         context_window=context_window)), None)

    def _identity_message(self, model_id, runtime_state=None):
        """The product-identity block for one Chat turn.

        The installed list comes from the runtime health probe, which is the
        cheapest authoritative answer available here — no second registry, and
        no per-model capability call or paired-worker round trip on the path
        every Chat message takes. When it cannot be read the block says so; it
        never falls back to a number.
        """
        try:
            # Named `installed`, not `models`: this module now imports a
            # `models` module, and a local of the same name would shadow it.
            installed = identity.linked_models(
                runtime_state if runtime_state is not None else runtime.probe())
        except Exception:                                  # noqa: BLE001
            # An unreachable engine or worker is a reason to say the inventory
            # is unavailable, never a reason to fail the person's message.
            installed = None
        return identity.system_message(engine=model_id, models=installed)

    def model_inventory(self, runtime_state: dict | None = None) -> list[dict]:
        """Every model this installation knows about, and its state here.

        Four states rather than a list of names: installed, supported but not
        installed, installed without recorded provenance, and unknown because
        the engine did not answer. A model the person disabled keeps its row —
        it is simply no longer eligible for new work, which is a different
        fact from being absent.
        """
        state = runtime_state if runtime_state is not None else runtime.probe()
        reachable = bool(state.get("reachable"))
        digests = state.get("digests") or {}
        local = {model: digests.get(model) for model in (state.get("models") or [])
                 if model}
        remote = {}
        remote_profiles = []
        try:
            node = self.preflight()
        except pairing.IdentityMismatch:
            node = None
        for item in (node or {}).get("models") or []:
            if item.get("model_id") and len(item.get("manifest_sha256") or "") == 64:
                remote[item["model_id"]] = item
        for item in (node or {}).get("inference_profiles") or []:
            try:
                remote_profiles.append(v1.ExecutionProfile.model_validate(item))
            except ValueError:
                continue
        local_profiles = self.local_profiles(state)
        selected = {scope: self.model_for(scope) for scope in MODEL_DEFAULTS}
        enablement = db.model_enablement(self.conn)
        recorded = db.selftests(self.conn)
        names = sorted(set(local) | set(remote) | set(MODEL_DEFAULTS.values())
                       | set(models.BY_ID))
        rows = []
        for model in names:
            # Named by role, not by operating system: the same words are true
            # on Windows, macOS and Linux, and this installation cannot know a
            # peer's OS beyond what that peer reports of itself.
            locations = ([device.location_label(local=True)] if model in local else []) + \
                        ([device.location_label(local=False)] if model in remote else [])
            enabled = enablement.get(model, True)
            local_integrity = models.integrity(model, local.get(model))
            worker_integrity = models.integrity(
                model, (remote.get(model) or {}).get("manifest_sha256"))
            local_eligible = (model in local and local_integrity["eligible"]
                              and any(p.model.model_id == model
                                      for p in local_profiles))
            remote_eligible = (model in remote and worker_integrity["eligible"]
                               and any(p.model.model_id == model
                                       for p in remote_profiles))
            eligible = []
            profile_scopes = {
                inference_profiles.CHAT: "chat",
                inference_profiles.CODE: "code",
                inference_profiles.DOCUMENTS: "documents.generate",
            }
            if enabled:
                for profile in [*local_profiles, *remote_profiles]:
                    scope = profile_scopes.get(profile.workflow_mode)
                    if profile.model.model_id == model and scope and scope not in eligible:
                        eligible.append(scope)
            if enabled and local_eligible:
                if runtime.VISION_CAPABILITY in \
                        (runtime.model_capabilities(model) or []):
                    eligible.append("documents.ocr")
            lifecycle = models.lifecycle_state(
                model, installed_here=model in local,
                installed_elsewhere=model in remote, runtime_reachable=reachable)
            rows.append({
                "id": model, "installed": bool(locations), "locations": locations,
                "state": lifecycle,
                "enabled": enabled,
                "eligible_scopes": eligible,
                "supported_scopes": list(
                    (models.entry_for(model).scopes if models.entry_for(model)
                     else ())),
                "provenance": models.provenance(model),
                "setup": models.setup_action(model) if lifecycle == models.ABSENT
                         else None,
                "selftests": models.selftest_view(
                    recorded, model=model, digest=local.get(model)),
                "selected_for": [scope for scope, chosen in selected.items()
                                 if chosen == model],
                "reasoning": db.get_reasoning(self.conn, model),
                "reasoning_note": "Reasoning may improve difficult work but is slower.",
                "digests": {"local": local.get(model),
                            "worker": (remote.get(model) or {}).get("manifest_sha256")},
                "integrity": {"local": local_integrity,
                              "worker": worker_integrity},
                "execution_profiles": {
                    "local": [p.model_dump() for p in local_profiles
                              if p.model.model_id == model],
                    "worker": [p.model_dump() for p in remote_profiles
                               if p.model.model_id == model],
                },
            })
        return rows

    def select_model(self, scope: str, model: str) -> dict:
        if scope not in MODEL_DEFAULTS:
            raise RequestError("that model scope does not exist")
        if model == "auto":
            raise RequestError("automatic model choice is not enabled yet", 409)
        row = next((item for item in self.model_inventory() if item["id"] == model),
                   None)
        if row is None or scope not in row["eligible_scopes"]:
            # Ordered from the most fundamental reason outwards, so the message
            # names the thing that actually has to change. A model that is both
            # absent and switched off is absent first: turning it back on would
            # not make it selectable.
            if row is None or not row["installed"]:
                raise RequestError("that model is not available for this workflow",
                                   409)
            if not row["enabled"]:
                raise RequestError(
                    "that model is switched off for new work; turn it back on first",
                    409)
            if scope == "documents.ocr":
                raise RequestError(
                    "the runtime did not confirm that model accepts document images",
                    409)
            raise RequestError("that model is not available for this workflow", 409)
        db.set_model_selection(self.conn, scope, model)
        return {"scope": scope, "model": model}

    def set_model_enabled(self, model: str, enabled: bool) -> dict:
        """Turn one model on or off for new work.

        Nothing is deleted and no running attempt changes: a job already
        under way keeps the model it was dispatched with, because silently
        swapping it would make the recorded attempt describe work that did not
        happen. A disabled model simply stops being eligible for the next one.
        """
        row = next((item for item in self.model_inventory() if item["id"] == model),
                   None)
        if row is None:
            raise RequestError("that model is not known to this installation", 404)
        db.set_model_enabled(self.conn, model, bool(enabled))
        return {"model": model, "enabled": bool(enabled),
                "impact": self.removal_impact(model)}

    def removal_impact(self, model: str) -> dict:
        """What a removal would and would not break, before it happens."""
        return models.removal_impact(
            model,
            selections={scope: self.model_for(scope) for scope in MODEL_DEFAULTS},
            enabled=db.model_enablement(self.conn))

    def run_model_selftest(self, scope: str,
                           runtime_state: dict | None = None) -> dict:
        """Run one capability's smallest representative check and record it.

        Named apart from `run_selftest`, which is the *worker* round-trip: the
        two answer different questions and must never be confused for one
        another in a status line.

        The result is stored against the manifest digest observed at the time,
        so replacing a model's bytes under the same tag cannot inherit a pass.
        A check that could not run is recorded as unavailable with its reason,
        never as a failure of the model.
        """
        if scope not in models.SELFTESTS:
            raise RequestError("there is no self-test for that workflow", 404)
        state = runtime_state if runtime_state is not None else runtime.probe()
        model = self.model_for(scope, new_work=True)
        try:
            if not state.get("reachable"):
                raise models.SelfTestError(
                    f"The local engine at {runtime.HOST} did not answer.")
            if model not in (state.get("models") or []):
                raise models.SelfTestError(
                    f"{model} is not installed on this computer.")
            # Asked only by the one check that needs a modality, so the other
            # three do not pay for a round trip whose answer they ignore.
            capabilities = (runtime.model_capabilities(model)
                            if models.SELFTESTS[scope].needs_vision else None)
            result = models.run_selftest(
                scope, model, generate=self._selftest_generate,
                artifact=docgen.selftest, capabilities=capabilities)
        except models.SelfTestError as exc:
            result = {"scope": scope, "model": model, "state": "unavailable",
                      "detail": str(exc)}
        return db.record_selftest(
            conn=self.conn, model=model, scope=scope, state=result["state"],
            detail=result["detail"],
            digest=(state.get("digests") or {}).get(model),
            runtime_version=state.get("server_version"))

    def _selftest_generate(self, model: str, messages: list[dict], **options) -> str:
        """One bounded local generation through a production message shape.

        Each caller supplies the same messages and decoder constraint as its
        real workflow. The allowance stays bounded, so this remains a
        capability check rather than a benchmark.

        It watches the coordinator's stopping flag for the same reason every
        other streaming path does: without it, quitting while a self-test is
        loading a cold model would wait out the runtime's whole request
        timeout instead of closing.
        """
        response_format = options.pop("response_format", None)
        output_allowance = options.pop("num_predict", None)
        if response_format == codeflow.PROPOSAL_SCHEMA:
            workflow, decoder = inference_profiles.CODE, "json_schema"
        elif response_format is not None:
            workflow, decoder = inference_profiles.DOCUMENTS, "json_schema"
        else:
            workflow, decoder = inference_profiles.CHAT, "text"
        state = runtime.probe()
        profile = self.local_profile(
            workflow=workflow, model_id=model, reasoning="disabled",
            decoder=decoder, runtime_state=state,
            output_allowance=output_allowance)
        if profile is None:
            raise models.SelfTestError(
                "this model/runtime/device combination has no qualified execution profile")
        inference = inference_profiles.request(
            profile, reasoning="disabled", decoder=decoder,
            output_allowance=output_allowance,
            decoder_schema_sha256=(inference_profiles.schema_sha256(response_format)
                                   if response_format is not None else None))
        collected, done = [], None
        for kind, payload in runtime.stream_chat(
                messages, profile=profile, inference=inference,
                response_format=response_format,
                should_cancel=self.stopping.is_set, **options):
            if kind == "delta":
                collected.append(payload)
            elif kind == "cancelled":
                raise models.SelfTestError("the self-test was stopped")
            elif kind == "done":
                done = payload
        if not done or done.get("done_reason") != "stop":
            raise models.SelfTestError("the model's self-test reply was incomplete")
        return "".join(collected)

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
               skill_id: str | None = None, output_format: str | None = None,
               doc_workflow: str | None = None, reuse_source_ids=None) -> str:
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
        # The document choices are made against this request and stored with
        # it, so a reopened conversation reports the file and workflow that
        # actually ran rather than whatever the composer shows now.
        if output_format is not None and output_format not in docflow.OUTPUT_FORMATS:
            raise RequestError("that output format does not exist", 400)
        if doc_workflow is not None and doc_workflow not in docflow.DOC_WORKFLOWS:
            raise RequestError("that document workflow does not exist", 400)
        if output_format == docflow.FORMAT_PDF and not pdfgen.available():
            raise RequestError(pdfgen.probe()["detail"], 409)
        scope = ("documents.generate" if skill_id in docflow.DOCUMENT_SKILLS
                 else "chat")
        if skill_id != docflow.SEARCH_SKILL:
            self.model_for(scope, new_work=True)
        reuse_source_ids = [] if reuse_source_ids is None else reuse_source_ids
        if (not isinstance(reuse_source_ids, list) or len(reuse_source_ids) > docflow.MAX_SOURCES
                or any(not isinstance(i, str) or len(i) != 36 for i in reuse_source_ids)
                or len(set(reuse_source_ids)) != len(reuse_source_ids)):
            raise RequestError("invalid earlier source selection")
        for source_id in reuse_source_ids:
            self._reused_source(chat_id, source_id)
        if reuse_source_ids and len(reuse_source_ids) + len(db.list_attachments(
                self.conn, chat_id=draft_id or chat_id)) > docflow.MAX_SOURCES:
            raise RequestError(f"Select at most {docflow.MAX_SOURCES} sources per request")
        job_id = db.create_job(self.conn, workspace_id=self.workspace_id,
                               chat_id=chat_id, request=text, skill_id=skill_id,
                               output_format=output_format,
                               doc_workflow=doc_workflow, reuse_source_ids=reuse_source_ids)
        message_id = db.add_message(self.conn, chat_id, "user", text, job_id=job_id)
        # The selection travels with the request it was made for. The local
        # run reads only files bound to this exact message.
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

            # AF-006. The route is decided before the attempt is created, so
            # the reason is part of the canonical record from the first write
            # rather than being back-filled once something has already run.
            uses_model = skill_id != docflow.SEARCH_SKILL
            scope = "documents.generate" if skill_id in docflow.DOCUMENT_SKILLS else "chat"
            model_id = self.model_for(scope) if uses_model else None
            reasoning = db.get_reasoning(self.conn, model_id) if uses_model else False
            reasoning_mode = "enabled" if reasoning else "disabled"
            workflow_mode = (inference_profiles.DOCUMENTS
                             if skill_id in docflow.DOCUMENT_SKILLS
                             else inference_profiles.CHAT)
            decoder_mode = ("json_schema" if skill_id in docflow.DOCUMENT_SKILLS
                            else "text")
            # Decided BEFORE routing. A request carrying files is answered on
            # this computer: the worker contract has no field for an
            # attachment, so dispatching one would produce an answer from a
            # model that never received the file while the reply said it was
            # read. Asked here rather than after the route so the worker is
            # not preflighted, dispatched to, or fallen back from.
            _message_id, request_files = self._request_sources(chat_id, job_id)
            request_text = self.conn.execute(
                "SELECT original_request FROM jobs WHERE job_id=?",
                (job_id,)).fetchone()["original_request"]
            if (skill_id not in docflow.DOCUMENT_SKILLS and not request_files
                    and docflow.requests_transcription(request_text)):
                raise docflow.WorkflowError("source_selection_required",
                    "Choose the earlier source with + → Reuse, or attach it again. No file was reread; earlier answer text is not the original source.")
            # Probed once and shared. Routing needs the model reference and the
            # Chat identity block needs the installed list, and both used to ask
            # separately — three extra loopback calls on every message for an
            # answer the turn already had.
            runtime_state = runtime.probe() if uses_model else None
            if skill_id in docflow.DOCUMENT_SKILLS:
                route = self._local_route(
                    dispatch.Route(
                        "local", "local coordinator: Documents runs on this computer"),
                    model_id, uses_model, runtime_state,
                    workflow=workflow_mode, reasoning=reasoning_mode,
                    decoder=decoder_mode, context_window=None,
                    output_allowance=None)
            elif request_files:
                route = self._local_route(
                    dispatch.Route(
                        "local", "local coordinator: this request has attached "
                        "files, which are read on this computer"),
                    model_id, uses_model, runtime_state,
                    workflow=workflow_mode, reasoning=reasoning_mode,
                    decoder=decoder_mode, context_window=None,
                    output_allowance=None)
            else:
                route = self.choose_route(model_id=model_id,
                                          runtime_state=runtime_state,
                                          workflow=workflow_mode,
                                          reasoning=reasoning_mode,
                                          decoder=decoder_mode)
            profile = (v1.ExecutionProfile.model_validate(route.profile)
                       if route.profile else None)
            inference = None
            history = self.chat_messages(chat_id)
            # Context selection consumes the chosen qualified profile. A
            # remote worker with a smaller measured window therefore receives
            # a different explicit pre-execution selection, never a hidden
            # runtime truncation.
            window = (profile.qualified_context_tokens if profile
                      else runtime.NUM_CTX)
            allowance = (profile.default_output_tokens if profile
                         else runtime.NUM_PREDICT)
            messages, selection = context.select(
                history, window=window, output_allowance=allowance)
            attempt_id = db.create_attempt(
                self.conn, job_id=job_id,
                node_id=route.node_id or self.node_id,
                route_reason=route.reason,
                model=route.model,
            )
            if route.remote:
                db.set_attempt_relationship(self.conn, attempt_id,
                                            route.relationship_id)
            if uses_model:
                db.set_attempt_reasoning(self.conn, attempt_id, model_id, reasoning)
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
            if uses_model and (route.model is None or profile is None):
                db.set_attempt_metrics(self.conn, attempt_id, {
                    "requested_profile_id": (route.profile or {}).get("profile_id"),
                    "actual_profile_id": None,
                    "route": "remote" if route.remote else "local",
                    "refusal_reason": "no compatible qualified execution profile"})
                self._stop(job_id, attempt_id, "failed", "running", {
                    "code": "unavailable",
                    "message": (f"the selected model {model_id} has no compatible "
                                "qualified execution profile at this target")[:256],
                    "retryable": True})
                return
            if route.remote and skill_id is None:
                # Ordinary chat goes to the paired worker. Document and Code
                # skills stay local: their workflows are C08/C09 and the worker
                # advertises neither capability, so dispatching them would be a
                # promise this build cannot keep.
                inference = inference_profiles.request(
                    profile, reasoning=reasoning_mode, decoder="text",
                    output_allowance=selection.output_allowance,
                    context_window=selection.context_window)
                logical_messages = [identity.system_message(
                    engine=model_id, models=None,
                    location="the paired worker"), *messages]
                db.set_attempt_inference(
                    self.conn, attempt_id, inference.model_dump())
                handled, attempt_id, profile, inference = self._run_remote(
                    job_id, chat_id, attempt_id, route, text=request_text,
                    messages=logical_messages, inference=inference)
                if handled:
                    return
                # Fell back: continue below on this computer, with the new
                # attempt the fallback opened. The context selection and the
                # reasoning choice are re-recorded against it, so the local
                # attempt states what it actually ran with rather than
                # inheriting the remote attempt's record by implication.
                db.set_attempt_reasoning(self.conn, attempt_id, model_id, reasoning)
                db.set_attempt_selection(self.conn, attempt_id,
                                         selection.as_dict())

            if skill_id in docflow.DOCUMENT_SKILLS:
                # A document skill replaces the ordinary chat turn: it reads
                # this request's attachments, then answers or writes from them.
                messages, prepared, extra = self._document_stage(
                    job_id, chat_id, skill_id, messages,
                    ocr_model=self.enabled_model_for("documents.ocr"),
                    profile=profile)
                if messages is None:
                    # The skill produced its own answer without the model.
                    if extra.get("conversion"):
                        extra["answer"] = self._convert_previous(
                            job_id, chat_id, attempt_id, extra["conversion"])
                    self._finish_document(job_id, chat_id, attempt_id, extra,
                                          reasoning)
                    return
            else:
                # Ordinary Chat reads the files sent with this one request.
                # Choosing a skill is no longer the price of asking about a
                # file, but the scope is unchanged: this request's attachments
                # and nothing else on the computer.
                messages, extra = self._chat_attachments(
                    job_id, chat_id, messages, selection.included_ids,
                    profile=profile)
                prepared = extra.get("prepared")
                final_selection = extra.get("selection")
                if final_selection is not None:
                    db.set_attempt_selection(self.conn, attempt_id,
                                             final_selection.as_dict())
                # Who the person is talking to, and what is answering. Without
                # it the model introduces itself as whatever family its weights
                # came from, which is true of the weights and wrong about the
                # product. Built from this attempt's own model, so changing the
                # selection changes the answer with no edit here. Chat only:
                # the document routes carry their own strict-JSON instructions
                # and must not be given a second voice.
                messages = [self._identity_message(model_id, runtime_state),
                            *messages]

            collected, metrics = [], {}
            thinking_seen = False
            note = extra.get("attachment_note") if extra else ""
            if note:
                # Said before the reply and saved with it, so the record of
                # which files were read survives a reopen and an export.
                collected.append(note)
                db.append_output(self.conn, attempt_id, note)
                self._emit(job_id, attempt_id,
                           {"kind": "output.delta", "text": note[:2048]})
            # A document that must come back as one JSON object is decoded
            # against a schema the runtime enforces, and is given its own output
            # ceiling. Both travel in `extra`, so this stays one call site;
            # they are passed only when a route actually set them, so an
            # ordinary Chat turn is called exactly as it was before.
            response_format = (extra or {}).get("response_format")
            if skill_id in docflow.DOCUMENT_SKILLS:
                inference = inference_profiles.request(
                    profile, reasoning=reasoning_mode, decoder="json_schema",
                    output_allowance=(extra or {}).get(
                        "num_predict", profile.default_output_tokens),
                    context_window=profile.qualified_context_tokens,
                    decoder_schema_sha256=inference_profiles.schema_sha256(
                        response_format))
            elif inference is None:
                inference = inference_profiles.request(
                    profile, reasoning=reasoning_mode, decoder="text",
                    output_allowance=selection.output_allowance,
                    context_window=selection.context_window)
            db.set_attempt_inference(
                self.conn, attempt_id, inference.model_dump(),
                actual_profile=profile.model_dump())
            if extra is not None:
                extra["_execution_profile"] = profile
                extra["_inference_request"] = inference
            for kind, payload in runtime.stream_chat(
                    messages, profile=profile, inference=inference,
                    should_cancel=lambda: self.is_cancelled(job_id)
                    or self.stopping.is_set(), response_format=response_format):
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

            metrics["route"] = "local"
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
                        extra, model_id=model_id)
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
            if exc.code in ("source_selection_required", "source_unavailable"):
                db.add_message(self.conn, chat_id, "assistant", str(exc), job_id=job_id)
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

    def _reused_source(self, chat_id: str, source_id: str):
        record = db.attachment_record(self.conn, source_id, self.workspace_id)
        if (record is None or record["chat_id"] != chat_id or record["state"] != "sent"
                or not self.conn.execute(
                    "SELECT 1 FROM messages WHERE message_id=? AND chat_id=? AND role='user'",
                    (record["message_id"], chat_id)).fetchone()):
            raise RequestError("That earlier source is unavailable in this conversation. Choose a source with + or re-attach it.", 409)
        return {**{k: record[k] for k in record if k != "stored_name"}, "reused": True}

    def _request_sources(self, chat_id: str, job_id: str):
        """This request's uploads plus explicitly selected same-chat sources."""
        job = self.conn.execute(
            "SELECT reuse_sources_json FROM jobs WHERE job_id=? AND chat_id=? AND workspace_id=?",
            (job_id, chat_id, self.workspace_id)).fetchone()
        if job is None:
            raise docflow.WorkflowError("unknown_source_request", "This source request is unavailable.")
        message = self.conn.execute(
            "SELECT message_id FROM messages WHERE job_id=? AND chat_id=? AND role='user'"
            " ORDER BY created_at, rowid LIMIT 1", (job_id, chat_id)).fetchone()
        if message is None:
            return None, []
        sources = db.list_attachments(self.conn, message_id=message["message_id"])
        try:
            sources.extend(self._reused_source(chat_id, source_id)
                           for source_id in json.loads(job["reuse_sources_json"] or "[]"))
        except RequestError as exc:
            raise docflow.WorkflowError("source_unavailable", str(exc)) from exc
        return message["message_id"], sources

    def _chat_attachments(self, job_id, chat_id, messages, selected_ids,
                          *, profile: v1.ExecutionProfile):
        """Read the files sent with an ordinary Chat request, if any.

        The same extraction the document skills use, and the same scope: only
        this request's own attachments. A file that could not be read is
        reported in the reply rather than dropped, so nobody is left thinking
        the model saw something it never received.
        """
        message_id, attachments = self._request_sources(chat_id, job_id)
        if not attachments:
            return messages, {}
        cancel = lambda: self.is_cancelled(job_id) or self.stopping.is_set()
        prepared = docflow.prepare_sources(
            self, chat_id=chat_id, message_id=message_id, job_id=job_id,
            attachments=attachments, should_cancel=cancel,
            ocr_model=self.enabled_model_for("documents.ocr"))
        if any(a.get("reused") for a in attachments) and prepared.skipped:
            reasons = "; ".join(f"{s['filename']}: {s['reason']}" for s in prepared.skipped)
            raise docflow.WorkflowError("source_unavailable", reasons)
        if not prepared.usable:
            # An ordinary question is still worth answering. The reply says
            # which file could not be read and why, so nobody is left thinking
            # the model saw something it never received — but the question is
            # not thrown away because an attachment was unreadable.
            reasons = "; ".join(f"{s['filename']}: {s['reason']}"
                                for s in prepared.skipped) or "no readable text was found"
            return messages, {"prepared": prepared,
                              "attachment_note": f"_Nothing could be read — {reasons}._\n\n"}
        # The extracted text is fenced as data before the model sees it, with
        # the same rule the document skills state: an instruction inside a
        # document is content, never authority.
        required_tokens = (
            context.estimate_tokens(docflow.UNTRUSTED_NOTE)
            + context.estimate_tokens(messages[-1]["content"])
            + (2 * context.PER_MESSAGE_OVERHEAD))
        attachment_tokens = max(
            0, context.input_budget(profile.qualified_context_tokens,
                                    profile.default_output_tokens)
            - required_tokens)
        fenced, notes = docflow.chat_context(
            prepared, attachment_tokens * docflow.CHARS_PER_TOKEN_FLOOR)
        if not fenced:
            return messages, {
                "prepared": prepared,
                "attachment_note": docflow.attachment_note(prepared, notes)}
        # The untrusted-document rule is a system instruction, not a line the
        # document blocks could imitate: a file cannot claim to be the system.
        built = [{"role": "system", "content": docflow.UNTRUSTED_NOTE},
                 *messages[:-1],
                 {"role": "user",
                  "content": f"{fenced}\n\n{messages[-1]['content']}"}]
        candidates = [
            {"message_id": "attachment-system", "role": message["role"],
             "text": message["content"]}
            for message in built[:1]]
        candidates.extend(
            {"message_id": message_id, "role": message["role"],
             "text": message["content"]}
            for message_id, message in zip(selected_ids, built[1:]))
        bounded, final_selection = context.select(
            candidates, window=profile.qualified_context_tokens,
            output_allowance=profile.default_output_tokens)
        if not final_selection.newest_fits:
            raise runtime.RuntimeUnavailable(final_selection.note)
        final_selection.included_ids = [item for item in final_selection.included_ids
                                        if item != "attachment-system"]
        final_selection.omitted_ids = [item for item in final_selection.omitted_ids
                                       if item != "attachment-system"]
        final_selection.omitted_count = len(final_selection.omitted_ids)
        return bounded, {"prepared": prepared, "chat_sources": True,
                       "selection": final_selection,
                       "attachment_note": docflow.attachment_note(prepared, notes)}

    @staticmethod
    def _document_source_budget(base_messages, output_allowance: int,
                                context_window: int = runtime.NUM_CTX) -> int:
        """Characters left for sources after the real fixed prompt is counted."""
        available = context.input_budget(context_window, output_allowance)
        fixed = context.estimate_messages(base_messages)
        if fixed >= available:
            raise docflow.WorkflowError(
                "context_too_large",
                "The request itself does not leave room for document context. "
                "Shorten it and try again.")
        return int((available - fixed) * context.CHARS_PER_TOKEN)

    def _fit_document_prompt(self, base_messages, output_allowance: int, build,
                             *, context_window: int = runtime.NUM_CTX):
        """Shrink source text until the complete built prompt fits."""
        budget = self._document_source_budget(
            base_messages, output_allowance, context_window)
        limit = context.input_budget(context_window, output_allowance)
        while True:
            messages = build(budget)
            used = context.estimate_messages(messages)
            if used <= limit:
                return messages
            budget -= int((used - limit) * context.CHARS_PER_TOKEN) + 1
            if budget < 0:
                raise docflow.WorkflowError(
                    "context_too_large",
                    "The document instructions do not fit this model's "
                    "qualified context window.")

    def _approval_prompt(self, question, report, supporting, passages, *,
                         context_window: int = runtime.NUM_CTX):
        """Build one approval prompt whose report and passages share one budget."""
        base = docflow.approval_note_messages(question, [], [])
        source_budget = min(
            docflow.MAX_CONTEXT_CHARS,
            self._document_source_budget(
                base, docflow.APPROVAL_NUM_PREDICT, context_window))

        # Keep room for both the primary report and its references. Retrieval is
        # ranked, so later passages are the first ones left out.
        passage_budget = source_budget // 2 if passages else 0
        selected_passages, passage_chars = [], 0
        for passage in passages:
            if passage_chars + len(passage.text) > passage_budget:
                continue
            selected_passages.append(passage)
            passage_chars += len(passage.text)

        report_budget = max(0, source_budget - passage_chars)
        input_limit = context.input_budget(
            context_window, docflow.APPROVAL_NUM_PREDICT)
        while True:
            pages, _trimmed = docflow.bounded_pages(report, report_budget)
            if not pages:
                raise docflow.WorkflowError(
                    "context_too_large",
                    "The approval-note request left no room for the inspection "
                    "report. Shorten the request or use fewer sources.")
            report_details, open_items = docflow.report_evidence(report, pages)
            conflicts = docflow.reference_conflicts(report_details, supporting)
            built = docflow.approval_note_messages(
                question, selected_passages, [(report, pages)], open_items, conflicts)
            used = context.estimate_messages(built)
            if used <= input_limit:
                return (built, selected_passages, pages, report_details,
                        open_items, conflicts)
            if selected_passages:
                passage_chars -= len(selected_passages.pop().text)
                continue
            excess_chars = int((used - input_limit) * context.CHARS_PER_TOKEN) + 1
            smaller = report_budget - excess_chars
            if smaller >= docflow.MIN_PAGE_FRAGMENT:
                report_budget = smaller
                continue
            raise docflow.WorkflowError(
                "context_too_large",
                "The approval-note instructions do not fit this model's "
                "qualified context window.")

    def _document_stage(self, job_id, chat_id, skill_id, messages, *, ocr_model,
                        profile: v1.ExecutionProfile | None = None):
        """Extract, then either build a prompt or answer without the model."""
        cancel = lambda: self.is_cancelled(job_id) or self.stopping.is_set()
        message_id, attachments = self._request_sources(chat_id, job_id)
        job = self.conn.execute(
            "SELECT original_request, output_format, doc_workflow FROM jobs"
            " WHERE job_id=?", (job_id,)).fetchone()
        request_text = job["original_request"]
        context_window = (profile.qualified_context_tokens
                          if profile else runtime.NUM_CTX)
        workflow = job["doc_workflow"] or (
            # A job written before the choice existed ran the fixed workflow,
            # so that is what it is reported as. Nothing is relabelled.
            docflow.WORKFLOW_APPROVAL_NOTE if skill_id == docflow.WRITE_SKILL
            else None)

        if skill_id == docflow.WRITE_SKILL and not attachments:
            # Write Document no longer requires a file. Either the person is
            # asking for the previous answer in a file, or for a new document
            # about whatever they typed.
            if docflow.looks_like_conversion(request_text, has_attachments=False):
                previous = db.latest_completed_answer(
                    self.conn, chat_id, before_job_id=job_id)
                if previous is None:
                    raise docflow.WorkflowError(
                        "no_previous_answer",
                        "There is no completed answer in this conversation to "
                        "save. Ask a question first, let the reply finish, then "
                        "ask for it as a file.")
                return None, None, {"conversion": previous,
                                    "workflow": docflow.WORKFLOW_CONVERSION}
            base = docflow.general_document_messages(request_text, [])
            history = self.chat_messages(chat_id)[:-1]
            built = self._fit_document_prompt(
                base, docflow.DOCUMENT_NUM_PREDICT,
                lambda budget: docflow.general_document_messages(
                    request_text, [], history, budget=budget),
                context_window=context_window)
            return built, None, {"workflow": docflow.WORKFLOW_GENERAL,
                                 "general": True, **docflow.GENERAL_CALL}

        prepared = docflow.prepare_sources(
            self, chat_id=chat_id, message_id=message_id, job_id=job_id,
            attachments=attachments, should_cancel=cancel, ocr_model=ocr_model)
        if not attachments:
            raise docflow.WorkflowError(
                "no_attachments",
                "Attach the files to read with the + button, then send the "
                "request again. This skill only reads files you send with it.")
        if not prepared.usable:
            reasons = "; ".join(f"{s['filename']}: {s['reason']}"
                                for s in prepared.skipped) or "no readable text was found"
            raise docflow.WorkflowError("unreadable", f"Nothing could be read — {reasons}.")

        question = request_text

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
            base, _notes, _scope = docflow.read_messages(question, [])
            output_allowance = (profile.default_output_tokens
                                if profile else runtime.NUM_PREDICT)
            budget = self._document_source_budget(
                base, output_allowance, context_window)
            while True:
                built, notes, citation_sources = docflow.read_messages(
                    question, prepared.sources, budget=budget)
                used = context.estimate_messages(built)
                limit = context.input_budget(context_window, output_allowance)
                if used <= limit:
                    break
                budget -= int((used - limit) * context.CHARS_PER_TOKEN) + 1
                if budget < 0:
                    raise docflow.WorkflowError(
                        "context_too_large",
                        "The document-reading instructions do not fit this "
                        "model's qualified context window.")
            return built, prepared, {"notes": notes, "prepared": prepared,
                                     "citation_sources": citation_sources,
                                     **docflow.READ_CALL}

        if workflow == docflow.WORKFLOW_GENERAL:
            # A general document written from the attached files. It makes no
            # page citations, so nothing is resolved against the sources.
            base = docflow.general_document_messages(question, [])
            history = self.chat_messages(chat_id)[:-1]
            built = self._fit_document_prompt(
                base, docflow.DOCUMENT_NUM_PREDICT,
                lambda budget: docflow.general_document_messages(
                    question, prepared.sources, history, budget=budget),
                context_window=context_window)
            return built, prepared, {"prepared": prepared, "general": True,
                                     "workflow": docflow.WORKFLOW_GENERAL,
                                     **docflow.GENERAL_CALL}

        # The fixed approval note: the report is the first attachment, the rest
        # are SOPs. Unchanged, and still what C08 is accepted against.
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
        (built, passages, pages, report_details,
         open_items, conflicts) = self._approval_prompt(
             question, report, supporting, passages,
             context_window=context_window)
        allowed_pages = {report["source_id"]: {p["number"] for p in pages}}
        for passage in passages:
            allowed_pages.setdefault(passage.source_id, set()).add(passage.page)
        citation_sources = [
            {**source, "pages": [page for page in source["pages"]
                                  if page["number"] in allowed_pages[source["source_id"]]]}
            for source in prepared.sources if source["source_id"] in allowed_pages]
        return built, prepared, {"passages": passages, "report": report,
                                 "prepared": prepared,
                                 "citation_sources": citation_sources,
                                 "report_details": report_details,
                                 "open_items": open_items,
                                 "reference_conflicts": conflicts,
                                 **docflow.APPROVAL_CALL}

    def _general_document(self, job_id, answer, extra, *, model_id):
        """A general document: parse, repairing the shape at most once."""
        return self._structured_reply(
            job_id, answer, extra, model_id=model_id,
            parse=docflow.parse_general_document,
            repair_messages=docflow.general_repair_messages,
            subject="document")

    def _approval_note(self, job_id, answer, extra, *, model_id):
        """The fixed approval note: the same contract, a stricter repair.

        The repair cannot smuggle grounding past the checks. Whatever comes
        back is handed to the same `parse` closure, so it meets
        `_strict_citations` and `retrieval.resolve` against the same selected
        sources and the same supplied pages: a citation the model changed or
        invented during the repair fails exactly as it would have the first
        time. The instruction forbids touching substance; validation is what
        enforces it.
        """
        sources = extra.get("citation_sources", [])
        note = self._structured_reply(
            job_id, answer, extra, model_id=model_id,
            parse=lambda reply: docflow.parse_approval_note(
                reply, sources, extra.get("reference_conflicts")),
            repair_messages=docflow.approval_repair_messages,
            subject="note")
        note["report_details"] = extra.get("report_details", [])
        note["open_items"] = extra.get("open_items", [])
        # Coordinator-owned, like the two above: the model was told about the
        # conflict, but whether it mentions one is not what decides whether the
        # artifact carries it.
        note["reference_conflicts"] = extra.get("reference_conflicts", [])
        return note

    def _structured_reply(self, job_id, answer, extra, *, model_id, parse,
                          repair_messages, subject):
        """Parse a structured reply, repairing the shape at most once.

        The schema is enforced on the decoder, so a malformed reply should be
        rare. When one arrives anyway it is nearly always a document that was
        written and then wrapped wrongly, and asking the same model to send the
        same content in the right shape recovers it without a second draft.

        Exactly one repair, and only for the codes that mean "wrongly shaped"
        rather than "nothing to shape" — `docflow.REPAIRABLE_CODES` says which,
        and why the others would have to invent content. A reply the repair
        cannot fix is reported, never retried again: a loop here would burn a
        person's machine on a model that cannot produce the format at all.

        Truncation never reaches this method. `_run` refuses any document reply
        whose runtime stop reason was not `stop`, before the parse, so half a
        JSON object is a failure rather than something to repair.
        """
        try:
            return parse(answer)
        except docflow.WorkflowError as exc:
            if (exc.code not in docflow.REPAIRABLE_CODES
                    or not extra.get("response_format")):
                raise
        if self.is_cancelled(job_id) or self.stopping.is_set():
            raise docflow.Cancelled()

        repaired, metrics = self._buffered_reply(
            job_id, repair_messages(answer),
            profile=extra["_execution_profile"],
            inference=extra["_inference_request"],
            response_format=extra.get("response_format"))
        if metrics.get("done_reason") != "stop":
            raise docflow.WorkflowError(
                "incomplete",
                f"The model stopped before it finished rewriting the {subject} "
                f"({metrics.get('done_reason') or 'no reason reported'}). "
                "Nothing was written.")
        # Parsed once more and not caught: a second malformed reply is the
        # answer, and it fails with its own reason rather than a third attempt.
        return parse(repaired)

    def _buffered_reply(self, job_id, messages, *, profile, inference,
                        response_format):
        """One model call whose output is collected, not streamed.

        Deliberately not the loop in `_run`: a repair reply is an internal
        format fix, so it is never appended to the saved output and never
        emitted to the page. The person sees the document or the failure.
        """
        collected, metrics = [], {}
        for kind, payload in runtime.stream_chat(
                messages, profile=profile, inference=inference,
                response_format=response_format,
                should_cancel=lambda: self.is_cancelled(job_id)
                or self.stopping.is_set()):
            if kind == "delta":
                collected.append(payload)
            elif kind == "cancelled":
                raise docflow.Cancelled()
            elif kind == "done":
                metrics = payload
        return "".join(collected), metrics

    def _document_answer(self, job_id, chat_id, attempt_id, skill_id, answer,
                         prepared, extra, *, model_id=None):
        """Turn the model's reply into the skill's real result."""
        if self.is_cancelled(job_id) or self.stopping.is_set():
            raise docflow.Cancelled()
        if skill_id == docflow.READ_SKILL:
            parsed = docflow.parse_read_answer(
                answer, extra.get("citation_sources", []))
            return docflow.read_answer(parsed, prepared, extra.get("notes", []))

        if extra.get("general"):
            document = self._general_document(job_id, answer, extra,
                                              model_id=model_id)
            if self.is_cancelled(job_id) or self.stopping.is_set():
                raise docflow.Cancelled()
            sources = prepared.sources if prepared else []
            artifact = self._write_artifact(
                job_id, chat_id, attempt_id, title=document["title"],
                blocks=docflow.general_blocks(document, sources),
                workflow=docflow.WORKFLOW_GENERAL)
            extra["_artifact"] = artifact
            return docflow.written_answer(document["title"], artifact, sources)

        note = self._approval_note(job_id, answer, extra, model_id=model_id)
        if self.is_cancelled(job_id) or self.stopping.is_set():
            raise docflow.Cancelled()

        artifact = self._write_artifact(
            job_id, chat_id, attempt_id,
            title=note["title"],
            blocks=docflow.note_blocks(note, prepared.sources,
                                       extra.get("passages", [])),
            workflow=docflow.WORKFLOW_APPROVAL_NOTE,
            citations=docflow.citation_list(note))
        extra["_artifact"] = artifact
        return docflow.artifact_answer(note, artifact, prepared,
                                       extra.get("passages", []))

    def job_output_format(self, job_id: str) -> str:
        """The file this request asked for. A job written before the choice
        existed reports the docx default, which is what it actually produced."""
        row = self.conn.execute(
            "SELECT output_format FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        chosen = (row["output_format"] if row else None) or docflow.DEFAULT_OUTPUT_FORMAT
        return chosen if chosen in docflow.OUTPUT_FORMATS else docflow.DEFAULT_OUTPUT_FORMAT

    def _write_artifact(self, job_id, chat_id, attempt_id, *, title, blocks,
                        workflow, citations=None):
        """Write, validate and record one artifact in the requested format.

        One path for every document this build produces, so a `.pdf` is
        written, reopened and recorded with exactly the discipline the `.docx`
        already had: atomic write, structure check on the real file, and the
        file removed rather than left behind if anything after it fails.
        """
        fmt = self.job_output_format(job_id)
        writer = pdfgen if fmt == docflow.FORMAT_PDF else docgen
        root = db.artifacts_root(self.state_path)
        stored = f"{db.new_id()}.{fmt}"
        try:
            if fmt == docflow.FORMAT_PDF:
                written = pdfgen.write_pdf(root / stored, title=title, blocks=blocks)
            else:
                written = docgen.write_docx(root / stored, title=title, blocks=blocks)
        except (docgen.ArtifactError, pdfgen.ArtifactError) as exc:
            raise docflow.WorkflowError(exc.code, str(exc)) from exc
        validation = writer.validate(root / stored)
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
                job_id=job_id, attempt_id=attempt_id, workflow=workflow,
                filename=writer.safe_filename(title), stored_name=stored,
                media_type=written["media_type"], byte_size=written["byte_size"],
                sha256=written["sha256"], validation=validation,
                citations=citations or [])
        except Exception:
            (root / stored).unlink(missing_ok=True)
            raise
        if self.is_cancelled(job_id) or self.stopping.is_set():
            db.delete_artifact(self.conn, root, artifact["artifact_id"],
                               self.workspace_id)
            raise docflow.Cancelled()
        return artifact

    def _convert_previous(self, job_id, chat_id, attempt_id, previous: dict) -> str:
        """Put an answer that already exists into a file with the same wording.

        The model is not called. That is the whole point of this path: an
        answer sent back through a model comes out rewritten, and the person
        asked to keep the one they read.
        """
        if self.is_cancelled(job_id) or self.stopping.is_set():
            raise docflow.Cancelled()
        text = previous["text"]
        title = docflow.conversion_title(text)
        artifact = self._write_artifact(
            job_id, chat_id, attempt_id, title=title,
            blocks=docflow.conversion_blocks(text),
            workflow=docflow.WORKFLOW_CONVERSION)
        return docflow.conversion_answer(artifact, previous)

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
        store = pairing.credential_store()
        state = {
            "paired": relationship is not None,
            # Deprecated, and kept only so an older interface build keeps
            # working. It is NOT a macOS-specific flag any more: it is derived
            # from the same `store` read on the line below, so the two can never
            # disagree, and on Windows or Linux it means "this computer's own
            # protected store is usable". New callers read `credential_store`,
            # which also says which store and why not — a Windows computer must
            # never be told it is missing a macOS framework. Remove this field
            # once no shipped interface reads it.
            "keychain_available": store["available"],
            "credential_store": store,
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
        except dispatch.IncompatibleContract:
            raise
        except (dispatch.DispatchUnavailable, pairing.PairingError):
            return None

    def choose_route(self, required: list[str] | None = None,
                     model_id: str | None = None,
                     require_model: bool = True,
                     runtime_state: dict | None = None,
                     workflow: str = inference_profiles.CHAT,
                     reasoning: str = "disabled", decoder: str = "text",
                     context_window: int | None = None,
                     output_allowance: int | None = None) -> dispatch.Route:
        """Where one attempt should run, and the sentence explaining why.

        `required` names the capabilities the step actually needs, so Code asks
        for `code.generate` rather than borrowing Chat's answer. It defaults to
        Chat's, which keeps every C06 caller unchanged.

        `runtime_state` lets a caller that has already probed hand the result
        in rather than paying for a second one. Optional, so every existing
        caller is unchanged.
        """
        relationship = self.paired_worker()
        if relationship is None:
            route = dispatch.Route("local", "local coordinator: no paired worker")
            return self._local_route(route, model_id, require_model,
                                     runtime_state, workflow=workflow,
                                     reasoning=reasoning, decoder=decoder,
                                     context_window=context_window,
                                     output_allowance=output_allowance)
        try:
            node = self.preflight(relationship)
        except pairing.IdentityMismatch as exc:
            # Not a fallback. The attempt records the refusal and stops.
            return dispatch.Route("identity-mismatch", f"refused: {exc}")
        except dispatch.IncompatibleContract as exc:
            return self._local_route(
                dispatch.Route(
                    "local", f"local coordinator: incompatible worker contract ({exc})"),
                model_id, require_model, runtime_state, workflow=workflow,
                reasoning=reasoning, decoder=decoder,
                context_window=context_window, output_allowance=output_allowance)
        route = dispatch.choose_route(
            relationship=relationship, node=node,
            required=required or ["text.generate"], model_id=model_id,
            require_model=require_model, workflow=workflow,
            reasoning=reasoning, decoder=decoder,
            context_window=context_window,
            output_allowance=output_allowance)
        if (route.remote and route.model
                and not models.digest_eligible(
                    route.model["model_id"], route.model.get("manifest_sha256"))):
            route = dispatch.Route(
                "local", "local coordinator: the worker's model manifest does "
                         "not match Refinix's recorded catalogue")
        return self._local_route(
            route, model_id, require_model, runtime_state, workflow=workflow,
            reasoning=reasoning, decoder=decoder,
            context_window=context_window, output_allowance=output_allowance)

    def _local_route(self, route: dispatch.Route, model_id: str | None,
                     require_model: bool,
                     runtime_state: dict | None = None, *, workflow: str,
                     reasoning: str, decoder: str,
                     context_window: int | None,
                     output_allowance: int | None) -> dispatch.Route:
        if route.remote or not require_model:
            return route
        model = (self.local_model_ref(model_id, runtime_state)
                 if model_id else None)
        profile = (self.local_profile(
            workflow=workflow, model_id=model_id, reasoning=reasoning,
            decoder=decoder, runtime_state=runtime_state,
            context_window=context_window, output_allowance=output_allowance)
                   if model_id and model else None)
        if model is None:
            reason = route.reason + "; the selected model is not installed locally"
        elif profile is None:
            reason = route.reason + \
                "; this computer has no compatible qualified execution profile"
        else:
            reason = route.reason
        return dispatch.Route(
            "local", reason, node_id=self.node_id, model=model,
            profile=profile.model_dump() if profile else None)

    def pair(self, *, address: str, port: int, fingerprint: str,
             certificate_pem: str, pairing_code: str) -> dict:
        """Complete OD-06 against a worker whose fingerprint a human confirmed.

        Order matters and is not an implementation detail: pin, verify the
        presented certificate, redeem the code, store the credential in the OS
        credential store, and only then record the relationship. A row written
        before that store accepts it would describe a pairing with no usable
        credential.
        """
        fingerprint = pairing.normalise_fingerprint(fingerprint)
        store = pairing.credential_store()
        if not store["available"]:
            # The store's own words, so each platform names its own missing
            # prerequisite instead of every computer being sent to fix macOS.
            raise RequestError(
                f"Pairing needs a protected credential store. {store['detail']} "
                "Storing the credential in the database is not permitted.", 501)
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

    def _run_remote(self, job_id, chat_id, attempt_id, route, *, text: str,
                    messages: list[dict], inference: v1.InferenceRequest):
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
        remote_profile = v1.ExecutionProfile.model_validate(route.profile)

        def compatible_local():
            local_profile = self.local_profile(
                workflow=inference.workflow_mode,
                model_id=route.model["model_id"], reasoning=inference.reasoning,
                decoder=inference.decoder,
                context_window=inference.context_window_tokens,
                output_allowance=inference.output_allowance_tokens)
            if local_profile is None:
                return None, None
            local_request = inference_profiles.request(
                local_profile, reasoning=inference.reasoning,
                decoder=inference.decoder,
                context_window=inference.context_window_tokens,
                output_allowance=inference.output_allowance_tokens,
                decoder_schema_sha256=inference.decoder_schema_sha256)
            return local_profile, local_request

        local_profile, local_request = compatible_local()
        if relationship is None or relationship["state"] != "paired":
            # Revoked between choosing the route and dispatching. Fall back
            # rather than dereferencing a row that is no longer there.
            if local_profile is None:
                self._stop(job_id, attempt_id, "failed", "running", {
                    "code": "incompatible_profile",
                    "message": "the pairing was revoked and no local profile can preserve the requested semantics",
                    "retryable": True})
                return True, attempt_id, remote_profile, inference
            local = self._fallback(
                job_id, attempt_id, "the pairing was revoked before dispatch",
                local_profile, local_request)
            return False, local, local_profile, local_request
        try:
            envelope = dispatch.build_envelope(
                job=job, attempt_id=attempt_id, step_id=step, route=route,
                coordinator_node_id=self.node_id, request_text=text,
                messages=messages, inference=inference)
            client = self.worker_client(relationship)
            # One key per attempt, reused by any retry of it. A fresh key on a
            # retry would create a second remote attempt instead of replaying
            # the first, which is the opposite of what idempotency is for.
            client.submit(envelope, dispatch.idempotency_key_for(attempt_id))
        except dispatch.ProfileMismatch as exc:
            db.set_attempt_metrics(self.conn, attempt_id, {
                "requested_profile_id": inference.profile_id,
                "actual_profile_id": None, "route": "remote",
                "refusal_reason": str(exc)[:256]})
            self._stop(job_id, attempt_id, "failed", "running", {
                "code": "incompatible_profile", "message": str(exc)[:256],
                "retryable": True})
            return True, attempt_id, remote_profile, inference
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
            return True, attempt_id, remote_profile, inference
        except pairing.IdentityMismatch as exc:
            # No fallback. A changed worker identity is the event pinning
            # exists to surface, and answering locally would bury it.
            self._stop(job_id, attempt_id, "failed", "running", {
                "code": "permission_denied", "message": str(exc)[:256],
                "retryable": False})
            return True, attempt_id, remote_profile, inference
        except (dispatch.DispatchUnavailable, pairing.PairingError) as exc:
            # Truthful fallback: the worker could not take the work, so this
            # runs locally and the record says so.
            if local_profile is None:
                db.set_attempt_metrics(self.conn, attempt_id, {
                    "requested_profile_id": inference.profile_id,
                    "actual_profile_id": None, "route": "remote",
                    "refusal_reason": str(exc)[:256]})
                self._stop(job_id, attempt_id, "failed", "running", {
                    "code": "unavailable",
                    "message": ("the worker refused and no local profile can preserve "
                                f"the requested semantics: {exc}")[:256],
                    "retryable": True})
                return True, attempt_id, remote_profile, inference
            local = self._fallback(
                job_id, attempt_id, str(exc), local_profile, local_request)
            return False, local, local_profile, local_request

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
            observed = outcome.metrics or {}
            if (observed.get("requested_profile_id") != inference.profile_id
                    or observed.get("actual_profile_id") != remote_profile.profile_id
                    or observed.get("context_window") != inference.context_window_tokens
                    or observed.get("output_token_limit")
                    != inference.output_allowance_tokens
                    or observed.get("reasoning") != inference.reasoning
                    or observed.get("decoder") != inference.decoder):
                db.set_attempt_metrics(self.conn, attempt_id, {
                    **observed, "route": "remote",
                    "refusal_reason": "worker metrics did not match requested semantics"})
                self._stop(job_id, attempt_id, "failed", "running", {
                    "code": "incompatible_profile",
                    "message": "the worker did not prove the requested inference semantics",
                    "retryable": True})
                return True, attempt_id, remote_profile, inference
            observed["route"] = "remote"
            db.set_attempt_actual_profile(
                self.conn, attempt_id, remote_profile.model_dump())
            db.set_attempt_state(self.conn, attempt_id, "validating",
                                 runtime_ms=outcome.runtime_ms,
                                 queue_ms=outcome.queue_ms, metrics=observed)
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
            return True, attempt_id, remote_profile, inference
        if outcome.state == "cancelled":
            self._stop(job_id, attempt_id, "cancelled", "running", outcome.failure)
            return True, attempt_id, remote_profile, inference
        # interrupted or failed: the workspace and history stay usable, and the
        # partial text that did arrive is already persisted. This is worker or
        # cluster loss, not a reason to silently re-run the same request.
        self._stop(job_id, attempt_id, "failed" if outcome.state == "failed"
                   else "interrupted", "running", outcome.failure)
        return True, attempt_id, remote_profile, inference

    def _fallback(self, job_id, attempt_id, detail: str,
                  profile: v1.ExecutionProfile,
                  inference: v1.InferenceRequest) -> str:
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
                         "so this ran on this computer with identical requested semantics",
            model=profile.model.model_dump())
        db.set_attempt_inference(
            self.conn, local, inference.model_dump(), profile.model_dump())
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
        """Ordinary Chat history only.

        Code conversations are real conversations with their own jobs, but
        they belong to the Code surface. Listing them here put an internal
        "Code activity" row in the person's Chat sidebar, which is why the
        kind is now recorded rather than inferred from a title.
        """
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM chats WHERE kind=? ORDER BY pinned DESC,"
            " updated_at DESC LIMIT 100", (db.CHAT_KIND,))]

    def code_conversations(self):
        return db.code_conversations(self.conn, self.workspace_id)

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
                if row["role"] == "user" and row["job_id"]:
                    try:
                        _, row["attachments"] = self._request_sources(chat_id, row["job_id"])
                    except docflow.WorkflowError:
                        pass  # unavailable references cannot become readable attachments
                row["skill_id"] = skills.get(row["job_id"])
                row["artifacts"] = (artifacts.pop(row["job_id"], [])
                                    if row["role"] == "assistant" else [])
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
            requested = a.pop("requested_inference_json", None)
            actual = a.pop("actual_profile_json", None)
            a["requested_inference"] = json.loads(requested) if requested else None
            a["actual_profile"] = json.loads(actual) if actual else None
            metrics = a.get("metrics_json")
            a["metrics"] = json.loads(metrics) if metrics else None
        events = [dict(r) for r in self.conn.execute(
            "SELECT * FROM events WHERE job_id=? ORDER BY sequence", (job_id,))]
        for e in events:
            e["data"] = json.loads(e.pop("data_json"))
        return {"job": dict(job), "attempts": attempts, "events": events}

    def capabilities(self, runtime_state: dict | None = None,
                     inventory: list[dict] | None = None) -> list[dict]:
        """Observed capability state. `available` requires every observation.

        A document skill is available only when the parsers it needs exist on
        this computer. A missing parser, OCR engine or search index disables
        that one skill and nothing else — Chat and Code stay usable.
        """
        state = runtime_state if runtime_state is not None else runtime.probe()
        inventory = inventory if inventory is not None else self.model_inventory(state)
        usable = {(row["id"], scope) for row in inventory
                  for scope in row["eligible_scopes"]}
        chat_model = self.model_for("chat")
        code_model = self.model_for("code")
        document_model = self.model_for("documents.generate")
        ocr_model = self.model_for("documents.ocr")
        # The runtime was already observed above; reuse it rather than probing
        # once more per capability row.
        reading = documents.capability_summary(
            state, ocr_model=self.enabled_model_for("documents.ocr"))
        searchable = retrieval.fts_available(self.conn)
        recorded = db.selftests(self.conn)
        rows = []
        for entry in CAPABILITIES:
            row = dict(entry)
            if entry.get("implemented") is False:
                row["state"] = "unavailable"
                row["detail"] = entry["setup"]
            elif entry.get("kind") == "document":
                blocked = self._document_blockers(entry, reading, searchable,
                                                  state,
                                                  (document_model, "documents.generate")
                                                  in usable, document_model)
                row["formats"] = reading["supported"]
                row["unavailable_reasons"] = reading["unavailable"]
                row["state"] = "blocked" if blocked else "available"
                row["detail"] = blocked[0] if blocked else entry["detail_available"]
                if blocked:
                    row["setup"] = blocked[0]
            elif entry.get("kind") == "surface":
                # Two prerequisites, reported separately because they need
                # different fixes: this computer must be able to keep a folder
                # bounded at all, and the model must be ready. Collapsing them
                # would send a Windows user to the model picker for something
                # no model can solve.
                if not repo.containment_supported():
                    row["state"] = "unavailable"
                    row["detail"] = repo.PLATFORM_NOTE
                    row["setup"] = repo.PLATFORM_NOTE
                else:
                    row["state"] = ("available" if (code_model, "code") in usable
                                    else "blocked")
                    row["detail"] = (entry["detail_available"] if row["state"] == "available"
                                     else "The AI engine or the configured model is not "
                                          "ready, so Code cannot propose changes yet.")
            elif (chat_model, "chat") not in usable and not state.get("reachable"):
                row["state"] = "blocked"
                row["detail"] = ("The AI engine on this computer did not answer, "
                                 "so nothing can run yet.")
                row["setup"] = "Open Settings to see what this computer needs."
            elif (chat_model, "chat") not in usable:
                row["state"] = "blocked"
                row["detail"] = (f"The selected model {chat_model} is not available "
                                 "on the coordinator or paired worker.")
                row["setup"] = "Choose an installed model in the model selector."
            else:
                row["state"] = "available"
                row["detail"] = "Runs on this computer."
            # The self-test is reported beside the state, not folded into it.
            # "This can run" and "this was checked here" are different claims,
            # and `docs/PROJECT.md` 4.5 asks for the second to be visible.
            scope = CAPABILITY_SELFTEST_SCOPE.get(entry["id"])
            if scope:
                model = self.model_for(scope)
                digest = next((r["digests"]["local"] for r in inventory
                               if r["id"] == model), None)
                row["selftest"] = models.selftest_view(
                    recorded, model=model, digest=digest)[scope]
            rows.append(row)
        return rows

    @staticmethod
    def _document_blockers(entry, reading, searchable, state, model_installed,
                           model_id) -> list[str]:
        """Every reason this one skill cannot run, in the order to show them."""
        blocked = []
        if entry.get("needs_runtime") and not state.get("reachable"):
            blocked.append("The AI engine on this computer did not answer.")
        elif entry.get("needs_runtime") and not model_installed:
            blocked.append(f"The selected model {model_id} is not installed "
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
        inventory = self.model_inventory(runtime_state)
        chat_model = self.model_for("chat")
        chat_row = next((row for row in inventory if row["id"] == chat_model), None)
        local_profiles = self.local_profiles(runtime_state)
        chat_profile = next((p for p in local_profiles
                             if p.model.model_id == chat_model
                             and p.workflow_mode == inference_profiles.CHAT), None)
        return {
            "product": {"name": "Refinix", "surface": "local"},
            "desktop": dict(self.desktop),
            # What this computer is, observed rather than assumed. Nothing here
            # claims the profile is qualified: that is evidence held elsewhere.
            "device": {**device.describe(),
                       "code_containment": repo.containment_backend()},
            "node_id": self.node_id,
            "workspace_id": self.workspace_id,
            "contract_version": v1.CONTRACT_VERSION,
            "contract_status": "reviewed draft; not frozen, integration pending C05",
            "bind": f"{BIND_HOST}",
            "runtime": runtime_state,
            "model_configured": chat_model,
            "model_installed": bool(
                chat_row and chat_row["integrity"]["local"]["eligible"]),
            "model_available": bool(
                chat_row and "chat" in chat_row["eligible_scopes"]),
            "model_selections": {scope: self.model_for(scope)
                                 for scope in MODEL_DEFAULTS},
            "auto_model": {"enabled": False,
                           "detail": "Automatic model choice is planned after the internal hackathon."},
            "models": inventory,
            # Which workflows have a smallest representative check the person
            # can run. Sent so the interface offers only the checks that exist.
            "selftest_scopes": sorted(models.SELFTESTS),
            "capabilities": self.capabilities(runtime_state, inventory),
            "attachments": {
                "max_bytes": db.MAX_ATTACHMENT_BYTES,
                "max_files": db.MAX_ATTACHMENTS_PER_REQUEST,
                "accepted": sorted({k.lstrip(".") for k in db.ATTACHMENT_TYPES}),
                # Ordinary Chat reads the files sent with one request, and
                # only those. A request carrying files is answered on this
                # computer, because the worker contract carries no attachment.
                "processing": "Files sent with a request are read on this "
                              "computer for that request only. Earlier files "
                              "are not read again, and a request with files is "
                              "not sent to the paired worker.",
            },
            "documents": {
                **documents.capability_summary(
                    runtime_state,
                    ocr_model=self.enabled_model_for("documents.ocr")),
                "search": retrieval.METHOD if retrieval.fts_available(self.conn)
                          else None,
                "search_note": retrieval.METHOD_NOTE,
                # Which artifact formats this computer can actually write,
                # observed rather than listed. Word is portable and is the
                # required artifact; PDF writing still needs the macOS
                # frameworks, and a picker that offered it anyway would fail at
                # Send instead of saying so beforehand.
                "generates": ([docflow.FORMAT_DOCX] if docgen_available() else [])
                             + ([docflow.FORMAT_PDF] if pdfgen.available() else []),
                "generate_detail": {docflow.FORMAT_DOCX: docgen.probe()["detail"],
                                    docflow.FORMAT_PDF: pdfgen.probe()["detail"]},
                "workflow": docflow.WORKFLOW,
            },
            "execution_profiles": [profile.model_dump()
                                   for profile in local_profiles],
            "bounded": {
                "profile_id": chat_profile.profile_id if chat_profile else None,
                "num_ctx": (chat_profile.qualified_context_tokens
                            if chat_profile else None),
                "num_predict": (chat_profile.default_output_tokens
                                if chat_profile else None),
                "think": (chat_profile.default_reasoning == "enabled"
                          if chat_profile else None)},
            "context": {
                "window_tokens": (chat_profile.qualified_context_tokens
                                  if chat_profile else None),
                "reply_allowance_tokens": (chat_profile.default_output_tokens
                                           if chat_profile else None),
                "conversation_budget_tokens": context.input_budget(
                    chat_profile.qualified_context_tokens,
                    chat_profile.default_output_tokens) if chat_profile else None,
                "counting_method": context.Selection().counting_method,
                "policy": "Older complete exchanges are left out of a request "
                          "when it will not fit. Saved history is never changed.",
            },
            "jobs_by_state": counts,
            "repaired_on_start": len(self.repaired),
            # Observed, not declared. Code needs a containment guarantee this
            # computer may not give, and saying "available" anyway would be the
            # fabricated green state `docs/PROJECT.md` 19 forbids.
            "surfaces": {"chat": "available", "settings": "available",
                         "code": ("available" if repo.containment_supported()
                                  else "unavailable")},
            "surface_notes": {"code": None if repo.containment_supported()
                              else repo.PLATFORM_NOTE},
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
        """Take one selected file into request-scoped local storage.

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
            elif route == "/v1/model/impact":
                self._json({"impact": c.removal_impact(
                    self._text(_as_payload(query), "model", 200))})
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
                self._json(c.code.state(
                    (query.get("repo_id") or [None])[0],
                    self._text(_as_payload(query), "conversation_id", 36)))
            elif route == "/v1/code/files":
                self._code(lambda: c.code.files(
                    self._text(_as_payload(query), "repo_id", 36),
                    (query.get("approval_id") or [None])[0],
                    self._text(_as_payload(query), "conversation_id", 36)))
            elif route == "/v1/code/view":
                # Only a relative path arrives here, and only relative paths
                # go back. The browser never learns where the folder is.
                self._code(lambda: c.code.view(
                    self._text(_as_payload(query), "repo_id", 36),
                    self._text(_as_payload(query), "path", 1024),
                    (query.get("approval_id") or [None])[0],
                    self._text(_as_payload(query), "conversation_id", 36)))
            elif route == "/v1/code/conversations":
                self._json({"conversations": c.code.conversations()})
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
            elif route == "/v1/proof":
                # AF-014. One card per job, aggregating one Proof record per
                # material attempt. Every value carries the source it came
                # from; anything not observed is reported unavailable.
                card = proof.job_card(c, query["job_id"][0])
                if card is None:
                    raise RequestError("unknown job", 404)
                self._json(card)
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
                # Validated here as well as in `submit`, so a malformed value
                # is refused before any job row exists.
                output_format = payload.get("output_format") or None
                if output_format is not None and (
                        not isinstance(output_format, str)
                        or output_format not in docflow.OUTPUT_FORMATS):
                    raise RequestError("invalid output format")
                doc_workflow = payload.get("doc_workflow") or None
                if doc_workflow is not None and (
                        not isinstance(doc_workflow, str)
                        or doc_workflow not in docflow.DOC_WORKFLOWS):
                    raise RequestError("invalid document workflow")
                job_id = c.submit(chat_id, text, draft_id=draft_id,
                                  skill_id=skill_id, output_format=output_format,
                                  doc_workflow=doc_workflow,
                                  reuse_source_ids=payload.get("reuse_source_ids"))
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
                record = next((row for row in c.model_inventory()
                               if row["id"] == model), None)
                if record is None or not set(record["eligible_scopes"]) & {
                        "chat", "code", "documents.generate"}:
                    raise RequestError("that model is not available for generation", 404)
                enabled = payload.get("enabled")
                if not isinstance(enabled, bool):
                    raise RequestError("enabled must be true or false")
                db.set_reasoning(c.conn, model, enabled)
                self._json({"model": model, "reasoning": enabled})
            elif route == "/v1/model/select":
                self._json(c.select_model(
                    self._text(payload, "scope", 64),
                    self._text(payload, "model", 200)))
            elif route == "/v1/model/enabled":
                enabled = payload.get("enabled")
                if not isinstance(enabled, bool):
                    raise RequestError("enabled must be true or false")
                self._json(c.set_model_enabled(
                    self._text(payload, "model", 200), enabled))
            elif route == "/v1/model/selftest":
                # A self-test asks the local engine one bounded question. It
                # downloads nothing and installs nothing, and it is only ever
                # started by the person.
                self._json({"selftest": c.run_model_selftest(
                    self._text(payload, "scope", 64))})
            elif route == "/v1/code/mode":
                self._code(lambda: c.code.set_mode(
                    self._text(payload, "repo_id", 36),
                    self._text(payload, "mode", 20)))
            elif route == "/v1/code/forget":
                self._code(lambda: c.code.forget(
                    self._text(payload, "repo_id", 36),
                    payload.get("discard_undo", False)))
            elif route == "/v1/code/propose":
                self._code(lambda: c.code.propose(
                    self._text(payload, "repo_id", 36),
                    self._text(payload, "request", 4000),
                    payload.get("paths") or [],
                    payload.get("approval_id") or None,
                    self._text(payload, "conversation_id", 36),
                    payload.get("execution_target") or None))
            elif route == "/v1/code/undo":
                self._code(lambda: c.code.undo(
                    self._text(payload, "repo_id", 36),
                    self._text(payload, "proposal_id", 36),
                    self._text(payload, "conversation_id", 36)))
            elif route == "/v1/code/conversation":
                self._code(lambda: c.code.new_conversation(
                    payload.get("title") or "",
                    payload.get("repo_id") or None))
            elif route == "/v1/code/conversation/context":
                self._code(lambda: c.code.update_conversation(
                    self._text(payload, "conversation_id", 36),
                    payload.get("repo_id") or None,
                    payload.get("open_path") or None))
            elif route == "/v1/code/reject":
                self._code(lambda: c.code.reject(
                    self._text(payload, "repo_id", 36),
                    self._text(payload, "proposal_id", 36),
                    self._text(payload, "conversation_id", 36)))
            elif route == "/v1/code/validate":
                self._code(lambda: c.code.validate(
                    self._text(payload, "repo_id", 36),
                    self._text(payload, "proposal_id", 36),
                    self._text(payload, "conversation_id", 36)))
            elif route == "/v1/code/apply":
                self._code(lambda: c.code.apply(
                    self._text(payload, "repo_id", 36),
                    self._text(payload, "proposal_id", 36),
                    payload.get("approval_id") or None,
                    self._text(payload, "conversation_id", 36)))
            elif route == "/v1/code/decision":
                # Opaque id, yes/no and the owning Code conversation. No
                # target, digest, mode, path or replacement content is accepted.
                self._code(lambda: c.code.decide(
                    self._text(payload, "approval_id", 36),
                    payload.get("approved"),
                    payload.get("conversation_id") or None))
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
