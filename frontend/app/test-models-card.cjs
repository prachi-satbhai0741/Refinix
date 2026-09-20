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
  assert.match(p.text('c-models-chip'), /1 installed/);
});

test('a supported model that is absent offers the command and never a download', () => {
  const p = render({ models: [ABSENT] });
  const row = p.rows()[0].textContent;
  assert.match(row, /ollama pull qwen3\.5:4b-q4_K_M/);
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
  const labels = p.rows()[0].children[2].children
    .filter((child) => child.tag === 'button')
    .map((b) => b.textContent);
  assert.ok(!labels.some((l) => /Self-test chat/.test(l)),
            'chat has no self-test in this build, so none is offered');
});

test('running a self-test asks the coordinator and nothing else', async () => {
  const p = render();
  const button = p.rows()[0].children[2].children
    .filter((child) => child.tag === 'button')
    .find((b) => /Self-test chat/.test(b.textContent));
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
