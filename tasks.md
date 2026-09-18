# Refinix implementation plan

Updated: 2026-09-18. The production architecture remains the destination. The
first release frontier is **Refinix Beta 0.1 / SIH Reviewer Preview**, followed
by Beta 0.2/0.3, a finals candidate and production qualification. The [PRD](docs/prd.md#7-release-scope)
owns scope; this file owns executable sequencing, dependencies and the cut-line.

The [2026-09-16 source audit](docs/evaluation.md#beta-source-audit) is the starting
point, not historical completion labels. No public support profile is
yet qualified. **Beta 0.1 must support Windows, macOS and Linux**, on exact
profiles selected in P01 under the [PRD](docs/prd.md#release-bands). The existing
Mac demo is a regression baseline, not the release boundary. P01–P06 apply to
all three OS families; portability is not postponed to P18. The retained
Linux/Kubernetes validator is a sandbox candidate, not proof of desktop support.
No task assigns permanent OS roles or authorises host setup.

## Operating contract

- Preserve the current UI, harness, functioning adapters and security boundaries.
  Reuse implemented paths and tests; qualify replacements before retiring them.
- The bands describe release dependencies, not permission to execute. Downloads,
  host changes, live checks and Git/publication retain [AGENTS.md](AGENTS.md)'s rules.
- State the existing path, outcome, smallest change and checks before each task.
  Independent preparation may overlap; acceptance requires the integrated result.
- Describe checkpoints by actual OS, architecture, role, shell and directory;
  supply exact steps, prerequisites, evidence and rollback when applicable. There
  are no permanent device owners, implementers or calendar commitments.
- Preserve dirty worktrees and user data. Historical handoffs supply evidence and
  reproduction context, not current commands or permission.
- Report implemented, observed, unresolved and next action separately. Requester
  acceptance is the final gate; source inspection is not runtime verification.

## Agent execution guide

Start here for an authorised implementation task. Read [AGENTS.md](AGENTS.md),
the PRD scope and only the focused authority/source paths needed for that task.
The [source audit](docs/evaluation.md#beta-source-audit) is a dated starting point;
reinspect changed callers and tests before deciding that a feature is absent or
complete. Do not read the whole archive or resume an old C-task by default.

1. Identify the requested P-task, its band, hard predecessors and acceptance row.
   Inspect `git status --short --branch`; preserve unrelated edits. A dependency
   with no accepted evidence is still open, even when its source exists.
2. Trace the existing UI/API → coordinator → runtime/worker → storage/validator
   path and affected callers. Use the table below to find the initial files;
   expand only where the real dependency requires it.
3. State the smallest change, preserved behaviour, relevant failure cases and
   allowed checks. Use existing fixtures/dependencies; no speculative framework,
   model download or host setup. Resolve routine choices from current evidence.
4. Build and review inside the authorised scope. Record what actually ran in
   `docs/evaluation.md`; put model qualification in `docs/model-catalog.md` and
   published-profile/update evidence in `docs/releases.md`. Link the evidence
   from this task's status instead of copying it into another handoff document.
5. Stop at a missing permission, essential input or device/requester checkpoint.
   Return the concrete handoff fields below. Never mark a task accepted from
   mocked checks, another agent's report or an unverified device “done”.

### Source and verification map

Paths below are starting points, not permission to run every suite. Inspect test
setup before execution: native renderer/model checks, sockets, containers and
live-device tools have different prerequisites. Missing dependencies are reported,
not installed to manufacture a pass.

| Tasks | Implementation starting point | Existing checks / evidence owner |
|---|---|---|
| P01–P03, P13 | `desktop/lifecycle.py`, `shell.py`, `setup_py2app.py`; `coordinator/runtime.py`; `.github/workflows/ci.yml` | `desktop/test_lifecycle.py`, `test_packaging.py`, `test_review_fixes.py`; [baseline](docs/evaluation.md#p01-baseline), [releases](docs/releases.md) |
| P04–P05, P17 | `coordinator/server.py` model inventory/select, `runtime.py`, `db.py`; `frontend/app/app.js` model controls | `coordinator/test_execution4c.py`, `test_reasoning.py`; [model lifecycle/qualification](docs/model-catalog.md#persistent-model-management) |
| P06, P16 | `coordinator/context.py`, `docflow.py`, `documents.py`, `ocr.py`, `retrieval.py`, artifact writers and `code_service.py`; current frontend | `test_context.py`, `test_documents.py`, `test_ocr.py`, `test_execution4a.py`, `test_reliability.py`, `test_code_access.py`; frontend composer/rendering/conversation checks; [workflow acceptance](docs/evaluation.md#beta-acceptance) |
| P07–P09, P18 | `worker/app.py`, `pairing.py`, `packages.py`, `validate.py`, `jobspec.py`; coordinator pairing; `deploy/k3s/` | Worker API/package/validation suites, deployment/guard checks, desktop packaging; [worker operations](docs/worker-operations.md), [security](docs/security.md) |
| P10–P12, P15, P20 | Coordinator/worker `dispatch.py`, worker `executor.py`, coordinator `server.py`, `code_service.py`, `proof.py`, status UI and shared contracts | `test_dispatch.py`, `test_remote_code.py`, `test_c10.py`, worker `test_executor.py`, frontend control/proof tests; [Beta](docs/evaluation.md#beta-acceptance) and [production evidence](docs/evaluation.md#production-acceptance) |
| P14, P19, P22–P23, P26 | Exact candidate package/source manifest, runtime fixtures, release metadata and platform/profile evidence | [Publication](docs/releases.md#beta-01-publication), [update acceptance](docs/releases.md#update-acceptance), per-profile clean-device checks; source CI alone is insufficient |
| P21, P24–P25 | Existing shared `backend/contracts/v1.py`, pairing/policy/context boundaries; qualified component extension only after task prerequisites | [Managed architecture](docs/architecture.md#private-server), [security checks](docs/security.md#14-threat-driven-checks), [optional adaptation](docs/model-catalog.md#11-personalisation-and-optional-model-adaptation) |

`coordinator/` and `worker/` in this table are under `backend/`; test filenames
without a prefix belong beside their implementation. Do not create speculative
test suites for later tasks before an implementation exists.

### Checkpoint and completion record

Return in the task conversation: **P-task/status; build/commit and dirty paths;
device role, OS/architecture, shell and actual directory; exact authorised
commands/UI steps; prerequisites and rollback; expected result; observed result
and safe evidence location; unresolved gate; next eligible action.** If an artifact,
version or host value is missing, request it before issuing setup commands.

Task states are planned → in progress → review → verified, or blocked with a
specific prerequisite. “Verified” records the accepted scope, environment and
requester sign-off, not universal support. Keep dated results in their authority
and append the request/change ledger entries. Update affected caller links and
checks whenever a file moves; do not leave stale helper text or skipped safety
coverage. Do not create a new C-style build brief for each agent/session.

### Deferred public presentation work

Root README, website content and the SIH PPT will receive a separate editorial
pass when authorised. Aim for clear positioning, polished demonstrations and a
credible full-product vision; [PRD claim labels](docs/prd.md#release-bands) and
accepted evidence control statements about downloadable functionality. This work
can proceed alongside implementation later, but does not close a technical gate.

## Numbered execution tasks

P01 remains **in progress**. P02–P26 are **planned outcomes**, including reuse and
qualification of existing code; they do not mean every component is absent.
The unstarted 2026-09-14 P02–P08 gates are superseded by this decomposition, with
mapping below. Historical C/E/AF/F IDs and recorded results are retained in the
[prototype archive](docs/archive/prototype-task-record.md).

Every row states its hard predecessors. Within an authorised scope, preparation
can overlap as described below. The acceptance owner is the focused canonical
document linked in the row; tasks do not define competing product contracts.

### Band A — Beta release critical path

All fourteen outcomes are **Beta blockers**. Acceptance is limited to the exact
published profiles. An unqualified capability is unavailable with an explanation;
a release label cannot excuse failure of an exposed functional path.

| Task / classification | Existing base → required outcome | Hard dependencies and exit evidence |
|---|---|---|
| P01 — Beta baseline and support contract — Beta blocker, in progress | Reuse recorded fixtures/checks; accept current gaps and select a narrow desktop, peer and sandbox matrix | No predecessor. Refresh the selected devices/builds, fix representative acceptance thresholds before judging results, and obtain requester agreement to the matrix. Select a desktop profile in every OS family; record unavailable implementation as gaps owned by P02–P13. P01 does not require those future implementations to pass. P18/P22 expand versions/hardware/backends. See [baseline](docs/evaluation.md#p01-baseline) |
| P02 — Package and isolation feasibility — Beta blocker | Inspect `desktop/lifecycle.py`, `setup_py2app.py`, native document dependencies and retained validator; choose supportable installation and native-dependency routes for all three OS families | P01. Prove that app/runtime/model provisioning and the selected sandbox route can be delivered without developer terminal setup. Identify signing, licences, host permissions, storage and offline assets. Stop if no safe path; no forced engine or shell rewrite. [Release profile](docs/releases.md#beta-01-publication) |
| P03 — App-managed local runtime — Beta blocker | Existing Ollama lifecycle/adapter → dependency-complete supported engine profile | P02. Clean-machine local inference on each selected OS, loopback bind, structured output, context bounds, cancellation/restart and memory limits. Reuse Ollama if it qualifies; replace with llama.cpp only after parity. [Runtime contract](docs/architecture.md#36-runtime-adapter) |
| P04 — Two qualified task/model combinations — Beta blocker | Existing model preferences and baseline manifest → curated supported choices | P03. Pin and qualify at least two distinct appropriate model options over at least two task types, including the scan/Code requirements. Qualify runtime/model compatibility on the selected OS profiles. Preserve baseline where suitable; an installed model name or one model in two profiles is insufficient. [Catalogue acceptance](docs/model-catalog.md#10-acceptance-for-one-catalogue-entry) |
| P05 — Persistent Settings → Models — Beta blocker | Existing inventory/select endpoints → complete supported catalogue lifecycle | P04. Installed and available choices, explicit download/offline import, cancel, integrity, capability self-test, enable/disable, safe removal and refreshed recommendations after onboarding. Exercise this lifecycle on all three OS profiles. No reset or lost chats; no runtime-inventory entry silently becomes trusted. [Lifecycle](docs/model-catalog.md#persistent-model-management) |
| P06 — Standalone workflows and artifacts — Beta blocker | Existing Chat, OCR, FTS5, artifact writers and Code proposal/Apply → dependable narrow local workflows | P03–P05. Real multi-turn Chat, scan + selected SOP → grounded readable Word artifact, reviewable Code patch, source isolation, scoped failure diagnostics and preserved local Apply/Undo label. Replace or adapt Apple-only document processing and implement safe Windows Code access. Resolve the [reported document/Code gaps](docs/evaluation.md#p01-manual-20260918), with source grounding, selection continuity and all approval modes checked on each OS. Qualify existing FTS5; embeddings do not fix platform dependencies. [Beta acceptance](docs/evaluation.md#beta-acceptance) |
| P07 — One qualified code sandbox profile — Beta blocker | Reuse `worker/validate.py`, `jobspec.py` and `deploy/k3s/50-validation.yaml` where suitable | P02 and P04. Actual network/host-file/resource-boundary tests and real fixture validation on the advertised toolchain; approved graphical connection to a supported execution peer is allowed. No inference-only peer is advertised as a sandbox. Administrator setup for a managed target must be reproducible and distinct from reviewer installation. [Security boundary](docs/security.md#8-filesystem-and-sandbox) |
| P08 — App-managed peer execution — Beta blocker | Existing worker protocol, packages, receipts/leases/events → packaged peer path for chosen profiles | P03–P04. Selected Windows, macOS and Linux profiles can request and receive bounded work; demonstrate cross-OS and same-OS peer operation. At least two real installations exchange bounded work without users managing queues/certificates/model servers; preserve durable receipt, cancellation and restart semantics when reusing/replacing the Redis execution path. This is not P21 organisation administration. [Trusted mesh](docs/architecture.md#trusted-mesh) |
| P09 — Discovery, trust and receiver controls — Beta blocker | Existing pinning, pairing/revocation and Settings → guided LAN relationship | P08. Discovery plus address fallback, two-sided confirmation, protected credentials on each selected OS (not macOS Keychain only), pause/revoke/stop, compatible inventory and receiver notification; real denied/expired/revoked/identity-change tests. [Connection workflow](docs/workflows.md#8-connecting-compute) |
| P10 — Practical model/device scheduling — Beta blocker | `choose_route`, model preferences and worker queue observation → automatic eligible-pair choice | P04, P08–P09. Capability/policy/installed-model filters, observed load/freshness and atomic receiver-wide capacity admission; conservative slots/queue suffice. Demonstrate different task/model choices and a busy target queued or bypassed only within policy. P15 owns fleet fairness and smarter estimates. [Scheduler](docs/architecture.md#35-router-and-scheduler) |
| P11 — Integrated remote workflows — Beta blocker | Existing dispatch and remote Code package/validate/Apply → usable paired execution in the current harness | P06–P10. Real remote inference with bounded selected Chat context and truthful reasoning support; reviewable patch + matching real sandbox command/output/exit result before approved write. Documents may stay local with an explicit route. No unrestricted transfer or duplicate final writes. [Workflows](docs/workflows.md) |
| P12 — Failures, status and offline evidence — Beta blocker | Existing cancellation, reconciliation, status and Proof Cards → ordinary reviewer failures handled visibly | P11. Exercise disconnect/restart, no compatible model, busy/low-memory peer, denied approval, failed validation and cancellation; no manual database repair. Capture scoped independent egress evidence for local and paired workflows; wire evidence references into job status without fabricating measurements. [Beta evidence](docs/evaluation.md#beta-acceptance) |
| P13 — Distributable Beta candidate — Beta blocker | Existing macOS bundle and source CI → immutable versioned authenticated installer for the selected matrix | P05–P12. Packages for Windows, macOS and Linux match source; clean install/model setup/offline use/relaunch/uninstall preserve data; signing/notarisation as required, licences and support notes. Manual authenticated replacement/recovery rehearsal suffices for 0.1; no unfinished updater advertised. [Beta publication](docs/releases.md#beta-01-publication) |
| P14 — Reviewer acceptance and publication — Beta blocker | Candidate, fixtures and evidence → a defensible Download Refinix Beta button | P13 and all Band A outcomes. Nondeveloper walkthrough from website candidate through install, model selection, local use, pairing, remote inference and validated patch; inspect artifact quality and known limitations. Requester accepts actual evidence and the matrix covering all three OS families; publication is a separate authorised human action. [Release gate](docs/releases.md#beta-01-publication) |

---
**BETA RELEASE FRONTIER — Refinix Beta 0.1 / SIH Reviewer Preview: after P14.**

This cut-line follows the complete reviewer journey. Removing P05 locks users to
onboarding; removing P08–P11 loses trusted distributed compute or actual routing;
removing P07/P12 loses safe validation or defensible offline/failure evidence.
P13/P14 turn the integrated implementation into a downloadable, usable product.
More tasks do not compensate for a failure within this boundary.
---

### Band B — Post-Beta product improvements

Completed, accepted improvements ship as versioned Beta 0.2/0.3 releases under
the same release rules. These are not a freeze on development or blockers for 0.1.
“Beta enhancement” means an eligible subsequent Beta feature; “Post-Beta” means
work after the first Beta whose inclusion depends on profile qualification.

| Task / classification | Outcome | Hard dependencies and exit evidence |
|---|---|---|
| P15 — Fleet scheduling — Beta enhancement | Better queue/load/transfer estimates, fair admission across requesters and multiple workers | P10, P12, P14. Three-device/two-chat Code + Chat scenario, contention/fairness and stale-reservation tests from [production acceptance](docs/evaluation.md#production-acceptance) |
| P16 — Retrieval and personal context — Beta enhancement | Qualified hybrid retrieval alongside FTS5, corpus lifecycle, editable instructions/curated memory and safe data-root migration | P06, P12, P14. Source/access invalidation, citation quality, restart, conflict-safe migration; [corpus boundaries](docs/architecture.md#corpus-and-personalisation-boundaries) |
| P17 — Models and calibrated recommendations — Beta enhancement | Additional qualified models, broader quality fixtures and measured ranking | P05, P14. Catalogue provenance, capability regressions, measured/estimated fit and justified numeric scores; no forced replacement of working models |
| P18 — More installation and execution profiles — Post-Beta | Additional OS versions/editions, architectures, Linux distributions, hardware and sandbox/toolchain profiles beyond the three-family Beta baseline | P02, P07–P09, P13–P14. New profile's clean graphical setup, protected credentials, path confinement, same-OS peer operation and per-capability acceptance; inference-only participation allowed |
| P19 — Explicit in-app updates — Beta enhancement | Settings → Updates, authenticated connected check/download and offline update import | P13–P14. Two actual versions on each offered updater profile pass [update acceptance](docs/releases.md#update-acceptance); preserve manual replacement path until qualified |
| P20 — Recovery, performance and proof improvements — Beta enhancement | Better recovery UX, cold/warm measurements, bounded cache tuning and stronger Proof Cards | P12, P14; P15 when measuring fleet behaviour. Fault injection and representative quality/resource baselines; no optimisation weakens correctness, privacy or evidence semantics |

### Band C — Finals / production maturity

These remain master-plan commitments or explicitly conditional research. Finals
selection may enable a roughly three-month hardening window, not a promised
schedule or automatic authorisation. Release acceptance follows evidence.

| Task / classification | Outcome | Hard dependencies and exit evidence |
|---|---|---|
| P21 — Private-server and organisation administration — Finals/product maturity | Common protocol plus users/admins, quotas, corpus permissions and templates | P08–P12, P16, P19. Multi-user isolation and authorised corpus lifecycle; [private-server architecture](docs/architecture.md#private-server) |
| P22 — Broad OS/backend qualification — Finals/product maturity | Complete advertised requester/receiver matrix and extended sandbox/toolchain testing | P18, P20. Current clean-device evidence per OS/edition/backend; homogeneous groups without hidden Linux inference dependency |
| P23 — Full update/recovery matrix — Finals/product maturity | Complete migration, rollback, mixed-version compatibility, signing-key recovery and managed upgrade qualification | P19, P22; P21 for managed rows. All advertised combinations satisfy [production release acceptance](docs/releases.md#production-release-acceptance) |
| P24 — Advanced trust and resource qualification — Finals/product maturity | Larger security/resource suites; hardware-backed trust or advanced cache/admission only where justified | P15, P20–P22. Threat-driven tests and measured benefit; established mechanisms, no bespoke crypto or unproven optimisations |
| P25 — Additional capability packs and adaptation research — Finals/product maturity, conditional | Language/voice/media packs and separately approved model adaptation | P05, P16–P17, P20. Exact manifests, privacy/quality/held-out regressions and disable/revert; [optional adaptation](docs/model-catalog.md#11-personalisation-and-optional-model-adaptation). Not mandatory for core production |
| P26 — Finals candidate and production qualification — Finals/product maturity | Integrate judge feedback, expanded evaluations, rehearsals, support and release evidence | Finals candidate: P14 plus every feature claimed for that candidate. Full production: P15–P24 and all claimed optional P25 profiles; pass [production acceptance](docs/evaluation.md#production-acceptance) with requester sign-off. A finals candidate may remain narrower than production |

### Dependency lanes and safe parallel work

- After P01, P02 investigates both package and sandbox feasibility early. After
  P03/P04, P05–P06, P07 and P08–P09 can proceed in parallel against shared contracts.
- P10 needs actual peer capabilities/admission; P11 joins local workflows,
  sandbox and routing. Do not bypass these joins with mocked acceptance.
- Installer/signing preparation and fixture/UX work for P12–P14 may start early;
  their final acceptance runs on the integrated, immutable candidate after P11.
- After P14, P15–P20 are independent lanes except their listed dependencies;
  P18 may add profiles incrementally. P19 need not wait for every future OS.
- P21, P22 and P24 can overlap once their prerequisites hold. P23 joins the
  updater and broader support matrix; P26 accepts only the features it claims.
  A dependency is an acceptance prerequisite, not an exclusive code owner.

### Previous production gate mapping

| 2026-09-14 gate | Replacement tasks; retained responsibility |
|---|---|
| P01 baseline | P01 selects profiles in all three desktop OS families; later expansion in P18/P22 |
| P02 runtime/packaging | P02–P03, P13; updater P19/P23 |
| P03 workflows/RAG/models | P04–P06, P11; retrieval/memory and extra models P16–P17 |
| P04 portable execution/isolation | P07–P08; broader profiles P18/P22 |
| P05 trusted peers | P09; deeper trust P24 |
| P06 placement/concurrency | P10–P12 minimum; fairness/fleet/recovery P15/P20 |
| P07 recommendations/releases | P05, P13–P14 first Beta; P17/P19/P22–P23 full maturity |
| P08 managed deployment | P21; production acceptance P26 |

## Acceptance evidence

[Beta acceptance](docs/evaluation.md#beta-acceptance) owns the minimum evidence;
[production acceptance](docs/evaluation.md#production-acceptance) remains the full
destination. Record exact builds, model hashes, fixtures, commands/procedures and
observed results. Historical checks count only for their original scope. No
runtime tests or device qualification ran during this documentation restructure.

## First-publication gate

P14 may publish only after [Beta publication acceptance](docs/releases.md#beta-01-publication).
The full updater and all-platform production matrix are no longer prerequisites
for 0.1. Authentication, data preservation, qualified exposed capabilities and
requester acceptance remain mandatory. No Download button points to source,
an unsigned prototype, a missing package or an unqualified advertised profile.

## Historical records

Dated prototype checkpoints are retained in the [prototype task archive](docs/archive/prototype-task-record.md).
They do not create additional active tasks or override P01–P26. The
[documentation index](docs/README.md#release-and-historical-material) maps retired
paths to their canonical replacements and preserved evidence.
