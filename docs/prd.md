# AegisForge Product Requirements Document

## SovereignMesh: Distributed, Air-Gapped AI Workbench

| Field | Value |
|---|---|
| Document version | 1.1 |
| Status | Working source of truth for research and prototype development |
| Repository | AegisForge |
| Product working name | SovereignMesh |
| Target | SIH Problem Statement 117 |
| Product type | Installable local AI workbench with optional trusted-device distribution |
| Primary v1 coordinator | MacBook |
| Last updated | 2026-08-31 |

> This document preserves the product decisions made during the initial SIH planning discussion. It separates settled v1 requirements from hypotheses and future scope so that the team can delete the original planning chat without losing its context.

---

## 1. Executive Summary

SovereignMesh is a self-hosted, model-agnostic AI workbench for confidential knowledge work. It is intended for organisations that cannot send prompts, documents, source code, drawings, or internal records to public AI services.

Users obtain the application from a public product website. The installed application then runs locally and manages approved open-weight models on the user's own hardware. The same application is installed on every trusted participating device. During setup, a device either creates a workspace as the coordinator or joins an existing workspace as a worker.

The system operates in two modes:

1. **Standalone mode:** one device runs the interface, models, tools, and jobs locally.
2. **Distributed mode:** the Mac coordinator routes independent tasks to trusted worker devices running compatible specialist models over an offline Wi-Fi or Ethernet LAN.

SovereignMesh does not split a single model across devices. Each job runs on one complete model on one selected device. Different jobs can run concurrently on different devices.

### Example

A user starts two chats on the Mac:

1. Read a scanned inspection report, search a local SOP, and generate a cited approval note.
2. Modify a small repository, run validation in a sandbox, and return a verified patch.

The document job is routed to an OCR or vision worker while the coding job is routed to a coding worker. Both results stream back to the Mac, which remains the owner of the chats, files, job state, artifacts, and canonical repository.

### Product statement

> SovereignMesh is one installable application that turns trusted local computers into a secure pool of specialist AI workers while retaining a coherent ChatGPT-like workspace and keeping sensitive work inside the organisation.

### One-line judge pitch

> A sovereign AI workbench that works on one machine and scales across trusted existing hardware for private, concurrent, and verifiable agentic work.

---

## 2. Context, Problem, and Opportunity

Government offices, PSUs, refineries, defence-linked manufacturers, engineering organisations, and internal software teams routinely handle confidential work such as:

- Approval notes and internal correspondence
- Board presentations and spreadsheets
- Engineering calculations
- Source code for internal tools
- Scanned inspection reports and drawings
- Manuals, SOPs, vendor information, and unreleased designs

Public AI services are often unsuitable because sensitive information would leave the organisation's controlled environment. A conventional local alternative is a powerful central GPU server, but that approach can create:

- High acquisition cost
- A single compute bottleneck
- Limited concurrency
- High memory and thermal pressure on one device
- Operational dependence on one machine
- Difficult model switching as open-weight models evolve
- Underuse of trusted computers that already exist inside the organisation

The product opportunity is not merely another offline chat interface. It is a usable local workbench that can:

- Install and manage approved models
- Select the right model for a task
- Execute multi-step work with local tools
- Produce real artifacts rather than chat text alone
- Run on one workstation
- Expand across trusted heterogeneous devices when available
- Prove that no external inference or data transfer occurred

### Honest limitation

A group of laptops is not automatically superior to a central GPU server. A central server is easier to secure, maintain, audit, and keep available. SovereignMesh is valuable only if the prototype proves useful workflow quality, reliable orchestration, and a measurable concurrency or resource advantage. Distribution is an accelerator and differentiator, not a substitute for completing the required agentic workbench.

---

## 3. Product Thesis and Differentiation

### Thesis

A set of smaller specialist models, correctly selected and independently verified, can provide a practical sovereign workbench without forcing every task through one large general-purpose model.

The product's value comes from the combination of:

- A familiar multi-chat local interface
- Curated model installation and compatibility guidance
- Automatic task-to-capability routing
- Standalone and distributed execution through one application
- Concurrent jobs across independent workers
- Local RAG and agentic tools
- Task-specific validation
- Secure pairing and revocation
- Visible routing, model, device, and tool evidence
- Graceful fallback when workers are unavailable

### What is not novel by itself

The following elements already exist independently and must not be presented as unprecedented:

- Local model runtimes
- Model download managers
- Chat interfaces
- RAG pipelines
- LAN APIs
- Task queues
- Distributed job schedulers

### Intended differentiation

The differentiator is their integration into a capability-aware, secure, offline workbench that uses ordinary heterogeneous trusted devices as specialist workers while keeping the user experience and canonical state on one coordinator.

### Product inspiration and boundary

FluidVoice inspired the desired onboarding pattern: install one desktop application, guide the user through obtaining a required local model, and then provide a simple offline experience. SovereignMesh extends that product pattern to multiple model capabilities, agentic tools, and trusted-device task distribution. FluidVoice is an inspiration, not an implementation dependency; no code or assets should be copied without a separate compatibility and licence review.

### Correct terminology

Use:

> Heterogeneous task-level inference orchestration across independent local model servers.

Do not use:

- Model sharding
- Combined VRAM
- One large model distributed across Wi-Fi
- A laptop cluster that replaces all GPU servers

---

## 4. Product Identity and Surfaces

### 4.1 Naming

- **AegisForge** is the current repository name.
- **SovereignMesh** is the current product and architecture working name.
- The team must choose one external product name before the landing page, installer, package IDs, certificates, or SIH submission are finalised.

Until that decision is made, this PRD uses SovereignMesh for the product and AegisForge for the repository.

### 4.2 Public website

The public website may be deployed on Vercel or an equivalent static/web hosting platform. It is responsible for:

- Explaining the product
- Publishing supported platforms and hardware expectations
- Linking to approved installer artifacts
- Publishing installer versions and SHA-256 checksums
- Hosting public documentation and release notes
- Clearly labelling alpha, prototype, and production readiness

The public website does not run inference, store private chats, coordinate workers, or become part of the offline runtime.

### 4.3 Installed desktop/node application

The same application is installed on every trusted device. It contains or launches the components required for the selected role:

- User interface when acting as coordinator
- Secure node service
- Hardware and capability discovery
- Model catalogue and installation integration
- Local runtime adapter
- Pairing and device identity
- Job execution and streaming
- Local audit and health reporting

### 4.4 Local workspace

The local workspace contains:

- Chats and summaries
- Job state
- Device registry
- Approved model manifests
- Knowledge-base indexes
- User-approved documents and repositories
- Audit metadata
- Generated artifacts

The Mac owns the canonical workspace in v1.

---

## 5. Users and Primary Use Cases

### 5.1 Primary users

- Government and PSU staff handling sensitive documents
- Engineers and inspectors
- Internal software teams
- Administrative and approval departments
- Organisations evaluating sovereign AI on existing hardware

### 5.2 Administrative users

- Local IT administrators
- Security reviewers
- Model and device administrators
- Hackathon team members operating the prototype

### 5.3 Core use cases

#### UC-01: Local chat and reasoning

The user asks a normal question. The coordinator selects a compatible local model, streams the answer, and displays the model and device used.

#### UC-02: Scanned inspection report

The user uploads a scanned report. The system:

1. Performs OCR or vision analysis locally.
2. Preserves page association and uncertainty.
3. Extracts structured findings.
4. Retrieves relevant passages from a local SOP.
5. Generates a cited approval note as a Word document.

#### UC-03: Repository coding task

The user selects a repository and requests a change. The system:

1. Identifies relevant files.
2. Creates a temporary isolated workspace.
3. Sends only required context to a coding worker.
4. Generates a patch.
5. Runs approved validation in a network-disabled sandbox.
6. Returns the patch, exit status, and validation report.
7. Applies nothing to the canonical repository without the coordinator's controlled final-write step.

#### UC-04: Concurrent work

The user starts document and coding work in separate chats. The jobs run concurrently on different devices and stream progress to the correct chat.

#### UC-05: Standalone operation

When no worker is connected, supported jobs run locally. Models may load and unload, and jobs may queue when hardware cannot run them concurrently.

#### UC-06: Worker failure

When a worker disconnects, the coordinator marks the attempt interrupted and either requeues it on another compatible worker or returns a clear recoverable failure. Final writes must not occur twice.

#### UC-07: Connected model provisioning

During an explicitly connected setup, the application uses an existing trusted model runtime or approved download source to obtain a model, verifies its manifest and checksum, and records its licence and compatibility metadata.

#### UC-08: Air-gapped model provisioning

An administrator imports an approved model bundle through removable media or an internal organisational server. The application verifies its manifest and checksum before installation. Unsigned or unapproved executable model code is rejected in the MVP.

---

## 6. Product Principles and Settled Decisions

1. **Offline runtime:** normal task execution must not require the public Internet.
2. **One application:** coordinator and worker roles come from the same installable product.
3. **Mac-led v1:** the Mac is the fixed coordinator and primary input/output device for the prototype.
4. **Future role flexibility:** any-node coordinator or replicated control is future scope.
5. **Standalone first:** the workbench must remain useful with no worker connected.
6. **Distributed acceleration:** extra trusted devices add capabilities and concurrency.
7. **No model splitting:** one request runs on one complete model on one device.
8. **Original request preserved:** routing metadata may be added, but the user's prompt is not silently simplified or replaced.
9. **Coordinator-owned state:** chats, context, files, jobs, artifacts, and final writes remain canonical on the coordinator.
10. **Curated models:** the MVP supports an approved catalogue, not arbitrary downloadable model code.
11. **Minimum necessary transfer:** workers receive only the task context and files they require.
12. **Verification over blind trust:** code, OCR, retrieval, and artifacts use task-specific checks.
13. **Visible operation:** the UI shows selected capability, model, device, routing reason, and tool progress.
14. **Graceful degradation:** losing a worker reduces capacity but does not corrupt canonical state.
15. **Local runtimes stay private:** Ollama, llama.cpp, MLX, or equivalent runtimes bind to loopback and are not directly exposed to the LAN.
16. **Existing runtimes first:** do not build a universal model runtime or downloader during the hackathon.
17. **Honest claims:** performance, quality, energy, and thermal benefits remain hypotheses until measured.

---

## 7. Scope and Release Stages

### 7.1 Five-day research and alpha prototype

The immediate goal is a research-backed alpha, not a worldwide production launch.

Minimum credible output:

- Repository foundation and shared documentation
- One Mac coordinator
- One Windows worker
- Real authenticated or prototype-paired LAN connection
- Real local-model inference on the worker
- Streaming output returned to the Mac
- Visible device, hardware, model, and capability information
- An approved model catalogue format
- A public landing page or deployable site shell
- Recorded open questions, benchmarks, and security boundaries

### 7.2 SIH internal-selection prototype

The selection prototype must prove:

- The concept is implemented beyond slides
- One real Mac-to-worker inference path works
- The original prompt and returned output are preserved
- No cloud inference is used
- The selected worker and model are visible
- The prototype can be reproduced by the team from repository documentation

### 7.3 Finals MVP

The finals MVP should demonstrate:

- Standalone and distributed modes
- At least two worker devices where venue hardware allows
- Automatic selection across at least two task types
- Concurrent OCR and coding jobs
- Scanned-document understanding
- Local SOP retrieval with citations
- Word document generation
- Sandboxed coding and validation
- Authenticated device pairing and revocation
- File integrity checks
- Worker failure handling
- Audit and network activity evidence
- Zero external inference calls during the demonstration

### 7.4 Post-hackathon product

Future development may include:

- Any installed node acting as coordinator and UI
- Replicated conversation and job state
- Coordinator failover and conflict resolution
- Organisation-wide identity and role management
- Multi-user queues and administrative policies
- Signed model bundles and controlled fleet updates
- Automatic application updates
- Department-level knowledge bases
- High-availability coordinators
- Multi-location deployments
- A broader but still governed model ecosystem

---

## 8. Non-Goals

The MVP will not include:

- Splitting one model across multiple devices
- Combining VRAM across devices
- Training or fine-tuning models
- Internet-based inference
- Kubernetes
- A custom transport protocol
- Support for every open-weight model
- Arbitrary Hugging Face code execution
- Unrestricted autonomous host file modification
- Cross-organisation device sharing
- Running 100B+ parameter models on the available laptops
- Perfect installers for every operating system in five days
- Production-grade automatic updates
- Full enterprise IAM
- A production-grade universal sandbox
- Every possible agentic workflow
- Hosting model weights directly on Vercel
- Replacing enterprise GPU servers in all scenarios

---

## 9. High-Level Architecture

```text
                         PUBLIC INTERNET

          Public website / docs / release metadata
                          |
             installer and checksum download
                          |
             connected setup only, if used

================== OFFLINE RUNTIME BOUNDARY ==================

                 Trusted Wi-Fi or Ethernet LAN

┌─────────────────────────────────────────────────────────────┐
│ Mac: SovereignMesh coordinator + optional local worker      │
│                                                             │
│ Multi-chat UI            Canonical context and files        │
│ Task classifier/router   Job queue and audit metadata       │
│ Device registry          Knowledge base and artifacts       │
│ Core local model         Controlled final-write authority   │
└──────────────────────┬───────────────────────┬──────────────┘
                       │ authenticated         │ authenticated
                       │ encrypted jobs        │ encrypted jobs
             ┌─────────▼─────────┐   ┌─────────▼─────────┐
             │ ASUS worker       │   │ LOQ/Victus worker │
             │ Same application  │   │ Same application  │
             │ Coding capability │   │ OCR/vision/reason  │
             │ Local runtime     │   │ Local runtime      │
             │ Isolated tools    │   │ Document tools     │
             └───────────────────┘   └───────────────────┘

           Model runtimes bind to localhost on every node.
```

### 9.1 Physical network clarification

The application does not replace Wi-Fi or Ethernet. It provides the trusted application protocol, identity, job handling, and model coordination over an existing local network. An offline LAN means devices can communicate locally while Internet routing is disabled or blocked.

### 9.2 Node roles

#### Create Workspace

The first device:

1. Installs the application.
2. Selects **Create Workspace**.
3. Detects hardware and available runtimes.
4. Installs or selects the mandatory coordinator core model.
5. Creates local workspace keys and state.
6. Starts the coordinator and optional local worker.
7. Presents a one-time pairing code or QR code.

#### Join Existing Workspace

A worker device:

1. Installs the same application.
2. Selects **Join Existing Workspace**.
3. Enters or scans the pairing code.
4. Receives a device-specific trusted identity.
5. Detects hardware and compatible capability packs.
6. Installs or selects at least one supported capability.
7. Begins heartbeat and capability reporting.

---

## 10. Core Components

### 10.1 Public distribution site

Responsibilities:

- Product explanation
- Platform and hardware guidance
- Release and checksum publication
- Installer download links
- Alpha/production status disclosure
- Public documentation

It must not contain:

- Model-host access tokens
- Signing keys
- Private release credentials
- User chats or private telemetry
- Confidential test data

### 10.2 Desktop shell and node application

Responsibilities:

- First-run setup
- Create/join workspace role selection
- Local service lifecycle
- Hardware discovery
- Model management UI
- Coordinator UI when enabled
- Worker status when joined
- Safe local configuration storage

### 10.3 Coordinator

Responsibilities:

- Maintain chats and canonical context
- Receive prompts, files, and user approvals
- Classify tasks and build bounded context packages
- Discover eligible workers
- Route, monitor, cancel, and requeue jobs
- Stream progress into the correct chat
- Maintain device, job, and audit metadata
- Store artifacts
- Apply verified final writes exactly once

### 10.4 Worker service

Responsibilities:

- Authenticate with one workspace
- Report OS, CPU, GPU, memory, runtime, models, and load
- Receive authorised jobs
- Call a localhost model runtime
- Stream events, tokens, results, and metrics
- Execute approved tools in isolation
- Return artifacts and checksums
- Reject unsupported, unauthorised, or out-of-policy work

### 10.5 Model runtime adapter

The adapter normalises an existing local runtime. The prototype should use one runtime wherever practical and add another only when hardware requires it.

Required adapter capabilities:

- List installed models
- Report model metadata
- Load or select a model
- Stream generation
- Cancel generation
- Report context limits
- Report health and availability
- Expose basic runtime statistics

### 10.6 Router and scheduler

The router determines:

- Required task capabilities
- Eligible models and devices
- Hardware compatibility
- Whether the model is already loaded
- Worker health and queue length
- Available memory
- Measured performance profile
- Optional thermal state when available

MVP routing order:

1. Classify using deterministic signals such as file type, explicit task, or selected workflow.
2. Exclude workers without the required capability.
3. Exclude unhealthy or memory-incompatible workers.
4. Prefer a worker with the required model already loaded.
5. Prefer the shorter queue.
6. Prefer the best measured compatible profile.
7. Fall back to the coordinator or queue the job.

The user must be able to see the reason and manually override the model or worker for debugging and demonstrations.

### 10.7 Context manager

The coordinator owns the complete conversation and source material. Context windows from different models never combine.

Each job receives a bounded task packet containing:

- Original user request
- Structured objective and capability requirements
- Relevant recent messages
- Conversation summary
- Relevant repository files or document passages
- Previous tool results
- Output schema and validation requirements
- Attachment metadata and checksums

Use four layers:

1. Immediate recent context
2. Working plan and tool state
3. Compressed conversation history
4. External local memory retrieved when needed

Prefer retrieval and summarisation over sending entire PDFs, repositories, or chat histories. Session affinity may prefer a warm worker, but the coordinator must always be able to reconstruct the task on another device.

### 10.8 Local knowledge base

Responsibilities:

- Import approved manuals, SOPs, and correspondence
- Process and index data locally
- Preserve source, page, and section metadata
- Retrieve relevant passages
- Provide citations to downstream document generation
- Operate without external embeddings or search APIs

### 10.9 Agent and tool runner

The MVP tool set is deliberately limited and auditable:

- Read user-approved files
- Write inside an isolated workspace
- Search local indexed documents
- Execute code with limits
- Generate a Word document
- Perform structured calculations
- Validate task output
- Retry or escalate low-confidence results

**Comment by Sahil Ranade:**

I suggest adding a configurable **Human Approval / Agent Autonomy mechanism** to the Agent and Tool Runner. Since SovereignMesh is designed for confidential industrial work and the agent can read files, execute code, generate artifacts, and potentially modify persistent data, the level of autonomy should not be the same for every workflow.

I propose three operating modes:

1. **Autonomous Mode** — The agent can perform permitted low-risk actions automatically, such as reading approved files, OCR, local retrieval, analysis, draft generation, and sandboxed validation. Existing security and tool restrictions still apply.

2. **Controlled Mode** — The agent can perform routine actions automatically, but actions that affect persistent or consequential data require explicit user approval. For example, generating and validating a code patch can happen automatically, but applying the patch to the canonical repository requires approval.

3. **Approval Mode** — The agent can analyse the task and prepare proposed actions, but controlled tool execution or consequential changes require explicit human approval before execution.

The mode should be enforced by the coordinator and applied at the workspace or job level. This gives the system a practical balance between automation and human control instead of treating every AI action equally.

This is particularly important for MRPL/industrial use cases because an agent should be able to work autonomously within a sandbox while keeping consequential operations under human authority. It also strengthens the existing principle that the coordinator retains final-write authority and prevents the agent from silently making persistent changes.

Suggested flow:

**User Request → Agent Planning → Policy/Permission Check → Execute Automatically OR Request Approval → Validation → Final Write**

This would make our "agentic" capability more suitable for real confidential enterprise environments while still preserving automation where human intervention is unnecessary.

— **Sahil Ranade**


Every tool call must be visible in the job timeline.
- Comment by **Prachi**

I suggest adding these two capabilities to strengthen SovereignMesh's focus on independent AI collaboration and protection of sensitive industrial data:

1.**Interconnecting Independent Models**
Allow multiple specialised local models to work independently while communicating through the coordinator when a task requires multiple capabilities. This enables models for coding, OCR, vision, reasoning, etc. to collaborate without sharing memory or combining VRAM.

2.**Privacy and Security of Sensitive Files**
Ensure confidential files remain within the trusted environment and are accessed only by authorised models, tools, and users. Data should be transferred on a minimum-necessary basis, protected with integrity checks, excluded from unnecessary audit logs, and never exposed to external AI services during offline operation.

These additions would strengthen the system's modularity, security, and data-sovereignty principles.

- **Prachi**
---

## 11. Model Provisioning and Capability Packs

### 11.1 Provisioning modes

#### Connected setup

- The user explicitly enables networked provisioning.
- The app obtains an approved model through an existing runtime or trusted source.
- The app verifies the expected manifest and SHA-256 checksum.
- The source, version, licence, and installation date are recorded.
- Connected setup ends before the sovereign offline runtime claim is demonstrated.

#### Air-gapped setup

- An administrator obtains an approved bundle outside the secure environment.
- The bundle is transferred through controlled removable media or an internal server.
- The app verifies manifest and checksum before import.
- Tampered, unknown, or incompatible bundles are rejected.

### 11.2 Mandatory software on every node

- SovereignMesh application
- Secure communication service
- Hardware and capability reporting
- Device identity and revocation support
- Local model-runtime integration
- At least one compatible model capability before accepting work

### 11.3 Mandatory coordinator capability

The coordinator requires:

- A small general chat/agent model
- Router and scheduler
- Chat and job database
- Core context-management functions

### 11.4 Candidate model catalogue

These are research candidates, not final commitments. Every entry must pass licence, compatibility, correctness, latency, and memory review before inclusion.

| Pack | Candidate | Purpose | Installation policy |
|---|---|---|---|
| Core Chat | Qwen3.5-4B, Q4 candidate | General chat, planning, routing assistance | Mandatory on coordinator |
| Knowledge/RAG | Qwen3-Embedding-0.6B candidate | Local embeddings and retrieval | Required when knowledge base is enabled |
| Documents | PaddleOCR-VL-1.6 candidate | OCR, scanned document, and layout understanding | Optional capability pack |
| Coding | Qwen2.5-Coder-7B-Instruct, Q4 candidate | Code generation and patch work | Optional capability pack |
| Reasoning/Vision | Qwen3.5-9B, Q4 candidate | Stronger reasoning or visual fallback | Optional; hardware-dependent |
| Voice | Qwen3-ASR-0.6B or evaluated local ASR | Local speech transcription | Optional capability pack |
| Speech output | Kokoro-82M candidate | Optional local text-to-speech | Future/optional |

### 11.5 Baseline-package decision still open

The original intent was to make the embedding/RAG model mandatory. The refined v1 architecture makes the small general model mandatory and installs embeddings when the knowledge-base feature is enabled. The team must benchmark download size, storage, first-run time, and the core demo before deciding whether embeddings become part of the default coordinator pack.

### 11.6 Hardware compatibility states

The model UI should report:

- Supported
- Supported but expected to be slow
- Insufficient memory
- Runtime unavailable
- Already installed
- Installed but unverified

### 11.7 Required model manifest

Every approved model entry must include:

- Stable model ID
- Display name and version
- Official source
- Model and code licence
- File names and sizes
- SHA-256 checksums
- Quantisation
- Required RAM and VRAM estimate
- Supported operating systems and runtimes
- Supported capabilities
- Recommended context limit
- Default output-token limit
- Installation and verification status

Do not infer that a model is safe or distributable merely because its weights are publicly downloadable.

---

## 12. Current Prototype Hardware and Tentative Assignment

| Device | Known hardware | v1 role | Tentative capability |
|---|---|---|---|
| MacBook Air | Apple M5, 10-core CPU/GPU, 16 GB unified memory, 512 GB | Coordinator, UI, canonical state, optional worker | Core chat/agent and local embeddings if benchmarks permit |
| ASUS V16 | Intel Core 7 240H, 16 GB DDR5 single-channel, RTX 5050 laptop GPU 8 GB VRAM, 512 GB | Worker | Coding model and code validation |
| Lenovo LOQ 15IRX9 | Intel Core i5-13450HX, 24 GB DDR5 dual-channel, RTX 3050 laptop GPU 6 GB VRAM, 512 GB | Worker | Reasoning or a larger model with CPU offload |
| HP Victus (Windows) | Intel Core i5-12450H, 16 GB DDR4, RTX 2050 4 GB VRAM, 1 TB | Worker | OCR/vision and model cache |
| HP Victus (Linux) | Intel Core i5-13420H, 16 GB, RTX 2050 4 GB VRAM, 512 GB, Ubuntu 24.04 with Docker | Worker | Sandboxed code execution |
| Dell Inspiron 15 3520 | Intel Core i5-1235U, 16 GB, Intel Iris Xe integrated only, 512 GB | Optional worker/fallback | Voice, fast chat, or embeddings |

Full inventory, including storage, networking, driver versions, and outstanding
gaps, is in [`devicespecifications.md`](devicespecifications.md).

Assignments are hypotheses. The team must record exact GPU VRAM, driver/runtime support, sustained speed, temperature, and output quality before final placement.

Do not read GPU VRAM from `systeminfo`, `Get-ComputerInfo`, or
`Win32_VideoController.AdapterRAM`. That field saturates at 4 GB, and it
misreported both the 8 GB and the 6 GB card in this fleet. Use `nvidia-smi`.

On 8 GB GPUs, begin with Q4 models, bounded contexts, and task-specific output limits. Do not rely on advertised 128K or larger context windows without local quality and memory tests.

---

## 13. Functional Requirements

Priority definitions:

- **P0:** required for the core prototype or sovereign claim
- **P1:** important for the finals MVP
- **P2:** future product capability

| ID | Requirement | Priority |
|---|---|---|
| FR-001 | Provide one installable application capable of coordinator and worker roles | P0 |
| FR-002 | Allow the first device to Create Workspace and another device to Join Existing Workspace | P0 |
| FR-003 | Operate on one workstation with no connected worker | P0 |
| FR-004 | Keep the Mac as the fixed v1 coordinator and primary UI | P0 |
| FR-005 | Pair a trusted worker using a one-time code or QR-based flow | P0 |
| FR-006 | Assign every worker a unique revocable device identity | P0 |
| FR-007 | Display hardware, runtime, installed models, health, and queue status | P0 |
| FR-008 | Maintain an approved model catalogue with source, licence, checksum, and compatibility metadata | P0 |
| FR-009 | Support connected provisioning through an existing model runtime or approved source | P1 |
| FR-010 | Support verified offline model-bundle import | P1 |
| FR-011 | Reject unapproved arbitrary executable model code in the MVP | P0 |
| FR-012 | Provide a multi-chat interface with independent job streams | P0 |
| FR-013 | Preserve the original prompt and relevant context | P0 |
| FR-014 | Build bounded model-specific context packages | P0 |
| FR-015 | Automatically route at least coding and document/OCR tasks | P0 |
| FR-016 | Show selected device, model, capability, and routing reason | P0 |
| FR-017 | Allow manual device/model override for debugging and demonstration | P1 |
| FR-018 | Stream partial output and progress to the correct chat | P0 |
| FR-019 | Transfer attachments and artifacts with SHA-256 verification | P0 |
| FR-020 | Cancel queued or running jobs | P0 |
| FR-021 | Detect worker loss and requeue safely when another compatible worker exists | P1 |
| FR-022 | Prevent duplicate final writes during retry or failover | P0 |
| FR-023 | Perform OCR/scanned-document analysis locally | P0 |
| FR-024 | Preserve page references and explicit OCR uncertainty | P0 |
| FR-025 | Search an entirely local knowledge base with citations | P0 |
| FR-026 | Generate a Word approval note from extracted and retrieved findings | P0 |
| FR-027 | Execute coding work inside an isolated, network-disabled workspace | P0 |
| FR-028 | Return a patch, validation command, output, and exit status | P0 |
| FR-029 | Keep the canonical repository and final-write authority on the coordinator | P0 |
| FR-030 | Maintain an auditable event timeline for every job | P0 |
| FR-031 | Show evidence of blocked or absent external runtime traffic | P0 |
| FR-032 | Store metadata by default instead of full confidential prompts in audit logs | P0 |
| FR-033 | Support local speech transcription | P1 |
| FR-034 | Generate PowerPoint and spreadsheet artifacts | P1 |
| FR-035 | Support multiple organisational users and roles | P2 |
| FR-036 | Allow any trusted node to become input/output/coordinator | P2 |

---

## 14. Job, Context, and Data Contracts

### 14.1 Job lifecycle

```text
Created
   |
Context Preparing
   |
Queued
   |
Routing
   |
Running
   |
Validating
   |
Completed

Failure paths:
Running -> Interrupted -> Requeue -> Routing
Running -> Failed
Any active state -> Cancelled
```

Every job and every attempt must have a unique ID. Completion and final artifact writes must be idempotent.

### 14.2 Example task envelope

```json
{
  "job_id": "job-42",
  "attempt_id": "attempt-1",
  "chat_id": "chat-coding",
  "task_type": "repository_change",
  "required_capabilities": ["coding", "sandbox"],
  "original_prompt": "Generate a basic HTML page in this repository.",
  "context_refs": ["file:index.html"],
  "attachment_sha256": {},
  "output_contract": "unified_patch_and_validation",
  "deadline_ms": 30000
}
```

The structured fields help routing; they never replace the original user input.

### 14.3 Minimum node API

The exact paths may change after protocol design, but the v1 capability surface requires:

```text
POST /pair
POST /pair/confirm
POST /pair/revoke
GET  /health
GET  /capabilities
POST /jobs
GET  /jobs/{job_id}
GET  /jobs/{job_id}/events
POST /jobs/{job_id}/cancel
```

### 14.4 Capability response

A worker should report:

- Device ID and trusted-state status
- Operating system and application version
- CPU, GPU, total memory, and available memory
- Installed model IDs and verification state
- Runtime name and version
- Supported task types
- Queue length and current job
- Loaded model
- Health and last heartbeat
- Temperature when reliable platform support exists

---

## 15. Repository and Artifact Safety

### 15.1 Coding workflow

1. The user selects an approved repository or folder.
2. The coordinator identifies relevant files.
3. A temporary workspace is created.
4. Required files are copied or transmitted with checksums.
5. The coding worker generates and validates a change in isolation.
6. The worker returns a unified patch and validation report.
7. The coordinator verifies target paths and patch applicability.
8. The coordinator performs the final write once, after the applicable approval policy.
9. The user can inspect the resulting diff.

The entire repository should not be transferred for every task.

### 15.2 File restrictions

- Workers may write only inside assigned temporary workspaces.
- Path traversal and symlink escape must be rejected.
- Host directories remain read-only unless explicitly selected.
- Code execution has network, time, memory, process, and filesystem limits.
- Temporary files follow a documented retention and cleanup policy.
- Artifacts include origin job ID and checksum.

### 15.3 Repository content rules

Never commit:

- Model weights
- Generated installers or release binaries
- Signing keys or tokens
- Private documents
- Real confidential scans
- Local chat databases
- Environment files containing secrets

Use synthetic or explicitly approved non-sensitive test fixtures.

---

## 16. Security, Privacy, and Supply Chain Requirements

Security is part of the product claim, not a later polish item.

### 16.1 Trust boundaries

1. Public website and release storage
2. Installer and application update boundary
3. Model source or offline import boundary
4. Coordinator application and workspace
5. Worker application
6. Local model runtime
7. Tool sandbox
8. User-selected documents and repositories

### 16.2 Network security

- Runtime operation must not require Internet access.
- Coordinator-to-worker traffic must be authenticated and encrypted.
- Standard HTTPS with device credentials or mTLS is preferred; do not invent cryptography.
- Pairing requires explicit approval and a short-lived one-time code.
- Each node receives a unique revocable identity.
- Unknown, revoked, or version-incompatible nodes are rejected.
- Local model runtimes bind to loopback.
- Worker APIs expose only the minimum required LAN surface.
- Heartbeats, timeouts, and message-size limits are enforced.

### 16.3 Data and privacy

- Prompts, documents, embeddings, and artifacts remain on trusted devices.
- Workers receive only necessary context.
- Audit logs store metadata by default, not full confidential content.
- Sensitive logging is opt-in and visibly labelled.
- Temporary task data is deleted according to a documented retention policy.
- The UI clearly distinguishes Connected Setup from Offline Runtime.
- No silent telemetry, analytics, crash upload, or update check is permitted in offline runtime.

### 16.4 Model supply chain

- Only curated catalogue entries are installable in the MVP.
- Model source, licence, file hash, runtime, and version are recorded.
- Imported files are verified before use.
- Model repositories requiring remote executable code are excluded unless separately reviewed and sandboxed.
- A model licence inventory must distinguish weights, code, tokenizer, and runtime licences.
- Model files are never treated as trustworthy solely because they came from a popular host.

### 16.5 Application distribution

- Every published installer has a version and SHA-256 checksum.
- Production releases should be code-signed for each supported platform.
- If the alpha is unsigned, the website must say so and provide verification steps.
- Release credentials and signing keys remain outside source control and build artifacts.
- The site must not claim the application is secure, signed, or production-ready until evidence exists.

### 16.6 Sandbox requirements

- Network disabled by default
- Bounded CPU, memory, runtime, process count, and filesystem
- Explicit input mount and output directory
- No host secrets or home-directory access
- Captured command, stdout, stderr, and exit status
- Cleanup after completion or failure

### 16.7 Security proof

The demo must show observable evidence rather than a verbal promise:

- Internet disconnected or egress blocked
- Local LAN remains available
- No external DNS or connection attempts during runtime
- Worker identity and selected model visible
- File hashes recorded
- Audit timeline available

---

## 17. Licensing, Ownership, and Repository Governance

### 17.1 Current conflict

The planning decision favoured a private repository and proprietary source while distributing compiled installers publicly. The current AegisForge repository contains an Apache-2.0 `LICENSE`, which grants reuse rights and conflicts with calling the source proprietary.

The team must resolve this before accepting substantial contributions or distributing the product:

1. Confirm SIH, college, sponsor, and team IP requirements.
2. Decide whether the project is Apache-2.0, another open-source licence, or proprietary.
3. Ensure the repository licence, contributor terms, website, installer, and product claims agree.
4. Record ownership and contribution expectations in writing.

Until resolved, do not describe the repository as proprietary and do not assume that making a repository private cancels an existing licence grant.

### 17.2 Required governance documents

The repository should eventually contain:

- `README.md` — project entry point and verified setup status
- `docs/prd.md` — this product source of truth
- `AGENTS.md` — repository-scoped rules for coding agents
- `SECURITY.md` — reporting, supported versions, and security invariants
- `CONTRIBUTING.md` — branch, review, testing, and ownership workflow
- `THIRD_PARTY_NOTICES.md` — models, runtimes, dependencies, and licences
- `docs/ARCHITECTURE.md` — component and deployment design
- `docs/PROTOCOL.md` — pairing, API, job, and event contracts
- `docs/THREAT_MODEL.md` — assets, actors, boundaries, and mitigations
- `docs/MODEL_CATALOG.md` — approved model selection and evidence
- `docs/RESEARCH.md` — benchmark results and rejected hypotheses
- `docs/DECISIONS.md` — dated architecture decisions
- `docs/DEMO.md` — reproducible demonstration procedure
- `.github/pull_request_template.md` — evidence-based review checklist

### 17.3 Collaboration rules

Branch and merge rules. These are implemented in
[`CONTRIBUTING.md`](../CONTRIBUTING.md) and enforced by
`scripts/setup-branch-protection.sh`:

- Protect `main` and `dev`. Direct pushes to either branch are prohibited for
  every contributor, repository admins included.
- Every change reaches `main` and `dev` through a pull request. Work flows one
  way: member branch to `dev`, then `dev` to `main`.
- Member-branch pull requests into `dev` run no automated CI or required status
  checks, and pushes to `dev` start no GitHub Actions. The team may review and
  merge integration PRs directly; the local hook and team discipline protect
  `dev` until server-side rules are available.
- Automated CI runs only for the `dev` to `main` release pull request. That
  release merges when its required checks pass.
- Approving reviews are **not** required, and any contributor may merge a pull
  request, including their own.
- Reviews are advisory and requested by hand. The repository carries no
  `CODEOWNERS` file: automatic review requests are notification noise when no
  review is required.
- The release gate is the pull request and its checks, not an approval quota.
  Add build, test, and validation jobs to the `main` required-check list as
  they land; do not run them for member pull requests into `dev`.

Evidence and honesty rules:

- Keep decisions evidence-backed and dated.
- Label features as planned, prototyped, verified, or deferred.
- Do not commit generated AI output without human review.
- Do not claim benchmarks that are not reproducible from repository instructions.

> **Changed 2026-08-31.** This section previously required at least one owner
> review for security, protocol, and model-catalogue changes. The team replaced
> that with the rules above: the enforced constraint is that nothing is pushed
> directly to `main` or `dev`, while merging stays open to anyone once checks
> pass, so a six-person sprint never blocks on one reviewer. Revisit before any
> external release — a review quota is cheap to reinstate with
> `REQUIRED_APPROVALS=1 ./scripts/setup-branch-protection.sh` plus
> `require_code_owner_review`.

> **Changed 2026-08-31 (CI scope).** Automated PR checks now run only on the
> `dev` to `main` release. Member branches still reach `dev` through PRs, but
> neither those integration PRs nor pushes to `dev` start Actions, so limited
> capacity is spent on the release candidate once.

---

## 18. Working Technology Choices

These choices reduce prototype risk but remain subject to Day 1 research and hardware validation.

| Area | Working choice | Status |
|---|---|---|
| Public site | React/Vite deployed to Vercel or equivalent | Candidate |
| Desktop shell | Tauri or an equivalent lightweight cross-platform shell | Decision required |
| Coordinator service | Python with FastAPI | Candidate |
| Worker service | Python with FastAPI | Candidate |
| Streaming | Server-Sent Events for one-way job streams | Candidate |
| Transport | HTTPS over local Wi-Fi/Ethernet | Settled direction |
| State | SQLite on coordinator | Candidate |
| Primary runtime | Ollama where supported | Candidate |
| Platform runtime fallback | llama.cpp or MLX where required | Candidate |
| Retrieval | Embedded local vector/index store | Benchmark before choosing dependency |
| Sandbox | Docker with networking disabled where practical | Candidate; platform limits apply |
| Word generation | `python-docx` | Candidate |
| Checksums | Standard SHA-256 | Settled |

Docker should isolate coordinator tools and code execution where practical, but it does not erase Metal, CUDA, Windows, Linux, driver, or GPU-pass-through differences. Native inference is expected on some platforms.

The prototype should not add multiple runtime adapters, vector databases, event systems, or packaging frameworks before one real end-to-end path proves they are needed.

---

## 19. Non-Functional Requirements and Measurement Plan

These are prototype targets, not verified product claims. Replace them with measured results before presentation.

| ID | Metric | Initial target |
|---|---|---:|
| NFR-01 | External inference calls during offline demo | 0 |
| NFR-02 | Corrupted file transfers accepted | 0 |
| NFR-03 | Warm first-token latency | Under 2 seconds |
| NFR-04 | Basic HTML task on warm worker | Under 12 seconds |
| NFR-05 | Prompt/small-file LAN overhead | Under 200 ms |
| NFR-06 | Concurrent independent task types | At least 2 |
| NFR-07 | Routing accuracy on curated prompt set | At least 90% |
| NFR-08 | Worker-loss detection | Under 5 seconds |
| NFR-09 | Distributed makespan improvement over sequential baseline | At least 30% |
| NFR-10 | Duplicate final writes after retry | 0 |

### Measurement rules

- Measure one-device and distributed runs on the same task set.
- Report time to first output and end-to-end completion separately.
- Report cold and warm model behaviour separately.
- Record RAM, VRAM, queue time, and temperature where reliable.
- Score coding, OCR, retrieval, and document quality separately.
- Do not publish one universal “AI accuracy” number.
- Do not claim lower energy or thermal stress without comparable measurements.

---

## 20. Output Verification

### 20.1 Coding

A coding result is successful only when:

- The patch targets approved paths.
- The patch applies cleanly in the temporary workspace.
- The requested validation runs.
- Command, output, and exit status are recorded.
- The coordinator verifies the patch before any final write.

### 20.2 OCR and scanned documents

An OCR result must include:

- Original document reference and checksum
- Extracted text
- Page association
- Confidence or uncertainty where supported
- Explicit unresolved fields
- No fabricated value for missing or unreadable content

### 20.3 Knowledge-grounded artifacts

A generated document must include:

- Relevant local source references
- Page or section information
- Extracted findings
- Unresolved uncertainties
- Artifact path and checksum

### 20.4 Escalation

Low-confidence results may be:

- Retried with different settings
- Routed to a stronger eligible local model
- Returned for human review

The system must not silently transform uncertainty into certainty.

---

## 21. Five-Day Research and Prototype Plan

The goal is to answer the questions that could kill the product while building one real vertical slice.

### Day 1: Repository and decision foundation

- Confirm team ownership, visibility, and licence direction
- Add members and protect the primary branch
- Adopt the PRD and create architecture/security decision documents
- Assign component owners
- Record exact hardware and operating systems
- Choose the thinnest viable desktop/service stack
- Deploy a minimal public landing page
- Create issues for every prototype acceptance criterion

Exit evidence:

- Owners named
- Licence conflict tracked
- Architecture decision recorded
- Site URL or local deploy proof
- Hardware inventory complete

### Day 2: First real Mac-to-worker inference

- Start the coordinator on the Mac
- Start one worker on Windows
- Implement explicit pairing or a clearly labelled prototype trust flow
- Add heartbeat and capability reporting
- Route one real prompt to one real local model
- Stream tokens and completion state back to the Mac
- Record LAN latency and cold/warm behaviour

Exit evidence:

- Reproducible prompt-to-worker-to-Mac path
- Device and model visible
- No mocked inference in the claimed path

### Day 3: Model catalogue and provisioning

- Implement the approved model-manifest schema
- Detect OS, RAM, VRAM, and runtime
- Integrate installation through one existing runtime
- Verify one model checksum
- Display compatibility and installed state
- Document connected setup and air-gapped import
- Benchmark candidate core and specialist models

Exit evidence:

- One verified catalogue entry installed
- Compatibility result visible
- Licence/source information recorded

### Day 4: Signature concurrent demonstration

- Add a coding worker path
- Add an OCR/document worker path
- Run both jobs concurrently in separate chats
- Validate the coding result
- Preserve OCR uncertainty and page mapping
- Show selected worker, model, and routing reason
- Measure sequential and distributed completion times

Exit evidence:

- Two real concurrent jobs
- Verified output from both workflows
- Comparable timing data

### Day 5: Sovereign proof and submission evidence

- Disconnect Internet access or enforce egress blocking
- Re-run the signature workflow
- Capture zero-outbound-traffic evidence
- Exercise cancellation or worker loss
- Complete threat-model and third-party licence inventory
- Replace projected metrics with measured results
- Rehearse and record the demo
- Label unfinished capabilities honestly

Exit evidence:

- Reproducible offline demo
- Network evidence
- Benchmark table
- Risk and limitation summary
- Backup recording

### Research priorities

Research only questions that materially affect feasibility:

- LAN latency and streaming reliability
- Model correctness on the chosen demo tasks
- VRAM/RAM fit and cold-load time
- macOS/Windows runtime compatibility
- Offline installation and checksum verification
- Worker failure and idempotent retry
- Pairing and credential storage
- Model, dependency, and distribution licences

---

## 22. Team Ownership

### Member 1: Coordinator and routing

- Job lifecycle
- Capability registry
- Deterministic routing
- Context packaging
- Failure handling
- Canonical state

### Member 2: Worker and inference

- Worker API
- Runtime integration
- Streaming
- Health and resource reporting
- Pairing

### Member 3: Product UI and public site

- Multi-chat workspace
- Model/capability installer UI
- Worker dashboard
- Job timeline and routing explanation
- Public landing/download site

### Member 4: Workflows, security, and verification

- OCR pipeline
- Local RAG
- Word generation
- Code sandbox
- Evaluation dataset
- Threat model and zero-egress evidence

If fewer people are available, combine coordinator and worker ownership first. Do not divide work into many empty components merely to give everyone a folder.

---

## 23. Acceptance Criteria and Demo Flow

### 23.1 Five-day alpha acceptance

- [ ] The repository documents product scope, architecture, security boundaries, and ownership.
- [ ] The Mac can send one real prompt to one worker.
- [ ] The worker calls a real local model and streams output back.
- [ ] The UI or logs identify the worker and model.
- [ ] One model manifest includes source, licence, compatibility, and checksum.
- [ ] The public site clearly separates download/distribution from offline runtime.
- [ ] Unimplemented features are labelled as planned, not demonstrated.

### 23.2 Finals MVP acceptance

- [ ] The system works on one mid-range workstation.
- [ ] The same application can join a second device as a worker.
- [ ] A third device can join for the concurrent demonstration where hardware permits.
- [ ] At least two task types are routed automatically.
- [ ] OCR and coding jobs can run concurrently on different devices.
- [ ] A scanned report is processed locally with page mapping and uncertainty.
- [ ] Relevant passages are retrieved from a local SOP with citations.
- [ ] An approval note is generated as a Word document.
- [ ] A repository coding task runs inside an isolated sandbox.
- [ ] The generated patch is validated and returned with evidence.
- [ ] The UI shows device, model, capability, and routing reason.
- [ ] Worker loss does not cause duplicate final writes.
- [ ] No external inference or data call occurs during the offline demonstration.
- [ ] Installed models expose source and licence information.
- [ ] Results and artifacts remain within the trusted environment.

### 23.3 Demonstration sequence

#### Preparation

1. Show the public website and release checksum as a separate distribution surface.
2. Confirm all required application and model artifacts are already installed.
3. Disconnect Internet access while preserving the isolated LAN.

#### Standalone baseline

1. Open SovereignMesh on the Mac.
2. Run or queue the selected OCR and coding tasks locally.
3. Record baseline completion time and resource use.

#### Distributed signature workflow

1. Display the paired trusted devices and capabilities.
2. Upload a scanned inspection report.
3. Start extraction, local SOP retrieval, and Word-note generation.
4. Open a second chat while the document task runs.
5. Request a small repository change.
6. Route coding and OCR to different workers.
7. Show concurrent progress and streamed results.
8. Open the generated Word document and cited evidence.
9. Show the returned patch and successful validation.

#### Sovereign and performance proof

1. Compare standalone and distributed completion time.
2. Show device/model assignments and audit events.
3. Show that original prompts and file checksums were preserved.
4. Show the network monitor or equivalent zero-egress evidence.

#### Resilience bonus

Disconnect one non-critical worker and demonstrate a safe requeue or explicit recoverable failure without duplicate output.

---

## 24. Risks, Mitigations, and Open Decisions

### 24.1 Major risks

| Risk | Why it matters | Mitigation |
|---|---|---|
| Project becomes only a networking demo | SIH requires an agentic workbench and real deliverables | Complete one document workflow and one verified coding workflow |
| Scope exceeds five days | Website, desktop packaging, models, security, and workflows are each substantial | Prove one connection first; defer production packaging and broad features |
| Small models produce weak output | Distribution does not compensate for bad answers | Benchmark specialist models and validate outputs |
| Wi-Fi or device instability | Live demonstration may fail | Prefer wired LAN where possible; heartbeat, timeout, and backup recording |
| Cold model loading dominates latency | Network routing may show no benefit | Preload demo models and report cold/warm separately |
| Cross-platform runtime differences | Docker does not remove Metal/CUDA/driver constraints | Common node API with the fewest necessary native adapters |
| Security surface grows with workers | More nodes mean more credentials and exposed services | Pairing, revocation, loopback runtimes, minimal APIs, and threat modelling |
| Air-gap claim conflicts with downloads | Models cannot download without connectivity | Separate connected provisioning from offline runtime and USB/internal import |
| Arbitrary model installation enables supply-chain risk | Model repositories may include executable code | Curated catalogue and verified manifests only in MVP |
| Licensing is inconsistent | Apache repository and proprietary claim cannot both be assumed | Resolve ownership and licence before contributions/distribution |
| Public installer is mistaken for public source | Distribution and source visibility are separate decisions | Document licence, source policy, and installer terms clearly |
| Repository transfer is too large | Latency and confidentiality suffer | Send only relevant files and return patches |
| Confidential content leaks into logs | Audit data becomes a liability | Metadata-only defaults and synthetic demo data |
| Retry duplicates changes | Coding and document writes may be applied twice | Unique attempt IDs and coordinator-owned idempotent final writes |
| Any-node control is attempted too early | Replication and failover multiply complexity | Keep the Mac as fixed v1 coordinator |
| Unverified performance claims reduce credibility | Judges can challenge thermal, quality, or latency claims | Present measured results and limitations only |

### 24.2 Open decisions

| ID | Decision | Needed by |
|---|---|---|
| OD-01 | Choose external product name: AegisForge, SovereignMesh, or another final name | Before public branding |
| OD-02 | Resolve Apache-2.0 versus proprietary/open-source direction and ownership | Before substantial contributions or releases |
| OD-03 | Confirm exact SIH/college IP and submission requirements | Day 1 |
| OD-04 | Choose desktop packaging approach | Day 1 |
| OD-05 | Confirm primary model runtime on macOS and Windows | Day 2 |
| OD-06 | Decide whether embeddings belong in the mandatory coordinator pack | After Day 3 footprint benchmark |
| OD-07 | Select final core, coding, OCR, reasoning, and voice models | After correctness/latency/licence benchmarks |
| OD-08 | Define alpha pairing security versus finals pairing security | Day 2 |
| OD-09 | Choose embedded retrieval implementation only after corpus benchmark | Before RAG workflow |
| OD-10 | Define supported installer platforms for the first public alpha | Before public download |

---

## 25. Final Position and Continuation Context

SovereignMesh is not a cloud wrapper, a model-sharding experiment, or a collection of unrelated model endpoints. It is intended to be a complete sovereign workbench with a public distribution surface and a private local runtime.

Its durable v1 architecture is:

- One application installed on every trusted device
- Mac as the fixed coordinator and primary interface
- Standalone operation when no workers are available
- Trusted worker devices for specialist capabilities and concurrent execution
- Curated core and optional model packs
- Connected setup or verified air-gapped import
- Coordinator-owned context, files, artifacts, and final writes
- Local agentic document and coding workflows
- Visible model, device, audit, integrity, and zero-egress evidence

The first implementation milestone is not a complete ChatGPT replacement. It is one real, measured Mac-to-worker inference path. The next milestone is the signature proof: concurrent OCR and coding work on separate trusted devices, returned to one coherent offline workspace with validation and network evidence.

Future any-device input/output and coordinator roles remain compatible with this direction but require replicated state, failover, and conflict handling that are intentionally outside v1.

This PRD is the starting point for the repository's architecture, workflow, security, model-catalogue, research, and demo documents. Any later decision that changes these requirements should be recorded in the repository and reflected here rather than left only in chat.
## Comment by Tanvi
>  
>
> I suggest adding an **AI Health & Sovereignty Dashboard** for administrators. It should provide a real-time view of server health, AI model status, CPU/RAM/GPU usage, active jobs, trusted workers, and network security.
>
> A key feature should be **Internet/Egress Monitoring**. If any AI component attempts to access an external service while offline/egress blocking is enabled, the connection should be blocked and recorded.
>
> The dashboard should visibly show:
>
> * Internet Access: **BLOCKED**
> * External AI/API Calls: **0**
> * External Connections: **0**
> * Blocked Attempts: **N**
> * Local AI/RAG/OCR: **ACTIVE**
>
> This makes our sovereignty claim **visible and auditable**, rather than simply stating that data stays inside the organization.
>
> — **Tanvi Shinde**
