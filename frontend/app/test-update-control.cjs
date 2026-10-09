/* Offline regressions for the update control in the header (Chat, Code,
 * Settings) and the offline half of Settings -> Updates.
 * Run: node --test this-file
 *
 * The rules under test: the header control appears only in a build that can
 * update itself and only while the computer reports a connection — hidden in
 * every state when it does not; nothing checks on its own (loading, opening
 * the panel, polling and reconnecting only redraw); Settings keeps Cancel,
 * Install for a verified download, Import and the internal update folder
 * offline; a failed or unreachable check is never "up to date".
 *
 * Everything is synthetic. No request leaves the harness.
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');

const source = readFileSync(`${__dirname}/app.js`, 'utf8').replace(/^import .*$/m, '');

function makeDocument() {
  const node = (tag = 'div') => {
    const el = {
      tag, children: [], dataset: {}, style: {}, hidden: false, disabled: false,
      value: '', checked: false, className: '', title: '', _text: '', attrs: {},
      classList: { add() {}, remove() {} },
      set textContent(v) { this._text = String(v); this.children = []; },
      get textContent() {
        return this._text + this.children.map((c) => c.textContent).join('');
      },
      append(...kids) { for (const k of kids) this.children.push(k); },
      prepend(...kids) { this.children.unshift(...kids); },
      replaceChildren(...kids) { this.children = []; this.append(...kids); },
      setAttribute(name, value) { this.attrs[name] = String(value); },
      removeAttribute(name) { delete this.attrs[name]; },
      getAttribute(name) { return name in this.attrs ? this.attrs[name] : null; },
      addEventListener(type, fn) { this.listeners = { ...(this.listeners || {}), [type]: fn }; },
      querySelector() { return null; }, querySelectorAll() { return []; },
      getBoundingClientRect() { return { top: 0, left: 900, right: 940, bottom: 40 }; },
      focus() { this.focused = true; }, remove() {}, contains() { return false; },
      get isConnected() { return true; },
      get lastElementChild() { return this.children[this.children.length - 1]; },
    };
    return el;
  };
  const byId = new Map();
  const listeners = {};
  return {
    getElementById(id) {
      if (!byId.has(id)) byId.set(id, node(`#${id}`));
      return byId.get(id);
    },
    createElement: (tag) => node(tag),
    createTextNode: (text) => ({ textContent: String(text) }),
    createDocumentFragment: () => node('#fragment'),
    createElementNS: (_ns, tag) => node(tag),
    addEventListener(type, fn) { listeners[type] = fn; },
    listeners,
    body: node('body'),
  };
}

function page({ online = true, bridge = null } = {}) {
  const document = makeDocument();
  const requests = [];
  const windowListeners = {};
  const navigator = { onLine: online };
  const scope = vm.createContext({
    document,
    navigator,
    window: {
      addEventListener(type, fn) { windowListeners[type] = fn; },
      location: { port: '8770' }, innerWidth: 1000,
      pywebview: bridge ? { api: bridge } : undefined,
      matchMedia: () => ({ matches: false, addEventListener() {},
                           removeEventListener() {}, addListener() {},
                           removeListener() {} }),
    },
    fetch: (path, options) => new Promise((resolve, reject) => requests.push({
      path, options,
      reply(body = {}, ok = true) { resolve({ ok, json: async () => body }); },
      fail(message) { reject(new Error(message)); },
    })),
    localStorage: { getItem() { return null; }, setItem() {} },
    setTimeout: (fn) => { scope.timer = fn; return 1; },
    clearTimeout() {}, setInterval() { return 1; },
    requestAnimationFrame() {},
    console: { error() {}, log() {}, warn() {} },
  });
  vm.runInContext(source, scope);
  const run = (code) => vm.runInContext(code, scope);
  const el = (id) => document.getElementById(id);
  const text = (id) => el(id).textContent;
  return { run, requests, document, el, text, navigator, windowListeners };
}

const BASE = { version: '0.1.0-internal.1', channel: 'internal', lane: 'macos-arm64',
  header_eligible: true, can_check: true, can_import: true, source: 'https',
  install_supported: true, install: { state: 'idle' },
  install_note: 'Install and restart closes Refinix, replaces the app and opens it again.' };

function status(updates) {
  return JSON.stringify({ updates: { ...BASE, ...updates } });
}

function buttons(p, id) {
  return p.el(id).children.filter((c) => c.tag === 'button').map((b) => b.textContent);
}

const STATES = {
  offered: { offer: { version: '0.1.0-internal.2', size: 1048576, notes: 'Fixes.' } },
  downloading: { download: { state: 'running', version: '0.1.0-internal.2',
                             bytes_done: 5, bytes_total: 10 } },
  verified: { download: { state: 'verified', version: '0.1.0-internal.2' } },
  ready: { download: { state: 'verified', version: '0.1.0-internal.2' },
           install: { state: 'ready', version: '0.1.0-internal.2' } },
  failed: { last_check: { at: 't', result: 'unreachable', detail: 'no route' } },
};

function updatePage(state, bridge = null) {
  const p = page({ bridge });
  p.run(`lastStatus = ${status(state)};
    loadStatus = async () => {
      renderUpdateControl(lastStatus); renderUpdatesCard(lastStatus); return lastStatus;
    };
    renderUpdatesCard(lastStatus); renderUpdateControl(lastStatus); openUpdatePopover();`);
  return p;
}

test('rapid clicks share one request across Settings and the header, and retry after failure', async () => {
  for (const [label, state, path] of [
    ['Check for updates', {}, '/v1/updates/check'],
    ['Download 0.1.0-internal.2', STATES.offered, '/v1/updates/download'],
    ['Cancel download', STATES.downloading, '/v1/updates/cancel'],
  ]) {
    const p = updatePage(state);
    const click = (id) => p.el(id).children.find(b => b.textContent === label).onclick;
    const settings = click('c-updates-actions');
    const header = click('update-popover-actions');
    const attempts = Array.from({ length: 20 }, (_, i) => (i % 2 ? header : settings)());
    assert.equal(p.requests.length, 1, `${label}: only one request`);
    assert.equal(p.requests[0].path, path);
    assert.deepEqual(buttons(p, 'c-updates-actions'), [], 'Settings locks immediately');
    assert.deepEqual(buttons(p, 'update-popover-actions'), ['Later'], 'header locks too');
    p.requests[0].fail('request failed');
    await Promise.all(attempts);
    assert.equal(p.run('updateBusy'), '', `${label}: failure allows retry`);
    const retry = settings();
    assert.equal(p.requests.length, 2);
    p.requests[1].reply({});
    await retry;
  }
});

test('rapid import clicks open one chooser and cancellation allows retry', async () => {
  let count = 0, reply;
  const p = updatePage({}, { choose_update_bundle() {
    count += 1;
    return new Promise(resolve => { reply = resolve; });
  } });
  const click = p.el('c-updates-actions').children.find(b => b.textContent === 'Import update…').onclick;
  const attempts = Array.from({ length: 20 }, () => click());
  assert.equal(count, 1);
  assert.match(p.text('update-popover-state'), /Importing/);
  reply({ cancelled: true });
  await Promise.all(attempts);
  const retry = click();
  assert.equal(count, 2);
  reply({ cancelled: true });
  await retry;
});

test('Install locks before preparation and calls the native installer once', async () => {
  for (const state of [STATES.verified, STATES.ready]) {
    let count = 0, reply;
    const p = updatePage(state, { install_update() {
      count += 1;
      return new Promise(resolve => { reply = resolve; });
    } });
    const click = p.el('c-updates-actions').children.find(b => b.textContent === 'Install and restart').onclick;
    const attempts = Array.from({ length: 20 }, () => click());
    assert.deepEqual(buttons(p, 'c-updates-actions'), []);
    if (state === STATES.verified) {
      assert.equal(p.requests.length, 1, 'one preparation request');
      assert.equal(p.requests[0].path, '/v1/updates/prepare');
      p.requests[0].reply({});
      await new Promise(setImmediate);
      p.run(`lastStatus = ${status(STATES.ready)}; timer()`);
      await new Promise(setImmediate);
    }
    assert.equal(count, 1);
    await Promise.all(Array.from({ length: 20 }, () => click()));
    assert.equal(count, 1, 'no extra native calls while confirmation is pending');
    reply({ cancelled: true });
    await Promise.all(attempts);
    assert.equal(p.run('updateBusy'), '', 'declined installation allows retry');
    const retry = click();
    assert.equal(count, 2);
    reply({ installing: true });
    await retry;
    await click();
    assert.equal(count, 2, 'keep locked while the app closes');
  }
});

test('offline, the header control is hidden in every state', () => {
  for (const [name, state] of Object.entries(STATES)) {
    const p = page({ online: false });
    p.run(`renderUpdateControl(${status(state)})`);
    assert.equal(p.el('update-toggle').hidden, true, name);
  }
});

test('online, it appears only for a build that can update itself', () => {
  const p = page();
  p.run(`renderUpdateControl(${status({})})`);
  assert.equal(p.el('update-toggle').hidden, false);
  for (const off of [{ header_eligible: false }, {}]) {
    const q = page();
    q.run(`renderUpdateControl(${JSON.stringify({ updates: off })})`);
    assert.equal(q.el('update-toggle').hidden, true);
  }
});

test('drawing, opening the panel and reconnecting never check for updates', () => {
  const p = page({ online: false });
  p.run('wireUpdateControl()');
  p.run(`lastStatus = ${status(STATES.offered)}; renderUpdateControl(lastStatus)`);
  assert.ok(p.windowListeners.online && p.windowListeners.offline, 'connection is watched');
  p.navigator.onLine = true;
  p.windowListeners.online();
  assert.equal(p.el('update-toggle').hidden, false);
  p.run('openUpdatePopover()');
  assert.equal(p.el('update-toggle').getAttribute('aria-expanded'), 'true');
  p.navigator.onLine = false;
  p.windowListeners.offline();
  assert.equal(p.el('update-toggle').hidden, true);
  assert.equal(p.el('update-popover').hidden, true, 'the panel closes when offline');
  assert.equal(p.requests.length, 0, 'no request was made without a click');
});

test('the button says what state it is in, and the dot means a verified offer', () => {
  const p = page();
  p.run(`renderUpdateControl(${status(STATES.ready)})`);
  assert.match(p.el('update-toggle').getAttribute('aria-label'), /ready to install/);
  assert.equal(p.el('update-dot').hidden, false);
  const q = page();
  q.run(`renderUpdateControl(${status({ last_check: { at: 't', result: 'up_to_date',
                                                      detail: 'newest' } })})`);
  assert.equal(q.el('update-dot').hidden, true);
  assert.match(q.el('update-toggle').getAttribute('aria-label'), /up to date/);
});

test('the panel opens, offers the next step and closes with focus back on the button', () => {
  const bridge = { install_update() {} };
  const p = page({ bridge });
  p.run(`lastStatus = ${status(STATES.verified)}; renderUpdateControl(lastStatus)`);
  p.run('openUpdatePopover()');
  assert.equal(p.el('update-popover').hidden, false);
  const labels = buttons(p, 'update-popover-actions');
  assert.deepEqual(labels, ['Install and restart', 'Check for updates', 'Later']);
  assert.match(p.text('update-popover-state'), /downloaded and verified/);
  p.run('closeUpdatePopover(true)');
  assert.equal(p.el('update-popover').hidden, true);
  assert.equal(p.el('update-toggle').getAttribute('aria-expanded'), 'false');
  assert.ok(p.el('update-toggle').focused);
});

test('an unreachable or failed check is never shown as up to date', () => {
  const p = page();
  p.run(`renderUpdatesCard(${status({ last_check: { at: 't', result: 'unreachable',
    detail: "Couldn't reach the update server: no route.", last_success: 'earlier' } })})`);
  assert.match(p.text('c-updates-chip'), /couldn't reach/);
  assert.doesNotMatch(p.text('c-updates-chip'), /up to date/);
  assert.match(p.text('c-updates-note'), /Last successful check: earlier/);
  const q = page();
  q.run(`renderUpdatesCard(${status({ source: 'folder', last_check: { at: 't',
    result: 'incomplete', detail: 'Not every bundle was checked.' } })})`);
  assert.match(q.text('c-updates-chip'), /not all checked/);
});

test('Settings keeps the offline actions and drops only the connected ones', () => {
  const bridge = { install_update() {}, choose_update_bundle() {} };
  const p = page({ online: false, bridge });
  p.run(`renderUpdatesCard(${status(STATES.verified)})`);
  const labels = buttons(p, 'c-updates-actions');
  assert.ok(labels.includes('Install and restart'));
  assert.ok(labels.includes('Import update…'));
  assert.ok(!labels.includes('Check for updates'));
  assert.match(p.text('c-updates-note'), /Connect to the internet to check for updates/);
  const running = page({ online: false, bridge });
  running.run(`renderUpdatesCard(${status(STATES.downloading)})`);
  assert.deepEqual(buttons(running, 'c-updates-actions'), ['Cancel download']);
});

test('a Beta install says how installing was checked, and never calls it accepted', () => {
  const p = page({ online: true });
  p.run(`renderUpdatesCard(${status({ version: '0.1.0-beta.1', channel: 'beta',
    maturity: 'beta', install_capability: 'provisional' })})`);
  const facts = p.text('c-updates-facts');
  assert.match(facts, /0\.1\.0-beta\.1 \(Beta\)/);
  assert.match(facts, /checked on hosted test machines; not yet confirmed on your kind of computer/);
  assert.doesNotMatch(facts, /accepted|qualified/i);
  const internal = page({ online: true });
  internal.run(`renderUpdatesCard(${status({ install_capability: 'internal-test' })})`);
  assert.doesNotMatch(internal.text('c-updates-facts'), /hosted test machines/);
});

test('internal builds check their update folder, from Settings even offline', () => {
  const p = page({ online: false });
  p.run(`renderUpdatesCard(${status({ source: 'folder', folder: '/Users/x/Refinix Updates' })})`);
  assert.ok(buttons(p, 'c-updates-actions').includes('Check update folder'));
  assert.match(p.text('c-updates-facts'), /Refinix Updates/);
  const header = page();
  header.run(`lastStatus = ${status({ source: 'folder' })}; renderUpdateControl(lastStatus);
              openUpdatePopover()`);
  assert.ok(buttons(header, 'update-popover-actions').includes('Check for updates'));
});

test('a folder offer is copied, not downloaded, and needs no connection', () => {
  const p = page({ online: false });
  p.run(`renderUpdatesCard(${status({ source: 'folder', offer: { version: '0.1.0-internal.2',
    size: 1, notes: '', source: { kind: 'bundle' } } })})`);
  assert.ok(buttons(p, 'c-updates-actions').includes('Get 0.1.0-internal.2 from the update folder'));
});

test('without install capability there is no Install button, and the reason is shown', () => {
  const bridge = { install_update() {} };
  const p = page({ bridge });
  p.run(`renderUpdatesCard(${status({ ...STATES.verified, install_supported: false,
    install_reason: 'Refinix can update itself only when it is in Applications.' })})`);
  assert.ok(!buttons(p, 'c-updates-actions').includes('Install and restart'));
  assert.match(p.text('c-updates-note'), /only when it is in Applications/);
});

test('every page carries the same accessible control and panel', () => {
  for (const name of ['index', 'code', 'control']) {
    const html = readFileSync(`${__dirname}/${name}.html`, 'utf8');
    assert.match(html, /id="update-toggle"[^>]*aria-haspopup="dialog"[\s\S]*?aria-controls="update-popover"/,
      `${name}: button`);
    assert.match(html, /id="update-popover" role="dialog"/, `${name}: panel`);
    assert.match(html, /id="update-popover-state" aria-live="polite"/, `${name}: live state`);
    assert.ok(html.indexOf('id="update-toggle"') < html.indexOf('id="theme-toggle"'),
      `${name}: beside the theme toggle, to its left`);
  }
});

test('a saved document reads as a document in the lifecycle, never "undefined"', () => {
  const p = page();
  p.run(`pushEvent({ occurred_at: '2026-10-07T10:00:00Z',
    data: { kind: 'artifact.created', artifact: { media_type: 'application/pdf' } } })`);
  const row = p.el('events').children[0];
  assert.doesNotMatch(row.textContent, /undefined/);
  assert.match(row.textContent, /document saved \(application\/pdf\)/);
  p.run(`pushEvent({ occurred_at: '2026-10-07T10:00:01Z',
    data: { kind: 'attempt.state', previous: 'running', current: 'completed' } })`);
  assert.match(p.el('events').children[0].textContent, /running → completed/);
});


test('the Ubuntu package route prepares behind a password before Install appears', () => {
  const bridge = { install_update: async () => ({}) };
  const deb = { ...STATES.verified, install_method: 'deb', maturity: 'preview',
                version: '0.1.0-preview.1', channel: 'beta' };
  let p = updatePage(deb, bridge);
  assert.deepEqual(buttons(p, 'c-updates-actions').filter((b) => /Prepare|Install/.test(b)),
                   ['Prepare (asks for your password)']);
  assert.match(p.text('c-updates-note'), /administrator password/);
  assert.match(p.text('c-updates-facts'), /0\.1\.0-preview\.1 \(tester preview\)/);
  p = updatePage({ ...deb, install: { state: 'ready', version: '0.1.0-preview.2' } }, bridge);
  assert.deepEqual(buttons(p, 'c-updates-actions').filter((b) => /Prepare|Install/.test(b)),
                   ['Install and restart']);
  // The macOS and Windows routes keep the single Install and restart step.
  p = updatePage({ ...STATES.verified, install_method: 'windows-setup' }, bridge);
  assert.ok(buttons(p, 'c-updates-actions').includes('Install and restart'));
});
