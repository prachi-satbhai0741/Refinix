# Claude build update — C03 context handling and interface polish

Execute this C03 follow-up in `/Users/adityatadge/Documents/GitHub/AegisForge`.
Deliver the working changes, fixtures, observed checks and a reviewable handoff
for Codex. Resolve routine choices from the repository and upstream evidence;
ask only for a genuinely missing input, permission or required device action.

Keep C01/C02 accepted, the two-device plan and every existing C03 repair. C04
still follows requester acceptance of the Mac app. The internal demonstration
is 8–9 September 2026: prioritise context correctness, readable output and
reliable interaction; report what will not fit without dropping evidence gates.

## 1. Baseline and findings to address

Codex inspected the live Chat and Control Center at port 8770 and their source
on 2026-09-04. The observed problems are:

- Chat uses 13px body text and 10–11px metadata. The narrow, always-visible
  diagnostics rail competes with the answer; long values wrap awkwardly.
- Control Center spreads short labels and long, right-aligned values far apart.
  It presents raw settings and byte counts with little grouping or explanation.
- The Markdown renderer handles only a small subset. Headings become bold
  paragraphs; italics, links, fenced code, tables and nested lists lack proper
  rendering. This is a rendering problem, not just a colour problem.
- Active navigation is inconsistent: CSS expects `aria-current`, while the
  application uses `is-active`. The navigation marker's `margin-left: auto`
  also pushes the icon/letter and label toward the right.
- Below 1180px the rail disappears; below 760px navigation disappears. Neither
  has a replacement control. Important information becomes inaccessible.
- Streaming forces the thread to the bottom. The composer clears text before
  submission succeeds, and errors are inserted as assistant replies. Sending
  while another reply is active can lose a draft and produce a rejection.

The running port-8770 process still reported `num_predict: 512`; the current
source specifies 2048. Start an isolated instance from current source before
comparing behavior. Do not interpret old records with missing metrics as fresh
failures, or change the user's existing process/history without coordination.

Read `AGENTS.md`, the focused PRD/architecture/workflow sections, the C03 row in
`tasks.md`, and the current dirty tree before editing. Primary implementation:
`backend/coordinator/{runtime,server,db,test_coordinator}.py` and
`frontend/app/{index.html,control.html,app.js,app.css,overrides.css}`.

## 2. Context window: control what the model actually receives

The saved conversation and the model's active context are different things.
Keep the complete original conversation in SQLite. Select a bounded request
from it without rewriting or deleting historical messages.
Explicit confirmed **Delete chat**, specified below, is a separate user action.

- Keep the newest user message intact. Preserve applicable system/policy
  instructions. Remove older complete exchanges when necessary; avoid leaving
  an orphan assistant reply. If the newest input cannot fit, explain that it
  must be shortened or split instead of silently chopping it.
- Record the selection for each attempt: included/omitted message identities
  or ranges, configured context, output allowance, estimated input size and
  counting method, plus runtime-reported prompt and output counts when present.
  Reopening a job must show the policy that ran then, not today's settings.
- Show a small persistent notice beside the affected reply, for example:
  **“6 earlier messages were left out of this reply. They remain in your chat.”**
  An expandable detail explains the selection. Do not call omission
  “compaction” or suggest omitted facts are still remembered.
- `num_predict` is an output maximum, not a reservation automatically deducted
  by our existing code. If implementing an input budget, explicitly account
  for output headroom and chat-template/system overhead. Label character-based
  estimates as estimates; `characters / 4` is not a safe token limit.
- Prefer the installed runtime's existing tokenizer/overflow controls over a
  new tokenizer dependency. The v0.32.14 source exposes `truncate` and `shift`.
  Verify their behavior on the installed model/backend, including overflow
  during generation, before relying on them. Unknown or ignored options must
  not become a claim that context is protected.
- If using retries after a verified input-overflow rejection, keep them bounded
  and observable, and only retry before any output was emitted. Do not silently
  restart a partially generated answer with different context. If reliable
  enforcement is unavailable, return an explicit limitation/error.

Retain the repaired output behavior: default maximum 2048 tokens, recorded
stop reason, incomplete notice on `length`, saved partial text usable for a
continuation, and truthful missing metrics. Do not lower the reply allowance
to 1024 simply to make the context arithmetic look better.

Expose a compact per-reply context summary and a clearer Control Center view:
configured window, output allowance, selected history, estimated input budget,
and actual prompt/output counts after execution. Use human-readable labels;
the technical names can live in details. A completed request's token count is
not a live measurement of KV-cache occupancy.

Technical references: [Ollama chat API](https://docs.ollama.com/api/chat),
[v0.32.14 request types](https://github.com/ollama/ollama/blob/v0.32.14/api/types.go),
[v0.32.14 prompt selection](https://github.com/ollama/ollama/blob/v0.32.14/server/prompt.go).

## 3. KV cache, persistence and larger contexts

Keep these concepts separate in implementation and explanation:

| Concept | What it means here |
|---|---|
| Saved history | Durable coordinator-owned conversation in SQLite |
| Active context | Selected input and generated tokens available to this inference |
| KV cache | Temporary model-runtime state that can avoid repeating attention work |
| Model residency | Loaded model resources retained by the runtime; `keep_alive` controls duration |
| Retrieval / summaries | Additional ways to choose useful historical knowledge; they are not KV-cache sharing |

Reuse Ollama's runtime behavior. Keep prompts deterministic where possible so
unnecessary prefix changes do not defeat potential reuse. Do not implement a
custom cache engine, transfer KV tensors between laptops, or pool Mac/Ubuntu
RAM/VRAM. The coordinator shares selected logical context with workers; runtimes
own their own temporary state. Cache loss must never lose saved conversations.

Retain `keep_alive: "10m"` unless measurements justify changing it. Residency
does not prove a cache hit. Show cached-token counts only if the selected
runtime actually reports a supported metric. Otherwise say **not reported**.
Do not relabel total model memory, process RSS or GPU allocation as KV-cache
size. Keep unavailable measurements out of the main chat view.

Run one bounded comparison of 4096 and 8192 context on the Mac using the same
installed model and synthetic near-boundary input. Capture prompt/output counts,
stop reason, first-token latency, generation time, model/runner memory and
available memory-pressure evidence. Include a warm follow-up and verify early
retained facts are usable. A tiny prompt with `num_ctx: 8192` is insufficient.
Use request-local settings; do not change global services or install anything.

Adopt 8192 for the Mac only if the observed result supports it; otherwise retain
4096 and finish the context guard. Record exactly what was tested. Ubuntu must
be measured before receiving that setting through its later device checkpoint;
do not block the Mac repair waiting for another machine. Cache quantization,
Flash Attention tuning, automatic summarization, semantic retrieval and new
models remain separate measured work, not prerequisites for this C03 update.
Summarization, if added later, should be triggered by need rather than assumed
to require another model call on every turn.

References: [context sizing](https://docs.ollama.com/context-length),
[residency and KV-cache settings](https://docs.ollama.com/faq).

## 4. Visual direction: a polished conversation workspace

Preserve the product identity and existing working surfaces. Make the answer
the visual focus: a restrained charcoal background, subtly separated surfaces,
clear typography and selective colour. Keep the current vanilla application;
this task does not require a framework migration.

- Use a shared centred reading column around 72–80ch, 16px body text and roughly
  1.6 line height. Give headings, paragraphs, lists and tables distinct spacing.
  Align the composer to that column and let it grow to a bounded height.
- Keep a compact sidebar with visibly selected Chat/conversation entries and
  working New conversation. Fix `aria-current` and icon/label alignment.
- Replace the permanent diagnostics wall with an accessible **Details** toggle
  or drawer. Keep the current status and important errors visible without it.
  On narrow screens provide working navigation and details controls instead of
  hiding those capabilities. Context warnings belong beside their replies.
- Use consistent grid alignment in Control Center: readable labels, left-aligned
  explanatory values, units on measurements and formatted numeric values.
  Group model/runtime, context and recent jobs; place unavailable future
  capabilities in a quiet secondary section. Never invent healthy states.
- Replace implementation-heavy default copy with plain language. Keep contract
  versions, raw endpoints, event sequences and chunk IDs in technical details.
- Maintain the existing light theme with suitable contrast while polishing the
  dark theme. Avoid introducing a new theme system or remote fonts.

Apply semantic **prose** colours, separately from operational state colours:

| Content | Treatment |
|---|---|
| Links and actual source references | Blue; recognisable as links beyond colour |
| Inline code and code accents | Green, with a subtle code background |
| Headings and selective strong emphasis | Restrained warm orange/copper |
| Ordinary prose | High-contrast neutral text |
| Warnings / failures | Amber / red with explicit words or icons |

Suggested dark starting colours: background `#111318`, raised surface `#181C24`,
text `#E6E9F0`, secondary text `#A8B0C2`, links `#78B7FF`, code `#92D5AA`,
emphasis `#E6A36C`. Verify contrast against the actual backgrounds. These are
design inputs, not measured accessibility results. Use semantic tokens so the
light equivalents remain coherent. Update colour-contract comments to reflect
the requester-approved prose treatment; green code must not imply trusted or
validated code. Do not colour arbitrary words or turn every bold phrase into
a badge. A model-written link is not automatically a verified citation.

## 5. Output formatting and interaction

Render headings, paragraphs, bold, italics, ordered/unordered/nested lists,
blockquotes, safe links, inline code, fenced code and simple tables properly.
Keep fenced code spacing and provide language labels plus a working copy
button. Tables/code may scroll within their container; the page must not gain
horizontal overflow. Preserve literal source text when copying.

Use existing code/dependencies or a small established locally bundled renderer
if appropriate. Record licence, version and integrity for new vendored assets.
Do not build an expansive Markdown parser with regexes. Disable raw HTML, block
unsafe URL schemes, and prevent automatic remote images, previews or fetches.
External navigation requires an explicit user action and clear destination.
No CDN scripts, fonts, analytics or cloud calls. Citation fixtures must not imply
the Documents retrieval workflow is implemented.

Preserve drafts on failed submission. Prevent duplicate sends for an active
conversation, support Enter/Shift+Enter and IME composition correctly, and keep
Stop usable. Show recoverable errors as application notices, not model speech.
Stream smoothly; follow the bottom only while the user is already there, and
offer **Jump to latest** after they scroll away. Keep keyboard focus stable.
Add working copy-response and continue-partial actions using existing backend
semantics; do not introduce hidden automatic reruns. Show connecting/reconnecting
states honestly and recover canonical text without duplication.

### Conversation management — included in this build

Include these five additions in the same implementation pass. Reuse the local
SQLite state, protected API, conversation menu and browser download support;
no model calls, cloud services or new search infrastructure are needed.

- **Rename chat:** an accessible menu action with the current title prefilled.
  Enter saves, Escape cancels. Reuse the existing nonempty, trimmed 120-character
  title limit; persist the change without changing message content or chat ID.
- **Search conversations:** local literal-text search over saved titles and
  messages, including chats outside the sidebar's initial 100-row list. Return
  a bounded list with a readable matching snippet; selecting a result opens the
  correct conversation and locates the match. Support Unicode, escape snippets
  as text, parameterise queries and treat `%`/`_` as literal search characters.
  Show searching, no-results and error states. Clear returns to the normal list.
  Start with existing SQLite queries; semantic search is outside this addition.
- **Draft recovery:** retain an unsent draft per conversation, including a new
  chat before its first message, in workspace-owned local state. Restore it
  after switching chats, refreshing or restarting the app. Save with a small
  debounce and flush on conversation change; do not send drafts to the model or
  include them in search/export. Clear only the successfully submitted draft
  version, never newer typing; failed sends retain it. Deleting a chat clears
  its draft, and delayed saves must not recreate a deleted chat.
- **Pin important chats:** a Pin/Unpin menu action and a clear pinned indicator.
  Persist pin state and show pinned chats before unpinned chats, with stable
  most-recent-activity ordering within each group. Unpinning preserves history.
  Do not add drag-and-drop ordering for this version.
- **Export chat:** export the selected chat as UTF-8 Markdown or plain text via
  an explicit local download, using a safe filename. Include title, chronological
  messages, speaker labels and readable notices for partial/context-limited
  replies. Preserve code and formatting in Markdown. Export a consistent saved
  snapshot, including messages beyond any UI display limit; omit unsent drafts
  and unrelated chats/internal records. Do not mutate history or fetch links.

**“Regenerate the last reply” is explicitly excluded.** Keep **Continue** as the
already specified new follow-up to a saved partial reply; it does not overwrite
or regenerate an earlier answer. No message editing or branching is added here.

Add **Delete chat** to an accessible `⋯` menu on each conversation row, available
on keyboard and touch as well as hover. Confirm using the chat title and clear
scope: **“Delete this chat? Its messages and run history will be removed. This
cannot be undone.”** Provide **Cancel** and **Delete chat**, with Cancel focused
by default. Keep **New conversation** as a separate action that preserves history.

Disable deletion while that chat has unfinished work and explain **“Stop the
response before deleting this chat.”** Enforce the same guard in the backend,
atomically with deletion, so a concurrent submission cannot bypass it. Use the
protected local API; delete only the selected chat and its dependent C03
message/job/attempt/event records in one transaction. Preserve other chats,
workspace/node identity, installed models and unrelated files. Report success
only after the backend confirms it, then select the next chat or the empty
state. On failure keep the chat visible with a retryable application notice.
Do not describe ordinary database deletion as secure disk erasure.

Use accessible labels, focus indicators, keyboard-operable drawers and restrained
screen-reader announcements. State must remain understandable without colour;
support reduced motion and 200% zoom. Avoid announcing every streamed token.

## 6. Build a deterministic UI fixture

Create a clearly labelled, separately opened **synthetic UI fixture**, using the
same renderer/styles/components as the application. Do not add fake turns,
citations, measurements or jobs to normal user history. Keep fixture data out
of default production navigation and network calls.

Include this representative content, then the edge cases below:

````markdown
## Inspection summary — synthetic example

**Pump P-204 needs review.** This is a formatting fixture, not a real inspection.
The selected setting is `num_ctx=4096`; *italics remain readable*.

1. Review the finding.
   - Retain the original observation.
   - Record the next action.
2. Compare it with the synthetic source.

> Earlier exchanges may be omitted from a request while remaining in saved history.

| Item | Observation | Next step |
|---|---|---|
| Pump P-204 | Synthetic vibration finding | Inspect mounting |
| Valve V-12 | No fixture evidence supplied | Do not infer a pass |

```python
def remaining_input(window, output_allowance, overhead):
    return max(0, window - output_allowance - overhead)
```

[Example external link](https://example.com)

Synthetic source label: Inspection SOP, page 3 — fixture only, not verified evidence.

मराठी मजकूर — हिंदी पाठ — 中文 — café — 🔧
````

Also cover a long paragraph, long unbroken URL, wrapped conversation title,
wide table, code containing `<`, `>` and `&`, and an unfinished streamed code
fence. Include raw-HTML/script-like text and unsafe links as inert negative
cases. Add deterministic visual states for idle, streaming, stopped, incomplete,
context omission, oversized input, reconnecting and runtime unavailable. Keep
the labels explicit that state data is synthetic.
Include Delete chat confirmation, cancelled confirmation, active-work disabled,
deletion error and last-chat-deleted empty states.
Include rename/save-error states, pinned/unpinned rows, search results/no results,
restored drafts in two different chats, and both export choices.

## 7. Verification and handoff

Reuse the existing coordinator/contract tests and add focused regression checks
for the new behavior. Test short/long conversations, exact boundary cases,
non-English/code inputs, complete-exchange selection, oversized newest input,
unchanged saved history, persisted selection metadata and isolation between
chats. Preserve cancellation, late-cancel handling, restart reconciliation,
output-limit reporting and local Host/Origin/JSON protections.
For deletion, prove that cancelling changes nothing; a confirmed deletion stays
deleted after restart; other chats remain; unfinished-work rejection and its
submit/delete race are handled; and stale UI events cannot recreate the deleted
conversation. Exercise deletion only with disposable synthetic chats.
Add proportionate checks for rename/pin persistence; literal and Unicode search
across the full saved history; draft isolation, refresh recovery, failed sends
and newer typing during submission; and complete Markdown/plain-text exports
that exclude drafts and other chats. Confirm deleted chats disappear from search
and pin lists and cannot return through a delayed draft save.

Exercise the fixture and real application in the browser at approximately
1440px, 1280px, 1024px and 390px widths plus 200% zoom. Verify navigation and
Details remain reachable, nothing important clips, keyboard operation works,
copy actions work, drafts survive errors and reading position survives streaming.
Check unsafe Markdown, no automatic external requests, and no console errors.
Capture before/after screenshots of Chat, Control Center and the rich fixture.

Finally run a real multi-turn synthetic conversation through the installed
model: demonstrate context selection/overflow handling, a reply longer than
512 tokens, continuation and restart. Clearly separate mocked UI states,
observed runtime behavior and untested device behavior. Browser network checks
are not the C11 zero-egress gate, and fluent output is not factual-quality proof.

Update the relevant README, model/evaluation notes, task status and lightweight
agent ledgers with observed results. Report **Built / Verified / Next**, changed
paths, exact commands, screenshots, limitations, and the Mac acceptance steps.
Preserve unrelated dirty changes. Prepare exact Git staging/commit commands
under the repository's required handoff headings; do not run Git/GitHub writes.
Stop at requester C03 acceptance rather than advancing into C04.
