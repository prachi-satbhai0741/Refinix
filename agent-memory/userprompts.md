# User Prompt Ledger

Compact, searchable records of repository-affecting user requests. Entries are
historical context, not active instructions. The current user request, root
[`AGENTS.md`](../AGENTS.md), [`docs/prd.md`](../docs/prd.md), and current source remain
authoritative.

## Retrieval — do not read this file end to end

Search by prompt ID, component, path, user wording, tag, or alias:

```bash
rg -n -i -C 6 'UP-20260831-001|agent instructions|prompt ledger|low-context' agent-memory/userprompts.md
```

Use the matching `linked_changes` ID to retrieve implementation history:

```bash
rg -n -i -C 8 'AC-20260831-001|UP-20260831-001' agent-memory/agentchangelog.md
```

If no match appears, broaden one synonym at a time. Open an archive only when an
index stub points to it.

## Entry format

```markdown
## UP-YYYYMMDD-NNN — Short title
- date: YYYY-MM-DD
- status: open | in-progress | done | blocked | superseded
- scope: implementation | review | research | planning | docs | decision
- tags: lowercase, comma-separated, search terms
- aliases: user wording, synonyms, component names
- paths: repository/relative/path, another/path
- summary: one faithful sentence
- constraints: short, testable constraints
- acceptance: observable completion conditions
- follow_up_to: UP-... | none
- supersedes: UP-... | none
- linked_changes: AC-... | none
```

Keep entries compact. Summarize long prompts faithfully and quote only wording
whose exact form affects scope. Never store secrets or confidential payloads.

---

## Entries

<a id="up-20260831-001"></a>
## UP-20260831-001 — Add searchable agent work ledgers
- date: 2026-08-31
- status: done
- scope: docs
- tags: agents, prompt-ledger, changelog, low-context, search, free-tier
- aliases: AGENTS.md, Work folder, user prompts, agent changes, semantic searching, Antigravity, OpenCode, limited context
- paths: AGENTS.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Create repository agent guidance plus compact interlinked prompt and change histories that low-limit agents can retrieve without reading entire files.
- constraints: Unlike the VNEC changelog; record only each request and its actual repository changes; remain small and easy to search as history grows.
- acceptance: Stable IDs, reciprocal links, tags, aliases, bounded entry templates, targeted retrieval commands, and a deferred archive policy exist.
- follow_up_to: none
- supersedes: none
- linked_changes: [AC-20260831-001](agentchangelog.md#ac-20260831-001)

<a id="up-20260831-002"></a>
## UP-20260831-002 — Run automated PR checks only for releases
- date: 2026-08-31
- status: done
- scope: decision, implementation, docs
- tags: ci, github-actions, pull-request, dev, main, release-gate
- aliases: CI only for main, checks only dev to main, no CI on member PRs, release checks
- paths: .github/workflows/pr-flow-guard.yml, .github/workflows/no-direct-push.yml, .github/pull_request_template.md, scripts/setup-branch-protection.sh, CONTRIBUTING.md, .github/CODEOWNERS, docs/prd.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Run automated PR checks only for the `dev` to `main` release PR, while leaving member to `dev` integration without CI.
- constraints: Preserve PR-only flow, run no GitHub Actions on `dev`, and keep reviews optional.
- acceptance: Both workflows trigger only for `main`, future required status checks apply only to `main`, and repository guidance states that `dev` PRs and pushes have no automated checks.
- follow_up_to: none
- supersedes: none
- linked_changes: [AC-20260831-002](agentchangelog.md#ac-20260831-002)

<a id="up-20260901-001"></a>
## UP-20260901-001 — Minimal repository foundation and agent memory rename
- date: 2026-09-01
- status: done
- scope: implementation, docs, decision
- tags: agent-memory, docs, gitignore, github-actions, repository-structure, git-safety
- aliases: rename Work folder, move prd under docs, backend frontend readme, simplify gitignore, filesystem edits only, no git operations, main-only actions
- paths: agent-memory/, docs/, backend/, frontend/, CLAUDE.md, .gitignore, AGENTS.md, CONTRIBUTING.md, .github/CODEOWNERS, scripts/setup-branch-protection.sh
- summary: Build a minimal, navigable repository foundation without speculative scaffolding, and confirm the main-only GitHub Actions policy.
- constraints: Filesystem edits only, no Git or GitHub state changes; preserve all existing dirty-tree work as user-owned; no network access; no framework scaffolding, package manifests, or empty architecture documents.
- acceptance: `Work/` is `agent-memory/` with a start-here README; root `prd.md` is `docs/prd.md`; `backend/` and `frontend/` hold boundary READMEs only; `.gitignore` is minimal and hides no plausible source; a root `CLAUDE.md` carries the Git-safety bootstrap; no workflow triggers for `dev`; every path reference is updated.
- follow_up_to: [UP-20260831-002](#up-20260831-002)
- supersedes: none
- linked_changes: [AC-20260901-001](agentchangelog.md#ac-20260901-001)

<a id="up-20260901-002"></a>
## UP-20260901-002 — Apply review findings on workflows, PRD link, and gitignore
- date: 2026-09-01
- status: done
- scope: review, implementation, docs
- tags: github-actions, actions-minutes, gitignore, anchoring, broken-link, review-fix
- aliases: delete no-direct-push, remove push workflow, checks only on PR to main, anchor gitignore folders, prd contributing link
- paths: .github/workflows/no-direct-push.yml, CONTRIBUTING.md, .gitignore, docs/prd.md, scripts/setup-branch-protection.sh, agent-memory/README.md
- summary: Apply three review findings: remove the push-triggered audit workflow, repair the PRD's CONTRIBUTING link after the move, and anchor root-only data folders in `.gitignore`.
- constraints: Filesystem edits only, no Git or GitHub state changes; keep `pr-flow-guard` as the sole workflow; do not anchor dependency or build directories that legitimately nest under `backend/` and `frontend/`.
- acceptance: No workflow triggers on any push; `pr-flow-guard` remains the only required main check; zero broken relative links; root data folders ignored while same-named source directories at depth are not.
- follow_up_to: [UP-20260901-001](#up-20260901-001)
- supersedes: none
- linked_changes: [AC-20260901-002](agentchangelog.md#ac-20260901-002)

<a id="up-20260901-003"></a>
## UP-20260901-003 — Keep tool-specific agent files local
- date: 2026-09-01
- status: done
- scope: docs, decision
- tags: gitignore, claude, codex, agent-instructions, local-only
- aliases: ignore claude.md, ignore codex.md, local agent files
- paths: .gitignore, docs/README.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Keep Claude- and Codex-specific root instruction files local while retaining `AGENTS.md` as the shared repository guidance.
- constraints: Ignore uppercase and lowercase spellings for cross-platform consistency; do not change the local files' contents.
- acceptance: `CLAUDE.md`, `claude.md`, `CODEX.md`, and `codex.md` are ignored and absent from the normal untracked-file status.
- follow_up_to: [UP-20260901-001](#up-20260901-001)
- supersedes: none
- linked_changes: [AC-20260901-003](agentchangelog.md#ac-20260901-003)

<a id="up-20260901-004"></a>
## UP-20260901-004 — Consolidate shared repository rules and drop CODEOWNERS
- date: 2026-09-01
- status: done
- scope: docs, decision
- tags: agents-md, git-safety, rules, codeowners, review-requests, consolidation
- aliases: shared rules in agents.md, no new rules file, single agent instruction file, remove codeowners, stop review requests, git allowlist
- paths: AGENTS.md, .github/CODEOWNERS, CONTRIBUTING.md, docs/prd.md, scripts/setup-branch-protection.sh, agent-memory/README.md
- summary: Keep shared AegisForge obligations in the tracked `AGENTS.md` and remove `CODEOWNERS` so opening a pull request stops requesting reviews.
- constraints: One tracked instruction file, no separate `docs/RULES.md`; include repository dos and don'ts only; exclude personal slash commands, modes, skills, plugins, tool preferences, and reviewer-assignment machinery; tool-local `CLAUDE.md` and `CODEX.md` stay ignored.
- acceptance: `AGENTS.md` carries repository Git boundaries, agent-memory rules, implementation safety, and AegisForge invariants without personal commands or operating modes; no `CODEOWNERS` file exists and no live reference to one remains.
- follow_up_to: [UP-20260901-003](#up-20260901-003)
- supersedes: none
- linked_changes: [AC-20260901-004](agentchangelog.md#ac-20260901-004)

<a id="up-20260901-005"></a>
## UP-20260901-005 — Add project README and propose a proof-first innovation
- date: 2026-09-01
- status: done
- scope: docs, product-decision
- tags: readme, prd, innovation, sovereignmesh, evidence
- aliases: root readme, PRD comment, sovereign proof card, proof-first differentiator
- paths: README.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Create a useful root README and provide a copyable PRD comment proposing a named, evidence-based differentiator.
- constraints: Keep the PRD unchanged; do not represent proposed capabilities as implemented or verified; preserve the repository's no-scaffolding status.
- acceptance: README describes the current planning-stage repository, links the PRD, states the project boundaries and security invariants, and labels innovations as proposed.
- follow_up_to: none
- supersedes: none
- linked_changes: [AC-20260901-005](agentchangelog.md#ac-20260901-005)

<a id="up-20260901-006"></a>
## UP-20260901-006 — Present the SIH challenge in the root README
- date: 2026-09-01
- status: done
- scope: docs, product-decision
- tags: readme, sih, sih26117, mrpl, sovereignmesh
- aliases: SIH problem statement 117, MRPL challenge, title description organisation
- paths: README.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Restructure the root README around the SIH Problem Statement 117 title, description, and sponsoring organisation.
- constraints: Use verified challenge metadata; do not add Taskboard/Docker claims or present planned capabilities as implemented.
- acceptance: README has a centered project header, accurate SIH26117/MRPL metadata, a concise challenge description, and an honest planning-stage project overview.
- follow_up_to: [UP-20260901-005](#up-20260901-005)
- supersedes: none
- linked_changes: [AC-20260901-006](agentchangelog.md#ac-20260901-006)

<a id="up-20260901-007"></a>
## UP-20260901-007 — Team device specification inventory
- date: 2026-09-01
- status: done
- scope: docs, research
- tags: hardware, device-specs, model-selection, gpu, vram, capability-packs, benchmarks
- aliases: devicespecifications.md, device specs, team laptops, hardware inventory, model fit, rtx, macbook m5, fleet, nvidia-smi
- paths: docs/devicespecifications.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Collect the six team members' device hardware into a document that drives model selection and capability-pack assignment.
- constraints: Treat model and capability notes as hypotheses until benchmarked; flag unreported fields rather than guessing them; do not edit the PRD in this change.
- acceptance: A device specification document lists all six devices with a summary table, per-device detail, tentative capability mapping, and an open-items list.
- follow_up_to: none
- supersedes: none
- linked_changes: [AC-20260901-007](agentchangelog.md#ac-20260901-007)

<a id="up-20260901-008"></a>
## UP-20260901-008 — Confirm remaining device specs and align the PRD hardware table
- date: 2026-09-01
- status: done
- scope: docs, research
- tags: hardware, device-specs, model-selection, gpu, vram, prd, capability-packs
- aliases: sahil specs, tanvi specs, rtx 3050 6gb, lenovo loq, dell inspiron, prd section 12, hardware table, adapterram
- paths: docs/devicespecifications.md, docs/prd.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Fold Sahil's and Tanvi's reported hardware into the device inventory and replace the hardware specifications in the PRD section 12 table so both documents agree.
- constraints: The device inventory is the reference for specifications, not the PRD; keep capability assignments labelled as hypotheses; do not alter PRD sections other than the hardware table.
- acceptance: All six devices carry confirmed CPU, RAM, GPU, and storage in the inventory; PRD section 12 lists all six with matching specifications and links to the inventory.
- follow_up_to: [UP-20260901-007](#up-20260901-007)
- supersedes: none
- linked_changes: [AC-20260901-008](agentchangelog.md#ac-20260901-008)

<a id="up-20260901-009"></a>
## UP-20260901-009 — Review device inventory and require open-source reuse
- date: 2026-09-01
- status: done
- scope: review, repository-guidance
- tags: device-specs, code-review, open-source, reuse, licensing, offline-runtime
- aliases: vedant recent push, reuse github code, local open source libraries, prototype acceleration
- paths: docs/devicespecifications.md, docs/prd.md, AGENTS.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Review Vedant's latest merged device-inventory change and require prototype work to reuse suitable local/offline open-source components before rebuilding commodity functionality.
- constraints: Do not import competing SIH solutions; accept only licence-compatible components with provenance and no required cloud or silent network behavior; keep the review separate from fixes.
- acceptance: Report actionable findings against merge `f4f0b62` and add the reusable-component policy to `AGENTS.md` without altering the reviewed device documentation.
- follow_up_to: none
- supersedes: none
- linked_changes: [AC-20260901-009](agentchangelog.md#ac-20260901-009)

<a id="up-20260901-010"></a>
## UP-20260901-010 — Correct reviewed device-inventory claims
- date: 2026-09-01
- status: done
- scope: docs, correction
- tags: device-specs, evidence, macbook, cuda, storage, prd
- aliases: fix needs fix, vedant review fixes, gpu configuration, cuda prerequisites, model capacity
- paths: docs/devicespecifications.md, docs/prd.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Correct the evidence status, Mac GPU configuration, NVIDIA prerequisites, and storage-capacity wording found in the review of Vedant's merged device inventory.
- constraints: Preserve tentative capability assignments; do not install runtimes, probe hardware, download models, or expand the architecture.
- acceptance: Unmeasured facts are labelled honestly, CUDA requirements are runtime-specific, 3–5 models is a prototype policy rather than a disk limit, and the PRD matches the inventory.
- follow_up_to: [UP-20260901-009](#up-20260901-009)
- supersedes: none
- linked_changes: [AC-20260901-010](agentchangelog.md#ac-20260901-010)

<a id="up-20260901-011"></a>
## UP-20260901-011 — Add private-server execution objective
- date: 2026-09-01
- status: done
- scope: docs, product-decision
- tags: prd, topology, standalone, trusted-mesh, private-server, scope
- aliases: one system multisystem server, private compute worker, three execution topologies
- paths: docs/prd.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Make private-server execution an explicit third product topology alongside standalone and trusted-device mesh operation.
- constraints: Treat the server as a worker using the existing job contract; preserve coordinator-owned canonical state, zero-cloud runtime, and the standalone-then-mesh SIH build order; defer a fully server-hosted multi-user control plane.
- acceptance: The executive summary, product thesis, use cases, principles, release scope, non-goals, and functional requirements consistently record the objective without making it an SIH MVP requirement.
- follow_up_to: none
- supersedes: none
- linked_changes: [AC-20260901-011](agentchangelog.md#ac-20260901-011)

<a id="up-20260901-012"></a>
## UP-20260901-012 — Reframe the product as a local agent harness
- date: 2026-09-01
- status: done
- scope: docs, product-decision, architecture
- tags: agent-harness, onboarding, workflows, model-packs, control-center, dynamic-nodes, prd-split
- aliases: local ChatGPT app, chat code documents sections, mandatory model setup, no permanent device role, distributed PRD
- paths: docs/, README.md, AGENTS.md, CONTRIBUTING.md, backend/README.md, frontend/README.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Reframe AegisForge as one local agent harness with task-specific surfaces, guided model onboarding, dynamic compute participation, and a local Control Center, then split the oversized PRD into focused documents.
- constraints: Every installation remains locally usable; pairing is reversible and never silently merges canonical state; required downloads depend on enabled capabilities; preserve offline, security, evidence, and licence boundaries; avoid speculative services and duplicate documentation.
- acceptance: The compact PRD defines the product and priorities; focused architecture, workflow, security, model, and evaluation documents own implementation detail; all repository references match the new document boundaries.
- follow_up_to: [UP-20260901-011](#up-20260901-011)
- supersedes: none
- linked_changes: [AC-20260901-012](agentchangelog.md#ac-20260901-012)

<a id="up-20260902-001"></a>
## UP-20260902-001 — Create the fast execution roadmap
- date: 2026-09-02
- status: done
- scope: docs, execution-planning
- tags: tasks, roadmap, internal-hackathon, distributed, integration, finals
- aliases: tasks.md, fast execution plan, claude implementation, codex review, five day sprint, twelve day sprint
- paths: tasks.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Create one operational roadmap that keeps a real distributed path in the internal-hackathon scope and carries the proven baseline into a twelve-day finals sprint.
- constraints: Preserve the user's uncommitted `docs/README.md`; do not create runtime scaffolding or claim planned work is implemented; keep task-level distribution, canonical coordinator ownership, offline operation, bounded workers, and daily integration gates.
- acceptance: `tasks.md` defines task IDs, owners, dependencies, five-day gates, the twelve-day follow-through, implementer/reviewer handoff rules, and an evidence-backed definition of done without duplicating focused product specifications.
- follow_up_to: [UP-20260901-012](#up-20260901-012)
- supersedes: none
- linked_changes: [AC-20260902-001](agentchangelog.md#ac-20260902-001)

<a id="up-20260902-002"></a>
## UP-20260902-002 — Rebalance tasks for paid-agent access
- date: 2026-09-02
- status: done
- scope: docs, execution-planning, ownership
- tags: tasks, ownership, claude-pro, codex-plus, free-tier, team-capacity
- aliases: aditya vedant build, antigravity free tier, nonblocking support tasks, paid agent seats
- paths: tasks.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Assign critical-path implementation to Aditya and Vedant, who have Claude Pro and Codex Plus, while giving the other four teammates bounded operational, fixture, evaluation, evidence, and demo responsibilities.
- constraints: Every teammate must own useful acceptance evidence; no core implementation dependency may assume paid-agent access outside Aditya and Vedant; preserve the five-day distributed target and existing security boundaries.
- acceptance: The ownership map and all AF task rows distinguish build owners from support or evidence owners, with every build task led by Aditya or Vedant and meaningful nonblocking work assigned to Sahil, Yug, Prachi, and Tanvi.
- follow_up_to: [UP-20260902-001](#up-20260902-001)
- supersedes: none
- linked_changes: [AC-20260902-002](agentchangelog.md#ac-20260902-002)

<a id="up-20260902-003"></a>
## UP-20260902-003 — Apply the reviewed documentation corrections
- date: 2026-09-02
- status: done
- scope: docs, execution-planning, repository-scaffolding
- tags: stale-references, models, hardware, fallback, manifests
- aliases: claude review corrections, qwen vision, day two kill switch, hardware owners, prd references
- paths: .github/pull_request_template.md, .gitignore, agent-memory/README.md, docs/model-catalog.md, docs/devicespecifications.md, tasks.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Apply only the accepted documentation corrections from the external review without adding new workflows or implementation scope.
- constraints: Preserve the mesh as a differentiator with a Day-2 fallback; retain active agent memory; do not add P&ID, PPT, Excel, calculation, or runtime-framework work.
- acceptance: References target current documents; Qwen3.5-4B vision remains evidence-labelled; catalogue loading is manifest-driven; all hardware checks have owners; failed Day-2 streaming cannot block the standalone signature workflows.
- follow_up_to: [UP-20260902-002](#up-20260902-002)
- supersedes: none
- linked_changes: [AC-20260902-003](agentchangelog.md#ac-20260902-003)

<a id="up-20260902-004"></a>
## UP-20260902-004 — Close the remaining reviewed corrections
- date: 2026-09-02
- status: done
- scope: docs
- tags: review-followup, multilingual, hardware-evidence, problem-statement, traceability
- aliases: remaining claude review items, yug multilingual FR, FR-037, vedant disk space, PS coverage
- paths: docs/prd.md, docs/evaluation.md, docs/model-catalog.md, docs/devicespecifications.md, tasks.md
- summary: Apply the reviewed corrections Codex did not cover, integrate the multilingual requirement into the PRD structure, and replace unmeasured hardware figures with locally measured ones.
- constraints: Do not add sprint scope that AF ownership already excluded; record each excluded problem-statement line as a decision instead; do not reassign teammates' tasks; documentation only, no runtime claims.
- acceptance: No orphaned requirement block or dangling FR id remains; multilingual scope carries a numbered outcome and candidate models with licence caveats; Vedant hardware figures match local command output; every problem-statement line has a recorded coverage decision.
- follow_up_to: [UP-20260902-003](#up-20260902-003)
- supersedes: none
- linked_changes: [AC-20260902-004](agentchangelog.md#ac-20260902-004)

<a id="up-20260902-005"></a>
## UP-20260902-005 — Align the five-day build with the mentor infrastructure
- date: 2026-09-02
- status: done
- scope: docs, architecture, execution-planning, security
- tags: kubernetes, docker, pods, service-api, redis, five-day-sprint
- aliases: mentor infrastructure, friday implementation plan, k3s worker, redis queue, parallel agents
- paths: docs/prd.md, docs/architecture.md, docs/security.md, docs/evaluation.md, tasks.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Replace the deferred Kubernetes and Redis position with a bounded five-day implementation plan that produces a usable mentor-aligned alpha.
- constraints: Keep standalone operation; use one Linux Kubernetes host rather than a speculative fleet cluster; keep SQLite canonical; use Redis only for bounded ephemeral coordination; treat reported agent capacity as parallel assistance rather than verification.
- acceptance: The PRD, architecture, security model, evaluation gates, and task board agree on Docker-built worker images, Kubernetes Pods and Service exposure, Redis responsibilities, named owners, early-completion stretch gates, and a five-day frozen demo path.
- follow_up_to: [UP-20260902-004](#up-20260902-004)
- supersedes: none
- linked_changes: [AC-20260902-005](agentchangelog.md#ac-20260902-005)

<a id="up-20260902-006"></a>
## UP-20260902-006 — Create the SIH PPT submission research brief
- date: 2026-09-02
- status: done
- scope: docs, presentation, research
- tags: sih26117, ppt, portal-submission, research, judge-preparation
- aliases: SIH PPT brief, six slide deck, presentation workers, research papers, portal submission
- paths: docs/sih-ppt-submission-brief.md, docs/README.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Create one non-normative source brief that lets the presentation team build the official six-slide SIH26117 idea deck without turning pitch copy into the v1 product baseline.
- constraints: Separate official wording, repository decisions, research, assumptions, and unverified prototype claims; follow the official template; do not claim planned runtime behaviour as working.
- acceptance: The brief provides exact problem context, a six-slide content plan, architecture and mentor mapping, feasibility and impact, source/research library, evidence placeholders, claim controls, and judge Q&A.
- follow_up_to: [UP-20260902-005](#up-20260902-005)
- supersedes: none
- linked_changes: [AC-20260902-006](agentchangelog.md#ac-20260902-006)

<a id="up-20260902-007"></a>
## UP-20260902-007 — Start Day 1 with the shared contracts
- date: 2026-09-02
- status: in-progress
- scope: backend, contracts, execution
- tags: af-001, day-1, contracts, lifecycle, redis, events
- aliases: day 01, task.md, shared job envelope, contract freeze
- paths: backend/contracts/, backend/requirements.txt, backend/README.md, tasks.md, README.md, docs/prd.md, docs/evaluation.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Start Day 1 of tasks.md by implementing the AF-001 contract prerequisite for the coordinator, worker, UI, and cluster packets.
- constraints: Preserve coordinator authority and offline boundaries; do not run Git writes, tests, installers, deployments, or model downloads without permission; no runtime or hardware claims from schemas.
- acceptance: One versioned contract package defines payloads, lifecycle, HTTPS, SSE, Redis, idempotency, and evidence semantics with synthetic examples and a runnable check.
- verification_authorization: User explicitly approved repository .venv creation, pinned Pydantic installation from PyPI, and offline contract checks.
- follow_up_to: [UP-20260902-005](#up-20260902-005)
- supersedes: none
- linked_changes: [AC-20260902-007](agentchangelog.md#ac-20260902-007)

<a id="up-20260903-001"></a>
## UP-20260903-001 — Assign Yug the worker execution spine
- date: 2026-09-03
- status: done
- scope: docs, execution-planning, ownership
- tags: yug, claude, worker-spine, day-1, day-2, ownership
- aliases: huge task for Yug Claude, two builders, worker runtime Redis K3s, review handoff
- paths: docs/yug-worker-spine.md, docs/README.md, tasks.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Create a substantial implementation packet for Yug's Claude after his current contract review, with Aditya and Yug owning current implementation and Aditya/Codex reviewing the resulting changes.
- constraints: Planning only in this turn; preserve shared contracts and daily gates; keep other members' hardware/evidence roles; use member-to-dev-to-main publication; do not transfer prior local test/install permission to another machine or session.
- acceptance: A self-contained packet defines the worker/runtime/Redis/container/K3s outcome, allowed paths, review prerequisite, phases, acceptance commands, failure cases, permissions, and review evidence; the current sprint reflects two build owners.
- follow_up_to: [UP-20260902-007](#up-20260902-007)
- supersedes: none
- linked_changes: [AC-20260903-001](agentchangelog.md#ac-20260903-001)

<a id="up-20260903-002"></a>
## UP-20260903-002 — Execute the human-checkpoint documentation plan
- date: 2026-09-03
- status: in-progress
- scope: docs, execution-planning, agent-guidance
- tags: human-checkpoints, claude, codex, setup, five-day-sprint
- aliases: named human intervention, checkpoint chunks, remove personal packet, build review explain resume
- paths: AGENTS.md, tasks.md, docs/README.md, docs/yug-worker-spine.md, docs/architecture.md, docs/devicespecifications.md, docs/evaluation.md, backend/contracts/README.md, CONTRIBUTING.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Replace personal implementation assignments with reviewed execution chunks that pause for named human actions and resume only after their results are verified.
- constraints: Documentation only; preserve AF task evidence and product/security gates; no runtime implementation, installs, downloads, deployments, tests or Git writes; preserve device facts and historical ledgers.
- acceptance: One shared tasks.md names each human checkpoint, required commands/evidence, stop/resume rules and plain-language build reports; obsolete personal packet is removed and active references are consistent.
- follow_up_to: [UP-20260903-001](#up-20260903-001)
- supersedes: [UP-20260903-001](#up-20260903-001)
- linked_changes: [AC-20260903-002](agentchangelog.md#ac-20260903-002)

<a id="up-20260903-003"></a>
## UP-20260903-003 — Remove calendar constraints from execution
- date: 2026-09-03
- status: in-progress
- scope: docs, execution-planning
- tags: numbered-tasks, human-checkpoints, prerequisites, calendar-independent
- aliases: no days, task number and name, execute then wait for human, remove deadline schedule
- paths: tasks.md, AGENTS.md, CONTRIBUTING.md, README.md, backend/README.md, backend/contracts/README.md, frontend/README.md, docs/README.md, docs/prd.md, docs/architecture.md, docs/evaluation.md, docs/devicespecifications.md, docs/sih-ppt-submission-brief.md, .github/pull_request_template.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Replace implementation day labels and calendar cadence with numbered tasks, explicit prerequisites and named human stop/resume checkpoints.
- constraints: Preserve existing uncommitted documentation, AF task state/acceptance, named human actions, evidence dates, history and runtime safety deadlines; no runtime changes, tests, installations or Git writes.
- acceptance: Active planning references use task numbers/names with no delivery dates or day limits, and all local links and sequence dependencies remain consistent.
- follow_up_to: [UP-20260903-002](#up-20260903-002)
- supersedes: none
- linked_changes: [AC-20260903-003](agentchangelog.md#ac-20260903-003)

<a id="up-20260903-004"></a>
## UP-20260903-004 — Analyse the documents and execute the board
- date: 2026-09-03
- status: in-progress
- scope: backend, contracts, documents-workflow, execution
- tags: c01, af-001, contracts, citations, documents, grounding, page-mapping
- aliases: execute tasks.md, citation contract, cited approval note, reduced team
- paths: backend/contracts/v1.py, backend/contracts/test_contracts.py, backend/contracts/examples.json, backend/contracts/README.md, tasks.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Analyse the planning documents and begin executing the board with only Yug and Aditya available, closing the citation gap the merged AF-001 draft left in the documents workflow.
- constraints: Only Yug and Aditya are available, so role assignments are suspended for this change; no Git or GitHub writes; keep the contract version at 1.0 and preserve coordinator authority and offline boundaries.
- acceptance: The contract carries a typed citation with source and page, a coordinator-side grounding guard rejects ungrounded output, and the contract check runs and passes locally.
- verification_authorization: User instruction to execute tasks covered running the existing offline contract check; no installation, network access, or Git write was performed.
- follow_up_to: [UP-20260902-007](#up-20260902-007)
- supersedes: none
- linked_changes: [AC-20260903-004](agentchangelog.md#ac-20260903-004)

<a id="up-20260903-005"></a>
## UP-20260903-005 — Execute the renumbered C01 contract repairs
- date: 2026-09-03
- status: in-progress
- scope: backend, contracts, execution
- tags: c01, af-001, contracts, output-validators, cancellation, interruption, checkpoints
- aliases: numbered execution tasks, chunk C01, contract repair, human checkpoint, stop reason
- paths: backend/contracts/v1.py, backend/contracts/test_contracts.py, backend/contracts/README.md, tasks.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Execute the C01 contract repairs defined by the renumbered execution board, then report the human checkpoint actions the board requires before C02.
- constraints: Only Yug and Aditya are available; no Git or GitHub writes; keep contract version 1.0 and the draft status; do not activate a runtime chunk or advance past the C01 human checkpoint.
- acceptance: Output validators match their declared kind, stopped attempts carry a typed reason, citation payloads exist, and the focused contract check runs and passes locally.
- verification_authorization: User instruction to execute the board covered running the existing offline contract check; no installation, network access, or Git write was performed.
- follow_up_to: [UP-20260903-004](#up-20260903-004)
- supersedes: none
- linked_changes: [AC-20260903-005](agentchangelog.md#ac-20260903-005)

<a id="up-20260903-006"></a>
## UP-20260903-006 — Address the C01 review findings
- date: 2026-09-03
- status: in-progress
- scope: backend, contracts, execution, review
- tags: c01, af-001, code-review, citations, evidence-binding, retry, board-status
- aliases: NEEDS FIX, Codex review, PR 29, proof attempt binding, current scope note
- paths: backend/contracts/v1.py, backend/contracts/test_contracts.py, backend/contracts/README.md, tasks.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Address Codex's two C01 review findings on merge d50ea38 so citation evidence binds to one dispatched attempt and the board reports C01's real review stage.
- constraints: Stay inside C01; keep C02 locked and the contract at version 1.0; no Git or GitHub writes; do not claim a runtime or pinned-environment result that was not observed.
- acceptance: The guard rejects a proof whose workspace, job, attempt or target node differs from the envelope, each with its own check, and the current-scope note states C01's review stage and open human checkpoint.
- verification_authorization: User instruction to address the review covered running the existing offline contract check; no installation, network access, or Git write was performed.
- follow_up_to: [UP-20260903-005](#up-20260903-005)
- supersedes: none
- linked_changes: [AC-20260903-006](agentchangelog.md#ac-20260903-006)
<a id="up-20260903-007"></a>
## UP-20260903-007 — Reconcile device evidence and prepare the C02 human checkpoint
- date: 2026-09-03
- status: in-progress
- scope: documentation, execution, hardware-inventory
- tags: c01, devicespecifications, tasks, human-checkpoint
- aliases: reconcile device evidence, prepare setup handoff, update inventory
- paths: docs/devicespecifications.md, tasks.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Update shared documentation using supplied hardware observations and deliver one consolidated human handoff containing only missing prerequisites, without starting runtime implementation.
- constraints: Stay within C01 evidence reconciliation. Do not start runtime implementation or execute any code. Do not fetch, pull or change Git.
- acceptance: Shared inventory reflects supplied evidence without overclaiming. The board records the real stage and remaining checkpoint. One concise, named human handoff is ready to relay.
- verification_authorization: No execution allowed.
- follow_up_to: [UP-20260903-006](#up-20260903-006)
- supersedes: none
- linked_changes: [AC-20260903-007](agentchangelog.md#ac-20260903-007)

<a id="up-20260903-008"></a>
## UP-20260903-008 — Close C01 documentation and carry C02 to its first checkpoint
- date: 2026-09-03
- status: in-progress
- scope: documentation, execution, runtime-decision, model-decision, infrastructure-pins
- tags: c01, c02, od-03, od-05, od-06, od-08, device-based-checkpoints
- aliases: close c01 docs, device based checkpoints, resolve od decisions, c02 setup package
- paths: tasks.md, AGENTS.md, agent-memory/README.md, docs/devicespecifications.md, docs/architecture.md, docs/model-catalog.md, docs/evaluation.md, docs/security.md, docs/prd.md, scripts/od03_runtime_comparison.py
- summary: Finish the C01 documentation closeout by replacing personal assignments with Claude/Codex roles and device-based human checkpoints, then resolve C02's OD-03/OD-05/OD-06/OD-08 decisions with recorded upstream sources and prepare the setup package for the macOS coordinator and Ubuntu worker.
- constraints: Use only Claude and Codex as agent roles; identify humans by device. Keep optional machines and their incomplete GPU details off the first configuration's critical path. Preserve historical evidence and Git identities. Keep AF-001 a draft. No installs, model downloads, service starts, deployments or Git/GitHub writes. Preserve existing uncommitted changes.
- acceptance: Active execution instructions are device-based and consistent; the four C02 decisions are recorded with provenance; the Ubuntu worker's read-only evidence commands are ready for Codex review; every claim distinguishes measured from estimated.
- verification_authorization: Read-only local inspection on the macOS coordinator; bounded local inference against the already-running loopback Ollama server.
- follow_up_to: [UP-20260903-007](#up-20260903-007)
- supersedes: none
- linked_changes: [AC-20260903-008](agentchangelog.md#ac-20260903-008)

<a id="up-20260903-009"></a>
## UP-20260903-009 — Repair the four remaining C02 review findings
- date: 2026-09-03
- status: in-progress
- tags: c02, runtime-comparison, stream-parser, inventory
- aliases: reasoning channel, missing generation timing, failed port probe, stale mac inventory
- paths: scripts/od03_runtime_comparison.py, scripts/test_od03_parser.py, docs/devicespecifications.md, docs/evaluation.md, docs/architecture.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: The requester authorised Codex to fix the four remaining C02 parser and inventory findings directly.
- constraints: Repository edits only; preserve existing changes and historical ledger entries; no Git writes, service starts, installs, downloads or inference runs.
- acceptance: Count separate reasoning in TTFT and suppression evidence, reject invalid generation timing, preserve socket-probe failures, and distinguish initial Mac inventory from the later measured response.
- verification_authorization: Prepare focused offline checks; test execution requires separate permission under AGENTS.md and CODEX.md.
- follow_up_to: [UP-20260903-008](#up-20260903-008)
- linked_changes: [AC-20260903-009](agentchangelog.md#ac-20260903-009)

<a id="up-20260903-010"></a>
## UP-20260903-010 — Prepare C02 closeout from returned device evidence
- date: 2026-09-03
- status: in-progress
- tags: c02, closeout, runtime-comparison, memory-reporting
- aliases: ubuntu inventory, bundled engine, defer comparisons, runner rss
- paths: tasks.md, docs/devicespecifications.md, docs/evaluation.md, docs/model-catalog.md, docs/architecture.md, docs/prd.md, scripts/od03_runtime_comparison.py, scripts/test_od03_parser.py, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: The requester resumed C02 closeout, then explicitly deferred the controlled cold-start and Ubuntu direct-engine comparisons while retaining Ollama.
- constraints: Record user-returned measurements with their limits; repair misleading RAM reporting; preserve historical evidence; no service starts, inference, installations, downloads, deployments or Git writes; C03 requires separate authorisation after acceptance.
- acceptance: The setup record reflects both devices, measured and deferred comparisons are distinct, and the closeout is ready for requester review.
- verification_authorization: Reuse the requester's existing permission for offline parser checks; memory checks mock process and GPU queries and make no live calls.
- follow_up_to: [UP-20260903-009](#up-20260903-009)
- linked_changes: [AC-20260903-010](agentchangelog.md#ac-20260903-010)

<a id="up-20260903-011"></a>
## UP-20260903-011 — Document recommended technologies and languages for every layer
- date: 2026-09-03
- status: in-progress
- tags: tech-stack, languages, frontend, architecture, documentation
- aliases: TechStack.md, typescript react vite, python sql, language selection
- paths: TechStack.md, README.md, docs/README.md, docs/architecture.md, frontend/README.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: The requester asked to update or create TechStack.md with the best-fitting language and technology for every application section after the stack critique and device-scope clarification.
- constraints: Documentation only; preserve the existing C02 changes, checkpoints and hardware evidence; distinguish implemented, recorded, recommended and deferred choices; no installs, scaffolding, runtime commands, tests or Git writes.
- acceptance: One discoverable stack guide covers all product surfaces and supporting layers, explains trade-offs, retains Ollama and Redis Streams, and records later device qualification without promising an unverified rollout.
- verification_authorization: Read-only source and official-documentation research, Markdown link and whitespace inspection; no runtime testing needed for prose changes.
- follow_up_to: [UP-20260903-010](#up-20260903-010)
- linked_changes: [AC-20260903-011](agentchangelog.md#ac-20260903-011)

<a id="up-20260903-012"></a>
## UP-20260903-012 — Address the two C02 closeout observations
- date: 2026-09-03
- status: in-progress
- tags: c02, closeout, listener, cancellation, review
- aliases: claude review, wildcard port 8080, cancellation not exercised, techstack handoff
- paths: tasks.md, docs/devicespecifications.md, docs/evaluation.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: The requester resumed the C02/TechStack handoff with Claude's review and explicitly authorised the two C02 documentation fixes.
- constraints: Preserve existing changes; keep C03 pending separate authorisation and the frontend recommendation unchanged; no tests, inference, host operations or Git writes.
- acceptance: Track the unidentified Ubuntu listener as its own C02 open item and state that cancellation was not exercised, with its later implementation and verification gate named.
- verification_authorization: Read-only source, documentation and diff inspection; no runtime checks for prose changes.
- follow_up_to: [UP-20260903-011](#up-20260903-011)
- linked_changes: [AC-20260903-012](agentchangelog.md#ac-20260903-012)

<a id="up-20260903-013"></a>
## UP-20260903-013 — Design the application UI and the public download site
- date: 2026-09-03
- status: in-progress
- scope: frontend, design
- tags: ui, design-direction, chat-surface, evidence-semantics, theming, accessibility
- aliases: two designs, chatbot UI, download website, hermes deepseek reference, control room blueprint, direction pick
- paths: frontend/design/, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Establish a visual direction for the Refinix application surfaces and the separate public distribution site, informed by reference products, then build the surfaces part by part starting with Chat.
- constraints: Plain HTML and CSS with no build chain; both light and dark themes; enforced, observed and unavailable must stay visually distinct; state names must come from the frozen contract; sample content must not read as measured evidence.
- acceptance: One recorded direction with tokens, a Chat surface reference page that passes a contrast sweep in every theme state, and a stated list of surfaces still to build.
- decisions: Control Room for application surfaces; Blueprint restricted to artifacts and the Proof Card; the public site is a separate bolder treatment; Chat built first.
- follow_up_to: none
- supersedes: none
- linked_changes: [AC-20260903-013](agentchangelog.md#ac-20260903-013), [AC-20260903-014](agentchangelog.md#ac-20260903-014), [AC-20260903-015](agentchangelog.md#ac-20260903-015), [AC-20260903-016](agentchangelog.md#ac-20260903-016), [AC-20260903-017](agentchangelog.md#ac-20260903-017), [AC-20260903-018](agentchangelog.md#ac-20260903-018), [AC-20260903-019](agentchangelog.md#ac-20260903-019), [AC-20260903-020](agentchangelog.md#ac-20260903-020), [AC-20260903-021](agentchangelog.md#ac-20260903-021), [AC-20260903-022](agentchangelog.md#ac-20260903-022), [AC-20260903-023](agentchangelog.md#ac-20260903-023), [AC-20260903-024](agentchangelog.md#ac-20260903-024), [AC-20260903-025](agentchangelog.md#ac-20260903-025), [AC-20260903-026](agentchangelog.md#ac-20260903-026), [AC-20260903-027](agentchangelog.md#ac-20260903-027), [AC-20260903-028](agentchangelog.md#ac-20260903-028), [AC-20260903-029](agentchangelog.md#ac-20260903-029), [AC-20260903-030](agentchangelog.md#ac-20260903-030), [AC-20260903-031](agentchangelog.md#ac-20260903-031), [AC-20260903-034](agentchangelog.md#ac-20260903-034), [AC-20260903-035](agentchangelog.md#ac-20260903-035), [AC-20260903-036](agentchangelog.md#ac-20260903-036), [AC-20260903-037](agentchangelog.md#ac-20260903-037)

<a id="up-20260903-014"></a>
## UP-20260903-014 — Replace per-chunk questions with one input handover
- date: 2026-09-03
- status: in-progress
- scope: documentation, execution, operating-contract
- tags: c03, operating-contract, handover, authorisation-scope
- aliases: handover pack, authorisation scope, reduce human intervention, batch inputs
- paths: tasks.md, AGENTS.md, docs/handover-pack.md, docs/README.md
- summary: Amend the operating contract so one explicit authorisation can cover a named chunk range and routine implementation questions stop being relayed as checkpoints, and add a handover template that collects the requester's inputs once.
- constraints: Documentation only. Keep missing authorisation a genuine checkpoint; repository evidence answers technical questions but never grants permission. Keep execution order separate from authorisation scope. Claim no numeric reduction in stops. Keep credentials and confidential inputs out of the tracked repository. Do not start C03 or clear any gate.
- acceptance: The amended rules distinguish order from scope, the handover template prefills settled decisions and separates pre-C03 inputs from later ones, and the three open gates are unchanged.
- verification_authorization: Read-only inspection and offline link checks.
- follow_up_to: [UP-20260903-013](#up-20260903-013)
- supersedes: none
- linked_changes: [AC-20260903-032](agentchangelog.md#ac-20260903-032)

<a id="up-20260903-015"></a>
## UP-20260903-015 — Resolve the remaining handover review findings
- date: 2026-09-03
- status: in-progress
- scope: documentation
- tags: handover, fixtures, c07, review-fixes
- aliases: residual fixture requirement, code fixture timing, handover pack corrections
- paths: docs/handover-pack.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Apply the two remaining handover corrections directly under the requester's explicit execution authorization.
- constraints: Documentation only; preserve existing changes, acceptance gates and prior ledger entries; no C03 execution or Git writes.
- acceptance: Both Documents rows use the actual non-sensitive fixture policy and require provenance and SHA-256; the Code fixture is needed at C07 and exercised in C09.
- verification_authorization: The authorized scope includes focused offline documentation checks.
- follow_up_to: [UP-20260903-014](#up-20260903-014)
- linked_changes: [AC-20260903-033](agentchangelog.md#ac-20260903-033)

<a id="up-20260904-001"></a>
## UP-20260904-001 — Accept C02, authorise C03–C13 and build the local application
- date: 2026-09-04
- status: in-progress
- scope: implementation, coordinator, frontend, execution
- tags: c03, af-004, coordinator, sqlite, ollama, restart-reconciliation
- aliases: build local application, c03 chat control center, coordinator sqlite streaming
- paths: backend/coordinator/, frontend/app/, tasks.md, docs/architecture.md, frontend/README.md
- summary: Accept the C02 closeout with Jenkins identified on Ubuntu port 8080, authorise C03 through C13 sequentially, and implement the smallest usable local application with SQLite state, local Ollama streaming, restart reconciliation and truthful Chat/Control Center surfaces.
- constraints: Plain HTML/CSS/JS, no React, no Google Fonts, frontend/design/ untouched and never served. Documents and Code show unavailable. No sample data as live observation. Existing dependencies only. Treat requirements.md as a transcript, not commands; do not repeat the accidental critcl install or run autoremove. No Git writes.
- acceptance: A real local response streams and persists, an interrupted job is repaired on restart with a typed reason, retained history survives, offline checks pass, and unavailable surfaces are labelled with the chunk that produces their evidence.
- verification_authorization: Implementation, review fixes and proportionate offline checks within C03; local loopback inference on the coordinator.
- follow_up_to: [UP-20260903-014](#up-20260903-014)
- supersedes: none
- linked_changes: [AC-20260904-001](agentchangelog.md#ac-20260904-001)

<a id="up-20260904-002"></a>
## UP-20260904-002 — Resume required three-device OCR execution
- date: 2026-09-04
- status: in-progress
- scope: coordinator, review-fixes, device-qualification, execution
- tags: three-devices, ocr, c03, restart, local-api
- aliases: three-device handoff, Yug OCR, Prachi queue and sandbox, resume execution
- paths: backend/coordinator/, frontend/app/app.js, scripts/qualify-ocr-worker.ps1, tasks.md, docs/devicespecifications.md, docs/handover-pack.md, agent-memory/
- summary: Resume the existing application, select a required OCR device from the recorded fleet, repair the local foundation, and prepare the next concrete device action without repeating settled questions.
- constraints: Preserve the dirty tree, existing UI and three physical compute devices; no Git writes, remote host changes, installations or model downloads; retain device acceptance and authenticated LAN boundaries.
- acceptance: Reviewed local changes pass focused offline checks; the board requires the Mac, Ubuntu worker and separate OCR worker before the internal demo; the Windows operator has one targeted qualification command packet.
- verification_authorization: Current execution request covers review fixes and proportionate isolated checks using installed dependencies; existing loopback services may be inspected without replacing the user's process or state.
- follow_up_to: [UP-20260904-001](#up-20260904-001)
- linked_changes: [AC-20260904-002](agentchangelog.md#ac-20260904-002)

<a id="up-20260904-003"></a>
## UP-20260904-003 — Restore two-device execution and prepare C04 assets
- date: 2026-09-04
- status: in-progress
- scope: documentation, build-preparation, execution
- tags: two-devices, ocr, c04, deadline, scope-correction
- aliases: withdraw mandatory third worker, defer Windows OCR, September 8-9 demo
- paths: tasks.md, docs/devicespecifications.md, docs/handover-pack.md, scripts/qualify-ocr-worker.ps1, backend/worker-image/, agent-memory/
- summary: Restore the Mac and Ubuntu critical path, retain C03 repairs, defer extra execution devices, and prepare C04 build assets and a combined Git handoff for the 8-9 September internal demonstration.
- constraints: C01/C02 stay accepted; requester accepts C03 after running the repaired app; C04 runtime implementation/build/deployment remain gated; no Git writes, installations, downloads of executable packages or live-service changes; preserve all existing source repairs.
- acceptance: OCR is part of C08 on the two-device setup; Windows qualification is deferred but retained; prepared build inputs have provenance and integrity; the schedule names deadline risks without dropping evidence gates.
- verification_authorization: Preparation includes proportionate offline checks with installed tooling and read-only upstream metadata lookup; no image build or dependency installation is authorised here.
- supersedes: [UP-20260904-002](#up-20260904-002) for mandatory third-device scope only
- follow_up_to: [UP-20260904-001](#up-20260904-001)
- linked_changes: [AC-20260904-003](agentchangelog.md#ac-20260904-003)

<a id="up-20260904-004"></a>
## UP-20260904-004 — Fix incomplete replies and browser disconnect errors
- date: 2026-09-04
- tags: c03, truncation, output-limit, browser-disconnect
- aliases: increase token reply limit, completed normally, connection reset by peer
- paths: backend/coordinator/, frontend/app/app.js, docs/model-catalog.md, docs/handover-pack.md, agent-memory/
- summary: Requester authorised repairing the reported C03 issues and asked to increase the reply token limit.
- request: Fix incorrect completion reporting, retain the stopping reason and partial reply, and handle expected browser disconnects; increase the bounded reply allowance without a new model.
- follow_up_to: [UP-20260904-003](#up-20260904-003)
- linked_changes: [AC-20260904-004](agentchangelog.md#ac-20260904-004)

<a id="up-20260904-005"></a>
## UP-20260904-005 — Prepare Claude's context and interface build brief
- date: 2026-09-04
- tags: c03, build-brief, context-window, kv-cache, ui, ux
- aliases: beautify UI, coloured output, UI fixture, Claude execution update
- paths: docs/c03-context-ui-build-brief.md, agent-memory/
- summary: Requester asked for a Claude execution brief covering context and cache concepts plus an inspected, more usable and polished interface.
- request: Analyse the current UI first; specify alignment, formatting, semantic output colours, responsive controls and a representative UI fixture alongside context-window and KV-cache requirements.
- follow_up_to: [UP-20260904-004](#up-20260904-004)
- linked_changes: [AC-20260904-005](agentchangelog.md#ac-20260904-005)

<a id="up-20260904-006"></a>
## UP-20260904-006 — Include Delete chat in the UI brief
- date: 2026-09-04
- tags: c03, ui, delete-chat, build-brief
- aliases: delete convo button, conversation menu
- paths: docs/c03-context-ui-build-brief.md, agent-memory/
- summary: Requester asked whether the redesigned conversation interface should include Delete chat.
- request: Include a discoverable, confirmed per-conversation deletion action in Claude's UI build scope.
- follow_up_to: [UP-20260904-005](#up-20260904-005)
- linked_changes: [AC-20260904-006](agentchangelog.md#ac-20260904-006)

<a id="up-20260904-007"></a>
## UP-20260904-007 — Add simple conversation management to the build brief
- date: 2026-09-04
- tags: c03, build-brief, rename, search, drafts, pin, export
- aliases: rename chat, search conversations, draft recovery, pin important chats, export chat
- paths: docs/c03-context-ui-build-brief.md, agent-memory/
- summary: Requester asked to include rename, search, draft recovery, pinning and export in Claude's existing build brief while excluding regeneration.
- request: Keep these additions simple enough for the same implementation pass; retain the already specified output and navigation improvements.
- follow_up_to: [UP-20260904-005](#up-20260904-005)
- linked_changes: [AC-20260904-007](agentchangelog.md#ac-20260904-007)

<a id="up-20260904-002"></a>
## UP-20260904-002 — C03 context handling and interface polish
- date: 2026-09-04
- status: in-progress
- scope: implementation, coordinator, frontend, context-window
- tags: c03, context-window, markdown, accessibility, responsive
- aliases: context selection, markdown renderer, ui fixture, 8192 context
- paths: backend/coordinator/, frontend/app/, docs/evaluation.md, docs/model-catalog.md
- summary: Bound what the model actually receives without changing saved history, and rebuild the reading experience — typography, prose colour, Markdown rendering, drawers, and interaction safety.
- constraints: Vanilla HTML/CSS/JS, no framework, no remote font, no CDN, no vendored dependency. frontend/design/ untouched. Saved history never rewritten. Character estimates labelled as estimates. Do not disturb the requester's existing port-8770 process.
- acceptance: Selection recorded per attempt and replayable, omission visible beside its reply, oversized input reported not chopped, renderer handles the full fixture safely, navigation and details reachable at every tested width, all offline checks pass.
- verification_authorization: Implementation, offline checks, and bounded local inference on the coordinator.
- follow_up_to: [UP-20260904-001](#up-20260904-001)
- supersedes: none
- linked_changes: [AC-20260904-002](agentchangelog.md#ac-20260904-002)

<a id="up-20260904-003"></a>
## UP-20260904-003 — Conversation management and a combined review
- date: 2026-09-04
- status: in-progress
- scope: implementation, coordinator, frontend, review
- tags: c03, rename, search, drafts, pin, export, review
- aliases: conversation management, chat search, draft recovery, export chat
- paths: backend/coordinator/, frontend/app/
- summary: Add rename, local conversation search, draft recovery, pin/unpin and Markdown/plain-text export reusing existing local storage and UI, then produce a combined review of the whole codebase and documentation for Codex.
- constraints: Reuse SQLite and the protected API; no model calls, cloud services or new search infrastructure. Regenerate is excluded; Continue stays. Drafts never reach the model, search or export.
- acceptance: All five behave correctly with fixture coverage and offline checks; the review covers the entire codebase and docs without further implementation.
- verification_authorization: Implementation, offline checks and bounded local inference on the coordinator.
- follow_up_to: [UP-20260904-002](#up-20260904-002)
- supersedes: none
- linked_changes: [AC-20260904-003](agentchangelog.md#ac-20260904-003)

<a id="up-20260904-008"></a>
## UP-20260904-008 — Execute the C03 review repairs
- date: 2026-09-04
- tags: c03, review-fixes, drafts, delete, export, context
- aliases: Codex execute, draft race, active chat deletion, Unicode export, context overflow
- paths: backend/coordinator/, frontend/app/, docs/evaluation.md, agent-memory/
- summary: Requester authorised Codex to repair the draft, deletion, export and context issues found in the C03 review.
- request: Implement the fixes and verify them with isolated regression checks and bounded local runtime evidence.
- follow_up_to: [UP-20260904-007](#up-20260904-007)
- constraints: Preserve existing changes and real chat history; no Git writes or C04 execution.
- linked_changes: [AC-20260904-008](agentchangelog.md#ac-20260904-008)

<a id="up-20260904-009"></a>
## UP-20260904-009 — Address the simultaneous-limit review feedback
- date: 2026-09-04
- tags: c03, review-follow-up, context, output-limit
- aliases: Claude PASS review, simultaneous token limits, limit_reason
- paths: backend/coordinator/, frontend/app/app.js, docs/c03-repair-handoff.md, agent-memory/
- summary: Requester supplied an independent PASS review with a remaining simultaneous context/output-limit finding.
- request: Evaluate the feedback as a follow-up to the authorised Codex repairs.
- follow_up_to: [UP-20260904-008](#up-20260904-008)
- linked_changes: [AC-20260904-009](agentchangelog.md#ac-20260904-009)

<a id="up-20260904-010"></a>
## UP-20260904-010 — Accept C03 and hand C04 execution to Claude
- date: 2026-09-04
- tags: c03, c04, acceptance, orchestration, networking
- aliases: C03 accepted, connect Mac and Ubuntu, Claude executes Codex reviews
- paths: tasks.md, docs/c03-repair-handoff.md, docs/c04-execution-brief.md, backend/worker-image/README.md, agent-memory/
- summary: Requester accepted C03 and asked Codex to orchestrate Claude's next build and explain Mac–Ubuntu connection steps.
- request: Record acceptance, prepare the bounded C04 execution handoff, and establish the next device checkpoint.
- constraints: Preserve the two-device sequence, existing changes and human deployment gates; no Git writes.
- follow_up_to: [UP-20260904-009](#up-20260904-009)
- linked_changes: [AC-20260904-010](agentchangelog.md#ac-20260904-010)

<a id="up-20260904-004"></a>
## UP-20260904-004 — Execute C04: worker API and image build
- date: 2026-09-04
- status: in-progress
- scope: implementation, worker, container-image
- tags: c04, af-003, worker-api, docker, image-digest
- aliases: worker image build, worker api, c04 execution
- paths: backend/worker/, backend/worker-image/, docs/c04-ubuntu-build-handoff.md, tasks.md
- summary: With C03 accepted and Ubuntu-to-Mac connectivity confirmed, implement the worker API against the frozen contract, complete the Docker build assets, and return the Ubuntu build handoff for Codex review.
- constraints: Build assets and implementation only; no cluster deployment, no host changes on Ubuntu, no Git writes. Pairing stays unimplemented per OD-06. The Ubuntu build produces the digest C05 pins.
- acceptance: The image builds and the worker API serves the reserved contract routes with real inference, and the Ubuntu operator has exact reviewed build and digest-inspection commands.
- verification_authorization: Implementation, offline checks, local container build and bounded local inference on the coordinator.
- follow_up_to: [UP-20260904-003](#up-20260904-003)
- supersedes: none
- linked_changes: [AC-20260904-005](agentchangelog.md#ac-20260904-005)

<a id="up-20260904-011"></a>
## UP-20260904-011 — Execute the remaining C04 export corrections
- date: 2026-09-04
- tags: c04, export, buildkit, review-fixes
- aliases: solve them yourself, explicit OCI export, stale test count
- paths: docs/c04-ubuntu-build-handoff.md, backend/worker-image/, scripts/image-digests.py, agent-memory/
- summary: Requester authorised Codex to fix the remaining OCI export instructions and stale check count directly.
- constraints: Edit existing files, keep the response concise, preserve worker code and other changes; no Git writes or Ubuntu host actions.
- follow_up_to: [UP-20260904-010](#up-20260904-010)
- linked_changes: [AC-20260904-011](agentchangelog.md#ac-20260904-011)

<a id="up-20260904-012"></a>
## UP-20260904-012 — Execution 1: Refinix desktop foundation
- date: 2026-09-04
- status: in-progress
- scope: implementation, desktop-shell, packaging, branding, ui
- tags: execution-1, refinix, pywebview, py2app, desktop, cancellation, attachments
- aliases: refinix desktop foundation, desktop shell, native window, app icon, stop behaviour
- paths: desktop/, frontend/app/, backend/coordinator/, scripts/build-brand-assets.py, docs/, tasks.md
- summary: Build a native desktop foundation named Refinix around the existing coordinator — pywebview shell, startup/shutdown lifecycle, branding, simplified Chat/Code navigation with skill and attachment composer, graphical settings, and working cancellation — targeting macOS first with prepared Windows and Ubuntu paths.
- request: Implement the desktop shell and packaging path, startup lifecycle with real readiness checks, Refinix branding from the supplied masters, simplified navigation and composer, card-based settings, and repaired /v1/cancel; report built, verified, screenshots, packaged location and remaining device checks.
- constraints: Separate from C01–C13 numbering; C05 stays paused with its dirty files and pending review preserved. Reuse the coordinator, SQLite state, frontend and event stream. No Git writes, Ubuntu operations, worker-image rebuilds or model downloads. New installations, downloads and live-device checks keep their permission gates and are consolidated into one setup handoff. Repository-editing agents, access-mode enforcement and OCR belong to Executions 2 and 3.
- acceptance: Refinix opens from the launcher into a native window, reports real service readiness, chats, stops an execution and reopens with history intact.
- verification_authorization: Implementation, proportionate offline checks against existing dependencies and isolated test data.
- follow_up_to: [UP-20260904-011](#up-20260904-011)
- linked_changes: [AC-20260904-013](agentchangelog.md#ac-20260904-013)

<a id="up-20260904-013"></a>
## UP-20260904-013 — Execute the desktop review fixes
- date: 2026-09-04
- status: fixes verified; requester acceptance pending
- scope: desktop, coordinator, verification
- tags: refinix, execution-1, review-fixes, cancellation, packaging
- aliases: execute fix all issues, open and view app, desktop correction pass
- paths: desktop/, backend/coordinator/, agent-memory/
- summary: Requester authorised fixing all six Execution 1 review findings and returning exact instructions to open Refinix.
- constraints: Preserve the existing frontend, C05 work and user data; no Git writes. New dependency and native-device setup remains a reviewed device checkpoint.
- follow_up_to: [UP-20260904-012](#up-20260904-012)
- linked_changes: [AC-20260904-014](agentchangelog.md#ac-20260904-014)

<a id="up-20260904-014"></a>
## UP-20260904-014 — Approve macOS desktop setup and launch
- date: 2026-09-04
- status: setup completed; requester acceptance pending
- scope: desktop, macos-setup, verification
- tags: refinix, dependency-install, py2app, native-launch
- aliases: approved desktop setup, build and open Refinix app
- paths: desktop/, agent-memory/
- summary: Requester explicitly approved the reviewed 10.1 MB dependency install, local app build and opening Refinix.
- constraints: Use desktop/.venv with hash-pinned PyPI dependencies; opening may start installed Ollama, but no model downloads or Docker startup; no Git writes or C05 actions.
- follow_up_to: [UP-20260904-013](#up-20260904-013)
- linked_changes: [AC-20260904-015](agentchangelog.md#ac-20260904-015)

<a id="up-20260904-015"></a>
## UP-20260904-015 — Accept the desktop smoke test and prepare its Git handoff
- date: 2026-09-04
- tags: refinix, acceptance, git-handoff, scoped-pr
- aliases: stopped chat survives quit, exclude C05 from commit, PR to dev
- paths: README.md, desktop/README.md, tasks.md, agent-memory/
- summary: Requester confirmed Chat, Stop, Command-Q and retained stopped history, then requested exact Git commands and a PR description excluding C05 changes.
- constraints: Prepare commands for the requester; no Git writes. Preserve all C05 work and label Windows/Linux packaging unfinished.
- follow_up_to: [UP-20260904-014](#up-20260904-014)
- linked_changes: [AC-20260904-016](agentchangelog.md#ac-20260904-016)

<a id="up-20260904-016"></a>
## UP-20260904-016 — Group remaining execution work and defer routine documentation
- date: 2026-09-04
- tags: grouped-execution, parallel-work, review-fixes, documentation-deferral
- aliases: C06 with C07, C08 with C09, C11 through C13 together, small fixes by Codex
- paths: tasks.md, agent-memory/
- summary: Requester approved the discussed grouped execution plan and asked to save a code-focused review policy for the remaining C tasks.
- request: Overlap independent work, give Claude one complete execution brief for substantial code corrections, let Codex implement small code fixes, and defer routine documentation corrections until all C tasks are implemented.
- constraints: Update the plan now; no C06 implementation, host actions or Git writes. Preserve C05 work and required device/safety gates; this is not permission to skip validation.
- follow_up_to: [UP-20260904-015](#up-20260904-015)
- linked_changes: [AC-20260904-017](agentchangelog.md#ac-20260904-017)

<a id="up-20260904-017"></a>
## UP-20260904-017 — Triage Claude's desktop follow-up review
- date: 2026-09-04
- tags: refinix, packaging, review-fixes, artifact-validation
- aliases: raw backend copied into bundle, extra cached wheel, missing acceptance records
- paths: desktop/setup_py2app.py, desktop/setup-macos.command, desktop/test_packaging.py, agent-memory/
- summary: Requester supplied Claude's desktop review for verification under the standing policy to fix small code issues directly and defer routine documentation cleanup.
- constraints: Preserve the running app, C05 changes and user data; no new dependencies, Git writes or full-suite reruns. Build a separate artifact to verify the packaging correction.
- follow_up_to: [UP-20260904-016](#up-20260904-016)

<a id="up-20260904-018"></a>
## UP-20260904-018 — Execution 2: repository editing, access modes and reasoning switch
- date: 2026-09-04
- status: in-progress
- scope: implementation, code-surface, access-policy, runtime, frontend
- tags: execution-2, repository-editing, access-modes, approvals, reasoning, blank-conversation
- aliases: code surface, partial full ask, think true false, model pill, blank chat pane
- paths: backend/coordinator/, desktop/, frontend/app/, tasks.md, docs/
- summary: Implement the Code repository-editing workflow with coordinator-enforced Partial/Full/Ask access modes, a per-model Reasoning On/Off composer control that sets Ollama's top-level think field, and repair the blank conversation pane at its shared render root cause.
- request: Build the three deliverables from current source, add focused offline checks over synthetic repositories, keep records truthful, and return a reviewable handoff.
- constraints: Edits limited to the deliverables; offline checks with existing dependencies; one bounded live Ollama check only if it is already reachable with the model installed; bundle rebuild only if Refinix is not running and needs no install. No Git/GitHub writes, installs, downloads, deployments, service or network changes, C05 or Ubuntu action, subagents, or dependency additions. Preserve every pre-existing dirty hunk.
- acceptance: Existing-file text edits inside an explicitly connected folder are proposed, diffed, policy-checked and atomically applied; reasoning is request-scoped and persisted per model; conversations never blank on a render or refresh failure.
- verification_authorization: Implementation, offline checks with synthetic repositories and temporary databases, and one bounded local runtime smoke check.
- follow_up_to: [UP-20260904-017](#up-20260904-017)
- linked_changes: [AC-20260904-019](agentchangelog.md#ac-20260904-019)

<a id="up-20260905-001"></a>
## UP-20260905-001 — Execution 2 correction pass from the Codex review
- date: 2026-09-05
- status: in-progress
- scope: implementation, code-surface, access-policy, filesystem, frontend
- tags: execution-2, review-fixes, ask-mode, short-io, diff-truncation, platform-gate
- aliases: codex needs fix, listing approval, stale repository, partial write, complete diff
- paths: backend/coordinator/, frontend/app/, tasks.md, agent-memory/
- summary: Fix the seven verified findings from the Codex review of Execution 2 and add regressions for each, keeping the execution pending re-review and requester acceptance.
- request: Make Ask-mode listing usable, make repository activation state-safe, handle short filesystem I/O, stop applying content the diff did not show, fail closed consistently where the platform cannot contain a folder, and make the policy matrix and audit agree.
- constraints: No packaged-app rebuild, installs, downloads, model or network services, Git/GitHub writes, C05 or Ubuntu action. Preserve every unrelated dirty hunk.
- acceptance: Each finding has a regression that fails without its fix, and the required suites pass.
- verification_authorization: Implementation and offline checks with synthetic repositories and temporary databases.
- follow_up_to: [UP-20260904-018](#up-20260904-018)
- linked_changes: [AC-20260905-001](agentchangelog.md#ac-20260905-001)

<a id="up-20260905-002"></a>
## UP-20260905-002 — Execution 3: document understanding, retrieval and generation
- date: 2026-09-05
- status: in-progress
- scope: implementation, documents, retrieval, artifacts, ui
- tags: execution-3, document-skills, extraction, fts, docx, code-composer, context-indicator
- aliases: read a document, search my documents, write a document, codex composer, context estimate
- paths: backend/coordinator/, frontend/app/, docs/, tasks.md, agent-memory/
- summary: Implement the three document skills inside Chat over the existing attachment intake, add bounded local retrieval with resolvable citations and a real .docx generation workflow, add a context-window indicator to the composer, and rebuild the Code surface around a Codex-style composer.
- request: Build Execution 3 completely in source, preserve the unfinished Execution 2 work and the C05 dirty tree, add focused tests, and hand back exact verification and rebuild commands.
- constraints: Source only. No test runs, installs, downloads, model calls, service starts, bundle rebuild, deployment or Git writes. Document work stays a skill inside Chat; no new top-level page and no expansion into C05-C09 or worker dispatch.
- acceptance: A selected document skill reads only that request's attachments, retrieval cites a real source and page, a structurally valid .docx is produced under coordinator storage, and export needs a recorded approval.
- verification_authorization: None. Tests are written but not run; the requester runs them.
<a id="up-20260905-001"></a>
## UP-20260905-001 — Neutral black palette, ChatGPT/Claude register, and collapsible walls
- date: 2026-09-05
- tags: refinix, palette, neutral-black, glassmorphism, panel-collapse, chat-ui
- aliases: background looks navy blue, make it black like chatgpt or claude, glassmorphism where it looks good, three line icon sidebar, collapse left and right panels, not only one section
- paths: frontend/design/, frontend/app/, frontend/README.md
- summary: Requester reported the application ground reading as navy blue in both the running app and the design reference, and asked for a neutral black palette in the ChatGPT/Claude register, glassmorphism applied selectively rather than everywhere, and a three-line control on each side that dismisses the left navigation and the right lifecycle rail so the middle window can be focused.
- constraints: Apply across every surface including Control Center, not one screen. Glass only where it looks good. Perform the work carefully rather than quickly.
- linked_changes: [AC-20260905-001](agentchangelog.md#ac-20260905-001)

<a id="up-20260905-002"></a>
## UP-20260905-002 — Apply the supplied Refinix lockup to the application surfaces
- date: 2026-09-05
- tags: refinix, brand, logo, wordmark, design-track
- aliases: why the new logo aint updated here, apply the new logo, refinix metal lockup in the nav
- paths: frontend/design/
- summary: Requester noticed the design track's Chat surface still showed a drawn stand-in symbol with the product name set as text, while the running application already carried the supplied brushed-metal REFINIX lockup, and asked for the real logo to be applied.
- constraints: none stated beyond applying the supplied mark.
- follow_up_to: [UP-20260905-001](#up-20260905-001)
- linked_changes: [AC-20260905-002](agentchangelog.md#ac-20260905-002)

<a id="up-20260905-003"></a>
## UP-20260905-003 — Review and repair Refinix Executions 2 and 3
- date: 2026-09-05
- status: completed
- scope: review, execution-2, execution-3, correction
- tags: refinix, code-surface, document-skills, security-review, review-fixes
- aliases: combined codex review, solve all bugs, execute e2 e3 fixes
- paths: backend/coordinator/, frontend/app/, agent-memory/
- summary: Requester authorised a complete combined review of Claude's Execution 2 and Execution 3 implementation and direct repair of verified defects.
- constraints: Preserve unrelated C05 work; no Git/GitHub writes, installs, downloads, model calls, service starts, packaged-app rebuild, deployment or Ubuntu action.
- acceptance: Repair confirmed Code and Documents correctness, security and UI defects; run proportionate isolated checks; report remaining native requester gates truthfully.
- verification_authorization: Implementation and offline checks with existing dependencies, synthetic repositories and temporary databases.
- follow_up_to: [UP-20260905-002](#up-20260905-002)
- linked_changes: [AC-20260905-003](agentchangelog.md#ac-20260905-003)
## UP-20260905-003 — Dark wine red for every failure and error state
- date: 2026-09-05
- tags: refinix, palette, fault, wine-red, error-state
- aliases: red colour for failed or error things, dark wine red text or icon, apply across the website
- paths: frontend/design/, frontend/app/
- summary: Requester asked that wherever red marks a failure or error, the text or icon becomes a dark wine red, applied across the whole website rather than one surface.
- constraints: Apply everywhere the failure red appears, including the public site.
- follow_up_to: [UP-20260905-002](#up-20260905-002)
- linked_changes: [AC-20260905-003](agentchangelog.md#ac-20260905-003)

<a id="up-20260905-004"></a>
## UP-20260905-004 — Fix the site's failing grey
- date: 2026-09-05
- tags: refinix, site, contrast, accessibility, ink-faint
- aliases: fix that grey contrast issue on the site
- paths: frontend/design/site.css
- summary: Requester asked for the pre-existing grey contrast failure on the public site, reported alongside the wine-red change, to be fixed as well.
- constraints: none stated.
- follow_up_to: [UP-20260905-003](#up-20260905-003)
- linked_changes: [AC-20260905-004](agentchangelog.md#ac-20260905-004)

<a id="up-20260905-005"></a>
## UP-20260905-005 — Narrow the metal ramps and fix everything else found
- date: 2026-09-05
- tags: refinix, site, contrast, accessibility, gradient-text, metal-ramp
- aliases: narrow the ramps, fix all the issues in one go, dont ask again
- paths: frontend/design/site.css
- summary: Requester approved narrowing the brushed-metal gradient ramps so the clipped-to-text lockups meet contrast, and asked that every issue found be fixed in one pass without returning for approval.
- constraints: Fix everything found; do not come back with questions.
- follow_up_to: [UP-20260905-004](#up-20260905-004)
- linked_changes: [AC-20260905-005](agentchangelog.md#ac-20260905-005)

<a id="up-20260905-006"></a>
## UP-20260905-006 — Correct the C05 denied isolation probe for kube-router rejection
- date: 2026-09-05
- status: implemented; requester verification pending
- scope: c05, correction, network-policy, checks
- tags: c05, netpolicy, kube-router, isolation-probe, exit-codes
- aliases: connection refused is not a failure, blocked-by-policy, denied probe exit 7, reject icmp-port-unreachable
- paths: deploy/k3s/checks/netpolicy-denied.yaml, deploy/k3s/checks/netpolicy-allowed.yaml, deploy/k3s/test_manifests.py, docs/c05-ubuntu-deployment-handoff.md
- summary: Ubuntu step G showed the allowed probe reaching Redis and the denied probe refused immediately by an explicit kube-router REJECT rule, so the denied probe must treat rejection as a policy denial rather than assuming a denial always times out.
- request: Make the smallest root-cause correction so timeout exit 124 and Connection refused both report one stable RESULT=blocked-by-policy prefix at exit 7, keep PONG at POLICY-NOT-ENFORCED exit 1, keep every non-network error a failure, leave the allowed probe unweakened, replace the over-general shared test assertion with focused ones, and update step G.
- constraints: One bounded correction; preserve every unrelated dirty-tree change; no Git/GitHub writes, installs, deployments, network calls or credential access. No new handoff document and no tasks.md edit yet.
- acceptance: Both denial mechanisms exit 7 under one matchable prefix, allowed-path refusal stays exit 9, the allowed-first pairing is documented, and `python3 -B deploy/k3s/test_manifests.py` passes.
- verification_authorization: Implementation plus the two named offline checks.
- follow_up_to: [UP-20260904-004](#up-20260904-004)
## UP-20260905-006 — Bring the new Code and composer surfaces onto our design system
- date: 2026-09-05
- tags: refinix, design-integration, code-surface, composer, parallel-work
- aliases: codex implemented app integration, perform design beauty changes only, integrate his buttons workflow and logic with our ui, dont change any logic
- paths: frontend/app/
- summary: A parallel execution landed the Code surface, the model and context controls and the access-mode selector as working UI. Requester asked for presentation-only work on top of it — no logic, no button behaviour, no code changes — bringing those new controls onto the design system built in this session.
- constraints: Design and appearance only. Do not change logic, button wiring or behaviour.
- follow_up_to: [UP-20260905-005](#up-20260905-005)
- linked_changes: [AC-20260905-006](agentchangelog.md#ac-20260905-006)

<a id="up-20260905-007"></a>
## UP-20260905-007 — Implement C06 distributed execution and prepare C07 fixtures
- date: 2026-09-05
- status: implemented; device gates and requester verification pending
- scope: c06, c07, distributed-execution, pairing, redis, preparation
- tags: c06, c07, af-005, af-006, af-007, od-06, pairing, redis-streams, executor, fixtures
- aliases: pair the mac and ubuntu, redis dispatch, durable receipt, route reason, synthetic fixtures, c08 dependency plan
- paths: backend/worker/, backend/coordinator/, deploy/k3s/, fixtures/c07/, frontend/app/, docs/, agent-memory/
- summary: With C05 cleared, implement AF-005 to AF-007 — OD-06 pairing over pinned TLS, real Redis Streams dispatch with an executor, coordinator routing with truthful fallback, and the minimum UI/manifests — while independently preparing C07's synthetic fixtures and the C08 dependency plan.
- request: Build C06 and C07 preparation in one bounded cycle, add focused offline checks with stateful fakes, and return one Mac/Ubuntu execution handoff.
- constraints: Preserve unrelated and user-owned work. No Git/GitHub writes, deployment, installation, model download, host mutation or live-device command. Offline checks authorised. Smallest secure standard-library solution; no invented cryptography. Preserve and reuse the local Documents and Code work; C07 must not implement C08/C09. Do not invent the new image digest.
- acceptance: Durable receipt before 202, pairing and pin failures closed, executor recovery and cancellation, canonical history surviving Redis/worker loss, truthful local fallback, and deterministic C07 fixtures.
- verification_authorization: Implementation plus offline checks with fakes and stubs; no container build or device acceptance.
- follow_up_to: [UP-20260905-006](#up-20260905-006)
- linked_changes: [AC-20260905-007](agentchangelog.md#ac-20260905-007)

<a id="up-20260905-008"></a>
## UP-20260905-008 — Repair the eight Codex findings against C06 and C07
- date: 2026-09-05
- status: implemented; every device gate still outstanding
- scope: c06, c07, review-fixes, nodeport, redis, executor, fixtures
- tags: c06, c07, review-fixes, nodeport-exposure, socket-proxy, event-replay, redis-authority, atomic-receipt, lease, raster-scan, self-test
- aliases: needs fix, dnat cannot be filtered by input, wait for terminal state, restart recovery, receipt unknown, duplicate delivery, synthetic scan, guided self-test
- paths: backend/worker/, backend/coordinator/, deploy/k3s/, fixtures/c07/, frontend/app/, docs/, agent-memory/
- summary: Codex returned NEEDS FIX with eight findings on the C06/C07 implementation, covering unsafe NodePort exposure, an impossible setup order, a snapshot event read, process-local attempt state, a non-atomic receipt, lease and acknowledgement semantics, a missing raster scan fixture, and the absent AF-007 self-test.
- request: Repair all eight as one bounded correction pass, add the named checks, and report exact counts.
- constraints: Preserve unrelated dirty-tree work. No Git/GitHub writes, deployment, host changes, downloads or live-device commands. Reuse Redis, the existing systemd proxy pattern and the current contracts; no Helm, Ingress, second broker, replicas, Kubernetes client or speculative abstractions.
- acceptance: NodePort stays on loopback behind a restricted host forwarder, the setup order is executable, event consumption waits for a terminal state, the routes survive an API restart, receipts commit atomically, duplicates and reclaimed leases are safe, the scan fixture exists with provenance, and the self-test uses the real path.
- verification_authorization: Implementation plus the named offline suites; no container build or device acceptance.
- follow_up_to: [UP-20260905-007](#up-20260905-007)
- linked_changes: [AC-20260905-008](agentchangelog.md#ac-20260905-008)

<a id="up-20260905-009"></a>
## UP-20260905-009 — Close the five remaining C06 safety boundaries
- date: 2026-09-05
- status: implemented; the C06 device gate is still unrun
- scope: c06, review-fixes, dispatch-ambiguity, pending-recovery, self-test, image-build
- tags: c06, review-fixes, receipt-unknown, ambiguous-commit, xautoclaim, xack, self-test-verdict, dockerfile
- aliases: atomic mutation is not client knowledge, sent flag set too late, ack destroys the pending entry, local rescue is not a distributed pass, executor suite missing from the build
- paths: backend/worker/, backend/coordinator/, backend/worker-image/Dockerfile, agent-memory/
- summary: A focused C06 review found five failure boundaries the passing suites did not simulate — an ambiguous Redis commit reported as definite, an HTTP send classified definite after transmission began, a recovered pending entry acknowledged away from its live owner, a self-test that passed on a local rescue, and an image build missing the executor suite.
- request: Find the smallest root-cause corrections consistent with the existing architecture and add regressions for each.
- constraints: Preserve the LAN forwarder, setup order, Redis-backed lookup, waiting event stream, owner-checked leases, C07 fixture and ordinary-path self-test. No new infrastructure, dependencies, brokers, frameworks or abstractions; no Redis redesign. No Git writes, image build, installs, services or device commands. Preserve unrelated C05/C07 work.
- acceptance: Ambiguous dispatch never authorises local fallback, pending work stays recoverable, the distributed self-test cannot pass on a fallback, and the Dockerfile matches the handoff.
- verification_authorization: Implementation plus the existing offline suites and syntax checks; no image build or device execution.
- follow_up_to: [UP-20260905-008](#up-20260905-008)
- linked_changes: [AC-20260905-009](agentchangelog.md#ac-20260905-009)

<a id="up-20260905-010"></a>
## UP-20260905-010 — Require the canonical job to pass the distributed self-test
- date: 2026-09-05
- status: implemented and focused-check passed; C06 device gate remains unrun
- scope: c06, self-test, review-fix
- tags: c06, self-test-verdict, canonical-job, regression
- aliases: completed remote attempt with failed job, self-test false positive
- paths: backend/coordinator/server.py, backend/coordinator/dispatch.py, backend/coordinator/test_dispatch.py, agent-memory/
- summary: The focused re-review found that a completed remote attempt could report a passing self-test even when the canonical job later failed.
- request: Apply only the smallest verdict correction and focused regression, without reopening the broader C06 review.
- constraints: Preserve all other C06/C07 work; no Git writes, build, deployment, install or device action.
- acceptance: A self-test passes only when the canonical job and a relationship-bound attempt both complete.
- verification_authorization: Run only the affected coordinator test module and `git diff --check`.
- follow_up_to: [UP-20260905-009](#up-20260905-009)
- linked_changes: [AC-20260905-010](agentchangelog.md#ac-20260905-010)

<a id="up-20260905-011"></a>
## UP-20260905-011 — Remove test credentials from the worker image build
- date: 2026-09-05
- status: implemented; Ubuntu rebuild pending
- scope: c06, dockerfile, secrets, image-build
- tags: c06, dockerfile, credentials, image-build, test-boundary
- aliases: dummy token in build history, coordinator import missing, Ubuntu C06 build failure
- paths: backend/worker-image/Dockerfile, backend/worker/test_executor.py, agent-memory/
- summary: Remove dummy identity values from the Dockerfile and keep the worker image build independent of coordinator-only source.
- request: Ensure generated IDs and tokens stay in secret storage rather than appearing in the Dockerfile after the Ubuntu C06 build exposed fixed test values.
- constraints: Preserve runtime Kubernetes Secret and TLS-file handling; fix only the failed image-build boundary without adding secret infrastructure.
- acceptance: The Dockerfile contains no token or node-ID value, and its worker-only offline suite does not import uncopied coordinator code.
- verification_authorization: No local test rerun requested; the authoritative check is the next Ubuntu image rebuild.
- follow_up_to: [UP-20260905-010](#up-20260905-010)
- linked_changes: [AC-20260905-011](agentchangelog.md#ac-20260905-011)

<a id="up-20260905-012"></a>
## UP-20260905-012 — Pin the observed C06 Ubuntu image
- date: 2026-09-05
- status: implemented; source push and deployment pending
- scope: c06, image-digest, manifests, provenance, handoff
- tags: c06, ubuntu, image-digest, containerd, provenance, deployment
- aliases: daf1052b, single manifest, digest alias, pin C06 image
- paths: backend/worker-image/provenance.json, deploy/k3s/20-worker.yaml, deploy/k3s/40-executor.yaml, deploy/k3s/test_manifests.py, docs/c06-distributed-execution-handoff.md, agent-memory/
- summary: Record and pin the single-manifest C06 image built and imported on the Ubuntu worker.
- request: Continue the C06 device checkpoint after containerd confirmed the C06 tag and explicit digest alias resolve to the same observed manifest.
- constraints: Use only observed digests; keep credentials outside the image and do not deploy the executor before pairing.
- acceptance: Both manifests pin the observed C06 digest, provenance distinguishes observed from unavailable archive evidence, and the build handoff produces a single manifest plus digest alias.
- verification_authorization: Source consistency only; deployment and runtime checks remain human steps.
- follow_up_to: [UP-20260905-011](#up-20260905-011)
- linked_changes: [AC-20260905-012](agentchangelog.md#ac-20260905-012)

<a id="up-20260905-013"></a>
## UP-20260905-013 — Make the mounted TLS key readable to the non-root worker
- date: 2026-09-05
- status: implemented; Ubuntu rollout retry pending
- scope: c06, kubernetes, tls, permissions, rollout
- tags: c06, kubernetes, tls, fsgroup, non-root, crashloopbackoff
- aliases: uvicorn permission denied, tls key unreadable, C06 pod crash
- paths: deploy/k3s/20-worker.yaml, deploy/k3s/test_manifests.py, agent-memory/
- summary: Fix the C06 worker startup failure without weakening the TLS private-key mode.
- request: Continue the live C06 rollout after the new worker Pod failed while Uvicorn loaded the mounted certificate chain.
- constraints: Preserve UID/GID 10001, mode 0440, the old ready worker during rollout, and all existing isolation boundaries.
- acceptance: Kubernetes assigns the secret volume to group 10001 so the non-root worker can read the key while other users cannot.
- verification_authorization: Source consistency only; the Ubuntu rollout is the authoritative check.
- follow_up_to: [UP-20260905-012](#up-20260905-012)
- linked_changes: [AC-20260905-013](agentchangelog.md#ac-20260905-013)

<a id="up-20260905-014"></a>
## UP-20260905-014 — Remove the invalid NodePort listener precheck
- date: 2026-09-05
- status: implemented; Ubuntu guard installation pending
- scope: c06, k3s, nodeport, systemd, handoff
- tags: c06, k3s, nodeport, systemd, socket-proxy, runtime-evidence
- aliases: empty ss, packet-rule NodePort, guard precheck timeout, TLS curl root certificate
- paths: deploy/k3s/host/aegisforge-worker-guard.service, deploy/k3s/host/test_guard.py, docs/c06-distributed-execution-handoff.md, agent-memory/
- summary: Remove a worker-guard startup check that incorrectly assumes a K3s NodePort appears as a process listener.
- request: Continue C06 after loopback TLS succeeded while `ss` correctly showed no listener for the packet-rule NodePort.
- constraints: Preserve the loopback-only K3s setting, guard-before-socket dependency, pinned TLS proof, and single-Mac firewall restriction.
- acceptance: The guard can start on the observed K3s implementation without weakening its firewall dependency, and the handoff treats TLS as functional proof.
- verification_authorization: Source consistency only; the Ubuntu systemd activation is the authoritative check.
- follow_up_to: [UP-20260905-013](#up-20260905-013)
- linked_changes: [AC-20260905-014](agentchangelog.md#ac-20260905-014)

<a id="up-20260905-015"></a>
## UP-20260905-015 — Consolidated C07–C10 source and artifact preparation
- date: 2026-09-05
- status: implemented; every C06–C10 human runtime gate still pending
- scope: c07, c08, c09, c10, documents, code, sandbox, approvals, proof, artifacts
- tags: c08, c09, c10, paddleocr-vl, quartz, resource-package, kubernetes-job, approvals, proof-cards
- aliases: consolidated execution, ocr on mac, code on ubuntu, validation job, durable write recovery
- paths: backend/coordinator/, backend/worker/, backend/contracts/v1.py, deploy/k3s/, frontend/app/, docs/, tasks.md
- summary: Build C08 Mac Documents/OCR, C09 distributed Code with a restricted Kubernetes validation Job, and C10 concurrency, approval binding, durable writes and Proof Cards in one cycle ahead of the human gates.
- request: Implement the complete C07-preparation-through-C10 source and offline-verifiable artifact candidate in one consolidated pass for a single combined Codex review.
- constraints: Mac keeps Documents and coordination; Ubuntu runs code generation and a restricted Kubernetes Job sandbox; reuse existing dispatch/approval/repository/SQLite/Redis paths; no installs, downloads, model pulls, Git writes, host or cluster mutation; ports 8080/8443/30443 unchanged.
- acceptance: Source and offline checks cover both workflows and their concurrency, approvals bind to exact workflow outputs, Proof Cards cite observed sources only, and rebuilt artifacts carry recorded digests.
- verification_authorization: Offline checks, bounded loopback Ollama reads, cached-input image build and macOS packaging only; all live device gates stay unrun.
- follow_up_to: [UP-20260905-014](#up-20260905-014)
- linked_changes: [AC-20260905-015](agentchangelog.md#ac-20260905-015)

<a id="up-20260905-016"></a>
## UP-20260905-016 — Close the C08–C10 review findings
- date: 2026-09-05
- status: implemented; every C06–C10 human runtime gate still pending
- scope: c08, c09, c10, model-selection, validation, sandbox, cleanup, proof
- tags: model-selector, paddleocr, auto-model, validation-gate, kubernetes-rbac, package-retention, proof-cards
- aliases: execute review fixes, unreachable validation, zero tests, job create escalation, unstable citation ids
- paths: backend/coordinator/, backend/worker/, deploy/k3s/, frontend/app/, docs/, tasks.md, agent-memory/
- summary: Apply the consolidated Codex review corrections so model choice is real, validation is reachable and meaningful, Kubernetes workload authority is contained, temporary packages expire, and Proof Cards use persisted evidence.
- request: Execute and solve the seven issues found in the review of the consolidated C07–C10 candidate.
- constraints: Preserve the accepted C08–C10 foundations and unrelated work; no Git/GitHub writes, downloads, installs, model pulls, deployment, or host/cluster mutation; every C06+ human gate remains pending.
- acceptance: Installed models are selectable by workflow with disabled Auto; apply requires a current observed passing validation that ran tests; sandbox authority cannot reach operational credentials; packages are cleaned at terminal acknowledgement, startup and periodically; Proof Card identities and sources are stable.
- verification_authorization: Run focused and proportionate offline tests and static checks only; no live service, cluster or model execution.
- follow_up_to: [UP-20260905-015](#up-20260905-015)
- linked_changes: [AC-20260906-001](agentchangelog.md#ac-20260906-001)

<a id="up-20260905-017"></a>
## UP-20260905-017 — A turning mark and a shining "Refinix Working" while the model runs
- date: 2026-09-05
- tags: refinix, chat, code-surface, composer, working-indicator, brand-mark, animation
- aliases: it just gets stuck then dumps the output, claude orange thinking animation, spin the logo, refinix working shine, bottom of chat and code
- paths: frontend/app/
- summary: Requester reported that Chat and Code show nothing between sending a request and the answer appearing, so the application reads as stuck. Asked for a Claude-style activity indicator at the bottom of both surfaces: the attached Refinix mark spinning continuously until the whole output is delivered, with small translucent "Refinix Working" text beside it carrying a continuous shine.
- constraints: Use the supplied Refinix mark, spin it because the artwork is circular, keep spinning for the full output, place it at the bottom as Claude does, and give the label a shining/reflecting animation.
- follow_up_to: [UP-20260905-006](#up-20260905-006)
- linked_changes: [AC-20260905-016](agentchangelog.md#ac-20260905-016)

<a id="up-20260905-018"></a>
## UP-20260905-018 — Copy as an icon on the right, and a round arrow for Jump to latest
- date: 2026-09-05
- tags: refinix, chat, code-surface, copy-control, jump-latest, icons
- aliases: copy reply icon after the output, small copy logo to the right, as it is on left now, arrow type circle icon, jump to latest screenshot
- paths: frontend/app/
- summary: Requester asked for two controls to become icons. The reply's "Copy reply" button under each answer becomes a small copy glyph at the right-hand end of the row rather than a worded button on the left. "Jump to latest" becomes the round outlined down-arrow shown in the supplied screenshot.
- constraints: Copy control moves to the right and becomes a small icon; the jump control takes the circular down-arrow form from the attached screenshot.
- follow_up_to: [UP-20260905-017](#up-20260905-017)
- linked_changes: [AC-20260905-017](agentchangelog.md#ac-20260905-017)

<a id="up-20260905-019"></a>
## UP-20260905-019 — Switch between installed models, drop the standing hint, tighten the chat box
- date: 2026-09-05
- tags: refinix, chat, model-selection, composer, coordinator-api, ollama
- aliases: switch model via that drop down arrow, more than one model installed, delete runs on this computer, big space heightwise looking bad
- paths: frontend/app/, backend/coordinator/
- summary: Three changes to the Chat composer. The model pill must become a real switcher — a computer with more than one model installed should be able to choose which one runs, from a list behind the pill's arrow, as in the attached screenshot. The standing "Runs on this computer" line comes out of the composer. The prompt box carries too much empty height and should be tightened.
- constraints: The switcher must actually switch, not just list. Screenshot supplied showing the model list above the pill.
- follow_up_to: [UP-20260905-018](#up-20260905-018)
- linked_changes: [AC-20260905-018](agentchangelog.md#ac-20260905-018)

<a id="up-20260906-001"></a>
## UP-20260906-001 — Repair the Python 3.13 worker image checks
- date: 2026-09-06
- status: implemented; Ubuntu rebuild pending
- scope: c06, c09, worker-image, offline-tests
- tags: docker-build, python-3.13, model-digest, zero-tests, test-fixture
- aliases: selected model is not installed, exit status 5, worker image 11 failures
- paths: backend/worker/test_worker_app.py, backend/worker/test_validation.py, agent-memory/
- summary: Repair the two stale test assumptions exposed by the authoritative Ubuntu worker-image build without weakening production admission or validation.
- request: Continue the ordered live setup after the Ubuntu C09 worker image ran 213 offline checks and failed 11.
- constraints: Keep model-digest admission fail-closed and keep zero discovered tests from passing; change only the shared fixtures that drifted across environments.
- acceptance: The focused worker API and validation suites pass locally, and the Ubuntu image build is rerun as the authoritative gate.
- verification_authorization: Focused offline tests and static checks locally; the container build remains the live Ubuntu check.
- follow_up_to: [UP-20260905-016](#up-20260905-016)
- linked_changes: [AC-20260906-002](agentchangelog.md#ac-20260906-002)

<a id="up-20260906-002"></a>
## UP-20260906-002 — Pin the observed C09 Ubuntu image
- date: 2026-09-06
- status: implemented; publication and K3s import pending
- scope: c06, c09, image-digest, provenance, manifests, handoff
- tags: ubuntu, docker, image-digest, archive, kubernetes, provenance
- aliases: 774218db, 873cd89c, 06013413, c09 image pin
- paths: backend/worker-image/provenance.json, deploy/k3s/, docs/c07-c10-runtime-handoff.md, tasks.md, agent-memory/
- summary: Pin the requester-observed C09 Ubuntu image and archive evidence everywhere the worker, executor and validation policy consume it.
- request: Continue the ordered setup after the Ubuntu image build passed and its digest, platform and archive evidence were returned.
- constraints: Use only observed digests and byte count; keep the archive outside Git; do not import, deploy or claim runtime acceptance from the build.
- acceptance: All four runtime image fields match provenance, the runnable handoff uses the same digest, and focused manifest checks pass.
- verification_authorization: Focused offline manifest and source consistency checks only; Ubuntu publication and cluster actions remain human gates.
- follow_up_to: [UP-20260906-001](#up-20260906-001)
- linked_changes: [AC-20260906-003](agentchangelog.md#ac-20260906-003)

<a id="up-20260906-003"></a>
## UP-20260906-003 — Repair the live C09 admission dry-run
- date: 2026-09-06
- status: implemented; Ubuntu server dry-run retry pending
- scope: c06, c09, kubernetes, admission-policy, runtime-handoff
- tags: cel, validatingadmissionpolicy, map-membership, pvc, rollout-order
- aliases: invalid argument to has macro, aegisforge jobs not found, pending worker
- paths: deploy/k3s/50-validation.yaml, deploy/k3s/test_manifests.py, docs/c07-c10-runtime-handoff.md, agent-memory/
- summary: Fix the invalid CEL map-key check and move C09 prerequisites before the worker rollout that consumes their PVC.
- request: Continue setup after the new worker stayed Pending on the missing jobs PVC and the server dry-run rejected the admission expression.
- constraints: Preserve fail-closed admission, use the Kubernetes-supported map membership operator, and do not apply anything until server dry-run passes.
- acceptance: Focused manifest checks pass and the live K3s server accepts every rendered object in dry-run.
- verification_authorization: Focused offline manifest checks locally; the Ubuntu server dry-run remains the authoritative compiler check.
- follow_up_to: [UP-20260906-002](#up-20260906-002)
- linked_changes: [AC-20260906-004](agentchangelog.md#ac-20260906-004)

<a id="up-20260906-004"></a>
## UP-20260906-004 — Connect C09 Pods to the observed runtime bridge
- date: 2026-09-06
- status: implemented; publication and live Pod verification pending
- scope: c06, c09, runtime, configmap, network-policy, handoff
- tags: ollama, cni0, runtime-host, egress, worker, executor
- aliases: health unavailable, 10.42.0.1, protected Ollama bridge
- paths: deploy/k3s/20-worker.yaml, deploy/k3s/40-executor.yaml, deploy/k3s/test_manifests.py, docs/c07-c10-runtime-handoff.md, agent-memory/
- summary: Point both C09 consumers at the observed guarded cni0 Ollama bridge and keep that endpoint locked to the narrow egress policy.
- request: Continue setup after the exact C09 worker passed loopback TLS but reported runtime health unavailable while the preserved bridge was stopped.
- constraints: Reuse the existing C05 socket proxy and guard; do not widen Ollama beyond loopback or grant Pod egress beyond the observed bridge /32 and port 11434.
- acceptance: Worker and executor ConfigMaps match the runtime-egress policy, focused checks pass, and the live worker later reports the installed model through the bridge.
- verification_authorization: Focused offline manifest checks locally; publication, policy apply and live worker health remain device gates.
- follow_up_to: [UP-20260906-003](#up-20260906-003)
- linked_changes: [AC-20260906-005](agentchangelog.md#ac-20260906-005)

<a id="up-20260906-005"></a>
## UP-20260906-005 — Repair the executor Pod grace-period field
- date: 2026-09-06
- status: implemented; verification and publication pending
- scope: c06, c09, kubernetes, executor, manifest
- tags: executor, deployment, pod-spec, termination-grace-period, strict-decoding
- aliases: unknown field terminationGracePeriodSeconds, executor deployment not found
- paths: deploy/k3s/40-executor.yaml, deploy/k3s/test_manifests.py, agent-memory/
- summary: Move the executor termination grace period from the container to the Kubernetes Pod spec after the live server rejected the manifest.
- request: Continue setup after K3s strict decoding refused the executor Deployment and therefore created no executor Pod.
- constraints: Preserve the 40-second recovery allowance and change only the invalid field placement with one regression check.
- acceptance: Offline manifest checks pass, K3s accepts the Deployment, and the executor becomes Ready.
- verification_authorization: Requester runs the focused manifest suite and live K3s apply; Git publication remains a human action.
- follow_up_to: [UP-20260906-004](#up-20260906-004)
- linked_changes: [AC-20260906-006](agentchangelog.md#ac-20260906-006)

<a id="up-20260906-006"></a>
## UP-20260906-006 — Repair the collapsed model selector
- date: 2026-09-06
- status: implemented and locally verified; publication and packaged-app rebuild pending
- scope: refinix, frontend, model-selection, c06-acceptance
- tags: model-selector, css-grid, accessibility, chat, routing
- aliases: vertical model text, fourteen pixel column, broken model dropdown
- paths: frontend/app/app.js, frontend/app/test-composer.cjs, agent-memory/
- summary: Render each model choice into the tick, name and location cells already defined by the selector's CSS grid.
- request: Repair the unusable model chooser exposed while switching Chat from PaddleOCR to the paired worker model during live C06 acceptance.
- constraints: Reuse the existing CSS and coordinator selection API; do not change routing, model inventory or visual tokens.
- acceptance: The browser check proves each option has three cells, the selector is legible after reload, and the worker model can be selected.
- verification_authorization: Requester runs the focused browser test and visually verifies the live selector; Git publication remains a human action.
- follow_up_to: [UP-20260906-005](#up-20260906-005)
- linked_changes: [AC-20260906-007](agentchangelog.md#ac-20260906-007)

<a id="up-20260906-007"></a>
## UP-20260906-007 — Preserve work across an executor rollout
- date: 2026-09-06
- status: implemented and locally verified; worker-image rebuild and live retry pending
- scope: c06, worker, executor, recovery, pairing
- tags: sigterm, redis-streams, restart-recovery, pairing-reload, worker-image
- aliases: cancelled before completion, rollout restart lost work, fresh pairing code refused
- paths: backend/worker/executor.py, backend/worker/pairing.py, backend/worker/test_executor.py, agent-memory/
- summary: Keep an in-flight entry recoverable on executor shutdown and make the running worker API see codes minted by the separate host CLI.
- request: Continue C06 after the live executor-rollout check preserved partial output but terminally cancelled the attempt instead of recovering it.
- constraints: Preserve explicit user cancellation and deadline behavior; keep the entry pending without a false terminal event; rebuild the worker image only once for both live-proven defects.
- acceptance: Focused executor checks pass, the rebuilt image pairs without an API restart, and a live executor rollout resumes the same attempt to completion.
- verification_authorization: Requester runs the focused offline suite and the reviewed Ubuntu rebuild and recovery steps; Git publication remains a human action.
- follow_up_to: [UP-20260906-006](#up-20260906-006)
- linked_changes: [AC-20260906-008](agentchangelog.md#ac-20260906-008)

<a id="up-20260906-008"></a>
## UP-20260906-008 — Add one-command presentation startup
- date: 2026-09-06
- status: implemented and locally verified; publication and device installation pending
- scope: c06, presentation, launcher, macos, ubuntu
- tags: refinix-start, motorola-hotspot, systemd, k3s, fail-closed
- aliases: Refinix start, college presentation, two-device startup
- paths: scripts/refinix, scripts/test_refinix_launcher.py, agent-memory/
- summary: Add one cross-platform command that verifies the fixed Motorola hotspot addresses before opening the Mac coordinator or starting the guarded Ubuntu stack.
- request: Make `Refinix start` a presentation-day command on both devices while the same Motorola hotspot travels with the team.
- constraints: Refuse unexpected addresses before changing host state, expose no secret, preserve the guarded listener, and reuse existing services and deployments.
- acceptance: Offline launcher checks pass, both command spellings install on each device, Ubuntu reaches Ready, and Mac opens Refinix only after the worker port is reachable.
- verification_authorization: Requester runs the focused offline checks and reviewed installation commands on both devices; Git publication remains a human action.
- follow_up_to: [UP-20260906-007](#up-20260906-007)
- linked_changes: [AC-20260906-009](agentchangelog.md#ac-20260906-009)

<a id="up-20260906-009"></a>
## UP-20260906-009 — Desktop Execution 4A: local documents and attachment intelligence
- date: 2026-09-06
- status: implemented and locally verified; requester acceptance pending
- scope: execution-4a, documents, attachments, macos, local-only
- tags: pdf-output, image-ocr, xlsx, chat-attachments, general-document, write-document
- aliases: convert answer to pdf, ocr an image into a document, read a spreadsheet, chat reads files
- paths: backend/coordinator/, frontend/app/, agent-memory/
- summary: Make Refinix useful as a standalone local application — put a finished answer into a Word or PDF file, read PNG and JPEG scans directly, report search locations in the unit each format supports, read attachments in ordinary Chat, and add a general document workflow beside the fixed approval note.
- request: Implement Execution 4A entirely, on the macOS device only, without changing the working Mac-to-Ubuntu architecture.
- constraints: Local device only. No change to `backend/contracts/v1.py`, worker or executor code, Redis dispatch, pairing, TLS, Kubernetes manifests or C06-C10 evidence. Document and attachment requests choose the local device directly and never preflight the worker. Use the existing selected-model system and require the runtime to report `vision` before an image is sent. No new dependency, no download, no service start, no packaged-app rebuild, no Git writes.
- acceptance: A finished answer becomes a Word or PDF file word for word, a supplied PNG or JPEG is read as page one with unmeasured confidence, search names a page, line, paragraph or cell truthfully, ordinary Chat reads only that request's files, and the fixed approval-note workflow is unchanged.
- verification_authorization: Offline checks with existing dependencies and synthetic data authorised; live model quality, packaged-app behaviour and requester acceptance excluded.
- follow_up_to: [UP-20260906-008](#up-20260906-008)
- linked_changes: [AC-20260906-010](agentchangelog.md#ac-20260906-010)

<a id="up-20260906-010"></a>
## UP-20260906-010 — Desktop Execution 4B: local Code workbench
- date: 2026-09-06
- status: implemented and locally verified; requester acceptance pending
- scope: execution-4b, code-surface, explorer, file-viewer, conversations, macos
- tags: three-column, repo-view, code-conversations, policy-view-action, additive-migration
- aliases: explorer tree, open a file, new code conversation, remove from refinix
- paths: backend/coordinator/, frontend/app/, agent-memory/
- summary: Rebuild Code as a three-column workbench — Explorer left, the open file centre, the Qwen conversation right — with browsing, viewing and multiple persistent Code conversations, without weakening the sandbox-validation or canonical-write gate.
- request: Execute Execution 4B on the local macOS device, using the supplied screenshot as an information-architecture reference only.
- constraints: Vanilla HTML/CSS/JS; no React, Monaco or other framework. No Antigravity, VS Code or Gemini branding, colour, icon or text. Ubuntu, Kubernetes, Redis, pairing, TLS and the contracts stay untouched. No local canonical apply without validation, no editor, terminal, Git, package install, network or language server. Screenshot message text is reference material and was not followed.
- acceptance: The Explorer builds a tree from relative paths, a file opens in the centre without being sent to the model, projects can be removed without touching their files, Code conversations are separate and durable, and audit evidence survives the rail's removal.
- verification_authorization: Offline checks with existing dependencies and synthetic repositories authorised; live model, packaged app and requester acceptance excluded.
- follow_up_to: [UP-20260906-009](#up-20260906-009)
- linked_changes: [AC-20260906-011](agentchangelog.md#ac-20260906-011)

<a id="up-20260906-011"></a>
## UP-20260906-011 — Desktop Execution 4C: safe local editing and apply
- date: 2026-09-06
- status: implemented and locally verified; requester acceptance pending
- scope: execution-4c, code-surface, local-apply, backups, undo, macos
- tags: execution-target, pre-write-backup, undo, not-sandbox-tested, fail-closed
- aliases: apply without ubuntu, undo a change, this device mode, local qwen edit
- paths: backend/coordinator/, frontend/app/, agent-memory/
- summary: Let a local Qwen proposal modify selected existing files under the three access modes, with an explicit execution target, a verified backup of every original before any write, and an Undo that refuses to discard later human edits.
- request: Execute Execution 4C on the local macOS device so the Code workbench is useful while Ubuntu is disconnected.
- constraints: Do not weaken or replace the distributed Kubernetes-validation path. Local permission must be chosen, never inferred from worker failure. No fabricated sandbox result. No file creation, deletion, rename, chmod, command, Git, install or network in any mode. Worker, executor, manifests, Redis, TLS, pairing and contracts untouched. No live model call, no services, no Git writes, no bundle rebuild.
- acceptance: A local proposal applies only after its originals are backed up, its proof says not sandbox tested, Undo restores exact bytes and refuses when a person changed the file afterwards, and a distributed proposal still requires an observed passing Kubernetes validation.
- verification_authorization: Offline checks against synthetic repositories and temporary databases authorised; live Qwen output, packaged app, Ubuntu validation and requester acceptance excluded.
- follow_up_to: [UP-20260906-010](#up-20260906-010)
- linked_changes: [AC-20260906-012](agentchangelog.md#ac-20260906-012)

<a id="up-20260907-001"></a>
## UP-20260907-001 — Executions 4A–4C integrated review corrections
- date: 2026-09-07
- status: implemented and locally verified; requester and Codex re-review pending
- scope: execution-4a, execution-4b, execution-4c, review-fixes, macos
- tags: fail-closed-target, verified-backups, conversation-ownership, local-attachments, aggregate-limits
- aliases: codex review fixes, corrupted target, backup verification, ask mode view approval
- paths: backend/coordinator/, frontend/app/, agent-memory/
- summary: Fix the ten defects Codex found in the combined 4A–4C review, plus a concurrent-backup race Claude found, without weakening the distributed Kubernetes validation path.
- request: Execute the full Codex correction set, items 1–10, including the UNIQUE(proposal_id, path) race, and do not defer the XLSX, PDF, conversion or removal-locking items.
- constraints: No packaged app rebuild, no Ubuntu or worker-image work, no live model call, no services, no Kubernetes/Docker/Redis/worker contact, no dependency installation, no Git or GitHub writes. The distributed apply gate must remain unchanged.
- acceptance: An unrecognised execution target stops before validation, approval, backup or writing; every local write is preceded by a verified backup; Code conversations own their local work; Ask-mode viewing completes its approval; a Chat request with files is answered locally; attachment context is bounded and never silently empty; XLSX has aggregate ceilings; no document output is silently truncated; removal is refused during active work; the ledgers state what the code does.
- verification_authorization: The already-authorised offline checks only.
- follow_up_to: [UP-20260906-011](#up-20260906-011)
- linked_changes: [AC-20260907-001](agentchangelog.md#ac-20260907-001)

<a id="up-20260907-002"></a>
## UP-20260907-002 — Codex closeout of Execution 4 integration defects
- date: 2026-09-07
- status: implemented and locally verified; requester and external runtime gates pending
- scope: execution-4a, execution-4b, execution-4c, review-fixes, macos
- tags: conversation-isolation, durable-approval, backup-hardening, bounded-context, lossless-pdf
- aliases: codex execute fixes, code conversation restore, reject proposal, safe project removal
- paths: backend/coordinator/, frontend/app/, agent-memory/
- summary: Repair the remaining verified 4A–4C integration defects in the shared coordinator and source UI while preserving the disconnected local path and the distributed validation boundary.
- request: Implement the full remaining correction set directly rather than sending another Claude prompt.
- constraints: No Git or GitHub writes, packaged-app rebuild, dependency installation, live model or service call, Ubuntu/Kubernetes/Docker/Redis/worker contact, or changes under backend/worker, backend/contracts or deploy.
- acceptance: Validation resolves the stored target before routing; Code state, approvals, audit and restored UI stay conversation-owned; Reject and Ask-mode view work durably; project removal is locked and explicitly acknowledges lost Undo; model prompts are bounded; PDF text and backups are not silently lost or escaped.
- verification_authorization: Proportionate offline checks with existing dependencies and isolated data only; packaged app, live Qwen, distributed worker and requester acceptance remain external gates.
- follow_up_to: [UP-20260907-001](#up-20260907-001)
- linked_changes: [AC-20260907-002](agentchangelog.md#ac-20260907-002)

<a id="up-20260907-003"></a>
## UP-20260907-003 — Run CI when work reaches main
- date: 2026-09-07
- status: implemented; first GitHub run and server-side enforcement pending
- scope: github-actions, ci, main, release-flow
- tags: main-ci, push, pull-request, python, frontend
- aliases: enable CI for main push, main push checks, release CI
- paths: .github/workflows/ci.yml, CONTRIBUTING.md, agent-memory/
- summary: Add one read-only CI job for main-targeting pull requests and commits that land on main without weakening the repository's PR-only release rule.
- request: Enable CI because the requester intends to publish the current work to main.
- constraints: Do not perform Git or GitHub writes; preserve the existing dev-to-main flow guard; use pinned dependencies and action commits; do not contact Ubuntu, Kubernetes, Redis, Docker or a live model.
- acceptance: Main-targeting pull requests and main pushes run the same Python and frontend checks, the flow guard remains pull-request-only, and documentation states that post-push CI cannot block a direct push.
- verification_authorization: Static workflow inspection only; the first GitHub-hosted run is the execution gate.
- follow_up_to: [UP-20260901-002](#up-20260901-002)
- linked_changes: [AC-20260907-003](agentchangelog.md#ac-20260907-003)

<a id="up-20260913-001"></a>
## UP-20260913-001 — Reconcile the Refinix production direction
- date: 2026-09-13
- status: authorised documentation update
- tags: product-direction, offline, cross-platform, automatic-routing, installation, rag
- aliases: production refinix, any device worker, no terminal setup, optional kubernetes, bundled llama.cpp
- paths: README.md, TechStack.md, tasks.md, docs/prd.md, docs/architecture.md, docs/workflows.md, docs/security.md, docs/model-catalog.md, docs/evaluation.md, docs/README.md, docs/devicespecifications.md, agent-memory/
- summary: Update the core product and implementation guidance from the production-planning discussion without fixed implementer roles, team assignments, or deadlines.
- request: Preserve the current UI; document guided installation, user-controlled model recommendations, offline local/trusted-device/private-server modes, concurrent automatic placement, local RAG, and component qualification.
- constraints: Documentation only; distinguish current source, historical prototype evidence, accepted direction, and unqualified candidates; preserve existing Kubernetes backend and security guarantees; no runtime or Git/GitHub changes.
- acceptance: The entry points and focused documents agree on the production direction and evidence boundaries, with outcome-based implementation gates and intact local links.
- verification_authorization: Proportionate static documentation checks only.
- linked_changes: [AC-20260913-001](agentchangelog.md#ac-20260913-001)

<a id="up-20260913-002"></a>
## UP-20260913-002 — Rename the repository to refinix
- date: 2026-09-13
- status: authorised rename; GitHub administrator access unavailable
- tags: repository-name, refinix, documentation, github
- aliases: rename aegisforge, refinix repository
- paths: README.md, CONTRIBUTING.md, AGENTS.md, docs/README.md, docs/prd.md, agent-memory/
- summary: Rename the repository from AegisForge to refinix and align its documentation identity.
- request: Use refinix as the repository name while preserving the existing application and workspace.
- constraints: Preserve earlier uncommitted documentation; do not rename compatibility-sensitive data paths or invent a completed GitHub rename.
- evidence: Authenticated GitHub REST metadata reports repository id 1352342428, current name AegisForge, push permission true and admin permission false.
- linked_changes: [AC-20260913-002](agentchangelog.md#ac-20260913-002)

<a id="up-20260914-001"></a>
## UP-20260914-001 — Document release readiness, updates and personalisation
- date: 2026-09-14
- status: authorised documentation execution
- tags: releases, updater, offline, kv-cache, context, corpus, personalisation
- aliases: no calendar deadline, update version, refinix memory, pagedattention, optional training
- paths: README.md, CONTRIBUTING.md, TechStack.md, tasks.md, docs/prd.md, docs/architecture.md, docs/workflows.md, docs/security.md, docs/model-catalog.md, docs/evaluation.md, docs/README.md, docs/releases.md, agent-memory/
- summary: Execute the approved documentation plan for a readiness-based installable core with safe future updates, cache policy and staged personalisation.
- request: Make install/use/upgrade acceptance mandatory for the first public release; preserve offline operation and add context/corpus/cache requirements with optional evaluated training later.
- constraints: Documentation and static checks only; no calendar commitments or fixed implementer identities; preserve operational timeouts, historical evidence, current code and Git/GitHub state.
- follow_up_to: [UP-20260913-001](#up-20260913-001)
- linked_changes: [AC-20260914-001](agentchangelog.md#ac-20260914-001)

<a id="up-20260915-001"></a>
## UP-20260915-001 — Establish the P01 production baseline and support contract
- date: 2026-09-15
- status: authorised P01 execution; device acceptance pending
- tags: p01, production-baseline, support-matrix, fixtures, offline-checks
- aliases: first production task, baseline and support contract, proceed production plan
- paths: docs/evaluation.md, docs/devicespecifications.md, tasks.md, agent-memory/
- summary: Establish the current source and offline-check baseline, candidate platform profiles and representative synthetic fixtures before runtime or packaging qualification.
- request: Proceed with P01 after identifying it as the first production gate.
- constraints: Preserve the current UI, harness, user data and Git state; no installers, downloads, live inference, service changes, worker contact, deployment or publication.
- verification_authorization: Proportionate existing-dependency offline checks with isolated test data; packaged-app, real-model, current worker and clean-device acceptance remain human checkpoints.
- acceptance: Record observed checks, gaps and failure cases separately from historical evidence; advertise no untested platform or capability and obtain current device/profile evidence before closing P01.
- follow_up_to: [UP-20260914-001](#up-20260914-001)
- device_confirmation: Requester confirmed all four inventoried Windows devices are available; three was a typo. Historical specifications are retained, not treated as fresh runtime evidence.
- linked_changes: [AC-20260915-001](agentchangelog.md#ac-20260915-001)

<a id="up-20260915-002"></a>
## UP-20260915-002 — Fix the P01 checkpoint folder layout
- date: 2026-09-15
- status: authorised review correction
- tags: p01, checkpoint, state-isolation, documentation
- aliases: execute review fix, sibling state directory, explain first task
- paths: docs/evaluation.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Correct the reviewed Code checkpoint instructions and explain P01 in plain language.
- request: Execute the review correction without weakening repository containment or treating P01 as complete.
- verification_authorization: Proportionate isolated offline verification of the corrected paths; no live workflow, installation or Git write.
- follow_up_to: [UP-20260915-001](#up-20260915-001)
- linked_changes: [AC-20260915-002](agentchangelog.md#ac-20260915-002)

<a id="up-20260915-003"></a>
## UP-20260915-003 — Check Refinix local runtime on the Mac
- date: 2026-09-15
- status: authorised Refinix-only runtime checks
- tags: p01, local-runtime, chat, documents, code, isolated-state
- aliases: refinix check only, real model checkpoint, return findings
- paths: docs/evaluation.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Check local Refinix workflows using existing models and isolated synthetic test data, then report observed findings.
- request: Execute the authorised Mac checkpoint for Refinix only; no unrelated application or system work.
- constraints: Preserve personal state and existing changes; no installs, downloads, remote worker contact, product fixes or Git writes.
- follow_up_to: [UP-20260915-002](#up-20260915-002)

<a id="up-20260915-004"></a>
## UP-20260915-004 — Implement bounded reliability handoff
- date: 2026-09-15
- status: authorised implementation and focused offline checks
- tags: reliability, artifacts, skills, markdown, source-reuse, ocr, code
- aliases: astra handoff, one-shot skills, structured output diagnostics
- paths: frontend/app/, backend/coordinator/, agent-memory/
- summary: Inspect and implement the supplied six reliability fixes without changing architecture or unrelated work.
- request: Fix duplicate artifacts, skill retention, list numbering, explicit scoped source reuse, OCR outcomes and Code schema/diagnostics; report actual checks and uncertainty.
- constraints: Preserve dirty changes, full-answer conversion, permissions, limits and model defaults; no Git writes, installs, downloads, personal state or live inference.
- verification_authorization: Relevant existing-dependency offline tests and syntax checks with synthetic disposable data.

<a id="up-20260915-005"></a>
## UP-20260915-005 — Fix reliability review findings
- date: 2026-09-15
- status: authorised implementation and proportionate offline checks
- tags: reliability, source-selection, skills, review
- aliases: remote OCR guard, new chat skill race, OCR discussion
- paths: backend/coordinator/server.py, backend/coordinator/docflow.py, backend/coordinator/test_reliability.py, frontend/app/app.js, frontend/app/test-composer.cjs, agent-memory/
- summary: Fix the three reviewed reliability gaps using existing code and synthetic checks.
- request: Execute the review fixes; preserve existing changes and product scope.
- follow_up_to: UP-20260915-004
- linked_changes: AC-20260916-001
- constraints: No Git writes, live models, GUI, downloads or personal state.

<a id="up-20260916-001"></a>
## UP-20260916-001 — Sequence a source-grounded SIH Beta inside the production plan
- date: 2026-09-16
- status: authorised documentation restructure and repository cleanup review
- tags: beta, release-frontier, model-lifecycle, source-audit, canonical-docs
- aliases: SIH Reviewer Preview, Band A, Band B, Band C, Settings Models
- paths: tasks.md, docs/, README.md, TechStack.md, backend/, frontend/README.md, agent-memory/
- summary: Reinspect implementation and evidence, preserve the production architecture, and define the earliest coherent downloadable Beta in canonical documents.
- request: Separate Beta blockers, versioned enhancements and finals/production maturity; make post-onboarding model management explicit; reconcile stale claims and remove only demonstrably obsolete material.
- constraints: Preserve working code, tests, fixtures, security boundaries, historical measurements and user data; no runtime execution, installs, downloads, host changes or Git/GitHub writes authorised by this planning task.
- supersedes: First-publication sequencing in [UP-20260914-001](#up-20260914-001); retains its production architecture and update destination.
- linked_changes: [AC-20260916-002](agentchangelog.md#ac-20260916-002)

<a id="up-20260916-002"></a>
## UP-20260916-002 — Consolidate historical handoffs and make execution self-contained
- date: 2026-09-16
- status: authorised documentation cleanup and affected reference/check maintenance
- tags: documentation-cleanup, archive, execution-context, beta, runbook
- aliases: lightweight professional repository, agent execution guide, retired C03 C04 handoffs
- paths: AGENTS.md, tasks.md, docs/, backend/, deploy/k3s/, scripts/image-digests.py, agent-memory/
- summary: Consolidate obsolete handoffs, retain unique evidence and safety checks, and make canonical documentation support the active execution plan.
- request: Follow the reviewed delete/consolidate/archive recommendation and give future agents sufficient source, acceptance and checkpoint context.
- constraints: Defer root README, website and SIH presentation content work; preserve existing edits, runtime behaviour, fixtures, provenance, historical measurements and Git state.
- verification_scope: Proportionate existing-dependency offline checks for relocated documentation and affected tests; no live devices, downloads, deployment or publication.
- follow_up_to: [UP-20260916-001](#up-20260916-001)
- linked_changes: [AC-20260916-003](agentchangelog.md#ac-20260916-003)

<a id="up-20260918-001"></a>
## UP-20260918-001 — Draft the P01 Beta support contract for requester acceptance
- date: 2026-09-18
- status: authorised documentation draft; parallel P11/P10 coding discussed but not yet started
- tags: p01, beta, support-matrix, baseline, windows
- aliases: P01 proposed matrix, Beta support contract draft, Windows contributor
- paths: docs/evaluation.md, agent-memory/
- summary: Draft the narrow P01 Beta support matrix and acceptance thresholds while the macOS runtime checkpoint is run separately by its device holder.
- request: Start P01 completion from a Windows 11 contributor device; the macOS arm64 device remains with a teammate for the runtime checkpoint.
- constraints: Proposal only; no requester acceptance, runtime checks, installs, downloads or Git writes.
- follow_up_to: [UP-20260916-002](#up-20260916-002)
- linked_changes: [AC-20260918-001](agentchangelog.md#ac-20260918-001)

<a id="up-20260918-002"></a>
## UP-20260918-002 — Require all three desktop OSes in Beta and record manual findings
- date: 2026-09-18
- status: authorised canonical documentation correction
- tags: beta, portability, p01, documents, code, manual-evidence
- aliases: not macOS only, M5 Tahoe 26.7, unsupported approval note
- paths: TechStack.md, tasks.md, docs/prd.md, docs/architecture.md, docs/workflows.md, docs/releases.md, docs/evaluation.md, docs/devicespecifications.md, agent-memory/
- summary: Make Windows, macOS and Linux first-Beta requirements and record the supplied Mac walkthrough failures without changing runtime code.
- request: Update the docs immediately, include document and Code issues, and keep execution focused on portability of the existing app.
- constraints: Preserve working behaviour; no runtime execution, installs, downloads, Git writes or public-presentation rewrite.
- supersedes: Mac-only Beta proposal in [UP-20260918-001](#up-20260918-001) and OS deferral in [UP-20260916-001](#up-20260916-001).
- linked_changes: [AC-20260918-002](agentchangelog.md#ac-20260918-002)

<a id="up-20260919-001"></a>
## UP-20260919-001 — Reconcile seven residual documentation conflicts
- date: 2026-09-19
- status: authorised focused documentation and diagram correction
- tags: beta, portability, evidence, model-ranking, diagram, documentation
- aliases: seven residual findings, retired AF mappings, OD-08 chronology
- paths: docs/evaluation.md, docs/devicespecifications.md, docs/releases.md, docs/model-catalog.md, docs/workflows.md, docs/architecture.md, docs/workflow-diagram.html, agent-memory/
- summary: Close the remaining OS scope, recovery, ranking, historical coverage and diagram claim/network conflicts.
- constraints: Preserve prior dirty edits, historical evidence and runtime behaviour; no installs, live tests, model calls or Git writes.
- follow_up_to: [UP-20260918-002](#up-20260918-002)
- linked_changes: [AC-20260919-001](agentchangelog.md#ac-20260919-001)

<a id="up-20260919-002"></a>
## UP-20260919-002 — Recheck the revised plan and begin Phase 1 execution
- date: 2026-09-19
- status: authorised implementation of a named Phase 1 slice on the macOS device
- tags: phase-1, portability, platform-paths, credentials, execution
- aliases: P plan retired, all-OS setup, move to execution, first Phase 1 batch
- paths: backend/coordinator/, desktop/, frontend/app/, fixtures/c07/, docs/evaluation.md, agent-memory/
- summary: Re-read the revised plan and product contract, then execute the first coherent Phase 1 slice on the available macOS device.
- request: Recheck tasks.md, docs/PROJECT.md and AGENTS.md after the P01-P26 retirement and the shift from a compulsory Mac device to all-OS support, then move to execution.
- decisions: Requester selected the platform data-root abstraction, portable protected credential storage and the fixture portability fix as the first batch; authorised resolving the docs/evaluation.md merge-conflict markers only; authorised adding pypdfium2 for portable PDF rendering when Phase 1 item E is executed.
- constraints: Repository edits limited to the selected batch; no other protected documentation edited; no installs, downloads, model or live runtime calls, deployments or Git/GitHub writes.
- follow_up_to: [UP-20260919-001](#up-20260919-001)
- linked_changes: [AC-20260919-002](agentchangelog.md#ac-20260919-002)

<a id="up-20260919-003"></a>
## UP-20260919-003 — Apply external review repairs before committing the Phase 1 batch
- date: 2026-09-19
- status: authorised focused repair of the uncommitted Phase 1 batch
- tags: phase-1, review, data-root, credentials, documentation
- aliases: codex review, occupancy too narrow, secret-tool prerequisite, keychain_available deprecation
- paths: backend/coordinator/paths.py, backend/coordinator/test_paths.py, backend/coordinator/credentials.py, backend/coordinator/server.py, agent-memory/
- summary: Repair the data-root occupancy rule and two documentation overstatements raised by an external review of the report, before the batch is committed.
- request: Relayed a review that had read the project documents and this session's report but not the source; asked for the flagged issues to be addressed.
- constraints: Repair only; no scope expansion, no new dependency, no protected documentation beyond the already-authorised file, no Git writes.
- follow_up_to: [UP-20260919-002](#up-20260919-002)
- linked_changes: [AC-20260919-003](agentchangelog.md#ac-20260919-003)

<a id="up-20260919-004"></a>
## UP-20260919-004 — Record live data-root acceptance and execute Phase 1 E
- date: 2026-09-19
- status: acceptance recorded; portable PDF rendering authorised
- tags: phase-1, data-root, acceptance, documents, pdf, portability
- aliases: restart persistence passed, pypdfium2 authorised, remove Quartz-only read path
- paths: agent-memory/, backend/coordinator/
- summary: Record the requester's restart-persistence observations, then remove the Quartz-only dependency from the Beta-critical PDF reading path.
- request: Requester reported both live checks passed — completed-task persistence after restart and cancelled-task persistence after restart — then authorised Phase 1 E with the already-approved pypdfium2.
- constraints: Preserve current document behaviour; add portability and failure tests; keep PDF writing separate unless the Phase 1 contract requires it; run the relevant suites and report source-tested and device-observed evidence separately.
- follow_up_to: [UP-20260919-003](#up-20260919-003)
- linked_changes: [AC-20260919-004](agentchangelog.md#ac-20260919-004)

<a id="up-20260919-005"></a>
## UP-20260919-005 — Repair the Documents routing and history defects (Batch 1)
- date: 2026-09-19
- status: authorised focused repair; generation-robustness hardening deferred to a separate batch
- tags: documents, routing, classifier, history, regression, phase-1
- aliases: create a document for your entire output, conversion vs general, text vs content, batch 1
- paths: backend/coordinator/docflow.py, backend/coordinator/test_document_intent.py, agent-memory/
- summary: Fix the confirmed conversion/general misrouting in both directions and the history binding that emptied every general document prompt.
- request: Execute the audited repair only; add the intent matrix and coordinator-level regression coverage; preserve the existing generation architecture.
- decisions: Reviewer rejected a bare verb-list addition because it would deepen the inverse-routing defect; the classifier must decide from source reference. Batch 2 (structured-output enforcement, output sizing, repair retries, truncation detection, parser tolerance) is explicitly NOT authorised yet.
- constraints: No protected-document edits, Git/GitHub writes, installs, model downloads, schema/API/frontend changes, or changes to `response_format`, `num_predict`, retry or JSON-parse tolerance.
- follow_up_to: [UP-20260919-004](#up-20260919-004)
- linked_changes: [AC-20260919-006](agentchangelog.md#ac-20260919-006)

<a id="up-20260919-006"></a>
## UP-20260919-006 — General document generation robustness (Batch 2)
- date: 2026-09-19
- status: authorised narrow robustness repair; Batch 1 accepted and not reopened
- tags: documents, generation, structured-output, repair, truncation, phase-1
- aliases: response_format, num_predict, MAX_ANSWER_TOKENS, one repair round, batch 2
- paths: backend/coordinator/docflow.py, backend/coordinator/server.py, backend/coordinator/test_document_generation.py, backend/coordinator/test_documents.py, agent-memory/
- summary: Make the general-document path dependable once a request has correctly reached it, using the runtime's existing structured-output support.
- request: Enforce a schema on the document call, give it a document-sized output budget, allow at most one bounded repair, reject truncated generation, and decide parser tolerance deliberately.
- constraints: No Documents redesign, no source-mode work, no schema/API/frontend change, no protected-document edits, no Git/GitHub writes, no installs or model downloads. Do not reopen the Batch 1 classifier without direct evidence of a regression.
- follow_up_to: [UP-20260919-005](#up-20260919-005)
- linked_changes: [AC-20260919-007](agentchangelog.md#ac-20260919-007)

<a id="up-20260920-001"></a>
## UP-20260920-001 — Grounded approval-note workflow hardening (Batch 3)
- date: 2026-09-20
- status: authorised hardening of the fixed Documents workflow; Batches 1 and 2 accepted and not reopened
- tags: documents, approval-note, grounding, citations, structured-output, phase-1
- aliases: inspection report plus SOP, C07 hero path, citation resolution, no-SOP honesty, batch 3
- paths: backend/coordinator/docflow.py, backend/coordinator/server.py, backend/coordinator/test_approval_note.py, backend/coordinator/test_document_generation.py, agent-memory/
- summary: Make the inspection-report plus SOP approval note dependable and traceable, reusing the proven Batch 2 mechanisms rather than building a second framework.
- request: Enforce a schema on the note call, size its output, allow one conservative format-only repair, verify retrieval scope and citation grounding, decide no-SOP behaviour from the contract, and add C07 regressions.
- constraints: No Documents redesign, no schema migration, no embeddings, no renderer or writer rewrite, no protected-document edits, no Git/GitHub writes, no installs or model downloads.
- follow_up_to: [UP-20260919-006](#up-20260919-006)
- linked_changes: [AC-20260920-001](agentchangelog.md#ac-20260920-001)

<a id="up-20260920-002"></a>
## UP-20260920-002 — Claim-level citations and product identity (Batch 4)
- date: 2026-09-20
- status: authorised final narrow hardening before manual C07 acceptance
- tags: documents, approval-note, citations, identity, chat, phase-1
- aliases: uncited recommendation, summary citations, I am Qwen, powered by, linked models, batch 4
- paths: backend/coordinator/docflow.py, backend/coordinator/identity.py, backend/coordinator/server.py, backend/coordinator/test_approval_note.py, backend/coordinator/test_identity.py, backend/coordinator/test_documents.py, backend/coordinator/test_execution4a.py, backend/coordinator/test_document_generation.py, agent-memory/
- summary: Close the remaining approval-note citation gap and make Chat identify as Refinix rather than as the underlying model.
- request: Two issues only — a consequential summary or recommendation must carry its own evidence, and the assistant must present itself as Refinix with the actual selected engine and a truthful model count.
- constraints: No semantic entailment work, no model-family hard-coding, no phrase interception, no schema migration, no protected-document edits, no Git/GitHub writes, no installs. Stop after this batch; the requester rebuilds and runs manual C07 acceptance next.
- follow_up_to: [UP-20260920-001](#up-20260920-001)
- linked_changes: [AC-20260920-002](agentchangelog.md#ac-20260920-002)

<a id="up-20260920-003"></a>
## UP-20260920-003 — Expose the approval-note workflow in the composer (Batch 5)
- date: 2026-09-20
- status: authorised narrow frontend wiring; requester rebuilds and reruns C07 next
- tags: documents, frontend, composer, approval-note, workflow, phase-1
- aliases: workflow chooser missing, general route taken, no page citations, batch 5
- paths: frontend/app/index.html, frontend/app/app.js, frontend/app/refinix.css, frontend/app/test-composer.cjs, backend/coordinator/test_approval_note.py, agent-memory/
- summary: Make the fixed grounded workflow selectable from Chat and prove the chosen value reaches the backend branch.
- request: A real C07 attempt attached the scan and the SOP, selected Write a document and asked in plain English for a grounded approval note; the job took the general route because no workflow chooser appeared.
- constraints: No new Documents implementation, no prompt classifiers, no phrase inference, no schema or API change, no Code or model work, no fixing the generic run's date or SOP wording in this batch.
- follow_up_to: [UP-20260920-002](#up-20260920-002)
- linked_changes: [AC-20260920-003](agentchangelog.md#ac-20260920-003)

<a id="up-20260920-004"></a>
## UP-20260920-004 — Composer hierarchy for Write a document (Batch 6)
- date: 2026-09-20
- status: authorised frontend layout refinement; requester rebuilds and verifies the packaged UI next
- tags: frontend, composer, layout, accessibility, documents, phase-1
- aliases: congested composer, prompt squeezed, amber helper row, batch 6
- paths: frontend/app/index.html, frontend/app/app.js, frontend/app/refinix.css, frontend/app/test-composer.cjs, agent-memory/
- summary: Give the prompt visual priority and demote the attachment-order helper from warning styling to guidance.
- request: The workflow is discoverable now, but the composer is congested and the prompt has lost priority; restructure the layout without changing Documents routing or behaviour.
- constraints: Layout only. No routing, payload, OCR, retrieval, model, citation or artifact change. No second workflow state. No custom dropdown replacing the native select. Verify CSS tokens exist before use.
- follow_up_to: [UP-20260920-003](#up-20260920-003)
- linked_changes: [AC-20260920-004](agentchangelog.md#ac-20260920-004)

<a id="up-20260920-005"></a>
## UP-20260920-005 — Consolidated takeover after parallel Chat and agent work
- date: 2026-09-20
- status: authorised reconciliation, review, focused fixes and offline verification; no Git/GitHub writes
- tags: takeover, review, phase-1, documents, identity, data-root, frontend
- aliases: master handover, parallel-agent reconciliation, unreadable-root, duplicate-listener, runtime-probe
- paths: docs/PROJECT.md, tasks.md, backend/coordinator/paths.py, backend/coordinator/server.py, backend/coordinator/test_paths.py, backend/coordinator/test_identity.py, frontend/app/app.js, frontend/app/test-composer.cjs, agent-memory/
- summary: Reconcile the detailed handover with current authority, source, dirty-tree changes and evidence; correct review findings; then continue the largest safe Phase 1 slice without weakening offline or containment boundaries.
- constraints: Preserve all inherited dirty work. Do not edit protected documentation, install or download dependencies, call a live model or remote worker, deploy, or perform Git/GitHub writes. Run focused offline checks only.
- linked_changes: [AC-20260920-005](agentchangelog.md#ac-20260920-005)

<a id="up-20260920-006"></a>
## UP-20260920-006 — Close approval-note evidence and document-structure gaps
- date: 2026-09-20
- status: authorised source fix and focused offline verification; packaged-app rerun pending
- tags: documents, approval-note, evidence-coverage, docx, accessibility, phase-1
- aliases: countersignature omitted, report metadata omitted, normal-only styles, semantic headings
- paths: backend/coordinator/docflow.py, backend/coordinator/docgen.py, backend/coordinator/pdfgen.py, backend/coordinator/server.py, backend/coordinator/test_approval_note.py, backend/coordinator/test_documents.py, backend/coordinator/test_execution4a.py, agent-memory/
- summary: Preserve labelled report identity and explicit missing values independently of model output, and generate semantically structured DOCX lists and headings.
- request: Fix the reviewed P-204 approval-note artifact after it omitted the report's countersignature gap and traceability metadata and encoded every paragraph as Normal style.
- constraints: Preserve inherited dirty work; no protected-document edits, installs, live model or remote-worker calls, deployments, or Git/GitHub writes. Run focused offline tests and render verification only.
- follow_up_to: [UP-20260920-005](#up-20260920-005)
- linked_changes: [AC-20260920-006](agentchangelog.md#ac-20260920-006)

<a id="up-20260920-007"></a>
## UP-20260920-007 — Standalone reviewer candidate across Windows, macOS and Linux
- date: 2026-09-20
- status: authorised independent implementation, offline verification and self-review; no Git/GitHub writes
- tags: phase-1, phase-2, standalone, windows, containment, model-lifecycle, packaging, capability-truth
- aliases: reviewer journey, pinned-handle backend, Settings -> Models, self-test, device roles, packaging boundary
- paths: backend/coordinator/winfs.py, backend/coordinator/repo.py, backend/coordinator/models.py, backend/coordinator/device.py, backend/coordinator/server.py, backend/coordinator/db.py, backend/coordinator/docgen.py, backend/coordinator/proof.py, backend/coordinator/code_service.py, backend/coordinator/dispatch.py, backend/coordinator/paths.py, desktop/packaging.py, desktop/lifecycle.py, desktop/setup_py2app.py, frontend/app/, agent-memory/
- summary: Move the repository materially closer to a dependable standalone Refinix reviewer candidate on the selected Windows, macOS and Linux profiles, in one integrated batch, ending at source and offline evidence rather than a device or release claim.
- request: Independently inspect the repository, decide the smallest coherent implementation for the standalone reviewer journey (install/open, detect environment, explain capabilities, set up or select a local model, self-test, use Chat/Documents/Code, persist and reopen), execute it, verify it and self-review the integrated result.
- constraints: Preserve the inherited dirty tree and the existing trusted-peer, worker, Redis and Kubernetes work. Keep the Ollama runtime adapter; no second inference runtime. Offline-first: no telemetry, background update check, silent download, cloud inference or non-loopback local service. Do not weaken repository containment to make Windows appear supported, and never substitute ordinary path resolution followed by an unrestricted open. No protected-document edits, installs, downloads, model downloads, live model calls, remote-worker access, deployment, credential changes, host-service changes or Git/GitHub writes. Do not publish Beta 0.1.
- follow_up_to: [UP-20260920-006](#up-20260920-006)
- linked_changes: [AC-20260920-007](agentchangelog.md#ac-20260920-007)

<a id="up-20260921-001"></a>
## UP-20260921-001 — Close the standalone reviewer correction batch
- date: 2026-09-21
- status: authorised implementation, focused offline verification and self-review; no Git/GitHub writes
- tags: model-lifecycle, selftest, provenance, remote-chat, containment, frontend, takeover
- aliases: disabled model still runs, representative self-test, manifest mismatch, stale replace window, worker identity, worker-only count
- paths: backend/contracts/, backend/coordinator/, backend/worker/, frontend/app/, agent-memory/
- summary: Take over after the other agent reached its limit and close the six reviewed standalone-reviewer defects with the smallest coherent reuse-first patch.
- request: Fix the reviewed issues directly, independently inspect and self-review the result, reuse existing code instead of introducing parallel machinery, and minimise back-and-forth before human verification.
- constraints: Preserve the committed baseline and unrelated work. No protected-document edits, installs, downloads, live model calls, remote-worker calls, packaging, deployment, credential changes or Git/GitHub writes. Run existing focused offline checks only and keep source/test evidence separate from device and release acceptance.
- follow_up_to: [UP-20260920-007](#up-20260920-007)
- linked_changes: [AC-20260921-001](agentchangelog.md#ac-20260921-001)

<a id="up-20260921-002"></a>
## UP-20260921-002 — Repair the py2app packaging-module collision
- date: 2026-09-21
- status: authorised narrow packaging correction and focused offline verification; packaged acceptance remains pending
- tags: macos, py2app, setuptools, packaging, module-shadowing
- aliases: packaging.utils missing, desktop packaging collision, packaging_plan
- paths: desktop/packaging_plan.py, desktop/setup_py2app.py, desktop/test_packaging.py, agent-memory/
- summary: Rename the Refinix-owned packaging-boundary module so the macOS build path can import setuptools' third-party `packaging` package.
- request: Fix the confirmed `desktop/packaging.py` shadowing failure at its root, retain the shared cross-platform packaging boundary, update all live callers, and add a regression reproducing the build-path import order.
- constraints: No `sys.path` workaround, dependency reinstall/downgrade, setuptools or py2app weakening, unrelated refactor, new dependency, protected-document edit, Git/GitHub write, package acceptance claim or human walkthrough.
- follow_up_to: [UP-20260921-001](#up-20260921-001)
- linked_changes: [AC-20260921-002](agentchangelog.md#ac-20260921-002)

<a id="up-20260921-003"></a>
## UP-20260921-003 — Repair the direct-script setup import and build the macOS package
- date: 2026-09-21
- status: authorised packaging repair, focused verification, real macOS build and bundle inspection; human GUI acceptance still pending
- tags: macos, py2app, packaging, direct-script-import, bundle-inspection
- aliases: No module named 'desktop', setup_py2app direct execution, sys.path[0] script directory
- paths: desktop/setup_py2app.py, desktop/test_packaging.py, agent-memory/
- summary: Fix the `from desktop import packaging_plan` failure that stopped the macOS build after UP-20260921-002, then run `desktop/setup-macos.command` and inspect the resulting bundle.
- request: Verify the repository state independently, repair the direct-script import defect at its root, add a regression modelling the real production invocation, run focused verification, run the actual macOS setup path, continue through directly related packaging blockers, inspect the built `.app`, and stop before the human GUI acceptance walkthrough.
- constraints: No `sys.path`/`PYTHONPATH` workaround, dependency or lock change, py2app replacement, recreated `desktop/packaging.py`, weakened staging/content/signature checks, trust-boundary regression, protected-document edit, Git/GitHub write, model download, GUI walkthrough or acceptance claim.
- follow_up_to: [UP-20260921-002](#up-20260921-002)
- linked_changes: [AC-20260921-003](agentchangelog.md#ac-20260921-003)

<a id="up-20260921-004"></a>
## UP-20260921-004 — Repair two macOS human-acceptance failures
- date: 2026-09-21
- status: authorised source correction, focused and broad offline verification, and a package rebuild; human GUI acceptance still pending
- tags: chat, reliability, documents, grounding, cross-source-identity, macos-acceptance
- aliases: reversed NPSH relation, SOP-MECH-814 vs SOP-MECH-014, governing reference unresolved
- paths: backend/coordinator/identity.py, backend/coordinator/models.py, backend/coordinator/docflow.py, backend/coordinator/server.py, agent-memory/
- summary: A packaged acceptance run passed launch, Chat history, cancellation, OCR and DOCX generation, but produced a confident technical answer with its central comparison reversed, and an approval note that used a supplied SOP's limit although the report named a different governing identifier.
- request: Reproduce both failures, fix each at the shared boundary that owns it rather than by special-casing the observed subject or identifiers, add regressions, run the authorised verification, rebuild the package if safe, and stop before the human GUI walkthrough.
- constraints: No hardcoded pump or NPSH answer, no string interception, no 814/014 branch, no fuzzy identifier resolution, no fixture or expected.json edit, no always-on second inference pass without reporting it, no new dependency, no schema migration, no model download, no cloud inference, no protected-document edit, no Git/GitHub write.
- follow_up_to: [UP-20260921-003](#up-20260921-003)
- linked_changes: [AC-20260921-004](agentchangelog.md#ac-20260921-004)

<a id="up-20260921-005"></a>
## UP-20260921-005 — Remove inference-envelope bottlenecks
- date: 2026-09-21
- status: authorised implementation, offline verification and self-review; no live model/device/package or Git/GitHub work
- tags: inference, context-budget, code, documents, telemetry, model-quality
- aliases: strangled models, whole-file output ceiling, shared document budget, actual num_predict
- paths: backend/coordinator/runtime.py, backend/coordinator/context.py, backend/coordinator/codeflow.py, backend/coordinator/code_service.py, backend/coordinator/docflow.py, backend/coordinator/server.py, related tests, agent-memory/
- summary: Make qualified local models use the largest safe request envelope the current profile supports instead of silently constraining whole-file Code and overflowing Documents prompts.
- request: Implement the reviewed fixes, use relevant skills, minimise complexity and token use, run focused and broad offline checks, and self-review the complete result.
- constraints: Preserve the dirty tree and security boundaries. Do not edit protected documentation, add dependencies, use advertised model maxima without device qualification, call live models/devices, package/deploy, or perform Git/GitHub writes.
- follow_up_to: [UP-20260921-004](#up-20260921-004)
- linked_changes: [AC-20260921-005](agentchangelog.md#ac-20260921-005)

<a id="up-20260921-006"></a>
## UP-20260921-006 — Complete qualified inference profiles and route parity
- date: 2026-09-21
- status: authorised continuation, offline verification and self-review; no deployment, live-device or Git/GitHub writes
- tags: inference-profile, contract-1.1, worker-negotiation, route-parity, takeover
- aliases: Tasks 2-4, qualified profile, profile advertisement, no silent downgrade
- paths: backend/contracts/, backend/coordinator/, backend/worker/, related tests, agent-memory/
- summary: Audit the partially completed Tasks 2-4 implementation inherited from another agent, repair confirmed defects and regressions, and finish qualified local profiles, worker negotiation and parity-or-explicit-refusal semantics.
- request: Continue from commit 0703511, preserve its work, trace all callers and persistence paths, complete the execution, run the authorised focused and broad offline verification, and leave review and physical-device validation for later.
- constraints: Keep whole-file Code redesign, UI redesign, model downloads, packaging, deployment, Windows/Linux qualification, LAN acceptance, protected-document edits and Git/GitHub writes out of scope. Preserve unrelated work and do not claim live-device support.
- follow_up_to: [UP-20260921-005](#up-20260921-005)
- linked_changes: [AC-20260921-006](agentchangelog.md#ac-20260921-006)

<a id="up-20260921-007"></a>
## UP-20260921-007 — Qualify current Mac execution workflows
- date: 2026-09-21
- status: authorised live local qualification, implementation, focused and broad verification, and self-review; no Git/GitHub writes
- tags: inference-profile, macos, ollama-0.33.3, chat, code, documents, live-qualification
- aliases: Mac M5 qualification, durable evidence, immutable profiles, automatic qualification pipeline
- paths: backend/contracts/profiles.py, profile-dependent tests, agent-memory/
- summary: Preserve historical profiles, make the completed Mac Chat qualification durable, and admit new Mac Code and Documents profiles for Ollama 0.33.3 only after their actual production workflows pass against the exact installed model bytes.
- request: Continue autonomously from the supplied execution-qualification handoff, run real local Ollama qualification on synthetic inputs, repair positional registry assumptions, perform the authorised regressions, record durable evidence, and identify the smallest next architecture step toward automated release qualification.
- constraints: Do not update or start Ollama, install dependencies, use sensitive data, wait for unavailable Ubuntu hardware, weaken exact matching, replace historical qualifications, edit protected documentation, package/deploy, or perform Git/GitHub writes. A failed workflow remains unqualified and fail-closed.
- follow_up_to: [UP-20260921-006](#up-20260921-006)
- linked_changes: [AC-20260921-007](agentchangelog.md#ac-20260921-007)

<a id="up-20260921-008"></a>
## UP-20260921-008 — Preserve the llmfit and runtime-direction decision
- date: 2026-09-21
- status: authorised concise protected-document and ledger update only
- tags: llmfit, hardware-observation, qualification, ollama, llama.cpp, technology-direction
- paths: docs/PROJECT.md, agent-memory/
- summary: Preserve `llmfit` as a future/internal qualification-tool candidate without making it a Beta dependency, and clarify that Ollama remains the qualified baseline while llama.cpp remains gated and unadopted.
- request: Record the evaluated `llmfit` posture and the existing Ollama/llama.cpp boundary in the most appropriate authority, preserve historical decisions and evidence, and make no implementation, profile, dependency, packaging or Git changes.
- constraints: Planning evidence never becomes qualification evidence. Do not add an integration or speculative abstraction, rewrite OD-03 history, or represent Ollama evidence as llama.cpp evidence.
- follow_up_to: [UP-20260921-007](#up-20260921-007)
- linked_changes: [AC-20260921-008](agentchangelog.md#ac-20260921-008)

<a id="up-20260921-009"></a>
## UP-20260921-009 — Generate exact execution-qualification artifacts
- date: 2026-09-21
- status: authorised implementation, live Mac reproduction, offline verification and Windows handoff; no Git/GitHub writes
- tags: qualification-artifact, execution-profile, macos, windows-handoff, ollama-0.33.3
- aliases: generated qualification evidence, Windows next, evidence-only profile artifact
- paths: backend/contracts/qualification.py, backend/contracts/test_qualification.py, scripts/qualify_execution.py, qualification-artifacts/, agent-memory/
- summary: Add the smallest strict, versioned qualification-artifact path that can reproduce the current Mac evidence and be run next on a real Windows device without turning an artifact into automatic runtime authority.
- request: Reconcile the supplied handoff with current authorities and dirty work, preserve the llmfit and Ollama/llama.cpp decisions already recorded, generate exact Chat/Code/Documents evidence from real production routes, run focused and broad verification, keep Linux deferred but in Beta scope, and provide the Windows teammate with an exact process.
- constraints: No profile/envelope widening, automatic artifact loader, signing system, llmfit or llama.cpp integration, dependency install, Linux-specific speculative work, deployment, publication or Git/GitHub write. Failed or unmeasured work remains unqualified, and qualification state remains distinct from release acceptance.
- follow_up_to: [UP-20260921-008](#up-20260921-008)
- linked_changes: [AC-20260921-009](agentchangelog.md#ac-20260921-009)

<a id="up-20260922-001"></a>
## UP-20260922-001 — Repair the Code and OCR workflow regressions without weakening the exact-profile architecture
- date: 2026-09-22
- tags: execution-profile, code-envelope, ocr, qualification, regression-repair, ollama-0.33.3
- aliases: linked-list Code workload, OCR fail-closed, stream_chat contract migration, K3s inference check
- paths: backend/contracts/profiles.py, backend/contracts/v1.py, backend/coordinator/ocr.py, backend/coordinator/documents.py, backend/coordinator/code_service.py, backend/coordinator/server.py, deploy/k3s/checks/, scripts/qualify_execution.py, agent-memory/
- summary: Repair the workflow regressions exposed after the exact-profile merge — the unmigrated OCR runtime call, the missing OCR workflow/profile, the Code output envelope and planner, and the collapsed failure reporting — while keeping fail-closed admission intact.
- request: Treat a complete C11 singly-linked prime-number list program as a representative Beta Code workload that must complete as a valid reviewable proposal on a qualified capable profile. Separate a normal allowance from a qualified maximum, stop budgeting generated files from existing file size, distinguish context exhaustion from output exhaustion, persist measured duration, migrate the OCR path to the current runtime contract, keep the unresolved OCR candidate unqualified and fail closed, and repair the obsolete K3s caller.
- constraints: No blind restore of 8,128 tokens and no invented envelope without current evidence; no promotion of the OCR candidate even if `/api/show` now reports `vision`; no invented Windows/Linux device profiles; no weakening of strict proposal JSON, path/hash validation, approval, sandbox or canonical-write protection; no partial structured output accepted or applied; no dependency/model install; no host service started or reconfigured; no packaged backend file edited directly; no Git/GitHub write.
- follow_up_to: [UP-20260921-009](#up-20260921-009)
- linked_changes: [AC-20260922-001](agentchangelog.md#ac-20260922-001)

<a id="up-20260922-002"></a>
## UP-20260922-002 — Resolve the audit findings to a source PASS
- date: 2026-09-22
- status: authorised implementation and proportionate offline verification; no Git/GitHub write
- tags: audit-correction, qualification, ocr, code-metrics, fail-closed
- paths: backend/contracts/, backend/coordinator/, frontend/app/app.js, scripts/qualify_execution.py, agent-memory/
- summary: Correct every actionable finding from the integrated review without turning failed model-quality evidence into workflow qualification.
- request: Remove the unsupported 4,096-token production admission, repair the representative qualification checks, enforce exact OCR profile identity at the shared boundary, expose Code attempt measurements in the Code surface, reconcile the evidence ledger, and verify the resulting source.
- constraints: Preserve unrelated dirty work, protected documentation and Git/GitHub state. Do not execute generated code on the host, weaken the sandbox requirement, fabricate a passing artifact, qualify the failed Qwen representative workload, install dependencies or claim device/release acceptance from source checks.
- follow_up_to: [UP-20260922-001](#up-20260922-001)
- linked_changes: [AC-20260922-002](agentchangelog.md#ac-20260922-002)

<a id="up-20260922-003"></a>
## UP-20260922-003 — Let Qwen use its native vision in ordinary Chat
- date: 2026-09-22
- status: authorised implementation and proportionate offline verification; no Git/GitHub write
- tags: chat, vision, ocr, qwen, attachment-routing, capability-detection
- paths: backend/coordinator/documents.py, backend/coordinator/server.py, backend/coordinator/test_documents.py, backend/coordinator/test_execution4a.py, agent-memory/
- summary: Stop routing every ordinary PNG/JPEG Chat attachment through the separately qualified Documents OCR extractor when the selected Chat model natively accepts images.
- request: On a two-model Mac where the Paddle OCR model is unusable, allow Qwen to receive an attached image for OCR, classification and general visual understanding when the local runtime reports its vision capability, without lowering answer quality or broadly bottlenecking the model.
- constraints: Preserve intelligent routing, request-scoped file access, digest/type/size checks, exact Chat execution limits, prompt-injection fencing and fail-closed structured document OCR. Do not fabricate an OCR qualification, install dependencies, call the live model, edit protected documentation or perform Git/GitHub writes.
- follow_up_to: [UP-20260922-002](#up-20260922-002)
- linked_changes: [AC-20260922-003](agentchangelog.md#ac-20260922-003)

<a id="up-20260924-001"></a>
## UP-20260924-001 — Qualify Ollama 0.34.2 for the current Mac
- date: 2026-09-24
- status: authorised live local qualification, exact profile registration, focused verification and macOS package rebuild; no Git/GitHub write
- tags: inference-profile, macos, ollama-0.34.2, chat, live-qualification, package
- paths: scripts/qualify_execution.py, scripts/test_qualify_execution.py, backend/contracts/profiles.py, backend/contracts/test_contracts.py, qualification-artifacts/, desktop/dist/Refinix.app, agent-memory/
- summary: Qualify the installed Ollama 0.34.2 runtime so Refinix can use the already installed Qwen model without weakening exact runtime/device/workflow admission.
- request: Qualify Ollama 0.34.2 after the official 0.33.3 macOS artifacts failed signature validation and the restored 0.34.2 runtime left the selected model unavailable for new work.
- constraints: Admit only workflows that pass the real production path on the exact model digest and current Mac. Keep unmeasured or failed Code and Documents workflows unavailable, preserve unrelated dirty work, do not edit protected documentation, and perform no Git/GitHub writes.
- follow_up_to: [UP-20260921-009](#up-20260921-009)
- linked_changes: [AC-20260924-001](agentchangelog.md#ac-20260924-001)

<a id="up-20260924-002"></a>
## UP-20260924-002 — Correct false missing-model capability messages
- date: 2026-09-24
- status: authorised implementation, focused verification and macOS package rebuild; no Git/GitHub write
- tags: capability-state, qualification, documents, code, ui-truthfulness, ollama-0.34.2
- paths: backend/coordinator/server.py, backend/coordinator/test_desktop_surface.py, frontend/app/app.js, desktop/dist/Refinix.app, agent-memory/
- summary: Replace the false claim that the installed Qwen model is missing when Documents or Code is blocked because its exact Ollama 0.34.2 workflow profile is unqualified.
- request: Implement the recommended wording correction shown by the capability-menu screenshot without force-enabling unqualified workflows.
- constraints: Preserve Chat availability, distinguish engine-down, model-missing, model-disabled and workflow-unqualified states, keep Documents and Code fail-closed, preserve unrelated dirty work, edit no protected documentation, and perform no Git/GitHub writes.
- follow_up_to: [UP-20260924-001](#up-20260924-001)
- linked_changes: [AC-20260924-002](agentchangelog.md#ac-20260924-002)

<a id="up-20260924-003"></a>
## UP-20260924-003 — Allow model-free previous-answer document conversion
- date: 2026-09-24
- status: authorised implementation, focused verification, macOS package rebuild and one live local conversion; no Git/GitHub write
- tags: documents, conversion, capability-gate, ollama-0.34.2, model-free, package
- paths: backend/coordinator/server.py, backend/coordinator/test_document_generation.py, backend/coordinator/test_desktop_surface.py, desktop/dist/Refinix.app, agent-memory/
- summary: Let Write a document save a completed answer on Ollama 0.34.2 without pretending that new model-generated Documents work is qualified.
- request: Repair the screenshot failure for "write me a document on your output" after Chat completed successfully and the broad Documents profile gate disabled Send.
- constraints: Reuse the existing deterministic conversion path, call no model, keep new document generation, document reading and Code fail-closed, preserve unrelated dirty work, edit no protected documentation, and perform no Git/GitHub writes.
- follow_up_to: [UP-20260924-002](#up-20260924-002)
- linked_changes: [AC-20260924-003](agentchangelog.md#ac-20260924-003)

<a id="up-20260924-004"></a>
## UP-20260924-004 — Enable proposal-only experimental Code on Ollama 0.34.2
- date: 2026-09-24
- status: authorised implementation, live local qualification, focused verification and macOS package rebuild; no Git/GitHub write
- tags: code, experimental-profile, small-edit, ollama-0.34.2, live-qualification, package
- paths: backend/contracts/profiles.py, backend/contracts/qualification.py, backend/coordinator/server.py, scripts/qualify_execution.py, qualification-artifacts/, desktop/dist/Refinix.app, agent-memory/
- summary: Enable Code only for small reviewable existing-file proposals on the exact current Mac profile, without claiming the previously failed complete-program workload or sandbox validation.
- request: Add an explicitly proposal-only experimental Code profile for Ollama 0.34.2, run live qualification, expose its limited scope honestly in the UI, and rebuild the app.
- constraints: Keep full-program generation and sandbox execution unqualified, preserve strict structured proposals and canonical-file protection, do not widen the 2,048-token allowance, preserve unrelated dirty work, edit no protected documentation, and perform no Git/GitHub writes.
- follow_up_to: [UP-20260924-003](#up-20260924-003)
- linked_changes: [AC-20260924-004](agentchangelog.md#ac-20260924-004)

<a id="up-20260924-005"></a>
## UP-20260924-005 — Repair Phase 1 document workflows on the Chat profile
- date: 2026-09-24
- status: authorised plan, implementation, offline verification, macOS package rebuild and live local Read/Write acceptance; requester verification pending; no Git/GitHub write
- tags: documents, chat-backed, docx, pdf-text-layer, page-references, ollama-0.34.2, package
- aliases: write a document, read a document, fresh prompt document, create a document of deep learning summarised, not available on this computer
- paths: backend/coordinator/server.py, backend/coordinator/docflow.py, backend/coordinator/documents.py, backend/coordinator/pdfrender.py, frontend/app/app.js, backend/coordinator/test_*.py, frontend/app/test-composer.cjs, desktop/dist/Refinix.app, agent-memory/
- summary: Make fresh-prompt document writing, DOCX reading and text-layer PDF reading work on Ollama 0.34.2 through the Documents-selected model's exact Chat profile, without claiming structured Documents or OCR qualification.
- constraints: One bounded Chat call per request; reuse the ordinary Chat attachment path and existing deterministic converter; keep previous-answer conversion model-free; keep scan-only PDFs and pictures unavailable with a named reason; no PaddleOCR or Qwen-vision document reading; no implementation provenance inside generated documents; structured 0.32.14/0.33.3 behaviour unchanged; exact-filename page-reference checks via retrieval.resolve; no new dependency, profile, protected-doc edit or Git/GitHub write.
- acceptance: Offline focused and broader tests pass; package builds, signs and matches source; live fresh write, conversion, DOCX, text-PDF and mixed-PDF reads complete and scan-only PDF is refused.
- follow_up_to: [UP-20260924-003](#up-20260924-003)
- supersedes: none
- linked_changes: [AC-20260924-005](agentchangelog.md#ac-20260924-005)

<a id="up-20261002-001"></a>
## UP-20261002-001 — Website: product video, pillar image, About us and Download Beta
- date: 2026-10-02
- status: plan agreed through review (v3), requester-approved execution; preview verification authorised; no Git/GitHub write or deployment
- tags: website, site.html, docs.html, video, about-us, navigation, design-reference
- aliases: replace design approach with video, pillar png, about us in docs, download beta glow, mobile nav anchor offset
- paths: frontend/design/site.html, frontend/design/site.css, frontend/design/docs.html, frontend/design/docs.css, frontend/design/assets/intro-video-poster.jpg, agent-memory/
- summary: Replace the homepage Design approach heading and cards with the supplied looping product video over the four preserved points, swap the drawn temple for the supplied pillar.png, add an About us section to Docs with homepage top/bottom links, rename visible Beta launch CTAs to Download Beta with a scoped nav glow, and keep anchors clear of the wrapping header.
- constraints: Four point titles/descriptions verbatim; supplied video/pillar/team-photo bytes unchanged; no compression without an available encoder; no purple in new elements; existing theme tokens only; countdown, destinations and private-source labels unchanged; no app/backend/protected-doc changes.
- follow_up_to: none
- linked_changes: [AC-20261002-001](agentchangelog.md#ac-20261002-001)

<a id="up-20261002-002"></a>
## UP-20261002-002 — Website consolidated repair (TOC, theme, motion, intro, docs copy, copy, links)
- date: 2026-10-02
- status: plan v3 agreed through review, requester-approved execution and verification; no Git/GitHub write or deployment
- tags: website, site.html, docs.html, accessibility, reduced-motion, toc, theme, design-reference
- aliases: docs toc highlight about, saved theme both pages, reduced motion intro, no-script intro, copy failed, link unavailable
- paths: frontend/design/site.html, frontend/design/site.css, frontend/design/docs.html, agent-memory/
- summary: Repair inherited website defects F1-F7 from the 2 October review: Docs TOC by reading position, one validated saved theme, reduced-motion and script-failure handling for the intro and clips, intro focus isolation, five Docs copy corrections, truthful Copy state, and plain-text unavailable destinations.
- constraints: Media, artwork, section order, four points, About copy, colours/fonts (Michroma added to Docs only), countdown endpoints, private-source wording and Download Beta destinations frozen; no app/backend/protected-doc changes; requester notes refinix.run deploys from dev.
- follow_up_to: [UP-20261002-001](#up-20261002-001)
- linked_changes: [AC-20261002-002](agentchangelog.md#ac-20261002-002)

<a id="up-20261002-003"></a>
## UP-20261002-003 — Website launch countdown as its own block
- date: 2026-10-02
- status: requester-directed execution of a countdown-only adjustment, then a full website audit; no Git/GitHub write or deployment
- tags: website, site.html, countdown, launch, design-reference
- aliases: countdown block, days hours minutes seconds, 2x2 countdown phone
- paths: frontend/design/site.html, frontend/design/site.css, agent-memory/
- summary: Move the launch timer out of the paragraph into a centred block between the paragraph and the three options, with Days/Hours/Minutes/Seconds digits comparable to the launch heading, four across on desktop and 2x2 on narrow phones, and no per-second screen-reader announcements; then audit the website.
- constraints: Paragraph, heading, deadline, IST timing, one-second ticks and zero stop preserved; nav glow, four points, media sizes, images and all other content unchanged; the earlier glow/points/media plan was not executed.
- follow_up_to: [UP-20261002-002](#up-20261002-002)
- linked_changes: [AC-20261002-003](agentchangelog.md#ac-20261002-003)

<a id="up-20261002-004"></a>
## UP-20261002-004 — Countdown side by side, larger, with digit animation
- date: 2026-10-02
- status: requester-directed execution; no Git/GitHub write or deployment
- tags: website, site.html, countdown, animation, cache
- aliases: countdown side by side, bigger countdown, rolling digits
- paths: frontend/design/site.html, frontend/design/site.css, agent-memory/
- summary: Requester's Safari showed the countdown stacked as plain "8Days/08Hours" text; asked for side-by-side units, bold larger digits and a more interesting digit-change animation.
- constraints: Deadline, IST timing, one-second ticks, zero stop and no per-second announcements preserved; other content unchanged.
- follow_up_to: [UP-20261002-003](#up-20261002-003)
- linked_changes: [AC-20261002-004](agentchangelog.md#ac-20261002-004)

<a id="up-20261002-005"></a>
## UP-20261002-005 — Final scoped website repair: entry scroll, prose dashes, stylesheet versions
- date: 2026-10-02
- status: requester-relayed Codex /execute instruction; executed; no Git/GitHub write or deployment
- tags: website, site.html, docs.html, scroll-restoration, punctuation, cache, ci
- aliases: get started lands on evidence, reload scroll position, remove em dashes, docs css version
- paths: frontend/design/site.html, frontend/design/docs.html, agent-memory/
- summary: Option A entry scroll (no restored mid-page position behind the intro; hash targets honoured), dash separators removed from reader-facing prose with commas/periods/colons, Docs references the homepage site.css version plus a versioned docs.css; run the full CI test set and website checks.
- constraints: Points, media sizes, glow, assets, countdown look/animation/timing, other copy, CSS, app/backend, protected docs and CI configuration frozen; R2-R4 dropped (requester accepts current presentation); isolated environment for dependencies; local results are not GitHub CI results.
- follow_up_to: [UP-20261002-004](#up-20261002-004)
- linked_changes: [AC-20261002-005](agentchangelog.md#ac-20261002-005)

<a id="up-20261002-006"></a>
## UP-20261002-006 — Verify actual website deployment and prepare publication
- date: 2026-10-02
- status: local deployment preparation authorised; four focused offline exporter tests explicitly authorised; no Git/GitHub write or live publication
- tags: website, deployment, github-pages, static-export
- paths: scripts/build-site.sh, scripts/test_build_site.py, frontend/design/, agent-memory/
- summary: Inspect how the public website deploys before deciding how to commit/push; user supplied the actual URL https://refinix.runs-on.dev.
- constraints: Preserve accepted website and media, unrelated dirty work and protected docs; prepare locally without changing hosting settings or publishing.
- follow_up_to: [UP-20261002-005](#up-20261002-005)
- linked_changes: [AC-20261002-006](agentchangelog.md#ac-20261002-006)

<a id="up-20261002-007"></a>
## UP-20261002-007 — Restore the published poster and WebM clips in the website source
- date: 2026-10-02
- status: plan v1.1 approved by requester (edits A-C and checks 1-6); executed; no Git/GitHub write, publish or deployment
- tags: website, site.html, media, performance, pages, exporter
- aliases: hero-poster preload, webm first, restore published optimisation, media regression before publishing
- paths: frontend/design/site.html, frontend/design/assets/hero-poster.jpg, frontend/design/assets/hero-loop.webm, frontend/design/assets/evidence-loop.webm, agent-memory/
- summary: Import hero-poster.jpg, hero-loop.webm and evidence-loop.webm byte-for-byte from refinix-site commit 072bb2586d02632a66e8c84664f88632041ad422; add the poster preload and intro poster and prefer WebM before the existing MP4 fallbacks; keep the exporter; verify parity, bundle references and playback.
- constraints: Every existing media file, design, text and countdown preserved; URL, CNAME, DNS and Pages settings untouched; publication via a clean-checkout dry-run procedure; HTTPS checked for validity not certificate identity; Git actions need separate explicit approval.
- follow_up_to: [UP-20261002-006](#up-20261002-006)
- linked_changes: [AC-20261002-007](agentchangelog.md#ac-20261002-007)

<a id="up-20261002-008"></a>
## UP-20261002-008 — Website-only source and publishing PRs
- date: 2026-10-02
- status: user approved focused checks, isolated website-only commits/branch pushes/PRs and publishing fork; no merge or direct protected-branch push
- tags: website, publication, github-pages, pull-request
- paths: frontend/design/, scripts/build-site.sh, scripts/test_build_site.py, agent-memory/
- summary: User confirmed the accepted website works locally, requested deployment, then explicitly approved website-only Git/PR work and checks. User also asked what the reported launcher-test address mismatch means; inspect and explain, without changing application code.
- constraints: Preserve accepted website, URL, unrelated dirty work, application code and protected docs; source PR into dev, publishing PR into the separate site repository; owner merge needed because the current account has read-only hosting-repository access.
- follow_up_to: [UP-20261002-007](#up-20261002-007)
- linked_changes: [AC-20261002-008](agentchangelog.md#ac-20261002-008)


<a id="up-20261003-001"></a>
## UP-20261003-001 — Standalone three-OS Beta and section-level execution
- date: 2026-10-03
- status: done
- scope: docs, decision
- tags: beta, standalone, cross-platform, updates, reuse, agent-execution
- paths: AGENTS.md, docs/PROJECT.md, tasks.md, docs/releases.md, README.md, docs/README.md, docs/security.md
- summary: User approved careful documentation changes for standalone Windows/macOS/Linux Beta with in-app updates, deferred distributed execution, reuse of existing repository code and execution by major sections without further task tiers or delegation.
- constraints: No workflow-tool download/install; preserve distributed source, local security/approval/recovery requirements, historical evidence and unrelated dirty work. Documentation permission does not authorise application changes, test suites, builds, live checks or Git writes.
- acceptance: Current authorities and entry points agree on Beta scope, deferred mesh gates, updater qualification and section-level execution.
- follow_up_to: none
- linked_changes: [AC-20261003-001](agentchangelog.md#ac-20261003-001)


<a id="up-20261004-001"></a>
## UP-20261004-001 — Runtime ownership UX and orchestration options
- date: 2026-10-04
- status: done
- scope: docs, decision
- tags: runtime, ollama, llama-cpp, qualification, onboarding, langgraph, reuse
- paths: AGENTS.md, docs/PROJECT.md, tasks.md, docs/model-catalog.md, docs/releases.md, docs/evaluation.md, README.md, docs/README.md
- summary: User approved careful documentation updates and another review to record that Refinix owns runtime compatibility/qualification, customers should open and use it without manual requalification after external updates, and the existing orchestration harness remains selected while LangGraph stays an option for evidenced need.
- constraints: Preserve existing repository implementation, prior standalone three-OS Beta/mesh-deferral decisions, security/admission and data recovery. No application implementation, test suites, downloads/installs, runtime checks, framework adoption or Git writes authorised by this documentation request.
- acceptance: Product/model/release/agent/phase guidance agrees on app-managed pinned engine ownership, automatic graphical installation checks, internal engineering qualification, truthful failure/recovery, and criteria for reconsidering LangGraph; source finding distinguished from an unobserved live diagnosis.
- follow_up_to: [UP-20261003-001](#up-20261003-001)
- linked_changes: [AC-20261004-001](agentchangelog.md#ac-20261004-001)


<a id="up-20261004-002"></a>
## UP-20261004-002 — Core Beta direction and reasoned execution handoff
- date: 2026-10-04
- status: handoff-prepared; coordination-pending
- scope: planning, handoff, memory
- tags: beta, code-quality, reuse, coherent-execution, review, runtime, memory
- paths: docs/beta-execution-handoff.md, agent-memory/
- summary: User requested a deep implementation-owner plan with independent agent review before a concrete change summary and sustained execution; prioritize optimizing existing code and product quality, remove evidenced unwanted code, update necessary docs, save this as the current core memory and pin it.
- constraints: Four existing major Beta sections; no nested delegation or per-file task trees; preserve dirty work, useful capabilities and deferred distributed code. Planning must precede application execution; tests/live actions/Git/publication retain their separate permission boundaries.
- acceptance: Source-grounded handoff explains reasons, alternatives, affected paths, coherent execution sections, meaningful acceptance and prerequisite/review gates; memory saved and current chat pinned; no unobserved delivery, agreement or implementation claims.
- follow_up_to: [UP-20261004-001](#up-20261004-001)
- linked_changes: [AC-20261004-002](agentchangelog.md#ac-20261004-002)


<a id="up-20261004-003"></a>
## UP-20261004-003 — Implementation-owner Beta plan for review
- date: 2026-10-04
- status: plan-recorded; review-pending
- scope: planning, handoff
- tags: beta, runtime, llama-cpp, model-lifecycle, sandbox, updater, review
- paths: docs/beta-execution-handoff.md
- summary: User asked the implementation owner to read the handoff and current authorities, independently inspect source, record a reasoned plan with corrections, affected paths, acceptance checks and prerequisites for review-agent evaluation, then later execute the approved plan in one sustained run without further delegation.
- constraints: Planning only before review; follow the handoff's coordination and execution gates; ask when blocked; no subagents, tests, downloads, installs, live runtime calls or Git writes in this step.
- acceptance: Plan in the handoff is source-grounded with checkable line references, a parity decision rule, section plans, cleanup evidence, validation families, one prerequisite batch with recommendations and a user-facing change summary.
- follow_up_to: [UP-20261004-002](#up-20261004-002)
- linked_changes: [AC-20261004-003](agentchangelog.md#ac-20261004-003)


<a id="up-20261004-004"></a>
## UP-20261004-004 — Research-backed presets and independent owner-plan review
- date: 2026-10-04
- status: docs-updated; owner-reconciliation-pending
- scope: documentation, research, review, memory
- tags: presets, hardware, research, reuse, beta, recovery, sandbox
- paths: AGENTS.md, docs/PROJECT.md, tasks.md, docs/model-catalog.md, docs/releases.md, docs/evaluation.md, docs/beta-execution-handoff.md
- summary: User requested category recommendations with precomputed hardware/runtime/context/KV/resource presets derived from existing research, hardware matching rather than startup calculations, reuse of existing tools, a memory update, necessary docs changes and an independent review/correction handoff asking the owner to review our doc changes.
- constraints: Do not require ownership of target laptops for research; preserve existing source, dirty work, four major sections and the original owner proposal. No app implementation, tests, downloads/installs, live runtime checks, new delegation or Git writes in this step.
- acceptance: Preset schema and evidence states agree across authorities; sources and reusable options identified; plan disagreements recorded with reasons and acceptance; actual delivery status reported honestly.
- follow_up_to: [UP-20261004-003](#up-20261004-003)
- linked_changes: [AC-20261004-004](agentchangelog.md#ac-20261004-004)


<a id="up-20261004-004"></a>
## UP-20261004-004 — Reconcile review findings and deepen the Beta plan
- date: 2026-10-04
- status: reconciliation-recorded; re-review-pending
- scope: planning, handoff
- tags: beta, presets, reuse, rollback, sandbox, observer, packaging
- paths: docs/beta-execution-handoff.md
- summary: User shared the review agent's NEEDS FIX result (preset matching, reuse, update recovery, sandbox enforcement, evidence claims) and asked the implementation owner to reason, improve the plan and analyse the repository more deeply.
- constraints: Planning and source inspection only; preserve the original proposal and the review section; necessary doc corrections already authorized; no subagents, tests, downloads, installs, builds or Git writes.
- acceptance: One appended reconciliation mapping R1-R5 into the same four sections with evidence, reuse decisions, recovery order, named sandbox enforcement, observer contract, revised prerequisites and change summary.
- follow_up_to: [UP-20261004-003](#up-20261004-003)
- linked_changes: [AC-20261004-004](agentchangelog.md#ac-20261004-004)


<a id="up-20261004-005"></a>
## UP-20261004-005 — Internal Windows/Ubuntu/macOS test packages and stronger cleanup rule
- date: 2026-10-04
- status: plan-updated; re-review-pending
- scope: planning, handoff
- tags: beta, packaging, build-matrix, test-artifacts, ci, cleanup
- paths: docs/beta-execution-handoff.md
- summary: User added a Beta requirement for complete internal test packages on Windows and Ubuntu alongside macOS, built natively from one source snapshot and version with pinned dependencies and the managed engine, labelled with SHA-256 manifests and short instructions, reused across tests and kept as N/N+1 builds for updater testing; plus a stronger reuse-first cleanup rule.
- constraints: Same four sections; no subagents or task tiers; no Git/GitHub writes or CI trigger; plan PASS not declared and the long run not started; model weights stay explicit assets; internal unsigned packages separate from signing, publication and device acceptance.
- acceptance: Reconciled plan, prerequisite batch and change summary updated; Codex doc changes re-checked; genuine build-environment prerequisite named.
- follow_up_to: [UP-20261004-004](#up-20261004-004)
- linked_changes: [AC-20261004-005](agentchangelog.md#ac-20261004-005)

<a id="up-20261004-006"></a>
## UP-20261004-006 — Approved corrected four-section Beta handoff and direct delivery
- date: 2026-10-04
- status: approved-direction; handoff-prepared; delivery-pending
- scope: handoff, coordination
- tags: beta, approval, reuse, schema-preflight, recovery, sandbox, packaging
- paths: docs/beta-execution-handoff.md, agent-memory/
- summary: After reviewing the owner's reply and receiving a plain-language explanation, the user approved the four-section approach and requested a corrected handoff delivered directly to the implementation owner.
- constraints: Reuse the existing handoff/code and established offline tools; no subagents or further task tiers. Preserve dirty work. Handoff approval does not silently authorize tests, downloads/installs, live calls, build/host actions, Git/CI writes, other protected-doc edits or publication.
- acceptance: The handoff includes actual-root ownership and coherent-copy schema admission, exclusive recovery, host IPC/io_uring denial, aggregate temporary-storage enforcement, final-artifact identities and reuse, four-section execution and one genuine prerequisite batch; direct delivery is reported only after visible confirmation.
- follow_up_to: [UP-20261004-005](#up-20261004-005)
- linked_changes: [AC-20261004-006](agentchangelog.md#ac-20261004-006)
- delivery_result: DELIVERED directly to the existing owner conversation, visibly confirmed as Message 9; owner response started. Detailed acknowledgement and required action permissions remain pending.


<a id="up-20261004-007"></a>
## UP-20261004-007 — Execute the approved four-section Beta plan
- date: 2026-10-04
- status: in-progress (Section 1 largely done; run paused at usage limit)
- scope: implementation, tests, local engine/model acquisition, packaging preparation, ledgers
- tags: beta, managed-engine, ownership, admission, readiness, presets, packaging, parity
- paths: backend/coordinator, backend/contracts, desktop, frontend/app, scripts, qualification-artifacts
- summary: User confirmed /execute with permissions: source changes in the four sections, offline suites, one pinned llama.cpp macOS release plus the Qwen3.5-4B model and projector (~3.4 GB) with a private Ollama comparison, llmfit for estimates, hash-pinned psutil/tuf/securesystemslib/urllib3, preparing native CI builds (no Git/Actions writes), and one releases.md §2 addition.
- constraints: No Git/GitHub/Actions writes, signing, publication, host/sandbox changes, privileged helpers or extra model downloads; generated-code execution stays unavailable where controls cannot be enforced.
- follow_up_to: [UP-20261004-006](#up-20261004-006)
- linked_changes: [AC-20261004-007](agentchangelog.md#ac-20261004-007)


<a id="up-20261004-008"></a>
## UP-20261004-008 — Preserve and review interrupted Beta Foundation work
- date: 2026-10-04
- status: done (review and checkpoint; implementation remains partial)
- scope: review, preservation, memory
- tags: beta, checkpoint, partial-execution, parity, source-review, low-context
- paths: tmp/beta-foundation-checkpoint-20261004T153112Z, agent-memory/
- summary: User requested a rigorous scan and preservation of the owner's interrupted work plus a memory checkpoint before starting a new chat; the user will resume execution after the owner's limit resets.
- constraints: Preserve the mixed dirty tree and approved four sections; no source fixes, tests, live models, downloads/installs, protected-doc edits, Git/Actions writes or delegation in this review. Future handoffs are copyable unless Computer Use is necessary.
- acceptance: Recoverable verified source/evidence snapshot, factual review and saved memory update; distinguish interrupted work and owner-reported checks from fresh review evidence.
- follow_up_to: [UP-20261004-007](#up-20261004-007)
- linked_changes: [AC-20261004-008](agentchangelog.md#ac-20261004-008)


<a id="up-20261005-001"></a>
## UP-20261005-001 — Resume the four-section Beta execution with seven review findings
- date: 2026-10-05
- status: in-progress
- scope: implementation, offline tests, ledgers
- tags: beta, resume, ownership, engine-cleanup, admission, build-identity, tiers, model-integrity, readiness
- paths: backend/coordinator, backend/contracts, desktop, frontend/app, scripts, .github/workflows
- summary: User re-issued /execute to continue the existing four-section plan from the interruption point and fold in seven validated findings: database aliases, engine survivor tracking, empty foreign SQLite, material build inputs/reuse and Windows installer isolation, Ubuntu distribution matching, installed-model byte identity, and startup readiness.
- constraints: Existing conversation permissions only; no Git/GitHub/Actions writes, signing, publication, privileged helpers, host/sandbox changes, extra model downloads, or protected-doc edits beyond the previously named releases.md §2 addition; no subagents or new planning cycle.
- follow_up_to: [UP-20261004-008](#up-20261004-008)
- linked_changes: [AC-20261005-001](agentchangelog.md#ac-20261005-001), [AC-20261005-002](agentchangelog.md#ac-20261005-002), [AC-20261005-003](agentchangelog.md#ac-20261005-003), [AC-20261005-004](agentchangelog.md#ac-20261005-004), [AC-20261005-005](agentchangelog.md#ac-20261005-005), [AC-20261005-006](agentchangelog.md#ac-20261005-006)


<a id="up-20261005-002"></a>
## UP-20261005-002 — Save the partial Beta checkpoint and explain runtime strictness
- date: 2026-10-05
- status: checkpoint requested; implementation remains partial
- scope: local Git commit, explanation
- tags: beta, checkpoint, managed-engine, ollama, qualification
- paths: backend, desktop, frontend/app, scripts, .github/workflows, docs, agent-memory
- summary: User explicitly requested a local commit of the existing work and an explanation of why Refinix restricts runtime versions when other applications integrate Ollama directly.
- constraints: Preserve unrelated website/media/temporary work; no push, release, new test runs, runtime changes or protected-document edits.
- linked_changes: [AC-20261005-007](agentchangelog.md#ac-20261005-007)


<a id="up-20261005-003"></a>
## UP-20261005-003 — Record verbatim user direction and align the Beta documents
- date: 2026-10-05
- status: memory and documentation complete; owner planning/review pending; implementation not authorized
- scope: memory, protected documentation, copyable planning handoff
- tags: beta, hackathon, upstream-reuse, open-model-choice, recommendations, auto-routing, verbatim-user-direction
- paths: docs/beta-user-direction-2026-10-05.md, AGENTS.md, docs/PROJECT.md, docs/model-catalog.md, docs/security.md, tasks.md
- original_request: Full original statement and follow-up instruction are preserved verbatim in [the requested report](../docs/beta-user-direction-2026-10-05.md); do not substitute this ledger metadata for the user's words.
- constraints: Save memory first, then align documents and provide a handoff for the user to send. Do not contact the implementation owner, implement, run tests/live models/downloads, or make Git/GitHub writes. The owner's next execution plan returns for independent review against the original requirements before implementation.
- linked_changes: [AC-20261005-008](agentchangelog.md#ac-20261005-008)


<a id="up-20261005-004"></a>
## UP-20261005-004 — Manual branch checkpoint and final-cleanup handoff
- date: 2026-10-05
- status: handoff update complete; staging, commit and push remain user actions
- scope: manual Git commands and copyable planning handoff
- paths: docs/beta-user-direction-2026-10-05.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- original_request: "alright next i want to git add commit and push everything to my branch \nonce everything is added and pushed to aditya \nalso the push and commit will be done by me so give me commands and statements accodingly \nalso in the copyabale handover mention that to delete unwanted code and also delete document { beta-user-direction-2026-10-05.md } after complete plan is executed \n\n\nand after that i'll start a new chat"
- constraints: Do not perform Git writes for the user. Plan cleanup only after complete approved execution and verification; preserve original requirements, useful code, deferred distributed paths and user data.
- linked_changes: [AC-20261005-009](agentchangelog.md#ac-20261005-009)


<a id="up-20261005-005"></a>
## UP-20261005-005 — Preserve the teammate-owned final README
- date: 2026-10-05
- status: requested headline recorded
- scope: headline in docs/beta-user-direction-2026-10-05.md
- original_request: "Also, a point that we don't have to update README as the final README will be pushed by one of my teammates, and that will be the final README. The README which we are currently having is not well structured compared to what his README is. So I don't want to push the current README in main as main will con contain the best REDME or if I'll tell you when the REDME is pushed to main, I'll tell to you and then accordingly we will pull only readme from main and then push the entire beta itself to my branch dev and main."
- constraints: Do not edit the repository-root README. Wait for the user's confirmation and Git authorization before bringing only the final README from main into aditya; preserve that README through normal aditya -> dev -> main integration.
- linked_changes: [AC-20261005-010](agentchangelog.md#ac-20261005-010)


<a id="up-20261006-001"></a>
## UP-20261006-001 — Plan, review and execute the model/runtime/routing package (A–F)
- date: 2026-10-06
- status: implementation delivered; requester verification pending
- scope: planning, review, implementation
- tags: beta, ollama-reuse, managed-llama-cpp, auto-routing, capacity, local-admission, check-fingerprint, schema-14
- paths: backend/contracts, backend/coordinator, desktop, frontend/app
- original_request: Planning request relayed by the user ("Planning only. Do not implement, edit files, run checks/models/downloads, or make Git/GitHub changes yet. Read docs/beta-user-direction-2026-10-05.md first…"), then two relayed independent reviews (nine corrections, six amendments, all accepted), then the relayed authorization "Execute the amended model/runtime/routing plan, sections A–F, including all nine initial corrections and all six final amendments… This approval is for this work package; it is not Beta release acceptance." The user confirmed it in chat with "Yes, execute it (Recommended)".
- constraints: Excluded: protected documentation and README edits, section G report retirement/deletion and destructive cleanup, Git/GitHub writes, installers, model downloads, remote-device actions, credential/network/security changes. Live checks loopback-only on the Mac with existing Ollama models and cached managed Qwen files, isolated temporary state, synthetic fixtures; read-only Hugging Face metadata. Keep Windows/Linux packages, updater/recovery, local sandbox and network-evidence gates outstanding.
- linked_changes: [AC-20261006-001](agentchangelog.md#ac-20261006-001)


<a id="up-20261006-002"></a>
## UP-20261006-002 — Resume the A–F execution after the usage limit
- date: 2026-10-06
- status: done; requester verification pending
- scope: implementation, verification
- tags: beta, resume, capacity, residency, preview
- paths: backend/coordinator/capacity.py, backend/coordinator/server.py, backend/coordinator/local_engine.py, backend/coordinator/db.py, frontend/app/app.js
- original_request: "continue", with a relayed compaction checkpoint asking to "resolve the capacity concern, finish remaining verification, and report changes, observed checks, failures and limitations. Do not claim complete Beta/release acceptance."
- constraints: Same scope and exclusions as UP-20261006-001; preserve the dirty tree and untracked files.
- linked_changes: [AC-20261006-001](agentchangelog.md#ac-20261006-001)


<a id="up-20261006-003"></a>
## UP-20261006-003 — Repair the five review findings in the A–F package
- date: 2026-10-06
- status: done; requester verification pending
- scope: implementation, verification
- tags: beta, review-fix, ollama-start, search-ocr, ocr-admission, capacity-refresh, hub-projector
- paths: desktop/lifecycle.py, backend/coordinator/{server,capacity,local_engine,runtime,docflow,documents,hub}.py, frontend/app/app.js
- original_request: A relayed independent review (NEEDS FIX, five reproduced defects) and its security diff report with no findings; the user confirmed in chat "Yes, fix all five (Recommended)".
- constraints: Same A–F scope and exclusions as UP-20261006-001; a focused regression for each finding.
- linked_changes: [AC-20261006-002](agentchangelog.md#ac-20261006-002)


<a id="up-20261006-004"></a>
## UP-20261006-004 — Complete the OCR memory and projector-pairing repairs
- date: 2026-10-06
- status: done; requester verification pending
- scope: implementation, verification
- tags: beta, review-fix, ocr-admission, capacity, hub-projector, scanned-search
- paths: backend/coordinator/{capacity,server,hub}.py, frontend/app/app.js
- original_request: A relayed follow-up review (NEEDS FIX: later OCR pages falsely refused; prefix matching invents projector compatibility and no text-only on the automatic path; verify scanned Search finds a known phrase on the right file and page); the user confirmed in chat "Yes, fix both (Recommended)".
- constraints: Same A–F scope and exclusions; regressions that fail on the previous code; live loopback scanned-Search phrase check.
- linked_changes: [AC-20261006-003](agentchangelog.md#ac-20261006-003)


<a id="up-20261006-005"></a>
## UP-20261006-005 — Ignore generated desktop review builds
- date: 2026-10-06
- status: done
- scope: implementation
- tags: gitignore, desktop, build-artifacts
- paths: .gitignore
- original_request: "add that to gitignore", referring to the untracked desktop/out/ review build.
- constraints: Keep local build files and existing staged work; no Git writes or test commands.
- linked_changes: [AC-20261006-004](agentchangelog.md#ac-20261006-004)
