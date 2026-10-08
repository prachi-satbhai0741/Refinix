# Refinix Project Contract

## Status and authority

| Field | Value |
|---|---|
| Product | Refinix |
| Repository | `prachi-satbhai0741/Refinix` (public); website `refinix.runs-on.dev` |
| Product target | Installable offline-first desktop AI workbench for Windows, macOS and Linux |
| Current release direction | Refinix Beta 0.1: a tester preview (`0.1.0-preview.N`) published for device testing first, then accepted Beta builds (`0.1.0-beta.N`); further Beta and production work follow |
| Install routes | Ubuntu 24.04 `.deb` (App Center); macOS DMG (first install) with ZIP update payloads; Windows 11 per-user setup. A platform without its required code signing (Developer ID, Authenticode) is shown as unavailable, never published unsigned — see [`releases.md`](releases.md) |
| Preview vs accepted | A tester preview is verified and published so it can be tried on devices; it is not accepted. Accepted builds never receive previews; previews may move on to accepted builds (one ordering key, [`releases.md`](releases.md)) |
| Beta 0.1 scope | Standalone Windows/macOS/Linux application, broad compatible local models, automatic task-to-model routing and user-initiated in-app updates; trusted-device mesh follows after Beta |
| Status | Production direction recorded; implementation, verification and release acceptance remain separate |

This file is the **single current product/architecture/workflow authority** for Refinix. It
consolidates the active requirements that were previously spread across `docs/prd.md`,
`docs/architecture.md`, `docs/workflows.md` and `TechStack.md`.

Those older files remain useful historical/reference snapshots and may contain prototype evidence,
old task labels, exact infrastructure pins or extended rationale. They no longer override this file.

Focused authorities still own specialist detail:

- [`security.md`](security.md) — security, privacy, trust, sandbox, supply chain and sovereignty proof;
- [`model-catalog.md`](model-catalog.md) — model manifests, provenance, provisioning, selection and qualification;
- [`releases.md`](releases.md) — installation packages, publication, GitHub release assets, updates and recovery;
- [`../tasks.md`](../tasks.md) — active implementation phases and sequencing;
- [`evaluation.md`](evaluation.md) — evidence/status observations, not product requirements.

Core documentation is protected by [`../AGENTS.md`](../AGENTS.md): agents must obtain user
permission before changing the product contract or other protected project docs.

A requirement in this file is a target contract. It does not by itself prove source support, runtime
quality, platform compatibility, security or release readiness.

The user's [5 October 2026 direction and follow-up](beta-user-direction-2026-10-05.md) are preserved
verbatim. This Beta reuses existing infrastructure; it is not a programme to certify every model
or build another inference platform. The model, runtime, recommendation and routing
rules below reflect that correction; older measured-only admission designs are not the current
local requirement. Implementation and the owner's next execution plan remain pending.

The current Beta scope is a deliberate release reduction: each advertised desktop profile must be
useful on its own. Discovery, pairing, receiving/dispatching peer jobs, fleet scheduling and private
server execution remain product direction, but are not Beta 0.1 dependencies or acceptance gates.
The mesh requirements below apply when that later capability is implemented and exposed. Preserve
existing distributed code, shared contracts and trust semantics; reuse the current prototype UI,
coordinator, runtime, storage, workflows and packaging rather than starting over.

Agents execute work by the major sections/outcomes in this contract and `tasks.md`. Complete the
authorised section across its affected files and callers, with authorised verification, without
further task tiers or delegation. Checklist steps are implementation aids, not separate assignments.
Use existing code and evidence to avoid missing working capabilities; repository-affecting actions
still follow `AGENTS.md` permissions.

---

# 1. Product definition

Refinix is an installable, offline-first AI workspace for confidential knowledge work. A normal user
should be able to download a platform package, complete graphical setup, choose compatible local
models with hardware-aware guidance, and use Chat/Documents and Code through one lightweight desktop
application.

The customer experience is **open Refinix and use it** after graphical setup. Refinix owns the
application dependencies and inference-engine lifecycle. Normal customers do not pin external runtime
versions, edit qualification records or repeat engineering qualification after an unrelated updater
runs. This is a usability requirement, not a promise of unlimited hardware compatibility or no bugs.

The product should hide infrastructure complexity from ordinary users. Normal use must not require
them to manually manage:

- Python environments;
- model-server commands;
- package managers;
- Redis;
- Kubernetes/K3s;
- certificates/fingerprints;
- worker queues;
- source checkouts.

Refinix's contribution is not training a foundation model. It is the **harness** around qualified
open-weight models: installation, context, retrieval, bounded tools, workflow orchestration,
model/device routing, approvals, trusted local compute, recovery and inspectable evidence.

The same core supports an open-source platform and a specialised commercial offering. A commercial
version may add customer-specific corpus preparation, governed workflows, templates, deployment,
evaluation and support without requiring cloud inference or a separate product architecture.

---

# 2. Problem and intended outcome

Industrial and public-sector organisations handle sensitive work such as:

- approval notes and internal correspondence;
- board presentations and spreadsheets;
- engineering calculations;
- internal tooling/code;
- inspection reports, scans, drawings, photographs and P&IDs;
- manuals, SOPs, vendor information, financial data and unreleased designs.

Public AI assistants may be useful, but moving confidential inputs to third-party services can
conflict with policy and creates a data-handling risk. A useful local alternative must do more than
produce chat text.

Refinix therefore targets:

1. self-hosted/offline operation with no public-cloud inference during normal work;
2. multiple open-weight models rather than a permanent single-model lock-in;
3. task-aware model and device selection;
4. bounded agentic execution with local tools and validation;
5. multimodal document/image understanding;
6. real deliverables such as Word/Excel/PDF/code rather than only chat transcripts;
7. local organisational grounding with traceable citations;
8. human authority over consequential actions;
9. visible, observable offline evidence of where and how a job ran;
10. trusted local compute participation without giving workers ownership of the user's workspace.

Use authorised public or synthetic data for development and demonstrations. Access to confidential
MRPL data is not assumed or required by this product contract.

---

# 3. Product surfaces and UX

Preserve the existing product shape rather than rebuilding the interface around infrastructure.

| Surface | Purpose |
|---|---|
| **Chat / Documents** | General reasoning, selected local knowledge, scans/images, document workflows and generated artifacts |
| **Code** | Selected repository/folder context, reviewable proposed changes, supported validation and approved application of edits |
| **Settings / Control Center** | Models, knowledge, devices, permissions, installation/update state, jobs, evidence and health |
| **Job status card** | Current model/device, stage, progress, queue/failure state, concise routing reason, cancellation and approvals |

Documents is a workflow/capability inside the Chat experience, not a mandatory separate top-level
screen. Preserve the current IDE-style Code surface and existing Settings/status patterns.

Ordinary users should see outcomes and understandable status, not Redis consumer groups, Pod names,
certificate commands or internal queue mechanics. Detailed diagnostics and proof/evidence may be
expandable.

An optional compact resource view may show CPU, GPU, RAM/VRAM, battery and temperature where those
values can be obtained reliably. Missing sensor data must be shown as unavailable/unknown, never
fabricated as zero.

Each task exposes two independent choices:

| Choice | Options |
|---|---|
| Work surface | Chat/Documents or Code |
| Execution target | Auto, this device, trusted devices, or a specific compatible paired device |

For Beta 0.1, execution stays on **this device**. Automatic local model choice is required and uses
installed compatible candidates, task needs and available capacity; team measurements are not a
prerequisite. Hide or clearly mark future peer/server controls unavailable; no normal
reviewer workflow may require pairing or a second computer. Do not expose an unfinished control as
functional merely because its source or UI already exists.

The user may also select compatible model preferences and a Balanced/Faster/Higher-quality
preference where supported. Safety/data policy remains a hard constraint.

---

# 4. Installation and first-run setup

## 4.1 Distribution goal

The website should offer platform-specific installers/packages for each supported OS/architecture with version and integrity
information. Normal product operation must not depend on the website remaining reachable.

Installers should bundle or graphically provision qualified application dependencies. Complete
offline bundles may include the dependencies required for their advertised capability set.

Ordinary users should not need terminal/package-manager/container/certificate setup. Unavoidable OS
permissions, drivers, virtualisation or sandbox prerequisites must be explained clearly rather than
silently changed or hidden.

## 4.2 Initial device establishment

On first launch, Refinix should establish the installation. Refinix creates a unique local node identity and should:

- persist that unique local node identity;
- create an empty local workspace;
- choose the platform-native application-data location;
- start only required loopback-bound local services;
- detect OS/architecture, CPU, supported GPU/backend, memory and free storage;
- detect supported existing runtimes where applicable;
- report unsupported prerequisites truthfully.

There is no permanent onboarding choice such as "Coordinator", "Worker", "Join workspace" or
"Server". These are runtime responsibilities, not permanent installation identities.

<a id="43-model-selection-during-setup"></a>
## 4.3 Model library and hardware recommendations

Show up to six initial recommendations, then **Show more**, upstream model discovery/downloads and
compatible advanced/offline imports. Recommendations are not the full library or an allowlist.
Qwen, Gemma, GLM, DeepSeek and GPT-OSS are examples, not exclusive choices. Reuse publisher/runtime
metadata, model cards and published evaluations rather than measuring every model in Refinix.

When Ollama is present, list its existing local models through its official API and run them through
Ollama without copying weights. Users may also browse/download Refinix-managed llama.cpp assets.
Without Ollama, offer the managed path directly. Show source and runtime on each entry, including
separate Ollama and managed copies of the same family. Select the backend internally from model
origin; no mandatory technical runtime chooser, second runtime install or repeated weight download.

Show, when known, publisher/source, licence, revision, format/quantization, size, runtime requirements,
capabilities and evidence origin. Hugging Face hosting is not universal certification. Prefer official
publisher artifacts; identify the publisher/converter when compatible quantized files come from a
third party. Downloads use recorded upstream sources and appropriate integrity verification.

<a id="431-reviewed-hardware-and-capability-presets"></a>
### 4.3.1 Lightweight hardware recommendations

Reuse current OS/architecture, CPU, RAM/unified memory, GPU/backend, obtainable VRAM and free-disk
facts with published requirements and lightweight estimates. Do not run startup benchmarks or build
a custom optimizer. Device brands are labels, not eligibility keys. Missing sensor data is unknown.
Published evidence and estimates must not be presented as Refinix measurements or model accuracy.

Users may choose larger or different models and override recommendations. Fit warnings guide users;
missing team measurements or an unmatched preset alone do not block downloads or local use. Explain
actual unsupported formats/capabilities, insufficient disk or failed resource admission. Downloading
a model does not imply it fits this computer or supports every workflow. Ordinary Beta remains local;
do not invent a peer fallback to conceal a limitation.

Recommended settings may include context/output budgets, quantization, backend/offload and
concurrency. Reuse upstream allocation/scheduling features and existing helpers. Check changing
capacity at use time; no need to own every laptop or load a 120B model on the available Mac to list
it. Model evidence does not replace package, sandbox or release evidence.

## 4.4 Capabilities

Compatible local models on either runtime may serve Chat, Documents and Code. Additional capabilities
require their real dependencies and formats. One model may serve several workflows; do not require
a second download just because an agent profile exists. Automatic assignment selects from installed
compatible models, with optional manual preferences and a visible reason for the choice.

## 4.5 Provisioning and local checks

Before a user-initiated download/import, show source, licence/revision, available integrity metadata,
size/storage needs, progress/cancellation and relevant prerequisites. No silent downloads. Connected
setup ends before normal offline inference; offline imports use the same source/integrity handling.
Preserve existing models, partial-download recovery and user data.

Establish runtime health/locality and use bounded capability checks or normal task execution to
report what actually works. Local checks record only their observed result, not general quality.
Do not require synthetic benchmarking, an exact team-measured profile or manual qualification before
each ordinary model/version can be used. Preserve parsing, grounding, approvals, file scope, backups,
resource bounds and safe tool execution. An unsupported capability fails with a specific explanation.

Customers do not create runtime profiles or maintain exact measured versions. Runtime-start/update
interactions must remain graphical and respect user authority; these requirements do not authorize
silent host changes. Remote-only client setup remains a post-Beta path with its own evidence.


---

# 5. Persistent model management

First-run setup does **not** freeze the model set. **Settings -> Models** remains available for the
installation's lifetime.

The same catalogue lifecycle should support onboarding and later management:

- distinguish installed models from supported not-installed choices;
- show exact manifest/provenance/capability/profile information;
- distinguish measured/estimated/unverified evidence;
- explicitly download supported compatible models later;
- import approved offline bundles;
- stage/cancel provisioning without corrupting active models;
- verify exact files after download/import;
- offer bounded capability checks and record normal task results without compulsory certification;
- enable/disable model eligibility for new work;
- safely remove models after showing affected capabilities/jobs/defaults;
- preserve shared files used by another model entry;
- recover cleanly from interrupted provisioning/removal;
- refresh recommendations when hardware/runtime/capability state changes.

Installed runtime inventory does not automatically become a trusted supported catalogue entry.
Arbitrary executable model code is not accepted merely because a runtime can see it.
This separates source endorsement from local use; it is not a measured-model allowlist. Existing
user-selected local models remain usable under actual compatibility, locality and task policy.

Multiple agent profiles may reuse one compatible model while keeping different instructions, tools,
policies and validators.

The recommendation catalogue provides starting choices while model discovery and runtime inventory
remain open to compatible alternatives. Source verification, installation, capability support,
upstream evidence and Refinix measurements are separate facts. The team need not measure or manually
approve every model before local selection.

Detailed manifests, evidence states, candidate models and provisioning rules remain in
[`model-catalog.md`](model-catalog.md).

---

# 6. Execution modes and responsibilities

The same application supports three execution modes.

These are the full product modes. Beta 0.1 qualifies **This device**; Trusted devices and Private
server are post-Beta work. Existing remote-only/prototype paths remain retained development evidence,
not substitutes for useful standalone operation on any advertised Beta desktop profile.

| Mode | Behaviour |
|---|---|
| **This device** | Supported models/tools execute locally without another computer |
| **Trusted devices** | Paired Refinix installations exchange bounded complete jobs or validated workflow steps according to capability, trust, policy and capacity |
| **Private server** | Desktop clients use organisation-managed private/offline compute through the same application job contract |

Every supported Windows, macOS and Linux installation may coordinate its own workspace and, when
permitted, receive jobs from others. An all-Mac or all-Windows peer group must not require a special
Ubuntu member for inference.

Only the execution target needs the model/tool required by the task.

### Runtime responsibilities

| Responsibility | Authority |
|---|---|
| **Workspace coordinator** | Owns that workspace's chats, selected sources, jobs, approvals, artifacts and canonical final writes |
| **Execution agent** | Accepts permitted bounded work locally or from paired workspaces; enforces capacity and limits |
| **Organisation service** | Adds authenticated users, authorised compute, quotas and explicitly managed shared corpora |
| **Optional Kubernetes backend** | Runs managed services and isolated validation Jobs behind the same application contract |

These are roles at runtime, not fixed OS assignments.

Pairing never merges workspaces. A worker may serve several requesting workspaces while each
requesting coordinator retains ownership of its own history/results. A new global cluster leader or
leader-election system is not required for the desktop trusted-device model.

Workspace transfer/migration and high-availability coordinator failover are separate later features.

---

# 7. Core system architecture

Refinix is the existing application harness:

```text
Chat / Documents ----\
Code -----------------+--> Refinix local service + workspace
Settings -------------/            |
                                   +-- context, retrieval, workflows, policy
                                   +-- model selection + device scheduling
                                   +-- runtime adapters + bounded tools + validators
                                   +-- durable jobs/artifacts/events
                                                |
                                this device / trusted peer / private server
```

A generic external agent framework is not a prerequisite. Keep the existing harness unless a
specific missing capability and maintenance/security benefit justifies replacement.

## 7.0 Orchestration choice and alternatives

**Current decision: continue with the existing Refinix harness.** Its coordinator, workflow runner,
state, tools and approval paths are the implementation baseline. Orchestration is a software role;
basic routing does not require a separate orchestrator LLM. A model-assisted classifier/planner is
conditional on a demonstrated need and must remain inside the enforced tool/approval boundaries.

Automatic local task-to-model assignment is required for Beta. Use workflow, prompt, attachments,
available capabilities, published evidence and current capacity to choose an appropriate installed
model and its runtime. Users need not choose a model per prompt; manual preferences are optional.
Persist the choice and concise reason. Do not claim perfect choices, invent quality scores or add a
framework merely to enable routing. Never silently alter an in-flight attempt or its permissions.

| Option | Role and evidence | Current decision |
|---|---|---|
| Existing Refinix harness | Reuse current coordinator/workflow/storage code; repair concrete gaps and qualify the integrated behaviour | Continue for the standalone Beta |
| LangGraph | Framework offering stateful workflow persistence, resumable execution and human approval checkpoints; integration cost and benefit in Refinix are unmeasured | Keep as an evaluation option; not adopted or a Beta prerequisite |

The LangGraph capability description comes from its
[official overview](https://docs.langchain.com/oss/python/langgraph/overview), not a Refinix benchmark.
Its workflow runtime is a different responsibility from the inference engine that loads model weights.
Changing orchestration frameworks does not establish inference-version isolation or model compatibility.

Reconsider LangGraph when a specific workflow gap is identified. Compare extending the existing path
with a bounded framework integration for implementation effort, ongoing maintenance, dependency/
licence inventory, offline execution, resource cost and persistence/recovery behaviour. Preserve
coordinator-owned canonical state, exact-action approvals and duplicate-write prevention. No cloud
tracing, telemetry or hosted service may become a hidden prerequisite. Competitor adoption alone does
not prove better economics or UX. No replacement is authorised by recording this option.

## 7.1 Local service

The local service is the durable boundary behind the desktop UI. It should:

- start/stop local components;
- own workspace/job state;
- expose a loopback-only UI API;
- coordinate pairing and worker communication;
- invoke compatible local runtimes under bounded task/data/tool policy;
- emit the event stream used by task surfaces and Control Center.

The service should also remain usable without the desktop shell so the same execution service can
run headlessly in a private-server profile.

## 7.2 Context and memory

The coordinator owns complete local conversation/source material. A worker receives only a **bounded task package** required for its attempt, including as applicable:

- original user request;
- structured task/capability requirements;
- selected recent context or summary;
- explicitly required files/retrieved passages;
- previous validated step output;
- allowed tool/output contracts;
- integrity metadata and limits.

Models do not share unrestricted context windows or persistent "shared memory" with each other.
Validated workflow output is passed as typed input to later steps.

Context selection may omit/trim request context to fit the chosen model, but that does not delete
saved conversation history. Selected/omitted context and relevant metrics should remain inspectable
where practical.

## 7.3 Workflow runner

Use named workflows and typed steps. A workflow defines:

- inputs;
- allowed tools;
- output schema;
- validation;
- action authority;
- cancellation;
- retry/recovery behaviour.

Prefer running a whole workflow on one eligible target when possible. Split a bounded step only when
capability, performance or policy justifies it. Models receive explicit validated inputs rather than
unrestricted access to another model's memory/state.

## 7.4 Policy and approval gate

Every consequential action is classified as:

- automatic inside an approved boundary;
- approval required;
- denied.

The coordinator enforces the primary policy boundary. A worker also rejects work outside the signed/
validated job contract. Worker/model output cannot grant itself additional permissions.

Approvals are tied to the exact action, target and attempt. A retry with materially different input
or output does not inherit an old approval.

## 7.5 Tool runner and validators

Tools operate only on explicit inputs and bounded workspaces. Validators are workflow-specific, for
example:

- Code — allowed paths, patch applicability, command, stdout/stderr, exit status;
- OCR — source hash, page mapping, confidence/uncertainty;
- retrieval — source/version/page/section citation validity;
- artifacts — readable/openable output, origin job and checksum.

---

# 8. Retrieval, corpus and personalisation

## 8.1 Local retrieval

Keep SQLite FTS5 lexical search as the existing baseline and qualify semantic retrieval alongside it.
A target hybrid pipeline is:

1. explicitly import selected files or an authorised managed corpus;
2. extract text, using qualified OCR/vision where required while retaining page/source metadata;
3. chunk with source hash, version and access scope;
4. create local embeddings for semantic retrieval when enabled;
5. combine semantic/lexical results as qualified;
6. pass only relevant authorised passages within the selected model context;
7. validate citations and report insufficient evidence honestly.

Embedding models retrieve passages; the generation model uses retrieved passages. Adding a document
to an index is not model training. Changing the embedding model/version invalidates/rebuilds the
affected vector index.

Source edits/deletion/access revocation must invalidate stale derived entries and caches.

Reranking is optional after retrieval evaluation shows a useful need.

## 8.2 Personal versus organisation corpus

Personal corpora remain with their workspace. A managed organisation may explicitly host a shared
corpus/index service, but compute pairing and corpus access are separate permissions. Check user and
document access before retrieval and before context is passed to an eligible execution target.

## 8.3 Instructions, memory, corpus and training are different stores

Keep logically distinct:

1. explicit user instructions/preferences;
2. curated durable memory/summaries;
3. authorised reference documents and derived indexes;
4. explicitly approved training examples/adapters.

Indexing a document does not authorise training on it. A user correction does not silently start
training. Optional adapters/personalisation require separate scope, storage, evaluation and disable/
revert behaviour.

Retrieved documents and model output are untrusted task data; they do not become authority merely
because their filenames resemble instruction files.

---

# 9. Router, scheduler and trusted mesh execution

The trusted-mesh and fleet scheduling requirements in this section are **post-Beta**. Beta model
selection, capability checks and resource limits apply locally without discovering or reserving peers.

Refinix selects a **model/device pair**, not only a model and not simply the machine with the
strongest GPU.

## 9.1 Routing stages

1. Determine task requirements from workflow, prompt and attachments. Deterministic rules are
   sufficient for obvious classes; any later classifier produces constrained labels and cannot
   change permissions.
2. Apply hard filters:
   - user target choice;
   - relationship trust;
   - data/corpus policy;
   - protocol/runtime compatibility;
   - installed compatible local model/tool capability; exact qualification where separately required
     by later worker admission or an advertised measured capability;
   - target health;
   - context/memory fit.
3. Rank eligible pairs using task-specific evidence and estimated completion cost such as:
   - queue wait;
   - transfer cost;
   - model loading;
   - inference/tool execution;
   - memory pressure;
   - reliable power/thermal information where available.
4. Reserve/admit capacity at the receiving agent across all requesting users/workspaces before dispatch.
5. Persist chosen model, device, concise reason and attempt. Release/reconcile reservations on
   completion, cancellation or expiry.

Missing measurements remain estimates. A model already loaded on a device is a preference, not a
reason to violate quality, policy or memory constraints.

## 9.2 Concurrency

Local Beta supports multiple installed models and jobs. Concurrent inference is permitted where
runtime features and current resources allow it; otherwise reuse queuing/loading/unloading. Do not
impose a universal one-model rule or promise every model can remain resident simultaneously. Manage
Refinix's reservations without stopping unrelated work in externally managed Ollama.

Independent jobs may execute concurrently on different eligible devices. A second job must account
for resources reserved by the first rather than repeatedly selecting one configured worker.

For example, a Code task may reserve a stronger eligible target while a general Chat task uses
another capable device.

The scheduler reacts to submitted work; it cannot predict future prompts or promise a globally
optimal schedule. Stable queues and deterministic tie-breaking should avoid route flapping.

## 9.3 What distribution is not

Refinix distributes complete jobs or bounded validated steps. There is **no model-weight sharding** across ordinary peer devices. It does **not** require:

- pooling RAM/VRAM across ordinary laptops;
- splitting one model's weights across peer devices;
- combining context windows;
- duplicate full-model execution to accelerate one answer;
- live inference-state/KV migration between peer devices.

User-pinned targets never silently change. Auto fallback remains within the user's granted trust,
data and execution policy.

---

# 10. Discovery, pairing and receiver controls

This section governs the deferred post-Beta mesh. Beta does not require discovery, pairing or
receiving remote work; retained prototype paths are not advertised as standalone Beta capabilities.

Settings -> Connect presents reachable Refinix installations on the local network. A radar-style view
may represent reachability but must never claim measured physical distance.

Shared Wi-Fi does not guarantee reachability; client isolation/firewalls may block local discovery.
Local mDNS/zeroconf is a candidate mechanism, with a guided address/pairing-code fallback.

**Discovery grants no trust.** Discovery must not advertise private prompts, corpus contents or
credentials.

Normal product pairing requires:

1. visible identity information;
2. explicit confirmation on both sides;
3. authenticated encrypted traffic using established mechanisms;
4. scoped revocable relationship credentials;
5. compatible protocol/capability negotiation;
6. receiver-side sharing/resource controls.

The normal user should not need to copy certificate fingerprints or run certificate commands.
Prototype certificate-pinning history may remain useful evidence, but product UX must provide guided
OS-portable trust and protected credential storage.

A receiving device should show which trusted user/device is using compute, the task type, relevant
resource use and a stop/cancel control. Do not expose full prompt content in notifications by default.

Pause sharing stops new admission and makes running-job disposition explicit. Revocation prevents
further access and cancels/reconciles affected attempts. Disconnecting/revoking never deletes the
receiver's own workspace.

Personal device sharing needs device-owner consent, not a mandatory organisation administrator.
Managed deployments add administrator policy separately.

---

# 11. Job contract and recovery semantics

Every workflow/job/step/attempt has a unique identifier. Canonical completion/final writes are
idempotent.

A logical lifecycle is:

```text
created
  -> context_preparing
  -> queued
  -> routing
  -> running
  -> validating
  -> awaiting_approval
  -> completed
```

Failure paths include interrupted/requeue, failed, cancelled and denied states.

A minimum job envelope carries, as applicable:

- workspace/workflow/job/step/attempt/chat IDs;
- original user request;
- task type/required capabilities;
- bounded context/attachment references with hashes;
- allowed tools/resource limits;
- output/validation contracts;
- approval policy reference;
- deadline/cancellation state.

Structured fields assist routing/enforcement but never replace the original user request.

The existing application contract includes health/capabilities, pairing, job submission/status,
events and cancellation endpoints over authenticated encrypted LAN communication. Server-Sent Events
may carry progress/events.

A lost response does not prove work never executed. After disconnect/crash, reconcile receipts and
side effects before retrying. Safely repeatable work may receive a new attempt; canonical final writes
must not be duplicated.

---

# 12. State ownership and local data

## 12.1 Coordinator-owned state

The workspace coordinator owns:

- chats and curated memory;
- instructions/rules;
- approval decisions;
- job/workflow/attempt state;
- device registry;
- approved model-manifest references;
- personal knowledge indexes;
- selected sources;
- artifacts/audit metadata;
- canonical final-write authority.

## 12.2 Worker state

A paired worker keeps only what it needs to execute/reconcile bounded work, such as:

- its node identity and trusted relationships;
- runtime/hardware/capability metadata;
- approved model-manifest references;
- active job state;
- temporary inputs/outputs;
- minimum reconciliation/audit metadata.

Compute-only workers do not retain complete remote workspaces. Temporary remote content follows a
documented retention/cleanup policy.

## 12.3 Redis state

Redis applies to the retained managed Kubernetes profile, not ordinary desktop peers. It may hold
bounded queue/attempt envelopes, consumer/pending state, leases, heartbeats, cancellation/progress and
safe bounded caches.

Redis is **not** canonical chat/corpus/approval/model-manifest/artifact/final-write storage. Canonical
state is persisted before dispatch. Redis loss interrupts active attempts; the coordinator decides
what may be retried.

## 12.4 Platform data roots

Target logical durable roots are outside replaceable application packages:

| Platform/profile | Target |
|---|---|
| macOS installed app | `~/Library/Application Support/Refinix/` |
| Linux installed app | `$XDG_DATA_HOME/refinix/`, default `~/.local/share/refinix/` |
| Windows installed app | `%LOCALAPPDATA%/Refinix/` |
| Explicit portable profile | user-selected `.refinix/` directory |

A representative logical root may contain:

```text
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
```

Structured state belongs in the database rather than Markdown. `AGENTS.md` holds explicit user
instructions and `memory.md` curated durable summaries/preferences. Neither may override enforced
security/organisation policy.

Temporary job/cache state is not durable memory. KV caches can contain private context and must obey
workspace/user/model/config compatibility and retention boundaries.

## 12.5 Legacy data migration

Existing `.aegisforge` state and previously used platform roots are compatibility-sensitive. Do not
rename/delete them merely because product/repository naming changes.

A future versioned migration should:

- stop competing writes;
- detect source/destination conflicts and free space;
- take a consistent snapshot;
- preserve models/credentials/content;
- verify the new store before selecting it;
- ask the user which source wins if both old/new stores contain data rather than silently merging;
- retain the old store until the new version passes startup/data checks;
- provide explicit later cleanup.

Do not run two writable canonical stores concurrently.

---

# 13. Runtime and resource policy

<a id="131-ownership-packaging-and-qualification"></a>
## 13.1 Runtime reuse, ownership and evidence

Both existing local Ollama and Refinix-managed upstream llama.cpp are Beta product paths. Reuse the
existing adapters and upstream features. Model origin selects the backend internally. Existing Ollama
assets stay in its store and run through its official API without copying. Reading Ollama's internal
files into llama.cpp or automatically converting/switching those files is not required for Beta.

The managed path supplies a pinned, integrity-verified engine for people who need it. External updates
or executable search paths must not replace its recorded bytes. That ownership boundary does not
prohibit other compatible managed models or the separate Ollama path. Preserve both stores and work.

Local admission uses actual API/format/capability compatibility, health, resources and task/data/tool
policy. Absence of an exact team-measured model/version/device profile is not a general refusal for
either runtime. Reuse upstream evidence and lightweight metadata/installation checks; the team does
not benchmark every model. Measurements remain honestly labelled evidence, never copied to different
combinations or promoted into guarantees. Worker admission and sandbox controls retain their own
contracts. Representative integrated workflow checks remain necessary for advertised app behavior.

A newer Ollama version alone must not disable ordinary work. Refresh relevant version/model/settings
metadata and recommend a normal upstream update when a required feature is missing. Maintain feature
minima and known incompatibility/security exclusions rather than one exact measured-version allowlist.
Recommend current supported upstream releases; an offline installation cannot continuously establish
which release is latest. Do not silently update the host or require developer qualification records.
Managed-engine upgrades retain the authenticated Refinix update/recovery boundary.

Chat, Documents and Code may use compatible local models on either path. Preserve streaming,
cancellation, bounded context, supported reasoning controls, structured parsing, grounding, approvals,
backups and safe tools. Compatibility checks do not establish general answer quality, zero egress,
package acceptance or performance on every computer.

Establish model locality before sending work or checks: loopback Ollama can front cloud inference.
Downloads are explicit connected setup from recorded upstream sources. GGUF or a Hugging Face listing
alone does not establish compatibility with every architecture/quantization/projector. Report real
limitations without turning missing measurements or hardware recommendations into a restriction.

## 13.2 Resource and context policy

The runtime owns KV-cache allocation and model-specific inference state. Refinix owns resource
budgets, admission, lifecycle and evidence. Do not implement a custom cache allocator, custom
PagedAttention kernel or cross-device KV migration for the desktop product.

Budget together:

- model weights;
- context-dependent KV/state;
- runtime buffers;
- concurrent reservations;
- safety headroom.

Bound input/output context and concurrency. Select relevant history/retrieval rather than deleting
saved history to fit memory. Preserve truncation/summary provenance.

Compatible prefix/cache reuse is permitted only when runtime support and model/adapter/token-prefix/
configuration/privacy scope all match. Default to isolated user/workspace scopes. Disk persistence is
disabled by default unless an explicitly qualified path provides access control and retention.

Test batching, prefix reuse, cache quantisation or engine attention optimisations individually before
enabling them. They are optimisations, not correctness requirements.

---

# 14. Agent profiles and workflows

An agent profile combines:

- one compatible model reference;
- profile instructions;
- allowed tools;
- workflow contract;
- action/approval policy;
- output validator.

Initial conceptual profiles:

| Profile | Tools | Validator focus |
|---|---|---|
| General Chat | local retrieval and approved read-only tools | response/citation checks where applicable |
| Document Agent | OCR/vision, retrieval, extraction, document generation | page mapping, uncertainty, citations, artifact integrity |
| Coding Agent | approved repository reads/search, isolated execution | allowed paths, patch applicability, command/output/exit status |

One model may serve multiple profiles. Models do not gain direct arbitrary file/tool/model access;
the harness grants bounded actions.

---

# 15. Chat behaviour

A normal Chat request:

1. opens/continues a conversation;
2. preserves the original request;
3. selects bounded recent context, curated memory and relevant local knowledge;
4. selects an eligible model/device;
5. streams output and visible tool events;
6. validates citations/tool results where used;
7. records response and proof metadata.

A remote-only client retains history and explains when execution requires an available trusted
compute target.

Preserve existing conversation-quality behaviours:

- complete saved history even when a bounded request omits old messages;
- visible context omissions/incomplete replies rather than silent replay with different context;
- explicit continuation of partial output;
- rename/pin/literal-Unicode search without changing conversation identity;
- per-conversation drafts surviving restart/error and clearing only for accepted submission version;
- confirmed deletion and protection against delayed events recreating deleted chats;
- Markdown/text export of the selected saved conversation, excluding drafts/other chats;
- safe Markdown rendering with inert raw HTML and no automatic remote images/fonts/previews;
- readable ordered lists/tables/code and distinction between links and validated citations;
- duplicate-send/IME guards, focus/keyboard accessibility, narrow-screen operation, reduced motion,
  readable contrast and 200% zoom;
- important errors/status must remain visible despite cosmetic UI changes.

Ordinary conversation deletion is not guaranteed secure physical erasure.

---

# 16. Documents workflow

The first fixed document story remains **inspection report -> grounded approval note**.

A target execution:

1. user selects a scan/image/PDF and optional local SOP/reference corpus;
2. coordinator records source hashes and creates the workflow;
3. OCR/vision extracts page-associated content and uncertainty;
4. extraction checks preserve unsupported/inconsistent/unresolved values instead of pretending
   certainty;
5. local retrieval selects relevant authorised SOP passages with page/section metadata;
6. the generation model receives only validated extraction + selected passages needed for drafting;
7. document generator creates a real Word artifact;
8. artifact validation records readability, citations/source linkage, origin job and checksum;
9. user reviews before consequential export/final write.

Co-locate the workflow on one eligible node when practical. Move bounded steps only for capability,
performance or data-policy reasons. Corpus permissions apply before retrieval/context leaves its
storage role.

The system cannot guarantee detection of every hallucinated/fabricated value. Preserve uncertainty
and insufficient-evidence states.

A generic uncited note must not satisfy a request for a source-grounded approval note.

Document platform dependencies are an explicit portability requirement: macOS-specific Quartz/AppKit
paths must not be mistaken for Windows/Linux support. Semantic retrieval improves retrieval but does
not replace portable PDF/image parsing/rendering or artifact writing.

---

# 17. Code workflow

The first fixed Code story remains **repository request -> reviewable validated patch**.

Target flow:

1. user selects an approved repository/folder and describes the change;
2. coordinator identifies the minimum relevant file set;
3. create an isolated temporary workspace;
4. copy/transmit required files with hashes;
5. coding agent prepares a patch only inside the temporary workspace;
6. approved validation runs with networking disabled and bounded resources;
7. return patch, command, stdout, stderr, exit status and artifact hashes;
8. coordinator verifies target paths and patch applicability;
9. user reviews the diff and approves/denies canonical modification;
10. an approved final write occurs exactly once.

Do not transfer the entire repository by default. Workers never directly write the coordinator's
canonical repository.

The current explicitly selected **local Apply/Undo** path remains distinct and labelled as local/non-
sandbox-tested mode. Preserve its approvals/backups. Do not silently call it sandbox validation.

Selection/permission scope must stay clear. Valid selected paths may persist for appropriate
follow-up work in the same project/conversation but file contents and approval bindings must be
refreshed before use. Switching projects must not carry selected paths/permissions across the
boundary.

No unrestricted host-execution fallback is allowed when a qualified sandbox is unavailable. Patch
proposal/review may remain available while validation is shown unavailable/requires an eligible peer.

---

# 18. Action and approval policy

| Action | Behaviour |
|---|---|
| Read explicitly selected files | automatic inside granted scope |
| OCR/retrieval/analysis/draft generation | automatic inside granted scope |
| Write inside assigned temporary workspace | automatic |
| Qualified network-disabled sandbox validation | automatic after the workflow/tool scope is authorised |
| Modify canonical files or persistent organisation data | approval required |
| Export/publish outside the workspace | approval required |
| Enable network access | approval required |
| Pair/revoke devices | approval required |
| Install models/dependencies | approval required |
| Access unselected paths/host secrets/unrestricted execution | denied |
| Contact a public AI service during offline runtime | denied |

Approval records the exact action/target/workflow/job/attempt/actor/timestamp. A denied action ends or
replans that step visibly; it does not become a vague generic failure.

Human approval and engineering verification are different gates. A user approving an action does not
prove model quality or sandbox security; a passing technical check does not grant authority for a
consequential write.

---

# 19. Control Center and status

The Control Center should expose understandable, truthful state for:

- installed/supported models and self-test state;
- hardware/runtime/storage state;
- active/queued/awaiting-approval/failed/completed jobs;
- current model/device/stage/routing reason;
- paired devices, capabilities, heartbeat and revocation;
- receiver-side remote-work notifications/controls;
- connected setup versus offline runtime;
- trusted LAN traffic and public-egress evidence;
- audit events, proof cards, retention/cleanup/export controls.

Do not hard-code healthy/secure/blocked/zero-traffic values. Unknown evidence is unknown.

---

# 20. Failure behaviour

## Model/dependency installation failure

Leave the capability unavailable. Existing working capabilities and workspace data remain usable.
Do not destroy a working model/runtime to complete a failed replacement.

## Worker disconnect

Mark the attempt interrupted and reconcile its receipt/side effects before retry. A lost response is
not proof the worker did nothing. Safely repeatable work may create a new attempt on an authorised
compatible target; canonical final writes remain exactly once.

Pinned/private work is never silently moved to another target.

## Approval denial/expiry

The action does not execute. Keep the job inspectable and allow cancellation/replanning only inside
the same authority.

## Validation failure

Do not promote the result into a validated artifact/canonical write. Show command/output/failure and
bounded retry/replan choices.

## Offline/sovereignty evidence unavailable

Show unavailable/observation-only. Never replace missing evidence with a green "secure" or "zero
egress" state.

---

# 21. Security and sovereignty invariants

Detailed enforcement belongs to [`security.md`](security.md). The following are product-level
non-negotiables.

## 21.1 Offline runtime

Normal work, retrieval, local discovery/pairing and trusted LAN execution require no public Internet
route or cloud account.

During offline runtime there is **no cloud inference** and no hidden public-service dependency:

- no public-cloud inference;
- no silent telemetry/analytics/crash upload;
- no silent background/startup/reconnection update checks;
- no runtime model/dependency download;
- no public DNS requirement for local operation;
- local runtimes stay loopback-bound;
- only required authenticated encrypted worker traffic is exposed to the trusted LAN.

Connected setup/update actions are explicit and separate from the offline evidence window.

## 21.2 Data minimisation

Workers receive only bounded required context/input. Full repositories/corpora/history are not
transferred by default. Compute pairing is not permission to browse arbitrary files or access a
corpus.

A trusted compute host can see the content it executes; transport encryption does not hide prompts
from that host. Sensitive organisation work must use approved compute destinations.

Logs contain metadata by default, not confidential prompt/document payloads.

## 21.3 Filesystem/sandbox

Workers/code tools:

- write only in assigned temporary workspaces;
- reject absolute escape, traversal, hard-link and symlink escape;
- mount only explicit inputs/output locations;
- do not access host secrets/credentials/home directory;
- keep generated code networking disabled by default;
- enforce CPU/memory/runtime/process/filesystem/output limits;
- capture command/stdout/stderr/exit/artifacts;
- clean temporary state at the defined retention boundary.

A container is a possible isolation mechanism, not universal proof. A timed host subprocess is not a
security sandbox. Windows Sandbox cannot be assumed for Windows Home profiles. Unsupported local
sandboxing must remain unavailable rather than fall back to unsafe host execution.

## 21.4 Model/dependency provenance

Accepted components require authoritative source, compatible licence, pinned version/revision,
expected files/hashes, runtime/hardware compatibility evidence, recorded local modifications and no
required silent cloud dependency.

Public availability does not prove licence, safety or compatibility.

## 21.5 Repository content

Never commit:

- model weights;
- generated installers/release binaries;
- signing keys, credentials or tokens;
- private/confidential documents/scans;
- user chats/memory exports/indexes/application databases;
- secret-bearing environment files;
- sensitive packet captures.

Use synthetic or explicitly approved non-sensitive fixtures.

---

# 22. Sovereign Proof Card and evidence semantics

The central sovereignty claim should be inspectable per job rather than presented only as a marketing
badge.

A Proof Card may bind:

- job/attempt/workflow identity;
- selected model/version/manifest;
- selected device;
- routing reason;
- input/output/artifact hashes;
- validation result;
- approvals;
- network enforcement/observation method and time window;
- relevant status/failure metadata.

Distinguish **enforcement** from **observation**:

| Signal | Meaning |
|---|---|
| Public egress policy: enforced | an identified system/network control is active |
| Public outbound flows observed: 0 | the named observer saw no public flow in the stated interval |
| External AI/API calls observed: 0 | no known external inference destination was observed in that interval |
| Blocked attempts: N | the named enforcing layer recorded N blocked attempts |
| Trusted LAN connections: N | allowed local peer traffic, not public egress |

Zero observed traffic does not prove enforcement. Unavailable evidence remains unavailable.

A demonstration evidence window should finish connected provisioning first, identify the enforcing
layer/observer/interfaces/time range, run the real workflow, bind model/device/tool/hash/approval
metadata and produce the Proof Card.

The card reports what was observed; it does not claim universal security or penetration resistance.

---

# 23. Kubernetes, Docker and Redis

The retained Kubernetes/K3s/Redis backend is valid infrastructure for managed compute and restricted
validation Jobs. It is **not** the desktop peer-discovery model and is not required on every laptop.

Current architectural roles:

- Docker — reproducible worker OCI images and dependencies;
- K3s/Kubernetes — managed worker/executor services, Services, resource policies and short-lived
  validation Jobs;
- Redis Streams — disposable dispatch/leases/heartbeats/cancellation/progress coordination;
- SQLite — canonical workspace/job/approval/artifact/audit state on the coordinator;
- local model runtime — loopback-bound generation on the execution host.

Kubernetes decides where its Pods run; Refinix decides task/model/data-policy/device routing.

Ordinary desktop trusted peers should participate through the authenticated Refinix application
protocol and local queue/admission implementation, not by becoming Kubernetes nodes or installing
Redis.

Exact historical infrastructure pins/digests remain reference evidence in the legacy architecture/
worker-operation records. They are not automatic upgrade instructions.

---

# 24. Technology direction

Preserve/reuse:

- Python for coordinator/workflow/contracts/tools/desktop orchestration;
- the existing HTML/CSS/JavaScript application frontend;
- SQLite for durable local state and FTS5 retrieval;
- existing Pydantic/shared job contracts;
- current document/artifact writers where portable;
- current worker/job protocol;
- existing K3s/Redis managed backend where useful.

Current/candidate directions that require qualification rather than blind adoption:

- existing Ollama adapter — current runtime baseline;
- bundled upstream `llama.cpp`/`llama-server` — preferred app-managed engine candidate;
- Qwen3.5-4B — current general baseline requiring workload-specific qualification;
- local embedding model such as Qwen3-Embedding-0.6B — semantic retrieval candidate;
- embedded vector extension such as sqlite-vec — local vector-search candidate;
- local mDNS/zeroconf — discovery candidate;
- platform-specific installer/signing/updater mechanisms — qualification choices;
- standalone sandbox backends/toolchains — per-OS/edition qualification.

`llmfit` is a promising MIT-licensed cross-platform hardware/model-fit tool, but Beta 0.1 does not
ship or integrate it as a runtime dependency. The preferred Beta posture is internal qualification
or release-engineering use only. Its observations and recommendations are planning evidence, never
qualification evidence: Refinix remains authoritative for exact model digests, runtime versions,
device classes, workflow qualification, capability admission, containment and generated
qualification artifacts. A later evaluation may choose to ship it, retain it as an internal tool or
reject it, based on measured benefit versus packaging, provenance, dependency-licence inventory,
security containment and JSON-compatibility cost. Do not introduce an adapter abstraction until an
integration is actually justified.

Use its documented [target-hardware profiles and JSON planning](https://github.com/AlexsJones/llmfit/blob/main/docs/cli.md)
as an option for preparing the reviewed presets without owning each target computer. Record the
tool revision and distinguish estimates from embedded community measurements. Do not rebuild its
fit estimator, expose its scores as model accuracy or add a runtime sidecar for Beta setup.

Do **not** introduce React, Go, Rust, a generic plugin platform, external vector database, service
mesh, second scheduler service or another agent framework merely to change the stack.

Additional voice/image/media packs may legitimately use additional local runtimes later; one
inference engine need not support every model family.

---

# 25. Platform support and Beta scope

Refinix Beta 0.1 direction requires at least one **exact qualified desktop profile in each OS family**:

- Windows;
- macOS;
- Linux.

This does not promise every OS release, edition, distribution, architecture, driver or hardware
combination. Desktop/package acceptance uses representative app/workflow evidence; it does not require
testing every downloadable model on every computer or create a general model/device allowlist.

Each selected desktop profile must be useful standalone for supported local Chat/Documents/Code,
model management, persistence and the offered update/recovery path. Reviewer installation and work
must not depend on another machine, a private server, Kubernetes, Redis or peer certificates.

Code capabilities remain per profile. Preserve reviewable local proposals and the explicitly labelled
local Apply/Undo mode; qualify sandbox execution on at least one eligible **local** profile. Do not
advertise sandbox execution on other profiles until qualified, or route a required Beta workflow to
a peer to conceal a missing local capability. No unrestricted host-execution fallback is permitted.

Trusted-device discovery, pairing, remote execution, receiving work and fleet scheduling are deferred
from Beta 0.1. Retain their source and architecture for post-Beta work. Later same-OS/cross-OS peer
qualification must still demonstrate there is no hidden Linux inference dependency.

Beta 0.1 also targets a qualified in-app update path on each advertised desktop profile. An existing
update design, a source merge or UI controls do not establish that this path works. Missing updater
acceptance remains a release blocker for this scope; using manual replacement as the sole release
path instead requires an explicit user decision, not an agent silently dropping the updater.

The product/website/presentation may discuss broader production architecture, but functional controls
and claims must distinguish:

- **Working now** — named build/profile evidence;
- **Beta / experimental** — bounded accepted scope with limitations;
- **Planned** — product direction not yet release-accepted.

---

# 26. GitHub, application release and updates

A source change becoming part of `main` is **not** an installed-user update.

The intended flow is:

```text
member branch
   -> dev
   -> main
   -> CI/build gates
   -> designated application version
   -> build each supported platform package
   -> package/compatibility checks
   -> sign/authenticate + verify distributed bytes
   -> publish immutable versioned release assets
   -> website / update metadata published last
```

One application version names one immutable artifact set. Corrected bytes require a new version; do
not silently replace a published version.

Use separate protocol/database/model-artifact versions where compatibility requires it; matching app
version alone is not enough to accept peer work or open migrated state.

GitHub Releases is the current initial public artifact-hosting candidate, subject to actual package
size/availability limits. A GitHub Actions build artifact or source archive is not automatically an
end-user release. Public installation must not require the user to have GitHub credentials.

Signing credentials remain outside source/untrusted builds/logs.

## 26.1 Beta 0.1 update/replacement boundary

Beta 0.1 includes a qualified **Settings -> Updates** path for each advertised desktop profile.
Reuse any suitable existing update/packaging code after tracing the actual implementation; its
presence and past summaries are not current package acceptance. The application handles the approved
download/install/restart steps, while connected checks and consequential installation remain explicit
user actions. There are no silent startup, background or reconnection checks.

Also qualify authenticated **manual full-package replacement and recovery** as the recovery path.
Manual replacement alone does not satisfy the current in-app updater scope without a user-approved
release-scope change.

For each published Beta profile, rehearse replacement with two labelled builds:

- stop/drain work;
- snapshot affected durable state;
- replace the app with an authenticated compatible package;
- reopen offline;
- verify chats, model references, credentials and artifacts;
- prove recovery from failed replacement without losing newer work or opening incompatible newer
  schemas with an old binary.

If Beta ships a schema migration, its failure/recovery becomes mandatory acceptance.

<a id="262-later-settings---updates"></a>
## 26.2 Settings -> Updates

After qualification on the shipped profile, Settings provides an explicit:

**Check for updates -> Download -> Install and restart**

plus **Import update** for a verified offline package.

Rules:

- checks are user-initiated; no silent startup/background/reconnection checks;
- fetch only required release metadata, not prompts/documents/hardware analytics;
- authenticate metadata/package and verify compatibility before execution;
- stage downloads separately from the running app;
- show version, notes, size, permissions/prerequisites, progress/cancel;
- preserve the working installation on interruption/verification failure;
- drain/reconcile jobs before replacement;
- back up affected durable state and run versioned migration/recovery;
- an offline/failed check means unavailable/last-checked, not unverified "Up to date";
- offline import applies the same trust/anti-downgrade/compatibility checks;
- update failure never disables an otherwise working offline version.

---

# 27. Private server and managed organisation direction

The private-server mode uses the same application job contract. A server does not have to use
Kubernetes if another qualified execution/isolation profile satisfies its needs; an existing managed
cluster may reuse the retained backend.

Managed organisation scope adds, after the core product:

- authenticated users/admins;
- compute eligibility and quotas;
- organisation-managed shared corpora with separate permissions;
- versioned templates/governed workflows;
- customer-specific workflow evaluation;
- controlled deployment/update/support.

Compute membership never silently grants access to personal workspaces/corpora. Employee
project-management/task-assignment features are outside the core product scope.

---

# 28. Release phases

Implementation sequencing is owned by [`../tasks.md`](../tasks.md). At product level:

Keep the existing phase identifiers for reference. The Beta execution order is **Phase 1 -> Phase 2
-> local Phase 4 acceptance -> Phase 5**. Phase 3 and the peer-specific part of Phase 4 follow after
Beta. These are major work sections; agents do not subdivide them into further assignment tiers.

## Phase 1 — Cross-platform foundation

Remove/contain macOS-only assumptions and establish portable data/runtime/document/Code/credential/
installer/sandbox foundations for selected Windows/macOS/Linux profiles. Peer-agent packaging is
deferred; preserve its shared interfaces without making completion a standalone Beta prerequisite.

**This is the current active phase and only the first part of the total Beta implementation.**

## Phase 2 — Complete standalone Refinix

Persistent model lifecycle plus dependable local Chat/Documents/Code workflows on selected profiles.

## Phase 3 — Trusted-device mesh

Graphical discovery/pairing, bounded peer execution, receiver controls and practical model/device
routing across selected profiles. **Deferred until after Beta 0.1.**

## Phase 4 — Safe execution, recovery and sovereignty proof

Qualified sandbox, failures/reconciliation, approvals/status and real offline/Proof Card evidence.
Qualify the exposed standalone paths before Beta; extend acceptance to peer paths after Phase 3.

## Phase 5 — Beta packaging and publication

Authenticated packages for selected Windows/macOS/Linux profiles, clean standalone user journey,
qualified in-app updates, manual replacement/recovery and user-accepted evidence before Download
Refinix Beta is published. Peer execution is not a publication gate.

## After Beta 0.1

Later versions/finals complete the trusted-device mesh and expand scheduling fairness/performance,
semantic retrieval and curated memory, additional models/profiles, updater improvements, managed
deployments, broad qualification, complete update/recovery matrices, stronger trust/resource testing
and optional capability/adaptation research.

---

# 29. Non-goals

Refinix does not require for the Beta/core direction:

- model sharding or pooled RAM/VRAM across peer laptops;
- cross-device KV-cache migration;
- foundation-model training;
- continuous reinforcement learning from conversations;
- cloud inference;
- arbitrary executable model imports;
- unrestricted host execution;
- employee project-management/task assignment;
- a generic plugin framework;
- a frontend rewrite;
- Kubernetes/Redis on every desktop;
- a new global scheduler/leader-election service;
- guarantee that every model works on every machine;
- guarantee that installer software can bypass unsupported drivers/host security restrictions;
- Kubernetes high availability or automatic workspace-coordinator failover for the first Beta.

---

# 30. Functional requirement register

Stable FR identifiers are retained so older evidence/history can still refer to them. Post-Beta mesh
priorities defer release timing, not the corresponding trust, isolation or recovery requirements.

| ID | Requirement | Product priority |
|---|---|---|
| FR-001 | Each installation owns a workspace; Beta operates standalone with qualified local dependencies; later remote-only clients need no local model | Core local / post-Beta remote |
| FR-002 | Graphical setup bundles/provisions dependencies and verifies enabled capabilities without terminal work | Core |
| FR-003 | Existing Chat/Documents, Code and Settings use one harness and job system | Core |
| FR-004 | Local and trusted-worker requests complete without cloud inference | Core local / post-Beta mesh |
| FR-005 | Pairing is explicit, reversible and never merges canonical state | Post-Beta mesh |
| FR-006 | Automatic task/model/device selection uses capability, policy, load and evidence; choices are visible and overridable | Core local / post-Beta mesh |
| FR-007 | Workers receive bounded context and use assigned workspaces | Post-Beta mesh |
| FR-008 | Actions are automatic, approval-required or denied under explicit policy | Core |
| FR-009 | Status exposes model, device, progress, validation and evidence honestly | Core |
| FR-010 | Normal operation has no public-network dependency or silent external traffic | Core |
| FR-011 | Documents support extraction/OCR, retrieval, citations and real file generation | Core |
| FR-012 | Code supports reviewable proposals and qualified sandbox validation before approved canonical writes | Core |
| FR-013 | Concurrent independent jobs are placed using current capacity across trusted devices | Post-Beta mesh |
| FR-014 | Interrupted attempts/retries cannot cause duplicate canonical writes | Core |
| FR-015 | Persistent Settings -> Models supports curated catalogue lifecycle after onboarding, including explicit download, verified offline import and safe removal | Core |
| FR-016 | Private server participates through the common worker/job interface | Managed |
| FR-017 | Organisation compute and corpus permissions remain separate and enforced | Managed |
| FR-018 | Canonical workspace transfer is a separate explicit migration feature | Later |
| FR-019 | Additional language/voice packs preserve units, identifiers and uncertainty when enabled | Later |
| FR-020 | Existing Kubernetes execution remains a supported backend profile; standalone Beta does not require it | Post-Beta managed |
| FR-021 | Redis remains ephemeral coordination in that backend; desktops need not install it | Post-Beta managed |
| FR-022 | Supported Windows, macOS and Linux installations can request/receive work without a dedicated Linux member | Post-Beta mesh |
| FR-023 | Recommendations show at most six initial choices, Show more, evidence-labelled fit and compatibility warnings | Core |
| FR-024 | Receiving devices expose active remote work and owner controls | Post-Beta mesh |
| FR-025 | Local semantic retrieval uses qualified embeddings alongside exact-term retrieval with source/access boundaries | Post-Beta core improvement |
| FR-026 | Published support claims name tested OS versions, architectures, runtimes and capabilities | Core |
| FR-027 | Runtime memory budgets account for weights, cache/state, context and concurrent jobs; cache reuse respects compatibility/privacy | Core |
| FR-028 | Editable instructions/curated memory use defined local data layout and safe legacy migration, distinct from chat history/model weights | Core direction |
| FR-029 | Beta provides qualified user-initiated in-app connected/offline updates plus authenticated manual recovery; offered paths preserve data | Core Beta release |
| FR-030 | Published versions come from platform build/sign/compatibility gates; an ordinary main change is not automatically a user update | Core |
| FR-031 | Optional local model adaptation uses approved datasets, isolated versioned adapters and held-out evaluation; no silent per-conversation training | Later |

---

# 31. Open decisions / qualification boundaries

These are unresolved qualification/design choices, not permission for an agent to decide silently.
Where resolving one changes the product contract or protected docs, the agent must give the user a
recommendation and obtain permission before changing those docs.

| ID | Current boundary |
|---|---|
| OD-01 | Confidential customer datasets are not assumed; any evaluation corpus needs its owner's authorisation |
| OD-02 | Open-source core + specialised paid offering remain direction; repository licence is unchanged until separately authorised |
| OD-03 | Existing local Ollama reuse and managed upstream llama.cpp are Beta product paths; model origin selects the backend, measured profiles are evidence rather than a local allowlist, and customers do not own qualification |
| OD-04 | Keep current UI/desktop shell; qualify installer formats, native dependencies, signing and recovery per platform |
| OD-05 | Retain Qwen3.5-4B baseline evidence; allow compatible coding/OCR and other alternatives using upstream metadata/evidence and honest task outcomes, without prior team certification of every model |
| OD-06 | Preserve prototype trust semantics; qualify graphical OS-portable discovery/pairing/revocation after Beta; local protected credentials remain a Beta requirement |
| OD-07 | Semantic retrieval is direction; qualify local embedding + embedded vector-search components before adoption |
| OD-08 | Retain existing Kubernetes/Redis backend evidence/pins; documentation does not silently upgrade/remove infrastructure |
| OD-09 | Qualify portable sandbox implementations/toolchains; no unsafe subprocess fallback |
| OD-10 | Define calibrated recommendation-score normalisation/quality datasets/confidence before numeric scoring |
| OD-11 | After Beta, qualify multi-worker admission/capacity/fairness/recovery using the retained shared job contract |
| OD-12 | Define supported OS version ranges/architecture/backend presets from published research and representative qualification; retain clean-package evidence for release |
| OD-13 | Qualify shared-corpus storage/identity/access/retention for managed deployments |
| OD-14 | Qualify Beta installer/hosting/signing/in-app updates/manual recovery on every advertised profile before publication; broader upgrade and peer matrices follow later |
| OD-15 | Qualify cache reuse/limits/optional engine optimisations per model/backend; no custom PagedAttention requirement |
| OD-16 | Formalise Refinix data-root migration/instruction precedence; optional adapters require separate training/evaluation qualification |
| OD-17 | Evaluate `llmfit` as planning-only hardware intelligence; Beta uses it at most internally, and later chooses shipped component, internal tool or rejection from measured integration cost/benefit |
| OD-18 | Continue the existing orchestration harness. LangGraph is an unadopted option; reconsider only for a demonstrated workflow gap with measured integration/maintenance benefit and preserved offline/state/approval/security semantics |

---

# 32. Success criteria and evidence boundary

A useful Beta reviewer should eventually be able to:

- install a published Refinix package on the advertised selected profile;
- choose/manage supported models graphically;
- complete real local Chat/Documents/Code workflows;
- observe the actual local model, progress and capability status without pairing another device;
- obtain a grounded readable document artifact;
- obtain a reviewable Code patch, with real sandbox validation on an eligible local profile and
  truthful validation limits on other profiles;
- see failures/limitations truthfully;
- inspect scoped offline/Proof Card evidence;
- update through the qualified in-app path and preserve data across update/replacement/recovery.

Graphical pairing, remote execution, receiver controls and fleet routing are post-Beta success
criteria. They do not block acceptance of the standalone Beta above.

Availability of source code, a passing mock test or one successful model answer is not release
acceptance.

Evidence/status observations belong in `evaluation.md` and related reference material. The uploaded
historical evaluation snapshot may contain stale/conflicted text; agents must not silently turn a
conflicted historical section into current product truth.

---

# 33. Documentation map

## Normal agent read path

1. [`../AGENTS.md`](../AGENTS.md) — how agents operate and when to ask the user.
2. This file — what Refinix is and how it should behave.
3. [`../tasks.md`](../tasks.md) — current implementation phase/outcome.
4. One focused authority only when relevant:
   - [`security.md`](security.md)
   - [`model-catalog.md`](model-catalog.md)
   - [`releases.md`](releases.md)

## Evidence/reference — read only when needed

- [`evaluation.md`](evaluation.md) — source/runtime/acceptance evidence and historical measurements.
- [`devicespecifications.md`](devicespecifications.md) — device inventory/historical hardware evidence.
- [`worker-operations.md`](worker-operations.md) — managed Linux/Kubernetes operational runbook.
- `docs/archive/` — historical reproduction material.
- `agent-memory/` — searchable user-request/change history.

## Retired active authorities — retained for compatibility/reference

- `docs/prd.md`
- `docs/architecture.md`
- `docs/workflows.md`
- `TechStack.md`

They may contain useful historical detail and inbound links, but current requirements come from this
file. Do not update all four to mirror every current decision; that duplication is intentionally
being removed.

## Presentation/research

Presentation and research material may explain the product but is non-normative. It must not
override this contract or turn planned features into verified claims.
