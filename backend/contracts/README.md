# AF-001 contract draft — 1.0

Status: **in progress; local contract checks passed, not frozen**. The Python
records, protocol constants, synthetic examples, and runnable checks exist. Coordinator,
worker, UI, and manifest consumers do not exist yet. Passing the contract check
alone does not satisfy the AF-001 integration gate or the Day 1 spine.

This implements the shared boundary in
[architecture §6](../../docs/architecture.md#6-job-and-workflow-contracts).
[v1.py](v1.py) owns payload shapes and constants; this document owns their
transport and persistence semantics. All IDs are canonical lowercase UUIDv4
strings. Timestamps use `YYYY-MM-DDTHH:MM:SSZ`; durations use milliseconds.
Every top-level record requires `contract_version: "1.0"`. Unknown fields,
unsupported versions, and coercion such as `"60"` to an integer are rejected.

## One source for consumers

- Python coordinator and worker import records from `backend.contracts.v1`.
  Authenticate and limit the incoming body first, then call `parse_message`.
  FastAPI routes must use these records rather than redeclaring their fields.
- The schema export carries the same version, transport constants, Redis
  constants, and JSON Schemas. The coordinator will expose this bundle to the
  local UI; manifest work must take its ports and version from the bundle.
- JSON Schema describes field shapes. Cross-field checks and lifecycle rules
  live in Python validators and must run at the receiving service. Browser
  validation is never a trust boundary.
- A schema-valid record is not an authorised action. Services must check the
  authenticated workspace/node relationship, active attempt, registered
  capabilities, approved manifests, expiry, hashes, and granted policy.
- These are snapshots. Revalidate serialised data at every boundary; do not
  mutate nested lists or bypass validation with `model_construct`/`model_copy`.

From the repository root, after permission for setup and checks:

```bash
python3 -m venv .venv
.venv/bin/python -m pip --isolated --disable-pip-version-check install --no-cache-dir --only-binary=:all: --index-url https://pypi.org/simple -r backend/requirements.txt
.venv/bin/python -m unittest backend.contracts.test_contracts -v
.venv/bin/python -m backend.contracts
```

Python 3.10+ is required by this package. The last command exports to stdout;
there is no separately maintained generated schema. The checks use stdlib
`unittest` and [synthetic JSON examples](examples.json), with no sockets,
database, models, Pods, or subprocesses. A zero digest in an example is a
placeholder, never an approved model or artifact hash.

## Records and authority

| Record | Purpose and owner |
|---|---|
| `Node` | Observed node identity, capability and manifest references, health, queue and memory; absence is `null`/`unknown`, never zero or healthy |
| `JobEnvelope` | Coordinator's bounded dispatch for one attempt: original request, IDs, capabilities, context, attachments, tools, limits, validation and approval policy |
| `Job` | Coordinator's canonical job snapshot; only the coordinator changes it |
| `Attempt` | One execution and its node, model, route, times, error and artifacts; the coordinator persists accepted observations |
| `Event` | Typed state, output, artifact, approval or proof event; worker events cannot decide job completion, approval or proof |
| `Approval` | Coordinator-only exact action, target, attempt and action digest, actor, expiry and decision |
| `Proof` | Coordinator's evidence references, citations and values; unavailable measurements stay `null` and have no inferred security status |

`ResourceRef` contains an opaque ID, SHA-256, byte size and media type. A worker
resolves it only against its explicitly transferred task package, never an
arbitrary URL, host path, repository, or knowledge base. Verify size and hash
before use. Reject traversal, symlink/hard-link escape and unselected resources
in the receiving filesystem code. Contract validation alone cannot do this.

`Citation` binds one drafted claim to the `ResourceRef` and 1-based page it came
from, carrying the verbatim source quote. `Proof.citations` is where the
`citations.resolve` validator finds its evidence; citation IDs are unique within
a proof. `require_grounded_citations(envelope, proof)` is the coordinator-side
grounding guard for
[documents step 8](../../docs/workflows.md#5-documents-workflow): it rejects a
proof paired with another job, a grounded output that carries no citation, and
any citation naming a resource the envelope never supplied. It cannot detect a
quote that misreads a page it was genuinely given — extraction fidelity and page
existence remain workflow-side checks, not contract validation.

`ModelRef.manifest_sha256` identifies the reviewed manifest in the coordinator's
[model catalogue](../../docs/model-catalog.md#4-required-manifest). The manifest
owns exact source, revision, licences and file hashes. Worker claims do not
establish approval, compatibility or self-test success.

`OutputContract` binds each output `kind` to the validator that proves it:
`text` requires `text.nonempty`, `json` requires `json.schema` and its approved
hash, `docx` requires `document.readable`, and `patch` requires `patch.applies`.
`citations.resolve` may be added to any rendered output; `sandbox.exit_zero` may
be added only to `patch`. A validator that cannot judge the declared kind, and a
validator requested twice, are rejected rather than silently ignored. Declaring
a validator is a requirement on the executor, not evidence that it ran.

An attempt that stops without output — `failed`, `cancelled` or `interrupted` —
carries exactly one typed `Failure`, so a lost worker, an expired deadline and
an operator cancellation stay distinguishable in canonical history instead of
collapsing into an untyped stop. `cancelled_by_user` is reserved for a real
cancellation and cannot be used to relabel a crash or an interruption.

The envelope's tool allowlist cannot contain canonical-write, installation,
network-enablement or pairing actions. Enforce CPU, memory, process, runtime,
workspace and output bounds in the executor; reject unsupported limits rather
than silently ignoring them. `tool_network: disabled` applies to the tool
sandbox, not the worker's required authenticated control traffic.

## Lifecycle and retry

The initial event is `job.state`, `previous: null`, `current: created`, with no
attempt ID. Normal job transitions are:

```text
created -> context_preparing -> queued -> routing -> running -> validating
validating -> completed                          (automatic policy boundary)
validating -> awaiting_approval -> completed      (approved final action)
awaiting_approval -> denied
routing -> queued                                (no eligible capacity)
routing/running/validating -> interrupted -> queued
any active job -> failed/cancelled
```

`require_transition` enforces these edges. Completed, failed, cancelled and
denied jobs have no outgoing edge; a denied action cannot be retried under a
different route. A new user request creates a new job.

An attempt starts `queued` and moves through `running -> validating -> completed`;
any active attempt can fail, cancel or become interrupted. All four attempt
terminal states are final. An interrupted job may requeue, but its old attempt
never resumes: create a new attempt ID and set `retry_of`. A worker completing
its attempt does not complete the canonical job or permit a final write.

Persist each canonical state change and its event together in SQLite. On
coordinator restart, reconcile active executions before accepting output; an
unrecoverable execution becomes interrupted or failed, never completed by
assumption. Accept worker results only for the active attempt and assigned
node. Late results from cancelled, replaced or revoked attempts cannot advance
state. Enforce `min(deadline_at - now, runtime_seconds)` at admission/execution;
a timestamp that is structurally valid may already have expired.

## HTTPS application boundary

The draft fixes worker container/Service target port **8443** and trusted-LAN
NodePort **30443**. AF-002 still must confirm host port availability, pin K3s and
image digests, and prove firewall/NetworkPolicy enforcement. Redis remains
ClusterIP-only. Local UI and local model runtimes remain loopback-only.

Use standard HTTPS with the server certificate fingerprint pinned during
explicit pairing; never use `verify=False`. Every request after pairing needs
a unique revocable relationship credential or mTLS, scoped to the authenticated
workspace and node. Reject unknown, expired, revoked and incompatible peers
before persistence or dispatch. Neither an ID in JSON nor a SHA-256 authenticates
the caller. Derive event producer identity from this authenticated context;
do not trust a submitted `producer: coordinator` label.

The credential/bootstrap wire format is deliberately **not frozen**: PRD OD-06
still needs the prototype pairing decision. The pairing routes remain
unavailable until that choice, OS credential-store integration and negative
checks are implemented. Do not invent a shared token or keep secrets in SQLite,
Redis, examples, config, URLs, logs or the schema bundle to bypass this gate.

Every request/response uses `X-AegisForge-Contract: 1.0`; record bodies also
carry the version. JSON bodies use `application/json`. Mutations require an
`Idempotency-Key` containing a UUIDv4; scope it to authenticated relationship,
method and resource. The raw JSON body limit is **262144 bytes** and the SSE
JSON event limit is **16384 bytes**. Enforce a streamed body cap before parsing,
including requests without Content-Length; the Python guard is a second check.
Reject compressed request bodies in this profile. Apply bounded connection,
request and heartbeat timeouts; throttle before enqueueing.

| Worker route | Payload / result |
|---|---|
| `GET /v1/health` | `Node`, including truthful degraded/unavailable health |
| `GET /v1/capabilities` | Same `Node` record; advertise only locally verified eligible capabilities |
| `POST /v1/pairing/confirm` | Reserved pending OD-06; no trust granted by the draft |
| `DELETE /v1/pairing/{relationship_id}` | Reserved pending OD-06; revocation must fence active work and preserve coordinator history |
| `POST /v1/jobs` | `JobEnvelope` -> `202` with initial `Attempt`, persisted/enqueued before acknowledging |
| `GET /v1/jobs/{job_id}?attempt_id={attempt_id}` | Current worker `Attempt` for that authenticated workspace, job and attempt |
| `GET /v1/jobs/{job_id}/events?attempt_id={attempt_id}` | SSE for that attempt; coordinator exposes its own persisted job stream to the local UI |
| `DELETE /v1/jobs/{job_id}?attempt_id={attempt_id}` | `202` with no body; record cancellation, stop/clean execution, then emit its terminal state |

The attempt query prevents a delayed cancel or poll from targeting a newer
retry. A worker never serves a fabricated canonical `Job`. The coordinator's
local application routes remain AF-004 work and use these same records.

Use `400` for missing/invalid contract headers, `401/403` for authentication or
authority failure, `404` for a resource outside the authenticated scope,
`409` for a version/idempotency/state conflict, `410` for an expired event
cursor, `413` for body limits, `422` for schema violations, `429` for admission
capacity, and `503` for unavailable runtime/Redis. Errors use `Failure` fields
`code`, `message`, `retryable`, with metadata-only messages. Do not expose
Pydantic's raw error inputs, prompts, paths, credentials or tracebacks.

## SSE, replay and privacy

`sse_frame` produces UTF-8 `text/event-stream` records:

```text
id: <sequence>
event: <data.kind>
data: <single JSON Event>

```

Sequence starts at 1. The coordinator owns one monotonic per-job sequence
across attempts; a worker owns its separate per-attempt sequence. Persist the
source event ID for deduplication, then assign a coordinator event ID/sequence
when accepting a worker observation. Never substitute Redis entry IDs or
timestamps for canonical sequence numbers. A reconnect supplies `Last-Event-ID`
and receives events strictly after that cursor, preserving stored IDs/order.
Return `410` before starting SSE if the cursor was trimmed; obtain the current
snapshot before resubscribing. Keepalives are SSE comments, not state changes.

Job creation and attempt creation each emit their initial state event. A worker
can emit only `attempt.state`, `output.delta` and `artifact.created`. Artifact
events require a complete transferred output whose integrity can be verified.
Only the coordinator emits `job.state`, `approval.required`, `proof.updated`.

Output deltas contain user content and may be persisted only in the coordinator's
protected chat/event store or bounded worker Redis stream. Ordinary audit logs
contain event metadata without delta text, original prompts or attachments.
Render deltas as text in the browser; never treat model output as HTML.

## Redis 7.2 contract

Use `redis_key`; IDs cannot add path/key delimiters. Here `R` is the
relationship UUID, `A` an attempt UUID, `N` a node UUID, and `K` an idempotency
UUID. No cross-relationship consumer or lookup is permitted.

| Key | Value / ownership / bound |
|---|---|
| `af:1.0:R:dispatch` | Stream, consumer group `executors-v1`; field `envelope` is the JSON `JobEnvelope`; at most 128 outstanding entries |
| `af:1.0:R:events:A` | Stream; field `event` is JSON `Event`; at most 2048 retained entries and 3600-second expiry |
| `af:1.0:R:lease:A` | Current executor's opaque ownership token; `SET NX EX 30`, renew every 10 seconds only while ownership matches |
| `af:1.0:R:heartbeat:N` | Metadata-only `Node` JSON; refresh every 10 seconds, expires after 30 seconds |
| `af:1.0:R:cancel:A` | `1`, expires after 3600 seconds; check before claiming and while executing |
| `af:1.0:R:idempotency:K` | Request digest plus accepted attempt ID and response status; expires after 3600 seconds |

Atomically check dispatch capacity and idempotency, then enqueue. Return `429`
when full. Do **not** trim live dispatch entries with `MAXLEN`: Redis 7.2 can
remove pending/unread work. Delete only acknowledged entries after the
coordinator has durably accepted the terminal result; combine `XACK`/`XDEL`
atomically. Expire the relationship dispatch stream only after it is empty and
has no pending entries. Never let a queue TTL erase live work.

Use consumer-group pending state and `XAUTOCLAIM` for abandoned deliveries. A
reconciler fences the old attempt and asks the coordinator for a new attempt;
reclaiming a stream entry is not permission to blindly repeat execution.
Lease renew/delete must compare the owner token atomically. Loss of the lease
stops execution. If a worker dies after emitting output but before acknowledgement,
the coordinator deduplicates the terminal observation and acknowledgement.

Event streams may trim old progress within their bound; a gap requires snapshot
reconciliation, never fabricated replay. Retain terminal metadata/artifacts
until coordinator receipt or the 3600-second retention boundary; expiry before
receipt makes the attempt interrupted, not successful. Remove temporary input
and output at that boundary. Redis persistence is disabled; memory is bounded
with `noeviction`, so capacity loss fails admission rather than evicting leases.
AF-002 must choose and verify the memory cap on the host.

Redis loss invalidates active attempts. The coordinator persists the interrupted
state, fences old IDs and decides whether a new attempt is authorised. Duplicate
compute is possible under at-least-once delivery; exactly-once final-write
authority never resides in Redis. Do not add a cache until a concrete consumer
needs one; any later cache requires explicit safe contents, size and expiry.

## Idempotency and approval

For a parsed record, `payload_sha256` hashes compact UTF-8 JSON with sorted object
keys, preserving list order and every validated field. This is the application
digest convention, not a cryptographic signature or general JSON canonicalisation
standard. Equivalent key order has the same digest; a different attempt or
request has a different digest.

Persist the scoped mutation key and digest with the accepted operation. A
repeated key with the same digest returns the existing operation and does not
enqueue again; different content returns `409`. DELETE digests bind its method,
normalised route, relationship, job and attempt IDs, even without a body.
Retain coordinator idempotency records for the lifetime of the job. Worker
Redis records are only a short-lived optimisation; their loss grants no new
canonical authority.

An approval's action digest binds the workspace/workflow/job/step/attempt IDs,
action, exact target, expected prior target hash (or explicit absence), input
hashes and proposed output hash. Store that exact action plan in coordinator
SQLite. Before applying it, require the current attempt, unchanged target and
output, matching unexpired approval, and an authenticated actor. The model or
worker cannot supply its own approving actor. A retry needs a fresh approval.

Final-write uniqueness is scoped to `(workspace_id, job_id, step_id, action,
target)` and survives attempt replacement. Record durable write intent and
reconcile the actual target/hash after a crash before retrying; a SQLite row
alone cannot atomically commit a filesystem write. AF-013 implements and tests
this boundary. Neither a digest helper nor an `approved` JSON record proves it.

## Reuse and remaining gates

Pydantic **2.13.5** provides strict validation and JSON Schema generation instead
of a bespoke validator. Source: [upstream pinned release](https://github.com/pydantic/pydantic/tree/v2.13.5);
licence: [MIT](https://github.com/pydantic/pydantic/blob/v2.13.5/LICENSE).
Local upstream modifications: none. The package uses the Python standard
library for JSON, hashing, timestamps and checks. No telemetry, Logfire, network
client, runtime, download or service startup is added by this package.

All five dependency versions are pinned in [requirements.txt](../requirements.txt).
The installed wheel inventory below comes from the approved PyPI installation
on 2026-09-02. All are unmodified upstream distributions; only pydantic-core is
platform-specific (`cp314-cp314-macosx_11_0_arm64`), the others are `py3-none-any`.

| Distribution / upstream release | Licence | Installed wheel SHA-256 |
|---|---|---|
| [pydantic 2.13.5](https://pypi.org/project/pydantic/2.13.5/) | MIT | `346a034f080da3755d8e9cb5e00e8b07de1d39e4f6e2c87d8ab7cafa0b269a73` |
| [pydantic-core 2.46.5](https://pypi.org/project/pydantic-core/2.46.5/) | MIT | `1a353f84de772f423b5ffb11d7ae352fbbef0f446f3c0b0af0f8236d7233606e` |
| [annotated-types 0.7.0](https://pypi.org/project/annotated-types/0.7.0/) | MIT | `1f02e8b43a8fbbc3f3e0d4f0f4bfc8131bcb4eebe8849b8e5c773f3a1c582a53` |
| [typing-extensions 4.15.0](https://pypi.org/project/typing-extensions/4.15.0/) | PSF-2.0 | `f0fa19c6845758ab08074a0cfa8b7aecb71c999ca73d62883bc25cc018c4e548` |
| [typing-inspection 0.4.2](https://pypi.org/project/typing-inspection/0.4.2/) | MIT | `4ed1cacbdc298c220f1bd249ed5287caa16f34d44ef4e9c3d0cbad5b521545e7` |

Other platform wheels and the worker image lock remain AF-003 work. Offline
execution may not install missing packages. These libraries supply local
validation/typing; no networking feature or instrumentation is used. The check
run is not independent zero-egress evidence.

Primary protocol references: [Pydantic strict validation](https://docs.pydantic.dev/latest/concepts/strict_mode/),
[JSON Schema export](https://docs.pydantic.dev/latest/concepts/json_schema/),
[WHATWG SSE](https://html.spec.whatwg.org/multipage/server-sent-events.html),
[Redis XAUTOCLAIM](https://redis.io/docs/latest/commands/xautoclaim/),
[Redis XTRIM](https://redis.io/docs/latest/commands/xtrim/).
Use Redis 7.2 semantics; later-version trimming/acknowledgement options are not
part of this profile.

### Observed local verification — 2026-09-02

Environment: Aditya's local Mac, macOS 26.6.2 arm64, Python 3.14.6 in repository
`.venv`. The user authorised dependency installation and offline contract checks.

- `.venv/bin/python -m unittest backend.contracts.test_contracts -v`: **5 tests
  passed**, including seven example round trips, malformed/unsafe records,
  terminal lifecycle guards, retry digests, Redis keys, and SSE text escaping.
- `.venv/bin/python -m pip --disable-pip-version-check check`: **no broken
  requirements**.
- `.venv/bin/python -m backend.contracts`: **exported parseable JSON**, version
  1.0, all seven schemas, 49068 bytes.
- `git diff --check`: passed; new Python/JSON files also passed syntax parsing
  and whitespace inspection.

### Observed local verification — 2026-09-03

Environment: Yug's local Windows 11 (AMD64) host, Python 3.13.2, **pydantic
2.13.4 already present — not the pinned 2.13.5**, and no `.venv` or install was
used. This is a second-platform smoke run, not a pinned-environment result; the
pinned interpreter and wheel remain unverified on Windows.

- `python -m unittest backend.contracts.test_contracts -v`: **8 tests passed**
  (Aditya's five plus the C01 output-validator, stop-reason and citation checks).
- `python -m backend.contracts`: **exported parseable JSON**, version 1.0, all
  seven schemas, `Citation` resolved under `Proof`, 52304 bytes.
- Every added rejection branch was executed individually and returned its own
  distinct message; each accepted case and the grounded happy path passed.
- `json.load` on `examples.json` and `git diff --check`: passed.

Before AF-001 can become `verified`: resolve OD-06, connect all four consumers
to this version, obtain requester verification, and repeat the checks on the
pinned pydantic 2.13.5 on at least one non-macOS host. Before Day 1 passes:
prove Prachi's cluster, the pinned worker image and real model response, plus
SQLite persistence and the local UI.
