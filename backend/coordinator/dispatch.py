"""AF-006 routing: this workspace to a paired worker, and back honestly.

This module decides *whether* to dispatch, builds the envelope, talks to the
worker over the pinned channel, and turns the worker's event stream back into
coordinator events. It owns no canonical state: `server.py` has already written
the job and the attempt to SQLite before anything here runs, so a failure at any
point below leaves a complete local record rather than a hole.

Three rules are load-bearing.

**A route is a decision with a reason.** `choose_route` returns a `Route` whose
`reason` is written to the attempt and shown in the UI. There is no unexplained
dispatch and no unexplained fallback; "no paired worker", "worker unhealthy" and
"worker lacks text.generate" are different sentences because they need different
fixes.

**Identity mismatch is not unavailability.** Everything that could mean "try
locally instead" — unreachable, unhealthy, wrong contract, no capability —
produces a fallback route. A certificate that does not match the pin produces
`IdentityMismatch`, which propagates. `security.md` 4.1 requires the operator to
see that the worker identity changed rather than to get a quietly local answer.

**Every remote record is re-validated before it is believed.** The worker is a
separate trust domain; its stream is parsed through `v1.parse_message` and
checked for the attempt it claims to describe. A record that fails is dropped,
never persisted, and never re-emitted.
"""

from __future__ import annotations

import http.client
import json
import time
from dataclasses import dataclass, field

from backend.contracts import v1
from backend.coordinator import pairing

CONNECT_TIMEOUT = 5.0
REQUEST_TIMEOUT = 15.0
STREAM_TIMEOUT = 900.0
MAX_SSE_LINE = v1.MAX_EVENT_BYTES

# Bounded so a remote worker cannot make the coordinator spin forever on a
# stream that never terminates.
MAX_STREAM_EVENTS = v1.MAX_EVENT_ENTRIES

# A stream cut short is retried from the last sequence seen. Bounded, because
# an executor that died mid-attempt must eventually be reported as lost rather
# than reconnected to forever.
MAX_RECONNECTS = 4
RECONNECT_DELAY = 0.5

# What the executor can actually report as an ending. `interrupted` is NOT one
# of them: it is the coordinator's own conclusion when nothing was reported, so
# treating it as a terminal record would end the read before the first event.
REPORTED_TERMINAL = frozenset({"completed", "failed", "cancelled"})


class DispatchUnavailable(Exception):
    """A DEFINITE refusal: the worker never took the work.

    Local execution may proceed, because no remote attempt exists. Raised only
    where that is actually known — the connection failed before the request was
    written, or the worker answered with a typed refusal.
    """


class ReceiptUnknown(Exception):
    """The request was sent and no answer came back.

    The worker may have committed the receipt and be running the attempt right
    now. Falling back locally here would run the same request twice and return
    whichever finished first, so this is deliberately NOT a subclass of
    `DispatchUnavailable`: a caller that means to fall back has to say so about
    a case where it is safe.
    """


@dataclass(frozen=True)
class Route:
    """Where an attempt goes, and the sentence explaining why."""

    kind: str                       # "remote" or "local"
    reason: str
    node_id: str | None = None
    relationship_id: str | None = None
    model: dict | None = None

    @property
    def remote(self) -> bool:
        return self.kind == "remote"


@dataclass
class StreamOutcome:
    """What a remote attempt actually produced. Missing stays missing."""

    state: str = "interrupted"
    text: str = ""
    events: list = field(default_factory=list)
    queue_ms: int | None = None
    runtime_ms: int | None = None
    failure: dict | None = None
    last_sequence: int = 0


# ------------------------------------------------------------------ routing ---

def choose_route(*, relationship: dict | None, node: dict | None,
                 required: list[str], model_id: str | None = None,
                 require_model: bool = True) -> Route:
    """Decide between the paired worker and local execution.

    Every refusal names the missing precondition. A caller that cannot dispatch
    still gets a `Route`, so the attempt records why it ran locally instead of
    recording nothing.
    """
    if relationship is None:
        return Route("local", "local coordinator: no paired worker")
    if relationship.get("state") == "revoked":
        return Route("local", "local coordinator: the pairing was revoked")
    if node is None:
        return Route("local",
                     "local coordinator: the paired worker did not answer preflight")
    supported = node.get("supported_contract_versions") or []
    if v1.CONTRACT_VERSION not in supported:
        return Route("local",
                     f"local coordinator: the worker does not speak contract "
                     f"{v1.CONTRACT_VERSION}")
    health = node.get("health")
    if health != "healthy":
        return Route("local",
                     f"local coordinator: the paired worker reported {health or 'unknown'}")
    advertised = set(node.get("capabilities") or [])
    if missing := set(required) - advertised:
        return Route("local",
                     "local coordinator: the worker does not advertise "
                     + ", ".join(sorted(missing)))
    depth = node.get("queue_depth")
    queue_note = "" if depth is None else f", queue depth {depth}"
    if not require_model:
        return Route("remote",
                     f"paired worker {node.get('display_name') or node['node_id']}: "
                     f"healthy{queue_note}", node_id=node["node_id"],
                     relationship_id=relationship["relationship_id"])
    models = node.get("models") or []
    chosen = None
    for candidate in models:
        if model_id is None or candidate.get("model_id") == model_id:
            chosen = candidate
            break
    if chosen is None:
        return Route("local",
                     "local coordinator: the worker does not offer "
                     f"{model_id or 'any advertised model'}")
    return Route("remote",
                 f"paired worker {node.get('display_name') or node['node_id']}: "
                 f"healthy, {chosen['model_id']}{queue_note}",
                 node_id=node["node_id"],
                 relationship_id=relationship["relationship_id"], model=chosen)


def build_envelope(*, job: dict, attempt_id: str, step_id: str, route: Route,
                   coordinator_node_id: str, request_text: str,
                   system_instruction: str | None = None,
                   runtime_seconds: int = 300,
                   output_bytes: int = 1_048_576,
                   task_type: str = "chat",
                   required_capabilities: list[str] | None = None,
                   context: list | None = None,
                   attachments: list | None = None,
                   allowed_tools: list[str] | None = None,
                   output: v1.OutputContract | None = None,
                   workspace_bytes: int = 67_108_864) -> v1.JobEnvelope:
    """One validated envelope, with an explicit target and relationship.

    Built through the contract type, so an envelope that could not be executed —
    a missing relationship on a remote target, a deadline before creation — is
    rejected here rather than at the worker.

    Every parameter below `output_bytes` defaults to exactly the C06 chat
    envelope, so Chat is unchanged by C09 arriving. Documents and Code pass
    their own task type, capabilities, selected `ResourceRef` inputs, allowed
    tools and output contract instead of getting a second builder: one place
    still decides how an envelope is shaped, and one place still rejects an
    envelope that could not be executed.
    """
    created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    deadline = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                             time.gmtime(time.time() + runtime_seconds + 30))
    return v1.JobEnvelope(
        contract_version=v1.CONTRACT_VERSION,
        workspace_id=job["workspace_id"], workflow_id=job["workflow_id"],
        job_id=job["job_id"], step_id=step_id, attempt_id=attempt_id,
        chat_id=job["chat_id"], coordinator_node_id=coordinator_node_id,
        target_node_id=route.node_id or coordinator_node_id,
        relationship_id=route.relationship_id,
        original_request=request_text, system_instruction=system_instruction,
        task_type=task_type,
        model=route.model,
        required_capabilities=list(required_capabilities or ["text.generate"]),
        context=list(context or []), attachments=list(attachments or []),
        allowed_tools=list(allowed_tools or []),
        limits=v1.Limits(cpu_millis=2000, memory_bytes=2_147_483_648,
                         runtime_seconds=runtime_seconds, processes=8,
                         workspace_bytes=workspace_bytes, output_bytes=output_bytes,
                         tool_network="disabled"),
        output=output or v1.OutputContract(kind="text", validators=["text.nonempty"],
                                           schema_ref=None),
        approval_policy="coordinator-default-v1", created_at=created,
        deadline_at=deadline, cancel_requested=False)


# ---------------------------------------------------------------- transport ---

class WorkerClient:
    """HTTPS to one paired worker, over its pinned certificate only.

    Kept behind a small surface — `health`, `submit`, `stream`, `cancel` — so
    the offline checks can substitute a stateful fake without stubbing sockets,
    and so every caller goes through the same pin check.
    """

    def __init__(self, *, address: str, port: int, fingerprint: str,
                 certificate_pem: str, credential: str,
                 timeout: float = REQUEST_TIMEOUT):
        self.address = address
        self.port = int(port)
        self.fingerprint = fingerprint
        self.credential = credential
        self.timeout = timeout
        self._context = pairing.pinned_context(certificate_pem)

    def _connect(self, timeout: float | None = None) -> http.client.HTTPSConnection:
        connection = http.client.HTTPSConnection(
            self.address, self.port, timeout=timeout or self.timeout,
            context=self._context)
        try:
            connection.connect()
        except OSError as exc:
            # Before any request is written, so nothing can be running there.
            raise DispatchUnavailable(
                f"the paired worker at {self.address}:{self.port} did not answer") from exc
        # After the handshake, before a single byte of credential moves.
        pairing.verify_presented(connection.sock, self.fingerprint)
        return connection

    def _headers(self, extra: dict | None = None) -> dict:
        headers = {"Authorization": f"Bearer {self.credential}",
                   "X-AegisForge-Contract": v1.CONTRACT_VERSION}
        headers.update(extra or {})
        return headers

    def health(self) -> dict:
        connection = self._connect(CONNECT_TIMEOUT)
        try:
            connection.request("GET", "/v1/health", headers=self._headers())
            response = connection.getresponse()
            body = response.read(v1.MAX_REQUEST_BYTES)
            if response.status != 200:
                raise DispatchUnavailable(
                    f"the worker refused preflight with status {response.status}")
            return json.loads(body)
        except (OSError, ValueError) as exc:
            raise DispatchUnavailable("the worker's preflight reply was unreadable") from exc
        finally:
            connection.close()

    def submit(self, envelope: v1.JobEnvelope, idempotency_key: str) -> dict:
        """Dispatch one attempt, distinguishing refusal from ambiguity.

        The distinction is the whole point. A failed connection is a definite
        "it never arrived". Once the POST begins, the work may be running: the
        worker commits its receipt atomically, so a response that never comes
        back does not mean the work did not start.
        """
        body = envelope.model_dump_json().encode("utf-8")

        # The ONLY definite non-acceptance on this side. `_connect` raises
        # before a byte of the request is written, so a failure there proves
        # the worker never saw it.
        connection = self._connect()

        # Past this line the outcome is not knowable from an exception.
        # `HTTPConnection.request` performs the transmission itself, so it can
        # raise having already written some or all of the body — an earlier
        # version set its "sent" flag only after `request` RETURNED, which
        # classified exactly that case as definite and let the coordinator run
        # the same work locally. There is no flag now: everything after a
        # successful connect is ambiguous unless the worker answers.
        try:
            connection.request("POST", "/v1/jobs", body=body, headers=self._headers({
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
                "Content-Length": str(len(body))}))
            response = connection.getresponse()
            payload = response.read(v1.MAX_REQUEST_BYTES)
            status = response.status
        except (OSError, ValueError) as exc:
            raise ReceiptUnknown(
                "the worker did not answer after the request began; the "
                "attempt may be running there") from exc
        finally:
            connection.close()

        if status == 202:
            try:
                return json.loads(payload)
            except ValueError as exc:
                # Accepted, and we cannot read which attempt. Certainly not a
                # refusal: the work exists.
                raise ReceiptUnknown(
                    "the worker accepted the request but its reply was "
                    "unreadable") from exc
        if 400 <= status < 500:
            # An authenticated, typed refusal. The worker read the envelope and
            # declined it, which proves no receipt was committed.
            raise DispatchUnavailable(_refusal(status, payload))
        # A 5xx. Only the codes the worker emits before or instead of its
        # atomic commit prove non-acceptance; everything else is unknown.
        if _definite_refusal(payload):
            raise DispatchUnavailable(_refusal(status, payload))
        raise ReceiptUnknown(_refusal(status, payload))

    def upload_package(self, body: dict) -> dict:
        """Send one attempt's selected files before its envelope is dispatched.

        Ordering matters and is not an implementation detail: the worker
        refuses a code envelope whose package is absent, so uploading first is
        what makes an accepted receipt mean "this attempt can actually run".

        An identical retry is idempotent at the worker, so a `ReceiptUnknown`
        here is safe to retry — unlike `submit`, where a retry under a new
        attempt would be a second run.
        """
        payload = json.dumps(body).encode("utf-8")
        connection = self._connect()
        try:
            connection.request("POST", "/v1/packages", body=payload,
                               headers=self._headers({
                                   "Content-Type": "application/json",
                                   "Content-Length": str(len(payload))}))
            response = connection.getresponse()
            answer = response.read(v1.MAX_REQUEST_BYTES)
            status = response.status
        except (OSError, ValueError) as exc:
            raise ReceiptUnknown(
                "the worker did not answer while the package was being sent") from exc
        finally:
            connection.close()
        if status in (200, 201):
            try:
                return json.loads(answer)
            except ValueError as exc:
                raise ReceiptUnknown(
                    "the worker stored the package but its reply was unreadable"
                ) from exc
        # Nothing was queued by this route, so every refusal is definite: no
        # attempt exists yet and the caller may still choose another route.
        raise DispatchUnavailable(_refusal(status, answer))

    def stream(self, job_id: str, attempt_id: str, after: int = 0):
        """Yield raw SSE `data:` payloads. Validation is the caller's job.

        A generator rather than a list so a long generation reaches the UI as it
        happens; the connection is closed when the caller stops iterating.
        """
        connection = self._connect(STREAM_TIMEOUT)
        try:
            connection.request(
                "GET",
                f"/v1/jobs/{job_id}/events?attempt_id={attempt_id}&after={after}",
                headers=self._headers())
            response = connection.getresponse()
            if response.status != 200:
                raise DispatchUnavailable(
                    _refusal(response.status, response.read(v1.MAX_REQUEST_BYTES)))
            for line in response:
                if len(line) > MAX_SSE_LINE:
                    raise DispatchUnavailable("the worker sent an oversized event")
                if line.startswith(b"data: "):
                    yield line[6:].strip()
        except OSError as exc:
            raise DispatchUnavailable("the worker's event stream ended abruptly") from exc
        finally:
            connection.close()

    def cancel(self, job_id: str, attempt_id: str) -> bool:
        connection = self._connect(CONNECT_TIMEOUT)
        try:
            connection.request("DELETE",
                               f"/v1/jobs/{job_id}?attempt_id={attempt_id}",
                               headers=self._headers())
            response = connection.getresponse()
            response.read(4096)
            return response.status in (202, 204)
        except OSError as exc:
            raise DispatchUnavailable("the cancellation did not reach the worker") from exc
        finally:
            connection.close()


def _refusal(status: int, payload: bytes) -> str:
    try:
        record = json.loads(payload)
        return f"the worker refused with {record['code']}: {record['message']}"
    except (ValueError, KeyError, TypeError):
        return f"the worker refused with status {status}"


# Codes the worker emits ONLY when it knows nothing was committed.
#
# `redis_lost` earns its place here because `DispatchQueue.enqueue` now raises
# it exclusively where the dispatch command provably never ran — the
# reservation failed, or the receipt was read back still unreserved. Where the
# commit's outcome cannot be established it raises `internal_error` instead,
# which is deliberately absent from this set and therefore becomes
# `ReceiptUnknown` below. Adding a code here authorises local fallback for it,
# so nothing joins this set without that proof.
DEFINITE_REFUSALS = frozenset({
    "redis_lost", "invalid_request", "permission_denied", "incompatible_contract",
    "deadline_exceeded", "cancelled_by_user", "idempotency_conflict",
})


def _definite_refusal(payload: bytes) -> bool:
    try:
        return json.loads(payload).get("code") in DEFINITE_REFUSALS
    except (ValueError, AttributeError, TypeError):
        return False


def idempotency_key_for(attempt_id: str) -> str:
    """One key per attempt, reused by every retry of that attempt.

    A fresh key per request would defeat the mechanism exactly when it is
    needed: after an ambiguous send, a retry under a new key is a second
    attempt, not a replay of the first. The attempt ID is already a UUIDv4 —
    the format the worker requires — and is already unique per attempt, so it
    is the key rather than a second identifier that has to be stored alongside
    it and kept in step.
    """
    return attempt_id


# ------------------------------------------------------------------- stream ---

def consume(client: WorkerClient, envelope: v1.JobEnvelope, *, on_event=None,
            should_cancel=None, after: int = 0,
            reconnects: int = MAX_RECONNECTS) -> StreamOutcome:
    """Read the remote stream until a terminal state, validating every record.

    `on_event` receives each accepted `v1.Event` so the caller can persist and
    re-emit it through the coordinator's existing path — the events reaching the
    UI are coordinator events derived from validated worker records, never the
    worker's bytes forwarded blind.

    **A cut stream is retried, not accepted as an outcome.** The worker holds
    the connection open until the attempt finishes, so a stream that ends early
    is a transport failure, and treating it as "the attempt stopped" marked
    running work `interrupted`. Each reconnect resumes from the last sequence
    already seen, so no output is delivered twice; `seen` guards the overlap a
    replay can still produce.
    """
    outcome = StreamOutcome()
    # Start from "queued", not the dataclass default of "interrupted": the
    # default is the *conclusion* drawn when nothing was reported, and using it
    # as the starting value ended the read before the first event arrived.
    outcome.state = "queued"
    outcome.last_sequence = max(0, after)
    seen: set[int] = set()
    attempts_left = max(1, reconnects)

    while attempts_left:
        attempts_left -= 1
        try:
            for raw in client.stream(envelope.job_id, envelope.attempt_id,
                                     after=outcome.last_sequence):
                if should_cancel is not None and should_cancel():
                    outcome.state = "cancelled"
                    outcome.failure = {"code": "cancelled_by_user",
                                       "message": "cancelled from the local interface",
                                       "retryable": True}
                    return outcome
                event = _accept(raw, envelope)
                if event is None:
                    continue
                if event.sequence in seen:
                    # A reconnect can repeat what we already stored.
                    continue
                seen.add(event.sequence)
                outcome.last_sequence = max(outcome.last_sequence, event.sequence)
                outcome.events.append(event)
                if event.data.kind == "output.delta":
                    outcome.text += event.data.text
                elif event.data.kind == "attempt.state":
                    outcome.state = event.data.current
                if on_event is not None:
                    on_event(event)
                if len(seen) >= MAX_STREAM_EVENTS:
                    attempts_left = 0
                    break
        except pairing.IdentityMismatch:
            raise
        except DispatchUnavailable:
            if attempts_left and outcome.state not in REPORTED_TERMINAL:
                time.sleep(RECONNECT_DELAY)
                continue
            # Out of reconnects. Whatever arrived is kept; the state stays
            # whatever the last valid record said, so partial output is never
            # silently promoted to complete.
            if outcome.state in ("running", "queued", "validating"):
                outcome.state = "interrupted"
            outcome.failure = {"code": "worker_lost",
                               "message": "the worker stopped answering before the "
                                          "attempt finished; partial output retained",
                               "retryable": True}
            return outcome
        if outcome.state in REPORTED_TERMINAL:
            break
        if attempts_left and (should_cancel is None or not should_cancel()):
            # The stream closed without a terminal state: the worker's own
            # bound was reached, or the connection was dropped cleanly. Resume
            # rather than declaring an outcome the worker never reported.
            time.sleep(RECONNECT_DELAY)
            continue
        break

    if outcome.state == "completed":
        outcome.failure = None
    elif outcome.state == "cancelled":
        outcome.failure = {"code": "cancelled_by_user",
                           "message": "cancelled before completion", "retryable": True}
    elif outcome.state == "failed":
        outcome.failure = {"code": "validation_failed",
                           "message": "the worker reported a failed attempt",
                           "retryable": True}
    else:
        outcome.state = "interrupted"
        outcome.failure = {"code": "worker_lost",
                           "message": "the worker's stream ended without a terminal state",
                           "retryable": True}
    return outcome


def _accept(raw: bytes, envelope: v1.JobEnvelope) -> v1.Event | None:
    """Parse one record and check it describes the attempt we dispatched."""
    try:
        event = v1.parse_message(v1.Event, raw)
    except Exception:                                          # noqa: BLE001
        return None
    if event.producer != "worker":
        return None                # a worker cannot speak as the coordinator
    if (event.workspace_id != envelope.workspace_id
            or event.job_id != envelope.job_id
            or event.attempt_id != envelope.attempt_id):
        return None                # a record about someone else's attempt
    if event.producer_node_id != envelope.target_node_id:
        return None                # produced by a node we did not dispatch to
    return event
