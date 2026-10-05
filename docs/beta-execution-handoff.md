# Standalone Beta execution handoff

Prepared at the user's request on 2026-10-04. Repository:
`/Users/adityatadge/Documents/GitHub/AegisForge`.

**State: USER-APPROVED CORRECTED EXECUTION DIRECTION — prerequisite permissions remain pending.**
The [approved execution addendum](#approved-execution-addendum-20261004) records the user's latest
approval and supersedes conflicting O.5, O.6, O.11 and prompt details. This approves the direction
and correction handoff; it does not establish runtime, sandbox, package or release acceptance. See
[Owner reconciliation](#owner-reconciliation-20261004) for the R1–R5 corrections. The
implementation owner's independent assessment and proposed plan are in
[Implementation-owner plan](#implementation-owner-plan--independent-assessment-2026-10-04); the
preparing draft and owner proposal below are preserved for comparison. The latest user direction and
[review-agent assessment](#review-agent-assessment-20261004) supersede conflicting proposal details.
This handoff is an execution aid, not a
replacement for [PROJECT.md](PROJECT.md), [tasks.md](../tasks.md) or the focused authorities.
Source review is not runtime, package or release acceptance.

## Outcome and engineering priorities

Deliver a dependable standalone Refinix Beta on selected Windows, macOS and Linux profiles,
using the existing application. A user completes graphical setup, chooses supported local
models, works in Chat/Documents/Code, reopens saved work and installs an explicitly requested,
verified Refinix update without managing an external inference server.

The optimization target is **correct, maintainable, useful, efficient code and reliable product
behavior**. Repository size is not a success metric. Protect user data and authority first;
preserve useful capabilities, improve measured performance and simplify maintenance. Remove
obsolete code when evidence supports removal, not to achieve a smaller diff or file count.

The implementation owner handles each major section end to end. The review agent independently
challenges assumptions and examines integration risk. Do not spawn further agents, divide files
into separate assignments, create additional task tiers or repeatedly hand routine choices back
to the user. Plan deeply, then execute sustained coherent work within permission.

## Current instructions and execution boundary

Read [AGENTS.md](../AGENTS.md), [PROJECT.md](PROJECT.md) and the active phase in
[tasks.md](../tasks.md). Read [model-catalog.md](model-catalog.md),
[security.md](security.md) and [releases.md](releases.md) as their domains are entered.
Inspect current source and callers before designing replacements. Historical graph/evaluation
entries identify places to investigate; they do not supersede current source or product authority.

The user has received the concrete change summary, approved the direction and requested this
corrected handoff and its delivery to the implementation owner. The earlier request for sustained
execution remains the intended next step. Keep the existing four sections; do not repeat the settled
planning exchange or invent another blanket approval for the same direction. The owner must still
establish the permissions needed for the actions below before performing them.

Before that transition, identify any permissions still required by AGENTS.md. Test commands,
installations, model/dependency downloads, migrations, live inference, remote-device changes,
Git/GitHub writes and publication are not silently authorized by planning or documentation work.
Request genuine prerequisites in one compact batch, with recommendations for product decisions.
Continue unaffected work within the approved source scope. The current documentation authorization
covers this handoff and the append-only ledgers. Other protected authorities, including a proposed
internal-channel addition to releases.md, still need explicit permission for their stated changes.
Changes to product scope or trust boundaries still require the user's decision.

**Coordination status:** Earlier Computer Use attempts were refused, and the user relayed the
initial planning prompts. Access subsequently worked: the review agent delivered the three-OS
package requirement and then a consolidated safety review to the existing owner conversation.
The owner accepted the socket/recovery/manifest findings in a reply-only proposal. The review agent
identified the remaining database-identity, io_uring and aggregate-storage gaps and explained the
corrected four-section approach. On 2026-10-04 the user approved that direction and requested this
handoff and delivery. This latest handoff was delivered directly to the existing owner conversation
and verified as its new Message 9; the owner began responding. Its detailed acknowledgement and
the outstanding action permissions remain pending.
The original proposals and reviews below remain historical evidence; no joint qualification PASS
or implementation verification is implied by the user's approval.

## Baseline established by source inspection

At preparation, the branch was `aditya`, HEAD was
`8c6d7a9fe1c15106fc542792e32e8b36e0bd34db`, and the checkout was dirty. Re-read status
before edits. Preserve all existing documentation, website/design changes, assets, build scripts
and untracked work. Do not reconstruct dirty files from HEAD or clean the workspace.

| Existing path | What must be reused or examined |
|---|---|
| [desktop/lifecycle.py](../desktop/lifecycle.py), [shell.py](../desktop/shell.py) | Existing startup, progress, process ownership, native dialogs, shutdown and pywebview shell. The current supervisor accepts an answering external Ollama or locates a system binary. |
| [runtime.py](../backend/coordinator/runtime.py) | Current Ollama HTTP adapter, cancellation, streaming, reasoning, structured output and metrics. The local endpoint is currently fixed to Ollama. |
| [profiles.py](../backend/contracts/profiles.py), [device.py](../backend/coordinator/device.py) | Exact model/digest/runtime/version admission and narrowly measured device recognition. Current local device matching names the measured Mac hardware; broader supported profile classes need new evidence. |
| [server.py](../backend/coordinator/server.py), [app.js](../frontend/app/app.js) | Status, selection, dispatch and UI. Backend blockers distinguish causes; `renderReadyLine` collapses several installed-but-unavailable conditions into the reported generic message. |
| [models.py](../backend/coordinator/models.py), [db.py](../backend/coordinator/db.py), [context.py](../backend/coordinator/context.py) | Catalog, selection/self-test state, canonical SQLite state and conversation/context budgeting. Current model setup guidance still delegates provisioning to external commands. |
| [paths.py](../backend/coordinator/paths.py), [credentials.py](../backend/coordinator/credentials.py), [winfs.py](../backend/coordinator/winfs.py) | Existing platform data, protected-storage and filesystem-containment work. Native roots and legacy `.aegisforge` compatibility already exist; preserve them. |
| [documents.py](../backend/coordinator/documents.py), [pdfrender.py](../backend/coordinator/pdfrender.py), [ocr.py](../backend/coordinator/ocr.py), [docflow.py](../backend/coordinator/docflow.py), [retrieval.py](../backend/coordinator/retrieval.py) | Document/render/OCR/artifact and lexical retrieval paths. Rendering, native vision and qualified OCR are separate capabilities. |
| [code_service.py](../backend/coordinator/code_service.py), [repo.py](../backend/coordinator/repo.py), [policy.py](../backend/coordinator/policy.py) | Selected repository context, proposals, approvals and local Apply/Undo. Preserve the distinction between applying a patch and validating it in a qualified sandbox. |
| [packaging_plan.py](../desktop/packaging_plan.py), [setup_py2app.py](../desktop/setup_py2app.py) | Existing shared packaging boundary and macOS builder. Windows/Linux tool names are candidates, not proof of pinned builders or accepted packages. |
| [od03_runtime_comparison.py](../scripts/od03_runtime_comparison.py), [qualify_execution.py](../scripts/qualify_execution.py) | Existing comparison parsers and qualification runner. Reuse them; the short runtime benchmark alone does not prove all workflow parity. |
| [backend/worker](../backend/worker), [backend/contracts](../backend/contracts) | Retained distributed implementation and shared contracts. Standalone Beta must not depend on a worker, Redis or Kubernetes. |

Source search did not identify a production in-app updater in the inspected desktop/coordinator/UI
path. Inspect any claimed release automation before concluding it implements customer updates.
Do not present documentation, a merged build workflow or a future control as updater completion.

The runtime-version mismatch is a source-supported explanation for the user's availability error,
not a freshly observed live diagnosis. Engine ownership addresses the underlying external-update
dependency; removing admission checks or changing only the error string does not solve it.

## Decisions to retain and comparisons to finish

| Recommendation | Reason | Required evidence or trade-off |
|---|---|---|
| App-managed pinned, verified `llama.cpp`/`llama-server` candidate; retain Ollama as development/parity baseline | Isolates shipped inference from system updates and gives Refinix ownership of installation and recovery | Confirm exact build, license, model assets, templates, feature parity and platform/backend packaging. Do not replace existing Ollama evidence with unmeasured llama.cpp profiles. |
| Retain the existing coordinator and orchestration harness | Existing state, approvals, workflows and contracts are valuable integration already paid for | Compare a framework only for a specific demonstrated gap. LangGraph is unadopted; no migration is justified by competitor usage alone. |
| Retain frontend, Python backend and pywebview shell | Addresses portability through existing boundaries and avoids a second application implementation | Validate native toolkit/dependency packaging on each selected profile. Do not promise universal OS or hardware support. |
| Small verified catalog, capability-based reuse and optional categories | Reduces qualification effort and resource demand while preserving user choice | Qualify each offered model/workflow combination. Vision declarations do not prove OCR. Voice/image generation remain later optional packs; do not force every engine into llama.cpp. |
| Existing SQLite and FTS5 retrieval baseline | Preserves durable state and a working offline retrieval path | Embeddings serve enabled semantic retrieval, not mandatory basic startup or PDF rendering. Preserve instructions, curated memory, citations and workspace boundaries. |
| Verified full-package updates with staged replacement and recovery | Reduces update complexity while delivering the required journey | Evaluate established per-platform installers/updaters and trust libraries. Full packages still require signing, authenticated metadata, replay protection and crash recovery. Delta updates need a demonstrated benefit. |

A dedicated orchestrator LLM is optional. Prefer deterministic routing for clear requests; add
model-assisted classification only when measured workflow errors justify its latency and memory.
If the preferred engine fails a required capability, present a bounded alternative with evidence
and implications. Do not silently drop the capability, ship two production engines by habit, or
weaken safety to force a chosen engine through.

## The four execution sections

These correspond to existing Phase 1, Phase 2, the local portion of Phase 4 and Phase 5.
Phase 3 and peer-specific acceptance remain after Beta. The following steps stay inside their
section and are not additional tasks or delegations.

### Foundation — Phase 1

- Trace UI/API -> coordinator -> runtime -> storage/validator and all affected call sites/fakes.
  Reuse portable path, credentials, document and filesystem code already present.
- Define the managed engine boundary: exact executable/build identity, dependencies, model paths,
  configuration, loopback endpoint, owned lifecycle and integrity checks. A PATH change, external
  listener or system runtime update cannot redirect work. Handle occupied ports and startup failure
  without taking ownership of an unrelated process.
- Preserve the current normalized streaming contract (`delta`, `thinking`, `done`), structured-output
  validation, cancellation of stalled reads, reasoning controls, context/output limits and metrics.
  Add only the adapter separation needed by actual supported engines; avoid a speculative plugin system.
- Verify model weights, tokenizer/template and any multimodal projector independently of model tags.
  Reuse existing assets only with established provenance and compatibility; do not assume an Ollama
  tag or manifest is directly interchangeable with a llama.cpp model artifact.
- Evolve support from individual measured-device IDs toward evidence-backed OS/architecture/backend/
  hardware bounds, with local fit checks. Keep exact engine/model qualification internally. Do not
  grant eligibility to every device by broadening a string match.
- Surface specific blockers and graphical recovery through the existing status UI. Preserve legacy
  data selection and credentials; propose a migration only if needed, with separate authorization.
- Identify packaging feasibility and at least one safe local Code validation candidate early.
  Keep all three OS families in scope without requiring peers or unrestricted host execution.

Exit: coherent portable source and a justified managed-runtime/packaging route, with remaining
device and installation evidence named. This is not yet accepted consumer packaging.

### Standalone workflows — Phase 2

- Complete hardware-aware graphical onboarding and Settings -> Models using existing catalog/state.
  Show supported small/medium/large choices where qualified, source/license/size and resource needs;
  allow optional categories to be skipped. Never present incompatible arbitrary models as supported.
- Implement explicit provisioning and verified offline import with staging, progress, cancellation,
  disk checks and integrity verification before activation. Run local installation/self-tests after
  approved setup; persist results against the actual artifact/engine identity. Safe removal must
  preserve chats and other models. Unsupported imports receive truthful limitations.
- Complete local automatic routing using hard capability, qualification, availability and resource
  filters. Reuse multi-capability models. If a selected automatic target fails, select another eligible
  local target only when the workflow is safe to retry; preserve permissions and user-pinned choices.
  Reconcile uncertain effects before retrying a step with consequential writes.
- Make context and output budgets model/workflow/profile-specific. Retain useful reasoning controls
  and visible truncation/omission explanations. Avoid loading every selected model at once; observe
  memory and queue capacity. Tune caching and concurrency only after measuring the real bottleneck.
- Finish persisted multi-turn Chat, grounded Documents, source/page citations, readable artifacts
  and reviewable Code proposals through the current UI. Preserve repository selection, Apply/Undo,
  approval snapshots and canonical writes. Audit `.refinix` portable mode, native data roots,
  AGENTS.md instructions, curated memory.md and selected retrieval context without merging workspaces.
- Qualify the narrow scan/image + selected SOP -> Word workflow required by tasks.md. An unqualified
  OCR candidate remains unsupported until provenance and workload evidence exist. If it cannot meet
  the Beta requirement, seek a specific scope decision instead of advertising a substitute as OCR.

Exit: the supported standalone journey works with at least two qualified task/model combinations
across at least two task types, with evidence appropriate to each claimed profile.

### Local safety, reliability and evidence — local Phase 4

- Exercise runtime loss/restart, stalled-stream cancellation, memory pressure, queueing, disabled or
  missing models, malformed output, denied approval, interrupted work and ordinary crashes.
  Preserve saved work, consistent job state and actionable recovery.
- Qualify one eligible local sandbox with actual network denial, host-file isolation and bounded
  resources. Other profiles accurately disclose local validation limits. A timeout or container
  name is not proof of isolation; a managed remote validator cannot substitute for standalone Beta.
- Demonstrate approval-bound, idempotent canonical writes and attempt reconciliation. Distinguish
  retryable inference from uncertain executed effects; never duplicate application of a patch.
- Bind real job/model/input/output/validation/approval data to existing proof/status surfaces.
  Separate network enforcement from scoped observation. Capture authorized evidence for representative
  local workflows without claiming universal absence of all possible egress.
- Fix release-blocking correctness, data-loss, security and core-workflow regressions in one coherent
  stabilization pass; avoid unrelated cosmetic churn.

Exit: ordinary failures recover without manual database repair, unsafe fallback or fabricated green
states; advertised local sandbox and sovereignty claims match observed evidence.

### Packages, updates and release — Phase 5

- Build the existing app from one designated source/version, pin adopted packaging dependencies,
  include required engine/native resources and verify the shipped file inventory. Keep durable
  state and separately managed model weights outside replaceable application files.
- Finalize one qualified profile in each OS family, including signing/notarization, prerequisites,
  credentials, permissions, resources and truthful capability limits. Do not assume one machine's
  package observations prove another platform works.
- Implement Settings -> Updates using established platform installation/update and verification
  components. Explicit check -> compatible authenticated offer -> staged download/verified offline
  import -> drain/cancel -> affected-state backup -> install/restart -> local health check/recovery.
  No silent checks, invented cryptography, mutable-branch scripts or forced upgrades.
- Exercise two labeled builds on every advertised profile, including an engine-changing transition.
  Reject tampering, wrong platform, invalid signer, replay and unauthorized downgrade before changing
  the application or data. Preserve newer user work when recovery involves older application schemas.
- Demonstrate nondeveloper install/setup/work/reopen/update/offline-restart journeys, manual full-package
  recovery and uninstall/data preservation. Manual replacement is recovery, not a replacement for
  the required in-app updater.
- Synchronize manifests, release notes, supported matrix, docs and available artifacts. Publication
  remains a separate authorized action after the user accepts evidence.

Exit: shipped bytes satisfy the advertised Beta claim set across Windows/macOS/Linux. Source tests
or a merge to main alone cannot establish this exit.

## Cleanup and performance discipline

For every proposed deletion or substantial simplification, identify callers/imports, package
inclusion, contract consumers, persisted-state compatibility, tests and later retained features.
Remove obsolete duplication, dead branches and replaced implementation only after the replacement
preserves required behavior. Keep evidence-bearing tests and history useful for qualification.
Exclude development/test files from release packages without deleting them from the repository.

Preserve distributed worker/contracts/runbooks for post-Beta. Do not remove their safety semantics
because their UI is deferred. Do not turn shared-contract changes into a mesh implementation project.

The strengthened rule and the evidence-backed candidates are in
[O.12](#o12-cleanup-rule): adapt existing code first, reuse established offline tools, add new code
only for a demonstrated gap, and remove confirmed dead or replaced code after caller, package, test
and stored-data checks.

Measure cold/warm startup, time to first token, generation throughput, resident memory, context fit,
queue behavior and artifact correctness when the required runtime checks are authorized. Compare
the same model bytes, template, prompt and settings. Report regressions and trade-offs. Faster
token generation cannot justify broken reasoning, citations, cancellation or data preservation.
Choose performance thresholds from measured baselines and the intended workflow, not invented
numbers. Maximum code quality means maintainable justified engineering, not maximum code volume.

## Plan review and acceptance

The implementation owner should independently inspect the source, challenge this draft, and update
this same handoff with evidence-backed corrections. The review agent independently evaluates the
proposal; do not merely restate the draft as agreement. Resolve material disagreements once in a
coherent review batch. Record decisions and evidence, not private chain-of-thought.

Before declaring the **plan** PASS, both agents need:

- an affected-path/caller map and inventory of capabilities being preserved;
- a runtime/packaging recommendation with unresolved parity facts clearly identified;
- bounded model, onboarding, routing, context, memory and recovery changes;
- safe cleanup candidates with supporting evidence, rather than a deletion quota;
- executable validation families and explicit device/environment/publication prerequisites;
- a concrete user-facing change summary covering changed behavior, paths, reasons, risks and recovery.

Plan PASS means the proposed implementation is justified and reviewable. It does not mean the engine,
model, package, sandbox, updater or release has passed qualification. If a live fact is required to
choose the architecture, leave that decision pending and request the bounded observation rather than
pretending the agents can settle it by reasoning alone.

Acceptance must include the following exact outcomes, at the appropriate evidence layer:

| Case | Required outcome |
|---|---|
| External Ollama upgrade/PATH change/foreign engine listener | Shipped Refinix keeps its verified managed engine and remains useful offline. |
| Missing or modified engine, model bytes or qualification records | Specific refusal and graphical repair; no version spoofing or fabricated eligibility. |
| Small supported model or optional category skipped | Supported chosen workflows work; skipped categories do not block basic use. |
| Automatic target fails, alternate capable target exists | Safe eligible fallback with a visible reason; permissions and effects remain correct. |
| User-pinned target fails or no eligible model exists | Truthful failure; no silent override, download or cloud fallback. |
| Reasoning, structured output, long context and cancellation | Preserve validated output behavior, qualified budgets, useful answers and responsive Stop. |
| Source selection, memory and retrieval | Workspace/permission isolation; accurate citations and no silent excessive context. |
| Scan/OCR and generated artifact | Measured extraction/generation quality and usable output; uncertainty remains visible. |
| Code proposal/apply/undo/sandbox | Approved bounded writes, no duplicate application, truthful validation and qualified isolation. |
| Close/reopen or failed operation | Chats, selections, credentials, instructions and artifacts persist consistently. |
| Update cancelled, tampered, incompatible or interrupted | Current installation/data remain usable; no partial activation or false success. |
| Valid connected update/offline import/engine transition | Verified installation, matching qualification, preserved work and offline restart. |
| Migration/install crash and rollback | Recover consistent compatible state without overwriting newer user work. |
| Clean installed package on each OS profile | Advertised standalone journey needs neither checkout, terminal setup nor peer. |
| Release evidence | Exact source/package/engine/model/profile identifiers; evidence strength and limitations disclosed. |

Once authorized, reuse existing contracts/coordinator/desktop and frontend offline tests plus focused
regressions for the changed behavior. CI currently includes `unittest` discovery and
`node --test frontend/app/test-*.cjs`; verify the chosen interpreter and each family's actual
dependencies before running them. Add meaningful adapter/fake checks for every changed caller.
Do not run live inference scripts or package installation as an unnoticed extension of offline tests.
Run proportionate checks once; repeat when changes, failures or unresolved concerns justify it.

### Review record

- Preparation/source alignment: reviewed by the preparing agent; no application verification performed.
- Implementation-owner independent plan: RECORDED 2026-10-04 in the section below, from source
  inspection only (HEAD `8c6d7a9`). No application edits, tests, builds, runtime calls, downloads or
  Git writes.
- Review-agent evaluation of that plan: **NEEDS FIX, 2026-10-04** — see
  [the consolidated assessment](#review-agent-assessment-20261004). Source/public-record inspection
  only; no application checks or implementation.
- Owner reconciliation of R1–R5: RECORDED 2026-10-04 —
  [Owner reconciliation](#owner-reconciliation-20261004). Source, package-metadata and public-record
  inspection only.
- Review-agent re-review of the reconciliation: **NEEDS FIX, 2026-10-04**. Recovery must stop all
  writers and hold exclusive ownership; read-only SQLite access alone is not byte-preserving;
  Ubuntu host IPC/alternate syscall routes need denial; embedded identity and external package
  checksums must be separate. Sent to the owner and acknowledged in a reply-only reconciliation.
- User requirement added 2026-10-04: internal macOS/Windows/Ubuntu test packages and a stronger
  cleanup rule, folded into the same four sections as [O.11](#o11-internal-test-packages) and
  [O.12](#o12-cleanup-rule), with build-environment prerequisite O.9 item 6. Not a plan PASS; the
  long implementation run has not started.
- Follow-up review of that reply: **NEEDS FIX on its exact wording, 2026-10-04**. The database header
  shortcut does not establish Refinix ownership/metadata; io_uring socket operations remain outside
  the proposed ordinary socket filter; per-file limits do not bound total job storage. These are
  mandatory corrections in the [approved addendum](#approved-execution-addendum-20261004).
- User checkpoint: **APPROVED DIRECTION AND HANDOFF, 2026-10-04**, after the plain-language
  four-section explanation. No further blanket direction approval is needed.
- Current handoff delivery: **DELIVERED, 2026-10-04**, visibly present as Message 9 in the existing
  owner conversation; owner response started. No execution result is inferred from delivery.
- Reconciled plan PASS: technical requirements are handed off with explicit acceptance gates;
  a tested implementation or joint qualification PASS is NOT ESTABLISHED.
- Concrete changes presented before execution: the reconciled summary is in O.10 of the owner
  reconciliation; it supersedes [P.9](#p9-proposed-user-facing-change-summary).
- Prerequisite batch for the user: [P.8](#p8-prerequisites-for-the-user--one-batch); revise it under
  the assessment. The preset/reuse direction and scoped doc changes are already authorized; do not
  re-ask them. Tests, downloads, installation, live processes and genuine release credentials remain
  separate prerequisites. Owning all proposed laptops is not required.
  Revised batch: O.9 of the owner reconciliation (permissions 1-6 and remaining human facts);
  check current authorization before asking, and batch only genuinely unanswered items. The
  four-section direction and corrections must not be re-asked as technical choices.
- Long-run application implementation: NOT STARTED.

<a id="implementation-owner-plan--independent-assessment-2026-10-04"></a>
## Implementation-owner plan — independent assessment (2026-10-04)

**Status: PROPOSED — awaiting review-agent evaluation.** Source inspection only, at branch `aditya`,
HEAD `8c6d7a9`, with the dirty tree recorded above (15 modified docs/design files; untracked handoff,
site assets, site build scripts and `tmp/`). Line numbers refer to that HEAD. Nothing here is
implemented, tested, device-observed or release-accepted.

### P.1 Verdict on the draft and evidence-backed corrections

The draft's direction stands: app-managed pinned engine, retained harness/UI/shell, small verified
catalogue with capability reuse, FTS5 baseline and verified full-package updates. Source inspection
changes the emphasis and adds defects the draft does not name.

| # | Finding | Evidence | Consequence |
|---|---|---|---|
| K1 | Most Phase 1 portability work already exists | [paths.py](../backend/coordinator/paths.py) native/legacy/portable roots and two-store refusal; [credentials.py](../backend/coordinator/credentials.py) Keychain/Credential Manager/Secret Service; [repo.py](../backend/coordinator/repo.py) + [winfs.py](../backend/coordinator/winfs.py) bounded containment; [pdfrender.py](../backend/coordinator/pdfrender.py) portable pypdfium2; [docgen.py](../backend/coordinator/docgen.py) portable Word | Do not redo them. Foundation effort goes to engine ownership, device classes, schema safety and Windows/Linux packaging. [pdfgen.py](../backend/coordinator/pdfgen.py) stays macOS-only optional PDF output; Word is the required artifact |
| K2 | **Newer-schema data-safety defect** | [db.py:438-440](../backend/coordinator/db.py) reads the stored version but never refuses a newer one; [db.py:566-570](../backend/coordinator/db.py) unconditionally overwrites it with the binary's `SCHEMA_VERSION` | An older binary (rollback, manual replacement, downgrade) opens and relabels a newer schema, contrary to [releases.md §5](releases.md). Fixed first, before any update/recovery work |
| K3 | Engine-ownership root cause is wider than the version string | [lifecycle.py:404-415](../desktop/lifecycle.py) adopts any listener answering on 127.0.0.1:11434; [lifecycle.py:82-88, 347-365](../desktop/lifecycle.py) resolve `ollama` via `PATH`/install dirs; [runtime.py:25](../backend/coordinator/runtime.py) fixed `HOST`; [server.py:225-250](../backend/coordinator/server.py) hard-codes runtime `"ollama"`; [profiles.py:94-142](../backend/contracts/profiles.py) bind exact Ollama versions | Only an owned, verified engine on a Refinix-chosen endpoint removes the first four. New evidence under that engine replaces exact-external-version dependence without spoofing |
| K4 | Customer-facing terminal instructions remain | `INSTALL_HINT` and `model_status` ([lifecycle.py:92-93, 478-492](../desktop/lifecycle.py)); `setup_action`/`removal_impact` commands ([models.py:307-353](../backend/coordinator/models.py)); [app.js:2947](../frontend/app/app.js) | Installed builds use graphical actions; commands remain only in an explicitly labelled developer-engine mode |
| K5 | Readiness travels as prose | [renderReadyLine app.js:2881-2902](../frontend/app/app.js); [_model_capability_blocker server.py:2656-2669](../backend/coordinator/server.py) | One typed `readiness` result in `/v1/status`; UI renders by code. The reported generic line becomes a specific blocker |
| K6 | Context indicator can disagree with dispatch | [context_estimate server.py:1121-1139](../backend/coordinator/server.py) uses fixed `NUM_CTX`/`NUM_PREDICT`; [_run server.py:781-786](../backend/coordinator/server.py) uses the profile | Both derive from the same selected profile |
| K7 | Stale status copy shown to users | `auto_model.detail` "after the internal hackathon" and `unavailable` claiming approvals/proof are unimplemented ([server.py:2718-2719, 2789-2795](../backend/coordinator/server.py)); `contract_status` ([server.py:2708](../backend/coordinator/server.py)); consumers [app.js:4020, 4044, 4090](../frontend/app/app.js) | Replace with truthful current state, updating consumers |
| K8 | Model identity for a non-Ollama engine | `v1.ModelRef.runtime` is a free label ([v1.py:63-67](../backend/contracts/v1.py)) but `manifest_sha256` means an Ollama registry manifest digest today | Define a Refinix model manifest (canonical JSON listing each component file: weights GGUF, optional projector, licence; name/size/SHA-256; upstream source/revision). Its canonical SHA-256 is `manifest_sha256` for managed-engine profiles. GGUF hashing covers the embedded tokenizer and chat template; any template override joins the manifest. No contract break |
| K9 | Device admission is one exact hardware string | [device.py:120-144](../backend/coordinator/device.py) admits only Mac17,3 with 16 GiB | Add evidence-backed device classes (OS family + architecture + backend + memory floor), each naming its representative evidence. Class bounds are a supported-matrix decision for the user (OD-12). Exact Mac profiles stay for the developer baseline |
| K10 | No updater, release pipeline or Windows/Linux builder | `PLATFORMS[...].pinned=False` in [packaging_plan.py](../desktop/packaging_plan.py); [ci.yml](../.github/workflows/ci.yml) is a Linux test job | Phase 5 is new implementation, not reuse |
| K11 | Code sandbox validation exists only through the paired Kubernetes worker | [code_service.py:966-1000](../backend/coordinator/code_service.py) requires a distributed target and a remote route | A local sandbox backend is new. The plan contract and allowlist in [validate.py](../backend/worker/validate.py) are mirrored, not imported (the worker is excluded from desktop packages) |
| K12 | One catalogue model cannot demonstrate model selection | [model-catalog.md §8](model-catalog.md): one model serving several profiles does not demonstrate selection; [models.py CATALOGUE](../backend/coordinator/models.py) has one entry | A second qualified model is required (decision Q4) |
| K13 | User instructions and curated memory are named but unused | [paths.py:101](../backend/coordinator/paths.py) lists `AGENTS.md`/`memory.md`; no reader in the coordinator | Bounded Beta implementation (FR-028 and the user's memory/retrieval direction) |
| K14 | Scan reading has no qualified profile | No `OCR` registry entry ([profiles.py:85-93](../backend/contracts/profiles.py)) | The scan + SOP -> Word workflow needs measured vision qualification on the managed engine, reusing the main model. If it fails, raise a scope decision rather than substitute |
| K15 | No coordinator-level inference admission | `submit` only blocks a second job per chat ([server.py:614-616](../backend/coordinator/server.py)); Chat, Code and self-tests can call the engine concurrently | Admission sized to engine slots and the memory budget, with visible queueing |
| K16 | A live-check tool ships in packages | [check_runtime_context.py](../backend/coordinator/check_runtime_context.py) passes `is_application_module`; it imports `unittest`, which py2app excludes | Exclude `check_` modules from packages; keep the file and its evidence command |

### P.2 Capabilities preserved (non-regression inventory)

- Exact admission at dispatch and target (`profiles.compatible`, `validate_request`), digest-bound
  self-tests with superseded/unconfirmed states, and the six trust-boundary corrections from
  `1ddaf1f` (disabled-model refusal, production-shaped self-tests, observed-digest matching,
  re-identify before atomic replacement, remote identity instruction, local-versus-worker eligibility).
- Normalised stream contract (`delta`, `thinking`, `done`, `cancelled`), `_CancelWatch` stalled-read
  abort, `truncate:false`/`shift:false` overflow refusal, unsaved reasoning, strict structured parsing,
  `limit_reason` metrics, history never deleted by selection.
- Job/attempt state machine, `reconcile_on_start`, `resume_writes`, approval-bound Apply/Undo labelled
  "Not sandbox tested — local device mode", artifact cleanup on cancel.
- Single-instance lock, own-workspace-only port reuse, stop-only-owned processes, data-root conflict
  refusal, legacy `.aegisforge`, owner-only permissions, protected credential stores, Windows containment.
- FTS5 search, page citations, document refusals, Chat-backed Documents fallback labelling.
- Package boundary verification (no tests, worker, fixtures or virtual environments shipped).
- Deferred worker, contracts, Kubernetes, Redis, pairing, dispatch and remote Code: untouched except
  additive, backward-compatible contract fields. `scripts/refinix` (mesh demo launcher) retained, not shipped.

### P.3 Changed seams and their callers

| Seam | Current non-test callers | Proposed change |
|---|---|---|
| `runtime.probe/stream_chat/model_capabilities/model_state/HOST/MODEL` | server.py, code_service.py, documents.py, ocr.py, check_runtime_context.py, desktop/lifecycle.py, desktop/shell.py, scripts/qualify_execution.py; 12 coordinator test modules | Public API kept. Endpoint, key and engine identity come from the active engine. Ollama path unchanged in developer mode; a llama-server adapter added beside it |
| `lifecycle.EngineSupervisor/find_ollama/model_status` | `run_startup`, desktop/__main__.py, desktop/shell.py, desktop/test_lifecycle.py | Installed builds use the managed supervisor in a new `backend/coordinator/engine.py`. The Ollama supervisor remains for developer mode |
| `profiles.for_observation`, `Coordinator.target_profile_id` | server.py `local_profiles`; worker keeps its own target | Accept a set of target IDs (legacy exact plus class). Worker unchanged |
| `db.connect` | Coordinator, tests; `read_workspace_id` is read-only | Newer-schema refusal before any DDL; never lowers the version; records last writer version |
| `models.setup_action/removal_impact` | `server.model_inventory`, `server.removal_impact`, app.js | Graphical provision/remove actions in managed mode |
| `/v1/status` | app.js ready line, engine/models/advanced cards | Additive `readiness`, `engine`, `hardware`, `setup`, `updates` objects; stale fields corrected with consumers |
| Code validation | `code_service.validate`, app.js Code surface | Adds a local sandbox route where qualified; remote route unchanged |

### P.4 Runtime and packaging recommendation

**Build one engine-agnostic managed boundary and designate exactly one shipped engine per profile
through a release-pinned engine manifest.** The candidate is pinned upstream `llama.cpp`
`llama-server`, as already decided. The existing Ollama adapter stays as the explicit developer
and parity baseline. A bounded parity checkpoint on the Mac (P-1) chooses the shipped engine.

Managed boundary (`backend/coordinator/engine.py`; headless-capable per PROJECT §7.1):

- **Engine manifest**, shipped inside the application: engine kind, upstream release tag/build and
  commit, licence, per-platform backend, and the relative path and SHA-256 of every shipped engine
  file. Committed as JSON; binaries are fetched by a pinned, hash-checked build script into an
  ignored directory and never committed.
- **Verification before every launch**; mismatch yields `engine_unverified` and a graphical repair
  route (reinstall/recover, never a download).
- **Launch**: absolute path only, no `PATH` lookup, no shell, minimal explicit environment, loopback
  host, Refinix-chosen free port in a private range, per-launch random API key, built-in web UI and
  slot persistence disabled, prompts not logged. Exact flags are verified against the pinned build's
  own help output at P-1, because they change between builds.
- **Ownership proof** after start: child alive; authenticated request accepted; unauthenticated
  request refused (so the listener enforces this launch's secret); reported build and model path
  match. A foreign listener is skipped, never adopted.
- **Lifecycle**: one engine process per loaded model, started lazily or for the default Chat model
  after setup; memory admission (default one resident model); idle unload after 10 minutes
  (matching today's `KEEP_ALIVE`); stop on quit; watchdog fails in-flight attempts as "engine
  stopped" and restarts on the next request; crash-loop limit becomes a blocker with Retry.
- **Weights** live content-addressed under a new `models/` data-root subdirectory, never in the package.

Adapter: keep `runtime.py`'s public API and move Ollama HTTP details beside it unchanged. Add a
llama-server adapter on the OpenAI-compatible streaming endpoint: reasoning through
`chat_template_kwargs.enable_thinking` and separated reasoning deltas; content deltas; `done` with
`timings`/usage mapped onto today's metric keys and `stop`/`length` reasons; structured output via
`response_format` JSON Schema; images as data-URI parts with a verified projector; cancellation
through the existing socket-abort watcher; overflow mapped to the existing message. `probe()` keeps
its shape, with installed models taken from Refinix's own verified install records. This is two
concrete adapters, not a plugin registry.

**Parity rule at P-1 (Mac profile, same model bytes and same Refinix prompts).** Adopt llama-server for
a profile only if all hold: (1) clean start/stop with loopback-only binding observed; (2) Chat
reasoning off/on separated with a visible answer; (3) Code proposal, general document, approval note
and page-reading schemas decode and parse strictly; (4) Stop is responsive during prompt processing
and generation; (5) overflow refused at the qualified window without silent truncation; (6) vision
reads the C07 page if OCR is to be claimed; (7) cold/warm TTFT, tokens/s and peak RSS recorded against
Ollama 0.34.2 on the same Mac, with regressions reported; (8) no outbound connection observed during
the run. First try the existing Ollama weights blob (same bytes, no download); if upstream
llama-server rejects or mis-serves it, acquire upstream-format GGUF and projector from an
authoritative source after a licence check. If (1)-(6) cannot be met by configuration in the pinned
build, stop and present the bounded alternative: a pinned app-managed Ollama build through the same
boundary (private host and model store, verified binary, cloud features verified absent), with its
own evidence. That is a user decision per [tasks.md](../tasks.md) Phase 1 item D.

Packaging candidates, confirmed by package spikes on each OS:

| OS profile candidate | Application | Engine backend | Install/update shape | Prerequisites to disclose |
|---|---|---|---|---|
| macOS 26, Apple Silicon | Existing pinned py2app bundle plus engine resources | Metal build | `.dmg` first install; signed `.app` zip as update payload, swapped by a helper after exit | Developer ID signing and notarisation need the user's Apple developer account |
| Windows 11 Home/Pro x64 | PyInstaller onedir (to be pinned) | Vulkan build measured against CPU (and CUDA if Vulkan underperforms) | Inno Setup per-user installer (no administrator); update runs the verified installer silently after exit; previous verified installer kept for recovery | WebView2 (present on Windows 11); Authenticode certificate, otherwise SmartScreen warnings |
| Ubuntu 24.04 desktop x86_64 | PyInstaller onedir packaged as AppImage with the static type-2 runtime (no libfuse2) | Vulkan/CPU as Windows | Single user-writable file replaced atomically; previous file kept for recovery | System GTK/WebKitGTK 4.1; "Allow executing" in Files |

Vulkan is proposed because one build covers the NVIDIA and Intel-only laptops in the recorded fleet;
it is a measured choice, not an assumption.

### P.5 Section plans

Each section is completed end to end before the next, with its checks; items are a checklist inside
the section, not separate tasks.

**Section 1 — Foundation (Phase 1)**

1. Schema guard (K2): read the stored version before DDL; refuse a newer schema with a startup blocker
   and "Open data folder"; never lower the version; record `app_version` of the last writer.
2. Managed engine boundary, manifest, fetch script and ownership proof (P.4); developer mode only from
   a source checkout with no managed engine present, or an explicit developer setting; frozen builds
   never use an external engine.
3. Runtime split and llama-server adapter; `local_model_ref`/`local_profiles` take runtime name and
   version from the active engine identity.
4. Profiles: device-class target IDs; managed-engine profiles enter the registry only from accepted
   qualification artifacts. Until then the managed path reports `no_qualified_profile`, which is the
   truthful state. Qualification artifacts gain engine build and device class (version 1.1, 1.0 still readable).
5. Hardware inventory in `device.py`: total/available memory and data-root free disk per OS; GPU and
   backends from the managed engine's device listing where available, otherwise OS probes; unknown
   stays unknown. `device_class()` predicates with explicit bounds.
6. Typed readiness (K5) in a small module rather than enlarging server.py; codes include
   `engine_missing`, `engine_unverified`, `engine_not_running`, `model_not_installed`,
   `model_integrity_mismatch`, `model_disabled`, `no_qualified_profile`, `device_unsupported`,
   `insufficient_memory`, `schema_newer`, `setup_incomplete`; each with detail and a graphical action.
7. Startup integration in lifecycle/shell; stale copy (K7) and package exclusion (K16) cleanup.
8. Packaging boundary: engine resources and manifests in `packaging_plan.py`; build-time check that every
   managed profile names the shipped engine build; Windows and Linux build scripts; a build-only CI
   matrix producing unsigned artifacts with no secrets and no publishing.

Offline checks: a fake hash-pinned engine executable for supervisor tests (hash mismatch refused; a
fake `ollama`/`llama-server` earlier on `PATH` never used; foreign listener skipped; listener that
accepts unauthenticated requests not adopted; crash yields a blocker; idle unload; only owned
processes stopped); recorded SSE fixtures for the adapter (reasoning separation, schema passthrough,
stop/length and metric mapping, stalled-stream cancel, overflow, malformed line); a database at
`SCHEMA_VERSION + 1` that opens today and must be refused; every readiness code from a constructed
state, including today's generic case; frontend tests per code; all existing suites in developer mode.

Exit: managed boundary in source with the developer baseline intact; P-1 evidence decides the Mac engine;
Windows/Linux routes have build scripts; schema guard landed.

**Section 2 — Standalone workflows (Phase 2)**

1. Catalogue entries gain component files, engine compatibility, resource needs and download sources.
   The Ollama entry stays for developer mode.
2. Provisioning (`provision.py`): explicit HTTPS download from the entry's own hosts (redirects only to
   that entry's listed hosts; system proxy honoured for downloads only), disk preflight, staging under
   `models/.staging/`, resume, streaming SHA-256, atomic promotion, additive schema tables for files and
   installs, SSE progress, cancel, startup cleanup of interrupted staging. Offline import accepts a bundle
   only when every file matches a catalogue entry exactly. Removal previews impact, drains or cancels
   affected work, deletes only unreferenced files and clears selections with alternatives offered.
   Automatic self-tests run after install/enable and are stored against model manifest, engine build
   and device class.
3. Onboarding and Settings -> Models in the existing frontend: device summary; at most six
   recommendations with Good fit/Marginal/Insufficient/Unknown labels marked measured or estimated, and
   Show more; capability choices where skipping Documents or Code never blocks Chat; review of sizes,
   sources, licences and data location; Download or Import; progress and cancel; automatic self-tests.
4. Fit check: weights + KV for the configured context and slots + runtime overhead + headroom against
   memory; measured RSS replaces estimates when evidence exists; no numeric score.
5. Local Auto: candidates are installed, enabled, integrity-verified, qualified for this engine, device
   class and workflow, and fit beside resident models. Ranked by the Balanced/Faster/Higher-quality
   preference, then evidence, then already-loaded, then stable ID. Route reason recorded on the attempt
   and Proof Card. Fallback only after a pre-output engine or model failure, as a new attempt with a
   visible reason; never for pinned choices; never after partial output.
6. Budgets: profile-derived everywhere (K6); engine context set to qualified context times slots.
7. Instructions and curated memory (K13): `AGENTS.md` and `memory.md` in the data root, editable and
   size-capped in Settings, added as fenced user-authored blocks after Refinix's own identity and policy
   text, inside the context budget with inclusion or omission recorded; never written automatically.
8. Scan reading: qualify `documents.ocr` with the main model's vision on the managed engine using C07
   synthetic fixtures; register only from evidence.
9. Second model (K12) per decision Q4, with full manifest and qualification.

Offline checks: provisioning against a loopback fixture server (resume, cancel, hash mismatch, low
disk, off-list redirect, crash mid-download, exact/tampered/unknown import, shared-file removal);
Auto ordering, pinned never moving, fallback only before output; fit labels; indicator equals dispatch;
instruction inclusion/omission records. Device checks on the Mac when authorised: setup, Chat,
Documents scan + SOP -> Word if OCR qualifies, Code proposal/Apply/Undo, quit and reopen.

**Section 3 — Local safety, reliability and evidence (local Phase 4)**

1. Engine failure handling with typed failures (`engine_stopped`, `out_of_memory`, `load_failed`) and
   no automatic retry after partial output.
2. Admission and visible queueing sized to engine slots and memory budget.
3. Local Code sandbox (`sandbox.py`), recommended first on macOS: a generated Seatbelt profile denying
   network, reads outside the job workspace and runtime, writes outside the job's temporary directory,
   and execution of anything but the bundled interpreter; resource limits for CPU, file size, open files
   and core dumps; wall-clock timeout; process-group memory and process-count monitoring with kill
   (macOS does not enforce address-space limits); output caps. Linux bubblewrap is the second candidate
   if usable without administrator changes on Ubuntu 24.04. Windows discloses validation unavailable
   for Beta. The approved-command contract mirrors the worker allowlist, with a test that the two
   allowlists stay equal. Scope is standard-library Python `unittest` projects like the C07 fixture.
4. Proof Cards bind engine build, model manifest, device class, input/output hashes, validation and
   approval. A sampled observer of Refinix and engine sockets during the job window reports
   "Public outbound flows observed: N" with method and interval. Enforcement stays "unavailable" unless
   an identified control exists.
5. One stabilisation pass over the failure matrix; fix release-blocking defects only.

Checks: offline fakes for watchdog, admission and policy generation. Sandbox escape tests (network,
private-file read, write outside temporary space, CPU, memory, process and output limits, timeout) run
real processes on the host, so they need permission Q-perm-3.

**Section 4 — Packages, updates and release (Phase 5)**

1. One version source (`packaging_plan.VERSION`) shown in status, stored in the database, embedded
   with commit and build date.
2. Builders for the three OS profiles verifying the shipped inventory (including engine files and
   manifests) against the package boundary.
3. Updater (`updates.py` plus an apply helper): TUF metadata through `python-tuf` with a packaged root,
   which supplies signature thresholds, expiry, rollback and freeze protection rather than invented
   cryptography. Explicit Check fetches metadata only. Compatible offers (platform, architecture,
   minimum schema, engine compatibility) are chosen from target metadata. Download to staging;
   verify TUF length and hash plus platform signature (`codesign`/Gatekeeper, Authenticode); drain or
   cancel jobs with confirmation; SQLite online backup plus instructions and memory into
   `backups/pre-update-<version>/`; helper swaps the application after exit and starts the new version
   in a health-check mode; failure restores the previous application. A newer database is set aside,
   never deleted or overwritten, and the older binary refuses it through K2. A persisted update journal
   makes every step crash-resumable. Offline import uses the same verification from a local bundle;
   expired metadata requires a fresh bundle.
4. Settings -> Updates: installed version, last check result (never "up to date" without a verified
   check), Check, Download, Install and restart, Import update, progress and cancel, notes.
5. Release tooling under `scripts/release/` to build TUF metadata with keys the user holds; CI never
   sees signing keys in pull-request jobs.

Offline checks: generated TUF test repositories for tampered target, expired timestamp, rollback
version, wrong platform and invalid signer, each refused with no promotion; journal recovery at every
step; swap logic on temporary directories. Device checks: two labelled builds per profile, including
an engine-changing transition, on the user's devices.

### P.6 Cleanup candidates (each with its evidence)

| Candidate | Evidence | Action |
|---|---|---|
| Stale status text and fields | K7 | Replace with truthful values; update app.js consumers |
| Terminal setup/removal commands | K4 | Developer mode only |
| Deprecated `keychain_available` | Marked for removal at [server.py:1849-1857](../backend/coordinator/server.py); still read at [app.js:3251, 3267](../frontend/app/app.js) | Move the UI to `credential_store.available`, then remove |
| `check_runtime_context.py` in packages | K16 | Exclude `check_` modules from packages; keep the file |
| Stale module docstrings ("only inference path in C03") | [runtime.py:1](../backend/coordinator/runtime.py), [server.py:1-10](../backend/coordinator/server.py) | Correct alongside the runtime split |

Retained deliberately: `AegisForgeCoordinator/` server prefix (renaming breaks recognition of an
already-running older coordinator); worker, contracts, Kubernetes, Redis, pairing and `scripts/refinix`.
There is no deletion quota.

### P.7 Validation families

- **Offline (needs Q-perm-1):** `desktop/.venv/bin/python` (3.12.13) `-m unittest discover` for
  `backend/contracts`, `backend/coordinator`, `desktop`, `scripts`, plus `backend/worker` and
  `deploy/k3s` to prove no regression; `node --test frontend/app/test-*.cjs` (Node 26.7 present).
- **Mac device (needs Q-perm-2/3):** P-1 parity and qualification artifacts; sandbox escape matrix;
  setup-to-reopen journey; local py2app build of the updated bundle.
- **User devices (after execution):** Windows and Linux package builds, install journeys, engine
  backends, sandbox disclosure, two-build update matrix.
- **Release (separate authorisation):** signing, notarisation, publication.

Each fix is tested against the original bad state (a newer-schema database, a foreign listener, the
generic ready line, a terminal command in Settings) rather than only the presence of the mitigation.

<a id="p8-prerequisites-for-the-user--one-batch"></a>
### P.8 Prerequisites for the user — one batch

Permissions (each scoped; none covers Git writes or publication):

- **Q-perm-1 — offline checks.** Run the families in P.7 with existing local tools.
  Recommendation: grant; implementation cannot be called tested without it.
- **Q-perm-2 — engine and model acquisition plus local inference on this Mac.** Download one pinned
  `llama.cpp` macOS arm64 release asset (exact build and SHA-256 recorded first) from the official
  GitHub releases; reuse the existing Ollama weights blob first; only if needed, download an
  upstream-format Qwen3.5-4B GGUF and projector (about 3-4 GB) from an authoritative source after a
  licence check; run loopback-only inference for qualification. Files stay outside the repository.
  Recommendation: grant, with a stop if provenance or licence cannot be established.
- **Q-perm-3 — host-process checks and local build.** Run the sandbox escape matrix on this Mac and
  build the py2app bundle locally (no signing or publishing). Recommendation: grant.
- **Q-perm-4 — dependency acquisition.** Hash-pinned install into `desktop/.venv` of `python-tuf` and
  its dependencies (`securesystemslib`, `cryptography`, `urllib3`) for updates and `psutil` for process
  and socket observation; pinning PyInstaller for the Windows/Linux builders (installed only where those
  builds run). Recommendation: grant; each records source, version, licence and hash.
- **Q-perm-5 — focused protected-doc updates during execution.** `model-catalog.md` (engine and model
  manifests, evidence), `releases.md` (chosen package/updater components), `security.md` (local sandbox
  and observer semantics), `evaluation.md` (evidence). `PROJECT.md`/`tasks.md` only if a scope decision
  changes them. Recommendation: grant for those four, limited to recording implemented decisions and evidence.

Decisions (Recommendation / Reason / Trade-off):

- **Q4 — second Beta model.** Recommend a smaller sibling of Qwen3.5-4B from the same authoritative
  source and licence (exact artifact fixed after provenance review), qualified for Chat and, if it
  passes, document generation, used by Auto for Faster and low-memory devices; 4B stays default for Code,
  Documents and scan reading. Reason: satisfies two-model selection, widens reach to 4 GB-VRAM and
  integrated-GPU laptops, small download. Trade-off: about 1-2 GB optional download and extra
  qualification; a 7B coder would help Code more but exceeds much of the recorded fleet.
- **Q5 — Beta device classes and devices.** Recommend (a) macOS 26 Apple Silicon with at least 16 GB
  unified memory (Metal); (b) Windows 11 x64 with at least 16 GB RAM and an NVIDIA GPU of at least 4 GB
  (Vulkan, CPU fallback measured); (c) Ubuntu 24.04 desktop x86_64 with at least 16 GB RAM and an NVIDIA
  GPU of at least 4 GB (Vulkan). Needed from the user: which Windows and Ubuntu machines will be used
  for qualification and roughly when. Trade-off: narrower than "any PC", but each class has a
  representative device; integrated-GPU-only Windows can follow as a CPU class once measured.
- **Q6 — first local sandbox profile.** Recommend macOS Seatbelt first, Linux bubblewrap second if
  usable without administrator changes, Windows disclosed unavailable for Beta. Reason: the Mac is the
  device available now and Seatbelt is a widely used local isolation primitive. Trade-off: Apple marks
  `sandbox-exec` deprecated though functional; memory limits are monitored rather than kernel-enforced.
- **Q7 — signing and update trust.** Recommend TUF metadata with root and targets keys held offline by
  the user and a timestamp/snapshot key only in a protected release job; GitHub Releases hosting. Needed:
  will the user obtain an Apple Developer Program membership and a Windows code-signing certificate?
  Without them the release gates in [releases.md](releases.md) cannot pass and installs show OS
  warnings; that would be a scope decision, not something to work around.

<a id="p9-proposed-user-facing-change-summary"></a>
### P.9 Proposed user-facing change summary

| Area | Today | After this plan | Main paths | Risk and recovery |
|---|---|---|---|---|
| AI engine | Uses whatever Ollama answers on port 11434 or finds on `PATH`; an Ollama update can disable Chat | Refinix starts its own verified engine on a private loopback port; an external Ollama is ignored by installed builds | `backend/coordinator/engine.py`, `runtime.py`, `desktop/lifecycle.py` | Modified or missing engine is refused with a repair action; developer mode keeps Ollama for contributors |
| Setup | Settings shows terminal commands | Graphical first-run setup: hardware summary, recommended models, sizes and licences, Download or Import, progress, cancel, automatic self-tests | `provision.py`, `models.py`, `device.py`, `frontend/app/*` | Nothing downloads without a click; failed setup leaves other capabilities usable |
| Readiness | "The selected model is unavailable for new work" for several causes | The specific cause and the action that fixes it | readiness module, `server.py`, `app.js` | None beyond copy changes |
| Model choice | Manual per workflow; Auto refused | Auto picks among qualified local models with a visible reason; pinned choices never move | `server.py`, `app.js` | Fallback only before any output |
| Memory | Not available | Editable instructions and curated memory, included within the context budget | data-root `AGENTS.md`/`memory.md`, Settings | Never written automatically; size-capped |
| Code | Local Apply/Undo labelled not sandbox-tested; validation only through a paired worker | On qualified Macs, sandboxed validation before Apply; elsewhere the existing label stays | `sandbox.py`, `code_service.py` | No host-execution fallback |
| Data safety | Older Refinix silently opens newer data | Older Refinix refuses newer data and explains how to recover | `db.py`, `lifecycle.py` | Data is never altered on refusal |
| Updates | None | Settings -> Updates with explicit Check, Download, Install and restart, Import update; backup and recovery | `updates.py`, apply helper, `scripts/release/` | Failed or tampered updates leave the current version working |
| Packages | macOS prototype bundle only | Build scripts for macOS, Windows and Ubuntu; unsigned CI artifacts | `desktop/`, `.github/workflows/` | Signing and publication remain user actions |

### P.10 Points for the review agent and open risks

Positions that differ from or sharpen the draft, for explicit challenge: engine-agnostic boundary with
managed Ollama only as a parity fallback (P.4); concrete device classes (K9, Q5); TUF as the single
cross-platform trust layer instead of three per-OS updater frameworks; AppImage with the static runtime
and per-user Inno Setup; Seatbelt as the first local sandbox; instructions/memory in Beta scope; a
second model as a Beta requirement; schema guard first; PDF output remaining macOS-only.

Open risks: whether the pinned upstream build serves Qwen3.5-4B correctly (architecture, template,
reasoning switch, schema grammar, vision projector) is unknown until P-1; Vulkan performance on the
fleet is unmeasured; WebKitGTK and PyGObject bundling on Ubuntu needs a device spike; macOS hardened
runtime entitlements for the engine are unverified; the full scope is large, so if the run cannot finish
all four sections coherently, sections finish in order and anything unfinished is reported as unmet,
never narrowed silently.

### P.11 Run order and stop rules

1. Section 1 offline work, then P-1 on the Mac if Q-perm-2 is granted. If parity fails, stop for the
   engine decision.
2. Section 2, then Mac journey checks if authorised.
3. Section 3, including the Mac sandbox matrix if Q-perm-3 is granted.
4. Section 4, including a local unsigned py2app build if authorised.
5. Focused doc updates if Q-perm-5 is granted; ledger entries; report with
   `GIT / GITHUB — RUN THESE YOURSELF` and `VERIFY — RUN THESE YOURSELF`.

Stop and ask only for: a failed parity rule, a provenance or licence failure, a scope decision (for
example OCR not qualifying), a security-boundary change, or a missing permission. Windows and Linux
device work, signing and publication follow the run as user checkpoints; implementation is not called
complete until the user has verified it.

<a id="review-agent-assessment-20261004"></a>
## Review-agent assessment — NEEDS FIX (2026-10-04)

This reviews the recorded P.1–P.11 proposal at HEAD `8c6d7a9` and the preserved dirty tree, against
the latest user request and changed authorities. The engine-ownership repair, existing API/UI reuse,
newer-schema guard, capability-specific qualification and four-section execution structure are sound
directions. A planning review is not fresh execution proof. No app edits, tests, installs, model
downloads, live inference or Git writes were performed.

### Required corrections inside the existing four sections

**R1 — Foundation/workflows: implement reviewed preset matching and use research first.**
P.5 section 2 item 4 still derives fit from weights/KV/overhead at setup; P.8 Q5 turns macOS 26,
16 GB and NVIDIA 4 GB into proposed minimums and asks which user-owned machines will be available.
The latest direction is a shipped table of category/hardware presets. Replace that design with
[the catalogue record](model-catalog.md#reviewed-presets), matched by OS range, chip/architecture,
backend, memory/VRAM and storage. Keep simple actual free-memory/disk/health checks and runtime
enforcement. Do not build a startup optimizer or match by MacBook/ASUS/HP brand names.

Use [the published research record](evaluation.md#hardware-presets-20261004) and existing evidence
to propose settings with explicit measured/estimated gaps. The existing Mac source matches only
`Mac17,3`/16 GiB in [device.py](../backend/coordinator/device.py); that is implementation evidence,
not a justified universal product minimum. A minimum macOS version must follow dependency/build
support, not the OS currently installed on the developer Mac. Windows 11 and Ubuntu 24.04 are
package candidates; no all-OS minimum matrix or 8 GB/RTX 2050 preset is accepted yet. Do not require
ownership of every laptop to research or implement tiers. Use representative available devices,
appropriate CI and volunteer observations for remaining package/security/update checks.

P.4 says Vulkan is a measured choice, although no new checks ran. Label backend/package choices
proposed until observed. Keep model artifact hashes/settings identical for adapter parity; if a new
GGUF/projector is needed, compare both engines using the same newly pinned artifacts where possible,
or explicitly separate the artifact change from the engine comparison. Historical Ollama context
8192/output 2048 on the Mac cannot qualify a new engine or all hardware classes.

**R2 — All sections: demonstrate reuse before authoring commodity infrastructure.**
The proposal jumps directly to custom `provision.py` download/resume/cache logic and an update swap
helper. Complete the small [reuse inventory](model-catalog.md#42-reuse-before-new-infrastructure)
inside those existing sections: existing path, upstream option, concrete policy/compatibility gap,
chosen integration and licence/network evidence. Evaluate pinned Hub download/cache APIs and runtime
resource controls; keep offline/telemetry and integrity requirements. Reuse existing paths,
credentials, containment and writers as P.1 K1 proposes.

The authorities already consider `llmfit` for internal planning. Its
[hardware-profile and JSON planning interface](https://github.com/AlexsJones/llmfit/blob/main/docs/cli.md)
can analyze target configurations without the physical laptop. Evaluate that route for generating
candidate presets before writing fit estimation yourself; inspect source/version, estimates and
community provenance. Keep it out of Beta runtime as currently decided and do not enable downloads,
benchmarks or result sharing without the relevant permission.

TUF is a suitable update-trust candidate, but its
[client API](https://theupdateframework.readthedocs.io/en/stable/api/tuf.ngclient.updater.html)
refreshes metadata, identifies and downloads targets. It does not implement native installation or
state recovery. Compare maintained platform tools, including
[Sparkle](https://sparkle-project.org/documentation/) where suitable, with the proposed minimal helper.
Choose the simplest qualified solution; do not mandate a new dependency merely because it exists.
Refinix still owns catalogue policy, workflow qualification, approvals and integration. No inspected
tool supplies that entire product contract.

**R3 — Foundation/packages: rollback must restore compatible working state.**
P.5 section 4 item 3 snapshots SQLite/instructions, restores the older app on failure and sets the
newer database aside. It does not specify installing the compatible snapshot at the canonical data
root. The schema guard can correctly refuse the newer DB while the restored app still cannot open
the workspace. [Release recovery](releases.md#5-data-models-and-compatibility) requires a compatible
binary **and** data state, while preserving newer user work.

Specify the journal states and recovery order for application, database/WAL-safe backup, affected
config/model references/instructions and other migrated state. Preserve newer state/artifacts in a
separate recovery location before restoring compatible state; avoid copying/replacing protected
credentials as plaintext. Explain the user-visible recovery result and what happens after a crash at
each step. Do not silently overwrite work created after the snapshot.

K2 is confirmed and should remain first: [db.connect](../backend/coordinator/db.py) currently executes
`journal_mode=WAL` and `_SCHEMA` before reading the schema version, then writes `SCHEMA_VERSION`
unconditionally. The corrected preflight must reject a newer schema before persistent database
changes, including journal-mode changes, rather than just before later DDL. Define how new/legacy
stores are distinguished without modifying an incompatible existing store. Keep focused acceptance
cases for newer-schema refusal and usable binary/data rollback, with newer work recoverable.

**R4 — Local safety: monitoring is not the promised resource boundary.**
P.5 section 3 proposes Seatbelt plus process-group memory/process-count polling because macOS
address-space limits are unavailable. That may be a candidate, but polling and killing after a
threshold does not establish hard aggregate memory/process limits or descendant containment.
[The existing worker limits](../backend/worker/validate.py) tolerate unsupported per-process limits
because Pod cgroups supply enforcement; copying the allowlist does not reproduce that boundary.
[Security policy](security.md#8-filesystem-and-sandbox) requires a qualified local sandbox and
refusal where unavailable.

Evaluate existing isolation tools before designing a replacement. For the chosen candidate, name
the enforcing mechanism and supported privilege/OS conditions for network, files, CPU, aggregate
memory, processes/descendants, wall time and output. Document limitations and keep execution
unavailable when required controls cannot be established. A successful policy-generation fake or
timeout is not sandbox qualification. The authorized live escape/resource matrix must cover the
actual packaged runner. If macOS cannot satisfy the contract, recommend another eligible local
profile/tool or raise the genuine product decision; do not weaken the requirement silently.

**R5 — Local evidence/packages: preserve observer coverage and dependency truth.**
P.5 section 3 item 4 needs a precise sampled-observer contract. A socket snapshot can miss short
connections. [psutil documents](https://psutil.readthedocs.io/stable/) privilege/incomplete-connection
limits and loss of descendant discovery when an intermediate process disappears. Report method,
interval, processes/interfaces covered, unavailable or partial coverage and observer errors. Use
connection/sample terminology unless actual flow tracking exists; never convert denied or incomplete
observation to a comprehensive zero-egress claim. Zero observed does not establish enforcement.
Evaluate an existing appropriate observer before writing bespoke tracking.

Likewise, package preflight must check native prerequisites. Microsoft's
[WebView2 distribution guide](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution)
recommends checking runtime presence; the Windows 11 label is not a substitute for that check.
The [static AppImage runtime](https://github.com/AppImage/type2-runtime) avoids a target `libfuse2`
dependency but still normally mounts through FUSE. Account for FUSE availability or a supported
graphical alternative, plus GTK/WebKit and backend prerequisites. Do not promise a terminal-free
install until the chosen package path is observed.

### Owner reconciliation and acceptance

Review the current-turn diffs in `AGENTS.md`, `docs/PROJECT.md`, `tasks.md`, `docs/model-catalog.md`,
`docs/releases.md` and the appended research record in `docs/evaluation.md`. Check requirements
against the implementation paths and flag actual contradictions. Preserve the original proposal
above; append one reconciled plan/change summary in this file, mapping R1–R5 to corrections within
the same four sections. Include evidence sources, remaining unknowns and the reuse decisions.
Do not create another task tree, handoff file or subagent.

Plan PASS requires a consistent preset/reuse design, recoverable binary/data transition, an honest
sandbox-enforcement path and accurate observation/package claims. It does not mean app tests or
release gates have passed. Before a sustained implementation run, present the reconciled concrete
change summary and ask only for still-required checks/downloads/host actions or human decisions.
Do not repeat settled direction or treat this documentation authorization as permission for live work.

<a id="owner-reconciliation-20261004"></a>
## Owner reconciliation — R1–R5 and deeper source findings (2026-10-04)

**Status: RECONCILED PROPOSAL — awaiting review-agent re-review.** The owner accepts R1–R5. This
section supersedes the conflicting parts of P.1–P.11, which stay above unchanged for comparison.
Inputs were source and package inspection at HEAD `8c6d7a9` on the same dirty tree, the changed
authorities, and public primary records read on 2026-10-04 (sources are cited inline). The only
local commands were non-mutating reads: `otool`, `sysconfig`, `git diff`, `grep`. Nothing was
installed, downloaded, built, tested or run against a model.

### O.1 Changed authorities reviewed

The current-turn changes are consistent with the implementation paths: AGENTS.md (presets, reuse,
brands are labels), PROJECT.md §4.3.1 and the llmfit paragraph, tasks.md Phase 1 item D and the
Phase 2 preset item, model-catalog.md §4.1/§4.2 and evidence labels, releases.md preset binding and
representative-device evidence, and the evaluation research record. Three points need wording or a
recorded decision during execution (a doc-correction scope that is already authorized):

| Location | Issue | Proposed handling |
|---|---|---|
| [model-catalog.md §4 closing paragraph](model-catalog.md#4-required-manifest) | "A reference to runtime-owned weights … does not duplicate weights managed by Ollama, llama.cpp" is Ollama-era wording. `llama-server` reads a file path and owns no store, so under the managed engine Refinix owns the content-addressed weight store outside the package | Clarify that the managed engine's weights are a Refinix-owned store, never duplicated, never inside the package |
| [PROJECT.md §4.3.1](PROJECT.md#431-reviewed-hardware-and-capability-presets) "existing offline libraries … should supply … downloads" | The reuse decision in O.4 keeps a small downloader on the HTTP client python-tuf already brings, rather than the Hugging Face library. This is allowed when the gap is evidenced | Record that decision and its gaps in the model-catalog reuse table; not a contract change |
| [evaluation research record](evaluation.md#hardware-presets-20261004) | The Ollama weights blob (3,389,971,840 B) is about the upstream split's weights (2.74 GB) plus projector (672 MB) | Supports K20 below. P-1 should expect new upstream artifacts and separate that change from the engine comparison |
| [releases.md](releases.md) and [PROJECT.md §26](PROJECT.md#26-github-application-release-and-updates) | They correctly say CI artifacts are not end-user releases and development artifacts are never accepted Beta updates, but they do not yet describe the **internal test-package channel** in O.11 | Propose one short releases.md addition during execution: internal unsigned artifacts with manifests, a separate trust root, and evidence status. Protected doc, so it is edited only with the user's permission |

Re-checked for the internal test-package requirement: no authority file has changed since this
review. Their modification times all precede this handoff's reconciliation edit, so the review
above stands; the only addition needed is the releases.md row above.

### O.2 New findings from deeper source and package inspection

| # | Finding | Evidence (observed now) | Consequence |
|---|---|---|---|
| K17 | **The macOS package's declared minimum OS is false** | The venv base is Homebrew Python (`desktop/.venv/pyvenv.cfg`), with `MACOSX_DEPLOYMENT_TARGET` 26 and platform `macosx-26.0-arm64`. `otool` shows `minos 26.0` for the Homebrew framework and for the copy inside `desktop/dist/Refinix.app`. [setup_py2app.py:85](../desktop/setup_py2app.py) declares `LSMinimumSystemVersion` 12.0; the pinned pypdfium2 wheel is `macosx_13_0_arm64` (`libpdfium.dylib` `minos 13.0`) | The current bundle cannot start below macOS 26 while claiming 12. The macOS floor must come from the build interpreter and the shipped binaries (R1). Build check: the highest `minos` of any shipped Mach-O must not exceed the declared minimum; the existing bundle must fail this check |
| K18 | Beta still exposes deferred mesh controls | Settings "Connected computers" card with a pairing form whose copy says "macOS Keychain" on every OS ([control.html:132-176](../frontend/app/control.html)); the Code target popover offers "Paired worker" ([app.js:4987-5006](../frontend/app/app.js)) | PROJECT §3 requires future peer controls hidden or marked unavailable. Hide them in Beta builds behind an off-by-default mesh setting; keep the code |
| K19 | The window backend is auto-selected | `webview.start(..., gui=gui)` with `gui=None` by default ([shell.py:575](../desktop/shell.py), [__main__.py:27](../desktop/__main__.py)) | Packaged builds pin `cocoa`/`edgechromium`/`gtk` and fail visibly when the backend is missing, instead of silently using an unqualified renderer |
| K20 | The existing Ollama blob is probably not an upstream-format artifact | Size match described in O.1; Ollama's Qwen3.5 manifest has no separate projector layer ([model-catalog §3.1](model-catalog.md#31-od-05--the-first-selected-model-set)) | P-1 stage A tries it at no cost. Expect stage B with newly pinned upstream weights and projector |
| K21 | llama-server's `--fit` adjusts any unset argument; `/health`, `/v1/health` and `/v1/models` need no API key; a router mode exists (`--models-dir`, `--models-preset`); `--offline` exists | [llama-server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md), read 2026-10-04 | Pass every qualified setting explicitly and turn fitting off. Prove ownership on an authenticated endpoint such as `/props`, not `/v1/models`. Evaluate router mode at P-1 as the reuse option for model load/unload. Corrects P.4 |
| K22 | `db.connect` will add Refinix tables to any SQLite file it is given | No `meta` check before `executescript(_SCHEMA)` ([db.py:434-437](../backend/coordinator/db.py)) | The preflight also refuses a non-Refinix or corrupt file without modifying it |
| K23 | macOS does not enforce memory resource limits | `RLIMIT_AS`/`RLIMIT_DATA` are accepted but not enforced on Darwin ([summary of the documented behaviour](https://rdrr.io/cran/unix/man/rlimit.html)) | Withdraws the Seatbelt-first sandbox (R4). See O.6 |

Two measured-improvement candidates, not commitments: (1) exact token counts from the engine's
template and tokenizer endpoints instead of the characters/3 estimate in
[context.py](../backend/coordinator/context.py), if the pinned build exposes them; (2) llama-server
prompt caching (`--cache-prompt`, enabled by default upstream) for multi-turn time-to-first-token,
kept only if P-1 shows correct output and the single-workspace isolation rules hold. Status
polling (about three loopback calls every 10-15 s per open window) can read the supervisor's state
instead, but it is not a bottleneck and is not prioritised.

### O.3 R1 — reviewed presets replace setup-time fit calculation

Withdrawn: P.5 §2 item 4 (weights + KV + overhead formula), P.8 Q5 minimums and device ownership,
and the P.4 wording "Vulkan is a measured choice". Backend and package choices are **proposed until
observed**.

**Data model in the existing boundary.** No second framework. Add a frozen `HardwareTier` record
type in [profiles.py](../backend/contracts/profiles.py), which is already "the only production
registry". Each `ExecutionProfile.target_profile_id` names a tier. The catalogue entries in
[models.py](../backend/coordinator/models.py) gain the §4.1 groups: identity/provenance, storage,
execution, capacity and evidence. A preset is the join of category, tier, recommended entry, its
qualified execution profiles, engine launch settings (context, output, KV cache types, slots,
offload, threads) and current-capacity floors. Records are Python constants, like `PROFILES`, so
packaging is unchanged and changes are reviewable. The legacy exact `Mac17,3` profiles stay bound
to their Ollama evidence; they are not a product minimum.

**Matching at setup.** Facts come from `device.py` using platform APIs, psutil (memory, disk,
processes), the managed engine's `--list-devices` for backend devices and VRAM, the chip family
from `sysctl machdep.cpu.brand_string` on macOS, and OS release from `platform`/os-release. Brands
are never read. Hard keys select candidate tiers. The recommended choice per category comes from the
reviewed record order; alternatives are listed with evidence labels (Measured in Refinix / Measured
externally / Estimated / Unavailable). The current-capacity check compares available memory and
free disk with the floors and confirms the engine answers. Admission repeats the check: queue,
unload, or use an approved lower preset; never retune.

**Preparing candidate tiers (release engineering only).** Use llmfit's documented
[`--profile` hardware JSON and `plan "<model>" --context N --json`](https://github.com/AlexsJones/llmfit/blob/main/docs/cli.md)
to produce estimates for hypothetical tiers without the hardware. The tool's docs say it does not
download or benchmark automatically; `bench --share` is never used. Its formula ignores KV and
runtime buffers in disk size and is not hybrid-architecture-aware, so outputs are labelled
Estimated with the llmfit revision. Combine with the external rows in the research record and
Refinix measurements from P-1 and representative devices. No tier enters the registry without
Refinix evidence for its execution profiles; unqualified tiers show as Planned.

**OS floors from dependencies, not the developer's OS.** macOS: the highest of the build
interpreter's deployment target, pypdfium2's 13.0, the pinned engine binary's `minos` (read at P-1)
and pywebview/WebKit needs. This requires a base Python with a documented deployment target
(python.org universal2 framework builds, used by CI's macOS runners) instead of Homebrew (K17).
Windows: the PyInstaller, WebView2 and engine-backend requirements. Ubuntu: the build host's glibc
(24.04 builds need glibc 2.39 or later). Exact observed builds stay as separate evidence. Candidate
tiers (Apple M-series unified memory; Windows x64 with a Vulkan dGPU or CPU-only; Ubuntu x86_64 with
a Vulkan dGPU or CPU-only) are proposals with floors filled from evidence, not invented.

**Parity at P-1, with the artifact change separated (R1).** Stage A, same bytes: try the existing
Ollama blob on the pinned llama-server against Ollama 0.34.2. Stage B, if A fails (likely, K20):
pin upstream-format Qwen3.5-4B weights and projector from an authoritative source after a licence
and provenance check. Compare llama-server with Ollama on those same new bytes, imported into a
temporary private Ollama store so the user's store is untouched, for the text workflows. Report
vision separately, because a same-bytes Ollama vision baseline may not be possible. The P.4 parity
criteria otherwise stand, plus explicit `--fit` off and the authenticated ownership check (K21).
Historical 8192/2048 Mac values qualify nothing new.

### O.4 R2 — reuse decisions

| Need | Existing path | Upstream option evaluated | Concrete gap | Decision | Licence / network evidence |
|---|---|---|---|---|---|
| Inference engine | runtime.py adapter (Ollama, developer) | Upstream `llama-server` | Engine ownership and qualified settings are Refinix's | Adopt the pinned build as candidate; one process per model at first; router mode adopted only if P-1 shows it keeps explicit per-model settings, unload control and ownership proof | MIT; `--offline` and `--no-webui` available ([README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)); network behaviour observed at P-1 |
| Preset preparation | Research record, qualification artifacts | llmfit | Estimates only | Internal release-engineering tool; never shipped | Planning-only per PROJECT; no bench/share |
| Hardware and process facts | device.py (OS, arch, Mac sysctl) | psutil; engine `--list-devices` | psutil has no universal GPU/VRAM detector | Adopt psutil (BSD-3) plus the engine's device listing; small OS-specific gaps stay in device.py | psutil makes no network calls |
| Model acquisition | none (terminal commands) | `huggingface_hub` `hf_hub_download` with pinned commit, `local_dir`, `dry_run` ([guide](https://huggingface.co/docs/huggingface_hub/en/guides/download)) | The guide shows no cancellation hook; it installs the native `hf_xet` client by default, adding a platform binary in three packages; cache metadata layout differs from Refinix's verified staging shared with offline import; only single pinned files with known SHA-256 are needed | Do not ship the Hub library in Beta. Download from the Hub's documented pinned resolve URLs (the URLs `hf_hub_url` builds) with urllib3, which python-tuf already brings: Range resume, streaming SHA-256, in-process cancel, progress over the existing event stream. Revisit if P-1 shows Range or throughput problems on Xet-backed files; then use the library in a cancellable subprocess | urllib3 MIT; system proxy honoured only for user-initiated downloads |
| Update trust | none | python-tuf 7.0.1 ngclient | TUF verifies metadata and targets only; it does not install or recover (R2) | Adopt for verification on all OSes. The client needs only `securesystemslib` (pure-Python Ed25519 verification by default) and `urllib3` ([tuf](https://pypi.org/pypi/tuf/json), [securesystemslib](https://pypi.org/pypi/securesystemslib/json)); signing tools with the `crypto` extra stay on the release machine | Apache-2.0 OR MIT; MIT; checks only on explicit user action |
| macOS install step | py2app bundle | Sparkle 2 | Sparkle brings its own appcast/EdDSA trust beside TUF and an Objective-C UI/installer integration through PyObjC, is macOS-only, and has no state recovery | Beta uses a minimal bundle swap through `renamex_np(RENAME_SWAP)` (atomic on APFS) run by the previous app (O.5). Sparkle remains the fallback if device qualification of the swap fails (translocation, permissions) | Sparkle MIT |
| Windows install step | none | Inno Setup per-user installer | Not a trust layer | Adopt as the installer and update applier, after TUF and Authenticode verification. The previous verified installer is kept for recovery | Inno Setup free licence; build-time only |
| Linux install step | none | AppImage (static type-2 runtime) or `.deb` | Static runtime still needs FUSE ([type2-runtime](https://github.com/AppImage/type2-runtime)); a `.deb` can declare GTK/WebKit dependencies but needs an administrator | Decide by observing a clean Ubuntu 24.04 desktop: AppImage if FUSE and WebKitGTK 4.1 are present by default, otherwise `.deb`. Both use atomic file replacement or the package manager plus TUF | Observation pending |
| Data snapshot | db.py, backups_root | SQLite online backup API (`Connection.backup`, stdlib) | none | Adopt; WAL-consistent | stdlib |
| Sandbox | worker validator (Pod cgroups) | systemd user services, Landlock, Job Objects, AppContainer, Seatbelt, Apple `container` | O.6 | O.6 | O.6 |
| Network observation | proof.py `_empty_network()` | psutil per-process connections; OS tools (`nettop`, `ss`, `Get-NetTCPConnection`); flow tracers (eBPF, ETW, NetworkExtension) | Flow tracers need privileges; snapshots miss short connections | psutil snapshots plus Python audit hooks (O.7) | as above |
| Packaging | py2app pinned; packaging_plan.py | PyInstaller (Windows, Linux) | Tool not pinned | Pin with hashes on the build hosts and CI only | GPL with bootloader exception; build-time |

Existing paths, credentials, containment and writers are reused unchanged (K1). The worker is not
imported into desktop code; the sandbox plan contract mirrors its allowlist with an equality test.

### O.5 R3 — compatible binary and data recovery

**Preflight first (K2, K22).** Before any `chmod`, journal-mode change or DDL, `db.connect` opens
the existing file read-only (`mode=ro` URI). A missing or zero-length file is a new store. A file
that is not SQLite, or has no `meta` table, is refused as not a Refinix store. A stored
`schema_version` above `SCHEMA_VERSION` is refused as `schema_newer`. Only then does today's open
proceed. The stored version is never lowered, and `meta.app_version` records the last writer.
Acceptance: the SHA-256 of the main, `-wal` and `-shm` files is unchanged after each refusal. That
test fails on today's code.

**Principle.** The application swap never touches data; the new binary migrates on first open. The
**previous** application, which is known-good code, runs the swap and any recovery. The new
application only reports its health in the journal.

**Journal.** `recovery/update-journal.json` is written with an atomic replace and fsync. It records
id, from/to version, schema and package hash, state, the snapshot manifest and set-aside paths. A
new `recovery/` data-root subdirectory holds snapshots and set-aside state, separate from Code-write
`backups/`. States, and what a crash at each one leaves:

| State | Action | After a crash or failure |
|---|---|---|
| `staged` | Package downloaded and TUF- and platform-signature-verified in `updates/staging/<id>/` | App and data unchanged; staging re-verified or discarded |
| `draining` | New work refused; running jobs finish or are cancelled with confirmation | Back to `staged`; `reconcile_on_start` repairs jobs |
| `snapshotted` | SQLite backup API copy plus `AGENTS.md`, `memory.md`, `config.toml`; manifest of hashes; `PRAGMA quick_check` on the copy | A partial snapshot is deleted; back to `staged` |
| `handoff` | Journal written; app exits; previous app starts in helper mode | Helper resumes from the journal |
| `swapping` | macOS `RENAME_SWAP` of the bundles; Linux atomic file replace keeping `.previous`; Windows verified installer, previous installer cached | No window without an application at the canonical path. Interrupted Windows setup uses the installer's own rollback, then the cached previous installer |
| `migrating` | New app records this before opening the database | No user work yet |
| `healthy` → `committed` | Database opens, `quick_check`, engine files verify and the engine answers, UI served; then the helper commits | The helper restores if `healthy` is not reached within its timeout or the new app exits first |

**Automatic recovery before commit.** If failure happens before `migrating`, the helper swaps the
application back; data is untouched. After `migrating`, the helper moves the current database
**with its `-wal` and `-shm` files** and changed instruction/config files into
`recovery/updates/<id>/set-aside/`, then copies the snapshot into the canonical path (temporary file
in the same folder, then atomic replace), verifies hashes, swaps the application back and records
`rolled_back_with_data`. Moving the sidecar files is essential: a stale WAL applied to the restored
file would corrupt it. Every step is idempotent and checked by hash on resume, following the
`resume_writes` pattern. Nothing is deleted. The previous version then shows: "The update to X
stopped at <step>. Version Y and your data from before the update are restored. Nothing was
deleted; the attempted update's data is kept in <folder>."

**User-initiated rollback after commit**, while the previous app and snapshot are retained:
Settings → Updates shows what will not appear in the previous version (chats, messages and artifacts
created after the snapshot, counted from the current database) and offers the existing Markdown
export first. It then sets the whole current state aside, restores the snapshot and swaps the
application. Returning to X later restores the set-aside state. Artifacts and attachments created
after the snapshot stay on disk. OS credential entries are never copied or renamed; Beta updates
keep credential identifiers stable. Model files are content-addressed and not removed by an update
until the user confirms cleanup after commit. The engine ships inside each application package, so
an application rollback also restores the matching engine. If an older binary meets a newer
database outside this flow (for example, a manual reinstall), the K2 guard refuses it and points to
Recovery.

Acceptance (offline, with fault injection at every state): the application and data end
consistent; the old binary opens the restored data; the set-aside state stays intact and reopens
in the newer version; a stale `-wal` is never applied; refusal leaves the files byte-identical.
Device: two labelled builds per profile, including an engine change.

### O.6 R4 — sandbox with named enforcement

The Seatbelt-first proposal is withdrawn (K23). Every Linux and Windows control named below is
kernel- or OS-enforced; where a required control cannot be established, validation stays
unavailable with its reason.

| Control | Ubuntu 24.04 desktop — **proposed first profile** | Windows 11 Home/Pro x64 — second candidate | macOS — not qualifiable natively |
|---|---|---|---|
| Launch | `systemd-run --user` transient **service** (not a scope, so seccomp properties apply) | `CreateProcess` with an AppContainer token, assigned to a Job Object without breakaway | Seatbelt |
| Network | `RestrictAddressFamilies=AF_UNIX` (seccomp) blocks IPv4/IPv6/packet sockets, so TCP, UDP and DNS fail; Landlock TCP rules (ABI ≥ 4) as a second layer | AppContainer with no network capabilities; loopback is also blocked by default | Seatbelt deny-network (would be enforced) |
| Files | Landlock: read-only interpreter, standard library and job inputs; read-write job temporary folder; no home directory | AppContainer: only paths whose ACLs grant its SID (interpreter, job folder) | Seatbelt file rules (would be enforced) |
| Aggregate memory | cgroup v2 `MemoryMax`, `MemorySwapMax=0`; systemd v255 (the Ubuntu 24.04 series) delegates `pids memory cpu` to user managers ([user@.service.in at v255](https://github.com/systemd/systemd/blob/v255/units/user@.service.in)); Ubuntu's packaging must still be observed | Job `JobMemoryLimit` | **None**: `RLIMIT_AS`/`RLIMIT_DATA` unenforced |
| Processes and descendants | cgroup `TasksMax` (`pids` delegated); the cgroup kills every descendant on stop | Job `ActiveProcessLimit`, kill-on-job-close | Seatbelt can deny `process-fork` |
| CPU | cgroup `CPUQuota` (rate cap, `cpu` delegated at v255) plus `LimitCPU` per process | Job hard CPU-rate cap plus time limit | `RLIMIT_CPU` |
| Wall time and output | `RuntimeMaxSec`; parent-side output caps; `LimitCORE=0` | Job termination; parent-side caps | Timeout; caps |
| Conditions checked before offering | Systemd user manager running; cgroup v2 with `memory`, `pids` and `cpu` delegated; Landlock enabled; system `python3` present | AppContainer and Job APIs (all editions); validation Python runtime present | — |

Ubuntu 24.04 restricts unprivileged user namespaces through AppArmor, and bubblewrap needs an
extra profile loaded by an administrator there
([summary of Ubuntu's restriction](https://discourse.ubuntu.com/t/understanding-apparmor-user-namespace-restriction/58007)),
so the namespace-based tools (bubblewrap, nsjail) are not the default route. Landlock is unprivileged; whether 24.04 ships it enabled must
be observed on the device. Reuse evaluation for Landlock: `landrun` (Go, MIT) against a roughly
100-line `ctypes` call of the documented system calls, made inside the sandboxed service just before
`exec`. Choose `landrun` unless it cannot express "deny all TCP" or adds an unacceptable binary.

macOS cannot meet the aggregate-memory requirement natively. Recommendation: macOS local validation
stays unavailable in Beta and keeps the existing "Not sandbox tested — local device mode" label. A
VM route through Apple's [`container`](https://github.com/apple/container) (macOS 26, Apple
Silicon, administrator install, OCI image provisioning, active development) is a later product
decision, not a silent substitute.

Interpreters: Ubuntu uses the system `python3`, which matches the project's own runtime. A frozen
PyInstaller application has no general `python` executable, so Windows needs a pinned validation
runtime (the python.org embeddable package) as an explicit pack. Scope: standard-library `unittest`
projects like the C07 fixture.

Acceptance: an escape and resource matrix on the **packaged** runner (TCP, UDP/DNS, reading
`~/.ssh`, writing outside the temporary folder, memory hog, fork bomb, CPU loop, wall timeout,
output flood) on the Ubuntu device. CI's `ubuntu-24.04` runner can exercise the kernel mechanisms
after enabling a lingering user manager, which is labelled CI evidence, not desktop acceptance.
Generating a policy or passing a timeout test is never qualification.

### O.7 R5 — observer contract and package preflights

**Observer v1 (sampled), reported per job window.** (1) A Python audit hook (`sys.addaudithook`)
in the coordinator records `socket.connect`, `socket.sendto` and `socket.getaddrinfo`. It is
complete for Python-level sockets in that process, but not for C code that bypasses the socket
module. (2) psutil snapshots of TCP and UDP sockets every 250 ms for the engine processes and for
sandbox processes listed from kernel-maintained membership (cgroup `cgroup.procs`, Job process
list), so descendants are not lost when a parent exits. (3) Processes not covered are listed with
the reason, for example macOS WebKit networking processes that are system XPC services rather than
Refinix children. The report names the method, interval, sample count, covered processes, partial
or denied coverage, observer errors and the time window. It uses wording such as "non-loopback
connections seen in samples" and "in-process connection attempts recorded", never "flows" or
"zero egress". Enforcement is reported only where it exists, for example "Code sandbox network:
enforced (seccomp address-family filter)". Otherwise it is "unavailable". A synthetic connection
opened and closed between samples must not be reported as observed-absent.

**Package preflights.** Windows: check WebView2 per
[Microsoft's guidance](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution)
in the installer and at start, with the pinned `edgechromium` backend (K19). If it is missing, explain
and offer Microsoft's installer as an explicit connected action. Linux: check `/dev/fuse` and
`fusermount3` (AppImage route), the WebKitGTK 4.1 typelib and libraries, and the Vulkan loader;
otherwise use the `.deb` route (O.4). All OSes: the engine's device listing is the backend
preflight, with a CPU build as the fallback where a CPU preset exists. "Terminal-free install" is
claimed only after the chosen package is observed on a clean system.

### O.8 Reconciled plan by section

Order is unchanged: each section is completed with its checks before the next.

**Section 1 — Foundation.** Database preflight and schema guard (O.5) → typed readiness → managed
engine boundary with explicit settings, fitting off, authenticated ownership proof and `--offline`
→ llama-server adapter → tier and preset record types (empty of unqualified tiers) and hardware
facts through psutil and the engine → hide mesh controls (K18) → pin the window backend (K19) →
macOS floor check and base-interpreter change (K17) → package exclusion of `check_` modules → P-1
stages A/B → registry entries only from accepted artifacts → **the shared build matrix and the
first internal test build set (O.11)**, so every later check runs on installed packages rather
than a checkout. Section 1 exits with labelled macOS, Windows and Ubuntu test artifacts from one
source snapshot, or with the single missing build environment named (O.11, O.9 item 6).

**Section 2 — Standalone workflows.** Presets and catalogue manifests → urllib3 downloader, exact-
match offline import (including verified import from an existing local Ollama blob if P-1 shows
llama-server serves it), safe removal → onboarding and Settings → Models by category with evidence
labels → local Auto (P.5 item 5, unchanged) → profile-derived budgets, with exact tokenization if
verified → instructions and curated memory → scan-reading qualification → second model (decision D1).

**Section 3 — Local safety.** Typed engine failures and admission → Ubuntu sandbox backend (Windows
second if time allows, otherwise disclosed) → observer v1 and Proof Card binding → stabilisation pass.

**Section 4 — Packages and updates.** Finalise the installers on the build matrix from Section 1
(macOS bundle on a documented base interpreter, Windows Inno Setup per-user installer, Ubuntu
package chosen by observation) with preflights and floor checks → TUF verification, journal,
previous-app helper, recovery → Settings → Updates and Recovery → release tooling with offline keys
→ the labelled N, N+1 and engine-changing build sets for updater and recovery testing (O.11).
Signing, notarisation and publication stay separate user-authorised steps.

Rebuild cadence across all four sections: a new labelled build set only when packaged code,
dependencies, configuration or resources change, or a defect fix requires it, normally once per
completed section plus fixes. Testers reuse one artifact for installation, workflow, restart and
failure checks.

### O.9 Revised prerequisite batch

The preset/reuse direction and the scoped doc corrections are already authorized and are not re-asked.

Permissions (none covers Git writes, signing or publication):

1. **Offline checks** — the P.7 families with `desktop/.venv` and Node 26.7, plus new offline tests.
2. **P-1 on this Mac** — one pinned llama.cpp macOS arm64 release asset; upstream Qwen3.5-4B weights
   and projector (about 3.4 GB) after a licence and provenance check; a temporary private Ollama
   store for same-bytes comparison; loopback-only inference. Nothing in the repository; the user's
   Ollama store untouched.
3. **llmfit for preset estimates** — one pinned release, run on this Mac with hypothetical profiles;
   no `bench` or `--share`.
4. **Dependencies** — hash-pinned install into `desktop/.venv` of psutil, python-tuf, securesystemslib
   and urllib3; release-side `securesystemslib[crypto]` only in a separate tooling environment.
5. **Local Mac package build** — a py2app build for checks, using a base interpreter with a
   documented deployment target (python.org universal2 build on this Mac, or CI's macOS runner if
   you prefer not to install it locally); unsigned.
6. **Windows and Ubuntu build environments — the one genuine blocker for those packages.** The
   owner can only reach this Mac, and PyInstaller does not cross-build. One of:
   (a) **recommended:** the user commits and pushes the branch containing the prepared
   `package.yml` workflow and dispatches it, or authorises the owner to do so. This uses
   GitHub-hosted `windows` and `ubuntu-24.04` runners plus a macOS runner; it needs Actions enabled
   and minutes available, and stores internal artifacts that team members download while signed in;
   (b) a team or volunteer Windows 11 x64 host and an Ubuntu 24.04 x86_64 host each run one build
   command on the shared source snapshot and return the outputs.
   Without (a) or (b), the owner delivers the complete, offline-tested build path and the macOS
   artifact and reports Windows/Ubuntu packages as blocked on this item only.
   No signing secrets are needed for internal builds; test update keys stay on the user's machine.

Human facts and decisions:

- **D1 — second Beta model.** Recommendation: a Qwen3.5 small-series sibling under the same licence
  family, with existence, licence and files confirmed at acquisition, for Faster and low-memory tiers;
  4B stays default for Code, Documents and scan reading. Gemma 3 4B QAT is gated and uses custom terms,
  which conflicts with no-account installation. Trade-off: about 1-2 GB optional download and
  extra qualification.
- **D2 — Beta sandbox scope.** Recommendation: Ubuntu as the first qualified local validation
  profile, Windows Job/AppContainer second if time allows, macOS unavailable in Beta. Trade-off: the
  developer Mac cannot qualify the sandbox itself; a representative Ubuntu device or volunteer must.
- **D3 — representative observations.** Not ownership: which Windows 11 and Ubuntu 24.04 machines
  (volunteer or team) will **install the prepared test packages** and run setup, workflow, restart,
  failure, sandbox and two-build update checks, and whether CI may run kernel-mechanism tests. No
  tester needs a checkout, Python or a compiler.
- **D4 — signing (publication only).** Will an Apple Developer Program membership and a Windows
  code-signing certificate be available? Without them, publication gates cannot pass. This does not
  block implementation.

### O.10 Reconciled user-facing change summary

| Area | Change for the user | Main paths | Evidence still needed |
|---|---|---|---|
| Engine | Installed Refinix runs its own verified engine on a private loopback port; system Ollama updates no longer affect it | engine.py, runtime.py, lifecycle.py | P-1 parity; each OS backend |
| Setup | Graphical setup recommends models per category from reviewed presets for this hardware, shows sizes, sources and evidence labels, and downloads or imports with progress and cancel | profiles.py, models.py, device.py, frontend | Presets need Refinix evidence before release |
| Readiness | The specific problem and its fix instead of "unavailable for new work" | readiness module, server.py, app.js | Offline tests |
| Data safety | An older Refinix refuses newer data without changing it; failed updates restore both the application and compatible data, and keep the newer data set aside | db.py, updates.py, apply helper | Fault-injection tests; device two-build runs |
| Updates | Settings → Updates and Recovery: explicit Check, Download, Install and restart, Import update, Restore previous version | updates.py, frontend, scripts/release | Signing accounts; per-OS runs |
| Code | Sandboxed validation where qualified (Ubuntu first); elsewhere the existing honest label | sandbox.py, code_service.py | Ubuntu escape matrix |
| Proof | Network observations report method, coverage and gaps; no zero-egress claims | proof.py | Observer tests; device windows |
| Beta scope | Pairing and paired-worker controls hidden or marked Planned | control.html, app.js | UI tests |
| Packages | macOS minimum OS stated truthfully; Windows/Ubuntu packages check WebView2, FUSE and WebKit before claiming readiness | desktop/, packaging_plan.py, CI | Clean-system observations |
| Internal test packages | Testers download a labelled, unsigned macOS, Windows or Ubuntu package with its SHA-256 and short instructions, install it and test directly; one artifact serves many checks | desktop/build.py, packaging_plan.py, locks, engine manifest, `.github/workflows/package.yml` | Windows/Ubuntu need O.9 item 6; artifacts are test evidence only, not signed releases |
| Cleanup | Confirmed dead functions, duplicate status work and replaced build/runtime paths removed after caller, package, test and stored-data checks; deferred mesh kept | db.py, runtime.py, repo.py, server.py, desktop/ | Offline tests before and after |

Unknowns that remain until observed: llama-server's handling of Qwen3.5 (template, reasoning switch,
schema grammar, projector) and cancellation on disconnect; Vulkan performance; Landlock and
delegation on the actual Ubuntu desktop; FUSE and WebKitGTK defaults on Ubuntu 24.04; the engine
binary's macOS floor; the Apple hardened-runtime entitlements the engine needs.

<a id="o11-internal-test-packages"></a>
### O.11 Internal test packages for macOS, Windows and Ubuntu (user requirement, 2026-10-04)

**Deliverable.** Complete installable packages for all three OS families, not only build scripts.
Each **build set** comes from one reviewed source snapshot and one application version, with
pinned dependencies and the managed engine and native resources included. Model weights are never
inside a package; they remain explicit setup downloads or offline-import bundles.

| OS profile | Artifact (example name) | Built natively on | Contents |
|---|---|---|---|
| macOS arm64 | `Refinix-0.1.0-internal.N-macos-arm64.zip` (ad-hoc-signed `.app`) | macOS arm64 with a python.org universal2 Python 3.12 base (K17) | Existing py2app bundle, Metal engine build, frontend, engine manifest, presets, internal test update root |
| Windows 11 x64 | `Refinix-0.1.0-internal.N-windows-x64-setup.exe` (unsigned, per-user, no administrator) | Windows x64 host or runner | PyInstaller onedir app, Vulkan and CPU engine builds, WebView2 check (O.7) |
| Ubuntu 24.04 x86_64 | `Refinix-0.1.0-internal.N-linux-x86_64.AppImage` and/or `refinix_0.1.0~internal.N_amd64.deb` (one kept once O.4 is observed) | Ubuntu 24.04 host or runner | PyInstaller onedir app, Vulkan and CPU engine builds, desktop entry and icons, FUSE/WebKit checks |

Every artifact ships with `<artifact>.sha256`, a `build-manifest.json` and a short `TESTING.md`.
The manifest records: artifact name, SHA-256 and size; OS, architecture and the computed minimum
OS (macOS `minos`, glibc floor, Windows version); version and build-set ID; the source snapshot
digest (and the Git commit when the tree is clean); the input digest; the base interpreter (version,
origin, deployment target); packaging tools and versions; every dependency with its lock hash; the
engine identity (release, backend, file hashes); native prerequisites; verified exclusions;
the internal update trust root ID; channel `internal`; signing state `unsigned`; build host or
runner image; and build time. The app shows "Internal test build — unsigned" in Settings.

**One build path, reusing what exists.** `desktop/packaging_plan.py` stays the single inventory: it
gains engine resources, manifest generation, the source and input digests and post-build
verification of the shipped tree for PyInstaller layouts as well as py2app. A new
`desktop/build.py` is the only driver for all three lanes: stage sources with the existing
`stage_application_sources` → install locked dependencies into an isolated environment → fetch and
verify pinned engine assets → run the platform tool (the existing `setup_py2app.py`, one shared
PyInstaller spec, Inno Setup or AppImage/`.deb` assembly) → verify contents, exclusions and OS floors
→ write the manifest, checksum and `TESTING.md`. Windows and Linux locks follow the existing
multi-platform hash pattern in `backend/requirements-render.lock`. `.github/workflows/package.yml`
is one manually dispatched matrix (macOS arm64, Windows x64, Ubuntu 24.04 x86_64) with read-only
permissions and no secrets. It runs the same `build.py` and adds a `build-set.json` listing the
three artifacts. It is prepared in the repository but not pushed or triggered without the user.
No new application or packaging framework is introduced, and `lifecycle`, `shell` and the frontend
are unchanged by packaging.

**Same source everywhere.** The snapshot digest is computed over the staged application sources,
frontend, locks, engine manifest and build configuration. CI computes it from the checked-out
commit; a native host builds from a `source-snapshot.tar` exported from the reviewed tree. A build
whose computed digest differs from the requested snapshot fails.

**Caching without stale packages.** Caches hold only verified inputs: pip wheels keyed by OS,
architecture, Python version and the lockfile hashes, and engine assets keyed by OS, architecture and
the engine-manifest hash. Hashes are re-checked on restore (`--require-hashes`, SHA-256). Built
packages are never cached or restored. After a build, the driver reads the manifest embedded in the
package and requires its source and input digests to equal the job's; artifact names carry the
version and an input-digest prefix.

**Rebuild only when inputs change.** `build.py` computes the input digest first. If it matches the
last recorded build set, it reports "inputs unchanged, reuse <set>" and does not label a new build,
unless an explicit rebuild reason is given (for example, a reproducibility check). The build-set
record in the repository lists hashes and identities only, never binaries. Tester observations cite
the artifact SHA-256, so evidence attaches to exact bytes.

**Updater and recovery builds.** Keep at least N and N+1, plus one build set whose engine manifest
changes, as immutable labelled internal builds. Offline update bundles for them are assembled and
signed with internal test TUF keys on the user's machine from the downloaded artifacts, so no keys
reach CI. Internal builds trust only the internal root and release builds only the release root, so
an internal artifact can never be offered as a Beta update. A connected-check test host is chosen in
Section 4.

**`TESTING.md` (short).** What the build is (internal, unsigned, not for distribution); its SHA-256;
install steps per OS: macOS "Open Anyway" in Privacy & Security for an unsigned app, Windows
SmartScreen "More info → Run anyway", Ubuntu "Allow executing" for the AppImage or App Center for
the `.deb`; known prerequisites (WebView2, GPU driver or CPU fallback, FUSE/WebKitGTK, free disk for
the model); where models come from (in-app download or the internal import bundle); what to record
(artifact SHA-256, OS build, hardware, steps, result, the data-folder log); uninstall and
data-preservation notes; known limitations (for example, Code sandbox only on Ubuntu).

**Acceptance.** Offline: driver tests for inventory, manifest fields, digest stability and
change detection, cache-key composition, refusal to relabel unchanged inputs, embedded-manifest
verification, exclusions across py2app and PyInstaller layouts, and the OS-floor check, which must
fail on today's `desktop/dist/Refinix.app` (K17). Build lanes: each lane produces its artifact and
manifest with the same snapshot digest. Testers: install without a checkout, Python or compiler,
complete setup and reuse the same artifact for workflow, restart and failure checks. These are
internal test artifacts; signing, notarisation, publication and real-device acceptance remain
separate gates.

<a id="o12-cleanup-rule"></a>
### O.12 Strengthened cleanup rule and confirmed candidates

Rule for every section: inspect and adapt existing code first; reuse suitable established offline
tools; add new code only for a demonstrated missing capability or integration gap. Remove confirmed
dead code, duplicate paths and obsolete replaced code only after checking callers, package inclusion
(`packaging_plan` module list), tests and stored-data compatibility. Preserve useful features, user
data, security boundaries and the deferred distributed implementation. Optimise reliability,
performance and maintainability, not repository size.

Evidence below comes from a read-only reference scan of every non-test top-level function and class
in `backend/coordinator`, `backend/contracts` and `desktop`, against all `.py`, `.js`, `.cjs` and
`.html` files, plus `grep`:

| Candidate | Evidence | Action |
|---|---|---|
| `db.clear_attachments`, `db.sources_for_message`, `db.ArtifactRejected`, `repo.is_excluded_directory` | No reference anywhere, including tests. `is_excluded_directory` duplicates inline `EXCLUDED_DIRECTORIES` checks ([repo.py:274, 559, 612](../backend/coordinator/repo.py)) and has a redundant condition | Remove in Section 1. None touches the schema or stored data |
| `runtime.installed_models` | No reference; duplicates the digests already returned by `probe()` | Remove during the runtime split |
| Duplicate status work | Each `/v1/status` poll computes `documents.capability_summary`, `ocr_profile` and `fts_available` twice ([server.py:2525-2528 and 2738-2742](../backend/coordinator/server.py)); `server.py:1482` also re-probes the runtime | Compute once per request and pass it through |
| Replaced paths | `setup-macos.command` hard-codes Homebrew Python (K17); terminal-command actions (K4); stale status fields (K7); deprecated `keychain_available` | Replace with `build.py` and graphical actions, then remove after the replacement is verified; developer-engine commands stay labelled |
| Test-only helpers | `paths.portable_root/database_in/holds_state`, `documents.supported_suffixes/redact`, `db.operation_for_approval`, `v1.payload_sha256` | Keep. `portable_root` serves the planned portable profile, which is a wiring gap to record, not dead code. Others are removed only if a replacement covers the tested behaviour |
| Deferred mesh | `db.list_relationships` (unused today), worker runtime near-copy, pairing, dispatch, `scripts/refinix` | Keep, hidden from Beta UI (K18) |

<a id="approved-execution-addendum-20261004"></a>
## Approved execution addendum — 2026-10-04

The user approved the explained direction and asked for a handoff to the implementation owner.
Use this addendum with O.1–O.12. It replaces conflicting details in O.5, O.6 and O.11 and the
older planning-only prompts. It incorporates the owner's reply-only recovery/sandbox/manifest
proposal with the final review corrections. These are implementation constraints inside the same
four sections, not additional work packages or agent assignments.

### Four sections and execution rule

| Existing section | Complete outcome |
|---|---|
| 1 — Foundation | Durable data/ownership guard; truthful readiness; managed pinned runtime candidate and caller integration; reviewed hardware/preset records; native UI and minimum-OS fixes; shared native build path and first three-OS internal artifacts when build permissions/environments are available |
| 2 — Standalone workflows | Graphical model download/import/removal; optional capability choices; compatible local routing/fallback; real context/output/resource budgets; preserved Chat/Documents/Code, instructions, memory and retrieval; qualified scan reading and second-model evidence where authorized |
| 3 — Local safety | Failure recovery and resource admission; sandbox enforcement below; honest observer/Proof Card coverage; coherent stabilization across the existing callers and fixtures |
| 4 — Packages and updates | Final native macOS/Windows/Ubuntu packages; TUF/platform verification as applicable to the channel; update/recovery helper; immutable N, N+1 and engine-change artifacts; package/device/update evidence before publication |

Use existing implementation and established offline tools first. Remove the O.12 candidates only
after rechecking callers, tests, packaging, stored-data compatibility and intended retained use.
Keep the deferred distributed code and trust boundaries; hide unfinished mesh controls in Beta.
Retain the current frontend, shell and orchestration harness. LangGraph is unadopted. Do not add a
custom fit optimizer, SQLite parser, download framework or sandbox framework for this work.

An owner handles its section and integration directly; no subagents, nested delegation, per-file
tasks or fresh session planning documents. Proceed in sustained coherent batches. A routine helper,
refactor or necessary caller change is an implementation choice, not a new user checkpoint.

### Data ownership and schema admission — replaces the O.5 preflight

The lock must identify the **actual canonical data root/database** selected by the entry point,
including an explicit `--state`. The current default `desktop.lock` does not follow that argument
([desktop/__main__.py:59](../desktop/__main__.py),
[lifecycle.py:192](../desktop/lifecycle.py)); record this as K24. Desktop, packaged and headless
coordinator entry points must participate in the same ownership rule. Keep ownership for the
writer's lifetime, not only while `connect()` returns. Recovery must exclude a concurrent startup.

Before any original-file SQLite open, chmod, journal change or DDL, establish exclusive ownership.
For an existing store, take a coherent private temporary copy of the main database and relevant
recovery journal state while writers are quiesced. Inspect only the copy with SQLite. WAL inspection
copies the WAL, not the SHM; SQLite may build its own SHM in the temporary directory. Handle an
unexpected hot rollback journal conservatively; do not silently inspect incomplete copied state.
Insufficient space, an ambiguous store, an active writer or an unreadable/corrupt copy blocks
admission with a clear reason and leaves the canonical files unchanged.

Verify required Refinix metadata and a valid schema version. Refuse non-Refinix stores and newer
schemas. A missing database is a new store; a zero-length existing file is treated as new only if
there is no conflicting journal/recovery state. Only after admission may the existing connect and
migration path write. Never lower a stored version. Updating `user_version` transactionally is
permitted as a consistency aid, but is not ownership proof. The Beta does **not** use the proposed
header-only acceptance shortcut: SQLite magic and `user_version` cannot establish application
identity or the presence of `meta`. Optimise this only after measured startup cost warrants it and
equivalent ownership/schema checks are demonstrated. Do not use `immutable=1` on a live database.

Acceptance when offline checks are authorized: foreign SQLite with nonzero `user_version`, newer
schema with/without a non-empty WAL, missing/corrupt metadata, ambiguous journals, low disk and two
launches on the same explicit state path. Refusal preserves existence, size, mtime and SHA-256 of
canonical main/WAL/SHM/journal files; it must not create SHM. Different legitimate roots stay isolated.
Reuse SQLite and the existing paths/locking boundaries rather than parsing SQLite tables yourself.
See [SQLite file identity](https://sqlite.org/fileformat.html#application_id) and
[read-only WAL behaviour](https://sqlite.org/wal.html#read_only_databases).

### Exclusive update and rollback recovery — supplements O.5

The previous known-good app acts as helper for automatic recovery and user-requested rollback.
Record owned-process identities (PID, start time and executable), update intent and each planned
move in the durable journal. Request graceful shutdown, then escalate only against proven owned
processes. Stop whole sandbox cgroups/Windows Jobs and reap all owned writers/children. Verify exit,
then acquire and hold the workspace/update ownership through every data move and restore. An update
intent/recovery state prevents a new ordinary launch from writing in the handoff interval.
If exit or exclusivity cannot be established, record `recovery_blocked` and change no canonical data.
Never signal a recycled PID or an unrelated listener/process.

Under that ownership, preserve the attempted version's complete state in a same-volume set-aside
directory. Journal main/WAL/SHM and instruction/config moves individually, with hashes and durable
progress. Restore verified snapshot files by same-directory temporary files and atomic replacement,
using qualified platform-specific durability primitives. Refuse a restore if an unexpected canonical
WAL/SHM remains. Resume each interrupted move by location and hash; preserve newer artifacts,
attachments and model files; retain stable credential identifiers. Switch to the compatible previous
app/data pair before reopening. Do not claim that SQLite atomicity alone makes all migration and
filesystem interruption paths safe.

Acceptance: hung live writer; survivor causing byte-preserving `recovery_blocked`; reused PID;
concurrent launch; interruption after every sidecar/config move and restore; stale WAL; reopening
the old snapshot and recovering the set-aside state in the newer version. Perform those checks on
labelled packaged N/N+1 builds as well as authorized offline fixtures.
See [SQLite warnings about renaming an open database](https://sqlite.org/howtocorrupt.html#unlinking_or_renaming_a_database_file_while_in_use).

### Sandbox controls — replaces conflicting O.6 Ubuntu details

Ubuntu remains the proposed first Code-validation profile, not a qualified result. Reuse the
systemd user **service**, Landlock and cgroup controls already evaluated. Before untrusted code
starts, require effective seccomp, native syscall architecture, enabled Landlock, a working user
manager and delegated memory/pids/cpu controls. Network and host IPC are denied with
`RestrictAddressFamilies=none` and `SystemCallArchitectures=native`.
Explicitly deny `io_uring_setup`, `io_uring_enter` and `io_uring_register`: kernel io_uring socket
operations bypass the ordinary `socket()` filter. Include that route in acceptance, not just
Python sockets. Do not rely on Landlock ABI 4 for host Unix-socket isolation.

Close unexpected inherited descriptors before exec, including sockets; supply only stdin from
`/dev/null` and bounded stdout/stderr. Replace the inherited user-manager environment with a minimal
allowlist. Restrict namespaces, privilege changes and tracing/process-memory access with the
established seccomp controls. Deny host signalling on ABI < 6; where supported, apply Landlock
signal/abstract-socket scope as an additional layer. Grant read/execute only to the necessary
interpreter/library/input paths and write only to the temporary workspace. Do not allow host bus,
agent or runtime-directory access. A canary must actually test denial, not treat an unreadable
`/proc` listing as proof that inherited descriptors were closed.

Keep aggregate memory/swap, process count, CPU, wall time, per-file size, FD and output controls.
Add a **total temporary-workspace byte and file/inode bound** using an established quota or
size-bounded isolated filesystem mechanism. `LimitFSIZE` limits one file, and `LimitNOFILE` limits
simultaneously open descriptors; neither limits aggregate disk/inode consumption. Name and verify
the mechanism and any graphical OS prerequisite before offering validation. A periodic directory
size poll is not a hard aggregate limit. If the profile cannot enforce the required storage bound,
validation stays unavailable and the unresolved qualification gate is reported; do not weaken the
security contract or silently install privileged helpers. Proposal/review and the existing clearly
labelled local Apply/Undo path remain available under their current approval policy.

Acceptance on the packaged runner: ordinary and io_uring sockets; user/system bus and control;
inherited descriptors; alternate ABIs; host signals/process access; home/outside-path reads/writes;
aggregate memory, processes, CPU and time; output flood; many sequential files below the per-file
limit; inode exhaustion; and descendant cleanup. Keep process/resource canaries and measured kernel
enforcement distinct. Windows remains a second candidate (LPAC/AppContainer plus Jobs and denial
of host broker named-pipe/RPC access); native macOS sandbox validation remains unavailable under
the present constraints. CI mechanism evidence does not replace desktop/package qualification.

Primary evidence: [systemd v255 directives](https://raw.githubusercontent.com/systemd/systemd/v255/man/systemd.exec.xml),
[v255 syscall groups](https://raw.githubusercontent.com/systemd/systemd/v255/src/shared/seccomp-util.c),
[Linux 6.8 io_uring sockets](https://raw.githubusercontent.com/torvalds/linux/v6.8/io_uring/net.c),
[Linux 6.8 per-file size enforcement](https://raw.githubusercontent.com/torvalds/linux/v6.8/fs/read_write.c),
and [Landlock ABI coverage](https://docs.kernel.org/userspace-api/landlock.html).

### Package identities and reuse — replaces conflicting O.11 manifest details

Embed `refinix-build.json` with version/build-set/channel, source and input digests and their
components, engine identity, lock hashes and trust-root identity. It excludes the enclosing
package's own SHA-256. After packaging, write `<artifact>.manifest.json` and `<artifact>.sha256`
with final name/size/hash, embedded identity and its hash. Extract the identity from the finished
artifact and compare it with the requested build. Never relabel old bytes as a new verified build.

The input identity includes staged sources/frontend, assets/locks/configuration, engine files,
build scripts, interpreter origin/version/hash/deployment target, packaging tools, SDK/toolchain,
runner image/host OS and applicable glibc floor. Reuse requires the actual retained artifact to exist
and its freshly read SHA-256 to match the record. Missing or mismatched bytes require a rebuild with
that reason. Re-verify cached inputs; never treat an unchecked restored binary as evidence.

Deliver complete macOS, Windows and Ubuntu installable artifacts from the same reviewed snapshot,
with the app, pinned dependencies and managed engine. Models remain explicit verified setup assets.
Reuse each immutable artifact across install/workflow/restart/failure observations. Keep N/N+1 and
an engine-change set for updater tests. Internal trust roots and locally held test keys stay separate
from production roots, signing and publication. O.11's native build environments remain necessary;
prepare the shared driver/workflow without triggering CI or performing Git writes absent permission.

### Required permissions and owner response

The settled direction is approved. Check existing session permissions, then request **one compact
batch** for only the genuinely unanswered O.9 actions: offline check families, pinned downloads and
isolated installs, live loopback parity, local packages and native CI/device checks. Do not describe
Windows/Ubuntu as the only possible blocker while the Mac build/download/check permissions are also
unanswered. Recommend native CI for Windows/Ubuntu; a source workflow is not a produced package.
Keep current-message Git/GitHub write authorization, signing and publication separate. Request
protected-authority edits by exact file and scope; this handoff does not grant blanket doc permission.

Continue authorized source preparation/implementation that does not depend on an unanswered action.
Do not ship unqualified presets, advertise a working sandbox, or claim package completion while
the corresponding checks are blocked. Missing representative observations can follow package
production; the user need not own every laptop. Routine technical decisions remain owner-owned.

Return a concise acknowledgement of this exact approved scope and the single genuine prerequisite
batch. Then proceed within permission through the four sections, updating factual ledger entries
and reporting observed results/remaining gates. No further speculative planning round is requested.

## Prompt to deliver to the implementation owner

The user has approved the explained four-section direction and requested this corrected handoff.
Read `/Users/adityatadge/Documents/GitHub/AegisForge/docs/beta-execution-handoff.md`, especially
"Approved execution addendum — 2026-10-04", and the current authorities. Preserve the dirty tree.

Use O.1–O.12 with the approved addendum overriding the older database header/read-only preflight,
recovery, AF_UNIX sandbox and self-referential package-manifest details. Keep the same four sections,
existing harness and merged capabilities; reuse established offline tools and remove only proven
unwanted code. Research-backed preset matching remains the setup approach. Deliver reusable native
macOS/Windows/Ubuntu packages when the build environments and required actions are authorized.

The original concerns are now concrete requirements, not invitations to create another plan:
actual-root lifetime ownership; SQLite validation on a locked coherent copy; exclusive recovery
after every writer exits; io_uring/host IPC denial and a hard aggregate temporary-storage bound;
separate embedded build identity and externally hashed final artifacts. Check the addendum's
acceptance cases during authorized verification. Keep Code execution unavailable where controls
cannot be enforced; this does not block the unaffected standalone foundation/workflow work.

Acknowledge the exact scope, inspect current source/callers and the relevant doc changes, then ask
one compact batch for genuinely missing O.9 permissions/human facts. The user approved the direction;
do not ask again about it or routine implementation choices. Continue authorized source work while
awaiting independent action permissions. Do not infer tests, downloads/installs, live calls,
build/host changes, Git/Actions writes, other protected-doc edits or publication from handoff approval.
No subagents, additional task tiers or per-session planning documents. After real prerequisites are
met, execute the largest coherent safe scope in a sustained run and report evidence by section.

## Prompt to deliver to the review agent

Historical prompt, preserved with the earlier proposal. The approved addendum and current owner
prompt supersede it; do not start another planning cycle merely because this old prompt remains.

Re-review `/Users/adityatadge/Documents/GitHub/AegisForge/docs/beta-execution-handoff.md`, section
"Owner reconciliation — R1–R5 and deeper source findings (2026-10-04)", against your NEEDS FIX
assessment, the current authorities and source at HEAD `8c6d7a9` with the recorded dirty tree.
Verify each new finding K17–K23 directly, including the `otool` minimum-OS observations and cited
lines. Also review O.11 (internal test packages: one build matrix, same snapshot, manifests, cache
and rebuild rules, updater build sets) and O.12 (cleanup evidence). Challenge the reuse decisions in O.4, particularly declining `huggingface_hub` and Sparkle
for Beta; the journal and recovery order in O.5; the per-OS enforcement table and the macOS
conclusion in O.6; and the observer contract in O.7. Read-only: do not edit application files,
run tests, download, install or perform Git writes.

Start with PASS, NEEDS FIX or BLOCKED. For each remaining disagreement give evidence and the change
you recommend. Record the re-review under "Review record" without rewriting either earlier section.
Joint PASS still means the plan is justified, not that any app, package, sandbox or update has passed.
