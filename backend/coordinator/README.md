# Coordinator — C03 local application

The smallest usable local application: a Python coordinator that owns canonical
state in SQLite, runs one real local inference through Ollama, streams it to a
browser UI, and survives a restart without losing or inventing history.

## Run it

```bash
cd /Users/adityatadge/Documents/GitHub/AegisForge
PYTHONPATH=. ./.venv/bin/python -m backend.coordinator
```

Then open <http://127.0.0.1:8770>. `--port` and `--state` override the defaults.
State lives at `~/.aegisforge/coordinator.sqlite3`, outside the repository.

Requires the local Ollama server on `127.0.0.1:11434` with
`qwen3.5:4b-q4_K_M` installed. If it is not running the Control Center reports
the runtime as unreachable and Chat fails the job with a typed `unavailable`
reason — it never fabricates a reply.

Chat allows up to **2,048 output tokens** per reply (formerly 512), with thinking
off and a 4,096-token context. `NUM_PREDICT` in `runtime.py` sets the reply limit;
restart the coordinator after changing it. Longer output can take longer to
generate. This is a maximum, not a promised answer length or a larger memory of
the conversation. No new model download is involved.

## Why the standard library

`backend/requirements.txt` pins pydantic and nothing else. FastAPI and uvicorn
are **not installed**, and installing them is a setup checkpoint rather than C03
implementation, so the coordinator uses `http.server`, `sqlite3` and `urllib`.
FastAPI remains the recorded direction for the **worker API at C04**, where a
pinned dependency install is already part of the image build. Revisit this for
the coordinator only if a measured need appears.

## Layout

| File | Responsibility |
|---|---|
| `db.py` | SQLite schema and every write, each validated through `backend.contracts.v1` first |
| `runtime.py` | Ollama adapter; bounded settings from the model catalogue |
| `server.py` | HTTP API, SSE stream, static UI; binds `127.0.0.1` only |
| `test_coordinator.py` | 25 offline checks — no external network or model calls |

`frontend/app/` holds the UI: `index.html` (Chat), `control.html` (Control
Center), `app.css` derived from the design tokens, `overrides.css` for
application-owned additions, and `app.js`. Model output is rendered as Markdown
built from DOM nodes — never `innerHTML` — so model text cannot inject markup.

## Contract binding

This is a real contract consumer, not a parallel schema. `Job`, `Attempt` and
`Event` records are constructed and validated **before** anything is written, and
state changes go through `v1.require_transition`, so an illegal transition raises
instead of reaching the database. The contract remains a **reviewed draft, not
frozen**; its integration gate is C05, not this chunk.

Port `8770` avoids the contract's worker ports (`8443`, `30443`) and the Jenkins
service observed on the Ubuntu worker's `8080`.

## Conversation management

| Action | Behaviour |
|---|---|
| Rename | Title only. Messages and the chat ID never change. Trimmed, non-empty, 120 characters — the same rule as creation. |
| Search | Literal, case-insensitive, over titles **and** message text, covering every saved chat rather than the sidebar's first page. `%` and `_` are escaped, so searching `100%` matches one chat rather than all of them. Parameterised queries; snippets rendered as text. |
| Drafts | One unsent draft per conversation, plus a slot for text typed before a chat exists. Stored in coordinator state so it survives a refresh or restart. **Never sent to the model, never searched, never exported.** Submitting clears only the version that was sent, so newer typing survives; a failed send keeps it. Deleting a chat clears its draft, and a delayed save cannot resurrect a deleted chat. |
| Pin | Ordering only — pinned chats sort first, most-recent-activity within each group. Unpinning preserves every message. Shown with a mark, not colour alone. |
| Export | An explicit local download of the **saved snapshot**: complete history, not what the interface happened to show. Markdown preserves the model's formatting; plain text stays literal. Partial and context-limited replies carry a readable note. Unsent drafts and other chats are excluded, filenames are sanitised, and nothing is mutated or fetched. |
| Delete | Removes the chat with its messages, jobs, attempts, events and draft. Confirmed by title, with Cancel focused. |

**Regenerate is deliberately absent.** Continue extends a saved partial reply; it
never overwrites or re-runs an earlier answer. No editing or branching.

## Truthful state

The offline-runtime invariant and `docs/security.md` §12 shape the surfaces:

- Documents and Code render **unavailable**; they are implemented at C08 and C09.
- Workers, cluster, approvals, Proof Cards and egress evidence render
  **unavailable**, each naming the chunk that produces its evidence.
- A missing measurement renders hatched as unavailable — never as a default,
  never as healthy.
- An empty model response is a **failure**, not a successful blank reply.
- A cancelled job writes no assistant message.
- Only the runtime's `stop` reason permits successful completion. `length`
  marks the job **failed** with a visible **Incomplete reply** notice; its
  partial text stays in the conversation and can be continued in the next turn.
  Missing or unexpected reasons fail validation rather than claiming success.
- The attempt records the actual stopping reason, output token count and limit.
  Existing databases receive one nullable metadata column at startup; old
  stopping reasons remain **not recorded**, and history is preserved.

## Stopping it

Ctrl+C stops the coordinator immediately, even with browser tabs holding SSE
connections open. That needs saying because the first build hung: the SSE
handler ran `while True` with a 15-second wait and had no exit path, so
`server_close()` waited on a thread that never returned. The loop now watches a
`stopping` event with a one-second poll, and `block_on_close` is disabled as
well. Verified by sending SIGINT with two SSE connections held open — it exits
in under a second and prints `stopping` then `stopped`.

The node ID is persisted beside the workspace ID. Local API requests require a
local Host and same Origin when present; bodies use the shared contract limit.
Ollama calls ignore proxy settings and reject redirects, so prompts stay on the
loopback runtime path.

Browser resets and broken pipes close that browser connection quietly. The
generation job continues independently; other server errors still surface.

## Restart reconciliation

A restart cannot leave a job claiming to be running. On startup, every attempt
still in `queued`, `running` or `validating` becomes `interrupted` with one typed
reason, its job follows, and the events are appended to the same sequence.
Partial output and conversation history are preserved. The startup banner prints
the number of jobs repaired.

`internal_error` is the closest available `Failure` code for a coordinator
restart; the contract has no dedicated one. The message says exactly what
happened.

## What this chunk does not do

No worker, no pairing, no cluster, no Documents or Code workflow, no approvals,
no Proof Cards, and no egress evidence. The browser making no external request
is a property of these pages — it is **not** zero-egress proof, which needs the
network controls and independent observation at C11.
