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

`frontend/app/` is the **application-owned** C03 UI: plain HTML, CSS and
JavaScript served by the coordinator, with no package.json, build step or
dependency set. Its stylesheet is derived from the design tokens but loads **no
external font**, so the running application makes no network request outside
loopback. Text renders wider than the design because the fallback `system-ui` is
not condensed; that is expected, while clipped labels or unusable controls are
functional defects.

`frontend/design/` remains the design track's own reference area and is not
served, linked or redirected into by the application.

The recorded alpha baseline uses local HTML, CSS, and JavaScript served by the
coordinator. [TechStack.md](../TechStack.md#3-frontend-and-product-surfaces)
proposes React + TypeScript + Vite for C03, with built assets still served
locally; this is a recommendation, not an implemented framework change.

Chat and Control Center form the first usable slice; Documents and Code reuse the same job form,
event stream, artifact links, and truthful unavailable states. Packaging remains
deferred until the complete demonstration path works.
