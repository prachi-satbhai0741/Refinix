/* AegisForge C03 UI.
 *
 * Every value rendered here comes from the coordinator. Nothing is defaulted to
 * a healthy-looking state: a missing observation renders as `unavailable`, which
 * the stylesheet hatches so it can never be mistaken for a measurement.
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

function turn(role, text) {
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
  if (role !== 'user') {
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
    const chip = $('job-chip');
    chip.textContent = d.current.replace(/_/g, ' ');
    chip.className = 'chip ' + (
      d.current === 'running' ? 'chip-running'
      : d.current === 'completed' ? 'chip-enforced'
      : ['failed', 'cancelled', 'denied'].includes(d.current) ? 'chip-fault'
      : d.current === 'interrupted' ? 'chip-caution' : 'chip-unknown');
    const done = ['completed', 'failed', 'cancelled', 'denied', 'interrupted'];
    $('cancel-btn').hidden = done.includes(d.current);
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
  if (!activeJob) return;
  const detail = await api(`/v1/job?job_id=${activeJob}`).catch(() => null);
  const a = detail && detail.attempts[detail.attempts.length - 1];
  if (a && a.selection) contextNotice(a.selection);
}

async function refreshAttempt() {
  if (!activeJob) return;
  const detail = await api(`/v1/job?job_id=${activeJob}`).catch(() => null);
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
    ['detail', err ? err.message : metrics.done_reason === 'stop'
      ? 'Model finished normally' : null, 'not recorded'],
  ]);
}

/* ---- conversation management ----------------------------------------- */

const NEW_CHAT_DRAFT = '__new__';
let searchTimer = null;
let draftTimer = null;
let openMenu = null;

/* Drafts live in coordinator state, so they survive a refresh or restart.
 * They are never sent to the model and never appear in search or export. */
async function loadDraft(id) {
  const input = $('input');
  if (!input) return;
  const { text } = await api(`/v1/draft?chat_id=${encodeURIComponent(id || NEW_CHAT_DRAFT)}`)
    .catch(() => ({ text: '' }));
  input.value = text || '';
  const mark = $('draft-mark');
  if (mark) mark.hidden = !text;
}

function saveDraftSoon(immediate = false) {
  const input = $('input');
  if (!input) return;
  clearTimeout(draftTimer);
  const send = () => api('/v1/draft', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId || NEW_CHAT_DRAFT, text: input.value }),
  }).catch(() => {});                 // a failed draft save must not interrupt typing
  if (immediate) send(); else draftTimer = setTimeout(send, 600);
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
  item('Delete chat', async () => {
    const yes = await confirmDialog(
      `Delete “${chat.title}”?`,
      'Its messages and run history will be removed. This cannot be undone.',
      'Delete chat');
    if (!yes) return;
    await api('/v1/chat/delete', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chat.chat_id }),
    }).catch((e) => notice('Could not delete the chat.', 'error', e.message));
    if (chat.chat_id === chatId) {
      chatId = null; activeJob = null;
      $('thread').replaceChildren();
      $('events').replaceChildren();
      renderLife(null);
    }
    loadChats();
  }, true);

  document.body.append(menu);
  openMenu = menu;
  menu.querySelector('button').focus();
}

/* Export is an explicit download of saved history. The link is created,
 * clicked and revoked in one gesture; nothing is fetched remotely. */
async function downloadExport(chat, fmt) {
  try {
    const url = `/v1/export?chat_id=${encodeURIComponent(chat.chat_id)}&format=${fmt}`;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const blob = await resp.blob();
    const name = (resp.headers.get('Content-Disposition') || '')
      .match(/filename="([^"]+)"/)?.[1] || `conversation.${fmt}`;
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
  if (chatId !== id) saveDraftSoon(true);   // flush before leaving
  chatId = id;
  activeJob = null;
  streamBox = null;
  lastSequence = 0;
  pendingEvents = new Map();
  const { messages } = await api(`/v1/messages?chat_id=${id}`);
  if (chatId !== id) return;
  $('thread').replaceChildren();
  if (!messages.length) turn('assistant', 'No messages in this conversation yet.');
  for (const m of messages) {
    const box = turn(m.role, m.text);
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
    const stopped = ['completed', 'failed', 'cancelled', 'denied', 'interrupted'];
    $('cancel-btn').hidden = stopped.includes(jobState);
    const chip = $('job-chip');
    renderLife(jobState);
    chip.textContent = jobState.replace(/_/g, ' ');
    chip.className = 'chip ' + (jobState === 'completed' ? 'chip-enforced'
      : jobState === 'interrupted' ? 'chip-caution'
      : ['failed', 'cancelled', 'denied'].includes(jobState) ? 'chip-fault' : 'chip-unknown');
    refreshAttempt();
    replayEvents();
  } else {
    renderLife(null);
    $('cancel-btn').hidden = true;
    $('job-chip').textContent = 'no job';
    $('events').replaceChildren();
    $('attempt-kv').replaceChildren();
  }
  loadChats();
  loadDraft(id);
}

async function send(text) {
  if (!chatId) {
    const { chat_id } = await api('/v1/chats', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: text.slice(0, 60) }),
    });
    chatId = chat_id;
  }
  streamBox = null;
  const { job_id } = await api('/v1/messages', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId, text }),
  });
  // Read persisted messages/output after acceptance; generation may already
  // have emitted events before the POST response reached this browser.
  await openChat(chatId);
}

/* ------------------------------------------------------------- Control --- */

async function loadControl() {
  const s = await api('/v1/status');
  const r = s.runtime;
  $('foot-node') && ($('foot-node').textContent = s.node_id.slice(0, 8));
  $('foot-bind') && ($('foot-bind').textContent = s.bind + ' only');

  if ($('kv-runtime')) {
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
    kv($('kv-contract'), [
      ['version', s.contract_version],
      ['status', s.contract_status],
      ['workspace', s.workspace_id.slice(0, 8)],
    ]);
    const counts = Object.entries(s.jobs_by_state);
    kv($('kv-jobs'), counts.length ? counts : [['jobs', null, 'none recorded yet']]);
    kv($('kv-surfaces'), Object.entries(s.surfaces));
    kv($('kv-unavailable'), Object.entries(s.unavailable).map(
      ([k, v]) => [k, null, v]));
    kv($('kv-restart'), [
      ['jobs repaired on start', s.repaired_on_start],
      ['method', 'attempts left executing become interrupted with a typed reason'],
    ]);
    const { jobs } = await api('/v1/jobs');
    const ul = $('job-list');
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
    $('refreshed').textContent = 'read at ' + new Date().toTimeString().slice(0, 8);
  }
  if ($('foot-runtime')) {
    $('foot-runtime').textContent = r.reachable
      ? `ollama ${r.server_version}` : 'unavailable';
  }
  if ($('head-model')) $('head-model').textContent = s.model_configured;
}

/* ----------------------------------------------------------------- boot -- */

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
  if (draftInput) draftInput.addEventListener('input', () => saveDraftSoon());
  document.addEventListener('click', (e) => {
    if (openMenu && !openMenu.contains(e.target)) closeMenu();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && openMenu) closeMenu();
  });
  loadControl().catch((e) => console.error('status unavailable:', e.message));
  if ($('composer')) {
    connect();
    loadChats().then(() => api('/v1/chats')).then(({ chats }) => {
      if (chats.length) openChat(chats[0].chat_id);
      else { renderLife(null); loadDraft(null); }
    }).catch((e) => console.error(e.message));

    $('composer').onsubmit = async (e) => {
      e.preventDefault();
      const input = $('input');
      const text = input.value.trim();
      if (!text) return;
      if (sending) {
        notice('A reply is still running.', 'warn',
               'Stop it first, or wait for it to finish. Your draft is kept.');
        return;
      }
      sending = true;
      input.disabled = true;
      $('send').disabled = true;
      try {
        await send(text);
        input.value = '';          // cleared only once the job is accepted
      } catch (err) {
        notice('Could not send that request.', 'error', err.message);
      } finally {
        sending = false;
        input.disabled = false;
        $('send').disabled = false;
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
    $('new-chat').onclick = async () => {
      chatId = null; activeJob = null;
      streamBox = null; jobState = null; lastSequence = 0;
      pendingEvents = new Map();
      $('cancel-btn').hidden = true;
      $('job-chip').textContent = 'no job';
      $('attempt-kv').replaceChildren();
      $('thread').replaceChildren();
      $('events').replaceChildren();
      deltaCount = 0; deltaChars = 0;
      renderLife(null);
      turn('assistant', 'New conversation. Send a request to start a job.');
      loadDraft(null);            // a draft typed before the chat exists
    };
    $('cancel-btn').onclick = () => {
      if (!activeJob) return;
      api('/v1/cancel', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: activeJob }),
      }).catch((e) => console.error(e.message));
    };
    setInterval(() => loadControl().catch(() => {}), 10000);
    // SSE is a notification channel; SQLite supplies any missed events.
    setInterval(() => {
      if (['running', 'queued', 'routing', 'context_preparing', 'created', 'validating']
          .includes(jobState)) replayEvents();
    }, 2000);
  } else if ($('refresh')) {
    $('refresh').onclick = () => loadControl().catch(() => {});
    setInterval(() => loadControl().catch(() => {}), 10000);
  }
});
