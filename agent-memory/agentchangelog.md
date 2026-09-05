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
