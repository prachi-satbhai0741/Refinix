<div align="center">

# AegisForge

**Refinix — a private local agent harness for confidential industrial knowledge work**

*A Smart India Hackathon 2026 submission for running open-weight, multimodal AI entirely on local infrastructure, with trusted-device task orchestration and demonstrable, verifiable offline operation.*

[![SIH 2026](https://img.shields.io/badge/Smart%20India%20Hackathon-2026-FF6B00?style=flat-square)](https://www.sih.gov.in/)
![Problem Statement](https://img.shields.io/badge/Problem%20Statement-SIH26117-0057B8?style=flat-square)
![Category](https://img.shields.io/badge/Category-Software-2E8B57?style=flat-square)
![Theme](https://img.shields.io/badge/Theme-Smart%20Automation-7B2CBF?style=flat-square)
![Status](https://img.shields.io/badge/Status-Research%20%26%20Prototype%20Planning-F59E0B?style=flat-square)
![License](https://img.shields.io/badge/License-Apache--2.0-green?style=flat-square)

</div>

---

## Table of Contents

- [SIH Problem Statement](#sih-problem-statement-117)
- [What Is AegisForge?](#what-is-aegisforge)
- [Why This Problem Is Hard](#why-this-problem-is-hard)
- [Design Philosophy: Coordinator, Not a Cluster](#design-philosophy-coordinator-not-a-cluster)
- [Product Surfaces and Setup](#product-surfaces-and-setup)
- [Proposed Innovation: The Sovereign Proof Card](#proposed-innovation-the-sovereign-proof-card)
- [Project Boundaries & Trust Model](#project-boundaries--trust-model)
- [Repository Structure](#repository-structure)
- [Current Status](#current-status)
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

## What Is AegisForge?

**AegisForge** is the name of this repository. **Refinix** is the current
working name for the product and its underlying architecture.

Refinix is one installable application with dedicated **Chat**,
**Documents**, and **Code** surfaces over a shared local agent harness. A
**Control Center** manages models, jobs, approvals, paired compute, health, and
sovereignty evidence.

Every installation creates a local workspace and remains useful on its own.
Pairing is an optional, reversible relationship: the workspace coordinator may
route bounded work to compatible trusted devices or a private server, but those
nodes never receive canonical workspace ownership merely by joining.

This is a deliberate architectural position, not an oversight — see [Design Philosophy](#design-philosophy-coordinator-not-a-cluster) below for why.

> **Status:** Day 1 implementation has started with [shared contracts and passing local checks](backend/contracts/README.md). No application runtime, model bundle or executable product exists yet. This README and the linked PRD describe the intended system, its constraints, and its demonstration plan.

---

## Why This Problem Statement

It's worth being explicit about why "just run a local LLM" doesn't satisfy the challenge, because the difficulty is exactly what the evaluation will probe:

- **Model diversity without redesign.** No single open-weight model is simultaneously the best choice for OCR-heavy document work, code generation, and long-context summarisation. A workbench that hardcodes one model becomes obsolete the moment a better open-weight release ships. The router has to be a first-class component, not a wrapper around one model.
- **"Agentic" is not "chatty."** A system that answers a question well once is not the same as a system that can plan a multi-step task, call tools, check its own output, and recover from a failed step. The challenge explicitly asks for the latter.
- **Proof, not policy.** Any team can claim "no data leaves the premises." The challenge specifically asks for a way to *show* it — live, during a demo — which means network isolation and evidence-collection have to be designed into the system from the start, not retrofitted for a demo screenshot.
- **Real file outputs, correctly formatted.** Producing a `.docx`, `.xlsx`, or `.pptx` that actually opens correctly and looks like something a human would sign off on is a meaningfully different engineering problem than producing well-formatted chat text.

---

## Design Philosophy: Coordinator, Not a Cluster

Refinix is **not** model sharding, distributed inference, or pooled VRAM across machines. Every job runs as **one complete model on one selected device** — there is no attempt to split a single model's weights or a single job's computation across multiple machines.

This matters for two reasons:

1. **Reliability in the field.** Industrial deployments are often a single workstation or a small number of machines on a closed LAN, not a data-center-grade cluster. A design that depends on tightly-coupled multi-node inference is fragile in exactly the environments this system targets. Standalone (single-device) operation must always work — additional devices are a capability and concurrency upgrade, never a requirement.
2. **Auditability.** When one job maps to one model on one device, the resulting evidence trail (which model, which device, which checksum, what output) is simple to construct and simple to verify. Distributed inference across devices would make the "proof of sovereignty" requirement significantly harder to demonstrate convincingly.

Extra trusted devices, when present, allow the coordinator to run independent jobs — for example, an OCR/document job and a coding job — **concurrently**, and to route specialist work (e.g., a vision-heavy task) to whichever local device is best equipped to handle it.

---

## Product Surfaces and Setup

First launch detects the device and existing runtimes, requires a compatible
main engine, lets the user enable capability packs, shows the full model
download and licence plan, verifies manifests, and runs real local self-tests.
It does **not** ask the user to choose a permanent coordinator, worker, or server
role.

| Surface | Purpose |
|---|---|
| Chat | General local agent and local knowledge |
| Documents | OCR/vision, retrieval, citations, and generated artifacts |
| Code | Repository context, isolated execution, validation, and patches |
| Control Center | Models, devices, jobs, approvals, health, and sovereignty evidence |

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
asked to take on faith. This is proposed, not implemented or verified; its
current contract is in [evaluation.md](docs/evaluation.md#7-sovereign-proof-card).

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
AegisForge/
├── backend/              # Planned coordinator, worker, router, and runtime boundary
├── frontend/             # Planned desktop workspace and public-site boundary
├── docs/
│   ├── prd.md             # Short product contract and priorities
│   ├── architecture.md    # Harness, nodes, state, jobs, and local data
│   ├── workflows.md       # Onboarding and task flows
│   ├── security.md        # Trust, privacy, sandbox, and proof boundaries
│   ├── model-catalog.md   # Model packs, manifests, and provisioning
│   └── evaluation.md      # Prototype plan, acceptance, metrics, and demo
├── agent-memory/         # Searchable record of repository-affecting work and decisions
├── CONTRIBUTING.md       # Branch, review, and release workflow
├── AGENTS.md             # Repository-wide implementation rules and conventions
└── README.md
```

## Start Here

There is nothing to install or run yet. Before contributing code:

1. Start with the [documentation map](docs/README.md) and short
   [PRD](docs/prd.md).
2. Do not begin framework scaffolding ahead of an approved v1 baseline and
   measured evidence from one local inference path followed by one real
   paired-worker path.

## Contributing

Follow the process in [CONTRIBUTING.md](CONTRIBUTING.md).
Server-side branch protection is **not yet active**, so this workflow is currently enforced by team discipline rather than tooling — please follow it deliberately until protection rules are configured.

## Licence

This repository is currently licensed under [Apache-2.0](LICENSE). The final product's licensing and ownership position remains an open decision tracked in the [PRD](docs/prd.md), and may change before submission.

---

<div align="center">

*Built for Smart India Hackathon 2026 — Problem Statement SIH26117 — Mangalore Refinery and Petrochemicals Limited (MRPL)*

</div>

---

## Team

**Team Name: Rokunin Sync**
