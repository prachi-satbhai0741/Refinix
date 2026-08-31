# backend

Coordinator and worker services.

## Intended boundary

From [`docs/prd.md`](../docs/prd.md) sections 10.3–10.9:

- **Coordinator** (10.3) — owns the canonical workspace: chats, job state,
  device registry, artifacts. Runs on the Mac in v1.
- **Worker service** (10.4) — executes one job on one complete model on one
  device. Exposes the minimum LAN surface described in 14.3.
- **Model runtime adapter** (10.5) — one adapter for the first proven runtime.
  Not a plugin system.
- **Router and scheduler** (10.6) — deterministic task-to-capability routing.
- **Context manager** (10.7), **local knowledge base** (10.8), and **agent and
  tool runner** (10.9).

Security invariants that apply to everything here: runtime operation must not
require Internet access (16.2), local model runtimes bind to loopback (16.2),
workers write only inside assigned temporary workspaces (15.2), and the sandbox
has networking disabled by default (16.6).

## Status: no scaffolding yet

There is no `pyproject.toml`, no source tree, and no dependencies — on purpose.

`docs/prd.md` section 18 lists Python with FastAPI as a **candidate**, not a
settled choice, and section 18 closes with: the prototype should not add
multiple runtime adapters, vector databases, event systems, or packaging
frameworks before one real end-to-end path proves they are needed.

Scaffolding lands when the team approves the PRD baseline and the technology
choices. Until then this directory holds its definition and nothing else.
