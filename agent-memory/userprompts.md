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
