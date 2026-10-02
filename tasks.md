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

**Current active phase: Phase 1 — Cross-platform foundation.**

Phase 1 is only the first part of the total Refinix Beta path. Completing Phase 1 does **not** mean
Refinix is Beta-complete, release-ready or production-qualified. It establishes the portable
foundation needed by the later local-product, trusted-mesh, safety/proof and release phases.

The product contract is [`docs/PROJECT.md`](docs/PROJECT.md). Security, models and release/update
detail remain in their focused authorities.

## 1. Operating contract

- Preserve the existing UI, harness, useful adapters, user data and security boundaries.
- Reuse working source before replacing it. A technology change requires a demonstrated product or
  portability need, not preference.
- Windows, macOS and Linux are all required desktop OS families for the Beta direction. Exact
  versions/architectures/backends must be qualified; the project does not promise every computer.
- The existing macOS application is the strongest current desktop baseline, not a permanent product
  restriction.
- The existing Linux/K3s/Redis worker/sandbox path is retained infrastructure, not a mandatory
  requirement for ordinary desktop peer participation.
- Plan/implementation/test/device/release states remain separate. Source existence is not acceptance.
- Do not split a coherent implementation merely because it spans multiple modules.
- Do not create a new task or handoff document for each agent session.
- Core documentation is protected by `AGENTS.md`; agents must obtain user permission before changing
  it.
- Tests, installers, model downloads, migrations, deployments and live device/runtime checks require
  the permissions defined in `AGENTS.md`.
- Historical dates and device mappings are evidence, not delivery deadlines or permanent roles.

## 2. How agents execute a phase

For the active phase:

1. Read `AGENTS.md`, `docs/PROJECT.md`, and this phase.
2. Inspect the current implementation path and relevant tests.
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
- packaged peer execution-agent direction;
- installer/dependency/sandbox prerequisites;
- exact support-profile assumptions ready for later device qualification.

Phase 1 establishes these foundations; Phase 2 proves the complete standalone product workflows.
Phase 3 proves trusted peer execution. Phase 4 closes sandbox/recovery/proof behaviour. Phase 5 turns
that integrated product into the published Beta candidate.

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

### Current SIH reviewer priority

For the current SIH reviewer cycle, prioritise a dependable standalone Refinix
installation on the selected Windows, macOS and Linux profiles before expanding
the trusted-device mesh.

The immediate target is:

download/install -> detect hardware -> recommend compatible local models ->
set up or import a model -> self-test -> use Chat, Documents and Code locally ->
persist and reopen work successfully.

During this portability pass:

- fix immediately any defect that blocks one of the selected OS profiles,
  causes data loss/corruption, weakens security/isolation, prevents installation,
  prevents model setup/inference, or makes a core standalone workflow unusable;
- record non-blocking workflow, model-quality, artifact-quality and UI regressions
  for the dedicated stabilization pass rather than interrupting cross-platform
  foundation work;
- after standalone operation is established across all three OS families, run a
  focused stabilization/bug-fix pass before reviewer packaging and publication;
- trusted-device discovery, pairing, distributed execution and scheduling remain
  part of the product architecture, but should not delay a usable standalone
  reviewer build. Resume that work when the standalone baseline is stable and
  schedule permits.

This is an execution priority, not a product-scope reduction. The trusted-device
mesh and later release phases remain in scope and retain their existing security,
qualification and acceptance requirements.

## Phase 1 checklist

### A. Current profile facts and assumptions

- Select/confirm one narrow candidate desktop profile in each OS family for the first Beta path.
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

### D. App-managed inference runtime

- Reuse the current Ollama path where it qualifies.
- Evaluate/implement the preferred bundled `llama.cpp`/`llama-server` path only when parity and
  packaging requirements justify it; do not force a migration simply because it is the target
  candidate.
- Preserve model selection, streaming, cancellation, structured output, context bounds, reasoning
  controls and health semantics across supported runtime adapters.
- Keep inference endpoints on loopback.
- Establish memory/resource budgeting hooks needed by later concurrency work.
- Do not require ordinary users to install/manage model servers from a terminal.

**Decision checkpoint:** if runtime parity evidence shows that keeping Ollama or moving to bundled
llama.cpp materially changes the Beta package, the agent must present a recommendation and obtain
user approval before changing the product/runtime direction or protected docs.

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

### G. Protected credentials, identity and peer-agent packaging foundation

- Define OS-appropriate protected credential storage for macOS, Windows and Linux.
- Preserve scoped relationship identity and revocation semantics.
- Make the production desktop package capable, in architecture/source, of including the app-managed
  execution-agent role rather than coordinator-only macOS packaging.
- Do not require Kubernetes or Redis on ordinary desktop peers.
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
- Select at least one safe Beta Code-validation route that can later be qualified end-to-end.
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
- an app-managed peer execution-agent packaging foundation;
- a safe sandbox route identified for later integrated qualification;
- known external/manual/device gates listed clearly.

**Phase 1 does not require:** publication, full model lifecycle UX, complete local document/code
quality acceptance, finished LAN mesh routing, final Proof Card egress evidence, or public Beta
installers. Those belong to later phases.

---

# Phase 2 — Complete standalone Refinix

**Status: NEXT AFTER PHASE 1**

## Phase 2 outcome

Make each selected desktop profile useful on its own through the existing Refinix interface, with
qualified local models and dependable Chat/Documents/Code workflows.

## Phase 2 required outcomes

- Persistent **Settings -> Models** lifecycle:
  - installed vs supported/uninstalled entries;
  - explicit compatible download or verified offline import;
  - progress/cancellation;
  - provenance/integrity verification;
  - capability self-test;
  - enable/disable;
  - safe removal without losing chats or unrelated models.
- At least two qualified task/model combinations across at least two task types; installed model
  names alone are insufficient.
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
before escalating to broad diagnostic commands. Qualify exact model/runtime/profile combinations;
do not extrapolate one machine's result to another.

## Phase 2 completion condition

A user can install/configure the selected local dependencies through the intended product path and
complete the narrow standalone Chat/Documents/Code journey on the supported profiles, with truthful
capability status and without public-cloud inference.

---

# Phase 3 — Trusted-device mesh

**Status: AFTER PHASE 2 FOUNDATION; PREPARATION MAY OVERLAP WHEN SAFE**

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

**Status: AFTER THE RELEVANT PHASE 2/3 PATHS EXIST**

## Phase 4 outcome

Turn the integrated local/peer product into a defensible private agent system by closing sandbox,
failure, recovery, approval and network-evidence behaviour.

## Phase 4 required outcomes

- At least one qualified Code sandbox execution profile with observed network denial, host-file
  isolation and resource limits.
- No unsupported desktop profile is advertised as having local sandbox execution.
- Canonical writes remain approval-bound and idempotent.
- Disconnect/restart, cancellation, validation failure, no-compatible-model, busy/low-memory peer,
  denied approval, revoked identity and ambiguous-receipt paths are handled visibly.
- Retry/recovery reconciles uncertain work before creating another attempt; duplicate canonical
  writes are prevented.
- Status UI shows real model, device, stage, queue/failure state and routing reason.
- Sovereignty evidence distinguishes enforcement from observation.
- Scoped independent public-egress evidence is captured for representative local and paired
  workflows; unavailable evidence remains unavailable.
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

Produce the first defensible **Refinix Beta 0.1 / SIH Reviewer Preview** from the integrated product.

## Phase 5 required outcomes

- Publish an exact supported OS/edition/architecture/backend/capability matrix containing at least
  one qualified profile in each of Windows, macOS and Linux.
- Build immutable packages from one designated source version/commit.
- Verify shipped source/resources, dependency/model manifests, notices, integrity and platform
  signing/notarisation requirements.
- Nondeveloper journey:
  website candidate -> package -> install -> hardware detection -> model setup/import -> self-test ->
  standalone work -> trusted pairing -> remote work -> validated Code path.
- Test first launch/relaunch, missing/denied dependencies/permissions, insufficient disk,
  cancellation, unsupported capability and uninstall/data preservation.
- Exercise Settings -> Models after onboarding.
- Rehearse authenticated **manual full-package replacement and recovery** on every published Beta
  profile. Beta 0.1 does not require a finished in-app updater.
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

- smarter fleet scheduling, queue/transfer estimates and fairness across requesting users/workspaces;
- stronger recovery/performance/Proof Card UX and measured cache tuning;
- hybrid semantic + lexical retrieval, corpus lifecycle and curated memory;
- additional qualified models and calibrated recommendation scoring;
- more OS/hardware/backend/sandbox profiles;
- explicit **Settings -> Updates** workflow with authenticated connected check/download/install and
  verified offline update import.

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
