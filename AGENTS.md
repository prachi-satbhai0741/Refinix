# Refinix Agent Instructions

Repository-wide rules defining what every coding agent must and must not do in
Refinix (repository name: refinix; formerly AegisForge).

## Authority and reporting

Order when context conflicts:

1. The current user request — defines the task and the permissions.
2. This file.
3. [`docs/prd.md`](docs/prd.md) — product scope *(review draft, not a v1 baseline)*.
4. The focused document linked by the PRD for architecture, workflow, security,
   models, hardware, or evaluation detail.
5. [`CONTRIBUTING.md`](CONTRIBUTING.md) — branch and merge flow.
6. Current source, tests, and observed command output.
7. [`agent-memory/`](agent-memory/README.md) — historical index only.

Report unresolved conflicts; never invent product behavior. Agents advise: raise
an ordinary concern once, then drop it and proceed. Security, privacy,
destructive-operation, and data-loss risks stay blockers until resolved.

**Never claim a check passed, or work is complete, unless you ran it and saw it
pass.** Another agent's summary is not evidence. Requester verification is the
final completion gate.

## Git

Agents may run only these read-only commands:

```text
git status    git diff    git log    git show    git check-ignore
git branch --list    git branch --show-current    git rev-parse    git ls-files
```

**Never run Git or GitHub writes** without explicit authorization in the current
message: `add` (including `git add -A` and `git add .`), `commit`, `push`,
`pull`, `fetch`, `merge`, `rebase`, `reset`, `restore`, `stash`, `clean`,
`checkout`, `switch`, `tag`, `git mv`, `git rm`, branch or ref mutation, or any
GitHub write — opening, editing, closing, or merging pull requests, or changing
settings, collaborators, rulesets, or Actions. - unless user explicitly asks for git run

"Finish", "complete", and "execute" are not authorization; neither is an earlier
message in the session.

Never push directly to `dev` or `main`; follow member branch → `dev` → `main`.
Preserve unrelated and user-owned changes in a dirty tree — never reconstruct a
file from `HEAD` or discard a modification you did not make.

Hand off under these headings, giving the repository directory, `git status -sb`,
**exact `git add` paths** — never `-A` — and a commit message matching the final
diff. If the branch is uncertain, include `git branch --show-current` rather than
guessing.

```text
GIT / GITHUB — RUN THESE YOURSELF
VERIFY — RUN THESE YOURSELF
```

## Before repository work

1. Run `git status --short --branch`. Preserve unrelated changes.
2. Read only the relevant PRD and contributing sections.
3. Search the ledgers with 2–5 task terms, likely paths, or a specific ID. Never
   search the bare `UP-`/`AC-` prefix; it matches every entry.

   ```bash
   rg -n -i -C 6 'term-a|term-b|likely/path' agent-memory/userprompts.md agent-memory/agentchangelog.md
   ```

4. Read the matching entry and a little context — not whole files.
5. Inspect the real callers, routes, tests, or documents the task touches.

## Agent memory

[`agent-memory/README.md`](agent-memory/README.md) covers retrieval, the two
ledgers, and archiving. Writing rules:

- Log repository-affecting requests in `agent-memory/userprompts.md` as
  `UP-YYYYMMDD-NNN`, appended before or alongside the first change. Skip
  greetings, status questions, and unrelated conversation.
- After changes are made and verified, append `AC-YYYYMMDD-NNN` to
  `agent-memory/agentchangelog.md` linking exactly one primary `prompt_id`. No
  repository file changed means no changelog entry.
- Date entries the day they are actually written. Every entry needs a stable ID,
  ISO date, lowercase `tags`, search `aliases`, repo-relative `paths`, a
  one-sentence `summary`, and short bullets. Prompts stay under ~25 lines,
  changelog entries under ~20.
- Record only what changed and what verification was observed — no diffs, long
  logs, hidden reasoning, future plans, or feature tours.
- On material scope change open a new ID and link `supersedes` or `follow_up_to`.
  Never silently rewrite a past entry, renumber IDs, or break cross-links.
- Never store secrets, credentials, private documents, real confidential data,
  or chain-of-thought. Keep entries in the same change as the work they describe.

## Implementation

- Make the smallest safe diff. Prefer deletion, reuse, and existing dependencies;
  avoid unrelated refactors and speculative abstractions.
- Build prototypes by adapting suitable local/offline open-source libraries and
  codebases before writing commodity functionality from scratch. Reuse only
  when the licence permits it; record the source, pinned version or commit,
  licence, and material local changes, and reject unlicensed, incompatible,
  cloud-dependent, or silently networked code.
- Fix root causes in the shared path after checking all callers. Never change
  behavior silently.
- Do not run tests, installers, migrations, deployments, model downloads, or
  live-environment commands without permission — give the exact command instead.
- Add the smallest runnable check for non-trivial logic and run proportionate
  validation before reporting.

## Human checkpoints

- Agents should follow the authorised chunk and device-based human checkpoints
  in [tasks.md](tasks.md#numbered-execution-tasks). Anyone may implement any
  module; a device named for a setup action is not an exclusive code owner.
- Build, review and fix within the authorised scope without repeated permission
  requests for ordinary coding. Resolve routine implementation questions from
  repository evidence, the established requirements and authoritative upstream
  documentation rather than relaying them as checkpoints; the scope also covers
  review fixes and proportionate offline checks on existing dependencies and
  isolated test data. Stop at a required human action or missing permission —
  repository evidence answers technical questions but never grants permission —
  and do not skip to another chunk or perform that action by assumption.
- Before stopping, prepare a reviewable handoff identifying the **device role**
  — for example `macOS coordinator` or `Ubuntu worker` — rather than a team
  member, with its OS, architecture, shell, actual directory, exact commands or
  UI steps, expected results and evidence to return. Downloads need approved
  sources, versions, licences, integrity and storage requirements; host changes
  need applicable rollback instructions.
- If required values or artifacts do not exist yet, request the concrete
  decision or prerequisite first. Do not provide speculative setup commands.
- Resume only after that device reports back and the relevant result is verified
  with permitted checks. A review pass or an install report alone does not prove
  the runtime acceptance gate or authorise a later chunk.
- Keep checks proportional to the changed behavior and required gates. After
  each build and review cycle, explain **Built**, **Verified**, and **Next / Human
  action** in plain language with an example, limitations and the actual device
  names.

## AegisForge invariants

From [`docs/prd.md`](docs/prd.md) and
[`docs/security.md`](docs/security.md); do not weaken without an approved
decision.

- Runtime operation must not require Internet access: no cloud inference,
  telemetry, analytics, or silent network calls in the offline runtime. Local
  runtimes bind to loopback; workers expose the minimum authenticated LAN
  surface.
- Workers write only inside assigned temporary workspaces, rejecting path
  traversal and symlink escape. Sandboxed execution has networking disabled by
  default with bounded CPU, memory, runtime, process, and filesystem access.
- Never commit model weights, installers or release binaries, signing keys or
  tokens, private documents, real confidential scans, local chat databases, or
  environment files with secrets
  ([repository content](docs/security.md#11-repository-content)).
- Record model source, licence, file hash, runtime, and version. Treat model
  names, licences, compatibility, and benchmarks as unverified until evidence is
  recorded in the [model catalogue](docs/model-catalog.md) and
  [evaluation evidence](docs/evaluation.md#1-evidence-labels).
- Do not claim a benchmark that is not reproducible from repository
  instructions. Label features planned, prototyped, verified, deferred, or
  rejected.

## Completion report

Lead with the outcome, then what changed or why nothing did. State changed paths,
the verification actually run, and any remaining blocker or unverified external
gate. Distinguish implementation from verification. Do not claim deployment,
model quality, security, zero-egress, or hardware compatibility from static code
alone.
