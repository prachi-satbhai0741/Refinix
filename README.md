<div align="center">

# Refinix

**Refinix — a private local agent harness for confidential industrial knowledge work**

*A Smart India Hackathon 2026 submission for running open-weight, multimodal AI entirely on local infrastructure, with trusted-device task orchestration and demonstrable, verifiable offline operation.*

[![SIH 2026](https://img.shields.io/badge/Smart%20India%20Hackathon-2026-FF6B00?style=flat-square)](https://www.sih.gov.in/)
![Problem Statement](https://img.shields.io/badge/Problem%20Statement-SIH26117-0057B8?style=flat-square)
![Category](https://img.shields.io/badge/Category-Software-2E8B57?style=flat-square)
![Theme](https://img.shields.io/badge/Theme-Smart%20Automation-7B2CBF?style=flat-square)
![Status](https://img.shields.io/badge/Status-Prototype%20%7C%20Beta%20in%20progress-F59E0B?style=flat-square)
![License](https://img.shields.io/badge/License-Apache--2.0-green?style=flat-square)

</div>

---

## Table of Contents

- [SIH Problem Statement](#sih-problem-statement-117)
- [What Is Refinix?](#what-is-refinix)
- [Why This Problem Statement](#why-this-problem-statement)
- [Design Philosophy: Coordinator, Not a Cluster](#design-philosophy-coordinator-not-a-cluster)
- [Product Surfaces and Setup](#product-surfaces-and-setup)
- [Proposed Innovation: The Sovereign Proof Card](#proposed-innovation-the-sovereign-proof-card)
- [Project Boundaries & Trust Model](#project-boundaries--trust-model)
- [Repository Structure](#repository-structure)
- [Current Status](docs/evaluation.md#current-status)
- [Getting Started](#start-here)
- [Contributing](#contributing)
- [License](#licence)

---

## SIH Problem Statement 117

| Field | Details |
|---|---|
| **Problem Statement ID** | SIH26117 |
| **Title** | Sovereign On-Premise Agentic AI Workbench using Open-Weight Multimodal LLMs for Confidential Industrial Work |
| **Organisation** | Mangalore Refinery and Petrochemicals Limited (MRPL) |
| **Category** | Software |
| **Theme** | Smart Automation |
| **Team Name** | Rokunin Sync |

### Challenge Description

Industrial and public-sector organisations — refineries, PSUs, defence-linked manufacturing units, and government offices — generate a large volume of sensitive but routine knowledge work: approval notes, board presentations, engineering calculations, internal tooling code, review of scanned drawings, and inspection reports. This work regularly involves confidential material such as Piping & Instrument Diagrams (P&IDs), financial data, vendor negotiations, unreleased designs, and internal correspondence.

Company policy keeps this data strictly on-premises, which means employees today face a binary choice: do the work manually and forfeit the productivity gains modern AI tools offer, or informally paste confidential material into public cloud AI assistants — a real and growing data-leak risk that policy alone does not prevent.

The challenge calls for a **self-hosted, air-gapped AI workbench** that:

- Runs multiple open-weight multimodal models locally and **automatically selects** the appropriate model for a given task (a coding request should not be handled by the same model or strategy as a document summarisation request).
- Supports adding new open-weight models over time **without redesigning the system**, given how quickly this space evolves.
- Behaves as a genuine **agent** — planning multi-step work, invoking local tools (file I/O, sandboxed code execution, spreadsheet operations, internal document search), and iterating rather than answering once and stopping.
- Handles **multimodal input**: scanned PDFs, handwritten notes, engineering drawings, and photographs, using on-device OCR and vision models.
- Produces **real deliverables** — approval notes, Word/Excel/PowerPoint files, working code, calculations with visible steps — not chat transcripts.
- Grounds itself in the **organisation's own knowledge base** (manuals, SOPs, past correspondence) through a local retrieval connector, with nothing leaving the premises.
- Provides **visible, demonstrable proof** — through logs or a live network monitor — that no external network call is made at any point during operation. This proof, not a written claim, is what the challenge treats as evidence of sovereignty.

The current requirement interpretation, open design decisions, and demonstration plan are maintained in the project [PRD](docs/prd.md), which should be treated as the living source of truth alongside this README.

---

<a id="what-is-aegisforge"></a>

## What Is Refinix?

**Refinix** is the product name; **refinix** is the selected repository name
(formerly AegisForge). The GitHub rename is pending a repository administrator: the
current remote remains `prachi-satbhai0741/AegisForge`. Existing checkout paths and
compatibility-sensitive `.aegisforge` application data remain unchanged.

Refinix is one installable application with dedicated **Chat** and **Code**
surfaces over a shared local agent harness. **Settings**, reached from secondary
navigation, manages models, jobs, approvals, paired compute, health, and
sovereignty evidence. Document work is a capability inside Chat rather than a
separate top-level surface.

Refinix targets Windows, macOS and Linux, with three offline execution modes:
this device, trusted local-network peers and an organisation's private server.
A device can request and contribute work; only execution targets need the selected
models/tools installed. Pairing never merges personal workspaces. Automatic routing
chooses compatible model/device pairs using task needs, permissions and available
capacity, while the user retains model and execution-target control.

The open-source platform and a specialised paid offering share this core. The paid
offering adds authorised customer corpora, workflows, templates, deployment and
support; it does not require a cloud inference service.

> **Status, 2026-09-16:** The current app/worker source and recent reliability
> repairs are recorded in the [source audit](docs/evaluation.md#beta-source-audit).
> The production architecture is retained. [Band A, P01–P14](tasks.md#numbered-execution-tasks)
> leads to **Refinix Beta 0.1 / SIH Reviewer Preview**, followed by versioned
> improvements and finals/production qualification. No public Beta support profile
> is accepted yet; a working checkout or old Mac bundle is not a release.

---

## Why This Problem Statement

It's worth being explicit about why "just run a local LLM" doesn't satisfy the challenge, because the difficulty is exactly what the evaluation will probe:

- **Model diversity without redesign.** No single open-weight model is simultaneously the best choice for OCR-heavy document work, code generation, and long-context summarisation. A workbench that hardcodes one model becomes obsolete the moment a better open-weight release ships. The router has to be a first-class component, not a wrapper around one model.
- **"Agentic" is not "chatty."** A system that answers a question well once is not the same as a system that can plan a multi-step task, call tools, check its own output, and recover from a failed step. The challenge explicitly asks for the latter.
- **Proof, not policy.** Any team can claim "no data leaves the premises." The challenge specifically asks for a way to *show* it — live, during a demo — which means network isolation and evidence-collection have to be designed into the system from the start, not retrofitted for a demo screenshot.
- **Real file outputs, correctly formatted.** Producing a `.docx`, `.xlsx`, or `.pptx` that actually opens correctly and looks like something a human would sign off on is a meaningfully different engineering problem than producing well-formatted chat text.

---

## Design Philosophy: Coordinator, Not a Cluster

Refinix distributes complete jobs or bounded workflow steps among trusted devices.
Each model invocation runs on one selected target; there is no model sharding or
pooled VRAM. Keep canonical workspace state and final-write authority with the
requester's coordinator. Independent Code and Chat jobs may run concurrently on
different targets, using receiver-side capacity reservations to avoid overloading
a device.

The existing Docker/K3s/Redis backend remains useful for managed services and
isolated validation Jobs. It is an **optional server execution profile**, not a
requirement for desktop installation or peer membership. Windows/macOS/Linux
peers communicate through Refinix's authenticated application API; they do not
need to become Kubernetes nodes. See [architecture](docs/architecture.md).

---

## Product Surfaces and Setup

The production installer packages or graphically provisions its qualified
dependencies. First launch scans hardware and offers up to six compatible model
recommendations, highest suitability first, plus Show more and supported user
choices. Scores distinguish estimates from measured results; a fit score is not
accuracy. Warn for heavy choices and refuse known-incompatible execution.

Model downloads, imports and updates are explicit. Ordinary runtime, retrieval,
discovery and LAN execution require no Internet connection or cloud account.
The installer should not require terminal/package-manager/certificate setup;
unavoidable OS permissions and unsupported prerequisites must be explained.
A remote-only client can skip local models. These are target installer behaviours,
not a claim that the existing prototype package already provides them.

The first Beta is gated by a complete reviewer journey on a narrow qualified
matrix, including real paired execution, routing and validated Code on an eligible
sandbox. Settings → Models remains available after onboarding for supported
provisioning, selection and safe removal. See the [model lifecycle](docs/model-catalog.md#persistent-model-management).
The [release contract](docs/releases.md#beta-01-publication) allows authenticated
manual package replacement/recovery for 0.1; in-app updates and broader platform
matrices follow. A main change reaches users only as an accepted, versioned release.

Preserve the existing UI:

| Surface | Purpose |
|---|---|
| Chat | General local agent and local knowledge; document work arrives here as a selectable skill with attachments |
| Code | Repository context, isolated execution, validation, and patches |
| Settings | Models, devices, jobs, approvals, health, and sovereignty evidence — secondary navigation |

For each task the user may choose Auto, this device, trusted devices, or a
specific paired target. Independent jobs can run concurrently where hardware
permits. The coordinator retains canonical state and exactly-once final-write
authority.

---

## Proposed Innovation: The Sovereign Proof Card

For every completed job, the proposed **Sovereign Proof Card** is intended to bundle together, in one inspectable artifact:

- The **routing decision and its rationale** — which model and device were selected, and why.
- **File checksums** for any generated deliverables, so outputs can be verified as untampered.
- **Validation results** — for example, sandbox test output for a coding task, or extraction confidence for an OCR task.
- **Observed zero-egress evidence** — a record, tied to that specific job, that no external network call occurred during its execution.

The goal of the Proof Card is to make the project's central sovereignty claim
**inspectable during a live demonstration**, rather than something judges are
asked to take on faith. The current [builder](backend/coordinator/proof.py) and UI
exist; network evidence is still unavailable. Source existence does not verify
egress enforcement. The [evidence contract](docs/evaluation.md#7-sovereign-proof-card)
and [Beta acceptance](docs/evaluation.md#beta-acceptance) govern claims.

---

## Project Boundaries & Trust Model

These constraints are treated as non-negotiable design requirements, not aspirational goals:

- **No silent network dependency.** Runtime operation must not require the public Internet, telemetry, analytics, or any background network call the user has not explicitly authorised.
- **Least-privilege workers.** Worker devices receive only the context required for the specific task assigned to them, and may write only inside a temporary workspace assigned to that job — never directly to the coordinator's file system.
- **Local-only network exposure.** Local model runtimes bind to loopback (`127.0.0.1`) by default; worker APIs expose only the minimum LAN surface needed for coordinator–worker communication, and nothing is exposed beyond the local network.
- **Isolated sandboxes.** Coding sandboxes run without network access by default and under bounded CPU/memory/time limits, so that a runaway or malicious generated script cannot exfiltrate data or exhaust host resources.
- **Full model provenance.** For every model in use, the system records its source, license, file hash, runtime, and version — both for reproducibility and so that license compliance can be audited.
- **Nothing sensitive enters version control.** Model weights, installers, secrets, private documents, confidential scans, and local chat databases must never be committed to this repository. `.gitignore` and contributor review are both relied upon to enforce this.

---

## Repository Structure

```text
refinix/
├── backend/
│   ├── contracts/         # Shared job, attempt, event and approval contract (draft)
│   ├── coordinator/       # The running local application: state, runtime, API, UI server
│   └── worker-image/      # C04 build inputs; no image built yet
├── desktop/               # Native window, startup lifecycle, icons and macOS packaging
├── frontend/
│   ├── app/               # The application interface actually served by the coordinator
│   └── design/            # Design track's visual reference; not served by the app
├── docs/
│   ├── prd.md             # Short product contract and priorities
│   ├── architecture.md    # Harness, nodes, state, jobs, and local data
│   ├── workflows.md       # Onboarding and task flows
│   ├── security.md        # Trust, privacy, sandbox, and proof boundaries
│   ├── model-catalog.md   # Model packs, manifests, and provisioning
│   └── evaluation.md      # Prototype plan, acceptance, metrics, and demo
├── agent-memory/         # Searchable record of repository-affecting work and decisions
├── TechStack.md          # Recommended languages and technologies for each layer
├── CONTRIBUTING.md       # Branch, review, and release workflow
├── AGENTS.md             # Repository-wide implementation rules and conventions
└── README.md
```

## Start Here

The following is the **existing developer/prototype launch path**, not the
production installer experience. On the configured macOS coordinator, double-click `desktop/dist/Refinix.app`,
or run:

```bash
open /Users/adityatadge/Documents/GitHub/AegisForge/desktop/dist/Refinix.app
```

The native app uses the installed Ollama model `qwen3.5:4b-q4_K_M` and starts
Ollama when needed. Keep its Dock icon for later launches. Setup on another
machine requires the [desktop setup handoff](desktop/README.md#setup-handoff).
For a source run, `desktop/.venv/bin/python -m desktop` opens the native window;
`./.venv/bin/python -m desktop --no-window` starts local services using the
existing backend dependencies, including Pydantic. `python3 -m backend.coordinator`
still starts the coordinator on its own, unchanged.

Details, including what the application deliberately does **not** do, are in
[backend/coordinator/README.md](backend/coordinator/README.md) and
[desktop/README.md](desktop/README.md).

### What reads what, right now

See the [current source snapshot](docs/evaluation.md#current-status) for document,
image, Code, worker and packaging boundaries. Runtime capability reports must
reflect installed models/tools, host compatibility and observed self-tests;
source availability alone is not proof that a capability works on every device.

Before implementation:

1. Read the [PRD](docs/prd.md) for the product contract and
   [architecture](docs/architecture.md) for task placement and state ownership.
2. Use [TechStack.md](TechStack.md) to distinguish existing dependencies from
   qualification candidates, including bundled llama.cpp and local embeddings.
3. Follow [tasks.md](tasks.md#numbered-execution-tasks) for outcome-based gates.
   Historical C/E/AF setup records explain the prototype; they do not prescribe
   permanent OS roles, production deadlines or a new frontend framework.

## Contributing

Follow the process in [CONTRIBUTING.md](CONTRIBUTING.md).
Server-side branch protection is **not yet active**, so this workflow is currently enforced by team discipline rather than tooling — please follow it deliberately until protection rules are configured.

## Licence

This repository is currently licensed under [Apache-2.0](LICENSE). The open-source core and specialised paid offering follow the [PRD](docs/prd.md); this documentation change does not relicense the repository, publish a release or grant rights to third-party corpora.

---

<div align="center">

*Built for Smart India Hackathon 2026 — Problem Statement SIH26117 — Mangalore Refinery and Petrochemicals Limited (MRPL)*

</div>

---

## Team

**Team Name: Rokunin Sync**
