# docs

## Status

[`prd.md`](prd.md) is the **current team-review draft**. It is **not final**
until the team approves a v1 baseline.

Treat it as the best available statement of intent, not as settled fact.
Sections 17.1 (licence conflict), 11.5 (baseline package), and 24.2 (open
decisions) list what is still undecided.

## What is deferred

`prd.md` section 17.2 lists a full documentation set the repository should
eventually carry:

- `ARCHITECTURE.md` — component and deployment design
- `PROTOCOL.md` — pairing, API, job, and event contracts
- `THREAT_MODEL.md` — assets, actors, boundaries, mitigations
- `MODEL_CATALOG.md` — approved model selection and evidence
- `RESEARCH.md` — benchmark results and rejected hypotheses
- `DECISIONS.md` — dated architecture decisions
- `DEMO.md` — reproducible demonstration procedure

**None of these are created yet, and that is deliberate.** Writing them before
the PRD baseline is accepted would document architecture the team has not
agreed to, and each one would need rewriting when the baseline changes. They
land once the PRD is approved.

Empty placeholder files are worse than absent ones: they look like coverage
that does not exist.

## Where things go

Future product and research documents belong under `docs/`.

These files stay at the repository root, because tools and contributors expect
them there:

`README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `LICENSE`, `.gitignore`

Tool-specific root files such as `CLAUDE.md` and `CODEX.md` are local-only and
ignored. Shared agent rules belong in `AGENTS.md`.

## Moved

Root `prd.md` moved to `docs/prd.md`. Links, scripts, and ledger entries
referring to the old path have been updated; if you find one that was missed,
it is a bug.
