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
requires a main engine for local inference, resolves dependencies for enabled capabilities, shows
source/licence/size information, and runs real self-tests. It never asks for a
permanent coordinator, worker, or server role.

The public site explains the product and may publish approved installer
versions and checksums. It never runs inference, stores private chats,
coordinates workers, or participates in offline runtime.

The UI must distinguish connected setup from offline runtime and must follow the
[Control Center evidence semantics](../docs/security.md#12-control-center-evidence-semantics).
It cannot hard-code secure, blocked, healthy, or zero-traffic states.

## Current runtime and design boundary

`frontend/app/` is the running application UI: local HTML/CSS/JavaScript served
by the coordinator, with Chat/document skills, IDE-style Code, Settings and job
status. Existing Node suites cover simulated DOM behaviour; they are not an
operator walkthrough. No React/TypeScript/Vite conversion is planned.

`frontend/design/` is the separate visual/site reference and is not served by the
application. Its sample onboarding, pairing and recommendations are not runtime
implementation. Keep its media and brand assets as design inputs, not evidence.

The app uses local assets/system fonts; any external fonts in the reference site
are outside the runtime. Scoped egress proof still requires independent observation.

The Beta UI work reuses these surfaces. Persistent **Settings → Models** follows
[the catalogue lifecycle](../docs/model-catalog.md#persistent-model-management);
guided pairing and truthful model/device routing follow [workflows](../docs/workflows.md).
Do not expose inactive controls as working. The [task graph](../tasks.md#numbered-execution-tasks)
puts clean packaging on the Beta path rather than deferring it until all production
features exist. Website/PPT claims follow [release bands](../docs/prd.md#release-bands).
