"""Worker API — the `/v1` surface reserved by the shared contract.

**The job routes are fail-closed.** Two prerequisites do not exist yet:

* **OD-06 pairing** — there is no way to confirm that a relationship is genuine,
  so a claimed `relationship_id` under a shared bearer token proves nothing.
* **AF-005 durable receipt** — the contract requires a job to be persisted and
  enqueued *before* acknowledging. An in-memory dictionary is not that, and
  documenting the gap does not close it.

While either is missing, `POST /v1/jobs` and the other job routes return a typed
`unavailable`. They do not return `202`. The execution path below is implemented
and exercised by offline checks so that C05/C06 can enable it; it is not reachable
over HTTP until the prerequisites are real.

`/v1/health` and `/v1/capabilities` remain available for preflight. They are
read-only and disclose only what was actually observed.

The listener speaks plain HTTP. Until OD-06 supplies pinned TLS it must not cross
a trust boundary; exposure is a C05 Service and NetworkPolicy concern.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import platform
import threading
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timezone

from fastapi import FastAPI, Header, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import TypeAdapter

from backend.contracts import v1
from backend.worker import runtime

# ---------------------------------------------------------------- limits ---

MAX_ACTIVE = int(os.environ.get("AEGIS_MAX_ACTIVE", "2"))
MAX_RETAINED = int(os.environ.get("AEGIS_MAX_RETAINED", "32"))
STREAM_QUEUE = 256
RELAY_QUEUE = 64
EMIT_TIMEOUT = 2.0          # never block execution on a reader that stopped
PRODUCER_JOIN = 5.0         # bounded wait for the producer thread to notice stop

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

# Populated only by a completed OD-06 pairing, which does not exist. Empty is
# the honest state, and it is what keeps the job routes closed.
_relationships: dict[str, dict] = {}

# Set only by an AF-005 durable receipt backend, which does not exist.
_receipt_backend = None

_attempts: "OrderedDict[str, dict]" = OrderedDict()
_streams: dict[str, asyncio.Queue] = {}
_idempotency: "OrderedDict[str, dict]" = OrderedDict()
_lock = asyncio.Lock()


def missing_prerequisites() -> list[str]:
    """What must exist before this worker may accept dispatched work."""
    missing = []
    if not _relationships:
        missing.append("a confirmed pairing relationship (OD-06 is not implemented)")
    if _receipt_backend is None:
        missing.append("a durable dispatch receipt (AF-005 is not implemented)")
    return missing


# ----------------------------------------------------------------- errors ---

def _failure(code: str, message: str, retryable: bool, status: int) -> JSONResponse:
    """Metadata-only. Never a prompt, path, credential, traceback or raw input."""
    return JSONResponse(
        status_code=status,
        content={"code": code, "message": message[:256], "retryable": retryable},
        headers={VERSION_HEADER: v1.CONTRACT_VERSION})


def _guard(authorization: str | None, contract: str | None) -> JSONResponse | None:
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not supplied or not hmac.compare_digest(supplied, _CREDENTIAL):
        return _failure("permission_denied", "unknown or missing worker credential",
                        False, 401)
    if contract is None:
        return _failure("invalid_request", f"{VERSION_HEADER} is required", False, 400)
    if contract != v1.CONTRACT_VERSION:
        return _failure("incompatible_contract",
                        "contract version is not supported by this worker", False, 409)
    return None


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
    active = sum(1 for a in _attempts.values() if a["state"] in {"queued", "running"})
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


@app.post("/v1/pairing/confirm")
async def pairing_confirm():
    return _failure("permission_denied",
                    "pairing is a recorded decision, not an implementation", False, 501)


@app.delete("/v1/pairing/{relationship_id}")
async def pairing_revoke(relationship_id: str):
    return _failure("permission_denied",
                    "pairing revocation is not implemented", False, 501)


# ---------------------------------------------------------------- attempt ---

def _as_attempt(record: dict) -> v1.Attempt:
    """Build the contract record, which validates it. Extra fields are forbidden
    and a terminal state must carry a finish timestamp and exactly one reason."""
    env = record["envelope"]
    return v1.Attempt(
        contract_version=v1.CONTRACT_VERSION, workspace_id=env.workspace_id,
        job_id=env.job_id, step_id=env.step_id, attempt_id=env.attempt_id,
        retry_of=None, node_id=NODE_ID, model=record["model"],
        state=record["state"], route_reason=record["route_reason"],
        created_at=record["created_at"], started_at=record["started_at"],
        finished_at=record["finished_at"], queue_ms=record["queue_ms"],
        runtime_ms=record["runtime_ms"], error=record["error"], artifacts=[])


def _set_state(record: dict, state: str, error: dict | None = None) -> None:
    """Maintain the timestamps the Attempt validator requires."""
    stamp = _now()
    if state in {"running", "validating", "completed"} and record["started_at"] is None:
        record["started_at"] = stamp
    if state in v1.TERMINAL_ATTEMPT_STATES:
        record["finished_at"] = record["finished_at"] or stamp
    record["state"] = state
    record["error"] = error
    _as_attempt(record)          # raises before an invalid record is served


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
    if envelope.relationship_id not in _relationships:
        # Verification, not merely presence. Empty registry means always closed.
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
    denied = _guard(authorization, x_aegisforge_contract)
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
    if envelope.cancel_requested:
        return _failure("cancelled_by_user",
                        "this envelope was already cancelled before dispatch", False, 409)
    remaining = _seconds_until(envelope.deadline_at)
    if remaining <= 0:
        return _failure("deadline_exceeded", "this envelope expired before admission",
                        False, 409)

    body_digest = hashlib.sha256(raw).hexdigest()
    async with _lock:
        seen = _idempotency.get(scope)
        if seen is not None:
            if seen["body"] != body_digest:
                return _failure("idempotency_conflict",
                                "this key was used with a different request body",
                                False, 409)
            return JSONResponse(status_code=202, content=seen["attempt"],
                                headers={VERSION_HEADER: v1.CONTRACT_VERSION})
        if envelope.attempt_id in _attempts:
            return _failure("idempotency_conflict", "attempt already accepted",
                            False, 409)
        active = sum(1 for a in _attempts.values() if a["state"] in {"queued", "running"})
        if active >= MAX_ACTIVE:
            return _failure("unavailable", "worker is at capacity", True, 429)
        probe = runtime.probe()
        if not probe["reachable"]:
            return _failure("unavailable", "the local model runtime is not answering",
                            True, 503)

        record = register(envelope)
        payload = _as_attempt(record).model_dump()
        _idempotency[scope] = {"body": body_digest, "attempt": payload}
        while len(_idempotency) > MAX_RETAINED:
            _idempotency.popitem(last=False)
        _evict_terminal()

    asyncio.create_task(_execute(envelope.attempt_id, remaining))
    return JSONResponse(status_code=202, content=payload,
                        headers={VERSION_HEADER: v1.CONTRACT_VERSION})


def register(envelope: v1.JobEnvelope) -> dict:
    """Create the in-memory attempt record. Not a durable receipt."""
    record = {
        "envelope": envelope, "state": "queued",
        "route_reason": "worker: accepted for local execution",
        "created_at": _now(), "started_at": None, "finished_at": None,
        "queue_ms": None, "runtime_ms": None, "error": None, "model": None,
        "job_id": envelope.job_id, "workspace_id": envelope.workspace_id,
        "sequence": 0, "output": "", "cancelled": False, "metrics": {},
    }
    _as_attempt(record)
    _attempts[envelope.attempt_id] = record
    _streams[envelope.attempt_id] = asyncio.Queue(maxsize=STREAM_QUEUE)
    return record


def _evict_terminal() -> None:
    """Bound retention by dropping finished attempts only — never active work."""
    finished = [k for k, a in _attempts.items()
                if a["state"] not in {"queued", "running"}]
    while len(_attempts) > MAX_RETAINED and finished:
        key = finished.pop(0)
        _attempts.pop(key, None)
        _streams.pop(key, None)


# ------------------------------------------------------------- execution ---

async def _emit(attempt_id: str, payload: dict) -> None:
    record = _attempts.get(attempt_id)
    queue = _streams.get(attempt_id)
    if record is None or queue is None:
        return
    record["sequence"] += 1
    event = v1.Event(
        contract_version=v1.CONTRACT_VERSION, workspace_id=record["workspace_id"],
        job_id=record["job_id"], attempt_id=attempt_id, event_id=str(uuid.uuid4()),
        sequence=record["sequence"], producer_node_id=NODE_ID, producer="worker",
        occurred_at=_now(), data=payload)
    try:
        await asyncio.wait_for(queue.put(v1.sse_frame(event)), EMIT_TIMEOUT)
    except (asyncio.TimeoutError, asyncio.QueueFull):
        record["overflowed"] = True


async def _execute(attempt_id: str, envelope_budget: float) -> None:
    record = _attempts.get(attempt_id)
    if record is None:
        return
    env = record["envelope"]

    # ONE absolute deadline for the whole attempt: the earlier of the envelope's
    # remaining time and its requested runtime_seconds. Every wait derives from
    # it, so a slow stream cannot extend the budget one read at a time.
    budget = min(envelope_budget, float(env.limits.runtime_seconds))
    deadline = time.monotonic() + max(0.0, budget)
    output_cap = env.limits.output_bytes

    await _emit(attempt_id, {"kind": "attempt.state", "previous": None,
                             "current": "queued"})
    _set_state(record, "running")
    await _emit(attempt_id, {"kind": "attempt.state", "previous": "queued",
                             "current": "running"})

    loop = asyncio.get_running_loop()
    relay: asyncio.Queue = asyncio.Queue(maxsize=RELAY_QUEUE)
    stop = threading.Event()

    def hand_off(item) -> bool:
        """Bounded put. Returns False when the consumer is gone or out of time."""
        left = deadline - time.monotonic()
        if left <= 0 or stop.is_set():
            return False
        future = asyncio.run_coroutine_threadsafe(relay.put(item), loop)
        try:
            future.result(timeout=left)
            return True
        except Exception:                                      # noqa: BLE001
            future.cancel()
            return False

    def produce():
        try:
            for item in runtime.stream_chat(
                    [{"role": "user", "content": env.original_request}],
                    should_cancel=lambda: record["cancelled"] or stop.is_set()
                    or time.monotonic() >= deadline,
                    timeout=max(0.5, deadline - time.monotonic())):
                if not hand_off(item):
                    return
        except Exception as exc:                               # noqa: BLE001
            hand_off(("raised", exc))
        finally:
            hand_off(None)

    producer = loop.run_in_executor(None, produce)
    metrics, failure = {}, None
    started = time.monotonic()
    try:
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                raise asyncio.TimeoutError
            item = await asyncio.wait_for(relay.get(), timeout=left)
            if item is None:
                break
            kind, payload = item
            if kind == "delta":
                record["output"] += payload
                if len(record["output"].encode("utf-8")) > output_cap:
                    failure = ("output_bytes", None)
                    break
                for i in range(0, len(payload), 2048):
                    await _emit(attempt_id, {"kind": "output.delta",
                                             "text": payload[i:i + 2048]})
            elif kind == "cancelled":
                record["cancelled"] = True
                break
            elif kind == "done":
                metrics = payload
            elif kind == "raised":
                failure = ("raised", payload)
                break
    except asyncio.TimeoutError:
        failure = ("deadline", None)
    finally:
        stop.set()                       # tell the producer to leave
        try:
            await asyncio.wait_for(asyncio.shield(producer), timeout=PRODUCER_JOIN)
        except Exception:                                      # noqa: BLE001
            pass          # bounded: a stuck producer must not hold the attempt

    record["metrics"] = metrics
    record["runtime_ms"] = metrics.get("runtime_ms") or int(
        (time.monotonic() - started) * 1000)

    # Cancellation fences a later completion.
    if record["cancelled"]:
        await _terminal(attempt_id, "cancelled", {
            "code": "cancelled_by_user", "message": "cancelled by the coordinator",
            "retryable": True})
        return
    if failure is not None:
        kind, detail = failure
        reason = {
            "deadline": {"code": "deadline_exceeded",
                         "message": "the attempt deadline was reached; partial output retained",
                         "retryable": True},
            "output_bytes": {"code": "validation_failed",
                             "message": f"output exceeded the requested {output_cap}-byte limit",
                             "retryable": False},
        }.get(kind, {"code": "unavailable", "message": str(detail)[:256],
                     "retryable": True})
        await _terminal(attempt_id, "failed", reason)
        return

    problem = _validate_output(record, metrics)
    if problem is not None:
        await _terminal(attempt_id, "failed", problem)
        return

    _set_state(record, "validating")
    await _emit(attempt_id, {"kind": "attempt.state", "previous": "running",
                             "current": "validating"})
    await _terminal(attempt_id, "completed", None)


def _validate_output(record: dict, metrics: dict) -> dict | None:
    """Only a validated output after a confirmed normal stop may complete."""
    reason = metrics.get("done_reason")
    if reason != "stop":
        detail = {
            "context": "the context window was reached",
            "output": "the reply token limit was reached",
            "context_and_output": "both the context window and the reply limit were reached",
        }.get(metrics.get("limit_reason"),
              f"the runtime stopped with reason {reason or 'unreported'}")
        return {"code": "validation_failed",
                "message": f"incomplete reply: {detail}; partial output retained",
                "retryable": True}
    if "text.nonempty" in record["envelope"].output.validators \
            and not record["output"].strip():
        return {"code": "validation_failed",
                "message": "the runtime returned no visible output", "retryable": True}
    return None


async def _terminal(attempt_id: str, state: str, error: dict | None) -> None:
    record = _attempts.get(attempt_id)
    if record is None:
        return
    previous = record["state"]
    _set_state(record, state, error)
    await _emit(attempt_id, {"kind": "attempt.state", "previous": previous,
                             "current": state})
    queue = _streams.get(attempt_id)
    if queue is not None:
        try:
            await asyncio.wait_for(queue.put(None), EMIT_TIMEOUT)
        except (asyncio.TimeoutError, asyncio.QueueFull):
            pass
    async with _lock:
        _evict_terminal()


# ----------------------------------------------------------------- reads ---

def _scoped(attempt_id: str, job_id: str) -> dict | None:
    record = _attempts.get(attempt_id)
    # The attempt query stops a delayed poll or cancel targeting a newer retry.
    return record if record and record["job_id"] == job_id else None


@app.get("/v1/jobs/{job_id}")
async def poll(job_id: str, attempt_id: str = Query(...),
               authorization: str | None = Header(None),
               x_aegisforge_contract: str | None = Header(None)):
    denied = _guard(authorization, x_aegisforge_contract)
    if denied:
        return denied
    if (shut := _closed()) is not None:
        return shut
    record = _scoped(attempt_id, job_id)
    if record is None:
        return _failure("unavailable", "no such attempt for this job", False, 404)
    # Exactly the contract's Attempt: no metrics, no counts, no extra fields.
    return JSONResponse(_as_attempt(record).model_dump(),
                        headers={VERSION_HEADER: v1.CONTRACT_VERSION})


@app.get("/v1/jobs/{job_id}/events")
async def events(job_id: str, attempt_id: str = Query(...),
                 authorization: str | None = Header(None),
                 x_aegisforge_contract: str | None = Header(None)):
    denied = _guard(authorization, x_aegisforge_contract)
    if denied:
        return denied
    if (shut := _closed()) is not None:
        return shut
    record = _scoped(attempt_id, job_id)
    if record is None:
        return _failure("unavailable", "no such attempt for this job", False, 404)
    queue = _streams.get(attempt_id)
    if queue is None:
        # One consumptive stream, no retained cursor. Replay arrives with AF-005.
        return _failure("events_expired",
                        "this attempt's stream is finished; replay arrives with AF-005",
                        False, 410)

    async def stream():
        while True:
            frame = await queue.get()
            if frame is None:
                return
            yield frame

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store",
                                      VERSION_HEADER: v1.CONTRACT_VERSION})


@app.delete("/v1/jobs/{job_id}")
async def cancel(job_id: str, attempt_id: str = Query(...),
                 authorization: str | None = Header(None),
                 x_aegisforge_contract: str | None = Header(None)):
    denied = _guard(authorization, x_aegisforge_contract)
    if denied:
        return denied
    if (shut := _closed()) is not None:
        return shut
    record = _scoped(attempt_id, job_id)
    if record is None:
        return _failure("unavailable", "no such attempt for this job", False, 404)
    record["cancelled"] = True
    return Response(status_code=202, headers={VERSION_HEADER: v1.CONTRACT_VERSION})
