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

<a id="ac-20260901-004"></a>
## AC-20260901-004 — Consolidate shared repository rules and remove CODEOWNERS
- date: 2026-09-01
- agent: Claude
- status: implemented
- prompt_id: [UP-20260901-004](userprompts.md#up-20260901-004)
- related_prompts: [UP-20260901-003](userprompts.md#up-20260901-003)
- tags: agents-md, git-safety, rules, codeowners, review-requests, consolidation
- aliases: shared rules in agents.md, single agent instruction file, remove codeowners, stop review requests, git allowlist
- paths: AGENTS.md, .github/CODEOWNERS, CONTRIBUTING.md, docs/prd.md, scripts/setup-branch-protection.sh, agent-memory/README.md
- summary: Kept `AGENTS.md` as the single tracked repository guide and deleted `.github/CODEOWNERS` so opening a pull request no longer requests reviews.
- changes: Added repository Git boundaries, agent-memory rules, and AegisForge invariants while excluding personal slash commands, PATCH/BUILD modes, skills, plugins, tool preferences, and reviewer-assignment machinery; compressed duplicated ledger guidance; deleted `.github/CODEOWNERS` with plain `rm` and updated its live references; corrected the stale `.DS_Store` snapshot.
- verification: `git diff --check` clean; `AGENTS.md` contains no personal slash commands, PATCH/BUILD modes, skills, plugins, Ponytail, Graphify, or subagent preferences; Git boundaries, agent-memory rules, and AegisForge invariants remain; shell, workflow, ruleset, link, and ignore checks from this uncommitted batch still pass.
- remaining: none

<a id="ac-20260901-005"></a>
## AC-20260901-005 — Add a truthful project README
- date: 2026-09-01
- agent: Codex
- status: verified
- prompt_id: [UP-20260901-005](userprompts.md#up-20260901-005)
- related_prompts: none
- tags: readme, prd, innovation, sovereignmesh, evidence
- aliases: root readme, project overview, sovereign proof card
- paths: README.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Replaced the one-line root README with an accurate planning-stage project overview.
- changes: Documented the product intent, repository status, proposed proof-first differentiator, non-negotiable boundaries, layout, and contribution flow; explicitly labelled the Sovereign Proof Card as proposed rather than implemented.
- verification: `git diff --check` passed; inspected the rendered Markdown source and its repository-relative links.
- remaining: The PRD remains unchanged; the proof-card idea needs team approval before it becomes a requirement.

<a id="ac-20260901-006"></a>
## AC-20260901-006 — Present the SIH challenge in the root README
- date: 2026-09-01
- agent: Codex
- status: verified
- prompt_id: [UP-20260901-006](userprompts.md#up-20260901-006)
- related_prompts: [UP-20260901-005](userprompts.md#up-20260901-005)
- tags: readme, sih, sih26117, mrpl, sovereignmesh
- aliases: SIH problem statement 117, MRPL challenge, centred README
- paths: README.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Reworked the root README around the SIH26117 challenge and its sponsor.
- changes: Added the verified SIH title, description, organisation, category, and theme in a centred badge-led README while retaining accurate planning-stage and security-boundary wording.
- verification: `git diff --check` passed; checked all repository-relative README targets exist.
- remaining: Challenge metadata is based on the published SIH problem-statement listing; the product itself remains unimplemented.

<a id="ac-20260901-007"></a>
## AC-20260901-007 — Add six-device hardware inventory
- date: 2026-09-01
- agent: Claude Code
- status: verified
- prompt_id: [UP-20260901-007](userprompts.md#up-20260901-007)
- related_prompts: none
- tags: hardware, device-specs, model-selection, gpu, vram, capability-packs
- aliases: devicespecifications.md, device specs, hardware inventory, model fit, fleet, nvidia-smi, adapterram
- paths: docs/devicespecifications.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Added `docs/devicespecifications.md` covering all six team devices with a summary table, per-device detail, tentative capability-pack mapping, and open items.
- changes: Recorded CPU, RAM, GPU VRAM, storage, OS, and network per device; corrected the ASUS V16 to an RTX 5050 Laptop with 8 GB VRAM, 191 GB free of 477 GB, and no Ethernet adapter; documented the signed 32-bit `AdapterRAM` wrapping bug that under-reports VRAM and flagged the Yug and Prachi 4 GB figures for recheck; flagged Sahil GPU and storage, Tanvi storage, and all runtimes as still needed.
- verification: `nvidia-smi`, `Get-PSDrive C`, and `Get-NetAdapter` run on the ASUS V16 for its row; `git diff --check` passed; confirmed every cited PRD section number exists in `docs/prd.md` and that the relative `prd.md` link resolves from `docs/`.
- remaining: Other five devices are transcribed from members' reported output, not measured here. `docs/prd.md` §12 still lists the ASUS V16 as an RTX 5060 and needs a separate correction.

<a id="ac-20260901-008"></a>
## AC-20260901-008 — Confirm remaining device specs and align the PRD hardware table
- date: 2026-09-01
- agent: Claude Code
- status: verified
- prompt_id: [UP-20260901-008](userprompts.md#up-20260901-008)
- related_prompts: [UP-20260901-007](userprompts.md#up-20260901-007)
- tags: hardware, device-specs, model-selection, gpu, vram, prd
- aliases: sahil specs, tanvi specs, rtx 3050 6gb, lenovo loq, dell inspiron, prd section 12, hardware table
- paths: docs/devicespecifications.md, docs/prd.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Completed the six-device inventory with Sahil's and Tanvi's hardware and replaced the PRD section 12 specifications so both documents agree.
- changes: Recorded Sahil as an RTX 3050 6 GB Laptop GPU with 24 GB dual-channel DDR5 and Ethernet present, replacing the earlier RTX 4050/4060 guess, and flagged App Control for Business as a possible runtime blocker; recorded Tanvi as i5-1235U with Iris Xe only, 16 GB, and a 390 Mbps Wi-Fi 5 link; reassigned the coding pack to the ASUS V16 as the sole 8 GB GPU and gave Sahil a reasoning/CPU-offload pack; rewrote the PRD section 12 table with all six devices, a link to the inventory, and a warning against reading VRAM from `AdapterRAM`.
- verification: `git diff --check` passed; confirmed the relative `devicespecifications.md` link resolves from `docs/`; re-grepped `docs/prd.md` for hardware mentions and found none outside the section 12 table; UP and AC cross-links confirmed reciprocal.
- remaining: Free disk space on four machines, `nvidia-smi` VRAM recheck for both RTX 2050 nodes, installed runtimes fleet-wide, and Sahil's App Control verification are still open.

<a id="ac-20260901-009"></a>
## AC-20260901-009 — Require licence-safe local open-source reuse
- date: 2026-09-01
- agent: Codex
- status: verified
- prompt_id: [UP-20260901-009](userprompts.md#up-20260901-009)
- related_prompts: none
- tags: agents-md, open-source, reuse, licensing, offline-runtime
- aliases: reuse github code, local open source libraries, prototype acceleration, dependency provenance
- paths: AGENTS.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Added a repository-wide implementation rule to adapt suitable local/offline open-source components before rebuilding commodity functionality.
- changes: Required licence compatibility, pinned source provenance, material-change records, and rejection of unlicensed, incompatible, cloud-dependent, or silently networked components.
- verification: `git diff --check` passed; the new rule and reciprocal UP/AC links were found in the working tree.
- remaining: Vedant's reviewed device documentation was not changed; reported findings need a separate approved correction.

<a id="ac-20260901-010"></a>
## AC-20260901-010 — Correct device-inventory evidence and prerequisites
- date: 2026-09-01
- agent: Codex
- status: verified
- prompt_id: [UP-20260901-010](userprompts.md#up-20260901-010)
- related_prompts: [UP-20260901-009](userprompts.md#up-20260901-009)
- tags: device-specs, evidence, macbook, cuda, storage, prd
- aliases: vedant review fixes, gpu configuration, cuda prerequisites, model capacity
- paths: docs/devicespecifications.md, docs/prd.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Corrected the three actionable findings from the device-inventory review and kept the PRD hardware row aligned.
- changes: Labelled reported versus measured hardware; left the Mac GPU core count pending local confirmation; made NVIDIA driver, CUDA Toolkit, and container-toolkit requirements runtime-specific; changed 3–5 models from a false disk limit to an explicit prototype policy.
- verification: `git diff --check` passed; stale overclaim phrases were absent; corrected evidence, prerequisite, capacity, PRD, and reciprocal ledger text was found.
- remaining: Hardware probes, runtime installation, model downloads, and local inference benchmarks remain unrun.

<a id="ac-20260901-011"></a>
## AC-20260901-011 — Add private-server execution objective
- date: 2026-09-01
- agent: Codex
- status: verified
- prompt_id: [UP-20260901-011](userprompts.md#up-20260901-011)
- related_prompts: none
- tags: prd, topology, standalone, trusted-mesh, private-server, scope
- aliases: one system multisystem server, private compute worker, three execution topologies
- paths: docs/prd.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Added private-server-worker execution as the third product topology while preserving the narrower SIH implementation scope.
- changes: Bumped the PRD to 1.2; added the topology to the executive summary, opportunity, thesis, use cases, principles, post-hackathon scope, non-goals, and P2 requirements; kept canonical state on the coordinator and excluded public-cloud inference and a full server-hosted control plane from the MVP.
- verification: `git diff --check` passed; all intended topology references were found; stale two-mode/distributed-mode wording was absent; reciprocal UP/AC links were found.
- remaining: Private-server mode is a documented post-hackathon objective, not implemented or runtime-verified.

<a id="ac-20260901-012"></a>
## AC-20260901-012 — Define the local agent harness and split product documentation
- date: 2026-09-01
- agent: Codex
- status: verified
- prompt_id: [UP-20260901-012](userprompts.md#up-20260901-012)
- related_prompts: [UP-20260901-011](userprompts.md#up-20260901-011)
- tags: agent-harness, onboarding, workflows, control-center, dynamic-nodes, models, prd-split
- aliases: local ChatGPT app, chat documents code, mandatory main engine, reversible pairing, distributed PRD
- paths: docs/prd.md, docs/architecture.md, docs/workflows.md, docs/security.md, docs/model-catalog.md, docs/evaluation.md, docs/README.md, docs/devicespecifications.md, README.md, AGENTS.md, CONTRIBUTING.md, backend/README.md, frontend/README.md, scripts/setup-branch-protection.sh
- summary: Reframed Refinix as one local agent harness with guided model setup, task-specific surfaces, dynamic compute participation, and a truthful Control Center, while moving detail out of the PRD.
- changes: Reduced the PRD to the product contract and 10 P0 outcomes; created focused architecture, workflow, security, model, and evaluation documents; integrated approval, specialist workflow, and sovereignty-dashboard proposals; reconciled live repository references.
- verification: `git diff --check` passed; all repository-local Markdown file links resolved; no stale numbered PRD references or raw proposal comments remained in live docs; new docs had no trailing whitespace; priorities counted 10 P0, 5 P1, and 3 P2.
- remaining: Runtime implementation, official SIH/IP confirmation, technology and model selection, local benchmarks, packaging, sandbox, pairing, and zero-egress proof remain unverified; requester review is the final documentation gate.

<a id="ac-20260902-001"></a>
## AC-20260902-001 — Add the fast execution roadmap
- date: 2026-09-02
- agent: Codex
- status: verified
- prompt_id: [UP-20260902-001](userprompts.md#up-20260902-001)
- related_prompts: [UP-20260901-012](userprompts.md#up-20260901-012)
- tags: tasks, roadmap, internal-hackathon, distributed, integration, finals
- aliases: tasks.md, fast execution plan, claude implementation, codex review, five day sprint, twelve day sprint
- paths: tasks.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Added one operational roadmap for the distributed internal-hackathon build and twelve-day finals follow-through.
- changes: Defined 19 planned tasks with owners, dependencies, daily gates, a nine-step demo, Claude implementation and Codex review handoffs, the proposed fleet mapping, definition of done, and explicit sprint exclusions.
- verification: `git diff --check` passed; `tasks.md` has 19 uniquely numbered planned AF tasks across five daily gates, no trailing whitespace, and existing repository targets for every local file link inspected.
- remaining: All runtime tasks remain planned and unverified; owners are proposed until Aditya confirms them, and the PRD still labels some aggressive internal targets as P1.

<a id="ac-20260902-002"></a>
## AC-20260902-002 — Rebalance roadmap ownership for tool access
- date: 2026-09-02
- agent: Codex
- status: verified
- prompt_id: [UP-20260902-002](userprompts.md#up-20260902-002)
- related_prompts: [UP-20260902-001](userprompts.md#up-20260902-001)
- tags: tasks, ownership, claude-pro, codex-plus, free-tier, team-capacity
- aliases: aditya vedant build, antigravity free tier, nonblocking support tasks, paid agent seats
- paths: tasks.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Reassigned every critical-path build task to Aditya or Vedant and converted the other team roles into bounded, useful support and evidence ownership.
- changes: Added the paid-agent capacity rule; split all 19 AF rows into build and support ownership; assigned Sahil integration drills, Yug document fixtures and scoring, Prachi Linux boundary operation, and Tanvi product acceptance and demo evidence; added the same ownership split to all twelve finals days.
- verification: `git diff --check` passed; no trailing whitespace was found; extracted build-owner fields show only Aditya, Vedant, or both for all 19 AF tasks and all twelve finals days.
- remaining: Antigravity plan capabilities and quotas remain intentionally unverified and noncritical; task owners must still accept their assignments, and all runtime work remains planned.

<a id="ac-20260902-003"></a>
## AC-20260902-003 — Apply focused documentation corrections
- date: 2026-09-02
- agent: Codex
- status: verified
- prompt_id: [UP-20260902-003](userprompts.md#up-20260902-003)
- related_prompts: [UP-20260902-002](userprompts.md#up-20260902-002)
- tags: stale-references, models, hardware, fallback, manifests
- aliases: claude review corrections, qwen vision, day two kill switch, hardware owners, prd references
- paths: .github/pull_request_template.md, .gitignore, agent-memory/README.md, docs/model-catalog.md, docs/devicespecifications.md, tasks.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Corrected stale documentation references and tightened the existing five-day plan without adding a workflow or framework.
- changes: Replaced dead PRD numbers with current document headings; recorded Qwen3.5-4B upstream vision capability with an evidence caveat; made catalogue loading manifest-driven; assigned all six hardware checks; added the Day-2 standalone fallback gate; refreshed stale ledger status.
- verification: `git diff --check` passed; targeted stale-reference search returned no matches; six hardware-check owner items and 19 unique AF task rows were found; introduced local targets and headings exist.
- remaining: Model/runtime compatibility, hardware readiness, owner acceptance, pairing, and all runtime behavior remain unverified.

<a id="ac-20260902-004"></a>
## AC-20260902-004 — Integrate multilingual scope and correct measured hardware
- date: 2026-09-02
- agent: Claude
- status: docs-only
- prompt_id: [UP-20260902-004](userprompts.md#up-20260902-004)
- related_prompts: [UP-20260902-003](userprompts.md#up-20260902-003)
- tags: review-followup, multilingual, hardware-evidence, problem-statement, traceability
- aliases: FR-037, FR-019, vedant disk space, PS coverage, indic models, wsl2 ubuntu
- paths: docs/prd.md, docs/evaluation.md, docs/model-catalog.md, docs/devicespecifications.md, tasks.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Integrated the multilingual requirement as a numbered PRD outcome, replaced unmeasured hardware figures with local command evidence, and made every problem-statement line traceable to a recorded decision.
- changes: Removed the orphaned `Comment By Yug` block whose `FR-037` id had no table entry and re-entered it as FR-019 in the outcome table and finals scope; restored a terminating newline; corrected Vedant free disk from 191 GB to a measured 43.3 GB in three places and recorded measured runtime state including absent Ollama, a Store-alias-only `python`, a stopped Docker daemon, and a usable Ubuntu WSL2 distro; added a Multilingual pack with AI4Bharat and Kokoro candidates carrying licence and ASR-accuracy caveats; added a problem-statement coverage section; linked sprint exclusions to their source lines.
- verification: `git diff --check` clean and no trailing whitespace; no `FR-037` or `Comment By Yug` residue anywhere; FR-019 resolves across four documents; diffstat 81 insertions and 26 deletions with no line-ending churn under `core.autocrlf=true`; hardware values reproduced on the ASUS V16 with `nvidia-smi`, `Get-PSDrive C`, `Get-Command`, and `wsl --list --verbose`.
- remaining: Task-ownership rebalance not applied because reassignment belongs to the integration owner; vision, calculation, PPT, and Excel coverage stay deferred by recorded decision; IndicTrans2 and Indic-TTS licences remain unreviewed; all runtime behaviour remains unverified.

<a id="ac-20260902-005"></a>
## AC-20260902-005 — Align the five-day plan with the mentor infrastructure
- date: 2026-09-02
- agent: Codex
- status: verified
- prompt_id: [UP-20260902-005](userprompts.md#up-20260902-005)
- related_prompts: [UP-20260902-004](userprompts.md#up-20260902-004)
- tags: kubernetes, docker, pods, service-api, redis, five-day-sprint
- aliases: mentor infrastructure, friday plan, k3s worker, redis streams, early completion
- paths: docs/prd.md, docs/architecture.md, docs/security.md, docs/evaluation.md, docs/devicespecifications.md, tasks.md, backend/README.md, frontend/README.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Replaced the Kubernetes and Redis deferral with a bounded mentor-aligned five-day alpha plan.
- changes: Selected one Ubuntu K3s host, Docker-built FastAPI workers, Kubernetes Deployments/Services/Jobs, internal Redis 7.2.x coordination, coordinator SQLite authority, a static local UI, named work packets, daily acceptance gates, and an early-completion ladder.
- verification: `git diff --check` passed; tasks.md contains 19 planned AF rows; targeted searches found no remaining Kubernetes/message-broker exclusion or stale Windows-worker Day-2 path; authoritative documents agree that Redis is ephemeral and not LAN-exposed.
- remaining: The repository still contains no runtime source; all cluster, image, Redis, model, sandbox, security, workflow, performance, and demo claims remain planned until observed on named hardware.

<a id="ac-20260902-006"></a>
## AC-20260902-006 — Add the SIH PPT submission research brief
- date: 2026-09-02
- agent: Codex
- status: verified
- prompt_id: [UP-20260902-006](userprompts.md#up-20260902-006)
- related_prompts: [UP-20260902-005](userprompts.md#up-20260902-005)
- tags: sih26117, ppt, portal-submission, research, judge-preparation
- aliases: SIH PPT brief, six slide deck, presentation workers, research papers, portal submission
- paths: docs/sih-ppt-submission-brief.md, docs/README.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Added one non-normative research and production brief for the official six-slide SIH26117 idea presentation.
- changes: Consolidated problem context, portal/template verification boundaries, portal-ready copy, architecture and mentor-stack explanation, differentiation, feasibility, impact, six slide instructions, speaker timing, evidence placeholders, claim controls, judge Q&A, and primary research/implementation references; linked it from the documentation index.
- verification: `git diff --check` passed; the brief contains 17 top-level numbered sections, all six required slide sections, the live-portal placeholder, evidence and claim controls, and only existing repository-local Markdown targets.
- remaining: Team ID, live portal terms and deadline, the downloaded official template, final product name, selected model/runtime, prototype screenshots, measurements, and every runtime claim still require team verification before submission.

<a id="ac-20260902-007"></a>
## AC-20260902-007 — Start AF-001 with checked shared contracts
- date: 2026-09-02
- agent: Codex
- status: partial
- prompt_id: [UP-20260902-007](userprompts.md#up-20260902-007)
- related_prompts: [UP-20260902-005](userprompts.md#up-20260902-005)
- tags: af-001, day-1, contracts, lifecycle, redis, sse, pydantic
- aliases: day 01, shared contract version 1.0, contract checks, unavailable evidence
- paths: backend/contracts/, backend/requirements.txt, backend/README.md, tasks.md, README.md, docs/prd.md, docs/evaluation.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Added the initial shared contract package and passed its local checks while keeping AF-001 in progress and all application runtime gates open.
- changes: Added seven versioned records, lifecycle and trust-boundary guards, SSE encoding, retry digests, Redis keys, schema export, synthetic examples, protocol semantics and dependency provenance; updated task and repository status text.
- verification: After explicit user approval, created ignored .venv and installed five pinned dependencies; five unittest checks passed on Python 3.14.6/macOS 26.6.2 arm64; pip check found no broken requirements; CLI export parsed with seven schemas; git diff --check, Python/JSON syntax parsing and 38 local Markdown file targets passed.
- remaining: OD-06 pairing protocol, all four contract consumers, requester verification, cluster, worker image/model inference, SQLite and UI remain unverified or unimplemented; no Git writes, model downloads or deployments ran.

<a id="ac-20260903-001"></a>
## AC-20260903-001 — Prepare Yug's worker-spine execution packet
- date: 2026-09-03
- agent: Codex
- status: verified
- prompt_id: [UP-20260903-001](userprompts.md#up-20260903-001)
- related_prompts: [UP-20260902-007](userprompts.md#up-20260902-007)
- tags: yug, claude, worker-spine, ownership, execution-packet, review
- aliases: WP-YUG-001, huge task, two builders, worker runtime Redis K3s handoff
- paths: docs/yug-worker-spine.md, docs/README.md, tasks.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Created a substantial worker execution packet for Yug's Claude and updated current-sprint build ownership to Aditya and Yug.
- changes: Defined six phases covering the review baseline, real model adapter, authenticated worker, Redis recovery, Docker/K3s and coordinator integration, with allowed paths, permission boundaries, runnable acceptance targets, failure evidence and publication/review handoff; kept other members' operational/evidence support and provisional finals assignments.
- verification: git diff --check passed; all 37 local Markdown file targets inspected exist; no trailing whitespace in the packet/index/board; all 19 AF IDs, states, task scopes, dependencies and acceptance gates are unchanged; current-sprint build owners are only Aditya/Yug; six packet phases are present.
- remaining: Yug's contract review, implementation, required runtime/host permissions, model/pairing decisions and actual acceptance remain open; no runtime tests, installs, deployments, Git writes or external messages were performed.

<a id="ac-20260903-002"></a>
## AC-20260903-002 — Replace personal packets with named human checkpoints
- date: 2026-09-03
- agent: Codex
- status: review
- prompt_id: [UP-20260903-002](userprompts.md#up-20260903-002)
- related_prompts: [UP-20260903-001](userprompts.md#up-20260903-001)
- tags: human-checkpoints, claude, codex, setup, five-day-sprint
- aliases: thirteen chunks, named setup operators, stop verify resume, team explanation
- paths: AGENTS.md, tasks.md, docs/README.md, docs/yug-worker-spine.md, docs/architecture.md, docs/devicespecifications.md, docs/evaluation.md, backend/contracts/README.md, CONTRIBUTING.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Replaced the personal worker packet and fixed build assignments with thirteen shared chunks ending at named human actions, including inventory commands and verification handoffs.
- changes: Deleted docs/yug-worker-spine.md; aligned shared agent, architecture, evaluation and contribution guidance; separated image build/digest receipt from deployment and required Built/Verified/Next explanations after each cycle.
- verification: git diff --check and static document comparisons passed; all 19 AF states/dependencies/acceptance rows, five daily gates and historical device measurements were preserved; thirteen chunks have named human actions and return evidence; no active obsolete-packet references or build-owner tables remain.
- remaining: Requester documentation acceptance and C01 authorisation are pending; no runtime code, tests, setup commands, installers, model downloads, deployments or Git writes were executed.

<a id="ac-20260903-003"></a>
## AC-20260903-003 — Make execution depend on task prerequisites
- date: 2026-09-03
- agent: Codex
- status: docs-only
- prompt_id: [UP-20260903-003](userprompts.md#up-20260903-003)
- related_prompts: [UP-20260903-002](userprompts.md#up-20260903-002)
- tags: numbered-tasks, human-checkpoints, prerequisites, calendar-independent
- aliases: C01 to C13, task name and number, wait for human, no implementation timetable
- paths: tasks.md, AGENTS.md, CONTRIBUTING.md, README.md, backend/README.md, backend/contracts/README.md, frontend/README.md, docs/README.md, docs/prd.md, docs/architecture.md, docs/evaluation.md, docs/devicespecifications.md, docs/sih-ppt-submission-brief.md, .github/pull_request_template.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Replaced implementation schedules with named C01–C13 tasks, explicit predecessors, human waits and task-numbered acceptance gates throughout active planning documents.
- changes: Removed delivery-day labels, Friday target and timed integration cadence; labelled later tasks F01–F12; aligned presentation/PR guidance and updated section links while retaining prior documentation changes.
- verification: Static comparisons passed for all 19 AF rows, five acceptance requirements, 13 human-action/evidence pairs and 12 follow-up requirements; historical dates, ledger prefixes and contract source/dependency hashes were preserved; active planning text has no remaining day/sprint cadence labels and git diff --check passed.
- remaining: Requester documentation review and C01 authorisation remain pending; no runtime implementation, runtime tests, setup operations or Git writes were performed.

<a id="ac-20260903-004"></a>
## AC-20260903-004 — Ground the documents workflow with typed citations
- date: 2026-09-03
- agent: Claude
- status: partial
- prompt_id: [UP-20260903-004](userprompts.md#up-20260903-004)
- related_prompts: [UP-20260902-007](userprompts.md#up-20260902-007)
- tags: c01, af-001, contracts, citations, documents, grounding, page-mapping
- aliases: citations.resolve, Citation record, require_grounded_citations, cited approval note
- paths: backend/contracts/v1.py, backend/contracts/test_contracts.py, backend/contracts/examples.json, backend/contracts/README.md, tasks.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Gave the merged AF-001 draft's citations.resolve validator a typed payload and a coordinator-side grounding guard so the documents workflow has a contract to build against.
- changes: Added a Citation record binding a claim to a resource and 1-based page with its verbatim quote; added Proof.citations with a uniqueness guard; added require_grounded_citations rejecting mismatched jobs, missing citations and unsupplied sources; extended the synthetic Proof example and the contract check.
- verification: Six unittest checks passed on Python 3.13.2/Windows 11 AMD64; each guard rejection branch was executed individually and returned a distinct message; schema export parsed with seven schemas and Citation resolved under Proof; examples.json parsed; git diff --check passed.
- remaining: Ran against pydantic 2.13.4, not the pinned 2.13.5, so the pinned environment is unverified on Windows; extraction uncertainty and unresolved-field records are deferred until an extractor exists; OD-06, consumer integration and every runtime gate remain open; no Git writes ran.

<a id="ac-20260903-005"></a>
## AC-20260903-005 — Complete the C01 contract repairs
- date: 2026-09-03
- agent: Claude
- status: partial
- prompt_id: [UP-20260903-005](userprompts.md#up-20260903-005)
- related_prompts: [UP-20260903-004](userprompts.md#up-20260903-004)
- tags: c01, af-001, contracts, output-validators, cancellation, interruption, failure-codes
- aliases: chunk C01, applicable validators, stopped attempt reason, cancelled_by_user
- paths: backend/contracts/v1.py, backend/contracts/test_contracts.py, backend/contracts/README.md, tasks.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Closed the two remaining C01 contract repairs so each output kind requires the validator that proves it and every stopped attempt records a typed reason.
- changes: Bound OutputContract validators to the declared output kind with required/optional tables and rejected duplicate validators; added the cancelled_by_user failure code, required a typed Failure on failed, cancelled and interrupted attempts, and blocked cancelled_by_user from relabelling a crash or interruption; added two focused checks and documented both rules.
- verification: Eight unittest checks passed on Python 3.13.2/Windows 11 AMD64; each added rejection branch was executed individually and returned a distinct correct message; every added accepted case parsed; schema export parsed at 52304 bytes with seven schemas.
- remaining: Ran against pydantic 2.13.4, not the pinned 2.13.5; the C01 human checkpoint is open, needing Aditya's acceptance of the reviewed contract diff and read-only device inventory from all six people; extraction uncertainty records, OD-06, consumer integration and every runtime gate remain open; no Git writes ran.
