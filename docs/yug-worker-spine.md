# WP-YUG-001 — Build the worker execution spine

Status: **planned execution packet**, issued 2026-09-03. No worker, model,
Redis or Kubernetes result is established by this document.

Implementation owner: **Yug**, using his Claude Code session.
Integration and review: **Aditya with Codex**.
Scope: AF-002 implementation assets, AF-003 and AF-005, plus worker-side
integration for AF-006. This is one substantial assignment with successive
working milestones. It does not authorise later workflow or scaling work.

## The outcome

Deliver a worker that can take a real bounded text-generation attempt from
Aditya's coordinator, execute one approved local model, stream typed results,
cancel and recover safely, and run from the same source in a pinned Docker
image on the single-node K3s host.

```text
Aditya's coordinator                    Yug's implementation
SQLite + local UI + routing   ->   authenticated worker API
                                           |
                                      Redis Streams
                                           |
                                      one executor
                                           |
                                    one local model
                                           |
coordinator accepts results   <-      typed SSE events
```

The worker must be useful before the complete UI exists. Supply a small
synthetic protocol client for real streaming and failure checks; it must use
the actual worker routes and shared contracts. It must not become a second
coordinator, persistent chat database, router, or approval system.

The first inference uses CPU if that is the available proven path. GPU setup
is not a prerequisite for the first response. Do not equate Yug's development
machine with the demo host: the recorded Windows/RTX 2050 inventory needs
refresh, while Prachi's Ubuntu machine remains the selected K3s host.

## Read before implementing

1. [AGENTS.md](../AGENTS.md), then [branch flow](../CONTRIBUTING.md#the-one-rule).
2. [Current task board](../tasks.md), particularly AF-001 through AF-006.
3. [PRD invariants and open decisions](prd.md), [architecture](architecture.md),
   [security boundaries](security.md), [model catalogue](model-catalog.md),
   [hardware evidence](devicespecifications.md), and [evaluation](evaluation.md).
4. [AF-001 contract semantics](../backend/contracts/README.md), the actual
   [records and helpers](../backend/contracts/v1.py),
   [examples](../backend/contracts/examples.json), and
   [checks](../backend/contracts/test_contracts.py).
5. Search the two ledgers for `af-001`, `worker-spine`, and the paths being
   changed. History does not override source or current user instructions.

Re-read the live checkout: the contract review may change the baseline after
this packet was written. The previously observed five contract checks are
historical evidence, not a substitute for checks on Yug's checkout.

## Ownership and allowed changes

| Area | Owner / rule |
|---|---|
| `backend/worker/` | Yug: worker API, executor, one runtime adapter, temporary state, targeted checks and smoke client; create only files needed by those processes |
| `backend/worker/requirements.txt` | Yug: pinned worker-only dependencies; include the existing contract requirements rather than copying their pins |
| `backend/worker/Dockerfile`, root `.dockerignore` | Yug: worker image using repository-root build context; allow only required worker/shared-contract sources and dependency files into that context |
| `infra/k3s/` | Yug: namespace, worker/executor/Redis workloads, Services, configuration, network policy and reproducible host instructions |
| `backend/worker/README.md`, `docs/evidence/yug-worker-spine.md` | Yug: setup/run commands, baseline, decision record, dependency/model/image provenance, observed checks and limitations |
| `backend/contracts/`, `backend/requirements.txt` | Aditya owns the shared seam; Yug proposes necessary fixes through his current review and applies only the agreed scope |
| `backend/coordinator/`, `frontend/` | Aditya: canonical SQLite, job/event persistence, UI, routing, coordinator credential handling, approval and final writes; Yug does not create competing versions |
| `docs/model-catalog.md`, `docs/devicespecifications.md` | Yug may append narrowly scoped, actually observed runtime/model/hardware evidence; no general rewrite |
| `tasks.md`, `backend/README.md`, the two ledgers | Only relevant task status, handoff links and append-only records; preserve concurrent edits |

The paths above that are absent today are permitted implementation destinations,
not instructions to generate empty folders or scaffolding. Keep the adapter in
the worker package until a second real caller justifies moving it. Aditya's
standalone path may reuse this same worker instead of building another adapter.

Do not modify AGENTS.md, licence terms, Actions, branch rules, personal agent
configuration, coordinator source or frontend source as part of this packet.
If a needed shared change emerges, present the exact small patch and affected
callers to Aditya. Do not fork a `v1_yug`, weaken validation or edit a test to
make an unsafe implementation pass.

## Permissions and publication

Ordinary source implementation inside this packet is its purpose. Runtime
tests, installations, model downloads, container builds/runs, K3s deployment,
host/firewall changes and Git writes still follow AGENTS.md and the current
session's explicit permissions. The earlier approval to install Pydantic on
Aditya's Mac does not authorise operations on Yug's or Prachi's machine.

Collect missing permissions into one concrete command list with the target
machine, download size/source where relevant, ports and cleanup scope. Execute
already authorised work without asking again. While an external gate is closed,
finish useful source, synthetic checks and documentation that do not depend on
it; label unrun commands `BLOCKED`, never `PASS`. Host access and deployment
must be approved by the host owner. Never change drivers or expose a LAN port
just to make a smoke check pass.

Yug publishes through **`yug` -> PR into `dev` -> release PR into `main`**.
There is no direct push to `dev` or `main`. This file grants no automatic Git
or GitHub-write permission to Claude. Yug performs those operations himself
unless his current message explicitly authorises them.

Aditya/Codex review the published diff and evidence. Supply the branch tip and
base SHA; if changes have reached `main`, also supply the release merge SHA and
pre-release base so the same work can be reviewed there. Publication does not
mark the packet or an AF task verified. Do not delete or overwrite history to
address review findings; make a scoped follow-up through the normal branch flow.

## Phase 0 — Finish the current review and settle the shared seams

Finish Yug's ongoing AF-001 review first. Report `PASS`, `NEEDS FIX`, or
`BLOCKED`, with exact paths/lines and one reproducer per material finding.
Separate contract defects from unimplemented downstream enforcement. Confirmed
shared defects go back to Aditya before worker code depends on them.

Record the agreed base SHA and contract version in the evidence file. Resolve
only decisions required by the next milestone:

| Decision | Required outcome |
|---|---|
| OD-03 / OD-05 | One runtime and one model, chosen from actual available hardware and reviewed upstream evidence; recorded revision/licence/hash/context/memory limits; no invented compatibility or silent download |
| OD-06 | One agreed prototype pairing and credential lifecycle, including invitation confirmation, OS-backed secret storage, certificate pinning, revocation and how Pods receive credentials without committing them |
| OD-08 | Exact supported K3s/Redis patch and image digests when preparing the host; take the Service port and contract constants from the shared export |
| Model selection | Agree how coordinator-selected model/manifest identity reaches admission and appears in the attempt; reject incompatible choices instead of silently substituting a model |
| Receipt and recovery | Agree how the coordinator acknowledges durable terminal receipt before `XACK`/deletion, and how a Redis restart or lease loss fences an old attempt |

These are questions the current consumers must settle, not findings asserted by
this packet. Proposed message/route additions belong in the shared contract,
with examples and checks, not in a private worker dialect. Aditya accepts changes
to the cross-process seam. Resolve the runtime before writing its adapter and
the pairing profile before enabling the LAN API. Do not block unrelated local
work on a K3s-host permission that it does not need.

Exit: one agreed review baseline, explicit decision owners and no unresolved
security/schema conflict in the milestone being implemented. Record still-open
external decisions rather than claiming the complete AF-001 gate passed.

## Phase 1 — Prove one real local model through one adapter

Reuse an approved existing runtime; do not implement inference or a downloader.
Provide the small operations actually needed: installed-model/manifest lookup,
truthful health, bounded streaming and cancellation. Pin dependencies, source,
licences and material local modifications. Consult current primary upstream
documentation for the selected version during implementation.

Use the explicit model/manifest selected at admission. Missing model, wrong
hash, incompatible runtime, load failure and unavailable runtime must be visible
failures. An HTTP 200 from a daemon does not prove that its model is usable.

Send a synthetic original request to the real model. Capture the first text
delta, terminal result, selected model, device, runtime/version, cold/warm timing
and measured memory where obtainable; otherwise report unavailable. Honour the
request deadline, cancellation and output-byte budget. Closing the SSE connection
alone is not proof generation stopped: demonstrate bounded resource release.

Keep any raw runtime endpoint on loopback; in a Pod, co-locate it with its caller
or use an in-process runtime. Do not expose the model daemon as another LAN or
cluster Service. No implicit model pulls, updates, telemetry or fallback to a
public provider. This first path accepts text only; reject unsupported tools,
attachments, resource references and output contracts explicitly.

Exit: reproducible real inference and cancellation from a documented command,
with no coordinator, UI or Redis dependency and no mocked response presented
as model execution.

## Phase 2 — Implement the authenticated worker API and direct execution

Implement the existing `/v1` health, capabilities, job submission, attempt
snapshot, SSE and cancellation surface using shared records and helpers. Add
pairing/revocation only under the agreed OD-06 profile. Keep one executor path
that both direct local execution and Redis dispatch call; no parallel fake mode.

Enforce authentication and workspace/relationship/node scope before job
creation. Validate contract version, streamed body size, actual deadline,
idempotency key, target/model, approved capabilities, tool policy, input hashes
where supported, and executable resource limits. Apply rate/connection bounds
and reject unsupported requests before allocating a job workspace or queue entry.

Temporary work is owner-only, belongs to the active attempt and cannot escape
its assigned root. No arbitrary host paths, whole-repository access, canonical
writes or host commands. Advertise only the text capability actually implemented.
Do not simulate Documents, Code, sandbox validation or an approval result.

Use the frozen state transitions and worker event kinds. Preserve stable event
IDs and sequence on replay, return the documented expired-cursor response, and
keep prompts/deltas/credentials out of ordinary logs. Derive producer identity
from the authenticated context, not a JSON claim. Cancellation targets an
explicit attempt; a delayed request must not cancel a newer retry.

Demonstrate same-key/same-content replay without duplicate work and same-key/
different-content conflict. A worker attempt finishing does not complete a
canonical job. Retain results for the agreed receipt/reconciliation boundary.

Exit: the real API smoke client streams and cancels a real model attempt,
negative admission checks fail safely, and unrelated workspace history is
neither accessed nor created by the worker.

## Phase 3 — Add Redis dispatch, leases and failure recovery

Implement the existing Redis 7.2 key/group/retention rules from the contract,
using a standard pinned Redis client. SQLite remains solely the coordinator's
authority. Do not add another broker, result database, distributed lock service
or queue abstraction framework.

Admission capacity, idempotency reservation and enqueue must be atomic. Handle
Redis unavailability and capacity exhaustion before promising acceptance. Keep
consumer pending state recoverable; no blind trimming of pending or unread
dispatch entries. Use owned leases with atomic compare-and-renew/release,
bounded heartbeats, cancellation and terminal-result retention.

Exercise the complete receipt path through the real API/client before deleting
work. An executor crash after terminal emission but before receipt/ack must
reconcile the same observation. Lease loss, abandoned pending entries and Redis
restart must fence old work and require coordinator-controlled retry with a new
attempt ID. An executor cannot create canonical retries or reuse approval.

Ephemeral event trimming must produce a detectable replay gap. Apply memory
limits, no-eviction admission failure, expiry and temporary-file cleanup. Do not
claim exactly-once computation; demonstrate that duplicate delivery cannot
grant additional authority or overwrite a newer attempt.

Exit: one actual Redis-backed execution plus observed duplicate admission,
pending recovery, cancel, lease loss, event gap and Redis-restart cases.

## Phase 4 — Package the same code and prove the K3s profile

Create the smallest pinned worker image with API and executor entry points.
Copy only needed worker/shared-contract files; model weights, credentials,
workspace files, repository history and local databases must not enter the
build context or image. Record the actual base and output image digests.

Create one namespace, worker API Deployment/Service, one executor replica, and
Redis Deployment/ClusterIP Service. Use the shared exported version/ports,
read-only approved model storage, bounded writable temporary storage and the
security controls already required by security.md. No privileged container,
host network/PID/IPC, Docker socket, home mount or default service-account token.

Check Pod limits against requested attempt limits. A Pod memory/CPU limit does
not by itself prove per-attempt process, disk or runtime enforcement. Implement
the applicable bounds or reject the envelope; document each enforcement source.

Configure meaningful readiness/liveness and orderly shutdown. Missing models
or Redis must produce truthful unavailable states without inventing ready
capabilities. Redis stays internal; only the authenticated worker Service is
LAN-exposed. Apply default-deny policies plus the minimum necessary flows and
verify their actual enforcement on the authorised host. Do not lock out host
administration or weaken the host firewall to bypass a failed check.

Provide preload, deployment, startup, smoke, shutdown and namespace-scoped
cleanup commands with exact pinned images and required host inputs. Complete
downloads before any offline run; use preloaded images without silent pulls.
Test through the Service, not just port-forward or localhost. Record Ready Pods,
the actual model response, Service reachability and Redis LAN isolation.

If Prachi's host is unavailable, finish the image/manifests and the authorised
local checks, report the host commands as blocked, and deliver the work for
review. Do not create another cluster or silently change the designated host.
Yug's Windows/WSL/Docker results do not establish Ubuntu K3s or GPU compatibility.

Exit: AF-002/AF-003 infrastructure evidence on the named host, or an explicit
hardware gate that prevents either task being marked verified.

## Phase 5 — Integrate once with Aditya's coordinator and hand off

Supply the exact worker startup command, non-secret configuration schema,
credential-store reference requirements, model manifest, version/ports, real
event trace and smoke command early enough for Aditya to wire AF-004/AF-006.
Do not wait for all failure drills to reveal a basic integration mismatch.

Aditya owns persistence, canonical replay ordering, route selection and final
job state. Yug owns the worker side and its repairs. Use the same actual API,
Redis and executor tested above. Verify a real Mac-to-Service round trip when
both sides and the host are available. Replacing an unavailable coordinator
with the synthetic client establishes worker behavior only.

For the complete Day 1/2 claim, the coordinator must persist job/attempt/model/
device/timing and remain usable after worker/Redis/cluster loss. That acceptance
requires Aditya's caller; this packet alone cannot certify it.

Stop after this spine and its requested repairs. Do not start OCR, Word,
repository patch execution, Kubernetes sandbox Jobs, voice, embeddings, another
runtime, multiple executors, a second node, Helm or a desktop wrapper. Those
remain under the task board's later gates.

## Acceptance commands and evidence matrix

After permission, rerun the existing baseline from repository root:

```bash
python -m unittest backend.contracts.test_contracts -v
python -m backend.contracts
```

Use the activated environment's Python (`.venv/bin/python` on Unix or
`.venv\Scripts\python.exe` on Windows). Include its exact path/version in evidence.

Deliver these two small runnable entry points as part of the packet:

```bash
python -m unittest discover -s backend/worker -p 'test_*.py' -v
python -m backend.worker.smoke --config /absolute/path/to/nonsecret-smoke.json --case stream
```

The smoke client must accept `--case` values `stream`, `cancel`, `idempotency`,
`replay`, `admission`, and `recovery`. Its configuration identifies the explicit
test endpoint, TLS trust, model and OS credential-store references; no credential
values in the file, command line or logs. Document equivalent real commands if
a smaller existing tool covers a case. Do not build a generic test platform.

`recovery` observes an operator-authorised disruption. It must not silently
kill Pods, flush Redis, change firewall rules or delete data. Record the exact
scoped fault command separately; the smoke client verifies its consequences.
The client exits nonzero for a failed or unavailable required check and records
each result as `PASS`, `FAIL`, or `BLOCKED`. Missing runtime/model/credentials/
cluster is not a passing skip. Isolated unit doubles are labelled as such.

| Case | Required observation |
|---|---|
| Current contract baseline | Current examples, version export and negative guards pass without weakening the contract |
| Admission | Missing/wrong/revoked/expired credentials, wrong workspace/target/version, expired deadline, unsupported model/tools/inputs and oversized bodies are rejected before dispatch |
| Real streaming | Original request reaches the approved model; live deltas, manifest/device and truthful terminal attempt are returned |
| Cancellation | Queued and running cases stop within the documented bound; resources and temporary state are released; late cancel cannot affect a retry |
| Idempotency | Same request returns the existing attempt; changed payload conflicts; concurrent duplicate submissions do not enqueue twice |
| SSE replay | Disconnect/reconnect preserves event identity/order; trimmed cursor is explicit; user text cannot inject an SSE frame |
| Pending and lease recovery | Killed or lease-losing executor leaves a detectable interrupted attempt; no unfenced continuation or blind same-ID rerun |
| Receipt crash window | Crash after terminal output before acknowledgement does not lose the retained result or create an extra canonical decision |
| Redis restart/full memory | Failures are visible; stale attempts are fenced; no canonical records are stored in Redis or assumed lost with it |
| Container and cluster | Pinned image, non-root bounded workload, Ready Pods and real Service-to-model response on the named host |
| Network and secrets | Runtime endpoint and Redis are not LAN-exposed; bad TLS fails; credentials/payloads do not enter image, logs or committed evidence |
| Coordinator integration | Real Aditya-owned SQLite caller accepts one result and preserves history after worker loss; otherwise mark this row blocked |

Use only synthetic/non-sensitive inputs. Record the exact command, date, host,
OS, versions/digests, input hash, result and limitation for each claimed row.
Keep measurements separate from estimates and network enforcement separate from
observed traffic. Passing a local contract check does not establish zero egress.

## Required review handoff

Publish a reviewable milestone after each phase; these are source checkpoints,
not instructions to create extra release PRs or trigger unnecessary Actions.
When a needed permission or host is absent, name the blocked row and deliver
the usable work already completed. Do not finish with only a plan if code can
be implemented within the authorised scope.

The final handoff in `docs/evidence/yug-worker-spine.md` must contain:

1. Scope completed and each AF task's actual state; no claim that all Day 1/2
   work passed from a worker-only run.
2. Reviewed base SHA, current branch/commit SHA, contract version and any agreed
   contract delta. Include release SHAs if the review follows a merge to main.
3. Changed paths and the exact setup/start/check/stop commands for another
   machine, with required inputs and owner-only credential setup explained.
4. The evidence matrix with observed output, model/dependency/image provenance,
   actual timings, and every failed or blocked case retained.
5. Known limitations, temporary-data retention, targeted cleanup procedure,
   and rollback/reconciliation behavior for interrupted work.
6. Review hotspots and remaining coordinator/host decisions, followed by the
   AGENTS.md `GIT / GITHUB — RUN THESE YOURSELF` and `VERIFY — RUN THESE YOURSELF`
   handoff sections. Keep secrets and confidential output out of the handoff.

Aditya/Codex inspect current source and rerun authorised acceptance commands.
Claude's summary, green unit checks, a successful image build or a merge to main
does not substitute for requester verification of the claimed real path.

## Prompt Aditya can give Yug's Claude

```text
Finish your current review of our AF-001 contracts and report any confirmed
blockers first. Then implement WP-YUG-001 in docs/yug-worker-spine.md against
the agreed current baseline. You own the worker API, one real local-runtime
adapter, Redis dispatch/recovery, Docker image, K3s assets, and worker evidence.
Aditya owns the coordinator, SQLite, routing, approvals and frontend.

Read AGENTS.md and the linked sources. Execute the packet in working phases;
do not stop at another plan or fabricate missing runtime results. Reuse the
shared contracts and ask Aditya about only necessary shared-boundary changes.
Follow existing permissions for tests, installs, downloads, host operations
and Git writes; group any missing approvals into exact commands once.

Return reviewable code, exact commands and observed PASS/FAIL/BLOCKED evidence.
Publish only through the authorised member-branch -> dev -> main workflow.
Aditya and Codex will review the actual published changes and verification.
```
