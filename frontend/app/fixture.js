/* Synthetic UI fixture: renderer cases and deterministic visual states.
 *
 * A module file, not an inline script. That matters: these cases deliberately
 * contain markup like a closing script tag, which would terminate an inline
 * <script> and execute — the exact failure these cases exist to test for.
 *
 * Nothing here is real data. No measurement, citation, job or device state on
 * this page describes anything that happened.
 */
import { renderMarkdown } from '/markdown.js';

const CLOSE = '</' + 'script>';          // never written literally

const RICH = [
  '## Inspection summary — synthetic example',
  '',
  '**Pump P-204 needs review.** This is a formatting fixture, not a real inspection.',
  'The selected setting is `num_ctx=8192`; *italics remain readable*.',
  '',
  '1. Review the finding.',
  '   - Retain the original observation.',
  '   - Record the next action.',
  '2. Compare it with the synthetic source.',
  '',
  '> Earlier exchanges may be omitted from a request while remaining in saved history.',
  '',
  '| Item | Observation | Next step |',
  '|---|---|---|',
  '| Pump P-204 | Synthetic vibration finding | Inspect mounting |',
  '| Valve V-12 | No fixture evidence supplied | Do not infer a pass |',
  '',
  '```python',
  'def remaining_input(window, output_allowance, overhead):',
  '    return max(0, window - output_allowance - overhead)',
  '```',
  '',
  '[Example external link](https://example.com)',
  '',
  'Synthetic source label: Inspection SOP, page 3 — fixture only, not verified evidence.',
  '',
  'मराठी मजकूर — हिंदी पाठ — 中文 — café — 🔧',
].join('\n');

const CASES = [
  ['Rich content', RICH],
  ['Long paragraph',
   'This is a deliberately long paragraph used to check the reading column, line '
   + 'height and wrapping behaviour at every tested width. '.repeat(6)],
  ['Long unbroken URL',
   'See https://example.com/a/very/long/path/that/should/not/cause/horizontal/page/'
   + 'overflow/at/any/width/abcdefghijklmnopqrstuvwxyz0123456789 for details.'],
  ['Wide table',
   '| Column one | Column two | Column three | Column four | Column five | Column six |\n'
   + '|---|---|---|---|---|---|\n'
   + '| synthetic | synthetic | synthetic | synthetic | synthetic | synthetic |'],
  ['Code containing < > &',
   '```html\n<div class="a" data-x="1 & 2">\n  <span>x &lt; y &amp;&amp; y &gt; z</span>\n</div>\n```'],
  ['Unfinished streamed fence',
   '```javascript\nconst partial = {\n  streaming: true,'],
  ['Raw HTML stays inert',
   'Model text: <script>alert("xss")' + CLOSE
   + ' and <img src=x onerror=alert(1)> and <b>not bold</b>.'],
  ['Unsafe link schemes blocked',
   '[javascript scheme](javascript:alert(1)) and '
   + '[data scheme](data:text/html,hello) and '
   + '[safe](https://example.com/ok)'],
  ['Nested lists',
   '- top\n  - second\n    - third\n- back to top\n\n1. one\n   1. one-a\n   2. one-b'],
  ['Emphasis and strikethrough',
   '**bold** _italic_ ~~struck~~ `inline code` and __also bold__'],
];

function chip(text, cls) {
  const el = document.createElement('span');
  el.className = `chip ${cls}`;
  el.textContent = text;
  return el;
}

function notice(text, kind, why) {
  const el = document.createElement('div');
  el.className = 'app-notice';
  el.dataset.kind = kind;
  el.append(text);
  const s = document.createElement('span');
  s.className = 'why';
  s.textContent = why;
  el.append(s);
  return el;
}

function selection(sel) {
  const el = document.createElement('details');
  el.className = 'context-notice';
  el.open = true;
  const sum = document.createElement('summary');
  sum.textContent = sel.note;
  const dl = document.createElement('dl');
  for (const [k, v] of [
    ['Left out of this request', `${sel.omitted_count} message(s) — still saved in this chat`],
    ['Sent to the model', `${sel.included} message(s)`],
    ['Estimated size', `${sel.estimated} of ${sel.budget} tokens`],
    ['Context window', `${sel.window} tokens`],
    ['How size was counted', sel.counting],
  ]) {
    const dt = document.createElement('dt'); dt.textContent = k;
    const dd = document.createElement('dd'); dd.textContent = v;
    dl.append(dt, dd);
  }
  el.append(sum, dl);
  return el;
}

function chatRow(title, {pinned = false, snippet = null, current = false} = {}) {
  const row = document.createElement('div');
  row.className = 'chat-row';
  const open = document.createElement('button');
  open.className = 'nav-item';
  if (current) open.setAttribute('aria-current', 'true');
  if (pinned) {
    const p = document.createElement('span');
    p.className = 'pin-mark'; p.textContent = '📌'; p.title = 'Pinned';
    open.append(p);
  }
  const t = document.createElement('span');
  t.className = 'title'; t.textContent = title;
  open.append(t);
  if (snippet) {
    const s = document.createElement('span');
    s.className = 'snippet'; s.textContent = snippet;
    open.append(s);
  }
  const menu = document.createElement('button');
  menu.className = 'row-menu-btn'; menu.textContent = '⋯';
  menu.setAttribute('aria-label', `Actions for ${title}`);
  row.append(open, menu);
  return row;
}

function group(...nodes) {
  const box = document.createElement('div');
  box.style.maxWidth = '20rem';
  box.append(...nodes);
  return box;
}

const STATES = [
  ['Pinned and unpinned rows', () => group(
    chatRow('Pinned inspection log', {pinned: true}),
    chatRow('Ordinary conversation'),
    chatRow('Currently open', {current: true}))],
  ['Search results with snippets', () => group(
    chatRow('Pump P-204 inspection', {snippet: 'user: the bearing on P-204 is worn…'}),
    chatRow('Valve survey', {snippet: 'assistant: …no P-204 reference found…'}))],
  ['Search — no results', () => {
    const p = document.createElement('p');
    p.className = 'lbl search-state';
    p.textContent = 'No conversations match “zzzznope”.';
    return p;
  }],
  ['Rename in progress', () => {
    const row = document.createElement('div');
    row.className = 'chat-row';
    const input = document.createElement('input');
    input.className = 'rename-input';
    input.value = 'Pump P-204 inspection';
    input.setAttribute('aria-label', 'Rename conversation');
    const menu = document.createElement('button');
    menu.className = 'row-menu-btn'; menu.textContent = '⋯';
    row.append(input, menu);
    return group(row);
  }],
  ['Rename failed', () => notice(
    'Could not rename this conversation.', 'error',
    'Synthetic state. A title cannot be empty.')],
  ['Restored draft — chat A', () => notice(
    'Draft restored.', 'warn',
    'Synthetic state. "the vibration reading from Tuesday was" — unsent, never sent to the model.')],
  ['Restored draft — chat B', () => notice(
    'Draft restored.', 'warn',
    'Synthetic state. "check whether V-12 was ever" — a separate chat keeps its own draft.')],
  ['Export choices', () => {
    const menu = document.createElement('div');
    menu.className = 'row-menu';
    menu.style.position = 'static';
    for (const label of ['Rename', 'Pin', 'Export as Markdown',
                         'Export as plain text', 'Delete chat']) {
      const b = document.createElement('button');
      b.textContent = label;
      if (label === 'Delete chat') b.dataset.danger = '1';
      menu.append(b);
    }
    return group(menu);
  }],
  ['Idle', () => chip('no job', 'chip-unknown')],
  ['Streaming', () => chip('running', 'chip-running')],
  ['Stopped by user', () => chip('cancelled', 'chip-fault')],
  ['Incomplete — hit the reply limit', () => notice(
    'The reply stopped at the 2048-token limit.', 'warn',
    'Synthetic state. The partial text is saved and can be continued.')],
  ['Context omission', () => selection({
    omitted_count: 6, included: 4, estimated: 4980, budget: 5168, window: 8192,
    counting: 'estimate: characters / 3.0',
    note: '6 earlier messages were left out of this reply. They remain in your chat.',
  })],
  ['Oversized input', () => notice(
    'That message is too large to send.', 'error',
    'Synthetic state. About 30009 tokens against a 5168-token budget. Shorten or split it.')],
  ['Reconnecting', () => notice(
    'Reconnecting to the coordinator…', 'warn',
    'Synthetic state. The conversation is safe; it is stored on this device.')],
  ['Runtime unavailable', () => notice(
    'The local model runtime is not answering.', 'error',
    'Synthetic state. Nothing was sent anywhere else.')],
];

const host = document.getElementById('cases');

for (const [title, source] of CASES) {
  const sec = document.createElement('section');
  sec.className = 'fixture-case';
  const h = document.createElement('h2');
  h.className = 'case-title';
  h.textContent = title;
  const body = document.createElement('div');
  body.className = 'prose';
  renderMarkdown(body, source);
  sec.append(h, body);
  host.append(sec);
}

for (const [title, build] of STATES) {
  const sec = document.createElement('section');
  sec.className = 'fixture-case';
  const h = document.createElement('h2');
  h.className = 'case-title';
  h.textContent = `State — ${title}`;
  sec.append(h, build());
  host.append(sec);
}
