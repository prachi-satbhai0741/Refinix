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

function turn(role, text, attachments, plain) {
  const article = document.createElement('article');
  article.className = `turn turn-${role === 'user' ? 'user' : 'agent'}`;
  const box = document.createElement('div');
  box.className = role === 'user' ? 'bubble' : 'prose';
  if (role === 'user') {
    box.textContent = text;
  } else {
    box.dataset.raw = text;          // literal source, used for copy and re-render
    renderMarkdown(box, text);
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
    note.textContent = attachments.length === 1
      ? 'This file was saved with your request. Refinix cannot read documents yet, so the reply came from your text alone.'
      : 'These files were saved with your request. Refinix cannot read documents yet, so the reply came from your text alone.';
    article.append(note);
  }
  if (role !== 'user' && !plain) {
    const bar = document.createElement('div');
    bar.className = 'turn-meta';
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'code-copy';
    copy.textContent = 'Copy reply';
    copy.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(box.dataset.raw || '');
        copy.textContent = 'Copied';
      } catch { copy.textContent = 'Copy failed'; }
      setTimeout(() => { copy.textContent = 'Copy reply'; }, 1500);
    });
    bar.append(copy);
    article.append(bar);
  }
  $('thread').append(article);
  maybeFollow();
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
  refreshSend();
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
  const input = $('input');
  if (input) input.focus();
}

/* The label is structured selection state, not editable prompt text: it lives
 * outside the textarea, is reachable by Tab, and Backspace at the start of an
 * empty-prefix request removes it. */
function renderSkill() {
  const chip = $('skill-chip');
  const status = $('skill-status');
  const hint = $('send-hint');
  if (!chip) return;
  const skill = selectedSkill();
  const live = skill ? (capabilities.find((c) => c.id === skill.id) || skill) : null;
  if (live) skillByChat.set(currentSlot(), live);

  if (!live) {
    chip.hidden = true;
    if (status) { status.hidden = true; status.textContent = ''; }
    if (hint) hint.textContent = 'Runs on this computer';
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
    // with the name only repeats it.
    status.textContent = live.state === 'available' ? '' : live.detail;
  }
  if (hint) {
    hint.textContent = live.state === 'available'
      ? 'Runs on this computer' : 'Remove the skill to send an ordinary request';
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

async function openChat(id) {
  if (chatId !== id) {
    saveDraftSoon(true);                  // capture and flush the old chat first
    chatId = id;
    publishSlot();
    loadDraft(id);
    loadStaged();
    renderSkill();
  }
  activeJob = null;
  streamBox = null;
  lastSequence = 0;
  pendingEvents = new Map();
  const { messages } = await api(`/v1/messages?chat_id=${id}`);
  if (chatId !== id) return;
  $('thread').replaceChildren();
  if (!messages.length)
    turn('assistant', 'No messages in this conversation yet.', null, true);
  for (const m of messages) {
    const box = turn(m.role, m.text, m.attachments);
    if (m.error_json) {
      const note = document.createElement('p');
      note.className = 'chip-caution';
      note.textContent = JSON.parse(m.error_json).message;
      box.append(note);
    }
  }
  // Restart reconciliation is visible here: a job that was interrupted keeps
  // its record, and its conversation still loads.
  const { jobs } = await api(`/v1/jobs?chat_id=${id}`);
  if (chatId !== id) return;
  const last = jobs[0];
  if (last) {
    jobState = last.state;
    renderLife(last.state);
    // Replay the recorded events so the rail shows what actually happened
    // rather than looking as though nothing did.
    $('events').replaceChildren();
    deltaCount = 0; deltaChars = 0;
    const detail = await api(`/v1/job?job_id=${last.job_id}`).catch(() => null);
    if (chatId !== id) return;
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
  const { job_id } = await api('/v1/messages', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: targetId, text,
      draft_id: sourceId || NEW_CHAT_DRAFT, draft_text: draftText ?? text }),
  });
  if (chatId !== sourceId || (sourceId === null && draftVersion !== version)) {
    loadChats();
    return;
  }
  if (draftText !== null && draftVersion === version && $('input').value === draftText) {
    $('input').value = '';
    ++draftVersion;
    if ($('draft-mark')) $('draft-mark').hidden = true;
  }
  // The selection was made against the draft slot and is bound to the request
  // the coordinator just accepted; move any local record with it.
  const sentFiles = staged.length;
  staged = [];
  renderStaged();
  const skill = skillByChat.get(sourceId || NEW_DRAFT_SLOT);
  if (skill && targetId !== (sourceId || NEW_DRAFT_SLOT)) {
    skillByChat.delete(NEW_DRAFT_SLOT);
    skillByChat.set(targetId, skill);
  }
  chatId = targetId;
  publishSlot();
  // Read persisted messages/output after acceptance; generation may already
  // have emitted events before the POST response reached this browser.
  await openChat(chatId);
  if (sentFiles) {
    notice(`${sentFiles} file${sentFiles === 1 ? '' : 's'} went with your request.`,
           'warn',
           'Refinix saved them on this computer. It cannot read documents yet, '
           + 'so the reply comes from your typed request alone.');
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

function renderOthersCard(s) {
  if (!$('c-others-facts')) return;
  chip($('c-others-chip'), 'none connected', 'unknown');
  $('c-others-lead').textContent =
    'Refinix can share work with other computers you connect. None is connected, '
    + 'so everything runs here.';
  facts($('c-others-facts'), [
    ['Connected computers', null, 'none'],
    ['This computer', `${s.node_id.slice(0, 8)} — the only one in use`],
  ]);
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
    li.append(text, stop);
    host.append(li);
  }
  actions($('c-work-actions'), [
    { label: 'View work', run: () => { location.href = '/'; } },
    { label: 'Refresh', run: () => loadStatus().catch(() => {}) },
  ]);
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

function renderAdvanced(s, jobs) {
  if (!$('kv-runtime')) return;
  const r = s.runtime;
  kv($('kv-runtime'), [
    ['endpoint', r.endpoint],
    ['reachable', r.reachable ? 'yes' : 'no'],
    ['server version', r.server_version, r.error || 'no server answered'],
    ['loaded model', r.loaded && r.loaded.model, 'nothing resident'],
    ['resident bytes', r.loaded && r.loaded.size_bytes, 'not reported'],
    ['GPU bytes', r.loaded && r.loaded.size_vram_bytes, 'not reported'],
    ['probe error', r.error, 'none'],
  ]);
  kv($('kv-models'), [
    ['configured', s.model_configured],
    ['installed', r.models.length ? r.models.join(', ') : null, 'runtime did not answer'],
    ['num_ctx', s.bounded.num_ctx],
    ['num_predict', s.bounded.num_predict],
    ['thinking', s.bounded.think ? 'on' : 'off (required for this model)'],
  ]);
  kv($('kv-context'), [
    ['context window', `${s.context.window_tokens} tokens`],
    ['reply allowance', `${s.context.reply_allowance_tokens} tokens`],
    ['conversation budget', `${s.context.conversation_budget_tokens} tokens`],
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
  const counts = Object.entries(s.jobs_by_state);
  kv($('kv-jobs'), counts.length ? counts : [['jobs', null, 'none recorded yet']]);
  kv($('kv-unavailable'), Object.entries(s.unavailable).map(([k, v]) => [k, null, v]));
  const ul = $('job-list');
  if (ul) {
    ul.replaceChildren();
    for (const j of jobs.slice(0, 12)) {
      const li = document.createElement('li');
      const kind = document.createElement('span');
      kind.className = 'kind';
      kind.textContent = j.state;
      const time = document.createElement('time');
      time.textContent = j.created_at.slice(11, 19);
      li.append(kind, document.createTextNode(' ' + j.original_request.slice(0, 60)), time);
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
  renderReadyLine(s);
  renderSkill();
  if ($('kv-unavailable') && !$('c-cap-list')) {
    // Chat's Details rail carries the same "not observed" list.
    kv($('kv-unavailable'), Object.entries(s.unavailable).map(([k, v]) => [k, null, v]));
  }
  if (!$('c-computer-facts')) return s;
  const { jobs } = await api('/v1/jobs');
  renderComputerCard(s);
  renderEngineCard(s);
  renderOthersCard(s);
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

/* Both drawers: click, Escape and scrim all close them. */
function wireDrawer(toggleId, panelId) {
  const toggle = $(toggleId), panel = $(panelId), scrim = $('scrim');
  if (!toggle || !panel) return;
  const set = (open) => {
    panel.dataset.open = String(open);
    toggle.setAttribute('aria-expanded', String(open));
    if (scrim) scrim.dataset.open = String(open);
  };
  set(false);
  toggle.addEventListener('click', () => set(panel.dataset.open !== 'true'));
  if (scrim) scrim.addEventListener('click', () => set(false));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && panel.dataset.open === 'true') {
      set(false);
      toggle.focus();
    }
  });
}

window.addEventListener('DOMContentLoaded', () => {
  wireDrawer('nav-toggle', 'nav');
  wireDrawer('rail-toggle', 'rail');
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
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && openMenu) closeMenu();
    if (e.key === 'Escape' && plusMenu) { closePlusMenu(); $('plus-btn').focus(); }
  });
  publishSlot();
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
  } else if ($('refresh')) {
    $('refresh').onclick = () => loadStatus().catch(() => {});
    setInterval(() => loadStatus().catch(() => {}), 10000);
  }
});
