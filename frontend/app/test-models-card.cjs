/* Offline regressions for Settings -> Models.
 * Run: node --test this-file
 *
 * This card exists so a person can see which models Refinix supports, which
 * are actually here, and what has been checked — for the installation's
 * lifetime, not only during setup. The failures it is written against are all
 * the same kind of lie:
 *
 *   * showing a model as ready when nothing was self-tested;
 *   * showing "none installed" when the engine simply did not answer;
 *   * presenting a model with no recorded source or licence as though Refinix
 *     had verified it;
 *   * implying a switch-off or a removal takes conversations with it;
 *   * naming a fixed operating system where the product means a role.
 *
 * Everything is synthetic. No engine, no model, no request leaves the harness.
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
      value: '', checked: false, className: '', title: '', _text: '',
      classList: { add() {}, remove() {} },
      set textContent(v) { this._text = String(v); this.children = []; },
      get textContent() {
        return this._text + this.children.map((c) => c.textContent).join('');
      },
      append(...kids) { for (const k of kids) this.children.push(k); },
      replaceChildren(...kids) { this.children = []; this.append(...kids); },
      setAttribute() {}, removeAttribute() {}, addEventListener() {},
      querySelector() { return null; }, querySelectorAll() { return []; },
      getBoundingClientRect() { return { top: 0, left: 0, right: 0, bottom: 0 }; },
      focus() {}, remove() {}, reset() {},
      contains() { return false; },
      get isConnected() { return true; },
    };
    return el;
  };
  const byId = new Map();
  return {
    getElementById(id) {
      if (!byId.has(id)) byId.set(id, node(`#${id}`));
      return byId.get(id);
    },
    createElement: (tag) => node(tag),
    createDocumentFragment: () => node('#fragment'),
    createElementNS: (_ns, tag) => node(tag),
    addEventListener() {},
    body: node('body'),
  };
}

function page() {
  const document = makeDocument();
  const requests = [];
  const scope = vm.createContext({
    document,
    window: {
      addEventListener() {}, location: { port: '8770' },
      matchMedia: () => ({ matches: false, addEventListener() {},
                           removeEventListener() {}, addListener() {},
                           removeListener() {} }),
    },
    navigator: {},
    fetch: (path, options) => new Promise((resolve, reject) => requests.push({
      path, options,
      body: options && options.body ? JSON.parse(options.body) : null,
      reply(body = {}, ok = true) { resolve({ ok, json: async () => body }); },
      fail(message) { reject(new Error(message)); },
    })),
    setTimeout: (fn) => { scope.timer = fn; return 1; },
    clearTimeout() {}, setInterval() { return 1; },
    console: { error() {}, log() {}, warn() {} },
  });
  vm.runInContext(source, scope);
  return {
    run: (code) => vm.runInContext(code, scope),
    requests, document,
    text: (id) => document.getElementById(id).textContent,
    rows: () => document.getElementById('c-model-list').children,
  };
}

const INSTALLED = {
  id: 'qwen3.5:4b-q4_K_M',
  installed: true,
  state: 'installed',
  enabled: true,
  locations: ['this computer'],
  eligible_scopes: ['chat', 'code', 'documents.generate'],
  selected_for: ['chat'],
  digests: { local: 'a'.repeat(64), worker: null },
  provenance: {
    known: true, source: 'registry.ollama.ai/library/qwen3.5, tag 4b-q4_K_M',
    licence: 'Apache-2.0', format: 'GGUF, Q4_K_M',
    evidence: 'Integrity verified from the manifest and blobs.',
    evidence_state: 'verified',
  },
  setup: null,
  selftests: {
    chat: { scope: 'chat', state: 'passed', detail: 'ok', ran_at: 'now',
            superseded: false, current: true },
  },
};

const ABSENT = {
  id: 'qwen3.5:4b-q4_K_M',
  installed: false,
  state: 'absent',
  enabled: true,
  locations: [],
  eligible_scopes: [],
  selected_for: ['chat'],
  digests: { local: null, worker: null },
  provenance: { known: true, source: 'registry.ollama.ai/library/qwen3.5',
                licence: 'Apache-2.0', evidence: 'Integrity verified.',
                evidence_state: 'verified' },
  setup: { kind: 'command', label: 'Install it yourself',
           command: 'ollama pull qwen3.5:4b-q4_K_M' },
  selftests: {},
};

const UNLISTED = {
  id: 'somebody/random:latest',
  installed: true,
  state: 'unlisted',
  enabled: true,
  locations: ['this computer'],
  eligible_scopes: ['chat', 'code'],
  selected_for: [],
  digests: { local: 'b'.repeat(64), worker: null },
  provenance: { known: false, evidence_state: 'unverified',
                note: 'Refinix has no recorded source, licence or manifest '
                      + 'for this model.' },
  setup: null,
  selftests: {},
};

function status(over = {}) {
  return Object.assign({
    runtime: { reachable: true, endpoint: 'http://127.0.0.1:11434' },
    models: [INSTALLED],
    selftest_scopes: ['chat', 'code', 'documents.generate', 'documents.ocr'],
  }, over);
}

/* Every button in a card, wherever it sits: the checks live under Details. */
function allButtons(node) {
  const found = node.tag === 'button' ? [node] : [];
  for (const child of node.children || []) found.push(...allButtons(child));
  return found;
}

function render(over = {}) {
  const p = page();
  p.run(`renderModelsCard(${JSON.stringify(status(over))})`);
  return p;
}

test('an installed catalogue model shows its recorded source and licence', () => {
  const p = render();
  const row = p.rows()[0].textContent;
  assert.match(row, /qwen3\.5:4b-q4_K_M/);
  assert.match(row, /registry\.ollama\.ai/);
  assert.match(row, /Apache-2\.0/);
  assert.match(p.text('c-models-chip'), /1 here/);
});

test('a worker-only model is never counted as installed on this computer', () => {
  const remote = Object.assign({}, INSTALLED, {
    locations: ['paired worker'],
    digests: { local: null, worker: 'a'.repeat(64) },
  });
  const p = render({ models: [remote] });
  assert.match(p.text('c-models-chip'), /0 here/);
  assert.match(p.text('c-models-lead'), /0 model\(s\) are installed on this computer/);
  assert.match(p.text('c-models-lead'), /1 are visible on a paired worker/);
});

test('an absent Ollama model is explained without a terminal command or download', () => {
  const p = render({ models: [ABSENT] });
  const row = p.rows()[0].textContent;
  assert.match(row, /Available through Ollama/);
  assert.doesNotMatch(row, /ollama pull/, 'Refinix gives no terminal steps');
  assert.match(row, /not installed/);
  assert.match(p.text('c-models-lead'), /1 Refinix supports are not/);
  assert.equal(p.requests.length, 0, 'showing a model must not call anything');
});

test('an absent model Refinix does not vouch for is not counted as supported', () => {
  const p = render({ models: [Object.assign({}, UNLISTED, {
    installed: false, state: 'absent', locations: [] })] });
  assert.doesNotMatch(p.text('c-models-lead'), /Refinix supports/);
  assert.match(p.rows()[0].textContent, /not installed/);
});

test('a model with no recorded provenance is labelled unverified, not verified', () => {
  const p = render({ models: [UNLISTED] });
  const row = p.rows()[0].textContent;
  assert.match(row, /unverified/);
  assert.match(row, /no recorded source/);
  assert.doesNotMatch(row, /Apache/);
});

test('an engine that did not answer means unknown, never "none installed"', () => {
  const p = render({ runtime: { reachable: false, endpoint: 'x' },
                     models: [Object.assign({}, INSTALLED,
                                            { state: 'unavailable',
                                              installed: false,
                                              locations: [] })] });
  assert.match(p.text('c-models-lead'), /unknown/);
  assert.doesNotMatch(p.text('c-models-lead'), /0 model/);
  assert.match(p.text('c-models-chip'), /not answering/);
});

test('a model nobody self-tested does not read as checked', () => {
  const p = render({ models: [Object.assign({}, INSTALLED, { selftests: {} })] });
  assert.match(p.rows()[0].textContent, /not self-tested/);
});

test('a self-test observed against different bytes is shown as superseded', () => {
  const p = render({ models: [Object.assign({}, INSTALLED, {
    selftests: { chat: { scope: 'chat', state: 'passed', detail: 'ok',
                         superseded: true, current: false } },
  })] });
  const row = p.rows()[0].textContent;
  assert.match(row, /superseded/);
  assert.doesNotMatch(row, /self-test passed/);
});

test('a failed self-test is never softened into "not run"', () => {
  const p = render({ models: [Object.assign({}, INSTALLED, {
    selftests: { chat: { scope: 'chat', state: 'failed',
                         detail: 'nothing came back', current: false,
                         superseded: false } },
  })] });
  assert.match(p.rows()[0].textContent, /self-test failed/);
});

test('a pass whose model is gone reads as unconfirmed, not as passed', () => {
  // The engine did not answer, or the model was removed. Showing "passed"
  // would let an absent model look ready; showing "not self-tested" would
  // lose the fact that a check was run.
  const p = render({ models: [Object.assign({}, INSTALLED, {
    selftests: { chat: { scope: 'chat', state: 'passed', detail: 'ok',
                         current: false, superseded: false } },
  })] });
  const row = p.rows()[0].textContent;
  assert.match(row, /self-test not confirmed here/);
  assert.doesNotMatch(row, /self-test passed/);
  assert.doesNotMatch(row, /not self-tested/);
});

test('a failure is never hidden behind another workflow passing', () => {
  const p = render({ models: [Object.assign({}, INSTALLED, {
    selftests: {
      chat: { scope: 'chat', state: 'passed', detail: 'ok',
              current: true, superseded: false },
      code: { scope: 'code', state: 'failed', detail: 'nothing came back',
              current: false, superseded: false },
    },
  })] });
  assert.match(p.rows()[0].textContent, /self-test failed/);
});

test('workflows nobody ran do not drown out one that did', () => {
  const p = render({ models: [Object.assign({}, INSTALLED, {
    selftests: {
      chat: { scope: 'chat', state: 'passed', detail: 'ok',
              current: true, superseded: false },
      code: { scope: 'code', state: 'not_run', detail: 'not run yet',
              current: false, superseded: false },
    },
  })] });
  assert.match(p.rows()[0].textContent, /self-test passed/);
});

test('switching a model off is explained as new work only, not as deletion', () => {
  const p = render({ models: [Object.assign({}, INSTALLED, { enabled: false })] });
  assert.match(p.rows()[0].textContent, /switched off/);
  assert.match(p.text('c-models-note'), /does not delete it/);
  assert.match(p.text('c-models-note'), /nothing you have written/i);
});

test('the switch sends exactly one explicit change and no removal', async () => {
  const p = render();
  const buttons = p.rows()[0].children[2].children
    .filter((child) => child.tag === 'button');
  const toggle = buttons.find((b) => /Switch off/.test(b.textContent));
  assert.ok(toggle, 'an installed model can be switched off');
  toggle.onclick();
  await new Promise((r) => setImmediate(r));
  assert.equal(p.requests.length, 1);
  assert.equal(p.requests[0].path, '/v1/model/enabled');
  assert.deepEqual(p.requests[0].body,
                   { model: 'qwen3.5:4b-q4_K_M', enabled: false });
});

test('removal impact is asked for before anything is removed', async () => {
  const p = render();
  const button = p.rows()[0].children[2].children
    .filter((child) => child.tag === 'button')
    .find((b) => /What removing this affects/.test(b.textContent));
  assert.ok(button, 'an installed model offers the consequence in advance');
  button.onclick();
  await new Promise((r) => setImmediate(r));
  assert.equal(p.requests.length, 1);
  assert.match(p.requests[0].path, /^\/v1\/model\/impact\?model=/);
  assert.equal(p.requests[0].options, undefined,
    'asking what a removal affects is a read, never a write');
});

test('the impact notice repeats that Refinix removes nothing itself', async () => {
  const p = render();
  const button = p.rows()[0].children[2].children
    .filter((child) => child.tag === 'button')
    .find((b) => /What removing this affects/.test(b.textContent));
  button.onclick();
  await new Promise((r) => setImmediate(r));
  p.requests[0].reply({ impact: {
    model: 'qwen3.5:4b-q4_K_M', blocked_capabilities: ['chat'],
    detail: 'Nothing you have written or generated is deleted.',
    command: 'ollama rm qwen3.5:4b-q4_K_M' } });
  await new Promise((r) => setImmediate(r));
  const shown = p.text('notices');
  assert.match(shown, /Affects: chat/);
  assert.match(shown, /does not remove models itself/);
  assert.match(shown, /ollama rm/);
});

test('a self-test is only offered for a workflow that has one', () => {
  const p = render({ selftest_scopes: ['documents.ocr'] });
  const labels = allButtons(p.rows()[0]).map((b) => b.textContent);
  assert.ok(!labels.some((l) => /Check Chat/.test(l)),
            'chat has no self-test in this build, so none is offered');
  assert.ok(labels.length > 0, 'the card still has its other controls');
});

test('a row\'s self-test checks that row\'s own model, by its key', async () => {
  const p = render({ models: [Object.assign({}, INSTALLED,
                                            { key: 'ollama|qwen3.5:4b-q4_K_M' })] });
  const button = allButtons(p.rows()[0]).find((b) => b.textContent === 'Check Chat');
  button.onclick();
  await new Promise((r) => setImmediate(r));
  assert.deepEqual(p.requests[0].body,
                   { scope: 'chat', model: 'ollama|qwen3.5:4b-q4_K_M' });
});

test('every workflow the model can run offers its check, not only the selected one', () => {
  const p = render({ models: [Object.assign({}, INSTALLED, { selected_for: [] })] });
  const labels = allButtons(p.rows()[0]).map((b) => b.textContent);
  for (const word of ['Chat', 'Code', 'Documents']) {
    assert.ok(labels.includes(`Check ${word}`), word);
  }
  assert.ok(!labels.some((l) => /documents\.generate|Self-test/.test(l)),
            'plain workflow names, never API scope names');
});

test('running a self-test asks the coordinator and nothing else', async () => {
  const p = render();
  const button = allButtons(p.rows()[0]).find((b) => b.textContent === 'Check Chat');
  assert.ok(button);
  button.onclick();
  await new Promise((r) => setImmediate(r));
  assert.equal(p.requests[0].path, '/v1/model/selftest');
  assert.deepEqual(p.requests[0].body, { scope: 'chat' });
});

test('the line under the name says where, not what the chip already says', () => {
  const p = render();
  const head = p.rows()[0].children[0];
  const sub = head.children[0].children[1].textContent;
  assert.equal(sub, 'this computer');
  assert.doesNotMatch(sub, /installed/);
});

test('a switched-off model says so once, on the line that names where it is', () => {
  const p = render({ models: [Object.assign({}, INSTALLED, { enabled: false })] });
  const head = p.rows()[0].children[0];
  assert.match(head.children[0].children[1].textContent,
               /this computer — switched off for new work/);
  assert.equal(head.children[1].textContent, 'switched off');
});

test('a coordinator that sends no removal command says so plainly', async () => {
  const p = render();
  const button = p.rows()[0].children[2].children
    .filter((child) => child.tag === 'button')
    .find((b) => /What removing this affects/.test(b.textContent));
  button.onclick();
  await new Promise((r) => setImmediate(r));
  p.requests[0].reply({ impact: {
    model: 'qwen3.5:4b-q4_K_M', blocked_capabilities: [],
    detail: 'Nothing you have written is deleted.', command: null } });
  await new Promise((r) => setImmediate(r));
  const shown = p.text('notices');
  assert.match(shown, /does not remove models itself/);
  assert.doesNotMatch(shown, /null/);
});

test('a location is a role, never an operating system', () => {
  const p = render();
  const row = p.rows()[0].textContent;
  assert.match(row, /this computer|here/);
  assert.doesNotMatch(row, /macOS|Ubuntu|Windows/);
});

test('the note never promises quality from a self-test', () => {
  const p = render();
  assert.match(p.text('c-models-note'), /not a measure of\s+answer quality/);
});

test('an absent model cannot be switched off, because there is nothing to switch', () => {
  const p = render({ models: [ABSENT] });
  const labels = p.rows()[0].children[2].children
    .filter((child) => child.tag === 'button')
    .map((b) => b.textContent);
  assert.ok(!labels.some((l) => /Switch off/.test(l)));
});

// Refinix's own engine: a catalogued model can be downloaded or imported, only
// when the person asks, and removed after the impact is shown.
const MANAGED_ABSENT = Object.assign({}, ABSENT, {
  id: 'qwen3.5-4b-q4_k_m',
  setup: { kind: 'download', label: 'Download', model: 'qwen3.5-4b-q4_k_m',
           download_bytes: 3413361504, detail: 'About 3.2 GB.' },
});

function buttons(p) {
  return p.rows()[0].children[2].children.filter((child) => child.tag === 'button');
}

test('a managed model offers a download with its size, and nothing starts by itself', () => {
  const p = render({ engine: { mode: 'managed' }, models: [MANAGED_ABSENT] });
  const download = buttons(p).find((b) => /^Download/.test(b.textContent));
  assert.ok(download, 'a download button is shown');
  assert.match(download.textContent, /3\.2 GB/);
  assert.equal(p.requests.length, 0, 'rendering must not request anything');
});

test('a download is confirmed with source, licence, revision and checksums first', async () => {
  const p = render({ engine: { mode: 'managed' }, models: [MANAGED_ABSENT] });
  let asked = '';
  p.run('window').confirm = (text) => { asked = text; return false; };
  const download = buttons(p).find((b) => /^Download/.test(b.textContent));
  download.onclick();
  await new Promise((r) => setImmediate(r));
  assert.match(p.requests[0].path, /\/v1\/model\/plan\?model=qwen3\.5-4b-q4_k_m/);
  p.requests[0].reply({
    display_name: 'Qwen3.5 4B', source: 'huggingface.co/x at abc', licence: 'Apache-2.0',
    revision: 'abc', download_bytes: 3413361504, already_staged_bytes: 0,
    location: '/data/models/qwen3.5-4b-q4_k_m', enough_space: true, free_bytes: 9e10,
    files: [{ name: 'w.gguf', size: 2740937888, sha256: 'f'.repeat(64) }],
  });
  await new Promise((r) => setImmediate(r));
  assert.match(asked, /huggingface\.co\/x at abc/);
  assert.match(asked, /Apache-2\.0/);
  assert.match(asked, /f{64}/);
  assert.equal(p.requests.length, 1, 'declining must not start a download');
});

test('a running download shows progress and can be cancelled', () => {
  const p = render({
    engine: { mode: 'managed' }, models: [MANAGED_ABSENT],
    provisioning: { 'qwen3.5-4b-q4_k_m': {
      kind: 'download', state: 'running', bytes_done: 1073741824,
      bytes_total: 4294967296, file: 'w.gguf' } },
  });
  const row = p.rows()[0].textContent;
  assert.match(row, /Downloading w\.gguf: 1\.0 of 4\.0 GB \(25%\)/);
  assert.ok(!buttons(p).some((b) => /^Download/.test(b.textContent)),
            'no second download is offered while one runs');
});

test('removal is offered for a managed model and only after its impact is shown', async () => {
  const p = render({ engine: { mode: 'managed' },
                     models: [Object.assign({}, INSTALLED, { id: 'qwen3.5-4b-q4_k_m' })] });
  const remove = buttons(p).find((b) => /Remove/.test(b.textContent));
  assert.ok(remove);
  let asked = '';
  p.run('window').confirm = (text) => { asked = text; return false; };
  remove.onclick();
  await new Promise((r) => setImmediate(r));
  assert.match(p.requests[0].path, /\/v1\/model\/impact/);
  p.requests[0].reply({ impact: { blocked_capabilities: ['chat'], detail: 'Chat stops.' } });
  await new Promise((r) => setImmediate(r));
  assert.match(asked, /This stops: chat/);
  assert.match(asked, /chats, documents and history are kept/);
  assert.equal(p.requests.length, 1, 'declining must not remove anything');
});

test('the developer engine never offers to remove a model itself', () => {
  const p = render({ models: [INSTALLED] });
  assert.ok(buttons(p).some((b) => /What removing this affects/.test(b.textContent)));
  assert.ok(!buttons(p).some((b) => /^Remove/.test(b.textContent)));
});

// Settings -> Updates: nothing is checked on its own, only verified offers are
// shown, and no Install control is drawn while installing is not built.
function renderUpdates(updates) {
  const p = page();
  p.run(`renderUpdatesCard(${JSON.stringify({ updates })})`);
  return p;
}

function updateButtons(p) {
  return p.document.getElementById('c-updates-actions').children
    .filter((child) => child.tag === 'button').map((b) => b.textContent);
}

test('a build that cannot check says why and offers no Check button', () => {
  const p = renderUpdates({ version: '0.1.0', channel: 'development', can_check: false,
    can_import: false, unavailable: 'This is a source checkout, not an installed package.' });
  assert.match(p.text('c-updates-lead'), /source checkout/);
  assert.deepEqual(updateButtons(p), []);
  assert.equal(p.requests.length, 0, 'rendering must not check for updates');
});

test('a failed check is never shown as up to date', () => {
  const p = renderUpdates({ version: '0.1.0-internal.1', channel: 'internal', can_check: true,
    last_check: { at: '2026-10-05T10:00:00Z', result: 'failed',
                  detail: 'The update information has expired, so it was not trusted.' } });
  assert.match(p.text('c-updates-chip'), /check failed/);
  assert.doesNotMatch(p.text('c-updates-chip'), /up to date/);
  assert.match(p.text('c-updates-facts'), /expired/);
});

test('a verified offer can be downloaded, and a verified package is never installed from here', () => {
  const offered = renderUpdates({ version: '0.1.0-internal.1', channel: 'internal',
    can_check: true, offer: { version: '0.1.1-internal.1', size: 2147483648, notes: 'Fixes.' } });
  assert.ok(updateButtons(offered).includes('Download 0.1.1-internal.1'));
  const verified = renderUpdates({ version: '0.1.0-internal.1', channel: 'internal',
    can_check: true, offer: { version: '0.1.1-internal.1', size: 1, notes: '' },
    download: { state: 'verified', path: '/data/updates/staging/0.1.1/Refinix.zip' },
    install_note: 'Installing an update from inside Refinix is not available in this build yet.' });
  assert.match(verified.text('c-updates-chip'), /package verified/);
  assert.match(verified.text('c-updates-note'), /not available in this build/);
  assert.ok(!updateButtons(verified).some((label) => /Install/.test(label)));
});

// Review finding: Browse Hugging Face gave every weight file the repository's
// first projector. Pairing now follows the coordinator, and anything it does
// not settle is the person's explicit choice.
const HUB_LISTING = {
  revision: 'a'.repeat(40), licence: 'apache-2.0', base_model: null, architecture: null,
  projectors: [{ file: 'mmproj-F16.gguf', size: 1 }, { file: 'mmproj-BF16.gguf', size: 1 }],
  choices: [
    { file: 'text-only.gguf', parts: ['text-only.gguf'], size: 1,
      pairing: 'none', projectors: [] },
    { file: 'named.gguf', parts: ['named.gguf'], size: 1, pairing: 'named',
      projectors: [{ file: 'mmproj-named-f16.gguf', size: 1 }] },
    { file: 'unsure.gguf', parts: ['unsure.gguf'], size: 1, pairing: 'ambiguous',
      projectors: [{ file: 'mmproj-F16.gguf', size: 1 }] },
  ],
};

test('a projector is paired only when it belongs to that file alone', () => {
  const p = page();
  const plan = (choice) => p.run(`hubPairingPlan(${JSON.stringify(choice)})`);
  const [text, named, unsure] = HUB_LISTING.choices;
  assert.deepEqual({ ...plan(text) }, { mode: 'text', projector: null });
  assert.deepEqual({ ...plan(named) }, { mode: 'paired', projector: 'mmproj-named-f16.gguf' });
  assert.equal(plan(unsure).mode, 'choose');
  assert.equal(plan({ ...named, pairing: 'repository', projectors: HUB_LISTING.projectors }).mode,
               'choose', 'two precisions are a choice');
});

test('browse sends the paired projector, text only, or what the person chose', () => {
  const p = page();
  const row = p.document.getElementById('hub-row');
  p.run(`renderHubFiles('Quant/Repo', ${JSON.stringify(HUB_LISTING)}, document.getElementById('hub-row'))`);
  const picks = row.children.slice(1);
  assert.deepEqual(picks.map((b) => b.textContent.split(' — ')[0].split(' · ').pop()), [
    'text-only.gguf', 'named.gguf', 'text only', 'unsure.gguf']);
  for (const pick of picks.slice(0, 3)) pick.onclick();
  assert.deepEqual(p.requests.map((r) => [r.path, r.body.file, r.body.projector,
                                          r.body.projector_confirmed]), [
    ['/v1/hub/resolve', 'text-only.gguf', null, false],
    ['/v1/hub/resolve', 'named.gguf', 'mmproj-named-f16.gguf', false],
    ['/v1/hub/resolve', 'named.gguf', null, false],
  ]);
  // The ambiguous file asks first, and nothing is sent until a choice is made.
  picks[3].onclick();
  assert.equal(p.requests.length, 3);
  assert.match(row.textContent, /nothing in this repository ties/);
  const labels = row.children.map((child) => child.textContent);
  assert.ok(labels.includes('Text only (no image input)'));
  row.children.find((child) => /With mmproj-F16\.gguf/.test(child.textContent)).onclick();
  assert.deepEqual([p.requests[3].body.file, p.requests[3].body.projector,
                    p.requests[3].body.projector_confirmed],
                   ['unsure.gguf', 'mmproj-F16.gguf', true]);
});


test('a failed check names its workflow, why, and whether it still applies', () => {
  const p = render({ models: [Object.assign({}, INSTALLED, {
    selftests: { chat: { scope: 'chat', state: 'failed', detail: 'left out the label',
                         current: false, superseded: false, matches_now: true,
                         failure_kind: 'missing_label', reply_excerpt: 'unsafe; 2.4' } },
  })] });
  const row = p.rows()[0].textContent;
  assert.match(row, /self-test failed — Chat/);
  assert.match(row, /formatting: left out the requested label/);
  assert.match(row, /matches this model and settings now/);
  assert.match(row, /unsafe; 2\.4/);
  assert.doesNotMatch(row, /backwards/, 'a formatting failure is not a wrong answer');
});

test('an older failure is labelled as history and does not raise the alert', () => {
  const p = render({ models: [Object.assign({}, INSTALLED, {
    selftests: { chat: { scope: 'chat', state: 'failed', detail: 'x', current: false,
                         superseded: false, matches_now: false } },
  })] });
  const head = p.rows()[0].children[0];
  assert.match(p.rows()[0].textContent, /Chat \(older result\)/);
  assert.match(p.rows()[0].textContent, /reason not recorded \(older check\)/);
  assert.doesNotMatch(head.textContent, /check failed/);
});

test('a reply excerpt is inert text, never markup', () => {
  const p = render({ models: [Object.assign({}, INSTALLED, {
    selftests: { chat: { scope: 'chat', state: 'failed', detail: 'x', current: false,
                         matches_now: true, failure_kind: 'extra_text',
                         reply_excerpt: '<img src=x onerror=alert(1)>' } },
  })] });
  const quotes = [];
  const walk = (n) => { if (n.tag === 'q') quotes.push(n); (n.children || []).forEach(walk); };
  walk(p.rows()[0]);
  assert.equal(quotes.length, 1);
  assert.equal(quotes[0].textContent, '<img src=x onerror=alert(1)>');
  assert.equal(quotes[0].children.length, 0, 'set as text, not parsed');
});

test('a critical problem stays visible while Details is closed', () => {
  const p = render({ models: [Object.assign({}, INSTALLED, {
    integrity: { local: { state: 'mismatch' } } })] });
  const head = p.rows()[0].children[0];
  assert.match(head.textContent, /files changed since they were installed/);
  assert.equal(p.rows()[0].children[1].tag, 'details', 'technical facts are collapsed');
});

test('the summary line says what the model is documented for, or that nobody did', () => {
  const documented = render({ models: [Object.assign({}, INSTALLED, {
    hints: ['general', 'vision'], evidence_level: 3, fit_label: 'Good fit (estimated)' })] });
  assert.match(documented.rows()[0].children[0].textContent,
               /Good for: general use, images \(publisher's card\) · Good fit/);
  const unknown = render({ models: [Object.assign({}, INSTALLED, { hints: [] })] });
  assert.match(unknown.rows()[0].children[0].textContent, /Strengths not documented/);
  const limited = render({ models: [Object.assign({}, INSTALLED, {
    hints: ['ocr'], limited_to: ['ocr'], evidence_level: 3 })] });
  assert.match(limited.rows()[0].children[0].textContent, /Documented for page reading only/);
});

test('a task its current check shows unfinished says Auto does not use it there', () => {
  const p = render({ models: [Object.assign({}, INSTALLED, {
    hints: ['ocr'], evidence_level: 1, auto_excluded: { chat: 'did not finish' } })] });
  assert.match(p.rows()[0].children[0].textContent,
               /Auto does not use it for Chat: its check there did not finish/);
  const tagged = render({ models: [Object.assign({}, INSTALLED, { hints: ['ocr'] })] });
  assert.doesNotMatch(tagged.rows()[0].children[0].textContent, /Auto does not use it/,
                      'tags alone never exclude a model');
});

test('a formatting-only check failure is a note, not a problem', () => {
  const p = render({ models: [Object.assign({}, INSTALLED, {
    selftests: { chat: { scope: 'chat', state: 'failed', detail: 'x', current: false,
                         matches_now: true, failure_kind: 'missing_label' } } })] });
  const alert = p.rows()[0].children[0].children[0].children.find((n) => /model-alert/.test(n.className));
  assert.equal(alert.className, 'model-alert model-note');
  const wrong = render({ models: [Object.assign({}, INSTALLED, {
    selftests: { chat: { scope: 'chat', state: 'failed', detail: 'x', current: false,
                         matches_now: true, failure_kind: 'wrong_verdict' } } })] });
  const fault = wrong.rows()[0].children[0].children[0].children.find((n) => /model-alert/.test(n.className));
  assert.equal(fault.className, 'model-alert');
});
