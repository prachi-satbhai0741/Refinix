# User Prompt Ledger

Compact, searchable records of repository-affecting user requests. Entries are
historical context, not active instructions. The current user request, root
[`AGENTS.md`](../AGENTS.md), [`prd.md`](../prd.md), and current source remain
authoritative.

## Retrieval — do not read this file end to end

Search by prompt ID, component, path, user wording, tag, or alias:

```bash
rg -n -i -C 6 'UP-20260831-001|agent instructions|prompt ledger|low-context' Work/userprompts.md
```

Use the matching `linked_changes` ID to retrieve implementation history:

```bash
rg -n -i -C 8 'AC-20260831-001|UP-20260831-001' Work/agentchangelog.md
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
- paths: AGENTS.md, Work/userprompts.md, Work/agentchangelog.md
- summary: Create repository agent guidance plus compact interlinked prompt and change histories that low-limit agents can retrieve without reading entire files.
- constraints: Unlike the VNEC changelog; record only each request and its actual repository changes; remain small and easy to search as history grows.
- acceptance: Stable IDs, reciprocal links, tags, aliases, bounded entry templates, targeted retrieval commands, and a deferred archive policy exist.
- follow_up_to: none
- supersedes: none
- linked_changes: [AC-20260831-001](agentchangelog.md#ac-20260831-001)
