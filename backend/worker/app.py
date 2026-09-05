"""Worker API — the `/v1` surface reserved by the shared contract.

**The job routes are open only when both C06 prerequisites are actually present**,
and the gate is evaluated per request rather than at import:

* **OD-06 pairing** (`backend.worker.pairing`) — at least one confirmed
  relationship, verified against a stored credential *hash*. An empty store
  keeps every job route closed, which is still the default state.
* **AF-005 durable receipt** (`backend.worker.dispatch`) — a reachable Redis
  Stream. The envelope is written to it *before* the 202, so an API process that
  dies immediately after answering leaves work an executor can still find.

If either is missing the routes return a typed `unavailable`, exactly as before.
Losing Redis at runtime closes them again with `redis_lost` rather than falling
back to an in-memory queue that would acknowledge work nobody will run.

Authority is split so a compromised half is bounded. `AEGIS_WORKER_TOKEN` is a
bootstrap credential for **preflight only** — `/v1/health` and `/v1/capabilities`,
which is what the kubelet probes use. Dispatched work requires a per-relationship
credential issued by pairing; the bootstrap token cannot submit, stream or cancel
a job, and a relationship credential authorises only its own relationship.

`/v1/health` and `/v1/capabilities` remain read-only and disclose only what was
actually observed.

The listener speaks plain HTTP inside the Pod. TLS termination with the pinned
OD-06 certificate is the Service/manifest boundary; the coordinator pins that
certificate as its sole trust anchor and aborts on a mismatch.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import platform
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import TypeAdapter

from backend.contracts import v1
from backend.worker import dispatch as dispatch_module
from backend.worker import pairing as pairing_module
from backend.worker import runtime
from backend.worker.redis_client import Redis

# ---------------------------------------------------------------- limits ---

MAX_ACTIVE = int(os.environ.get("AEGIS_MAX_ACTIVE", "2"))

# Event streaming is a bounded wait, never an open-ended one.
STREAM_POLL_SECONDS = 0.25    # how often the stored log is re-read
STREAM_IDLE_LIMIT = 90.0      # no new event: assume the executor is gone
STREAM_WALL_LIMIT = 1800.0    # hard ceiling, matching Limits.runtime_seconds

SUPPORTED_TASK_TYPES = {"chat"}
SUPPORTED_CAPABILITIES = {"text.generate"}
SUPPORTED_OUTPUT_KINDS = {"text"}
SUPPORTED_VALIDATORS = {"text.nonempty"}

VERSION_HEADER = "X-AegisForge-Contract"
_ID = TypeAdapter(v1.Id)

# --------------------------------------------------------------- identity ---

def _node_identity() -> str:
    """A distinct, persistent identity. A shared default would make two workers
    indistinguishable to a coordinator."""
    supplied = os.environ.get("AEGIS_NODE_ID", "").strip()
    if supplied:
        return _ID.validate_python(supplied)
    path = os.environ.get("AEGIS_NODE_ID_FILE", "/tmp/aegisforge-node-id")
    try:
        with open(path) as handle:
            return _ID.validate_python(handle.read().strip())
    except Exception:                                          # noqa: BLE001
        generated = str(uuid.uuid4())
        try:
            with open(path, "w") as handle:
                handle.write(generated)
        except OSError:
            pass          # an ephemeral identity is still distinct per process
        return generated


_CREDENTIAL = os.environ.get("AEGIS_WORKER_TOKEN", "")
if not _CREDENTIAL or len(_CREDENTIAL) < 32:
    # Refuse to START, not merely to answer.
    raise SystemExit(
        "AEGIS_WORKER_TOKEN must be set to at least 32 characters. "
        "The worker will not start without a credential.")

NODE_ID = _node_identity()
DISPLAY_NAME = os.environ.get("AEGIS_NODE_NAME", "aegisforge-worker")
APP_VERSION = os.environ.get("AEGIS_APP_VERSION", "0.1.0")

app = FastAPI(title="AegisForge worker", docs_url=None, redoc_url=None,
              openapi_url=None)

# OD-06 state. The default path is inside the Pod's own writable volume; an
# empty store is the honest starting state and keeps the job routes closed.
PAIRING_PATH = Path(os.environ.get("AEGIS_PAIRING_STATE",
                                   "/var/lib/aegisforge/pairing.json"))
_pairing = pairing_module.PairingStore(PAIRING_PATH)

# AF-005 durable receipt. Constructed only when an address was configured;
# reachability is re-checked per request, because a Redis that answered at
# startup and is gone now must close the routes rather than silently queue.
_receipt_backend: dispatch_module.DispatchQueue | None = None
if os.environ.get("AEGIS_REDIS_HOST"):
    _receipt_backend = dispatch_module.DispatchQueue(Redis(
        os.environ["AEGIS_REDIS_HOST"],
        int(os.environ.get("AEGIS_REDIS_PORT", "6379")),
        password=os.environ.get("AEGIS_REDIS_PASSWORD") or None))

# NO PROCESS-LOCAL ATTEMPT STATE. Everything the job routes need is in Redis,
# which is what lets a restarted API Pod answer for work it never admitted.


def missing_prerequisites() -> list[str]:
    """What must exist before this worker may accept dispatched work.

    Evaluated per request. Both halves are observations, not configuration: a
    relationship that was revoked and a Redis that stopped answering both close
    the routes again without a restart.
    """
    missing = []
    if not _pairing.relationships():
        missing.append("a confirmed pairing relationship (OD-06)")
    if _receipt_backend is None:
        missing.append("a durable dispatch receipt backend (AF-005)")
    elif not _receipt_backend.is_live():
        missing.append("a reachable dispatch queue (AF-005)")
    return missing


# ----------------------------------------------------------------- errors ---

def _failure(code: str, message: str, retryable: bool, status: int) -> JSONResponse:
    """Metadata-only. Never a prompt, path, credential, traceback or raw input."""
    return JSONResponse(
        status_code=status,
        content={"code": code, "message": message[:256], "retryable": retryable},
        headers={VERSION_HEADER: v1.CONTRACT_VERSION})


def _bearer(authorization: str | None) -> str:
    return (authorization or "").removeprefix("Bearer ").strip()


def _contract_guard(contract: str | None) -> JSONResponse | None:
    if contract is None:
        return _failure("invalid_request", f"{VERSION_HEADER} is required", False, 400)
    if contract != v1.CONTRACT_VERSION:
        return _failure("incompatible_contract",
                        "contract version is not supported by this worker", False, 409)
    return None


def _guard(authorization: str | None, contract: str | None) -> JSONResponse | None:
    """Preflight authority: the bootstrap token OR any relationship credential.

    `/v1/health` is what the kubelet probes call with `AEGIS_WORKER_TOKEN`, and
    what a paired coordinator calls with its own credential. Neither is
    sufficient for a job route — `_job_guard` below requires the relationship.
    """
    supplied = _bearer(authorization)
    if not supplied:
        return _failure("permission_denied", "unknown or missing worker credential",
                        False, 401)
    if not hmac.compare_digest(supplied, _CREDENTIAL) and _identify(supplied) is None:
        return _failure("permission_denied", "unknown or missing worker credential",
                        False, 401)
    return _contract_guard(contract)


def _identify(credential: str) -> dict | None:
    """Which relationship this credential belongs to, or None.

    Every candidate is compared even after a match, so the time taken does not
    reveal the position of a relationship in the store. At most
    `pairing.MAX_RELATIONSHIPS` comparisons, so this stays constant-ish and
    cheap; there is no per-request cache, because a revoked credential must stop
    working immediately rather than at the end of a cache window.
    """
    found = None
    for relationship_id in _pairing.relationships():
        try:
            record = _pairing.authorise(relationship_id, credential)
        except pairing_module.PairingError:
            continue
        found = found or record
    return found


def _job_guard(authorization: str | None, contract: str | None):
    """Job-route authority. Returns (relationship record, None) or (None, refusal).

    The bootstrap token is deliberately rejected here. It is mounted into the
    Pod for probes and is visible to anything that can read the Deployment's
    Secret reference; letting it dispatch work would make pairing decorative.
    """
    supplied = _bearer(authorization)
    denied = _failure("permission_denied",
                      "dispatched work requires a paired relationship credential",
                      False, 401)
    if not supplied:
        return None, denied
    record = _identify(supplied)
    if record is None:
        return None, denied
    if (refusal := _contract_guard(contract)) is not None:
        return None, refusal
    return record, None


def _closed() -> JSONResponse | None:
    """The fail-closed gate on every job route."""
    blockers = missing_prerequisites()
    if not blockers:
        return None
    return _failure(
        "unavailable",
        "this worker cannot accept dispatched work without " + " and ".join(blockers),
        True, 503)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _seconds_until(stamp: str) -> float:
    deadline = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (deadline - datetime.now(timezone.utc)).total_seconds()


# ------------------------------------------------------------------- node ---

def _node(observed: bool) -> dict:
    if not observed:
        return v1.Node(
            contract_version=v1.CONTRACT_VERSION, node_id=NODE_ID,
            display_name=DISPLAY_NAME, app_version=APP_VERSION,
            platform=f"{platform.system()} {platform.machine()}",
            supported_contract_versions=[v1.CONTRACT_VERSION],
            capabilities=[], models=[], health="unknown", observed_at=None,
            queue_depth=None, available_memory_bytes=None,
            loaded_model_id=None).model_dump()

    probe = runtime.probe()
    models, loaded = [], None
    digest = (probe.get("digests") or {}).get(runtime.MODEL, "")
    if probe["reachable"] and len(digest) == 64:
        models = [v1.ModelRef(model_id=runtime.MODEL, manifest_sha256=digest,
                              runtime="ollama",
                              runtime_version=probe["server_version"] or "unknown")]
        # Installed is not loaded: only an /api/ps residency observation sets this.
        if probe.get("loaded") == runtime.MODEL:
            loaded = runtime.MODEL
    # Capability is advertised only when this worker could actually accept work.
    eligible = bool(models) and not missing_prerequisites()
    # Queue depth is an observation of Redis, and stays `None` when it cannot be
    # observed. A restarted API reporting 0 while work runs would be a
    # measurement the coordinator routes on and that was never true.
    active = None
    if _receipt_backend is not None:
        depths = [_receipt_backend.active_attempts(relationship_id)
                  for relationship_id in _pairing.relationships()]
        active = sum(depths) if depths else 0
    return v1.Node(
        contract_version=v1.CONTRACT_VERSION, node_id=NODE_ID,
        display_name=DISPLAY_NAME, app_version=APP_VERSION,
        platform=f"{platform.system()} {platform.machine()}",
        supported_contract_versions=[v1.CONTRACT_VERSION],
        capabilities=["text.generate"] if eligible else [],
        models=models,
        health=("healthy" if probe["reachable"] and eligible
                else "degraded" if probe["reachable"] else "unavailable"),
        observed_at=_now(), queue_depth=active,
        available_memory_bytes=None, loaded_model_id=loaded).model_dump()


@app.get("/v1/health")
async def health(authorization: str | None = Header(None),
                 x_aegisforge_contract: str | None = Header(None)):
    denied = _guard(authorization, x_aegisforge_contract)
    return denied or JSONResponse(_node(observed=True),
                                  headers={VERSION_HEADER: v1.CONTRACT_VERSION})


@app.get("/v1/capabilities")
async def capabilities(authorization: str | None = Header(None),
                       x_aegisforge_contract: str | None = Header(None)):
    denied = _guard(authorization, x_aegisforge_contract)
    return denied or JSONResponse(_node(observed=True),
                                  headers={VERSION_HEADER: v1.CONTRACT_VERSION})


# ---------------------------------------------------------------- pairing ---

@app.post("/v1/pairing/confirm")
async def pairing_confirm(request: Request,
                          x_aegisforge_contract: str | None = Header(None)):
    """Redeem a one-time code for this relationship's credential.

    Deliberately **not** behind the bootstrap token. Its authority is the
    short-lived single-use code, which reached the coordinator out of band and
    is presented inside the already-pinned TLS channel — OD-06's whole point is
    that a human confirmed the certificate fingerprint before this call.

    The credential is returned once and never again. The worker keeps only a
    salted hash, so this response cannot be reconstructed from worker state.
    """
    if (refusal := _contract_guard(x_aegisforge_contract)) is not None:
        return refusal
    raw = await _read_bounded(request)
    if raw is None:
        return _failure("invalid_request", "request body is too large", False, 413)
    try:
        body = json.loads(raw or b"{}")
        relationship_id = _ID.validate_python(body["relationship_id"])
        workspace_id = _ID.validate_python(body["workspace_id"])
        code = body["pairing_code"]
    except Exception:                                          # noqa: BLE001
        return _failure("invalid_request",
                        "relationship_id, workspace_id and pairing_code are required",
                        False, 422)
    try:
        credential = _pairing.redeem(code, relationship_id=relationship_id,
                                     workspace_id=workspace_id)
    except pairing_module.PairingError as exc:
        status = 409 if exc.code == "idempotency_conflict" else 403
        return _failure(exc.code, exc.message, False, status)
    # The only place the plaintext exists outside the coordinator's Keychain.
    return JSONResponse(
        status_code=201,
        content={"relationship_id": relationship_id, "credential": credential,
                 "node_id": NODE_ID, "contract_version": v1.CONTRACT_VERSION},
        headers={VERSION_HEADER: v1.CONTRACT_VERSION, "Cache-Control": "no-store"})


@app.delete("/v1/pairing/{relationship_id}")
async def pairing_revoke(relationship_id: str,
                         authorization: str | None = Header(None),
                         x_aegisforge_contract: str | None = Header(None)):
    """Delete the stored hash and fence work in flight.

    A relationship may revoke only itself: presenting relationship A's
    credential to delete relationship B is refused as if B did not exist.
    """
    record, refusal = _job_guard(authorization, x_aegisforge_contract)
    if refusal is not None:
        return refusal
    if record["relationship_id"] != relationship_id:
        return _failure("permission_denied",
                        "a credential may revoke only its own relationship",
                        False, 403)
    _pairing.revoke(relationship_id)
    # Fence first-class: the relationship-scoped cancel key stops attempts
    # already running in the executor Pod. A loop over process memory would
    # have fenced nothing — the work is not in this process.
    if _receipt_backend is not None:
        _receipt_backend.revoke_relationship(relationship_id)
    return Response(status_code=204, headers={VERSION_HEADER: v1.CONTRACT_VERSION})


# ------------------------------------------------------------- admission ---

def _unsupported(envelope: v1.JobEnvelope) -> str | None:
    """Refuse what this worker cannot execute, rather than ignoring it."""
    if envelope.task_type not in SUPPORTED_TASK_TYPES:
        return f"this worker executes only {sorted(SUPPORTED_TASK_TYPES)}"
    if set(envelope.required_capabilities) - SUPPORTED_CAPABILITIES:
        return f"this worker provides only {sorted(SUPPORTED_CAPABILITIES)}"
    if envelope.output.kind not in SUPPORTED_OUTPUT_KINDS:
        return f"this worker produces only {sorted(SUPPORTED_OUTPUT_KINDS)} output"
    if set(envelope.output.validators) - SUPPORTED_VALIDATORS:
        return f"this worker runs only {sorted(SUPPORTED_VALIDATORS)}"
    if envelope.context or envelope.attachments:
        return "this worker cannot resolve context or attachment packages"
    if envelope.target_node_id != NODE_ID:
        return "this envelope targets a different node"
    if envelope.relationship_id is None:
        return "a dispatched envelope must carry a relationship"
    if not _pairing.is_active(envelope.relationship_id):
        # Verification, not merely presence. An empty or revoked store closes.
        return "this relationship has not been confirmed by pairing"
    return None


def idempotency_scope(key: str | None, envelope: v1.JobEnvelope) -> str:
    """A UUIDv4 key, scoped to the verified relationship, route and resource.

    The contract's `Id` is a UUIDv4; an arbitrary string is not an idempotency
    key. Scoping includes the relationship so a key cannot cross relationships.
    """
    validated = _ID.validate_python(key)          # raises on anything else
    return hashlib.sha256(
        f"POST:/v1/jobs:{envelope.relationship_id}:{envelope.workspace_id}"
        f":{envelope.job_id}:{validated}".encode()).hexdigest()


async def _read_bounded(request: Request) -> bytes | None:
    """Stop reading past the limit instead of buffering the whole body first."""
    total, chunks = 0, []
    async for chunk in request.stream():
        total += len(chunk)
        if total > v1.MAX_REQUEST_BYTES:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


@app.post("/v1/jobs")
async def submit(request: Request,
                 authorization: str | None = Header(None),
                 x_aegisforge_contract: str | None = Header(None),
                 idempotency_key: str | None = Header(None),
                 content_type: str | None = Header(None),
                 content_encoding: str | None = Header(None)):
    relationship, denied = _job_guard(authorization, x_aegisforge_contract)
    if denied:
        return denied
    # Fail closed before anything else. No 202 without a durable receipt and a
    # confirmed relationship; the body is not even read.
    if (shut := _closed()) is not None:
        return shut

    if content_encoding:
        return _failure("invalid_request", "compressed request bodies are not accepted",
                        False, 415)
    if not (content_type or "").startswith("application/json"):
        return _failure("invalid_request", "Content-Type must be application/json",
                        False, 415)

    raw = await _read_bounded(request)
    if raw is None:
        return _failure("invalid_request", "request body is too large", False, 413)
    try:
        envelope = v1.parse_message(v1.JobEnvelope, raw)
    except Exception:                                          # noqa: BLE001
        return _failure("invalid_request", "job envelope failed contract validation",
                        False, 422)
    try:
        scope = idempotency_scope(idempotency_key, envelope)
    except Exception:                                          # noqa: BLE001
        return _failure("invalid_request",
                        "Idempotency-Key must be a UUIDv4", False, 400)

    if (reason := _unsupported(envelope)) is not None:
        return _failure("invalid_request", reason, False, 422)
    if envelope.relationship_id != relationship["relationship_id"]:
        # The credential that authenticated is the one whose work this must be.
        # Without this, any paired coordinator could dispatch into another
        # relationship's queue and read its events.
        return _failure("permission_denied",
                        "this envelope belongs to a different relationship",
                        False, 403)
    if envelope.workspace_id != relationship["workspace_id"]:
        return _failure("permission_denied",
                        "this envelope belongs to a different workspace", False, 403)
    if envelope.cancel_requested:
        return _failure("cancelled_by_user",
                        "this envelope was already cancelled before dispatch", False, 409)
    remaining = _seconds_until(envelope.deadline_at)
    if remaining <= 0:
        return _failure("deadline_exceeded", "this envelope expired before admission",
                        False, 409)

    body_digest = hashlib.sha256(raw).hexdigest()
    relationship_id = relationship["relationship_id"]

    # Capacity comes from Redis, not from a counter this process keeps. A
    # restarted API had a queue depth of zero while work was running, and a
    # stale dictionary entry could hold a slot against a finished attempt for
    # the life of the process.
    #
    # There is deliberately NO "this attempt is already known" refusal here. A
    # client that retries after a lost response sends the same envelope under
    # the same key, and rejecting that would turn the retry idempotency exists
    # for into a 409. `enqueue` distinguishes the two cases — same key and same
    # body replays the original receipt, same key and a different body
    # conflicts — and a duplicate that reaches the stream anyway is suppressed
    # by the executor's lease and terminal marker.
    if _receipt_backend.active_attempts(relationship_id) >= MAX_ACTIVE:
        return _failure("unavailable", "worker is at capacity", True, 429)

    payload = _attempt_record(envelope, "queued").model_dump()

    # THE RECEIPT, committed atomically. Nothing below this line may return 202
    # unless the envelope is in the dispatch stream, and nothing may return an
    # error once it is: `enqueue` writes the entry and its acceptance together.
    try:
        stored = _receipt_backend.enqueue(
            envelope, scope=scope, body_digest=body_digest,
            idempotency_key=idempotency_key, epoch=_pairing.epoch(),
            attempt_payload=payload)
    except dispatch_module.DispatchError as exc:
        return _failure(exc.code, exc.message, exc.retryable, exc.status)

    return JSONResponse(status_code=202, content=stored,
                        headers={VERSION_HEADER: v1.CONTRACT_VERSION})


# ----------------------------------------------------------------- reads ---
#
# NOTHING HERE CONSULTS PROCESS MEMORY. Execution moved to the executor Pod at
# C06 and the receipt lives in Redis, so an API Pod that restarts mid-attempt
# must still answer for work it no longer remembers. Every route below resolves
# the attempt through `find_attempt`, which reads the dispatch stream the
# receipt was written to. A dictionary here would answer 404 for running work.


def _resolve(job_id: str, attempt_id: str, relationship: dict):
    """The envelope this worker admitted, or None if it never did.

    Also the authorization check: an envelope belongs to exactly one
    relationship, workspace and job, so a caller holding relationship A's
    credential cannot read or cancel B's attempt by guessing its ID.
    """
    if _receipt_backend is None:
        return None
    try:
        envelope = _receipt_backend.find_attempt(
            relationship["relationship_id"], attempt_id)
    except dispatch_module.DispatchError:
        return None
    if envelope is None or envelope.job_id != job_id:
        return None
    if (envelope.relationship_id != relationship["relationship_id"]
            or envelope.workspace_id != relationship["workspace_id"]):
        return None
    return envelope


def _attempt_record(envelope: v1.JobEnvelope, state: str) -> v1.Attempt:
    """Build the contract record from the envelope plus the observed state.

    Reconstructed rather than remembered: the envelope is durable and the state
    comes from the executor's event log, so the same answer survives a restart.
    """
    stamp = _now()
    started = stamp if state in {"running", "validating", "completed"} else None
    finished = stamp if state in v1.TERMINAL_ATTEMPT_STATES else None
    return v1.Attempt(
        contract_version=v1.CONTRACT_VERSION, workspace_id=envelope.workspace_id,
        job_id=envelope.job_id, step_id=envelope.step_id,
        attempt_id=envelope.attempt_id, retry_of=None, node_id=NODE_ID,
        model=None, state=state,
        route_reason="worker: enqueued for executor dispatch",
        created_at=envelope.created_at, started_at=started,
        finished_at=finished, queue_ms=None, runtime_ms=None,
        error=_stop_reason(state), artifacts=[])


def _observed_state(relationship_id: str, attempt_id: str) -> str:
    """The attempt's state, derived from the executor's own events.

    "queued" when the log is empty: an admitted attempt the executor has not
    picked up yet has genuinely not started, and inventing a terminal state
    would be a claim about work that has not happened.
    """
    if _receipt_backend is None:
        return "queued"
    try:
        events = _receipt_backend.read_events(relationship_id, attempt_id,
                                              admitted=True)
    except dispatch_module.DispatchError:
        return "queued"
    state = "queued"
    for event in events:
        if event.get("data", {}).get("kind") == "attempt.state":
            state = event["data"]["current"]
    return state


def _stop_reason(state: str) -> dict | None:
    """The Attempt validator requires exactly one typed reason on a stop.

    The executor reports the state change; the reason here is the generic one
    for that state, because the API did not observe the cause. It never claims
    `cancelled_by_user` for a failure — the contract forbids that pairing.
    """
    return {
        "cancelled": {"code": "cancelled_by_user",
                      "message": "cancelled before completion", "retryable": True},
        "failed": {"code": "internal_error",
                   "message": "the executor reported a failed attempt",
                   "retryable": True},
        "interrupted": {"code": "worker_lost",
                        "message": "the executor stopped without finishing",
                        "retryable": True},
    }.get(state)


@app.get("/v1/jobs/{job_id}")
async def poll(job_id: str, attempt_id: str = Query(...),
               authorization: str | None = Header(None),
               x_aegisforge_contract: str | None = Header(None)):
    relationship, denied = _job_guard(authorization, x_aegisforge_contract)
    if denied:
        return denied
    if (shut := _closed()) is not None:
        return shut
    envelope = _resolve(job_id, attempt_id, relationship)
    if envelope is None:
        return _failure("unavailable", "no such attempt for this job", False, 404)
    state = _observed_state(relationship["relationship_id"], attempt_id)
    # Exactly the contract's Attempt: no metrics, no counts, no extra fields.
    return JSONResponse(_attempt_record(envelope, state).model_dump(),
                        headers={VERSION_HEADER: v1.CONTRACT_VERSION})


@app.get("/v1/jobs/{job_id}/events")
async def events(job_id: str, attempt_id: str = Query(...), after: int = Query(0),
                 authorization: str | None = Header(None),
                 x_aegisforge_contract: str | None = Header(None)):
    """Stream this attempt's events until it reaches a terminal state.

    **This waits.** A single snapshot of the log was the earlier behaviour and
    it was wrong: immediately after submission the log is empty or holds only
    `queued`, so the coordinator saw a stream end with no terminal state and
    marked perfectly good work `interrupted`. The executor is a different Pod,
    so there is no in-process queue to attach to; the connection is held open
    and the log is re-read instead.

    Three bounds, because an unbounded wait is its own failure:

    * the attempt's own `deadline_at` — the work cannot outlive it;
    * `STREAM_IDLE_LIMIT` with no new event, which catches an executor that
      died between its last event and its terminal one;
    * the cancellation key, so a cancelled attempt stops streaming promptly
      rather than waiting out the deadline.

    `after` makes it resumable: a coordinator that reconnects passes the last
    sequence it persisted and receives only what it missed, so a reconnect
    cannot duplicate output.
    """
    relationship, denied = _job_guard(authorization, x_aegisforge_contract)
    if denied:
        return denied
    if (shut := _closed()) is not None:
        return shut
    envelope = _resolve(job_id, attempt_id, relationship)
    if envelope is None:
        # No receipt at all. Distinct from an admitted attempt with no events
        # yet, which is handled below by waiting rather than refusing.
        try:
            _receipt_backend.read_events(relationship["relationship_id"], attempt_id)
        except dispatch_module.DispatchError as exc:
            return _failure(exc.code, exc.message, exc.retryable, exc.status)
        return _failure("unavailable", "no such attempt for this job", False, 404)

    relationship_id = relationship["relationship_id"]
    budget = min(_seconds_until(envelope.deadline_at), STREAM_WALL_LIMIT)

    async def stream():
        cursor = max(0, after)
        deadline = time.monotonic() + max(0.0, budget)
        quiet_since = time.monotonic()
        while True:
            try:
                pending = _receipt_backend.read_events(
                    relationship_id, attempt_id, after_sequence=cursor,
                    admitted=True)
            except dispatch_module.DispatchError:
                return          # Redis went away; the coordinator sees the cut
            for payload in pending:
                try:
                    event = v1.Event.model_validate(payload)
                except Exception:                              # noqa: BLE001
                    continue    # never forward a record the contract rejects
                cursor = max(cursor, event.sequence)
                quiet_since = time.monotonic()
                yield v1.sse_frame(event)
            state = _observed_state(relationship_id, attempt_id)
            if state in v1.TERMINAL_ATTEMPT_STATES:
                return
            now = time.monotonic()
            if now >= deadline or now - quiet_since > STREAM_IDLE_LIMIT:
                return
            try:
                if _receipt_backend.cancelled(relationship_id, attempt_id):
                    # Keep reading briefly so the executor's own cancelled
                    # event is delivered rather than cut off mid-flight.
                    deadline = min(deadline, now + STREAM_POLL_SECONDS * 4)
            except dispatch_module.DispatchError:
                return
            await asyncio.sleep(STREAM_POLL_SECONDS)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store",
                                      VERSION_HEADER: v1.CONTRACT_VERSION})


@app.delete("/v1/jobs/{job_id}")
async def cancel(job_id: str, attempt_id: str = Query(...),
                 authorization: str | None = Header(None),
                 x_aegisforge_contract: str | None = Header(None)):
    """Record the cancellation where the executor will see it.

    Setting a flag in this process would cancel nothing: the work is running in
    another Pod, and after an API restart this process never admitted it at all.
    The Redis key is the cancellation boundary, and the executor polls it.
    """
    relationship, denied = _job_guard(authorization, x_aegisforge_contract)
    if denied:
        return denied
    if (shut := _closed()) is not None:
        return shut
    if _resolve(job_id, attempt_id, relationship) is None:
        return _failure("unavailable", "no such attempt for this job", False, 404)
    try:
        _receipt_backend.request_cancel(relationship["relationship_id"], attempt_id)
    except dispatch_module.DispatchError as exc:
        return _failure(exc.code, exc.message, exc.retryable, exc.status)
    return Response(status_code=202, headers={VERSION_HEADER: v1.CONTRACT_VERSION})
