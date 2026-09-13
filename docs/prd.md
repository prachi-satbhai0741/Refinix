# Refinix Product Requirements

## Refinix: Private Local Agent Harness

| Field | Value |
|---|---|
| Document version | 3.0 |
| Status | Production direction recorded; implementation and release acceptance remain separate |
| Target | Offline desktop AI workbench; SIH26117 provides the industrial use case |
| Repository / product | refinix / Refinix (formerly AegisForge; GitHub rename pending administrator) |
| Last updated | 2026-09-13 |

This is the product contract. It supersedes earlier prototype-only scope,
fixed device placement, and calendar-based priorities as production requirements.
It does not declare existing code complete, approve a runtime migration, or
establish a verified release. Focused documents own the details below.

## 1. Product definition

Refinix is an installable offline AI workspace for Windows, macOS, and Linux.
A user downloads it from the product website, completes graphical setup, chooses
models with hardware-aware guidance, and uses Chat, Documents, and Code through
one lightweight interface. Users do not manage model servers, dependencies,
queues, certificates, or Kubernetes from a terminal.

The same application supports three execution modes:

| Mode | Product behaviour |
|---|---|
| This device | Supported models and tools execute locally without another computer |
| Trusted devices | Paired Refinix installations automatically share complete jobs according to capability, permission, current load, and measured performance |
| Private server | Desktop clients use an organisation-managed offline server through the same job interface; an administrator controls access and resources |

Any supported OS may request work and contribute compute. A group of only Macs
or only Windows desktops must not require a separate Linux machine. Capability
availability still depends on qualified hardware, runtimes, and sandbox support.

One shared core supports an open-source platform and a specialised commercial
offering. The latter adds customer-specific corpus preparation, governed
workflows, templates, deployment, evaluation, and support. It does not require a
separate codebase or cloud inference. The repository's existing licence remains
in force; publication, licence changes, and commercial packaging are separate
actions, not authorised by this document.

## 2. Problem and intended outcome

Nontechnical users need a reliable private assistant that can reason, work with
documents and images, write code, use bounded local tools, and produce real files.
The product contribution is dependable orchestration, retrieval, installation,
and trusted compute use; it does not require training a foundation model.

The recorded SIH26117 brief requests model selection across task types, bounded
agentic work, local knowledge grounding, real deliverables, sandboxed coding,
multimodal understanding, and observable offline evidence. Trusted desktop
distribution is an additional product feature, not an assumed official mandate.

Use authorised public or synthetic document samples with expected results for
development and demonstrations. Later access to confidential MRPL data is
unconfirmed. Such data, if authorised, stays in the approved local environment.
The official statement and submission terms still require authoritative review;
the repository transcription is not independent confirmation.

## 3. Product surfaces

Preserve the existing UI: Chat with document capabilities, the IDE-style Code
surface, graphical Settings, and the right-side job status card. Documents is a
workflow category; no separate top-level screen or frontend rewrite is required.

| Surface | User intent | Visible result |
|---|---|---|
| Chat / Documents | Ask, reason, understand scans/images, search selected knowledge, generate documents | Answer or artifact, sources, uncertainty, progress |
| Code | Inspect selected project files, propose changes, execute supported checks | Reviewable changes, validation result, approved application of edits |
| Settings / Control Center | Manage models, knowledge, devices, permissions, and installation | Clear capability and connection states |
| Job status card | Understand ongoing work | Model, device, stage, queue/failure state, concise routing reason, cancellation |

Keep pipeline internals out of ordinary interaction. Detailed diagnostics and
evidence are expandable. An optional compact resource panel may show CPU, GPU,
RAM/VRAM and temperature where reliably available; missing readings stay unknown.

## 4. First-run setup

1. Offer platform-specific installers on the website with versions and integrity
   information. Normal operation must not depend on that website.
2. Bundle application dependencies, or provision approved components
   automatically inside explicitly connected setup. Complete offline bundles
   include the dependencies required for their advertised capabilities.
3. Detect OS/architecture, CPU, GPU/backend, memory, free storage, and applicable
   host prerequisites. Explain OS permission, driver, or virtualisation blockers
   through the UI; never silently change host security or claim unsupported fit.
4. Present up to six relevant model recommendations, highest suitability first,
   with Show more and supported advanced model import. Explain source, licence,
   download size, resource estimates, compatibility, and evidence.
5. Let the user choose models and enabled capabilities. Recommendations are not
   compulsory. Warn about slow or marginal configurations; refuse execution on
   known incompatible configurations without preventing eligible remote use.
6. Manage downloads, cancellation, integrity checks, installation, and capability
   self-tests without terminal commands. Preserve existing models and user data
   on failure or update.
7. Open the available capabilities with truthful status.

A local generative model is required for local inference, not for a client using
a trusted server. Only the device executing a task needs its model and tools.
A compatible model may serve several profiles; do not force redundant downloads.
No permanent coordinator/worker identity is chosen during personal installation.

Scores are explained suitability indices out of 100, not probabilities of
correctness. A hardware scan cannot produce an accuracy percentage. Measurement
and ranking rules belong in [model-catalog.md](model-catalog.md#6-onboarding-selection).

## 5. Dynamic compute participation

Each installation can coordinate its own jobs and, with permission, receive jobs
from other installations. No production rule assigns Documents to a Mac or Code
to Linux. Shared-compute roles are unrelated to who implements the software.

Auto selects an eligible model/device combination using task quality evidence,
current capacity, queue wait, transfer cost, model loading, and execution
estimates. Safety and data permissions are hard constraints. Users can override
model, target, and a Balanced/Faster/Higher quality preference within those
constraints.

The required concurrency example is two requests in separate chats, one Code and
one general Chat, with three eligible devices. Placement of the second request
must account for resources reserved by the first. Do not always choose the
strongest GPU or send every request to one configured worker. Receiving workers
admit jobs against capacity across all requesting workspaces.

Settings provides Connect and a radar-style discovery view of discoverable
Refinix installations on the reachable local network. Device discovery does not
measure physical distance or grant trust. Confirm pairing, provide revocation
and pause-sharing controls, and show the receiving owner which device is using
their compute, the task type, and controls to stop work. Do not expose full
prompts in notifications by default.

The requesting workspace retains canonical chats, approvals, and results.
Pairing never merges personal workspaces or grants access to private files.
Organisation access is governed separately from permission to use compute.

Distribution moves complete jobs or bounded workflow steps; it does not pool
VRAM or shard model weights. Prefer keeping a workflow together when compatible;
split steps only for a justified capability need using bounded, validated input.
No unrestricted model-to-model memory or live inference migration is required.

## 6. Product invariants

1. Normal work, discovery, pairing, retrieval, and distributed execution need no
   public Internet or cloud account. Public downloads and updates are explicit.
2. No cloud inference, silent telemetry, analytics, crash upload, background
   update check, or runtime model/dependency download.
3. Inference endpoints bind to loopback; only minimal authenticated encrypted
   Refinix worker endpoints are exposed to the permitted LAN.
4. Canonical state and consequential writes remain under the workspace
   coordinator's recorded policy; workers receive bounded inputs.
5. Tools use confined workspaces and enforce filesystem, CPU, memory, process,
   runtime and output limits. Untrusted code has networking disabled.
6. Discovery, pairing, compute access, and corpus access are separate grants.
7. Models, dependencies, and installers require source, licence, version,
   integrity and compatibility records.
8. Prefer suitable existing components; preserve working contracts and user
   data. Do not replace a framework or runtime merely to change the stack.
9. Planned, implemented, tested, and release-accepted are distinct claims.
   Human approval for actions and engineering verification are different gates.

[security.md](security.md) owns enforcement and confidentiality limits.

## 7. Release scope

Priorities describe outcomes, not dates or implementation assignments.

<a id="71-alpha-p0"></a>
### 7.1 Core: P0

Guided desktop installation; offline Chat/reasoning; document and image
understanding; OCR and cited document generation; bounded coding and sandbox
validation; task-aware model selection; local and trusted-device execution;
capacity-aware concurrency; permission controls; cancellation and recovery.
Distribution is part of the core direction, not optional merely because the
official demonstration can run on one workstation.

<a id="72-finals-target-p1"></a>
### 7.2 Managed deployment: P1

Private-server execution, organisation users and administrators, compute quotas,
separately authorised shared corpora, versioned templates, and customer-specific
workflow evaluation. Server clients use the same UI and need no local copy of a
remote model. A private deployment remains offline.

<a id="73-post-hackathon-p2"></a>
### 7.3 Optional or deferred: P2

Speech input/output, image generation, additional media capabilities, specialised
language packs, employee task assignment, coordinator migration, and high
availability. A radar animation or resource overlay must not displace core
workflow reliability.

## 8. Outcome requirements

Stable IDs are retained; priorities and wording below supersede the old
prototype-only table.

| ID | Requirement | Priority |
|---|---|---|
| FR-001 | Each installation owns a workspace; local operation works when its dependencies are available, while remote-only clients need no local model | P0 |
| FR-002 | Graphical setup bundles/provisions dependencies and verifies enabled capabilities without terminal work | P0 |
| FR-003 | Existing Chat/Documents, Code and Settings use one harness and job system | P0 |
| FR-004 | Local and trusted-worker requests complete without cloud inference | P0 |
| FR-005 | Pairing is explicit, reversible, and never merges canonical state | P0 |
| FR-006 | Automatic task/model/device selection uses capability, policy, load and evidence; choices are visible and overridable | P0 |
| FR-007 | Workers receive bounded context and use assigned workspaces | P0 |
| FR-008 | Actions are automatic, approval-required or denied under explicit policy | P0 |
| FR-009 | Status exposes model, device, progress, validation and evidence honestly | P0 |
| FR-010 | Normal operation has no public network dependency or silent external traffic | P0 |
| FR-011 | Documents support extraction/OCR, retrieval, citations and real file generation | P0 |
| FR-012 | Code supports reviewable proposals and validated sandbox execution before approved canonical writes | P0 |
| FR-013 | Concurrent independent jobs are placed using current capacity across multiple trusted devices | P0 |
| FR-014 | Interrupted attempts and retries cannot cause duplicate canonical writes | P0 |
| FR-015 | Models support explicit connected installation and verified offline import | P0 |
| FR-016 | A private server participates through the common worker interface | P1 |
| FR-017 | Organisation compute and corpus permissions are separate and enforced | P1 |
| FR-018 | Canonical workspace transfer is a separate explicit migration feature | P2 |
| FR-019 | Additional language/voice packs preserve units, identifiers and uncertainty when enabled | P2 |
| FR-020 | Existing Kubernetes execution remains a supported backend profile; it is not required on every desktop | P0 |
| FR-021 | Redis remains ephemeral coordination in that backend; desktop peers need not install it | P0 |
| FR-022 | Supported Windows, macOS and Linux installations can request and receive work without a dedicated Linux member | P0 |
| FR-023 | Recommendations show at most six initial choices, Show more, explained scores and compatibility warnings | P0 |
| FR-024 | Receiving devices expose active remote work and owner controls | P0 |
| FR-025 | Local semantic retrieval uses qualified embeddings alongside exact-term retrieval with source/access boundaries | P0 |
| FR-026 | Published support claims name tested OS versions, architectures, runtimes and capabilities | P0 |

## 9. Non-goals

No model sharding, pooled RAM/VRAM, foundation-model training, cloud inference,
arbitrary executable model imports, employee project-management system, or
unrestricted host execution. No forced frontend rewrite, generic plugin framework,
or replacement of the existing harness without a demonstrated integration benefit.
No guarantee that every model works on every computer, that all GPU drivers or
host restrictions can be bypassed by an installer, or that the strongest GPU
always gives the fastest or most accurate answer.

Kubernetes high availability and automatic coordinator failover are not required
to deliver the three execution modes.

## 10. Success measures

Acceptance is defined in [evaluation.md](evaluation.md#production-acceptance)
and sequenced in [tasks.md](../tasks.md#numbered-execution-tasks). It includes:
clean-machine setup without terminal assistance; usable offline core workflows;
task-aware selection across at least two task types; concurrent three-device
placement; isolated context; cancellation and recovery without duplicate writes;
source-grounded artifacts; and scoped offline evidence.

Availability of code or a successful model answer alone is not release acceptance.

## 11. Open decisions

| ID | Decision / current boundary |
|---|---|
| OD-01 | Independently confirm official problem wording and submission terms; future confidential datasets are not guaranteed |
| OD-02 | Open-source core and specialised paid offering are the direction; current repository licence remains unchanged |
| OD-03 | Ollama is the existing adapter; bundled upstream llama.cpp is the preferred engine candidate, pending parity and packaging qualification |
| OD-04 | Keep current UI and desktop shell; qualify installer formats, native dependencies, signing, and update/rollback for each supported platform |
| OD-05 | Retain Qwen3.5-4B as baseline; qualify coding/OCR specialists and exact artifacts using representative evaluations |
| OD-06 | Preserve prototype pairing; qualify graphical, OS-portable credential storage, discovery, pairing and revocation |
| OD-07 | Add semantic retrieval to the document direction; qualify Qwen3-Embedding-0.6B and embedded vector search before adoption |
| OD-08 | Retain existing Kubernetes/Redis pins and backend evidence; documentation does not upgrade or remove deployed infrastructure |
| OD-09 | Qualify portable sandbox implementations and supported toolchains; no unsafe subprocess fallback |
| OD-10 | Define recommendation-score normalisation, quality datasets, and measurement confidence |
| OD-11 | Qualify multi-worker admission, capacity reporting, fairness and recovery using the shared job contract |
| OD-12 | Define the supported OS/architecture/backend matrix from clean-device evidence |
| OD-13 | Qualify shared-corpus storage, identity, access control and retention for managed deployments |

## 12. Canonical document map

- [architecture.md](architecture.md) — harness, scheduling, nodes, state and protocol
- [workflows.md](workflows.md) — installation, surfaces, connection and task behaviour
- [security.md](security.md) — trust, permissions, sandbox, supply chain and evidence
- [model-catalog.md](model-catalog.md) — models, scoring, provisioning and runtime qualification
- [devicespecifications.md](devicespecifications.md) — historical device measurements
- [evaluation.md](evaluation.md) — current evidence boundary and acceptance criteria
- [../TechStack.md](../TechStack.md) — concrete component choices and candidates
- [../tasks.md](../tasks.md) — outcome-based implementation gates and historical prototype record
- [../CONTRIBUTING.md](../CONTRIBUTING.md) — Git and release contribution rules
