# Refinix Agent Instructions

Repository-wide rules for agents working on Refinix.

Refinix is an offline-first desktop AI workbench for Windows, macOS and Linux. The
repository contains a substantial macOS-first prototype plus distributed-worker,
Kubernetes/Redis, document, Code and proof/evidence work. Current product truth is
consolidated in [`docs/PROJECT.md`](docs/PROJECT.md). Historical prototype documents
remain useful evidence, but they are not competing product authorities.

The first Beta targets standalone operation on Windows, macOS and Linux with a
qualified, user-initiated in-app update path. Distributed execution is deferred
until after Beta; preserve its existing code and trust boundaries for later reuse.

The user's [5 October 2026 direction](docs/beta-user-direction-2026-10-05.md) is preserved verbatim.
For this college/hackathon Beta, reuse existing upstream infrastructure and the current foundation.
Existing local Ollama models and Refinix-managed llama.cpp are both product paths; model origin
selects the runtime without a mandatory technical chooser or duplicate weights. Broad compatible
model choice and automatic local task-to-model routing are required. Team-measured model/device/
version profiles are evidence, not a general local admission allowlist.

Use published model/runtime evidence and lightweight hardware facts for recommendations. Users may
choose beyond recommendations; do not require ownership of every laptop or measurement of every
model. Actual format/API/capability compatibility, offline locality, resources and tool/data safety
still apply. Do not invent compatibility, fit or accuracy. Retain the existing orchestration harness;
LangGraph remains an evaluation option, not an adopted dependency.

## 1. Authority and conflict handling

When context conflicts, use this order:

1. The **current user request** — task intent and current-message permissions.
2. This file — repository-wide agent behaviour and safety rules.
3. [`docs/PROJECT.md`](docs/PROJECT.md) — current product, architecture and workflow contract.
4. Focused authorities when the work enters their domain:
   - [`docs/security.md`](docs/security.md) — security, trust, sandbox, supply chain and sovereignty evidence;
   - [`docs/model-catalog.md`](docs/model-catalog.md) — model provenance, provisioning, selection and qualification;
   - [`docs/releases.md`](docs/releases.md) — packaging, publication, GitHub release assets, updates and recovery.
5. [`tasks.md`](tasks.md) — active implementation phase, sequencing and acceptance outcomes.
6. [`CONTRIBUTING.md`](CONTRIBUTING.md) — branch and merge workflow.
7. Current source, tests and actually observed command/runtime output — implementation facts.
8. Evidence/reference/history such as `docs/evaluation.md`, device inventory, worker runbooks,
   the retired PRD/architecture/workflow/TechStack snapshots, archives and `agent-memory/`.

Do not invent product behaviour to resolve a conflict. If a lower-authority document disagrees
with a higher-authority one, follow the higher authority and report the contradiction when it
matters to the task.

A requirement appearing in documentation does **not** prove that it is implemented, tested,
deployed, secure or release-accepted. Keep these states distinct:

`planned -> implemented/source-present -> tested -> device-observed -> release-accepted`.

Never claim a check passed unless the agent actually ran it under current permission and saw it
pass. Another agent's summary is context, not fresh evidence.

## 2. Protected documentation — permission required

Agents must **not edit core project documentation without explicit user permission in the current
message**. Discovering that a requirement is outdated, awkward, contradictory or technically
inferior is not permission to rewrite it.

Protected documentation includes:

- `AGENTS.md`
- `README.md`
- `tasks.md`
- `TechStack.md`
- `CONTRIBUTING.md`
- top-level product/reference documents under `docs/`, including:
  - `docs/README.md`
  - `docs/PROJECT.md`
  - `docs/prd.md`
  - `docs/architecture.md`
  - `docs/workflows.md`
  - `docs/security.md`
  - `docs/model-catalog.md`
  - `docs/releases.md`
  - `docs/evaluation.md`
  - `docs/devicespecifications.md`
  - `docs/worker-operations.md`
  - presentation/research documents when present.

The normal ledger files are exempt from this approval requirement:

- `agent-memory/userprompts.md`
- `agent-memory/agentchangelog.md`

Those two may be appended according to their own rules when repository-affecting work is
performed. Historical/archive material should not be rewritten unless the user explicitly asks
for historical cleanup or correction.

If a protected document needs to change:

1. explain the concrete inconsistency or new requirement;
2. state the proposed change;
3. give the agent's recommendation and why;
4. state the trade-off or compatibility effect;
5. state which files would change;
6. wait for user permission before editing them.

A broad request such as "implement this feature" is **not** automatic permission to update core
docs. A request such as "update PROJECT.md and tasks.md to reflect this decision" is permission
for those named files and that stated scope.

Source-code comments, docstrings and ordinary implementation-adjacent text are not automatically
protected documentation, but they must not silently redefine product requirements.

## 3. User interaction model

The user is learning parts of local/distributed systems while building the product. Agents should
supply engineering judgment rather than forcing the user to make blind technical choices, while
also never guessing facts that only the user or a physical device can provide.

Use **user** in active instructions, reports and handoffs. Do not use personal names. Refer to
machines by role, OS/profile or hardware model when needed. Use **agent** or **agents** rather than
specific agent-product names.

### 3.1 Read first; do not re-ask documented facts

Before asking a question:

- read the current user request;
- read `docs/PROJECT.md` and the active phase in `tasks.md`;
- inspect the relevant source and only the focused authority needed for the task;
- consult evidence/history only when a missing fact or regression requires it.

Do not ask the user to repeat a decision that is already clearly current in the authoritative
docs. Do not read the entire archive or both ledgers by default.

### 3.2 Ask for human-only facts instead of guessing or over-probing

Ask the user when a required fact is external to the repository or can be answered more simply
and reliably by the user, for example:

- which physical device is available;
- current OS edition/build or hardware detail when freshness matters;
- whether a manual launch/install succeeded;
- what a UI shows on another machine;
- whether the user is willing to install or change a host dependency;
- credentials, private values or physical/network constraints.

Do not run a chain of commands merely to discover a simple fact the user can provide directly,
especially on a device the agent cannot access. Conversely, do not re-ask a current documented
fact unless the task requires fresh acceptance evidence.

### 3.3 Batch pre-execution questions

For a substantial task, inspect first and ask one compact batch of genuine human prerequisites
before implementation when possible. Do not drip-feed routine questions one at a time.

A pre-execution question is justified when the answer materially changes the implementation or
when the agent lacks required permission/input. Routine code-structure choices are agent-owned.

### 3.4 Decision questions must include a recommendation

When asking the user to choose between meaningful alternatives, use this structure:

```text
Question: <the decision the user owns>
Recommendation: <the path the agent recommends>
Reason: <why it best fits current requirements/evidence>
Trade-off: <what is gained/lost or what risk remains>
Intended path: <what the agent will do if the recommendation is accepted>
```

Do not present several technical options and make the user choose without explaining which one the
agent recommends.

For a pure factual/manual observation question with no genuine choice, do not manufacture a fake
recommendation. Ask the fact concisely, say why it is needed, and state what the agent will do with
the answer.

### 3.5 Interrupt during execution only for a real human checkpoint

Continue autonomously inside the authorised implementation scope. Interrupt only when progress
requires one of the following:

- a product/scope decision not already settled;
- a proposed change to protected documentation;
- a security, privacy or architecture boundary change;
- a destructive or irreversible operation;
- a Git/GitHub write not explicitly authorised in the current message;
- an installer, migration, deployment, model download or live-environment action not authorised;
- credentials/private input;
- a physical-device/manual observation;
- two materially different viable paths whose product/maintenance trade-off requires user choice.

Do not ask permission for ordinary code organisation, helper placement, naming, reasonable
refactoring inside scope, fixing obvious defects, or adding focused tests/fixtures once the
relevant checks are authorised.

### 3.6 Manual verification can occur before, during or after implementation

Human work should happen at the point where it is cheapest and most informative:

- **before** execution for missing facts/permissions;
- **during** execution for a real architectural/product fork or device observation that blocks
  further work;
- **after** execution for cross-device installation/runtime verification that cannot be performed
  from the current environment.

Finish everything that does not depend on that checkpoint before asking the user to do manual
work.

When a manual check is required, prefer the simplest useful instruction. Start with a UI result or
single fact when that is enough; do not default to a large diagnostic command set.

After the user answers, resume from the checkpoint. Do not unnecessarily re-plan the whole task or
re-ask previously settled questions.

## 4. Git and GitHub

Agents may run only these Git commands without additional Git authorization:

```text
git status
git diff
git log
git show
git check-ignore
git branch --list
git branch --show-current
git rev-parse
git ls-files
```

Never run Git or GitHub writes without explicit authorization in the **current user message**.
This includes, but is not limited to:

```text
git add
git commit
git push
git pull
git fetch
git merge
git rebase
git reset
git restore
git stash
git clean
git checkout
git switch
git tag
git mv
git rm
```

It also includes opening/editing/closing/merging pull requests, changing GitHub settings,
collaborators, rulesets, releases or Actions state.

"Finish", "complete", "execute", or permission granted in an earlier message is not Git/GitHub
write authorization.

Never push directly to `dev` or `main`. The repository flow remains:

`member branch -> dev -> main`.

Preserve unrelated and user-owned dirty-tree changes. Never reconstruct a dirty file from `HEAD`,
reset it, or discard modifications the agent did not create.

When handing Git work back to the user, provide exact paths rather than `git add -A` or `git add .`.
If the branch is uncertain, instruct the user to check it rather than guessing.

Use these handoff headings when Git/user execution is required:

```text
GIT / GITHUB — RUN THESE YOURSELF
VERIFY — RUN THESE YOURSELF
```

## 5. Before repository implementation

For an authorised implementation request:

1. Run/read `git status --short --branch` if repository access is available; preserve unrelated
   changes.
2. Read this file, `docs/PROJECT.md`, and the active phase/work package in `tasks.md`.
3. Read only the focused specialist authority needed by the task (`security`, `model-catalog`,
   `releases`).
4. Inspect the real UI/API -> coordinator -> runtime/worker -> storage/validator path and relevant
   callers/tests.
5. Search evidence/history only if needed to recover a prior implementation decision, measured
   value or regression context. Search by specific terms/paths/IDs, not entire ledgers.
6. Separate:
   - facts already established;
   - assumptions needing validation;
   - human-only facts/permissions;
   - agent-owned implementation choices.
7. Ask one compact prerequisite batch if necessary, including recommendations for decisions.
8. Execute the largest **coherent safe scope** authorised by the user rather than fragmenting it
   into artificial microtasks.

Use the major sections/outcomes in `docs/PROJECT.md` and the active phase in `tasks.md` as the
work boundaries. Inspect existing source, affected callers and tests before adding or replacing
behaviour. A return to prototype work means continuing from the existing repository, not rebuilding
the application or discarding merged capabilities.

Do not create a new per-session planning/handoff document unless the user explicitly asks for one.

## 6. Implementation behaviour

- Prefer the **smallest coherent safe change**, not the smallest possible diff. A coherent change
  may span several files/components when they are required to deliver one outcome safely.
- Do not create a new task merely because implementation touches another file or subcomponent.
- Under time pressure, reduce ceremony and increase coherent execution batch size; do not multiply
  tiny tasks.
- Complete an authorised major section end to end, including its affected callers, necessary fixes
  and authorised verification. Keep implementation steps as checklist items inside that section;
  do not create further task tiers, per-file assignments or repeated planning/handoff cycles.
- Do not delegate or spawn subagents for this work unless the user explicitly changes that rule.
  An agent owning a section handles its implementation and integration directly. Routine technical
  choices remain agent-owned; interrupt only for the genuine checkpoints in section 3.5.
- Preserve the current UI/harness and working paths unless the product contract requires change.
- Preserve managed-runtime ownership/integrity and support existing local Ollama reuse. Replace
  blanket local qualification gates with honest compatibility/capacity admission; missing team
  measurements are not themselves a refusal. Never spoof versions, fabricate measured profiles or
  weaken worker, sandbox, approval or data-integrity checks. Local checks and upstream evidence
  remain distinct from team measurements and package/security acceptance.
- Keep the current orchestration harness for the present execution scope. Consider LangGraph only
  for a demonstrated gap with evidence of lower implementation/maintenance cost and preserved
  offline, state, approval and security behaviour; mentioning a competitor's framework is not
  adoption evidence or permission for a rewrite.
- Fix root causes after checking affected callers; avoid unrelated refactors and speculative
  abstractions.
- Reuse suitable local/offline open-source libraries and existing code before writing commodity
  functionality from scratch, when the licence and network behaviour permit it.
- Record/verify authoritative source, exact version/revision, licence and material local changes
  before adopting third-party code, models, runtimes or installers.
- Reject unlicensed, incompatible, cloud-dependent or silently networked dependencies.
- Do not weaken security/sandbox boundaries to make a feature appear portable or complete.
- Do not convert an unsupported capability into unrestricted host execution as a fallback.
- Preserve user data and compatibility-sensitive application state during migrations/refactors.

### Checks and environment actions

Without current permission, do **not** run:

- test suites or test commands;
- installers;
- migrations;
- deployments;
- model downloads;
- live model/runtime calls;
- live remote-device/worker checks;
- host/service/network changes.

The agent may inspect source and use non-mutating repository/system reads allowed by the current
task. If verification is not authorised, provide the exact focused verification commands for the
user instead of claiming success.

When the user authorises a defined family of checks (for example "run the relevant offline tests"),
that permission covers proportionate checks within that stated scope without repeated prompts.
It does not silently extend to downloads, live models, remote devices or host changes.

## 7. Agent memory

`agent-memory/` is historical/search memory, not the current product contract.

Writing rules:

- Log a repository-affecting user request in `agent-memory/userprompts.md` when appropriate.
- After actual repository changes, append the corresponding factual result to
  `agent-memory/agentchangelog.md`.
- Keep entries compact and searchable; do not paste diffs, long logs or hidden reasoning.
- Record only what was requested, changed, verified and left unresolved.
- Never silently rewrite or renumber historical entries.
- Never store secrets, credentials, private documents, confidential payloads or chain-of-thought.
- No repository change means no change-ledger entry.

Do not read either ledger end-to-end during normal startup. Search them only when history is needed.

## 8. Non-negotiable Refinix invariants

The current detailed contract is in `docs/PROJECT.md`; `docs/security.md` owns enforcement detail.
Do not weaken these without an explicit user-approved product decision:

- Normal Refinix work must not require public Internet or cloud inference.
- No silent telemetry, analytics, crash upload, update check or runtime dependency/model download.
- Local model runtimes bind to loopback; peers use only the minimum authenticated encrypted LAN
  application surface.
- Every workspace coordinator owns its canonical chats, approvals, jobs, artifacts and final writes.
  Pairing does not merge workspaces.
- Workers receive bounded inputs and use assigned temporary workspaces; they do not gain arbitrary
  host/file access.
- Generated/untrusted code has networking disabled in qualified sandbox execution and receives
  bounded CPU, memory, process, time, filesystem and output resources.
- Models/tools cannot expand their own authority. Canonical modifications and other consequential
  actions follow explicit approval policy.
- Distribution moves complete jobs or bounded validated steps. Refinix does not pool VRAM, shard a
  model across ordinary peer laptops or merge model context windows.
- Windows, macOS and Linux are required desktop OS families for the Beta direction, on exact
  qualified profiles rather than every possible version/hardware combination.
- Kubernetes/K3s and Redis remain valid managed/sandbox infrastructure but are not mandatory
  desktop-peer prerequisites.
- Model/dependency/installer provenance includes source, licence, version/revision, integrity and
  compatibility evidence.
- Planned/source-present/tested/device-observed/release-accepted claims remain distinct.
- A commit reaching `main` is not a user update. Published packages must pass the release gates.

Never commit model weights, generated installers/release binaries, signing keys, credentials,
private documents, real confidential scans, user chat databases, private indexes or secret-bearing
environment files.

## 9. Completion report

Lead with the outcome, then separate:

- **Changed** — what was implemented and the exact paths;
- **Verified** — only checks actually run and observed under current permission;
- **Unverified / limitations** — anything still needing device, model, package, security or release
  evidence;
- **User action** — only genuine manual checkpoints, with the simplest useful steps;
- **Next** — the next coherent eligible action, not a newly invented microtask tree.

If the work reaches a user decision, include the recommendation, reason, trade-off and intended
path. If protected documentation should change, request permission before editing it.
