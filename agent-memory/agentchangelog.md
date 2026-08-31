# Agent Change Ledger

Compact records of what agents actually changed for a logged user prompt. This
is not a release changelog, task manager, design document, or instruction source.

## Retrieval — do not read this file end to end

Search by change ID, prompt ID, path, tag, or component:

```bash
rg -n -i -C 8 'AC-20260831-001|UP-20260831-001|AGENTS.md|prompt-ledger' agent-memory/agentchangelog.md
```

Follow `prompt_id` to recover the originating request:

```bash
rg -n -i -C 6 'UP-20260831-001' agent-memory/userprompts.md
```

## Entry format

```markdown
## AC-YYYYMMDD-NNN — Short result
- date: YYYY-MM-DD
- agent: tool or agent name
- status: implemented | partial | docs-only | blocked
- prompt_id: [UP-...](userprompts.md#up-...)
- related_prompts: UP-... | none
- tags: lowercase, comma-separated, search terms
- aliases: user wording, synonyms, component names
- paths: repository/relative/path, another/path
- summary: one sentence describing the delivered outcome
- changes: short bullets or semicolon-separated facts
- verification: exact checks and observed result
- remaining: unresolved work or none
```

Record facts only. Do not paste diffs, long logs, hidden reasoning, or planned
work. No repository file change means no changelog entry.

---

## Entries

<a id="ac-20260831-001"></a>
## AC-20260831-001 — Create repository agent and work-ledger guidance
- date: 2026-08-31
- agent: Codex
- status: docs-only
- prompt_id: [UP-20260831-001](userprompts.md#up-20260831-001)
- related_prompts: none
- tags: agents, prompt-ledger, changelog, low-context, search
- aliases: AGENTS.md, Work folder, user prompt history, agent change history, semantic search
- paths: AGENTS.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Added repository-wide agent rules and two compact, reciprocal, search-optimized work ledgers.
- changes: Defined authority and safe preflight; added ID/tag/alias/path templates; enforced targeted retrieval, small entries, reciprocal links, and deferred quarterly archives.
- verification: Targeted `rg` retrieval found both IDs and reciprocal links; all Markdown fences are balanced; no trailing whitespace was found; `git diff --check` passed.
- remaining: none

<a id="ac-20260831-002"></a>
## AC-20260831-002 — Restrict automated PR checks to main releases
- date: 2026-08-31
- agent: Codex
- status: verified
- prompt_id: [UP-20260831-002](userprompts.md#up-20260831-002)
- related_prompts: none
- tags: ci, github-actions, pull-request, dev, main, release-gate
- aliases: CI only for main, checks only dev to main, no CI on member PRs, release checks
- paths: .github/workflows/pr-flow-guard.yml, .github/workflows/no-direct-push.yml, .github/pull_request_template.md, scripts/setup-branch-protection.sh, CONTRIBUTING.md, .github/CODEOWNERS, docs/prd.md
- summary: Limited automated PR checks and future required status checks to the `dev` to `main` release path.
- changes: Removed all `dev` workflow triggers and the member allowlist; made the future `dev` ruleset PR-only with no status checks; aligned the PRD and contribution guidance.
- verification: Shell and YAML parsing passed; generated main/dev ruleset JSON passed `jq` assertions; simulated guard allowed `dev` and rejected `aditya`; both workflow trigger inspections showed only `main`; `git diff --check` passed.
- remaining: GitHub-hosted behavior is unverified until merged; server-side rulesets remain inactive on the current plan.

<a id="ac-20260901-001"></a>
## AC-20260901-001 — Minimal repository foundation and agent-memory rename
- date: 2026-09-01
- agent: Claude
- status: implemented
- prompt_id: [UP-20260901-001](userprompts.md#up-20260901-001)
- related_prompts: [UP-20260831-002](userprompts.md#up-20260831-002)
- tags: agent-memory, docs, gitignore, github-actions, repository-structure, git-safety
- aliases: rename Work folder, move prd under docs, backend frontend readme, simplify gitignore, filesystem edits only
- paths: agent-memory/, docs/, backend/, frontend/, CLAUDE.md, .gitignore, AGENTS.md, CONTRIBUTING.md, .github/CODEOWNERS, scripts/setup-branch-protection.sh
- summary: Renamed the work ledgers to `agent-memory/`, moved the PRD under `docs/`, added boundary-only project folders, and cut `.gitignore` from 188 to 108 lines.
- changes: Moved `Work/` to `agent-memory/` and `prd.md` to `docs/prd.md` with plain `mv`; added `agent-memory/README.md`, `docs/README.md`, `backend/README.md`, `frontend/README.md`, and a root `CLAUDE.md` Git-safety bootstrap; updated every `Work/` and root-`prd.md` reference; removed `.gitignore` patterns that could hide source (`models/`, `index/`, `workspace/`, `*.npz`, `*.crt`, `*.bin`, CLAUDE/CODEX); no scaffolding, manifests, or deferred architecture documents created.
- verification: `git diff --check` clean; `bash -n` on both scripts and `sh -n` on the pre-push hook passed; both workflows parsed and trigger only `branches: [main]` with no `dev` trigger; simulated guard gave `dev`->`main` exit 0 and `aditya`->`main` exit 1; generated ruleset JSON asserted `main` has `required_status_checks` and `dev` has none; `git check-ignore --no-index` confirmed 14 artifact paths ignored and 11 plausible source paths not ignored; `git ls-files -ci --exclude-standard` returned only `.DS_Store`; no stale `Work/` or root `prd.md` references remain.
- remaining: `.DS_Store` is still tracked; a human must run `git rm --cached .DS_Store` and commit. No Git or GitHub state was changed: nothing staged, committed, pushed, merged, or configured.

<a id="ac-20260901-002"></a>
## AC-20260901-002 — Remove push audit workflow, fix PRD link, anchor gitignore folders
- date: 2026-09-01
- agent: Claude
- status: implemented
- prompt_id: [UP-20260901-002](userprompts.md#up-20260901-002)
- related_prompts: [UP-20260901-001](userprompts.md#up-20260901-001)
- tags: github-actions, actions-minutes, gitignore, anchoring, broken-link, review-fix
- aliases: delete no-direct-push, remove push workflow, checks only on PR to main, anchor gitignore folders, prd contributing link
- paths: .github/workflows/no-direct-push.yml, CONTRIBUTING.md, .gitignore, docs/prd.md, scripts/setup-branch-protection.sh, agent-memory/README.md
- summary: Deleted the push-triggered audit workflow so Actions run only on pull requests targeting `main`, repaired the PRD's `CONTRIBUTING.md` link, and anchored root-only data folders in `.gitignore`.
- changes: Removed `.github/workflows/no-direct-push.yml` with plain `rm`, leaving `pr-flow-guard` as the only workflow; rewrote the CONTRIBUTING enforcement section from three layers to two and stated plainly that no GitHub audit of pushes remains; pointed `docs/prd.md` 17.3 at `../CONTRIBUTING.md`; anchored `/secrets/`, `/credentials/`, `/weights/`, `/private/`, `/scans/`, `/confidential/`, `/logs/` while leaving `node_modules/`, `dist/`, `.venv/`, `coverage/` unanchored for `backend/` and `frontend/`; on review, corrected an overstated claim that a direct push leaves "no trace on GitHub" -- the commit stays visible, only prevention and alerting are absent.
- verification: `git diff --check` clean; `bash -n` on both scripts and `sh -n` on the hook passed; only `pr-flow-guard.yml` remains and it triggers solely on `pull_request` to `main` with zero push triggers repository-wide; simulated guard gave `dev`->`main` exit 0 and `aditya`->`main` exit 1; ruleset JSON still asserts `main` has required checks and `dev` has none; a repository-wide scan of relative markdown links found 0 broken; `git check-ignore --no-index` confirmed 7 same-named source paths at depth are no longer hidden while the 7 root data folders and all build artifacts remain ignored; `git ls-files -ci --exclude-standard` returned only `.DS_Store`.
- remaining: With the audit workflow gone and no ruleset applied, nothing prevents or alerts on a direct push to `main` or `dev`; the commit stays visible in branch history, but the local hook is the only guard. `.DS_Store` still needs `git rm --cached .DS_Store` from a human. No Git or GitHub state was changed.

<a id="ac-20260901-003"></a>
## AC-20260901-003 — Ignore local Claude and Codex instruction files
- date: 2026-09-01
- agent: Codex
- status: docs-only
- prompt_id: [UP-20260901-003](userprompts.md#up-20260901-003)
- related_prompts: [UP-20260901-001](userprompts.md#up-20260901-001)
- tags: gitignore, claude, codex, agent-instructions, local-only
- aliases: ignore claude.md, ignore codex.md, local agent files
- paths: .gitignore, docs/README.md
- summary: Kept tool-specific root instructions local while preserving `AGENTS.md` as shared guidance.
- changes: Ignored uppercase and lowercase Claude/Codex filenames and documented the shared-versus-local boundary.
- verification: `git check-ignore -v` matched all four spellings; normal `git status --short` omitted the local `CLAUDE.md` and `CODEX.md` files; `git diff --check` passed.
- remaining: none
