# AegisForge Execution Roadmap

Status: active execution board; tasks advance only with recorded evidence.

The internal sprint deliberately attempts every P0 outcome plus the signature
workflow and concurrency outcomes currently labelled P1 in the PRD. This is an
aggressive execution target, not a silent change to PRD priority labels.

This file turns the [PRD](docs/prd.md) into an execution order. Product and
security requirements remain owned by the focused documents in
[docs/README.md](docs/README.md); this file owns only sequence, ownership, and
integration gates.

## Mission

Win the internal selection with one real sovereign agent application that:

- runs useful work on one device;
- automatically routes complete task steps to trusted local workers;
- runs Documents and Code work concurrently where hardware permits;
- returns a cited Word artifact and a sandbox-validated code patch;
- keeps canonical state, approval, and final writes on the coordinator; and
- proves public egress was blocked or independently observed during the demo.

Distribution means task-level orchestration, not model sharding or combined
VRAM. No mocked inference, routing, sandbox, artifact, or network evidence may
be presented as real.

## Friday product bar

The candidate is not judged by file count, agent count, or Kubernetes objects:

- **Usable:** a new operator can open the local UI, submit a real job, follow
  progress, cancel it, and retrieve the result without a developer editing
  state by hand.
- **Viable:** one MRPL-relevant scanned-report workflow produces a grounded,
  cited, openable approval note; the infrastructure is in service of this
  outcome rather than the whole demonstration.
- **Presentable:** the team can show Docker image provenance, Ready Pods,
  Services, Redis queue state, deterministic routing, approval, failure
  recovery, and scoped offline evidence in one coherent story.

If the Documents workflow is not real by the Day 3 gate, a second worker,
multilingual support, voice, scaling, and visual polish are stopped. If the
complete frozen path does not pass three consecutive rehearsals, it is not the
candidate regardless of how many individual components work.

## Operating contract

- The team reports access to six Antigravity seats, Claude Pro, Codex Plus,
  free-tier Codex, OpenCode, and other assistants. This is planning capacity,
  not evidence that any task or tool works.
- A human owner remains accountable for every task. AI agents receive bounded
  work packets with allowed paths, frozen contracts, an acceptance command, and
  forbidden scope. Agent count never replaces integration or hardware proof.
- Critical-path build work may be assigned across the team after each owner
  proves the required local environment with the task's smallest acceptance
  check. Until then, Aditya or Vedant remains the fallback build owner.
- Aditya is integration owner and retains control of Git, merges, conflicts,
  scope decisions, and demo acceptance.
- Claude takes bounded implementation tasks and returns changed paths, exact
  checks run, observed results, and remaining failures.
- Codex reviews the current integrated source and observed evidence rather than
  relying on an implementation summary. Codex changes code only when explicitly
  authorised.
- Team members own capability work on their branches and merge through the
  [member branch -> `dev` -> `main` flow](CONTRIBUTING.md#the-one-rule).
- Integrate into `dev` at least twice daily. A module is not considered working
  until it runs through the shared coordinator contract.
- No two agents may invent parallel versions of the job envelope, event schema,
  authentication, Redis keys, or Kubernetes manifests. AF-001 freezes those
  seams before downstream work merges.
- Tests, installers, model downloads, migrations, deployments, and live-system
  commands require the permission defined in [AGENTS.md](AGENTS.md).

Task states are `planned`, `in-progress`, `review`, `verified`, or `blocked`.
Only observed acceptance evidence moves a task to `verified`.

## Proposed ownership

Aditya may reassign work without changing the architecture.

| Owner | Role | Required output |
|---|---|---|
| Aditya | Coordinator and integration owner | Frozen contracts, SQLite authority, routing, integration, scope, and release candidate |
| Vedant | Worker and model owner | Docker image, FastAPI worker, runtime adapter, Redis consumer, and streaming |
| Prachi | Kubernetes and isolation owner | K3s host, manifests, Services, Redis, NetworkPolicies, sandbox Jobs, and cluster evidence |
| Sahil | Contract and reliability owner | Contract checks, lifecycle/routing matrices, retry, cancellation, and failure drills |
| Yug | Documents owner | Public fixtures, OCR/page mapping, retrieval grounding, and document quality evidence |
| Tanvi | Product and demo owner | Local web UI, Control Center acceptance, Proof Card review, and demo pack |

The hardware mapping is a hypothesis until measured; use
[devicespecifications.md](docs/devicespecifications.md) for current evidence.
Prachi must close the K3s-host portion of the
[hardware checks](docs/devicespecifications.md#still-needed-before-final-model-placement)
before AF-002 begins. The other checks gate only the device or model assignment
they affect; they do not block the first cluster spine.

## Immediate work packets

These four packets start in parallel after Aditya publishes the AF-001 contract
draft. Each packet has one merge owner even when several AI agents assist.

| Packet | Owner | Allowed initial paths | First observable result |
|---|---|---|---|
| Contract and coordinator | Aditya | `backend/contracts/`, coordinator source, smallest contract check | One SQLite-persisted local job emits the frozen event sequence |
| Worker image and runtime | Vedant | worker source, `Dockerfile`, runtime adapter | One Docker-built image answers `/v1/health` and streams one real model response |
| Kubernetes and Redis | Prachi | `infra/k3s/`, deployment instructions | K3s reports Ready worker and Redis Pods; only the worker Service is reachable from the LAN |
| UI and acceptance | Tanvi | `frontend/`, acceptance checklist | The local browser UI shows one live job and truthful unavailable states |

Sahil writes contract and failure checks against the frozen envelope. Yug
prepares the public scan, page ground truth, SOP, and expected output without
blocking the Day 1 spine.

## Internal hackathon: five-day execution

### Day 1 — Freeze contracts and prove the local spine

| ID | State | Build owner | Support and evidence | Task | Depends on | Acceptance gate |
|---|---|---|---|---|---|---|
| AF-001 | in-progress | Aditya | Sahil checks lifecycle and schema cases | Freeze versioned node, job, attempt, event, approval, proof, HTTPS, Redis-key, and idempotency contracts | — | Coordinator, worker, UI, and manifests consume one contract version; schema examples pass the smallest contract check |
| AF-002 | planned | Prachi | Vedant reviews image/runtime requirements | Provision one pinned single-node K3s cluster on Prachi's Ubuntu host and deploy pinned Redis 7.2.x behind ClusterIP | AF-001 | Kubernetes reports Ready Redis and worker placeholders; Redis is unreachable from the LAN; versions, digests, and licences are recorded |
| AF-003 | planned | Vedant | Sahil records latency and failure output | Build the smallest Docker worker image with FastAPI, one runtime adapter, the frozen Service API, and one real model | AF-001, AF-002 | A real prompt streams from a worker Pod; source, licence, revision, image digest, memory, and latency are recorded |
| AF-004 | planned | Aditya + Tanvi | Sahil checks state transitions | Implement SQLite-backed coordinator state and the smallest local browser UI over one event stream | AF-001 | A local job reaches a truthful terminal state after restart; Chat and Control Center show live state while unfinished surfaces say unavailable |

AF-001 has a [contract draft with five passing local checks](backend/contracts/README.md).
The OD-06 pairing decision, shared consumers and requester verification remain
open; no Day 1 application runtime gate has passed.

Day 1 gate: the pinned Docker image runs in a Ready Kubernetes Pod, one real
response streams through the worker API, and the coordinator persists the job,
attempt, model, device, and timing record. No workflow work starts before this
spine passes.

### Day 2 — Prove real distributed execution

| ID | State | Build owner | Support and evidence | Task | Depends on | Acceptance gate |
|---|---|---|---|---|---|---|
| AF-005 | planned | Vedant + Prachi | Sahil tests pending, acknowledged, expired, and reclaimed work | Connect the worker API and executor through Redis Streams, leases, cancellation, bounded retention, and cleanup | AF-002, AF-003 | One queued attempt is consumed and acknowledged; a killed consumer leaves recoverable pending work; Redis restart loses no canonical record |
| AF-006 | planned | Aditya | Sahil executes the routing matrix | Route from the Mac coordinator to the Kubernetes Service using capability, health, queue, and explicit-target rules | AF-003–AF-005 | Mac -> authenticated Service -> Redis -> executor -> SSE response completes with visible route reason and local fallback |
| AF-007 | planned | Tanvi | Aditya connects only the frozen event contract | Finish the usable Chat and Control Center slice with guided preflight/self-test, node health, Pod readiness, model, queue, progress, cancel, disconnect, and fallback state | AF-004–AF-006 | A fresh documented setup selects the curated manifest and reaches a real self-test; every displayed value has a source and missing evidence displays unavailable |

Day 2 gate: a real Mac -> Kubernetes Service -> Redis -> executor Pod -> Mac
inference completes, and stopping the cluster leaves the Mac workspace and its
canonical history usable.

If this path has not passed by the end of Day 2, freeze a standalone demo
baseline and stop infrastructure expansion. Do not add nodes, replicas, Helm,
Ingress, another broker, or another runtime to repair an unproven single path.

### Day 3 — Complete both signature workflows

| ID | State | Build owner | Support and evidence | Task | Depends on | Acceptance gate |
|---|---|---|---|---|---|---|
| AF-008 | planned | Yug + Vedant | Yug owns public scans, ground truth, and scores | Implement scan rendering plus local OCR/vision extraction with source hash, page mapping, and explicit uncertainty through the shared job contract | AF-003, AF-006 | The public sample scan produces structured, page-linked extraction without fabricated missing values |
| AF-009 | planned | Aditya + Yug | Tanvi opens and reviews the Word output | Add the minimum local SOP retrieval, cited drafting, Word generation, and artifact validation path | AF-008 | `inspection_report_to_approval_note` returns an openable cited `.docx` with checksum |
| AF-010 | planned | Vedant + Sahil | Sahil owns the synthetic repository fixture | Implement bounded repository context and patch generation inside an assigned temporary workspace | AF-003, AF-006 | `repository_request_to_validated_patch` returns an applicable patch without modifying the canonical repository |
| AF-011 | planned | Prachi | Vedant supplies the sandbox image; Sahil checks outputs | Run each approved validation command as a short-lived restricted Kubernetes Job Pod | AF-002, AF-010 | Default-deny egress, non-root execution, limits, deadline, cleanup TTL, command output, and artifact hashes are observed; no Docker socket is mounted |

Day 3 gate: the application produces one real Word approval note and one real
validated code patch through the same Service, Redis, job, event, and approval
contracts.

### Day 4 — Run concurrently and prove sovereignty

| ID | State | Build owner | Support and evidence | Task | Depends on | Acceptance gate |
|---|---|---|---|---|---|---|
| AF-012 | planned | Aditya + Prachi | Sahil executes the concurrency matrix and records timings | Run independent Documents and Code attempts concurrently through separate Redis consumers and Pods | AF-005, AF-009, AF-011 | Both jobs progress simultaneously, retain separate attempt/artifact state, and show honest queue time |
| AF-013 | planned | Aditya | Tanvi executes the approval and denial checklist | Enforce approval before canonical writes and bind it to the exact action, target, and attempt | AF-004, AF-009, AF-011 | Denial writes nothing; retry cannot reuse a stale approval; approval performs one bounded final write |
| AF-014 | planned | Aditya + Tanvi | Tanvi checks every value against its source | Produce per-job Proof Cards from SQLite, Redis, Kubernetes, model, validation, integrity, approval, and network evidence | AF-012, AF-013 | Every displayed value has an identified source and observation window; unavailable evidence is not inferred |
| AF-015 | planned | Prachi | Vedant confirms runtime endpoints; Sahil records interface and time bounds | Enforce default-deny Pod egress and host public-egress blocking while retaining authenticated Service traffic | AF-011, AF-014 | The real concurrent run completes with zero observed public outbound flow in the named interval and only documented LAN/cluster flows |

Day 4 gate: Documents and Code complete concurrently on distributed compute,
with visible Pods, Redis queue state, routing, approvals, artifacts, and scoped
zero-egress evidence.

### Day 5 — Break it, freeze it, and rehearse it

| ID | State | Build owner | Support and evidence | Task | Depends on | Acceptance gate |
|---|---|---|---|---|---|---|
| AF-016 | planned | Sahil | Aditya and Vedant repair only observed blockers | Exercise cancellation, executor-Pod loss, Redis restart, cluster loss, retry, and local fallback | AF-012–AF-015 | Failure is recoverable, canonical history survives, and no duplicate final write occurs |
| AF-017 | planned | Sahil + Yug | Every teammate runs assigned fixtures and records named-device measurements | Run the same standalone and Kubernetes fixtures; record cold/warm latency, queue time, RAM/VRAM, restarts, and output quality | AF-008–AF-016 | Results are reproducible and slower results are reported honestly |
| AF-018 | planned | Aditya | Codex reviews the integrated source; Tanvi assembles the evidence pack | Review the integrated source, licences, evidence, demo claims, and remaining blockers | AF-017 | Every claimed feature is observed; planned or broken paths are labelled and excluded from the script |
| AF-019 | planned | Aditya + Vedant | The full team operates assigned demo stations and rehearses handoffs | Run the frozen demo from clean start three consecutive times and record one backup demonstration | AF-018 | Three successful runs use the same documented setup and public sample inputs |

Day 5 gate: no feature work remains. Only demo-breaking fixes, evidence repair,
and rehearsal may enter the internal candidate.

## Internal demo order

1. Show the Ready worker, executor, and Redis Pods plus the worker and internal
   Redis Services; explain that Docker built the pinned workload images.
2. Open the application and show Chat, Documents, Code, and Control Center.
3. Show the installed model, Kubernetes worker, queue, and route reason.
4. Block public Internet and start the named observation window.
5. Start the scanned-report workflow and the code workflow.
6. Show Redis dispatch and separate executing Pods without exposing payloads.
7. Open the cited Word artifact and the validated code patch.
8. Approve one bounded write, deny another, then terminate one executor Pod.
9. Show recovery, both Proof Cards, and the end of the observation window.

## Early-completion ladder

Finishing a calendar day early means starting the next unpassed gate, not
starting unrelated features. Stretch work unlocks only in this order:

1. **After Day 2 passes:** finish both signature workflows and their fixtures.
2. **After Day 3 passes:** add one bounded image-understanding moment and one
   calculation-with-steps inside the approval note.
3. **After Day 4 passes:** add a second executor replica and prove Redis-backed
   concurrency and Pod-loss recovery on the same cluster.
4. **After three clean rehearsals:** evaluate one additional physical worker or
   the narrow text-only part of FR-019.

Do not unlock multi-node Kubernetes, voice, PPT, Excel, broad P&ID support,
another runtime, or another broker during the five-day candidate.

## After internal selection: twelve-day finals sprint

| Day | Build owner | Support owner | Focus | Exit gate |
|---:|---|---|---|---|
| 1 | Aditya | Tanvi records judge feedback and the claim matrix | Triage judge feedback and freeze the finals claim set | Every accepted change maps to a PRD requirement or observed demo weakness |
| 2 | Aditya + Vedant | Sahil owns pairing negative cases | Harden node identity, pairing credentials, compatibility checks, and revocation | Invalid, expired, and revoked workers are rejected |
| 3 | Aditya | Sahil runs the complete fault matrix | Harden retries, cancellation, worker-loss recovery, idempotency, and cleanup | Interrupted jobs recover without duplicate final writes or retained temp data |
| 4 | Vedant | Yug expands fixtures and scores every page | Improve OCR/vision on the fixed public scan set | Page mapping and uncertainty meet the recorded quality threshold |
| 5 | Aditya | Yug checks citations; Tanvi reviews Word output | Improve local retrieval, citations, drafting, and Word validation | The approval note is grounded, readable, cited, and reproducible |
| 6 | Vedant | Sahil expands synthetic coding fixtures | Improve repository context selection and patch validation | The coding fixture passes without unrestricted repository transfer |
| 7 | Vedant | Prachi runs and records Linux boundary checks | Harden the Linux sandbox and verify its actual resource/network boundaries | Escape, network, timeout, process, and filesystem checks fail safely |
| 8 | Aditya + Vedant | Tanvi owns setup acceptance; Sahil operates reset devices | Complete guided setup, capability detection, manifests, and offline bundle import | A reset installation reaches honest self-test status without silent downloads |
| 9 | Aditya | Tanvi owns Control Center and Proof Card acceptance | Finish Control Center, approval UX, evidence semantics, and Proof Cards | No security or health value is hard-coded or inferred from missing evidence |
| 10 | Aditya + Vedant | All teammates capture their device measurements | Benchmark standalone versus distributed cold/warm runs | Same fixtures produce honest performance and quality comparisons |
| 11 | Aditya + Vedant | All teammates execute assigned failure drills | Break the complete system across supported demo machines and repair blockers | Full demo survives worker loss, bad input, denied approval, and unavailable evidence |
| 12 | Aditya | Entire team owns rehearsal, video, and presentation stations | Freeze code, licences, artifacts, instructions, video, and presentation | Three clean rehearsals pass; no unverified capability appears in the pitch |

## Definition of done for every implementation task

- The task's real caller and shared contract are used; no parallel mock path is
  sold as implementation.
- Trust-boundary inputs are validated and failures are visible.
- Non-trivial logic leaves the smallest runnable regression check.
- The implementer reports exact changed paths and commands actually run.
- The reviewer inspects the current combined diff and reruns only authorised
  checks needed for the claim.
- Source, pinned version or commit, licence, network behaviour, and material
  changes are recorded for reused open-source components.
- Runtime evidence is labelled `prototyped` or `verified` only after it is
  observed on the named device.

## Deliberately excluded from the sprint

- model sharding or pooled VRAM;
- training or fine-tuning;
- a generic multi-agent or visual workflow builder;
- multi-node or highly available Kubernetes, Helm, an operator, a service mesh,
  Redis Cluster, another message broker, or a custom model runtime;
- production multi-user IAM, high availability, or coordinator transfer;
- voice, PPT, Excel, and broad P&ID support before the two signature workflows
  and distributed proof are stable;
- perfect installers for every operating system.

Each exclusion that the problem statement names is recorded against its source
line in [problem-statement coverage](docs/evaluation.md#11-problem-statement-coverage).
Exclusion means excluded from the five-day sprint, not abandoned: multilingual
and voice work is FR-019 in the finals scope.

Add an excluded item only after the current day's gate passes and Aditya accepts
the resulting risk to the frozen demo.
