/* Refinix application UI.
 *
 * Every value rendered here comes from the coordinator. Nothing is defaulted to
 * a healthy-looking state: a missing observation renders as `unavailable`, which
 * the stylesheet hatches so it can never be mistaken for a measurement.
 *
 * Two rules this file is responsible for keeping:
 *   - ordinary product messages say what the person can do next, in their
 *     words. Internal chunk numbers and implementation jargon live behind
 *     Details and Advanced, not in the sentence a user reads;
 *   - a capability that does not exist is never implied. An attached file is
 *     described as received, never as read.
 */
'use strict';

import { renderMarkdown } from '/markdown.js';

const $ = (id) => document.getElementById(id);
const api = (p, o) => fetch(p, o).then(async (r) => {
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
  return body;
});

/* A stroked 16x16 glyph. Geometry only — weight, size and colour are the
 * stylesheet's, so an icon inherits whatever control it is dropped into. */
function svgIcon(d) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 16 16');
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('focusable', 'false');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', d);
  svg.append(path);
  return svg;
}

/* Two sheets, the back one drawn open so the front can overlap it without
 * needing a fill to hide behind — the control sits on glass, which has no
 * one colour to fill with. */
const ICON_COPY = 'M2.25 7.85a1.6 1.6 0 0 1 1.6-1.6h4.3a1.6 1.6 0 0 1 1.6 1.6v4.3'
  + 'a1.6 1.6 0 0 1-1.6 1.6h-4.3a1.6 1.6 0 0 1-1.6-1.6z'
  + 'M6.25 6.25V3.85a1.6 1.6 0 0 1 1.6-1.6h4.3a1.6 1.6 0 0 1 1.6 1.6v4.3'
  + 'a1.6 1.6 0 0 1-1.6 1.6h-2.4';
const ICON_TICK = 'M3.5 8.4 6.4 11.3 12.5 5.2';

/* An unavailable fact is rendered, never omitted and never filled in. */
function cell(value, note) {
  const dd = document.createElement('dd');
  if (value === null || value === undefined || value === '') {
    dd.className = 'unavailable';
    dd.textContent = note || 'unavailable';
  } else {
    dd.textContent = String(value);
  }
  return dd;
}

function kv(target, rows) {
  target.replaceChildren();
  for (const [key, value, note] of rows) {
    const div = document.createElement('div');
    const dt = document.createElement('dt');
    dt.textContent = key;
    div.append(dt, cell(value, note));
    target.append(div);
  }
}


/* ---- scroll, notices ------------------------------------------------- */

const NEAR_BOTTOM = 80;

function atBottom() {
  const t = $('thread');
  if (!t) return true;
  return t.scrollHeight - t.scrollTop - t.clientHeight < NEAR_BOTTOM;
}

let following = true;

/* Only pull the view down if the reader was already at the bottom. Scrolling
 * up to re-read must not be yanked away mid-answer. */
function maybeFollow() {
  const t = $('thread');
  if (!t) return;
  if (following) t.scrollTop = t.scrollHeight;
  const jump = $('jump-latest');
  if (jump) jump.hidden = following;
}

/* Recoverable problems are application notices, never words put in the
 * model's mouth. */
function notice(text, kind = 'error', why) {
  const host = $('notices');
  if (!host) return;
  const el = document.createElement('div');
  el.className = 'app-notice';
  el.dataset.kind = kind;
  el.append(text);
  if (why) {
    const span = document.createElement('span');
    span.className = 'why';
    span.textContent = why;
    el.append(span);
  }
  host.replaceChildren(el);
  setTimeout(() => { if (el.isConnected) el.remove(); }, 12000);
}

/* The context selection that actually ran, shown beside its reply. */
function contextNotice(selection) {
  if (!selection || !selection.omitted_count) return;
  const el = document.createElement('details');
  el.className = 'context-notice';
  const sum = document.createElement('summary');
  sum.textContent = selection.note
    || `${selection.omitted_count} earlier messages were left out of this reply.`;
  const dl = document.createElement('dl');
  const rows = [
    ['Left out of this request', `${selection.omitted_count} message(s) — still saved in this chat`],
    ['Sent to the model', `${selection.included_ids.length} message(s)`],
    ['Estimated size', `${selection.estimated_input_tokens} of ${selection.input_budget_tokens} tokens`],
    ['Context window', `${selection.context_window} tokens`],
    ['Reply allowance', `${selection.output_allowance} tokens`],
    ['How size was counted', selection.counting_method],
  ];
  for (const [k, v] of rows) {
    const dt = document.createElement('dt'); dt.textContent = k;
    const dd = document.createElement('dd'); dd.textContent = v;
    dl.append(dt, dd);
  }
  el.append(sum, dl);
  $('thread').append(el);
  maybeFollow();
}

/* ---------------------------------------------------------------- Chat --- */

const JOB_STEPS = ['created', 'context_preparing', 'queued', 'routing',
                   'running', 'validating', 'completed'];

let chatId = null;
let activeJob = null;
let jobState = null;
let lastSequence = 0;
let pendingEvents = new Map();
let replaying = null;

async function replayEvents() {
  const id = activeJob;
  if (!id || replaying === id) return;
  replaying = id;
  try {
    const detail = await api(`/v1/job?job_id=${id}`);
    if (activeJob === id) for (const ev of detail.events) onEvent(ev);
  } catch (e) { console.error('event replay unavailable:', e.message); }
  finally { if (replaying === id) replaying = null; }
}

function renderLife(current) {
  const list = $('life');
  if (!list) return;
  const at = JOB_STEPS.indexOf(current);
  list.replaceChildren();
  JOB_STEPS.forEach((step, i) => {
    const li = document.createElement('li');
    li.className = at < 0 ? 'st-todo'
      : i < at ? 'st-done' : i === at ? 'st-now' : 'st-todo';
    const dot = document.createElement('span');
    dot.className = 'dot';
    li.append(dot, document.createTextNode(step.replace(/_/g, ' ')));
    list.append(li);
  });
}

/* Render one turn into `host`, which defaults to the live thread.
 *
 * The detached-host argument is what makes the repair possible: openChat()
 * builds the whole replacement view off-screen and commits it in one step, so
 * a failure part-way through can never leave a cleared pane behind. */
function turn(role, text, attachments, plain, host, skill, artifacts) {
  const article = document.createElement('article');
  article.className = `turn turn-${role === 'user' ? 'user' : 'agent'}`;
  const box = document.createElement('div');
  box.className = role === 'user' ? 'bubble' : 'prose';
  if (role === 'user') {
    box.textContent = text;
  } else {
    box.dataset.raw = text;          // literal source, used for copy and re-render
    // One formatter defect must cost one message's formatting, not the
    // conversation. The fallback is textContent — never innerHTML.
    try {
      renderMarkdown(box, text);
    } catch (err) {
      box.replaceChildren();
      box.textContent = text;
      const note = document.createElement('p');
      note.className = 'lbl format-fallback';
      note.textContent = 'Formatting unavailable — shown as plain text';
      box.append(note);
      console.error('markdown render failed for one message:', err.message);
    }
  }
  article.append(box);
  if (attachments && attachments.length) {
    const list = document.createElement('ul');
    list.className = 'turn-attachments';
    list.setAttribute('aria-label', 'Files sent with this request');
    for (const record of attachments) list.append(attachmentRow(record, null));
    article.append(list);
    const note = document.createElement('p');
    note.className = 'lbl';
    // What actually happened to these files, per request. Ordinary Chat now
    // reads the files sent with that one request, and nothing else.
    const capability = skill && capabilities.find((c) => c.id === skill);
    note.textContent = capability
      ? `Read by ${capability.name} for this request.`
      : (attachments.length === 1
        ? 'Read for this request, on this computer. Earlier files are not '
          + 'read again.'
        : 'Read for this request, on this computer. Earlier files are not '
          + 'read again.');
    article.append(note);
  }
  if (artifacts && artifacts.length) {
    const list = document.createElement('ul');
    list.className = 'turn-attachments';
    list.setAttribute('aria-label', 'Documents Refinix produced');
    for (const artifact of artifacts) list.append(artifactRow(artifact));
    article.append(list);
  }
  if (role !== 'user' && !plain) {
    const bar = document.createElement('div');
    bar.className = 'turn-meta';
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'turn-copy';
    /* Icon-only now, so everything the label used to say has to go somewhere
     * a label is not: the glyph becomes a tick, the accessible name and the
     * tooltip both change, and only a failure spends colour. */
    const setCopyState = (state) => {
      const label = state === 'copied' ? 'Copied'
        : state === 'failed' ? 'Copy failed' : 'Copy reply';
      copy.dataset.copy = state;
      copy.title = label;
      copy.setAttribute('aria-label', label);
      copy.replaceChildren(svgIcon(state === 'copied' ? ICON_TICK : ICON_COPY));
    };
    setCopyState('idle');
    copy.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(box.dataset.raw || '');
        setCopyState('copied');
      } catch { setCopyState('failed'); }
      setTimeout(() => setCopyState('idle'), 1500);
    });
    bar.append(copy);
    article.append(bar);
  }
  (host || $('thread')).append(article);
  if (!host) maybeFollow();
  return box;
}

let streamBox = null;

const ACTIVE_STATES = ['created', 'context_preparing', 'queued', 'routing',
                       'running', 'validating'];
/* True from the moment Stop is pressed until the job actually stops, so the
 * button reports what is happening instead of looking unresponsive. */
let stopping = false;

/* Send and Stop share one slot: while work is running, Stop is the prominent
 * control, and it is restored the same way when an active conversation is
 * reopened. */
function setActive(state) {
  const active = ACTIVE_STATES.includes(state);
  const stop = $('cancel-btn');
  const send = $('send');
  if (!active) stopping = false;
  if (stop) {
    stop.hidden = !active;
    stop.disabled = stopping;
    stop.textContent = stopping ? 'Stopping…' : 'Stop';
  }
  if (send) send.hidden = active;
  setWorking(active);
  refreshSend();
}

/* The turning mark and the shining word, shared by Chat and Code. It reports
 * work that is genuinely running and nothing else: Chat drives it from the
 * job state the coordinator reports, Code turns it off in a finally, so a
 * failed proposal cannot leave it spinning over nothing. */
function setWorking(on) {
  const el = $('working');
  if (el) el.hidden = !on;
}

function setJobChip(state) {
  const chip = $('job-chip');
  if (!chip) return;
  chip.textContent = state ? state.replace(/_/g, ' ') : 'no job';
  chip.className = 'chip ' + (
    state === 'running' ? 'chip-running'
      : state === 'completed' ? 'chip-enforced'
        : ['failed', 'cancelled', 'denied'].includes(state) ? 'chip-fault'
          : state === 'interrupted' ? 'chip-caution' : 'chip-unknown');
}

let deltaCount = 0;
let deltaChars = 0;

/* One row per state change. Output deltas would otherwise flood the rail with
 * one line per token, so they collapse into a single rolling counter. */
function pushEvent(ev) {
  const ul = $('events');
  if (!ul) return;
  if (ev.data.kind === 'output.delta') {
    deltaCount += 1;
    deltaChars += ev.data.text.length;
    let row = ul.querySelector('li[data-stream]');
    if (!row) {
      row = document.createElement('li');
      row.dataset.stream = '1';
      const kind = document.createElement('span');
      kind.className = 'kind';
      kind.textContent = 'output';
      row.append(kind, document.createTextNode(' '),
                 Object.assign(document.createElement('span'), { className: 'count' }));
      ul.prepend(row);
    }
    row.querySelector('.count').textContent =
      `${deltaChars} chars in ${deltaCount} chunks`;
    return;
  }
  const li = document.createElement('li');
  const kind = document.createElement('span');
  kind.className = 'kind';
  kind.textContent = ev.data.kind === 'job.state' ? 'job' : 'attempt';
  const time = document.createElement('time');
  time.textContent = ev.occurred_at.slice(11, 19);
  li.append(kind,
            document.createTextNode(` ${ev.data.previous || 'start'} → ${ev.data.current}`),
            time);
  ul.prepend(li);
  while (ul.children.length > 24) ul.lastElementChild.remove();
}

function onEvent(ev) {
  if (!activeJob || ev.job_id !== activeJob || ev.sequence <= lastSequence) return;
  pendingEvents.set(ev.sequence, ev);
  while (pendingEvents.has(lastSequence + 1)) {
    const next = pendingEvents.get(lastSequence + 1);
    pendingEvents.delete(++lastSequence);
    applyEvent(next);
  }
  if (pendingEvents.size) replayEvents();
}

function applyEvent(ev) {
  pushEvent(ev);
  const d = ev.data;
  if (d.kind === 'job.state') {
    jobState = d.current;
    renderLife(d.current);
    setJobChip(d.current);
    setActive(d.current);
    const done = ['completed', 'failed', 'cancelled', 'denied', 'interrupted'];
    if (done.includes(d.current)) {
      streamBox = null;
      // Reload from canonical state, then show which context actually ran.
      openChat(chatId)
        .then(showSelection)
        .catch((e) => notice('Could not refresh the conversation.', 'error', e.message));
    }
  } else if (d.kind === 'output.delta') {
    if (!streamBox) streamBox = turn('assistant', '');
    streamBox.dataset.raw = (streamBox.dataset.raw || '') + d.text;
    renderMarkdown(streamBox, streamBox.dataset.raw);
    maybeFollow();
  } else if (d.kind === 'attempt.state') {
    refreshAttempt();
  }
}

async function showSelection() {
  const id = activeJob;
  if (!id) return;
  const detail = await api(`/v1/job?job_id=${id}`).catch(() => null);
  if (activeJob !== id) return;
  const a = detail && detail.attempts[detail.attempts.length - 1];
  if (a && a.selection) contextNotice(a.selection);
}

async function refreshAttempt() {
  const id = activeJob;
  if (!id) return;
  const detail = await api(`/v1/job?job_id=${id}`).catch(() => null);
  if (activeJob !== id) return;
  if (!detail || !detail.attempts.length) return;
  const a = detail.attempts[detail.attempts.length - 1];
  const err = a.error_json ? JSON.parse(a.error_json) : null;
  const metrics = a.metrics_json ? JSON.parse(a.metrics_json) : {};
  kv($('attempt-kv'), [
    ['state', a.state],
    ['route reason', a.route_reason],
    ['runtime ms', a.runtime_ms, 'not measured'],
    ['stop reason', metrics.done_reason, 'not recorded'],
    ['output tokens', metrics.eval_count, 'not measured'],
    ['reply limit', metrics.output_token_limit, 'not recorded'],
    ['limit reached', metrics.limit_reason?.replace(/_/g, ' '), 'not reported'],
    ['detail', err ? err.message : metrics.done_reason === 'stop'
      ? 'Model finished normally' : null, 'not recorded'],
  ]);
}

/* ---- composer sizing and the context estimate ------------------------- */

/* Both composers start one line tall, grow with the text, stop at a maximum
 * and scroll inside themselves after that. Height is set from scrollHeight
 * rather than by counting characters, so wrapped lines, pasted blocks and
 * different fonts all measure correctly. */
const COMPOSER_MIN_ROWS = 1;
const COMPOSER_MAX_PX = 260;

function autogrow(input) {
  if (!input) return;
  // Collapse first: scrollHeight only shrinks if the box is allowed to.
  input.style.height = 'auto';
  const wanted = input.scrollHeight;
  const capped = Math.min(wanted, COMPOSER_MAX_PX);
  input.style.height = `${capped}px`;
  input.style.overflowY = wanted > COMPOSER_MAX_PX ? 'auto' : 'hidden';
}

/* Re-measure after anything that changes the text or the available width:
 * a restored draft, a switched chat or project, an attachment chip appearing,
 * a send that empties the box, and a window resize. */
function wireAutogrow(input) {
  if (!input) return;
  input.rows = COMPOSER_MIN_ROWS;
  input.style.resize = 'none';          // sizing is automatic, not dragged
  input.addEventListener('input', () => autogrow(input));
  window.addEventListener('resize', () => autogrow(input));
  autogrow(input);
}

/* ---- context indicator ------------------------------------------------ */

/* The figure comes from the coordinator, which uses context.py — the same code
 * that decides what actually gets sent. There is deliberately no second
 * estimator in this file: two counters would eventually disagree, and the one
 * on screen would be the wrong one. */
let contextState = null;
let contextTimer = null;
let contextPopover = null;

function shortTokens(value) {
  if (!Number.isFinite(value)) return '—';
  return value >= 1000 ? `${(value / 1000).toFixed(1)}k` : String(value);
}

function renderContextMeter() {
  const meter = $('context-meter');
  if (!meter) return;
  if (!contextState) { meter.hidden = true; return; }
  meter.hidden = false;
  $('context-figure').textContent =
    `Context ≈ ${shortTokens(contextState.used_tokens)}`
    + ` / ${shortTokens(contextState.budget_tokens)}`;
  meter.dataset.level = contextState.level;
  meter.setAttribute('aria-label', contextSentence(contextState));
  meter.title = contextSentence(contextState);
}

function contextSentence(state) {
  if (!state.newest_fits) {
    return 'This message is too long to send on its own. Shorten it, or split '
      + 'it into two messages.';
  }
  if (state.omitted_count) {
    return `${state.omitted_count} earlier message(s) will not be sent with this `
      + 'request. They stay saved in this conversation. Start a new chat to give '
      + 'the model a fresh window, and carry over the details it still needs.';
  }
  if (state.level === 'near') {
    return 'This conversation is close to the amount the model can be given at '
      + 'once. Soon, earlier messages will stop being sent — starting a new chat '
      + 'with a short summary keeps the relevant context explicit.';
  }
  return `About ${state.used_tokens} of ${state.budget_tokens} tokens of room `
    + 'used. This is an estimate, not an exact count.';
}

async function refreshContext() {
  const input = $('input');
  if (!$('context-meter')) return;
  try {
    contextState = await api('/v1/context', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chatId, draft: input ? input.value : '' }),
    });
  } catch (err) {
    contextState = null;
  }
  renderContextMeter();
}

/* Typing should not send a request per keystroke. */
function refreshContextSoon() {
  clearTimeout(contextTimer);
  contextTimer = setTimeout(refreshContext, 400);
}

function closeContextPopover(returnFocus) {
  if (!contextPopover) return;
  contextPopover.remove();
  contextPopover = null;
  const meter = $('context-meter');
  if (meter) {
    meter.setAttribute('aria-expanded', 'false');
    if (returnFocus) meter.focus();
  }
}

function openContextPopover() {
  closeContextPopover(false);
  const meter = $('context-meter');
  if (!meter || !contextState) return;
  const box = document.createElement('div');
  box.className = 'model-popover context-popover';
  box.setAttribute('role', 'dialog');
  box.setAttribute('aria-label', 'How much of the conversation fits');

  const headline = document.createElement('p');
  headline.className = 'mp-name';
  headline.textContent = contextSentence(contextState);
  box.append(headline);

  const facts = document.createElement('dl');
  facts.className = 'facts';
  const rows = [
    ['Estimated use', `${contextState.used_tokens} tokens`],
    ['Room for the conversation', `${contextState.budget_tokens} tokens`],
    ['Model window', `${contextState.context_window} tokens`],
    ['Reserved for the reply', `${contextState.reply_allowance} tokens`],
    ['How it is counted', contextState.counting_method],
  ];
  for (const [key, value] of rows) {
    const div = document.createElement('div');
    const dt = document.createElement('dt'); dt.textContent = key;
    const dd = document.createElement('dd'); dd.textContent = value;
    div.append(dt, dd);
    facts.append(div);
  }
  box.append(facts);

  const note = document.createElement('p');
  note.className = 'mp-note';
  note.textContent = contextState.policy
    + ' The figure is an estimate from character counts, not the model’s own tokenizer.';
  box.append(note);

  document.body.append(box);
  const rect = meter.getBoundingClientRect();
  const height = box.getBoundingClientRect().height;
  box.style.left = `${Math.round(Math.max(8, rect.left))}px`;
  box.style.top = `${Math.round(Math.max(8, rect.top - height - 8))}px`;
  contextPopover = box;
  meter.setAttribute('aria-expanded', 'true');
  box.querySelector('p').setAttribute('tabindex', '-1');
}

/* ---- capabilities, skills and attachments ---------------------------- */

const NEW_DRAFT_SLOT = '__new__';

/* 14px line icons, inline so the application requests no icon font. */
const ICONS = {
  chat: 'M3 4h10v7H6l-3 3z',
  document: 'M4 2h5l3 3v9H4z M9 2v3h3',
  compose: 'M3 11l7-7 3 3-7 7H3z',
  search: 'M7 2a5 5 0 1 0 3 9l3 3 1-1-3-3A5 5 0 0 0 7 2z',
  code: 'M6 4L2 8l4 4 M10 4l4 4-4 4',
  paperclip: 'M11 5L6 10a2 2 0 0 0 3 3l5-5a4 4 0 0 0-6-6L3 7',
};

function icon(name) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 16 16');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '1.4');
  svg.setAttribute('stroke-linejoin', 'round');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', ICONS[name] || ICONS.chat);
  svg.append(path);
  return svg;
}

let capabilities = [];
/* Skill selection is composer state for this session, kept per conversation so
 * switching back restores what was chosen. It is never sent as prompt text. */
const skillByChat = new Map();
let staged = [];                 // files selected but not yet sent
let plusMenu = null;

function currentSlot() {
  return chatId || NEW_DRAFT_SLOT;
}

/* The native bridge reads this to know which conversation a chosen file
 * belongs to. It is the only value the shell takes from the page. */
function publishSlot() {
  window.refinixDraftId = currentSlot();
}

function selectedSkill() {
  return skillByChat.get(currentSlot()) || null;
}

function bytes(n) {
  if (!Number.isFinite(n)) return '';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

async function loadCapabilities() {
  try {
    const body = await api('/v1/capabilities');
    capabilities = body.capabilities || [];
  } catch (err) {
    capabilities = [];
  }
  renderSkill();
}

function chooseSkill(id) {
  const skill = capabilities.find((c) => c.id === id) || null;
  if (!skill || skill.kind === 'default') skillByChat.delete(currentSlot());
  else skillByChat.set(currentSlot(), skill);
  renderSkill();
  renderModelPill();
  const input = $('input');
  if (input) input.focus();
}

/* The label is structured selection state, not editable prompt text: it lives
 * outside the textarea, is reachable by Tab, and Backspace at the start of an
 * empty-prefix request removes it. */
function renderSkill() {
  const chip = $('skill-chip');
  const status = $('skill-status');
  if (!chip) return;
  const skill = selectedSkill();
  const live = skill ? (capabilities.find((c) => c.id === skill.id) || skill) : null;
  if (live) skillByChat.set(currentSlot(), live);

  if (!live) {
    chip.hidden = true;
    if (status) { status.hidden = true; status.textContent = ''; }
    refreshSend();
    return;
  }
  chip.hidden = false;
  chip.dataset.available = String(live.state === 'available');
  const iconHost = $('skill-icon');
  iconHost.replaceChildren(icon(live.icon));
  const name = $('skill-name');
  name.textContent = live.name;
  name.setAttribute('aria-label', `Selected skill: ${live.name}. Activate to change it.`);
  $('skill-remove').setAttribute('aria-label', `Remove the ${live.name} skill`);
  if (status) {
    status.hidden = live.state === 'available';
    // The capability's own sentence already says what is missing; prefixing it
    // with the name only repeats it. What to do about it follows, because the
    // composer no longer carries a standing hint line to put it on.
    status.textContent = live.state === 'available' ? ''
      : `${live.detail} Remove the skill to send an ordinary request.`;
  }
  refreshSend();
}

/* Send is disabled rather than quietly falling back to plain chat, because a
 * request sent under a skill that cannot run would be answered as if it had. */
function refreshSend() {
  const send = $('send');
  if (!send) return;
  const skill = selectedSkill();
  const blocked = !!(skill && skill.state !== 'available');
  send.disabled = sending || blocked;
  send.title = blocked ? `${skill.name} is not available yet.` : '';
}


/* ---- the model pill and its Reasoning switch -------------------------- */

/* One selected model per workflow, one Boolean per model. The choices live in
 * coordinator state, so they survive a restart and a fallback port; browser
 * storage is origin-scoped and would not. A submitted request snapshots the
 * value server-side, so
 * flipping the switch afterwards cannot change work already running. */
let models = [];
let modelSelections = {};
let modelPopover = null;

function modelScope() {
  if ($('code-composer')) return 'code';
  const skill = selectedSkill();
  if (skill?.id === 'search-documents') return null;
  return skill ? 'documents.generate' : 'chat';
}

function activeModel(scope = modelScope()) {
  return models.find((model) => model.id === modelSelections[scope]) || null;
}

function renderModelPill() {
  const pill = $('model-pill');
  if (!pill) return;
  const model = activeModel();
  pill.hidden = !model;
  if (!model) return;
  $('model-name').textContent = model.id;
  const mark = $('model-reasoning');
  mark.hidden = !model.reasoning;
  pill.setAttribute('aria-label', model.reasoning
    ? `Model ${model.id}, reasoning on. Change it.`
    : `Model ${model.id}, reasoning off. Change it.`);
  pill.title = model.eligible_scopes?.includes(modelScope()) ? ''
    : 'This model is not available for this workflow.';
}

function closeModelPopover(returnFocus) {
  if (!modelPopover) return;
  modelPopover.remove();
  modelPopover = null;
  const pill = $('model-pill');
  if (pill) {
    pill.setAttribute('aria-expanded', 'false');
    if (returnFocus) pill.focus();
  }
}

function openModelPopover() {
  closeModelPopover(false);
  const model = activeModel();
  const pill = $('model-pill');
  if (!model || !pill) return;

  const box = document.createElement('div');
  box.className = 'model-popover';
  box.setAttribute('role', 'dialog');
  box.setAttribute('aria-label', 'Model settings');

  const name = document.createElement('p');
  name.className = 'mp-name';
  name.textContent = 'Choose an installed model';
  box.append(name);

  appendModelChoices(box, modelScope(),
                     modelScope() === 'code' ? 'Code model'
                     : modelScope() === 'chat' ? 'Chat model' : 'Document model');
  if (modelScope() === 'documents.generate') {
    appendModelChoices(box, 'documents.ocr', 'Document OCR model');
  }
  if (selectedSkill()?.id === 'write-document') {
    appendDocumentChoices(box);
  }
  if ($('code-composer')) appendTargetChoices(box);

  const row = document.createElement('div');
  row.className = 'mp-row';
  const label = document.createElement('span');
  label.className = 'mp-label';
  label.id = 'mp-reasoning-label';
  label.textContent = 'Reasoning';
  // A real switch: role, state and keyboard activation, not a styled div.
  const toggle = document.createElement('button');
  toggle.type = 'button';
  toggle.className = 'mp-switch';
  toggle.setAttribute('role', 'switch');
  toggle.setAttribute('aria-labelledby', 'mp-reasoning-label');
  toggle.setAttribute('aria-checked', String(!!model.reasoning));
  toggle.disabled = !model.eligible_scopes?.includes(modelScope());
  const state = document.createElement('span');
  state.className = 'mp-state';
  state.textContent = model.reasoning ? 'On' : 'Off';
  toggle.append(state);
  row.append(label, toggle);
  box.append(row);

  const note = document.createElement('p');
  note.className = 'mp-note';
  note.textContent = model.eligible_scopes?.includes(modelScope())
    ? 'On lets the model work through the problem first. Slower, and it can use '
      + 'the whole reply budget before answering.'
    : 'This model is not installed on this computer, so reasoning cannot change.';
  box.append(note);

  toggle.addEventListener('click', async () => {
    const next = toggle.getAttribute('aria-checked') !== 'true';
    toggle.disabled = true;
    try {
      const saved = await api('/v1/model/reasoning', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: model.id, enabled: next }),
      });
      model.reasoning = saved.reasoning;
      toggle.setAttribute('aria-checked', String(saved.reasoning));
      state.textContent = saved.reasoning ? 'On' : 'Off';
      renderModelPill();
    } catch (err) {
      notice('That setting could not be saved.', 'error', err.message);
    } finally {
      toggle.disabled = !model.eligible_scopes?.includes(modelScope());
    }
  });

  document.body.append(box);
  const rect = pill.getBoundingClientRect();
  const height = box.getBoundingClientRect().height;
  box.style.left = `${Math.round(Math.max(8, rect.right - box.offsetWidth))}px`;
  box.style.top = `${Math.round(Math.max(8, rect.top - height - 8))}px`;
  modelPopover = box;
  pill.setAttribute('aria-expanded', 'true');
  toggle.focus();
}

/* The row is a name and a location inside one narrow popover, and the name is
 * the identity: "qwen3.5:4b-q4_K_M" and "qwen3:4b" differ only in the middle,
 * so a name clipped to "qwen…" names nothing. The location prose is wider than
 * the name it was displacing, and the machine reads just as clearly short.
 * Only the display is shortened; the inventory keeps naming both in full. */
const LOCATION_SHORT = { 'macOS coordinator': 'Mac', 'Ubuntu worker': 'Ubuntu' };

function locationLabel(locations) {
  if (!locations?.length) return 'not installed';
  return locations.map((where) => LOCATION_SHORT[where] || where).join(' + ');
}

/* Write Document's two choices, made before the request and sent with it.
 * They are structured selection state like the skill chip, not prompt text:
 * the coordinator stores them on the job, so a reopened conversation reports
 * the file and the workflow that actually ran. */
const OUTPUT_FORMATS = [
  { id: 'docx', name: 'Word (.docx)', tag: 'default' },
  { id: 'pdf', name: 'PDF (.pdf)', tag: '' },
];
const DOC_WORKFLOWS = [
  { id: 'general_document', name: 'General document', tag: 'default' },
  { id: 'inspection_report_to_approval_note',
    name: 'Inspection approval note', tag: 'cited' },
];

let outputFormat = 'docx';
let docWorkflow = 'general_document';

function appendDocumentChoices(box) {
  appendChoiceGroup(box, 'Save as', OUTPUT_FORMATS, outputFormat, (id) => {
    outputFormat = id;
  });
  appendChoiceGroup(box, 'Workflow', DOC_WORKFLOWS, docWorkflow, (id) => {
    docWorkflow = id;
  });
  const note = document.createElement('p');
  note.className = 'mp-note';
  note.textContent = docWorkflow === 'general_document'
    ? 'A general document is written from your request and any files you '
      + 'attach. Ask to save or convert the previous answer and it is copied '
      + 'with the same wording, without asking the model again.'
    : 'The fixed inspection workflow. It needs a report attached, checks every '
      + 'citation against the pages it read, and leaves unresolved values '
      + 'unresolved.';
  box.append(note);
}

function appendChoiceGroup(box, labelText, choices, current, onPick) {
  const group = document.createElement('div');
  group.className = 'mp-choices';
  group.setAttribute('role', 'radiogroup');
  group.setAttribute('aria-label', labelText);
  const label = document.createElement('p');
  label.className = 'mp-label';
  label.textContent = labelText;
  group.append(label);
  const rows = document.createElement('div');
  rows.className = 'mp-models';
  for (const choice of choices) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'mp-model';
    const selected = current === choice.id;
    button.dataset.selected = String(selected);
    button.setAttribute('role', 'radio');
    button.setAttribute('aria-checked', String(selected));
    appendModelChoiceParts(button, selected, choice.name, choice.tag);
    button.onclick = () => {
      onPick(choice.id);
      closeModelPopover(false);
      openModelPopover();
      renderModelPill();
    };
    rows.append(button);
  }
  group.append(rows);
  box.append(group);
}

function appendModelChoices(box, scope, labelText) {
  const group = document.createElement('div');
  group.className = 'mp-choices';
  group.setAttribute('role', 'radiogroup');
  group.setAttribute('aria-label', labelText);
  const label = document.createElement('p');
  label.className = 'mp-label';
  label.textContent = labelText;
  group.append(label);

  const auto = document.createElement('button');
  auto.type = 'button';
  auto.className = 'mp-model';
  auto.setAttribute('role', 'radio');
  auto.setAttribute('aria-checked', 'false');
  appendModelChoiceParts(auto, false, 'Auto model', 'after internal hackathon');
  auto.disabled = true;
  group.append(auto);

  for (const candidate of models) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'mp-model';
    const selected = modelSelections[scope] === candidate.id;
    const unavailable = !candidate.eligible_scopes?.includes(scope);
    button.dataset.selected = String(selected);
    button.setAttribute('role', 'radio');
    button.setAttribute('aria-checked', String(selected));
    const location = locationLabel(candidate.locations);
    appendModelChoiceParts(button, selected, candidate.id,
      candidate.installed && unavailable
        ? `${location} — unavailable for this workflow` : location);
    button.disabled = unavailable;
    button.onclick = async () => {
      button.disabled = true;
      try {
        await api('/v1/model/select', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ scope, model: candidate.id }),
        });
        await loadStatus();
        closeModelPopover(true);
      } catch (err) {
        notice('That model could not be selected.', 'error', err.message);
        button.disabled = false;
      }
    };
    group.append(button);
  }
  box.append(group);
}

function appendModelChoiceParts(button, selected, name, tag) {
  const tick = document.createElement('span');
  tick.className = 'mp-tick';
  tick.textContent = selected ? '✓' : '';
  const modelName = document.createElement('span');
  modelName.className = 'mp-model-name';
  modelName.textContent = name;
  const modelTag = document.createElement('span');
  modelTag.className = 'mp-tag';
  modelTag.textContent = tag;
  button.append(tick, modelName, modelTag);
}

/* ---- attachments ------------------------------------------------------ */

async function loadStaged() {
  const slot = currentSlot();
  try {
    const { attachments } = await api(`/v1/attachments?chat_id=${encodeURIComponent(slot)}`);
    if (currentSlot() !== slot) return;
    staged = attachments;
  } catch (err) {
    staged = [];
  }
  renderStaged();
}

function attachmentRow(record, onRemove) {
  const li = document.createElement('li');
  li.className = 'attachment';
  li.append(icon('paperclip'));
  const name = document.createElement('span');
  name.className = 'a-name';
  name.textContent = record.filename;            // escaped as text, never markup
  const meta = document.createElement('span');
  meta.className = 'a-meta';
  meta.textContent = bytes(record.byte_size);
  li.append(name, meta);
  if (onRemove) {
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'a-remove';
    remove.textContent = '×';
    remove.setAttribute('aria-label', `Remove ${record.filename}`);
    remove.onclick = () => onRemove(record);
    li.append(remove);
  }
  return li;
}

/* A generated document, with its export gated on a recorded approval. */
function artifactRow(artifact) {
  const li = document.createElement('li');
  li.className = 'attachment artifact-row';
  li.append(icon('document'));
  const name = document.createElement('span');
  name.className = 'a-name';
  name.textContent = artifact.filename;      // text only, never markup
  const meta = document.createElement('span');
  meta.className = 'a-meta';
  meta.textContent = `${bytes(artifact.byte_size)} · `
    + `${artifact.validation.paragraphs} paragraphs`
    + (artifact.state === 'exported' ? ' · saved' : '');
  const save = document.createElement('button');
  save.type = 'button';
  save.className = 'btn';
  save.textContent = 'Save a copy';
  save.onclick = () => exportArtifact(artifact);
  li.append(name, meta, save);
  return li;
}

/* Saving a copy outside Refinix's storage is a separate decision, recorded
 * before a single byte leaves. Being generated is not permission to leave. */
async function exportArtifact(artifact) {
  let pending;
  try {
    pending = await api('/v1/artifact/approve-export', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ artifact_id: artifact.artifact_id }),
    });
  } catch (err) {
    notice('That document could not be prepared for saving.', 'error', err.message);
    return;
  }
  const approval = pending.needs_approval;
  const yes = await confirmDialog(
    `Save ${artifact.filename} outside Refinix?`,
    'The file leaves the folder Refinix manages and is no longer tracked by it. '
    + 'Refinix drafted it from the documents you attached; check it before it '
    + 'is used.', 'Save a copy');
  if (!yes) {
    await api('/v1/code/decision', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approval_id: approval.approval_id, approved: false }),
    }).catch(() => {});
    notice('Nothing was saved.', 'warn', 'A denied request stays denied.');
    return;
  }
  try {
    await api('/v1/code/decision', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approval_id: approval.approval_id, approved: true }),
    });
  } catch (err) {
    notice('That approval could not be recorded.', 'error', err.message);
    return;
  }
  try {
    const response = await fetch('/v1/artifact/export', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ artifact_id: artifact.artifact_id,
                             approval_id: approval.approval_id }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    const href = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = href;
    anchor.download = artifact.filename;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(href);
  } catch (err) {
    notice('That document could not be saved.', 'error', err.message);
  }
}

function renderStaged() {
  const host = $('attachments');
  if (!host) return;
  host.replaceChildren(...staged.map((a) => attachmentRow(a, removeStaged)));
  host.hidden = staged.length === 0;
}

async function removeStaged(record) {
  try {
    await api('/v1/attachment/delete', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ attachment_id: record.attachment_id }),
    });
  } catch (err) {
    notice('That file could not be removed.', 'error', err.message);
    return;
  }
  staged = staged.filter((a) => a.attachment_id !== record.attachment_id);
  renderStaged();
}

/* One intake path for both the native picker and the browser file input: the
 * bytes go to the coordinator, which bounds the size, checks the type and
 * chooses the stored name. No filesystem path is ever sent from this page. */
async function stageFiles(files) {
  const slot = currentSlot();
  const rejected = [];
  for (const file of Array.from(files).slice(0, 10)) {
    try {
      const data = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onerror = () => reject(new Error('the file could not be read'));
        reader.onload = () => resolve(String(reader.result).split(',')[1] || '');
        reader.readAsDataURL(file);
      });
      const body = await api('/v1/attachments', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: slot, filename: file.name, data }),
      });
      if (currentSlot() === slot) staged.push(body.attachment);
    } catch (err) {
      rejected.push(`${file.name}: ${err.message}`);
    }
  }
  renderStaged();
  if (rejected.length) {
    notice(`${rejected.length} file${rejected.length === 1 ? ' was' : 's were'} not attached.`,
           'warn', rejected.join(' • '));
  }
}

/* The native picker returns records the shell already stored, so this only
 * merges them into the list the composer is showing. */
async function stageFromNative() {
  try {
    const result = await window.pywebview.api.choose_files();
    for (const record of result.accepted || []) staged.push(record);
    renderStaged();
    for (const bad of result.rejected || []) {
      notice(`${bad.filename || 'That file'} was not attached.`, 'warn', bad.reason);
    }
  } catch (err) {
    notice('The file picker could not be opened.', 'error', err.message);
  }
}

function pickFiles() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.choose_files) {
    stageFromNative();
  } else {
    $('file-input').click();
  }
}

/* ---- the + menu ------------------------------------------------------- */

function closePlusMenu() {
  if (!plusMenu) return;
  plusMenu.remove();
  plusMenu = null;
  const button = $('plus-btn');
  if (button) button.setAttribute('aria-expanded', 'false');
}

function openPlusMenu() {
  closePlusMenu();
  const button = $('plus-btn');
  const menu = document.createElement('div');
  menu.className = 'plus-menu';
  menu.setAttribute('role', 'menu');

  const entry = (name, sub, iconName, handler, state) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.setAttribute('role', 'menuitem');
    if (state) b.dataset.state = state;
    const glyph = document.createElement('span');
    glyph.append(icon(iconName));
    const text = document.createElement('span');
    const title = document.createElement('span');
    title.className = 'm-name';
    title.textContent = name;
    text.append(title);
    if (sub) {
      const s = document.createElement('span');
      s.className = 'm-sub';
      s.textContent = sub;
      text.append(s);
    }
    b.append(glyph, text);
    b.onclick = () => { closePlusMenu(); handler(); };
    menu.append(b);
    return b;
  };

  const files = document.createElement('p');
  files.className = 'menu-label';
  files.textContent = 'Attach';
  menu.append(files);
  entry('Add files…', 'Images, PDFs and documents from this computer',
        'paperclip', pickFiles);

  const skillLabel = document.createElement('p');
  skillLabel.className = 'menu-label';
  skillLabel.textContent = 'Skills';
  menu.append(skillLabel);
  for (const cap of capabilities) {
    if (cap.kind === 'default') continue;
    entry(cap.name,
          cap.state === 'available' ? cap.summary : cap.detail,
          cap.icon, () => chooseSkill(cap.id),
          cap.state === 'available' ? 'available' : 'unavailable');
  }
  if (selectedSkill()) {
    entry('Plain request', 'Remove the selected skill', 'chat',
          () => chooseSkill(null));
  }

  document.body.append(menu);
  const rect = button.getBoundingClientRect();
  const height = menu.getBoundingClientRect().height;
  menu.style.left = `${Math.round(rect.left)}px`;
  menu.style.top = `${Math.round(Math.max(8, rect.top - height - 6))}px`;
  plusMenu = menu;
  button.setAttribute('aria-expanded', 'true');
  menu.querySelector('button').focus();
}

/* ---- conversation management ----------------------------------------- */

const NEW_CHAT_DRAFT = '__new__';
let searchTimer = null;
let draftTimer = null;
let draftVersion = 0;
let draftReady = false;
// ponytail: serialize saves in this browser; concurrent-tab editing is not merged.
let draftWrites = Promise.resolve();
let openMenu = null;

/* Drafts live in coordinator state, so they survive a refresh or restart.
 * They are never sent to the model and never appear in search or export. */
async function loadDraft(id) {
  const input = $('input');
  if (!input) return;
  const version = ++draftVersion;
  draftReady = false;
  input.value = '';
  if ($('draft-mark')) $('draft-mark').hidden = true;
  await draftWrites.catch(() => {});
  if (chatId !== id || draftVersion !== version) return;
  try {
    const { text } = await api(`/v1/draft?chat_id=${encodeURIComponent(id || NEW_CHAT_DRAFT)}`);
    if (chatId !== id || draftVersion !== version) return;
    input.value = text || '';
    draftReady = true;
    if ($('draft-mark')) $('draft-mark').hidden = !text;
  } catch (err) {
    if (chatId === id && draftVersion === version)
      notice('Could not restore this draft.', 'error', err.message);
  }
}

function saveDraftSoon(immediate = false) {
  const input = $('input');
  if (!input || !draftReady) return draftWrites;
  clearTimeout(draftTimer);
  const body = JSON.stringify({ chat_id: chatId || NEW_CHAT_DRAFT, text: input.value });
  const save = () => {
    draftWrites = draftWrites.catch(() => {}).then(() => api('/v1/draft', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body,
    }));
    draftWrites.catch((err) => notice('Draft could not be saved.', 'error', err.message));
    return draftWrites;
  };
  if (immediate) return save();
  draftTimer = setTimeout(save, 600);
  return draftWrites;
}

function closeMenu() {
  if (openMenu) { openMenu.remove(); openMenu = null; }
}

function confirmDialog(title, body, danger) {
  return new Promise((resolve) => {
    const dlg = document.createElement('dialog');
    dlg.className = 'confirm';
    const h = document.createElement('h2'); h.textContent = title;
    const p = document.createElement('p'); p.textContent = body;
    const row = document.createElement('div'); row.className = 'row';
    const cancel = document.createElement('button');
    cancel.className = 'btn'; cancel.textContent = 'Cancel';
    const ok = document.createElement('button');
    ok.className = 'btn'; ok.textContent = danger;
    if (danger) ok.dataset.danger = '1';
    row.append(cancel, ok);
    dlg.append(h, p, row);
    document.body.append(dlg);
    const done = (v) => { dlg.close(); dlg.remove(); resolve(v); };
    cancel.onclick = () => done(false);
    ok.onclick = () => done(true);
    dlg.addEventListener('cancel', (e) => { e.preventDefault(); done(false); });
    dlg.showModal();
    cancel.focus();                    // Cancel focused, per the destructive-action rule
  });
}

function rowMenu(anchor, chat) {
  closeMenu();
  const menu = document.createElement('div');
  menu.className = 'row-menu';
  menu.setAttribute('role', 'menu');
  const rect = anchor.getBoundingClientRect();
  menu.style.left = `${Math.round(rect.left)}px`;
  menu.style.top = `${Math.round(rect.bottom + 4)}px`;

  const item = (label, fn, danger) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.setAttribute('role', 'menuitem');
    b.textContent = label;
    if (danger) b.dataset.danger = '1';
    b.onclick = async () => { closeMenu(); await fn(); };
    menu.append(b);
    return b;
  };

  item('Rename', () => startRename(chat));
  item(chat.pinned ? 'Unpin' : 'Pin', async () => {
    await api('/v1/chat/pin', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chat.chat_id, pinned: !chat.pinned }),
    }).catch((e) => notice('Could not change the pin.', 'error', e.message));
    loadChats();
  });
  item('Export as Markdown', () => downloadExport(chat, 'md'));
  item('Export as plain text', () => downloadExport(chat, 'txt'));
  const remove = item('Delete chat', () => deleteChat(chat), true);
  remove.disabled = true;
  remove.title = 'Checking for unfinished work…';
  api(`/v1/jobs?chat_id=${encodeURIComponent(chat.chat_id)}`).then(({ jobs }) => {
    const busy = jobs.some((j) => !['completed', 'failed', 'cancelled', 'denied', 'interrupted'].includes(j.state));
    remove.disabled = busy;
    remove.title = busy ? 'Stop the response before deleting this chat.' : '';
    remove.textContent = busy ? 'Delete chat — stop the response first' : 'Delete chat';
  }).catch(() => { remove.title = 'Could not check this chat. Reopen the menu to retry.'; });

  document.body.append(menu);
  openMenu = menu;
  menu.querySelector('button').focus();
}

async function deleteChat(chat) {
    const yes = await confirmDialog(
      `Delete “${chat.title}”?`,
      'Its messages and run history will be removed. This cannot be undone.',
      'Delete chat');
    if (!yes) return;
    try {
      await api('/v1/chat/delete', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chat.chat_id }),
      });
    } catch (err) {
      notice('Could not delete the chat.', 'error', err.message);
      return;
    }
    if (chat.chat_id === chatId) {
      clearTimeout(draftTimer);
      draftReady = false;
      newChat();
    }
    loadChats();
}

/* Export is an explicit download of saved history. The link is created,
 * clicked and revoked in one gesture; nothing is fetched remotely. */
async function downloadExport(chat, fmt) {
  try {
    const url = `/v1/export?chat_id=${encodeURIComponent(chat.chat_id)}&format=${fmt}`;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const blob = await resp.blob();
    const disposition = resp.headers.get('Content-Disposition') || '';
    const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
    const name = encoded ? decodeURIComponent(encoded)
      : disposition.match(/filename="([^"]+)"/)?.[1] || `conversation.${fmt}`;
    const href = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = href; a.download = name;
    document.body.append(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(href);
  } catch (err) {
    notice('Could not export this conversation.', 'error', err.message);
  }
}

function startRename(chat) {
  const row = document.querySelector(`[data-chat="${chat.chat_id}"]`);
  if (!row) return;
  const input = document.createElement('input');
  input.className = 'rename-input';
  input.value = chat.title;              // current title prefilled
  input.setAttribute('aria-label', 'Rename conversation');
  const button = row.querySelector('.nav-item');
  button.replaceWith(input);
  input.focus();
  input.select();
  const finish = async (save) => {
    if (!save) { loadChats(); return; }
    try {
      await api('/v1/chat/rename', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chat.chat_id, title: input.value }),
      });
    } catch (err) {
      notice('Could not rename this conversation.', 'error', err.message);
    }
    loadChats();
  };
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); finish(true); }
    if (e.key === 'Escape') { e.preventDefault(); finish(false); }
  });
  input.addEventListener('blur', () => finish(true));
}

function chatRow(chat, snippet) {
  const row = document.createElement('div');
  row.className = 'chat-row';
  row.dataset.chat = chat.chat_id;

  const open = document.createElement('button');
  open.className = 'nav-item';
  open.type = 'button';
  if (chat.chat_id === chatId) open.setAttribute('aria-current', 'true');
  if (chat.pinned) {
    const pin = document.createElement('span');
    pin.className = 'pin-mark';
    pin.textContent = '📌';
    pin.title = 'Pinned';
    open.append(pin);                  // a mark, not colour alone
  }
  const title = document.createElement('span');
  title.className = 'title';
  title.textContent = chat.title;
  open.append(title);
  if (snippet) {
    const s = document.createElement('span');
    s.className = 'snippet';
    s.textContent = snippet;           // escaped as text, never markup
    open.append(s);
  }
  open.onclick = () => openChat(chat.chat_id);

  const menu = document.createElement('button');
  menu.className = 'row-menu-btn';
  menu.type = 'button';
  menu.textContent = '⋯';
  menu.setAttribute('aria-label', `Actions for ${chat.title}`);
  menu.setAttribute('aria-haspopup', 'menu');
  menu.onclick = (e) => { e.stopPropagation(); rowMenu(menu, chat); };

  row.append(open, menu);
  return row;
}

async function runSearch(term) {
  const state = $('search-state');
  const list = $('chat-list');
  if (!term.trim()) { state.hidden = true; loadChats(); return; }
  state.hidden = false;
  state.textContent = 'Searching…';
  try {
    const { results } = await api(`/v1/search?q=${encodeURIComponent(term)}`);
    if (!results.length) {
      state.textContent = `No conversations match “${term}”.`;
      list.replaceChildren();
      return;
    }
    state.textContent = `${results.length} match${results.length === 1 ? '' : 'es'}`;
    list.replaceChildren();
    for (const r of results) {
      list.append(chatRow(
        { chat_id: r.chat_id, title: r.title, pinned: r.pinned },
        r.field === 'title' ? null : `${r.field}: ${r.snippet}`));
    }
  } catch (err) {
    state.textContent = `Search failed: ${err.message}`;
    list.replaceChildren();
  }
}

async function loadChats() {
  const { chats } = await api('/v1/chats');
  const list = $('chat-list');
  list.replaceChildren();
  for (const c of chats) list.append(chatRow(c));
}

/* Only the newest openChat() may commit.
 *
 * Comparing chatId alone cannot tell two concurrent loads of the SAME chat
 * apart, so a slower earlier response could overwrite a newer render. Each
 * invocation takes the next number and checks it still holds it. */
let openGeneration = 0;

/* Optional per-message extras are parsed defensively: one malformed field is
 * a missing note, never a missing message. */
function messageNote(raw) {
  if (!raw) return null;
  let message;
  try {
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
    message = parsed && typeof parsed.message === 'string' ? parsed.message : null;
  } catch { message = null; }
  if (!message) return null;
  const note = document.createElement('p');
  note.className = 'chip-caution';
  note.textContent = message;
  return note;
}

/* Build the whole replacement view off-screen, then swap it in once. */
function buildThread(messages) {
  const host = document.createDocumentFragment();
  if (!messages.length) {
    turn('assistant', 'No messages in this conversation yet.', null, true, host);
    return host;
  }
  for (const m of messages) {
    const attachments = Array.isArray(m.attachments) ? m.attachments : null;
    const box = turn(m.role, typeof m.text === 'string' ? m.text : '',
                     attachments, false, host, m.skill_id,
                     Array.isArray(m.artifacts) ? m.artifacts : null);
    const note = messageNote(m.error_json);
    if (note) box.append(note);
  }
  return host;
}

async function openChat(id) {
  const generation = ++openGeneration;
  const current = () => openGeneration === generation && chatId === id;
  const switched = chatId !== id;
  if (switched) {
    saveDraftSoon(true);                  // capture and flush the old chat first
    chatId = id;
    publishSlot();
    loadDraft(id);
    loadStaged();
    renderSkill();
  }
  let messages;
  try {
    ({ messages } = await api(`/v1/messages?chat_id=${id}`));
  } catch (err) {
    // The pane that is already on screen is the last thing known to be true.
    // Keep it and say the refresh failed; never replace it with nothing.
    if (current()) notice('Could not refresh this conversation.', 'error', err.message);
    return;
  }
  if (!current()) return;

  let replacement;
  try {
    replacement = buildThread(messages);
  } catch (err) {
    if (current()) notice('Could not display this conversation.', 'error', err.message);
    return;
  }
  if (!current()) return;
  // The only step that touches the live thread, and it cannot throw.
  activeJob = null;
  streamBox = null;
  lastSequence = 0;
  pendingEvents = new Map();
  const thread = $('thread');
  thread.replaceChildren(replacement);
  // Only a real switch returns to the latest turn. A refresh of the chat
  // already on screen leaves the reader where they were.
  if (switched) following = true;
  maybeFollow();

  // Restart reconciliation is visible here: a job that was interrupted keeps
  // its record, and its conversation still loads. Everything from here is the
  // technical rail: a failure below leaves the conversation readable.
  let jobs;
  try {
    ({ jobs } = await api(`/v1/jobs?chat_id=${id}`));
  } catch (err) {
    if (current()) console.error('job history unavailable:', err.message);
    return;
  }
  if (!current()) return;
  const last = jobs[0];
  if (last) {
    jobState = last.state;
    renderLife(last.state);
    // Replay the recorded events so the rail shows what actually happened
    // rather than looking as though nothing did.
    $('events').replaceChildren();
    deltaCount = 0; deltaChars = 0;
    const detail = await api(`/v1/job?job_id=${last.job_id}`).catch(() => null);
    if (!current()) return;
    if (detail) for (const ev of detail.events) pushEvent(ev);
    lastSequence = detail?.events.at(-1)?.sequence || 0;
    const attempt = detail?.attempts.at(-1);
    if (attempt?.output_text && !messages.some((m) =>
      m.job_id === last.job_id && m.role === 'assistant')) {
      streamBox = turn('assistant', attempt.output_text);
    }
    activeJob = last.job_id;
    jobState = detail?.job.state || last.state;
    renderLife(jobState);
    setJobChip(jobState);
    // Reopening an active conversation restores Stop, because the job is still
    // running on this computer whether or not this window was watching it.
    setActive(jobState);
    refreshAttempt();
    replayEvents();
  } else {
    renderLife(null);
    setJobChip(null);
    setActive(null);
    $('events').replaceChildren();
    $('attempt-kv').replaceChildren();
  }
  loadChats();
}

async function send(text, { draftText = null } = {}) {
  const sourceId = chatId, version = draftVersion;
  await saveDraftSoon(true);             // no delayed old save may follow acceptance
  let targetId = sourceId;
  if (!targetId) {
    const { chat_id } = await api('/v1/chats', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: text.slice(0, 60) }),
    });
    targetId = chat_id;
  }
  const skill = selectedSkill();
  const { job_id } = await api('/v1/messages', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: targetId, text,
      draft_id: sourceId || NEW_CHAT_DRAFT, draft_text: draftText ?? text,
      // The chosen skill is submitted with the request and stored on the job.
      // It is not left as state only this page knows about. The document
      // choices travel the same way, and only when they apply.
      skill_id: skill ? skill.id : undefined,
      output_format: skill?.id === 'write-document' ? outputFormat : undefined,
      doc_workflow: skill?.id === 'write-document' ? docWorkflow : undefined }),
  });
  if (chatId !== sourceId || (sourceId === null && draftVersion !== version)) {
    loadChats();
    return;
  }
  if (draftText !== null && draftVersion === version && $('input').value === draftText) {
    $('input').value = '';
    ++draftVersion;
    autogrow($('input'));
    if ($('draft-mark')) $('draft-mark').hidden = true;
  }
  // The selection was made against the draft slot and is bound to the request
  // the coordinator just accepted; move any local record with it.
  const sentFiles = staged.length;
  staged = [];
  renderStaged();
  if (skill && targetId !== (sourceId || NEW_DRAFT_SLOT)) {
    skillByChat.delete(NEW_DRAFT_SLOT);
    skillByChat.set(targetId, skill);
  }
  chatId = targetId;
  publishSlot();
  // Read persisted messages/output after acceptance; generation may already
  // have emitted events before the POST response reached this browser.
  await openChat(chatId);
  refreshContext();
  if (sentFiles) {
    notice(`${sentFiles} file${sentFiles === 1 ? '' : 's'} went with your request.`,
           skill ? 'ok' : 'warn',
           skill
             ? `${skill.name} reads only the files sent with this request.`
             : 'Plain Chat reads only the files sent with this request on this '
               + 'computer, and tells you if any file could not be read.');
  }
}

function newChat() {
  saveDraftSoon(true);
  chatId = null; activeJob = null;
  streamBox = null; jobState = null; lastSequence = 0;
  pendingEvents = new Map();
  publishSlot();
  setActive(null);
  setJobChip(null);
  $('attempt-kv').replaceChildren();
  $('thread').replaceChildren();
  $('events').replaceChildren();
  deltaCount = 0; deltaChars = 0;
  renderLife(null);
  turn('assistant', 'New conversation. Ask a question below to start.', null, true);
  loadDraft(null);
  loadStaged();
  renderSkill();
}

/* ---------------------------------------------------------------- Code --- */

/* The Code surface. Enforcement lives in the coordinator: this file sends an
 * opaque repository id, validated relative paths, a request in words, a mode
 * from a fixed list, and an approval id plus yes/no. It never sends a
 * filesystem path, a digest, an approved flag or replacement content, and it
 * never decides whether something is allowed. */

let codeState = null;
let repoFiles = [];
let selectedPaths = new Set();
let proposing = false;
/* Only the newest activation may commit, and only for the repository it was
 * started for. Chat learned this lesson first; Code needs the same guard,
 * because a late file list from one project must never appear under another. */
let codeGeneration = 0;
let activeRepo = null;

const nativeBridge = () => (window.pywebview && window.pywebview.api) || null;

function codeApi(path, body) {
  return api(path, body === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/* Switching, connecting or reconnecting a project starts from nothing: a
 * selection made in one folder must never be submitted against another, even
 * when both contain a file of the same name. */
function resetRepositoryState() {
  selectedPaths = new Set();
  repoFiles = [];
  // The open file belonged to the project being left. Keeping it on screen
  // would show one project's file above another project's work.
  if (typeof closeViewer === 'function') closeViewer(false);
  // Results belong to the folder they came from. A diff or an approval from
  // the previous project must not sit above the new one's composer.
  if (typeof clearCodeResults === 'function') clearCodeResults();
  if ($('code-context')) {
    $('code-context').replaceChildren();
    $('code-context').hidden = true;
  }
}

/* `skipFiles` matters after an approved listing: the files have just been
 * fetched with that one-shot approval, and asking again without one would
 * raise a fresh approval card and throw the answer away. */
async function loadCodeState(repoId, { reset = false, skipFiles = false } = {}) {
  if (!codeConversation) return codeState;
  const generation = ++codeGeneration;
  if (reset) resetRepositoryState();
  const parts = [];
  if (repoId) parts.push(`repo_id=${encodeURIComponent(repoId)}`);
  // Scoped, so a fresh conversation never inherits the project's last
  // proposal and a refresh cannot cross conversations.
  if (codeConversation) {
    parts.push(`conversation_id=${encodeURIComponent(codeConversation)}`);
  }
  const query = parts.length ? `?${parts.join('&')}` : '';
  let next;
  try {
    next = await api(`/v1/code/state${query}`);
  } catch (err) {
    if (codeGeneration === generation) {
      notice('Code could not be refreshed.', 'error', err.message);
    }
    return codeState;
  }
  if (codeGeneration !== generation) return codeState;
  if (next.active !== activeRepo) {
    // The coordinator chose a different project than the one on screen.
    resetRepositoryState();
    activeRepo = next.active;
  }
  codeState = next;

  // Awaited, not fired and forgotten: the listing can need approval, and that
  // approval has to reach the same render as the rest of the state.
  if (codeState.active && !skipFiles) {
    const listing = await loadRepoFiles(codeState.active, generation);
    if (codeGeneration !== generation) return codeState;
    if (listing && listing.needs_approval) {
      const known = new Set(codeState.pending_approvals.map((a) => a.approval_id));
      if (!known.has(listing.needs_approval.approval_id)) {
        codeState.pending_approvals = [...codeState.pending_approvals,
                                       listing.needs_approval];
      }
    }
  }
  renderCode();
  return codeState;
}

async function connectRepository() {
  const bridge = nativeBridge();
  if (!bridge || !bridge.choose_repository) {
    notice('Connecting a folder needs the Refinix application.', 'warn',
           'The native folder picker is only available in the desktop app. '
           + 'There is deliberately no box to type a path into.');
    return;
  }
  let result;
  try {
    result = await bridge.choose_repository();
  } catch (err) {
    notice('The folder picker could not be opened.', 'error', err.message);
    return;
  }
  if (!result || result.cancelled) return;
  if (result.error) {
    notice('That folder was not connected.', 'error', result.error);
    return;
  }
  // A newly connected folder is a repository change like any other.
  await activateRepository(result.repository.repo_id);
}

async function persistCodeContext(repoId, openPath = null) {
  if (!codeConversation) return null;
  const updated = await codeApi('/v1/code/conversation/context', {
    conversation_id: codeConversation,
    repo_id: repoId || undefined,
    open_path: openPath || undefined,
  });
  const index = codeConversations.findIndex((c) => c.chat_id === codeConversation);
  if (index >= 0) codeConversations[index] = updated;
  renderConversationHead();
  return updated;
}

async function activateRepository(repoId) {
  try {
    await persistCodeContext(repoId, null);
  } catch (err) {
    notice('That conversation could not switch projects.', 'error', err.message);
    return;
  }
  await loadCodeState(repoId, { reset: true });
}

/* Returns the response so the caller can render a listing approval with the
 * rest of the state. Commits nothing once a newer activation has started. */
async function loadRepoFiles(repoId, generation, approvalId) {
  const parts = [`repo_id=${encodeURIComponent(repoId)}`,
                 `conversation_id=${encodeURIComponent(codeConversation)}`];
  if (approvalId) parts.push(`approval_id=${encodeURIComponent(approvalId)}`);
  const query = `?${parts.join('&')}`;
  let body;
  try {
    body = await api(`/v1/code/files${query}`);
  } catch (err) {
    if (codeGeneration !== generation) return null;
    repoFiles = [];
    notice('The file list could not be read.', 'error', err.message);
    return null;
  }
  if (codeGeneration !== generation || repoId !== activeRepo) return null;
  repoFiles = body.needs_approval ? [] : (body.files || []);
  return body;
}

/* Access lives in the composer now, as one pill beside `+`. The large Access
 * mode card is gone: a permanent panel restating the same three choices took
 * the work area and told the reader nothing they had not already chosen. */
const MODE_LABELS = {
  ask: 'Ask for approval',
  partial: 'Approve for me',
  full: 'Full access',
};

let modeMenu = null;

function activeRepository() {
  if (!codeState) return null;
  return codeState.repositories.find((r) => r.repo_id === codeState.active) || null;
}

function renderModePill() {
  const pill = $('mode-pill');
  if (!pill || !codeState) return;
  const repo = activeRepository();
  pill.hidden = !repo;
  if (!repo) return;
  const label = MODE_LABELS[repo.mode] || repo.mode;
  $('mode-name').textContent = label;
  pill.dataset.mode = repo.mode;
  pill.setAttribute('aria-label', `Access: ${label}. Change it.`);
}

function closeModeMenu(returnFocus) {
  if (!modeMenu) return;
  modeMenu.remove();
  modeMenu = null;
  const pill = $('mode-pill');
  if (pill) {
    pill.setAttribute('aria-expanded', 'false');
    if (returnFocus) pill.focus();
  }
}

function openModeMenu() {
  closeModeMenu(false);
  const pill = $('mode-pill');
  const repo = activeRepository();
  if (!pill || !repo) return;
  const menu = document.createElement('div');
  menu.className = 'plus-menu mode-menu';
  menu.setAttribute('role', 'menu');
  for (const mode of codeState.modes) {
    const button = document.createElement('button');
    button.type = 'button';
    button.setAttribute('role', 'menuitemradio');
    button.setAttribute('aria-checked', String(repo.mode === mode.id));
    const glyph = document.createElement('span');
    glyph.textContent = repo.mode === mode.id ? '✓' : '';
    const text = document.createElement('span');
    const name = document.createElement('span');
    name.className = 'm-name';
    // Codex-style words for the same enforced backend modes; the ids are
    // unchanged, so nothing about what is allowed moves with the label.
    name.textContent = MODE_LABELS[mode.id] || mode.label;
    const sub = document.createElement('span');
    sub.className = 'm-sub';
    sub.textContent = mode.summary;
    text.append(name, sub);
    button.append(glyph, text);
    button.onclick = () => { closeModeMenu(true); changeMode(mode); };
    menu.append(button);
  }
  document.body.append(menu);
  const rect = pill.getBoundingClientRect();
  const height = menu.getBoundingClientRect().height;
  menu.style.left = `${Math.round(Math.max(8, rect.left))}px`;
  menu.style.top = `${Math.round(Math.max(8, rect.top - height - 6))}px`;
  modeMenu = menu;
  pill.setAttribute('aria-expanded', 'true');
  menu.querySelector('button').focus();
}

async function changeMode(mode) {
  if (!codeState?.active) return;
  if (mode.confirm) {
    const yes = await confirmDialog(
      'Turn on Full access for this folder?',
      // The coordinator's own sentence, so the warning cannot drift from the
      // policy it describes. It names the sandbox tests that do not run on
      // this device, which is the part a person most needs to have read.
      (mode.confirm_note ? `${mode.confirm_note} ` : '')
      + 'It still cannot run commands, use Git, install anything, create or '
      + 'delete files, or work outside this folder.',
      'Turn on Full access');
    if (!yes) return;
  }
  try {
    await codeApi('/v1/code/mode', { repo_id: codeState.active, mode: mode.id });
  } catch (err) {
    notice('That mode could not be set.', 'error', err.message);
    return;
  }
  // Nothing is shown as active until the coordinator confirms it persisted.
  await loadCodeState(codeState.active);
}

/* Results are turns, not panels. Each one carries its own diff, its own
 * approval and its own outcome, so the information the dashboard used to hold
 * is still here — attached to the operation it describes. */
function codeTurn(build) {
  const article = document.createElement('article');
  article.className = 'turn turn-agent';
  build(article);
  const thread = $('thread');
  if (thread) {
    thread.append(article);
    if (following) thread.scrollTop = thread.scrollHeight;
  }
  return article;
}

function approvalCard(approval) {
  const card = document.createElement('section');
  card.className = 'card approval-card';
  const head = document.createElement('div');
  head.className = 'card-head';
  const title = document.createElement('h2');
  title.textContent = {
    'canonical.write': 'Approve this change?',
    'repo.list': 'Approve listing this project\u2019s files?',
  }[approval.action] || 'Approve reading these files?';
  const chip = document.createElement('span');
  chip.className = 'chip chip-caution';
  chip.textContent = 'waiting for you';
  head.append(title, chip);
  card.append(head);

  const facts = document.createElement('dl');
  facts.className = 'facts';
  // A malformed approval must not take the whole panel down with it; the
  // fields it does carry are still worth showing.
  const detail = approval.detail || {};
  const rows = [
    ['Project', detail.repo_name || '—'],
    ['Files', (detail.paths || []).join(', ') || approval.target],
    ['Expires', approval.expires_at],
  ];
  for (const [k, v] of rows) {
    const div = document.createElement('div');
    const dt = document.createElement('dt'); dt.textContent = k;
    const dd = document.createElement('dd'); dd.textContent = v;
    div.append(dt, dd);
    facts.append(div);
  }
  card.append(facts);

  const actions = document.createElement('div');
  actions.className = 'card-actions';
  const approve = document.createElement('button');
  approve.className = 'btn btn-primary';
  approve.textContent = 'Approve';
  approve.onclick = () => decideApproval(approval, true);
  const deny = document.createElement('button');
  deny.className = 'btn btn-stop';
  deny.textContent = 'Deny';
  deny.onclick = () => decideApproval(approval, false);
  actions.append(approve, deny);
  card.append(actions);
  return card;
}

async function decideApproval(approval, approved) {
  const viewTarget = approval.action === 'repo.view' ? {
    repo_id: approval.repo_id,
    path: (approval.detail?.paths || [])[0] || approval.target,
  } : null;
  if (approved && approval.action === 'repo.view'
      && (!viewTarget.repo_id || !viewTarget.path)) {
    notice('That file approval is incomplete.', 'error',
           'Open the file again; this approval was not consumed.');
    return;
  }
  try {
    await codeApi('/v1/code/decision', {
      approval_id: approval.approval_id, approved,
      conversation_id: approval.conversation_id || codeConversation || undefined,
    });
  } catch (err) {
    notice('That decision could not be recorded.', 'error', err.message);
    return;
  }
  if (!approved) {
    notice(approval.action === 'canonical.write'
      ? 'Nothing was written.' : 'No file was read.', 'warn',
      'A denied request stays denied.');
    await loadCodeState(codeState.active);
    return;
  }
  // An approved decision is carried out by repeating THAT operation with the
  // approval id. The coordinator matches action and digest, so retrying the
  // wrong operation would simply fail — each action returns to its own path.
  if (approval.action === 'canonical.write') {
    await applyProposal(approval.proposal_id || (approval.detail || {}).proposal_id
      || codeState?.proposal?.proposal_id, approval.approval_id);
    return;
  }
  if (approval.action === 'repo.view') {
    // Reopen the exact file this approval was raised for. Falling through to
    // proposeChange here asked the model to change a file the person only
    // wanted to look at.
    await openFileInViewer(viewTarget.repo_id, viewTarget.path,
                           approval.approval_id);
    await loadCodeState(codeState.active, { skipFiles: true });
    return;
  }
  if (approval.action === 'repo.list') {
    const generation = ++codeGeneration;
    const listing = await loadRepoFiles(codeState.active, generation,
                                        approval.approval_id);
    // Refresh the rest of the state, but keep the listing this approval just
    // bought: re-requesting it would only raise another approval.
    await loadCodeState(activeRepo, { skipFiles: !!(listing && listing.files) });
    return;
  }
  await proposeChange(approval.approval_id);
}

function proposalCard(proposal) {
  const card = document.createElement('section');
  card.className = 'card';
  const head = document.createElement('div');
  head.className = 'card-head';
  const title = document.createElement('h2');
  title.textContent = 'Proposed change';
  const chip = document.createElement('span');
  chip.className = 'chip ' + (proposal.state === 'applied' ? 'chip-enforced'
    : proposal.state === 'proposed' ? 'chip-unknown' : 'chip-caution');
  chip.textContent = proposal.state.replace(/_/g, ' ');
  head.append(title, chip);
  card.append(head);

  const summary = document.createElement('p');
  summary.className = 'card-lead';
  summary.textContent = proposal.summary;    // model text, as a text node only
  card.append(summary);

  if (!proposal.edits.length) {
    const none = document.createElement('p');
    none.className = 'lbl';
    none.textContent = 'The model proposed no file changes. Nothing was written.';
    card.append(none);
    return card;
  }

  for (const edit of proposal.edits) {
    const block = document.createElement('div');
    block.className = 'diff-block';
    const path = document.createElement('p');
    path.className = 'diff-path';
    path.textContent = edit.path;
    const state = document.createElement('span');
    state.className = 'lbl';
    state.textContent = edit.state === 'proposed' ? '' : ` — ${edit.state}`;
    if (edit.detail) state.textContent += `: ${edit.detail}`;
    path.append(state);
    const pre = document.createElement('pre');
    pre.className = 'diff';
    // The complete diff, never shortened, and inserted as text so model
    // output can never become markup.
    pre.textContent = edit.diff;
    block.append(path, pre);
    card.append(block);
  }

  const note = document.createElement('p');
  note.className = 'lbl';
  note.textContent = 'This diff is for you to review, and it shows everything '
    + 'Apply would write. A valid proposal shows the workflow ran; it is not '
    + 'evidence that the change is correct.';
  card.append(note);

  const local = codeState?.execution_target === 'this_device';
  if (local) {
    // Said before the buttons, in the coordinator's words. A local change was
    // never inside the Ubuntu sandbox and this line must never imply it was.
    const untested = document.createElement('p');
    untested.className = 'prose-note';
    untested.dataset.state = 'unvalidated';
    untested.textContent = codeState.validation_note
      || 'Not sandbox tested — local device mode';
    card.append(untested);
  }

  if (proposal.state === 'proposed') {
    const actions = document.createElement('div');
    actions.className = 'card-actions';
    const validation = codeState?.validation;
    const passed = !!(validation?.observed && validation?.passed
      && validation.patch_sha256 === proposal.digest);
    const action = document.createElement('button');
    action.className = 'btn btn-primary';
    // A local change is applied after review here; a distributed one still
    // has to come back from the sandbox first. One button, two honest labels.
    action.textContent = local ? 'Accept and apply'
      : passed ? 'Apply this change' : 'Validate in sandbox';
    action.onclick = () => (local || passed)
      ? applyProposal(proposal.proposal_id, null)
      : validateProposal(proposal.proposal_id);
    actions.append(action);
    const reject = document.createElement('button');
    reject.className = 'btn';
    reject.textContent = 'Reject';
    reject.onclick = () => rejectProposal(proposal.proposal_id);
    actions.append(reject);
    if (validation && !local) {
      const result = document.createElement('span');
      result.className = 'lbl';
      result.textContent = passed
        ? `Sandbox passed ${validation.tests_run} test(s).`
        : `Sandbox did not pass${validation.detail ? `: ${validation.detail}` : '.'}`;
      actions.append(result);
    }
    card.append(actions);
  }

  // Also after a partial apply: some files really did change, and those are
  // exactly the ones a person needs to be able to put back.
  if (['applied', 'partially_applied'].includes(proposal.state)
      && codeState?.can_undo) {
    const actions = document.createElement('div');
    actions.className = 'card-actions';
    const undo = document.createElement('button');
    undo.className = 'btn';
    undo.textContent = 'Undo this change';
    undo.onclick = () => undoProposal(proposal.proposal_id);
    actions.append(undo);
    const note = document.createElement('span');
    note.className = 'lbl';
    note.textContent = 'Restores the files Refinix replaced, if nothing else '
      + 'has changed them since.';
    actions.append(note);
    card.append(actions);
  }
  return card;
}

/* Reject writes nothing and leaves the open file exactly as it is. */
async function rejectProposal(proposalId) {
  try {
    await codeApi('/v1/code/reject', {
      repo_id: codeState.active, proposal_id: proposalId,
      conversation_id: codeConversation });
  } catch (err) {
    notice('That change could not be rejected.', 'error', err.message);
    return;
  }
  await loadCodeState(codeState.active, { skipFiles: true });
}

async function undoProposal(proposalId) {
  let result;
  try {
    result = await codeApi('/v1/code/undo', {
      repo_id: codeState.active, proposal_id: proposalId,
      conversation_id: codeConversation });
  } catch (err) {
    // A failed Undo leaves everything on screen. Blanking the conversation or
    // the file because one request failed would lose the person's place.
    notice('That change could not be undone.', 'error', err.message);
    return;
  }
  const stale = (result.files || []).filter((f) => f.state === 'rejected_stale');
  if (stale.length) {
    notice('Some files changed after Refinix wrote them and were left alone.',
           'warn', stale.map((f) => f.path).join(', '));
  }
  await loadCodeState(codeState.active, { skipFiles: true });
  await refreshOpenFile();
}

/* After a write, the centre column is re-read from disk rather than being
 * shown the proposed text: what is on screen must be what is in the file. */
async function refreshOpenFile() {
  if (!openFile) return;
  const { repo_id: repoId, path } = openFile;
  try {
    const file = await api(`/v1/code/view?repo_id=${encodeURIComponent(repoId)}`
                           + `&path=${encodeURIComponent(path)}`
                           + `&conversation_id=${encodeURIComponent(codeConversation)}`);
    if (!openFile || openFile.path !== path) return;
    if (file.lines) {
      openFile = { repo_id: repoId, ...file };
      paintFile(file.lines);
    }
  } catch (err) {
    // Keep the last known content and say so. An empty viewer would read as
    // "the file is gone", which is a worse lie than a stale view.
    notice('The open file could not be re-read; showing the last version '
           + 'Refinix loaded.', 'warn', err.message);
  }
}

/* The audit is reference material, so it sits under Details rather than
 * occupying the work area. */
function renderAudit(rows) {
  const list = $('audit-list');
  if (!list) return;
  list.replaceChildren();
  for (const row of rows.slice(0, 20)) {
    const li = document.createElement('li');
    const text = document.createElement('span');
    const name = document.createElement('span');
    name.className = 'c-name';
    name.textContent = row.action;
    const detail = document.createElement('span');
    detail.className = 'c-detail';
    detail.textContent = [row.detail.path, row.detail.target, row.detail.reason]
      .filter(Boolean).join(' — ') || row.occurred_at;
    text.append(name, detail);
    const chip = document.createElement('span');
    chip.className = 'chip ' + ({
      applied: 'chip-enforced', approved: 'chip-enforced',
      allowed_automatically: 'chip-observed', awaiting_approval: 'chip-caution',
      denied: 'chip-fault', expired: 'chip-fault', rejected_stale: 'chip-fault',
      failed: 'chip-fault',
    }[row.outcome] || 'chip-unknown');
    chip.textContent = row.outcome.replace(/_/g, ' ');
    li.append(text, chip);
    list.append(li);
  }
}

function renderUnavailable(rows) {
  const list = $('unavailable-list');
  if (!list) return;
  list.replaceChildren();
  for (const row of rows) {
    const li = document.createElement('li');
    const text = document.createElement('span');
    text.className = 'c-detail';
    text.textContent = row.detail;
    li.append(text);
    list.append(li);
  }
}

function renderCode() {
  if (!codeState || !$('code-composer')) return;
  // One answer for the whole surface. Where the coordinator cannot keep a
  // folder bounded, nothing here is offered — not even a connect button that
  // would fail.
  const usable = codeState.code_supported !== false;
  const repo = activeRepository();
  const connected = usable && !!repo;

  const chooser = $('connect-btn');
  chooser.disabled = !usable;
  $('project-name').textContent = repo ? repo.name : 'Choose project';
  chooser.dataset.connected = String(!!repo);
  $('switch-btn').hidden = !repo;
  $('composer-box').hidden = !connected;
  $('plus-btn').disabled = !connected;
  renderModePill();

  renderExplorer();

  renderAudit(codeState.audit || []);
  renderUnavailable(codeState.unavailable || []);
  renderCodeContext();

  const intro = $('intro');
  if (intro) intro.hidden = connected;
  if (codeState.platform_note) {
    showCodeResult((article) => {
      const warn = document.createElement('p');
      warn.className = 'warn-line';
      warn.textContent = codeState.platform_note;
      article.append(warn);
    }, 'platform');
  }
  // Approvals appear where the work paused, and a proposal arrives as a result.
  for (const approval of codeState.pending_approvals || []) {
    showCodeResult((article) => article.append(approvalCard(approval)),
                   `approval:${approval.approval_id}`);
  }
  if (codeState.proposal) {
    showCodeResult((article) => article.append(proposalCard(codeState.proposal)),
                   `proposal:${codeState.proposal.proposal_id}:${codeState.proposal.state}:`
                   + `${codeState.validation?.validation_id || 'unvalidated'}`);
  }
}

/* Results accumulate like a conversation, but the same result is not appended
 * twice when the state is polled again. */
const shownResults = new Set();

function showCodeResult(build, key) {
  if (key) {
    if (shownResults.has(key)) return null;
    shownResults.add(key);
  }
  return codeTurn(build);
}

function clearCodeResults() {
  shownResults.clear();
  const thread = $('thread');
  if (!thread) return;
  const intro = $('intro');
  thread.replaceChildren(...(intro ? [intro] : []));
}

/* The selected files live in the composer, as chips beside `+`. Connecting a
 * folder never grants a whole-repository read: the selection stays explicit. */
function renderCodeContext() {
  const host = $('code-context');
  if (!host) return;
  const chosen = repoFiles.filter((f) => selectedPaths.has(f.path));
  host.replaceChildren(...chosen.map((file) => {
    const li = document.createElement('li');
    li.className = 'attachment';
    li.append(icon('code'));
    const name = document.createElement('span');
    name.className = 'a-name';
    name.textContent = file.path;
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'a-remove';
    remove.textContent = '×';
    remove.setAttribute('aria-label', `Remove ${file.path}`);
    remove.onclick = () => {
      selectedPaths.delete(file.path);
      renderCodeContext();
    };
    li.append(name, remove);
    return li;
  }));
  host.hidden = chosen.length === 0;
  renderSelectionHint();
  autogrow($('code-input'));
}

/* `+` opens the bounded file picker for this project. */
function openFileMenu() {
  closePlusMenu();
  const button = $('plus-btn');
  const menu = document.createElement('div');
  menu.className = 'plus-menu file-menu';
  menu.setAttribute('role', 'menu');

  const label = document.createElement('p');
  label.className = 'menu-label';
  label.textContent = `Files in this project (${repoFiles.length})`;
  menu.append(label);

  const filter = document.createElement('input');
  filter.className = 'chat-search';
  filter.type = 'search';
  filter.placeholder = 'Filter files';
  filter.setAttribute('aria-label', 'Filter files');
  menu.append(filter);

  const rows = document.createElement('div');
  rows.className = 'file-list';
  menu.append(rows);

  const draw = () => {
    const needle = filter.value.toLowerCase();
    rows.replaceChildren();
    const shown = repoFiles.filter((f) => !needle
      || f.path.toLowerCase().includes(needle)).slice(0, 300);
    if (!shown.length) {
      const empty = document.createElement('p');
      empty.className = 'lbl';
      empty.textContent = repoFiles.length
        ? 'No file matches that.'
        : 'No readable text files, or reading needs approval.';
      rows.append(empty);
      return;
    }
    for (const file of shown) {
      const row = document.createElement('label');
      row.className = 'file-row';
      const box = document.createElement('input');
      box.type = 'checkbox';
      box.checked = selectedPaths.has(file.path);
      box.addEventListener('change', () => {
        if (box.checked) selectedPaths.add(file.path);
        else selectedPaths.delete(file.path);
        renderCodeContext();
      });
      const name = document.createElement('span');
      name.className = 'file-path';
      name.textContent = file.path;
      row.append(box, name);
      rows.append(row);
    }
  };
  filter.addEventListener('input', draw);
  draw();

  document.body.append(menu);
  const rect = button.getBoundingClientRect();
  const height = menu.getBoundingClientRect().height;
  menu.style.left = `${Math.round(Math.max(8, rect.left))}px`;
  menu.style.top = `${Math.round(Math.max(8, rect.top - height - 6))}px`;
  plusMenu = menu;
  button.setAttribute('aria-expanded', 'true');
  filter.focus();
}

function renderSelectionHint() {
  const hint = $('selection-hint');
  if (!hint) return;
  hint.textContent = selectedPaths.size
    ? `${selectedPaths.size} file(s) selected`
    : 'No files selected';
  const send = $('code-send');
  if (send) send.disabled = proposing || !selectedPaths.size || !codeState?.active;
}

async function proposeChange(approvalId) {
  const input = $('code-input');
  const request = (input?.value || '').trim();
  if (!request || !codeState?.active) return;
  proposing = true;
  $('code-send').hidden = true;
  $('code-stop').hidden = false;
  setWorking(true);
  const status = $('code-status');
  status.hidden = false;
  status.textContent = 'Reading the selected files and asking the model on this computer…';
  try {
    const body = await codeApi('/v1/code/propose', {
      repo_id: codeState.active, request, paths: [...selectedPaths],
      approval_id: approvalId || undefined,
      // The request belongs to one Code conversation, so its job, proposal
      // and approval cannot surface under a different one.
      conversation_id: codeConversation || undefined,
      // Where this runs is chosen, never inferred. "The worker did not answer"
      // is not permission to write to someone's files without the sandbox.
      execution_target: executionTarget,
    });
    status.hidden = true;
    if (body.needs_approval) {
      notice('Refinix needs your approval before reading those files.', 'warn',
             'Nothing has been read or sent to the model yet.');
    }
  } catch (err) {
    status.hidden = false;
    status.textContent = err.message;
  } finally {
    proposing = false;
    $('code-send').hidden = false;
    $('code-stop').hidden = true;
    setWorking(false);
    await loadCodeState(activeRepo);
  }
}

async function applyProposal(proposalId, approvalId) {
  if (!proposalId || !codeState?.active) return;
  try {
    const body = await codeApi('/v1/code/apply', {
      repo_id: codeState.active, proposal_id: proposalId,
      approval_id: approvalId || undefined,
      conversation_id: codeConversation,
    });
    if (body.needs_approval) {
      notice('Refinix needs your approval before writing.', 'warn',
             'The file on disk has not changed.');
    } else if (body.state === 'applied') {
      notice(`${body.applied} file(s) updated.`, 'warn', body.atomicity);
    } else {
      notice(`${body.applied} of ${body.total} file(s) updated.`, 'error',
             body.results.filter((r) => r.state !== 'applied')
               .map((r) => `${r.path}: ${r.detail}`).join(' • '));
    }
  } catch (err) {
    // The conversation and the open file stay exactly as they were: a refused
    // or failed write changed nothing, and the screen should say so by not
    // changing either.
    notice('That change was not applied.', 'error', err.message);
  }
  await loadCodeState(activeRepo);
  // Re-read from disk, so the centre column shows the file rather than the
  // text that was proposed for it.
  await refreshOpenFile();
}

async function validateProposal(proposalId) {
  if (!proposalId || !codeState?.active) return;
  try {
    const result = await codeApi('/v1/code/validate', {
      repo_id: codeState.active, proposal_id: proposalId,
      conversation_id: codeConversation,
    });
    notice(result.passed ? 'Sandbox validation passed.' : 'Sandbox validation failed.',
           result.passed ? 'warn' : 'error',
           result.passed ? `${result.tests_run} test(s) ran.`
                         : (result.detail || result.stderr || 'No passing result was recorded.'));
  } catch (err) {
    notice('Sandbox validation could not run.', 'error', err.message);
  }
  await loadCodeState(activeRepo);
}

function wireCode() {
  wireConversationControls();
  $('connect-btn').addEventListener('click', connectRepository);
  $('switch-btn').addEventListener('click', connectRepository);
  $('code-composer').onsubmit = (e) => { e.preventDefault(); proposeChange(null); };
  wireAutogrow($('code-input'));
  const modePill = $('mode-pill');
  if (modePill) {
    modePill.addEventListener('click', (e) => {
      e.stopPropagation();
      if (modeMenu) closeModeMenu(true);
      else openModeMenu();
    });
  }
  $('code-stop').addEventListener('click', () => {
    if (codeState?.active) {
      codeApi('/v1/code/cancel', { repo_id: codeState.active }).catch(() => {});
    }
  });
  $('code-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && e.keyCode !== 229) {
      e.preventDefault();
      $('code-composer').requestSubmit();
    }
  });
  const pill = $('model-pill');
  if (pill) {
    pill.addEventListener('click', (e) => {
      e.stopPropagation();
      if (modelPopover) closeModelPopover(true);
      else openModelPopover();
    });
  }
  $('plus-btn').addEventListener('click', (e) => {
    e.stopPropagation();
    if (plusMenu) closePlusMenu();
    else openFileMenu();
  });
  initializeCode().catch((err) =>
    notice('Code could not load.', 'error', err.message));
}

/* ------------------------------------------------------------ Settings --- */

/* Cards, not tables. Every card shows state that was actually observed and
 * offers the action that state allows. Nothing here fabricates a percentage,
 * a progress bar, a connectivity claim or a security badge: a measurement that
 * does not exist stays unavailable. The raw readouts live under Advanced. */

function facts(target, rows) {
  if (!target) return;
  target.replaceChildren();
  for (const [key, value, note] of rows) {
    const div = document.createElement('div');
    const dt = document.createElement('dt');
    dt.textContent = key;
    div.append(dt, cell(value, note));
    target.append(div);
  }
}

function chip(target, text, kind) {
  if (!target) return;
  target.textContent = text;
  target.className = `chip chip-${kind}`;
}

function actions(target, list) {
  if (!target) return;
  target.replaceChildren();
  for (const item of list) {
    if (item.command) {
      const code = document.createElement('p');
      code.className = 'setup-command';
      code.textContent = item.command;
      target.append(code);
      continue;
    }
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn';
    button.textContent = item.label;
    button.onclick = item.run;
    target.append(button);
  }
}

let lastStatus = null;

/* The one line of readiness in the navigation, on every screen. */
function renderReadyLine(s) {
  const line = $('ready-line');
  if (!line) return;
  const reachable = s.runtime.reachable;
  if (!reachable) {
    line.dataset.state = 'failed';
    line.textContent = 'The AI engine is not answering. Open Settings.';
  } else if (!s.model_installed) {
    line.dataset.state = 'attention';
    line.textContent = 'The model is not installed. Open Settings.';
  } else {
    line.dataset.state = 'ok';
    line.textContent = 'Ready on this computer.';
  }
}

function renderComputerCard(s) {
  if (!$('c-computer-facts')) return;
  const shell = s.desktop || {};
  const running = shell.shell
    ? (shell.packaged ? 'The Refinix application started it'
      : 'The Refinix desktop window started it')
    : 'Started on its own, without the Refinix window';
  chip($('c-computer-chip'), 'running', 'enforced');
  $('c-computer-lead').textContent =
    'Refinix and everything it stores are on this computer. Its local address '
    + 'accepts connections from this computer only.';
  facts($('c-computer-facts'), [
    ['Coordinator', running],
    ['Local address', `127.0.0.1:${shell.port || (location.port || '—')}`],
    ['Where your data is kept', shell.state_folder, 'not reported by the window'],
    ['Conversations saved', Object.values(s.jobs_by_state).reduce((a, b) => a + b, 0) + ' request(s) recorded'],
    ['Repaired when it last started', `${s.repaired_on_start} unfinished request(s)`],
  ]);
  const list = [];
  if (window.pywebview && window.pywebview.api && window.pywebview.api.open_state_folder) {
    list.push({ label: 'Open the data folder',
                run: () => window.pywebview.api.open_state_folder() });
  }
  list.push({ label: 'Re-check now', run: () => loadStatus().catch(() => {}) });
  actions($('c-computer-actions'), list);
}

function renderEngineCard(s) {
  if (!$('c-engine-facts')) return;
  const r = s.runtime;
  const target = $('c-engine-chip');
  const list = [];
  if (!r.reachable) {
    chip(target, 'not answering', 'fault');
    $('c-engine-lead').textContent =
      'Chat needs the AI engine running on this computer. Refinix did not get '
      + 'an answer from it, and it will not install or download anything on its own.';
    list.push({ label: 'Try again', run: () => loadStatus().catch(() => {}) });
  } else if (!s.model_installed) {
    chip(target, 'model missing', 'caution');
    $('c-engine-lead').textContent =
      `The engine is running, but the model Refinix is set to use is not on this `
      + `computer. Download it yourself with the command below, then re-check.`;
    list.push({ command: `ollama pull ${s.model_configured}` });
    list.push({ label: 'Re-check now', run: () => loadStatus().catch(() => {}) });
  } else {
    chip(target, 'ready', 'enforced');
    $('c-engine-lead').textContent = 'The engine answered and the model is installed.';
    list.push({ label: 'Re-check now', run: () => loadStatus().catch(() => {}) });
  }
  facts($('c-engine-facts'), [
    ['Engine', r.reachable ? `Ollama ${r.server_version || ''}`.trim() : null,
     r.error || 'no answer from this computer'],
    ['Model in use', s.model_configured],
    ['Model installed', s.model_installed ? 'yes' : null, 'not on this computer'],
    ['Loaded in memory now', r.loaded && r.loaded.model, 'nothing loaded'],
    ['Other models here', r.models.length ? r.models.join(', ') : null,
     'the engine listed none'],
  ]);
  actions($('c-engine-actions'), list);
}

/* AF-007. Every value here is observed now or shown as unavailable. There is
 * no cached "last known healthy": a stale number displayed as current is the
 * fabricated health this card exists to avoid. */
function renderOthersCard(s, worker) {
  if (!$('c-others-facts')) return;
  const form = $('pair-form');

  if (!worker) {
    chip($('c-others-chip'), 'unavailable', 'unknown');
    $('c-others-lead').textContent =
      'Refinix could not read the connection state, so nothing about another '
      + 'computer is shown.';
    facts($('c-others-facts'), [['Connected computers', null, 'not observed']]);
    return;
  }

  if (worker.identity_mismatch) {
    /* Never offered as "try again" or quietly answered locally: the worker
     * presented a different certificate, and that is what the operator has to
     * see. */
    chip($('c-others-chip'), 'identity changed', 'failed');
    $('c-others-lead').textContent =
      'The connected computer presented a different certificate than the one '
      + 'you confirmed. Refinix refused the connection and did not send your '
      + 'request anywhere.';
    facts($('c-others-facts'), [
      ['Status', 'refused — worker identity changed'],
      ['What Refinix did', 'nothing was sent; the request was not run elsewhere'],
      ['Fingerprint you confirmed', worker.relationship?.fingerprint || null,
       'not recorded'],
    ]);
    actions($('c-others-actions'), [
      { label: 'Disconnect this computer',
        run: () => revokePairing(worker.relationship.relationship_id) },
    ]);
    return;
  }

  if (!worker.paired) {
    chip($('c-others-chip'), 'none connected', 'unknown');
    $('c-others-lead').textContent = worker.keychain_available
      ? 'Refinix can share work with another computer you connect. None is '
        + 'connected, so everything runs here.'
      : 'Connecting another computer needs the macOS Keychain to hold its '
        + 'credential. It is not available here, so connecting is switched off.';
    facts($('c-others-facts'), [
      ['Connected computers', null, 'none'],
      ['This computer', `${s.node_id.slice(0, 8)} — the only one in use`],
      ['Where requests run', 'on this computer'],
    ]);
    actions($('c-others-actions'), worker.keychain_available
      ? [{ label: 'Connect a computer', run: () => { if (form) form.hidden = false; } }]
      : []);
    return;
  }

  const node = worker.node;
  const relationship = worker.relationship || {};
  const health = worker.health || 'unavailable';
  chip($('c-others-chip'), health, health === 'healthy' ? 'ok'
    : health === 'unavailable' ? 'failed' : 'attention');
  $('c-others-lead').textContent = worker.would_dispatch
    ? 'Chat requests run on the connected computer. If it stops answering, '
      + 'Refinix runs them here instead and says so.'
    : 'A computer is connected but is not taking work right now, so requests '
      + 'run here.';
  facts($('c-others-facts'), [
    ['Connected computer', relationship.display_name || relationship.address],
    ['Address', `${relationship.address}:${relationship.port}`],
    ['Certificate fingerprint', relationship.fingerprint],
    /* Missing measurements stay missing. `queue_depth` and the model are only
     * present when the worker actually reported them. */
    ['Model there', node?.models?.[0]?.model_id || null, 'not reported'],
    ['Waiting requests', node && node.queue_depth !== null && node.queue_depth !== undefined
      ? String(node.queue_depth) : null, 'not reported'],
    ['Last checked', node?.observed_at || null, 'not observed'],
    ['Where the next request runs', worker.route_reason],
  ]);
  actions($('c-others-actions'), [
    /* Explicit, never automatic: the self-test sends a real request to the
       connected computer and the model spends real time on it. */
    { label: 'Run distributed self-test', run: runSelftest },
    { label: 'Disconnect this computer',
      run: () => revokePairing(relationship.relationship_id) },
  ]);
}

/* The self-test goes down the ORDINARY request path — route choice, pinned
 * channel, durable receipt, executor, event replay. There is no bypass, so a
 * pass means that path works and not that a test helper does. */
async function runSelftest() {
  const box = $('c-selftest');
  const setNote = (text) => { if (box) box.textContent = text; };
  setNote('Sending one request to the connected computer…');
  let started;
  try {
    started = await api('/v1/worker/selftest', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
  } catch (error) {
    setNote(String(error.message || error));
    return;
  }
  for (let attempt = 0; attempt < 120; attempt += 1) {
    let result;
    try {
      result = await api(`/v1/worker/selftest?job_id=${started.job_id}`);
    } catch (error) {
      setNote(String(error.message || error));
      return;
    }
    if (result.finished) {
      renderSelftest(result);
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  setNote('The self-test did not finish within two minutes. Its record is in '
          + 'the Connection self-test conversation.');
}

/* Report what happened, including a fallback, rather than a pass/fail badge:
 * "it ran here instead" is the answer the operator most needs to see. */
function renderSelftest(result) {
  const box = $('c-selftest');
  if (!box) return;
  box.replaceChildren();
  const headline = document.createElement('p');
  headline.className = result.passed ? 'ok' : 'attention';
  headline.textContent = result.passed
    ? 'Passed. The request ran on the connected computer and came back.'
    : `Did not pass. The request ended as ${result.state}.`;
  box.append(headline);
  const list = document.createElement('dl');
  list.className = 'facts';
  for (const attempt of result.attempts) {
    const row = document.createElement('div');
    const key = document.createElement('dt');
    key.textContent = attempt.ran_remotely ? 'On the connected computer'
      : 'On this computer';
    row.append(key, cell(`${attempt.state} — ${attempt.route_reason}`));
    list.append(row);
  }
  const pod = document.createElement('div');
  const podKey = document.createElement('dt');
  podKey.textContent = 'Pod readiness';
  /* Deliberately unavailable: Refinix has no Kubernetes credential, and asking
     for one to fill in a row would be a larger permission than this needs. */
  pod.append(podKey, cell(result.pod_readiness, result.pod_readiness_note));
  list.append(pod);
  box.append(list);
}

async function revokePairing(relationshipId) {
  if (!relationshipId) return;
  await api('/v1/pair/revoke', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ relationship_id: relationshipId }),
  });
  await loadStatus();
}

/* The form is submitted once. Nothing it holds is written to storage, and the
 * fields are cleared immediately: the pairing code is single-use and the
 * certificate is not the page's to keep. */
function wirePairForm() {
  const form = $('pair-form');
  if (!form) return;
  const cancel = $('pair-cancel');
  if (cancel) cancel.onclick = () => { form.hidden = true; form.reset(); };
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const note = $('pair-note');
    const payload = {
      address: $('pair-address').value.trim(),
      port: Number($('pair-port').value.trim()) || 30443,
      fingerprint: $('pair-fingerprint').value.trim(),
      certificate_pem: $('pair-certificate').value,
      pairing_code: $('pair-code').value.trim(),
    };
    try {
      await api('/v1/pair', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      form.reset();
      form.hidden = true;
      await loadStatus();
    } catch (error) {
      if (note) note.textContent = String(error.message || error);
    } finally {
      $('pair-code').value = '';
      $('pair-certificate').value = '';
    }
  });
}

function renderWorkCard(s, jobs) {
  if (!$('c-work-list')) return;
  const running = jobs.filter((j) => ACTIVE_STATES.includes(j.state));
  chip($('c-work-chip'), running.length ? `${running.length} running` : 'nothing running',
       running.length ? 'running' : 'unknown');
  $('c-work-lead').textContent = running.length
    ? 'These requests are running on this computer now.'
    : 'Nothing is running. Recent requests are listed under Advanced.';
  const host = $('c-work-list');
  host.replaceChildren();
  for (const job of running) {
    const li = document.createElement('li');
    const text = document.createElement('span');
    const name = document.createElement('span');
    name.className = 'w-name';
    name.textContent = job.original_request.slice(0, 80);
    const detail = document.createElement('span');
    detail.className = 'w-detail';
    detail.textContent = `started ${job.created_at.slice(11, 19)}`;
    text.append(name, detail);
    const evidence = document.createElement('button');
    evidence.type = 'button';
    evidence.className = 'btn btn-proof';
    evidence.textContent = 'Proof';
    evidence.onclick = () => { showProof(job.job_id).catch(() => {}); };
    const stop = document.createElement('button');
    stop.type = 'button';
    stop.className = 'btn btn-stop';
    stop.textContent = 'Stop';
    stop.onclick = async () => {
      stop.disabled = true;
      stop.textContent = 'Stopping…';
      try {
        await api('/v1/cancel', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ job_id: job.job_id }),
        });
      } catch (err) {
        notice('That request could not be stopped.', 'error', err.message);
        stop.disabled = false;
        stop.textContent = 'Stop';
      }
      loadStatus().catch(() => {});
    };
    li.append(text, evidence, stop);
    host.append(li);
  }
  actions($('c-work-actions'), [
    { label: 'View work', run: () => { location.href = '/'; } },
    { label: 'Refresh', run: () => loadStatus().catch(() => {}) },
  ]);
}

/* AF-014 Proof Card.
 *
 * The page renders exactly what the coordinator returned and adds nothing.
 * Every row carries the source the backend stated, and a value the backend
 * reported as absent is shown as unavailable WITH that reason — never as 0,
 * "no", "healthy" or an empty row. A card that claimed more than the record
 * behind it would be the specific failure AF-014 exists to prevent.
 */
async function showProof(jobId) {
  const host = $('c-proof');
  if (!host) return;
  host.hidden = false;
  host.replaceChildren();
  let card;
  try {
    card = await api(`/v1/proof?job_id=${encodeURIComponent(jobId)}`);
  } catch (err) {
    const failed = document.createElement('p');
    failed.className = 'unavailable';
    failed.textContent = `No proof could be read for this job: ${err.message}`;
    host.append(failed);
    return;
  }
  renderProofCard(card);
}

/* One Proof row. The source is rendered for EVERY value, not only for a
 * missing one: "runtime 4200 ms" and "runtime 4200 ms, from coordinator
 * SQLite" are different claims, and AF-014 requires the second. `kv` shows a
 * note only when the value is absent, which is right for a status card and
 * wrong here. */
function proofRow(target, label, value, source) {
  const row = document.createElement('div');
  const key = document.createElement('dt');
  key.textContent = label;
  const body = cell(value, source);
  const origin = document.createElement('span');
  origin.className = 'proof-source';
  /* An absent value already reads as its own reason, so repeating the source
     under it would say the same sentence twice. */
  origin.textContent = (value === null || value === undefined || value === '')
    ? '' : ` — source: ${source}`;
  body.append(origin);
  row.append(key, body);
  target.append(row);
}

function renderProofCard(card) {
  const host = $('c-proof');
  if (!host) return;
  host.hidden = false;
  host.replaceChildren();

  const heading = document.createElement('h3');
  heading.textContent = `Proof — ${card.task_type} job, ${card.state}`;
  host.append(heading);

  for (const entry of card.attempts) {
    const proof = entry.proof;
    const block = document.createElement('section');
    block.className = 'proof-attempt';
    const title = document.createElement('h4');
    title.textContent = `${entry.where} — attempt ${proof.attempt_id.slice(0, 8)}`;
    block.append(title);

    const facts = document.createElement('dl');
    facts.className = 'facts';
    const rows = [
      ['Ran on', entry.where, entry.sources.state],
      ['State', entry.state, entry.sources.state],
      ['Why here', entry.route_reason, entry.sources.route_reason],
      ['Model', proof.model ? proof.model.model_id : null, entry.sources.model],
      ['Model manifest', proof.model ? proof.model.manifest_sha256 : null,
       entry.sources.model],
      ['Queue time', proof.queue_ms === null ? null : `${proof.queue_ms} ms`,
       entry.sources.queue_ms],
      ['Runtime', proof.runtime_ms === null ? null : `${proof.runtime_ms} ms`,
       entry.sources.runtime_ms],
      ['Validation',
       proof.validation === 'unavailable' ? null : proof.validation,
       entry.sources.validation],
      ['Pod', proof.pod ? `${proof.pod.pod_name} (${proof.pod.pod_uid})` : null,
       entry.sources.pod],
      ['Pod image', proof.pod ? proof.pod.image_digest : null, entry.sources.pod],
      ['Approval', proof.approval_id, entry.sources.approval],
      ['Network', null, entry.sources.network],
    ];
    for (const [label, value, source] of rows) proofRow(facts, label, value, source);
    block.append(facts);

    if (proof.artifacts.length) {
      const list = document.createElement('ul');
      list.className = 'proof-artifacts';
      for (const artifact of proof.artifacts) {
        const li = document.createElement('li');
        li.textContent = `${artifact.media_type} — ${artifact.size_bytes} bytes, `
          + `SHA-256 ${artifact.sha256.slice(0, 16)}…`;
        list.append(li);
      }
      block.append(list);
    }
    if (proof.citations.length) {
      const list = document.createElement('ul');
      list.className = 'proof-citations';
      for (const citation of proof.citations) {
        const li = document.createElement('li');
        li.textContent = `page ${citation.page} — ${citation.quote}`;
        list.append(li);
      }
      block.append(list);
    }
    if (entry.validation_detail) {
      const detail = entry.validation_detail;
      const pre = document.createElement('p');
      pre.className = 'proof-validation';
      pre.textContent = `${detail.command.join(' ')} → exit `
        + `${detail.exit_status === null ? 'unavailable' : detail.exit_status}`;
      block.append(pre);
    }
    host.append(block);
  }

  const note = document.createElement('p');
  note.className = 'proof-note';
  note.textContent = card.evidence_note;
  host.append(note);
  const network = document.createElement('p');
  network.className = 'unavailable';
  network.textContent = card.network;
  host.append(network);
}

function renderCapabilityCard(s) {
  const host = $('c-cap-list');
  if (!host) return;
  const ready = s.capabilities.filter((c) => c.state === 'available').length;
  chip($('c-cap-chip'), `${ready} of ${s.capabilities.length} ready`,
       ready ? 'enforced' : 'unknown');
  host.replaceChildren();
  for (const cap of s.capabilities) {
    const li = document.createElement('li');
    const text = document.createElement('span');
    const name = document.createElement('span');
    name.className = 'c-name';
    name.textContent = cap.name;
    const detail = document.createElement('span');
    detail.className = 'c-detail';
    detail.textContent = cap.state === 'available' ? cap.summary : cap.detail;
    text.append(name, detail);
    const state = document.createElement('span');
    state.className = 'chip chip-' + (cap.state === 'available' ? 'enforced'
      : cap.state === 'blocked' ? 'caution' : 'unknown');
    state.textContent = cap.state === 'available' ? 'ready'
      : cap.state === 'blocked' ? 'needs setup' : 'not built yet';
    li.append(text, state);
    host.append(li);
  }
}

/* ---- Advanced: the activity charts ------------------------------------ *
 *
 * Three charts drawn from records the coordinator already keeps, not from
 * anything measured for the sake of a picture:
 *
 *   reply time    updated_at - created_at per job. The one number on this
 *                 page a person running a model locally actually wants.
 *   by hour       created_at bucketed into the 24 hours of local time.
 *   outcomes      jobs_by_state, which is the authoritative all-time count —
 *                 the job LIST is a recent window, so the two are not the
 *                 same population and the captions say which is which.
 *
 * Hand-drawn: bars in CSS so their labels stay crisp at any width, and the
 * donut in SVG because an arc is not a box. No chart library is fetched —
 * this application makes no network request outside 127.0.0.1.
 */

const SVG_NS = 'http://www.w3.org/2000/svg';

/* Local wall-clock, to agree with the by-hour chart. Slicing the ISO string
   shows UTC, which is a different clock from the one the reader is on. */
function fmtClock(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso).slice(11, 19);
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function fmtSecs(s) {
  if (s < 1) return '<1s';
  if (s < 60) return Math.round(s) + 's';
  const m = Math.floor(s / 60);
  const rest = Math.round(s % 60);
  return rest ? `${m}m ${rest}s` : `${m}m`;
}

function chartHead(title, sub) {
  const cap = document.createElement('figcaption');
  const t = document.createElement('span');
  t.className = 'chart-title';
  t.textContent = title;
  const s = document.createElement('span');
  s.className = 'chart-sub';
  s.textContent = sub;
  cap.append(t, s);
  return cap;
}

function chartEmpty(text) {
  const p = document.createElement('p');
  p.className = 'chart-empty unavailable';
  p.textContent = text;
  return p;
}

function chartFoot(pairs) {
  const ul = document.createElement('ul');
  ul.className = 'chart-foot';
  for (const [name, value] of pairs) {
    const li = document.createElement('li');
    const n = document.createElement('span');
    n.textContent = name;
    const v = document.createElement('b');
    v.textContent = value;
    li.append(n, v);
    ul.append(li);
  }
  return ul;
}

/* How long each job took, oldest at the left so the row reads as time. */
function renderDurationChart(host, jobs) {
  if (!host) return;
  host.replaceChildren();
  const rows = (jobs || [])
    .map((j) => ({
      secs: (Date.parse(j.updated_at) - Date.parse(j.created_at)) / 1000,
      state: j.state,
      request: j.original_request || '',
    }))
    .filter((r) => Number.isFinite(r.secs) && r.secs >= 0)
    .reverse();

  host.append(chartHead('Reply time',
    rows.length ? `${rows.length} recent jobs, oldest first` : 'nothing recorded'));
  if (!rows.length) {
    host.append(chartEmpty('no job has run on this computer yet'));
    return;
  }

  const secs = rows.map((r) => r.secs);
  const max = Math.max(...secs, 1);
  const sorted = [...secs].sort((a, b) => a - b);
  const mid = sorted.length / 2;
  const median = sorted.length % 2
    ? sorted[Math.floor(mid)]
    : (sorted[mid - 1] + sorted[mid]) / 2;

  const plot = document.createElement('div');
  plot.className = 'plot';

  const rule = document.createElement('span');
  rule.className = 'plot-rule';
  rule.style.bottom = (median / max * 100).toFixed(2) + '%';
  const tag = document.createElement('i');
  tag.textContent = 'median ' + fmtSecs(median);
  rule.append(tag);

  const bars = document.createElement('div');
  bars.className = 'bars';
  for (const r of rows) {
    const bar = document.createElement('span');
    bar.className = 'bar';
    bar.dataset.state = r.state;
    /* A job that finished inside a second is still a job that ran, so it keeps
       a visible stub rather than collapsing to nothing. */
    bar.style.height = Math.max(3, r.secs / max * 100).toFixed(2) + '%';
    bar.title = `${fmtSecs(r.secs)} · ${r.state}\n${r.request.slice(0, 120)}`;
    bars.append(bar);
  }

  plot.append(bars, rule);
  host.append(plot, chartFoot([
    ['median', fmtSecs(median)],
    ['slowest', fmtSecs(max)],
  ]));
}

/* When this computer was working, over the 24 hours of local time. */
function renderHourChart(host, jobs) {
  if (!host) return;
  host.replaceChildren();
  const buckets = new Array(24).fill(0);
  let counted = 0;
  for (const j of jobs || []) {
    const d = new Date(j.created_at);
    if (Number.isNaN(d.getTime())) continue;
    buckets[d.getHours()] += 1;
    counted += 1;
  }

  host.append(chartHead('By hour',
    counted ? `${counted} recent jobs, local time` : 'nothing recorded'));
  if (!counted) {
    host.append(chartEmpty('no job has run on this computer yet'));
    return;
  }

  const max = Math.max(...buckets, 1);
  const plot = document.createElement('div');
  plot.className = 'plot';
  const bars = document.createElement('div');
  bars.className = 'bars bars-tight';
  buckets.forEach((n, hour) => {
    const bar = document.createElement('span');
    bar.className = 'bar';
    /* An empty hour is drawn as an empty hour. A minimum bar height here
       would invent activity that did not happen, so zero gets no bar and the
       axis underneath carries the position. */
    bar.style.height = n ? Math.max(6, n / max * 100).toFixed(2) + '%' : '0';
    bar.title = `${String(hour).padStart(2, '0')}:00 — ${n} job${n === 1 ? '' : 's'}`;
    bars.append(bar);
  });
  plot.append(bars);

  const axis = document.createElement('div');
  axis.className = 'plot-axis';
  for (const label of ['00', '06', '12', '18', '24']) {
    const s = document.createElement('span');
    s.textContent = label;
    axis.append(s);
  }

  const busiest = buckets.indexOf(max);
  host.append(plot, axis, chartFoot([
    ['busiest', `${String(busiest).padStart(2, '0')}:00`],
    ['peak', `${max} job${max === 1 ? '' : 's'}`],
  ]));
}

/* Outcomes, as a share of everything this workspace has ever run. */
function renderOutcomeDonut(host, byState) {
  if (!host) return;
  host.replaceChildren();
  const rows = Object.entries(byState || {})
    .map(([state, n]) => [state, Number(n) || 0])
    .filter(([, n]) => n > 0);
  const total = rows.reduce((sum, [, n]) => sum + n, 0);

  host.append(chartHead('Outcomes', total ? `${total} jobs, all time` : 'nothing recorded'));
  if (!total) {
    host.append(chartEmpty('no job has run on this computer yet'));
    return;
  }

  const R = 40;
  const CIRC = 2 * Math.PI * R;
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('viewBox', '0 0 100 100');
  svg.setAttribute('class', 'donut');
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label',
    rows.map(([s, n]) => `${n} ${s}`).join(', '));

  const track = document.createElementNS(SVG_NS, 'circle');
  track.setAttribute('cx', '50');
  track.setAttribute('cy', '50');
  track.setAttribute('r', String(R));
  track.setAttribute('class', 'donut-track');
  svg.append(track);

  let offset = 0;
  for (const [state, n] of rows) {
    const len = n / total * CIRC;
    const arc = document.createElementNS(SVG_NS, 'circle');
    arc.setAttribute('cx', '50');
    arc.setAttribute('cy', '50');
    arc.setAttribute('r', String(R));
    arc.setAttribute('class', 'donut-arc');
    arc.setAttribute('data-state', state);
    /* A hair of gap between arcs so two neighbours never read as one. */
    arc.setAttribute('stroke-dasharray', `${Math.max(0, len - 1)} ${CIRC - len + 1}`);
    arc.setAttribute('stroke-dashoffset', String(-offset));
    const title = document.createElementNS(SVG_NS, 'title');
    title.textContent = `${state}: ${n}`;
    arc.append(title);
    svg.append(arc);
    offset += len;
  }

  const wrap = document.createElement('div');
  wrap.className = 'donut-wrap';
  const mid = document.createElement('div');
  mid.className = 'donut-mid';
  const done = rows.reduce((n, [s, c]) => n + (s === 'completed' ? c : 0), 0);
  const pct = document.createElement('b');
  pct.textContent = Math.round(done / total * 100) + '%';
  const cap = document.createElement('span');
  cap.textContent = 'completed';
  mid.append(pct, cap);
  wrap.append(svg, mid);

  const legend = document.createElement('ul');
  legend.className = 'donut-legend';
  for (const [state, n] of rows) {
    const li = document.createElement('li');
    const sw = document.createElement('span');
    sw.className = 'sw';
    sw.dataset.state = state;
    const nm = document.createElement('span');
    nm.textContent = state;
    const num = document.createElement('b');
    num.textContent = String(n);
    li.append(sw, nm, num);
    legend.append(li);
  }
  host.append(wrap, legend);
}

/* ---- Advanced panel readouts ----------------------------------------- *
 *
 * Four of these draw rather than list. Nothing here invents a value: each one
 * renders numbers the coordinator already publishes, and says so plainly when
 * a number is missing instead of drawing an empty shape as if it were zero.
 */

/* Whether the engine answered is the first thing anyone opening this panel
   wants to know, and a dot carries it faster than a row of text can. */
function renderProbeLine(host, r) {
  if (!host) return;
  host.replaceChildren();
  const dot = document.createElement('span');
  dot.className = 'probe-dot';
  dot.dataset.state = r.reachable ? 'up' : 'down';
  const text = document.createElement('span');
  text.textContent = r.reachable
    ? `answering on ${r.endpoint}`
    : `no answer from ${r.endpoint}`;
  host.append(dot, text);
}

/* The installed models as tags, with the configured one marked. A comma-joined
   string of model ids was the single worst offender for mid-word wrapping. */
function renderModelTags(host, configured, installed) {
  if (!host) return;
  host.replaceChildren();
  if (!installed || !installed.length) {
    const li = document.createElement('li');
    li.className = 'unavailable';
    li.textContent = 'the runtime did not answer';
    host.append(li);
    return;
  }
  for (const name of installed) {
    const li = document.createElement('li');
    li.className = 'tag';
    li.textContent = name;
    if (name === configured) {
      li.dataset.current = 'true';
      li.title = 'the configured model';
    }
    host.append(li);
  }
}

/* The context window as one bar. The remainder past the conversation budget
   and the reply allowance is DRAWN, not dropped: it is the part of the window
   the contract holds back, and leaving it out would make the two published
   numbers look like they filled the window when they do not. */
function renderBudget(host, c) {
  if (!host) return;
  host.replaceChildren();
  const win = Number(c && c.window_tokens) || 0;
  if (!win) {
    const p = document.createElement('figcaption');
    p.className = 'unavailable';
    p.textContent = 'no window reported';
    host.append(p);
    return;
  }
  const budget = Math.max(0, Number(c.conversation_budget_tokens) || 0);
  const reply = Math.max(0, Number(c.reply_allowance_tokens) || 0);
  const held = Math.max(0, win - budget - reply);

  const cap = document.createElement('figcaption');
  cap.textContent = `${win.toLocaleString()} token window`;

  const bar = document.createElement('div');
  bar.className = 'budget-bar';
  const legend = document.createElement('ul');
  legend.className = 'budget-legend';

  for (const [kind, label, tokens] of [
    ['budget', 'conversation', budget],
    ['reply', 'reply allowance', reply],
    ['held', 'held back', held],
  ]) {
    if (!tokens) continue;
    const seg = document.createElement('span');
    seg.className = 'budget-seg';
    seg.dataset.kind = kind;
    seg.style.width = (tokens / win * 100).toFixed(2) + '%';
    seg.title = `${label}: ${tokens.toLocaleString()} tokens`;
    bar.append(seg);

    const li = document.createElement('li');
    const sw = document.createElement('span');
    sw.className = 'sw';
    sw.dataset.kind = kind;
    const nm = document.createElement('span');
    nm.textContent = label;
    const nu = document.createElement('b');
    nu.textContent = tokens.toLocaleString();
    li.append(sw, nm, nu);
    legend.append(li);
  }
  host.append(cap, bar, legend);
}

/* The state of a job, in the chip vocabulary the rest of the product uses. */
function jobChipClass(state) {
  if (state === 'completed') return 'chip-enforced';
  if (state === 'failed' || state === 'interrupted') return 'chip-fault';
  if (state === 'cancelled') return 'chip-unknown';
  if (state === 'running') return 'chip-observed';
  return 'chip-caution';
}

function renderAdvanced(s, jobs) {
  if (!$('kv-runtime')) return;
  const r = s.runtime;
  renderProbeLine($('probe-line'), r);
  kv($('kv-runtime'), [
    ['server version', r.server_version, r.error || 'no server answered'],
    ['loaded model', r.loaded && r.loaded.model, 'nothing resident'],
    ['resident bytes', r.loaded && r.loaded.size_bytes, 'not reported'],
    ['GPU bytes', r.loaded && r.loaded.size_vram_bytes, 'not reported'],
    ['probe error', r.error, 'none'],
  ]);
  renderModelTags($('model-tags'), s.model_configured, r.models);
  kv($('kv-models'), [
    ['configured', s.model_configured],
    ['num_ctx', s.bounded.num_ctx],
    ['num_predict', s.bounded.num_predict],
    ['thinking', s.bounded.think ? 'on' : 'off (required for this model)'],
  ]);
  renderBudget($('budget'), s.context);
  kv($('kv-context'), [
    ['counting method', s.context.counting_method],
    ['policy', s.context.policy],
  ]);
  kv($('kv-contract'), [
    ['contract version', s.contract_version],
    ['contract status', s.contract_status],
    ['bind', s.bind + ' only'],
    ['node', s.node_id],
    ['workspace', s.workspace_id],
  ]);
  const shell = s.desktop || {};
  kv($('kv-shell'), [
    ['window toolkit', shell.shell, 'not started from the desktop shell'],
    ['platform', shell.platform, 'not reported'],
    ['packaged application', shell.shell ? (shell.packaged ? 'yes' : 'no') : null,
     'not reported'],
    ['port', shell.port, 'not reported'],
    ['reused a running coordinator', shell.shell
      ? (shell.reused_coordinator ? 'yes' : 'no') : null, 'not reported'],
    ['engine started by Refinix', shell.shell
      ? (shell.engine_started_by_refinix ? 'yes' : 'no') : null, 'not reported'],
  ]);
  kv($('kv-restart'), [
    ['jobs repaired on start', s.repaired_on_start],
    ['method', 'attempts left executing become interrupted with a typed reason'],
  ]);
  renderDurationChart($('chart-duration'), jobs);
  renderHourChart($('chart-hours'), jobs);
  renderOutcomeDonut($('chart-outcomes'), s.jobs_by_state);
  kv($('kv-unavailable'), Object.entries(s.unavailable).map(([k, v]) => [k, null, v]));
  const ul = $('job-list');
  if (ul) {
    ul.replaceChildren();
    if (!jobs.length) {
      const li = document.createElement('li');
      li.className = 'unavailable';
      li.textContent = 'no jobs recorded yet';
      ul.append(li);
    }
    for (const j of jobs.slice(0, 12)) {
      const li = document.createElement('li');
      const state = document.createElement('span');
      state.className = 'chip ' + jobChipClass(j.state);
      state.textContent = j.state;
      /* The full request stays in the title; the row itself truncates in CSS
         rather than being cut at 60 characters, so widening the window shows
         more of it instead of the same clipped string. */
      const text = document.createElement('span');
      text.className = 'job-text';
      text.textContent = j.original_request;
      text.title = j.original_request;
      const time = document.createElement('time');
      time.textContent = fmtClock(j.created_at);
      time.dateTime = j.created_at;
      li.append(state, text, time);
      ul.append(li);
    }
  }
  const stamp = $('refreshed');
  if (stamp) stamp.textContent = 'read at ' + new Date().toTimeString().slice(0, 8);
}

async function loadStatus() {
  const s = await api('/v1/status');
  lastStatus = s;
  capabilities = s.capabilities || capabilities;
  if (Array.isArray(s.models)) {
    models = s.models;
    modelSelections = s.model_selections || modelSelections;
    renderModelPill();
  }
  renderReadyLine(s);
  renderSkill();
  if ($('kv-unavailable') && !$('c-cap-list')) {
    // Chat's Details rail carries the same "not observed" list.
    kv($('kv-unavailable'), Object.entries(s.unavailable).map(([k, v]) => [k, null, v]));
  }
  if (!$('c-computer-facts')) return s;
  const { jobs } = await api('/v1/jobs');
  // Preflight is a live observation and can fail on its own; a worker that
  // cannot be read must not blank the rest of the Control Center.
  let worker = null;
  try {
    worker = await api('/v1/worker');
  } catch (error) {
    worker = null;
  }
  renderComputerCard(s);
  renderEngineCard(s);
  renderOthersCard(s, worker);
  renderWorkCard(s, jobs);
  renderCapabilityCard(s);
  renderAdvanced(s, jobs);
  return s;
}

/* ----------------------------------------------------------------- boot -- */

/* Everything the composer adds: the + menu, file selection, drag-and-drop and
 * the keyboard path for the skill label. */
function wireComposer() {
  const box = $('composer-box');
  const hint = $('drop-hint');
  const input = $('input');

  $('plus-btn').addEventListener('click', (e) => {
    e.stopPropagation();
    if (plusMenu) { closePlusMenu(); return; }
    openPlusMenu();
  });

  const fileInput = $('file-input');
  fileInput.addEventListener('change', () => {
    if (fileInput.files.length) stageFiles(fileInput.files);
    fileInput.value = '';                  // the same file can be chosen again
  });

  let dragDepth = 0;
  const setDrag = (on) => {
    box.dataset.drag = String(on);
    hint.hidden = !on;
  };
  for (const type of ['dragenter', 'dragover']) {
    box.addEventListener(type, (e) => {
      if (!Array.from(e.dataTransfer?.types || []).includes('Files')) return;
      e.preventDefault();
      if (type === 'dragenter') dragDepth += 1;
      setDrag(true);
    });
  }
  box.addEventListener('dragleave', () => {
    dragDepth = Math.max(0, dragDepth - 1);
    if (!dragDepth) setDrag(false);
  });
  box.addEventListener('drop', (e) => {
    if (!e.dataTransfer || !e.dataTransfer.files.length) return;
    e.preventDefault();
    dragDepth = 0;
    setDrag(false);
    stageFiles(e.dataTransfer.files);
  });
  // A file dropped anywhere else must not navigate the window away.
  for (const type of ['dragover', 'drop']) {
    window.addEventListener(type, (e) => {
      if (Array.from(e.dataTransfer?.types || []).includes('Files')) e.preventDefault();
    });
  }

  const pill = $('model-pill');
  if (pill) {
    pill.addEventListener('click', (e) => {
      e.stopPropagation();
      if (modelPopover) closeModelPopover(true);
      else openModelPopover();
    });
  }

  $('skill-name').addEventListener('click', openPlusMenu);
  $('skill-remove').addEventListener('click', () => { chooseSkill(null); });
  $('skill-chip').addEventListener('keydown', (e) => {
    if (e.key === 'Backspace' || e.key === 'Delete') {
      e.preventDefault();
      chooseSkill(null);
    }
  });
  // Backspace at the very start of an empty request removes the label, the
  // way a token in a recipient field behaves.
  input.addEventListener('keydown', (e) => {
    if (e.key !== 'Backspace' || !selectedSkill()) return;
    if (input.selectionStart === 0 && input.selectionEnd === 0) {
      e.preventDefault();
      $('skill-name').focus();
    }
  });
}

function connect() {
  const es = new EventSource('/v1/events');
  es.onopen = () => replayEvents();
  es.onmessage = (m) => { try { onEvent(JSON.parse(m.data)); } catch (_) {} };
  es.onerror = () => {
    // The browser reconnects on its own; say so rather than showing a wrong state.
    const chip = $('job-chip');
    if (chip && !['running'].includes(jobState)) {
      chip.classList.add('chip-unknown');
    }
  };
}

let sending = false;

/* ---- theme, the surface menu and the conversation search ------------- *
 *
 * Three surfaces share one header control, so the theme lives beside the panel
 * wiring rather than on any one page. Each page's inline boot script has
 * already resolved the attribute before the first paint; this keeps the button
 * in step with it, records a change, and stops following the machine once
 * someone has stated a preference.
 */
const THEME_KEY = 'refinix.theme';
const SYSTEM_DARK = window.matchMedia('(prefers-color-scheme: dark)');

function storedTheme() {
  try { return localStorage.getItem(THEME_KEY); } catch (_) { return null; }
}

function currentTheme() {
  return document.documentElement.dataset.theme
    || (SYSTEM_DARK.matches ? 'dark' : 'light');
}

function applyTheme(mode, animate) {
  const root = document.documentElement;
  /* A token swap must not transition — see the note in app.css. The attribute
     is dropped two frames later, so ordinary interaction keeps its motion and
     the swap itself lands in one paint. */
  if (animate) {
    root.setAttribute('data-theme-switching', '');
    requestAnimationFrame(() => requestAnimationFrame(
      () => root.removeAttribute('data-theme-switching')));
  }
  root.dataset.theme = mode;
  const btn = $('theme-toggle');
  if (!btn) return;
  const dark = mode === 'dark';
  /* The label names the state first and the action second, because the icon
     shows the state and a label that contradicted it would be worse than
     none. */
  const label = dark ? 'Dark mode is on. Switch to light mode.'
                     : 'Light mode is on. Switch to dark mode.';
  btn.setAttribute('aria-label', label);
  btn.setAttribute('aria-pressed', String(dark));
  btn.title = label;
}

/* CSS can reserve a scrollbar gutter but cannot name its width, and the
   composer needs the same one the conversation reserves. Measured from the
   scroller itself, so an overlay-scrollbar platform correctly reports zero. */
function syncScrollGutter() {
  const thread = $('thread');
  if (!thread) return;
  const reserved = thread.offsetWidth - thread.clientWidth;
  document.documentElement.style.setProperty(
    '--scroll-gutter', (reserved / 2).toFixed(2) + 'px');
}

function wireTheme() {
  applyTheme(currentTheme(), false);
  const btn = $('theme-toggle');
  if (btn) {
    btn.addEventListener('click', () => {
      const next = currentTheme() === 'dark' ? 'light' : 'dark';
      applyTheme(next, true);
      try { localStorage.setItem(THEME_KEY, next); } catch (_) {}
    });
  }
  SYSTEM_DARK.addEventListener('change', (e) => {
    if (!storedTheme()) applyTheme(e.matches ? 'dark' : 'light', true);
  });
}

/* The field is folded away until you ask for it: the icon in the heading is
   the whole control when you are not searching. Closing it clears the term, so
   the list you are left looking at is never a filtered one with no visible
   reason for being short. */
function wireSearchToggle() {
  const btn = $('chat-search-btn');
  const field = $('chat-search');
  if (!btn || !field) return;

  const set = (open) => {
    field.hidden = !open;
    btn.setAttribute('aria-expanded', String(open));
    if (open) { field.focus(); return; }
    if (field.value) { field.value = ''; runSearch(''); }
  };
  set(false);

  btn.addEventListener('click', () => set(field.hidden));
  field.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { set(false); btn.focus(); }
  });
}

/* Both walls fold away so the conversation can have the window.
 *
 * Two modes, one pair of controls. On a wide window the grid track collapses
 * to zero and the middle column genuinely gets the room — that is the point,
 * and an overlay would cover the conversation rather than widen it. On a
 * narrow one the wall becomes an overlay with a scrim, because at 375px there
 * is no room to give.
 *
 * The breakpoints match the responsive block in app.css. Previously each panel
 * was display:none above its breakpoint with a text button that only appeared
 * below it, so on a desktop there was no way to reclaim the middle column and
 * on a phone the rail's routing evidence simply did not exist.
 */
const PANEL_MQ = {
  nav:  window.matchMedia('(max-width: 760px)'),
  rail: window.matchMedia('(max-width: 1180px)'),
};

function wirePanels() {
  const app = document.querySelector('.app');
  const scrim = $('scrim');
  if (!app) return;

  /* Persisted per panel, per surface: a collapsed rail on Chat should not
     collapse it on Settings, where it carries different evidence. Storage can
     throw outright (private windows, blocked site data), so reads and writes
     are guarded and the UI is correct with no stored value. */
  const surface = (location.pathname.split('/').pop() || 'index.html');
  const key = (name) => `refinix.panel.${surface}.${name}`;
  const stored = (name) => {
    try { return localStorage.getItem(key(name)); } catch (_) { return null; }
  };
  const remember = (name, value) => {
    try { localStorage.setItem(key(name), value); } catch (_) {}
  };

  const panels = {};
  for (const name of ['nav', 'rail']) {
    const el = $(name);
    const toggle = $(`${name}-toggle`);
    if (!el || !toggle) {
      /* Code and Settings carry no rail. A control for a panel that is not on
         the page is worse than no control, so it is removed rather than left
         to do nothing. */
      if (toggle) toggle.hidden = true;
      continue;
    }
    panels[name] = { el, toggle, mq: PANEL_MQ[name] };
  }

  const isOpen = (name) => app.dataset[name] === 'open';

  /* The scrim is raised by CSS — `.app[data-nav="open"] ~ .scrim`, declared
     inside the same media queries as the overlays — so there is one source of
     truth and a collapsed track on a wide window raises nothing. */
  const set = (name, open, save = true) => {
    const panel = panels[name];
    if (!panel) return;
    app.dataset[name] = open ? 'open' : 'closed';
    panel.toggle.setAttribute('aria-expanded', String(open));
    if (save) remember(name, open ? 'open' : 'closed');
  };

  for (const [name, panel] of Object.entries(panels)) {
    panel.toggle.addEventListener('click', () => set(name, !isOpen(name)));

    /* A stored choice wins on a wide window; on a narrow one both walls start
       closed regardless, because opening over the conversation is never the
       right thing to do to someone who just loaded the page. */
    set(name, panel.mq.matches ? false : stored(name) !== 'closed', false);

    /* Crossing a breakpoint changes what the same state means: leaving overlay
       mode restores the remembered choice, entering it closes. */
    panel.mq.addEventListener('change', (e) => {
      set(name, e.matches ? false : stored(name) !== 'closed', false);
    });
  }

  const closeOverlays = (refocus) => {
    for (const [name, panel] of Object.entries(panels)) {
      if (panel.mq.matches && isOpen(name)) {
        set(name, false);
        if (refocus) panel.toggle.focus();
      }
    }
  };

  if (scrim) scrim.addEventListener('click', () => closeOverlays(false));
  document.addEventListener('keydown', (e) => {
    /* Escape dismisses an overlay. It deliberately does not collapse a docked
       panel on a wide window — that is a layout preference, not a trap. */
    if (e.key === 'Escape') closeOverlays(true);
  });
}

window.addEventListener('DOMContentLoaded', () => {
  wirePanels();
  wireTheme();
  syncScrollGutter();
  window.addEventListener('resize', syncScrollGutter);
  const thread = $('thread');
  if (thread) {
    thread.addEventListener('scroll', () => {
      following = atBottom();
      const jump = $('jump-latest');
      if (jump) jump.hidden = following;
    });
  }
  const jump = $('jump-latest');
  if (jump) {
    jump.addEventListener('click', () => {
      following = true;
      thread.scrollTop = thread.scrollHeight;
      jump.hidden = true;
    });
  }
  const search = $('chat-search');
  if (search) {
    search.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => runSearch(search.value), 220);
    });
    search.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { search.value = ''; runSearch(''); }
    });
  }
  wireSearchToggle();
  const draftInput = $('input');
  if (draftInput) draftInput.addEventListener('input', () => {
    ++draftVersion;
    draftReady = true;
    if ($('draft-mark')) $('draft-mark').hidden = !draftInput.value;
    saveDraftSoon();
  });
  document.addEventListener('click', (e) => {
    if (openMenu && !openMenu.contains(e.target)) closeMenu();
    if (plusMenu && !plusMenu.contains(e.target) && e.target !== $('plus-btn')) {
      closePlusMenu();
    }
    const pill = $('model-pill');
    if (modelPopover && !modelPopover.contains(e.target)
        && !(pill && pill.contains(e.target))) {
      closeModelPopover(false);
    }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && openMenu) closeMenu();
    if (e.key === 'Escape' && plusMenu) { closePlusMenu(); $('plus-btn').focus(); }
    if (e.key === 'Escape' && modelPopover) closeModelPopover(true);
  });
  publishSlot();
  wirePairForm();
  loadStatus().catch((e) => console.error('status unavailable:', e.message));
  if ($('composer')) {
    connect();
    wireComposer();
    loadCapabilities();
    loadChats().then(() => api('/v1/chats')).then(({ chats }) => {
      if (chats.length) openChat(chats[0].chat_id);
      else { renderLife(null); loadDraft(null); loadStaged(); }
    }).catch((e) => console.error(e.message));

    $('composer').onsubmit = async (e) => {
      e.preventDefault();
      const input = $('input');
      const text = input.value.trim();
      if (!text) return;
      const skill = selectedSkill();
      if (skill && skill.state !== 'available') {
        notice(`${skill.name} is not available yet.`, 'warn',
               `${skill.detail} Remove the skill to send an ordinary request.`);
        return;
      }
      if (sending) {
        notice('A reply is still running.', 'warn',
               'Stop it first, or wait for it to finish. Your draft is kept.');
        return;
      }
      sending = true;
      $('send').disabled = true;
      try {
        await send(text, { draftText: input.value });
      } catch (err) {
        notice('Could not send that request.', 'error', err.message);
      } finally {
        sending = false;
        refreshSend();
        input.focus();
      }
    };
    $('input').addEventListener('keydown', (e) => {
      // isComposing guards IME: Enter while composing selects a candidate.
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && e.keyCode !== 229) {
        e.preventDefault();
        $('composer').requestSubmit();
      }
    });
    wireAutogrow($('input'));
    $('new-chat').onclick = newChat;
    $('cancel-btn').onclick = async () => {
      if (!activeJob || stopping) return;
      stopping = true;
      setActive(jobState);                 // shows "Stopping…" straight away
      try {
        await api('/v1/cancel', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ job_id: activeJob }),
        });
      } catch (err) {
        stopping = false;
        setActive(jobState);
        notice('That reply could not be stopped.', 'error', err.message);
      }
    };
    setInterval(() => loadStatus().catch(() => {}), 10000);
    // SSE is a notification channel; SQLite supplies any missed events.
    setInterval(() => {
      if (['running', 'queued', 'routing', 'context_preparing', 'created', 'validating']
          .includes(jobState)) replayEvents();
    }, 2000);
  } else if ($('code-composer')) {
    wireCode();
    setInterval(() => loadStatus().catch(() => {}), 15000);
  } else if ($('refresh')) {
    $('refresh').onclick = () => loadStatus().catch(() => {});
    setInterval(() => loadStatus().catch(() => {}), 10000);
  }
});

/* ---- Execution 4B: Explorer, file viewer and Code conversations --------- */

/* Which folders are open, per project, so a redraw does not fold the tree the
 * person just expanded. Keyed by project because two projects can hold the
 * same relative path and must not share expansion state. */
const expandedFolders = new Map();
let openFile = null;          // { repo_id, path, lines, ... }
let viewerToken = 0;          // only the newest open may paint

function foldersFor(repoId) {
  if (!expandedFolders.has(repoId)) expandedFolders.set(repoId, new Set());
  return expandedFolders.get(repoId);
}

/* The tree the coordinator returns is relative paths only. Building it here
 * from `repoFiles` keeps the Explorer and the selection list showing one set
 * of files: they cannot disagree because there is only one source. */
function buildTree(files) {
  const root = { folders: new Map(), files: [] };
  for (const entry of files || []) {
    const path = String(entry.path || '').replace(/^\/+|\/+$/g, '');
    if (!path) continue;
    const parts = path.split('/');
    let node = root;
    for (const folder of parts.slice(0, -1)) {
      if (!node.folders.has(folder)) {
        node.folders.set(folder, { folders: new Map(), files: [] });
      }
      node = node.folders.get(folder);
    }
    node.files.push({ ...entry, name: parts[parts.length - 1], path });
  }
  const convert = (node, prefix) => {
    const out = [];
    for (const name of [...node.folders.keys()].sort()) {
      const child = `${prefix}${name}`;
      out.push({ kind: 'folder', name, path: child,
                 children: convert(node.folders.get(name), `${child}/`) });
    }
    for (const file of node.files.sort((a, b) => a.name.localeCompare(b.name))) {
      out.push({ kind: 'file', name: file.name, path: file.path,
                 byte_size: file.byte_size });
    }
    return out;
  };
  return convert(root, '');
}

function treeRow({ kind, name, meta, depth, selected, expanded, onClick }) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'tree-row';
  button.dataset.kind = kind;
  button.style.paddingLeft = `${8 + depth * 12}px`;
  button.setAttribute('role', 'treeitem');
  if (expanded !== undefined) button.setAttribute('aria-expanded', String(expanded));
  button.setAttribute('aria-selected', String(!!selected));
  const twisty = document.createElement('span');
  twisty.className = 'tree-twisty';
  twisty.setAttribute('aria-hidden', 'true');
  twisty.textContent = expanded === undefined ? '' : '›';
  const label = document.createElement('span');
  label.className = 'tree-name';
  label.textContent = name;
  const tail = document.createElement('span');
  tail.className = 'tree-meta';
  tail.textContent = meta || '';
  button.append(twisty, label, tail);
  button.onclick = onClick;
  return button;
}

function renderExplorer() {
  const host = $('explorer');
  if (!host || !codeState) return;
  host.replaceChildren();
  if (!codeState.repositories.length) {
    const empty = document.createElement('p');
    empty.className = 'tree-note';
    empty.textContent = 'No project is connected yet. Use + to choose a folder.';
    host.append(empty);
    return;
  }
  for (const entry of codeState.repositories) {
    const isActive = entry.repo_id === codeState.active;
    const open = foldersFor(entry.repo_id);
    host.append(treeRow({
      kind: 'project', name: entry.name, meta: entry.mode || '',
      depth: 0, selected: isActive, expanded: isActive,
      onClick: () => {
        if (isActive) return;
        activateRepository(entry.repo_id);
      },
    }));
    if (!isActive) continue;
    const children = document.createElement('div');
    children.className = 'tree-children';
    children.setAttribute('role', 'group');
    if (!repoFiles.length) {
      const note = document.createElement('p');
      note.className = 'tree-note';
      note.textContent = codeState.pending_approvals?.length
        ? 'This project needs your approval before its files can be listed.'
        : 'No readable text files were found in this project.';
      children.append(note);
    } else {
      paintNodes(buildTree(repoFiles), children, 1, entry.repo_id, open);
    }
    host.append(children);

    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'tree-row';
    remove.dataset.kind = 'action';
    remove.style.paddingLeft = '20px';
    remove.setAttribute('role', 'treeitem');
    const spacer = document.createElement('span');
    spacer.className = 'tree-twisty';
    const text = document.createElement('span');
    text.className = 'tree-name';
    text.textContent = 'Remove from Refinix';
    remove.append(spacer, text, document.createElement('span'));
    remove.onclick = () => removeProject(entry);
    host.append(remove);
  }
}

function paintNodes(nodes, host, depth, repoId, open) {
  for (const node of nodes) {
    if (node.kind === 'folder') {
      const expanded = open.has(node.path);
      host.append(treeRow({
        kind: 'folder', name: node.name, depth, expanded,
        onClick: () => {
          if (expanded) open.delete(node.path); else open.add(node.path);
          renderExplorer();
        },
      }));
      if (expanded) {
        const group = document.createElement('div');
        group.className = 'tree-children';
        group.setAttribute('role', 'group');
        paintNodes(node.children, group, depth + 1, repoId, open);
        host.append(group);
      }
    } else {
      host.append(treeRow({
        kind: 'file', name: node.name, depth,
        meta: selectedPaths.has(node.path) ? 'in request' : '',
        selected: openFile && openFile.repo_id === repoId
                  && openFile.path === node.path,
        onClick: () => openFileInViewer(repoId, node.path),
      }));
    }
  }
}

/* ---- the open file ----------------------------------------------------- */

function viewerState(message, kind = 'note') {
  const body = $('viewer-body');
  if (!body) return;
  const p = document.createElement('p');
  p.className = 'viewer-state';
  p.dataset.kind = kind;
  p.textContent = message;
  body.replaceChildren(p);
}

function closeViewer(persist = true) {
  const closingRepo = openFile?.repo_id || activeRepo;
  openFile = null;
  viewerToken += 1;
  const tabs = $('viewer-tabs');
  const crumb = $('viewer-crumb');
  if (tabs) tabs.hidden = true;
  if (crumb) crumb.hidden = true;
  const body = $('viewer-body');
  if (body) {
    const empty = document.createElement('p');
    empty.className = 'viewer-empty';
    empty.textContent = 'Choose a project in the Explorer, then open a file to '
      + 'read it here. Opening a file does not send it to the model.';
    body.replaceChildren(empty);
  }
  if (persist && closingRepo && codeConversation) {
    persistCodeContext(closingRepo, null).catch((err) =>
      notice('The closed file could not be remembered.', 'warn', err.message));
  }
  renderExplorer();
}

async function openFileInViewer(repoId, path, approvalId) {
  const token = ++viewerToken;
  const generation = codeGeneration;
  const tabs = $('viewer-tabs');
  const crumb = $('viewer-crumb');
  if (tabs) tabs.hidden = false;
  if ($('viewer-tab-name')) $('viewer-tab-name').textContent = path.split('/').pop();
  if (crumb) { crumb.hidden = false; crumb.textContent = path; }
  viewerState('Opening…');
  let file;
  try {
    file = await api(`/v1/code/view?repo_id=${encodeURIComponent(repoId)}`
                     + `&path=${encodeURIComponent(path)}`
                     + `&conversation_id=${encodeURIComponent(codeConversation)}`
                     + (approvalId ? `&approval_id=${encodeURIComponent(approvalId)}` : ''));
  } catch (err) {
    // A response for a file the person has already navigated away from must
    // never paint, and neither must one from a project they have left.
    if (token !== viewerToken || generation !== codeGeneration) return;
    viewerState(err.message || 'That file could not be opened.', 'error');
    return;
  }
  if (token !== viewerToken || generation !== codeGeneration) return;
  if (file.needs_approval) {
    // Remember which file this decision is about, and put the approval in
    // front of the person instead of only describing it.
    viewerState('This project asks before actions, so opening this file needs '
                + 'your approval. Opening it does not send it to the model.');
    if (codeState) {
      const known = new Set((codeState.pending_approvals || [])
        .map((a) => a.approval_id));
      if (!known.has(file.needs_approval.approval_id)) {
        codeState.pending_approvals = [...(codeState.pending_approvals || []),
                                       file.needs_approval];
      }
    }
    renderCode();
    return;
  }
  openFile = { repo_id: repoId, ...file };
  paintFile(file.lines || []);
  try {
    await persistCodeContext(repoId, file.path);
  } catch (err) {
    notice('The open file could not be remembered.', 'warn', err.message);
  }
  renderExplorer();
}

function paintFile(lines) {
  const body = $('viewer-body');
  if (!body) return;
  const grid = document.createElement('div');
  grid.className = 'code-lines';
  lines.forEach((line, index) => {
    const num = document.createElement('span');
    num.className = 'code-num';
    num.textContent = String(index + 1);
    const text = document.createElement('span');
    text.className = 'code-text';
    // Inserted as text. A file is data, and nothing in it becomes markup.
    text.textContent = line;
    grid.append(num, text);
  });
  body.replaceChildren(grid);
}

/* ---- removing a project ------------------------------------------------ */

async function removeProject(entry) {
  if (proposing) {
    notice('Wait for the current request to finish before removing this project.',
           'error');
    return;
  }
  const ok = window.confirm(
    `Remove “${entry.name}” from Refinix?\n\n`
    + 'This disconnects the folder from Refinix. Your files are not deleted, '
    + 'renamed or changed in any way, and the folder stays exactly where it is.');
  if (!ok) return;
  let result;
  try {
    result = await codeApi('/v1/code/forget', {
      repo_id: entry.repo_id, discard_undo: false });
    if (result.confirmation_required) {
      const discard = window.confirm(
        `Refinix is holding ${result.undo_lost} original file copy/copies for `
        + 'changes in this project. Remove it anyway and put those Undo actions '
        + 'out of reach?');
      if (!discard) return;
      result = await codeApi('/v1/code/forget', {
        repo_id: entry.repo_id, discard_undo: true });
    }
  } catch (err) {
    // The coordinator refuses while work is in flight; that refusal is the
    // authoritative one and is shown as it arrives.
    notice('That project could not be removed.', 'error', err.message);
    return;
  }
  if (!result.disconnected) return;
  expandedFolders.delete(entry.repo_id);
  if (openFile && openFile.repo_id === entry.repo_id) closeViewer();
  await loadCodeState(null, { reset: true });
}

/* ---- Code conversations ------------------------------------------------ */

let codeConversation = null;
let codeConversations = [];
let conversationGeneration = 0;

async function loadCodeConversations() {
  try {
    const body = await api('/v1/code/conversations');
    codeConversations = body.conversations || [];
  } catch (_) {
    codeConversations = [];
  }
  renderConversationHead();
  return codeConversations;
}

function renderConversationHead() {
  const title = $('conv-title');
  if (title) {
    const current = codeConversations.find((c) => c.chat_id === codeConversation);
    title.textContent = current ? current.title : 'Code conversation';
  }
  const list = $('conv-history-list');
  if (!list || list.hidden) return;
  list.replaceChildren();
  if (!codeConversations.length) {
    const empty = document.createElement('p');
    empty.className = 'tree-note';
    empty.textContent = 'No Code conversations yet.';
    list.append(empty);
    return;
  }
  for (const entry of codeConversations) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'conv-item';
    button.setAttribute('aria-current', String(entry.chat_id === codeConversation));
    const name = document.createElement('span');
    name.className = 'conv-item-name';
    name.textContent = entry.title;
    const meta = document.createElement('span');
    meta.className = 'conv-item-meta';
    // A disconnected project stays named and stays unavailable. Reopening
    // this conversation must not reconnect a folder behind the person's back.
    meta.textContent = entry.repo_id
      ? (entry.project_available ? `Project: ${entry.repo_name}`
                                 : 'Project no longer connected')
      : 'No project recorded';
    button.append(name, meta);
    button.onclick = () => selectConversation(entry.chat_id);
    list.append(button);
  }
}

async function selectConversation(chatId) {
  const selection = ++conversationGeneration;
  codeConversation = chatId;
  // A newer selection wins, so a slow load for the conversation just left
  // cannot paint its proposal into the one now on screen.
  if (typeof clearCodeResults === 'function') clearCodeResults();
  closeViewer(false);
  const list = $('conv-history-list');
  if (list) { list.hidden = true; }
  const toggle = $('conv-history');
  if (toggle) toggle.setAttribute('aria-expanded', 'false');
  renderConversationHead();

  const entry = codeConversations.find((c) => c.chat_id === chatId);
  // A project that was removed stays removed. Reopening history must not
  // reconnect a folder behind the person's back.
  const project = entry && entry.project_available ? entry.repo_id : null;
  await loadCodeState(project, { reset: true });
  if (conversationGeneration !== selection || codeConversation !== chatId) return;
  const generation = codeGeneration;
  await restoreConversationTurns(chatId, generation);
  if (conversationGeneration !== selection || codeConversation !== chatId) return;
  const remembered = codeState?.conversation?.open_path;
  if (project && remembered) {
    await openFileInViewer(project, remembered);
  }
}

/* The persisted turns of one Code conversation, so reopening it shows the
 * work rather than an empty panel. */
async function restoreConversationTurns(chatId, generation) {
  let body;
  try {
    body = await api(`/v1/messages?chat_id=${encodeURIComponent(chatId)}`);
  } catch (err) {
    notice('That conversation could not be reopened.', 'error', err.message);
    return;
  }
  if (codeGeneration !== generation || codeConversation !== chatId) return;
  for (const message of body.messages || []) {
    showCodeResult((article) => {
      const p = document.createElement('p');
      p.className = message.role === 'user' ? 'card-lead' : 'prose-note';
      p.textContent = message.text;
      article.append(p);
    }, `restored-${message.message_id}`);
  }
}

async function newCodeConversation() {
  let made;
  try {
    made = await codeApi('/v1/code/conversation', {
      title: '', repo_id: codeState?.active || null });
    codeConversation = made.chat_id;
  } catch (err) {
    notice('A new conversation could not be started.', 'error', err.message);
    return;
  }
  ++conversationGeneration;
  // A new conversation clears the visible work, and forgets no project.
  if (typeof clearCodeResults === 'function') clearCodeResults();
  closeViewer(false);
  await loadCodeConversations();
  await loadCodeState(made.repo_id || null, { reset: true });
}

async function initializeCode() {
  await loadCodeConversations();
  if (codeConversations.length) {
    await selectConversation(codeConversations[0].chat_id);
  } else {
    await newCodeConversation();
  }
}

function wireConversationControls() {
  const fresh = $('conv-new');
  if (fresh) fresh.onclick = () => newCodeConversation();
  const history = $('conv-history');
  const list = $('conv-history-list');
  if (history && list) {
    history.onclick = () => {
      const open = list.hidden;
      list.hidden = !open;
      history.setAttribute('aria-expanded', String(open));
      if (open) renderConversationHead();
    };
  }
  const close = $('viewer-close');
  if (close) close.onclick = () => closeViewer();
  const connect = $('connect-btn-nav');
  if (connect && $('connect-btn')) {
    connect.onclick = () => $('connect-btn').click();
  }
}

/* ---- Execution 4C: where the work runs --------------------------------- */

/* Chosen by the person, sent with the request, and recorded on the proposal.
 * `this_device` never contacts the worker; `distributed` keeps the Kubernetes
 * sandbox requirement exactly as it was. */
let executionTarget = 'this_device';

const TARGETS = [
  { id: 'this_device', name: 'This device',
    tag: 'local qwen, no sandbox tests' },
  { id: 'distributed', name: 'Ubuntu worker',
    tag: 'sandbox tested' },
];

function appendTargetChoices(box) {
  appendChoiceGroup(box, 'Run on', TARGETS, executionTarget, (id) => {
    executionTarget = id;
  });
  const note = document.createElement('p');
  note.className = 'mp-note';
  note.textContent = executionTarget === 'this_device'
    ? 'Runs on the local model. Changes are reviewed here and written after '
      + 'Refinix’s own checks — the Ubuntu sandbox tests do not run, and '
      + 'Refinix keeps a copy of every file it replaces so you can undo it.'
    : 'Generates on the paired Ubuntu worker and requires a passing sandbox '
      + 'validation before any file is written.';
  box.append(note);
}
