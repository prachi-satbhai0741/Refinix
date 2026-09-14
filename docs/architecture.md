# Architecture

## Status and authority

This document owns the architecture under [prd.md](prd.md). The production
direction is accepted for planning; new components and migrations below are
not implemented or qualified merely by appearing here. See the
[current source snapshot](evaluation.md#current-status) and
[implementation gates](../tasks.md#numbered-execution-tasks).

## 1. System shape

Refinix is the harness: the existing context manager, workflow runner, policy,
job state, routing, runtime calls, tools and validators behind one desktop UI.
Preserve Chat with document workflows, the IDE-style Code surface, Settings and
the right-hand job status card. A generic agent framework is not a prerequisite.

    Chat / documents ──┐
    Code ──────────────┼──> Refinix local service and workspace
    Settings ──────────┘       │
                               ├── context, retrieval, workflows and policy
                               ├── model selection and device scheduling
                               ├── runtime, tools and validators
                               └── durable jobs, artifacts and visible events
                                            │
                                 this device / trusted peer / private server

The production desktop package includes an app-managed execution agent so each
supported OS can both request and contribute work. This is a change from the
current macOS bundle, which packages the coordinator but excludes the worker.

## 2. Installation and runtime responsibilities

| Responsibility | Authority |
|---|---|
| Workspace coordinator | Owns that workspace's chats, selected files, jobs, approvals and final writes |
| Execution agent | Accepts permitted bounded work locally or from paired workspaces; enforces capacity and limits |
| Organisation service | Manages authenticated users, authorised compute and explicitly managed shared corpora |
| Optional Kubernetes backend | Operates managed services and sandbox Jobs behind the same application contract |

These are runtime responsibilities, never permanent OS assignments. Every
supported Windows, macOS and Linux installation can participate; an all-Mac or
all-Windows peer group must not require an Ubuntu host. Only an execution target
needs the required model and tools installed. A remote-only client can skip local
models and must accurately show its offline-without-peers limitations.

Installers package the application, language runtime, qualified inference engine
and required libraries for each supported OS/architecture. The model manager
handles selected model downloads or verified offline imports. Users should not
need terminals, package managers, Kubernetes or certificate commands. Signing,
OS permissions, drivers and any sandbox virtualisation prerequisites require
platform-specific qualification and guided setup; they cannot be wished away.

Pairing never merges workspaces. A device may coordinate its own jobs while
serving permitted jobs from several peers, with receiver-side admission across
all requesters. Use the existing coordinator as each workspace's scheduler;
a new global cluster leader or leader-election system is not required. Workspace
transfer and high-availability failover remain separate future work.

### Discovery and participation

Settings → Connect lists reachable Refinix devices on the local network in a
radar-style view. This depicts discovery, not measured physical distance. Devices
have distinct IP addresses; shared Wi-Fi does not guarantee reachability when
client isolation or firewalls intervene. Evaluate local mDNS discovery using
[python-zeroconf](https://github.com/python-zeroconf/python-zeroconf), with a guided
address/pairing-code fallback. Discovery grants no trust and advertises no private
prompts, corpus contents or credentials.

Pairing requires visible confirmation, authenticated encrypted traffic, revocable
scoped credentials and compatible protocol versions. The receiver controls sharing,
resource limits and cancellation, and sees the requesting device and task type.
Personal pairing does not require an organisation administrator; managed operation
adds administrator policy without silently enrolling employee devices.

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

Reuse named workflows and typed steps. Each defines inputs, tools, output schema,
validation, authority, cancellation and retry policy. Keep the original request
and separate per-chat context throughout. Prefer running a whole task on one
eligible device; split bounded steps only for a useful capability or policy reason.
Models receive selected inputs and return validated outputs, not shared memory.

### Local retrieval (RAG)

Keep SQLite FTS5 lexical search and qualify semantic retrieval alongside it:

1. Import explicitly selected files or an authorised managed corpus.
2. Extract text; invoke qualified OCR/vision for scans and retain page metadata.
3. Chunk with source hashes, document versions and access scope.
4. Create local embeddings and combine semantic results with lexical matches.
5. Pass only relevant authorised passages within the selected model's context.
6. Validate citation references; report missing or insufficient evidence.

Qwen3-Embedding-0.6B and an embedded SQLite vector extension are candidates in
[the catalogue](model-catalog.md#8-runtime-strategy), not installed dependencies.
Embedding models retrieve passages; the generation model answers using them.
New documents require indexing, not retraining the generation model. Changing
embedding model/version requires rebuilding the affected vector index. Source
updates, access revocation and deletion must invalidate stale retrieval results.
Reranking is optional only after retrieval evaluation shows a need.

Personal corpora stay with their workspace. An organisation may explicitly host
its own corpus/index service; check user and document permissions before retrieval
and again before passing context to an allowed execution device. Shared corpus
storage does not transfer ownership of personal chats.

### Corpus and personalisation boundaries

Keep three stores logically distinct: user preferences/instructions; authorised
reference documents with derived retrieval indexes; and explicitly approved
training examples. Indexing a document does not authorise training on it. Extraction,
embedding, source and access-policy versions govern index/cache validity. A source
update invalidates affected derived entries; retain or rebuild only authorised data.

The context manager selects relevant instructions, memory and retrieved passages
within the selected model's budget. Neither a file on disk nor a retained KV cache
teaches the model permanent knowledge. Models cannot rewrite their own authority.
Start with memory and RAG; [optional model adaptation](model-catalog.md#11-personalisation-and-optional-model-adaptation)
is separate from ordinary conversation execution.

### 3.4 Policy and approval gate

Every action is classified by the coordinator as:

- automatic within an approved boundary;
- approval required before execution or final write;
- denied.

The worker enforces a second boundary and rejects work outside the signed job
contract. Worker output cannot grant itself more authority.

### 3.5 Router and scheduler

Select a **model/device pair**, not just a model or the fastest GPU. Current
source selects stored workflow models and one active paired worker; fleet ranking
and capacity reservations are new work, not existing behaviour.

1. Identify task requirements from the selected workflow, prompt and attachments.
   Deterministic rules suffice for clear tasks; any later model-assisted classifier
   produces constrained labels and cannot change permissions.
2. Apply hard filters: user target choice, trust, data policy, protocol/runtime
   compatibility, installed model/tool capability, health, context and memory fit.
3. Rank eligible pairs using task-specific measured quality and estimated completion
   time: queue + input transfer + model loading + inference/tool execution. Account
   for power preference, memory pressure and reliable thermal information. Missing
   measurements remain estimates; a loaded model is a preference, not an override
   of quality or safety requirements.
4. Reserve capacity at the receiving agent before dispatch. The receiver admits
   work across all requesters atomically, rejects stale/over-capacity reservations
   and expires abandoned reservations. Queue or reselect within authorised scope.
5. Persist the chosen model, device, concise reason and attempt; update the UI and
   notify the receiver. Release reservations on completion, cancellation or lease
   expiry and reconcile uncertain work before retrying.

For two concurrent chats on three devices, the Code job may reserve the strongest
eligible device; the following general Chat job considers that reservation and
can use another available model/device. Faster hardware is not always the fastest
completion. The scheduler reacts to submitted work; it cannot predict future
prompts or promise a globally optimal result. Deterministic tie-breaking and
stable queues prevent repeated route switching.

Whole tasks or bounded steps move between devices. There is no model sharding,
pooled VRAM, or duplicate full-model execution intended to accelerate one answer.
User-pinned targets never silently change. Auto fallback stays within the granted
data and execution policy; ambiguous tool execution must reconcile before retry.

### 3.6 Runtime adapter

Ollama remains the current runtime. Qualify a pinned upstream **llama.cpp
llama-server** as the preferred bundled engine for supported models. The local
service owns its lifecycle and uses loopback requests; it handles the same model
selection, streaming, cancellation, context, structured outputs and health contract.
This choice aims to remove manual runtime setup; it does not claim superior quality
or speed before measurement.

Use one qualified default engine per supported profile. Do not force users to
install both engines or migrate model stores before parity and rollback are proven.
Keep an existing adapter only for a real supported need. GGUF is a format, not a
promise that every architecture, quantisation or vision projector works with every
build. Future voice or image-generation packs may need different engines.

Refinix already supplies the application harness. DeepSeek Harness or another
agent framework is not adopted: qualify a specific missing capability and offline,
permission and maintenance fit before replacing any existing path.

### KV cache and runtime resource policy

The inference engine owns KV-cache allocation and other model-specific inference
state; Refinix owns budgets, admission, lifecycle and evidence. Do not implement a
custom cache allocator, PagedAttention kernel or cross-device KV migration.

- Budget weights, context-dependent cache/state, runtime buffers and safety
  headroom together. Use backend/model measurements rather than one universal
  per-token formula. Receiver admission accounts for concurrent reservations.
- Bound input/output context and concurrency. Select relevant history/RAG rather
  than silently deleting stored history to fit memory. Preserve truncation or
  summary provenance; a loaded model is not the same as a retained conversation.
- Reuse compatible prefixes only where the engine supports it and the model,
  adapter, token prefix, configuration and privacy scope match. Default to isolated
  user/workspace cache scopes; no private cross-user reuse or prompt-bearing debug
  endpoints. An instruction/adapter change must not reuse incompatible state.
- Define idle eviction, cancellation cleanup, model unload and memory-pressure
  handling. Reconcile live attempts before releasing their capacity. Cache persistence
  to disk is disabled by default; supported opt-in persistence needs access control
  and retention. Do not claim secure erasure merely because a slot was released.
- Test native prefix reuse, cache quantisation, batching and attention optimisations
  individually for supported builds. Enable only after correctness, peak memory,
  latency and concurrency evidence. PagedAttention is an engine-level option,
  potentially useful for server workloads, not a mandatory app dependency.

[llama.cpp server controls](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
and [vLLM PagedAttention](https://docs.vllm.ai/en/latest/design/paged_attention/)
are upstream references, not evidence of enabled settings in this prototype.

### 3.7 Tool runner and validators

Tools operate on explicit inputs and bounded workspaces. Validators are
workflow-specific:

- code: allowed paths, patch applicability, command, output, and exit status;
- OCR: source hash, page mapping, confidence or uncertainty;
- retrieval: source and page or section citations;
- artifacts: readable output, origin job, and checksum.

## 4. State ownership

The logical ownership below is the target contract; it does not imply a completed
data-directory or database-schema migration.

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

Remote job content follows a documented deletion policy. Compute-only workers
do not retain complete remote workspaces. An explicitly managed organisation
corpus has separate storage and access policy.

### 4.3 Redis coordination state

This section applies to the retained Kubernetes backend, not every desktop.

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

Target layout, not an executed migration: one logical Refinix data root outside
the replaceable app package, resolved through platform-native locations.

| Platform/profile | Target location |
|---|---|
| macOS installed app | `~/Library/Application Support/Refinix/` |
| Linux installed app | `$XDG_DATA_HOME/refinix/`, default `~/.local/share/refinix/` |
| Windows installed app | `%LOCALAPPDATA%/Refinix/` |
| Explicit portable profile | User-selected `.refinix/` directory |

A leading dot is not a cross-platform security or hidden-file guarantee. Use
owner-only permissions where supported and the OS credential store for secrets.
The logical root contains:

    config.toml
    AGENTS.md
    memory.md
    state.db
    audit/events.jsonl
    artifacts/
    jobs/
    model-manifests/
    corpus/
    tmp/

AGENTS.md holds explicit user instructions; memory.md contains curated preferences
and summaries. Structured chats, job/approval state, audit metadata and source/index
references remain in the database. The context manager deliberately selects relevant
content, rather than appending every file to every request. Corpus files are only
explicitly imported/authorised sources. Model manifests reference app- or runtime-owned
weights without duplicating external stores. Temporary job/cache data is not durable
memory; any training dataset/adapter has separate explicit scope and retention.

User instructions and remembered preferences cannot override enforced security or
organisation policy. For conflicting preferences, the current explicit user request
takes precedence within permitted scope, followed by explicit instructions and then
curated memory. Retrieved documents and model outputs are untrusted task data, not
new instructions. Proposing a memory change does not authorise a silent policy edit;
provide inspect/edit/delete controls and record provenance.

### Legacy data migration

The current `.aegisforge` state and previously documented AegisForge platform roots
are compatibility-sensitive. Detect them explicitly; do not rename paths merely
because the repository is renamed. A versioned migration must stop competing writes,
check destination conflicts/free space, take a consistent snapshot, preserve models,
credentials and content, and verify the new store before selecting it. If both roots
exist, ask the owner to select a source rather than merging chats or overwriting data.
Map legacy rules.md to AGENTS.md only when present and after conflict-safe verification.
Keep the old store until the new version passes its startup/data checks; provide an
explicit later cleanup action. Do not run old and new writable stores concurrently.

### Application lifecycle and updates

The app package and durable data have separate ownership. Updates use a staged,
authenticated package and a qualified installer/updater, drain active work and perform
versioned migration/recovery. The app never updates itself by pulling source from
main. Installed peers exchange protocol/capability information before accepting work
across versions. [releases.md](releases.md) owns publication, connected checks, offline
import and rollback; packaging/updater frameworks remain qualification choices.

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

The existing versioned JSON/HTTPS application contract provides:

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

The workspace uses its local execution agent and installed compatible models.
No peer, server, Redis or Kubernetes is required for ordinary local inference.
Sandboxed code execution still needs a qualified platform isolation backend.
Losing peers preserves local state and any capabilities available locally.

### Trusted mesh

Paired application agents exchange authenticated bounded jobs over the LAN.
Windows, macOS and Linux peers use native qualified inference backends and the
same application protocol. Each receiver enforces resources and permissions;
the requesting workspace owns its history and final writes. This profile must
preserve receipts, idempotency, leases, cancellation, event ordering and restart
reconciliation when using a local queue instead of the Redis-backed executor.

### Kubernetes execution profile — alpha

**Retained prototype backend; optional managed deployment in the production
product.** Docker builds OCI images; K3s manages the worker API/executor services,
Service endpoints and short-lived code-validation Jobs; Redis Streams handles
queueing, leases, receipts and progress. SQLite remains canonical workspace state.
Kubernetes schedules Pods; Refinix decides the task's model, data policy and target.

The current deployed design places services on Linux and calls host Ollama via
a guarded bridge. Ordinary generation uses a long-running executor; it does not
create a new model Pod per prompt. Validation Jobs use isolated temporary inputs
and outputs. Preserve this working design and its recorded evidence while the
portable execution profile is qualified; do not remove infrastructure simply
because desktop users should not configure it.

[K3s does not support native Windows nodes](https://docs.k3s.io/faq#does-k3s-support-windows).
[Upstream Kubernetes supports Linux and supported Windows Server workers](https://kubernetes.io/docs/concepts/windows/intro/),
with a Linux control plane. macOS and Windows desktop Linux-container setups use
virtualisation; this does not establish native GPU access or painless installation.
Kubernetes membership is therefore not the cross-platform peer discovery mechanism.

### Private server

The same application job contract targets organisation-managed compute. A single
server need not run Kubernetes; an existing managed cluster may use the retained
backend. Add authenticated users, quotas, data/corpus permissions and administrative
controls before multi-user acceptance. Organisation-hosted corpora are explicitly
managed storage; a compute worker must not silently become a copy of every client's
workspace. This remains private-network operation with no public inference.

## 8. Working technology direction

[TechStack.md](../TechStack.md) distinguishes current components from candidates.
Reuse the Python backend, current HTML/CSS/JavaScript UI and desktop shell,
SQLite state, contracts and validators. No React rewrite, generic plugin system,
new event platform, service mesh or external vector-database service is required.
Platform packaging, inference parity, semantic retrieval and safe sandboxing have
separate qualification gates.

The following pins and observations are **historical prototype records**, not
current installer instructions or a production dependency selection. Later source
and evidence may supersede a status recorded here.

### 8.1 OD-08 — resolved infrastructure pins

Retrieved from upstream on **2026-09-03** for the **Ubuntu worker**
(`linux/amd64`). Every digest below was read from the upstream registry or
release API, not copied from a summary. Nothing here has been pulled, deployed,
or run: these are *pins to use*, not observed runtime evidence.

| Component | Pin | Digest | Licence | Provenance |
|---|---|---|---|---|
| K3s | `v1.36.4+k3s1` (Kubernetes 1.36, released 2026-08-27) | — (installer release, not an image) | Apache-2.0 | `stable` channel at [`update.k3s.io/v1-release/channels`](https://update.k3s.io/v1-release/channels) |
| Redis | `redis:7.2.16` | index `sha256:74566c6910d13ae61e7ce73ebd3127438a1fe805b309b097c323142719ec8a5b`<br>`linux/amd64` `sha256:e17e3a1993da428251cbd88dbdb3de8c8d4007f840d7350eb17a2d8695fa705f` | BSD-3-Clause | Docker Hub `library/redis`; version confirmed against `src/version.h` on the upstream `7.2` branch (`REDIS_VERSION "7.2.16"`) |
| Worker base image | `python:3.13-slim-bookworm` | index `sha256:ed86c82274b3c69b52fb5820f358f0bd7df0b603332063cb5c6e32bd220c3e6e`<br>`linux/amd64` `sha256:2f2e5a876c71a6757f55ec57f2add0225ddaf01c802a33fcc29073943f94d907` | PSF (Python) over Debian 12 packages | Docker Hub `library/python` |
| Worker image | `aegisforge-worker:c04` | manifest `sha256:a1eb434c91ff5e51a095ccbdc5becd10e98a099a281302ef68e86b531543a295`<br>config `sha256:4d9c91892fc813c846f08a42fa17dde870b0a35f4e969431522059738dd96b5f` | MIT/Apache/PSF via `requirements.lock` and the base image | **Built on the Ubuntu worker 2026-09-04**, `linux/amd64`, 11 layers, 52 in-image checks passing under `--network=none`. This is the digest C05 pins. |

Compatibility notes:

- **7.2.16 is the newest 7.2 patch**, and 7.2 is the last Redis line under
  BSD-3-Clause; 7.4 moved to RSALv2/SSPLv1. Staying on 7.2.x is a licence
  decision, so the pin must not drift upward without a licence review.
- The floating `redis:7.2` and `redis:7.2-bookworm` tags currently resolve to
  the same index digest as `7.2.16`. **Deploy the digest, not the tag.**
- The `macOS coordinator` has `kubectl` **v1.36.1** and the Ubuntu worker
  reported **v1.36.3** at C02, the same minor as the pinned K3s v1.36.x.
  This is client-version evidence; no cluster was contacted or provisioned.
- Redis and the worker base image share Debian 12 (bookworm), which keeps one
  libc and one CA bundle across the cluster workloads.

**Ports are already fixed by the C01 contract, not reopened here:**
`WORKER_PORT = 8443` and `WORKER_NODE_PORT = 30443` in
[`backend/contracts/v1.py`](../backend/contracts/v1.py), exported through
`export_contract()["transport"]`. C02 does not renegotiate them. What is
outstanding is deployment enforcement: the Ubuntu worker's returned C02 TCP
snapshot showed `127.0.0.1:11434` and `*:8080`, with no listener observed on
8443/30443. Port 8080 was already occupied; do not reuse it there without a
fresh ownership check. C05 must recheck availability and verify actual Service
ports and forwarding rules with Redis unreachable from the LAN. The absence
of a listener proves neither a future bind nor deployment enforcement.

**Not resolved here:** the sandbox image and the built worker digest. Cluster
provisioning and deployment remain C05 work; C04 produces the worker image.
This section pins inputs only.

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
