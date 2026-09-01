# frontend

Desktop agent application and separate public distribution site.

## Intended application surfaces

From [workflows.md](../docs/workflows.md):

- **Chat** — general local agent and local knowledge.
- **Documents** — OCR/vision, retrieval, citations, and generated artifacts.
- **Code** — selected repository context, isolated validation, and patches.
- **Control Center** — onboarding, models, jobs, approvals, paired devices,
  health, cleanup, and sovereignty evidence.

These surfaces consume one local harness API and event stream. They do not own
separate model, memory, permission, routing, or audit systems.

First-run onboarding creates a local workspace automatically, detects hardware,
requires a main engine, resolves dependencies for enabled capabilities, shows
source/licence/size information, and runs real self-tests. It never asks for a
permanent coordinator, worker, or server role.

The public site explains the product and may publish approved installer
versions and checksums. It never runs inference, stores private chats,
coordinates workers, or participates in offline runtime.

The UI must distinguish connected setup from offline runtime and must follow the
[Control Center evidence semantics](../docs/security.md#12-control-center-evidence-semantics).
It cannot hard-code secure, blocked, healthy, or zero-traffic states.

## Status: no scaffolding yet

There is no package.json, source tree, or dependency set.

The [architecture direction](../docs/architecture.md#8-working-technology-direction)
defers the desktop shell decision until one real local and paired-worker harness
path works. A local web interface may prove that path before packaging; do not
let cross-platform installer work block inference and orchestration evidence.
