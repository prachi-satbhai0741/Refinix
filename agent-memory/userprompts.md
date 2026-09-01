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
