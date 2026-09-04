# AegisForge Product Requirements

## Refinix: Private Local Agent Harness

| Field | Value |
|---|---|
| Document version | 2.1 |
| Status | Team-review draft; not an approved v1 baseline |
| Target | Smart India Hackathon Problem Statement SIH26117 |
| Repository name | AegisForge |
| Product working name | Refinix |
| Team name | Rokunin Sync |
| Last updated | 2026-09-01 |

This document is the short product contract. Detailed design belongs in the
linked architecture, workflow, security, model, hardware, and evaluation
documents; it should not be copied back into this file.

## 1. Product definition

Refinix is an installable, private agent harness for confidential
industrial knowledge work. It provides dedicated Chat, Documents, and Code
surfaces over one local coordinator, one policy boundary, and one auditable job
system.

Every installation is immediately useful on its own. When trusted compute is
available, the same application can route bounded work to paired devices or an
organisation-managed private server without changing the user's workspace.

> One private agent application for chat, documents, and code that works on one
> device and can safely use trusted local compute when available.

The alpha also proves the mentor-directed deployment shape: a
Docker-built worker image runs as Kubernetes-managed Pods, a Kubernetes Service
exposes the authenticated worker API, and Redis coordinates bounded ephemeral
work. Kubernetes is an execution profile for trusted compute; it does not make
standalone use depend on a cluster.

The repository contains product planning, the shared contract draft, and a
**running local coordinator** covering Chat and a minimum Control Center over
one local model. The distributed half of the product — worker, pairing, cluster,
Documents and Code workflows, approvals and offline evidence — is not built, and
each of those surfaces reports itself unavailable rather than implying otherwise.
No model, performance, security, or hardware claim becomes current product
evidence until it is reproduced and recorded.

## 2. Problem and intended outcome

Industrial and public-sector teams handle sensitive documents, drawings,
calculations, source code, correspondence, and internal procedures that should
not be sent to public AI services. They need local agentic assistance that can:

- choose an appropriate approved model for the task;
- plan bounded multi-step work and call local tools;
- understand scanned and multimodal material;
- search organisation-owned knowledge locally with citations;
- produce real documents, calculations, and verified code changes;
- show observable evidence that offline work did not use external inference;
- remain useful on one machine and gain capability or concurrency from trusted
  nearby compute.

This is the repository's current interpretation of SIH26117. The team must
retain an authoritative copy of the official problem statement and reconcile
material differences before freezing the v1 baseline.

## 3. Product surfaces

The interface presents four clear destinations:

| Surface | User intent | Harness behaviour |
|---|---|---|
| Chat | Ask, reason, and explore local knowledge | General agent with bounded local tools |
| Documents | Process scans, retrieve evidence, and generate artifacts | OCR/vision, local retrieval, citations, and document validation |
| Code | Inspect a selected repository and prepare verified changes | Bounded context, isolated execution, patch validation, and approval |
| Control Center | Understand and control the local installation | Models, devices, jobs, approvals, health, retention, and sovereignty evidence |

An agent profile is not merely a model. It combines a model, instructions,
allowed tools, workflow, approval policy, and output validator. One installed
model may back more than one compatible profile.

The Control Center is an operational surface, not another autonomous agent.

## 4. First-run setup

Installation must not ask the user to choose a permanent coordinator, worker,
or server role. First launch:

1. Creates a local node identity and local workspace automatically.
2. Detects the operating system, CPU, memory, GPU, free storage, and supported
   local runtimes.
3. Requires the user to choose a compatible main engine model.
4. Lets the user enable the Code and Documents capabilities.
5. Resolves the smallest required model and tool plan for those capabilities.
6. Shows source, licence, download size, expected memory use, and evidence
   status before confirmation.
7. Installs through an approved existing runtime or verifies an offline bundle.
8. Verifies manifests and checksums.
9. Runs a real local self-test for the main engine and every enabled capability.
10. Opens the application only with honestly reported capability status.

The main engine is mandatory for an interactive installation. A separate
specialist model is required only when the enabled capability cannot be served
correctly by an already installed compatible model. Semantic retrieval requires
an embedding model; basic local search does not.

Downloads occur only during an explicit connected-setup flow. Offline runtime
must not silently download, update, report analytics, or call a cloud model.
Air-gapped installations use verified removable-media or internal-server
bundles.

## 5. Dynamic compute participation

Coordinator, worker, and private-server are runtime responsibilities, not
installation identities.

- Every installation retains its own local workspace and can run locally.
- Pairing is explicit, authenticated, reversible, and managed from the Control
  Center.
- Joining another workspace as a worker does not merge or replace local chats,
  memory, files, rules, or artifacts.
- A paired worker receives only the bounded job context it needs and never
  becomes the canonical owner of the remote workspace.
- Disconnecting or revoking trust returns the installation to ordinary local
  operation without data migration.

Each task exposes an execution choice:

- Auto
- This device
- Trusted devices
- A specific paired device or private server

Auto routing uses deterministic capability and health evidence. The selected
model, device, and reason remain visible and manually overridable for debugging
and demonstrations.

Refinix performs task-level orchestration, not model sharding or combined
VRAM. One job step runs one complete model on one selected device. A
coordinator-managed workflow may pass validated, typed output between steps;
models do not communicate directly or share unrestricted memory.

## 6. Product invariants

1. Normal runtime operation requires no public Internet access.
2. Public-cloud inference, silent telemetry, analytics, crash uploads, and
   background update checks are forbidden in offline runtime.
3. Local model runtimes bind to loopback; workers expose only the minimum
   authenticated and encrypted LAN surface.
4. Canonical chats, context, rules, files, approvals, and final writes remain
   with the workspace coordinator.
5. Workers write only inside assigned temporary workspaces.
6. Tool execution is network-disabled by default and bounded by CPU, memory,
   runtime, process, and filesystem limits.
7. Canonical or consequential writes require the coordinator's recorded
   approval policy.
8. Models and dependencies require recorded source, licence, version or commit,
   integrity evidence, and material local changes.
9. Existing licence-compatible local/open-source components are preferred over
   rebuilding commodity functionality.
10. Features and evidence are labelled planned, prototyped, verified, or
    deferred; static documentation is never reported as runtime proof.

The enforceable boundaries are detailed in [security.md](security.md).

## 7. Release scope

### 7.1 Alpha: P0

The alpha must prove:

- one installation completes guided setup and real local main-engine inference;
- Chat, Documents, Code, and Control Center are distinct surfaces over one
  harness rather than separate applications;
- one real prompt travels from the primary workspace to one paired worker and
  streams back;
- one Docker-built worker image is deployed through Kubernetes, reaches Ready
  Pods behind a Service, and completes that paired-worker prompt;
- Redis carries only bounded queue, lease, heartbeat, cache, and event state;
  canonical workspace and final-write state remain on the coordinator;
- the original request, selected device, model, routing reason, and job state
  are visible;
- worker participation is reversible and does not move canonical state;
- one bounded workflow produces a validated result;
- consequential final writes pass through a recorded approval gate;
- offline execution records observable network and audit evidence;
- the setup and demonstration can be reproduced from repository instructions.

### 7.2 Finals target: P1

The finals target adds:

- standalone execution and trusted-mesh execution through the same interface;
- concurrent Documents and Code workflows on different eligible devices;
- scanned-report extraction with page mapping and explicit uncertainty;
- local SOP retrieval with citations and a generated Word approval note;
- a repository patch produced and validated in a network-disabled sandbox;
- authenticated pairing, revocation, worker-loss handling, and exactly-once
  final writes;
- a useful per-job Sovereign Proof Card and truthful Control Center evidence;
- supported Indian-language interaction produced entirely by local models.

### 7.3 Post-hackathon: P2

Post-hackathon objectives include:

- an organisation-managed on-premises or air-gapped server joining through the
  existing worker contract;
- multi-user identity, roles, queues, and administrative policy;
- one node participating in multiple remote workspaces concurrently;
- coordinator transfer, replicated state, failover, and conflict resolution;
- signed installers, controlled fleet updates, and broader governed model
  catalogues.

A private server is additional compute, not a public-cloud dependency or a
separate multi-user control plane.

## 8. Outcome requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-001 | Every interactive installation creates a local workspace and remains useful without another device | P0 |
| FR-002 | Guided setup selects and verifies the main engine plus dependencies required by enabled capabilities | P0 |
| FR-003 | Chat, Documents, Code, and Control Center use one harness, policy boundary, and job system | P0 |
| FR-004 | One real local prompt and one real paired-worker prompt complete without cloud inference | P0 |
| FR-005 | Pairing is explicit and reversible and never silently merges or moves canonical state | P0 |
| FR-006 | Routing is deterministic, capability-aware, visible, and overridable | P0 |
| FR-007 | Workers receive bounded context and write only inside assigned temporary workspaces | P0 |
| FR-008 | Agent actions pass through an enforceable automatic, approval-required, or denied policy | P0 |
| FR-009 | Jobs expose progress, model, device, validation, integrity, and network evidence | P0 |
| FR-010 | Offline runtime has no required external inference, telemetry, analytics, or update traffic | P0 |
| FR-011 | Documents can perform local OCR, retrieval, citation, and artifact generation | P1 |
| FR-012 | Code can return a validated patch without directly modifying the canonical repository | P1 |
| FR-013 | Independent Documents and Code jobs can run concurrently on separate eligible nodes | P1 |
| FR-014 | Worker interruption cannot produce duplicate final writes | P1 |
| FR-015 | Models support connected installation and verified air-gapped import | P1 |
| FR-016 | A private server can participate through the same worker contract | P2 |
| FR-017 | Multiple organisational users and policy roles are supported | P2 |
| FR-018 | Canonical workspace ownership can move between nodes safely | P2 |
| FR-019 | Supported Indian languages work offline for input and output, preserving equipment tags, units, and citations, and showing low confidence | P1 |
| FR-020 | A Docker-built worker image runs as Kubernetes-managed Pods behind a Service and completes one real bounded job | P0 |
| FR-021 | Redis coordinates ephemeral dispatch, leases, heartbeats, cache, and worker events without becoming canonical workspace storage | P0 |

## 9. Non-goals

The alpha and finals MVP do not include:

- model sharding or pooled VRAM;
- training or fine-tuning models;
- public-cloud inference;
- arbitrary executable model code;
- a multi-node or highly available Kubernetes control plane;
- a Redis cluster, Redis as canonical storage, or another message broker;
- a custom transport or Kubernetes operator;
- a universal model downloader or runtime abstraction;
- a generic multi-agent framework or visual workflow builder;
- unrestricted autonomous host modification;
- production-grade multi-user IAM, high availability, or automatic updates;
- perfect installers for every supported operating system;
- claims that ordinary laptops replace enterprise GPU servers.

## 10. Success measures

Prototype targets are hypotheses until measured:

| Measure | Target |
|---|---:|
| External inference calls during offline demo | 0 |
| Accepted corrupted transfers | 0 |
| Real paired-worker path | At least 1 |
| Ready worker Pods behind the Kubernetes Service | At least 1 |
| Canonical records lost after Redis restart | 0 |
| Concurrent independent workflow types | At least 2 for finals |
| Duplicate final writes after retry | 0 |
| Routing decision visible | Every demonstrated job |
| Required model provenance visible | Every installed demo model |

Detailed measurement rules and the demo sequence are in
[evaluation.md](evaluation.md).

## 11. Open decisions

| ID | Decision | Needed by |
|---|---|---|
| OD-01 | Confirm the authoritative SIH26117 wording and submission/IP terms | Before v1 baseline |
| OD-02 | Resolve the final product name and Apache-2.0 versus another ownership direction | Before substantial distribution |
| OD-03 | Choose the first cross-platform local runtime after hardware proof | **Resolved C02** — Ollama; see [model-catalog.md](model-catalog.md#od-03--ollama-is-the-first-runtime) |
| OD-04 | Choose the desktop packaging approach after the local harness path works | Before installer work |
| OD-05 | Select the main, document, coding, and embedding models from measured evidence | **Main engine resolved C02** — `qwen3.5:4b-q4_K_M`; the rest stay unprovisioned until C07 |
| OD-06 | Define prototype pairing credentials versus finals-grade pairing | **Recorded C02, unimplemented** — see [security.md §4.1](security.md#41-od-06--the-prototype-pairing-decision) |
| OD-07 | Decide whether semantic retrieval is enabled by default after footprint testing | Before onboarding is frozen |
| OD-08 | Pin the K3s release, Redis 7.2 patch and image digest, worker/sandbox image digests, and Service port | **Partly resolved C02** — K3s, Redis and base image pinned in [architecture.md §8.1](architecture.md#81-od-08--resolved-infrastructure-pins); worker/sandbox digests follow C04; ports 8443/30443 fixed by C01, deployment enforcement follows C05 |

## 12. Canonical document map

- [architecture.md](architecture.md) — harness, node, state, protocol, and local-data design
- [workflows.md](workflows.md) — onboarding, surfaces, approvals, and task flows
- [security.md](security.md) — trust, privacy, sandbox, supply chain, and evidence
- [model-catalog.md](model-catalog.md) — model packs, manifests, provisioning, and selection
- [devicespecifications.md](devicespecifications.md) — actual team hardware and open checks
- [evaluation.md](evaluation.md) — evidence rules, plan, metrics, acceptance, and demo
- [../CONTRIBUTING.md](../CONTRIBUTING.md) — branch, review, and release process

When these documents conflict, this PRD owns product scope while the focused
document owns implementation detail within that scope. Unresolved conflicts must
be recorded instead of silently choosing one.
