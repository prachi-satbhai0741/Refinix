# AegisForge Execution Roadmap

Status: active execution board; tasks advance only with recorded evidence.

The alpha implementation deliberately attempts every P0 outcome plus the signature
workflow and concurrency outcomes currently labelled P1 in the PRD. This is an
aggressive execution target, not a silent change to PRD priority labels.

This file turns the [PRD](docs/prd.md) into an execution order. Product and
security requirements remain owned by the focused documents in
[docs/README.md](docs/README.md); this file owns execution chunks, named human
checkpoints, and integration gates.

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

## Product acceptance

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

Until C09 verifies both signature workflows, a second worker, multilingual
support, voice, scaling, and visual polish remain deferred. If the
complete frozen path does not pass three consecutive rehearsals, it is not the
candidate regardless of how many individual components work.

## Operating contract

Claude builds; Codex reviews the current combined source and observed results.
Anyone may implement any AF task. No agent needs a person's identity to edit
code, and no person has exclusive ownership of a module. Names below identify
human actions on particular devices or acceptance checks, not coding ownership.

- Execute one authorised chunk at a time. Within it, build, review and fix
  confirmed findings without repeatedly asking permission for ordinary coding.
- Stop execution at the first required human action: a missing decision or
  permission, download, installation, host command, pairing, physical operation,
  artifact inspection, or Git publication. Do not bypass it by advancing another
  chunk. A newly discovered human dependency splits the chunk at that point.
- Prepare the exact action and obtain Codex's review before the human performs
  it. The human reports back through their agent or Aditya; verify the result
  before resuming. A message saying "done" alone does not prove a runtime gate.
- Continue only within the authorised scope after the checkpoint is cleared.
  This board is not permission to execute the entire plan. Documentation
  approval does not start runtime implementation or authorise terminal setup.
- Humans can reassign a checkpoint to someone with the required access. Update
  the actual names/device in the handoff; never silently operate another device.
- Keep the shared contract, coordinator authority and task acceptance gates. No
  alternate job schema, authentication scheme, Redis namespace or manifest set.
- Tests and machine operations retain the permissions in [AGENTS.md](AGENTS.md).
  Reuse applicable permissions already granted; do not transfer permission from
  one person's machine/session to another's. Missing permission is a checkpoint.
- Humans publish through [member branch -> dev -> main](CONTRIBUTING.md#the-one-rule).
  Integrate reviewed work when its acceptance and human checkpoints are clear.
  Agents do not publish without authorisation.

Task states remain `planned`, `in-progress`, `review`, `verified`, or `blocked`.
A human dependency records `blocked` plus the exact required action, not a code
failure. Only observed acceptance and requester verification justify `verified`.
The chunk map does not change the AF task states recorded below.

## Human checkpoint handoff

Every stop must contain all of the following in the conversation, ready for
Aditya to relay to the team. Do not create personal task documents.

1. **Who and where:** each person's name, device, OS, shell and working
   directory. If everyone is needed, spell out Aditya, Yug, Sahil, Vedant,
   Prachi and Tanvi. Explain each person's action.
2. **Action and reason:** the exact decision, UI steps or copy-paste commands,
   what they change, and why the current chunk cannot proceed without them.
3. **Setup details:** for downloads/installations, approved source link,
   version/revision, licence, expected integrity value and verification command,
   download/disk requirements and destination. For deployment, pin the actual
   image digest. Give required privileges and rollback/cleanup where applicable.
4. **Return evidence:** exact output, installed path/version/hash or artifact
   observation needed, plus what success and failure look like. Exclude secrets,
   personal documents, credentials and unnecessary machine identifiers.
5. **Resume condition:** the focused check agents will perform with permission,
   remaining human acceptance and the next eligible chunk. Do not unlock later
   work from an unverified setup claim.

Unknown versions, unavailable artifacts or an unmade policy choice are reasons
for a decision checkpoint, not placeholder commands for someone to execute.
Prepare future commands against the actual implementation and current device
inventory. Do not distribute speculative installs now. The first read-only
[inventory commands](docs/devicespecifications.md#checkpoint-c01-read-only-inventory)
are ready for C01; missing tooling must be reported rather than installed there.

## Numbered execution tasks

The **thirteen numbered tasks** below define execution order. Building an image
and reporting its digest must precede reviewing and applying the pinned cluster
deployment. More human dependencies create additional stops; an already
satisfied setup action needs evidence, not a repeated installation.

Execute C01 → C02 → C03 → C04 → C05 → C06 → C07 → C08 → C09 → C10 → C11 →
C12 → C13. The **After** column means the previous task's reviewed work, human
checkpoint and return-evidence checks are all clear. At **Wait**, pause until
the named people return the required evidence. Do not skip ahead while waiting.
Progress depends on these conditions, with no duration limit or delivery date.

**Current scope:** documentation only. No runtime chunk is activated by this
edit. **Next implementation task: C01 — Contracts and prerequisites**, once
authorised. AF-001 remains a draft; its review fixes, pairing decision and
consumer integration are outstanding.
Update this current-scope note when the requester authorises a new chunk; the
note itself never grants permission.

Names use the currently documented devices: Aditya's Mac is the coordinator,
Prachi's Ubuntu device is the candidate single-node K3s host, and Yug's Windows
machine is the current Claude development environment. These placements need
fresh C01 evidence. Sahil's and Vedant's GPU machines and Tanvi's machine are
not automatic extra workers; adding one requires a measured need and a new
named setup checkpoint. Everyone can still build any module.

| Task number and name | After | Claude builds; Codex reviews | Wait: named human action | Verify before continuing |
|---|---|---|---|---|
| C01 — Contracts and prerequisites | — | **AF-001** — Repair output-validator requirements, typed cancellation/interruption reasons, and citation/page payloads; update examples and focused checks. Keep the contract draft until consumers integrate. | **Aditya:** accept reviewed contract changes. **Aditya, Yug, Sahil, Vedant, Prachi, Tanvi:** report the read-only inventory for their own device. | Reviewed contract diff and authorised check results; each device's current inventory or explicit unavailability. Use it to prepare setup choices. No runtime installation here. |
| C02 — Environment setup | C01 cleared | **AF-001–AF-004 preparation** — Prepare exact setup instructions and evidence-backed runtime/model/pairing choices (OD-03/05/06), plus K3s/Redis/base-image pins (OD-08); built-image digests follow C04. | **Aditya and Yug:** confirm the proposed choices with Codex's review. **Aditya:** Mac dependencies/main model. **Yug:** development dependencies on Windows if missing. **Prachi:** approved Ubuntu worker/build dependencies and model files. | Humans supply versions, paths, hashes and setup output. Agents verify compatibility with permitted checks. Only approved required components are installed; no cluster deployment or six-device model rollout. |
| C03 — Local application | C02 cleared | **AF-004, local AF-003 adapter** — Implement coordinator SQLite, local inference, basic Chat/Control Center, streaming and restart reconciliation using the installed runtime. | **Aditya:** start the reviewed local commands, send a request and restart the app. **Tanvi:** inspect UI/history with Aditya; no second installation required. | Real local response and retained job/attempt history after restart; missing measurements display unavailable. Return observations and permitted runtime-check output. |
| C04 — Worker image build | C03 cleared | **AF-003, AF-002 preparation** — Implement the worker/API and Docker build assets against the reviewed contract and pairing policy; prepare exact build and digest-inspection commands. | **Prachi:** run the reviewed image build on Ubuntu and report build output, immutable image digest, architecture and provenance. | Agents inspect the actual build result and prepare a deployment pinned to that digest. Build failure stays in C04; a Dockerfile alone is not image evidence. |
| C05 — Cluster deployment and integration | C04 cleared | **AF-001–AF-004 integration** — Review the pinned K3s/Redis/worker manifests, limits and Service exposure using C04's image evidence. | **Prachi:** provision/apply the reviewed cluster commands. **Aditya:** perform the coordinator acceptance steps supplied for this setup. | Ready Pods, internal-only Redis, one real worker-model response, persisted coordinator metadata and shared-version consumers. Pass the C05 integration gate before C06. |
| C06 — Distributed execution | C05 cleared | **AF-005–AF-007** — Implement Redis dispatch/leases/receipt, routing, SSE replay, cancellation, recovery, preflight and truthful fallback. | **Aditya and Prachi:** connect and explicitly pair Mac/worker, apply reviewed LAN settings, and perform the documented disconnect/cancel exercise. | Actual Mac -> Service -> Redis -> executor -> Mac completion, correct route reason, and usable canonical history after cluster loss. Pass the C06 distributed-execution gate. |
| C07 — Workflow inputs and setup | C06 cleared | **AF-008–AF-011 preparation** — Prepare permitted scan/SOP and synthetic-code fixtures, their checks, and only the additional model/dependency setup the two workflows require. | **Yug:** supply/approve public scan/SOP provenance. **Sahil:** approve the synthetic repository and allowed validation commands. **Aditya:** select coordinator inputs. **Prachi:** install any approved missing worker workflow packages/models. | Source hashes, expected extraction/citation examples, selected repository/base and commands, plus verified installed artifacts. If another device is needed, stop and name its operator before any download. |
| C08 — Documents workflow | C07 cleared | **AF-008–AF-009** — Implement real rendering/OCR, uncertainty, page mapping, local retrieval, cited drafting, DOCX creation and artifact checks. | **Aditya and Tanvi:** open the Word output. **Yug:** compare extracted facts and citations with the approved scan/SOP. | Openable Word output with checksum, resolvable citations and honest missing values. Fix discrepancies before proceeding to Code. |
| C09 — Code workflow | C08 cleared | **AF-010–AF-011** — Implement bounded repository context, patch generation and restricted validation Jobs. Reuse approved images where suitable; a new image needing a build creates another checkpoint before deployment. | **Prachi:** apply reviewed sandbox configuration and run the approved host steps. **Sahil and Aditya:** inspect the patch and validation results on the approved fixture. | Applicable patch, observed approved-command result, enforced limits/network isolation and cleanup; canonical repository unchanged. Pass the C09 signature-workflow gate. |
| C10 — Concurrent workflows and approvals | C09 cleared | **AF-012–AF-014** — Implement concurrent workflows, exact-action approvals, durable final-write recovery and evidence-backed Proof Cards. | **Aditya:** choose the output destination and exercise approve/deny/expiry. **Tanvi:** inspect both workflows and the displayed proof against the observed results. | Concurrent progress with separate attempts/artifacts; denial writes nothing; approval writes once; no inferred health, timing or network measurements. |
| C11 — Offline evidence | C10 cleared | **AF-015** — Prepare reviewed Pod/host network controls, rollback commands and independent observation for the real concurrent run. | **Prachi:** apply Ubuntu/cluster controls. **Aditya:** apply Mac controls. **Sahil:** record the named device/interface/time window using the reviewed observation procedure. | Actual concurrent outputs plus enforcement and observation evidence for the specified scope. Preserve trusted LAN traffic and pass the C11 concurrent/offline gate; absent evidence remains unavailable. |
| C12 — Recovery and measurements | C11 cleared | **AF-016–AF-017** — Prepare bounded failure drills and comparable standalone/distributed measurements; inspect results and repair confirmed recovery defects. | **Aditya and Prachi:** perform reviewed restart/disconnect/Pod/Redis/cluster operations. **Sahil:** record timing, resources, quality and failure outcomes. | Canonical history survives, stale attempts are fenced, no duplicate final writes, and reproducible cold/warm results on named devices. Rerun affected checks after fixes. |
| C13 — Candidate acceptance | C12 cleared | **AF-018–AF-019** — Codex reviews the integrated source/evidence; Claude fixes remaining defects and prepares the frozen demo instructions and claim list. | **Aditya and Yug:** operate three clean-start runs and record a backup. **Prachi:** operate the cluster. **Sahil:** compare results with evidence. **Vedant:** check selected model/runtime provenance. **Tanvi:** inspect artifacts and demo clarity. **Aditya:** accept the candidate and coordinate human Git promotion. | Three successful runs on the same documented setup, backup recording, honest claims, independent review and requester acceptance. This closes the alpha, not the later finals scope. |

The AF rows below retain their dependency and acceptance meaning. For AF-001,
C01 reviews the shared draft, C02 resolves setup/security decisions, and C03–C05
prove its consumers. Dependency preparation may use that reviewed draft; neither
AF-001 nor a dependent integration gate becomes verified before its full evidence
exists. Do not claim a contract freeze from schema checks alone.

## Verification and team explanation

- Before building, name the smallest check that demonstrates the chunk's
  changed behavior. Run it only with the required permission.
- Claude supplies changed paths, exact commands, environment and observed
  results. Codex inspects the combined diff and independently verifies the
  material claims with proportionate authorised checks.
- Reuse valid results tied to the same source/environment. Rerun checks affected
  by changes; broaden only for a shared-boundary risk or a required gate. Do not
  repeat a full suite after every edit or add CI triggers to police each chunk.
- Exercise the relevant end-to-end path at each task acceptance gate and the
  three final rehearsals. Contract tests cannot replace model, device, sandbox,
  approval or network evidence. Tests reduce risk; they do not guarantee perfection.
- After **every build and review cycle**, explain to Aditya: **Built** (plain
  language plus one example), **Verified** (observed checks and limits), and
  **Next / Human action** (names, instructions, return evidence and resume
  condition). Review reports use `PASS`, `NEEDS FIX`, or `BLOCKED`; a code-review
  pass does not clear an outstanding human or runtime gate.

## AF implementation requirements

### AF-001–AF-004 — Contracts and local execution

| ID | State | Task | Depends on | Acceptance gate |
|---|---|---|---|---|
| AF-001 | in-progress | Freeze versioned node, job, attempt, event, approval, proof, HTTPS, Redis-key, and idempotency contracts | — | Coordinator, worker, UI, and manifests consume one contract version; schema examples pass the smallest contract check |
| AF-002 | planned | Provision one pinned single-node K3s cluster on the authorised Ubuntu host and deploy pinned Redis 7.2.x behind ClusterIP | AF-001 | Kubernetes reports Ready Redis and worker placeholders; Redis is unreachable from the LAN; versions, digests, and licences are recorded |
| AF-003 | planned | Build the smallest Docker worker image with FastAPI, one runtime adapter, the frozen Service API, and one real model | AF-001, AF-002 | A real prompt streams from a worker Pod; source, licence, revision, image digest, memory, and latency are recorded |
| AF-004 | planned | Implement SQLite-backed coordinator state and the smallest local browser UI over one event stream | AF-001 | A local job reaches a truthful terminal state after restart; Chat and Control Center show live state while unfinished surfaces say unavailable |

AF-001 has a [contract draft with five passing local checks](backend/contracts/README.md).
The OD-06 pairing decision, shared consumers and requester verification remain
open; the C05 application integration gate has not passed.

C05 gate: the pinned Docker image runs in a Ready Kubernetes Pod, one real
response streams through the worker API, and the coordinator persists the job,
attempt, model, device, and timing record. No workflow work starts before this
spine passes.

### AF-005–AF-007 — Distributed execution

| ID | State | Task | Depends on | Acceptance gate |
|---|---|---|---|---|
| AF-005 | planned | Connect the worker API and executor through Redis Streams, leases, cancellation, bounded retention, and cleanup | AF-002, AF-003 | One queued attempt is consumed and acknowledged; a killed consumer leaves recoverable pending work; Redis restart loses no canonical record |
| AF-006 | planned | Route from the Mac coordinator to the Kubernetes Service using capability, health, queue, and explicit-target rules | AF-003–AF-005 | Mac -> authenticated Service -> Redis -> executor -> SSE response completes with visible route reason and local fallback |
| AF-007 | planned | Finish the usable Chat and Control Center slice with guided preflight/self-test, node health, Pod readiness, model, queue, progress, cancel, disconnect, and fallback state | AF-004–AF-006 | A fresh documented setup selects the curated manifest and reaches a real self-test; every displayed value has a source and missing evidence displays unavailable |

C06 gate: a real Mac -> Kubernetes Service -> Redis -> executor Pod -> Mac
inference completes, and stopping the cluster leaves the Mac workspace and its
canonical history usable.

While C06 is unverified, preserve the standalone baseline and repair the
existing distributed path before C07. Infrastructure expansion remains blocked. Do not add nodes, replicas, Helm,
Ingress, another broker, or another runtime to repair an unproven single path.

### AF-008–AF-011 — Signature workflows

| ID | State | Task | Depends on | Acceptance gate |
|---|---|---|---|---|
| AF-008 | planned | Implement scan rendering plus local OCR/vision extraction with source hash, page mapping, and explicit uncertainty through the shared job contract | AF-003, AF-006 | The public sample scan produces structured, page-linked extraction without fabricated missing values |
| AF-009 | planned | Add the minimum local SOP retrieval, cited drafting, Word generation, and artifact validation path | AF-008 | `inspection_report_to_approval_note` returns an openable cited `.docx` with checksum |
| AF-010 | planned | Implement bounded repository context and patch generation inside an assigned temporary workspace | AF-003, AF-006 | `repository_request_to_validated_patch` returns an applicable patch without modifying the canonical repository |
| AF-011 | planned | Run each approved validation command as a short-lived restricted Kubernetes Job Pod | AF-002, AF-010 | Default-deny egress, non-root execution, limits, deadline, cleanup TTL, command output, and artifact hashes are observed; no Docker socket is mounted |

C09 gate: the application produces one real Word approval note and one real
validated code patch through the same Service, Redis, job, event, and approval
contracts.

### AF-012–AF-015 — Concurrency, approvals and offline evidence

| ID | State | Task | Depends on | Acceptance gate |
|---|---|---|---|---|
| AF-012 | planned | Run independent Documents and Code attempts concurrently through separate Redis consumers and Pods | AF-005, AF-009, AF-011 | Both jobs progress simultaneously, retain separate attempt/artifact state, and show honest queue time |
| AF-013 | planned | Enforce approval before canonical writes and bind it to the exact action, target, and attempt | AF-004, AF-009, AF-011 | Denial writes nothing; retry cannot reuse a stale approval; approval performs one bounded final write |
| AF-014 | planned | Produce per-job Proof Cards from SQLite, Redis, Kubernetes, model, validation, integrity, approval, and network evidence | AF-012, AF-013 | Every displayed value has an identified source and observation window; unavailable evidence is not inferred |
| AF-015 | planned | Enforce default-deny Pod egress and host public-egress blocking while retaining authenticated Service traffic | AF-011, AF-014 | The real concurrent run completes with zero observed public outbound flow in the named interval and only documented LAN/cluster flows |

C11 gate: Documents and Code complete concurrently on distributed compute,
with visible Pods, Redis queue state, routing, approvals, artifacts, and scoped
zero-egress evidence.

### AF-016–AF-019 — Recovery and candidate acceptance

| ID | State | Task | Depends on | Acceptance gate |
|---|---|---|---|---|
| AF-016 | planned | Exercise cancellation, executor-Pod loss, Redis restart, cluster loss, retry, and local fallback | AF-012–AF-015 | Failure is recoverable, canonical history survives, and no duplicate final write occurs |
| AF-017 | planned | Run the same standalone and Kubernetes fixtures; record cold/warm latency, queue time, RAM/VRAM, restarts, and output quality | AF-008–AF-016 | Results are reproducible and slower results are reported honestly |
| AF-018 | planned | Review the integrated source, licences, evidence, demo claims, and remaining blockers | AF-017 | Every claimed feature is observed; planned or broken paths are labelled and excluded from the script |
| AF-019 | planned | Run the frozen demo from clean start three consecutive times and record one backup demonstration | AF-018 | Three successful runs use the same documented setup and public sample inputs |

C13 gate: no feature work remains. Only demo-breaking fixes, evidence repair,
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

## Optional work after verified tasks

Proceed to the next eligible task only when its prerequisites and human
checkpoint are clear. C07–C09 remain required after C06. Additional scope needs
requester approval and these prerequisites:

1. **After C09 passes:** add one bounded image-understanding moment and one
   calculation-with-steps inside the approval note.
2. **After C11 passes:** add a second executor replica and prove Redis-backed
   concurrency and Pod-loss recovery on the same cluster.
3. **After C13 passes:** evaluate one additional physical worker or
   the narrow text-only part of FR-019.

Do not unlock multi-node Kubernetes, voice, PPT, Excel, broad P&ID support,
another runtime, or another broker for the alpha candidate.

## After internal selection: finals tasks

This later scope is not activated by the alpha execution pass. Anyone may
implement it. Define named human checkpoints from then-current hardware and
requirements before starting it; do not retain permanent build assignments.

| Task | Focus | Exit gate |
|---:|---|---|
| F01 | Triage judge feedback and freeze the finals claim set | Every accepted change maps to a PRD requirement or observed demo weakness |
| F02 | Harden node identity, pairing credentials, compatibility checks, and revocation | Invalid, expired, and revoked workers are rejected |
| F03 | Harden retries, cancellation, worker-loss recovery, idempotency, and cleanup | Interrupted jobs recover without duplicate final writes or retained temp data |
| F04 | Improve OCR/vision on the fixed public scan set | Page mapping and uncertainty meet the recorded quality threshold |
| F05 | Improve local retrieval, citations, drafting, and Word validation | The approval note is grounded, readable, cited, and reproducible |
| F06 | Improve repository context selection and patch validation | The coding fixture passes without unrestricted repository transfer |
| F07 | Harden the Linux sandbox and verify its actual resource/network boundaries | Escape, network, timeout, process, and filesystem checks fail safely |
| F08 | Complete guided setup, capability detection, manifests, and offline bundle import | A reset installation reaches honest self-test status without silent downloads |
| F09 | Finish Control Center, approval UX, evidence semantics, and Proof Cards | No security or health value is hard-coded or inferred from missing evidence |
| F10 | Benchmark standalone versus distributed cold/warm runs | Same fixtures produce honest performance and quality comparisons |
| F11 | Break the complete system across supported demo machines and repair blockers | Full demo survives worker loss, bad input, denied approval, and unavailable evidence |
| F12 | Freeze code, licences, artifacts, instructions, video, and presentation | Three clean rehearsals pass; no unverified capability appears in the pitch |

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

## Outside the alpha scope

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
Exclusion means excluded from the alpha, not abandoned: multilingual
and voice work is FR-019 in the finals scope.

Add an excluded item only after its prerequisite task passes and Aditya accepts
the resulting risk to the frozen demo.
