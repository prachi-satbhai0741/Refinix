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

<a id="ac-20260903-006"></a>
## AC-20260903-006 — Bind citation evidence to one dispatched attempt
- date: 2026-09-03
- agent: Claude
- status: partial
- prompt_id: [UP-20260903-006](userprompts.md#up-20260903-006)
- related_prompts: [UP-20260903-005](userprompts.md#up-20260903-005)
- tags: c01, af-001, code-review, citations, evidence-binding, retry, board-status
- aliases: require_grounded_citations, superseded retry, proof pairing, current scope note
- paths: backend/contracts/v1.py, backend/contracts/test_contracts.py, backend/contracts/README.md, tasks.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Fixed the reviewed evidence-binding defect so a superseded retry's proof can no longer clear the attempt that replaced it, and corrected the board's current-scope note.
- changes: Replaced the guard's single job_id comparison with a workspace, job, attempt and target-node comparison naming the mismatched field; added four rejection checks covering workspace, job, superseded attempt and untargeted node; documented the binding and recorded Codex's independent pinned-dependency run; set the current-scope note to C01 in review with C02 locked.
- verification: Reproduced all three reported acceptances before the fix and confirmed each is now rejected with its own message; eight unittest checks passed and the grounded happy path still passes on Python 3.13.2/Windows 11 AMD64 with pydantic 2.13.4; schema export unchanged at 52304 bytes.
- remaining: Windows verification against the pinned pydantic 2.13.5 is still outstanding; Aditya's acceptance and the six device inventories keep the C01 checkpoint open and C02 locked; extraction uncertainty records, OD-06, consumer integration and every runtime gate remain open; no Git writes ran.

<a id="ac-20260903-007"></a>
## AC-20260903-007 — Reconciled device evidence and prepared setup handoff
- prompt_id: [UP-20260903-007](userprompts.md#up-20260903-007)
- date: 2026-09-03
- status: in review
- scope: documentation, execution, hardware-inventory
- tags: c01, devicespecifications, tasks, human-checkpoint
- aliases: reconcile device evidence, prepare setup handoff, update inventory
- paths: docs/devicespecifications.md, tasks.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Updated docs/devicespecifications.md with new read-only inventory data from all six team members, and updated tasks.md to reflect the C01 review status and open human checkpoints.
- changes: Clarified in devicespecifications.md that new tool paths do not prove runtime readiness or versions. Updated disk space metrics and WindowsApps aliases limitations. Retained historical GPU memory for Vedant (truncated output) and Yug (missing output). Updated tasks.md current scope to reflect inventory receipt, Codex's PASS review at e7f44fb, and explicitly kept the C01 human checkpoint open for Aditya's acceptance and missing inventory details.
- verification: Checked documentation changes matched requirements; no code was executed and no tests were run.
- remaining: Aditya's acceptance of the reviewed contract diff is pending. Missing inventory details (Yug's GPU, Vedant's complete GPU line, network confirmations, and specific version/service status) need to be supplied by the team. C02 remains locked. No Git writes ran.

<a id="ac-20260903-008"></a>
## AC-20260903-008 — C01 documentation closeout and C02 decisions
- prompt_id: [UP-20260903-008](userprompts.md#up-20260903-008)
- date: 2026-09-03
- status: in review
- scope: documentation, execution, runtime-decision, model-decision, infrastructure-pins
- tags: c01, c02, od-03, od-05, od-06, od-08, device-based-checkpoints
- aliases: close c01 docs, device based checkpoints, resolve od decisions, ollama measurement
- paths: tasks.md, AGENTS.md, agent-memory/README.md, docs/devicespecifications.md, docs/architecture.md, docs/model-catalog.md, docs/evaluation.md, docs/security.md, docs/prd.md, scripts/od03_runtime_comparison.py
- summary: Converted the active execution instructions to device-based human checkpoints, recorded the OD-03 runtime, OD-05 model, OD-06 pairing and OD-08 infrastructure decisions with upstream provenance, and measured a bounded local inference on the macOS coordinator.
- changes: Replaced every personal assignment in tasks.md and AGENTS.md with `macOS coordinator`/`Ubuntu worker` roles and requester acceptance, leaving ledger names and Git identities untouched. Added a first-configuration section to devicespecifications.md that puts the four Windows machines and both incomplete GPU lines off the critical path, recorded the coordinator's measured runtimes and model provenance, and added the read-only C02 evidence commands for the Ubuntu worker. Pinned K3s v1.36.4+k3s1, redis:7.2.16 and python:3.13-slim-bookworm with registry digests and licences in architecture.md 8.1. Selected Ollama (OD-03) and a one-model set (OD-05) in model-catalog.md, recorded the prototype pairing policy in security.md 4.1, and added scripts/od03_runtime_comparison.py with its method in evaluation.md 5.1.
- review_fixes: Codex returned NEEDS FIX with seven findings; all seven are addressed. Removed `ollama list` from both inventory blocks because fourteen Ollama subcommands carry `PreRunE: checkServerHeartbeat`, which calls `startApp` on a refused connection, and reconciled tasks.md to record that the coordinator's Ollama app was started that way. Replaced the unfiltered `systemctl cat` grep with an allowlisted `OLLAMA_*` extraction so proxy credentials and tokens cannot enter a verbatim transcript. Moved both runtimes onto templated chat endpoints with thinking disabled and prompt caching left at each default, and stopped disabling llama-server's cache one-sidedly. Labelled llama-server's first request `first_request_after_server_start` with `includes_model_load: false`. Made the parsers reject malformed lines, error objects, missing terminal records and missing metrics with a non-zero exit, and added scripts/test_od03_parser.py. Restored the C01-fixed ports WORKER_PORT 8443 and WORKER_NODE_PORT 30443 in architecture.md, leaving only host availability and deployment verification outstanding. Added response hashing and corrected the cold-penalty attribution.
- verification: Confirmed backend/ is unchanged since e7f44fb, so Codex's eight-check PASS is reused rather than rerun; independently confirmed the coordinator venv matches all five pinned dependencies. Confirmed against ollama v0.32.14 cmd/cmd.go that fourteen subcommands start the app and the root version command does not. Ran 15 offline parser checks: all passed. Re-ran the corrected script against the already-running loopback Ollama server via /api/chat: 89 tokens / 598 characters and one response SHA-256 across four runs, cold TTFT 2.504 s including 2.300 s model load, warm median 0.225 s, ~37.9 tok/s, RSS 3.83-3.90 GB; the earlier untemplated /api/generate figures are superseded, not averaged. Cold penalty is 93.2 percent model load and 6.6 percent prompt evaluation. Confirmed the server listens on 127.0.0.1:11434 only, and re-hashed all four model blobs against their content-addressed names. Checked every internal documentation link and anchor.
- remaining: Codex re-review and requester acceptance of this closeout; the Ubuntu worker's read-only evidence and its setup; the llama-server half of the OD-03 comparison, which needs an install checkpoint, plus a comparable cold figure timed from server start; worker and sandbox image digests at C04, and host port availability plus deployment verification for the contract's 8443/30443 at C02 and C05. AF-001 stays a draft, OD-06 is recorded but unimplemented, Windows is explicitly unverified, and no Git writes ran.

<a id="ac-20260903-009"></a>
## AC-20260903-009 — Repaired remaining C02 parser and inventory findings
- prompt_id: [UP-20260903-009](userprompts.md#up-20260903-009)
- date: 2026-09-03
- status: in review
- tags: c02, runtime-comparison, stream-parser, inventory
- aliases: reasoning channel, missing generation timing, failed port probe, stale mac inventory
- paths: scripts/od03_runtime_comparison.py, scripts/test_od03_parser.py, docs/devicespecifications.md, docs/evaluation.md, docs/architecture.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Fixed separate-reasoning evidence and generation-metric validation, preserved socket-probe failures, and reconciled the Mac inventory with the later recorded inference.
- changes: TTFT now observes both llama-server channels; reasoning contributes to the suppression flag without entering the visible-response hash. Missing, nonpositive, nonfinite or incorrectly typed generation metrics are rejected. One socket snapshot covers runtime and contract ports without claiming availability from an empty result; initial Mac state is distinguished from subsequent measurement.
- verification: The requester separately approved offline tests. On the macOS coordinator, `python3 -B scripts/test_od03_parser.py` passed all 20 tests. Four simulated runs of the documented socket probe passed for empty, occupied, failed and missing-command cases; no host socket query ran. Python and shell syntax checks and `git diff --check` passed.
- remaining: Requester acceptance and real Ubuntu inventory/setup remain open in C02. No inference, service start, installation, download, deployment or Git write ran; earlier runtime measurements were not rerun.

<a id="ac-20260903-010"></a>
## AC-20260903-010 — Prepared C02 closeout and corrected runtime memory evidence
- prompt_id: [UP-20260903-010](userprompts.md#up-20260903-010)
- date: 2026-09-03
- status: in review
- tags: c02, closeout, runtime-comparison, memory-reporting
- aliases: ubuntu inventory, bundled engine, defer comparisons, runner rss
- paths: tasks.md, docs/devicespecifications.md, docs/evaluation.md, docs/model-catalog.md, docs/architecture.md, docs/prd.md, scripts/od03_runtime_comparison.py, scripts/test_od03_parser.py, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Recorded user-returned Ubuntu setup and both devices' inference evidence, retained Ollama with explicit comparison deferrals, and repaired the daemon-only RAM report.
- changes: Added versions, model manifest identity, per-run timings, corrected memory units and provenance; documented the reused Mac bundle and reproduction commands. Memory snapshots now list exact-name process candidates with PID, parent PID, RSS and PID-matched GPU memory, without endpoint attribution or aggregation. Reconciled C02 status and C01-fixed ports; removed the incomplete direct-server launch hint in favour of the documented command.
- verification: Reused prior offline-test permission; `python3 -B scripts/test_od03_parser.py` passed 23 tests, including three mocked memory checks. Python syntax, five shell blocks checked with syntax-only parsers, reported medians/RSS conversions and `git diff --check` passed; 165 local Markdown links/anchors had no failures. `git diff --exit-code e7f44fb -- backend` confirmed no backend changes. Device runtime results were reviewed from returned output, not rerun.
- remaining: Requester acceptance of the closeout; C03 requires separate authorisation. Controlled cold-start and Ubuntu direct-engine comparisons are deferred by requester, not passed. No live process/socket queries, inference, service starts, installs, downloads, deployments or Git writes ran in this closeout.

<a id="ac-20260903-011"></a>
## AC-20260903-011 — Added the language and technology guide
- prompt_id: [UP-20260903-011](userprompts.md#up-20260903-011)
- date: 2026-09-03
- status: in review
- tags: tech-stack, languages, frontend, architecture, documentation
- aliases: TechStack.md, typescript react vite, python sql, language selection
- paths: TechStack.md, README.md, docs/README.md, docs/architecture.md, frontend/README.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Created a discoverable guide recommending languages and technologies for each product surface and supporting layer, with evidence states and trade-offs.
- changes: Recommended TypeScript/React/Vite for the UI, Python for orchestration and tools, SQL/SQLite for state, and existing native inference engines; retained Ollama and Redis Streams. Distinguished the proposed UI revision from the recorded vanilla baseline, qualified OCR/document candidates and licences, and preserved conditional additional-worker scope.
- verification: Inspected current source and official upstream documentation. A read-only check of five documents resolved all 57 local Markdown links/anchors and found no whitespace problems; `git diff --check` passed. No runtime tests were needed or run for these prose changes.
- remaining: Requester review of the guide; adoption and dependency pinning belong to the relevant authorised implementation chunks. No scaffold, dependency installation, live command, runtime change or Git write ran; prior C02 changes were preserved.

<a id="ac-20260903-012"></a>
## AC-20260903-012 — Clarified C02 listener and cancellation gaps
- prompt_id: [UP-20260903-012](userprompts.md#up-20260903-012)
- date: 2026-09-03
- status: in review
- tags: c02, closeout, listener, cancellation, review
- aliases: claude review, wildcard port 8080, cancellation not exercised, techstack handoff
- paths: tasks.md, docs/devicespecifications.md, docs/evaluation.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Made the unidentified Ubuntu listener an explicit C02 follow-up and recorded that application cancellation remains unimplemented and untested.
- changes: Separated wildcard binding from C05 contract-port checks and untested LAN reachability; reconciled the closeout's next human action; assigned cancellation implementation and the device exercise to the existing C06 / AF-005–AF-007 gate.
- verification: Inspected the recorded socket evidence, comparison transport and C06 task definitions; `git diff --check` passed. `git diff --exit-code e7f44fb -- backend` confirmed no backend changes. No tests, inference or live host checks ran.
- remaining: Ubuntu listener identification and exposure review, requester acceptance and separate C03 authorisation. TechStack.md and all AF states remain unchanged; no Git writes ran.

<a id="ac-20260903-013"></a>
## AC-20260903-013 — Add the Control Room design tokens and the Chat surface reference
- date: 2026-09-03
- agent: Claude
- status: partial
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: [UP-20260902-007](userprompts.md#up-20260902-007)
- tags: ui, design-tokens, chat-surface, theming, accessibility, evidence-semantics
- aliases: control room tokens, blueprint artifact, cyanotype dark, approval gate, execution target picker, contrast sweep
- paths: frontend/design/README.md, frontend/design/tokens.css, frontend/design/chat.css, frontend/design/chat.html, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Added a two-theme design token set and a static Chat surface reference page that renders the approval gate, execution-target picker and job inspector using the frozen contract vocabulary.
- changes: Recorded the Control Room direction with Blueprint reserved for artifacts; added light and dark token blocks resolving across system-default and explicit choices; built the Chat page with lifecycle rail using JobState literals, event log using Event.data.kind values, and an approval gate carrying an Approval.action; rendered unavailable evidence as a hatched grey row that cannot read as a healthy zero; suppressed transitions during a theme swap.
- verification: Served the page locally and swept all 108 text-bearing elements for contrast in three theme states — system dark, explicit dark, explicit light; raised six token values and recessed the disabled target control after the first sweep failed; final minimum ratio 4.49:1 with every other element at or above 4.5:1. Confirmed the three webfonts load rather than silently falling back by measuring glyph widths against the fallback stacks. Grid resolves to 188/860/232 at 1280px with no horizontal overflow.
- remaining: Documents, Code, Control Center and the public distribution site are unbuilt. The page is a static reference: it is not wired to the coordinator or the event stream. Fonts load from Google Fonts and must be self-hosted before any offline build. Other browsers, screen readers, keyboard traversal order and breakpoints below 1100px are unverified. No Git writes ran.

<a id="ac-20260903-014"></a>
## AC-20260903-014 — Add the public distribution site reference
- date: 2026-09-03
- agent: Claude
- status: partial
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: none
- tags: ui, public-site, distribution, blueprint, theming, accessibility
- aliases: download website, cyanotype whiteprint, p&id hero, checksum verification, pre-release state
- paths: frontend/design/site.css, frontend/design/site.html, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Added a static reference for the public distribution site in its own Blueprint treatment, carrying an honest pre-release download state rather than a fabricated release.
- changes: Added a self-contained token block that does not inherit the application tokens, since the site is a separate trust boundary; built hero, sovereignty-proof, capability and download sections; drew the hero P&ID plate as inline SVG; rendered enforced, observed and unavailable as three distinct claim kinds with the unavailable one hatched; marked the page with a sample-content strip and replaced download buttons with a stated not-yet-released state; documented the treatment and the theme-swap measurement pitfall in the design README.
- verification: Swept all 93 text-bearing elements for contrast in dark and light; zero failures, minimum 7.54:1 dark and 5.19:1 light. Confirmed no horizontal overflow at 1265px client width. Fixed a hero SVG annotation clipped outside its viewBox and removed an empty text node. Confirmed the data-theme-switching hook suppresses transitions, measured as transition-duration 0s while set.
- remaining: Documents, Code and Control Center surfaces are unbuilt. Both pages are static references not wired to the coordinator. Fonts load from Google Fonts and must be self-hosted before any offline build. Version numbers, checksums, system requirements and release artifact names on the site are placeholders and require team decisions. Other browsers, screen readers, keyboard traversal and sub-1100px breakpoints are unverified. No Git writes ran.

<a id="ac-20260903-015"></a>
## AC-20260903-015 — Rework the public site treatment after design review
- date: 2026-09-03
- agent: Claude
- status: partial
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: none
- tags: ui, public-site, design-review, ornament, theming, accessibility
- aliases: remove drafting grid, atmospheric ground, corinthian helmet, meander frieze, placeholder artwork
- paths: frontend/design/site.css, frontend/design/site.html, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Replaced the public site treatment after the requester rejected the tiled drafting-grid background, moving to an atmospheric ground and an engraved classical plate.
- changes: Removed the tiled grid background entirely and replaced it with two soft radial fields behind the content; removed the hard-bordered claim and build grids in favour of hairline rules and larger spacing; enlarged the display type and softened button geometry; replaced the P&ID hero plate with a drawn medallion holding a frontal Corinthian helmet above a Greek meander frieze, chosen because the aegis is the source of the repository name; added a visible circular marker stating the artwork is a placeholder; retained the honest pre-release download state and sample-content strip.
- verification: Reference sites reviewed in-browser before reworking. Swept all 92 text-bearing elements for contrast in dark and light using the data-theme-switching hook to avoid transition races; zero failures, minimum 7.20:1 dark and 5.30:1 light. Confirmed no horizontal overflow at 1245px client width and that hero, three sections and footer occupy contiguous vertical space with no gaps. First helmet attempt drawn in profile read as an unrecognisable silhouette and was rebuilt frontally; crest and scale then corrected on a second pass.
- remaining: The hero artwork is explicitly provisional and awaits a chosen commissioned or public-domain replacement. Documents, Code and Control Center surfaces are unbuilt. Both pages are static references not wired to the coordinator. Fonts load from Google Fonts and must be self-hosted before any offline build. Version numbers, checksums and system requirements remain placeholders. The preview pane would not paint content below the fold, so sections after the hero were verified by measurement rather than by screenshot. No Git writes ran.

<a id="ac-20260903-016"></a>
## AC-20260903-016 — Add four engraved plates and ambient motion to the public site
- date: 2026-09-03
- agent: Claude
- status: partial
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: none
- tags: ui, public-site, ornament, svg, motion, accessibility
- aliases: corinthian helmet, athenian owl, doric temple, labyrinth, ember eyes, conic ray field
- paths: frontend/design/site.css, frontend/design/site.html, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Replaced the single simple helmet with four dense engraved plates and added restrained ambient motion, after the requester judged the previous ornament too sparse and too plain.
- changes: Raised the hero medallion detail with a beaded border, a thirty-leaf laurel wreath, a twenty-four unit egg-and-dart ring and a hundred-spoke conic ray field; rebuilt the helmet with a crest drawn over the bowl, a decorated brow band, bowl hatching, egg-and-dart along the nasal and cheek spirals; added three further plates - an Athenian owl tetradrachm on the proof section, a Doric temple elevation on the capability section, and a concentric labyrinth on the download section; added ember glow and long-cycle blinking on the helmet and owl eyes, one travelling glimmer on the labyrinth, and a four-minute rotation on the ray field, all disabled under prefers-reduced-motion.
- verification: Reference sites re-examined before drawing. All four plates inspected by lifting the below-fold figures to the top of the document, since the preview pane would not paint below the fold. Swept all 92 text-bearing elements for contrast in dark and light with transitions suppressed; zero failures, minimum 7.20:1 dark and 5.30:1 light. Confirmed no horizontal overflow at 1245px and that all seven declared animations report a running playState. Three drawing defects were found and corrected on review: the bowl painted over the crest, the gorgoneion collided with the crest and read as an insect so it was replaced with a decorated brow band, and the laurel leaves pointed radially instead of lying along the ring.
- remaining: All four plates are explicitly provisional placeholders. Documents, Code and Control Center surfaces are unbuilt. Both pages are static references not wired to the coordinator. Fonts load from Google Fonts and must be self-hosted before any offline build. Version numbers, checksums and system requirements remain placeholders. Sections below the hero were verified by measurement and by lifting elements, not by full-page screenshot. No Git writes ran.

<a id="ac-20260903-017"></a>
## AC-20260903-017 — Rebuild the public site on a glass surface system with an interactive product demo
- date: 2026-09-03
- agent: Claude
- status: partial
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: none
- tags: ui, public-site, glassmorphism, interaction, motion, accessibility
- aliases: surface switcher, tabbed terminal, copy button, scroll reveal, theme toggle, near-black ground
- paths: frontend/design/site.css, frontend/design/site.html, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Rebuilt the public site on a near-black glass surface system with roughly twice the content and a working product demo, after the requester judged the previous version empty and unimpressive.
- changes: Replaced the token set with a near-black ground, three-layer radial lighting and glass panels using low-alpha fills, hairline borders and backdrop blur; adopted DM Sans for UI while keeping Spectral for display and IBM Plex Mono for terminal blocks; added a sticky blurred nav with a pre-release chip and a theme toggle, a formula band, a four-card design-approach row, a stats band, a two-column get-started block, a closing section and an expanded footer; added an interactive surface switcher with working Chat, Documents, Code and Control Center panels that demonstrate the evidence semantics on the public page; added tabbed terminal blocks with a copy button, scroll reveal, card hover lift and a pointer spotlight; retained all four engraved plates and their ambient motion. Reference sites were studied for surface technique only; their copy, branding and product content were not reproduced.
- verification: Read the reference page structure and measured its computed surface tokens before building. Swept 268 text-bearing elements for contrast in both themes with every panel unhidden; zero failures, minimum 7.20:1 dark and 5.62:1 light. Confirmed no horizontal overflow at 1265px, no console errors, and that tab switching, the copy button and the theme toggle all behave correctly in both directions. Four defects were found and fixed during review: a .hero > * rule overrode the spotlight overlay position and displaced the whole hero grid; semantic ok and danger colours were hardcoded for dark and failed at 1.92:1 in light; reveal styles applied without a scripted-document guard, so a script failure would have hidden the entire page; and IntersectionObserver-based reveal stranded 31 elements permanently invisible after an anchor jump, replaced with a scroll position check re-run on load and hashchange.
- remaining: All four plates remain provisional placeholders. Documents, Code and Control Center application surfaces are unbuilt. Both pages are static references not wired to the coordinator. Fonts load from Google Fonts and must be self-hosted before any offline build. Version numbers, checksums, system requirements and the stats figures are placeholders requiring team decisions. Sections below the hero were verified by measurement and by lifting elements into view, since the preview pane would not paint below the fold. Other browsers, screen readers and keyboard traversal are unverified. No Git writes ran.

<a id="ac-20260903-018"></a>
## AC-20260903-018 — Place the team mark and prepare the logo asset slot
- date: 2026-09-03
- agent: Claude
- status: partial
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: none
- tags: ui, branding, assets, public-site, chat-surface
- aliases: rokunin sync logo, team mark, brand token, logo placement, data uri inlining
- paths: frontend/design/assets/README.md, frontend/design/site.css, frontend/design/site.html, frontend/design/chat.css, frontend/design/chat.html, frontend/design/tokens.css, agent-memory/agentchangelog.md
- summary: Placed the Rokunin Sync mark across the public site and the Chat surface using a drawn stand-in, and prepared the asset slot so the supplied logo file drops in without further edits.
- changes: Added a brand orange token to both site themes and all three application theme blocks, kept separate from the semantic signal colour; added a drawn SVG symbol as a stand-in mark in the site nav and the Chat surface header; placed the full lockup in the footer credit and the closing signature as team attribution rather than as the product wordmark, since the lockup spells the team name and the product is Refinix; made those images stay hidden until they actually decode so a missing asset degrades to the text credit instead of a broken image; created assets/README.md recording the expected filenames, the Refinix versus Rokunin Sync distinction, the swap procedure and the licensing note; taught the single-file artifact build to inline anything under assets/ as a data URI, since published artifact pages cannot load external images.
- verification: Confirmed the symbol renders at the intended size in brand orange on both pages and that the SVG use reference resolves; confirmed both lockup images correctly remain hidden while the file is absent; fixed the version string wrapping to two lines in the Chat header after the mark was added, verified back to one line with no horizontal overflow; confirmed the artifact build reports the two missing asset references and leaves them untouched rather than emitting broken markup.
- remaining: The supplied logo image could not be written to disk from the conversation, so frontend/design/assets/rokunin-sync-logo.png does not exist and the placed mark is a drawn stand-in, not the real artwork. A team member must save the file at that path; the lockup then appears automatically and the artifact build inlines it. The four engraved plates also remain provisional. Documents, Code and Control Center surfaces are unbuilt. Fonts load from Google Fonts and must be self-hosted before any offline build. No Git writes ran.

<a id="ac-20260903-019"></a>
## AC-20260903-019 — Change the public site headline to "Nothing leaves the machine"
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: none
- tags: ui, public-site, copy
- aliases: hero headline, nothing leaves the machine, plant wording
- paths: frontend/design/site.html, agent-memory/agentchangelog.md
- summary: Changed the public site hero headline from "Nothing leaves the plant" to "Nothing leaves the machine" at the requester’s direction.
- changes: Edited the hero h1 only. The three other uses of "plant" were left in place because they carry a different sense: the capability heading describes the work an industrial plant generates, the download copy describes the installer reaching the plant, and the token comments describe HMI plant state.
- verification: Confirmed the headline wraps to three balanced lines at 1240px with text-wrap balance and stays inside its box; no new horizontal overflow attributable to the change.
- remaining: The wording is narrower than the product behaviour it sits above. The same page advertises pairing, where the coordinator routes bounded job context to a trusted device over the LAN, so work can leave the originating machine while remaining on the premises. Flagged to the requester; the wording stands as their decision.

<a id="ac-20260903-020"></a>
## AC-20260903-020 — Replace the pointer spotlight with a grain particle field
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: none
- tags: ui, public-site, motion, canvas, performance, accessibility
- aliases: grain field, particles, cursor interaction, spotlight removed, canvas background
- paths: frontend/design/site.css, frontend/design/site.html, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Replaced the pointer-tracked gradient spotlight with a canvas grain field whose particles drift on a slow rotation and scatter away from the cursor.
- changes: Removed the spotlight overlay, its CSS and its pointer handler, along with the hero grid guard that existed only to exclude it. Added a fixed canvas behind all content carrying roughly 1,200 low-alpha particles; the field rotates slowly about the viewport centre to echo the sync mark, about a fifth of the grains carry the brand orange, and particles near the pointer brighten and are pushed outward before easing back. Particle colours are read from CSS custom properties so the field follows the theme toggle. Restricted to fine pointers, skipped entirely under reduced motion, and paused while the tab is hidden.
- verification: Measured the reference implementation directly before building - its particle canvas draws pure white at 0.04 alpha over about 0.84 percent of its pixels, desktop only. Tuned this field to 0.49 percent coverage at 0.047 average alpha with a 23 percent warm share, lower than the reference because it is visible at rest rather than only on movement. Confirmed pointer response by comparing a 300px region at the cursor against the far corner: 5.4x peak alpha and 3.6x average. Confirmed the field recolours in both directions across the theme toggle, that hero layout is unchanged after removing the grid guard, and that no console errors occur. Three defects were found and fixed: the field was far too sparse at first tuning, it painted nothing until the first animation frame so a hidden tab stayed blank, and the theme recolour was deferred inside a double requestAnimationFrame so it never ran where frames are throttled.
- remaining: The four engraved plates and the team lockup remain provisional. The logo asset is still absent, so two 404 requests per page load are expected until it is added. Live pointer motion could not be observed in the preview pane because it holds the document hidden and starves requestAnimationFrame; interaction was verified by forcing synchronous repaints instead. Other browsers, screen readers and keyboard traversal are unverified. No Git writes ran.

<a id="ac-20260903-021"></a>
## AC-20260903-021 — Repalette the public site to black, silver and sky blue, and deepen the glass
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: none
- tags: ui, public-site, palette, glassmorphism, accessibility
- aliases: silver sky blue palette, amber removed, glass recipe, backdrop saturate, colour discipline
- paths: frontend/design/site.css, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Replaced the amber-accented palette with black, silver and sky blue after the requester rejected it, and rebuilt the glass treatment with a gradient fill, saturation lift, inset highlight and depth shadow.
- changes: Measured the reference implementation’s live colours and custom properties rather than estimating, then rebuilt both theme token blocks around a near-black ground, a cooler blue-black panel ground, four silver text tiers and a sky-blue accent. Applied colour discipline: sky blue carries every accent, green is limited to the enforced state, and orange is reserved for the team mark. Recoloured the helmet plate embers, the grain particles and the card hover glow from amber to sky blue. Replaced the flat glass with a shared recipe combining a gradient fill, blur with a saturation lift, an inset top highlight and an outer depth shadow, with a separate light-theme variant.
- verification: Swept 268 text-bearing elements for contrast in both themes with every panel unhidden; zero failures, minimum 5.37:1 dark and 4.70:1 light. Confirmed the glass computes the intended gradient, blur and shadow stack in both themes, and that both themes render correctly. One regression was introduced and fixed during this change: a global sed intended to remove duplicated panel backgrounds also stripped the fill from the buttons, nav chip, theme toggle and file rows, leaving the theme toggle on the browser default grey at 2.44:1; all four were restored and re-verified.
- remaining: The Rokunin Sync mark stays brand orange against the new blue and silver, which is a deliberate single-accent choice the requester may want revisited. The four engraved plates and the team lockup remain provisional, and the logo asset is still absent so two 404 requests per page load persist. The application surfaces keep their separate instrument palette and were not touched. No Git writes ran.

<a id="ac-20260903-022"></a>
## AC-20260903-022 — Replace the hero plate with the supplied video clip
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: none
- tags: ui, public-site, media, assets, repo-size, accessibility
- aliases: hero video, hero-loop.mp4, poster frame, screen blend, helmet removed
- paths: frontend/design/assets/hero-loop.mp4, frontend/design/assets/hero-poster.jpg, frontend/design/assets/README.md, frontend/design/site.css, frontend/design/site.html, agent-memory/agentchangelog.md
- summary: Replaced the engraved Corinthian-helmet plate in the hero with the supplied 15 MB video clip, circularly masked and blended into the page, with a still captured from the clip as its fallback.
- changes: Copied the supplied clip to assets/hero-loop.mp4 and removed the helmet plate markup from the hero, cutting about 15 KB of inline SVG. Added a square media container with the clip absolutely positioned inside a circular mask, cropped by object-fit, screen-blended so its black ground drops out, feathered at the edges by a radial mask and ringed by a hairline. The light theme inverts and multiplies instead, since a pale ground gives screen nothing to reveal. Captured a frame at 13.5 s from the running clip and saved it as assets/hero-poster.jpg, used as the video poster, the reduced-motion still and the fallback image. Added a mp4 and image mime map plus byte-range headers to the scratch dev server, and taught the artifact build to leave assets over an inline size cap as external references.
- verification: Confirmed the clip loads and plays with no media error, readyState 4, and that an explicit play call is not rejected. Fixed a layout defect found on first render: the clip is portrait 720x1280 and, as a flow child, its intrinsic height overrode the container aspect-ratio and stretched the hero box to 495x880; taking it out of flow restored a true 495x495 square. Confirmed both render paths - live clip visible with the still hidden, and, with the fallback forced, the still visible at the same size and blend, loaded at its natural 560x560. Confirmed both themes render correctly and that the artifact build inlines the poster while leaving the clip external.
- remaining: The clip is a 15 MB binary committed as an ordinary Git blob and needs a decision - Git LFS, exclusion plus deploy-time delivery, or re-encoding to a fraction of the size. No encoder was available locally to re-encode it. It cannot be inlined into a single-file artifact build, so artifact previews show the still frame and only a served copy animates. The team lockup asset is still absent. Documents, Code and Control Center surfaces remain unbuilt. No Git writes ran.

<a id="ac-20260903-023"></a>
## AC-20260903-023 — Transcode the hero clip so it plays, and enlarge the hero art
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: none
- tags: ui, public-site, media, performance, repo-size
- aliases: hero-loop.webm, mediarecorder transcode, vp9, hero sizing, blank space
- paths: frontend/design/assets/hero-loop.webm, frontend/design/assets/README.md, frontend/design/site.css, frontend/design/site.html, agent-memory/agentchangelog.md
- summary: Transcoded the 15 MB hero master to a 2.3 MB WebM so the clip plays in a single-file build instead of falling back to a still, and enlarged the hero art to close the empty space on the right.
- changes: With no encoder installed, produced the transcode in the browser - drew the master frame by frame into a 600x600 canvas, already centre-cropped to match how the page renders it, and captured 13 seconds from the 8 s mark with MediaRecorder at VP9 and 1.3 Mbps, saving the result through a dev-server write hook. Added the WebM as the first source ahead of the mp4, and taught the artifact build to inline video types under an 8 MB cap. Enlarged the hero art by giving the right column the larger grid share, letting the figure bleed past its column, and holding the circular mask solid to 63 percent before feathering rather than 52 percent.
- verification: Confirmed the page selects hero-loop.webm as currentSrc and plays it with no media error. Confirmed the artifact build inlines it, producing a 3.15 MB page against the 16 MB ceiling, where the previous build left the clip external and showed only the still. Art grew from 495 to 580 px square, 17 percent larger, and the container stays square. Two regressions were caught and fixed while sizing: the first bleed pushed 181 px of horizontal overflow, traced to the ray field scaling with the enlarged plate, and a narrower text column wrapped the call-to-action row onto two lines; after rebalancing, horizontal overflow measures zero, down from the 2 px that predated this change, and all three buttons sit on one row.
- remaining: The 15 MB mp4 master is now unused by every current browser but still committed as an ordinary Git blob, and should be excluded, moved to LFS, or dropped. The team lockup asset is still absent. Documents, Code and Control Center surfaces remain unbuilt. No Git writes ran.

<a id="ac-20260903-024"></a>
## AC-20260903-024 — Add the intro gate, swap the hero to the deity artwork, and replace grain with a network field
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: none
- tags: ui, public-site, media, motion, assets, layout
- aliases: intro gate, get started, glitch turbulence, deity reveal, network field, full width
- paths: frontend/design/assets/, frontend/design/site.css, frontend/design/site.html, agent-memory/agentchangelog.md
- summary: Replaced the hero clip with the supplied deity engraving, added a full-screen intro gate that plays the clip and hands off to the site through a glitch and a deity reveal, and swapped the grain background for a linked network field.
- changes: Widened the page from 1180 to 1560 px so content no longer sits in a narrow column. Removed the circular hero clip and its ray field, putting the supplied deity artwork in its place, pushed for contrast on the dark theme and inverted on the light one. Added an intro gate holding a native-resolution clip, the team mark top left, and a glass control bottom centre; the space either side of the portrait clip is filled by the network field. On activation the clip runs an SVG turbulence displacement with a slice-tear animation, then the deity fades in with two sky-blue eyes blinking on long offset cycles, holds two seconds, and withdraws to the left as the gate fades. Replaced the grain particle system with a network of drifting nodes linked to near neighbours, which the pointer attracts, brightens and links to directly. Derived a transparent PNG of the team mark by keying the black out of the supplied JPEG, so it needs no blend mode and works on both themes. Produced a native 720x1280 intro transcode at 3.6 MB by recording the video element stream directly.
- verification: Confirmed the gate sequences base to glitching to revealing to exiting to gone, that the eyes are positioned from the artwork box rather than the viewport so they stay on the face at any size, and that the deity artwork reads on black - measured at 52 percent light pixels and mean luminance 147 over its opaque area. Swept 267 text-bearing elements for contrast in both themes; zero failures, minimum 5.37:1 dark and 4.70:1 light, with no horizontal overflow. Confirmed the artifact build inlines six assets for an 8.63 MB page against the 16 MB ceiling. Two defects were found and fixed: the intro canvas collapsed to a canvas element’s intrinsic 300x150 because the centring grid stopped inset:0 from stretching an absolutely positioned child, and the footer mark still pointed at a PNG that did not exist.
- remaining: The 15 MB mp4 master is referenced only as a last-resort source and remains an ordinary Git blob needing exclusion, LFS or removal. Motion was verified by driving the sequence and holding states open, since the preview pane starves requestAnimationFrame while hidden. Documents, Code and Control Center surfaces remain unbuilt. No Git writes ran.

<a id="ac-20260903-025"></a>
## AC-20260903-025 — Silver mark with sheen, blindfold light rays, smoke, and intro performance work
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: none
- tags: ui, public-site, branding, motion, performance, media
- aliases: silver logo, sheen sweep, light rays, blindfold, smoke, get started button, canvas throttling
- paths: frontend/design/assets/, frontend/design/site.css, frontend/design/site.html, agent-memory/agentchangelog.md
- summary: Replaced the orange mark with the supplied silver one and gave it a swept highlight, rebuilt the entry control, turned the eye points into light escaping a blindfold, added smoke around the figure, and cut the animation cost that was making the intro stutter.
- changes: Derived a transparent PNG from the supplied silver JPEG by keying out the black and trimming the transparent margin, then added a highlight swept across a copy of the mark and masked to the mark’s own alpha, so it reads as light travelling over metal rather than a bar crossing a rectangle. Rebuilt the entry control: the arrow now points sideways in its own round well, the surface is a brighter glass with a hover highlight that crosses it, and nothing in the hover or active state touches position. Replaced the eye points with slits at the cloth line, each driving a masked cone of light up and down, sized in viewport units. Added two drifting smoke layers behind the figure for the hold. Cut animation cost three ways: only one network field runs at a time, links batch into two paths per frame instead of one stroke call per link, canvas density is capped at 1.25 and node count reduced.
- verification: Measured both video files before changing anything - each decodes at about 57 fps with zero dropped frames, so the reported stutter was the page rather than the clip, and the work went into animation cost instead of re-encoding. Benchmarked the link drawing at 0.50 ms per frame per canvas before and 0.05 ms after, with two canvases previously running at once. Confirmed the control holds position under hover, measured identical at x 607 y 766 before and after, and that its arrow path is horizontal. Confirmed the sheen animation is attached, the beams resolve to 185 px up and 141 px down against a 4 px slit, and the smoke layers render at 686 and 845 px. Swept 267 text elements in both themes: zero failures, 5.37:1 dark and 4.70:1 light, no horizontal overflow. Artifact builds to 8.45 MB against the 16 MB ceiling.
- remaining: The beams were first sized as a percentage of the slit and came out about 25 px long; they are now in viewport units. Bitrate hints are ignored when recording from a video element stream and the canvas route needs animation frames the preview pane does not provide, so the intro clip length remains the only reliable size control - it is a 12 s loop taken from the 31.5 s master. The 15 MB mp4 master is still an ordinary Git blob. Motion was verified by holding states open rather than by watching it run. No Git writes ran.

<a id="ac-20260903-026"></a>
## AC-20260903-026 — Fix the intro clip sizing and quality, retarget the exit, and set the wordmark in chrome
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: none
- tags: ui, public-site, media, layout, branding, motion
- aliases: intro video cropped, indefinite grid height, dvh sizing, exit right, chrome wordmark, deity glitch in
- paths: frontend/design/assets/intro.webm, frontend/design/site.css, frontend/design/site.html, agent-memory/agentchangelog.md
- summary: Found and fixed the intro clip overflowing its viewport, raised its encode bitrate, sent the figure right onto the hero artwork instead of off to the left, gave it a glitched entrance, and set the wordmark as chrome type.
- changes: The clip and the figure were sized with percentage heights inside a centring grid, where a centred item has an indefinite block size, so the percentage fell back to the media intrinsic height - a 1280px clip in a 1000px window, cropped top and bottom. Both now size in viewport units with dvh and a viewport max-width. Re-encoded the clip at 6.03 Mbps against the previous 2.33, at native 720x1280. The exit now measures the hero artwork box at run time and maps the figure onto it, so it travels right and settles where the page shows it rather than sliding off to the left. Added a torn, displaced entrance so the figure arrives the way the clip left instead of fading up still. Replaced the mark with the REFINIX wordmark set in Michroma under a brushed-chrome gradient with a sheen masked to the letterforms. Moved the artwork and the team lockup to single CSS custom properties so a single-file build inlines each once rather than per element, and taught the build to inline url() references in stylesheets.
- verification: Measured the clip before and after - 720x1280 in a 1000px viewport before, 563x1000 after, top at 0 and bottom at 1000, fully visible, height filled and aspect ratio correct to within 0.005. Confirmed the exit transform resolves to a positive x translation of 385px with a 1.041 scale onto a hero box 783px wide, and that the arrival animation is attached. Confirmed Michroma loads and the wordmark clips its gradient to text. Swept 267 text elements in both themes: zero failures, 5.37:1 dark and 4.70:1 light, no horizontal overflow. Artifact builds to 12.17 MB against the 16 MB ceiling, down from 13.42 MB before the single-inline change.
- remaining: The supplied REFINIX wordmark image could not be written to disk from the conversation, so it is set as type; a saved PNG can replace it. Bitrate remains only loosely controllable - the recorder overshoots the hint by roughly two times and the canvas route needs animation frames the preview pane does not provide, so duration stays the practical size lever. The 15 MB mp4 master is still an ordinary Git blob. No Git writes ran.

<a id="ac-20260903-027"></a>
## AC-20260903-027 — Play the master clip untouched, fix the page network field, add lightning and a breathing hero glow
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: none
- tags: ui, public-site, media, layout, motion, canvas
- aliases: master first source, replaced element intrinsic size, canvas 300x150, lightning, breathing glow, periodic glitch
- paths: frontend/design/site.css, frontend/design/site.html, agent-memory/agentchangelog.md
- summary: Stopped transcoding for served pages by putting the supplied master first in the source list, fixed the page network field being confined to a corner, and added lightning on the reveal plus a breathing glow and periodic tear on the page figure.
- changes: The clip had been re-encoded for every delivery, and each pass is a generation of loss; the master mp4 is now the first source so a served copy plays the supplied file untouched, with the WebM left as a fallback for single-file builds where the master cannot be inlined and the browser falls through on its own. Fixed the page network canvas: an absolutely positioned canvas is a replaced element, so width auto resolved to its intrinsic 300 by 150 rather than stretching to its insets, which confined the whole field to the top-left corner; it now sizes explicitly and a ResizeObserver rebuilds the buffer when the element changes size rather than relying on window resize alone. Added two offset full-bleed lightning flashes with an asymmetric rise and fall on the reveal. Wrapped the page figure so a sky-blue and a silver field breathe behind it on different periods. Added a short tear on the page figure every three seconds, driven by a class the script toggles so the gaps cost nothing.
- verification: Confirmed the page selects hero-loop.mp4 as currentSrc. Measured the page canvas before and after - 300 by 150 with drawing confined to that corner before, filling the viewport after, with drawn content spanning to 1575 of 1585 horizontally and 996 of 1000 vertically. Confirmed the periodic tear fires via a mutation observer over a 3.6 s window, and that both breathing animations are attached. Swept 267 text elements in both themes: zero failures, 5.37:1 dark and 4.70:1 light. Caught and fixed a 68 px horizontal overflow introduced by the glow reaching past the layout; overflow is back to zero. Artifact builds to 12.17 MB against the 16 MB ceiling.
- remaining: Artifact previews still fall back to the WebM, so only a served copy shows the master untouched. The supplied REFINIX wordmark image could not be written to disk from the conversation and remains set as type. The 15 MB master is still an ordinary Git blob. No Git writes ran.

<a id="ac-20260903-028"></a>
## AC-20260903-028 — Complete the application design: Documents, Code and Control Center
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: [UP-20260902-007](userprompts.md#up-20260902-007)
- tags: ui, application-surfaces, documents, code, control-center, evidence-semantics, accessibility
- aliases: chatbot ui complete, control center, shared app shell, co3 unblock, four surfaces
- paths: frontend/design/app.css, frontend/design/documents.css, frontend/design/documents.html, frontend/design/code.css, frontend/design/code.html, frontend/design/control.css, frontend/design/control.html, frontend/design/chat.css, frontend/design/chat.html, frontend/design/tokens.css, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Built the three missing application surfaces and extracted a shared shell, so the application design is complete and can be handed to the consumer waiting on it.
- changes: Verified first that only Chat existed and its three sibling links were dead. Extracted everything common to the four surfaces into app.css - the frame, surface nav, inspector rail, state chips, buttons, approval gate, artifact treatment and dense row tables - and reduced chat.css to Chat-only rules, so a surface file now carries only what is unique to it. Built Documents against the inspection_report_to_approval_note workflow, with source hashes, the seven-step pipeline showing which node ran each step, findings that always carry their page, an unresolved finding that keeps the extractor’s own words rather than inferring a value, section-level citations and an artifact validation record. Built Code against repository_request_to_validated_patch, showing the minimum file set rather than a repository transfer, the patch prepared in a temporary workspace, the sandbox run with command, exit status, stdout and an explicitly empty stderr, and the coordinator checks that run before approval is offered. Built Control Center covering all eight groups from workflows section 10, leading with runtime state, and carrying installation, models, agent profiles and self-test, jobs, paired devices with capabilities and revocation, resource meters, network evidence and audit with retention and export, plus an exportable Proof Card in the rail. Wired the four pages to link to each other.
- verification: Swept every text-bearing element on all four surfaces in three theme states - system dark, explicit dark and explicit light - 668 elements in total: zero failures and no horizontal overflow on any surface, worst ratio 4.53:1. Two token defects were found and fixed during the sweep: --st-fault measured 4.03:1 in dark where it carries failed chips and diff deletions, and --signal measured 4.49:1 on the sunken rail in light. Confirmed every surface link and stylesheet reference on every page resolves with status 200.
- remaining: First-run onboarding (workflows section 2) and the pairing exchange screens (section 8) are not built; Control Center shows pairing state and offers the controls but the invite, code exchange and confirmation screens do not exist. All four surfaces remain static references: they render fixed sample markup, are not wired to the coordinator and consume no event stream, and no value on them is a measurement. Fonts load from Google Fonts and must be self-hosted before any offline build. Screen readers, keyboard traversal order and other browsers are unverified. No Git writes ran.

<a id="ac-20260903-029"></a>
## AC-20260903-029 — Build the onboarding and pairing screens
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: none
- tags: ui, application-surfaces, onboarding, pairing, evidence-semantics, accessibility
- aliases: first run, five steps, no silent downloads, self-test, trust exchange, pairing code, workspaces not merged
- paths: frontend/design/onboarding.css, frontend/design/onboarding.html, frontend/design/onboarding-install.html, frontend/design/pairing.css, frontend/design/pairing.html, frontend/design/control.html, frontend/design/tokens.css, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Built first-run onboarding and the pairing exchange, the two screens the previous pass left out, and wired the Control Center entry points that had nowhere to go.
- changes: Built onboarding against workflows section 2, split across two pages so the stepper stays legible. Step 1 is reported rather than asked - there is no Create Workspace, Join, Coordinator, Worker or Server choice, because those are runtime responsibilities and not a setup question. Step 2 is the main engine picker, where every card carries source, licence, model and version id, download and installed size, quantisation, RAM and VRAM need, and runtime and OS, and every figure states whether it was measured on this device, only reported, or exceeds what this device has - so Fast and Quality read as guidance rather than as a promise. Step 3 turns each capability into its dependency plan and does not let one be skipped. Step 4 states every action, size, licence and checksum before anything is fetched, lists the permissions and data locations, and confirms in words what would have been unavailable had the install failed. Step 5 ships one capability failing: semantic knowledge is unavailable because the embedding model installed but no corpus path is configured, reported rather than hidden. Built pairing against section 8 as a dialog over a dimmed Control Center, since that is where it is reached from. It shows the short-lived single-use code, the two identities side by side so a person can compare fingerprints, a what-pairing-does list where the three things it does not do carry as much weight as the three it does, and node-04's advertised capabilities separated from what has actually been observed. Wired the four Control Center buttons - Change setup, Re-run self-test, Pair a device, Review and pair - which previously led nowhere.
- verification: Swept every text-bearing element on all seven application pages in three theme states at a 1440 by 900 viewport, 3,054 element checks in total: zero failures, worst ratio 4.53:1, which is the same --text-dim on --surface pair everywhere. Confirmed zero horizontal overflow on all seven at 375, 768, 1024 and 1440. Two contrast defects surfaced and were fixed: --st-unknown measured 4.43:1 on the light sunken ground, and --text-faint, which passes on --surface, fell to 4.06:1 on --surface-raised, which is what the model cards and the pairing identity cards sit on - the token was darkened and the two selectors moved up to --text-dim.
- remaining: Onboarding step 4 is drawn in its confirmed state, so there is no progress or failure view for a download that stalls. Pairing is drawn at step 3 of 5; revoke is offered from the Control Center but its confirmation is not drawn. All seven pages remain static references carrying sample data only - no figure is a measurement and the pairing code is not a credential - and none is wired to the contract in backend/contracts/v1.py. Fonts still load from Google Fonts and must be self-hosted before any offline build. Screen readers, keyboard traversal order and other browsers are unverified. A collapsed preview pane reports clientWidth 0, which makes an overflow check read as hundreds of pixels on a page that has none; overflow numbers are only trustworthy at an explicit viewport. No Git writes ran.

<a id="ac-20260903-030"></a>
## AC-20260903-030 — Retheme the application surfaces: silver, sky blue, black, scarce green, purple, and selective curves
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: none
- tags: ui, application-surfaces, palette, tokens, geometry, accessibility
- aliases: chatbot ui retheme, silver sky blue black, purple agent provenance, radius scale, curved edges, brand silver
- paths: frontend/design/tokens.css, frontend/design/app.css, frontend/design/chat.css, frontend/design/documents.css, frontend/design/code.css, frontend/design/control.css, frontend/design/onboarding.css, frontend/design/pairing.css, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Rebuilt the application palette around a near-black ground with silver type, sky blue, one green and one purple, and introduced a radius scale that curves what you touch while leaving readouts square. The public site was deliberately not touched.
- changes: Rebuilt tokens.css in both themes. Dark went to a near-black cool ground with silver type tiers; light went from warm grey-green to cool silver daylight. Sky blue replaced amber as --signal, so the live accent, focus ring, selection and running state all read blue. Green was pulled back to --st-enforced plus the completed marks on a plan, pipeline or job lifecycle, and nothing else. Added --agent and --agent-soft in purple with a single job: provenance, meaning this came from the local model's own reasoning. It marks the plan's left rail in Chat and the capability that ran each step in Chat and in the Documents pipeline, and it is never used for status - which is exactly why it cannot be confused with enforced, observed or unavailable. The node a step ran on stays silver, because that is routing, not authorship. --brand moved from orange to silver so the Rokunin mark sits inside the palette; it remains its own token used in two places, so recolouring the mark is a one-line change. Added a radius scale where none was used before - --radius had been declared and never applied, so every surface was square by omission. One rule decides where it lands: things you touch or talk to curve, things you read as a measurement stay square. Buttons, chips, bubbles, the composer, nav items, cards, panels and dialogs curve; dense claim tables, diffs, run output, meters and the artifact document do not, and --radius-data exists at 0px to make that deliberate rather than accidental. Where a curved container holds square rows the container carries the radius with overflow hidden, so a panel stops looking like a spreadsheet without the data losing its grid. Nav items became inset pills whose active marker is an inset box-shadow rather than a border-left, because a 2px border on a rounded box bows around the corner instead of reading as a straight bar. A chat turn now tightens the corner on the side it is anchored to. Corrected two colour misuses found while applying the rule: the pairing terms list marked what pairing does in green and what it does not do in fault red, so four rows that exist to reassure the reader were painted as errors - they are now the live accent and silver. The Code diff keeps conventional green and red for added and removed lines, and that exception is written into tokens.css rather than left as a silent contradiction.
- verification: Swept all seven application pages in three theme states at 1440 by 900, 3,054 element checks: zero contrast failures. The floor rose from 4.53:1 to 4.74:1 rather than costing contrast, because the new grounds are darker in dark and cooler in light while the type tiers held; Control Center, onboarding and pairing measure 5.01:1 and the install page 5.20:1. The purple was checked before it was used - 6.98:1 dark and 5.92:1 light on the grounds it lands on, at 10px where the 4.5:1 threshold applies with no large-text exemption. Confirmed zero horizontal overflow on all seven at 375, 768, 1024 and 1440, which the nav pill margin change could have broken and did not. Confirmed the pairing markers resolve to sky blue and silver rather than green and red. Confirmed site.html links only site.css and that site.css carries its own token block, so the public site is untouched by the retheme.
- remaining: The four earlier token contrast fixes are now structural rather than patched, but --text-faint on --surface-raised remains the tightest pair in the system and is the first thing to re-measure if surfaces are lightened again. The retheme is colour and geometry only: no page gained or lost content, and all seven remain static references carrying sample data, wired to nothing. Fonts still load from Google Fonts and must be self-hosted before any offline build. Screen readers, keyboard traversal order and other browsers are unverified. No Git writes ran.

<a id="ac-20260903-031"></a>
## AC-20260903-031 — Glassmorphism and deeper curves across the application surfaces
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: none
- tags: ui, application-surfaces, glassmorphism, geometry, tokens, accessibility, tooling
- aliases: glass morphism chatbot ui, oval curves, atmosphere fields, backdrop-filter, compositing contrast audit, scrim modal
- paths: frontend/design/tokens.css, frontend/design/app.css, frontend/design/chat.css, frontend/design/documents.css, frontend/design/code.css, frontend/design/control.css, frontend/design/onboarding.css, frontend/design/pairing.css, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Added a glass system to the application surfaces and enlarged the radius scale toward oval, keeping verbatim output and documents opaque and square. Rewrote the contrast auditor to composite translucent layers, which found two failures the previous one structurally could not see. The public site was again left untouched.
- changes: Enlarged the radius scale - 26px for dialogs and the largest panels, 18px for panels and cards, 13px for buttons and containers, 9px for nav items and tags, and a dedicated 20px for a chat turn, which is now the most oval thing in the app and tightens the corner on the side it is anchored to. Added a glass system. Glass only reads as glass when there is something behind it worth blurring, so the app now sits on three soft radial fields over the flat ground; without them every panel is flat translucent grey. The same distinction that governs curves governs glass: glass on the frame and on containers, opaque on verbatim output and on documents. The nav, rail, header, composer, panels, cards and dialogs are glass; the diff, the stdout and stderr panes, the meters, the artifact and the Proof Card are not, because those are read literally and refracted ground behind 11px monospace costs legibility for nothing. Two tiers for cost rather than looks: glass tokens carry the backdrop blur and belong to top-level surfaces, veil tokens are fill only for containers already sitting on a blurred parent, because blurring an already-blurred surface is expensive and shows almost nothing with a dozen panels on screen. Two structural changes were forced. The gap-of-1px-over-an-opaque-parent divider trick, used for the Documents sources and the onboarding plan totals, needs that parent opaque, which blocks everything behind it - both became separated cards with real gaps, which reads better anyway. And the light-mode atmosphere had to be rebuilt: dark tints at 10 percent over a light ground darken it, costing contrast for dark text, so the light fields are now near-white pastels that lift, and the light ground was deepened to D2D9E4 because near-white glass on a near-white ground collapses into a single tone and the panels stopped reading as panels.
- verification: Rewrote the contrast auditor, because glass broke the old one in a way that would have hidden failures rather than reported them: it walked up the ancestor chain until it found a background with alpha above .55 and used that, and with glass that colour is never what is on screen. The new auditor alpha-composites every layer from the root down including the strongest rgba stop of each gradient, and computes each ratio twice - once with gradient layers and once without, taking the lower - because a white-ish overlay lowers contrast for light text and raises it for dark text, so neither case is universally the worst. That found two genuine failures. The pairing dialog measured 3.48:1 in light, where a .55 white modal over a 62 percent black scrim composites to a muddy mid-tone; --glass-modal and --scrim are now their own tokens and it measures 6.33:1. The unavailable hatch measured 4.46:1 where --text-faint crosses --line-soft, which the old walk never saw because it stopped at the opaque row beneath; --line-soft was lightened in light so the hatch reads as a drawing mark rather than a bar. After both fixes: all seven pages, three theme states, 3,054 element checks, zero failures, floor 4.60:1. Confirmed zero horizontal overflow on all seven at 375, 768, 1024 and 1440, which the two layout changes could have broken and did not. Confirmed at runtime that none of the new tokens - glass-base, scrim, radius-bubble - resolve on site.html and that its ground is unchanged at rgb(9,9,10), so the public site is untouched.
- remaining: The glass floor of 4.60:1 is slightly below the 4.74:1 the palette pass reached; that is the honest number under a strictly compositing measurement rather than a regression in the design. backdrop-filter is applied to top-level surfaces only, but no frame-rate measurement was taken - the preview pane starves animation frames, so glass performance on a low-end GPU is unverified and is the first thing to check on real hardware. Browsers without backdrop-filter degrade to the flat translucent fill, which is legible but not glass; this was not tested anywhere but Chromium. All seven pages remain static references carrying sample data, wired to nothing. Fonts still load from Google Fonts. No Git writes ran.

<a id="ac-20260903-032"></a>
## AC-20260903-032 — Handover model and authorisation-scope amendment
- prompt_id: [UP-20260903-014](userprompts.md#up-20260903-014)
- date: 2026-09-03
- status: in review
- scope: documentation, execution, operating-contract
- tags: c03, operating-contract, handover, authorisation-scope
- aliases: handover pack, authorisation scope, reduce human intervention
- paths: tasks.md, AGENTS.md, docs/handover-pack.md, docs/README.md
- summary: Separated execution order from authorisation scope in the operating contract, stopped routine implementation questions being relayed as checkpoints, and added a one-time requester handover template.
- changes: Rewrote three operating-contract bullets in tasks.md so authorisation may cover a named chunk range while work still proceeds one chunk at a time after each acceptance gate clears, routine implementation questions resolved from repository evidence and upstream documentation are explicitly not checkpoints, and execution stops for exactly three things including missing authorisation. Recorded that repository evidence can answer a technical question but never grants permission, and that a supplied input removes the question but never the gate. Aligned the AGENTS.md human-checkpoint bullet. Added docs/handover-pack.md with settled decisions prefilled, pre-C03 items separated from C07-C13 items, an authorisation-sentence template, an agents-prepare-the-fixture option for the code demo, and confidential inputs directed to the git-ignored private/handover/. Linked it from docs/README.md.
- review_fixes: Codex returned NEEDS FIX with four findings; all four are addressed. Restored missing authorisation as a checkpoint in both the introduction and the copyable authorisation template, with a note not to delete that clause when copying. Gave provisioning constraints and device operating windows their real earliest-needed chunks, C04 and C05, instead of filing them under C11-C13, and added an earliest-needed column to the remaining rows. Removed an invented claim that scans and SOPs must be publicly redistributable: security.md section 11 actually requires synthetic or explicitly approved non-sensitive fixtures, and C07 separately requires source hashes and provenance. Corrected the contract row from frozen to reviewed draft, not frozen, integration pending C05. Also recorded that ignore rules are a safety net rather than a guarantee, since git add -f bypasses them.
- verification: Confirmed private/handover/, scans/, secrets/ and .env are ignored using git check-ignore, while recording that a forced add bypasses ignore rules. Prefilled values were read from the current source rather than retyped: the OD-08 pins from architecture.md, the model tag from model-catalog.md and ports 8443/30443 from backend/contracts/v1.py. Checked every internal Markdown link and anchor across the repository and git diff --check.
- remaining: Codex review of the combined diff, then requester acceptance. The three C03 gates are unchanged and uncleared: the Ubuntu *:8080 identification, C02 acceptance, and explicit C03 authorisation. No handover inputs have been supplied yet, no code was written and no Git writes ran.

<a id="ac-20260903-033"></a>
## AC-20260903-033 — Resolve the remaining handover review findings
- prompt_id: [UP-20260903-015](userprompts.md#up-20260903-015)
- date: 2026-09-03
- status: in review
- scope: documentation
- tags: handover, fixtures, c07, review-fixes
- aliases: residual fixture requirement, code fixture timing, handover pack corrections
- paths: docs/handover-pack.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Removed the residual public-redistribution requirement and moved Code-fixture preparation to its C07 approval checkpoint.
- changes: Both Documents rows now use the repository's synthetic-or-approved-non-sensitive fixture policy and require provenance and SHA-256; the Code-fixture heading now says it is needed at C07 and exercised in C09.
- verification: `git diff --check` passed; the handover file has no trailing whitespace; focused searches confirmed both fixture rows, the C07/C09 heading and their agreement with security.md and tasks.md.
- remaining: Requester verification and Git publication remain human actions. C03 was not started and its three gates remain uncleared.

<a id="ac-20260903-034"></a>
## AC-20260903-034 — Unify the intro screen, retime the reveal, and make the page glitch pixel-based
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: none
- tags: ui, public-site, motion, media, intro-gate, accessibility
- aliases: ambient wash, video gutters, one colour screen, 1.3 second hold, rays cancelled, pixel glitch, block displacement
- paths: frontend/design/site.css, frontend/design/site.html, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Filled the intro's side gutters with the clip's own colour so the screen reads as one surface, shortened the figure's hold to 1.3s and made the rays and lightning end with it, and replaced the page figure's slice tear with a block-displacement pixel glitch.
- changes: The clip is portrait in a landscape window, so the gutters sat flat black against a lit frame and the whole screen read as a video dropped into a hole. Added an ambient wash: a 40x72 canvas takes a downscaled copy of the current frame ten times a second and is stretched and blurred across the viewport behind the network field, so the horizontal stretch drags the frame's own edge colour outward to meet the window. A short feather on the clip's vertical edges removes the last hard line. Ten samples a second costs nothing next to decoding the clip a second time, which is the obvious alternative and far more expensive; the network field is untouched and still runs over the top. Shortened the figure's hold from 2s to 1.3s before it travels right onto its place in the page. Fixed the rays and the lightning outliving the exit: an animated property beats a plain declaration in the cascade, so the existing exit rule setting opacity to 0 never won and the rays kept firing through the exit and the fade after it - the figure had gone and the light stayed. Both now carry animation none with important on exit, the blink cycle was shortened from 3.2s to 1.15s so a full blink lands inside the shorter hold instead of being cut off part way, and both lightning strikes were retimed to finish at 1.2s, inside the hold rather than trailing past it. Replaced the page figure's periodic tear with a pixel glitch. The new #pixglitch filter quantises its turbulence with discrete transfer functions, so the image is displaced in flat blocks and breaks up like failing pixels; the previous version stacked clip-path bands, which slide whole horizontal strips and read as a film tear rather than a digital one. Three things stack to sell it: the block displacement, a red and cyan channel split carried in the same filter, and a stepped jitter so the figure snaps between positions instead of sliding, with a fine line mask dropping out thin runs of pixels. The SVG animation is restarted with beginElement on each burst, or the pattern would freeze and every burst would break up identically. A light-theme variant keeps the inversion through the burst.
- verification: Instrumented the sequence with a mutation observer and 60ms opacity sampling: video glitch 0 to 1005ms, figure holds 1005 to 2308ms which is 1303ms against the 1300ms target, rays alive 1020 to 2282ms then animation none and opacity 0 at the first sample after the exit begins, both lightning strikes complete by 1801ms well inside the hold. Confirmed the ambient canvas is fed - 2161 of 2880 pixels carrying frame colour, the 720x1280 master playing, and no canvas tainting. Confirmed the periodic burst fires on schedule by polling at 50ms over 8 seconds, after a mutation-observer check gave a false negative. Confirmed the light-theme variant resolves to pixjolt-light with the inversion retained. Swept the site with the compositing auditor in both themes, 184 elements each: this found two pre-existing failures the older ancestor-walk auditor could not see - --accent at 4.14:1 on a light glass panel and --ink-faint at 4.18:1 on the artifact's raised ground, neither related to this work - and after raising both tokens the site measures zero failures, 4.87:1 light and 5.03:1 dark, with no horizontal overflow and no console errors.
- remaining: The ambient wash samples on a 100ms timer rather than requestVideoFrameCallback, so on a stalled decode it repeats the last frame rather than stopping; harmless, but rVFC would be tidier where supported. Frame rate during the burst was not measured - the preview pane starves animation frames - so the filter's cost on a low-end GPU is unverified, and the block glitch is a heavier filter than the tear it replaced. Only Chromium was tested; a browser without SVG filter support drops to an unfiltered jitter. The clip and the artwork remain placeholders. No Git writes ran.

<a id="ac-20260903-035"></a>
## AC-20260903-035 — Remove the sample strip, close the page rhythm, and apply the reviewed copy edits
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: none
- tags: ui, public-site, copy, spacing, layout, evidence-semantics
- aliases: sample strip removed, blank space, section rhythm, scroll padding, hero copy, VRAM line, attempt 1 of 3
- paths: frontend/design/site.html, frontend/design/site.css, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Removed the top sample-content strip and closed the section rhythm that made the page read as mostly empty, and applied a reviewed set of copy edits after checking each factual claim against the docs - two of which did not hold.
- changes: Removed the sample-content strip and its rule. The substantive disclosure is unaffected: the No public release yet paragraph still sits in the download section where a visitor is actually deciding something, and the nav still carries a Pre-release chip above the fold. Tightened the page rhythm. Section spacing is one token and every section pays it on the bottom only, with subsequent sections carrying padding-top zero inline; #proof and .closing had both been missed, so those junctions were double - 260px and 156px against a 130px rhythm, which is most of what read as empty page. The token went from clamp(76px, 9vw, 148px) to clamp(52px, 5.4vw, 92px), the formula band's own padding came down with it, and both double junctions were closed, taking the document from 8187px to 7538px at 1440 with the rhythm now an even 78 to 105px throughout. Added scroll-padding-top, because the nav is sticky at top zero and without it every in-page anchor landed with its own heading hidden behind the bar. Copy: the hero lede now says running entirely on hardware inside your perimeter rather than hardware you already own, which drops a presumption about the reader, and a live counter at zero rather than a counter you can read, which makes the metaphor concrete. The first stat became 2 execution targets without leaving your policy boundary, this device or a trusted paired device - a real count from workflows.md section 9 - replacing 1 machine is a complete installation, which was not a count. Added an 8 GB VRAM recommendation to the Windows and Linux cards so a visitor can self-assess against the figure every model is quantised for.
- verification: Checked the three factual claims the review flagged rather than taking them on trust, and two failed. The site said the sandbox runs with networking switched off; security.md line 227 says networking disabled, so the site was aligned to the document's wording. The Chat mockup showed Attempt 1 of 3, but workflows.md line 268 says only bounded retry options and the contract carries retryable and retry_of with no maximum anywhere - the ceiling was invented, so the number came out rather than inventing a matching policy in the docs. The third held: refinix verify --manifest renders at 412px inside a 522px box and is not truncated. The 8 GB VRAM figure is the top of the fleet in devicespecifications.md and Q4 quantisation is confirmed in model-catalog.md, though the fleet's top VRAM is recorded there as historical rather than reconfirmed, and 6 GB is the highest currently measured. Swept the site in both themes after the changes, 195 elements each: zero contrast failures, 4.87:1 light and 5.03:1 dark. Confirmed no page-level horizontal overflow at 768, 1024, 1440 and 1920, and at the narrowest width the pane will emulate: the one element extending past the viewport is a span inside a terminal block with overflow-x auto, and document.body.scrollWidth minus the layout viewport is zero, so it scrolls inside its own box as intended.
- remaining: The pane reports clientWidth 400 while innerWidth is 470 at narrow settings and refuses to emulate below that, so true mobile widths are still unverified by direct measurement. It also will not paint below the fold, so the tightened rhythm was confirmed by measuring landmark-to-landmark gaps rather than by looking at the scrolled page. The band's removal moves all pre-release signalling below the fold except the nav chip; if the download-section disclosure is ever softened, the strip should come back. No Git writes ran.

<a id="ac-20260903-036"></a>
## AC-20260903-036 — Fit the hero to one screen, reorder the page, set the formula in a pixel face, and wire two brand lockups
- date: 2026-09-03
- agent: Claude
- status: partial
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: none
- tags: ui, public-site, layout, typography, branding, information-architecture
- aliases: hero one screen, deity resize, verify box above the fold, section reorder, pixel font, minecraft font, brand lockups, logo fallback
- paths: frontend/design/site.html, frontend/design/site.css, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Sized the hero so the terminal card and the whole figure land above the fold, reordered the page with download directly under the formula band, set the formula line in a pixel face and halved its padding, and wired both supplied brand lockups behind a fallback because the image files could not be written from the conversation.
- changes: The hero is now sized from the viewport rather than its content, at 100svh minus the nav. The two things that overflowed are capped by viewport height and not only width: the headline moved to clamp(2.4rem, min(6.6vw, 8.6vh), 6.2rem), because a width-only clamp gave 99px on a 900px-tall window and pushed the terminal card off the bottom, and the figure is now sized from its height on .hero-plate rather than .hero-art - the plate is what carries the breathing fields as pseudo-elements, so sizing the art alone would have left the glow at the old scale. A width-driven box had made the figure 873px tall inside an 836px window. Hero padding came down from 72/78 to about 28 each. Below max-height 800px and max-width 1200px the one-screen constraint is released, because there is genuinely not enough room for headline, lede, actions, terminal card and a portrait figure at once on a short small screen. Reordered the page to the owner's sequence: hero, formula, download, design approach, product, what it does, the evidence rule, counts, closing - which also means the pre-release disclosure now appears before the page describes anything, since it lives in the download section. The section that leads the sequence takes the top padding and every other one keeps padding-top zero, so the download section gave up its inline zero and the evidence rule gained one. The formula line is set in Pixelify Sans with its tracking cut from .22em to .06em, because a pixel face carries its own spacing and the extra letter-spacing pulled the words apart, and the band's padding was roughly halved. Wired both supplied lockups: horizontal in the nav where the bar is short and wide, stacked on the intro gate which is a full screen with room above and below.
- verification: Measured the hero at 1440x900 before and after: 1023px tall against an 836px window with the terminal card's bottom at 967 and the figure 873px tall, versus 836px, the figure fully visible from 120 to 880, and the terminal card ending at 838. Confirmed the same fit at 1366x768, 1536x864 and 1920x1080. Confirmed Pixelify Sans actually loads rather than silently falling back. Confirmed the section order renders as hero, formula, get, statement, surfaces, work, proof, stats, closing. Swept both themes, 195 elements each: zero contrast failures, 4.87:1 light and 5.03:1 dark. Apparent horizontal overflow of 11px at 1024 and 41px at 768 was checked directly and is the vertical scrollbar skewing clientWidth again - zero elements extend past the layout viewport and document.body.scrollWidth minus the viewport is negative at both.
- remaining: STATUS PARTIAL because the two supplied logo images could not be written to disk from the conversation, which is the same limitation hit with the wordmark earlier. The markup, sizing and fallback are all in place and reference assets/refinix-lockup-h.png and assets/refinix-lockup-v.png; until those files exist each img removes itself on error and a :has() rule reveals the type wordmark underneath, so the page renders correctly but still shows the old type lockup rather than the supplied artwork. The owner needs to save both attachments to those paths. Pixelify Sans is the closest modern pixel face on Google Fonts; Silkscreen is the nearer match to Minecraft's own bitmap and is already the first fallback if a swap is wanted. The evidence rule section landed after the four the owner listed because they did not place it; it is a one-block move if that is wrong. No Git writes ran.

<a id="ac-20260903-037"></a>
## AC-20260903-037 — Remove the download section, extend the evidence rule in a pixel face, and replace the owl with a supplied clip
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-013](userprompts.md#up-20260903-013)
- related_prompts: none
- tags: ui, public-site, information-architecture, typography, media, copy
- aliases: get started removed, download section removed, pre-release disclosure moved, pixel font evidence rule, owl replaced, evidence clip, no transcode
- paths: frontend/design/site.html, frontend/design/site.css, frontend/design/assets/evidence-loop.mp4, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Removed the download section while preserving the disclosure it carried and the anchor four links depended on, extended the evidence rule and set the whole section in the pixel face, and replaced the drawn owl with the supplied clip copied byte-for-byte.
- changes: Removed the Get started section entirely, and handled two things it took with it rather than letting them break. The No public release yet paragraph was the page's only substantive pre-release statement once the top strip went, and it lived inside that section - it now opens the closing section, reworded, because the old text pointed at builds below that no longer exist. Four links pointed at the removed id (nav, hero CTA, closing CTA, footer), so the closing section took id="get" and all four still resolve, landing on the section that states no build exists. The section that now leads the middle took its top padding back. Extended the evidence rule with two paragraphs drawn from security.md section 12 rather than invented, leaving the existing opening untouched because it is the strongest paragraph on the page. Set the whole section - label, heading, body and all three claim cards - in Pixelify Sans, with sizes larger and line-height looser than the rest of the page, because a pixel face has a small x-height and at the page's normal scale reads markedly harder than the prose around it. Replaced the drawn Athenian owl with the supplied motion clip, copied into assets byte-for-byte with no transcode, paused while off screen by an IntersectionObserver because the page can have two clips alive at once and decoding both is what costs frames, and given controls rather than autoplay under prefers-reduced-motion.
- verification: Confirmed the copied clip is byte-identical to the source with cmp, so there is no transcode and no generation of loss; it reports 720x720, readyState 4 and 16.67s, plays from evidence-loop.mp4 and its currentTime advances. Confirmed zero dead anchors on the page after the section removal, that the closing section carries id="get", and that the notice moved rather than vanished. Confirmed the claim cards actually took the pixel face after the first selector attempt targeted .card rather than the real .claim class and silently missed. Swept both themes, 161 elements each: zero contrast failures, 4.87:1 light and 5.03:1 dark. Zero elements past the layout viewport at 768, 1024, 1366 and 1440, and the hero's terminal card still lands above the fold at 1366x768. Document height fell from 7310px to 6085px.
- remaining: The evidence rule is now the one section on the site set in a display face at body sizes; it passes contrast, but it is the first place to look if a legibility complaint arrives, and reverting is a single selector block. The clip's own frame rate was not measured - no ffprobe on this machine and the preview pane starves animation frames - so smoothness on real hardware is unverified, though nothing in the pipeline re-encodes it. The two brand lockup images are still not on disk, so the nav and intro still show the type fallback. No Git writes ran.

<a id="ac-20260904-001"></a>
## AC-20260904-001 — C03 local application implemented
- prompt_id: [UP-20260904-001](userprompts.md#up-20260904-001)
- date: 2026-09-04
- status: in review
- scope: implementation, coordinator, frontend, execution
- tags: c03, af-004, coordinator, sqlite, ollama, restart-reconciliation
- aliases: build local application, c03 chat control center, coordinator sqlite streaming
- paths: backend/coordinator/, frontend/app/, tasks.md, docs/architecture.md, frontend/README.md, agent-memory/
- summary: Implemented the smallest usable local application — contract-validated SQLite state, local Ollama streaming, restart reconciliation, cancellation, and Chat plus a minimum Control Center on plain HTML/CSS/JS.
- changes: Added backend/coordinator with db.py, runtime.py, server.py, __main__.py, README.md and 12 offline checks. Every Job, Attempt and Event is constructed and validated through backend.contracts.v1 before it is written, and state changes go through require_transition, so an illegal transition raises instead of persisting. Added frontend/app with application-owned HTML, CSS and JavaScript reusing the design's class vocabulary; the stylesheet is derived from the design tokens with no external font, and frontend/design/ is untouched and never served or linked. Documents and Code render unavailable, and workers, cluster, approvals, Proof Cards and egress each name the chunk that produces their evidence. Recorded the standard-library deviation from the FastAPI direction in architecture.md, since FastAPI is not installed and adding it is a setup checkpoint; FastAPI remains the C04 worker-API direction. Updated the board with the Jenkins identification, the two Ubuntu Docker endpoints and the different-subnet finding.
- verification: Ran on the macOS coordinator against the loopback Ollama server. A real request returned "The capital of France is Paris." with the full contract-legal sequence of 18 events and runtime 3503 ms. SIGKILL during generation then restart repaired the job: job and attempt both interrupted with a typed internal_error reason, 320 characters of partial output and all conversation history retained, events continuing at sequence 69 without a gap. Cancellation produced cancelled_by_user, kept 334 partial characters and wrote no assistant message. lsof showed 127.0.0.1:8770 only. In the browser both surfaces rendered real observed values, streaming worked through the UI, the Enter key submitted, zero elements were clipped and all six resource requests went to loopback. 12 coordinator checks and the 8 existing contract checks pass.
- acceptance_fixes: The requester's acceptance run found two defects, both fixed. Ctrl+C did not stop the coordinator: the SSE handler looped with no exit path, so server_close() waited on a thread that never returned. A stopping event with a one-second poll releases it, and block_on_close is disabled; isolating the variable showed block_on_close alone was not the cause, so the initial diagnosis was corrected. The interface was too busy: model output now renders as Markdown built from DOM nodes rather than showing raw asterisks and hashes, output deltas collapse from one row per token into a single rolling counter, the evidence panel became a collapsed disclosure, and event labels no longer wrap mid-word. Recorded events now replay when a conversation loads, so the rail no longer looks as though nothing happened.
- remaining: Codex review and the macOS coordinator acceptance run — real prompt, streaming response, restart, retained history. Browser observation of loopback requests is not zero-egress evidence, which needs C11 controls and independent observation. No worker, pairing, cluster, Documents, Code, approvals or Proof Cards exist. AF-001 stays a draft until C05. The Ubuntu 8080 wildcard exposure review and the different-subnet routing question remain open. No Git writes ran.

<a id="ac-20260904-002"></a>
## AC-20260904-002 — Repair C03 and require the third OCR device
- prompt_id: [UP-20260904-002](userprompts.md#up-20260904-002)
- date: 2026-09-04
- status: in review
- scope: coordinator, review-fixes, device-qualification, execution
- tags: three-devices, ocr, c03, concurrency, restart, local-api
- aliases: Yug OCR worker, event replay, local boundary, persisted node identity
- paths: backend/coordinator/, frontend/app/app.js, scripts/qualify-ocr-worker.ps1, tasks.md, docs/devicespecifications.md, docs/handover-pack.md, agent-memory/
- summary: Repaired C03 and changed the execution board to require a separate Windows OCR worker before the internal demo.
- changes: Serialized SQLite access, repaired every unfinished job after a crash, persisted node identity, rejected overlapping chat requests, closed the late-cancel write race, bounded and same-origin checked local HTTP, disabled Ollama proxies/redirects, and recovered UI output/events missed before POST or during reconnect. Selected the inventoried Windows HP Victus for OCR, required qualification at C07 and real remote OCR at C08, and added one later read-only PowerShell packet.
- verification: 29 coordinator/contract checks passed; JavaScript syntax and diff whitespace checks passed. An isolated browser run returned `local check passed` from loopback Ollama in 583 ms, rendered the lifecycle, stopped, restarted with the same node ID, and restored the prompt and answer. The existing port-8770 process and state were untouched.
- remaining: Restart and accept the repaired source on the macOS coordinator, then implement/build C04 on Ubuntu. Windows qualification, OCR setup, pairing and real OCR remain C07-C08 gates. No Git writes ran.

<a id="ac-20260904-003"></a>
## AC-20260904-003 — Restore two-device scope and prepare C04 image inputs
- prompt_id: [UP-20260904-003](userprompts.md#up-20260904-003)
- date: 2026-09-04
- status: in review
- scope: documentation, build-preparation, execution
- tags: two-devices, ocr, c04, deadline, scope-correction
- aliases: deferred Windows qualification, September 8-9 demo, worker-base image inputs
- paths: tasks.md, docs/devicespecifications.md, docs/handover-pack.md, scripts/qualify-ocr-worker.ps1, backend/worker-image/, agent-memory/
- summary: Restored the two-device critical path, retained the C03 repairs, and prepared pinned Linux image inputs and a combined Git handoff.
- changes: Removed mandatory Windows execution and C07 qualification; restored C08 OCR to Mac/Ubuntu; marked the retained PowerShell packet deferred. Recorded 8-9 September as the internal demo window with sequential targets and slip risks. Added a digest-pinned Python base, thirteen hash-pinned wheels, provenance, restrictive Docker context and gated Ubuntu commands. The preparation image exports contracts; the worker API remains unimplemented.
- verification: Re-read and hash-matched the pinned Docker Hub base manifest; checked PyPI versions, licences, wheel hashes and dependency closure for Python 3.13/Linux against existing contract pins. Offline validation passed for all build paths and all 12 C03 source hashes remained unchanged; no application tests were rerun for this documentation/build-input change.
- remaining: Requester C03 acceptance, then C04 worker implementation, actual image build and manifest-digest evidence. No image, wheel, installer or model was downloaded; registry metadata only. No service or Git writes ran.

<a id="ac-20260904-004"></a>
## AC-20260904-004 — Repair reply limits and browser disconnect handling
- prompt_id: [UP-20260904-004](userprompts.md#up-20260904-004)
- date: 2026-09-04
- status: in review
- tags: c03, truncation, output-limit, browser-disconnect, migration
- aliases: completed normally, 2048 tokens, incomplete reply, connection reset by peer
- paths: backend/coordinator/db.py, backend/coordinator/runtime.py, backend/coordinator/server.py, backend/coordinator/test_coordinator.py, backend/coordinator/README.md, frontend/app/app.js, docs/model-catalog.md, docs/handover-pack.md, tasks.md, agent-memory/
- summary: Raised C03 replies to 2048 tokens and made capped output, stopping evidence and expected browser disconnects truthful.
- changes: Added nullable attempt metrics with an additive history-preserving upgrade; only stop completes, length fails validation with retained annotated text usable for continuation, and unknown reasons stay unverified. The HTTP connection boundary handles reset/broken-pipe exceptions while SSE always unsubscribes and other errors remain visible. Updated the model settings and manual handoff.
- verification: 33 coordinator/contract checks, JavaScript syntax and diff whitespace passed. A temporary Mac instance produced a real 664-token reply ending in stop in 22735 ms, displayed limit 2048, and retained text/metrics and node identity after restart. The browser rendered a separate synthetic length fixture with its incomplete notice. The temporary instance and tab were closed.
- remaining: Restart and accept the repaired normal Mac app before C04. Existing port-8770 process/history were untouched; real response content was not quality-validated. No installs, model downloads or Git writes ran.

<a id="ac-20260904-005"></a>
## AC-20260904-005 — Prepare inspected context and UI execution brief
- prompt_id: [UP-20260904-005](userprompts.md#up-20260904-005)
- date: 2026-09-04
- status: prepared
- tags: c03, build-brief, context-window, kv-cache, ui, ux
- aliases: Claude build update, semantic output colours, synthetic UI fixture
- paths: docs/c03-context-ui-build-brief.md, docs/handover-pack.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Prepared Claude's requested build brief after inspecting live Chat, Control Center and current context/rendering source.
- changes: Specified bounded context selection and overflow evidence, distinct history/cache/residency concepts, conditional Mac context measurement, typography/alignment/responsive fixes, semantic colours, safe Markdown, interaction repairs, a synthetic fixture payload and acceptance checks.
- verification: Read live browser state and screenshots; confirmed active-selector mismatch, hidden responsive controls, renderer limits, forced scrolling and draft-clearing behavior from source. The live process reported 512 output tokens while source specifies 2048. Checked brief whitespace, code fences, required scope and referenced implementation paths; diff whitespace passed.
- remaining: Claude implements and verifies the brief, followed by Codex review and requester C03 acceptance. No application code, live history, runtime configuration or Git state was changed; no application tests were run for this documentation deliverable.

<a id="ac-20260904-006"></a>
## AC-20260904-006 — Add Delete chat to Claude's UI scope
- prompt_id: [UP-20260904-006](userprompts.md#up-20260904-006)
- date: 2026-09-04
- status: prepared
- tags: c03, ui, delete-chat, build-brief
- aliases: delete convo, confirmed deletion, conversation menu
- paths: docs/c03-context-ui-build-brief.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Added confirmed per-conversation deletion, backend concurrency requirements and fixture coverage to the execution brief.
- changes: Specified an accessible menu, titled confirmation, unfinished-work guard, atomic scoped record deletion, failure/empty states and disposable-data checks.
- verification: Reviewed current retention/deletion guidance; brief whitespace, code fences and deletion requirements checked; diff whitespace passed.
- remaining: Claude implementation and verification. No application code or user chat data changed; no application tests or Git writes ran.

<a id="ac-20260904-007"></a>
## AC-20260904-007 — Add five conversation-management features to the brief
- prompt_id: [UP-20260904-007](userprompts.md#up-20260904-007)
- date: 2026-09-04
- status: prepared
- tags: c03, build-brief, rename, search, drafts, pin, export
- aliases: simple chat management, exclude regeneration, one build pass
- paths: docs/c03-context-ui-build-brief.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Extended Claude's existing execution brief with rename, local search, draft recovery, pinning and export, explicitly excluding regeneration.
- changes: Defined small local implementations, persistence and deletion interactions, fixture states and focused verification; retained Continue as a separate follow-up action.
- verification: Checked the current chat schema/read paths, all five requested requirements, the regeneration exclusion, Markdown fixture fences and whitespace; diff whitespace passed.
- remaining: Claude implementation and verification. Only documentation changed; no application tests, live data changes or Git writes ran.

<a id="ac-20260904-002"></a>
## AC-20260904-002 — Context selection, Markdown renderer and interface rebuild
- prompt_id: [UP-20260904-002](userprompts.md#up-20260904-002)
- date: 2026-09-04
- status: in review
- scope: implementation, coordinator, frontend, context-window
- tags: c03, context-window, markdown, accessibility, responsive
- aliases: context selection, markdown renderer, ui fixture, 8192 context
- paths: backend/coordinator/context.py, backend/coordinator/test_context.py, backend/coordinator/{db,runtime,server,test_coordinator}.py, frontend/app/, docs/evaluation.md, docs/model-catalog.md
- summary: Added bounded context selection with recorded per-attempt metadata, adopted a measured 8192 window on the Mac, replaced the ad-hoc Markdown handling with a real tokenizer, and rebuilt typography, drawers and interaction safety.
- changes: New context.py selects a bounded request from saved history in complete exchanges, never orphaning an assistant reply, keeping the newest message intact, and reporting rather than chopping an oversized one. The selection persists on the attempt through a new selection_json column with an additive migration, so a reopened job shows the policy that ran then. Adopted num_ctx 8192 on the coordinator from measurement. Captured runtime-reported prompt tokens separately from the character estimate. Added markdown.js, a block-then-inline tokenizer built entirely from DOM nodes: raw HTML stays inert, javascript and data URLs are shown but never clickable, safe links carry noopener/noreferrer/nofollow and display their host, and code blocks carry a language label and a copy button that copies literal source. Rebuilt overrides.css with a 76ch reading column, 16px prose, semantic prose colours separate from operational state colours, and drawers so navigation and details stay reachable below 1180px and 760px. Fixed the aria-current mismatch, preserved drafts on failed submission, blocked duplicate sends, guarded IME composition, and made streaming follow the bottom only when the reader is already there with a Jump to latest control otherwise. Added fixture.html/fixture.js as a labelled synthetic fixture covering rich content and eight deterministic states.
- verification: 46 offline checks pass, including 12 new context checks covering budget arithmetic, oldest-first omission, orphan prevention, exact boundary, dense scripts, oversized newest input and replayable metadata. Measured 4096 against 8192 on the coordinator: +220 MiB resident, warm TTFT 0.196 s to 0.203 s, early fact retrieved at 3052 prompt tokens. A seven-turn real conversation drove estimated input to 5132 of 5168 then into omission at turns 6 and 7; saved history stayed 16 messages and the model said it no longer had an omitted fact instead of inventing one. In the browser at 1440, 1024 and 390 px: no horizontal overflow, no clipped controls, navigation and details reachable at every width, drawer opens on click and closes on Escape, zero external requests, and the fixture confirmed inert raw HTML, blocked unsafe schemes, 3 code blocks, 2 tables, 4 nested lists and an unfinished fence.
- remaining: Codex review and the macOS coordinator acceptance run. Two defects were found and fixed during this work: a base display rule ordered after its media query left the menu control unreachable at 390 px, and a closing script tag inside an inline fixture literal terminated the script and executed an alert, which is why the fixture is now a module file. The character estimate runs about 1.8x conservative against measured prompt counts. Ubuntu keeps 4096 until its own measurement. Browser request checks are not the C11 zero-egress gate. No Git writes ran; the requester's port-8770 process was left untouched.

<a id="ac-20260904-003"></a>
## AC-20260904-003 — Conversation management added
- prompt_id: [UP-20260904-003](userprompts.md#up-20260904-003)
- date: 2026-09-04
- status: in review
- scope: implementation, coordinator, frontend
- tags: c03, rename, search, drafts, pin, export, delete
- aliases: conversation management, chat search, draft recovery, export chat
- paths: backend/coordinator/db.py, backend/coordinator/server.py, backend/coordinator/test_conversations.py, frontend/app/
- summary: Added rename, literal local search, draft recovery, pin/unpin, Markdown and plain-text export, and delete, reusing SQLite state and the protected API.
- changes: Added a pinned column and a drafts table with additive migrations, plus rename_chat, set_pinned, delete_chat, search, get_draft, set_draft, clear_draft_if_matches and export_chat. Search escapes LIKE wildcards so % and _ are literal, is parameterised, covers every saved chat rather than the sidebar page, and excludes drafts. Drafts are workspace-owned, never reach the model, search or export; a submit clears only the version that was sent and a delayed save cannot resurrect a deleted chat. Export builds a saved snapshot with speaker labels, notes for length-stopped and context-limited replies, a sanitised filename and no mutation. Added six routes and a per-row accessible menu with rename in place, pin indicator, both export choices and a title-confirmed delete with Cancel focused. Chats now sort pinned first, then most recent.
- verification: 73 offline checks pass, 27 of them new: rename trimming and rejection, literal % and _ search, Unicode and case-insensitive search, reach beyond the sidebar page, draft isolation and submit-version clearing, resurrection prevention, pin persistence and ordering, cascade delete, and export scope, formatting, filename safety and non-mutation. In the browser: search for 100% matched exactly one chat, clearing restored the list, the row menu exposed five actions with focus landing on Rename, pinning showed its mark, rename prefilled and saved on Enter, and a draft survived both a chat switch and a full page reload. A real export contained the saved exchange and excluded the draft.
- remaining: Codex review. The delete confirmation uses a native modal dialog which hangs the automation harness, so its Cancel-focused behaviour was verified by construction rather than by an automated click; a human should confirm it. Regenerate remains excluded by design.

<a id="ac-20260904-004"></a>
## AC-20260904-004 — Corrected stale documentation claims
- prompt_id: [UP-20260904-003](userprompts.md#up-20260904-003)
- date: 2026-09-04
- status: in review
- scope: documentation
- tags: c03, readme, accuracy, stale-claims
- aliases: fix stale docs, readme says nothing to run, doc accuracy
- paths: README.md, backend/README.md, docs/prd.md, docs/evaluation.md
- summary: Corrected six documentation claims that became false once the coordinator started running, without overclaiming what still does not exist.
- changes: README's status banner said no application runtime or executable product exists; it now states that a local coordinator runs with Chat and a minimum Control Center, and names what is still absent. Replaced "There is nothing to install or run yet" with the actual run command and a link to the coordinator README. Expanded the repository tree, which listed backend and frontend only as planned boundaries, to show contracts, coordinator, worker-image, app and design. prd.md and evaluation.md's status paragraphs were updated the same way. backend/README.md claimed five contract checks pass and that the coordinator, runtime adapter and database do not exist; corrected to eight contract checks, 73 offline checks in total, and a description of what exists versus what does not. Recorded there that FastAPI remains the C04 worker-API direction while the C03 coordinator uses the standard library. Annotated the OD-03 comparison table's 4096 as the value held constant for that comparison, since the coordinator now runs 8192.
- verification: Swept README, backend, frontend and every docs file for stale phrases and found none remaining. 384 local Markdown links and anchors resolve, git diff --check is clean, and the 73 offline checks still pass. Every replacement names what is still missing so the corrections do not overclaim in the other direction.
- remaining: Codex review. Non-documentation review findings are unaddressed by design: GET query parameters are not length-bounded the way POST fields are, and backend/__init__.py is missing so unittest discover fails from the repository root. No Git writes ran.

<a id="ac-20260904-008"></a>
## AC-20260904-008 — Repair the C03 acceptance defects
- prompt_id: [UP-20260904-008](userprompts.md#up-20260904-008)
- date: 2026-09-04
- status: verified locally; requester acceptance pending
- tags: c03, review-fixes, drafts, delete, export, context
- aliases: stale draft responses, atomic delete guard, Marathi export, context overflow
- paths: backend/coordinator/, frontend/app/app.js, frontend/app/test-conversations.cjs, docs/evaluation.md, docs/model-catalog.md, docs/c03-repair-handoff.md, agent-memory/
- summary: Fixed draft navigation/submission races, active-job deletion, Unicode export headers and context overflow enforcement on the Mac.
- changes: Guarded restored drafts by chat/edit version and serialized captured saves; preserved failed-deletion state; rejected unfinished deletion atomically with HTTP 409; preserved Unicode combining marks with encoded download filenames; disabled runtime truncation/shifting and distinguished context, output and unidentified length limits while retaining partial replies. Added focused regressions, a repeatable bounded runtime check and the device/Git handoff.
- verification: 80 Python checks and 8 Node frontend checks passed; JavaScript syntax and diff whitespace passed. Installed Ollama 0.32.14 retained a fact at 5034 prompt tokens, rejected oversized input before output, and stopped at 8042 prompt plus 150 output tokens with a saved context-limited partial reply. Browser tests confirmed draft switch/reload recovery, busy-delete disabling, Cancel focus, cancelled deletion and confirmed deletion surviving reload. Both Marathi exports returned HTTP 200 with the correct filename and excluded unsent drafts.
- remaining: Requester restarts and accepts C03 on the macOS coordinator. Ubuntu policy verification and C04 remain separate checkpoints. Temporary servers/tabs were closed; real chat history and pre-existing changes were preserved. No installs, model downloads, service changes or Git writes ran.

<a id="ac-20260904-009"></a>
## AC-20260904-009 — Report simultaneous context and output limits
- prompt_id: [UP-20260904-009](userprompts.md#up-20260904-009)
- date: 2026-09-04
- status: verified locally
- tags: c03, review-follow-up, context, output-limit
- aliases: simultaneous caps, limit_reason, both bounds reached
- paths: backend/coordinator/runtime.py, backend/coordinator/server.py, backend/coordinator/db.py, backend/coordinator/test_coordinator.py, frontend/app/app.js, docs/c03-repair-handoff.md, agent-memory/
- summary: Removed the ambiguous single-limit classification when a reply reaches both configured bounds.
- changes: Record context_and_output for simultaneous caps, display readable wording in the UI and export, retain full-context guidance, and recognise a measured output cap even without a prompt count.
- verification: Extended the existing partial-reply regression with 6144+2048 and missing-prompt-count cases; all 80 Python and 8 Node checks passed, plus JavaScript syntax and diff whitespace. No additional real-model run was needed for the classifier change.
- remaining: Requester C03 acceptance on the macOS coordinator. No Git writes or live-history changes.

<a id="ac-20260904-010"></a>
## AC-20260904-010 — Record C03 acceptance and prepare Claude's C04 handoff
- prompt_id: [UP-20260904-010](userprompts.md#up-20260904-010)
- date: 2026-09-04
- status: handoff prepared; Claude dispatch pending
- tags: c03, c04, acceptance, orchestration, networking
- aliases: accepted Mac app, Claude execution brief, connect Ubuntu and Mac
- paths: tasks.md, docs/c03-repair-handoff.md, docs/c04-execution-brief.md, backend/worker-image/README.md, agent-memory/
- summary: Recorded requester C03 acceptance and prepared the C04 source/build handoff with trusted-LAN checks and device evidence gates.
- changes: Advanced current scope to C04, labelled old network addresses historical, retained separate image/deployment/pairing gates and clarified that the prepared base image is not the final worker. Added a paste-ready Claude brief, exact device commands and scoped Git handoff.
- verification: Mac route/address reads reported en0, 192.168.68.132 and gateway 192.168.68.1. Claude Code 2.1.246 was present but auth status reported loggedIn false; the enabled browser inventory had no Claude session. Four document fence checks, 26 local file-link checks, acceptance/dispatch assertions and git diff --check passed. No application tests were rerun for this documentation-only change.
- remaining: Requester sends the brief to the existing Claude conversation and returns Ubuntu LAN output; Codex reviews the resulting C04 source before the Ubuntu image-build checkpoint. No direct Claude dispatch, installations, service changes or Git writes ran.

<a id="ac-20260904-005"></a>
## AC-20260904-005 — Worker API implemented and image verified
- prompt_id: [UP-20260904-004](userprompts.md#up-20260904-004)
- date: 2026-09-04
- status: in review
- scope: implementation, worker, container-image
- tags: c04, af-003, worker-api, docker, image-digest
- aliases: worker image build, worker api, c04 execution
- paths: backend/worker/, backend/worker-image/, docs/c04-ubuntu-build-handoff.md, tasks.md, agent-memory/
- summary: Implemented the worker service against the frozen /v1 contract, completed the pinned image, verified it by building and running it, and prepared the Ubuntu build handoff.
- changes: Added backend/worker with an Ollama adapter and a FastAPI application serving exactly the contract's reserved worker routes, including the attempt_id scoping that stops a delayed poll or cancel targeting a newer retry. The service refuses to start without a bearer credential compared in constant time, so it cannot run open on a LAN; both pairing routes return 501 because OD-06 is recorded but unimplemented. A model is advertised only when the runtime reports a real 64-character manifest digest, replacing an earlier placeholder of zeros. Health reports unknown with no measurements when nothing was observed. Truncation and shifting are disabled, and the limit classifier checks the output branch first so a capped reply after a large prompt is not mislabelled as a context stop. Errors carry only a Failure code, short message and retryable flag. Rewrote the Dockerfile to run the worker with a build-time route check under --network=none, extended the dockerignore, recorded the verification build in provenance.json, and wrote the Ubuntu handoff with endpoint-explicit Docker commands and rollback.
- verification: Built the image for linux/amd64 on the macOS coordinator under emulation: 13 wheels installed under --require-hashes, 8 contract checks passing inside the image with --network=none, route surface matching the contract, 49,496,153 bytes across 11 layers, running as uid 10001 with /app not writable. Ran the container and exercised the API: POST /v1/jobs returned 202, the SSE stream carried attempt.state, three output.delta frames and completion, the model answered DISPATCHED, and runtime_ms was 2812. Authentication returned 401 without or with a wrong token, 400 without the contract header and 409 on a wrong version; a wrong attempt_id returned 404, a malformed envelope 422 and pairing 501. 90 Python checks and 8 Node checks pass.
- remaining: Codex review of the implementation and handoff, then the Ubuntu build. The Mac build was emulated and never pushed, so it is not the deployment artifact; C05 pins the digest the Ubuntu operator reports. Kubernetes readiness, Service exposure, Redis, NetworkPolicy enforcement and container GPU access remain unverified C05 work. No Git writes ran.

<a id="ac-20260904-006"></a>
## AC-20260904-006 — C04 review corrections
- prompt_id: [UP-20260904-004](userprompts.md#up-20260904-004)
- date: 2026-09-04
- status: in review
- scope: implementation, worker, container-image, documentation
- tags: c04, af-003, streaming, admission, idempotency, image-digest
- aliases: c04 corrections, worker streaming fix, manifest digest
- paths: backend/worker/, backend/worker-image/, scripts/image-digests.py, docs/c04-ubuntu-build-handoff.md
- summary: Fixed the three reproduced worker defects plus admission, identity, idempotency and handoff findings from Codex's C04 review.
- changes: Output is now forwarded incrementally through a backpressured thread-to-async relay instead of materialising the whole generator first, so partial text survives an error or cancellation and reaches the stream as it is produced. A reply is validated before completing: a length stop no longer completes, its typed incomplete reason names which bounds were reached using the accepted context_and_output semantics, and the partial text is retained. Admission refuses unsupported task types, capabilities, output kinds and validators, context or attachment packages, envelopes targeting another node, pre-cancelled envelopes, expired deadlines and absent relationships, and returns 429 at capacity rather than evicting active work. Request bodies are bounded during streaming rather than after, compression and non-JSON content types are refused, and the runtime timeout follows the job's remaining deadline. Idempotency keys are required, scoped to route and resource and bound to a body hash, so an exact retry replays the original 202 and a changed body conflicts. Node identity is distinct and persisted rather than a shared default, the service exits at import when no credential of at least 32 characters is set, contract version headers appear on error paths, and upstream runtime error text is no longer echoed. loaded_model_id now needs an actual residency observation rather than an installed listing. Added 19 behavioural checks that run inside the image at build time, and scripts/image-digests.py to read manifest, config and archive digests from a saved archive. Rewrote the build handoff and the worker-image README.
- verification: 37 checks pass inside a linux/amd64 image built under emulation with --network=none. A live container showed the first output event at 2.73 s of a 15.98 s generation across 417 deltas, confirming incremental delivery; an exact retry replayed 202 while a changed body returned 409; and unsupported task type, output kind, wrong target node and pre-cancelled envelopes were refused with typed codes. Confirmed manifest, config and archive digests are three distinct values and that docker image inspect .Id reports different objects under BuildKit and the classic builder, which is why the handoff no longer relies on it. 90 Python and 8 Node checks pass offline.
- remaining: Codex re-review, then the Ubuntu build. Container-to-runtime networking is deliberately unattempted and belongs with the C05 Pod networking design; the earlier untested 172.17.0.1 claim was retracted. Acceptance in the worker is in-memory and is not a durable receipt, which needs AF-005. Pairing stays at 501. The Mac build was emulated, never pushed, and is not the deployment artifact. No Git writes ran.

<a id="ac-20260904-007"></a>
## AC-20260904-007 — C04 re-review blockers closed
- prompt_id: [UP-20260904-004](userprompts.md#up-20260904-004)
- date: 2026-09-04
- status: in review
- scope: implementation, worker, container-image
- tags: c04, fail-closed, od-06, af-005, deadline, attempt-schema, idempotency
- aliases: c04 blockers, worker fail closed, absolute deadline
- paths: backend/worker/, backend/worker-image/, scripts/image-digests.py, docs/c04-ubuntu-build-handoff.md
- summary: Closed all five C04 re-review blockers by making the job routes fail closed, enforcing one absolute deadline with the envelope's limits, serving contract-valid Attempt records, and requiring UUIDv4 idempotency keys scoped to the relationship.
- changes: All four job routes now return a typed 503 while OD-06 pairing and the AF-005 durable receipt are absent, so the worker never returns 202 for in-memory acceptance and never trusts an unverified relationship over plain HTTP; the relationship registry is populated by nothing in the application, so there is no deployable bypass, and a check asserts that. Health and capabilities remain available and advertise no capability while the worker cannot accept work. Execution now derives every wait from one absolute deadline taken as the earlier of the envelope's remaining time and its runtime_seconds, with no per-read floor, and enforces output_bytes and a bounded producer join through a stop event. Attempt records are built through the contract on every read, so state, started_at, finished_at and the single typed reason are validated and the previously extra metrics and output_chars fields are gone. Idempotency keys must be UUIDv4 and are scoped by relationship, workspace, job and route. The archive extractor now detects Docker Archive layouts and reports that the format carries no manifest digest instead of presenting the config digest as one.
- verification: 52 checks pass inside a linux/amd64 image built with --network=none, including new cases for the fail-closed gate, the absent bypass, contract-valid terminal attempts with no extra fields, a slow stream that cannot extend a 0.30 second budget, runtime_seconds bounding the attempt, output_bytes enforcement, and rejection of non-UUIDv4 keys. A live container returned 503 with a typed reason on all four job routes while health reported degraded with empty capabilities and loaded_model_id null; the container exits 1 with no credential. The extractor was exercised against an OCI single manifest, an OCI index with an attestation, and an unrecognised archive. 90 Python and 8 Node checks pass offline.
- remaining: Codex re-review. Enabling dispatch needs OD-06 pairing and the AF-005 receipt; until then the worker builds and reports health but accepts no work, which is the intended C04 state. Container-to-runtime networking and TLS remain C05. The Mac build was emulated, never pushed, and is not the deployment artifact. No Git writes ran.

<a id="ac-20260904-011"></a>
## AC-20260904-011 — Correct the C04 OCI export path
- prompt_id: [UP-20260904-011](userprompts.md#up-20260904-011)
- date: 2026-09-04
- status: source and instructions verified; Ubuntu build pending
- tags: c04, export, buildkit, review-fixes
- aliases: explicit OCI output, docker-container builder, archive guidance
- paths: docs/c04-ubuntu-build-handoff.md, backend/worker-image/README.md, backend/worker-image/provenance.json, scripts/image-digests.py, agent-memory/
- summary: Replaced the BuildKit/docker-save assumption with an explicit OCI export and a pinned dedicated builder checkpoint.
- changes: Added Buildx prerequisites, a digest-pinned BuildKit 0.33.0 builder with bounded resources, fresh artifact directory, explicit type=oci output, provenance/storage/rollback and Git handoff. Removed obsolete dependency-only build and unloaded-image smoke commands. Corrected archive error guidance and labelled the old 37-check image historical while recording the latest 52 checks as Claude-reported, with independently checked source count.
- verification: OCI and Docker-archive CLI cases passed with synthetic temporary archives; handoff shell syntax, local document links, provenance/pin consistency and 8+10+34 source count passed. git diff --check passed. Public BuildKit manifest bytes matched SHA-256, its config reported linux/amd64, licence was Apache-2.0 and compressed layers totalled 112271581 bytes. Local Buildx help confirmed used flags; no builder was created.
- remaining: Ubuntu operator verifies its Buildx availability and performs the image build/export after reviewed Git transfer. The 52 container checks were not rerun by Codex. No images downloaded, builds/deployments, worker-code changes or Git writes ran.

<a id="ac-20260904-008"></a>
## AC-20260904-008 — C04 Ubuntu build evidence recorded
- prompt_id: [UP-20260904-004](userprompts.md#up-20260904-004)
- date: 2026-09-04
- status: in review
- scope: documentation, container-image, execution
- tags: c04, af-003, image-digest, ubuntu-build, od-08
- aliases: c04 build result, worker manifest digest, ubuntu image build
- paths: backend/worker-image/provenance.json, docs/architecture.md, tasks.md
- summary: Recorded the Ubuntu worker's C04 image build, whose manifest digest is the artifact C05 pins.
- changes: Added the Ubuntu build to provenance.json with device, endpoint, platform, flags, base digest, manifest, config and archive digests, layer count, in-image check result and the observed health record. Replaced the OD-08 worker-image row in architecture.md, which had said no digest existed yet, with the built manifest and config digests and their build conditions. Recorded the same evidence in the tasks.md current-scope note, including that the digest differs from the earlier emulated Mac build because image configs embed a creation timestamp, so no reproducible-build claim is made.
- verification: Reviewed the returned build transcript. The base image resolved by the OD-08 pinned digest 2f2e5a87, 13 wheels installed under --require-hashes with pip check reporting no broken requirements, and 52 in-image checks passed with --network=none. The reported manifest digest a1eb434c and config digest 4d9c9189 match the build's own exporting manifest and exporting config lines, an independent cross-check. The archive was 48 MB across 11 layers, matching the emulated Mac build's layer count. The container reported a distinct generated node identity, empty capabilities, health unavailable and loaded_model_id null, which is correct for no reachable runtime and fail-closed job routes. Claude did not run this build; the evidence is the operator's returned transcript.
- remaining: Codex review of the build evidence and requester acceptance close C04. A built image is not a running Pod: Kubernetes readiness, Service exposure, Redis, NetworkPolicy, container GPU access and container-to-runtime networking are C05. Dispatch stays closed until OD-06 pairing and the AF-005 receipt exist. No Git writes ran.

<a id="ac-20260904-009"></a>
## AC-20260904-009 — C05 deployment assets prepared
- prompt_id: [UP-20260904-004](userprompts.md#up-20260904-004)
- date: 2026-09-04
- status: in review
- scope: implementation, deployment, kubernetes
- tags: c05, af-002, k3s, redis, networkpolicy, manifests
- aliases: c05 manifests, k3s deployment, redis clusterip, worker nodeport
- paths: deploy/k3s/, docs/c05-ubuntu-deployment-handoff.md, tasks.md
- summary: Prepared the K3s deployment manifests pinned to the accepted C04 manifest digest, with offline invariant checks and the exact Ubuntu host commands, leaving installation and deployment at the human checkpoint.
- changes: Added deploy/k3s with a namespace carrying restricted Pod Security and a default-deny NetworkPolicy applied before any workload, a DNS exception, Redis 7.2.16 pinned by its OD-08 linux/amd64 digest behind ClusterIP with snapshots and append-only disabled since it is not storage, and the worker Deployment pinned by the C04 manifest digest with imagePullPolicy Never behind the contract's NodePort 30443 to port 8443. Every Pod runs non-root with privilege escalation disabled, all capabilities dropped, RuntimeDefault seccomp, a read-only root filesystem, bounded CPU and memory and no service-account token. Worker egress is limited to Redis; runtime egress is deliberately absent because Ollama binds host loopback, which no Pod can reach, so a guessed CIDR would be useless or far too wide. The credential is created by the operator and no Secret is committed. Added 16 offline invariant checks and the deployment handoff.
- verification: The 16 checks confirm the worker digest matches provenance.json, the Redis digest matches the OD-08 pin in architecture.md, no image uses a floating tag, Service ports match WORKER_PORT and WORKER_NODE_PORT read from the contract source, Redis is ClusterIP with no nodePort and no Ingress exists anywhere, the default-deny policy sits in the lowest-numbered file so ordering cannot create a workload before it, worker egress contains no 0.0.0.0/0, every Deployment is hardened and resource-bounded, nothing uses hostNetwork, hostPath, hostPort or privileged, and no manifest defines a Secret or inlines a token. kubectl --dry-run=client was attempted and needs a live cluster to resolve API groups, so it could not run offline. 90 Python and 8 Node checks still pass.
- remaining: Codex review, then the Ubuntu checkpoint. Nothing was installed or deployed. A gate conflict is recorded for the requester: C05's row expects one real worker-model response, which this deployment cannot produce because the job routes are fail-closed pending OD-06 and AF-005 and the Pod has no route to the host runtime. Container GPU access, dispatch through Redis and zero-egress evidence remain later work. No Git writes ran.

<a id="ac-20260904-010"></a>
## AC-20260904-010 — C05 review blockers closed
- prompt_id: [UP-20260904-004](userprompts.md#up-20260904-004)
- date: 2026-09-04
- status: in review
- scope: implementation, deployment, kubernetes
- tags: c05, probes, redis-auth, networkpolicy, exposure, artifact-path
- aliases: c05 blockers, authenticated probes, redis password, isolation proof
- paths: deploy/k3s/, docs/c05-ubuntu-deployment-handoff.md, tasks.md
- summary: Closed all five C05 review blockers — unauthenticated probes, Redis protected mode, a meaningless isolation test, unfinished network exposure, and the stale artifact path — and added the missing in-Pod inference and coordinator persistence checks.
- changes: Replaced all three worker httpGet probes with authenticated exec probes that read the credential from the container environment and send the contract header, so a healthy Pod is no longer restarted by a 401 while the endpoint keeps its authentication. Gave Redis a required password from an operator-created Secret expanded through sh so it never appears as an argument literal, and authenticated its readiness and liveness probes, which would otherwise have failed with NOAUTH. Replaced the ad-hoc kubectl run isolation test with two reviewed Pod manifests carrying the full restricted Pod Security context so admission cannot reject them before a connection is attempted; each reports a RESULT line separating a network refusal from DNS, authentication, protected-mode and missing-tooling failures, and the allowed half must pass before the denied half means anything. Kept the Kubernetes API and the worker NodePort closed to the LAN with reversible firewall rules rather than exposing plain HTTP, recording that K3s listens on all interfaces by default and that TLS belongs to OD-06. Switched to the preserved artifact at /home/prachi/.aegisforge/artifacts/c04/worker.tar and removed the rebuild advice. Added a separate narrow runtime-egress manifest and an in-Pod bounded inference check through the runtime adapter, plus the missing macOS coordinator metadata-persistence steps across a restart.
- verification: 30 offline invariant checks pass, 14 of them new: the worker has no unauthenticated httpGet probe and its probes send both required headers, Redis requires a password sourced from a Secret rather than a literal and its probes authenticate, both isolation Pods satisfy restricted Pod Security and pin their image, the allowed half carries the selected label and the denied half does not, both distinguish five failure modes, the default worker egress reaches Redis and nothing else with no ipBlock, and the runtime policy is a single /32. 106 Python and 8 Node checks pass. Nothing was installed or deployed.
- remaining: Codex re-review, then the Ubuntu checkpoint. Recorded for the requester that Ready Pods plus adapter-level inference is not completed integration: a response through the public job routes needs OD-06 pairing and the AF-005 receipt. LAN exposure and TLS arrive with pairing. No Git writes ran.

<a id="ac-20260904-011"></a>
## AC-20260904-011 — C05 second-round blockers closed
- prompt_id: [UP-20260904-004](userprompts.md#up-20260904-004)
- date: 2026-09-04
- status: in review
- scope: implementation, deployment, kubernetes
- tags: c05, nodeport, kube-proxy, ollama-forwarder, redis-cli, sqlite
- aliases: c05 second review, nodeport-addresses, socket proxy, rediscli auth
- paths: deploy/k3s/, docs/c05-ubuntu-deployment-handoff.md
- summary: Closed six further C05 findings covering the firewall layer, Ollama rebinding, an unsupported redis-cli flag, an inference check that could not fail, a broken persistence query and the password still reaching process arguments.
- changes: Replaced INPUT firewall rules with install-time controls, because NodePort traffic is DNATed and forwarded and never traverses INPUT, and a blunt INPUT drop on 6443 would break cluster components reaching the API by node address. K3s now installs with --bind-address 127.0.0.1 and --kube-proxy-arg=nodeport-addresses=127.0.0.1/32, which live in the systemd unit and survive a reboot, with verification and a documented reinstall if the single-node bind does not come Ready. Ollama is no longer rebound: a systemd-socket-proxyd unit listens on the CNI bridge and forwards to the untouched loopback listener, with an INPUT rule limiting it to the Pod CIDR and rollback that removes only the new units, never systemctl revert ollama. Recorded plainly that NetworkPolicy does not govern traffic to a Pod's own node, so the runtime is reachable by any Pod on this node rather than the worker alone. Removed redis-cli -t, which does not exist in the 7.2 parser and would have been read as a command, replacing it with timeout and an exit-status classification that treats 124 as blocked and reports refused and empty-output separately. Moved the Redis password out of process arguments entirely: the server reads it from a config file written to the Pod's own tmpfs, and clients use REDISCLI_AUTH instead of -a. Rewrote the inference check to fail on an empty, truncated or wrong answer, a done_reason other than stop, missing token counts, or its own overall deadline. Corrected the persistence query to SELECT value FROM meta WHERE key='contract_version'.
- verification: Confirmed against the Redis 7.2 source that the CLI parser accepts a c d e h i n p r s u v x and no -t, and that REDISCLI_AUTH is supported. Confirmed the previous SQL fails with no such column and the corrected form returns 1.0 against the live coordinator database, alongside an attempt carrying state, node id, route reason and runtime and a 475-event count. 33 manifest invariant checks pass, six of them new, including that the password never reaches argv, clients use REDISCLI_AUTH, no redis-cli -t appears in any command, probes classify exit status rather than empty output, and probes report seven distinct failure modes. Three of those checks initially failed by matching their own explanatory comments, so the matcher now strips comment lines. 123 Python and 8 Node checks pass. Nothing was installed or deployed.
- remaining: Codex re-review, then the Ubuntu checkpoint. Two arrangements are untested on the target host and are marked so with verification and rollback: the single-node --bind-address and whether kube-proxy accepts a loopback nodeport-addresses CIDR. The forwarder restricts the runtime to Pods on this node, not to the worker Pod. No Git writes ran.

<a id="ac-20260904-012"></a>
## AC-20260904-012 — C05 completed in one pass
- prompt_id: [UP-20260904-004](userprompts.md#up-20260904-004)
- date: 2026-09-04
- status: in review
- scope: implementation, deployment, kubernetes, host-units
- tags: c05, k3s, guards, probes, redis-auth, inference-check, handoff
- aliases: c05 single pass, cluster guard, ollama forwarder, ordered handoff
- paths: deploy/k3s/, docs/c05-ubuntu-deployment-handoff.md
- summary: Completed C05 deployment assets against the single execution brief, with host guard units, corrected workload configuration, an executable bounded inference check and one ordered operator sequence.
- changes: Worker probe timeouts raised to 20s against the measured 13s worst-case health budget, since /v1/health calls runtime.probe which makes three HTTP calls; readiness now documents that it means the API answers, not that jobs are accepted. The worker Service selector gained a component label so an isolation Pod carrying only the policy label can never become a Service endpoint. Redis writes its generated config into a bounded memory-backed volume, verifies the credential is readable and non-empty before starting, and both server and clients keep the password out of process arguments; Secrets are group-readable with fsGroup so a non-root user can read them. Both isolation probes gained fsGroup, credential-readability reporting and timeout -k. Added host units under deploy/k3s/host: a tagged idempotent guard script, a cluster guard that k3s requires so failure to protect prevents startup, an Ollama guard that waits for the bridge and that the proxy socket requires, and the proxy units. K3s now installs with SKIP_ENABLE and SKIP_START so protection precedes any listener, keeps the API reachable by cluster components by dropping only the LAN interface, and restricts NodePort through kube-proxy rather than INPUT. The inference check became a real script piped over kubectl exec -i with an explicit container, a SIGALRM deadline that interrupts blocked reads and covers the initial probe, and a bounded outer wrapper. Rewrote the handoff as one ordered A-K sequence.
- verification: 70 offline checks pass across three new suites. 41 manifest invariants, including probe timeouts exceeding the health budget, probes never matching the Service selector, group-readable Secrets with fsGroup, credential readability checked before use, generated config in bounded memory and timeout -k. 15 guard checks against a stubbed iptables and ip confirm loopback and cluster CIDRs stay allowed, only the LAN interface is dropped, NodePort is not handled in INPUT, apply is idempotent, removal deletes only tagged rules and never flushes, a missing bridge fails rather than guessing, and Ollama's loopback is never firewalled. 14 checks exercise the real inference script and the real wrapper across valid, empty, wrong, truncated, missing-metric, zero-count, unreachable and blocked-read cases, plus stdin forwarding, failure propagation, explicit container, missing Pod and a stuck exec. Two genuine defects surfaced from those checks and were fixed: an unbounded rule-removal loop, and a watchdog that killed only the direct child so grandchildren held the pipe open. A 16-point cross-check confirms source, manifests and handoff agree. Shell syntax and YAML structure validated. 123 Python and 8 Node checks pass.
- remaining: Codex review, then the Ubuntu checkpoint. Nothing installed or deployed. Two arrangements remain untested on the target host and are marked so with verification and scoped rollback: whether kube-proxy accepts a loopback nodeport-addresses CIDR, and the socket-proxy path. The runtime forwarder admits every Pod on this node, not the worker alone, because NetworkPolicy does not govern a Pod's connection to its own node. Public job routes stay fail-closed; C06 owns dispatch. No Git writes ran.

<a id="ac-20260904-013"></a>
## AC-20260904-013 — Execution 1: Refinix desktop foundation
- prompt_id: [UP-20260904-012](userprompts.md#up-20260904-012)
- date: 2026-09-04
- status: in review
- scope: implementation, desktop-shell, packaging, branding, ui, cancellation
- tags: execution-1, refinix, pywebview, py2app, attachments, skills, settings-cards, stop
- aliases: desktop foundation, native window, refinix branding, stalled cancel, attachment intake
- paths: desktop/, frontend/app/, backend/coordinator/, scripts/build-brand-assets.py, README.md, tasks.md
- summary: Built a native desktop foundation named Refinix around the existing coordinator — pywebview shell with a bounded startup lifecycle, brand assets derived from the supplied masters, simplified Chat/Code navigation with a skill-and-attachment composer, card-based Settings, and repaired cancellation — with macOS packaging prepared but not built.
- changes: New `desktop/` package. `lifecycle.py` holds the whole startup sequence with no window toolkit so it is testable offline: an OS-level single-instance lock, port selection that reuses only this workspace's own coordinator and never attaches to an unrelated listener, an engine supervisor that starts Ollama only when it is installed and stops only a copy it started, and model detection that reports the exact `ollama pull` command without downloading. `shell.py` opens the window on a local startup page that shows readable progress and a Try again button, and exposes a six-method bridge with no method that accepts a path, URL or command from the page. `server.py` gained `build_server`/`shutdown_server` so the shell serves the same coordinator on a thread, a bundle-aware `static_root()`, `/v1/capabilities`, attachment routes with a route-scoped 28 MB bound, a focus route for a second launch, and observed capability state in `/v1/status`. `db.py` gained an attachments table and helpers: names are sanitised for display only, the stored name is the attachment id, writes are confined to `~/.aegisforge/attachments`, and size, count, type and emptiness are all bounded. Attachments bind to the request that carried them and are described as received, never as read; the export says the same. `runtime.py` gained `_CancelWatch`, which aborts the socket from a second thread so a cancel reaches a stalled stream instead of waiting out the 300 s request timeout. The frontend was rebranded and simplified: Chat | Code top level, Control Center renamed Settings and moved to secondary navigation with interactive cards over observed state and the readouts under Advanced, a composer carrying an inline skill label with a keyboard path plus `+` attachment intake by native picker, file input and drag-and-drop, and Send that becomes a prominent Stop showing "Stopping…" on click. Code renders no access selector, because no access mode is enforced. Icons and the header wordmark are derived from the two brand masters by `scripts/build-brand-assets.py`; the originals are untouched.
- verification: 151 Python checks pass, 71 of them new, plus 8 Node checks. New suites cover the engine supervisor across running, stopped, missing, dying and silent runtimes with a bounded timeout; port choice against a real occupied socket, another workspace's coordinator and an exhausted range; the single-instance lock including a corrupt lock file; attachment intake including traversal, wrong type, empty, oversized, count bound, removal, and that a stored name from outside the folder is never unlinked; that file contents and names never reach the model request; capability state under every runtime condition; and cancellation. Two genuine defects surfaced from those checks and were fixed: the cancel watcher's abort raised `http.client.IncompleteRead`, which is neither OSError nor ValueError, so it escaped as a crash instead of a cancellation — caught by a test that streams from a real local socket that then stalls; and `[hidden]` did nothing against app.css's `display` rules, so the drop hint and skill label were always visible. Observed in a browser against an isolated database: streaming, Stop during a stall recording `cancelled` with the partial text on the attempt and no assistant message, Stop restored after a full reload of an active conversation, attachment add and remove with the file appearing and disappearing on disk, the skill label reachable and removable by keyboard, and both light and dark themes. `python3 -m desktop --no-window` ran the real sequence: all six steps ok, a second launch refused to start and asked the running copy to come forward, and an unrelated listener on the preferred port caused a different free port to be chosen rather than an attachment to it. Nothing was installed, downloaded or deployed; no C05 test was rerun as evidence.
- remaining: Codex review, then requester acceptance. `Refinix.app` is **not built** — py2app and pywebview are not installed, so no native-window screenshot and no packaged-launch result exist; the exact install and acceptance commands are the setup handoff in `desktop/README.md`. Whether pywebview, pyobjc and py2app support this Mac's CPython 3.14.6 is unverified and is the first question that handoff answers. The Windows and Ubuntu launch and packaging paths are written and unverified on any device. C05 is untouched and stays paused. No Git writes ran.

<a id="ac-20260904-014"></a>
## AC-20260904-014 — Verify the desktop review corrections
- prompt_id: [UP-20260904-013](userprompts.md#up-20260904-013)
- date: 2026-09-04
- status: fixes verified; requester acceptance pending
- tags: refinix, desktop, review-fixes, cancellation, lifecycle
- aliases: pre-header cancellation, reused coordinator quit, Windows lock offset, native Quit
- paths: desktop/, backend/coordinator/runtime.py, backend/coordinator/server.py, backend/coordinator/test_desktop_surface.py, README.md, tasks.md
- summary: Fixed the six desktop findings and added regressions without replacing the existing frontend or coordinator.
- changes: Cancellation owns the loopback HTTP connection before response headers; startup cancellation cleans late resources; native Quit waits for the startup worker; reused coordinators expose active jobs and receive confirmed cancellation without shutdown; both native entry points record the selected port; Windows metadata sits outside the locked byte; dependency locks contain valid hashes and existing backend pins.
- verification: 161 Python checks passed under desktop CPython 3.12, and 8 Node checks passed; after the final native Quit repair, all 7 focused desktop review regressions passed. Synthetic checks cover stalled headers/body, startup cleanup, reused-coordinator cancellation, native entry metadata, lock offsets and source staging. Shell syntax and git diff --check passed.
- remaining: Windows native behavior and requester visual/chat acceptance are unverified. No C05 checks or Git writes ran.

<a id="ac-20260904-015"></a>
## AC-20260904-015 — Build and open the macOS Refinix application
- prompt_id: [UP-20260904-014](userprompts.md#up-20260904-014)
- date: 2026-09-04
- status: setup completed; requester acceptance pending
- tags: refinix, macos, py2app, dependency-locks, standalone
- aliases: Refinix app launch, source-independent bundle, signature verification
- paths: desktop/, .gitignore, README.md, tasks.md
- summary: Completed the approved isolated desktop dependency setup, repaired actual bundle failures and opened Refinix.app on the macOS coordinator.
- changes: Added the executable setup script and 20 hash-pinned artifacts totaling 12,495,337 bytes, including existing backend pins. Packaging stages only application sources, disables external site-packages and avoids py2app's dangling optimized-bytecode link; setup verifies the ad-hoc signature before launch.
- verification: Artifact hashes, pip check and codesign --verify --deep --strict passed. Final bundle opened from desktop/dist/Refinix.app and reported packaged mode with reachable existing Ollama. A copied bundle started with repository and Homebrew Python reads denied; the denial was verified. Reopening reused the same instance, including on fallback port 8771.
- remaining: No real inference request or native screenshot was produced in this correction pass; visual/chat acceptance remains with the requester. Developer ID signing, notarisation, Windows and Ubuntu packaging are unfinished. No Docker startup, model downloads, C05 execution or Git writes ran.

<a id="ac-20260904-016"></a>
## AC-20260904-016 — Record requester acceptance and isolate the desktop handoff
- prompt_id: [UP-20260904-015](userprompts.md#up-20260904-015)
- date: 2026-09-04
- tags: refinix, requester-acceptance, git-handoff, scoped-pr
- aliases: stopped chat retained after quit, desktop-only tasks patch, exclude C05
- paths: README.md, desktop/README.md, tasks.md, agent-memory/
- summary: Updated current desktop status with the requester's successful Chat/Stop/quit/history check and prepared explicit staging commands and PR text excluding pending C05 changes.
- evidence: Requester reported starting and stopping Chat, quitting with Command-Q, reopening with the stopped conversation retained, and supplied a generated follow-up reply.
- verification: Current branch is aditya and the index is empty. Inspected the shared-file diffs; only tasks.md mixes desktop and C05 edits. A temporary desktop-only tasks patch was checked against HEAD and leaves all numbered execution-task content identical to HEAD. No application tests were repeated.
- remaining: No Git writes performed; requester runs the supplied commit/push/PR commands. Windows/Linux packaging and native acceptance remain unfinished; C05 remains paused.

<a id="ac-20260904-017"></a>
## AC-20260904-017 — Group the remaining C-task execution
- prompt_id: [UP-20260904-016](userprompts.md#up-20260904-016)
- date: 2026-09-04
- tags: grouped-execution, parallel-preparation, parallel-workflows, final-validation
- aliases: C06 plus C07, C08 plus C09, C11 through C13 session
- paths: tasks.md, agent-memory/
- summary: Replaced the strictly sequential remaining plan with requester-approved grouped work while preserving required device and acceptance gates.
- changes: C07 fixture and dependency planning may overlap C06 after C05, while C07 device setup and acceptance wait for C06. C08 Documents and C09 Code implementation may run in parallel after C07 against shared interfaces, with separate verification before C10. C11-C13 share one prepared final-validation session but retain offline, recovery, measurement and three-rehearsal gates in order.
- verification: `git diff --check` passed. A before/after snapshot confirmed every existing C05 deployment file and the current C05 status section were byte-for-byte unchanged. Table dependencies and grouped-plan statements were checked for the retained gates. No application tests were run for this documentation-only plan update.
- remaining: No C06-C13 implementation, device action or Git write occurred. C05 remains paused and dirty; resume only from its current device checkpoint.

<a id="ac-20260904-018"></a>
## AC-20260904-018 — Exclude repository files from the macOS bundle
- prompt_id: [UP-20260904-017](userprompts.md#up-20260904-017)
- date: 2026-09-04
- tags: refinix, py2app, packaging, artifact-validation
- aliases: raw backend bundle leak, staged build cwd, application bundle allowlist
- paths: desktop/setup_py2app.py, desktop/setup-macos.command, desktop/test_packaging.py, agent-memory/
- summary: Corrected py2app's build context so a release bundle contains only the staged application modules and rejects repository files.
- changes: Builds run from the filtered source staging directory with absolute output paths. A post-build check now inspects loose and zipped application modules for missing or unwanted files.
- verification: The new check rejected the existing bundle's worker, tests, READMEs and cache files. All 17 focused packaging tests passed. A separate release build passed its content check and strict signature verification; its loose and zipped application inventory contained only allowed modules. The documented alias build also completed.
- remaining: The separately built proof bundle was not installed or launched, so the running app remains untouched. The unused 4.16.0 wheel stays as harmless local cache. No full-suite, native interaction, C05 action or Git write ran.

<a id="ac-20260904-019"></a>
## AC-20260904-019 — Execution 2: Code surface, access modes, Reasoning switch
- prompt_id: [UP-20260904-018](userprompts.md#up-20260904-018)
- date: 2026-09-05
- status: implemented; Codex review and requester acceptance pending
- scope: implementation, code-surface, access-policy, runtime, frontend
- tags: execution-2, repository-editing, access-modes, approvals, reasoning, blank-pane
- aliases: partial full ask, native folder picker, think true false, atomic replace, stale render
- paths: backend/coordinator/, desktop/shell.py, frontend/app/, docs/, tasks.md
- summary: Added an enforced repository-editing workflow, a per-model Reasoning switch that reaches the real request, and a root-cause repair for the conversation pane that could go blank behind valid history.
- changes: New `repo.py` holds the filesystem boundary: strict relative-path normal form, a documented deny list, descriptor-relative traversal that refuses to follow links at every component, O_NONBLOCK so a FIFO cannot hang a read, hard-link and non-regular refusal, strict UTF-8 only, and an atomic same-directory replacement that re-verifies type and hash immediately before `os.replace` and preserves the original permission bits. New `policy.py` is one pure decision function over three modes and four actions, with a named denial for commands, Git, installs, network, and file creation, deletion and renaming in every mode. New `codeflow.py` builds one instruction message labelling repository text as untrusted data, parses a strict JSON proposal, and computes bounded unified diffs. New `code_service.py` routes every operation through a single gate, so no HTTP handler evaluates a mode. `db.py` gained model preferences, repositories, proposals, approvals and a code audit at schema 4, plus an additive `reasoning_json` column; approvals are one-shot, expiry-checked and matched against the stored digest, and the decision route accepts only an opaque id and a boolean. `runtime.py` takes a request-scoped `think` and yields `thinking` separately from `delta`, so reasoning is progress and never the answer. `shell.py` gained `choose_repository`, which takes no argument; there is deliberately no HTTP route accepting a filesystem path, so a reused coordinator reports that rather than gaining one. The frontend added the model pill and its Reasoning switch, the Code surface, and the render repair: the thread is built in a detached fragment and committed once, `renderMarkdown` failures fall back to literal text for that message only, optional fields parse defensively, and a monotonic generation token rejects a stale load even for the same chat.
- verification: 237 Python checks pass, 108 of them new across `test_code_access` (54), `test_reasoning` (19) and additions elsewhere; 21 Node checks pass, 13 of them the new rendering regressions. The rendering suite was mutation-checked against a copy of the source in a scratch directory: restoring the pre-clear plus the unisolated markdown call fails the two formatting regressions, and removing the generation token fails the same-chat overlap regression, so the checks catch the original defects. A local HTTP stand-in observed the exact `/api/chat` body: `think` false and true at the top level, no `/think` suffix, unchanged num_ctx/num_predict/truncate/shift. A real socket that streams a thinking chunk then stalls confirmed cancellation still lands in under 3 s. Two E1 assertions were updated rather than weakened, because Code is now implemented and the runtime signature changed. `git diff --check` is clean. One bounded live check ran against the already-running Ollama 0.33.3 with the already-installed model, starting and downloading nothing: `think=false` gave 0 thinking chunks and a visible answer on `stop`; `think=true` gave 101 thinking chunks and the same visible answer on `stop`. Only chunk and character counts were recorded; no reasoning text was printed or persisted. The UI was exercised against an isolated database: the pill toggled Off to On, the choice persisted in `model_prefs`, and the Code surface listed a synthetic project with its modes and audit.
- remaining: Codex review, then the requester acceptance sequence in the final handoff. `desktop/dist/Refinix.app` still carries the Execution 1 build because the accepted instance is running and was not quit; rebuilding is the requester's step. Not implemented and reported unavailable: sandboxed execution, worker dispatch, file creation/deletion/rename, project commands, Git, installs and network enablement. The Windows write path is unexercised — its behaviour is gated by the same capability probe. No claim is made about the model's coding quality. C05 untouched, no Git writes.

<a id="ac-20260905-001"></a>
## AC-20260905-001 — Execution 2 review corrections
- prompt_id: [UP-20260905-001](userprompts.md#up-20260905-001)
- date: 2026-09-05
- status: corrected; Codex re-review and requester acceptance pending
- scope: implementation, code-surface, access-policy, filesystem, frontend
- tags: execution-2, review-fixes, ask-mode, short-io, complete-diff, platform-gate, handler-order
- aliases: seven findings, listing approval, stale repository state, partial write, retired action names
- paths: backend/coordinator/, frontend/app/, tasks.md, agent-memory/
- summary: Closed all seven review findings and added regressions that fail without each fix, plus one further defect found while verifying them.
- changes: Ask-mode listing now works end to end: `/v1/code/files` returns its approval to the interface, each approved action returns to its own operation instead of every non-write being retried as a proposal, and the listing an approval bought is kept rather than discarded by the refresh that follows. `db.request_approval` reuses an existing pending approval for the same action and digest, so repeated attempts no longer stack cards. Repository activation is state-safe: one reset clears selection and files whenever the active project changes, including native connection, and a monotonic generation plus a repository check stops a late answer for one project landing under another. `repo.py` loops short reads and short writes, verifies the written size before promotion, and turns a stalled or failed write into a refusal that leaves the original file and removes the temporary one. The diff is no longer truncated: `unified_diff` returns the complete diff or the proposal is refused, so Apply can never write bytes the review did not show. The platform capability now gates the whole Code surface rather than only the write, and `PLATFORM_NOTE` no longer claims reading and proposing still work. Reading files and sending them to the model became one action, `repo.read_and_propose`; the split names are retired, denied in every mode, and hidden from the user-facing unavailable list, and the proposal audit records the outcome the gate actually produced with its approval id. While verifying, `do_GET` was found catching `ValueError` above `RequestError` and `CodeError`, making both unreachable and answering 400 for every 403 and 404; the handlers are now ordered most specific first.
- verification: 256 Python checks pass, including 73 in `test_code_access`; 31 Node checks pass across three frontend suites, 10 of them the new Code surface regressions. Each fix was mutation-checked against a scratch copy: removing the listing retry fails the listing regression, removing every repository reset fails both selection regressions, removing every generation guard fails the cross-project regression, and the earlier pane mutations still fail their own tests. The Ask-mode sequence was then exercised over real loopback HTTP against a synthetic project: listing answered 202 with a `repo.list` approval, asking again returned the same approval rather than a second one, approving and retrying returned the file list, offering that approval to the proposal route was refused 409 as a mismatch, and an unknown repository answered 404 rather than 400. The same sequence was driven in the browser: the approval card appeared, approving it showed both files and left no new card. `git diff --check` is clean. Nothing was installed, downloaded or rebuilt, no model was called, and the running packaged app was not touched.
- remaining: Codex re-review, then the requester acceptance sequence. `desktop/dist/Refinix.app` still carries the Execution 1 build; rebuilding is the requester's step after quitting the running instance. Still unavailable and reported so: sandboxed execution, worker dispatch, file creation, deletion and rename, project commands, Git, installs and network enablement. The Windows path remains unexercised and is gated by the same capability check. No claim is made about the model's coding quality. C05 untouched, no Git writes.

<a id="ac-20260905-002"></a>
## AC-20260905-002 — Execution 3: document skills, retrieval, .docx generation
- prompt_id: [UP-20260905-002](userprompts.md#up-20260905-002)
- date: 2026-09-05
- status: implemented in source; no tests run (permission not granted); Codex review of E2+E3 and requester acceptance pending
- scope: implementation, documents, retrieval, artifacts, ui
- tags: execution-3, extraction, fts5, docx, citations, context-indicator, codex-composer
- aliases: read a document, search my documents, write a document, approval note, project chooser
- paths: backend/coordinator/, frontend/app/, docs/, tasks.md, agent-memory/
- summary: Turned the three document skills into working capabilities over the existing attachment intake, added keyword retrieval with checked citations and a real .docx generation workflow, added a context-window indicator fed by context.py, and rebuilt the Code surface around a Codex-style composer.
- changes: New `documents.py` reads `.txt`, `.md`, `.csv`, `.json` and `.docx` with the standard library, re-verifying the intake digest before parsing, keeping pages separate, and leaving a page count Word did not write as missing. Its probe reports PDF and OCR unavailable with the exact missing prerequisite; nothing invents text for a scan and no text extractor is called OCR. New `retrieval.py` searches SQLite FTS5 within one request's sources, quotes every term so FTS operators in a question or a document cannot change the query, bounds passages, takes them round-robin so one source cannot flood the context, orders deterministically, and re-resolves every citation against the selected sources and their real pages. New `docgen.py` writes a genuine OOXML `.docx` with `zipfile`, atomically and without overwriting, and validates it by reopening the package. New `docflow.py` holds the three skills and `inspection_report_to_approval_note`, fences document text as untrusted data, parses the model's note through a strict schema, and turns an unresolvable citation into a visible unresolved item rather than dropping it. `db.py` gained extraction, page, FTS and artifact tables at schema 5 plus a `skill_id` column on jobs; `server.py` computes real capability state per skill, carries the skill through submit into the job, dispatches document skills inside `_run` with cancellation checked between stages, exposes `/v1/context` from `context.py`, and gates artifact export behind a one-shot approval bound to the file's digest. The frontend added the context meter and its popover, autogrowing prompt boxes for both composers, artifact rows with approval-gated export, and a rebuilt Code surface: the Access mode, Proposed change and What Refinix did panels are gone, access is a composer pill using Codex labels over unchanged backend ids, proposals and complete diffs arrive as chronological results, approvals appear inline, file selection moved into the `+` picker, and the audit sits under Details.
- verification: **None. No test, service, model call or build was run — permission was not granted for this pass.** Every changed Python file and both JavaScript files were parsed only (`ast.parse`, `node --check`), and `git diff --check` is clean. While writing the code I also ran a few `python3 -c "import ..."` module-import checks, which execute module-level code; nothing else was executed. Focused tests were written and left unrun: `backend/coordinator/test_documents.py` covers digest mismatch, unsupported and malformed formats, page-bound extraction, missing values staying missing, retrieval ordering, bounds, isolation and no-result, citation resolution, prompt-injection text staying data, strict parsing, valid DOCX structure, artifact provenance, atomic and confined writes, cancellation producing no artifact, plain Chat not reading attachments, a skill reading only its own request's files, export approval and replay, capability-unavailable leaving Chat and Code available, and the context estimate reusing context.py with the draft counted. `frontend/app/test-composer.cjs` covers the absent dashboard panels, the project chooser above the prompt, the composer access selector mapping to existing ids, inline diffs and approvals, project switching clearing context, stale responses, composer growth and capping, and the context indicator's warnings.
- remaining: One combined Codex review of Executions 2 and 3, then requester acceptance. Execution 2 never received a completed verdict. PDF reading and OCR are unavailable on this computer and are reported so rather than approximated. Whether a generated `.docx` opens in Word, the model's output quality, and packaged-app behaviour are unverified. `desktop/dist/Refinix.app` still holds the Execution 1 build, so neither E2 nor E3 is in the packaged app. C08, AF-008 and AF-009 are not marked verified, and the distributed Documents workflow is untouched. C05 untouched, no Git writes.

<a id="ac-20260905-003"></a>
## AC-20260905-003 — Combined Execution 2 and 3 review repairs
- prompt_id: [UP-20260905-003](userprompts.md#up-20260905-003)
- date: 2026-09-05
- status: source and offline review passed; requester native acceptance pending
- scope: review, execution-2, execution-3, security, correction
- tags: refinix, code-surface, document-skills, approvals, containment, review-fixes
- aliases: combined codex review, e2 e3 verdict, source pass, packaged app pending
- paths: backend/coordinator/, frontend/app/, tasks.md, agent-memory/
- summary: Completed the combined review, repaired the confirmed Code and Documents defects, and left only native/package and real-model requester gates.
- changes: Fixed the Code page's syntax failure and removed-DOM file-list gate; made context estimates and artifact approval tokens POST-only; bound approvals to exact targets; verified proposed replacement digests; serialized proposal/application state; made repository listing descriptor-relative; bounded attachment and DOCX reads; hardened citation schemas and source scope; made cancellation and chat deletion remove derived artifacts; filtered invalid XML; corrected document capability and attachment notices; and kept the context/new-chat guidance truthful.
- verification: 288 coordinator tests, 60 browser-side tests and 17 packaging checks passed. Python compilation, JavaScript syntax and `git diff --check` passed. A completed diff security scan recorded four low-severity findings in the captured Claude patch; all four and five additional defence/privacy defects are repaired in the current tree.
- remaining: Quit and rebuild `desktop/dist/Refinix.app`, then perform native folder, access-mode, Code apply, document-read, generated-DOCX and context-indicator requester checks. No model, network, install, deployment, Ubuntu or Git write ran. PDF/OCR and distributed document execution remain unavailable; unrelated C05 work was preserved.
<a id="ac-20260905-001"></a>
## AC-20260905-001 — Neutral black palette, selective glass, and collapsible walls across every surface
- prompt_id: [UP-20260905-001](userprompts.md#up-20260905-001)
- date: 2026-09-05
- agent: Claude
- status: implemented
- tags: refinix, palette, neutral-black, glassmorphism, panel-collapse, contrast-audit, accessibility
- aliases: navy to black, chatgpt claude aesthetic, hamburger panel toggle, glass on floating surfaces only, st-unknown contrast, panel-scrim collision
- paths: frontend/design/tokens.css, frontend/design/app.css, frontend/design/chat.css, frontend/design/shell.js, frontend/design/chat.html, frontend/design/documents.html, frontend/design/code.html, frontend/design/control.html, frontend/design/onboarding.html, frontend/design/onboarding-install.html, frontend/design/pairing.html, frontend/design/README.md, frontend/app/app.css, frontend/app/app.js, frontend/app/overrides.css, frontend/app/refinix.css, frontend/app/index.html, frontend/app/code.html, frontend/app/control.html, frontend/README.md, agent-memory/
- summary: Rebuilt the palette on a strictly neutral black ground, cut glass back to surfaces that actually float, and added a three-line control at each end of every surface header that folds the nav and the rail away — applied to both the design track and the running application.
- changes: The navy was three stacked biases, not one token: the grey ramp leaned blue (#0E1218/#151A22/#242C38), the atmosphere ran a rgba(109,179,242,.13) field over all of it, and the glass carried saturate(150%), which multiplies whatever tint it refracts. Every grey is now R=G=B, the atmosphere is white lift plus one whisper of violet, and saturate sits near 100%. The accent hues keep their jobs unchanged — sky for live, green for enforced, purple for agent provenance, amber caution, red-clay fault. The artifact treatment stopped being a cyanotype: a prussian-blue document was the single largest blue object on the Chat surface, and it is now graphite in both themes. Glass was redistributed from "the frame and all containers" to only what floats — the header band, the composer box, the approval gate, dialogs, the onboarding and pairing cards, and the floating controls. The nav and rail are now flat and opaque at --surface-sunken, darker than the canvas; blurring two full-height walls with nothing behind them is what washed the previous build into one tone. The composer band was deliberately un-glassed and the glass moved to the box inside it, because a full-width 120px slab of glass sits across the bottom of every screen. Chat moved into the ChatGPT/Claude register: a centred 46rem reading column, a user turn as a bounded right-aligned object and an agent turn with no bubble at all, prose at 15.5px, an oval composer, and .thread masked at both edges so text dissolves into the header and composer rather than stopping at a hard line. --font-ui moved from IBM Plex Sans Condensed to IBM Plex Sans, which the application could never load anyway, so the two tracks no longer differ by a width; the Google Fonts link on all seven pages was updated to match. Both walls now fold: on a wide window the grid track collapses to zero so the middle column genuinely gets the room, and below 1180px (rail) and 760px (nav) the same control opens an overlay with a scrim, replacing a display:none that had silently deleted the routing evidence and then the navigation. State is remembered per panel per surface, storage guarded in both directions. The app track's app.css was regenerated as an exact concatenation of the four design files it documents itself as being derived from, so the copy cannot drift; frontend/app keeps its no-build-step property. The public site (site.html, site.css) was not touched.
- verification: Wrote a compositing contrast auditor — glass defeats the usual walk-up-to-an-opaque-ancestor approach — that alpha-composites every layer from the root down including the strongest rgba stop of each gradient, and takes the lower of the with-gradient and without-gradient ratios. Swept all seven design pages and four application pages in dark and light at 1440x900: 1,704 text-bearing elements, zero failures. Confirmed first that the two dark token blocks are byte-identical (43 declarations each) and that no :root[data-theme="light"] block exists, so the two system states cover all three theme resolutions. Dark floor 4.86:1, light floor 4.57:1. Three real defects were found and fixed during the sweep. --st-unknown measured 4.45:1 on a veiled panel and was raised from #8C8C8C to #9A9A9A. A new .scrim rule collided with pairing.css, which already owns that class for the always-visible pairing backdrop and declares neither opacity nor visibility — a hidden-by-default .scrim leaked through and hid the entire pairing dialog, 76 elements; the overlay backdrop is now .panel-scrim. And the app track's error notice used a hardcoded #F0A79F with no light variant, measuring 1.89:1 in light, now the themed --st-fault. Confirmed zero horizontal overflow on every page at 375, 768, 1024 and 1440. The run-target group was clipped at 375 by the composer box's overflow, putting node-03 out of reach; it now wraps to two rows with every destination pickable. Verified the collapse in the browser on both tracks: tracks measure 0px, panels take visibility:hidden so they leave the tab order, main widens from 950px to 1425px, aria-expanded tracks state, and the choice persists. Verified the overlay and scrim at 375, and that IBM Plex Sans actually loads.
- remaining: The application still has no coordinator running in this environment — no Python on the machine — so the palette and the collapse were verified against the app's own static shell and its synthetic fixture page, not against live coordinator data. Screen readers, keyboard traversal order and browsers other than Chromium remain unverified, as before. backdrop-filter frame rate on low-end hardware is still unmeasured. Fonts still load from Google Fonts in the design track and must be self-hosted before any offline build. No Git writes ran.

<a id="ac-20260905-002"></a>
## AC-20260905-002 — Supplied Refinix lockup on every application surface, site left drawn
- prompt_id: [UP-20260905-002](userprompts.md#up-20260905-002)
- date: 2026-09-05
- agent: Claude
- status: implemented
- tags: refinix, brand, logo, wordmark, brand-strip, contrast-audit
- aliases: raster lockup in nav, brand-ground both themes, brand-tag token, drawn stand-in removed
- paths: frontend/design/assets/refinix-wordmark.png, frontend/design/assets/refinix-mark.png, frontend/design/assets/README.md, frontend/design/tokens.css, frontend/design/app.css, frontend/design/onboarding.css, frontend/design/chat.html, frontend/design/code.html, frontend/design/control.html, frontend/design/documents.html, frontend/design/onboarding.html, frontend/design/onboarding-install.html, frontend/design/pairing.html, frontend/app/app.css, frontend/app/refinix.css, agent-memory/
- summary: Replaced the drawn stand-in symbol and text wordmark with the supplied brushed-metal REFINIX lockup across all seven design-track application surfaces, on a brand strip that keeps its near-black ground in both themes.
- changes: The design track drew the lockup because the supplied artwork is a raster on a black square and a baked-in black block shows as a rectangle on a light theme — true for the public site, but not for an application surface that owns the ground behind the mark. frontend/app had already solved this in refinix.css with a strip that keeps a near-black ground in both themes; the design track now matches it rather than diverging. Copied refinix-wordmark.png and refinix-mark.png from frontend/app/assets, which scripts/build-brand-assets.py already crops from the two masters in assets/Brand, so both tracks show one mark from one source. Removed the drawn SVG symbol and the <b>Refinix</b> text from all seven pages — five .nav-brand surfaces and the two .setup-brand onboarding rails, whose strip is bled back out to the rail edges with negative margins so it reads as a strip and not a floating plate. Moved --brand-ground and --brand-edge out of refinix.css into tokens.css, declared outside the theme blocks because being identical in every theme is the point, and deleted the duplicate declarations from refinix.css so one mark has one source of truth. Added --brand-tag at #8A8A8A for the build tag beside the lockup: anything on that strip is measured against #050505 and not against the theme's ground, so --text-faint would have been a dark grey there in light mode. site.html was deliberately not touched — it has a genuinely light surface with no strip to sit a mark on, so its drawn lockups remain correct; assets/README.md now records the split and why, and its stale claim that the application surfaces reference the symbol by name was corrected.
- verification: Confirmed the image loads and renders 127x24 on a 245px strip with ground rgb(5,5,5) and tag rgb(138,138,138), no overflow. Re-ran the compositing contrast auditor after the token change on Chat, onboarding and pairing in dark and light at 1440x900: zero failures, floors unchanged at 5.49/5.22/4.86 dark and 4.57/5.13 light. Checked the running application separately: brand strip resolves to rgb(5,5,5) with a rgb(36,36,36) edge from the relocated tokens, logo loads, zero failures, floor 5.63. Checked 375px with the navigation open as an overlay: no page overflow, logo does not overflow its strip. Confirmed no drawn brand SVG remains on any page but site.html, and that frontend/app/app.css is still an exact concatenation of the four design files.
- remaining: The lockup is a raster on an opaque ground, so it can only ever sit on the brand strip; a transparent export would let it sit on any surface and is still worth having. The application still has no coordinator running here, so this was checked against the static shell. Screen readers, keyboard traversal and non-Chromium browsers remain unverified. No Git writes ran.

<a id="ac-20260905-003"></a>
## AC-20260905-003 — Failure red moved to dark wine, one token per track
- prompt_id: [UP-20260905-003](userprompts.md#up-20260905-003)
- date: 2026-09-05
- agent: Claude
- status: implemented
- tags: refinix, palette, fault, wine-red, contrast-audit, accessibility
- aliases: st-fault wine, danger wine, diff removed lines, error notice colour, hue 349
- paths: frontend/design/tokens.css, frontend/design/site.css, frontend/app/app.css, agent-memory/
- summary: Every failure and error red is now a dark wine at hue 349 degrees, changed at the two tokens that already carried it rather than at any of the fourteen places that use them.
- changes: Confirmed first that every red in the product already routes through one token per track — --st-fault in the application palette and --danger on the public site — so this was a two-value change, not a sweep. The application's fourteen consumers all inherit it: the fault chip, the deny button, the stop button, the failed ready-line, the attachment remove hover, the error notice, the danger row-menu item, the diff's removed lines and the run output's bad rows. LIGHT gets a literal dark wine, #6E2230, measuring 10.5:1 on the raised surface and 7.99:1 on the sunken one. DARK could not take the same value: #6E2230 on the near-black ground measures about 2:1 and is unreadable, so dark keeps the hue and lifts the luminance to #CC6B7D, which clears the floor at 4.89:1 on the raised panel and 5.63:1 on the base ground. That is still a real change rather than a darkening — the previous dark value, #F0908A, sat at hue 3.5 degrees, which is an orange-red salmon; both new values sit at 349 degrees, a blue-leaning wine. The public site's --danger took the same two values in its own dark and light blocks. The palette doctrine at the top of tokens.css was rewritten: it had described the fault colour as "red-clay" and had claimed the diff was left alone as an exception, when the diff in fact spends the palette's own fault and enforced tokens — it keeps the notation, not a separate pair of colours.
- verification: Re-ran the compositing contrast auditor after the change. Code surface, where the diff is the largest block of red: zero failures in both themes, floor 5.28 dark and 4.57 light, with the removed lines measured at rgb(204,107,125) and rgb(110,34,48). Application fixture page, which carries the error notices and a fault chip: zero failures, floor 4.89 dark and 4.81 light, notice and chip both resolving to the wine. Public site: the diff's removed line measures rgb(204,107,125) on its rgb(7,7,8) ground in dark and rgb(110,34,48) in light, and no failure on that page carries either wine value. Swept every hex in every stylesheet by computed hue and saturation to confirm no reddish literal survives outside the two tokens; the only hit left is a hex inside an explanatory comment, not a live declaration. Confirmed frontend/app/app.css is still an exact concatenation of the design track.
- remaining: The site carries fifteen pre-existing contrast failures unrelated to this change and not touched by it: a grey, rgb(118,124,133), measuring 4.2:1, and the gradient-clipped wordmark text, which reports as transparent because the auditor cannot measure background-clip:text and is a false positive rather than a defect. The site's light theme is gated only on an explicit data-theme attribute, not on prefers-color-scheme, so it cannot be exercised by system preference. No Git writes ran.

<a id="ac-20260905-004"></a>
## AC-20260905-004 — Site --ink-faint raised; both themes now clear 4.5:1 on real text
- prompt_id: [UP-20260905-004](userprompts.md#up-20260905-004)
- date: 2026-09-05
- agent: Claude
- status: implemented
- tags: refinix, site, contrast, accessibility, ink-faint, gradient-text
- aliases: 767C85 raised, 888E97, faint tier, background-clip text measurement
- paths: frontend/design/site.css, agent-memory/
- summary: Raised the public site's dark-theme faint text tier from #767C85 to #888E97, taking its worst real case from 3.77:1 to 4.80:1, and measured the remaining reported failures to establish which are genuine.
- changes: The failure was one token, --ink-faint in the site's dark block, feeding 22 declarations and 34 rendered elements: file sizes, terminal tab and copy controls, terminal comments, event sources, key/value labels, the diff's context lines, demo captions, stat annotations and build requirements. The reported 4.2:1 was not the worst case — that was 3.77:1 on the file-size span, which sits on a nested card compositing to rgb(34,34,35) rather than on the page ground, so the binding surface is lighter than the page. #888E97 keeps the palette's cool cast and moves only luminance, so the tier still reads a clear step below --ink-dim at #9AA0A8. The light block's --ink-faint at #5E6A78 was measured and already passes, so it was left alone.
- verification: Confirmed the fix with a focused probe over every element resolving to the new colour: 34 elements, all pass, worst 4.80:1, up from 3.77:1. Ran the full compositing auditor on the site in both themes, driving the theme through the page's own toggle rather than by setting the attribute — setting data-theme directly leaves descendants reporting stale computed colours in this environment, which had made an earlier light-theme reading unreliable. Both themes now report zero failures on ordinary text. The ten remaining reported items are all background-clip:text elements whose computed colour is transparent, so they were measured separately by evaluating each gradient stop against the ground: the metal wordmark spans 1.43:1 to 20.14:1 in dark and 3.48:1 to 15.12:1 in light, and the tagline words span 3.63:1 to 11.44:1 in light. The low end is the ramp's shadow band, which is what makes the type read as brushed metal; the majority of every glyph is far above threshold. That is a deliberate brand treatment rather than a defect, and it was left unchanged.
- remaining: The metal ramps' darkest and lightest bands sit below threshold as described above; tightening them is a brand decision, not a bug fix, and was not taken unilaterally. The site's light theme is still gated only on an explicit data-theme attribute and never activates from prefers-color-scheme. No Git writes ran.

<a id="ac-20260905-005"></a>
## AC-20260905-005 — Metal ramps narrowed, an invisible intro lockup fixed, auditor taught to read clipped text
- prompt_id: [UP-20260905-005](userprompts.md#up-20260905-005)
- date: 2026-09-05
- agent: Claude
- status: implemented
- tags: refinix, site, contrast, accessibility, gradient-text, metal-ramp, intro-gate, auditor
- aliases: background-clip text measurement, silver-3 silver-4, intro gate black in both themes, wordmark invisible in light
- paths: frontend/design/site.css, agent-memory/
- summary: Narrowed both brushed-metal ramps so every band of a clipped letterform is readable, found and fixed a lockup that was effectively invisible on the intro gate in light mode, and upgraded the contrast auditor to measure clipped-to-text gradients rather than skip them.
- changes: Clipped-to-text gradients are still text, and a reader has to resolve the whole letterform rather than its darkest band, so every stop must clear threshold. Dark ramp: the fold ran down to #262C32 at 1.43:1, which made the middle of every glyph an unreadable band; the fold is kept but shallowed to #757B84 at 4.72:1, and the 60% stop lifted from #6E777F, which was 4.42:1, to #7C838C. Light ramp: on a pale ground the ceiling fails rather than the floor, so #79818A at 3.48:1 and #6B737C at 4.24:1 became #626A74 and #5C646E. Two shared tokens also carried failures into .formula b and .stat b and were moved with them: dark --silver-4 from #5A616A at 3.21:1 to #797F88, and light --silver-3 from #767E88 at 3.63:1 to #616A74. The type reads as brushed aluminium rather than dark steel now, which is the cost of the fix and is stated in the stylesheet.
  A separate and worse defect surfaced while verifying: .intro is background #000 in BOTH themes — it is a black curtain, not a page surface — but the light theme applied its two pale-ground adjustments inside it, running the dark metal ramp and a brightness(.62) filter over black. The lockup on the intro gate measured 1.23:1 in light mode: the first screen every visitor sees had an invisible mark. Both adjustments are now scoped out of .intro, with the metal-on-black ramp written out literally there because the silver tokens resolve to their light values inside a light root.
- verification: Upgraded the auditor first, since the old one reported clipped text as transparent and so could not see any of this: it now detects background-clip:text, measures every gradient stop against the backdrop, takes the worst, and excludes the element's own gradient from its own backdrop. Re-swept all twelve pages — seven design surfaces, the public site, and four application pages — in dark and light. Zero failures everywhere. Design floors 4.74 to 5.49 dark and 4.57 to 5.90 light; application floors 4.89 to 5.68 dark and 4.81 to 5.56 light; site 4.38 dark and 4.84 light, the sub-4.5 floors being large text measured against the 3:1 threshold. Confirmed no horizontal overflow. Verified the intro fix directly by forcing the gate visible in each theme and measuring its lockup: worst stop 4.92:1 in both, against 1.23:1 before in light, with the mark keeping its metal-on-black drop shadow rather than the darkening filter.
- remaining: One thing was deliberately not changed. The site's light theme is still reachable only through its own toggle and never from prefers-color-scheme, unlike the application, whose tokens.css requires three theme states. Wiring the site to system preference means removing the hardcoded data-theme="dark" from the markup and restructuring roughly forty tokens into a media query, and it changes what every visitor on a light system sees by default. That is a product decision about the public site's first impression rather than a defect, so it is recorded here rather than taken unilaterally. No Git writes ran.

<a id="ac-20260905-006"></a>
## AC-20260905-006 — Denied isolation probe accepts rejection as policy enforcement
- prompt_id: [UP-20260905-006](userprompts.md#up-20260905-006)
- date: 2026-09-05
- status: source and offline checks passed; Ubuntu re-run and requester acceptance pending
- scope: c05, correction, network-policy, checks, documentation
- tags: c05, netpolicy, kube-router, blocked-by-policy, exit-codes, allowed-first
- aliases: connection refused counted as failure, denied probe exit 7, reject icmp-port-unreachable, paired probe gate
- paths: deploy/k3s/checks/netpolicy-denied.yaml, deploy/k3s/checks/netpolicy-allowed.yaml, deploy/k3s/test_manifests.py, docs/c05-ubuntu-deployment-handoff.md, agent-memory/
- summary: Corrected the denied probe's false assumption that a NetworkPolicy denial must time out, so K3s kube-router's immediate rejection is scored as enforcement rather than a step G failure.
- changes: In `netpolicy-denied.yaml` both `timeout` exit 124 and `Connection refused` now emit the stable `RESULT=blocked-by-policy` prefix with the observed mechanism in parentheses and exit 7; `PONG` stays `RESULT=POLICY-NOT-ENFORCED` exit 1, and DNS, credential, authentication, protected-mode, empty-output, tooling and other errors keep their distinct non-zero codes. Its header states that the probe is valid only after the allowed half proves the same Service and credential work. `netpolicy-allowed.yaml` is unweakened — comments only: refusal there stays `RESULT=refused` exit 9, because refusal on the permitted path means an unavailable Service. In `test_manifests.py` the over-general assertion requiring both probes to carry identical `timeout-or-blocked`/`refused` strings was narrowed to the modes that mean the same thing on both paths, and a new `TestDenialMechanisms` asserts denied timeout and denied refusal each give a blocked result at exit 7 under one parenthesised prefix, denied PONG gives POLICY-NOT-ENFORCED exit 1, non-network errors never score as denials, allowed refusal stays exit 9 with no denial success case, and the allowed-first pairing is documented in both files. Step G of the handoff now tables both mechanisms under exit 7, makes the allowed probe a stop-if-it-fails gate, and records the observed Ubuntu run.
- review_fixes: `unittest.main()` sat above two thirds of the classes, so the documented `python3 -B deploy/k3s/test_manifests.py` silently ran 16 of 48 tests and would have reported a pass without executing the new assertions. Moved the entry point to the end of the file; no test body was changed to accommodate it.
- verification: Ran `python3 -B deploy/k3s/test_manifests.py`: 55 tests, OK — up from 16 executed before the entry-point fix. Confirmed the two new refusal assertions fail against the pre-correction branch and pass after it, using a scratch copy outside the repository. `git diff --check` clean.
- remaining: Re-running step G on the Ubuntu worker and requester acceptance. The corrected classification is verified statically only — no cluster, kubectl, network call or credential access occurred here, and the recorded rejection rule comes from the requester's transcript, not from a command run in this session. The iptables packet counter is explicitly not treated as evidence of the denied attempt. `tasks.md` and the execution-state table are untouched by request; no Git writes, installs or deployments ran, and every unrelated dirty hunk was preserved.
## AC-20260905-006 — Code surface and composer controls brought onto the design system, no logic touched
- prompt_id: [UP-20260905-006](userprompts.md#up-20260905-006)
- date: 2026-09-05
- agent: Claude
- status: implemented
- tags: refinix, design-integration, code-surface, composer, floating-surfaces, palette, contrast-audit
- aliases: app-plain rail wrap, rail-toggle icon, font-mono undefined, plus-menu model-popover row-menu glass, mp-switch green, lbl misuse, composer bar heights
- paths: frontend/app/code.html, frontend/app/refinix.css, frontend/app/overrides.css, agent-memory/
- summary: Presentation-only pass over the newly landed Code surface and composer controls: fixed a broken three-column layout, replaced an orphaned text button with the panel control, repaired a font token that resolved to nothing, unified three different floating-surface treatments, corrected one palette misuse and evened the composer bar. app.js was not touched.
- changes: A real layout break first. code.html gained a .rail but kept class "app app-plain", which declares only two grid tracks — the rail had no column and wrapped underneath the navigation, stacking the audit list and the unavailable list below the sidebar. Dropping app-plain restores three tracks; control.html keeps it, correctly, because it still has no rail.
  The rail control on that page was a bare text button reading "Details", left over from the drawer this session replaced; its .rail-toggle class no longer had any CSS, so it rendered unstyled. It is now the same three-line panel-toggle every other surface carries, keeping its id and aria-controls so the existing wiring finds it unchanged.
  Four rules set font-family to var(--font-mono, ...) — a token this system does not define — so the diff, the model name, the diff path and the popover name all silently fell back off IBM Plex Mono onto a generic stack. They now use --font-data, which is the real token.
  Three families of floating surface had arrived with three appearances: the + menu and its mode and file variants, the model and context popovers, and the conversation row menu, carrying 6px and 13px radii, two hand-written shadows and two different border tokens. A menu and a popover opened from the same composer did not look related. They now share one rule using the glass treatment app.css already defines for things that float, since that is exactly what they are.
  One palette misuse: the reasoning toggle used --st-enforced when on. Green in this palette means a named control is active or a step completed; a live setting is what the sky accent is for, and spending green there made "reasoning is on" read as an enforcement claim. It is now --signal.
  One readability fix: a full sentence in code.html was set in .lbl, which is a 10px uppercase mono micro-label. It now uses a .prose-note style — quieter than the paragraph above it but still body copy — so .lbl keeps meaning "machine-side label" everywhere.
  Finally the composer bar, whose controls arrived at three heights: the + button at 30px, the mode, model and context pills at 27px and Send, Stop and Propose at 33px, reading as three rows compressed into one. All now sit on a 30px baseline. Shape stays deliberately split — pill for a setting you choose, button radius for an action you take — so the row scans as settings on the left and actions on the right.
- verification: Confirmed app.js has no diff at all: every change is CSS plus three presentational edits in code.html — a layout class, a button's appearance with its id and aria-controls preserved, and a text style class. Verified the regression risk directly: the rewritten rail toggle still opens and closes, aria-expanded tracks it, and the track collapses to 0px and returns to 244px. Measured the composer bar on both Chat and Code with the hidden controls revealed: every control 30px, all equal. Confirmed the three floating surfaces now resolve to one treatment — 18px radius, glass fill, blur and the shared shadow tokens — and that the reasoning toggle resolves to the sky accent. Confirmed the diff now resolves to IBM Plex Mono and .prose-note to 14.26px sans with no uppercase transform, against 10px uppercase mono before. Ran the compositing contrast auditor over Code, Chat, Settings and the fixture in dark and light at 1440, and Code again at 375: zero failures everywhere, floors 4.89 to 5.68 dark and 5.56 light, no horizontal overflow, and the grid correctly collapsing to a single column at 375.
- remaining: Screenshots could not be captured — the preview pane cannot paint while the host window is minimised, so this pass was verified by computed-style and geometry measurement rather than visually. The dynamic parts of the Code surface (repository list, proposed diffs, approval cards, the file and mode menus) never render without a coordinator, so their styling was checked by instantiating the classes and by revealing the hidden controls, not by exercising a real job. A visual pass over those states is still worth doing once a backend is running. No Git writes ran.

<a id="ac-20260905-007"></a>
## AC-20260905-007 — C06 distributed execution implemented; C07 fixtures and C08 dependency plan prepared
- prompt_id: [UP-20260905-007](userprompts.md#up-20260905-007)
- date: 2026-09-05
- status: implemented and offline-checked; every device gate outstanding
- scope: c06, c07, pairing, redis, executor, routing, fixtures, documentation
- tags: c06, c07, af-005, af-006, af-007, od-06, pairing, redis-streams, executor, tls-pinning, fixtures
- aliases: durable receipt, blocked no more, pair the two devices, route reason, truthful fallback, pumpcheck fixture
- paths: backend/worker/, backend/coordinator/, deploy/k3s/, fixtures/c07/, frontend/app/, docs/, agent-memory/
- summary: Replaced the fail-closed job gate with real OD-06 pairing and a Redis Streams receipt, added an executor Pod and coordinator routing with truthful fallback, and prepared the C07 fixture pack and C08 dependency plan.
- changes: New `worker/pairing.py` issues single-use expiring codes and per-relationship credentials, storing only salted SHA-256 hashes at mode 0600 and bumping a fence epoch on revocation; `worker/pairing_cli.py` prints the certificate fingerprint and mints a code without logging either. New `worker/redis_client.py` is a bounded stdlib RESP2 client, chosen over redis-py so the pinned image lock and provenance are unchanged. New `worker/dispatch.py` writes the validated envelope to the dispatch stream before the 202, keeps idempotency in Redis, and replays stored events or reports `events_expired`. New `worker/executor.py` recovers abandoned entries, claims a lease with SET NX, heartbeats, polls cancellation and revocation, and leaves work recoverable when killed. `worker/app.py` now separates preflight authority (bootstrap token) from job authority (relationship credential), implements both pairing routes, and reads attempt state from the executor's event log; its local execution path was removed rather than duplicated, and its streaming/budget/cancellation checks moved to the executor tests. New coordinator `pairing.py` pins the certificate as sole trust anchor, compares the presented leaf digest, and keeps the credential in the Keychain only; new coordinator `dispatch.py` decides the route with a stated reason, builds the envelope, and re-validates every remote record. `server.py` routes chat to a paired healthy worker, falls back locally with a new attempt and a visible reason, and refuses outright on an identity mismatch. `db.py` schema 7 adds a relationships table holding no secret plus attempt fencing. Manifests add `40-executor.yaml` (no Service, no ingress, same image), a worker PVC, a TLS Secret mount and uvicorn TLS termination. `fixtures/c07/` adds a synthetic inspection report, SOP, expected facts/missing/uncertainty/citations, a deliberately broken stdlib-only Python repository, and SHA-256 provenance.
- review_fixes: A self-review found and fixed two real defects. A Redis loss mid-attempt raised out of the executor and skipped its lease release; emits now degrade to `interrupted` and the entry stays recoverable. The Control Center's pairing and revoke calls passed a payload where `api()` expects fetch options, so they were sent as GETs with no body. Separately, the four browser-side suites were failing 50 of 60 checks on HEAD because the Node harness lacked a `window.matchMedia` stub, which made any frontend change unverifiable; the harness was stubbed and all 60 pass again. No application behaviour was changed to accommodate a test.
- verification: Ran 495 Python checks — contracts 8, coordinator 31/28/13/35/80/82/19, new dispatch 40, new executor 40, worker runtime 10, C07 fixtures 19, manifests 65, guard 25 — all OK. Ran 72 browser-side checks across five suites, all pass, including a new `test-control-centre.cjs`. `git diff --check` clean; every changed Python and JavaScript file compiles. Redis, TLS, the Keychain and Kubernetes are stateful fakes or fake connections throughout and are NOT reported as live proof. `backend.worker.test_worker_app` could not run here — FastAPI exists only inside the pinned image — so it is unrun and executes at image build time.
- remaining: Every C06 device gate: the Ubuntu C06 image build and its digest (both manifests still carry the C04 placeholder and say so), source transfer, deployment, certificate generation, pairing, the LAN firewall change, real distributed inference, cancellation and disconnect recovery — all in docs/c06-distributed-execution-handoff.md. C07 device setup and acceptance stay blocked until C06 passes; docs/c08-dependency-plan.md installs nothing. tasks.md is not updated and no chunk is marked verified. No Git write, install, download, deployment, host change, model call or network request occurred.

<a id="ac-20260905-008"></a>
## AC-20260905-008 — Eight C06/C07 review findings repaired
- prompt_id: [UP-20260905-008](userprompts.md#up-20260905-008)
- date: 2026-09-05
- status: implemented and offline-checked; every C06/C07 device gate outstanding
- scope: c06, c07, review-fixes, exposure, redis, executor, fixtures, ui
- tags: c06, c07, review-fixes, nodeport, socket-proxy, event-replay, restart-recovery, atomic-receipt, lease-fencing, raster-scan, self-test
- aliases: dnat cannot be filtered by input, wait for terminal state, receipt unknown, duplicate delivery, synthetic scan, guided self-test
- paths: backend/worker/, backend/coordinator/, deploy/k3s/, fixtures/c07/, frontend/app/, docs/, agent-memory/
- summary: Repaired all eight findings — the NodePort is no longer widened, the setup order is executable, event consumption waits for a terminal state, the worker keeps no attempt state in process, receipts commit atomically, lease and acknowledgement semantics are safe against duplicates, a raster scan fixture exists, and AF-007's self-test runs the real path.
- changes: (1) The handoff no longer changes `nodeport-addresses`; it stays `127.0.0.1/32` and a new `worker` guard plus `aegisforge-worker-proxy` socket/service put a TLS-passthrough `systemd-socket-proxyd` listener on the LAN address, permitting one `AEGIS_MAC_ADDRESS` and refusing to apply without it. IPv6 stays dropped. (2) The handoff was rewritten in dependency order — addresses, TLS, image, worker API, forwarder, pair, relationship ID, executor, acceptance — because the executor needs an ID pairing mints and pairing needs the port open. (3) `/v1/jobs/{job}/events` now holds the connection and re-reads the log until a terminal state, the attempt deadline, an idle limit or a cancellation; an admitted attempt with no events is not `events_expired`. `consume` reconnects from the last sequence rather than treating a cut stream as an outcome. (4) The worker's `_attempts` dictionary is gone: `find_attempt` reads the dispatch stream, capacity comes from `active_attempts`, and poll/events/cancel authorise from Redis. (5) `XADD` and the accepted receipt commit in one `EVAL`; the coordinator reuses one key per attempt and treats a post-send transport failure as `ReceiptUnknown`, which never falls back. (6) Heartbeat and release are atomic owner-checked scripts; a terminal event is the done marker, checked before running and required before acknowledging. (7) `fixtures/c07/make_scan.py` generates a deterministic three-page raster PDF with no text layer, recorded with method, tool versions, hash and size. (8) A Control Center self-test runs the ordinary submit path and reports each attempt's route reason; Pod readiness stays unavailable with its reason.
- review_fixes: Two further defects were found by the new checks. `consume` started from `StreamOutcome`'s default state of `interrupted`, which is terminal, so the loop exited before the first event; it now starts from `queued`. `submit` refused a legitimate retry with `idempotency_conflict` before reaching the replay path, turning the retry idempotency exists for into a 409; the pre-check is removed and duplicate suppression is the executor's lease and terminal marker.
- verification: 591 Python checks and 78 browser-side checks, all passing. New or grown: coordinator dispatch 45, worker executor 59, guard 44, C07 fixtures 32, Control Center 18. `backend.worker.test_worker_app` was previously unrun; its 40 checks now pass against a clearly labelled minimal stand-in for FastAPI that exercises route logic only — the authoritative run remains the image build, and the stub is not evidence the service works. Redis, TLS, the Keychain, Kubernetes and iptables are fakes throughout and are not reported as live proof. `git diff --check` clean; all Python compiles, all JavaScript parses, the guard script passes `sh -n`.
- remaining: Every C06 device gate in the rewritten handoff, in order: the Ubuntu C06 image build and digest (both manifests still carry the C04 placeholder), TLS generation, worker-API deployment, the LAN forwarder, pairing, the relationship-ID patch, executor deployment, and the six acceptance checks including the new API-restart one. C07 device setup and acceptance stay blocked until C06 passes; no OCR is implemented and `docs/c08-dependency-plan.md` installs nothing. tasks.md is untouched and no chunk is marked verified. No Git write, install, download, deployment, host change, model call or network request occurred.

<a id="ac-20260905-009"></a>
## AC-20260905-009 — Five C06 safety boundaries closed
- prompt_id: [UP-20260905-009](userprompts.md#up-20260905-009)
- date: 2026-09-05
- status: implemented and offline-checked; the C06 Mac/Ubuntu gate remains unrun
- scope: c06, review-fixes, dispatch-ambiguity, pending-recovery, self-test, image-build
- tags: c06, receipt-unknown, ambiguous-commit, xautoclaim, xack, self-test-verdict, dockerfile
- aliases: atomic mutation is not client knowledge, sent flag set too late, ack destroys the pending entry, local rescue is not a distributed pass
- paths: backend/worker/dispatch.py, backend/worker/executor.py, backend/coordinator/dispatch.py, backend/coordinator/server.py, backend/worker-image/Dockerfile, agent-memory/
- summary: Split dispatch failures into definite and unknown, moved the HTTP ambiguity boundary to the connect edge, stopped a recovering executor acknowledging an entry its live owner still holds, required a relationship-bound completion for a distributed self-test pass, and added the executor suite to the image build.
- changes: `DispatchQueue.enqueue` is now two phases. A reservation failure is definite (`redis_lost`); a commit failure resolves against the dispatch stream and the receipt, returning 202 when the entry is there, refusing only when the receipt still reads `reserved` — the atomic script writes both, so an unadvanced receipt proves the XADD did not run — and otherwise raising `internal_error`, which is outside the coordinator's `DEFINITE_REFUSALS` and becomes `ReceiptUnknown`. `_replay_receipt` no longer reports an in-flight reservation as definite. `WorkerClient.submit` dropped its `sent` flag: `HTTPConnection.request` performs the transmission and can raise mid-write, so everything after a successful connect is ambiguous, while connect failures and typed 4xx/definite-5xx refusals stay definite. `Executor._handle` no longer acknowledges when `claim` fails — `XAUTOCLAIM` transfers the single pending entry rather than copying it, so that XACK removed the group's only record of work a live owner was still running; the entry now stays pending and its reset idle timer keeps the loop from spinning. `selftest_result` requires a relationship-bound attempt to have reached `completed` and reports `fell_back` separately. The Dockerfile's offline test stage now runs `backend.worker.test_executor` alongside the application suite.
- verification: 623 Python checks and 78 browser-side checks pass — coordinator dispatch 67 and worker executor 69, both grown by the new regressions. Each fix was confirmed load-bearing by reverting it and observing the matching regression fail: a committed-but-unacknowledged Redis reply, a POST raising during transmission, an auto-claimed entry meeting a live owner and remaining recoverable after that owner disappeared, a remote interruption rescued locally, and the Dockerfile omission. `git diff --check` clean; all Python compiles, all JavaScript parses, the guard script passes `sh -n`. Redis, TLS, the Keychain, Kubernetes, iptables and the Docker image are fakes or source inspection throughout and prove none of those behaviours.
- remaining: The whole C06 device gate in docs/c06-distributed-execution-handoff.md, unchanged and unrun: image build and digest, TLS, worker API, LAN forwarder, pairing, relationship ID, executor, and the six acceptance checks. C07 preparation is untouched. tasks.md is not updated and no chunk is marked verified. No Git write, image build, install, deployment, host change, model call or network request occurred.

<a id="ac-20260905-010"></a>
## AC-20260905-010 — Distributed self-test requires canonical job completion
- prompt_id: [UP-20260905-010](userprompts.md#up-20260905-010)
- date: 2026-09-05
- status: implemented and focused-check passed; C06 device gate remains unrun
- scope: c06, self-test, review-fix
- tags: c06, self-test-verdict, canonical-job, regression
- aliases: completed remote attempt with failed job, self-test false positive
- paths: backend/coordinator/server.py, backend/coordinator/dispatch.py, backend/coordinator/test_dispatch.py, agent-memory/
- summary: A distributed self-test now passes only when both the canonical job and a relationship-bound attempt complete.
- changes: Restored canonical job completion to the pass predicate, added the failed-job regression, and aligned the HTTP submission docstring with its conservative ambiguity boundary.
- verification: `.venv/bin/python -B -m unittest backend.coordinator.test_dispatch` passed 68 tests; `git diff --check` passed. The system Python attempt did not execute tests because it lacks Pydantic.
- remaining: The C06 image build and all Mac/Ubuntu device gates remain unrun. No Git write, build, install, deployment or device action occurred.

<a id="ac-20260905-011"></a>
## AC-20260905-011 — Worker image build no longer exposes test identity values
- prompt_id: [UP-20260905-011](userprompts.md#up-20260905-011)
- date: 2026-09-05
- status: implemented; Ubuntu rebuild pending
- scope: c06, dockerfile, secrets, image-build
- tags: c06, dockerfile, credentials, image-build, test-boundary
- aliases: dummy token in build history, coordinator import missing, Ubuntu C06 build failure
- paths: backend/worker-image/Dockerfile, backend/worker/test_executor.py, agent-memory/
- summary: Removed fixed test identity values from the Docker build command and removed a redundant worker test dependency on coordinator-only source.
- changes: The image build now invokes the offline suites without inline token or node-ID values; `test_worker_app` continues to install its own non-secret fixtures before importing the guarded app. The redundant cross-package assertion was removed from `test_executor`; the coordinator suite already exercises `internal_error` as receipt-unknown and `redis_lost` as definite.
- verification: Source inspection confirmed runtime credentials remain `secretKeyRef` values, TLS remains in the `worker-tls` Secret, and no Dockerfile token or node-ID value remains. No tests or image build were run locally; the Ubuntu rebuild is authoritative.
- remaining: Commit and push these two source corrections, pull them on Ubuntu, then rerun the C06 image build. All later C06 device gates remain pending.

<a id="ac-20260905-012"></a>
## AC-20260905-012 — Observed C06 image digest pinned
- prompt_id: [UP-20260905-012](userprompts.md#up-20260905-012)
- date: 2026-09-05
- status: implemented; source push and deployment pending
- scope: c06, image-digest, manifests, provenance, handoff
- tags: c06, ubuntu, image-digest, containerd, provenance, deployment
- aliases: daf1052b, single manifest, digest alias, pin C06 image
- paths: backend/worker-image/provenance.json, deploy/k3s/20-worker.yaml, deploy/k3s/40-executor.yaml, deploy/k3s/test_manifests.py, docs/c06-distributed-execution-handoff.md, agent-memory/
- summary: Pinned the Ubuntu-built C06 worker image manifest in both deployments and recorded only the artifact evidence actually observed.
- changes: Worker and executor now pin `sha256:daf1052b...`; provenance records its observed config digest, successful offline build layer and streamed import while leaving unavailable archive fields null. The handoff now disables provenance/SBOM attestations for one Linux manifest and creates the explicit containerd digest alias used by the manifests.
- verification: Requester output showed the single-manifest build, `sha256:daf1052b...` tag and explicit digest alias in K3s containerd. Source consistency and `git diff --check` were checked locally; no deployment or runtime test was run by Codex.
- remaining: Push this source update, pull it on Ubuntu, then deploy only the worker API and prove loopback TLS before opening the guarded LAN forwarder. The executor remains blocked until pairing creates the relationship ID.

<a id="ac-20260905-013"></a>
## AC-20260905-013 — Non-root worker can read its mounted TLS identity
- prompt_id: [UP-20260905-013](userprompts.md#up-20260905-013)
- date: 2026-09-05
- status: implemented; Ubuntu rollout retry pending
- scope: c06, kubernetes, tls, permissions, rollout
- tags: c06, kubernetes, tls, fsgroup, non-root, crashloopbackoff
- aliases: uvicorn permission denied, tls key unreadable, C06 pod crash
- paths: deploy/k3s/20-worker.yaml, deploy/k3s/test_manifests.py, agent-memory/
- summary: Assigned the worker Pod's volumes to its existing GID so Uvicorn can read the TLS key without making it world-readable.
- changes: Added pod-level `fsGroup: 10001`, matching the repository's Redis secret-volume pattern, and a focused assertion pairing it with secret mode `0440`.
- verification: Requester logs proved `PermissionError` at Uvicorn `load_cert_chain`; pod events proved the pinned C06 image was present. `git diff --check` passed locally; no test or deployment was run by Codex.
- remaining: Push and pull the two-file source fix plus ledger entries, rerun the manifest suite, and reapply only `20-worker.yaml`. Keep the executor undeployed until pairing produces its relationship ID.

<a id="ac-20260905-014"></a>
## AC-20260905-014 — Worker guard accepts packet-rule NodePort implementations
- prompt_id: [UP-20260905-014](userprompts.md#up-20260905-014)
- date: 2026-09-05
- status: implemented; Ubuntu guard installation pending
- scope: c06, k3s, nodeport, systemd, handoff
- tags: c06, k3s, nodeport, systemd, socket-proxy, runtime-evidence
- aliases: empty ss, packet-rule NodePort, guard precheck timeout, TLS curl root certificate
- paths: deploy/k3s/host/aegisforge-worker-guard.service, deploy/k3s/host/test_guard.py, docs/c06-distributed-execution-handoff.md, agent-memory/
- summary: Deleted the invalid `ss` listener wait while retaining the firewall guard as a hard dependency of the LAN socket.
- changes: The worker guard now applies its scoped rules as soon as K3s is active. The handoff records that `ss` may be empty for a packet-rule NodePort, uses the successful TLS request as functional proof, reads the root-only certificate via root curl without exposing the token, and expects only the LAN proxy to appear as a process listener.
- verification: Requester output showed empty `ss`, loopback-only K3s configuration, an authenticated pinned-TLS Node response, and plaintext rejection with exit 52. `git diff --check` passed locally; no systemd unit was installed or started by Codex.
- remaining: Push and pull this correction, install the worker guard/proxy units with the observed addresses, then verify the rules, LAN listener and Mac-only reachability before pairing.

<a id="ac-20260905-015"></a>
## AC-20260905-015 — C08 Documents, C09 distributed Code and C10 evidence, source and macOS artifact
- prompt_id: [UP-20260905-015](userprompts.md#up-20260905-015)
- date: 2026-09-05
- status: implemented; every C06–C10 human runtime gate still pending
- scope: c07, c08, c09, c10, documents, code, sandbox, approvals, proof, artifacts
- tags: c08, c09, c10, quartz, ocr, resource-package, kubernetes-job, rbac, approvals, proof-cards
- aliases: paddleocr vl no vision, scan rendering, validation job, durable write recovery, af-008 af-014
- paths: backend/coordinator/, backend/worker/, deploy/k3s/, frontend/app/, desktop/setup_py2app.py, docs/, tasks.md, README.md
- summary: Implemented C08 local Documents/OCR, C09 packaged remote code generation with a restricted Kubernetes validation Job, and C10 concurrency, approval binding, durable final writes and Proof Cards.
- changes: New `pdfrender`/`ocr` render and read scan pages through the existing Ollama adapter, which now requires an OBSERVED `vision` capability before sending an image. New worker `packages`/`codegen`/`kube`/`jobspec`/`validate` carry a bounded idempotent JSON package and run one approved command in a Job with no token, no egress and a read-only package mount. `deploy/k3s/50-validation.yaml` adds a separate jobs volume, a six-verb namespaced Role and default-deny policies. Approvals gained workflow/job/step/attempt columns; a durable `write_operations` record is created in the same transaction that claims an approval and is resumed at startup. New `proof.py` and a Control Center card show one record per attempt with a source for every value.
- verification: Observed on the macOS coordinator 2026-09-05 — 840 Python checks pass under `.venv` (7 skipped: no PyObjC), 174 under `desktop/.venv` (4 skipped), 90 browser checks across 6 suites. Twelve mutation checks each broke a matching regression, including one that found and fixed a real defect: the claimed write record was held on the shared service object and could cross between concurrent approvals. The C07 scan fixture was read end to end by the already-installed `qwen3.5:4b-q4_K_M` (local fixture evidence only). The macOS application rebuilt, ships the new modules and Quartz, and `codesign --verify --deep --strict` reports valid.
- remaining: The linux/amd64 worker image was NOT built — the pinned base and all wheels are absent from the Docker cache and downloading is unauthorised, so the C09 worker changes still need a build on Ubuntu. The configured `MedAIBase/PaddleOCR-VL:0.9b` reports `["completion"]` with no projector and rejects images, so scan reading fails closed pending a requester decision. No Kubernetes Job, package transport, pairing or distributed run has ever executed; C05–C10 all remain unaccepted. Next steps are in `docs/c07-c10-runtime-handoff.md`.

<a id="ac-20260905-016"></a>
## AC-20260905-016 — Working indicator: the mark turns and the label shines while a job runs
- prompt_id: [UP-20260905-017](userprompts.md#up-20260905-017)
- date: 2026-09-05
- agent: Claude
- status: implemented
- tags: refinix, chat, code-surface, composer, working-indicator, brand-mark, animation, reduced-motion
- aliases: refinix working, spinning mark, shine sweep, background-clip text, read-width alignment, matchMedia harness gap
- paths: frontend/app/index.html, frontend/app/code.html, frontend/app/refinix.css, frontend/app/app.js, agent-memory/
- summary: Added one activity indicator shared by Chat and Code — the brand mark turning on a near-black disc beside a shining "Refinix Working" — sitting in the reading column immediately above each prompt box, driven by real job state rather than by a timer.
- changes: The mark is the existing refinix-mark.png, which is metal on a near-black ground and cannot recolour for a light theme, so it keeps its own ground exactly as .brand does: an 18px near-black disc in both themes. The disc is round because a rotating circle has no moving edge, and the square original is inset 1px so the circular clip meets only ground — the art reaches 1.05x the inscribed radius at 18px and 0.94x once inset. No new asset was produced and the mark was not redrawn.
  The label is a gradient clipped to the text, one band of light crossing it left to right every 2.4s. Two details were wrong on the first attempt and are now fixed in place: with background-repeat:no-repeat every letter outside the band had no paint at all and rendered transparent, so only "Ref" was visible — it is repeat-x, with both ends of the ramp on the base colour so the tile abuts itself invisibly; and the travel is stated in em rather than percent, because a background wider than its box takes percentage positions in reverse. The ramp runs --text-faint to --text, which gains contrast in both themes instead of washing out in light.
  Alignment needed the same expression .composer-box resolves. app.css sizes the reading column with --read-w, overrides.css re-bases it on --read-width, and only the second is what the box ends up at; using --read-w put the mark 106px left of the box it belongs to.
  app.js gained one function, setWorking. Chat calls it from setActive, so it follows the coordinator's own job state — every active state on, every terminal state off, and still on while a pressed Stop is taking effect. Code calls it around proposeChange, off in the finally, so a failed proposal cannot leave it turning over nothing. Hiding uses [hidden], so neither animation ticks when there is no work.
- verification: Rendered the real index.html and code.html over a scratchpad static server. Both indicators resolve to exactly the composer box's left edge (270px at 1440, 16px at 375), no horizontal overflow, label uncut. Confirmed the mark is genuinely turning by sampling its computed transform across 400ms, and read the sweep by freezing both animations at four points in the cycle at 5x — the disc stays round with no arrow clipped, and the band crosses left to right — in dark and light. Confirmed all four rules and both media fallbacks parsed from the CSSOM, and that under reduced motion the label paints flat at --text-dim with background-image:none, so it cannot be stranded on a transparent slice.
  The four frontend suites cannot run as committed: app.js calls window.matchMedia, which none of the four fake windows provides, so all 101 tests error during setup. This is pre-existing — HEAD fails identically, 101 for 101 — and was not introduced here. Adding the stub to scratchpad copies only, the suites pass 60/60 with these changes, and five further behaviour tests written against the same harness pass: every active state turns it on and every terminal state off, Stop keeps it on until the job stops, streaming keeps it on and completion stops it, and both a failed and a successful Code proposal stop it.
- remaining: The missing matchMedia stub in the four committed test files is left as found; fixing it is a test-harness change outside this request, and it means the repository suites are red until someone does. On Code, the indicator now sits above the box while the existing "Reading the selected files…" sentence stays inside it — both are true and neither was removed, but the pair is worth a second look. No Git writes ran.

<a id="ac-20260905-017"></a>
## AC-20260905-017 — Reply copy becomes a right-hand icon; Jump to latest becomes a round arrow
- prompt_id: [UP-20260905-018](userprompts.md#up-20260905-018)
- date: 2026-09-05
- agent: Claude
- status: implemented
- tags: refinix, chat, code-surface, copy-control, jump-latest, icons, svg, composer-anchoring
- aliases: turn-copy, ICON_COPY, ICON_TICK, svgIcon, jump-latest circle, bottom 100%, composer position relative
- paths: frontend/app/app.js, frontend/app/index.html, frontend/app/code.html, frontend/app/overrides.css, frontend/app/refinix.css, agent-memory/
- summary: Both controls are now icons. The reply's copy button is a 26px glyph at the right-hand end of the turn row, and Jump to latest is a round 34px down-arrow centred above the composer. Fixing the second one uncovered and repaired a positioning bug the previous change had introduced.
- changes: app.js gained one helper, svgIcon, which builds a stroked 16x16 glyph and leaves weight, size and colour to the stylesheet. The reply button moved off the shared .code-copy class onto .turn-copy — code blocks keep their worded Copy, which names which of several blocks it belongs to and so still needs words. Losing the label meant relocating everything the label carried: the glyph swaps to a tick, the title and aria-label both change, and a failure spends --st-fault. Success deliberately does not spend green: in this palette green means enforced or a completed lifecycle step, and a clipboard write is neither, so it is the tick plus full-strength silver.
  Jump to latest lost its text for a round outlined arrow, keeping title and aria-label so it still has a name.
  Positioning it exposed a real bug from AC-20260905-016. Its geometry was bottom:7.5rem from .main, a figure measured against one particular composer height — and the working indicator added a row to that composer, which slid the button down over the prompt box it is supposed to sit above. The same offset already failed for the prompt box growing to its 14em cap. It is now an absolutely positioned child of .composer at bottom:100%, so it tracks whatever height the composer happens to be.
- verification: Rendered both real pages over a scratchpad static server, dark and light, at 1440 and 375. The copy control sits flush with the reading column's right edge (760 at 1440, 359 at 375, matching the prose edge exactly) and all three states read correctly at 5x — two overlapping sheets, a tick, and the wine failure. The jump button is 34px, border-radius 50%, carries no text, and is centred on the reading column to the pixel (515 of 515; 188 at 375). Confirmed the positioning fix directly: forcing the prompt box to 332px moved the button up 215px with it and it still cleared the box, where the old fixed offset would have been buried; it also clears the working indicator and, on Code, the project row.
  The four repository suites still cannot run as committed — app.js calls window.matchMedia and none of the four fake windows provides it, unchanged from HEAD and unrelated to this work. With that stub added to scratchpad copies only, 68 of 68 pass: the 60 repository tests, the 5 working-indicator tests from the previous change, and 3 new ones here — the control renders as an icon button with an accessible name and no visible words, copying swaps both the glyph and the name and restores them, and a clipboard failure is reported rather than swallowed.
- remaining: Two things found and not taken. The prose tokens in overrides.css are dark-first with their light values only inside @media (prefers-color-scheme: light) and no :root[data-theme="light"] block, so the Control Center's own light toggle does not reach them and the reading column keeps dark text on a light ground — the exact failure app.css's header rule warns about. That is a pre-existing defect in nine tokens, outside this request. Centring the jump button rather than leaving it in the right-hand corner follows the supplied screenshot and is a one-line revert if that was not intended. No Git writes ran.

<a id="ac-20260905-018"></a>
## AC-20260905-018 — Model selection end to end, composer hint removed, prompt box wired to grow
- prompt_id: [UP-20260905-019](userprompts.md#up-20260905-019)
- date: 2026-09-05
- agent: Claude
- status: implemented
- tags: refinix, model-selection, coordinator-api, composer, autogrow, ollama, contract-change
- aliases: v1/model/select, offered_models, active_model, selected_model meta key, mp-model, send-hint removed, rows=1, wireAutogrow input
- paths: backend/coordinator/db.py, backend/coordinator/server.py, backend/coordinator/code_service.py, backend/coordinator/test_reasoning.py, frontend/app/app.js, frontend/app/index.html, frontend/app/code.html, frontend/app/refinix.css, agent-memory/
- summary: A computer with more than one model installed can now choose which one runs, from a list behind the pill. This needed the backend as well as the page: the coordinator offered exactly one model and had no way to select another. The composer also loses its standing hint line, and the Chat prompt box was tightened — and, in the process, found never to have been wired to grow at all.
- changes: This reverses a stated product position. server.py said "Only models this build actually supports are offered; a name in the runtime's tag list is not approval to use it", and /v1/model/reasoning rejected any model but the build default. The requester asked for the opposite, so the runtime's own tag list is now the offer.
  Coordinator: db gained get/set_selected_model over one `meta` key — a property of the workspace, not of a model, so model_prefs would have allowed two rows to claim it. Coordinator.offered_models() returns every installed tag plus the build default (kept even when missing, because its absence is a fact the Control Center states), each with its own stored reasoning and an active flag. Coordinator.active_model() honours the stored choice only while the runtime still reports it, so uninstalling a model cannot leave every request pointing at something that is gone. The job path and code_service now read that model, snapshot it on the attempt, and pass it to stream_chat, which already took a model argument. New route /v1/model/select; /v1/model/reasoning now accepts any offered model. Capability blockers say "the selected model" and name the one that would actually run.
  Page: the pill grew a caret and opens a radiogroup of models above the existing Reasoning switch, which is redrawn on a switch because reasoning is stored per model. The coordinator decides and the page redraws from its answer, so a refused switch cannot leave the pill claiming a model that is not running. A model the runtime no longer reports stays listed, disabled and tagged rather than vanishing.
  Composer: #send-hint is gone. It carried two sentences; the standing one was the request, and the other — remove the skill to send an ordinary request — moved onto the skill status line, which already appears exactly when a skill cannot run.
  Height: the prompt box was rows="2", so a one-line prompt reserved two. It is rows="1" now, and that exposed the real defect: wireAutogrow was only ever called for the Code box. Chat's box was never wired, and refinix.css sets resize:none with overflow-y:hidden — autogrow is what turns overflow back on — so past two lines the text went under the bottom edge, invisible and unscrollable. Measured before the fix: six typed lines, 135px of content in a 45px box, overflow hidden.
- verification: Backend: ran the real coordinator against the real Ollama on a throwaway state file and port, never the user's own. /v1/status returns the new shape; selecting an uninstalled model is refused 404, selecting the installed one succeeds, reasoning follows, and status reflects both. 9 new tests in test_reasoning cover the offer, the default being listed when missing, the fallback when a choice disappears, per-model reasoning, the request reaching the chosen model with that model's own switch, the attempt recording it, and validation. Full backend suite 297 tests: the set of failing tests is byte-identical to HEAD's (66, chiefly the Code surface being unsupported on Windows), so nothing changed state.
  Page: drove the real index.html and code.html against the real coordinator through a proxy that injects two extra models, dark and light, 1440 and 375. Switching to another model updates the pill, moves the mark and flips the Reasoning switch to that model's own value; a not-installed model is listed, disabled, tagged and explained; the popover fits at 375. Composer measured at 96px for an empty or one-line prompt against 118px before, growing to 260px and then scrolling, with nothing hidden at any length. 74 of 74 frontend tests pass (60 repository, 14 written across these three changes), still with the matchMedia stub applied to scratchpad copies only.
- remaining: Two things stated rather than taken. runtime.py's bounded settings — num_ctx 8192, num_predict 2048, think false — were measured against the default model in docs/model-catalog.md; another model now runs under those same bounds and has not been characterised at that size. And the light-theme defect from AC-20260905-017 is now pinned down: light driven by prefers-color-scheme is correct, but the Control Center's own data-theme="light" toggle does not reach the nine dark-first tokens in overrides.css, which is why the model pill renders as a black slab under that toggle and not under the OS preference. Neither was in this request. No Git writes ran.

<a id="ac-20260906-001"></a>
## AC-20260906-001 — C08–C10 review corrections
- prompt_id: [UP-20260905-016](userprompts.md#up-20260905-016)
- date: 2026-09-06
- status: implemented; live Ubuntu and Kubernetes verification pending
- scope: c08, c09, c10, model-selection, validation, sandbox, cleanup, proof
- tags: model-selector, paddleocr, validation-gate, kubernetes-admission, package-retention, proof-cards
- aliases: auto model disabled, zero tests refused, validation job containment, stable citations
- paths: backend/contracts/, backend/coordinator/, backend/worker/, deploy/k3s/, frontend/app/, docs/c07-c10-runtime-handoff.md, tasks.md
- summary: Closed the integrated review findings without advancing any C06–C10 human gate.
- changes: Workflow-scoped model choices now persist and propagate exactly, Auto is visibly disabled, document search shows no false model choice, and OCR enables only a runtime-confirmed vision model. Code apply now requires a current observed sandbox pass over the full selected snapshot with at least one parsed unittest result. Validation Jobs are constrained by credential-free identity plus admission policy, temporary packages expire on terminal acknowledgement, startup and a periodic sweep, and Proof Card citation identities and approval sources are persisted.
- verification: Observed on the macOS coordinator: 888 Python checks passed with 4 intentional skips; 91 browser checks passed; JavaScript and worker API source parsed; final `git diff --check` passed. The FastAPI worker route suite remains authoritative only inside the pinned image build.
- remaining: Build the linux/amd64 worker image, server-dry-run and apply the admission policy, pair the devices, run one real validation Job, and choose a vision-capable OCR model or accept scan OCR as blocked. C06–C10 remain unaccepted until those device checks pass.

<a id="ac-20260906-002"></a>
## AC-20260906-002 — Worker image checks are deterministic on Python 3.13
- prompt_id: [UP-20260906-001](userprompts.md#up-20260906-001)
- date: 2026-09-06
- status: implemented and locally checked; authoritative Ubuntu image rebuild pending
- scope: c06, c09, worker-image, offline-tests
- tags: docker-build, python-3.13, model-digest, zero-tests, test-fixture
- aliases: selected model is not installed, exit status 5, worker image 11 failures
- paths: backend/worker/test_worker_app.py, backend/worker/test_validation.py, agent-memory/
- summary: Made the worker image checks supply their installed-model evidence explicitly and test the zero-test gate independently of Python's unittest exit-code change.
- changes: The shared API fixture now makes its fake runtime advertise the same model digest carried by its envelopes. The zero-discovery check injects a successful zero-test result, so it still proves the minimum-test guard even when Python 3.13 itself exits 5 for no tests. Production admission and validation code are unchanged.
- verification: `backend.worker.test_validation` passed 45 checks under the local Python 3.14 environment; both edited test files compiled; `git diff --check` passed. The worker API suite could not run locally because neither existing Mac virtual environment contains FastAPI, so the Ubuntu image build remains authoritative.
- remaining: Commit and push the four changed files, pull them on Ubuntu, then rerun the cached-input C09 worker image build. No image, service, Kubernetes object, credential or Git state was changed by Codex.

<a id="ac-20260906-003"></a>
## AC-20260906-003 — Observed C09 worker image pinned
- prompt_id: [UP-20260906-002](userprompts.md#up-20260906-002)
- date: 2026-09-06
- status: implemented and offline-checked; publication and K3s import pending
- scope: c06, c09, image-digest, provenance, manifests, handoff
- tags: ubuntu, docker, image-digest, archive, kubernetes, provenance
- aliases: 774218db, 873cd89c, 06013413, c09 image pin
- paths: backend/worker-image/provenance.json, deploy/k3s/, docs/c07-c10-runtime-handoff.md, tasks.md, agent-memory/
- summary: Pinned the requester-observed C09 Ubuntu image across the worker, executor, validation policy, provenance and live handoff.
- changes: All four runtime image references now use manifest digest `sha256:774218db...`; provenance records the observed config digest, archive SHA-256 and byte size. The handoff records step A passed, uses the new digest in the admission probe and limits its history scan to AegisForge-created layers so the upstream Python signing key is not a false positive. The execution ledger now distinguishes the passed image build from pending C06 runtime acceptance.
- verification: Requester output showed the linux/amd64 build's offline layer pass, manifest and config digests, and a root-owned mode-0600 archive outside the repository with SHA-256 `06013413...` and 49,579,008 bytes. Locally, 79 manifest checks passed, provenance parsed as JSON, every live image consumer matched the recorded digest, and `git diff --check` passed.
- remaining: Publish these eight files, pull them on Ubuntu, import and alias the image in K3s containerd, then recreate the address-bound TLS identity and resume the guarded C06 rollout. No cluster object or service was changed by Codex.

<a id="ac-20260906-004"></a>
## AC-20260906-004 — C09 admission policy compiles its map-key check
- prompt_id: [UP-20260906-003](userprompts.md#up-20260906-003)
- date: 2026-09-06
- status: implemented and offline-checked; Ubuntu server dry-run retry pending
- scope: c06, c09, kubernetes, admission-policy, runtime-handoff
- tags: cel, validatingadmissionpolicy, map-membership, pvc, rollout-order
- aliases: invalid argument to has macro, aegisforge jobs not found, pending worker
- paths: deploy/k3s/50-validation.yaml, deploy/k3s/test_manifests.py, docs/c07-c10-runtime-handoff.md, agent-memory/
- summary: Replaced an invalid CEL map-key `has` call with membership and ordered C09 prerequisites before the worker rollout that mounts their PVC.
- changes: The admission identity rule now uses `'aegisforge.dev/attempt' in object.metadata.labels`, the Kubernetes-supported form, while retaining the outer labels-field presence guard. A focused regression rejects the invalid map-index macro. The runtime handoff now runs `50-validation.yaml` after digest pinning and before rolling out either consumer.
- verification: Requester output proved the previous server dry-run failed closed without creating resources and named the exact CEL compilation error. Locally, 80 manifest checks passed and `git diff --check` passed. The live K3s server dry-run remains required after publication.
- remaining: Publish these five files, pull them on Ubuntu, re-render the manifest with cluster IP `10.43.0.1`, and rerun server dry-run. The old worker remains Ready; the new worker stays Pending until the jobs PVC exists.

<a id="ac-20260906-005"></a>
## AC-20260906-005 — C09 consumers use the guarded Ollama bridge
- prompt_id: [UP-20260906-004](userprompts.md#up-20260906-004)
- date: 2026-09-06
- status: implemented and offline-checked; publication and live worker verification pending
- scope: c06, c09, runtime, configmap, network-policy, handoff
- tags: ollama, cni0, runtime-host, egress, worker, executor
- aliases: health unavailable, 10.42.0.1, protected Ollama bridge
- paths: deploy/k3s/20-worker.yaml, deploy/k3s/40-executor.yaml, deploy/k3s/test_manifests.py, docs/c07-c10-runtime-handoff.md, agent-memory/
- summary: Pointed both C09 consumers at the observed guarded cni0 Ollama forwarder and tied the endpoint to the existing /32 egress policy.
- changes: Worker and executor ConfigMaps now use `http://10.42.0.1:11434`; a focused check requires that endpoint to match `10.42.0.1/32` port 11434 in the separate runtime policy. The live handoff now includes the previously missing runtime-bridge step before LAN exposure and pairing.
- verification: Requester output showed cni0 `10.42.0.1/24`, Ollama 0.33.2 and both expected model digests, the host runtime still bound only to `127.0.0.1:11434`, the guarded proxy bound to `10.42.0.1:11434`, Pod-CIDR ACCEPT followed by broader DROP, and the bridge returning the runtime version. Locally, 81 manifest checks and `git diff --check` passed.
- remaining: Publish these six files, pull them on Ubuntu, apply `30-runtime-egress.yaml` and reapply only `20-worker.yaml`, then confirm the worker advertises the installed model. The executor remains undeployed until pairing creates its relationship ID.

<a id="ac-20260906-006"></a>
## AC-20260906-006 — Executor grace period moved to the Pod spec
- prompt_id: [UP-20260906-005](userprompts.md#up-20260906-005)
- date: 2026-09-06
- status: implemented and offline-checked; publication and live executor retry pending
- scope: c06, c09, kubernetes, executor, manifest
- tags: executor, deployment, pod-spec, termination-grace-period, strict-decoding
- aliases: unknown field terminationGracePeriodSeconds, executor deployment not found
- paths: deploy/k3s/40-executor.yaml, deploy/k3s/test_manifests.py, agent-memory/
- summary: Moved the executor's 40-second termination grace period from its container to the Kubernetes Pod spec.
- changes: The recovery allowance is unchanged; only its invalid indentation changed. A focused manifest regression now requires the field at Pod level and rejects it inside the container.
- verification: Requester ran 82 manifest checks on the macOS coordinator; all passed. `git diff --check` was silent. The failed Ubuntu apply had created only the executor ConfigMap and ingress NetworkPolicy; K3s rejected the Deployment before any executor Pod existed.
- remaining: Commit and push these three files, pull them on Ubuntu, reapply `40-executor.yaml`, and prove the executor Deployment Ready. The earlier pairing-state reload defect remains to be repaired before final acceptance.

<a id="ac-20260906-007"></a>
## AC-20260906-007 — Model choices use their existing three-column layout
- prompt_id: [UP-20260906-006](userprompts.md#up-20260906-006)
- date: 2026-09-06
- status: implemented and locally verified; publication and packaged-app rebuild pending
- scope: refinix, frontend, model-selection, c06-acceptance
- tags: model-selector, css-grid, accessibility, chat, routing
- aliases: vertical model text, fourteen pixel column, broken model dropdown
- paths: frontend/app/app.js, frontend/app/test-composer.cjs, agent-memory/
- summary: Split every model option into the tick, model-name and location cells its existing CSS grid expects.
- changes: The selector now renders three spans instead of one raw text node in the 14-pixel tick column, while retaining the existing inventory, selection API and visual styles. Radio roles and checked state expose the same choice semantics to assistive technology.
- verification: Requester ran the focused browser suite after the correction: 31 checks passed, including the three-cell regression. The live selector screenshot showed horizontal readable choices and the Ubuntu model was selected successfully. `git diff --check` was silent.
- remaining: Publish the source and rebuild the packaged Refinix application before presentation use. No routing, model inventory or visual token changed.

<a id="ac-20260906-008"></a>
## AC-20260906-008 — SIGTERM leaves work recoverable and fresh codes visible
- prompt_id: [UP-20260906-007](userprompts.md#up-20260906-007)
- date: 2026-09-06
- status: implemented and locally verified; worker-image rebuild and live retry pending
- scope: c06, worker, executor, recovery, pairing
- tags: sigterm, redis-streams, restart-recovery, pairing-reload, worker-image
- aliases: cancelled before completion, rollout restart lost work, fresh pairing code refused
- paths: backend/worker/executor.py, backend/worker/pairing.py, backend/worker/test_executor.py, agent-memory/
- summary: Restored the intended unacknowledged shutdown path and made the running API reload codes written by the host CLI.
- changes: Executor shutdown now raises the existing `Stopped` signal through both generation and validation instead of emitting a false cancellation and acknowledging the stream entry. Pairing redemption reloads the shared file under its existing lock before matching a CLI-issued code.
- verification: Requester ran the focused executor suite with the repository virtual environment and reported all checks passed, including regressions for pending SIGTERM work and a code minted by a second store process. `git diff --check` was silent.
- remaining: Publish, rebuild the linux/amd64 worker image once, repin its observed digest and repeat the live pairing-without-restart and executor-rollout recovery checks. The previous live image still contains both defects.

<a id="ac-20260906-009"></a>
## AC-20260906-009 — One guarded presentation-start command for both devices
- prompt_id: [UP-20260906-008](userprompts.md#up-20260906-008)
- date: 2026-09-06
- status: implemented and locally verified; publication and device installation pending
- scope: c06, presentation, launcher, macos, ubuntu
- tags: refinix-start, motorola-hotspot, systemd, k3s, fail-closed
- aliases: Refinix start, college presentation, two-device startup
- paths: scripts/refinix, scripts/test_refinix_launcher.py, agent-memory/
- summary: Added one cross-platform launcher for the fixed Motorola hotspot presentation profile.
- changes: On Ubuntu, `refinix start` verifies the worker address before starting K3s, Ollama, both guarded forwarders and waiting for all three Deployments. On macOS it prints and verifies the Wi-Fi address, requires the protected worker port to be reachable, then opens the packaged application. Unexpected networks stop before service or application startup, and the launcher reads no secret.
- verification: Requester ran the offline launcher checks with the repository virtual environment, `sh -n`, the browser suite and `git diff --check`, and reported all passed.
- remaining: Publish and install the same file as `/usr/local/bin/refinix` and `/usr/local/bin/Refinix` on both devices, then execute it once on Ubuntu followed by Mac. The launcher is deliberately bound to the current Motorola IP profile; it does not silently rewrite certificate or firewall trust.

<a id="ac-20260906-010"></a>
## AC-20260906-010 — Local document output, image reading and attachment intelligence
- prompt_id: [UP-20260906-009](userprompts.md#up-20260906-009)
- date: 2026-09-06
- status: implemented and locally verified; requester acceptance pending
- scope: execution-4a, documents, attachments, macos, local-only
- tags: pdf-output, image-ocr, xlsx, chat-attachments, general-document, write-document
- aliases: convert answer to pdf, ocr an image into a document, read a spreadsheet, chat reads files
- paths: backend/coordinator/pdfgen.py, backend/coordinator/xlsx.py, backend/coordinator/ocr.py, backend/coordinator/documents.py, backend/coordinator/docflow.py, backend/coordinator/retrieval.py, backend/coordinator/server.py, backend/coordinator/db.py, backend/coordinator/test_execution4a.py, frontend/app/app.js, agent-memory/
- summary: Added local PDF output, direct PNG and JPEG reading, spreadsheet extraction, format-appropriate search locations, attachment reading in ordinary Chat, and a general document workflow beside the unchanged approval note.
- changes: `pdfgen.py` writes a real PDF with the already-installed Quartz framework and lays text out through AppKit, because `CoreText` is absent here and the plain Quartz text call is MacRoman-only; it reopens the file to read back a real page count. `ocr.py` gained a direct image path that checks the magic number against the declared type and never claims a Quartz render. `xlsx.py` reads a workbook per worksheet, drops external relationships, refuses macros and traversal, and reports a formula as a formula with any cached value labelled as cached. `retrieval.describe_location` states a PDF page, a text line range, a Word paragraph or a worksheet cell, and never invents a line number for a PDF or a page Word did not establish. Write Document now runs without an attachment: a request to save the previous answer copies it word for word with no model call, and a general request writes a new document. Output format and workflow are stored on the job. Ordinary Chat reads the files sent with that one request, and a request carrying files is routed to this computer before any worker contact, because the worker contract has no attachment field. The extraction is fenced as data under a system instruction, shares one budget across the attachments, includes a bounded part of a page too large to fit whole rather than dropping it, and names what was refused or trimmed.
- verification: 518 coordinator checks pass under the packaged interpreter (4 skipped) and 476 under the repository virtual environment (7 skipped, the PyObjC-dependent ones); 42 of those are the new Execution 4A regressions. 96 browser-side checks pass across six suites. `git diff --check` silent. The suite performs local capability reads against 127.0.0.1:11434; no generation call ran.
- remaining: Requester acceptance on the packaged application, which still predates this work and needs a rebuild. Live model output quality, real Word and PDF rendering in other applications, and the Code surface are all out of this scope.

<a id="ac-20260906-011"></a>
## AC-20260906-011 — Three-column Code workbench with real Code conversations
- prompt_id: [UP-20260906-010](userprompts.md#up-20260906-010)
- date: 2026-09-06
- status: implemented and locally verified; requester acceptance pending
- scope: execution-4b, code-surface, explorer, file-viewer, conversations, macos
- tags: three-column, repo-view, code-conversations, policy-view-action, additive-migration
- aliases: explorer tree, open a file, new code conversation, remove from refinix
- paths: backend/coordinator/policy.py, backend/coordinator/code_service.py, backend/coordinator/db.py, backend/coordinator/server.py, backend/coordinator/test_execution4b.py, backend/coordinator/test_code_access.py, frontend/app/code.html, frontend/app/app.js, frontend/app/refinix.css, frontend/app/test-code-surface.cjs, frontend/app/test-composer.cjs, agent-memory/
- summary: Rebuilt Code as Explorer, open file and conversation columns, added a separate view action, and gave Code its own durable conversations.
- changes: `repo.view` is a new policy action, automatic under partial and full and approval-gated under ask; it is deliberately not `repo.read`, because opening a file puts it on the person's screen while reading puts it in a model prompt, and the reply states that opening sent nothing to the model. The Explorer tree is built in `frontend/app/app.js` from the relative paths `/v1/code/files` returns; no absolute path reaches the page, and there is one implementation rather than two that could drift. Chats now record a `kind`, so Code conversations stop appearing in ordinary Chat history and search. Conversation ownership was completed in the correction round below: local proposals open a real job and attempt in the selected conversation, their request and result are persisted there, and Code state is conversation-scoped. The permanent audit rail became a collapsed Activity section inside the conversation column. Removing a project disconnects it through the existing forget path, is confirmed first, and touches no file. The refusal while work is running is enforced in the coordinator as of the correction round below.
- verification: 542 coordinator checks pass under the packaged interpreter (4 skipped) and under the repository virtual environment (12 skipped); 24 are the new Execution 4B regressions. 112 browser-side checks pass across six suites, 27 of them on the Code surface. Layout observed in a browser at 1280 px (three columns) and 900 px (file view primary, conversation an opaque drawer with a scrim), with no horizontal page overflow at either width. `git diff --check` silent.
- remaining: Apply still requires a passing sandbox validation on the paired worker, which is disconnected, so Validate and Apply remain unavailable and say so. Requester acceptance on the packaged application, which predates this work.

<a id="ac-20260906-012"></a>
## AC-20260906-012 — Explicit local apply with mandatory backups and Undo
- prompt_id: [UP-20260906-011](userprompts.md#up-20260906-011)
- date: 2026-09-06
- status: implemented and locally verified; requester acceptance pending
- scope: execution-4c, code-surface, local-apply, backups, undo, macos
- tags: execution-target, pre-write-backup, undo, not-sandbox-tested, fail-closed
- aliases: apply without ubuntu, undo a change, this device mode, local qwen edit
- paths: backend/coordinator/code_service.py, backend/coordinator/db.py, backend/coordinator/policy.py, backend/coordinator/server.py, backend/coordinator/test_execution4c.py, frontend/app/app.js, frontend/app/test-code-surface.cjs, agent-memory/
- summary: Added a recorded execution target, a verified pre-write backup of every original, an Undo bound to the applied digest, and honest local validation state.
- changes: Proposals record `execution_target`; a row without one defaults to `distributed`, so nothing written earlier can become locally applicable by omission. A `this_device` request builds a local route directly and never preflights, routes or contacts the worker. `apply` branches on the recorded target: distributed keeps the observed-passing sandbox requirement unchanged, and local refuses outright if a passing validation row exists against it, because that would be evidence the proposal did not earn. Before any local write, every original is re-read, re-hashed against the reviewed base and copied into coordinator-owned storage outside the project. As of the correction round below, each stored copy is then reopened and verified — ordinary private file, recorded size, recorded digest, bound to this proposal — for every planned edit before the write loop begins, so a row alone is never taken as proof that a backup exists. Undo restores only files still holding exactly what the proposal wrote, through the same hardened atomic path, and refuses as stale otherwise. Full access now carries a confirmation naming the missing sandbox tests.
- verification: 570 coordinator checks pass under the packaged interpreter (4 skipped) and the repository virtual environment (12 skipped); 28 are the new Execution 4C regressions. 120 browser-side checks pass across six suites. `git diff --check` silent. No live model call, worker contact, Kubernetes, Redis or Docker was made.
- review_fixes: A self-review before handoff found and fixed four defects. `resume_writes` reached the write path directly, so a restart could have replaced a file whose original was never copied; the backup now lives in `_run_operation`, the one place that writes, and a recovered operation backs up first. Undo reported a file that was never written as "changed after Refinix wrote it"; it now reports it as unchanged, and Undo is offered after a partial apply as well as a complete one. The Full-access dialog did not name the missing sandbox tests; it now uses the coordinator's own sentence. A second, unused folder-tree implementation in Python was removed in favour of the one the page actually ships.
- remaining: Live Qwen output quality, packaged-app behaviour and requester acceptance. Distributed validation still requires the paired worker, which is disconnected. The bundle rebuild needs separate authorisation after all three executions are reviewed.

<a id="ac-20260907-001"></a>
## AC-20260907-001 — Integrated review corrections for Executions 4A–4C
- prompt_id: [UP-20260907-001](userprompts.md#up-20260907-001)
- date: 2026-09-07
- status: implemented and locally verified; requester and Codex re-review pending
- scope: execution-4a, execution-4b, execution-4c, review-fixes, macos
- tags: fail-closed-target, verified-backups, conversation-ownership, local-attachments, aggregate-limits
- aliases: codex review fixes, corrupted target, backup verification, ask mode view approval
- paths: backend/coordinator/code_service.py, backend/coordinator/db.py, backend/coordinator/docflow.py, backend/coordinator/xlsx.py, backend/coordinator/pdfgen.py, backend/coordinator/server.py, backend/coordinator/test_execution4a.py, backend/coordinator/test_execution4b.py, backend/coordinator/test_execution4c.py, frontend/app/app.js, frontend/app/test-code-surface.cjs, agent-memory/
- summary: Closed the ten defects from the combined review plus a concurrent-backup race, leaving the distributed sandbox gate unchanged.
- changes: One `stored_target` resolver now interprets every persisted execution target; an unrecognised value stops before validation, approval, operation creation, backup or writing, and `state` reports it as unusable instead of making the surface unreadable. Every planned edit's backup is reopened and verified — file type, size, digest, and binding to this proposal — before the write loop begins, and a `UNIQUE(proposal_id, path)` race now reuses the verified winner or raises `BackupError` rather than escaping as a database error. Local proposals open a real job and attempt in the selected Code conversation, persist their request and result, and Code state is conversation-scoped so a fresh conversation cannot inherit the project's last proposal. Approving `repo.view` reopens that exact file with the approval instead of falling through to a proposal. A Chat request carrying files is routed to this computer before any preflight, its documents are fenced under a system instruction, share one budget, and a page too large to fit whole contributes a marked part rather than being dropped. XLSX gained aggregate byte, cell, text and compression-ratio ceilings checked from archive headers, and parses shared strings once. A PDF block taller than a page is split across pages, and conversion splits long lines and refuses an over-long answer rather than truncating it. Project removal is refused in the coordinator while work is unfinished and reports how much Undo it puts out of reach.
- verification: 600 coordinator checks pass under the packaged interpreter (4 skipped) and the repository virtual environment (13 skipped); 126 browser-side checks pass across six suites. `git diff --check` silent. No live model call, worker contact, Kubernetes, Redis, Docker, installation or app rebuild.
- remaining: Codex re-review, live Qwen output quality, packaged-app behaviour, and the distributed path, which still requires the disconnected Ubuntu worker. The bundle rebuild remains unauthorised.
- follow_up_to: [AC-20260906-012](#ac-20260906-012)

<a id="ac-20260907-002"></a>
## AC-20260907-002 — Codex closeout of Execution 4 integration defects
- prompt_id: [UP-20260907-002](userprompts.md#up-20260907-002)
- date: 2026-09-07
- status: implemented and locally verified; requester and external runtime gates pending
- scope: execution-4a, execution-4b, execution-4c, review-fixes, macos
- tags: conversation-isolation, durable-approval, backup-hardening, bounded-context, lossless-pdf
- aliases: codex closeout, reject proposal, safe project removal, final prompt bound
- paths: backend/coordinator/, frontend/app/, agent-memory/
- summary: Closed the remaining source-level 4A–4C integration defects while leaving Ubuntu disconnected and the distributed validation boundary intact.
- changes: Target validation now precedes worker routing; proposals, approvals, audit, project and open-file state stay conversation-owned; Reject is durable; Ask replays the exact approved view; removal locks against writes and Undo and requires an explicit count-based acknowledgement before stored Undo is put out of reach. Final attachment prompts share the real context selector, oversized pages contribute bounded text, general-document inputs share one ceiling, PDF pagination preserves characters, and backup creation, verification, Undo and cleanup refuse unsafe paths, links, modes and changed bytes. Local failure lifecycles now end with contract-valid states, while legacy workspace-conversation approvals and partial-apply recovery remain usable.
- verification: The complete coordinator suite passed 614 Python checks with 14 environment/platform skips in the repository virtual environment; the framework-independent lossless-pagination check passed. All six frontend suites passed 129 Node checks. The temporary loopback fixtures ran only after sandbox permission was granted; no live generation, worker, Kubernetes, Redis, Docker, installation, packaging or Git write ran.
- correction: Supersedes AC-20260907-001 as the current closeout record; that entry's all-items claim and larger test totals preceded this independent rerun and are not evidence for this state.
- remaining: Rebuild and inspect the packaged application, exercise real Qwen attachment/document/code flows, run the native PDF checks where Quartz/AppKit is available, then perform requester acceptance. The distributed path still requires a separately authorised Ubuntu reconnection and live validation.
- supersedes: [AC-20260907-001](#ac-20260907-001)

<a id="ac-20260907-003"></a>
## AC-20260907-003 — Main CI for release PRs and landed commits
- prompt_id: [UP-20260907-003](userprompts.md#up-20260907-003)
- date: 2026-09-07
- status: implemented; first GitHub run and server-side enforcement pending
- scope: github-actions, ci, main, release-flow
- tags: main-ci, push, pull-request, python, frontend
- aliases: enable CI for main push, main push checks, release CI
- paths: .github/workflows/ci.yml, CONTRIBUTING.md, agent-memory/
- summary: Added one least-privilege CI job that runs the repository's Python and browser-side checks before and after work reaches main.
- changes: Main CI runs for pull requests targeting `main` and pushes to `main`, checks out without persisted credentials, installs the existing hash-pinned Linux dependency set under Python 3.13, runs the contract, coordinator, worker, deployment, fixture and script suites, then runs all frontend Node tests under Node 24. The existing `pr-flow-guard` remains pull-request-only. Contribution guidance now distinguishes a pre-merge gate from a post-push audit and names `ci` for future branch protection.
- verification: Ruby parsed the workflow YAML successfully; source inspection confirmed both main triggers, read-only contents permission, non-persisted checkout credentials, hash-required dependency installation and the complete frontend test glob. `git diff --check` was silent. No test suite, installer, Git/GitHub write or external runtime command ran.
- remaining: The configured GitHub remote still names `prachi-satbhai0741/AegisForge`, but the authenticated `gh` client received HTTP 404 when reading its Actions permissions, so Actions enablement could not be confirmed. The workflow must first reach `main`, and its first hosted run is unverified. A push-triggered failure cannot reject or undo a direct push. Server-side protection remains absent until an admin successfully applies the ruleset with `pr-flow-guard ci` required.
- follow_up_to: [AC-20260907-002](#ac-20260907-002)

<a id="ac-20260913-001"></a>
## AC-20260913-001 — Reconcile the Refinix production direction
- prompt_id: [UP-20260913-001](userprompts.md#up-20260913-001)
- date: 2026-09-13
- status: documentation updated and statically checked; requester review pending
- tags: product-direction, offline, cross-platform, automatic-routing, installation, rag
- aliases: production refinix, optional kubernetes, bundled llama.cpp, dynamic peer placement
- paths: README.md, TechStack.md, tasks.md, docs/prd.md, docs/architecture.md, docs/workflows.md, docs/security.md, docs/model-catalog.md, docs/evaluation.md, docs/README.md, docs/devicespecifications.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Reconciled the core documents around offline desktop installation, dynamic trusted compute and a shared open-source/managed product core.
- changes: Preserved current UI and prototype backend; separated runtime/RAG/sandbox candidates from source evidence; added scoring, receiver controls, corpus permissions and outcome-based gates without fixed implementer assignments or deadlines.
- history: Retained dated prototype measurements and checkpoint records as historical context; corrected obsolete entry-point claims.
- verification: Static source/document inspection; git diff --check passed; 621 local links/anchors across 36 tracked Markdown files passed with no broken targets; all 13 changed files are Markdown. No runtime tests, installs, model downloads, service changes or Git/GitHub writes.
- remaining: Requester review of product wording; component qualification and platform/runtime acceptance require separately authorised implementation and observed checks.

<a id="ac-20260913-002"></a>
## AC-20260913-002 — Align repository naming with refinix
- prompt_id: [UP-20260913-002](userprompts.md#up-20260913-002)
- date: 2026-09-13
- status: documentation updated; GitHub rename blocked by missing administrator access
- tags: repository-name, refinix, documentation, github
- aliases: rename aegisforge, refinix repository, admin rename
- paths: README.md, CONTRIBUTING.md, AGENTS.md, docs/README.md, docs/prd.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Set the documented repository identity to refinix and prepared the administrator rename handoff without claiming the remote changed.
- changes: Updated current headings and repository/product identity; kept the former README anchor; documented the pending remote rename and a clone destination named refinix. Existing clone URLs, local checkout, application data and historical records remain intact.
- verification: GitHub REST returned repository id 1352342428 under the old name with push=true and admin=false; gh rename help and official GitHub instructions confirmed the administrator handoff. Static diff check passed; 623 local links/anchors across 36 tracked Markdown files passed with no broken targets.
- remaining: A repository administrator must rename the remote; verify the same repository id and update clone origins afterward. No GitHub mutation, commit, push, local-directory move or application migration occurred.

<a id="ac-20260914-001"></a>
## AC-20260914-001 — Document release readiness, updates and personalisation
- prompt_id: [UP-20260914-001](userprompts.md#up-20260914-001)
- date: 2026-09-14
- status: documentation updated and statically checked; requester review pending
- tags: releases, updater, offline, kv-cache, context, corpus, personalisation
- aliases: no calendar deadline, update version, refinix memory, optional training
- paths: README.md, CONTRIBUTING.md, TechStack.md, tasks.md, docs/prd.md, docs/architecture.md, docs/workflows.md, docs/security.md, docs/model-catalog.md, docs/evaluation.md, docs/README.md, docs/releases.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Recorded readiness-based public installation and upgrades, engine-owned cache policy, persistent context and optional evaluated adaptation.
- changes: Added the focused release contract; aligned core requirements, implementation gates, technology choices, workflows and security around explicit signed updates with offline import and recovery.
- changes: Defined target Refinix data roots and safe legacy migration; separated memory, corpus and training data; kept paging and weight adaptation conditional on evidence.
- verification: git diff --check and local Markdown link/anchor checks passed; changed/new files are Markdown only. Confirmed historical task/evaluation sections and official-problem transcription unchanged, with append-only ledger edits. New entry IDs are unique; pre-existing historical duplicate IDs were preserved.
- remaining: Requester wording review and separately authorised implementation/platform acceptance. No runtime tests, installations, downloads, data migration, Git/GitHub writes or application release occurred.

<a id="ac-20260915-001"></a>
## AC-20260915-001 — Record the P01 source and offline baseline
- prompt_id: [UP-20260915-001](userprompts.md#up-20260915-001)
- date: 2026-09-15
- status: P01 source/offline baseline verified; device and requester acceptance pending
- tags: p01, support-matrix, source-baseline, fixtures, offline-checks
- aliases: first production gate, four windows devices, current workflow gaps
- paths: docs/evaluation.md, docs/devicespecifications.md, tasks.md, agent-memory/
- summary: Recorded the current production qualification profiles, source gaps, reusable synthetic fixtures, local regression evidence and next isolated runtime checkpoint without changing product code.
- changes: Marked P01 in progress, corrected the available Windows-device count to four, kept advertised support unqualified, and separated existing safeguards from P02-P07 runtime gaps.
- verification: 614 coordinator checks passed with 14 skips after loopback allowance; 338 contract/worker-support/deployment/script checks, 32 fixture checks, 51 desktop checks, nine native renderer/PDF checks and 129 frontend checks passed. Existing bundle contents verified; 28 shipped modules and primary UI files matched current source. `git diff --check` and 297 changed-document links/anchors passed.
- remaining: Run the isolated macOS real-workflow checkpoint, obtain current Windows/Ubuntu checkout and runtime evidence, verify retained-worker behaviour and obtain requester acceptance before closing P01. Worker API checks remain unrun because FastAPI/HTTPX are absent; no install, live inference, worker contact, deployment, app rebuild or Git/GitHub write ran.

<a id="ac-20260915-002"></a>
## AC-20260915-002 — Correct the P01 checkpoint state isolation
- prompt_id: [UP-20260915-002](userprompts.md#up-20260915-002)
- date: 2026-09-15
- status: review correction verified; P01 device acceptance remains pending
- tags: p01, checkpoint, state-isolation, documentation
- aliases: sibling project and state, state_root review fix
- paths: docs/evaluation.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Moved the documented test database into a sibling state directory so Code can accept the disposable project.
- changes: Added state-directory creation, corrected the launch/restart path and explained the containment boundary; preserved the prior baseline diff and safety implementation.
- verification: An isolated standard-library check called the existing canonical_root function: the corrected sibling layout was accepted, the old nested layout raised state_root, and selecting the parent raised contains_state. Documentation path assertions and git diff --check passed.
- remaining: Real application/model/device checks and requester acceptance; no app launch, model call, install, runtime code change or Git/GitHub write.

<a id="ac-20260915-004"></a>
## AC-20260915-004 — Implement bounded reliability handoff
- prompt_id: [UP-20260915-004](userprompts.md#up-20260915-004)
- date: 2026-09-15
- status: implemented and checked with synthetic offline tests; requester acceptance pending
- tags: reliability, artifacts, skills, markdown, source-reuse, ocr, code
- aliases: one artifact card, one-shot skill, explicit source reuse, structured diagnostics
- paths: backend/coordinator/code_service.py, backend/coordinator/codeflow.py, backend/coordinator/db.py, backend/coordinator/docflow.py, backend/coordinator/ocr.py, backend/coordinator/server.py, backend/coordinator/test_code_access.py, backend/coordinator/test_ocr.py, backend/coordinator/test_reliability.py, frontend/app/app.js, frontend/app/markdown.js, frontend/app/test-composer.cjs, frontend/app/test-rendering.cjs
- summary: Fixed six bounded reliability defects while preserving permissions, model limits, previous-answer conversion and existing UI structure.
- changes: Generated artifacts now belong to one assistant turn; skills are one submission; ordered lists preserve starts and structure; earlier files require explicit same-chat reuse with revalidation and visible provenance.
- changes: OCR records typed transcription/unreadable/refusal outcomes and literal uncertainty; Code requests use the existing structured decoder and retain bounded failure diagnostics without weakening semantic path validation.
- verification: 279 focused coordinator tests and 137 complete frontend tests passed; the final 88 Code/reliability tests passed after the last diagnostic change. Python compile, node syntax and git diff --check passed.
- remaining: Real-model OCR and Code quality, packaged-app parity, historical presentation failure and generated-document depth remain unverified. The reasoning transport suite could not bind its synthetic loopback server in this sandbox.

<a id="ac-20260916-001"></a>
## AC-20260916-001 — Fix three reliability review findings
- prompt_id: [UP-20260915-005](userprompts.md#up-20260915-005)
- date: 2026-09-16
- status: implemented and checked offline; requester acceptance pending
- tags: reliability, source-selection, skills, review
- aliases: remote OCR guard, new chat skill race, OCR discussion
- paths: backend/coordinator/server.py, backend/coordinator/docflow.py, backend/coordinator/test_reliability.py, frontend/app/app.js, frontend/app/test-composer.cjs, agent-memory/userprompts.md
- summary: Source-less transcription stops before routing, OCR discussion remains ordinary Chat, and newer skill selections survive first-chat acceptance.
- changes: Moved source validation before route selection and reused the job request text; narrowed the English transcription heuristic; transferred newer draft skills only when the composer transitions to its created chat and refreshed the chip.
- verification: New backend and new-chat skill regressions failed before fixes and passed afterward. Ran 115 coordinator reliability/document/attachment tests and all 139 frontend tests successfully; git diff --check passed.
- remaining: The intent detector is a conservative English heuristic. Packaged-app and real-model quality checks remain unverified; no GUI, live inference, downloads, personal state or Git writes were used.

<a id="ac-20260916-002"></a>
## AC-20260916-002 — Reconcile the source-grounded Beta frontier
- prompt_id: [UP-20260916-001](userprompts.md#up-20260916-001)
- date: 2026-09-16
- status: documentation integrated and statically checked; requester review pending
- tags: beta, task-graph, model-lifecycle, source-audit, documentation-cleanup
- aliases: P14 Beta frontier, SIH Reviewer Preview, persistent Settings Models
- paths: tasks.md, docs/, README.md, TechStack.md, CONTRIBUTING.md, backend/README.md, backend/contracts/README.md, backend/coordinator/README.md, backend/worker/README.md, backend/worker-image/README.md, frontend/README.md, frontend/design/README.md, agent-memory/
- summary: Preserved the production architecture and replaced the first-publication sequence with a dependency-based Beta frontier grounded in current source and recorded evidence.
- changes: P01–P14 Beta blockers, P15–P20 versioned improvements and P21–P26 finals/production maturity; mapped old gates, defined persistent model lifecycle and narrow authenticated Beta installation/recovery.
- changes: Recorded current implementation gaps and recent reliability repairs; corrected stale component status, marked old handoffs historical and retained referenced reproduction/fixture/design assets after cleanup review.
- verification: Inspected current source/test bodies, CI/build definitions, docs and retained evidence. All 745 local links/anchors across 37 tracked Markdown files passed; 26 ordered tasks, band classifications, backward dependencies, preserved historical task/evaluation sections and Markdown-only scope passed. git diff --check passed. No application tests or live acceptance ran.
- remaining: Requester review of revised plan and separate device/runtime/package/publication gates. No runtime code, tests, installs, downloads, services, user state or Git/GitHub writes changed.

<a id="ac-20260916-003"></a>
## AC-20260916-003 — Consolidate execution context and retire prototype briefs
- prompt_id: [UP-20260916-002](userprompts.md#up-20260916-002)
- date: 2026-09-17
- status: consolidated and checked offline; requester review pending
- tags: documentation, execution-guide, archive, worker-operations, cleanup
- aliases: retired C handoffs, lightweight task board, deferred public presentation
- paths: AGENTS.md, tasks.md, docs/README.md, docs/archive/, docs/worker-operations.md, docs/workflows.md, docs/evaluation.md, docs/model-catalog.md, backend/coordinator/, backend/worker-image/README.md, backend/worker/pairing_cli.py, deploy/k3s/, scripts/image-digests.py, agent-memory/
- summary: Replaced duplicated active handoffs with canonical execution guidance while preserving reproduction history and safety coverage.
- changes: Deleted two superseded briefs after retaining their requirements; archived seven handoffs/plans and the historical task board; reduced active tasks.md from 830 to 224 lines and added source, check and checkpoint guidance.
- changes: Consolidated managed-worker operations, repaired active references and made missing safety documents fail their existing tests; flagged conflicting historical build/schema claims and deferred public presentation work.
- verification: Eight focused documentation safety tests passed. Checked local Markdown links/anchors, archive wording, historical task preservation, all 26 task classifications/dependencies and unchanged runtime structure; git diff --check passed.
- verification: Snapshot hashes confirm this cleanup preserved root README, frontend/design, SIH presentation brief and C07 fixtures, including prior edits; historical ledgers remain append-only.
- remaining: Requester review and current device/runtime/package acceptance. No model calls, installs, services, deployment, Git/GitHub writes or production qualification; only runtime help/comment references changed.

<a id="ac-20260918-001"></a>
## AC-20260918-001 — Draft the P01 Beta support contract
- prompt_id: [UP-20260918-001](userprompts.md#up-20260918-001)
- date: 2026-09-18
- status: draft written; requester decision and macOS runtime checkpoint pending
- tags: p01, beta, support-matrix, documentation
- aliases: P01 proposed matrix, Beta support contract draft
- paths: docs/evaluation.md, agent-memory/
- summary: Added a proposed narrow Beta support matrix and the requester decisions that close P01.
- changes: Recorded Windows, macOS and Linux as the target matrix with per-OS source gaps (Quartz rendering, Keychain credentials, dir_fd writes, macOS-only packaging) and the tasks.md P18 conflict for requester decision.
- verification: Local anchors checked by inspection; git diff --check passed. No application tests, runtime checks, installs or Git writes.
- remaining: Requester acceptance of the contract; macOS runtime checkpoint results and gap-to-task assignment.

<a id="ac-20260918-002"></a>
## AC-20260918-002 — Restore all-OS Beta scope and record the manual baseline
- prompt_id: [UP-20260918-002](userprompts.md#up-20260918-002)
- date: 2026-09-18
- status: documentation corrected; runtime acceptance remains pending
- tags: beta, portability, p01, documents, code, evidence
- aliases: three OS Beta, Tahoe M5 walkthrough, P06 workflow gaps
- paths: TechStack.md, tasks.md, docs/prd.md, docs/architecture.md, docs/workflows.md, docs/releases.md, docs/evaluation.md, docs/devicespecifications.md, agent-memory/
- summary: Required Windows, macOS and Linux desktop profiles before Beta publication and assigned the reported document/Code failures to P06.
- changes: Removed the unaccepted Mac-only matrix; made initial tasks portable and reserved P18/P22 for expanded coverage; preserved security, sandbox and updater boundaries.
- changes: Recorded requester-reported Tahoe 26.7/M5/16 GB, Chat/Stop/persistence results, screenshot/DOCX failures and unverified Code approval/selection reports, without claiming fresh runtime passes.
- verification: Reviewed the documentation diff and task ownership; 832 local Markdown links/anchors across 37 files, 26 ordered task rows, Markdown-only scope and git diff --check passed. No runtime code, fixtures, archives or public presentation content changed.
- remaining: Exact Windows/Linux target profiles, acceptance thresholds, portability implementation and device qualification. No tests, app/model runs, installs, deployment or Git writes.

<a id="ac-20260919-001"></a>
## AC-20260919-001 — Close seven residual scope and evidence conflicts
- prompt_id: [UP-20260919-001](userprompts.md#up-20260919-001)
- date: 2026-09-19
- status: documentation and diagram corrected; runtime acceptance unchanged
- tags: beta, portability, evidence, model-ranking, diagram, documentation
- aliases: seven residual findings, retired AF mappings, OD-08 chronology
- paths: docs/evaluation.md, docs/devicespecifications.md, docs/releases.md, docs/model-catalog.md, docs/workflows.md, docs/architecture.md, docs/workflow-diagram.html, agent-memory/
- summary: Removed remaining ambiguity about three-OS Beta scope, per-profile recovery, recommendation scores, active task ownership and network evidence.
- changes: Retired the historical Windows exclusion while preserving its inbound anchor; narrowed matrices only within each OS family; required replacement/recovery for every published profile.
- changes: Separated Beta compatibility/fit from P17 scores; rewrote coverage with P-task owners and implementation/runtime/release states; reconciled OD-08 dates without changing digests.
- changes: Diagram now labels target behaviour and unavailable network evidence; removed external fonts and uses system fonts. Prior dirty changes preserved.
- verification: Static checks confirmed no old conflict phrases, AF-numbered coverage mappings or diagram external resources/network calls; recorded digests and ledger prefixes preserved; git diff --check passed.
- remaining: Diagram visual layout and live network behaviour were not tested; documentation does not establish runtime or release acceptance. No app tests, installs, model calls or Git writes.

<a id="ac-20260919-002"></a>
## AC-20260919-002 — Phase 1 platform data roots and portable credential storage
- prompt_id: [UP-20260919-002](userprompts.md#up-20260919-002)
- date: 2026-09-19
- status: implemented and checked offline on the macOS device; requester verification pending
- tags: phase-1, platform-paths, credentials, portability, documentation
- aliases: paths.py, credentials.py, data-root conflict, Credential Manager, secret-tool, DS_Store fixture
- paths: backend/coordinator/paths.py, backend/coordinator/credentials.py, backend/coordinator/pairing.py, backend/coordinator/__main__.py, backend/coordinator/server.py, backend/coordinator/test_paths.py, backend/coordinator/test_credentials.py, desktop/lifecycle.py, desktop/test_lifecycle.py, frontend/app/app.js, frontend/app/test-control-centre.cjs, fixtures/c07/test_fixtures.py, docs/evaluation.md, agent-memory/
- summary: Gave Refinix one per-OS durable data root and one per-OS protected credential store, without migrating existing state or adding a dependency.
- changes: Added `paths.py` resolving the PROJECT.md 12.4 roots for macOS, Windows, Linux and an explicit portable profile; it creates, moves and merges nothing, keeps an existing `.aegisforge` store selected per 12.5, ignores zero-byte database leftovers, and reports two occupied roots as a refusal instead of choosing. Wired it into `desktop/lifecycle.py` (STATE_DIR/STATE_DB/LOCK_FILE, new `check_data_root` refusing startup before the database is opened) and the coordinator entry point.
- changes: Added `credentials.py` with macOS Keychain (moved unchanged, same service name and hex encoding), Windows Credential Manager via ctypes and Linux Secret Service via `secret-tool`; unlisted platforms get no store rather than a guess, and there is no file fallback anywhere. `pairing.py` now delegates and keeps `PairingError`/`KeychainUnavailable` so every existing caller is unaffected.
- changes: Status now carries `credential_store` alongside the historical `keychain_available`; the pairing refusal and the Control Center card name this computer's own missing prerequisite instead of the macOS Keychain on every OS. Fixed the C07 manifest check counting git-ignored desktop metadata (`.DS_Store`, `Thumbs.db`) as unrecorded fixture content.
- changes: Resolved the six committed merge-conflict markers in `docs/evaluation.md`, keeping the accepted all-OS support contract and the supplied Mac walkthrough and dropping the superseded Mac-only proposal that its own text labelled not accepted. Both existing anchors preserved. No other protected document changed.
- verification: Ran on this macOS device — backend/contracts 8, backend/coordinator 697 (14 skipped, 73 new), deploy/k3s 140, fixtures/c07 32, scripts 25, desktop 57 (6 new), frontend 141 (2 new): all passed. `git diff --check` clean; no conflict markers remain in any tracked file. Confirmed live resolution selects the existing `~/.aegisforge` store with no conflict, so the workspace was not moved.
- verification: backend/worker still reports one pre-existing collection error, `No module named 'fastapi'`, because the root virtual environment holds only the pydantic pins; CI installs the worker lock. Unchanged by this work.
- remaining: Windows Credential Manager and Linux Secret Service are source-present and exercised only through injected fakes; both need device observation. Phase 1 items D, E, F, H and I are untouched — portable PDF rendering (`pdfrender.py`, `pdfgen.py`), Windows-safe bounded Code access (`repo.py`) and non-macOS packaging (`setup_py2app.py`) remain macOS-bound. Roughly 39 links across 22 files still point at retired `tasks.md` anchors; not authorised in this batch. No installs, downloads, model or runtime calls, deployments or Git/GitHub writes.

<a id="ac-20260919-003"></a>
## AC-20260919-003 — Widen data-root occupancy and correct two overstated claims
- prompt_id: [UP-20260919-003](userprompts.md#up-20260919-003)
- date: 2026-09-19
- status: repaired and checked offline on the macOS device; requester verification pending
- tags: phase-1, data-root, occupancy, credentials, documentation
- aliases: inspect_root, Occupancy, residue, secret-tool prerequisite, keychain_available deprecated
- paths: backend/coordinator/paths.py, backend/coordinator/test_paths.py, backend/coordinator/credentials.py, backend/coordinator/server.py, agent-memory/
- summary: A root is now occupied by any durable content, not only by a non-empty database, and two claims in the prior report were corrected.
- changes: Replaced the database-only occupancy rule with `inspect_root`/`Occupancy`. A root counts as somebody's workspace when it holds a usable database, written instructions/curated memory (`config.toml`, `AGENTS.md`, `memory.md`), or any populated defined subdirectory such as `artifacts/`, `attachments/`, `backups/`, `corpus/` or `model-manifests/`. A conflict can therefore now be raised by content with no usable database, which the first implementation missed. Added `refinix.db` to the recognised database names so a product rename cannot become a store that resolution reads as an empty directory.
- changes: A lone zero-byte database, an empty defined subdirectory and an unrecognised loose file such as a hand-placed worker certificate remain non-occupancy, because refusing to start over a stray file is a worse failure than reporting it. They are now listed as `residue`, and `DataRoot.unselected_residue` reports what was in the root that resolution did not pick, so "the other root looked empty" is checkable instead of silent. Desktop metadata is excluded entirely.
- changes: Corrected the Linux claim: `secret-tool` plus an unlocked keyring session is a host prerequisite (`libsecret-tools`), not a free-of-dependency path. Recorded that FR-002 requires the graphical setup to provision and verify it for the selected Linux Beta profile, and assigned that to Phase 1 item H. Documented `keychain_available` as deprecated and noted it is derived from the same store read as `credential_store`, so the two cannot disagree.
- verification: Ran on this macOS device — backend/contracts 8, backend/coordinator 709 (14 skipped; 12 new occupancy checks), deploy/k3s 140, fixtures/c07 32, scripts 25, desktop 57, frontend 141: all passed. `git diff --check` clean. Confirmed live resolution still selects the existing `~/.aegisforge` store with no conflict, and now reports the macOS target root's two leftovers as residue rather than treating the root as simply empty.
- verification: Confirmed against source that two review concerns were already satisfied: the C07 fixture fix excludes an explicit four-name desktop-metadata set rather than matching `.gitignore`, and `keychain_available` and `credential_store.available` come from one call so an old caller cannot read false while the store works.
- remaining: Windows Credential Manager and Linux Secret Service are still exercised only through injected fakes and need device observation. Linux keyring provisioning is unimplemented (Phase 1 H). Phase 1 D, E, F, H and I remain open. No installs, downloads, model or runtime calls, deployments or Git/GitHub writes.

<a id="ac-20260919-004"></a>
## AC-20260919-004 — Requester-reported data-root acceptance on the macOS device
- prompt_id: [UP-20260919-004](userprompts.md#up-20260919-004)
- date: 2026-09-19
- status: requester-reported acceptance recorded; no repository code changed by this entry
- tags: phase-1, data-root, acceptance, macos, evidence
- aliases: restart persistence, completed task persisted, cancelled task persisted
- paths: agent-memory/
- summary: The platform data-root resolution was accepted on the live macOS workspace by requester observation.
- changes: No source change. This entry records acceptance evidence for [AC-20260919-002](#ac-20260919-002) and [AC-20260919-003](#ac-20260919-003).
- verification: Requester reported, on the live macOS workspace, that a completed task persisted across an application restart and that a cancelled task also persisted across a restart. Both are supplied observations, not an agent rerun. They establish that the existing store was re-selected on restart and that canonical task state survived, so the resolution did not move or shadow the workspace.
- remaining: The reported checks exercise the coordinator database across restart. They do not separately exercise the `artifacts/`/`attachments/` derivation, which is an unchanged pure function of the database's parent. Acceptance is recorded here only; `docs/evaluation.md` is protected and was not updated, so this evidence is not yet in the evaluation record. Windows and Linux data roots remain source-tested and not device-observed.

<a id="ac-20260919-005"></a>
## AC-20260919-005 — Portable PDF rendering replaces the Quartz-only read path
- prompt_id: [UP-20260919-004](userprompts.md#up-20260919-004)
- date: 2026-09-19
- status: implemented and source-tested on the macOS device; Windows and Linux remain device-unobserved
- tags: phase-1, documents, pdf, portability, pypdfium2, provenance, packaging
- aliases: item E, pdfrender backends, PDFium, stdlib PNG encoder, renderer provenance, requirements-render.lock
- paths: backend/coordinator/pdfrender.py, backend/coordinator/test_pdfrender.py, backend/coordinator/ocr.py, backend/coordinator/test_ocr.py, backend/coordinator/documents.py, backend/coordinator/test_documents.py, backend/requirements.txt, backend/requirements-render.lock, desktop/requirements-macos.lock, desktop/setup_py2app.py, desktop/test_packaging.py, .github/workflows/ci.yml, agent-memory/
- summary: PDF page reading no longer depends on an Apple framework; the same engine renders on Windows, macOS and Linux, and provenance names whichever engine drew the page.
- changes: Rebuilt `pdfrender.py` as two backends behind the unchanged public contract (`probe`, `available`, `page_count`, `render_pages`, `RenderError`, `RenderedPage`, every bound). `pypdfium2` is preferred everywhere; the macOS Quartz path is retained as a fallback so an installed bundle predating the dependency keeps reading documents. Added `selected_backend()`, `backends()` and an explicit `backend=` argument so the two can be compared on one computer. Bytes-only input, no path or URL, and form environments are never initialised, so interactive form content and its scripting are not evaluated.
- changes: PNG is encoded from raw scanlines with `struct`/`zlib` — one colour type, no alpha, filter 0 on every line — rather than adding an imaging library, because the authorised dependency was the renderer alone. `RenderedPage.renderer` records the backend that drew the page and `ocr.method_label` reports it; an unrecorded renderer is labelled unrecorded instead of being filled in from the probe. A fixed "(Quartz)" provenance string would have become false the moment a second backend existed.
- changes: Corrected two defects found while writing the tests. Demanding PDFium reproduce this module's rounding failed on every real page, because PDFium rounds a scaled edge up; the produced bitmap is now the authority and the pixel ceiling is applied to it. PDFium's page size already applies `/Rotate`, so the Quartz path's edge swap must not be repeated there — a rotated fixture now guards it.
- changes: Declared pypdfium2 5.13.0 in `backend/requirements.txt` with per-platform wheel digests, hash-pinned it for macOS arm64 in `desktop/requirements-macos.lock`, and added `backend/requirements-render.lock` carrying all four published wheel hashes. The worker-image lock was deliberately left alone: the worker renders nothing and its `provenance.json` records an already-built image by digest. Added a CI step installing the render lock, without which the new portability checks would silently skip on the Linux runner. py2app now bundles `pypdfium2` and `pypdfium2_raw` as packages, because the PDFium binary is package data that modulegraph cannot follow.
- verification: Ran on this macOS device. Plain virtual environment, standing in for a profile with no Apple frameworks — contracts 8, coordinator 755 (12 skipped), deploy/k3s 140, fixtures/c07 32, scripts 25: all passed. Desktop virtual environment with both renderers — coordinator 755 (4 skipped), desktop 58, frontend 141: all passed. `git diff --check` clean.
- verification: Device-observed on this macOS device only: the real C07 three-page scan renders to structurally valid PNG through PDFium, byte-identical across two runs, with ink present rather than a blank page, and both backends agree on page count and geometry for it within a pixel. The hash-pinned render lock was installed into a fresh virtual environment under `--require-hashes`, so the recorded digest was matched against a real downloaded wheel.
- verification: Source-tested only, through injected fakes or synthetic in-memory PDFs: encrypted and security-handler refusals (classified by PDFium error code, not message text), every bound and refusal, cancellation, deadline, rotation, and the PNG encoder's structure. A degenerate MediaBox was recorded as normalised by PDFium to US Letter, so the zero-size guard is tested directly rather than through a document.
- remaining: No Windows or Linux device has rendered anything; the portable path is source-tested and CI-bound, not device-observed. PDF *writing* (`pdfgen.py`) is still Quartz and AppKit only, deliberately: `docs/PROJECT.md` 16 requires a Word artifact and PDF output stays an additional format already gated on `pdfgen.available()`, whose refusal correctly names macOS. Phase 1 items D, F, H and I remain open. `backend/worker` still reports the pre-existing `fastapi` collection error in the plain environment. No deployments, model calls or Git/GitHub writes.

<a id="ac-20260919-006"></a>
## AC-20260919-006 — Documents routing repair: reference-driven conversion and bound history
- prompt_id: [UP-20260919-005](userprompts.md#up-20260919-005)
- date: 2026-09-19
- status: implemented and regression-tested offline; real-app verification pending
- tags: documents, routing, classifier, history, regression, phase-1
- aliases: looks_like_conversion, _PRIOR_OUTPUT, _message_body, intent matrix, batch 1
- paths: backend/coordinator/docflow.py, backend/coordinator/test_document_intent.py, agent-memory/
- summary: Write Document now chooses between copying the previous answer and writing a new one from the request's reference rather than its verb, and a general document again receives the conversation.
- changes: Replaced the verb-keyed conversion rule in `looks_like_conversion` with an ordered reference rule: an attachment wins; no document verb means no export; an explicit reference to earlier output (`your answer`, `previous response`, `answer above`, `what you just wrote`, `entire output`) selects conversion outright; a bare singular demonstrative selects it only with a format word and only when no new subject matter is named; everything else is a new document. Because the reference now decides, the verb list was safely completed with `create`, `generate` and `produce` — the missing `create` was the reported regression, and adding it without the reference requirement would have sent every "Create a document explaining X" into the copy path.
- changes: Widened the new-subject-matter stems to `explain\w*`, `describ\w*`, `summar\w*`, `research\w*`, `cover\w*`, `outlin\w*` plus `regarding`/`concerning`. The previous `explain` never matched "explaining" and `summar(y|ise|ize) of` never matched "summarising", which is how a new-document request could be answered with a copy of an earlier reply. `_CONVERT_VERBS` and `_BACK_REFERENCE` were removed with no remaining references.
- changes: Added `_message_body`, which reads `text` then `content`, and used it in `general_document_messages`. `Coordinator.chat_messages` returns `messages` rows carrying `text`, while the function read only `content`, so every general document silently lost its conversation and the model was left with a single request line. That is what produced the observed "No external data or instructions were provided to expand upon".
- changes: Added `test_document_intent.py` — a 30-row phrase matrix asserting both routes, named regressions for each defect, history-binding checks for `text`, `content` and mixed shapes, and coordinator-level checks that drive `Coordinator._run` against a temporary database and a stubbed runtime. No change to `server.py`: the honest no-previous-answer refusal already existed and is now covered.
- verification: Ran on this macOS device. Focused suites — test_document_intent 23, test_execution4a 53 (7 skipped), test_documents 88, test_reliability 10, test_context 14, test_ocr 55 (4 skipped), test_conversations 28: all passed. Full offline suites, plain environment — contracts 8, coordinator 778 (12 skipped), deploy/k3s 140, fixtures/c07 32, scripts 25. Desktop environment — coordinator 778 (4 skipped), desktop 58, frontend 141. All passed. `git diff --check` clean.
- verification: Confirmed the new checks fail against the pre-repair implementations restored in memory: 20 of 23 failed, including every coordinator-level check, so they are real regressions rather than tests written around the new code. Demonstrated that "Create a document for your entire output" completes through the deterministic conversion route with `stream_chat` never called and the previous answer present in the artifact; that "Create a document explaining machine learning" reaches generation with the earlier answer inside the prompt; and that the same request with no completed answer fails honestly, writing no artifact and no file.
- changes: Self-review after the first pass found and fixed two false-positive classes in the new rule itself. The reference gap allowed any word or two between a pointer and an output noun, so "your findings and response times" and "the last inspection response time" read as references to a reply; only a closed modifier list is accepted now. A bare demonstrative was matched anywhere in the request, so "Create a document with three sections and number it" filed the previous answer instead of writing a new document; a demonstrative now counts only as the object of a transformation verb (`convert`, `save`, `export`, `download`, `turn`, `render`, `put`, `make`) within three words, never for `create`, `generate`, `produce` or `write`. Six more matrix rows and three named regressions cover both. The history comprehension was also rewritten as a plain loop for readability.
- remaining: Real-app verification on the packaged application is still required. General document generation remains structurally fragile and was deliberately untouched in this batch: the document model call passes no `response_format`, uses the chat-sized `num_predict` while `MAX_ANSWER_TOKENS` stays dead code, has no repair round and no truncation check, and `parse_general_document` rejects a markdown-fenced or preamble-wrapped reply. Six of seven realistic small-model shapes are refused. That is the separately authorised follow-up batch. No Windows or Linux device evidence; these changes are platform-independent. No installs, model calls, deployments or Git/GitHub writes.

<a id="ac-20260919-007"></a>
## AC-20260919-007 — General documents are decoded against an enforced schema, sized, and repaired once
- prompt_id: [UP-20260919-006](userprompts.md#up-20260919-006)
- date: 2026-09-19
- status: implemented and regression-tested offline; packaged-app verification pending
- tags: documents, generation, structured-output, repair, truncation, phase-1
- aliases: GENERAL_DOCUMENT_FORMAT, DOCUMENT_NUM_PREDICT, REPAIRABLE_CODES, _general_document, _buffered_reply
- paths: backend/coordinator/docflow.py, backend/coordinator/server.py, backend/coordinator/test_document_generation.py, backend/coordinator/test_documents.py, agent-memory/
- summary: A general document is now asked for as a runtime-enforced JSON object with its own output ceiling, and a wrongly shaped reply gets exactly one repair instead of being discarded.
- changes: Added `GENERAL_DOCUMENT_FORMAT`, the narrowest JSON schema matching what `parse_general_document` already accepts, and `GENERAL_CALL`, which carries it and the output budget in the stage result. `_document_stage` attaches it to both general branches only; the approval-note and read-document routes are untouched and are asserted to receive no schema, because their replies are different shapes. The shared streaming call in `_run` passes the two parameters only when a route set them, so an ordinary Chat turn is called exactly as before.
- changes: Replaced the unused `MAX_ANSWER_TOKENS = 1024` with `DOCUMENT_NUM_PREDICT = 3072`. The old constant was never wired to anything and was smaller than the 2048-token chat default, so wiring it would have made documents shorter than an answer. 3072 fits the worst-case prompt inside num_ctx 8192 with the runtime's truncate and shift both off, and is asserted against both bounds.
- changes: Added `Coordinator._general_document` and `_buffered_reply`. A reply whose failure code is in `REPAIRABLE_CODES` — `not_json`, `not_object`, `unknown_fields`, the same set `ocr.py` repairs — gets one further call carrying the original context, the malformed reply and a format-only instruction. Everything else raises immediately, because `bad_sections`, `bad_section` and `too_many_sections` would require inventing or dropping content. The repair is schema-constrained and bounded too, runs with reasoning off, is never streamed or saved as output, and is parsed once more without catching: a second malformed reply is the answer.
- changes: The parser was deliberately left strict. Structured enforcement plus one repair is the robustness; a parser that scavenged JSON out of arbitrary prose would accept replies the model never meant as a document and would mask the schema not being enforced. A markdown fence is a parse failure recovered by the repair, and there is a test recording that decision.
- changes: `fake_stream` in `test_documents.py` now records `response_format`, `num_predict` and a call count, so the call contract is asserted at the production boundary rather than on the constants.
- verification: Corrected a wrong claim from the previous audit. Truncation rejection for document skills **already existed** in committed HEAD — `_run` fails any document reply whose runtime stop reason is not `stop`, before the parse — so it was covered by new tests rather than implemented again. Truncated output therefore never reaches the repair, which is the intended semantics.
- verification: A `minItems` constraint on both arrays was written and then removed during self-review: no schema in this repository has exercised that construct against the runtime, `PAGE_SCHEMA` uses only type/properties/required/additionalProperties/enum, and the parser already refuses an empty section list. The schema now uses only constructs with in-repo production precedent.
- verification: Ran on this macOS device. New suite test_document_generation 30. Focused suites — test_document_intent 26, test_execution4a 53 (7 skipped), test_documents 88, test_reliability 10, test_context 14, test_conversations 28, test_ocr 55 (4 skipped), test_reasoning 22, test_c10 19: all passed. Full offline suites — contracts 8, coordinator 811 (12 skipped), deploy/k3s 140, fixtures/c07 32, scripts 25; desktop environment coordinator 811 (4 skipped), desktop 58, frontend 141. All passed. `git diff --check` clean.
- verification: Adversarial self-review confirmed the ordering and the bounds by source: `_general_document` runs before `_write_artifact`, there are exactly two `stream_chat` call sites in the document path, `_general_document` contains no loop, and tests assert one call for a clean reply, two for a repaired one, two however many replies are queued, and one when truncation or a non-repairable code arrives. Cancellation during the repair leaves no artifact and no file.
- changes: Self-review after the first pass found and fixed a correctness defect in the repair itself. The malformed reply was cut to 4,000 characters while the instruction promised to keep every paragraph, so a document past that length would have come back shorter with the remainder silently gone — and would have passed both the enforced schema and the parser, which is the exact failure class this work exists to prevent. Raising the cap alone was not enough: the original prompt plus a full-length reply plus room to rewrite it overruns `runtime.NUM_CTX`, and the runtime is called with truncate and shift off, so that would have failed the repair on precisely the long documents needing it. `general_repair_messages` is now self-contained — the malformed reply and the target shape, with no sources or history resent — which both fits the context at full reply length and removes the material a second draft could have been written from. `MAX_REPAIR_REPLY_CHARS` is derived from the output budget so the cap sits above anything the budget can emit. Five further checks cover whole-reply carriage, context fit at full length, the pathological bound, absence of sources in the repair prompt, and a runtime failure during the repair leaving no artifact.
- remaining: Attempt metrics are recorded before the repair runs, so a repaired document reports the first call's token counts and the repair's are not attributed anywhere. Nothing is fabricated and the counts shown remain measured, but the work is understated; correcting it needs a metrics-only attempt update that does not exist yet and was left out of this batch deliberately.
- remaining: No device evidence that this runtime build honours the nested array-of-object schema — that construct has no in-repo precedent either, and only a real generation on the packaged application can confirm it; a build that ignored `format` would fall back to the repair round, and one that rejected it would fail the request visibly. The approval-note route is still prose-schema only and remains fragile in the same way general generation was; it was deliberately out of scope. Artifact content quality is a model question, not a contract one. No Windows or Linux device evidence; these changes are platform-independent. No installs, model calls, deployments or Git/GitHub writes.

<a id="ac-20260920-001"></a>
## AC-20260920-001 — The approval note is schema-enforced, and its no-procedure case is stated
- prompt_id: [UP-20260920-001](userprompts.md#up-20260920-001)
- date: 2026-09-20
- status: implemented and regression-tested offline; packaged-app verification pending
- tags: documents, approval-note, grounding, citations, structured-output, phase-1
- aliases: APPROVAL_NOTE_FORMAT, APPROVAL_NUM_PREDICT, approval_repair_messages, _structured_reply, Procedure comparison
- paths: backend/coordinator/docflow.py, backend/coordinator/server.py, backend/coordinator/test_approval_note.py, backend/coordinator/test_document_generation.py, agent-memory/
- summary: The fixed grounded workflow now decodes against an enforced schema with its own budget and one substance-preserving repair, and an artifact drafted without a procedure says so.
- verification: Inspection first confirmed that citation grounding was already correct and did not need rewriting. `retrieval.resolve` refuses a source that was not selected and a page that does not exist; `_strict_citations` requires a citation on every finding and fails the whole note on any unresolved one rather than dropping it; `_document_stage` narrows `citation_sources` to the report pages actually sent plus the retrieved passage pages, so a citation to a real page the model never received also fails. Retrieval is already bounded, workspace-scoped, source-scoped and deterministically ordered. Those were covered with regressions rather than changed.
- changes: Confirmed the starting hypothesis — the approval note was still asking for JSON in prose alone. Added `APPROVAL_NOTE_FORMAT`, the narrowest schema matching what `parse_approval_note` accepts, and `APPROVAL_CALL`, attached to the approval branch only. `APPROVAL_NUM_PREDICT` is 3072, sized from MAX_FINDINGS rather than inherited: twenty findings with their citation objects reach roughly 2,000 tokens, and the worst-case prompt still fits inside `runtime.NUM_CTX` with truncate and shift off. `APPROVAL_SCHEMA` stays, because the grammar cannot express its rules — cite only supplied ids, never invent a value, put anything uncited in `unresolved`.
- changes: Factored `_general_document` into `_structured_reply`, taking a parse callable and a repair-message builder, and added `_approval_note` beside it. One helper, two contracts; no second generic framework. The note's repair is self-contained and deliberately does NOT resend the report pages or SOP passages: a model holding the evidence again could redraft a finding or choose a different citation and still pass validation, because the new citation would resolve. Its instruction forbids adding or removing a finding, changing or replacing a citation, supplying an absent measurement, resolving an unresolved item, or adding an approval/compliance/safety conclusion. Enforcement is structural rather than textual — the repaired note meets the same `parse_approval_note` against the same sources, so a citation invented during a repair fails exactly as it would have the first time. `REPAIRABLE_CODES` is reused unchanged, so `unresolved_citation` and `bad_citations` are never repaired.
- changes: Resolved the no-procedure gap. The contract makes the reference corpus optional and nothing invented an SOP, but an artifact drafted from the report alone looked identical to one checked against a procedure. `note_blocks` now adds a "Procedure comparison" section whenever no passage was used, distinguishing "no reference document was selected" from "one was selected but nothing in it matched" because the remedy differs. Coordinator-authored, never model text.
- verification: Ran on this macOS device. New suite test_approval_note 42. Focused suites — test_document_generation 35, test_document_intent 26, test_documents 88, test_execution4a 53 (7 skipped), test_ocr 55 (4 skipped), test_reliability 10, test_context 14, test_conversations 28, fixtures/c07 32: all passed. Full offline — coordinator 857 (12 skipped) plain and 857 (4 skipped) desktop, contracts 8, deploy/k3s 140, scripts 25, desktop 58, frontend 141. `git diff --check` clean.
- verification: The adversarial matrix was run against the real parser. A fabricated suction-pressure value, an uncited swapped reading and limit, an uncited "all readings are within limits", an "inspection passed" with an invented citation, an SOP-compliance claim citing an unselected source, a citation to an absent page and a malformed citation are each refused, and none of their codes is repairable. A coordinator-level hero test drives report plus procedure through extraction, retrieval, generation, citation resolution and a real DOCX that is reopened and read back: 7.9 and 7.1 stay distinct, the loose bolts and the fourteen-day re-inspection survive, suction pressure stays in the unresolved section with no bar figure anywhere near it, and both source hashes appear in the artifact.
- verification: Two test-side defects were found and fixed during the work, both mine rather than the product's. Citations were written against `--- PAGE n ---` markers in the text fixture, but plain-text extraction returns a single page and those markers are a fixture convention, so the citations were genuinely unresolvable and the grounding check was right to refuse them. A repair-isolation assertion keyed on wording that legitimately appears in the note itself and was rewritten against markers unique to the raw fixtures. Page association is now proved separately with a stubbed three-page scan: a citation to page 3 resolves, page 4 is refused, the cited page reaches the artifact and the renderer provenance survives.
- changes: Self-review after the first pass found and closed the most serious hole in the workflow, and it was not one Batch 3 introduced. `parse_approval_note` required a citation on every finding but never required a finding, so a note with `findings: []` carried no citation anywhere and its summary and recommendation were free text: "everything is in order" with "approved for continued operation" passed the *grounded* workflow having cited nothing at all. Every finding needing a citation is worth nothing if a note may have none. Empty findings stay legitimate in the one honest case — the documents established nothing — so the rule mirrors what `parse_read_answer` already applies to an answer: refused as `ungrounded_note` only when `unresolved` is also empty. Not repairable, because repairing it would ask the model to invent the findings it did not make. The check runs after field validation so a missing or oversized title still reports itself rather than being masked by a vaguer grounding error, which is what two existing checks caught when it was placed first.
- changes: Two smaller self-review fixes. The no-procedure sentence claimed no reference document "was selected", which is wrong when one was attached and could not be read — such a file is absent from `prepared.sources` and the block cannot tell the two cases apart — so it now states only what is certainly true and suggests attaching one. `MAX_REPAIR_REPLY_CHARS` was derived from `DOCUMENT_NUM_PREDICT` alone while serving both repairs; it now tracks the larger of the two budgets, so raising either cannot start silently truncating the other.
- remaining: Grounding here is traceability, not verification. A finding that cites a page that exists is accepted without anything comparing the sentence to that page, so a correctly cited but factually wrong claim — the reading and the limit swapped, for instance — still passes. What the contract removes is the uncited and the fabricated claim. The boundary is recorded as its own test rather than left implicit; closing it needs claim-level checking the current architecture does not have. The approval-note grammar shares the general document's unobserved constructs: nested array-of-object is still not device-confirmed against this runtime build. Plain-text sources remain single-page, so page-level citation granularity for them is whole-file. No Windows or Linux device evidence; these changes are platform-independent. No installs, model calls, deployments or Git/GitHub writes.

<a id="ac-20260920-002"></a>
## AC-20260920-002 — Every claim carries its own evidence, and Chat answers as Refinix
- prompt_id: [UP-20260920-002](userprompts.md#up-20260920-002)
- date: 2026-09-20
- status: implemented and regression-tested offline; packaged-app verification pending
- tags: documents, approval-note, citations, identity, chat, phase-1
- aliases: claim_field, bad_claim, identity.py, engine for this reply, installed model count
- paths: backend/coordinator/docflow.py, backend/coordinator/identity.py, backend/coordinator/server.py, backend/coordinator/test_approval_note.py, backend/coordinator/test_identity.py, backend/coordinator/test_documents.py, backend/coordinator/test_execution4a.py, backend/coordinator/test_document_generation.py, agent-memory/
- summary: A note's summary and recommendation now answer for their own evidence, and an ordinary Chat turn states which product is speaking and which engine is running.
- changes: Reproduced the reported gap first — a note whose recommendation read "equipment is fully compliant and approved for unrestricted operation" passed the grounded workflow because an unrelated finding carried a citation. `summary` and `recommendation` are now `{text, citations}` objects, the same shape a finding already used, validated through the same `_strict_citations` and `retrieval.resolve` against the same selected sources. No new resolver and no new representation. `citation_list` now rolls up all three, so the artifact record shows what supported the conclusion rather than only the findings, and `note_blocks` prints their labels the way it prints a finding's. The enforced grammar, the prose rules and the repair instruction were updated together so the schema, the parser and what the model is told cannot drift apart. `bad_claim` is not repairable: supplying a missing citation is substance, not format.
- changes: Ordinary Chat had no system message at all, which is why the packaged application answered "I am Qwen3.5" — true of the weights, wrong about the product. Added `identity.py`, which builds one compact block naming Refinix as the product, the engine as this attempt's own selected model, and the installed model count. It does no I/O of its own, contains no model family or vendor anywhere, and is not an interception layer: there is no phrase list and no canned reply, so "tell me about yourself" works as well as "who are you". It also states that document, attachment and pasted text never redefine those facts.
- verification: Three self-review corrections, all mine. The first draft read the count from `Coordinator.model_inventory`, which asks the runtime for each model's capabilities and asks a paired worker for its list — per-model round trips on the path every Chat message takes. An existing coordinator check caught it by patching a single runtime response, and the block now reads the health probe instead; the cost is that a model installed only on a paired worker is not counted, so the wording says "installed on this computer" rather than implying a complete survey. The second was a resilience test that patched `runtime.probe` to raise, which breaks every caller in the run rather than the identity lookup; it is now two checks, one for an unreachable engine and one for the guard itself. The third was an injection check asserting exactly one system message; an attachment turn now carries two coordinator-authored ones, so it asserts the property that matters — none of them is written by the file — instead of the count, and a second positional assumption beside it was removed.
- verification: The identity block is prepended after `context.select` has chosen what fits, so its tokens are spent outside that budget and the runtime is called with truncate off. Measured at 331 estimated tokens against the 912 the existing safety fraction already holds back, and asserted against that reserve rather than a fixed character count, so a future edit that outgrows the margin fails in a test rather than in front of a person.
- verification: Ran on this macOS device. New suite test_identity 26; test_approval_note 51 (six new citation regressions covering an uncited recommendation, an uncited summary, a grounded recommendation, the resolver applied to recommendation citations, the roll-up, and non-repairability). Full offline — coordinator 895 (12 skipped) plain and 895 (4 skipped) desktop, contracts 8, deploy/k3s 140, fixtures/c07 32, scripts 25, desktop 58, frontend 141. All passed. `git diff --check` clean. A grep across the identity path confirms no model family or vendor name appears in it, and every identity check runs against two model identifiers, one deliberately outside the catalogue.
- changes: A second self-review pass found two more defects in this batch's own work. The installed-model listing was unbounded: past roughly thirty-five models the block outgrew the token margin the conversation budget reserves, and because the runtime is called with truncate off that is a refused request rather than a trimmed one — every message a person sent would have failed once their library grew. The listing is now capped at twelve names with the remainder acknowledged, the exact count is never abbreviated, and a single name is bounded too, so the block holds at roughly 527 tokens whether one model is installed or five hundred.
- changes: The identity lookup had also added a whole extra `runtime.probe` — three loopback calls — to every Chat turn, when the turn already probed once for routing. That probe is now taken once and threaded through `choose_route`, `_local_route` and `local_model_ref` alongside the identity block, all via optional parameters that leave every other caller unchanged. Measured at one probe per turn, which is the pre-change baseline: the identity block now costs no additional runtime I/O at all.
- remaining: Nothing here can force a model to obey the instruction; a sufficiently weak or contrary model could still misdescribe itself, and only device testing shows how this one behaves. The count covers models installed on this computer, not on a paired worker, and it is not a readiness claim — a model present is not a model self-tested. Grounding remains traceability rather than entailment: a claim citing a page that exists is accepted without anything comparing the sentence to that page. No Windows or Linux device evidence; these changes are platform-independent. No installs, model calls, deployments or Git/GitHub writes.

<a id="ac-20260920-003"></a>
## AC-20260920-003 — The document workflow is chosen in the composer, not hidden in model settings
- prompt_id: [UP-20260920-003](userprompts.md#up-20260920-003)
- date: 2026-09-20
- status: implemented and regression-tested offline; packaged-app C07 verification pending
- tags: documents, frontend, composer, approval-note, workflow, phase-1
- aliases: workflow-chip, renderWorkflowChip, DOC_WORKFLOWS, doc_workflow payload
- paths: frontend/app/index.html, frontend/app/app.js, frontend/app/refinix.css, frontend/app/test-composer.cjs, backend/coordinator/test_approval_note.py, agent-memory/
- summary: The fixed approval-note workflow can now be selected beside the skill it belongs to, and the selected value is proved to change the backend route.
- verification: The reported root cause was refined before any edit. The chooser was not missing: `DOC_WORKFLOWS`, `appendDocumentChoices` and the `doc_workflow` payload field all existed and were correct. The control was rendered only inside the model-settings popover — `role="dialog"`, labelled Model settings — so a person selecting Write a document saw the skill chip and nothing else. The defect was discoverability, not absence, which is why the repair surfaces the existing state rather than building a second control. The "It makes no page citations" sentence was also accurate: it is the general route's own wording from `docflow.written_answer`, so it correctly reported the route that ran.
- changes: Added a workflow control to the composer beside the skill chip — a labelled native select, shown only while Write a document is selected, defaulting to General document so existing general requests cannot silently become the industrial workflow. It reads and writes the same `docWorkflow` state the popover already used and renders from the same `DOC_WORKFLOWS` list, so the two views cannot drift and no workflow identifier is duplicated; the identifier itself is now named once as `APPROVAL_NOTE_WORKFLOW`. Choosing the approval note reveals one line of help about the positional attachment contract — inspection report first, further files optional references — shown only for the workflow whose result depends on that order. The chip disappears with the skill, and an ordinary turn sends no workflow at all.
- changes: No prompt classifier and no phrase inference: selection stays explicit application state. The payload wiring was already correct and was left alone. Styling reuses the skill chip's own tokens; three custom properties written in the first draft (`--ink`, `--ink-soft`, `--focus`) do not exist in this stylesheet and were replaced with the real `--text`, `--text-faint` and the `--veil` focus treatment used elsewhere, after checking each one resolves.
- verification: Ran on this macOS device. Nine new composer checks cover the workflow being visible and defaulting to general, the approval note being selectable and sticking, the help line appearing only for it, the sent body carrying `skill_id=write-document` with the chosen `doc_workflow`, the default sending `general_document`, attachment add and remove leaving the choice alone, skill removal hiding the control and sending no workflow, `read-document` and `search-documents` neither showing nor sending one, and the two views sharing one value. Five new coordinator checks drive `submit` with the same files and the same wording under each workflow and prove the routes differ: the approval note reaches the grounded branch with its own schema and recorded citations, the general value reaches the general branch with none, the "no page citations" sentence appears on the general route and never on the grounded one, and an unknown workflow value is refused at the boundary so the two lists cannot drift into something silently ignored.
- verification: frontend 150, coordinator 903 (12 skipped) plain and 903 (4 skipped) desktop, contracts 8, deploy/k3s 140, fixtures/c07 32, scripts 25, desktop 58. All passed. `git diff --check` clean and `node --check` clean.
- remaining: Not device-verified. The packaged application must be rebuilt before the control exists in it, and the C07 acceptance run is the checkpoint. The generic run's impossible date and SOP-identifier wording were deliberately not touched: that output came from the general route, and whether it recurs through the grounded route is a separate question that only the rerun can answer. The positional attachment contract is unchanged — first file is the report — and is now explained rather than enforced in the page. No Windows or Linux device evidence. No installs, model calls, deployments or Git/GitHub writes.

<a id="ac-20260920-004"></a>
## AC-20260920-004 — The prompt gets its own row; configuration gets its own
- prompt_id: [UP-20260920-004](userprompts.md#up-20260920-004)
- date: 2026-09-20
- status: implemented and regression-tested offline; packaged-app UX verification pending
- tags: frontend, composer, layout, accessibility, documents, phase-1
- aliases: composer-task, composer-hint, renderTaskRow, prompt width
- paths: frontend/app/index.html, frontend/app/app.js, frontend/app/refinix.css, frontend/app/test-composer.cjs, agent-memory/
- summary: The skill and workflow controls moved out of the prompt's flex row, and the attachment-order line stopped wearing the caution colour.
- verification: Two causes, one of them introduced by the previous batch. `.composer-line` was a wrapping flex row holding the skill chip, the workflow chip and the textarea together, with the textarea at `flex: 1 1 16rem; min-width: 12rem` — so every control took width from the writing area, and adding the workflow chip turned an existing squeeze into a narrow column. Separately, the attachment-order helper was given `class="skill-status"`, which is `--st-caution`: ordinary advice about how files are read was rendered in the colour reserved for an unavailable capability, which is why it read as a warning.
- changes: Added a `composer-task` row above the prompt holding the skill chip and the workflow chip, wrapping when there is more configuration than fits. `composer-line` now holds the label and textarea alone, and the input is `flex: 1 1 auto; width: 100%; min-width: 0`, so the prompt owns its row at every width and the fixed 12rem floor beside controls is gone. `renderTaskRow` hides the row when neither chip is shown, so an empty configuration band never appears above the prompt; it is called from both `renderSkill` branches, from the select's change handler and from the model-settings picker, so every path that can change chip visibility updates it.
- changes: The helper moved to its own `composer-hint` class in the muted `--text-faint` tier with a decorative circled-i, and its wording shortened to describe how the files will be read rather than instructing after the fact. `skill-status` keeps the caution tier for the case it was written for. All five custom properties used were checked against the stylesheet first — the earlier batch shipped three invented ones, and the grep used to confirm them missed multi-declaration lines, so both the tokens and the check were redone.
- changes: No state was added. The control is still the same native select over the same `DOC_WORKFLOWS`, reading and writing the same `docWorkflow`, and the model-settings view remains a second view of that one value. Send payload logic untouched.
- verification: Ran on this macOS device. Six new composer checks cover the task row preceding the prompt row in the markup with no control sharing the prompt row, the row hiding when nothing configures the request, the helper carrying `composer-hint` and never `skill-status` and containing no failure language, the helper being absent for the general workflow, two attachments plus a chosen workflow surviving together, and Send still carrying both the text and the chosen `doc_workflow`. Structural claims are asserted against `index.html` because the harness's document does not parse markup. frontend 156 passed; coordinator 903 (12 skipped) confirms the backend was untouched. `git diff --check` clean, `node --check` clean.
- changes: Self-review corrected two accessibility details and one claim. The circled-i is CSS generated content, which most engines DO place in the accessibility tree, so the previous report's claim that it was out of it was wrong; it now carries `content: "\\24D8" / ""` so the alternative-text syntax silences it where supported and it degrades to being read where not. The select also gained `aria-describedby="workflow-hint"`, so the guidance is announced with the control it describes rather than only being reachable by scanning the page; when the general workflow hides the guidance, assistive technology ignores the hidden target and nothing extra is said.
- verification: Checked the Code surface for collateral damage, since `.composer-line` is shared. `code.html` uses it for a label and a textarea only, which is exactly the shape Chat now has, so removing the wrap and the 12rem floor is beneficial there rather than harmful; its suite passes. Confirmed chip visibility is set in only two functions and `renderTaskRow` follows both on every path, so the configuration row cannot be left showing when empty or hidden when populated. Confirmed the CSS escape survived the edit as a single backslash rather than a literal one.
- remaining: Not visually verified. Automated checks prove structure, state and payload, not that the result looks right at a given width — the packaged rebuild is the checkpoint. The positional attachment contract is unchanged and still only explained, not enforced. No Windows or Linux evidence. No backend, model, routing or Git/GitHub changes.

<a id="ac-20260920-005"></a>
## AC-20260920-005 — Takeover review closed three inherited edge cases
- prompt_id: [UP-20260920-005](userprompts.md#up-20260920-005)
- date: 2026-09-20
- status: implemented and regression-tested offline; packaged and cross-platform evidence remains open
- tags: takeover, review, phase-1, data-root, identity, frontend, containment
- aliases: workflowWired, unreadable occupancy, runtime_state fallback, Windows Code gate
- paths: backend/coordinator/paths.py, backend/coordinator/server.py, backend/coordinator/test_paths.py, backend/coordinator/test_identity.py, frontend/app/app.js, frontend/app/test-composer.cjs, agent-memory/
- summary: Reconciled the supplied handover against current authority and source, preserved the inherited dirty tree, and fixed three concrete defects without changing the product contract.
- changes: The workflow select used the test harness's private `handlers` field as its idempotence check; real DOM nodes do not have that field, so repeated skill renders accumulated change listeners. It now marks the real element with `data-workflow-wired`, and the harness keeps handler storage private so the regression cannot hide behind test-only state.
- changes: Data-root inspection treated every top-level `OSError` as an empty root. An unreadable legacy root could therefore be replaced by a new native store, creating two possible canonical workspaces. Unreadable roots and entries now have an explicit occupied state; a genuinely missing root remains empty.
- changes: A paired-worker route that fell back locally discarded the Chat turn's already-observed runtime state, causing another probe and allowing attempt routing metadata and the product-identity message to disagree. The same observation is now threaded through that fallback, with a regression asserting one probe and one engine identity.
- verification: Fresh focused checks on this macOS source tree: 373 backend, desktop lifecycle and C07 fixture tests passed in total. The combined run passed 372 and hit one sandbox-only loopback bind refusal; that exact test then passed alone with loopback access. Composer 59 passed, `node --check frontend/app/app.js` passed, and `git diff --check` passed.
- remaining: The supplied packaged-app observations remain user-reported device evidence rather than fresh agent evidence. Exact claim-to-page acceptance for the produced approval-note DOCX cannot be closed without the artifact, and the report-only packaged run is still pending. Remote Chat identity parity remains deliberately deferred. Windows Code remains fail-closed because its current containment relies on POSIX descriptor-relative operations; replacing that with ordinary resolved paths would weaken the security contract. No Windows/Linux device evidence, installs, model calls, remote-worker calls, deployments or Git/GitHub writes.

<a id="ac-20260920-006"></a>
## AC-20260920-006 — Approval notes preserve report evidence and semantic structure
- prompt_id: [UP-20260920-006](userprompts.md#up-20260920-006)
- date: 2026-09-20
- status: implemented and regression-tested offline; packaged-app C07 rerun pending
- tags: documents, approval-note, evidence-coverage, docx, accessibility, phase-1
- aliases: report_evidence, open_items, Report details, numbering.xml, styles.xml
- paths: backend/coordinator/docflow.py, backend/coordinator/docgen.py, backend/coordinator/pdfgen.py, backend/coordinator/server.py, backend/coordinator/test_approval_note.py, backend/coordinator/test_documents.py, backend/coordinator/test_execution4a.py, agent-memory/
- summary: Coordinator-owned evidence now prevents explicit report gaps from disappearing, and generated DOCX artifacts carry real heading and list semantics.
- changes: The validator previously proved only that emitted claims cited real pages; it could not detect a material field the model omitted. The coordinator now conservatively copies bounded labelled report identity and explicit missing/open values from the same bounded pages already supplied to the model, attaches page citations, and appends them as Report details and Open items recorded in the report. This covers the omitted countersignature without attempting general semantic completeness or adding a second model call.
- changes: DOCX packages now include minimal native styles and numbering parts. Titles, headings, numbered findings, bullets and quoted notes are encoded as semantic OOXML paragraphs; PDF output keeps equivalent visible markers. The portable default font is Arial and no dependency was added.
- verification: Ran 205 focused coordinator document, approval-note and PDF tests; all passed. `git diff --check` passed. Generated and rendered a fresh representative DOCX with the bundled document runtime: one page, readable sans-serif layout, no clipping or overlap, correct report details, numbered findings, open-item bullets and the cited not-countersigned field.
- remaining: The existing user artifact is unchanged. A rebuilt package and report-only C07 run are still required for installed-app acceptance. Citation resolution remains traceability, not semantic entailment. No live model, packaged-app, Windows/Linux, deployment or release evidence was produced.

<a id="ac-20260920-007"></a>
## AC-20260920-007 — Windows Code containment, model lifecycle and truthful device labels
- prompt_id: [UP-20260920-007](userprompts.md#up-20260920-007)
- date: 2026-09-20
- status: implemented and regression-tested offline; Windows and Linux device evidence, packaging tools and live-model evidence remain open
- tags: phase-1, phase-2, standalone, windows, containment, model-lifecycle, packaging, capability-truth
- aliases: winfs, pinned-handle, containment_supported, models.py, device.py, packaging.py, selftest, FILE_SHARE_DELETE, FILE_FLAG_OPEN_REPARSE_POINT
- paths: backend/coordinator/winfs.py, backend/coordinator/repo.py, backend/coordinator/models.py, backend/coordinator/device.py, backend/coordinator/server.py, backend/coordinator/db.py, backend/coordinator/docgen.py, backend/coordinator/proof.py, backend/coordinator/code_service.py, backend/coordinator/dispatch.py, backend/coordinator/paths.py, backend/coordinator/test_repo_windows.py, backend/coordinator/test_models.py, backend/coordinator/test_paths.py, backend/coordinator/test_c10.py, backend/coordinator/test_code_access.py, backend/coordinator/test_approvals.py, backend/coordinator/test_execution4b.py, backend/coordinator/test_execution4c.py, backend/coordinator/test_remote_code.py, desktop/packaging.py, desktop/lifecycle.py, desktop/setup_py2app.py, desktop/test_packaging.py, desktop/test_lifecycle.py, frontend/app/app.js, frontend/app/control.html, frontend/app/refinix.css, frontend/app/test-models-card.cjs, frontend/app/test-composer.cjs, frontend/app/test-proof-card.cjs, agent-memory/
- summary: Code is no longer structurally unavailable on Windows, Settings now carries a bounded model lifecycle, and device and capability labels state what was observed rather than which machines the prototype ran on.
- changes: Windows had no `openat`, so the whole Code surface failed closed there. `winfs.py` supplies the same containment guarantee from two documented Win32 behaviours: `FILE_FLAG_OPEN_REPARSE_POINT` opens the link rather than its target, so the handle always holds the object that was checked, and a handle taken without `FILE_SHARE_DELETE` pins every ancestor against rename and delete for the whole operation, which makes opening the next component by full path equivalent to `openat`. Directory handles ask for no access at all, so `FILE_FLAG_BACKUP_SEMANTICS` cannot override a file permission on the way. Data transfer uses ordinary `os` calls on a descriptor adopted from the handle, keeping the native surface small.
- changes: `repo.py` now dispatches to a POSIX or a Windows backend behind one gate. `descriptor_traversal_supported` keeps its POSIX meaning, and `containment_supported`/`containment_backend` became the question the surface asks; all callers and tests were moved to them. The bounds, refusal codes, stale-hash check, atomic replacement and identity checks are shared, so the two backends differ only in how a name becomes an open object. `canonical_root` now refuses a Windows junction or mount point, which `Path.is_symlink()` does not report, and refuses the Windows system folders by name under a drive root; `root_is_intact` refuses a root that became a reparse point. Where neither backend is available the surface stays fail-closed.
- changes: `models.py` holds the curated catalogue, which is deliberately one entry — the only artifact whose source, licence, manifest digest, layers and runtime floor were recorded. The recorded OCR conversion is annotated but never offered, because its provenance is unresolved. Four states are kept apart: installed, absent, installed-without-recorded-provenance, and unknown-because-the-engine-did-not-answer; whether Refinix vouches for a model is a separate answer carried by `provenance`. Settings -> Models is a new Control Center card showing each model's state, recorded source and licence, self-test state, install command when absent, an enable/disable switch and a removal-impact report. Refinix still downloads and removes nothing: both are commands the person runs.
- changes: Capability self-tests were added with per-model, per-workflow results stored against the manifest digest they were observed on, so replacing a model's bytes under the same tag supersedes the result rather than inheriting a pass. `model_prefs` gained an `enabled` column and a `model_selftests` table (schema 11, additive). A disabled model stops being eligible for new work and is refused by `select_model`; nothing is deleted and no running attempt changes.
- changes: Device labels are now roles. Model locations and Proof Card attribution come from `device.location_label`, so a Windows or Linux installation no longer reports work as having run on a "macOS coordinator" or "Ubuntu worker", and the frontend's execution-target list names a paired worker rather than a distribution. `status` gained an observed `device` block, reports the Code surface from what this computer can actually do rather than a hard-coded "available", and reports which artifact formats can be written — the composer now disables PDF with its reason on a computer without the macOS frameworks instead of accepting the choice and failing at Send.
- changes: `docgen_available` was a `hasattr` check; it now writes a small document to a temporary folder and reopens it once per process, so Documents reports a real observation. `desktop/packaging.py` holds the application boundary — modules, frontend files, platform assets, exclusions and probe-based prerequisites — which `setup_py2app.py` now consumes, so a Windows or Linux package step uses the same answers instead of a second list. Each platform's plan states whether this repository pins its tool; only macOS does. The engine spawn detaches correctly on Windows (`start_new_session` is POSIX-only and was silently ignored there), and a relative `LOCALAPPDATA` no longer produces a candidate path tested against the launch directory.
- verification: Ran on this macOS device. Under the repository interpreter: 1002 coordinator tests (12 skipped), 82 desktop tests, 8 contract tests, 165 of 166 worker tests, 32 fixture tests, 25 script tests. Under the desktop packaging interpreter, which carries PyObjC and pypdfium2: the same 1002 coordinator tests with only 4 skips, closing the PDF-writer skips. Frontend: 180 Node checks across seven files, `node --check` clean, `git diff --check` clean. The Windows backend has 38 focused checks driven through `repo.py` by a `CreateFileW` emulator over a real directory tree; it asserts at every call that no name is opened without `FILE_FLAG_OPEN_REPARSE_POINT` and no handle with `FILE_SHARE_DELETE`. Generated a representative synthetic approval note as both `.docx` and `.pdf` and inspected the single rendered page: citations, uncertainty, source hashes, the OCR confidence note and Punjabi/Hindi/Japanese/Greek text all correct.
- changes: Self-review corrected four defects it found. A Windows write whose temporary file was created and then failed inspection left the file in the user's project folder; it is now removed, except when the failure was a name collision, where removing it would delete a file Refinix did not create. The Windows listing reopened the whole chain from the root for every folder; it now descends with a held parent, as the POSIX walk does. `lifecycle_state` reported an ordinary missing model as "unknown" when Refinix had no manifest for it, conflating absence with an unreachable engine. A `/v1/models` route and a status catalogue copy duplicated what `/v1/status` already carried and nothing read them; both were removed, and the removal-impact route is now used by the card instead of being dead. `paths._platform_label` was folded into `device.os_label`, and a local named `models` that would shadow the new module was renamed.
- remaining: No Windows or Linux device evidence. The Windows containment backend is source-present and exercised through an injected API; the real `kernel32` binding has never executed, and no support claim follows from these tests. No Windows or Linux packaging tool is pinned, so no package for either can be built from this checkout — the application boundary is complete and pinning the tool plus running it on the profile is the remaining step. No model was downloaded and no live model was called, so every self-test path is proved with fakes and fixtures rather than against a running engine. PDF writing stays macOS-only and capability-gated; Word remains the portable artifact. `backend/worker/test_worker_app` cannot import because `fastapi` is not installed in any local environment, which predates this batch. Remote Chat parity, trusted-mesh work, sandbox qualification and Proof Card egress evidence remain in their later phases. No installs, downloads, deployments, credential changes or Git/GitHub writes.
- changes: A second review pass over the whole diff found and fixed five more defects, four of them in code no test could have reached. `winfs` compared `CreateFileW`'s result against a literal `-1`, but ctypes returns a `HANDLE` as an unsigned pointer-width int, so `(HANDLE)-1` arrives as 0xFFFFFFFFFFFFFFFF and the check would have matched nothing on any Windows build: every refused open would have been read as a success and then failed at the next call with "invalid handle" instead of "the file is not there", which also defeated the temporary-name collision guard. The sentinel is now computed at bind time from the same pointer width ctypes is using. `_open_osfhandle` was being passed `_O_WRONLY`, which its documented flag set does not include; the descriptor's access comes from the handle, so only the binary flag is passed now — that one is load-bearing, because text mode would rewrite line endings under a hash.
- changes: A stored self-test could read as current when the installed model's digest could not be observed at all — the engine down, or the model uninstalled — which let an absent model look ready. A pass is now current only against a digest that matches what is installed; when nothing can be observed it is neither current nor superseded, and the interface says "self-test not confirmed here" rather than "passed" or "not self-tested". The Windows write path also cleaned up its temporary file at each raise rather than in one `finally`, so a failure it did not anticipate left both a descriptor and a stray file in the user's project folder; it now mirrors the POSIX structure exactly, cleaning up unless the file was promoted and never touching a name that was somebody else's to begin with. `select_model` reported a model that was both absent and switched off as "switched off", sending the person to a control that would not have helped.
- changes: Smaller corrections from the same pass: the self-test now asks `/api/show` only for the one check that needs a modality instead of on every run, and watches the coordinator's stopping flag so quitting during a cold model load does not wait out the runtime's full request timeout; a model row printed its state twice, once under the name and once as a chip, and the sub-line now says where the model is; a removal report with no command would have rendered "run null yourself"; `selftest_view` took a `runtime_version` it never read; `provenance` set one key twice; `packaging` imported `field` unused.
- verification: Re-ran everything after the corrections. Under the repository interpreter: 1010 coordinator tests (12 skipped) and 82 desktop tests. Under the desktop packaging interpreter: the same 1010 with 4 skips. Frontend: 186 Node checks across seven files. Regenerated the representative approval note and re-rendered its page: byte-identical to the pre-correction render, with only the document's creation timestamp differing between runs, so none of these corrections changed what is produced. `node --check` and `git diff --check` clean.

<a id="ac-20260921-001"></a>
## AC-20260921-001 — Model execution and trust evidence now agree
- prompt_id: [UP-20260921-001](userprompts.md#up-20260921-001)
- date: 2026-09-21
- status: implemented and regression-tested offline; live-model, package and cross-device acceptance remain open
- tags: model-lifecycle, selftest, provenance, remote-chat, containment, frontend
- aliases: model_disabled, integrity mismatch, representative checks, system_instruction, final stale check, local model count
- paths: backend/contracts/v1.py, backend/contracts/examples.json, backend/coordinator/code_service.py, backend/coordinator/dispatch.py, backend/coordinator/docgen.py, backend/coordinator/documents.py, backend/coordinator/identity.py, backend/coordinator/models.py, backend/coordinator/ocr.py, backend/coordinator/repo.py, backend/coordinator/server.py, backend/coordinator/winfs.py, backend/worker/executor.py, frontend/app/app.js, related tests, agent-memory/
- summary: New work now honours model enablement and observed manifest integrity, self-tests exercise production-shaped workflows, remote Chat receives Refinix identity, file replacement rechecks immediately before promotion, and Settings distinguishes local from worker-only models.
- changes: Chat, Documents, OCR and Code refuse a disabled selected model before a model call; routing refuses known catalogue entries whose observed digest is absent or mismatched, while unlisted models remain plainly unverified. Self-tests now use each workflow's production messages, strict schema and parser, including a standard-library generated OCR image and a model-derived DOCX write/reopen. The remote envelope carries a bounded Refinix identity system instruction consumed as a system-role message by Chat workers. POSIX and Windows replacement paths re-open, re-identify and re-hash the target after the temporary file is durable and immediately before atomic replacement; Windows uses an exclusive final verification handle. Status and Settings report local eligibility separately from worker availability and never count a worker-only model as installed here.
- verification: Ran 1020 coordinator tests with 12 expected skips, 174 contract and dependency-free worker tests, and 187 frontend tests; all passed. The reasoning/loopback group also passed 24 tests with local bind access. Changed Python modules compiled, and `git diff --check` passed.
- remaining: No live model self-test, packaged application, real Windows `kernel32`, Linux device, paired-worker device or release gate was exercised. The Windows close-to-rename boundary cannot be held across `os.replace`; the second exclusive check narrows it to the required final syscall boundary. `backend/worker/test_app.py` remains unrun because the existing environment has no FastAPI, and no dependency was installed. No protected documentation or Git/GitHub state was changed.

<a id="ac-20260921-002"></a>
## AC-20260921-002 — The internal package plan no longer shadows setuptools
- prompt_id: [UP-20260921-002](userprompts.md#up-20260921-002)
- date: 2026-09-21
- status: implemented and regression-tested offline; package rebuild and human acceptance not performed
- tags: macos, py2app, setuptools, packaging, module-shadowing
- aliases: packaging_plan.py, packaging.utils, build path import
- paths: desktop/packaging_plan.py, desktop/setup_py2app.py, desktop/test_packaging.py, agent-memory/
- summary: The shared Refinix packaging boundary keeps its design under a non-conflicting module name, and the failing macOS import order now resolves third-party `packaging` correctly.
- changes: Renamed `desktop/packaging.py` to `desktop/packaging_plan.py`, updated the py2app setup script and packaging tests to import that explicit module, and added a subprocess regression that inserts `desktop` first on `sys.path` before importing both `packaging` and `packaging.utils`.
- verification: The 35 desktop packaging tests passed under `desktop/.venv`. The direct reproduction resolved `packaging` to `desktop/.venv/lib/python3.12/site-packages/packaging/__init__.py`; touched files compiled and `git diff --check` passed. Lifecycle code was untouched, so its suite was not rerun.
- remaining: No py2app package rebuild, signature/content verification, launch or human acceptance walkthrough was performed. No dependencies, protected documents or Git/GitHub state were changed.

<a id="ac-20260921-003"></a>
## AC-20260921-003 — The setup entry imports the way the setup command runs it
- prompt_id: [UP-20260921-003](userprompts.md#up-20260921-003)
- date: 2026-09-21
- status: implemented, regression-tested, package built and inspected; human GUI acceptance not performed
- tags: macos, py2app, packaging, direct-script-import, bundle-inspection
- aliases: No module named 'desktop', runpy direct-script regression, Refinix.app candidate
- paths: desktop/setup_py2app.py, desktop/test_packaging.py, agent-memory/
- summary: `desktop/setup-macos.command` executes the setup file by path, so the repository root is never on `sys.path`; the setup entry now imports its packaging boundary as the sibling module that invocation actually resolves, and a regression runs the file the same way.
- changes: Replaced `from desktop import packaging_plan` with `import packaging_plan` in `desktop/setup_py2app.py` and recorded in its docstring that the file is a script run by path, not a module imported as `desktop.setup_py2app`. `setup_module_namespace()` now executes the source with `desktop` on `sys.path` so the in-process helper resolves what the build resolves, and a new subprocess regression runs the real file through `runpy.run_path` under `-P` with `run_name="not_main"`, which reproduces direct-script import conditions without starting a build. The existing third-party `packaging` collision regression is unchanged, the staged-source `sys.path` insertion before py2app setup is untouched, and `packaging_plan.py` was not modified.
- verification: 36 desktop packaging tests passed under `desktop/.venv` (35 before, plus the new regression). The new regression was confirmed to fail against the `c4a5a28` source with the original `ModuleNotFoundError: No module named 'desktop'`. `packaging` still resolved to `desktop/.venv/lib/python3.12/site-packages/packaging/__init__.py` with `desktop` first on the path; touched files compiled and `git diff --check` passed. `./desktop/setup-macos.command` then completed: `pip check` reported no broken requirements, py2app built `desktop/dist/Refinix.app` (48 MB, arm64 thin, `com.refinix.desktop`, 0.1.0, `LSMinimumSystemVersion` 12.0, local networking allowed with no arbitrary-loads exception), and `/usr/bin/codesign --verify --deep --strict` passed against the ad-hoc signature. `verify_application_contents` passed through the repaired import path; the bundle ships 35 application modules, the ten frontend files byte-identical to the working tree, `webview`, `pypdfium2`/`pypdfium2_raw` with `libpdfium.dylib`, and `Quartz`/`objc` in `python312.zip`; a scan found no worker, test, fixture, deploy, docs, virtual-environment, model-weight or user-state file. The only build warnings were `strip` re-sign notices and modulegraph optional-backend `missing conditional` lines.
- remaining: The package is built and inspected, not accepted. The setup script opened the package, but no human GUI or workflow acceptance observation was performed: no Chat, Documents, Code, self-test, disabled-model refusal, manifest-mismatch or persistence observation was made, and the signature is ad-hoc rather than Developer ID or notarised. No remaining macOS packaging blocker was observed. Windows and Linux remain unbuilt. `desktop/build`, `desktop/dist` and `desktop/build.log` are generated output. No dependency, lock, protected document or Git/GitHub state was changed.

<a id="ac-20260921-004"></a>
## AC-20260921-004 — Relation direction in Chat, and reference identity in grounded notes
- prompt_id: [UP-20260921-004](userprompts.md#up-20260921-004)
- date: 2026-09-21
- status: implemented and regression-tested offline; current package rebuild, live-model observation and human GUI acceptance pending
- tags: chat, reliability, documents, grounding, cross-source-identity, macos-acceptance
- aliases: reversed NPSH relation, SOP-MECH-814 vs SOP-MECH-014, TECHNICAL_CARE, reference_conflicts
- paths: backend/coordinator/identity.py, backend/coordinator/models.py, backend/coordinator/docflow.py, backend/coordinator/server.py, backend/coordinator/test_identity.py, backend/coordinator/test_models.py, backend/coordinator/test_approval_note.py, agent-memory/
- summary: Two failures with one theme — fluency is not proof. A technical answer was confident and had its central comparison backwards, and an approval note's citations all resolved while the identity of the governing procedure was never established.
- changes: `identity.TECHNICAL_CARE` is added to the system block every ordinary Chat turn already carries, local and remote alike, asking the model to check the reversible part of a relation — which side of a comparison is larger, available against required, minimum against maximum, causal direction, units — and to name its uncertainty rather than pick a direction. It states no fact about any subject. The Chat self-test no longer asks "what is 2 + 2?" and accepts any non-empty reply; it supplies two numbers and a rule and checks both the verdict and which number the reply puts on the smaller side, so a model that writes fluently while reversing the comparison now fails and is recorded as failed. In Documents, `docflow.reference_conflicts` compares the governing identifier the report states against the identifier each selected reference declares for itself, using `named_identity` for the report's labelled field and `declared_identity` for a reference's own header, anchored to a line start so an asset tag is not read as a document's identity. A differing identifier or revision is preserved as coordinator-owned evidence with citations to both sources, rendered above the summary as "Reference identity not established", and `REFERENCE_QUALIFIER` is attached to the recommendation by the coordinator rather than requested from the model. Identifiers are never reconciled: OCR-confusable characters only change the wording to say a misreading is possible. Review found three defects in the first attempt and they are corrected here. The conflict was rendered beside a note that still called 7.1 an alarm limit, so it warned without constraining anything; `parse_approval_note` now refuses a claim that judges the inspection against an unestablished reference's limit, with `unresolved_reference` outside `REPAIRABLE_CODES`, and the companion Chat answer carries the conflict above the summary. A follow-up review found that uncertainty wording anywhere in the claim exempted a later definitive judgement; that exemption is removed, so the model cannot acknowledge unresolved identity and then judge the asset anyway. The Chat validator searched for a verdict token and a number independently, which passed "not unsafe; smaller number: 2.4" and a reply that answered then contradicted itself; it now requires the asked-for line by `fullmatch` and reports a wrong shape and a reversed relation as different failures. Identifier extraction matched upper case only, so a `sop-mech-014` header declared no identity and silently skipped the comparison; it is case-insensitive before normalising, with a digit requirement so `drive-end` is not read as a document number, and a line-start identifier carrying a revision wins over a bare one so an asset tag beginning a line cannot become the reference's identity.
- verification: 1,067 coordinator tests passed with 12 expected skips, including 96 in `test_approval_note`, 66 in `test_models` and 33 in `test_identity`; 8 contract tests passed. The three test files go from 148 to 195 test methods: 47 net new focused regressions, covering exact match, identifier mismatch, revision mismatch, a revision only one side states, a report naming no standard, a reference naming none, OCR near-matches, an unrelated document, citations to both sources, selected-references-only comparison, an AST check that no identifier or limit from the observed run is reachable as an executable constant, refusal of the noncompliant scripted note against acceptance of the same evidence stated conditionally, negated and self-contradicting Chat replies, and lowercase headers matching and mismatching. Touched files compiled and `git diff --check` passed. `./desktop/setup-macos.command` rebuilt `desktop/dist/Refinix.app` before the review corrections; `codesign --verify --deep --strict` and `verify_application_contents` passed against that build.
- remaining: The packaged bundle on disk predates the review corrections — `models.py`, `docflow.py` and `server.py` in it no longer match the working tree — because Refinix was running and the app was not terminated to rebuild it. A rebuild after quitting the app is required before any packaged observation. No live model call was made: the Ollama server was not running on this computer and starting a host daemon was not authorised, so the exact reversed-relation prompt has not been measured against the real engine and the escalation question — whether instruction and self-test alone are enough — is unanswered. Neither fix is human-accepted; both need the packaged reruns. The out-of-scope cancellation telemetry gaps (runtime, stop reason, output tokens, reply limit reported as not measured) were left untouched, as were Windows and Linux packaging. No dependency, lockfile, schema, fixture, protected document or Git/GitHub state was changed.

<a id="ac-20260921-005"></a>
## AC-20260921-005 — Local inference envelopes now fit what they promise
- prompt_id: [UP-20260921-005](userprompts.md#up-20260921-005)
- date: 2026-09-21
- status: implemented and regression-tested offline; live-model, distributed-route, package and device acceptance remain open
- tags: inference, context-budget, code, documents, telemetry, model-quality
- aliases: dynamic Code output, whole-file preflight, shared source budget, actual output_token_limit
- paths: backend/coordinator/runtime.py, backend/coordinator/context.py, backend/coordinator/codeflow.py, backend/coordinator/code_service.py, backend/coordinator/docflow.py, backend/coordinator/server.py, related tests, agent-memory/
- summary: Local Code and Documents now size complete requests against the qualified runtime window, and telemetry reports the output allowance actually sent.
- changes: Runtime metrics use the request's real `num_predict`. Documents counts the complete built prompt, shares its source room between report and references, and trims deterministically until it fits. Code raises the whole-file output allowance when the selected result fits, refuses impossible selections before inference, and repairs malformed JSON without resending source files.
- verification: 1,072 coordinator tests passed with 4 expected skips; the 224 unique focused tests passed, including the reasoning group rerun with loopback access after the sandbox refused temporary binds. `git diff --check` passed.
- remaining: No live model, package or device run was performed. The worker stays at its separate 4,096-token/no-reasoning/current-request envelope, remote Code keeps its fixed contract, and the local profile remains the currently qualified 8,192-token window rather than an advertised model maximum. Code still returns whole files and therefore rejects selections whose maximal valid response cannot fit. The unlisted-model trust-contract mismatch remains outside this correction. No protected documentation or Git/GitHub state was changed.

<a id="ac-20260921-006"></a>
## AC-20260921-006 — Qualified profiles now govern local and worker inference
- prompt_id: [UP-20260921-006](userprompts.md#up-20260921-006)
- date: 2026-09-21
- status: implemented and regression-tested offline; worker API dependency, deployment configuration and physical-device acceptance remain open
- tags: inference-profile, contract-1.1, worker-negotiation, route-parity, compatibility
- aliases: ExecutionProfile, InferenceRequest, inference.metrics, profile refusal, bounded remote history
- paths: backend/contracts/profiles.py, backend/contracts/v1.py, backend/coordinator/runtime.py, backend/coordinator/server.py, backend/coordinator/dispatch.py, backend/coordinator/code_service.py, backend/coordinator/db.py, backend/worker/runtime.py, backend/worker/app.py, backend/worker/executor.py, related tests, agent-memory/
- summary: Local and distributed inference now consume exact measured model/runtime/device/workflow profiles; remote execution carries bounded Chat history and cannot silently change reasoning, decoder, context or output semantics.
- changes: Audited inherited commit 0703511 and retained its shared profile registry, contract 1.1 inference request/messages/metrics, additive attempt persistence, profile-aware local runtime, bounded worker advertisement, admission validation and executor-side revalidation. Corrected legacy 1.0 health serialization so the new profile field is omitted rather than emitted empty, and prohibited 1.0 events from claiming 1.1 inference metrics. Code now reuses one runtime observation for model, profile and route selection. Migrated the broad offline harness to exact qualified observations without weakening production fail-closed behaviour. Added proofs that multi-turn Chat history and the same inference semantics reach the worker unchanged and that local and remote attempts persist the requested and actual profile.
- verification: The complete coordinator suite passed 1,073 tests with 4 platform skips. Contract and dependency-free worker suites passed 179 tests. Focused parity, reasoning and remote-Code checks passed 118 tests; the desktop integration suite passed 35 tests with loopback permission. `git diff --check` passed.
- remaining: `backend.worker.test_worker_app` could not import because FastAPI is not installed in the available local interpreters; no dependency was installed. No live Ollama call, worker deployment, package rebuild, real paired-LAN route, Windows/Linux run or release gate was exercised. The current worker registry truthfully advertises only the measured 4,096-token Chat profile with reasoning disabled; remote Code therefore refuses until separately qualified. A deployed exact Ubuntu worker must be given `AEGIS_TARGET_PROFILE_ID=hp-victus-i5-13420h-rtx2050-4gb-ubuntu-24.04` and rechecked against Ollama 0.33.2 plus the recorded model digest before it can advertise that profile. No protected documentation or Git/GitHub state was changed.

<a id="ac-20260921-007"></a>
## AC-20260921-007 — Mac Chat, Code and Documents qualified on Ollama 0.33.3
- prompt_id: [UP-20260921-007](userprompts.md#up-20260921-007)
- date: 2026-09-21
- status: live-qualified on the named Mac profile and regression-tested in source; package, release and other-device acceptance remain open
- tags: inference-profile, macos, apple-m5, ollama-0.33.3, qwen3.5, chat, code, documents
- aliases: b97d55b, cf1fa18e, 7f593bfa, current Mac workflow qualification
- paths: backend/contracts/profiles.py, backend/contracts/test_contracts.py, backend/coordinator/test_coordinator.py, backend/coordinator/test_desktop_surface.py, backend/coordinator/test_dispatch.py, backend/coordinator/test_models.py, backend/coordinator/test_reasoning.py, backend/worker/test_executor.py, backend/worker/test_worker_app.py, backend/worker/test_worker_runtime.py, agent-memory/
- summary: The exact Apple M5 16 GB/macOS 26.7 target `mac17-3-m5-16gb`, loopback Ollama 0.33.3, model `qwen3.5:4b-q4_K_M` and manifest `2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd` now have additive measured Chat, Code and Documents profiles. The 0.32.14 Mac profiles and 0.33.2 Ubuntu Chat profile remain unchanged.
- qualification: Chat profile `b97d55b3ba3326226f5022a3fd89bee5988e880bc168114d36bcc3d22fb63807` retains 8,192 context, 2,048 default/max output, text decoding and both reasoning modes. The handed-off live run observed the exact runtime/digest at `127.0.0.1:11434`, zero eligible profiles before the additive entry, direct 8,192-context execution, separate thinking with visible content, a real completed Coordinator turn with requested profile equal to actual profile, reasoning-enabled `17 * 23 -> 391` without persisted thinking, and two-turn continuity recovering `ORBIT-4821`. The current pass independently reprobed the same runtime, digest, target and loopback endpoint before using that evidence.
- qualification: Code profile `cf1fa18e009aba16dd12fe199be4c3a1d2668056cfaab08a578bcc5cd015debb` qualifies `code.whole_file` at 8,192 context and a deliberately conservative 2,048 default/max output, not the historical 8,128 maximum. The real `CodeService.propose` path ran against a temporary one-file repository in reasoning-disabled and reasoning-enabled modes. Both calls used JSON-schema decoding, persisted requested profile equal to actual profile, completed with `done_reason=stop`, produced a validated replacement changing subtraction to addition, and left the canonical file byte-for-byte unchanged because no apply was approved. Before the candidate entered the process-local registry, the same exact runtime/model request returned `model_unavailable` without a model call or mutation. Recorded model outputs were 161 and 257 tokens under the 2,048 cap.
- qualification: Documents profile `7f593bfa689e2184f856e7223e2d4e7a08e62de3fdb921c46a0097df3a25bba3` qualifies `documents.structured` at 8,192 context, 3,072 default/max output, JSON-schema decoding and both reasoning modes. The real `Coordinator.submit` plus `_run` production route consumed a synthetic text attachment in each mode, fenced it as an untrusted DOCUMENT block, persisted requested profile equal to actual profile, completed with `done_reason=stop`, and wrote Word artifacts that reopened as readable with the exact 7.9 mm/s and 24-hour facts. The artifacts contained 8 and 9 paragraphs; outputs used 60 and 2,160 tokens under the 3,072 cap. Without the candidate, submission failed closed at capability admission before inference. Existing adversarial regressions prove truncated/invalid structured replies create no successful artifact.
- changes: Added the two measured 0.33.3 workflow records and changed the Chat evidence reference to this durable anchor. Added one exact-observation regression proving 0.33.3 admits precisely Chat, Code and Documents with their measured caps and 0.33.4 admits none. Replaced every `PROFILES[index]` dependency in backend tests with explicit target/workflow/runtime selection, so additive registry order cannot silently retarget a check.
- verification: Live local qualification passed for Code twice and Documents twice as described above. A final live observation against the source registry admitted exactly the three 0.33.3 profile IDs and caps recorded here. Focused offline verification passed 346 tests. The complete coordinator suite passed 1,073 tests with 4 expected platform skips. Contracts plus all dependency-free worker suites passed 180 tests. Touched files compiled, no positional profile indexing remains under `backend/`, and `git diff --check` passed before ledger finalisation.
- remaining: `backend.worker.test_worker_app` still cannot import because FastAPI is absent from the available desktop interpreter; no dependency was installed, and its authoritative check remains the pinned worker image build. No package rebuild, release gate, real remote/LAN route, Windows qualification, Ubuntu requalification or Linux device run was performed. The next architecture step should be a small versioned qualification-artifact format generated by a release qualification runner and loaded into the existing exact-match registry, followed by a release gate and startup match against runtime, model digest and target profile. Do not replace the current registry or add auto-update logic until artifact compatibility, integrity/signing and rollback are specified and tested.

<a id="ac-20260921-008"></a>
## AC-20260921-008 — llmfit retained as a planning/internal-tool candidate
- prompt_id: [UP-20260921-008](userprompts.md#up-20260921-008)
- date: 2026-09-21
- status: documentation decision recorded; no implementation or qualification claim
- tags: llmfit, hardware-observation, qualification-boundary, ollama, llama.cpp
- paths: docs/PROJECT.md, agent-memory/
- summary: Recorded that Beta 0.1 will not ship or integrate `llmfit`; internal qualification/release-engineering use is the preferred near-term posture, with later adoption, continued internal use or rejection decided from measured value and integration cost.
- changes: Clarified that `llmfit` output is planning evidence only and Refinix retains qualification authority. Reaffirmed Ollama as the current qualified/runtime baseline and pinned upstream llama.cpp/llama-server as an unadopted app-managed candidate gated by same-model workflow parity, runtime behaviour, containment, packaging and recovery evidence. Added OD-17 without rewriting historical OD-03.
- verification: Reconciled `docs/PROJECT.md`, `tasks.md` and `docs/model-catalog.md`; no authority conflict was found. Documentation and ledger only; runtime/source, dependencies, profiles, packaging, qualification evidence and Git state were not changed by this decision.

<a id="ac-20260921-009"></a>
## AC-20260921-009 — Exact execution qualification now produces evidence-only artifacts
- prompt_id: [UP-20260921-009](userprompts.md#up-20260921-009)
- date: 2026-09-21
- status: implemented, live-reproduced on the named Mac and regression-tested; Windows/Linux device and release acceptance remain open
- tags: qualification-artifact, execution-profile, macos, windows-handoff, ollama-0.33.3
- aliases: artifact 1.0, candidate-only evidence, qualify_execution.py, generated Mac evidence
- paths: backend/contracts/qualification.py, backend/contracts/test_qualification.py, scripts/qualify_execution.py, qualification-artifacts/macos/mac17-3-m5-16gb/ollama-0.33.3-qwen3.5-4b-q4-k-m.json, agent-memory/
- summary: A strict version-1.0 artifact now records exact device, runtime/model, profile, reasoning/decoder, limit and measured workflow evidence without becoming a profile loader or release gate.
- changes: Added frozen Pydantic evidence records that accept only non-eligible candidate profiles, require exact requested/actual profile identity and full claimed reasoning/decoder coverage, bind all workflows to one observed model/runtime and target, require workflow-specific safety evidence, cap input size, refuse overwrites and hard-code `release_accepted` false. Added one standard-library runner that probes exact Ollama/model identity, uses temporary coordinator state and source files, invokes the real Chat, Code and Documents paths with reasoning disabled and enabled, verifies Code did not mutate its canonical file, reopens the generated DOCX and checks its two required source facts, and writes only after every result validates. An explicit `--candidate` flag may prepend a profile only inside the qualification process; emitted profiles are converted back to candidate/unverified and product code never consumes the artifact. No production profile, envelope, dependency or runtime was changed. The prior llmfit/Ollama/llama.cpp decision remains AC-20260921-008; no duplicate protected-document edit was needed.
- qualification: Generated artifact 1.0 for target `mac17-3-m5-16gb`, Darwin release 25.6.0/arm64, Ollama 0.33.3 and the recorded Qwen digest. It reproduces the existing Chat `b97d55b` 8192/2048, Code `cf1fa18e` 8192/2048 and Documents `7f593bfa` 8192/3072 identities. All six runs completed with exact requested=actual IDs and stop reasons; reasoning-disabled runs exposed no thinking and reasoning-enabled runs exposed a separate thinking channel. One intermediate Documents run omitted a required fact and produced no artifact; after making the synthetic request explicitly require both source facts verbatim, the complete run passed without weakening the validator.
- verification: 18 contract/artifact tests passed, including malformed/extra input, missing workflow evidence, incomplete reasoning coverage, runtime drift, non-admission and non-overwrite checks. The focused coordinator selection initially ran 390 tests with only 10 sandbox loopback-bind errors; its 23-test reasoning module then passed with loopback permission. The complete coordinator suite passed 1,073 tests with 12 expected platform skips. Dependency-free worker suites passed 168 tests. The generated artifact independently revalidated through the CLI. `backend.worker.test_worker_app` remains unavailable because FastAPI is absent; no dependency was installed.
- remaining: The artifact is review evidence, not automatic runtime authority, signing/integrity distribution, release acceptance or package evidence. A production profile still requires explicit reviewed source registration; automatic loading remains deferred until its trust, compatibility, rollback and signing boundary is designed. Windows must run this workflow on the real selected profile and repair genuine portability defects without weakening the contract. Linux desktop qualification remains a required later Beta gate and is neither implemented nor claimed here. No package/release, remote/LAN route, deployment or Git/GitHub write was performed.

<a id="ac-20260922-001"></a>
## AC-20260922-001 — Code envelope/planner repair and OCR fail-closed contract migration
- prompt_id: [UP-20260922-001](userprompts.md#up-20260922-001)
- date: 2026-09-22
- status: implemented, offline-regression-tested, live-measured on the named Mac and rebuilt into the packaged app; the representative Code workload is a CONFIRMED MODEL-QUALITY BLOCKER and remains unmet
- tags: execution-profile, code-envelope, output-planner, ocr, fail-closed, qualification, k3s
- aliases: stream_chat contract migration, documents.ocr workflow mode, prime_list.c workload, no_qualified_profile refusal
- paths: backend/contracts/profiles.py, backend/contracts/v1.py, backend/coordinator/ocr.py, backend/coordinator/documents.py, backend/coordinator/docflow.py, backend/coordinator/code_service.py, backend/coordinator/db.py, backend/coordinator/models.py, backend/coordinator/server.py, backend/coordinator/test_ocr.py, backend/coordinator/test_code_access.py, backend/coordinator/test_models.py, backend/coordinator/test_documents.py, backend/coordinator/test_execution4a.py, deploy/k3s/checks/pod_inference_check.py, deploy/k3s/checks/test_inference_check.py, scripts/qualify_execution.py
- summary: Migrated the two production runtime callers the exact-profile change left behind, gave OCR its own workflow mode and a truthful unqualified refusal, stopped budgeting generated files from existing file size, and split the collapsed Code failure message into the bound that actually fired.
- changes: `ocr.read_page` now takes REQUIRED keyword-only `profile` and `inference` and no longer passes the removed `model=`/`think=`/`num_predict=`; `extract_image`/`extract_pdf` build the page request from the profile and re-check it independently of the capability probe. Added the `documents.ocr` workflow mode to the profile registry and the contract literal, parameterised profile construction over a `ModelRef`, and registered NO OCR profile: the installed candidate's licence and provenance remain unresolved. `ocr.probe`/`image_probe` refuse without a profile before touching the runtime, `documents` maps that to a distinct `no_ocr_profile` code, and a non-`OcrError` failure from the reading path becomes a named `reading_failed` document refusal instead of escaping as a raw `TypeError`. `documents.ocr` is no longer added to a model's eligible scopes from vision capability alone — it now requires a qualified OCR profile like every other scope. Self-test workflow is selected from the requested scope rather than sniffed from the response schema. `_proposal_output_limit` now sends the smallest of the qualified maximum and the remaining context instead of a floor derived from the selected file, keeping the selection size as a lower bound that still fails closed; the single `selection_too_large` sentence became two that name the bound that fired with its measured value. `_incomplete_detail` distinguishes output exhaustion, context exhaustion and an unexplained stop, each stating that nothing was applied. Added `db.set_attempt_runtime_ms` so a measured Code duration is persisted rather than reported as "not measured". The qualification runner now separates the probed allowance from the claimed maximum and can run a representative complete-program workload in place of the two-line smoke edit. Repaired the K3s Pod inference check to resolve a qualified profile and build an `InferenceRequest`, and rewrote its stub to the current contract against the real profile registry. No envelope was widened, no profile registered, no dependency installed and no protected document edited.
- qualification: The 4,096 and 6,144 requests were diagnostic candidate runs only and did not qualify or register a larger production envelope. They stopped naturally at 1,303–1,801 output tokens, which ruled out truncation but did not establish Code quality: none of the representative complete-program attempts passed strict proposal plus compilation acceptance. The production Ollama 0.33.3 macOS Code profile therefore remains at its previously qualified 2,048 default/max output. The 2026-09-21 artifact was preserved and not overwritten; no new passing artifact was written.
- verification: Claude reported backend/contracts 18 passed; backend/coordinator 1,111 passed with 12 expected platform skips; deploy/k3s 140 passed; fixtures/c07 32 passed; scripts 25 passed, plus live diagnostic model runs and a package rebuild. Those are prior-run evidence, not fresh checks by the correcting agent. `backend.worker.test_worker_app` could not import because FastAPI was absent and no dependency was installed. The source corrections and their fresh verification are recorded separately in AC-20260922-002.
- remaining: The representative linked-list workload FAILS on model quality, not on envelope. Six attempts through the real strict path (three source, two qualification, one packaged) produced zero acceptable results while never truncating and never using more than 44% of the allowance: three valid proposals that fail `cc -std=c11 -Wall -Wextra -Werror` on distinct hard errors (`*head->value` precedence, `int result = ... ? "yes" : "no"`, `#include <stdint_t>`, `printf("%zu", head ? : 0)`), and two proposals rejected by strict validation. Canonical files were unchanged and nothing was applied in every case. Beta therefore needs either a stronger coding model or an explicitly narrower Code claim; that is a product decision and was not taken here. OCR stays unavailable by design — `/api/show` confirms the installed candidate declares only `["completion"]`, and the qwen model that DID pass the old vision gate has no OCR profile either. Windows/Linux still have no target profile. No signing, publication or release acceptance; no Git/GitHub write.

<a id="ac-20260922-002"></a>
## AC-20260922-002 — Audit corrections pass source and package checks
- prompt_id: [UP-20260922-002](userprompts.md#up-20260922-002)
- date: 2026-09-22
- status: implemented and offline-regression-tested; rebuilt macOS package verified; live model quality and cross-platform/release acceptance remain separate
- tags: audit-correction, qualification, ocr-profile, code-metrics, package-parity
- paths: backend/contracts/profiles.py, backend/contracts/qualification.py, backend/coordinator/ocr.py, backend/coordinator/code_service.py, backend/coordinator/test_ocr.py, backend/coordinator/test_code_access.py, frontend/app/app.js, scripts/qualify_execution.py, scripts/test_qualify_execution.py, desktop/refinix.py, desktop/test_packaging.py, agent-memory/
- summary: Removed the unsupported Code-profile promotion, made representative qualification fail closed without source-bound compile and behaviour proof from the no-network sandbox, enforced exact OCR workflow/model/request identity at the shared boundary, exposed the latest Code generation measurements and failure detail in the Code surface, repaired evidence anchors and claims, and prevented packaged launches from writing application `__pycache__` files into the bundle.
- changes: The Ollama 0.33.3 Mac Code profile remains at its previously qualified 2,048 default/max output and prior evidence reference. Qualification profile selection now matches both default and maximum allowances. Any widened Code maximum requires representative compile and behaviour evidence at the artifact-schema boundary; the runner also refuses every new/unregistered Code candidate without representative mode and refuses representative mode before inference when no qualified sandbox validator is connected. Representative proof is bound to the named workload, generated-source hash, exact strict C11 compiler invocation and qualified no-network sandbox, and host execution is refused. OCR probes and page reads reject non-OCR, wrong-model, ineligible, identity-hash-mismatched or inference-mismatched profiles before runtime contact. Code state returns a scoped public attempt summary and the interface renders route, duration, stop reason, output, limits and error detail for successful or failed generation. The macOS entry disables bytecode writes before importing application modules. No generated code was executed on the host, no model/OCR profile was promoted, no protected document or Git/GitHub state was changed.
- verification: Focused contracts/OCR/Code/qualifier selection passed 198 tests with 4 expected live-OCR skips. The complete coordinator suite passed 1,116 tests with 12 expected skips after the loopback-only tests were run outside sandbox policy. Contracts plus K3s and scripts passed 189 tests; C07 fixtures passed 32; desktop lifecycle/packaging/review passed 85 in the pinned packaging environment. JavaScript syntax, touched Python compilation and `git diff --check` passed. Rebuilt `desktop/dist/Refinix.app` from the existing pinned environment; strict deep code-signature verification and the bundle-contents verifier passed, the changed production modules/frontend/entry script matched source byte-for-byte, and no application `__pycache__` directory was present. The first rebuild used relative output paths and failed recursively inside staging; the previous app remained recoverable in `/tmp/refinix-build-backup.20dTIQ`, the failed generated staging tree was isolated there, and the documented absolute-path rebuild succeeded.
- remaining: Source/package audit verdict is PASS for the reviewed defects. The representative linked-list workload remains a confirmed quality failure for `qwen3.5:4b`; no passing artifact exists and Code is not newly quality-qualified by this correction. A stronger coding model or an explicitly narrower Beta claim remains a product decision. OCR remains unavailable until an exact OCR model/runtime/device profile is qualified. The rebuilt app was not manually launched, and Windows, Linux, paired sandbox, signing identity/publication and release acceptance were not claimed.

<a id="ac-20260922-003"></a>
## AC-20260922-003 — Ordinary Chat now preserves Qwen native vision
- prompt_id: [UP-20260922-003](userprompts.md#up-20260922-003)
- date: 2026-09-22
- status: implemented and offline-regression-tested; package rebuild and manual live-model acceptance remain open
- tags: chat, vision, ocr, qwen, attachment-routing, capability-detection
- paths: backend/coordinator/documents.py, backend/coordinator/server.py, backend/coordinator/test_documents.py, backend/coordinator/test_execution4a.py, agent-memory/
- summary: A single PNG/JPEG attached to ordinary Chat now reaches the selected Chat model as verified image bytes when the local runtime reports that exact model supports vision, instead of being blocked by the separate Documents OCR profile.
- changes: Extracted the existing private-file and digest validation into `documents.verified_bytes` and reused it before direct transport. The direct path retains storage containment, no-follow regular-file checks, digest verification, PNG/JPEG signature and media-type validation, the runtime image-size/count limits, the exact qualified Chat profile and its context/output bounds. A system message keeps instructions visible inside the image untrusted. The saved reply states that native vision was used and does not call it qualified document OCR. Models without a runtime-reported vision capability keep the existing extraction/refusal path; structured document/PDF OCR remains profile-qualified and fail closed.
- verification: The focused Chat, extraction and OCR group passed 98 tests with 4 expected live-OCR skips. The complete coordinator suite passed 1,116 tests with 12 expected skips, including its loopback tests under the required local permission. Contracts passed 19 tests. Desktop packaging/review checks passed 44 tests in the pinned desktop environment. `git diff --check` passed. No live model request was made.
- remaining: `desktop/dist/Refinix.app` was not rebuilt because the user planned to update the application after this source change. Multi-image native Chat remains bounded by the existing one-image runtime limit and therefore keeps the prior fail-closed route. Structured OCR/PDF extraction still needs an exact OCR profile and does not borrow Chat qualification. The worker FastAPI test remains unavailable in the coordinator/desktop environments because FastAPI is not installed; no dependency was installed. No protected document or Git/GitHub state was changed.

<a id="ac-20260922-004"></a>
## AC-20260922-004 — Windows source hardening passes; full execution qualification remains blocked
- prompt_id: [UP-20260922-004](userprompts.md#up-20260922-004)
- date: 2026-09-22
- status: Windows portability implemented and device-observed; full execution qualification BLOCKED at the qualified Code sandbox prerequisite; no Windows profile or artifact admitted
- tags: windows, exact-profile, qualification, filesystem, credentials, worker-refusal, native-vision, ollama-0.30.10
- paths: backend/contracts/profiles.py, backend/contracts/test_contracts.py, backend/coordinator/code_service.py, backend/coordinator/credentials.py, backend/coordinator/db.py, backend/coordinator/docgen.py, backend/coordinator/documents.py, backend/coordinator/runtime.py, backend/coordinator/test_approval_note.py, backend/coordinator/test_approvals.py, backend/coordinator/test_code_access.py, backend/coordinator/test_credentials.py, backend/coordinator/test_documents.py, backend/coordinator/test_execution4a.py, backend/coordinator/test_execution4c.py, backend/coordinator/test_paths.py, backend/coordinator/test_remote_code.py, backend/coordinator/test_repo_windows.py, backend/worker/packages.py, backend/worker/test_executor.py, backend/worker/test_packages.py, backend/worker/test_validation.py, backend/worker/test_worker_app.py, backend/worker/validate.py, desktop/packaging_plan.py, desktop/setup_py2app.py, desktop/test_lifecycle.py, desktop/test_packaging.py, docs/PROJECT.md, agent-memory/
- summary: The exact-profile architecture was retained and Windows-specific byte, filesystem, cancellation, document-generation, credential-capability and test-portability defects were repaired. The measured Windows combination remains an unregistered process-local candidate because representative Code cannot qualify without the required no-network sandbox and one Documents reasoning-enabled run ended at the length bound.
- changes: Restored the historical macOS Code maximum to its accepted 2,048-token envelope and locked it with a registry regression. Added binary-mode attachment/package access, Windows-safe DOCX fsync, CRLF-safe source presentation, Win32 pinned-handle backup verification/atomic replacement, cancellation socket release, and an honest Credential Manager persistence probe. The worker validator imports on Windows but refuses the unavailable POSIX resource-limit sandbox. Added live kernel32 Unicode/space-path and junction refusal checks, exact worker mutation/refusal matrices, executor-time revalidation tests, and cross-platform packaging path handling. No fallback host compiler/sandbox, Windows execution profile, artifact loader, llama.cpp or llmfit integration was added.
- windows_evidence: Observed Windows NT 10.0 build 26200.9457, Home Single Language display version 25H2, x64; Intel Core i5-12450H; 16,802,910,208 bytes memory; RTX 2050 4,096 MiB with driver 592.27 plus Intel UHD. Loopback-only Ollama 0.30.10 reported `qwen3.5:4b-q4_K_M`, digest `2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`, with completion/vision/tools/thinking. Process-local Chat 8,192/2,048 completed in both reasoning modes. Documents 8,192/3,072 completed with reasoning disabled and produced a readable required-fact-preserving DOCX; reasoning enabled stopped at `length` and was discarded. Native Chat vision directly received verified image bytes for description and synthetic OCR, while the document OCR extractor was not called. Credential Manager offered session-only generic persistence in this logon session; a session credential round-trip succeeded and was deleted, while required local-machine/enterprise persistence failed closed. No synthetic credential or temporary qualification workspace remained.
- task3_task4: A live in-process Windows worker observation against the real runtime advertised zero unqualified inference profiles/capabilities under contract 1.1, omitted the field for 1.0 and refused generation before `/api/chat`. Offline tests cover wrong identity, runtime, digest, device, workflow, decoder, reasoning, context/output bounds and contract compatibility with no model invocation, plus executor revalidation and requested/actual persistence. Local/remote semantic parity and explicit incompatibility paths passed offline; no real two-device route was available, so live distributed acceptance remains pending.
- verification: Contracts and qualification runner 25 passed. The complete coordinator suite passed 1,119 tests with 29 expected skips. The complete worker suite, including available HTTP tests, passed 217 with 18 expected Windows/POSIX skips. Documents/approval checks passed 324 with 10 skips; focused worker refusal/revalidation checks passed 33; desktop packaging/review/lifecycle passed 85. Python compilation and diff integrity passed. The strict qualification runner exited 1 at the representative-Code sandbox gate and confirmed no artifact was written. Canonical disposable Code source stayed unchanged in focused apply/undo checks; generated DOCX self-test and live disabled-reasoning document reopening passed.
- remaining: Full Windows qualification is BLOCKED, not qualified: no connected qualified no-network Code sandbox validator, no successful all-six-case artifact and no production Windows profile. No trusted second endpoint was available for a real encrypted paired route. Windows Credential Manager local-machine persistence was unavailable in the observed logon session. Windows packaging/installer/signing/update/recovery and release acceptance were not exercised. Linux remains required and unqualified. Historical evidence and the Ollama baseline are unchanged; artifact admission remains manual and no Git/GitHub write was performed.

<a id="ac-20260924-001"></a>
## AC-20260924-001 — Ollama 0.34.2 is qualified for Mac Chat only
- prompt_id: [UP-20260924-001](userprompts.md#up-20260924-001)
- date: 2026-09-24
- status: Chat qualified, source-registered, packaged and live-observed; Code, Documents and release acceptance remain unavailable
- tags: inference-profile, macos, ollama-0.34.2, chat, qualification-artifact, fail-closed, package
- paths: scripts/qualify_execution.py, scripts/test_qualify_execution.py, backend/contracts/profiles.py, backend/contracts/test_contracts.py, qualification-artifacts/macos/mac17-3-m5-16gb/ollama-0.34.2-qwen3.5-4b-q4-k-m-chat.json, desktop/dist/Refinix.app, agent-memory/
- summary: Registered one exact Ollama 0.34.2 Mac profile after the real Chat workflow passed with both reasoning modes; no other workflow was promoted.
- changes: The qualification runner can now select an explicit workflow subset, preserving its all-workflow default and the Code sandbox gate. Added immutable candidate evidence for the exact Qwen digest and a production Chat profile at 8,192 context and 2,048 default/maximum output tokens. Added regressions proving 0.34.2 admits only Chat and 0.34.3 admits nothing. Rebuilt the macOS app from source. No protected document, dependency, model weight or Git/GitHub state was changed.
- qualification: Chat passed twice through the real coordinator path against Ollama 0.34.2 and the recorded Qwen digest. Reasoning disabled completed with `done_reason=stop`, 18 output tokens and 518 ms; reasoning enabled completed with `done_reason=stop`, a separate thinking channel, 625 output tokens and 16,683 ms. Documents failed closed at the existing 3,072-token production allowance with `done_reason=length`; a 4,096-token diagnostic was not registrable because the production path still requested 3,072, so no Documents profile was added. Code was not run or registered because no qualified no-network representative validator is connected.
- verification: The artifact independently revalidated and matched the live-generated file byte for byte. The qualifier/contracts group passed 19 tests; coordinator model and desktop packaging checks passed 108 tests; `git diff --check` passed. The rebuilt app passed strict deep code-signature verification, bundle-content validation and packaged/source profile parity. Live packaged status observed Ollama 0.34.2 reachable, the exact model digest verified, `model_available: true`, one local Chat profile, and Chat `state: available`.
- remaining: Code and Documents stay fail-closed on 0.34.2, and the artifact remains evidence rather than release acceptance. The rebuilt app is running from `desktop/dist/Refinix.app`; the replaced package is recoverable during this session from `/private/tmp/refinix-0342-build.cf6fYL/Refinix.previous.app`. Windows, Linux, paired-worker and public-release gates were not exercised.

<a id="ac-20260924-002"></a>
## AC-20260924-002 — Capability menu distinguishes installed from qualified
- prompt_id: [UP-20260924-002](userprompts.md#up-20260924-002)
- date: 2026-09-24
- status: implemented, regression-tested, packaged and live-observed
- tags: capability-state, qualification, documents, code, ui-truthfulness, ollama-0.34.2
- paths: backend/coordinator/server.py, backend/coordinator/test_desktop_surface.py, frontend/app/app.js, desktop/dist/Refinix.app, agent-memory/
- summary: The capability menu now reports the actual missing Documents or Code execution profile instead of falsely saying the installed model is absent.
- changes: Added one shared capability blocker that preserves distinct messages for an unreachable engine, a locally absent model, a model switched off for new work and an installed model lacking an exact workflow profile. Documents and Code reuse it. The reasoning popover now says a model is unavailable for the selected workflow rather than assuming it is not installed. No capability was enabled and no qualification boundary changed.
- verification: The focused desktop-surface suite passed 36 tests, including the new exact Ollama 0.34.2 regression; JavaScript syntax and `git diff --check` passed. The rebuilt app passed strict deep code-signature verification, bundle-content validation and packaged/source parity. Live packaged status reported Refinix-owned Ollama 0.34.2, Chat available, Search available, and exact qualified-profile blockers for Documents and Code. The rebuilt menu was also observed to render those exact messages.
- remaining: Documents and Code remain unavailable on Ollama 0.34.2 until their separate qualification blockers are resolved. The replaced package is recoverable during this session from `/private/tmp/refinix-capability-copy.Nf0Wxz/Refinix.previous.app`. No protected document, dependency, model, credential or Git/GitHub state changed.

<a id="ac-20260924-003"></a>
## AC-20260924-003 — Previous-answer export bypasses Documents inference qualification
- prompt_id: [UP-20260924-003](userprompts.md#up-20260924-003)
- date: 2026-09-24
- status: implemented, regression-tested, packaged and live-observed
- tags: documents, conversion, capability-gate, ollama-0.34.2, model-free, package
- paths: backend/coordinator/server.py, backend/coordinator/test_document_generation.py, backend/coordinator/test_desktop_surface.py, desktop/dist/Refinix.app, agent-memory/
- summary: Write a document is now available in an explicit conversion-only mode when DOCX output works but the selected model has no qualified Documents execution profile.
- changes: Request-specific admission recognises a no-attachment request to save the previous completed answer, skips model selection and runtime probing for that deterministic route, and reuses the existing `convert_previous_answer` workflow. The capability response exposes the limited mode and its honest summary; a non-conversion request still receives the exact missing Documents-profile refusal before a job is created. Read and Code remain blocked. No frontend branching or new document workflow was added.
- verification: The three focused coordinator modules passed 98 tests after the two existing temporary-loopback cancellation checks were rerun outside sandbox policy. The exact screenshot phrase completed with `runtime.stream_chat` asserted unused, and new generation remained refused. The rebuilt app passed strict deep code-signature verification and source/package parity. Live status on Ollama 0.34.2 reported Write available with `conversion_only: true`; the UI enabled Send, and one live request completed as `convert_previous_answer` with `model_json: null`, producing a reopened 5,718-byte DOCX containing the prior answer.
- remaining: New model-written Documents, document reading and Code remain unavailable until separately qualified for Ollama 0.34.2. The replaced package is recoverable during this session from `/private/tmp/refinix-conversion-gate.trvN69/Refinix.previous.app`. No protected document, dependency, model, credential or Git/GitHub state changed.

<a id="ac-20260924-004"></a>
## AC-20260924-004 — Proposal-only experimental Code qualified on Ollama 0.34.2
- prompt_id: [UP-20260924-004](userprompts.md#up-20260924-004)
- date: 2026-09-24
- status: implemented, live-qualified, regression-tested, packaged and live-observed; full-program and sandbox validation remain unqualified
- tags: code, experimental-profile, small-edit, ollama-0.34.2, qualification-artifact, package
- paths: backend/contracts/profiles.py, backend/contracts/qualification.py, backend/contracts/test_contracts.py, backend/coordinator/server.py, backend/coordinator/test_desktop_surface.py, scripts/qualify_execution.py, scripts/test_qualify_execution.py, qualification-artifacts/macos/mac17-3-m5-16gb/ollama-0.34.2-qwen3.5-4b-q4-k-m-code-proposal.json, desktop/dist/Refinix.app, agent-memory/
- summary: The exact current Mac, Qwen digest and Ollama 0.34.2 profile now admits Code as an experimental small-edit proposal surface only.
- changes: Added `proposal.small_edit` qualification evidence, a `--proposal-only-code` runner mode that refuses output-limit widening, and exact profile `5543ca0903ce733e36b9b88a964f80865d3ea1816ac3f1b269720742ca76f0f1` at 8,192 context and 2,048 default/maximum output with JSON-schema decoding and both reasoning modes. Capability output labels Code experimental and states that complete-program and sandbox validation are not qualified. Rebuilt and launched the macOS app; no protected document, dependency, model weight or Git/GitHub state changed.
- qualification: The real Code proposal route passed in both modes against Ollama 0.34.2 and the exact Qwen digest. Reasoning disabled completed with `done_reason=stop`, 140 output tokens and 6,233 ms; reasoning enabled completed with `done_reason=stop`, 251 output tokens and 6,514 ms. Both produced valid structured small edits and left the canonical source unchanged.
- verification: Qualifier and contract checks passed 14 tests; focused profile, capability and Code checks passed 33 tests; the broader Code/security/profile group passed all 162 tests after its two loopback-only cancellation tests were rerun outside sandbox policy. The rebuilt app passed strict deep code-signature verification and source/package parity. Live status reported Ollama 0.34.2, the exact eligible Code profile, `experimental: true`, and the intended limitation; the Code UI rendered and reported `Ready on this computer.`
- remaining: The 4B model's representative complete-program workload remains a confirmed quality failure, and no sandbox execution profile is claimed. New model-written Documents and document reading also remain unqualified. The replaced package is recoverable during this session from `/private/tmp/refinix-code-proposal.SVOwxR/Refinix.previous.app`. No release, Windows, Linux or worker acceptance was performed.

<a id="ac-20260924-005"></a>
## AC-20260924-005 — Chat-backed Read/Write documents and PDF text layer on Ollama 0.34.2
- prompt_id: [UP-20260924-005](userprompts.md#up-20260924-005)
- date: 2026-09-24
- status: implemented, regression-tested, packaged and live-observed; requester verification pending
- tags: documents, chat-backed, docx, pdf-text-layer, page-references, ollama-0.34.2, package
- paths: backend/coordinator/server.py, backend/coordinator/docflow.py, backend/coordinator/documents.py, backend/coordinator/pdfrender.py, frontend/app/app.js, backend/coordinator/test_document_generation.py, backend/coordinator/test_desktop_surface.py, backend/coordinator/test_documents.py, backend/coordinator/test_ocr.py, backend/coordinator/test_pdfrender.py, frontend/app/test-composer.cjs, desktop/dist/Refinix.app, agent-memory/
- summary: When the Documents-selected model has no structured Documents profile but an exact Chat profile, Read and Write run as one bounded Chat call over validated extracted text, and PDFs are read from their PDFium text layer first.
- changes: Added `_document_execution` (structured / chat_backed / blocked) shared by capabilities, submit and run; Chat-backed skills reuse `_chat_attachments` with native vision off, refuse without usable files, and add a short output instruction; fresh documents are converted by the existing `conversion_blocks` writer with workflow `chat_generated_document` and no provenance in the file; Read answers keep the model text and append a footer that checks `[file p.N]` references (plus the two observed Qwen variants) by exact filename through `retrieval.resolve`, reporting unmatched ones as "Could not be matched to a supplied file and page"; `pdfrender.text_pages` reads text without rendering under existing bounds and marks pages over 40,000 characters as partly read; scan-only PDFs are refused as scans; capability rows add `model_scope: "chat"` and show the Documents model's Chat self-test; the approval note is refused on this route; the model pill checks `model_scope`.
- verification: Focused document modules passed 400 tests (4 pre-existing OCR-profile skips) and `test-composer.cjs` 65; broader coordinator 1171 and contracts 20 passed, desktop 85 and all frontend 188 passed; worker `test_worker_app` needs absent `fastapi` and two launcher tests need a specific hotspot IP (environment, unrelated). Rebuilt app passed py2app content verification, strict deep codesign and source parity for the four backend files and `app.js`. Live on Ollama 0.34.2 with the exact Qwen digest: "create a document of deep learning summarised" completed in one Chat-profile attempt (text decoder, stop, 641 tokens) producing a readable 16-paragraph DOCX with no model/profile text; previous-answer conversion used no model; the approval note returned 409; DOCX, text-PDF and mixed-PDF reads completed with matched page references after the reference fix; the mixed PDF named its unread page; scan-only PDF was refused before any model call; Stop during Write left no artifact.
- remaining: Scanned PDFs and pictures remain unavailable; a matched reference proves only that the page was supplied (live answers sometimes cite the wrong page of a supplied file); output is capped at 2048 tokens; document quality is unmeasured; the scan refusal is truncated at 256 characters; requester verification, protected-doc follow-up (deferred D4) and Git handoff remain. Backups: /private/tmp/refinix-phase1-docs.vTH9yn/ and /private/tmp/refinix-phase1-refs.DW5sN7/.

<a id="ac-20261002-001"></a>
## AC-20261002-001 — Website product video, pillar, About us and Download Beta
- prompt_id: [UP-20261002-001](userprompts.md#up-20261002-001)
- date: 2026-10-02
- status: implemented and preview-observed; requester verification pending
- tags: website, site.html, docs.html, video, about-us, navigation, design-reference
- paths: frontend/design/site.html, frontend/design/site.css, frontend/design/docs.html, frontend/design/docs.css, frontend/design/assets/intro-video-poster.jpg, agent-memory/
- summary: Homepage approach section is now the supplied 16:9 video (autoplay muted loop, user pause kept, off-screen/hidden pause, reduced-motion poster) above the four unchanged points in 4/2/1 columns; the temple SVG is replaced by assets/pillar.png capped at 960px; Docs gains #about with the supplied team photo (560px cap) and contributions; visible Beta launch CTAs read Download Beta; the homepage nav keeps Download Beta and About us on phones; anchor scroll-padding follows the measured header height.
- changes: Poster extracted from the 3 s frame (1920x1080 JPEG, 110,223 bytes) with the built-in Swift/AVFoundation toolchain; no video re-encode (no ffmpeg). Video SHA-256 b9388761…6317, pillar f8ad8abb…5c25 and team photo 5a6537dd…bec unchanged. Docs inline link now reads "launch countdown". Stale site.html header comment about the temple updated. Old .cards/.statement CSS left in place unused.
- verification: Preview at 1440/1000/768/560/366 px: no horizontal overflow; points 4/2/2/1/1 columns; header 65/65/113/109/108 px with offset 89/89/137/133/132 px and #get/#surfaces/#work/#proof all clear of the bar; clip looped 9.15→0.10 s and continued; user pause survived scroll away/back; clip held while the pane was hidden and resumed when shown; Node harness confirmed reduced-motion start paused then plays on click; dark/light token colours, glow and focus outline observed; docs.html#about loads clear of the header; media URLs 200; only pre-existing 404s (lockup PNGs, favicon).
- remaining: TOC highlights "Limits & answers" rather than "About us" when About is reached, because the page cannot scroll the last section into the TOC band (existing TOC logic); real-browser reduced-motion and separate-tab hidden behaviour not observed in the pane; team photo is 1.93 MB (lazy-loaded); faces render about 28 px wide at 560 px and about 16 px at 366 px; requester visual verification and Git handoff pending.

<a id="ac-20261002-002"></a>
## AC-20261002-002 — Website consolidated repair
- prompt_id: [UP-20261002-002](userprompts.md#up-20261002-002)
- date: 2026-10-02
- status: implemented and preview-observed; real reduced-motion and successful clipboard write unverified; requester verification pending
- tags: website, site.html, docs.html, accessibility, reduced-motion, toc, theme, design-reference
- paths: frontend/design/site.html, frontend/design/site.css, frontend/design/docs.html, agent-memory/
- summary: Docs TOC marks the last part past a reading line (parent lit, final part at page end); both pages apply a validated refinix.site.theme before paint; homepage has a DOMContentLoaded script-failure fallback, a no-script intro rule, inert page and managed focus during the intro, a reduced-motion still path, cancellable intro stages, a start()-guarded canvas, a shared clip policy with an evidence-clip pause button, and a live motion-preference listener; Copy reports failure honestly; unavailable destinations are plain text.
- changes: Docs copy rows F5 (eligible for local Chat, Try again, usually takes longer, pinned-first ordering, attached or explicitly reused files). F7 labels: Security model (link unavailable), Report an issue (link unavailable), private-for-now and licence text unlinked. Michroma added to the Docs font request. Added a load-time refocus of the intro Enter control after fragment scrolling (found in verification: site.html#get dropped focus to body). docs.css unchanged; no media bytes changed.
- verification: Browser pane, pane visible: TOC #files/#questions/#about direct, scroll both ways, TOC click and back/forward all correct; homepage anchors clear at 1440/1000/768/720/366/320 with offsets 89/89/137/136/132/167 px; Docs anchors clear at 1440/1000/768/366/320; theme persists across pages and reload, invalid value ignored; intro keeps focus, keyboard entry lands on nav brand or #get Download Beta; demo and terminal tabs switch by arrow keys with visible focus; no demo clipping at any width (terminal scrolls locally); product clip looped 9.68->0.67 s, user pause kept across scroll; evidence toggle pauses/plays; hidden pane paused the product clip at 5.38 s and it resumed from 5.38 s when shown; both themes rendered; console only pre-existing lockup PNG and favicon 404s. Simulated: fault copies (scripts removed, error injected after intro lock, localStorage throwing) behaved as intended; clipboard success/refusal/missing-API states via substituted API. Syntax: all inline scripts pass node --check.
- remaining: Real macOS Reduce motion not tested (requester skipped); a successful real clipboard write not observed (pane refuses writes, button showed Copy failed); real background-tab switch not tested (pane tabs report visible); requester visual confirmation of phone-width playback not given; 320 px homepage header wraps to three rows; Git handoff pending; requester says refinix.run deploys from dev (unverified by agent).

<a id="ac-20261002-003"></a>
## AC-20261002-003 — Website launch countdown block
- prompt_id: [UP-20261002-003](userprompts.md#up-20261002-003)
- date: 2026-10-02
- status: implemented and preview-observed; requester verification pending
- tags: website, site.html, countdown, launch, design-reference
- paths: frontend/design/site.html, frontend/design/site.css, agent-memory/
- summary: The countdown no longer rewrites the launch paragraph; a role=timer block of four units (Days, Hours, Minutes, Seconds) sits centred between the paragraph and the buttons.
- changes: Countdown script writes into four data-cd spans with the same LAUNCH_START/LAUNCH_END, one-second interval and zero clamp; digits use the heading's Spectral 700 and clamp size, 12px Plex Mono labels, glass/edge tokens; 4 columns, 2x2 at <=560px (max 320px); hidden under html:not(.js).
- verification: Served files at 127.0.0.1:8000 matched disk hashes. Observed in the pane: digits 50.4px = heading 50.4px at 1440, 36.7px = heading at 768, 29.6px at 390/320; 4 across at 1440/768, 2x2 at 390/320; centred, between paragraph and buttons, no overflow; paragraph text unchanged; displayed value matched an independent computation within the one-second tick and advanced 2 s in 2.1 s; dark and light colours; no js class hides the block. Simulated: Node harness with a faked clock showed 9:00:00:00 before/at window open, 5:12:00:00 mid-window, 0:00:00:01 then 0:00:00:00 with the interval cleared, and no interval after the end.
- remaining: Real screen-reader behaviour not tested; Docs TOC/About photo not re-observed this pass (pane hidden; docs files unchanged since the AC-20261002-002 observation); requester visual verification and Git handoff pending.

<a id="ac-20261002-004"></a>
## AC-20261002-004 — Countdown row, size, rolling digits and stylesheet version
- prompt_id: [UP-20261002-004](userprompts.md#up-20261002-004)
- date: 2026-10-02
- status: implemented and preview-observed; requester verification pending
- tags: website, site.html, countdown, animation, cache
- paths: frontend/design/site.html, frontend/design/site.css, agent-memory/
- summary: The stacked plain-text rendering was new HTML with a cached old site.css (no countdown rules). site.html now links site.css?v=20261002-cd2. Countdown is four units in one row at every width (2x2 removed), digits clamp(2.2rem, 1.1rem + 4.4vw, 4.6rem) Spectral 700, and only changed digits roll (new digit drops in blurred with a brief accent glow, old falls away, clipped to the slot).
- changes: Script renders each number as an aria-hidden digit row plus one visually hidden plain copy; rolls skipped under the page's live reduced-motion flag; outgoing copies removed after 700 ms. Unit cards gain an inset accent hairline. docs.html still links unversioned site.css.
- verification: Pane (served 127.0.0.1:8765, same folder; requester's :8000 server had stopped): versioned stylesheet loaded; 1440 digits 73.6px vs heading 50.4px, units 177px; 390 units 83px, 320 units 66px, digits 35.2px, labels 11px fit (SECONDS 51px); one row, no page overflow; dark and light; roll observed in DOM (one cd-in and one cd-out per changed digit, none left over) and frozen mid-roll in screenshots, including an hours change at 59:59; plain copy matches visible digits; digit rows aria-hidden. Inline scripts pass node --check.
- remaining: Real Reduce motion and screen-reader output not tested; boundary/zero stop not re-simulated after the DOM change (time arithmetic unchanged); requester visual verification in Safari and Git handoff pending.

<a id="ac-20261002-005"></a>
## AC-20261002-005 — Website entry scroll, prose punctuation and stylesheet versions
- prompt_id: [UP-20261002-005](userprompts.md#up-20261002-005)
- date: 2026-10-02
- status: implemented and preview-observed; CI scripts suite has 2 pre-existing failures (below); requester verification pending
- tags: website, site.html, docs.html, scroll-restoration, punctuation, cache, ci
- paths: frontend/design/site.html, frontend/design/docs.html, agent-memory/
- summary: Reloading after scrolling no longer leaves Get started mid-page: scroll restoration is manual while the intro is up (set early, and again on pagehide because a reload reuses the mode the page was left in), release() scrolls to the hash target or the top, then hands restoration back to the browser after load (and on a bfcache pageshow) so in-page Back/Forward still scroll; the script-failure fallback also restores auto. 10 site and 29 docs dash separators replaced (titles now "Refinix: ..."; team rows "Name: role"); the unavailable-value dash, code-diff lines and code comments kept. docs.html links site.css?v=20261002-cd2 and docs.css?v=20261002-r1.
- changes: Found during verification: leaving restoration manual broke same-document Back (address changed, no scroll), hence the hand-back; handing back without the pagehide reset let a later reload restore 4253 px behind the intro (would misplace the figure's travel), hence the pagehide reset. CSS, media and other content unchanged (site.css 6938327e, docs.css 84a46260, media hashes as recorded).
- verification: Pane at 1440x900 (pane hidden; timers and layout still exercised): clean fresh load -> top, focus nav brand; scroll 4300 + reload -> no restore (y 0 before entry), entry at top; in-page #proof -> #surfaces -> Back -> Evidence at 89 px, Forward -> Surfaces at 89 px; reload with #proof -> Evidence at 89 px, focus its first control; direct site.html#get and Docs "launch countdown" click -> #get at 89 px, countdown fully visible, focus Download Beta; Docs -> Back (not bfcache here) re-shows the intro and lands at the top, previous 3000 px position lost; Forward -> Docs. Simulated: main script throwing after the intro lock -> fallback hides intro, page scrollable, restoration auto; clock shifted to the deadline -> 0:00:00:01 then 0:00:00:00 held 9 s. Accepted presentation unchanged at 1024 (video/pillar 954.375 px, 2 columns, 17/15.5 px, glow 14 px/0.35); both themes at 1440 and 390 rendered; no duplicate ids; only unresolved refs are the pre-existing lockup PNG swap hooks; inline scripts pass node --check. CI set (local, isolated venv, Python 3.14.6 not 3.13; worker lock --require-hashes fails on macOS arm64 as it is Linux x86_64 only, so the same pinned versions were installed without hashes; render lock installed with hashes): contracts 20 OK; coordinator 1183 OK, 13 skipped (7 PyObjC absent, 4 no qualified OCR profile by design, 1 PDF writing unavailable, 1 Quartz fallback absent); worker 213 OK; deploy/k3s 140 OK; fixtures/c07 32 OK; scripts 32 run, 2 FAILED; node --test (Node 26.7.0 not 24) 188 pass.
- remaining: scripts/test_refinix_launcher.py fails 2 tests because commit c08262b (on origin/aditya) moved scripts/refinix to 10.177.11.113/.160 while the test still mocks 10.219.115.x; main/dev are consistent at 10.219.115.x, so merging this branch toward main would fail GitHub CI until script and test agree (outside website scope, not changed). Real Safari, real Reduce motion, screen readers, bfcache-restore path and deployed refinix.run not observed; GitHub CI not run (triggers only on main); requester verification and Git handoff pending.

<a id="ac-20261002-006"></a>
## AC-20261002-006 — Actual Pages publishing path and local website exporter
- prompt_id: [UP-20261002-006](userprompts.md#up-20261002-006)
- date: 2026-10-02
- status: local export prepared and focused offline checks passed; not committed, pushed or deployed
- tags: website, deployment, github-pages, static-export
- paths: scripts/build-site.sh, scripts/test_build_site.py, agent-memory/
- summary: Live DNS and GitHub Pages metadata identify refinix.runs-on.dev as vedantsur09/refinix-site, main branch at repository root, legacy Pages build. Its README documents scripts/build-site.sh, missing from inspected source branches. Earlier ledger reports of refinix.run deploying from dev were unverified and are superseded by these observations.
- changes: Added dependency-free exporter accepting a new output directory, preserving homepage/CSS/media bytes, renaming site.html to index.html, retargeting Docs homepage links, copying referenced assets only, and emitting CNAME/.nojekyll. Refuses existing output, required missing media and assets escaping the public folder. Added four offline boundary checks. Existing website and media unchanged.
- verification: GitHub Pages metadata and successful publishing run 34136160239 observed; public main at 072bb2586d02632a66e8c84664f88632041ad422. Source repo has no Pages site/deployment records or inspected workflow linking dev to that public repo. Remote dev...aditya diverges (ahead 2, behind 4), with application changes. Four exporter tests passed; actual bundle at /private/tmp/refinix-site-publish-20261002 contains 2 pages, 2 CSS files, 10 assets, CNAME and .nojekyll (35,707,593 bytes). Local page links/fragment targets resolve, excluding the two known optional lockup-image fallbacks; all exported media/CSS and homepage bytes match canonical files.
- remaining: No external/manual sync outside inspected repositories established; live site still serves older content. Source branch CI is not newly verified; prior launcher fixture failures remain outside this scope. Media weight retained without re-encoding. Publish through a separate reviewed update to the public site repository; no wholesale aditya merge or direct source dev/main push recommended. No Git writes, hosting changes, protected-document edits or live publication performed.

<a id="ac-20261002-007"></a>
## AC-20261002-007 — Published poster and WebM clips restored in website source
- prompt_id: [UP-20261002-007](userprompts.md#up-20261002-007)
- date: 2026-10-02
- status: implemented and preview-observed; requester verification pending
- tags: website, site.html, media, performance, pages, exporter
- paths: frontend/design/site.html, frontend/design/assets/hero-poster.jpg, frontend/design/assets/hero-loop.webm, frontend/design/assets/evidence-loop.webm, agent-memory/
- summary: site.html preloads assets/hero-poster.jpg, gives the intro video that poster, and orders sources hero-loop.webm, hero-loop.mp4, intro.webm; the evidence clip prefers evidence-loop.webm before its mp4. The three files were fetched from vedantsur09/refinix-site at 072bb25 via the Git blobs API and matched their blob ids and sizes (8ca6f037 83,193 B; 06cd1e92 4,950,238 B; ebb0ef89 1,957,919 B) before being copied in.
- changes: No CSS, Docs, exporter or existing media change (site.css 6938327e, docs.html 8a93ff54, docs.css 84a46260; hero-loop.mp4, evidence-loop.mp4, intro.webm, intro video.mp4, pillar.png, About US.png, intro-video-poster.jpg unchanged). site.html now 557aae6a. The intro source comment was rewritten because "master first" no longer holds.
- verification: Parity (pane hidden): hero WebM 720x1280, 31.5 s vs master 720x1280, 31.466 s; evidence WebM 720x720, 16.666 s vs mp4 16.667 s; poster 720x1280 JPEG; screenshots matched at hero 0 s and 6.0 s and evidence 0 s (seeking and later playback were blocked by the hidden pane). Real page: intro currentSrc hero-loop.webm, no hero-loop.mp4 or intro.webm request, poster fetched by the preload link at 15 ms (200), intro box 506x900 (720x1280 ratio, no shift), evidence currentSrc evidence-loop.webm, only the lockup 404s; entry lands at the top; countdown ticks; intro rendered at 1440 dark and 390 light. Simulated: copy without the WebM files and poster -> both clips play their mp4s. Fresh export /private/tmp/refinix-site-publish-20261002-media: 13 assets, 42,699,423 B, all bytes equal source, 12 Docs links to index.html, 78 references resolve (only the 3 lockup placeholders unresolved). node --check of inline scripts, git diff --check and the 4 exporter tests passed.
- verification (pane visible): approach clip (intro video.mp4) and evidence clip (evidence-loop.webm) each paused on Pause, stayed paused when scrolled away and back, played on Play, paused off screen while playing and resumed on return. Frame parity by mean absolute pixel difference (90x160 hero, 120x120 evidence; unrelated hero frames 29.18 as control): hero 0.5/5/10/20/30 s 4.74-5.95, 15 s and 25 s 4.27 and 2.54 at a one-frame (0.033 s) offset; evidence 0.5-16 s 1.36-2.83; poster closest to master 13.5 s at 2.79.
- remaining: Real Safari/WebM behaviour, real Reduce motion and the publish itself pending. Publishing replaces public hero-loop.mp4 (15,489,302 B) and evidence-loop.mp4 (4,100,132 B) with the source fallbacks. Git actions and publication need separate approval and push access to refinix-site.

<a id="ac-20261002-008"></a>
## AC-20261002-008 — Website PRs prepared from isolated committed source
- prompt_id: [UP-20261002-008](userprompts.md#up-20261002-008)
- date: 2026-10-02
- status: source and publishing PRs open and mergeable; not merged or deployed
- tags: website, publication, github-pages, pull-request
- paths: frontend/design/, scripts/build-site.sh, scripts/test_build_site.py, agent-memory/
- summary: Created an isolated source checkout from remote dev 1e79d877, copied only the 13 website/exporter files and appended the existing website ledger entries to dev's ledgers. Committed 1f383fedcc89cd8e02b8faeb845e5509578c113a on codex/website-publication; source PR https://github.com/prachi-satbhai0741/Refinix/pull/65 targets dev and excludes unrelated aditya application commits. Original source checkout/branch and website bytes preserved.
- changes: Created public publishing fork adityatadge31/refinix-site. Exported from committed source into /private/tmp/refinix-site-publish-committed-20261002; copied bundle into clean publishing checkout without deleting files or changing README/.gitattributes/.nojekyll. Publishing commit 7a2b244cb1b79b4bfb4716acd4a625ff30440397 changes 12 website files; PR https://github.com/vedantsur09/refinix-site/pull/1 targets main. Both PRs attached to this task.
- verification: Four focused exporter tests passed in the original and isolated source checkouts. Inline script syntax, unique page ids, links/fragment targets, CNAME and source/bundle media/CSS parity passed. Every committed publishing file matches the generated bundle; no file deletions. git diff --check passed. Both PRs observed open and mergeable; this is not a claim of full CI passing. Hosting remains main/root at refinix.runs-on.dev, current upstream main 072bb25. No DNS/Pages settings changed.
- remaining: Publishing owner must merge PR 1 because current account has pull-only access; source PR merge separately pending. No protected branches pushed, PRs merged or deployment claimed. Post-deployment verification awaits owner merge. Launcher inspection confirmed scripts/refinix uses 10.177.11.113/.160 while aditya tests mock 10.219.115.x; these are two-device demo-network assumptions, unrelated to website publication or user identity. Launcher/test files were not changed or executed.


<a id="ac-20261003-001"></a>
## AC-20261003-001 — Standalone Beta contract and coherent section execution
- date: 2026-10-03
- agent: agent
- status: docs-only
- prompt_id: [UP-20261003-001](userprompts.md#up-20261003-001)
- tags: beta, standalone, cross-platform, updates, reuse, agent-execution
- paths: AGENTS.md, docs/PROJECT.md, tasks.md, docs/releases.md, README.md, docs/README.md, docs/security.md, agent-memory/
- summary: Aligned seven current instruction/product/release/entry-point documents with standalone three-OS Beta, qualified user-initiated in-app updates and post-Beta mesh execution.
- changes: Retained phase IDs with Beta order 1 -> 2 -> local 4 -> 5; deferred mesh and peer packaging/acceptance; preserved distributed contracts, local sandbox/approval/data/recovery/offline requirements; required existing-code inspection/reuse and direct major-section completion without further task tiers or delegation; removed active PRD/P-task references from release/readme guidance; preserved renamed-heading anchors; appended ledgers without rewriting existing entries.
- verification: Reviewed scoped diffs and stale-gate searches; read-only inspection found all 17 added/changed local Markdown links resolve, no conflict markers/duplicate explicit anchors/unmatched fences in seven changed docs, and 31 FR plus 17 OD identifiers remain unique. No application tests, builds, model/device/updater checks or Git writes performed.
- remaining: No implementation/device/package/updater/release acceptance established by these documentation edits. Active Phase 1 remains unchanged; every advertised Beta profile still needs actual qualification before publication.


<a id="ac-20261004-001"></a>
## AC-20261004-001 — App-managed runtime contract and retained harness decision
- date: 2026-10-04
- agent: agent
- status: docs-only
- prompt_id: [UP-20261004-001](userprompts.md#up-20261004-001)
- tags: runtime, qualification, onboarding, updates, langgraph, evidence
- paths: AGENTS.md, docs/PROJECT.md, tasks.md, docs/model-catalog.md, docs/releases.md, docs/evaluation.md, README.md, docs/README.md, agent-memory/
- summary: Updated eight documents to make runtime versioning/qualification release-owned, require a pinned app-managed engine isolated from external Ollama changes, and keep the existing harness with LangGraph unadopted pending a demonstrated gap and comparative evidence.
- changes: Recorded automatic local installation checks distinct from engineering qualification; preserved strict admission/provenance/context/security controls; added managed-engine update/mismatch/recovery acceptance cases; clarified current Ollama source versus preferred unqualified bundled llama.cpp; added OD-18 and sourced orchestration options from official LangGraph documentation; corrected active lifecycle P-task references; appended source-supported runtime-error finding without rewriting historical evaluation body or claiming live diagnosis.
- verification: Reviewed per-turn diffs against saved dirty-file baselines. Static documentation inspection resolved all 17 added/changed local links, found no conflict markers/duplicate explicit anchors/unmatched fences across eight documents, preserved all 31 FR and prior 17 OD IDs while adding OD-18, and confirmed historical evaluation body plus eight source/security/website files unchanged. Scoped git diff --check passed before ledger append. No application tests, live runtime/model/device calls, downloads, installers, migrations or Git writes ran.
- remaining: Current runtime-version admission/UI behaviour is not repaired by these docs. App-managed packaging, engine parity, graphical recovery, each OS profile and updater transition remain unimplemented/unverified release work. Continue the existing Phase 1 without a harness rewrite or further task tiers.


<a id="ac-20261004-002"></a>
## AC-20261004-002 — Source-grounded standalone Beta execution handoff
- date: 2026-10-04
- agent: agent
- status: planning-only; implementation-owner coordination pending
- prompt_id: [UP-20261004-002](userprompts.md#up-20261004-002)
- tags: beta, planning, code-quality, runtime, review, memory
- paths: docs/beta-execution-handoff.md, agent-memory/
- summary: Created the requested execution handoff with source/caller map, retained decisions and trade-offs, four coherent sections, cleanup/performance discipline, exact acceptance cases and an explicit pending independent-review record.
- changes: Saved the user's core direction as an authorized Codex memory extension note and pinned the current chat. Handoff distinguishes current external Ollama and narrow measured device admission from planned managed-engine/support work, and avoids claiming build automation is an accepted in-app updater. Existing core docs/source/website work was preserved.
- verification: Read current authority/source, queried the existing Graphify graph without installing/rebuilding, checked all 35 handoff links, inspected document structure and observed git diff --check pass. Hash comparison confirmed 452 baseline source/document files unchanged and both ledger prefixes intact before append. Memory save and sidebar pin returned success. No application tests, builds, runtime calls, installations, downloads, migrations, subagents or Git writes ran.
- remaining: Computer Use refused access to the running implementation-owner app; no prompt delivered, independent plan received, joint PASS or application implementation established. The handoff contains a ready-to-send prompt and the coordination checkpoint.


<a id="ac-20261004-003"></a>
## AC-20261004-003 — Implementation-owner plan recorded in the Beta handoff
- date: 2026-10-04
- agent: agent
- status: planning-only; review-agent evaluation pending
- prompt_id: [UP-20261004-003](userprompts.md#up-20261004-003)
- tags: beta, planning, runtime, schema-safety, updater, sandbox
- paths: docs/beta-execution-handoff.md, agent-memory/
- summary: Added the implementation owner's independent assessment and plan to the handoff, updated its state, coordination status and review record, and appended a ready-to-send review-agent prompt. Preparing draft left unchanged for comparison.
- changes: Sixteen source-cited findings, including a newer-schema overwrite in db.connect, adoption of any listener on the Ollama port, customer-facing terminal commands, prose-only readiness, a fixed-window context indicator and a live-check module shipped in packages. Proposed an engine-agnostic managed boundary with a llama-server adapter decided by a Mac parity rule, device classes, provisioning/onboarding, local Auto, instructions/memory, a Seatbelt-first local sandbox, TUF-based updates, per-OS packaging candidates, cleanup candidates, validation families, a permission/decision batch and a user-facing change summary.
- verification: Read-only source and authority inspection at HEAD 8c6d7a9. Cited line ranges re-checked against source; all 81 handoff links and anchors resolve and code fences balance (local Python check). No application edits, tests, builds, runtime calls, downloads, installs, subagents or Git writes.
- remaining: Review-agent evaluation, reconciliation and the user's answers to the prerequisite batch are pending. No implementation, device, package, updater or release evidence exists for anything in the plan.


<a id="ac-20261004-004"></a>
## AC-20261004-004 — Reviewed preset contract and NEEDS FIX plan handoff
- date: 2026-10-04
- agent: agent
- status: docs-only; owner-reconciliation-pending
- prompt_id: [UP-20261004-004](userprompts.md#up-20261004-004)
- tags: presets, primary-research, reuse, runtime, recovery, sandbox, review
- paths: AGENTS.md, docs/PROJECT.md, tasks.md, docs/model-catalog.md, docs/releases.md, docs/evaluation.md, docs/beta-execution-handoff.md, agent-memory/
- summary: Saved the explicitly requested core direction in a Codex memory extension note; aligned seven documents on research-backed hardware/category presets and recorded an independent NEEDS FIX review while preserving the owner proposal.
- changes: Added preset schema, brand-versus-hardware matching, supported OS ranges versus observed builds, current-capacity guards and external/Refinix/estimated evidence distinctions. Added primary published model/artifact observations and reuse options, including already-considered llmfit target-profile/JSON planning, upstream runtime controls, Hub acquisition, platform metrics and update tools. Five consolidated findings require preset/reuse reconciliation, usable compatible-data rollback, actual sandbox resource enforcement and accurate observer/native-prerequisite claims. Ready-to-send owner prompt explicitly requires review of the changed docs.
- verification: Static documentation inspection resolved all 17 new local links, found balanced fences/no duplicate explicit anchors or conflict markers, preserved all 31 FR and 18 OD IDs, the original owner proposal and historical evaluation body, and confirmed 168 source-file hashes unchanged. Scoped git diff --check passed. Source/public primary-record reads only; no application tests, benchmarks, downloads, installs, model/runtime calls or Git writes. Computer Use again refused access to the owner app; no follow-up message delivered.
- remaining: Owner must inspect the current doc diff and reconcile the five findings in the same four sections. Joint PASS, app implementation, finalized all-OS minimums/presets and package/security/updater acceptance remain unestablished. Direct coordination remains unavailable; user delivery of the prepared prompt is the simple checkpoint.


<a id="ac-20261004-004"></a>
## AC-20261004-004 — Owner reconciliation of R1-R5 recorded in the Beta handoff
- date: 2026-10-04
- agent: agent
- status: planning-only; review-agent re-review pending
- prompt_id: [UP-20261004-004](userprompts.md#up-20261004-004)
- tags: beta, presets, reuse, rollback, sandbox, observer, packaging
- paths: docs/beta-execution-handoff.md, agent-memory/
- summary: Appended an owner reconciliation accepting R1-R5, with new findings K17-K23, reuse decisions, a journalled binary-and-data recovery design, per-OS sandbox enforcement, a sampled-observer contract, package preflights, revised prerequisites and a reconciled change summary. Updated the handoff state, coordination note, review record and review-agent prompt. Earlier sections unchanged.
- changes: Key findings: the built macOS bundle embeds Homebrew Python with minos 26.0 while Info.plist claims 12.0 and pypdfium2 needs 13.0; deferred pairing controls remain visible; the window backend is auto-selected; db.connect writes into any SQLite file; llama-server --fit adjusts unset settings and /v1/models needs no API key; macOS leaves RLIMIT_AS/DATA unenforced, so the Seatbelt-first sandbox is withdrawn in favour of an Ubuntu systemd-user-service plus Landlock profile, with Windows Job/AppContainer second.
- verification: Read-only source, git diff, otool and sysconfig inspection at HEAD 8c6d7a9; public primary records for llama-server, llmfit, huggingface_hub, python-tuf, securesystemslib, systemd v255, apple/container and macOS rlimits. All 125 handoff links/anchors resolve and code fences balance. No application edits, tests, builds, downloads, installs, runtime calls, subagents or Git writes.
- remaining: Review-agent re-review, joint PASS and the user's answers to the revised prerequisites are pending. No implementation, device, package, sandbox, updater or release evidence exists.


<a id="ac-20261004-005"></a>
## AC-20261004-005 — Internal test-package build matrix and cleanup evidence added to the handoff
- date: 2026-10-04
- agent: agent
- status: planning-only; review-agent re-review pending
- prompt_id: [UP-20261004-005](userprompts.md#up-20261004-005)
- tags: beta, packaging, build-matrix, test-artifacts, cleanup
- paths: docs/beta-execution-handoff.md, agent-memory/
- summary: Added O.11 (internal macOS/Windows/Ubuntu test packages from one snapshot through one build driver and one dispatched CI matrix, with manifests, checksums, TESTING.md, verified-input caching, rebuild-only-on-change and N/N+1/engine-change build sets on a separate internal trust root) and O.12 (strengthened cleanup rule with scan evidence). Updated O.1, O.8, O.9 (build-environment blocker as item 6), O.10, the cleanup section pointer, review record and re-review prompt.
- changes: Confirmed by read-only reference scan and grep: db.clear_attachments, db.sources_for_message, db.ArtifactRejected, repo.is_excluded_directory and runtime.installed_models have no references; /v1/status computes the document capability summary, OCR profile and FTS check twice. Authority files unchanged since the prior review (mtimes); proposed one releases.md addition for the internal channel, pending permission.
- verification: All 132 handoff links/anchors resolve and fences balance; cited repo.py and server.py lines re-read. No application edits, tests, builds, downloads, installs, CI runs, subagents or Git writes.
- remaining: Windows/Ubuntu packages depend on a native build environment (user-dispatched Actions matrix or team/volunteer hosts). Re-review, plan PASS and permissions are pending; no package, device or release evidence exists.

<a id="ac-20261004-006"></a>
## AC-20261004-006 — Approved corrected execution handoff delivered
- date: 2026-10-04
- agent: agent
- status: handoff-delivered; required-action-permissions-pending
- prompt_id: [UP-20261004-006](userprompts.md#up-20261004-006)
- tags: beta, approval, handoff, source-reuse, recovery, sandbox, build-identity
- paths: docs/beta-execution-handoff.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Added the user-approved execution addendum to the existing handoff, preserved earlier proposals, corrected active state/review/coordination and owner prompt, and delivered it directly to the existing implementation-owner conversation.
- changes: Same four sections; actual-root lifetime locking and coherent-copy SQLite identity/schema preflight; exclusive writer shutdown and journalled data recovery; io_uring/host IPC denial and hard aggregate byte/inode bounds; separate embedded identity/final artifact records with verified reuse. Retained all-OS native packages, existing harness, research-backed presets and reuse-first cleanup. Required permissions are one genuine batch rather than a new planning loop; other protected docs and Git/CI remain separate.
- verification: Static handoff inspection resolved 117 local links, found unique explicit anchors, balanced fences and one approved-addendum anchor; scoped diff whitespace inspection passed. Computer Use visibly confirmed the sent handoff as Message 9 in the existing owner chat and showed the owner responding. No application edits by this agent, tests, builds, installs/downloads, live runtime calls, Git/Actions writes or release actions.
- remaining: Detailed owner acknowledgement and missing O.9 action permissions/human facts. No sandbox, runtime, package, updater or release acceptance is implied; native build environments and representative observations are still necessary.


<a id="ac-20261004-007"></a>
## AC-20261004-007 — Section 1 foundation: ownership, admission, managed engine, readiness, presets, build path
- date: 2026-10-04
- agent: agent
- status: partial; Sections 2–4 not started; paused at usage limit
- prompt_id: [UP-20261004-007](userprompts.md#up-20261004-007)
- paths: backend/coordinator/{ownership,build_info,engine,local_engine,runtime_llamacpp,readiness,fake_llama_server,db,server,runtime,device,models,repo}.py, backend/contracts/profiles.py, backend/requirements-runtime.lock, desktop/{lifecycle,shell,__main__,refinix,packaging_plan,setup_py2app,build}.py, desktop/engine/{engine-pins.json,fetch.py}, desktop/{refinix.spec,packaging-tools.json,TESTING.md.in,requirements-*-{windows,linux}.lock}, desktop/windows/refinix.iss, desktop/linux/*, frontend/app/{app.js,control.html,test-control-centre.cjs}, scripts/{qualify_execution,engine_parity}.py, new tests.
- changes: Workspace lock follows the actual database for every entry point; schema admission inspects a private copy and refuses newer/foreign/corrupt/ambiguous stores byte-for-byte unchanged (old connect shown to downgrade 13→12); schema 13 adds model_installs. Managed llama.cpp b11390 engine: pinned fetch with SHA-256, per-launch verification, loopback port, API-key ownership proof, fit off, minimal environment, orphan reaping, GPU/CPU lane choice; adapter keeps the stream contract. Typed readiness replaces the generic ready line. Hardware tiers/presets in profiles.py (no unqualified preset). Mesh controls hidden in Beta; window toolkit pinned with WebView2/WebKitGTK preflight. Removed dead db/repo/runtime functions and duplicate status work. Build driver, locks, spec, Inno and Linux templates prepared; CI workflow not yet written.
- verification: Observed this session: contracts 20 OK; coordinator 1252 OK (4 skipped) before later engine-lane tests; engine tests 36 OK; readiness 12 OK; ownership/admission 24 OK; desktop 91 OK; build-driver tests 17 OK; Node 192/192. Pre-existing: worker suite needs fastapi; scripts launcher test has 2 IP-drift failures. Live (Mac, loopback): engine and model hashes matched pins; Ollama blob refused by upstream engine; managed qualification passed Chat and Code, Documents with reasoning on hit the 3072-token limit in one of two runs; smoke parity: page reading misread identifiers (MG- for NG-2026-0417); overflow refused; Stop worked; loopback-only; peak RSS ~5.0 GB; 24.7 tok/s warm.
- remaining: Full parity run with Ollama same-bytes baseline still running in background; Sections 2–4, package workflow, releases.md §2 edit, preset registration from evidence, OCR scope decision, Windows/Ubuntu builds via user-run CI.


<a id="ac-20261004-008"></a>
## AC-20261004-008 — Interrupted Foundation checkpoint preserved and independently reviewed
- date: 2026-10-04
- agent: agent
- status: review/checkpoint complete; implementation partial
- prompt_id: [UP-20261004-008](userprompts.md#up-20261004-008)
- tags: beta, checkpoint, static-review, parity, integrity, memory
- paths: tmp/beta-foundation-checkpoint-20261004T153112Z, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Preserved 64 mixed dirty-tree source/docs/evidence files in a verified archive with a tracked patch, hashes, integrity receipt and review; wrote the user-requested external memory update note for the next chat.
- changes: Review records five static findings: database-alias ownership gap, engine exit/record handling, empty foreign SQLite admission, incomplete build/reuse inputs, and Ubuntu distro matching; Windows installer verification needs disposable-host isolation. Recorded the overbroad older Mac sandbox claim as unproven while retaining the approved deferral. Application source and protected docs unchanged.
- verification: All archived file hashes matched source at capture; 30 Python files parsed without imports/execution; two model files and all 60 local engine manifest entries rehashed successfully. Completed parity JSON read: Code 3/3 both modes; approval note 3/3 off and 0/3 on; general document 3/3 off and 2/3 on; strict Chat 0/3 off and 3/3 on; page reading 0/3. release_accepted=false. Owner counts in AC-007 were not rerun. No application tests, live calls, downloads, installs, builds, host changes or Git writes.
- remaining: Owner resumes the existing plan, addresses review findings and parity failures, then completes Sections 2–4 and native package/device/update gates. PRESETS remains empty; package.yml absent; no final Beta/release acceptance. Recovery archive excludes weights/binaries/private app data and unrelated untracked media/tmp.


<a id="ac-20261005-001"></a>
## AC-20261005-001 — Foundation review findings fixed: aliases, survivors, admission, build identity, tiers, model bytes, startup readiness
- date: 2026-10-05
- agent: agent
- status: source and offline checks done; requester verification pending
- prompt_id: [UP-20261005-001](userprompts.md#up-20261005-001)
- paths: backend/coordinator/{ownership,db,server,engine,local_engine,runtime_llamacpp,readiness,device}.py, backend/contracts/profiles.py, desktop/{lifecycle,__main__,build}.py, frontend/app/app.js, scripts/engine_parity.py, .github/workflows/ci.yml, tests in backend/coordinator/test_{ownership_admission,engine,readiness}.py and desktop/test_{lifecycle,build}.py
- changes: Store paths are canonicalised (realpath) before locking, admission, connect, the coordinator and startup; hard-linked databases are refused (`alias`). Engine stop/reap forget a process only after confirmed exit; survivors, unreadable identity and missing start time raise `engine_stop_blocked`, keep the record and block a replacement launch; typed readiness code added. Admission refuses an empty SQLite file with nonzero user_version and turns unreadable meta into `metadata`. Build input identity adds interpreter executable/library hashes and origin, host/SDK, Inno Setup binaries digest and the requested trust root; reuse needs a complete, valid, freshly hashed artifact set; the Windows installer identity check runs only with `--disposable-host` and refuses a host with Refinix registered. Linux tiers require distribution `ubuntu` and VERSION_ID 24.04. Install records carry per-file size/SHA-256; status reads compare filesystem identity without hashing, loads re-hash once per launch and refuse/unload changed bytes; status/startup share `Coordinator.chat_readiness`. Adapter closes its loopback socket. CI installs the runtime lock.
- verification: Observed this session in desktop/.venv: coordinator 1308 OK (4 skipped); contracts 20 OK; desktop 125 OK; deploy/k3s 140 OK; fixtures/c07 32 OK; Node 192/192. New alias tests fail under the previous spelling-based rule (2 failures) and pass now. Pre-existing, out of Beta scope: worker suite needs fastapi; scripts launcher 2 IP-drift failures (deferred mesh launcher).
- remaining: Ubuntu 26.04 and other distributions need their own evidence before matching; Windows change-time residual noted in FileChecks; package/device/update gates untouched.


<a id="ac-20261005-002"></a>
## AC-20261005-002 — Section 1 evidence: fixture debugging, managed qualification, Mac preset/profiles, releases §2, package workflow
- date: 2026-10-05
- agent: agent
- status: source, offline checks and loopback evidence done; requester verification pending
- prompt_id: [UP-20261005-001](userprompts.md#up-20261005-001)
- paths: backend/contracts/profiles.py, backend/coordinator/server.py, scripts/qualify_execution.py, scripts/test_qualify_execution.py, backend/coordinator/test_{engine,document_generation}.py, frontend/app/test-control-centre.cjs, desktop/packaging_plan.py, docs/releases.md (§2 "Internal test artifacts", authorised scope), .github/workflows/package.yml, qualification-artifacts/macos/macos-applesilicon-metal-16g/qualification-managed-b11390-metal-2026-10-05.json
- changes: Strict Chat fixture with reasoning off: the model replies "unsafe; 2.4" (correct verdict and number, label omitted) 3/3, so it fails the exact shape; checker unchanged, decision left to the user. Page reading: at the 1600 px render the model reads NG-2026-0417 as MG-… deterministically (greedy 3/3) and SOP-MECH-014 varies with sampling; at a 2200 px render all identifiers were read in 5/5 runs (greedy 2, catalogue sampling 3). OCR stays unqualified. Qualification script can claim reasoning modes per workflow. Managed qualification passed Chat (both), Code small-edit proposal (both) and Documents (reasoning off). Registered the macos-applesilicon-metal-16g preset (8192 ctx, 1 slot, all layers, f16 cache, measured peak RSS 4.29 GiB, floors 5 GiB/1 GiB) and three managed profiles bound to that artifact. Documents with reasoning on now runs in the qualified mode with a disclosed route note; the person's model setting is unchanged. Added the authorised releases.md §2 internal-artifact text. Wrote the manually dispatched package workflow (three native lanes, read-only, no secrets, verified-input caches, disposable-host installer check); not triggered.
- verification: Loopback live runs on this Mac (model and engine hashes re-verified at load). Offline: coordinator 1317 OK (4 skipped); contracts 20 OK; desktop 125 OK; fixtures/c07 32 OK; scripts 38 with the 2 pre-existing launcher failures; Node 194/194; workflow YAML parsed and lane chooser executed locally; build.py --plan ran without building.
- remaining: Profiles/preset cover one representative device; other M-series Macs, Windows and Ubuntu tiers have no presets. Package workflow needs a user dispatch; Windows runner Inno Setup presence unconfirmed. Sections 2–4 continue.


<a id="ac-20261005-003"></a>
## AC-20261005-003 — Section 2: graphical model download/import/removal and load-time resource admission
- date: 2026-10-05
- agent: agent
- status: source and offline checks done; preview observed; requester verification pending
- prompt_id: [UP-20261005-001](userprompts.md#up-20261005-001)
- paths: backend/coordinator/{provisioning,test_provisioning,server,models,local_engine,engine}.py, backend/contracts/profiles.py, desktop/shell.py, frontend/app/{app.js,test-models-card.cjs}, backend/coordinator/test_engine.py
- changes: New `provisioning.Provisioner` (urllib3, already pinned): user-confirmed download of the catalogue's pinned HTTPS files with streaming SHA-256, resumable staging that is re-hashed before resume, HTTPS-only redirects, disk-space admission, cancel; exact-match import (bytes decide the role; copies, never moves); removal that waits for running work, unloads the engine, deletes the record then the folder. No automatic sweep or retry. TLS verifies certificates and falls back to the OS root file when a packaged Python has none. Endpoints: GET /v1/model/plan, POST /v1/model/download, /v1/model/provisioning/cancel, /v1/model/remove; native import via the shell bridge only (no HTTP path input). Settings → Models shows Download (size), Import files… (desktop window only), progress with Cancel, and Remove… after the impact is shown. Preset admission floors (2 GiB available memory, 1 GiB disk) are checked when a model is about to load; the memory floor is an estimate (mapped model pages excluded), not a measured minimum.
- verification: Offline: provisioning 21 OK; engine 76 OK; coordinator full suite OK (4 skipped); desktop OK; Node 199/199; scripts unchanged (2 pre-existing launcher failures). Browser preview of a headless coordinator on a scratch workspace: managed engine verified, tier macos-applesilicon-metal-16g matched, readiness `setup_incomplete`, Settings → Models shows "Download (3.2 GB)", /v1/model/plan returned source/licence/revision/sizes/SHA-256/location/free space, no console errors. No download was started.
- remaining: A real download/import through the packaged app is a device check. Page-reading render change (2200 px) deferred to an OCR qualification decision. Onboarding capability choices and Auto routing not started.


<a id="ac-20261005-004"></a>
## AC-20261005-004 — Section 3: process network observer on Proof Cards; read-only sandbox control check
- date: 2026-10-05
- agent: agent
- status: source and offline checks done; requester verification pending
- prompt_id: [UP-20261005-001](userprompts.md#up-20261005-001)
- paths: backend/coordinator/{observer,sandbox_probe,proof,db,server,code_service}.py, backend/coordinator/test_{observer,sandbox_probe}.py, frontend/app/{app.js,test-proof-card.cjs}
- changes: `observer.Window` records, for each local job (and each Code model call), what Refinix's own processes connected to: a Python audit hook for every coordinator connect/sendto/name lookup, and psutil samples of the engine's sockets every 0.25 s. Stored per attempt in a new nullable `attempts.network_json` column (additive; schema version unchanged, older builds ignore it). Proof Cards show observed public/local-network counts with the observer's coverage note; policy stays `unavailable` (nothing enforces), observer errors withhold counts, remote attempts never borrow this computer's observation. `sandbox_probe.probe` reports, read-only, the Ubuntu profile's controls (user manager, systemd ≥255, seccomp, Landlock ABI, delegated memory/pids/cpu) and always lists the missing aggregate temporary-storage limit; validation is never offered in this build. Shown on Settings → This computer.
- verification: Offline: observer 13 OK; sandbox probe 5 OK; coordinator suite OK; desktop OK; Node 200/200.
- remaining: Ubuntu sandbox runner and its hard storage limit need an Ubuntu environment and evaluation of a no-host-change mechanism (udisks loop image is the open candidate; user-namespace tmpfs is blocked by Ubuntu 24.04's default AppArmor userns restriction unless a host profile is added — outside current approval). Observer is observation only; no enforcement claim.


<a id="ac-20261005-005"></a>
## AC-20261005-005 — Section 4 (part): TUF update check/download/offline import, release metadata tool, embedded trust files
- date: 2026-10-05
- agent: agent
- status: source and offline checks done; requester verification pending
- prompt_id: [UP-20261005-001](userprompts.md#up-20261005-001)
- paths: backend/coordinator/{updates,test_updates,server}.py, scripts/update_repository.py, desktop/{build,shell,setup_py2app}.py, desktop/refinix.spec, desktop/test_build.py, frontend/app/{app.js,control.html,test-models-card.cjs}, .github/workflows/package.yml
- changes: `updates.UpdateService` uses python-tuf with the packaged trust root as bootstrap; checks only on request; offers only a signed `<channel>/<lane>/latest.json` whose version is newer, data format not older, numeric minimum OS met, and whose package target's signed custom fields agree; downloads to staging with TUF length/SHA-256 checks, progress and cancel; offline bundles go through the same client and trust state. HTTPS only, no redirects, OS-root TLS fallback. Settings → Updates (version, last check, offer, notes, download, Import update… in the window); no Install control is drawn because in-app install/recovery is not built — the verified package's folder is shown. `scripts/update_repository.py` (init keys outside the repo, publish packages from build manifests with per-lane latest.json, bundle) signs with securesystemslib's bundled pure-Python Ed25519 — internal test keys only. build.py `--trust-root`/`--update-feed` validate and embed `refinix-update-root.json`/`refinix-update-feed.json`, record their SHA-256 and the data-format version in the identity and input digest, and refuse a package missing them; the workflow passes them when `desktop/updates/internal-{root,feed}.json` exist.
- verification: Offline against a real throwaway signed repository: updates 20 OK, with refusals observed for the intended reasons (wrong signer "signed by 0/1 keys", replayed older timestamp "must be >= 2", plain HTTP, expiry, hash mismatch). Coordinator 1367 OK (4 skipped); desktop 128 OK; contracts OK; fixtures/c07 OK; Node 203/203; scripts 2 pre-existing launcher failures.
- remaining: No internal trust root exists yet (a key ceremony for the user; not created by the agent). In-app install, data set-aside/restore and per-OS switch/recovery helper; N/N+1 and engine-change package sets via the user's CI dispatch; device/update acceptance.


<a id="ac-20261005-006"></a>
## AC-20261005-006 — Section 4 (part): journalled data set-aside, restore and resume for update recovery
- date: 2026-10-05
- agent: agent
- status: source and offline checks done; requester verification pending
- prompt_id: [UP-20261005-001](userprompts.md#up-20261005-001)
- paths: backend/coordinator/{recovery,test_recovery,db}.py, desktop/{lifecycle,build}.py
- changes: `recovery.Recovery` (workspace lock required at every journal write): set_aside copies the database and WAL (never SHM) with sizes/SHA-256 through temp+fsync+atomic replace; commit; restore moves the attempted version's main/WAL/SHM/journal into recovery/attempted/<version>-<time>/ (nothing deleted), refuses if any unexpected database file remains, and puts verified kept files back atomically; resume finishes an interrupted set-aside or restore by location and hash; any unsafe condition records `recovery_blocked` and changes nothing further. Admission is version-aware: the version being verified may open during an update, a blocked recovery is refused with its own code and reason. Desktop startup finishes an interrupted step before admission, rolls the previous version back to its data during an unfinished update, and commits after the new version starts. Packages' TESTING notes state the update limits.
- verification: Offline with real SQLite stores and a real lock: recovery 12 OK (interrupted set-aside and restore resumed; changed kept copy and late -journal both block with canonical files byte-identical; old/new/other version admission; desktop startup finishing a restore). Full suites: coordinator 1379 OK (4 skipped); desktop 128 OK; deploy/k3s 140 OK; fixtures/c07 32 OK; contracts OK; Node 203/203; scripts 2 pre-existing launcher failures.
- remaining: Nothing yet calls set_aside: the per-OS install/switch helper (previous app as helper, process exit verification, binary swap and rollback) needs packaged N/N+1 builds on each OS. No device, package or update acceptance is claimed.


<a id="ac-20261005-007"></a>
## AC-20261005-007 — Prepare a local partial Beta checkpoint
- date: 2026-10-05
- agent: agent
- status: checkpoint prepared; implementation and release acceptance remain partial
- prompt_id: [UP-20261005-002](userprompts.md#up-20261005-002)
- paths: backend, desktop, frontend/app, scripts, .github/workflows, docs, AGENTS.md, README.md, tasks.md, agent-memory
- changes: Recorded the user's local-commit authorization and selected the existing standalone Beta source, build configuration, scope documents and synthetic qualification evidence for preservation. Kept separate website changes, media assets and temporary work outside the checkpoint. No application logic or protected documentation was edited in this checkpoint step.
- verification: Current branch/status and selected paths inspected; git diff --check passed. Previously recorded implementation checks remain attributed to their original entries; no test suites, models, packages or CI were run for this checkpoint.
- remaining: Known execution gaps and package/device/update/release acceptance remain open. Local checkpoint authorization does not authorize a push or publication.


<a id="ac-20261005-008"></a>
## AC-20261005-008 — Save verbatim user direction and align the Beta requirements
- date: 2026-10-05
- agent: agent
- status: memory, documentation and copyable planning handoff complete; owner plan/review pending
- prompt_id: [UP-20261005-003](userprompts.md#up-20261005-003)
- paths: docs/beta-user-direction-2026-10-05.md, AGENTS.md, README.md, docs/{PROJECT,README,model-catalog,security,releases,beta-execution-handoff}.md, tasks.md
- changes: Saved the original statement and follow-up verbatim in the requested Codex memory update note first, then in the repository report. Aligned active documentation with upstream/runtime reuse, broad compatible model choice, recommendations instead of model/device/version allowlists, automatic local routing and capacity-aware multiple-model/job support. Preserved tool/data/offline boundaries and distribution deferral; marked the old execution handoff's conflicting proposals historical. Added a planning-only handoff for the user to send and a review rubric grounded in the full statements.
- verification: Read current source and documentation; verified the report's two statement blocks match the saved memory, report file-link targets exist, and tracked documentation diff whitespace checks pass. No application tests, live models, downloads, CI or Git writes were run. No message was sent to the implementation owner.
- remaining: Implementation is unchanged. The owner must inspect the updated documents/source and return an execution plan through the user for independent critique; device/package/update/release claims still require observed evidence.


<a id="ac-20261005-009"></a>
## AC-20261005-009 — Add post-execution cleanup to the planning handoff
- date: 2026-10-05
- agent: agent
- status: handoff complete; user-run Git checkpoint pending
- prompt_id: [UP-20261005-004](userprompts.md#up-20261005-004)
- paths: docs/beta-user-direction-2026-10-05.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- changes: Added a final cleanup stage for proven unused/replaced code after approved implementation and authorised verification. Recorded the user's request to delete the temporary direction report only after preserving both verbatim statements in repository memory and repairing active links. No code or report was deleted.
- verification: Inspected current branch/status, changed paths and untracked checkpoint/media inventory. Current branch is aditya, one commit ahead of the local origin/aditya tracking reference. No tests, live models, downloads or Git writes were run.
- remaining: The user stages, reviews, commits and pushes the current changes. The implementation owner returns a plan for independent review before execution; eventual cleanup remains conditional on complete execution and verification.


<a id="ac-20261005-010"></a>
## AC-20261005-010 — Add the README ownership headline
- date: 2026-10-05
- agent: agent
- status: headline added
- prompt_id: [UP-20261005-005](userprompts.md#up-20261005-005)
- paths: docs/beta-user-direction-2026-10-05.md, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- changes: Added a prominent README ownership note at the top of the direction report. Root README work belongs to the teammate; later file-only synchronization from main waits for user confirmation and authorization, followed by normal member -> dev -> main integration preserving the final README.
- verification: Read current report, branch/status and relevant agent rules. No root README edit, tests, live calls or Git writes were performed.
- remaining: User confirmation that the final README has reached main and separate authorization for subsequent Git work.


<a id="ac-20261006-001"></a>
## AC-20261006-001 — Both local runtimes, Auto routing, capacity and local admission (A–F)
- date: 2026-10-06
- agent: agent
- status: implemented and checked by the agent; requester verification pending; not Beta acceptance
- prompt_id: [UP-20261006-001](userprompts.md#up-20261006-001), [UP-20261006-002](userprompts.md#up-20261006-002)
- paths: backend/contracts/profiles.py; backend/coordinator/{admission,capacity,router,hub,fake_ollama,test_model_runtime}.py (new); backend/coordinator/{runtime,runtime_llamacpp,models,engine,local_engine,provisioning,db,server,readiness,ocr,pdfrender,documents,docflow,identity,code_service}.py and their tests; desktop/{lifecycle,shell}.py; frontend/app/{app.js,control.html,refinix.css} and tests
- changes: Existing Ollama and the Refinix-managed llama.cpp engine run side by side; the model's origin selects the runtime ("ollama|name", "llama.cpp|id"), with no copied weights. Local candidate profiles replace the team-measurement gate on this computer only (locality, digest, declared capabilities and bounds), while worker/node/dispatch checks stay strict. Auto routing per request with a stored reason; pins are refused, never swapped. Capacity ledger (unified/discrete/CPU; resident weights once, per-job working state, bounded cancellable wait); a resident model reserves no new working state only for the window it was loaded with. Single managed-engine lease queue (b11390 router mode rejected: unauthenticated child listeners). Library of eight pinned Hugging Face entries, explicit Hub browse/resolve, imports without download. Schema 14 adds nullable model_selftests.check_fingerprint. Resume fixes: window-aware residency; install reads serialized on the shared connection (preview found InterfaceError under concurrent status/capabilities); Settings shows model names, runtimes and current Auto picks instead of internal keys.
- verification: Offline: coordinator 1459 OK (4 skipped); contracts 20 OK; desktop 128 OK; frontend 208 pass; scripts 38 with the 2 known hotspot-address launcher failures; worker 169 with the 1 known missing-fastapi import error (not installed). Loopback live on the Mac: Auto and pinned chats on both runtimes, vision routing for page reading, scan+SOP to DOCX with citations, a reviewable Code proposal with no disk change, concurrent Ollama and managed streams, a fingerprinted OCR self-test, and Ollama 0.35.1 /api/ps reporting the num_ctx sent (same window: no reload; new window: reload). Preview UI: Settings and one Auto chat with its route reason. Ollama and the managed engine started by these checks were stopped.
- remaining: Requester UI walkthrough. Chat self-test strict-format decision; a second managed model not tested live (no download authorized); protected docs (model-catalog, evaluation and others) still describe the earlier state; section G cleanup awaits named permission. Windows/Linux packages, updater/recovery, local sandbox and network-evidence gates remain outstanding.


<a id="ac-20261006-002"></a>
## AC-20261006-002 — Repair five review findings (Ollama start, Search scans, OCR admission, stale waits, Hub projectors)
- date: 2026-10-06
- agent: agent
- status: implemented and checked by the agent; requester verification pending
- prompt_id: [UP-20261006-003](userprompts.md#up-20261006-003)
- paths: desktop/lifecycle.py, desktop/test_lifecycle.py, backend/coordinator/{server,capacity,local_engine,runtime,docflow,documents,hub,test_model_runtime,test_documents}.py, frontend/app/{app.js,test-models-card.cjs}
- changes: (1) The Ollama supervisor beside the managed engine probes Ollama alone. (2) Search observes the runtimes when it has files, so a scan reaches the page-reading model Auto picks. (3) Page reads go through a job-scoped admitted call; a job's uses of one model share a ledger group and do not add up, and a job's end releases its whole group. (4) A memory wait re-reads residency and the loaded window each retry (Ollama /api/ps, engine state). (5) Hub listings pair projectors per model (named, repository, ambiguous, none); resolve refuses a projector not published for that file and a projector offered as weights; the UI auto-pairs only one unambiguous projector and otherwise asks, text only included.
- verification: Each new regression failed against the old behaviour and passes now. Offline: coordinator 1468 OK (4 skipped); contracts 20 OK; desktop 129 OK; frontend 210 pass; scripts 38 with the 2 known launcher failures; worker 169 with the 1 known missing-fastapi error. Loopback live: Settings "Start Ollama" beside the managed engine started ollama serve as the coordinator's child and shutdown stopped it; Search over the 3-page scan read every page through the managed Qwen vision model with one admitted reservation per page and none left afterwards.
- remaining: Requester walkthrough; items listed in AC-20261006-001 remain.


<a id="ac-20261006-003"></a>
## AC-20261006-003 — Stop double-counting loaded memory; pair projectors only on exact names
- date: 2026-10-06
- agent: agent
- status: implemented and checked by the agent; requester verification pending
- prompt_id: [UP-20261006-004](userprompts.md#up-20261006-004)
- paths: backend/coordinator/{capacity,server,hub,test_model_runtime}.py, frontend/app/{app.js,test-models-card.cjs}
- changes: A request needing no new memory is always admitted. Reservations record their window; a fresh reading that shows the model loaded at that window releases the reservation's working state as well as its weights. Each page read takes a fresh residency reading. Hub pairing: only an exact model-name match (named) or an unnamed projector in a single-model repository pairs automatically; related or prefix names and unnamed projectors beside several models are ambiguous, and resolve refuses them without projector_confirmed, which only the explicit choice screen sends. Paired files also offer text only.
- verification: New regressions fail against the reverted logic and pass now. Offline: coordinator 1473 OK (4 skipped); contracts 20 OK; desktop 129 OK; frontend 210 pass; scripts 38 with the 2 known launcher failures; worker 169 with the 1 known missing-fastapi error. Loopback live: scanned Search "transfer pump" returned inspection-report-scan.pdf page 1 and "discharge pressure" page 2; scan+SOP to Word completed with 3 checked citations, later pages admitted on a fresh reading (resident, window 8192) with the answer reservation released to 0/0; no reservations left; engine stopped.
- remaining: Requester walkthrough; Chat self-test strictness; platform/package, updater/recovery, sandbox and network-evidence gates.


<a id="ac-20261006-004"></a>
## AC-20261006-004 — Ignore generated desktop review builds
- date: 2026-10-06
- agent: agent
- status: implemented and ignore behavior observed
- prompt_id: [UP-20261006-005](userprompts.md#up-20261006-005)
- paths: .gitignore, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- changes: Added the repository-root-anchored /desktop/out/ ignore rule; retained all local build files and existing staged work.
- verification: git check-ignore -v matched the output directory, review ZIP and bundled executable to .gitignore:51. git status no longer reported desktop/out/ as untracked; the changed-file whitespace check passed. No tests, staging, commit or push performed.
- remaining: User stages the ignore rule and ledger appends with the existing checkpoint.


<a id="ac-20261007-001"></a>
## AC-20261007-001 — Model-agnostic routing with fallback, setup and Settings overview, categories, Dependabot, WebView2 bundling
- date: 2026-10-07
- agent: agent
- status: implemented and checked by the agent; requester verification pending
- prompt_id: [UP-20261007-001](userprompts.md#up-20261007-001)
- paths: see UP-20261007-001
- changes: Router ranks any compatible model from recorded evidence (publisher card 3, repository tags 2, runtime GGUF tags 1; never names) into an ordered list; documented limitations or a confirmed runtime incompatibility (picture-in tags while the runtime refuses pictures) remove a model from Auto only; pins keep hard checks and get a warning. Run and Code walk the list through memory admission before an attempt exists; precheck, preview, readiness and run share one task builder; picture questions are classified (transcription/text/visual, ambiguous = visual) and visual questions never take the OCR text route. Browse no longer assumes "general"; version-1 records drop guessed tags. Self-test: line breaks rejected before whitespace normalisation, formatting vs wrong-answer kinds, selftest-v3, schema 15 adds failure_kind and reply_excerpt, matches_now computed on read. Setup: footer button and Settings badge, overview card, hardware from startup, Ollama found/start panel, choices saved in meta, categories with queued downloads and shared disk check (recommend() removed). Settings: technical cards in a Details group, model cards with summary, alert and collapsible details. Windows setup installs a pinned, Microsoft-signed offline WebView2 runtime only when missing; .deb is the main Linux package. dependabot.yml (pip + Actions to dev), lock pin-consistency CI step, ci.yml checks Dependabot PRs into dev. Removed: LocalEngine.facts, engine hints map, router aliases, code_service router import, recommendation UI.
- verification: Offline final: coordinator 1513 OK (4 skipped); contracts 20 OK; desktop 137 OK (1 skipped); frontend 225 pass; scripts 38 with the 2 known launcher failures; worker suite not run (fastapi missing). Pin check proven to fail on a simulated declaration-only bump. Live, loopback, scratch REFINIX_DATA_ROOT, packaged builds local-review-20261007/b/c: first-run setup, Start Ollama (Refinix-owned, stopped at quit), Use existing models, relaunch kept the explanation hidden, Auto "hi" answered by qwen3.5 Ollama, pinned PaddleOCR ran with a recorded warning, Qwen off gave no_suitable_model instead of PaddleOCR, Word document written, scanned report read (NG-2026-0417, P-204) and searched (page 1). Chat self-test reply captured: qwen3.5 Ollama "unsafe; 2.4" (missing_label). Code proposal live through the source coordinator (f-string diff, nothing written). Real data store unchanged.
- remaining: D1 (accept the unlabelled self-test answer) awaits the user. Folder connection for Code in the packaged window needs the native picker (computer use unavailable). Windows/Linux packages and device checks, public host, signing/notarisation, updater and other Beta 0.1 gates; Dependabot activation after reaching main.


<a id="ac-20261007-002"></a>
## AC-20261007-002 — Repair the review findings: fallback budgets, picture intent, D1/D9, page-reader fallback, signature binding, Setup
- date: 2026-10-07
- agent: agent
- status: implemented and checked by the agent; requester verification pending
- prompt_id: [UP-20261007-002](userprompts.md#up-20261007-002)
- paths: see UP-20261007-002
- changes: Chat checks each candidate's window and reply allowance (and again after a default-window fallback) before an attempt; Code moves to the next model when the whole-file budget does not fit; pins never fall back. Picture intent: only clear text requests take the read-then-answer route; visual, verification, mixed or unclear requests need vision; a source-dependent request with nothing readable is refused. Removed the tag-absence "image input only" exclusion; D9 adds failure kind "incomplete" (runtime-reported output-limit stop only) that excludes a model from Auto for that task while the result matches; D1 accepts the unlabelled verdict and number; check definition selftest-v4. Page reader chosen from its own ordered list and admitted before the first page, fixed for the job; stored method names the reader and its runtime; extraction record takes model/runtime from the reader's profile. WebView2 signature check passes the path through REFINIX_SIGNATURE_PATH. Setup opens once on first launch (setup.first_opened); the footer link always shows, only the badge is conditional. Removed: image_input_only, the "incompatible" field, Coordinator.enabled_model_for; stray blank line.
- verification: Offline final: coordinator 1526 OK (4 skipped); contracts 20 OK; desktop 139 OK (1 skipped); frontend 226 pass; scripts 38 with the 2 known launcher failures; worker suite not run (fastapi missing). Live (loopback, scratch REFINIX_DATA_ROOT, builds local-review-20261007d then e): cached managed Qwen imported (3,413,361,504 bytes, manifest c0d7259f…); Ollama stopped → Chat answered by qwen3.5-4b-q4_k_m (llama.cpp); Ollama Qwen off → managed answered; managed off (it was Auto's first choice) → Ollama qwen3.5:4b-q4_K_M answered as second choice; page reading on the managed reader stored "qwen3.5-4b-q4_k_m on Refinix engine"; Chat check v4: Ollama Qwen passed; PaddleOCR failed on formatting (multi_line) this run, so not excluded. First launch opened Setup once (source preview) and the packaged window recorded setup.first_opened. Refinix-started Ollama and the engine stopped at quit; real data unchanged.
- remaining: Native Code folder picker (user, scratch data); genuine Windows signature/installer run; Windows/Linux packages and devices; signing/notarisation, updater, migration/replacement recovery and other Beta 0.1 gates; Dependabot activation after reaching main.


<a id="ac-20261007-003"></a>
## AC-20261007-003 — Complete the interrupted final repair verification using build 7g
- date: 2026-10-07
- agent: agent
- status: affected repair verification passed on this Mac; not Beta release acceptance
- prompt_id: [UP-20261007-003](userprompts.md#up-20261007-003)
- changed: These two ledgers only. Application source was preserved. The prior agent's latest source already refuses requests with no readable attachments, classifies text-only picture requests using whole-request matches, resolves/caches the page reader only when OCR is needed, and combines coordinator-authored system instructions into one leading Chat system message. No rebuild or application-copy cleanup was performed.
- build: local-review-20261007g, version 0.1.0 internal, macos-arm64. ZIP SHA-256 3e095616d4a30cdc27402416d388c5cd3fe3f4419bc630ee3b842b377b76acc8, 36,029,987 bytes. The 77-file shared application snapshot matches current source: 751f07172b79adc3b8ac990e55821f5580c026d051ad8015951b151ca084e95f.
- verified: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest backend.coordinator.test_model_runtime backend.coordinator.test_document_generation backend.coordinator.test_documents -q` ran 316 tests, OK with 1 skipped. The initial restricted run had 5 fake-loopback socket permission errors; the same authorized tests passed with sandbox permission lifted. The prior agent's reported 1533-test coordinator pass and other suites were not rerun or represented as fresh observations.
- live: Native packaged UI, existing scratch data, Ollama stopped. Inspected the persisted completed notes.txt answer (P-204, 7.9 mm/s versus 7.1 mm/s). Submitted a new Word-writing request on managed Qwen/llama.cpp: completed in 2062 ms, 60 output tokens, normal stop; the saved DOCX contains the supplied title and all three requested steps, passes ZIP CRC inspection, and matches its recorded SHA-256 802a7663d975db57cecd492f657a66a1cd7f02dd15658e86b615f6a662b93ac7. A new malformed-PDF summarisation request refused before any output, with the corrected error wording. Setup remained available while Ready and its explanation reopened. The native Code folder picker connected a disposable folder; a managed-model proposal produced only the requested subtraction-to-addition diff. The proposal was rejected; the fixture stayed unchanged.
- lifecycle/data: Open-file inspection confirmed the scratch database. Normal Quit stopped the application and owned llama-server; no Refinix/Ollama/llama-server processes remained. Relaunched the same 7g executable with the explicit scratch REFINIX_DATA_ROOT, without building another app. Chat history, the generated document, connected project and rejected proposal persisted; Setup did not force first-launch onboarding again. Final normal Quit exited successfully and left no matching processes. Real coordinator.sqlite3, -wal and -shm byte hashes remained identical across this continuation. The real store's pre-existing schema is 15; no migration or real-data launch was performed.
- remaining: A cosmetic lifecycle row for document artifact completion displays `attempt start -> undefined` although the saved job/attempt state is completed; not fixed in this verification scope. Genuine Windows signature/installer execution, Windows/Linux package/device qualification, signing/notarisation, updater trust/acceptance and replacement/migration recovery remain release gates. Dependabot activation still requires reaching the default branch through the authorized Git flow. No publication or Git writes occurred.


<a id="ac-20261007-004"></a>
## AC-20261007-004 — Prepare the requested updater and app-consolidation handoff
- date: 2026-10-07
- agent: agent
- status: handoff complete; plan and execution pending
- prompt_id: [UP-20261007-004](userprompts.md#up-20261007-004)
- changed: Created agent-memory/handoffs/2026-10-07-refinix-in-app-update-and-consolidation.md with the user's latest words, verified continuation checkpoint, existing update/recovery paths, graphical bootstrap/update requirements, safe duplicate cleanup, full release gates and the next review checkpoint. Appended these two ledgers only.
- inspected: Current status and focused updater, recovery, native shell, frontend and release/security authorities. Existing update service verifies/stages/imports packages but explicitly lacks in-app installation/relaunch; the current package lacks a configured trust root/feed. The three unpacked review bundles remain present.
- limitations: No application implementation, build, launch, deletion, tests, live model calls, downloads, data migration, protected-document edits, Git/GitHub writes or publication occurred. Earlier test/runtime observations are attributed to AC-20261007-003, not rerun here. The implementation owner must return a plan for independent review before execution.


<a id="ac-20261007-005"></a>
## AC-20261007-005 — Reconcile v3 and update the updater handoff for public installations
- date: 2026-10-07
- agent: agent
- status: handoff updated; v3 design PASS with required additions, implementation pending
- prompt_id: [UP-20261007-005](userprompts.md#up-20261007-005)
- changed: Updated the existing updater handoff in place with the latest verbatim user message, confirmed retention/owned-process boundaries, clean a260d99 baseline, full website-installed application update requirement, main-to-qualified-package/feed release chain, online-only connected header visibility and retained Settings offline import. Added v3 review disposition, archive/recovery clarifications and public OS/package acceptance criteria. Appended the normal ledgers; older ledger entries were preserved.
- inspected: Entire v3 plan, current status/source, release/security authorities and the internal-only package workflow. The prior five findings are addressed in the proposed design; public package/signing/feed publication is still missing, and passive online hints do not prove Internet/feed reachability.
- verified: Readback confirmed the latest message is present verbatim, the original verbatim request is unchanged, both approvals and the public/connectivity requirements are present, and previous ledger content is unchanged. `git diff --check` passed; changed paths are limited to this handoff and the two normal ledgers.
- limitations: No updater source changes, tests, builds, launches, installs, app cleanup, model calls, protected-document edits, Git/GitHub writes or publication. Historical repair evidence remains attributed to AC-20261007-003. Application execution and public release/device qualification remain later authorized work.


<a id="ac-20261007-006"></a>
## AC-20261007-006 — Accept v5 design and update the existing updater handoff
- date: 2026-10-07
- agent: agent
- status: v5 design PASS with implementation clarifications; execution pending
- prompt_id: [UP-20261007-006](userprompts.md#up-20261007-006)
- changed: Reconciled the existing handoff with v3 plus v4/v5: no age cutoff for already verified staging; expiry rejection for new imports; header hidden offline in every state; Settings retains local install/import/cancellation/recovery; internal-folder source supports the visibility proof; network observations state their limits. Preserved the raw user requests, approved retention/process boundaries and public release scope. Added mandatory saved signed-evidence/ownership and supported-schema-transition clarifications, carried forward channel/capability foundations, and retained the manual checkpoints without requesting another plan revision. Appended the two normal ledgers.
- inspected: Entire v5 attachment and the affected v3/v4 clauses, current status, AGENTS.md, PROJECT.md section 26, active tasks, focused release/security clauses and current updater offer/compatibility source. The four v4 review points are resolved at design level. A checksum or unsigned record alone does not authenticate a publisher; a higher schema number alone does not establish a supported transition.
- verified: Document readback confirmed the committed raw request was retained, website/update boundaries and v5 clauses were present, committed ledger prefixes were unchanged and the only changed paths were the existing handoff and two normal ledgers. `git diff --check` passed. These are documentation checks, not application tests.
- limitations: No application source, protected-document, data or package changes; no tests, builds, downloads, launches, installs, cleanup, host/network changes, Git/GitHub writes or publication. Design approval and the supplied attachment do not start implementation or establish device/release acceptance. Historical repair evidence remains attributed to AC-20261007-003.


<a id="ac-20261007-007"></a>
## AC-20261007-007 — In-app update: implementation and internal proof to checkpoint (a)
- date: 2026-10-07
- agent: agent
- status: implemented, offline-tested and packaged-proven on this Mac (internal channel, unsigned); not updater/release acceptance
- prompt_id: [UP-20261007-007](userprompts.md#up-20261007-007)
- changed: backend/coordinator/{updates.py (sources incl. internal update folder, bounded outer bundles, source-tagged download, kept signed evidence, offline install admission, prepare, eligibility, unreachable wording), app_archive.py (new: bounded app-ZIP checks with acyclic in-app link chains, extraction, tree and bundle verification), recovery.py (update_id/data_root binding, keep previous journal, discard, block, launches never restore/commit), server.py (install gate, writer and request activity, close_for_install, prepare/check-folder/cancel-install/acknowledge routes; refused POST closes its connection), provisioning.py (writer registration, active()), engine.py (reap_recorded_process exposed; logic unchanged)}; desktop/{update_apply.py (new helper, launch gate, resume table, owned-process checks, swap/relaunch/supervise/rollback, sweep), shell.py (install sequence, ui_ready commit, SIGTERM via wakeup fd), refinix.py and __main__.py (helper mode, launch gate), lifecycle.py (commit removed from startup), build.py (--channel, install capability, label/build-number rule, CFBundleVersion, input binding, ditto --norsrc --noextattr, never-index), setup_py2app.py, refinix.spec, updates/internal-root.json and internal-feed.json (public root; keys outside the repository)}; scripts/update_repository.py (bundle naming/atomic write, channel check, qualified_migrations); frontend/app/{app.js (shared header update control, Settings card, lifecycle row fix), index/code/control.html, refinix.css}; tests: test_app_archive, test_update_install, test_update_quiesce, test_update_apply, test_install_flow, test-update-control (new) and updated test_recovery, test_build, test-models-card.
- verified: desktop/.venv (Python 3.12.13, tuf 7.0.1): coordinator 1574 OK (4 skipped); desktop 180 OK (1 skipped); node --test frontend/app/test-*.cjs 238 pass. Source preview (headless coordinator): no console errors on Chat/Code/Settings, no /v1/updates request on load, honest unavailable state.
- packaged: fixtures 0.1.0-internal.3 (c341ce38c2314547e114a889d975821ff906ef4a3b35f8be84491ee2e22bbd18) and 0.1.0-internal.4 (417e5a635acdd14de539e0c3c7d9b1ad1ffdb76a1efc107d7ad726d7ab11e92f), internal root 8ceaddd13f7c623187b1c95dd39ec6841e6b18cf8eb419d1cd6c7c42dd19921f; superseded fixtures 0.1.0-internal.1/.2 kept as ZIPs. In scratch roots under the session scratchpad: no update traffic or metadata before a request; folder check, copy with evidence and prepare (offline evidence, extraction, codesign seal, engine check) on real packages; real helper H1 commit in 3 s; H2 new version killed before commit rolled back with newer data kept; H3 helper crash after swap resumed by the next launch and committed; H4 unrelated process from the app blocked and never signalled; bad bundles (unsafe, older, other platform, expired, tampered package, app/offer mismatch) refused; SIGTERM gives an orderly exit. Real ~/.aegisforge store hashes unchanged.
- found_and_fixed_during_proof: refused POST left its body to be parsed as a new request; resumed helper did not record itself as live; discarded attempts left their expanded app (79 MB).
- remaining: the user's own Install and restart click and the Wi-Fi observation (checkpoint a), user bootstrap of /Applications/Refinix.app (b), first click-update on real data (c), cleanup of the three unpacked copies (d). Insufficient disk is unit-tested only. Credentials on macOS use /usr/bin/security, so Keychain access is not bound to Refinix's ad-hoc signature; pairing credentials are a deferred feature and were not exercised. No HTTPS feed in this batch; Windows/Linux helpers, Beta root, signing/notarisation, hosting and publication remain later authorised work. No Git/GitHub writes.
- checkpoints (2026-10-07, later): (a) passed — user's click updated scratch 0.1.0-internal.3 → .4 (handed_off 23:19:21, committed 23:19:24 local), Wi-Fi off/on hid/showed the header icon (user-reported), 0 non-loopback connections from the scratch app in the measured window; Cmd+Q left no processes. Real store backed up with SHA256SUMS to ~/Refinix Backups/2026-10-07-before-updater (matches pre-session hashes). (b) passed — user installed /Applications/Refinix.app 0.1.0-internal.3 (seal ok, no quarantine, not translocated); real data schema 15, no migration. (c) passed — user's first real click-update to 0.1.0-internal.4 (quiescing 23:25:26 → committed 23:25:38); data journal committed for the same attempt; previous 0.1.0-internal.3 and data copy kept; old app and helper exited.
- found: the Settings page polls status every 10 s and fetches /v1/worker, which makes the coordinator try a previously paired worker at 10.219.115.160:30443 (private LAN, worker port) — seen from both old and new versions, unrelated to updates; pre-existing deferred-mesh behaviour to review separately. Checkpoint (d) cleanup not yet done.


<a id="ac-20261007-008"></a>
## AC-20261007-008 — Enforce the standalone mesh boundary and prepare internal.5
- date: 2026-10-07
- agent: agent
- status: source/offline checks and package preparation passed; primary internal.5 native update, normal Quit and checkpoint (d) pending
- prompt_id: [UP-20261007-008](userprompts.md#up-20261007-008)
- changed: Reused server.mesh_enabled for active-peer lookup, preflight, client construction and pairing, so packaged builds cannot contact saved workers or route work remotely. Source development still requires REFINIX_ENABLE_MESH=1; saved pairing rows remain unchanged. Settings requests /v1/worker only when mesh is enabled. Added offline regressions covering repeated observations/routing, direct transport/credential refusal, packaged opt-in refusal, development opt-in preservation and repeated Settings polls; retained remote fixtures explicitly opt into mesh. No deferred mesh code was removed.
- verified: Focused dispatch/remote Code 96 OK. Full coordinator 1578 OK (4 skipped) with permitted loopback fake servers; the initial restricted run failed because local socket binds were denied. All frontend checks 239 pass. git diff --check passed. Primary disk identity is internal.4 at /Applications/Refinix.app; only that Refinix app process was observed (PID 44160, executable/start time recorded). Its install journal is committed for .3→.4; the three pre-updater backup files match their SHA256SUMS. These fresh observations do not repeat the user's earlier Wi-Fi/UI acceptance.
- packaged: Cached-input-only updater-n5 / 0.1.0-internal.5, macos-arm64, bundle build 5, internal-test capability, unsigned/ad-hoc seal, schema 15. ZIP 35,838,758 bytes, SHA-256 46adeb724aab7882f51aa1d57ac6c3949bff9b3f6aa6fce615868816dac42270; shared source digest 38e67dce9d054c3539c848501219909f14d5e731dcf08782f09a6b07e2b1afa2. Existing private internal test signer used without key changes; local metadata versions advanced to 3. Real signed bundle .4→.5 passed folder offer, verified copy/staging, offline evidence authentication, bounded archive extraction, codesign seal and engine integrity, and reached ready against an isolated temporary install fixture. No swap or native launch in this preparation proof. Offline result saved in desktop/out/updater-n5/offline-admission-proof.json. Verified update bundle copied atomically to ~/Refinix Updates; the previous .4 bundle is retained.
- cleanup/evidence: All three older review ZIPs match their manifests and retain a build record. Their unpacked folders remain untouched. A bounded 15-minute read-only process/connection sampler was started for the user's next click-update and normal Quit; /private/tmp/refinix-internal5-network-monitor.jsonl. Sampling is observational evidence, not network enforcement or proof that no transient connection occurred.
- remaining: User opens Check for updates → Get internal.5 → Install and restart, verifies persisted work, visits Settings, then performs normal Quit. Confirm new app/owned-process exit and sampled worker traffic before checkpoint (d), which may move only the three named unpacked folders to the Bin and unregister them. Public release workflow, Beta root/HTTPS feed, signing/notarisation, Windows/Linux helpers and device qualification remain later separately authorised work. No Git/GitHub writes, protected-document changes, model calls/downloads, real-store migration, credential deletion or app-copy deletion occurred.
- checkpoint continuation: User reports the internal.5 update completed with no visible issue. Fresh reads confirm /Applications/Refinix.app is updater-n5 / 0.1.0-internal.5, and install/data journals both committed for update_id 0d1d16596b654bd1 (.4→.5, same canonical data root). The old application PID 44160 and helper PID 79409 exited; only the updated primary app PID 79437 remains. The sampler recorded 193 post-commit samples over approximately 3 minutes 20 seconds with no non-loopback connections or observation errors. This is a sampled window, not network-enforcement proof. The previous app remains retained and the three older unpacked folders are untouched. Separate normal Quit and explicit checkpoint (d) cleanup confirmation remain pending.


<a id="ac-20261007-009"></a>
## AC-20261007-009 — Complete normal Quit and the approved primary-app consolidation
- date: 2026-10-07
- agent: agent
- status: checkpoint (d) completed; internal macOS continuation complete, not public Beta release acceptance
- prompt_id: [UP-20261007-009](userprompts.md#up-20261007-009)
- changed: Unregistered only the three approved old app paths using lsregister -u and moved their containing unpacked folders through the native macOS Trash API. local-review-20261006/unpacked → ~/.Trash/unpacked; local-review-20261007e/unpacked → ~/.Trash/unpacked 23-52-40-456; local-review-20261007g/unpacked → ~/.Trash/unpacked 23-52-40-464. Full absolute recovery mapping is recorded in /private/tmp/refinix-checkpoint-d-trash-moves.json. Appended these normal ledgers; no source or protected-document edits.
- verified: User's normal Quit followed by fresh process scans found no Refinix app/helper/engine processes. The monitor recorded 113 consecutive no-app samples after the last app observation at 18:20:59 UTC. All three old folders are absent from their original locations and present in the Bin, and their old paths are absent from the actual user-session Launch Services registry. Spotlight returned exactly /Applications/Refinix.app, whose identity remains updater-n5 / 0.1.0-internal.5 / schema 15. Primary identity and all 15 retained ZIP/manifest/checksum/testing/build-record files have unchanged SHA-256 hashes. The initial sandboxed registry/Spotlight reads returned an empty view; the user-session reads confirmed the result. git diff --check passed.
- monitor: Stopped only this chat's own sampler after matching its exact script, PID 76840, executable and start time against the first log sample; its observations remain at /private/tmp/refinix-internal5-network-monitor.jsonl. Other historical stale Launch Services entries were outside the three-path cleanup scope and were left untouched; they did not appear in Spotlight's Refinix.app result.
- remaining: Public release workflow, Beta trust root/HTTPS feed, signing/notarisation, Windows/Linux helpers and device qualification remain separate later work. No Git/GitHub writes, public publication, model/network configuration changes, real-data migration, credential/model/ZIP deletion or wider repository cleanup occurred. Application remains closed after the normal Quit check.


<a id="ac-20261008-001"></a>
## AC-20261008-001 — Repair updater retention, journal and trusted-root failure paths
- date: 2026-10-08
- agent: agent
- status: implemented and offline-tested; source review passes for the three findings
- prompt_id: [UP-20261008-001](userprompts.md#up-20261008-001)
- tags: updater, recovery, journal, retention, root-rotation, offline-tests
- paths: desktop/update_apply.py, desktop/test_update_apply.py, desktop/test_install_flow.py, backend/coordinator/updates.py, backend/coordinator/test_update_install.py
- changes: Retention now runs under workspace ownership while the install remains committing, before the final committed marker. A subsequent attempt waits for the previous helper to exit; helper observation, timeout and lock adoption bind to the attempt ID, versions and data root. Stale helpers cannot prune or act on another attempt. Existing unreadable, malformed or incomplete install journals refuse startup/preparation; a missing install journal with unfinished data recovery also refuses. Offline authentication reads the newest cached trusted root and requires every consecutive authenticated rotation to it, refusing missing/unreadable history and disagreement at the final root. Optional process/status reads stay permissive. Existing install-flow fixtures now follow the real plan, snapshot, swap and retained-app sequence; returned fake helpers exit.
- verification: The six initial regression methods failed on the original implementation (12 failures including subcases), confirming the findings. Repaired focused updater paths: 53 tests OK. Full offline coordinator: 1580 tests OK, 4 skipped; full desktop: 187 tests OK, 1 skipped. The final stale-helper/retention/crash checks: 3 OK after adding the lock-adoption assertion. git diff --check passed. Full suites used permitted loopback fixtures and temporary test workspaces; logs are /private/tmp/refinix-review-fixes-coordinator-tests.log and /private/tmp/refinix-review-fixes-desktop-tests.log.
- remaining: These fixes are in source only. The installed internal.5 application was not rebuilt, launched or replaced, and package/device acceptance of these new bytes remains pending. No public release, Git/GitHub writes, protected-document changes, real-data migration, model calls/downloads, host configuration changes or further app/ZIP cleanup occurred.

## AC-20261008-002 — Guard repeated update actions and prepare internal.6
- date: 2026-10-08
- agent: agent
- status: implemented, offline-tested and internally packaged; native user install pending
- prompt_id: [UP-20261008-002](userprompts.md#up-20261008-002)
- related_prompts: UP-20261008-001
- tags: updater, rapid-clicks, idempotency, internal-package, offline-tests
- paths: frontend/app/app.js, frontend/app/test-update-control.cjs, backend/coordinator/updates.py, backend/coordinator/test_updates.py, backend/coordinator/test_update_install.py, desktop/shell.py, desktop/test_install_flow.py, desktop/out/updater-n6
- summary: Repeated update clicks now share one in-progress action; authenticated staged downloads and prepared installs are reused, and the new internal.6 update bundle is ready for the user.
- changes: The existing frontend busy state is claimed before asynchronous work and redraws both header and Settings, preventing duplicate checks, downloads, import choosers and install calls while preserving explicit retries after cancellation/failure. Coordinator download requests reuse a fully authenticated same-offer stage; damaged cached bytes are refused before a new explicit download. Install preparation shares the metadata-operation lock and revalidates/reuses its existing ready attempt. The native shell takes one nonblocking installation lock before showing confirmation. No new dependencies. Built internal.6/updater-n6 with cached engine inputs, schema 15 and the existing internal trust root, including AC-20261008-001's recovery/root-chain fixes. Signed local feed metadata advanced to targets/snapshot/timestamp version 4; the verified update bundle was placed in ~/Refinix Updates without replacing old bundles.
- verification: Added regressions failed before repair (frontend: three failures; initial backend/native methods: three failures and one error). After repair, focused Python updater/native paths: 57 tests OK; updater frontend: 15 passed. Full offline coordinator: 1584 tests OK, 4 skipped; desktop: 188 tests OK, 1 skipped; frontend: 242 passed. Package identity/hash, exact shipped frontend/coordinator source and desktop bytecode, complete signed offline authentication, real ad-hoc macOS seal and pinned engine integrity passed. An isolated fixture verified 20 post-download requests reused one file and repeated preparation reused one attempt, then cancelled the expanded fixture without an app swap. Actual update-folder admission is recorded in desktop/out/updater-n6/offline-admission-proof.json; network sockets were blocked (one harmless urllib3 IPv6 loopback capability probe). All 69 pre-existing package/record/update-bundle/primary-identity hashes stayed unchanged. Artifact SHA-256: a7395f97ff1645b42af515bbd2b8467046b450c029fc7f564ce9956b3e5ecddf; update-bundle SHA-256: 790de9413d6de6d0145c8621252bb33e3d2fad12b94e423fc3d7f46bd3bc6ded. Logs: /private/tmp/refinix-internal6-*-tests.log, /private/tmp/refinix-internal6-build.log and /private/tmp/refinix-internal6-admission-proof.log.
- remaining: /Applications/Refinix.app remains internal.5; the user will install internal.6 and observe the native result. Current changes are uncommitted. Public Beta release, Developer ID signing/notarisation, HTTPS feed and Windows/Linux qualification remain outside this batch. No Git/GitHub writes, protected-document edits, real-data migration, model calls/downloads, primary launch/install, or original-package cleanup occurred.

<a id="ac-20261008-003"></a>
## AC-20261008-003 — Public Beta update channel, Windows and Ubuntu install helpers, release tooling
- date: 2026-10-08
- agent: agent
- status: implemented and offline-tested; Ubuntu .deb rules natively qualified in an emulated container; device and signing evidence pending
- prompt_id: [UP-20261008-003](userprompts.md#up-20261008-003)
- tags: updater, tuf, beta-feed, maturity, deb, pkexec, polkit, windows-job, release-tooling, workflows
- paths: backend/coordinator/release.py, backend/coordinator/tuf_offline.py, backend/coordinator/install_methods.py, backend/coordinator/updates.py, backend/coordinator/app_archive.py, desktop/update_apply.py, desktop/update_windows.py, desktop/deb_root.py, desktop/install_check.py, desktop/refinix.py, desktop/shell.py, desktop/build.py, desktop/setup_py2app.py, desktop/packaging_plan.py, desktop/windows/refinix.iss, desktop/linux/control.in, desktop/linux/com.refinix.desktop.policy, desktop/macos/entitlements.plist, desktop/updates/beta-feed.json, desktop/python-version-windows.txt, scripts/update_repository.py, scripts/requirements-release.lock, scripts/release_assemble.py, scripts/qualify_deb.py, scripts/refinix, .github/workflows/release.yml, deploy/distribution/workflows/, frontend/app/app.js, tests beside each
- changes: One release identity (internal/beta channels; preview/accepted/final maturity; ordering key; Debian X.Y.Z~R.S; linear public build number). Beta publisher with encrypted keys, consistent snapshots, separate preview/accepted pointers, no overwrites, forward-only history, advance/refresh/renew/withdraw/rotate/verify/bundle. Client: pointers by maturity, per-format payloads, packages via public TUF calls with redirects only to listed hosts, .deb recovery packages, evidence root continuity. Helper split into mac-app swap, Windows setup run inside a kill-on-close job from process creation with registry snapshot and file-list completeness, and Ubuntu .deb through a pkexec root step (request folder opened without links, copies authenticated with expiry at admission, offline re-check later, dpkg/APT under the front-end lock, recovery by dpkg state, recorded rollback). Builder: Beta labels, preview-test capability, Developer ID inside-out signing + notarisation + DMG, Authenticode hooks, shipped file list, polkit policy, control fields allow-list. release.yml (manual, read-only, designated main commit), distribution-repo deploy/advance/refresh templates, release assembly. Launcher address drift fixed at its cause.
- verification: Full offline suites on macOS: coordinator 1624 OK (5 skipped), desktop 223+ OK, scripts OK, contracts 20 OK, frontend 242+ pass; new focused tests include test_updates_beta (26, incl. the unchanged e234a0a client reading new internal output and online-key rotation recovering from a fast-forward), test_update_methods (13), test_deb_root (16), test_build (48), test_workflows (10), test_release_assemble (6). Ubuntu 24.04 amd64 container (Docker Desktop, emulated; image ubuntu@sha256:534baea6…): 66 Linux unit tests OK as an unprivileged user and 14/14 native .deb qualification checks passed with dpkg 1.22.6 / apt 2.8.3 (Inst+Conf plan, --reinstall, refusals, admission, install, rollback, held lock, unfinished-work refusals, kill during unpack → same-copy repair, unpacked → configure). The container run found and fixed a real defect: request folders inherited Ubuntu's 002 umask and were refused by root.
- remaining: Beta trust root/keys (user, offline, CP-A), signing (none ready), Windows native job/installer tests (CI runner or VM), clean-Ubuntu device and pkexec/polkit prompt behaviour, real package builds, website publication and live feed (owners, CP-B). No Git/GitHub writes, publication or protected-document edits yet.

## AC-20261008-004 — Sandbox, cleanup, presentation, website downloads, release workflow repairs and local package builds
- date: 2026-10-08
- agent: agent
- status: implemented and offline-tested; packages built locally for checking only; device testing, signing, publication and Beta acceptance pending
- prompt_id: [UP-20261008-003](userprompts.md#up-20261008-003)
- tags: sandbox, landlock, systemd-run, code-apply-modes, native-dialogs, performance, cleanup, sih-removal, website, release-workflow, deb, dmg, ocr-beta
- paths: backend/coordinator/sandbox_launcher.py, backend/coordinator/sandbox_local.py, backend/coordinator/code_service.py, backend/coordinator/server.py, backend/coordinator/sandbox_probe.py, backend/coordinator/{db,engine,capacity,models,device}.py, desktop/shell.py, desktop/refinix.spec, frontend/app/app.js, frontend/design/{site.html,site.css,docs.html}, scripts/build-site.sh, scripts/release_assemble.py, scripts/measure_performance.py, .github/workflows/{release.yml,package.yml}, README.md, CONTRIBUTING.md, AGENTS.md, tasks.md, docs/{PROJECT,README,releases,security,evaluation,model-catalog}.md, docs/workflow-diagram.html, frontend/design/assets/README.md, tests beside each
- changes: Ubuntu Code sandbox (provisional): a launcher on the system Python under `systemd-run --user` with no address families, a system-call filter, no new privileges, no namespaces and resource limits, Landlock confining files to a fixed-size workspace image, self-checks and an input digest; Code validation bound to proposal, inputs, command and profile; Apply modes `sandbox_validated` and an explicit, audited `unsandboxed`. Native error dialogs on Ubuntu (GTK → zenity → stderr). Performance harness (no optimisation justified). Dead code removed (ten unused functions); old checkpoint, presentation brief/PDFs and ignored build output moved to the private archive with a hash manifest. Current public presentation without SIH branding; repository renamed to Refinix in docs. Scan reading labelled Beta in the app and catalogue. Website: the 10 October countdown and "private for now" labels replaced by a tester-preview section whose download cards build-site.sh renders from a release's release.json (files only from that release's download folder, with SHA-256; unsigned platforms shown unavailable with the reason); owner publish commands updated. Release workflow repairs found by building: Windows/Ubuntu jobs installed only part of the packaging plan's locks (the bundle would have lacked the update client, psutil and PDF rendering), the Ubuntu job lacked libpython3.12 (PyInstaller refuses without it), the .deb qualification step used the wrong arguments, interpreter and guard, and feed-signing tests ran before their lock; macOS internal job lacked its build lock. Documented the one-time Beta key/root setup and that the first public build number is 7 or higher (internal builds 1–6 exist on the release Mac).
- verification: Final offline suites on the Mac (Python 3.12, Node): coordinator 1635 OK (5 skipped), desktop 224 OK (1 skipped), scripts 62 OK, contracts 20 OK, frontend 247 pass; `git diff --check` clean. Ubuntu 24.04 amd64 container (emulated): the real `.deb` and AppImage of `0.1.0-preview.1` built the release.yml way in 45 s, then `qualify_deb.py --real` passed 23/23 (dpkg 1.22.6, APT 2.8.3: update rules, real control fields and files, APT install with dependencies, installed tree = file list, root entry refuses without pkexec); feed-signing Linux tests 42 OK once the release lock was installed. Release assembly and the site export ran on that package. macOS: unsigned Beta ZIP + DMG (public build 7) built in 20 s; DMG checksum valid, ad-hoc signature verifies, Gatekeeper rejects as expected, LSMinimumSystemVersion 26.0 (Homebrew Python). Website export checked in the browser at phone and desktop widths with no console errors. Landlock ABI 8 enforcement observed in a native arm64 container. Performance: launch to first status 330 ms, status 4.3 ms median, idle 0% CPU / 107 MB, 3-page scan render 111 ms, 256 MB update stage 326 ms + admission 200 ms. Incident: launching the packaged Mac app for a smoke check used the default data folder (the packaged entry ignores development flags); it ran the same idempotent post-update tidy-up internal.6 runs, kept the previous app and data copy, and migrated nothing (schema 15 both); later package checks read bundles without launching them. Not run: systemd-run/udisks sandbox properties, any Windows build or check, any device walkthrough, signing, publication.
- remaining: Beta keys/root (user, offline), CP-A commit and member → dev → main, Windows build on the hosted runner, signing (none ready), owners' Pages/environments/About settings, CP-B publication, device walkthroughs (Ubuntu desktop, Windows PC), Codex deep review, one repair batch, Beta acceptance.


<a id="ac-20261008-readme-sync"></a>
## AC-20261008-README-SYNC — Copy only the final README from main
- date: 2026-10-08
- agent: agent
- status: README synchronized; release-policy/doc/screenshot changes handed back to the implementation owner
- prompt_id: [UP-20261008-README-SYNC](userprompts.md#up-20261008-readme-sync)
- changed: Replaced only root README.md with GitHub's exact file from main commit 01928744466d75ad6f52064db450c7ca75c743b0; appended the normal ledgers. No merge, branch change, commit or push.
- verified: GitHub blob SHA-1 11816fce2bae41d2e48330e24603fa24a714a2c2 matches the downloaded UTF-8 bytes; local README readback SHA-256 af2552d9a505283e3e25ff873f907a54c70dac3724a0a2884b5f9c74f38630bc matches. The prior dirty README is preserved at /private/tmp/refinix-readme-before-main-20261008-9z611f2j/README.md; adjacent sync-record.json records both hashes and the source identity.
- findings: The current release assembler/docs still require platform signing; a coherent owner change is needed for the user's unsigned public Beta direction. The imported README preserves the teammate's final structure and includes older implementation-status paragraphs needing targeted owner reconciliation. Latest owner entry AC-20261008-004 reports Mac ZIP/DMG and Ubuntu packages built for checks, Windows build pending; those checks were not rerun here.
- limitations: No app source changes, other protected-doc edits, screenshots, tests, builds, installations, live model calls, release publication, Git/GitHub writes or messages to the implementation owner occurred. Real screenshots, current Beta presentation, platform download/install verification and device acceptance remain owner work.

<a id="ac-20261010-segment1-repair"></a>
## AC-20261010-SEGMENT1-REPAIR — Recovery safeguards and native CI repairs
- date: 2026-10-10
- prompt_id: [UP-20261010-SEGMENT1-REPAIR](userprompts.md#up-20261010-segment1-repair)
- changed: Loop ownership checked before sandbox unmount; damaged Ubuntu current-attempt authority refuses admission without pruning recovery; native report/exit gates fail closed; public verification checks requested website/package version. Bounded APT setup shared by four workflows, with one official mirror fallback. Windows native fixtures clean up their process trees. Focused regressions and approved evaluation/tasks evidence updated.
- verified: Coordinator 1656 tests OK (16 skipped), desktop 253 OK (6 skipped), scripts 75 OK, contracts 21 OK, frontend 248 passed; focused recovery/CI/public regressions 73 OK; four workflows passed actionlint; diff whitespace clean. Hash-pinned test dependencies installed only in a temporary environment. Initial broad checks needed approved loopback fixture access and the missing pinned packaging dependency.
- remaining: Fresh native qualification on the repaired commit, then production keys/root and user merge/publication checkpoints. Earlier run 37981019381: Windows unit failure, Linux APT stall/cancel, Mac lane success under the earlier gate. No production keys, app/data install, real models, dev/main merge or public release touched.

## AC-20261010-SEGMENT1-NATIVE-REPAIR — Fix failures exposed by the repaired CI gates
- date: 2026-10-10
- changed: The shared Ubuntu build action exposes only system gi/cairo in an isolated virtual environment, preventing unrelated runner AWS/OpenSSL imports. Package-launch and update-journey status reads allow 10 seconds for bounded runtime probes. Regression checks preserve scratch-root identity and refuse missing toolkit bindings.
- observed: Run 37988624319 at 0aa4645: Linux APT 18 seconds, builds passed, native signing-unit imports failed on inherited OpenSSL; Windows native units and both builds passed, package checks 5/6 (launch probe timed out while the app served requests). Local worker 217, deployment fixtures 140 and C07 fixtures 32 passed after completing the temporary test environment.
- remaining: Hosted qualification of the follow-up commit and the agreed production-key/manual checkpoints.

## AC-20261010-SEGMENT1-GTK-METADATA — Preserve GTK version metadata in the isolated build
- date: 2026-10-10
- changed: Link only PyGObject/pycairo egg-info alongside gi/cairo, preserving GTK isolation and the exact distribution version metadata required by PyInstaller's hook.
- verified: Inspected the repository hash-pinned PyInstaller 6.22.3 Linux wheel without installing it; hook-gi reads importlib metadata for PyGObject. Workflow regression proves the selected metadata is discoverable and unrelated packages stay excluded; actionlint and whitespace checks passed.
- observed: Run 37989900925 at 27915ee: Ubuntu GTK import passed but build hook failed without metadata; Windows package qualification plus update and rollback journeys passed after the timing fix. Fresh full native qualification remains required.

## AC-20261010-SEGMENT1-INTERRUPTION-QUALIFIER — Recognise a safely discarded interrupted setup
- date: 2026-10-10
- changed: The interrupted-update qualifier recognises the existing cancelled/discarded terminal states only with the old installed version, matching shipped file manifest and unchanged saved work. Production recovery logic is unchanged.
- verified: Focused workflow/public/journey regressions 24 passed, including rejection of a wrong version or incomplete restored tree. The isolated GTK metadata regression and four-workflow actionlint passed; fresh native qualification remains required.
- observed: Run 37989900925 Mac package and all three journeys passed; Windows package, normal update and rollback passed before the interrupted-setup qualifier waited on an unrecognised recovery state.

## AC-20261010-SEGMENT1-UBUNTU-SCRATCH-HOME — Respect the root updater's home boundary in CI
- date: 2026-10-10
- changed: Ubuntu journey fixtures live inside the runner user's home, as the real root updater requires. A failed bundle import or update preparation stops that journey promptly; interruption polling also recognises an already-ended attempt. Production filesystem restrictions are unchanged.
- verified: Focused workflow/public/journey regressions 26 passed, including home placement despite a different system temporary folder and failed prerequisite refusal. Run 37991781158 at b8fbc81: Ubuntu setup 19 seconds, Ubuntu/Windows builds and package qualifiers passed, Mac package and 24 journey checks passed. Remaining native recovery and floor checks are pending.

## AC-20261010-SEGMENT1-RECORDED-HELPER — Target the actual helper and retain diagnostic evidence
- date: 2026-10-10
- changed: Interruption qualification kills the helper identified by the update journal's PID, creation time and executable, then waits for death, instead of scanning command-line text. Native app/helper logs and helper status are retained inside report artifacts; user data and signed bundles are excluded.
- observed: Run 37991781158 Windows package 6/6, normal update and rollback passed; interrupted recovery stayed at installer_running with N+1 installed (journey 22/24). This is not a passing recovery path. The follow-up qualifies an exact recorded-helper kill and preserves diagnostics for any remaining application defect.
- verified: Focused qualification/workflow regressions 26 passed; native rerun is required.

## AC-20261010-SEGMENT1-BOOTSTRAP-FUSE — Recover before application imports and use rootless storage
- date: 2026-10-10
- observed: Run 37995379252 at 5a4a052: Ubuntu package 29/29 and update journeys 25/25; sandbox UDisks authorization failed in the headless session. Windows package 6/6 and journeys 22/24; exact helper death was confirmed, but the partial installation failed to import pydantic_core before recovery (resume_count stayed zero). Mac package/journeys and the oldest macOS runner passed.
- changed: Packaged startup uses the existing workspace lock and recovery gate before application imports; device profile imports are deferred until needed. Linux prefers the existing FUSE backend, journals the mount before launching it, preserves image/resource/security limits and retains failed cleanup for retry.
- verified: Fresh-process regression proves a missing application dependency cannot prevent recovery handoff or cause database admission. Desktop suite 254 tests OK (6 skipped); coordinator 1657 tests OK (16 skipped); focused update/path/sandbox checks 134 OK; final startup/FUSE group 37 OK, including interrupted-mount cleanup. Native follow-up remains pending.

## AC-20261010-SEGMENT1-MOUNT-PATHS — Detect escaped paths during sandbox cleanup
- date: 2026-10-10
- changed: Decode mountinfo's octal escapes once when matching a mount point or source, preserving detection for data folders containing spaces or literal backslashes.
- verified: Sandbox suite 23 tests OK, including escaped paths and rejection of recursive decoding; whitespace check clean. A native run at the final source commit remains required.
