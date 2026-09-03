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
## AC-20260903-001 — Add the Control Room design tokens and the Chat surface reference
- date: 2026-09-03
- agent: Claude
- status: partial
- prompt_id: [UP-20260903-001](userprompts.md#up-20260903-001)
- related_prompts: [UP-20260902-007](userprompts.md#up-20260902-007)
- tags: ui, design-tokens, chat-surface, theming, accessibility, evidence-semantics
- aliases: control room tokens, blueprint artifact, cyanotype dark, approval gate, execution target picker, contrast sweep
- paths: frontend/design/README.md, frontend/design/tokens.css, frontend/design/chat.css, frontend/design/chat.html, agent-memory/userprompts.md, agent-memory/agentchangelog.md
- summary: Added a two-theme design token set and a static Chat surface reference page that renders the approval gate, execution-target picker and job inspector using the frozen contract vocabulary.
- changes: Recorded the Control Room direction with Blueprint reserved for artifacts; added light and dark token blocks resolving across system-default and explicit choices; built the Chat page with lifecycle rail using JobState literals, event log using Event.data.kind values, and an approval gate carrying an Approval.action; rendered unavailable evidence as a hatched grey row that cannot read as a healthy zero; suppressed transitions during a theme swap.
- verification: Served the page locally and swept all 108 text-bearing elements for contrast in three theme states — system dark, explicit dark, explicit light; raised six token values and recessed the disabled target control after the first sweep failed; final minimum ratio 4.49:1 with every other element at or above 4.5:1. Confirmed the three webfonts load rather than silently falling back by measuring glyph widths against the fallback stacks. Grid resolves to 188/860/232 at 1280px with no horizontal overflow.
- remaining: Documents, Code, Control Center and the public distribution site are unbuilt. The page is a static reference: it is not wired to the coordinator or the event stream. Fonts load from Google Fonts and must be self-hosted before any offline build. Other browsers, screen readers, keyboard traversal order and breakpoints below 1100px are unverified. No Git writes ran.

<a id="ac-20260903-002"></a>
## AC-20260903-002 — Add the public distribution site reference
- date: 2026-09-03
- agent: Claude
- status: partial
- prompt_id: [UP-20260903-001](userprompts.md#up-20260903-001)
- related_prompts: none
- tags: ui, public-site, distribution, blueprint, theming, accessibility
- aliases: download website, cyanotype whiteprint, p&id hero, checksum verification, pre-release state
- paths: frontend/design/site.css, frontend/design/site.html, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Added a static reference for the public distribution site in its own Blueprint treatment, carrying an honest pre-release download state rather than a fabricated release.
- changes: Added a self-contained token block that does not inherit the application tokens, since the site is a separate trust boundary; built hero, sovereignty-proof, capability and download sections; drew the hero P&ID plate as inline SVG; rendered enforced, observed and unavailable as three distinct claim kinds with the unavailable one hatched; marked the page with a sample-content strip and replaced download buttons with a stated not-yet-released state; documented the treatment and the theme-swap measurement pitfall in the design README.
- verification: Swept all 93 text-bearing elements for contrast in dark and light; zero failures, minimum 7.54:1 dark and 5.19:1 light. Confirmed no horizontal overflow at 1265px client width. Fixed a hero SVG annotation clipped outside its viewBox and removed an empty text node. Confirmed the data-theme-switching hook suppresses transitions, measured as transition-duration 0s while set.
- remaining: Documents, Code and Control Center surfaces are unbuilt. Both pages are static references not wired to the coordinator. Fonts load from Google Fonts and must be self-hosted before any offline build. Version numbers, checksums, system requirements and release artifact names on the site are placeholders and require team decisions. Other browsers, screen readers, keyboard traversal and sub-1100px breakpoints are unverified. No Git writes ran.

<a id="ac-20260903-003"></a>
## AC-20260903-003 — Rework the public site treatment after design review
- date: 2026-09-03
- agent: Claude
- status: partial
- prompt_id: [UP-20260903-001](userprompts.md#up-20260903-001)
- related_prompts: none
- tags: ui, public-site, design-review, ornament, theming, accessibility
- aliases: remove drafting grid, atmospheric ground, corinthian helmet, meander frieze, placeholder artwork
- paths: frontend/design/site.css, frontend/design/site.html, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Replaced the public site treatment after the requester rejected the tiled drafting-grid background, moving to an atmospheric ground and an engraved classical plate.
- changes: Removed the tiled grid background entirely and replaced it with two soft radial fields behind the content; removed the hard-bordered claim and build grids in favour of hairline rules and larger spacing; enlarged the display type and softened button geometry; replaced the P&ID hero plate with a drawn medallion holding a frontal Corinthian helmet above a Greek meander frieze, chosen because the aegis is the source of the repository name; added a visible circular marker stating the artwork is a placeholder; retained the honest pre-release download state and sample-content strip.
- verification: Reference sites reviewed in-browser before reworking. Swept all 92 text-bearing elements for contrast in dark and light using the data-theme-switching hook to avoid transition races; zero failures, minimum 7.20:1 dark and 5.30:1 light. Confirmed no horizontal overflow at 1245px client width and that hero, three sections and footer occupy contiguous vertical space with no gaps. First helmet attempt drawn in profile read as an unrecognisable silhouette and was rebuilt frontally; crest and scale then corrected on a second pass.
- remaining: The hero artwork is explicitly provisional and awaits a chosen commissioned or public-domain replacement. Documents, Code and Control Center surfaces are unbuilt. Both pages are static references not wired to the coordinator. Fonts load from Google Fonts and must be self-hosted before any offline build. Version numbers, checksums and system requirements remain placeholders. The preview pane would not paint content below the fold, so sections after the hero were verified by measurement rather than by screenshot. No Git writes ran.

<a id="ac-20260903-004"></a>
## AC-20260903-004 — Add four engraved plates and ambient motion to the public site
- date: 2026-09-03
- agent: Claude
- status: partial
- prompt_id: [UP-20260903-001](userprompts.md#up-20260903-001)
- related_prompts: none
- tags: ui, public-site, ornament, svg, motion, accessibility
- aliases: corinthian helmet, athenian owl, doric temple, labyrinth, ember eyes, conic ray field
- paths: frontend/design/site.css, frontend/design/site.html, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Replaced the single simple helmet with four dense engraved plates and added restrained ambient motion, after the requester judged the previous ornament too sparse and too plain.
- changes: Raised the hero medallion detail with a beaded border, a thirty-leaf laurel wreath, a twenty-four unit egg-and-dart ring and a hundred-spoke conic ray field; rebuilt the helmet with a crest drawn over the bowl, a decorated brow band, bowl hatching, egg-and-dart along the nasal and cheek spirals; added three further plates - an Athenian owl tetradrachm on the proof section, a Doric temple elevation on the capability section, and a concentric labyrinth on the download section; added ember glow and long-cycle blinking on the helmet and owl eyes, one travelling glimmer on the labyrinth, and a four-minute rotation on the ray field, all disabled under prefers-reduced-motion.
- verification: Reference sites re-examined before drawing. All four plates inspected by lifting the below-fold figures to the top of the document, since the preview pane would not paint below the fold. Swept all 92 text-bearing elements for contrast in dark and light with transitions suppressed; zero failures, minimum 7.20:1 dark and 5.30:1 light. Confirmed no horizontal overflow at 1245px and that all seven declared animations report a running playState. Three drawing defects were found and corrected on review: the bowl painted over the crest, the gorgoneion collided with the crest and read as an insect so it was replaced with a decorated brow band, and the laurel leaves pointed radially instead of lying along the ring.
- remaining: All four plates are explicitly provisional placeholders. Documents, Code and Control Center surfaces are unbuilt. Both pages are static references not wired to the coordinator. Fonts load from Google Fonts and must be self-hosted before any offline build. Version numbers, checksums and system requirements remain placeholders. Sections below the hero were verified by measurement and by lifting elements, not by full-page screenshot. No Git writes ran.

<a id="ac-20260903-005"></a>
## AC-20260903-005 — Rebuild the public site on a glass surface system with an interactive product demo
- date: 2026-09-03
- agent: Claude
- status: partial
- prompt_id: [UP-20260903-001](userprompts.md#up-20260903-001)
- related_prompts: none
- tags: ui, public-site, glassmorphism, interaction, motion, accessibility
- aliases: surface switcher, tabbed terminal, copy button, scroll reveal, theme toggle, near-black ground
- paths: frontend/design/site.css, frontend/design/site.html, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Rebuilt the public site on a near-black glass surface system with roughly twice the content and a working product demo, after the requester judged the previous version empty and unimpressive.
- changes: Replaced the token set with a near-black ground, three-layer radial lighting and glass panels using low-alpha fills, hairline borders and backdrop blur; adopted DM Sans for UI while keeping Spectral for display and IBM Plex Mono for terminal blocks; added a sticky blurred nav with a pre-release chip and a theme toggle, a formula band, a four-card design-approach row, a stats band, a two-column get-started block, a closing section and an expanded footer; added an interactive surface switcher with working Chat, Documents, Code and Control Center panels that demonstrate the evidence semantics on the public page; added tabbed terminal blocks with a copy button, scroll reveal, card hover lift and a pointer spotlight; retained all four engraved plates and their ambient motion. Reference sites were studied for surface technique only; their copy, branding and product content were not reproduced.
- verification: Read the reference page structure and measured its computed surface tokens before building. Swept 268 text-bearing elements for contrast in both themes with every panel unhidden; zero failures, minimum 7.20:1 dark and 5.62:1 light. Confirmed no horizontal overflow at 1265px, no console errors, and that tab switching, the copy button and the theme toggle all behave correctly in both directions. Four defects were found and fixed during review: a .hero > * rule overrode the spotlight overlay position and displaced the whole hero grid; semantic ok and danger colours were hardcoded for dark and failed at 1.92:1 in light; reveal styles applied without a scripted-document guard, so a script failure would have hidden the entire page; and IntersectionObserver-based reveal stranded 31 elements permanently invisible after an anchor jump, replaced with a scroll position check re-run on load and hashchange.
- remaining: All four plates remain provisional placeholders. Documents, Code and Control Center application surfaces are unbuilt. Both pages are static references not wired to the coordinator. Fonts load from Google Fonts and must be self-hosted before any offline build. Version numbers, checksums, system requirements and the stats figures are placeholders requiring team decisions. Sections below the hero were verified by measurement and by lifting elements into view, since the preview pane would not paint below the fold. Other browsers, screen readers and keyboard traversal are unverified. No Git writes ran.

<a id="ac-20260903-006"></a>
## AC-20260903-006 — Place the team mark and prepare the logo asset slot
- date: 2026-09-03
- agent: Claude
- status: partial
- prompt_id: [UP-20260903-001](userprompts.md#up-20260903-001)
- related_prompts: none
- tags: ui, branding, assets, public-site, chat-surface
- aliases: rokunin sync logo, team mark, brand token, logo placement, data uri inlining
- paths: frontend/design/assets/README.md, frontend/design/site.css, frontend/design/site.html, frontend/design/chat.css, frontend/design/chat.html, frontend/design/tokens.css, agent-memory/agentchangelog.md
- summary: Placed the Rokunin Sync mark across the public site and the Chat surface using a drawn stand-in, and prepared the asset slot so the supplied logo file drops in without further edits.
- changes: Added a brand orange token to both site themes and all three application theme blocks, kept separate from the semantic signal colour; added a drawn SVG symbol as a stand-in mark in the site nav and the Chat surface header; placed the full lockup in the footer credit and the closing signature as team attribution rather than as the product wordmark, since the lockup spells the team name and the product is Refinix; made those images stay hidden until they actually decode so a missing asset degrades to the text credit instead of a broken image; created assets/README.md recording the expected filenames, the Refinix versus Rokunin Sync distinction, the swap procedure and the licensing note; taught the single-file artifact build to inline anything under assets/ as a data URI, since published artifact pages cannot load external images.
- verification: Confirmed the symbol renders at the intended size in brand orange on both pages and that the SVG use reference resolves; confirmed both lockup images correctly remain hidden while the file is absent; fixed the version string wrapping to two lines in the Chat header after the mark was added, verified back to one line with no horizontal overflow; confirmed the artifact build reports the two missing asset references and leaves them untouched rather than emitting broken markup.
- remaining: The supplied logo image could not be written to disk from the conversation, so frontend/design/assets/rokunin-sync-logo.png does not exist and the placed mark is a drawn stand-in, not the real artwork. A team member must save the file at that path; the lockup then appears automatically and the artifact build inlines it. The four engraved plates also remain provisional. Documents, Code and Control Center surfaces are unbuilt. Fonts load from Google Fonts and must be self-hosted before any offline build. No Git writes ran.

<a id="ac-20260903-007"></a>
## AC-20260903-007 — Change the public site headline to "Nothing leaves the machine"
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-001](userprompts.md#up-20260903-001)
- related_prompts: none
- tags: ui, public-site, copy
- aliases: hero headline, nothing leaves the machine, plant wording
- paths: frontend/design/site.html, agent-memory/agentchangelog.md
- summary: Changed the public site hero headline from "Nothing leaves the plant" to "Nothing leaves the machine" at the requester’s direction.
- changes: Edited the hero h1 only. The three other uses of "plant" were left in place because they carry a different sense: the capability heading describes the work an industrial plant generates, the download copy describes the installer reaching the plant, and the token comments describe HMI plant state.
- verification: Confirmed the headline wraps to three balanced lines at 1240px with text-wrap balance and stays inside its box; no new horizontal overflow attributable to the change.
- remaining: The wording is narrower than the product behaviour it sits above. The same page advertises pairing, where the coordinator routes bounded job context to a trusted device over the LAN, so work can leave the originating machine while remaining on the premises. Flagged to the requester; the wording stands as their decision.

<a id="ac-20260903-008"></a>
## AC-20260903-008 — Replace the pointer spotlight with a grain particle field
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-001](userprompts.md#up-20260903-001)
- related_prompts: none
- tags: ui, public-site, motion, canvas, performance, accessibility
- aliases: grain field, particles, cursor interaction, spotlight removed, canvas background
- paths: frontend/design/site.css, frontend/design/site.html, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Replaced the pointer-tracked gradient spotlight with a canvas grain field whose particles drift on a slow rotation and scatter away from the cursor.
- changes: Removed the spotlight overlay, its CSS and its pointer handler, along with the hero grid guard that existed only to exclude it. Added a fixed canvas behind all content carrying roughly 1,200 low-alpha particles; the field rotates slowly about the viewport centre to echo the sync mark, about a fifth of the grains carry the brand orange, and particles near the pointer brighten and are pushed outward before easing back. Particle colours are read from CSS custom properties so the field follows the theme toggle. Restricted to fine pointers, skipped entirely under reduced motion, and paused while the tab is hidden.
- verification: Measured the reference implementation directly before building - its particle canvas draws pure white at 0.04 alpha over about 0.84 percent of its pixels, desktop only. Tuned this field to 0.49 percent coverage at 0.047 average alpha with a 23 percent warm share, lower than the reference because it is visible at rest rather than only on movement. Confirmed pointer response by comparing a 300px region at the cursor against the far corner: 5.4x peak alpha and 3.6x average. Confirmed the field recolours in both directions across the theme toggle, that hero layout is unchanged after removing the grid guard, and that no console errors occur. Three defects were found and fixed: the field was far too sparse at first tuning, it painted nothing until the first animation frame so a hidden tab stayed blank, and the theme recolour was deferred inside a double requestAnimationFrame so it never ran where frames are throttled.
- remaining: The four engraved plates and the team lockup remain provisional. The logo asset is still absent, so two 404 requests per page load are expected until it is added. Live pointer motion could not be observed in the preview pane because it holds the document hidden and starves requestAnimationFrame; interaction was verified by forcing synchronous repaints instead. Other browsers, screen readers and keyboard traversal are unverified. No Git writes ran.

<a id="ac-20260903-009"></a>
## AC-20260903-009 — Repalette the public site to black, silver and sky blue, and deepen the glass
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-001](userprompts.md#up-20260903-001)
- related_prompts: none
- tags: ui, public-site, palette, glassmorphism, accessibility
- aliases: silver sky blue palette, amber removed, glass recipe, backdrop saturate, colour discipline
- paths: frontend/design/site.css, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Replaced the amber-accented palette with black, silver and sky blue after the requester rejected it, and rebuilt the glass treatment with a gradient fill, saturation lift, inset highlight and depth shadow.
- changes: Measured the reference implementation’s live colours and custom properties rather than estimating, then rebuilt both theme token blocks around a near-black ground, a cooler blue-black panel ground, four silver text tiers and a sky-blue accent. Applied colour discipline: sky blue carries every accent, green is limited to the enforced state, and orange is reserved for the team mark. Recoloured the helmet plate embers, the grain particles and the card hover glow from amber to sky blue. Replaced the flat glass with a shared recipe combining a gradient fill, blur with a saturation lift, an inset top highlight and an outer depth shadow, with a separate light-theme variant.
- verification: Swept 268 text-bearing elements for contrast in both themes with every panel unhidden; zero failures, minimum 5.37:1 dark and 4.70:1 light. Confirmed the glass computes the intended gradient, blur and shadow stack in both themes, and that both themes render correctly. One regression was introduced and fixed during this change: a global sed intended to remove duplicated panel backgrounds also stripped the fill from the buttons, nav chip, theme toggle and file rows, leaving the theme toggle on the browser default grey at 2.44:1; all four were restored and re-verified.
- remaining: The Rokunin Sync mark stays brand orange against the new blue and silver, which is a deliberate single-accent choice the requester may want revisited. The four engraved plates and the team lockup remain provisional, and the logo asset is still absent so two 404 requests per page load persist. The application surfaces keep their separate instrument palette and were not touched. No Git writes ran.

<a id="ac-20260903-010"></a>
## AC-20260903-010 — Replace the hero plate with the supplied video clip
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-001](userprompts.md#up-20260903-001)
- related_prompts: none
- tags: ui, public-site, media, assets, repo-size, accessibility
- aliases: hero video, hero-loop.mp4, poster frame, screen blend, helmet removed
- paths: frontend/design/assets/hero-loop.mp4, frontend/design/assets/hero-poster.jpg, frontend/design/assets/README.md, frontend/design/site.css, frontend/design/site.html, agent-memory/agentchangelog.md
- summary: Replaced the engraved Corinthian-helmet plate in the hero with the supplied 15 MB video clip, circularly masked and blended into the page, with a still captured from the clip as its fallback.
- changes: Copied the supplied clip to assets/hero-loop.mp4 and removed the helmet plate markup from the hero, cutting about 15 KB of inline SVG. Added a square media container with the clip absolutely positioned inside a circular mask, cropped by object-fit, screen-blended so its black ground drops out, feathered at the edges by a radial mask and ringed by a hairline. The light theme inverts and multiplies instead, since a pale ground gives screen nothing to reveal. Captured a frame at 13.5 s from the running clip and saved it as assets/hero-poster.jpg, used as the video poster, the reduced-motion still and the fallback image. Added a mp4 and image mime map plus byte-range headers to the scratch dev server, and taught the artifact build to leave assets over an inline size cap as external references.
- verification: Confirmed the clip loads and plays with no media error, readyState 4, and that an explicit play call is not rejected. Fixed a layout defect found on first render: the clip is portrait 720x1280 and, as a flow child, its intrinsic height overrode the container aspect-ratio and stretched the hero box to 495x880; taking it out of flow restored a true 495x495 square. Confirmed both render paths - live clip visible with the still hidden, and, with the fallback forced, the still visible at the same size and blend, loaded at its natural 560x560. Confirmed both themes render correctly and that the artifact build inlines the poster while leaving the clip external.
- remaining: The clip is a 15 MB binary committed as an ordinary Git blob and needs a decision - Git LFS, exclusion plus deploy-time delivery, or re-encoding to a fraction of the size. No encoder was available locally to re-encode it. It cannot be inlined into a single-file artifact build, so artifact previews show the still frame and only a served copy animates. The team lockup asset is still absent. Documents, Code and Control Center surfaces remain unbuilt. No Git writes ran.

<a id="ac-20260903-011"></a>
## AC-20260903-011 — Transcode the hero clip so it plays, and enlarge the hero art
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-001](userprompts.md#up-20260903-001)
- related_prompts: none
- tags: ui, public-site, media, performance, repo-size
- aliases: hero-loop.webm, mediarecorder transcode, vp9, hero sizing, blank space
- paths: frontend/design/assets/hero-loop.webm, frontend/design/assets/README.md, frontend/design/site.css, frontend/design/site.html, agent-memory/agentchangelog.md
- summary: Transcoded the 15 MB hero master to a 2.3 MB WebM so the clip plays in a single-file build instead of falling back to a still, and enlarged the hero art to close the empty space on the right.
- changes: With no encoder installed, produced the transcode in the browser - drew the master frame by frame into a 600x600 canvas, already centre-cropped to match how the page renders it, and captured 13 seconds from the 8 s mark with MediaRecorder at VP9 and 1.3 Mbps, saving the result through a dev-server write hook. Added the WebM as the first source ahead of the mp4, and taught the artifact build to inline video types under an 8 MB cap. Enlarged the hero art by giving the right column the larger grid share, letting the figure bleed past its column, and holding the circular mask solid to 63 percent before feathering rather than 52 percent.
- verification: Confirmed the page selects hero-loop.webm as currentSrc and plays it with no media error. Confirmed the artifact build inlines it, producing a 3.15 MB page against the 16 MB ceiling, where the previous build left the clip external and showed only the still. Art grew from 495 to 580 px square, 17 percent larger, and the container stays square. Two regressions were caught and fixed while sizing: the first bleed pushed 181 px of horizontal overflow, traced to the ray field scaling with the enlarged plate, and a narrower text column wrapped the call-to-action row onto two lines; after rebalancing, horizontal overflow measures zero, down from the 2 px that predated this change, and all three buttons sit on one row.
- remaining: The 15 MB mp4 master is now unused by every current browser but still committed as an ordinary Git blob, and should be excluded, moved to LFS, or dropped. The team lockup asset is still absent. Documents, Code and Control Center surfaces remain unbuilt. No Git writes ran.

<a id="ac-20260903-012"></a>
## AC-20260903-012 — Add the intro gate, swap the hero to the deity artwork, and replace grain with a network field
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-001](userprompts.md#up-20260903-001)
- related_prompts: none
- tags: ui, public-site, media, motion, assets, layout
- aliases: intro gate, get started, glitch turbulence, deity reveal, network field, full width
- paths: frontend/design/assets/, frontend/design/site.css, frontend/design/site.html, agent-memory/agentchangelog.md
- summary: Replaced the hero clip with the supplied deity engraving, added a full-screen intro gate that plays the clip and hands off to the site through a glitch and a deity reveal, and swapped the grain background for a linked network field.
- changes: Widened the page from 1180 to 1560 px so content no longer sits in a narrow column. Removed the circular hero clip and its ray field, putting the supplied deity artwork in its place, pushed for contrast on the dark theme and inverted on the light one. Added an intro gate holding a native-resolution clip, the team mark top left, and a glass control bottom centre; the space either side of the portrait clip is filled by the network field. On activation the clip runs an SVG turbulence displacement with a slice-tear animation, then the deity fades in with two sky-blue eyes blinking on long offset cycles, holds two seconds, and withdraws to the left as the gate fades. Replaced the grain particle system with a network of drifting nodes linked to near neighbours, which the pointer attracts, brightens and links to directly. Derived a transparent PNG of the team mark by keying the black out of the supplied JPEG, so it needs no blend mode and works on both themes. Produced a native 720x1280 intro transcode at 3.6 MB by recording the video element stream directly.
- verification: Confirmed the gate sequences base to glitching to revealing to exiting to gone, that the eyes are positioned from the artwork box rather than the viewport so they stay on the face at any size, and that the deity artwork reads on black - measured at 52 percent light pixels and mean luminance 147 over its opaque area. Swept 267 text-bearing elements for contrast in both themes; zero failures, minimum 5.37:1 dark and 4.70:1 light, with no horizontal overflow. Confirmed the artifact build inlines six assets for an 8.63 MB page against the 16 MB ceiling. Two defects were found and fixed: the intro canvas collapsed to a canvas element’s intrinsic 300x150 because the centring grid stopped inset:0 from stretching an absolutely positioned child, and the footer mark still pointed at a PNG that did not exist.
- remaining: The 15 MB mp4 master is referenced only as a last-resort source and remains an ordinary Git blob needing exclusion, LFS or removal. Motion was verified by driving the sequence and holding states open, since the preview pane starves requestAnimationFrame while hidden. Documents, Code and Control Center surfaces remain unbuilt. No Git writes ran.

<a id="ac-20260903-013"></a>
## AC-20260903-013 — Silver mark with sheen, blindfold light rays, smoke, and intro performance work
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-001](userprompts.md#up-20260903-001)
- related_prompts: none
- tags: ui, public-site, branding, motion, performance, media
- aliases: silver logo, sheen sweep, light rays, blindfold, smoke, get started button, canvas throttling
- paths: frontend/design/assets/, frontend/design/site.css, frontend/design/site.html, agent-memory/agentchangelog.md
- summary: Replaced the orange mark with the supplied silver one and gave it a swept highlight, rebuilt the entry control, turned the eye points into light escaping a blindfold, added smoke around the figure, and cut the animation cost that was making the intro stutter.
- changes: Derived a transparent PNG from the supplied silver JPEG by keying out the black and trimming the transparent margin, then added a highlight swept across a copy of the mark and masked to the mark’s own alpha, so it reads as light travelling over metal rather than a bar crossing a rectangle. Rebuilt the entry control: the arrow now points sideways in its own round well, the surface is a brighter glass with a hover highlight that crosses it, and nothing in the hover or active state touches position. Replaced the eye points with slits at the cloth line, each driving a masked cone of light up and down, sized in viewport units. Added two drifting smoke layers behind the figure for the hold. Cut animation cost three ways: only one network field runs at a time, links batch into two paths per frame instead of one stroke call per link, canvas density is capped at 1.25 and node count reduced.
- verification: Measured both video files before changing anything - each decodes at about 57 fps with zero dropped frames, so the reported stutter was the page rather than the clip, and the work went into animation cost instead of re-encoding. Benchmarked the link drawing at 0.50 ms per frame per canvas before and 0.05 ms after, with two canvases previously running at once. Confirmed the control holds position under hover, measured identical at x 607 y 766 before and after, and that its arrow path is horizontal. Confirmed the sheen animation is attached, the beams resolve to 185 px up and 141 px down against a 4 px slit, and the smoke layers render at 686 and 845 px. Swept 267 text elements in both themes: zero failures, 5.37:1 dark and 4.70:1 light, no horizontal overflow. Artifact builds to 8.45 MB against the 16 MB ceiling.
- remaining: The beams were first sized as a percentage of the slit and came out about 25 px long; they are now in viewport units. Bitrate hints are ignored when recording from a video element stream and the canvas route needs animation frames the preview pane does not provide, so the intro clip length remains the only reliable size control - it is a 12 s loop taken from the 31.5 s master. The 15 MB mp4 master is still an ordinary Git blob. Motion was verified by holding states open rather than by watching it run. No Git writes ran.

<a id="ac-20260903-014"></a>
## AC-20260903-014 — Fix the intro clip sizing and quality, retarget the exit, and set the wordmark in chrome
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-001](userprompts.md#up-20260903-001)
- related_prompts: none
- tags: ui, public-site, media, layout, branding, motion
- aliases: intro video cropped, indefinite grid height, dvh sizing, exit right, chrome wordmark, deity glitch in
- paths: frontend/design/assets/intro.webm, frontend/design/site.css, frontend/design/site.html, agent-memory/agentchangelog.md
- summary: Found and fixed the intro clip overflowing its viewport, raised its encode bitrate, sent the figure right onto the hero artwork instead of off to the left, gave it a glitched entrance, and set the wordmark as chrome type.
- changes: The clip and the figure were sized with percentage heights inside a centring grid, where a centred item has an indefinite block size, so the percentage fell back to the media intrinsic height - a 1280px clip in a 1000px window, cropped top and bottom. Both now size in viewport units with dvh and a viewport max-width. Re-encoded the clip at 6.03 Mbps against the previous 2.33, at native 720x1280. The exit now measures the hero artwork box at run time and maps the figure onto it, so it travels right and settles where the page shows it rather than sliding off to the left. Added a torn, displaced entrance so the figure arrives the way the clip left instead of fading up still. Replaced the mark with the REFINIX wordmark set in Michroma under a brushed-chrome gradient with a sheen masked to the letterforms. Moved the artwork and the team lockup to single CSS custom properties so a single-file build inlines each once rather than per element, and taught the build to inline url() references in stylesheets.
- verification: Measured the clip before and after - 720x1280 in a 1000px viewport before, 563x1000 after, top at 0 and bottom at 1000, fully visible, height filled and aspect ratio correct to within 0.005. Confirmed the exit transform resolves to a positive x translation of 385px with a 1.041 scale onto a hero box 783px wide, and that the arrival animation is attached. Confirmed Michroma loads and the wordmark clips its gradient to text. Swept 267 text elements in both themes: zero failures, 5.37:1 dark and 4.70:1 light, no horizontal overflow. Artifact builds to 12.17 MB against the 16 MB ceiling, down from 13.42 MB before the single-inline change.
- remaining: The supplied REFINIX wordmark image could not be written to disk from the conversation, so it is set as type; a saved PNG can replace it. Bitrate remains only loosely controllable - the recorder overshoots the hint by roughly two times and the canvas route needs animation frames the preview pane does not provide, so duration stays the practical size lever. The 15 MB mp4 master is still an ordinary Git blob. No Git writes ran.

<a id="ac-20260903-015"></a>
## AC-20260903-015 — Play the master clip untouched, fix the page network field, add lightning and a breathing hero glow
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-001](userprompts.md#up-20260903-001)
- related_prompts: none
- tags: ui, public-site, media, layout, motion, canvas
- aliases: master first source, replaced element intrinsic size, canvas 300x150, lightning, breathing glow, periodic glitch
- paths: frontend/design/site.css, frontend/design/site.html, agent-memory/agentchangelog.md
- summary: Stopped transcoding for served pages by putting the supplied master first in the source list, fixed the page network field being confined to a corner, and added lightning on the reveal plus a breathing glow and periodic tear on the page figure.
- changes: The clip had been re-encoded for every delivery, and each pass is a generation of loss; the master mp4 is now the first source so a served copy plays the supplied file untouched, with the WebM left as a fallback for single-file builds where the master cannot be inlined and the browser falls through on its own. Fixed the page network canvas: an absolutely positioned canvas is a replaced element, so width auto resolved to its intrinsic 300 by 150 rather than stretching to its insets, which confined the whole field to the top-left corner; it now sizes explicitly and a ResizeObserver rebuilds the buffer when the element changes size rather than relying on window resize alone. Added two offset full-bleed lightning flashes with an asymmetric rise and fall on the reveal. Wrapped the page figure so a sky-blue and a silver field breathe behind it on different periods. Added a short tear on the page figure every three seconds, driven by a class the script toggles so the gaps cost nothing.
- verification: Confirmed the page selects hero-loop.mp4 as currentSrc. Measured the page canvas before and after - 300 by 150 with drawing confined to that corner before, filling the viewport after, with drawn content spanning to 1575 of 1585 horizontally and 996 of 1000 vertically. Confirmed the periodic tear fires via a mutation observer over a 3.6 s window, and that both breathing animations are attached. Swept 267 text elements in both themes: zero failures, 5.37:1 dark and 4.70:1 light. Caught and fixed a 68 px horizontal overflow introduced by the glow reaching past the layout; overflow is back to zero. Artifact builds to 12.17 MB against the 16 MB ceiling.
- remaining: Artifact previews still fall back to the WebM, so only a served copy shows the master untouched. The supplied REFINIX wordmark image could not be written to disk from the conversation and remains set as type. The 15 MB master is still an ordinary Git blob. No Git writes ran.

<a id="ac-20260903-016"></a>
## AC-20260903-016 — Complete the application design: Documents, Code and Control Center
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-001](userprompts.md#up-20260903-001)
- related_prompts: [UP-20260902-007](userprompts.md#up-20260902-007)
- tags: ui, application-surfaces, documents, code, control-center, evidence-semantics, accessibility
- aliases: chatbot ui complete, control center, shared app shell, co3 unblock, four surfaces
- paths: frontend/design/app.css, frontend/design/documents.css, frontend/design/documents.html, frontend/design/code.css, frontend/design/code.html, frontend/design/control.css, frontend/design/control.html, frontend/design/chat.css, frontend/design/chat.html, frontend/design/tokens.css, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Built the three missing application surfaces and extracted a shared shell, so the application design is complete and can be handed to the consumer waiting on it.
- changes: Verified first that only Chat existed and its three sibling links were dead. Extracted everything common to the four surfaces into app.css - the frame, surface nav, inspector rail, state chips, buttons, approval gate, artifact treatment and dense row tables - and reduced chat.css to Chat-only rules, so a surface file now carries only what is unique to it. Built Documents against the inspection_report_to_approval_note workflow, with source hashes, the seven-step pipeline showing which node ran each step, findings that always carry their page, an unresolved finding that keeps the extractor’s own words rather than inferring a value, section-level citations and an artifact validation record. Built Code against repository_request_to_validated_patch, showing the minimum file set rather than a repository transfer, the patch prepared in a temporary workspace, the sandbox run with command, exit status, stdout and an explicitly empty stderr, and the coordinator checks that run before approval is offered. Built Control Center covering all eight groups from workflows section 10, leading with runtime state, and carrying installation, models, agent profiles and self-test, jobs, paired devices with capabilities and revocation, resource meters, network evidence and audit with retention and export, plus an exportable Proof Card in the rail. Wired the four pages to link to each other.
- verification: Swept every text-bearing element on all four surfaces in three theme states - system dark, explicit dark and explicit light - 668 elements in total: zero failures and no horizontal overflow on any surface, worst ratio 4.53:1. Two token defects were found and fixed during the sweep: --st-fault measured 4.03:1 in dark where it carries failed chips and diff deletions, and --signal measured 4.49:1 on the sunken rail in light. Confirmed every surface link and stylesheet reference on every page resolves with status 200.
- remaining: First-run onboarding (workflows section 2) and the pairing exchange screens (section 8) are not built; Control Center shows pairing state and offers the controls but the invite, code exchange and confirmation screens do not exist. All four surfaces remain static references: they render fixed sample markup, are not wired to the coordinator and consume no event stream, and no value on them is a measurement. Fonts load from Google Fonts and must be self-hosted before any offline build. Screen readers, keyboard traversal order and other browsers are unverified. No Git writes ran.

<a id="ac-20260903-017"></a>
## AC-20260903-017 — Build the onboarding and pairing screens
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-001](userprompts.md#up-20260903-001)
- related_prompts: none
- tags: ui, application-surfaces, onboarding, pairing, evidence-semantics, accessibility
- aliases: first run, five steps, no silent downloads, self-test, trust exchange, pairing code, workspaces not merged
- paths: frontend/design/onboarding.css, frontend/design/onboarding.html, frontend/design/onboarding-install.html, frontend/design/pairing.css, frontend/design/pairing.html, frontend/design/control.html, frontend/design/tokens.css, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Built first-run onboarding and the pairing exchange, the two screens the previous pass left out, and wired the Control Center entry points that had nowhere to go.
- changes: Built onboarding against workflows section 2, split across two pages so the stepper stays legible. Step 1 is reported rather than asked - there is no Create Workspace, Join, Coordinator, Worker or Server choice, because those are runtime responsibilities and not a setup question. Step 2 is the main engine picker, where every card carries source, licence, model and version id, download and installed size, quantisation, RAM and VRAM need, and runtime and OS, and every figure states whether it was measured on this device, only reported, or exceeds what this device has - so Fast and Quality read as guidance rather than as a promise. Step 3 turns each capability into its dependency plan and does not let one be skipped. Step 4 states every action, size, licence and checksum before anything is fetched, lists the permissions and data locations, and confirms in words what would have been unavailable had the install failed. Step 5 ships one capability failing: semantic knowledge is unavailable because the embedding model installed but no corpus path is configured, reported rather than hidden. Built pairing against section 8 as a dialog over a dimmed Control Center, since that is where it is reached from. It shows the short-lived single-use code, the two identities side by side so a person can compare fingerprints, a what-pairing-does list where the three things it does not do carry as much weight as the three it does, and node-04's advertised capabilities separated from what has actually been observed. Wired the four Control Center buttons - Change setup, Re-run self-test, Pair a device, Review and pair - which previously led nowhere.
- verification: Swept every text-bearing element on all seven application pages in three theme states at a 1440 by 900 viewport, 3,054 element checks in total: zero failures, worst ratio 4.53:1, which is the same --text-dim on --surface pair everywhere. Confirmed zero horizontal overflow on all seven at 375, 768, 1024 and 1440. Two contrast defects surfaced and were fixed: --st-unknown measured 4.43:1 on the light sunken ground, and --text-faint, which passes on --surface, fell to 4.06:1 on --surface-raised, which is what the model cards and the pairing identity cards sit on - the token was darkened and the two selectors moved up to --text-dim.
- remaining: Onboarding step 4 is drawn in its confirmed state, so there is no progress or failure view for a download that stalls. Pairing is drawn at step 3 of 5; revoke is offered from the Control Center but its confirmation is not drawn. All seven pages remain static references carrying sample data only - no figure is a measurement and the pairing code is not a credential - and none is wired to the contract in backend/contracts/v1.py. Fonts still load from Google Fonts and must be self-hosted before any offline build. Screen readers, keyboard traversal order and other browsers are unverified. A collapsed preview pane reports clientWidth 0, which makes an overflow check read as hundreds of pixels on a page that has none; overflow numbers are only trustworthy at an explicit viewport. No Git writes ran.

<a id="ac-20260903-018"></a>
## AC-20260903-018 — Retheme the application surfaces: silver, sky blue, black, scarce green, purple, and selective curves
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-001](userprompts.md#up-20260903-001)
- related_prompts: none
- tags: ui, application-surfaces, palette, tokens, geometry, accessibility
- aliases: chatbot ui retheme, silver sky blue black, purple agent provenance, radius scale, curved edges, brand silver
- paths: frontend/design/tokens.css, frontend/design/app.css, frontend/design/chat.css, frontend/design/documents.css, frontend/design/code.css, frontend/design/control.css, frontend/design/onboarding.css, frontend/design/pairing.css, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Rebuilt the application palette around a near-black ground with silver type, sky blue, one green and one purple, and introduced a radius scale that curves what you touch while leaving readouts square. The public site was deliberately not touched.
- changes: Rebuilt tokens.css in both themes. Dark went to a near-black cool ground with silver type tiers; light went from warm grey-green to cool silver daylight. Sky blue replaced amber as --signal, so the live accent, focus ring, selection and running state all read blue. Green was pulled back to --st-enforced plus the completed marks on a plan, pipeline or job lifecycle, and nothing else. Added --agent and --agent-soft in purple with a single job: provenance, meaning this came from the local model's own reasoning. It marks the plan's left rail in Chat and the capability that ran each step in Chat and in the Documents pipeline, and it is never used for status - which is exactly why it cannot be confused with enforced, observed or unavailable. The node a step ran on stays silver, because that is routing, not authorship. --brand moved from orange to silver so the Rokunin mark sits inside the palette; it remains its own token used in two places, so recolouring the mark is a one-line change. Added a radius scale where none was used before - --radius had been declared and never applied, so every surface was square by omission. One rule decides where it lands: things you touch or talk to curve, things you read as a measurement stay square. Buttons, chips, bubbles, the composer, nav items, cards, panels and dialogs curve; dense claim tables, diffs, run output, meters and the artifact document do not, and --radius-data exists at 0px to make that deliberate rather than accidental. Where a curved container holds square rows the container carries the radius with overflow hidden, so a panel stops looking like a spreadsheet without the data losing its grid. Nav items became inset pills whose active marker is an inset box-shadow rather than a border-left, because a 2px border on a rounded box bows around the corner instead of reading as a straight bar. A chat turn now tightens the corner on the side it is anchored to. Corrected two colour misuses found while applying the rule: the pairing terms list marked what pairing does in green and what it does not do in fault red, so four rows that exist to reassure the reader were painted as errors - they are now the live accent and silver. The Code diff keeps conventional green and red for added and removed lines, and that exception is written into tokens.css rather than left as a silent contradiction.
- verification: Swept all seven application pages in three theme states at 1440 by 900, 3,054 element checks: zero contrast failures. The floor rose from 4.53:1 to 4.74:1 rather than costing contrast, because the new grounds are darker in dark and cooler in light while the type tiers held; Control Center, onboarding and pairing measure 5.01:1 and the install page 5.20:1. The purple was checked before it was used - 6.98:1 dark and 5.92:1 light on the grounds it lands on, at 10px where the 4.5:1 threshold applies with no large-text exemption. Confirmed zero horizontal overflow on all seven at 375, 768, 1024 and 1440, which the nav pill margin change could have broken and did not. Confirmed the pairing markers resolve to sky blue and silver rather than green and red. Confirmed site.html links only site.css and that site.css carries its own token block, so the public site is untouched by the retheme.
- remaining: The four earlier token contrast fixes are now structural rather than patched, but --text-faint on --surface-raised remains the tightest pair in the system and is the first thing to re-measure if surfaces are lightened again. The retheme is colour and geometry only: no page gained or lost content, and all seven remain static references carrying sample data, wired to nothing. Fonts still load from Google Fonts and must be self-hosted before any offline build. Screen readers, keyboard traversal order and other browsers are unverified. No Git writes ran.

<a id="ac-20260903-019"></a>
## AC-20260903-019 — Glassmorphism and deeper curves across the application surfaces
- date: 2026-09-03
- agent: Claude
- status: verified
- prompt_id: [UP-20260903-001](userprompts.md#up-20260903-001)
- related_prompts: none
- tags: ui, application-surfaces, glassmorphism, geometry, tokens, accessibility, tooling
- aliases: glass morphism chatbot ui, oval curves, atmosphere fields, backdrop-filter, compositing contrast audit, scrim modal
- paths: frontend/design/tokens.css, frontend/design/app.css, frontend/design/chat.css, frontend/design/documents.css, frontend/design/code.css, frontend/design/control.css, frontend/design/onboarding.css, frontend/design/pairing.css, frontend/design/README.md, agent-memory/agentchangelog.md
- summary: Added a glass system to the application surfaces and enlarged the radius scale toward oval, keeping verbatim output and documents opaque and square. Rewrote the contrast auditor to composite translucent layers, which found two failures the previous one structurally could not see. The public site was again left untouched.
- changes: Enlarged the radius scale - 26px for dialogs and the largest panels, 18px for panels and cards, 13px for buttons and containers, 9px for nav items and tags, and a dedicated 20px for a chat turn, which is now the most oval thing in the app and tightens the corner on the side it is anchored to. Added a glass system. Glass only reads as glass when there is something behind it worth blurring, so the app now sits on three soft radial fields over the flat ground; without them every panel is flat translucent grey. The same distinction that governs curves governs glass: glass on the frame and on containers, opaque on verbatim output and on documents. The nav, rail, header, composer, panels, cards and dialogs are glass; the diff, the stdout and stderr panes, the meters, the artifact and the Proof Card are not, because those are read literally and refracted ground behind 11px monospace costs legibility for nothing. Two tiers for cost rather than looks: glass tokens carry the backdrop blur and belong to top-level surfaces, veil tokens are fill only for containers already sitting on a blurred parent, because blurring an already-blurred surface is expensive and shows almost nothing with a dozen panels on screen. Two structural changes were forced. The gap-of-1px-over-an-opaque-parent divider trick, used for the Documents sources and the onboarding plan totals, needs that parent opaque, which blocks everything behind it - both became separated cards with real gaps, which reads better anyway. And the light-mode atmosphere had to be rebuilt: dark tints at 10 percent over a light ground darken it, costing contrast for dark text, so the light fields are now near-white pastels that lift, and the light ground was deepened to D2D9E4 because near-white glass on a near-white ground collapses into a single tone and the panels stopped reading as panels.
- verification: Rewrote the contrast auditor, because glass broke the old one in a way that would have hidden failures rather than reported them: it walked up the ancestor chain until it found a background with alpha above .55 and used that, and with glass that colour is never what is on screen. The new auditor alpha-composites every layer from the root down including the strongest rgba stop of each gradient, and computes each ratio twice - once with gradient layers and once without, taking the lower - because a white-ish overlay lowers contrast for light text and raises it for dark text, so neither case is universally the worst. That found two genuine failures. The pairing dialog measured 3.48:1 in light, where a .55 white modal over a 62 percent black scrim composites to a muddy mid-tone; --glass-modal and --scrim are now their own tokens and it measures 6.33:1. The unavailable hatch measured 4.46:1 where --text-faint crosses --line-soft, which the old walk never saw because it stopped at the opaque row beneath; --line-soft was lightened in light so the hatch reads as a drawing mark rather than a bar. After both fixes: all seven pages, three theme states, 3,054 element checks, zero failures, floor 4.60:1. Confirmed zero horizontal overflow on all seven at 375, 768, 1024 and 1440, which the two layout changes could have broken and did not. Confirmed at runtime that none of the new tokens - glass-base, scrim, radius-bubble - resolve on site.html and that its ground is unchanged at rgb(9,9,10), so the public site is untouched.
- remaining: The glass floor of 4.60:1 is slightly below the 4.74:1 the palette pass reached; that is the honest number under a strictly compositing measurement rather than a regression in the design. backdrop-filter is applied to top-level surfaces only, but no frame-rate measurement was taken - the preview pane starves animation frames, so glass performance on a low-end GPU is unverified and is the first thing to check on real hardware. Browsers without backdrop-filter degrade to the flat translucent fill, which is legible but not glass; this was not tested anywhere but Chromium. All seven pages remain static references carrying sample data, wired to nothing. Fonts still load from Google Fonts. No Git writes ran.
