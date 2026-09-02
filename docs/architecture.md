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
| Kubernetes worker host | Runs the containerised worker API, executor Pods, and ephemeral Redis coordination for a trusted workspace |

An installation may coordinate its own workspace while acting as a worker for
one explicitly paired remote workspace. The prototype may limit a node to one
active remote pairing at a time. Multi-workspace concurrency is P2.

Pairing does not copy, merge, replace, or promote a local workspace. Coordinator
transfer is a separate P2 feature because it requires explicit state migration,
conflict handling, and rollback.

For the five-day alpha, Prachi's Ubuntu machine is the only Kubernetes host.
It runs a single-node K3s cluster. Docker builds the worker and sandbox images;
K3s runs those OCI images through its CRI-compatible container runtime. The
team does not build a six-laptop Kubernetes cluster during the sprint.

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

Redis reports only ephemeral queue depth, leases, and worker heartbeats. The
router never treats Redis as the authority for completed work, approvals, or
final writes.

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

### 4.3 Redis coordination state

Redis exists to coordinate disposable work between the worker API and executor
Pods. It may hold:

- bounded job and attempt envelopes;
- queue and consumer-group state;
- short leases, heartbeats, cancellation flags, and progress events;
- explicitly safe caches with a size limit and expiry.

It does not hold canonical chats, approvals, model manifests, artifact records,
or final-write authority. The coordinator persists those in SQLite before a job
is dispatched. Redis loss marks active attempts interrupted; the coordinator
decides whether to create a new attempt and requeue it.

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

The alpha freezes one versioned JSON/HTTPS application contract:

    GET    /v1/health
    GET    /v1/capabilities
    POST   /v1/pairing/confirm
    DELETE /v1/pairing/{relationship_id}
    POST   /v1/jobs
    GET    /v1/jobs/{job_id}
    GET    /v1/jobs/{job_id}/events
    DELETE /v1/jobs/{job_id}

The events route uses Server-Sent Events. Every mutating request carries a job
or relationship identifier, authentication, size limits, and an idempotency
key where retry can create duplicate work.

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

### Kubernetes execution profile — five-day alpha

The first mentor-aligned profile is deliberately one cluster on one Linux host:

    Mac coordinator + SQLite
              |
        authenticated HTTPS
              |
    Kubernetes Service (NodePort on trusted LAN)
              |
       worker-api Deployment
              |
        Redis ClusterIP Service
          |               |
    executor Pods    sandbox Job Pods

- A Dockerfile builds the worker image; model weights are never baked into the
  image or committed to the repository.
- A Kubernetes Deployment owns the long-running worker API and executor Pods.
- A Kubernetes Service gives the changing API Pods one stable endpoint. Redis
  has a ClusterIP Service and is never exposed to the LAN.
- Redis Streams provide bounded at-least-once dispatch and progress events.
  SQLite idempotency prevents duplicate canonical writes.
- A short-lived Kubernetes Job runs each code-validation task with an explicit
  deadline and cleanup TTL. It does not receive the Docker socket.
- Models mount read-only from an approved host path or persistent volume. Each
  job receives only a disposable workspace.
- Scaling above one executor replica is a stretch only after the single-Pod
  end-to-end path and retry semantics pass.

This is not a peer-to-peer Kubernetes cluster, production high availability,
or a new control plane for canonical application state.

### Private server

An organisation-managed server runs the same worker service, advertises
capabilities, and receives bounded jobs. It does not become canonical storage
or introduce a separate user workflow. This is P2 and does not mean public
cloud inference.

## 8. Working technology direction

The five-day baseline minimises prototype risk:

| Area | Direction | Status |
|---|---|---|
| Local service and worker API | Python with FastAPI | Alpha decision |
| One-way job streaming | Server-Sent Events | Alpha decision |
| Coordinator state | SQLite | Alpha decision |
| Container image build | Docker with pinned base-image digest | Alpha decision |
| Kubernetes distribution | Single-node K3s on the Ubuntu host | Alpha decision; runtime proof required |
| Kubernetes workloads | Deployments for services; short-lived Jobs for code validation | Alpha decision |
| Shared ephemeral coordination | Redis 7.2.x Streams and expiring keys | Alpha decision; exact image digest required |
| Runtime | One existing local runtime first | Decision required |
| Retrieval | SQLite full-text baseline; semantic index only when proven necessary | Candidate |
| Code isolation | Restricted Kubernetes Job Pod with default-deny egress | Platform proof required |
| Alpha UI | Local HTML/CSS/JavaScript served by the coordinator; desktop wrapper deferred | Alpha decision |
| Checksums | Standard SHA-256 | Settled |

Do not add Helm, an operator, service mesh, Redis Cluster, another event
platform, vector database, generic agent framework, plugin framework, or a
second runtime adapter before a measured end-to-end path proves the need.

Redis 7.2.x is selected for the alpha because it retains the BSD-3-Clause
licence; AF-002 must choose the latest supported 7.2 patch, review its current
security notices, and pin the container digest.
K3s uses a CRI-compatible runtime rather than the removed Kubernetes Docker
shim, while still running the OCI images built with Docker.

## 9. Implementation references

- [Kubernetes workloads](https://kubernetes.io/docs/concepts/workloads/) — Pods,
  Deployments, and Jobs.
- [Kubernetes Service API](https://kubernetes.io/docs/concepts/services-networking/)
  — stable endpoints for changing Pods.
- [K3s quick start](https://docs.k3s.io/quick-start) and
  [networking services](https://docs.k3s.io/networking/networking-services) —
  single-node cluster and the included network-policy controller.
- [Redis Streams](https://redis.io/docs/latest/develop/data-types/streams/) —
  consumer groups, acknowledgements, pending work, and bounded retention.
- [Redis licences](https://redis.io/legal/licenses/) — Redis 7.2.x and earlier
  remain BSD-3-Clause.
- [Redis Open Source version management](https://redis.io/docs/latest/operate/oss_and_stack/install/version-mgmt/)
  — supported releases and maintenance dates.
- [Docker build guidance](https://docs.docker.com/build/building/best-practices/)
  — minimal images and digest pinning.
