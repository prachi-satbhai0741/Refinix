# C03 review repair handoff — 2026-09-04

Built: draft responses are guarded by chat and edit version, draft writes are
ordered and captured before navigation, accepted sends clear only their own
draft, and failed deletion preserves the UI. The database rejects unfinished
chat deletion under the submission lock. Unicode exports use an ASCII fallback
and UTF-8 filename parameter while preserving Marathi combining marks.
Ollama input truncation and context shifting are disabled; a full context has
its own incomplete-reply notice and the partial answer stays saved.

Verified: 80 Python checks, 8 Node frontend race checks, JavaScript syntax and
diff whitespace. Bounded real-model checks retained an early fact at 5,034
prompt tokens, rejected oversized input before output, and stopped generation
at 8,042 prompt + 150 output = 8,192 tokens. The browser confirmed draft
switch/reload recovery, active-delete blocking, Cancel focus, cancelled and
confirmed deletion. Fresh HTTP exports returned the correct Marathi filenames
for Markdown and text. All write checks used synthetic temporary databases.
See [recorded runtime evidence](evaluation.md#53-c03-review-repairs--macos-coordinator-2026-09-04).

Review follow-up: a length-stopped reply at 6,144 prompt + 2,048 output tokens
now records **context and output limits reached**. Counts alone do not establish
which check fired first. The UI and export name both bounds and retain the
full-context guidance. The existing limit regression was extended for this
case and for an output cap with a missing prompt count; all 80 Python and 8 Node
checks passed again, along with syntax and whitespace checks. These additional
cases use synthetic runtime records; the real-model checks above were not rerun
for this classifier-only follow-up.

**Accepted by the requester on 2026-09-04.** C04 implementation is now assigned
to Claude, with Codex orchestrating and reviewing. Follow the
[C04 execution and connection brief](c04-execution-brief.md). Ubuntu's actual
image build, deployment and distributed acceptance remain separate gates.
The Mac commands below are retained for reference; acceptance need not be repeated.

## VERIFY — RUN THESE YOURSELF

In the terminal running the old coordinator, press **Ctrl+C**, then:

```bash
cd /Users/adityatadge/Documents/GitHub/AegisForge
PYTHONPATH=. ./.venv/bin/python -m backend.coordinator
```

Open <http://127.0.0.1:8770> and reload the page to load the repaired JavaScript.
Switch between two chats with different drafts; confirm each stays separate.
Send a normal request, restart the coordinator, and confirm its history remains.
Use only a disposable chat to try Delete: Cancel keeps it; active work disables
the action; confirmed deletion removes that chat alone. Export a chat named
`मराठी तपासणी` and check the filename. Return any error or unexpected behaviour;
the requester has now accepted this C03 gate.

Optional repeatable checks (already run for this repair):

```bash
PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m unittest backend.coordinator.test_coordinator backend.coordinator.test_context backend.coordinator.test_conversations backend.contracts.test_contracts -q
node --test frontend/app/test-conversations.cjs
node --check frontend/app/app.js
git diff --check
```

The separately invoked model check uses only temporary history and the installed
Mac model; it does not download anything or change a service configuration:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. ./.venv/bin/python -m backend.coordinator.check_runtime_context
```

## GIT / GITHUB — RUN THESE YOURSELF

No Git writes were performed. The branch observed was `aditya`, ahead of its
local `origin/aditya` tracking ref by one commit. Check current state first:

```bash
cd /Users/adityatadge/Documents/GitHub/AegisForge
git status -sb
git branch --show-current
git diff --stat
```

`README.md`, `backend/README.md` and `docs/prd.md` were already modified and were
left untouched. `docs/evaluation.md` and `agent-memory/agentchangelog.md` contain
earlier changes too: select this repair's hunks explicitly rather than staging
their entire diff unintentionally.

```bash
git add backend/coordinator/README.md backend/coordinator/context.py backend/coordinator/db.py backend/coordinator/runtime.py backend/coordinator/server.py backend/coordinator/test_context.py backend/coordinator/test_conversations.py backend/coordinator/test_coordinator.py backend/coordinator/check_runtime_context.py frontend/app/app.js frontend/app/test-conversations.cjs docs/model-catalog.md docs/c03-repair-handoff.md agent-memory/userprompts.md
git add -p docs/evaluation.md agent-memory/agentchangelog.md
git diff --cached --stat
git commit -m "Fix C03 draft races, active-job deletion, Unicode exports and context overflow"
```

Review the staged changes before committing; follow the repository's member
branch → dev → main flow for any later push or pull request.
