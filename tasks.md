# AegisForge Execution Roadmap

Status: active planning board; every AF task starts as `planned`.

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

## Operating contract

- Aditya and Vedant are the only members with both Claude Pro and Codex Plus.
  Every critical-path build task is therefore owned by one or both of them.
- The other teammates use their available free or student tools for bounded
  work that does not block on premium-agent limits: fixtures, hardware runs,
  manual acceptance, failure drills, measurements, evidence, documentation,
  and demo operation.
- No critical dependency assumes that an unverified Antigravity plan provides
  a particular model, quota, or feature.
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
- Tests, installers, model downloads, migrations, deployments, and live-system
  commands require the permission defined in [AGENTS.md](AGENTS.md).

Task states are `planned`, `in-progress`, `review`, `verified`, or `blocked`.
Only observed acceptance evidence moves a task to `verified`.

## Proposed ownership

Aditya may reassign work without changing the architecture.

| Owner | Role | Required output |
|---|---|---|
| Aditya | Core builder, coordinator, integration owner | Coordinator, application, routing, workflows, proof, and release candidate |
| Vedant | Core builder, model and worker owner | Runtime integration, worker execution, OCR/code adapters, and sandbox integration |
| Sahil | Integration QA and distributed-run operator | State/routing matrices, repeatable pairing and failure drills, measurements |
| Yug | Document-fixture and OCR-evaluation owner | Public scans, page-level ground truth, SOP fixtures, OCR quality report |
| Prachi | Linux sandbox and network-evidence operator | Reproducible sandbox runs, resource/network observations, failure evidence |
| Tanvi | Product acceptance and demo-evidence owner | Surface copy/checklists, manual UI acceptance, Proof Card review, demo pack |

The hardware mapping is a hypothesis until measured; use
[devicespecifications.md](docs/devicespecifications.md) for current evidence.
The named owners must close its six
[hardware checks](docs/devicespecifications.md#still-needed-before-final-model-placement)
before AF-002 begins.

## Internal hackathon: five-day execution

### Day 1 — Freeze contracts and prove the local spine

| ID | State | Build owner | Support and evidence | Task | Depends on | Acceptance gate |
|---|---|---|---|---|---|---|
| AF-001 | planned | Aditya | Sahil lists lifecycle cases and checks event names | Freeze the minimum node, model-manifest, job, event, step-result, approval, and proof contracts already defined in the architecture | — | One versioned contract set is used by the coordinator and worker code; catalogue entries load from valid manifests rather than code changes |
| AF-002 | planned | Vedant | Sahil records the hardware run sheet and measurements | Select one cross-platform local runtime and verify one curated main model on actual hardware | AF-001 | A real prompt streams locally; model source, licence, revision, memory, and latency are recorded |
| AF-003 | planned | Aditya | Sahil prepares expected state transitions and failure cases | Implement the smallest coordinator path: create job, route locally, stream events, persist terminal state | AF-001, AF-002 | Restart-safe job record reaches a truthful terminal state without mocked inference |
| AF-004 | planned | Aditya | Tanvi supplies surface copy and an unavailable-state checklist | Create the thinnest usable Chat, Documents, Code, and Control Center shell over the shared event stream | AF-001 | All four surfaces open and display real coordinator state; unavailable capabilities say unavailable |

Day 1 gate: one real local response streams through the application and leaves
a persisted job, model, device, and timing record.

### Day 2 — Prove real distributed execution

| ID | State | Build owner | Support and evidence | Task | Depends on | Acceptance gate |
|---|---|---|---|---|---|---|
| AF-005 | planned | Aditya + Vedant | Sahil repeats pairing and disconnect on his laptop and records outcomes | Run the same bounded worker service on the Mac and one Windows machine with prototype authenticated pairing | AF-001–AF-003 | Mac sends one real prompt to the worker and streams the result back |
| AF-006 | planned | Aditya | Sahil supplies and executes the routing-scenario matrix | Implement deterministic capability and health routing with an explicit target override | AF-003, AF-005 | Route reason, selected node, selected model, queue state, and fallback reason are visible |
| AF-007 | planned | Aditya | Tanvi performs Control Center acceptance and captures screenshots | Connect paired-node health, model capability, job progress, disconnect, and revoke controls to Control Center | AF-005, AF-006 | Displayed state comes from live worker/coordinator events, not constants |

Day 2 gate: a real Mac -> worker -> Mac inference completes, and disconnecting
the worker leaves the Mac workspace usable.

If real worker streaming has not passed by the end of Day 2, freeze a standalone
demo baseline and move further mesh work behind AF-008–AF-011. Do not present
pairing as working until its acceptance gate passes.

### Day 3 — Complete both signature workflows

| ID | State | Build owner | Support and evidence | Task | Depends on | Acceptance gate |
|---|---|---|---|---|---|---|
| AF-008 | planned | Vedant | Yug curates public scans, page ground truth, and OCR scores | Implement scan rendering plus local OCR/vision extraction with source hash, page mapping, and explicit uncertainty | AF-003 | The public sample scan produces structured, page-linked extraction without fabricated missing values |
| AF-009 | planned | Aditya | Yug prepares the SOP/citation fixture; Tanvi opens and reviews the Word output | Add the minimum local SOP retrieval, cited drafting, Word generation, and artifact validation path | AF-008 | `inspection_report_to_approval_note` returns an openable cited `.docx` with checksum |
| AF-010 | planned | Vedant | Sahil prepares the synthetic repository request and expected validation | Implement bounded repository context and patch generation inside an assigned temporary workspace | AF-003 | `repository_request_to_validated_patch` returns an applicable patch without modifying the canonical repository |
| AF-011 | planned | Vedant | Prachi operates the Linux sandbox and records the enforced boundaries | Execute the approved validation command in a bounded Linux sandbox with networking disabled | AF-010 | Command, stdout, stderr, exit status, limits, and artifact hashes return to the coordinator |

Day 3 gate: the application produces one real Word approval note and one real
validated code patch through the shared job system.

### Day 4 — Run concurrently and prove sovereignty

| ID | State | Build owner | Support and evidence | Task | Depends on | Acceptance gate |
|---|---|---|---|---|---|---|
| AF-012 | planned | Aditya | Sahil executes the concurrency matrix and records timings | Schedule independent Documents and Code steps concurrently on eligible nodes | AF-006, AF-009, AF-011 | Both jobs progress simultaneously and retain separate attempt and artifact state |
| AF-013 | planned | Aditya | Tanvi executes the approval and denial acceptance checklist | Enforce approval before canonical writes and expose the exact action, target, attempt, and decision | AF-003, AF-009, AF-011 | Denial writes nothing; approval performs one bounded final write |
| AF-014 | planned | Aditya | Tanvi checks every Proof Card value against its source and captures the demo evidence | Produce per-job Proof Cards from real model, device, tool, validation, integrity, approval, and network events | AF-012, AF-013 | Every displayed proof value has an identified source and observation window |
| AF-015 | planned | Aditya + Vedant | Prachi operates the Linux enforcement/observer and records interface and time bounds | Block public egress while retaining required trusted-LAN traffic and capture independent observations | AF-005, AF-014 | The real concurrent run completes with zero observed public outbound flow in the named interval |

Day 4 gate: Documents and Code complete concurrently on distributed compute,
with visible routing, approvals, artifacts, and scoped zero-egress evidence.

### Day 5 — Break it, freeze it, and rehearse it

| ID | State | Build owner | Support and evidence | Task | Depends on | Acceptance gate |
|---|---|---|---|---|---|---|
| AF-016 | planned | Aditya + Vedant | Sahil executes the cancellation, disconnect, retry, and fallback drill | Exercise cancellation, worker loss, retry, and local fallback | AF-012 | Failure is recoverable and produces no duplicate canonical write |
| AF-017 | planned | Aditya + Vedant | Every teammate runs assigned fixtures and records named-device measurements | Run the same standalone and distributed fixtures; record cold/warm latency, queue time, RAM/VRAM, and output quality | AF-008–AF-016 | Results are reproducible and slower results are reported honestly |
| AF-018 | planned | Aditya | Codex reviews the integrated source; Tanvi assembles the evidence pack | Review the integrated source, licences, evidence, demo claims, and remaining blockers | AF-017 | Every claimed feature is observed; planned or broken paths are labelled and excluded from the script |
| AF-019 | planned | Aditya + Vedant | The full team operates assigned demo stations and rehearses handoffs | Run the frozen demo from clean start three consecutive times and record one backup demonstration | AF-018 | Three successful runs use the same documented setup and public sample inputs |

Day 5 gate: no feature work remains. Only demo-breaking fixes, evidence repair,
and rehearsal may enter the internal candidate.

## Internal demo order

1. Open the application and show the four surfaces.
2. Show installed models and paired devices in Control Center.
3. Block public Internet and start the named observation window.
4. Start the scanned-report workflow and the code workflow.
5. Show deterministic routing to different eligible nodes.
6. Open the cited Word artifact and the validated code patch.
7. Approve one bounded write and deny another.
8. Disconnect a non-critical worker and show safe local continuity or requeue.
9. Open both Proof Cards and end the observation window.

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
- Kubernetes, a message broker, or a custom model runtime;
- production multi-user IAM, high availability, or coordinator transfer;
- voice, PPT, Excel, and broad P&ID support before the two signature workflows
  and distributed proof are stable;
- perfect installers for every operating system.

Add an excluded item only after the current day's gate passes and Aditya accepts
the resulting risk to the frozen demo.
