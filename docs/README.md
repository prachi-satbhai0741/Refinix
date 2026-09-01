# AegisForge documentation

## Status

The documentation defines a team-review draft. The repository does not yet
contain a verified runtime, installer, or model bundle.

## Start here

1. [prd.md](prd.md) — short product contract, scope, priorities, and open decisions
2. [architecture.md](architecture.md) — harness, nodes, state, jobs, and local data
3. [workflows.md](workflows.md) — onboarding, Chat, Documents, Code, approvals, and Control Center
4. [security.md](security.md) — trust, privacy, sandbox, supply chain, and sovereignty evidence
5. [model-catalog.md](model-catalog.md) — model packs, manifests, provisioning, and selection
6. [devicespecifications.md](devicespecifications.md) — current fleet evidence and open hardware checks
7. [evaluation.md](evaluation.md) — five-day plan, measurements, acceptance, risks, and demo

The PRD owns product scope. Each focused document owns implementation detail
inside that scope. Record conflicts instead of duplicating or silently changing
requirements.

## Documentation rules

- Keep the PRD short; detailed contracts belong in their focused document.
- Record a requirement once and link to it elsewhere.
- Label features planned, prototyped, verified, deferred, or rejected.
- Treat reported hardware, model names, licences, compatibility, and benchmarks
  as unverified until evidence is recorded.
- Do not leave discussion comments inside normative documents after a decision;
  integrate the accepted requirement and rely on Git and the ledgers for history.
- Do not create empty placeholder documents.

## Repository-level documents

- [../README.md](../README.md) — project entry point
- [../AGENTS.md](../AGENTS.md) — shared coding-agent rules
- [../CONTRIBUTING.md](../CONTRIBUTING.md) — branch, review, and release workflow
- [../LICENSE](../LICENSE) — current repository licence
- [../agent-memory/README.md](../agent-memory/README.md) — historical request and change index

Tool-specific files such as CLAUDE.md and CODEX.md remain local and ignored.
Shared rules belong in AGENTS.md.
