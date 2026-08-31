<div align="center">

# AegisForge

**SovereignMesh — a planned, air-gapped agentic AI workbench for confidential industrial knowledge work**

*A Smart India Hackathon 2026 project for running open-weight multimodal AI locally, with trusted-device task orchestration and verifiable offline operation.*

[![SIH 2026](https://img.shields.io/badge/Smart%20India%20Hackathon-2026-FF6B00?style=flat-square)](https://www.sih.gov.in/)
![Problem statement](https://img.shields.io/badge/Problem%20Statement-SIH26117-0057B8?style=flat-square)
![Category](https://img.shields.io/badge/Category-Software-2E8B57?style=flat-square)
![Theme](https://img.shields.io/badge/Theme-Smart%20Automation-7B2CBF?style=flat-square)
![Status](https://img.shields.io/badge/Status-Research%20%26%20Prototype%20Planning-F59E0B?style=flat-square)
![License](https://img.shields.io/badge/License-Apache--2.0-green?style=flat-square)

</div>

---

## SIH Problem Statement 117

| Field | Details |
|---|---|
| **Problem statement** | SIH26117 (serial no. 117) |
| **Title** | Sovereign On-Premise Agentic AI Workbench using Open-Weight Multimodal LLMs for Confidential Industrial Work |
| **Organisation** | Mangalore Refinery and Petrochemicals Limited (MRPL) |
| **Category** | Software |
| **Theme** | Smart Automation |

### Challenge description

Industrial organisations handle sensitive approval notes, engineering calculations,
inspection reports, drawings, code, and internal correspondence that cannot leave
their premises. The challenge calls for a self-hosted, air-gapped AI workbench
that uses open-weight multimodal models locally, selects suitable models for
different tasks, performs agentic tool-based work, and returns real deliverables
rather than chat responses alone.

The challenge expects local multimodal understanding, knowledge grounding,
sandboxed coding, and visible evidence that no external calls occur during
operation. See the [challenge listing](https://pscmr.ac.in/PSCMR/sih/index.html)
and the project [PRD](docs/prd.md) for the current requirement interpretation.

---

## What is AegisForge?

**AegisForge** is the repository name; **SovereignMesh** is the current product
and architecture working name. The project is designed as one installable
application that keeps a user's chats, files, job state, and final artifacts on
a local coordinator while routing independent work to compatible, trusted local
devices when available.

It is not model sharding or pooled VRAM. Each job runs on one complete model on
one selected device. Extra devices add specialist capability and concurrency;
the system must still work in standalone mode.

> **Status:** Research and prototype planning. No runtime source tree, package
> manifest, model bundle, or executable product exists in this repository yet.

---

## Intended workflow

1. Work in a local multi-chat workspace on the coordinator.
2. Select an eligible trusted device and local model for each task.
3. Run independent document/OCR and coding jobs concurrently where hardware
   permits.
4. Return citations, generated artifacts, patches, validation output, and job
   evidence to the coordinator.
5. Keep final writes controlled by the coordinator and retain canonical state
   locally.

## Proposed innovation: Sovereign Proof Card

For every completed job, the proposed **Sovereign Proof Card** would bring
together the routing reason, selected model and device, file checksums,
validation result, and observed zero-egress evidence. It is intended to make
the project's sovereignty claim inspectable during a demonstration—not merely
asserted. This is a proposed feature, not an implemented or verified one.

---

## Project boundaries

- Runtime operation must not require the public Internet, telemetry, analytics,
  or silent network calls.
- Workers receive only the context required for a task and write only inside
  assigned temporary workspaces.
- Local model runtimes bind to loopback; worker APIs expose the minimum required
  LAN surface.
- Coding sandboxes run without networking by default and with bounded resources.
- Model source, licence, file hash, runtime, and version must be recorded.
- Model weights, installers, secrets, private documents, confidential scans, and
  local chat databases must never be committed.

---

## Repository structure

```text
AegisForge/
├── backend/              # Planned coordinator, worker, router, and runtime boundary
├── frontend/             # Planned desktop workspace and public-site boundary
├── docs/
│   └── prd.md            # Product requirements and demonstration evidence
├── agent-memory/         # Searchable record of repository-affecting work
├── CONTRIBUTING.md       # Branch, review, and release flow
├── AGENTS.md             # Repository-wide implementation rules
└── README.md
```

## Start here

There is nothing to install or run yet. Read the [PRD](docs/prd.md), especially
the settled decisions, open decisions, security requirements, and five-day
prototype plan. Framework scaffolding should follow an approved v1 baseline and
measured evidence from the first Mac-to-worker local inference path.

## Contributing

Follow [CONTRIBUTING.md](CONTRIBUTING.md). The intended flow is a personal
branch → pull request to `dev` → checked release pull request from `dev` to
`main`. Server-side branch protection is not active yet, so the team must follow
the workflow deliberately.

## Licence

This repository is currently licensed under [Apache-2.0](LICENSE). The final
product's licensing and ownership position remains an open PRD decision.
