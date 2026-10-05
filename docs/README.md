# Refinix documentation

This directory contains the product contract, focused authorities, evidence/reference material and
historical records for Refinix.

The documentation structure is deliberately designed so an agent does **not** need to read a large
stack of overlapping design documents before every implementation task.

## Start here

Normal agent/developer context order:

1. [`../AGENTS.md`](../AGENTS.md) — how agents work, what needs permission, and how human checkpoints work.
2. [`PROJECT.md`](PROJECT.md) — the current product, architecture and workflow contract.
3. [`../tasks.md`](../tasks.md) — the current implementation phase and later phases.
4. Read **one focused authority only when relevant**:
   - [`security.md`](security.md)
   - [`model-catalog.md`](model-catalog.md)
   - [`releases.md`](releases.md)

That three-file core (`AGENTS.md` + `PROJECT.md` + `tasks.md`) should answer most implementation
questions.

Do not preload the entire documentation tree, archives or ledgers unless the current task genuinely
needs them.

## Authority map

| Document | Role |
|---|---|
| [`PROJECT.md`](PROJECT.md) | **Current canonical product/architecture/workflow contract** |
| [`security.md`](security.md) | Focused authority for security, privacy, trust, sandbox, supply chain and sovereignty evidence |
| [`model-catalog.md`](model-catalog.md) | Focused authority for model manifests, provisioning, selection and qualification |
| [`releases.md`](releases.md) | Focused authority for installers/packages, GitHub publication, application updates and recovery |
| [`../tasks.md`](../tasks.md) | Standalone Beta sequence: Phase 1 -> Phase 2 -> local Phase 4 -> Phase 5; Phase 3 and peer acceptance after Beta |
| [`../AGENTS.md`](../AGENTS.md) | Agent permissions, interaction model, Git rules and implementation behaviour |
| [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | Human branch/review contribution flow |

If a focused authority contradicts `PROJECT.md` at the product level, report the conflict rather
than silently changing product behaviour. `AGENTS.md` defines the full conflict order.

## Current execution status

The active implementation plan is **Phase 1 — Cross-platform foundation**.

Phase 1 addresses the existing macOS-first assumptions and establishes portable foundations for the
selected Windows, macOS and Linux Beta profiles.

It is **only the first phase of the standalone Beta implementation**. The Beta path is:

- Phase 2 — complete standalone Refinix;
- Phase 4 — local safe execution, recovery and sovereignty proof;
- Phase 5 — three-OS Beta packaging, qualified in-app updates, acceptance and publication.

Phase 3 — trusted-device mesh, including peer-agent packaging — and the peer-specific part of Phase 4
are deferred until after Beta 0.1. Preserve their existing source and contracts for reuse. Phase
identifiers remain unchanged so historical references still resolve.

Agents work by these major sections/outcomes, reuse the existing repository and complete authorised
work across affected files and callers. Checklist items do not become further task tiers or delegated
assignments. Do not install a workflow framework or rebuild the application to adopt this approach.

The [runtime contract](PROJECT.md#13-runtime-and-resource-policy) assigns engine versioning and
qualification to development/release work, with automatic graphical installation checks for
customers. The [orchestration decision](PROJECT.md#70-orchestration-choice-and-alternatives) keeps
the current harness; LangGraph remains an unadopted option for a demonstrated need.

See [`../tasks.md`](../tasks.md) for the exact outcomes.

## Protected documentation

Core documentation must not drift during implementation.

Agents must obtain explicit user permission before editing the protected project docs defined in
[`../AGENTS.md`](../AGENTS.md), including `PROJECT.md`, `tasks.md`, the root/project READMEs and
focused product authorities.

If an agent believes a requirement should change, it must first tell the user:

- what is wrong/outdated;
- its recommended change;
- why;
- the trade-off;
- which documents would change;
- the intended execution path.

The normal request/change ledgers under `agent-memory/` are the main exception and may be appended
according to their own rules without asking for a separate documentation-edit approval.

## Evidence and reference material

These files are valuable, but they are **not current product authorities**.

### [`evaluation.md`](evaluation.md)

Source/runtime/evaluation evidence, acceptance observations, historical measurements and prototype
records. Read it for a specific evidence question rather than as normal startup context.

Implementation/source presence and historical test counts do not automatically establish current
runtime or release acceptance.

If an uploaded/cached historical copy contains merge-conflict markers or contradictory branches,
do not pick one silently and promote it into current requirements. Recover the accepted state from
the authoritative contract/current repository evidence or ask the user when necessary.

### [`devicespecifications.md`](devicespecifications.md)

Historical/current-reported device inventory and measurements. Device measurements are useful for
qualification planning but are not permanent product roles and may become stale. Fresh release
claims require current device/profile evidence.

### [`worker-operations.md`](worker-operations.md)

Operational runbook for the retained managed Linux/Kubernetes backend. It is not a second task board
and is not a desktop-user setup guide.

### `archive/`

Historical reproduction procedures, handoffs and retired task material. Open only for a specific
historical measurement/reproduction question.

## Legacy compatibility/reference snapshots

The following files are intentionally retained because old links, historical reasoning and detailed
prototype records may still point to them:

- [`prd.md`](prd.md)
- [`architecture.md`](architecture.md)
- [`workflows.md`](workflows.md)
- [`../TechStack.md`](../TechStack.md)

They are **not part of the normal active authority chain anymore**.

Their current production requirements have been consolidated into [`PROJECT.md`](PROJECT.md). Do not
keep editing all four simply to mirror every product decision; that duplicated synchronization work
is exactly what the consolidation removes.

When one of these snapshots disagrees with `PROJECT.md`, current product truth comes from
`PROJECT.md` unless the user explicitly approves a new change.

## Presentation and research material

Presentation/research documents such as the SIH submission brief or workflow diagram may explain the
idea, demo story and judge Q&A. They are non-normative.

Presentation copy may describe the broader product vision, but claims about current functionality
must preserve the distinction between:

- Working now;
- Beta/experimental;
- Planned.

Presentation work cannot silently change product requirements.

## Agent memory

`../agent-memory/userprompts.md` and `../agent-memory/agentchangelog.md` are searchable historical
ledgers.

They are **search-only during normal startup**. Do not read them end-to-end by default. Search by
specific task term, component, path or known ID only when a past request/change must be recovered.

Historical entries are facts about what was requested or changed at that time; they do not override
the current user request, `AGENTS.md` or `PROJECT.md`.

## Documentation rules

- Record current product requirements once in `PROJECT.md` and link to them instead of copying them
  into several active design documents.
- Keep specialist implementation/security/model/release detail in its focused authority.
- Keep evidence in evidence/reference material rather than rewriting it as product truth.
- Label planned, source-present, tested, device-observed and release-accepted states honestly.
- Do not create new planning/handoff documents for routine agent sessions.
- Do not create empty placeholder documents.
- Preserve historical records instead of rewriting them to make the past look current.
- Core documentation changes require the user permission described in `AGENTS.md`.

## Repository-level documents

- [`../README.md`](../README.md) — public/project entry point.
- [`../AGENTS.md`](../AGENTS.md) — repository-wide agent rules.
- [`../tasks.md`](../tasks.md) — active five-phase implementation plan.
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — branch/review process.
- [`../LICENSE`](../LICENSE) — repository licence.
- `../agent-memory/` — historical searchable request/change records.

Tool-specific local instruction files remain separate/local as configured by the repository; shared
project rules belong in `AGENTS.md`.
