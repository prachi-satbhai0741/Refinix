# Architecture

## Status and authority

This document owns the implementation shape allowed by
[prd.md](prd.md). It is a review draft, not verified runtime evidence.

## 1. System shape

Refinix is one local agent harness with several user-facing workflow
surfaces. The desktop interface and headless worker use the same local service
and contracts.

    Chat ─────────┐
    Documents ────┼──> Local harness
    Code ─────────┘       │
                          ├── context and memory
    Control Center ────────├── workflow runner
                          ├── policy and approval gate
                          ├── router and scheduler
                          ├── runtime and tool adapters
                          ├── validators
                          └── events, audit, and proof
                                   │
                       ┌───────────┼───────────┐
                       │           │           │
                   this device  paired node  private server

The interface does not contain separate Chat, OCR, and Code backends. Each
surface submits a typed job or workflow to the same harness.

## 2. Installation and runtime responsibilities

Every interactive installation:

- creates a local node identity;
- creates and owns a local workspace;
- can run supported work locally;
- can invite and use trusted compute;
- can explicitly accept bounded work from a trusted workspace;
- can stop participating without losing its local state.

Coordinator, worker, and server are dynamic responsibilities:

| Responsibility | Meaning |
|---|---|
| Workspace coordinator | Owns canonical chats, rules, files, jobs, approvals, and artifacts for one workspace |
| Local worker | Executes an eligible job for its own coordinator |
| Paired worker | Accepts bounded jobs from a trusted remote coordinator |
| Private-server worker | Runs the same worker service headlessly on organisation-managed compute |

An installation may coordinate its own workspace while acting as a worker for
one explicitly paired remote workspace. The prototype may limit a node to one
active remote pairing at a time. Multi-workspace concurrency is P2.

Pairing does not copy, merge, replace, or promote a local workspace. Coordinator
transfer is a separate P2 feature because it requires explicit state migration,
conflict handling, and rollback.

## 3. Harness components

### 3.1 Local service

The local service is the durable boundary behind the desktop interface. It:

- starts and stops local components;
- owns workspace and job state;
- exposes a loopback-only UI API;
- coordinates pairing and worker communication;
- invokes existing local model runtimes;
- emits one event stream consumed by the task surfaces and Control Center.

The service must remain usable without the desktop shell so the same worker can
run headlessly on a private server.

### 3.2 Context and memory

The coordinator owns complete local conversation and source material. A worker
receives a bounded task package containing only:

- the original user request;
- structured task and capability requirements;
- selected recent context or a summary;
- explicitly required files or retrieved passages;
- previous validated step output;
- tool and output contracts;
- integrity metadata and limits.

Models do not share context windows. Workflow output is validated and passed by
the coordinator as typed input to a later step.

### 3.3 Workflow runner

The prototype implements named, fixed workflows rather than a generic agent
graph engine. A workflow owns:

- ordered or dependency-linked steps;
- required capabilities;
- input and output contracts;
- applicable tools;
- validation and approval checkpoints;
- failure and retry policy.

The first workflows are defined in [workflows.md](workflows.md).

### 3.4 Policy and approval gate

Every action is classified by the coordinator as:

- automatic within an approved boundary;
- approval required before execution or final write;
- denied.

The worker enforces a second boundary and rejects work outside the signed job
contract. Worker output cannot grant itself more authority.

### 3.5 Router and scheduler

The router considers:

- user execution choice;
- required capabilities;
- installed and verified model manifests;
- worker trust and application compatibility;
- health, queue length, available memory, and loaded model;
- measured compatibility evidence;
- optional thermal state when reliable.

Prototype routing order:

1. Respect an explicit compatible target.
2. Classify the task from its selected surface and deterministic signals.
3. Exclude untrusted, unhealthy, incompatible, or insufficient nodes.
4. Prefer a compatible already-loaded model.
5. Prefer the shorter queue.
6. Prefer the best measured compatible profile.
7. Fall back to this device or queue with a clear explanation.

Routing assistance from a model may be evaluated later, but it must not replace
the deterministic safety filters.

### 3.6 Runtime adapter

The adapter normalises one approved existing local runtime first. Required
operations are:

- list installed models;
- report runtime and model metadata;
- load or select a model;
- stream generation;
- cancel generation;
- report context limits and health.

Add another runtime only when actual target hardware cannot use the first. Do
not build a universal runtime or downloader.

### 3.7 Tool runner and validators

Tools operate on explicit inputs and bounded workspaces. Validators are
workflow-specific:

- code: allowed paths, patch applicability, command, output, and exit status;
- OCR: source hash, page mapping, confidence or uncertainty;
- retrieval: source and page or section citations;
- artifacts: readable output, origin job, and checksum.

## 4. State ownership

### 4.1 Coordinator state

The workspace coordinator owns:

- chats and curated memory;
- rules and approval decisions;
- job, workflow, and attempt state;
- device registry;
- approved model manifests;
- knowledge indexes;
- selected source material;
- artifacts and audit metadata;
- canonical final-write authority.

### 4.2 Worker state

A paired worker stores only:

- its node identity and trusted relationship;
- runtime, hardware, and capability metadata;
- approved model-manifest references;
- active bounded job state;
- temporary input and output;
- minimum audit metadata needed for reconciliation.

Remote job content follows a documented deletion policy. A worker never stores
the coordinator's full chat history, rules, memory, repository, or knowledge
base.

## 5. Local application data

The application uses one logical data root resolved through platform-native
locations:

| Platform | Default |
|---|---|
| macOS | Library/Application Support/AegisForge inside the user's home |
| Linux | XDG data and config directories |
| Windows | LocalAppData/AegisForge |

A portable developer profile may use a user-selected hidden .aegisforge
directory. The application must not assume that Unix dot directories are hidden
or correctly permissioned on every platform.

Logical contents:

    config.toml
    rules.md
    memory.md
    state.db
    audit/events.jsonl
    artifacts/
    jobs/
    model-manifests/
    tmp/

- rules.md is a user-editable policy and instruction surface.
- memory.md contains curated durable summaries only; raw chats and confidential
  source material are not copied into it automatically.
- state.db stores canonical structured state.
- tmp contains disposable per-job workspaces, not a durable temp.md file.
- model-manifests records provenance and runtime references; existing runtimes
  continue to own their model weights.
- secrets and device credentials use the operating-system credential store, not
  Markdown, logs, or ordinary configuration.

The data root and temporary workspaces must be owner-only where the platform
supports permissions. Backup, export, and deletion behaviour must be explicit.

## 6. Job and workflow contracts

### 6.1 Lifecycle

    created
      -> context_preparing
      -> queued
      -> routing
      -> running
      -> validating
      -> awaiting_approval
      -> completed

Failure paths:

    running -> interrupted -> requeue -> routing
    any active state -> failed
    any active state -> cancelled
    awaiting_approval -> denied

Every workflow, job, step, and attempt has a unique identifier. Completion and
canonical final writes are idempotent.

### 6.2 Minimum envelope

An envelope includes:

- workspace, workflow, job, step, attempt, and chat identifiers;
- original user request;
- task type and required capabilities;
- context and attachment references with hashes;
- allowed tools and resource limits;
- output and validation contracts;
- approval policy reference;
- deadline and cancellation state.

The structured fields assist routing and enforcement; they never replace the
original user request.

### 6.3 Minimum node surface

Exact routes remain a protocol decision, but the capability surface requires:

    pair, confirm, and revoke
    health and capabilities
    create, inspect, stream, and cancel jobs

Use standard authenticated HTTPS or mTLS over the trusted LAN. Do not invent
cryptography or a custom transport.

## 7. Execution topologies

### Standalone

The coordinator routes to its own local worker. Losing every paired node reduces
capacity but does not make the workspace unusable.

### Trusted mesh

The coordinator sends independent complete job steps to paired workers. It may
run unrelated Code and Documents jobs concurrently. This is orchestration, not
model sharding.

### Private server

An organisation-managed server runs the same worker service, advertises
capabilities, and receives bounded jobs. It does not become canonical storage
or introduce a separate user workflow. This is P2 and does not mean public
cloud inference.

## 8. Working technology direction

Current candidates minimise prototype risk:

| Area | Direction | Status |
|---|---|---|
| Local service | Python with FastAPI or equivalent | Candidate |
| One-way job streaming | Server-Sent Events | Candidate |
| Coordinator state | SQLite | Candidate |
| Runtime | One existing local runtime first | Decision required |
| Retrieval | SQLite full-text baseline; semantic index only when proven necessary | Candidate |
| Code isolation | Existing container/runtime sandbox with networking disabled | Platform proof required |
| Desktop shell | Lightweight wrapper around the local service | Decision required after the harness path |
| Checksums | Standard SHA-256 | Settled |

Do not add a message broker, event platform, vector database, generic agent
framework, plugin framework, or multiple runtime adapters before a measured
end-to-end path proves the need.
