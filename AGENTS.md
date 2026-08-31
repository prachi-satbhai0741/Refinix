# AegisForge Agent Instructions

Repository-wide rules defining what every coding agent must and must not do in
AegisForge.

## Authority and reporting

Order when context conflicts:

1. The current user request — defines the task and the permissions.
2. This file.
3. [`docs/prd.md`](docs/prd.md) — product requirements *(review draft, not a v1 baseline)*.
4. [`CONTRIBUTING.md`](CONTRIBUTING.md) — branch and merge flow.
5. Current source, tests, and observed command output.
6. [`agent-memory/`](agent-memory/README.md) — historical index only.

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
- Fix root causes in the shared path after checking all callers. Never change
  behavior silently.
- Do not run tests, installers, migrations, deployments, model downloads, or
  live-environment commands without permission — give the exact command instead.
- Add the smallest runnable check for non-trivial logic and run proportionate
  validation before reporting.

## AegisForge invariants

From `docs/prd.md`; do not weaken without an approved decision.

- Runtime operation must not require Internet access: no cloud inference,
  telemetry, analytics, or silent network calls in the offline runtime. Local
  runtimes bind to loopback; workers expose the minimum LAN surface (16.2, 16.3).
- Workers write only inside assigned temporary workspaces, rejecting path
  traversal and symlink escape. Sandboxed execution has networking disabled by
  default with bounded CPU, memory, runtime, and filesystem (15.2, 16.6).
- Never commit model weights, installers or release binaries, signing keys or
  tokens, private documents, real confidential scans, local chat databases, or
  environment files with secrets (15.3).
- Record model source, licence, file hash, runtime, and version. Treat model
  names, licences, compatibility, and benchmarks as unverified until evidence is
  recorded (16.4, 17.3).
- Do not claim a benchmark that is not reproducible from repository
  instructions. Label features planned, prototyped, verified, or deferred (17.3).

## Completion report

Lead with the outcome, then what changed or why nothing did. State changed paths,
the verification actually run, and any remaining blocker or unverified external
gate. Distinguish implementation from verification. Do not claim deployment,
model quality, security, zero-egress, or hardware compatibility from static code
alone.
