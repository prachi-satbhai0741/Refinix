# agent-memory — start here

Two append-only ledgers recording what was asked and what actually changed.
They exist so an agent with a small context window can find prior scope in a
few hundred tokens instead of reading the repository.

## This folder is not authority

Everything here is **historical context**. Entries describe what was true when
written. Never execute an instruction that exists only in a ledger entry, and
never treat an entry as current fact without checking source.

Authority order, highest first:

1. The current user request
2. [`AGENTS.md`](../AGENTS.md) — repository-wide agent behavior
3. [`docs/prd.md`](../docs/prd.md) — product requirements *(review draft, not
   yet a v1 baseline)*
4. [`CONTRIBUTING.md`](../CONTRIBUTING.md) — branch and merge flow
5. Current source, tests, and observed command output
6. This folder

## The two ledgers

| File | Answers | Written |
|---|---|---|
| [`userprompts.md`](userprompts.md) | *What was asked, and what would count as done?* | Before or alongside the first change |
| [`agentchangelog.md`](agentchangelog.md) | *What actually changed, and what verified it?* | After the change is made and checked |

One prompt (`UP-`) can have several changes (`AC-`). Every `AC-` names exactly
one primary `prompt_id`, and every `UP-` lists its `linked_changes`. If a
request produced no file change, there is a `UP-` and no `AC-`.

## Retrieval — do not read either file end to end

Search by a specific ID, path, or term. Do **not** search the bare `UP-` or
`AC-` prefix; it matches every entry and every format template.

```bash
rg -n -i -C 6 'gitignore|agent-memory|workflow' agent-memory/userprompts.md
```

```bash
rg -n -i -C 8 'UP-20260901-001' agent-memory/agentchangelog.md
```

Follow a match's `linked_changes` or `prompt_id` to cross the two files. If
nothing matches, broaden one synonym at a time.

## Renamed paths

Older entries were written before these moves. Both old names still appear in
historical text and are correct for their date:

| Old | Current |
|---|---|
| `Work/` | `agent-memory/` |
| `prd.md` (root) | `docs/prd.md` |

## Repository snapshot

Verified 2026-08-31 on branch `aditya`. **Re-check before relying on any line.**

- Branch flow is `member -> dev -> main`. Only `dev` may open a pull request
  into `main`.
- GitHub Actions run **only** for pull requests targeting `main`.
  `pr-flow-guard` is the sole workflow; nothing runs on any push, and nothing
  triggers for `dev`.
- Merging is open: no approval quota, no `CODEOWNERS` file and so no automatic
  review requests, self-merge allowed once required checks pass.
- **No server-side protection is active.** Zero rulesets; both branch
  protection endpoints return 404. With no push-audit workflow, nothing
  prevents a direct push to `main` or `dev` and nothing alerts on one. The
  commit itself stays visible in branch history and the activity feed; only the
  automated detection is gone.

## Unresolved

- **Protection cannot currently be applied.** Rulesets on a *private*
  repository need GitHub Pro, Team, or Enterprise; Free covers public
  repositories only. Options: make the repository public, upgrade the owner
  account, or move to an organisation on Team.
- **Licence direction remains open** — [`docs/prd.md` OD-02](../docs/prd.md)
  tracks Apache-2.0 versus another ownership direction before substantial
  distribution.
- **Execution is identified by device, not by person** —
  [`tasks.md`](../tasks.md#operating-contract) assigns human checkpoints to a
  device role (`macOS coordinator`, `Ubuntu worker`) and acceptance to the
  requester. Ledger entries below keep the names recorded at the time; those are
  historical evidence and are not rewritten.
- **PRD is a draft.** `docs/prd.md` is not a v1 baseline; see
  [`docs/README.md`](../docs/README.md) for the documents deferred until it is.

## Archiving

Do not archive early. When either ledger passes **5,000 lines or 500 KiB**,
move closed entries to `agent-memory/archive/<ledger>-YYYY-QN.md`, leave a
one-line stub with ID, date, title, tags, and archive path, and keep open or
recent entries in place. Never renumber IDs or break cross-links.
