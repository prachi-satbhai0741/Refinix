# Refinix implementation plan

## Status

This is the active implementation plan for the current production direction.

The previous P01-P26 decomposition is retired as an **active execution system**. Its useful
requirements and acceptance intent are preserved here and in `docs/PROJECT.md`; historical P-task
records remain available in repository history/evidence when a specific past decision must be
recovered.

The plan now uses five large implementation phases. A phase is a **coherent outcome**, not a queue
of microscopic tasks. An authorised agent should execute as much of the current phase as can be
completed safely within the user's scope, pausing only at genuine human checkpoints.

Keep the phase identifiers for historical references. For the standalone Beta, execute **Phase 1 ->
Phase 2 -> local Phase 4 acceptance -> Phase 5**. **Phase 3 and peer-specific Phase 4 work are deferred
until after Beta 0.1.** The Beta includes qualified in-app updates on Windows, macOS and Linux.

**Current active phase: Phase 5 — Refinix Beta 0.1 publication, then device acceptance.** The source
work of Phases 1, 2, local Phase 4 and Phase 5 is implemented and offline-tested. The review A1 repair
batch (10 October 2026) is repaired, locally checked and native-qualified at
`d109b49f6c9bdc4b72bda9f347c6481442f96984` on Windows Server 2025, Ubuntu 24.04 and macOS 15/14.
Segment 1's repair/source/native work is complete. The user has generated the production Beta keys
and confirmed an encrypted iCloud backup; the public root is verified at
`desktop/updates/beta-root.json`, with production-root package qualification still pending.
`docs/releases.md` records the user's approved encrypted iCloud/Apple Passwords exception to the
offline custody default. [evaluation.md](docs/evaluation.md#beta-01-segment-1) records
the observed results and remaining gates. Device acceptance is open on every platform, so none of
those phases is complete.

**5 October 2026 direction:** the [full user statements](docs/beta-user-direction-2026-10-05.md) are
preserved verbatim: broad upstream model choice, existing Ollama reuse, managed llama.cpp,
lightweight recommendations and automatic local task-to-model routing, without team certification
of every model/device/version, on the existing foundation, with distribution deferred.

**10 October 2026 direction (user):** the public name is **Refinix Beta 0.1** (`0.1.0-beta.N`, a normal
GitHub release, public build 8); macOS and Windows are published **unsigned** with each OS's warning;
the website offers the macOS DMG, the Windows setup and the Ubuntu `.deb`; the release happens
**before** the user's device walkthrough, and device acceptance stays a separate record.

### Launch sequence (current)

1. Repairs and native qualification of one recorded commit on hosted runners (`qualify.yml`); any
   later code change repeats the affected checks. Segment 1 passed run
   [38055591709](https://github.com/prachi-satbhai0741/Refinix/actions/runs/38055591709) at the commit
   recorded above; the closing results-only update does not change application/workflow code.
2. Production Beta keys and root (the user; custody in `docs/releases.md`) →
   `desktop/updates/beta-root.json` committed.
3. Member → dev → main, the user merging; `main`'s file tree equals the qualified tree.
4. `release.yml` on that commit: all three lanes, each package qualified on its exact bytes, the
   Mac bytes again on the oldest arm64 macOS runner; `release_assemble.py`; the CP-B manifest.
5. CP-B (the user): publish the release, stage the feed offline, merge the website PR, advance the
   feed (exact live check), `verify-public.yml` and anonymous downloads of the DMG, setup and `.deb`.
6. Launch complete / device testing pending → the user's device walkthrough → one repair batch as new
   immutable versions → device acceptance recorded per platform.

### Completed in source (offline-tested; native runner results in evaluation.md; not device-accepted)

- Public Beta update channel: signed TUF feed with preview and Beta pointers, one version ordering
  key, forward-only publisher, exact live-feed check, daily refresh, root rotation, offline bundles.
- In-app updates on all three platforms: macOS app swap; Windows per-user setup inside a
  kill-on-close job with registry restore and file-list completeness; Ubuntu `.deb` through a
  password-protected root step with one current attempt per installation and direction-aware
  recovery; packaged N → N+1 update, rollback and interrupted-update journeys on hosted runners.
- Release tooling: Beta package workflow for all three lanes with bound native qualification, release
  assembly for the unsigned Beta, website feed workflows (templates for the website repository),
  public verification workflow; Developer ID/notarisation and Authenticode paths kept for later.
- Ubuntu Code sandbox (provisional until device qualification) wired into validation and Apply, with
  prompt Cancel, recoverable cleanup and live-input re-checks before a sandbox-validated Apply.
- Linux native messages, context indicator details, dead-code removal, launcher drift fix.
- Website download cards rendered from the release record, with minimum OS, OS warning and
  device-testing state; scan reading labelled Beta.

### Open acceptance items

- Every device walkthrough (Windows 11, macOS, Ubuntu desktop) on published packages: SmartScreen /
  Smart App Control, Gatekeeper's Open Anyway, the real polkit prompt, real workflows and updates.
- Ubuntu sandbox qualification on a real desktop session (still provisional after the runner checks).
- Production Beta keys, the website owner's settings and secrets, and the live feed.
- Developer ID and Windows code signing (optional later; not a Beta prerequisite).

Phase 1 is only the first part of the total Refinix Beta path. Completing Phase 1 does **not** mean
Refinix is Beta-complete, release-ready or production-qualified. It establishes the portable
foundation needed by the local-product, standalone safety/proof and release phases. Trusted-mesh
work remains a later product section, not a first-Beta prerequisite.

The product contract is [`docs/PROJECT.md`](docs/PROJECT.md). Security, models and release/update
detail remain in their focused authorities.

## 1. Operating contract

- Preserve the existing UI, harness, useful adapters, user data and security boundaries.
- Reuse working source before replacing it. A technology change requires a demonstrated product or
  portability need, not preference.
- Continue prototype work from the existing repository and preserve merged capabilities. Trace each
  relevant UI/API, coordinator, runtime/tool, storage and validator path before adding code; repair
  or adapt the existing path instead of rebuilding it or overlooking available behaviour.
- Reuse upstream infrastructure and published evidence within the Beta scope. Local
  model admission uses actual compatibility and capacity; team measurements are evidence, not a
  general allowlist. Keep graphical setup, a managed engine path and existing Ollama reuse.
- Keep the current orchestration harness. LangGraph remains a considered option under
  `docs/PROJECT.md` section 7.0, not a dependency to install or a prerequisite to completing Beta.
- Windows, macOS and Linux are all required desktop OS families for the Beta direction. Publish
  evidence-backed minimum OS versions/ranges, architectures and backends; record exact tested builds
  separately. Linux initially targets Ubuntu. The project does not promise every computer.
- Prepare reviewed hardware/capability presets from existing research and representative evidence;
  setup matches those records with lightweight current-capacity checks. Reuse established offline
  tools and the existing code. Do not build a custom startup optimizer or require ownership of every
  target laptop before research or implementation. Model benchmarks do not replace package acceptance.
- The existing macOS application is the strongest current desktop baseline, not a permanent product
  restriction.
- The existing Linux/K3s/Redis worker/sandbox path is retained infrastructure, not a mandatory
  requirement for ordinary desktop peer participation.
- Plan/implementation/test/device/release states remain separate. Source existence is not acceptance.
- Do not split a coherent implementation merely because it spans multiple modules.
- Organise work only by the major sections/outcomes in `docs/PROJECT.md` and these phases. Complete
  the authorised section directly, including integration and authorised verification. Do not add
  further task tiers, per-file assignments or subagent delegation unless the user changes this rule.
- Do not create a new task or handoff document for each agent session.
- Core documentation is protected by `AGENTS.md`; agents must obtain user permission before changing
  it.
- Tests, installers, model downloads, migrations, deployments and live device/runtime checks require
  the permissions defined in `AGENTS.md`.
- Historical dates and device mappings are evidence, not delivery deadlines or permanent roles.

## 2. How agents execute a phase

For the active phase:

1. Read `AGENTS.md`, `docs/PROJECT.md`, and this phase.
2. Inspect the existing implementation, affected callers and relevant tests; identify reusable
   behaviour and concrete gaps before implementing anything.
3. Read `security.md`, `model-catalog.md` or `releases.md` only when the work enters that domain.
4. Recover historical evidence only when needed; do not preload the archive/ledgers.
5. Identify any facts/permissions that only the user can provide.
6. Ask those questions together before execution when possible.
7. For a user-owned decision, give **Recommendation / Reason / Trade-off / Intended path**.
8. Implement the largest coherent safe scope that does not depend on an unresolved checkpoint.
9. Finish all possible work before asking the user for manual verification on another device.
10. Report implementation, actual verification, limitations and the next coherent action separately.

A phase may involve several code changes and several manual checkpoints. These are **checklist items**,
not separate project-management tasks unless the user explicitly chooses to split ownership.
Routine code organisation and obvious fixes remain agent-owned. Do not turn inspection, planning,
implementation, integration and verification into separately delegated tasks or repeated handoffs.

## 3. Human checkpoint model

### Before execution

Ask only for facts/permissions that cannot be safely derived from current authoritative docs and
source. Prefer a simple user answer over unnecessary device probing when the fact is straightforward.

Examples:

- which Windows/Linux machine is available for the current qualification pass;
- whether the user permits a specific dependency/install action;
- a fresh OS edition/build when release evidence requires freshness;
- whether the user accepts a proposed architecture/security/product change.

### During execution

Pause only for a real fork: architecture/product decision, protected-doc change, security boundary,
destructive operation, unavailable credential, new installation/host action, or a manual device
observation that blocks further implementation.

### After execution

Request the smallest manual validation that the current environment cannot perform. Prefer a UI
observation or one focused command before escalating to a larger diagnostic procedure.

A manual checkpoint does not create a new phase. Resume the same phase after the answer.

---

# Phase 1 — Cross-platform foundation

**Status: ACTIVE**

## Phase 1 outcome

Transform the existing macOS-first desktop/runtime assumptions into a portable Refinix foundation
that can be built toward supported Windows, macOS and Linux desktop profiles without changing the
product's architecture or forcing users to operate developer infrastructure.

At the end of Phase 1, the repository should have one explicit cross-platform foundation for:

- platform data/config paths;
- local service/application lifecycle;
- app-managed inference-runtime integration;
- document/PDF/image dependencies;
- bounded Code filesystem access;
- protected credential storage abstraction;
- retained shared job/identity interfaces for later peer execution;
- installer/dependency/sandbox prerequisites;
- exact support-profile assumptions ready for later device qualification.

Phase 1 establishes these foundations; Phase 2 proves the complete standalone product workflows.
The local part of Phase 4 closes sandbox/recovery/proof behaviour. Phase 5 turns that standalone
product, including qualified in-app updates, into the published Beta candidate. Phase 3 proves
trusted peer execution after Beta and then repeats the relevant Phase 4 checks for exposed peer paths.

## Starting point

The current repository already contains substantial working/prototyped behaviour:

- a macOS desktop path using the existing shell/lifecycle and current frontend;
- coordinator SQLite state, Chat/context, document, Code, approval and artifact paths;
- current Ollama runtime integration and a measured Qwen3.5-4B baseline;
- worker protocol, pairing/revocation, receipts/leases/events and distributed Code paths;
- K3s/Redis/executor/validation infrastructure on the retained managed Linux profile;
- Proof Card source/UI with network evidence still incomplete;
- historical device/runtime measurements and synthetic fixtures.

Known portability gaps include macOS-specific packaging/native document dependencies, OS-specific
credential storage, Windows-safe bounded filesystem operations, a desktop package that does not yet
contain the full peer execution role, and unqualified runtime/installer/sandbox paths on the three
OS families.

### Standalone-first priority

For Beta 0.1, prioritise a dependable standalone Refinix installation on the
selected Windows, macOS and Linux profiles before expanding the trusted-device
mesh.

The immediate target is:

download/install -> detect hardware -> recommend compatible local models ->
set up or import a model -> self-test -> use Chat, Documents and Code locally ->
persist and reopen work successfully.

Then qualify the in-app update and recovery journey on each advertised OS profile before publication.

During this portability pass:

- fix immediately any defect that blocks one of the selected OS profiles,
  causes data loss/corruption, weakens security/isolation, prevents installation,
  prevents model setup/inference, or makes a core standalone workflow unusable;
- record non-blocking workflow, model-quality, artifact-quality and UI regressions
  for the dedicated stabilization pass rather than interrupting cross-platform
  foundation work;
- after standalone operation is established across all three OS families, run a
  focused stabilization/bug-fix pass before tester-preview packaging and publication;
- trusted-device discovery, pairing, distributed execution and scheduling remain
  part of the product architecture, but should not delay a usable standalone
  build. Resume that work after Beta 0.1 when the standalone baseline is
  stable and schedule permits.

This is a **Beta 0.1 release-scope reduction**. Discovery, pairing, peer-agent packaging, remote
execution, fleet scheduling and private-server use are not Beta prerequisites. Preserve their source
and shared contracts for post-Beta work, with their security and acceptance requirements intact.
Do not make standalone workflows or Beta installation depend on a second machine.

## Phase 1 checklist

### A. Current profile facts and assumptions

- Select/confirm one narrow candidate desktop profile in each OS family for the first Beta path.
- Derive candidate tiers from official dependency/model data and published benchmarks first. Record
  minimum versions, CPU/backend, RAM/VRAM and storage, with measured/estimated limits distinguished.
  Device brands are labels. Arrange remaining package/device checks through available machines,
  suitable CI or volunteer observations; the user need not own all target hardware.
- Record OS edition/architecture/backend facts from current user/device evidence when freshness is
  required; do not treat old inventory as fresh release acceptance.
- Keep capability support per profile: an inference-capable profile does not automatically gain a
  local sandbox.
- Do not drop Windows, macOS or Linux to simplify the Beta direction.

**Human checkpoint:** if fresh device facts are needed, ask the user directly for the smallest set of
facts first. Run larger probes only when the user authorises them or the simple fact is insufficient.

### B. Platform abstraction and durable data

- Use platform-native Refinix data roots and keep durable data outside replaceable application files.
- Preserve compatibility-sensitive legacy `.aegisforge` state until a separately authorised,
  versioned migration is implemented and verified.
- Keep structured state in SQLite; do not move canonical state into Markdown or network shares.
- Define portable paths for temporary jobs, artifacts, corpus/index data and model manifests.
- Preserve owner-only protections where supported.
- Keep credentials/secrets out of SQLite/plaintext config when OS-protected storage is required.

### C. Desktop/local-service lifecycle

- Preserve the current UI and coordinator harness.
- Make startup/shutdown/service discovery behaviour portable rather than embedding macOS-only
  assumptions.
- Keep UI/local service endpoints loopback-bound.
- Ensure failure states are truthful when a required runtime/native dependency is unavailable.
- Do not introduce a new frontend framework merely for portability.

<a id="d-app-managed-inference-runtime"></a>
### D. Reused local runtimes and compatible model admission

- Reuse the existing Ollama adapter as a product path for installed local Ollama models, without
  copying weights. Keep the managed upstream llama.cpp path for users who need it.
- Select the backend from model origin internally; show runtime/source on entries. Users with
  Ollama may also download managed models. No mandatory technical runtime chooser or second install.
- Preserve managed-engine executable/configuration/integrity ownership; an external updater cannot
  replace its bytes. Broaden managed model choice beyond the current static measured entry.
- Replace blanket local exact-profile gates with actual API/format/task capability, health/locality,
  resource and data/tool-policy admission. Preserve measured evidence honestly; no spoofed versions,
  invented qualification, weakened worker checks or unsafe host execution.
- A newer Ollama version alone does not block normal work. Refresh metadata and explain real missing
  features/security exclusions, offering normal graphical upstream update/start guidance under user
  authority rather than requiring every customer to maintain a measured version.
- Preserve streaming, cancellation, context bounds, reasoning, structured parsing, model identity,
  task validators, persisted history and approvals across both adapters and every affected caller.
- Keep inference local/offline and reject cloud-backed choices before work is sent.
- Reuse allocation/loading/queuing features for multiple models/jobs. Permit concurrency where
  capacity allows it; do not impose a universal one-model rule or disturb other Ollama clients.
- Use lightweight hardware facts and published estimates for recommendations, not a mandatory
  optimizer, per-model benchmark or hardware allowlist. Real format/capacity failures stay visible.

**Next planning checkpoint:** the implementation owner inspects current source/callers and proposes
one coherent plan against the user's verbatim requirements. The user returns that plan for independent
review. Ask only for genuine new scope/security/host actions; do not re-ask settled model freedom,
Documents/Code use, automatic assignment or distribution deferral.

### E. Cross-platform document/image foundation

- Identify and replace/adapt Quartz/AppKit-only rendering/processing assumptions needed by Beta
  document workflows.
- Preserve source hashes, page association, uncertainty and artifact/citation contracts.
- Keep FTS5 available as the qualified lexical retrieval baseline.
- Do not use embeddings as a substitute for missing PDF/image rendering or artifact generation.
- Keep semantic retrieval as later qualified work unless required by the current authorised scope.
- Ensure generated artifacts use portable paths and do not depend on the source checkout.

### F. Cross-platform bounded Code access

- Preserve explicit repository/folder selection and current access/approval modes.
- Replace/adapt descriptor/platform assumptions that do not work safely on Windows without falling
  back to unrestricted path access.
- Keep traversal/symlink/link escape protections and canonical-write approval behaviour.
- Preserve local Apply/Undo as its explicitly labelled non-sandbox local mode until qualified
  sandbox execution proves a stronger route.
- Do not silently read the entire repository to solve selection friction.

<a id="g-protected-credentials-identity-and-peer-agent-packaging-foundation"></a>
### G. Protected credentials, identity and retained peer interfaces

- Define OS-appropriate protected credential storage for macOS, Windows and Linux.
- Preserve scoped relationship identity and revocation semantics.
- Qualify local protected storage and installation identity without requiring discovery, pairing or
  a packaged peer execution agent. Complete peer packaging in the deferred Phase 3.
- Do not require Kubernetes, Redis or peer certificates for standalone Beta use.
- Preserve the existing authenticated worker/job contract so later peer execution can reuse its
  receipts/cancellation/reconciliation semantics.

### H. Installer/dependency feasibility

- Determine the supportable application/runtime/native-library packaging route for each candidate OS
  profile.
- Identify signing/notarisation, permissions, driver/virtualisation, storage and licence
  prerequisites early.
- Preserve models as separately managed artifacts where appropriate; do not bake large mutable model
  weights blindly into application packages.
- Ensure normal end users do not need Python/package-manager/certificate/Kubernetes setup in a
  terminal for advertised capabilities.
- Record unsupported prerequisites honestly rather than weakening security or faking readiness.

### I. Sandbox feasibility boundary

- Preserve the existing restricted Kubernetes validator as a real candidate/evidence path.
- Select at least one safe local Beta Code-validation route that can later be qualified end-to-end
  on an eligible advertised profile; a remote sandbox is not a standalone Beta dependency.
- Do not treat a container, timed host subprocess or remote inference peer as proof of sandbox
  isolation.
- Windows Home limitations must be considered; Windows Sandbox cannot be assumed universal.
- No unsafe host-execution fallback.

## Phase 1 completion condition

Phase 1 is complete only when the user accepts that the repository has a coherent, implementable
cross-platform foundation and there are no unresolved macOS-only assumptions blocking the selected
Windows/macOS/Linux Beta profiles at the architecture/source level.

Completion should include:

- the chosen candidate profile assumptions for all three OS families;
- portable platform/data/credential abstractions in source where required;
- a defined/implemented local runtime packaging direction with no silent terminal dependency;
- a portable document-processing route for the Phase 2 workflow;
- safe bounded Code path handling across the selected profiles;
- retained shared job/identity interfaces without a peer-packaging completion gate;
- a safe sandbox route identified for later integrated qualification;
- known external/manual/device gates listed clearly.

**Phase 1 does not require:** publication, full model lifecycle UX, complete local document/code
quality acceptance, updater acceptance, final Proof Card egress evidence or public Beta installers.
Those belong to the later standalone/release sections. LAN discovery, pairing, routing and peer
packaging remain deferred until after Beta.

---

# Phase 2 — Complete standalone Refinix

**Status: NEXT AFTER PHASE 1**

## Phase 2 outcome

Make each selected desktop profile useful through the existing interface, with broad compatible
local models, automatic task-to-model routing and useful Chat/Documents/Code workflows. Reuse existing
infrastructure and published evidence; do not certify every model as a prerequisite.

## Phase 2 required outcomes

- Persistent **Settings -> Models** lifecycle:
  - existing Ollama and managed entries with runtime/source identity, plus broad upstream discovery;
  - explicit compatible download or verified offline import;
  - progress/cancellation;
  - provenance/integrity verification;
  - lightweight compatibility/health/locality information and honest task failures;
  - enable/disable;
  - safe removal without losing chats or unrelated models.
- Reuse download/import integrity, progress and cancellation. Local checks or real task execution
  show observed results without mandatory synthetic certification for every model/version. Customers
  do not register qualification profiles. Preserve app/tool/package safety evidence separately.
- Recommend using lightweight hardware facts and published/estimated requirements. Users may choose
  beyond recommendations; show source, evidence, format/runtime needs and resource warnings. No
  hardware-brand/device allowlist or compulsory benchmark. Ordinary runtime remains offline.
- Implement automatic local assignment from workflow/prompt/attachments, available capabilities
  and capacity; preserve optional manual overrides and persist a concise routing reason.
- Exercise multiple model identities/jobs and representative Chat/Documents/Code tasks, including
  existing Ollama and managed paths. Use available small models and deterministic fixtures where
  appropriate; do not require a large model download or claim mocked checks establish real performance.
- Demonstrate capacity-aware concurrent work or queuing, preserving cancellation and other clients.
- Real multi-turn Chat with bounded context, reasoning behaviour, cancellation, persisted history and
  truthful omissions/failures.
- Grounded scan/image + selected SOP -> readable Word artifact with page/source citations and
  uncertainty preserved.
- Reviewable Code proposal with clear selection/permission scope and preserved local Apply/Undo
  distinction.
- Local source isolation and no cross-project permission leakage.
- Current UI remains the product surface; no frontend rewrite.
- Each advertised desktop profile remains useful without any peer.

## Human/device checkpoints

Use real device/model checks only when authorised. Ask the user for simple device/UI observations
before escalating to broad diagnostic commands. Record exact identities/settings for observed runs;
do not extrapolate one result to another or make every model's measurement a local admission gate.

## Phase 2 completion condition

A user can install/configure the selected local dependencies through the intended product path and
complete the narrow standalone Chat/Documents/Code journey on the supported profiles, with truthful
capability status and without public-cloud inference.

---

# Phase 3 — Trusted-device mesh

**Status: DEFERRED UNTIL AFTER BETA 0.1; NOT A BETA RELEASE GATE**

Preserve existing source, contracts and historical evidence. Do not resume mesh expansion merely
because a local Beta change touches shared code; finish the authorised standalone section first.

## Phase 3 outcome

Allow normal Refinix installations on Windows, macOS and Linux to discover, trust and use each
other's eligible compute through the product UI, without making ordinary peer machines Kubernetes
nodes.

## Phase 3 required outcomes

- App-managed peer execution using the existing bounded job protocol.
- Cross-OS and same-OS peer operation on selected profiles; no hidden Linux requirement.
- Local discovery plus guided address fallback.
- Explicit two-sided pairing, authenticated encrypted traffic and OS-protected credentials.
- Pause sharing, revoke, stop/cancel and receiver-visible remote-work controls.
- Capability/model/health advertisement only within trusted relationships.
- Remote Chat transports bounded selected context rather than only the latest raw request.
- Remote Code returns the patch and matching validation evidence before any approved canonical write.
- Documents may remain local when policy/capability requires it; routing must say so honestly.
- Automatic model/device selection applies hard trust/data/capability filters and fresh capacity.
- Receiver-wide admission prevents overcommit across multiple requesting users/workspaces.
- User-pinned targets never silently move.
- No pooled VRAM, model sharding or merged workspaces.

## Phase 3 completion condition

At least two real Refinix installations can pair graphically and execute bounded work across the LAN
with the requesting coordinator retaining canonical state. The user can see which model/device was
selected and why, and the receiver can control shared compute.

---

# Phase 4 — Safe execution, recovery and sovereignty evidence

**Status: LOCAL PATHS AFTER PHASE 2, BEFORE BETA; PEER PATHS AFTER DEFERRED PHASE 3**

## Phase 4 outcome

Qualify the standalone product's sandbox, failure, recovery, approval and network-evidence behaviour
before Beta. Extend the same requirements to peer paths after Phase 3; peer acceptance does not
block the local release.

## Phase 4 required outcomes

- At least one qualified local Code sandbox execution profile with observed network denial, host-file
  isolation and resource limits.
- No unsupported desktop profile is advertised as having local sandbox execution.
- Canonical writes remain approval-bound and idempotent.
- Local runtime disconnect/restart, cancellation, validation failure, no-compatible-model,
  busy/low-memory device and denied approval are handled visibly before Beta. Peer disconnect,
  revoked relationships, receiver admissions and ambiguous remote receipts are qualified after Phase 3.
- Retry/recovery reconciles uncertain work before creating another attempt; duplicate canonical
  writes are prevented.
- Status UI shows real model, device, stage, queue/failure state and routing reason.
- Sovereignty evidence distinguishes enforcement from observation.
- Scoped independent public-egress evidence is captured for representative local workflows before
  Beta and paired workflows after Phase 3; unavailable evidence remains unavailable.
- Proof Cards bind job/model/device/input-output hashes/validation/approval/network observation
  without overstating universal security.

## Phase 4 completion condition

The reviewer-facing workflows survive ordinary failures without manual database repair, unsafe
fallbacks or fabricated green states, and the demonstrated sovereignty claim is tied to actual
observed/enforced evidence.

---

# Phase 5 — Beta packaging, acceptance and publication

**Status: FINAL PHASE BEFORE BETA 0.1 PUBLICATION**

## Phase 5 outcome

Produce the first defensible standalone **Refinix Beta 0.1** on Windows, macOS and Linux, including
in-app updates and recovery — reached through the launch sequence above: a natively qualified public
Beta first, device testing on its downloads, one repair batch, then device acceptance.

## Phase 5 required outcomes

- Publish an exact supported OS/edition/architecture/backend/capability matrix containing at least
  one qualified profile in each of Windows, macOS and Linux.
- Build immutable packages from one designated source version/commit.
- Verify shipped source/resources, dependency/model manifests, notices, integrity and platform
  signing/notarisation requirements.
- Nondeveloper journey:
  website candidate -> package -> install -> hardware detection -> model setup/import -> self-test ->
  standalone work -> persist/reopen -> in-app update -> offline restart with preserved work.
  Code sandbox validation is demonstrated locally on an eligible profile; other profiles disclose
  their validation limits without requiring peer setup.
- Test first launch/relaunch, missing/denied dependencies/permissions, insufficient disk,
  cancellation, unsupported capability and uninstall/data preservation.
- Verify that the package uses its recorded app-managed engine and still performs offline work
  after an unrelated system-runtime update/change. Release-engineering checks cover wrong/missing
  packaged engine bytes and qualification-record mismatch with truthful refusal and graphical recovery.
- Qualify a Refinix release transition that changes the managed engine; matching profiles, selected
  models, local work, migration/recovery and preserved state must work without customer qualification.
- Exercise Settings -> Models after onboarding.
- Trace and reuse existing updater/packaging code where suitable, then qualify **Settings -> Updates**
  connected check/download/install/restart and verified offline import with two labelled builds on
  every published Beta profile, following `docs/releases.md`. No silent checks or unverified controls.
- Rehearse authenticated **manual full-package replacement and recovery** on every published Beta
  profile as a recovery path. It is not a substitute for the in-app updater unless the user explicitly
  approves changing this Beta scope. An unqualified updater remains a release blocker.
- Preserve chats, model references, credentials, artifacts and compatible state across the offered
  replacement/recovery path.
- Release notes disclose Beta limitations, supported models/targets and recovery/removal guidance.
- User reviews and accepts the actual evidence before publication.
- Publication/GitHub/release writes remain separate explicitly authorised human actions.

## GitHub/release boundary

Repository flow remains:

`member branch -> dev -> main -> CI/build gates -> designated version -> platform packages -> signing/verification -> versioned release assets -> website/update metadata`.

A merge/change on `main` does **not** update installed applications. GitHub Releases is the current
initial public artifact-hosting candidate, subject to the release contract. Users must receive
versioned verified packages, not source checkouts or CI artifacts presented as releases.

## Phase 5 completion condition

Only after every exposed Beta capability passes its applicable acceptance on the shipped package,
and the user accepts the evidence, may a **Download Refinix Beta** link be published.

---

# After Beta 0.1 — additional product work

The production direction continues after Phase 5. These are not prerequisites for the first Beta
unless the user deliberately promotes one into the Beta claim set.

## Beta 0.2 / 0.3 improvements

- complete the deferred Phase 3 trusted-device mesh and peer-specific Phase 4 acceptance;
- smarter fleet scheduling, queue/transfer estimates and fairness across requesting users/workspaces;
- stronger recovery/performance/Proof Card UX and measured cache tuning;
- hybrid semantic + lexical retrieval, corpus lifecycle and curated memory;
- additional qualified models and calibrated recommendation scoring;
- more OS/hardware/backend/sandbox profiles;
- extend the qualified Beta updater with additional profiles/transitions and improvements justified
  by measured need; retain explicit connected actions and verified offline import.

## Finals / production maturity

- organisation/private-server users, administrators, quotas and separately authorised shared corpora;
- broader client/receiver/toolchain qualification;
- complete update/migration/rollback/mixed-version/signing-key recovery matrices;
- deeper threat/resource/admission testing;
- additional language/voice/media capability packs where justified;
- optional evaluated adapters/personalisation with separate approved datasets and held-out tests;
- finals candidate integration, judge feedback, rehearsal/support and eventual full production qualification.

## Explicitly not implied by the phase plan

The plan does not require model sharding, pooled VRAM, foundation-model training, arbitrary model
runtime code, cloud inference, employee project-management features, a React rewrite, a new generic
agent framework, Kubernetes on every desktop, or high-availability coordinator failover for Beta.

---

# Evidence and status recording

- `docs/evaluation.md` remains evidence/reference, not the product contract.
- `docs/devicespecifications.md` remains historical/device evidence; fresh support claims need fresh
  device/profile observations.
- `docs/worker-operations.md` remains the managed Linux/Kubernetes operational runbook.
- `agent-memory/` remains searchable historical request/change memory.
- The retired `docs/prd.md`, `docs/architecture.md`, `docs/workflows.md` and `TechStack.md` remain
  compatibility/reference snapshots. Current requirements come from `docs/PROJECT.md`.

Agents must obtain user permission before changing these protected docs, as defined in `AGENTS.md`.
