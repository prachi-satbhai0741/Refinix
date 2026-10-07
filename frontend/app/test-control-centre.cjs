/* Offline regressions for the Control Center's connected-computer card (AF-007).
 * Run: node --test this-file
 *
 * What this card must never do is display something it did not observe. A
 * "healthy" chip from a stale reading, a queue depth of 0 when the worker
 * reported none, or a quiet local answer after a certificate mismatch would
 * each be a lie the operator cannot see through. These checks are written
 * against those four failures.
 *
 * Everything is synthetic. No worker, no Keychain, no request leaves the
 * harness.
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
      focus() {}, remove() {}, reset() { this.wasReset = true; },
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
  const run = (code) => vm.runInContext(code, scope);
  const text = (id) => document.getElementById(id).textContent;
  return { run, requests, document, text };
}

// The paired-computer card is deferred and hidden unless the feature is on;
// these tests exercise the retained card with the feature switched on.
const STATUS = { node_id: '11111111-2222-4333-8444-555555555555',
                 features: { mesh: true } };

function paired(over = {}) {
  return Object.assign({
    paired: true,
    credential_store: { available: true },
    identity_mismatch: null,
    would_dispatch: true,
    health: 'healthy',
    route_reason: 'paired worker ubuntu-worker: healthy, qwen3.5:4b-q4_K_M',
    relationship: {
      relationship_id: '66666666-6666-4666-8666-666666666666',
      display_name: 'ubuntu-worker', address: '192.168.1.20', port: 30443,
      fingerprint: 'AB:CD:EF', node_id: 'n', workspace_id: 'w',
      paired_at: '2026-09-05T00:00:00Z', state: 'paired',
    },
    node: {
      node_id: 'n', display_name: 'ubuntu-worker', health: 'healthy',
      observed_at: '2026-09-05T10:00:00Z', queue_depth: 2,
      models: [{ model_id: 'qwen3.5:4b-q4_K_M' }],
    },
  }, over);
}

function render(worker) {
  const p = page();
  p.run(`renderOthersCard(${JSON.stringify(STATUS)}, ${JSON.stringify(worker)})`);
  return p;
}

test('with nothing connected it says work runs here', () => {
  const p = render({ paired: false, credential_store: { available: true } });
  assert.match(p.text('c-others-chip'), /none connected/);
  assert.match(p.text('c-others-facts'), /on this computer/);
});

test('without a credential store it says connecting is switched off, not that it failed', () => {
  const p = render({ paired: false, credential_store: { available: false } });
  assert.match(p.text('c-others-lead'), /switched off/);
  assert.equal(p.document.getElementById('c-others-actions').children.length, 0,
    'no connect button when the credential has nowhere legitimate to go');
});

test('the unavailable store names this computer\'s own prerequisite', () => {
  // The coordinator knows which store this OS uses; the card must repeat that
  // rather than sending a Windows or Linux user to fix a macOS framework.
  const p = render({
    paired: false,
    credential_store: {
      available: false, backend: 'secret-service',
      detail: 'This computer has no `secret-tool`, so the desktop keyring cannot be reached.',
    },
  });
  assert.match(p.text('c-others-lead'), /secret-tool/);
  assert.doesNotMatch(p.text('c-others-lead'), /Keychain/);
});

test('an older coordinator that sends no store detail still explains itself', () => {
  const p = render({ paired: false, credential_store: { available: false } });
  assert.match(p.text('c-others-lead'), /not available here/);
});

test('a paired healthy worker shows its observed measurements', () => {
  const p = render(paired());
  assert.match(p.text('c-others-chip'), /healthy/);
  const facts = p.text('c-others-facts');
  assert.match(facts, /192\.168\.1\.20:30443/);
  assert.match(facts, /AB:CD:EF/);
  assert.match(facts, /qwen3\.5:4b-q4_K_M/);
  assert.match(facts, /2/, 'the reported queue depth is shown');
});

test('a measurement the worker did not report is unavailable, not zero', () => {
  const p = render(paired({
    node: { node_id: 'n', health: 'healthy', observed_at: null,
            queue_depth: null, models: [] },
  }));
  const facts = p.text('c-others-facts');
  assert.match(facts, /not reported/);
  assert.doesNotMatch(facts, /Waiting requests0/,
    'a missing queue depth must never render as a number');
});

test('a certificate mismatch is shown as a refusal, never as unavailable', () => {
  const p = render(paired({
    identity_mismatch: 'the worker identity changed', health: 'unavailable',
  }));
  assert.match(p.text('c-others-chip'), /identity changed/);
  const lead = p.text('c-others-lead');
  assert.match(lead, /different certificate/);
  assert.match(lead, /did not send your request anywhere/);
});

test('a mismatch never claims the request was answered locally', () => {
  const p = render(paired({ identity_mismatch: 'changed' }));
  assert.doesNotMatch(p.text('c-others-lead'), /runs? (them )?here instead/);
});

test('a connected but unusable worker says work runs here and why', () => {
  const p = render(paired({
    health: 'degraded', would_dispatch: false,
    route_reason: 'local coordinator: the paired worker reported degraded',
  }));
  assert.match(p.text('c-others-chip'), /degraded/);
  assert.match(p.text('c-others-facts'), /reported degraded/);
});

test('an unreadable preflight blanks nothing and claims nothing', () => {
  const p = render(null);
  assert.match(p.text('c-others-chip'), /unavailable/);
  assert.match(p.text('c-others-facts'), /not observed/);
});

test('the pairing form sends every value the worker needs, once', async () => {
  const p = page();
  p.run('wirePairForm()');
  const form = p.document.getElementById('pair-form');
  p.run(`
    $('pair-address').value = '192.168.1.20';
    $('pair-port').value = '30443';
    $('pair-fingerprint').value = 'AB:CD:EF';
    $('pair-certificate').value = '-----BEGIN CERTIFICATE-----';
    $('pair-code').value = 'one-time-code';
  `);
  assert.ok(form.addEventListener, 'the form must be wired');
});

test('the code and certificate are cleared from the page after a submit', () => {
  const p = page();
  p.run('wirePairForm()');
  p.run(`$('pair-code').value = 'one-time-code';`);
  // The handler clears both in its finally block; assert the fields exist to
  // be cleared, so a rename cannot silently leave a secret on the page.
  assert.equal(p.run(`$('pair-code').value`), 'one-time-code');
  assert.equal(typeof p.run(`$('pair-certificate').value`), 'string');
});

test('a paired worker offers the self-test and the disconnect', () => {
  const p = render(paired());
  const labels = p.document.getElementById('c-others-actions')
    .children.map((c) => c.textContent);
  assert.deepEqual(labels, ['Run distributed self-test',
                            'Disconnect this computer']);
});

test('nothing offers the self-test before a computer is connected', () => {
  const p = render({ paired: false, credential_store: { available: true } });
  const labels = p.document.getElementById('c-others-actions')
    .children.map((c) => c.textContent);
  assert.ok(!labels.includes('Run distributed self-test'));
});

test('the self-test starts only when asked, and by POST', async () => {
  const p = page();
  p.run('runSelftest()').catch(() => {});
  await new Promise(setImmediate);
  assert.equal(p.requests.length, 1, 'exactly one request, and only on demand');
  assert.equal(p.requests[0].path, '/v1/worker/selftest');
  assert.equal(p.requests[0].options.method, 'POST');
});

test('the page never starts a self-test on its own', () => {
  /* It invokes the model on the connected computer. Anything that ran it from
     a status poll would spend real time there without being asked. */
  const source = readFileSync(`${__dirname}/app.js`, 'utf8');
  const status = source.slice(source.indexOf('async function loadStatus'),
                              source.indexOf('async function loadStatus') + 1200);
  assert.doesNotMatch(status, /runSelftest/);
  assert.doesNotMatch(source, /setInterval\([^)]*runSelftest/);
});

test('repeated Settings refreshes only request a worker when mesh is enabled', async () => {
  for (const features of [{ mesh: false }, undefined, { mesh: true }]) {
    const p = page();
    p.run(`globalThis.networkCalls = [];
      fetch = async (path) => {
        networkCalls.push(path);
        return { ok: true, json: async () => path === '/v1/status'
          ? ${JSON.stringify({ features })} : path === '/v1/jobs' ? { jobs: [] } : {} };
      };`);
    for (const name of ['renderReadyLine', 'renderSetupAction', 'openSetupOnce',
      'renderSkill', 'afterStatus', 'renderOverview', 'renderComputerCard',
      'renderEngineCard', 'renderModelsCard', 'renderModelChoiceNote',
      'renderOllamaLine', 'renderUpdatesCard', 'renderOthersCard',
      'renderWorkCard', 'renderCapabilityCard', 'renderAdvanced']) {
      p.run(`${name} = () => {};`);
    }
    for (let i = 0; i < 3; i += 1) await p.run('loadStatus()');
    const calls = JSON.parse(p.run('JSON.stringify(networkCalls)'));
    assert.equal(calls.filter((path) => path === '/v1/worker').length,
      features?.mesh ? 3 : 0);
    assert.equal(calls.filter((path) => path === '/v1/status').length, 3);
  }
});

test('the result names where each attempt ran and why', () => {
  const p = page();
  p.run(`renderSelftest(${JSON.stringify({
    passed: false, state: 'completed',
    attempts: [
      { state: 'interrupted', ran_remotely: true,
        route_reason: 'paired worker ubuntu-worker: healthy' },
      { state: 'completed', ran_remotely: false,
        route_reason: 'local coordinator: the paired worker was unavailable' },
    ],
    pod_readiness: null, pod_readiness_note: 'not observed — no Kubernetes access',
  })})`);
  const text = p.text('c-selftest');
  assert.match(text, /On the connected computer/);
  assert.match(text, /On this computer/);
  assert.match(text, /paired worker ubuntu-worker/);
  assert.match(text, /was unavailable/);
});

test('pod readiness is unavailable with a reason, never guessed', () => {
  const p = page();
  p.run(`renderSelftest(${JSON.stringify({
    passed: true, state: 'completed',
    attempts: [{ state: 'completed', ran_remotely: true, route_reason: 'ok' }],
    pod_readiness: null,
    pod_readiness_note: 'not observed — Refinix has no Kubernetes access',
  })})`);
  const text = p.text('c-selftest');
  assert.match(text, /no Kubernetes access/);
  assert.doesNotMatch(text, /\bReady\b/,
    'readiness must not be claimed from a request that never asked Kubernetes');
});

test('revoking asks the coordinator, never the worker directly', async () => {
  const p = page();
  /* The returned promise is deliberately not awaited: `revokePairing` reloads
     the whole Control Center afterwards, and this harness answers only the
     request under test. What matters is the request that was made. */
  p.run(`revokePairing('66666666-6666-4666-8666-666666666666')`).catch(() => {});
  await new Promise(setImmediate);
  assert.equal(p.requests.length, 1);
  assert.equal(p.requests[0].path, '/v1/pair/revoke');
  assert.equal(p.requests[0].options.method, 'POST');
  assert.equal(p.requests[0].body.relationship_id,
               '66666666-6666-4666-8666-666666666666');
});

test('the address a request goes to is never a value from the page URL', () => {
  /* Pairing targets an address a person typed after confirming a fingerprint
     out of band. Nothing here may take it from the location bar. */
  const source = readFileSync(`${__dirname}/app.js`, 'utf8');
  const handler = source.slice(source.indexOf('function wirePairForm'),
                              source.indexOf('function wirePairForm') + 1400);
  assert.doesNotMatch(handler, /location\./);
  assert.doesNotMatch(handler, /localStorage/,
    'the pairing code and certificate are not the page\'s to keep');
});

test('the paired-computer card is hidden in a Beta build', () => {
  const p = page();
  p.run(`renderOthersCard(${JSON.stringify({ node_id: STATUS.node_id })}, `
        + `${JSON.stringify({ paired: false, credential_store: { available: true } })})`);
  assert.equal(p.text('c-others-chip'), '', 'nothing was rendered into a hidden card');
  assert.equal(p.document.getElementById('c-others-actions').children.length, 0);
});

/* Typed readiness (K5). The generic "unavailable for new work" sentence used to
 * cover a modified engine, an external runtime upgrade, a missing model and a
 * switched-off model alike; each now has its own code and words. */
const READY_STATUS = {
  runtime: { reachable: true, models: ['qwen3.5-4b-q4_k_m'], server_version: 'b11390-metal' },
  model_installed: true, model_available: false,
  readiness: { code: 'no_qualified_profile', state: 'attention',
    message: 'qwen3.5-4b-q4_k_m has not been qualified with the Refinix engine b11390-metal on this kind of computer.',
    detail: 'The model is installed, but no checked setting exists for this engine and hardware combination.',
    action: { kind: 'open_settings', target: 'models', label: 'Open Settings → Models' } },
};

test('the ready line names the specific cause, not the generic sentence', () => {
  const p = page();
  p.run(`renderReadyLine(${JSON.stringify(READY_STATUS)})`);
  const line = p.document.getElementById('ready-line');
  assert.equal(line.dataset.state, 'attention');
  assert.equal(line.dataset.code, 'no_qualified_profile');
  assert.match(line.textContent, /not been qualified/);
  assert.doesNotMatch(line.textContent, /unavailable for new work/);
});

test('a modified engine is a failure with a repair action, never a command', () => {
  const p = page();
  const status = {
    ...READY_STATUS, model_configured: 'qwen3.5-4b-q4_k_m',
    engine: { mode: 'managed', release: 'b11390', backend: 'metal', verified: false,
      problems: ['llama-server does not match the shipped engine'], running: false },
    readiness: { code: 'engine_unverified', state: 'failed',
      message: 'The Refinix engine files were changed, so the engine was not started.',
      detail: 'Reinstall Refinix from a verified package.',
      action: { kind: 'reinstall', label: 'How to repair Refinix' } },
  };
  p.run(`renderReadyLine(${JSON.stringify(status)}); renderEngineCard(${JSON.stringify(status)})`);
  assert.equal(p.document.getElementById('ready-line').dataset.state, 'failed');
  const actions = p.text('c-engine-actions');
  assert.match(actions, /How to repair Refinix/);
  assert.doesNotMatch(actions, /ollama/i);
  assert.match(p.text('c-engine-facts'), /does not match the shipped engine/);
});

test('the managed engine card names the engine and never offers a terminal command', () => {
  const p = page();
  const status = {
    ...READY_STATUS, model_configured: 'qwen3.5-4b-q4_k_m',
    engine: { mode: 'managed', release: 'b11390', backend: 'metal', verified: true,
      problems: [], running: false },
    readiness: { code: 'ready', state: 'ok', message: 'Ready on this computer.',
      detail: '', action: null },
  };
  p.run(`renderEngineCard(${JSON.stringify(status)})`);
  assert.match(p.text('c-engine-facts'), /Refinix engine b11390 \(metal\)/);
  assert.match(p.text('c-engine-lead'), /do not change it/);
  assert.doesNotMatch(p.text('c-engine-actions') + p.text('c-engine-facts'), /ollama pull/);
});

// The preview finding: the engine card printed origin-qualified keys, and a
// model Auto was choosing said no workflow used it.
const TWO_RUNTIMES = {
  models: [
    { key: 'llama.cpp|qwen3.5-4b-q4_k_m', id: 'qwen3.5-4b-q4_k_m', installed: true,
      display_name: 'Qwen3.5 4B (Q4_K_M)', runtime_label: 'Refinix engine',
      locations: ['this computer'], selected_for: [] },
    { key: 'ollama|qwen3.5:4b-q4_K_M', id: 'qwen3.5:4b-q4_K_M', installed: true,
      display_name: 'qwen3.5:4b-q4_K_M', runtime_label: 'Ollama',
      locations: ['this computer'], selected_for: ['code'] },
  ],
  model_choices: {
    chat: { key: 'llama.cpp|qwen3.5-4b-q4_k_m', pinned: false, refusal: null },
    code: { key: 'ollama|qwen3.5:4b-q4_K_M', pinned: true, refusal: null },
    'documents.generate': { key: 'llama.cpp|qwen3.5-4b-q4_k_m', pinned: false, refusal: null },
    'documents.ocr': { key: null, pinned: false, refusal: 'no installed model reads pages' },
  },
};

test('the engine card names models and runtimes, not internal keys', () => {
  const p = page();
  const status = {
    ...READY_STATUS, ...TWO_RUNTIMES, model_configured: 'llama.cpp|qwen3.5-4b-q4_k_m',
    engine: { mode: 'managed', release: 'b11390', backend: 'metal', verified: true,
      problems: [], running: false },
    readiness: { code: 'ready', state: 'ok', message: 'Ready.', detail: '', action: null },
  };
  p.run(`renderEngineCard(${JSON.stringify(status)})`);
  const facts = p.text('c-engine-facts');
  assert.match(facts, /Auto, now Qwen3\.5 4B \(Q4_K_M\) \(Refinix engine\)/);
  assert.match(facts, /qwen3\.5:4b-q4_K_M \(Ollama\)/);
  assert.doesNotMatch(facts, /llama\.cpp\||ollama\|/);
});

test('used-for names pinned workflows and what Auto picks right now', () => {
  const p = page();
  const [managed, ollama] = TWO_RUNTIMES.models;
  const used = (model) => p.run(`modelFactRows(${JSON.stringify(model)}, ${JSON.stringify(
    TWO_RUNTIMES.model_choices)})`).find((row) => row[0] === 'Used for');
  assert.equal(used(managed)[1], 'Chat (Auto, right now), Documents (Auto, right now)');
  assert.equal(used(ollama)[1], 'Code (pinned)');
  const idle = p.run(`modelFactRows(${JSON.stringify({ ...managed, key: 'llama.cpp|other' })}, ${
    JSON.stringify(TWO_RUNTIMES.model_choices)})`).find((row) => row[0] === 'Used for');
  assert.equal(idle[1], null);
  assert.equal(idle[2], 'not chosen for any workflow right now');
});

// Refinix's own engine reports changed model files without a digest, and
// files not yet re-read this session as pending; both must read plainly.
test('a changed model file is named as changed, not hidden as unobserved', () => {
  const p = page();
  const rows = p.run(`modelFactRows(${JSON.stringify({
    integrity: { local: { state: 'mismatch', observed: null } } })})`);
  const integrity = rows.find((row) => row[0] === 'Integrity');
  assert.match(integrity[1], /changed since it was installed/);
});

test('a pending file check says when it is checked', () => {
  const p = page();
  const rows = p.run(`modelFactRows(${JSON.stringify({
    integrity: { local: { state: 'pending', observed: 'c'.repeat(64) } } })})`);
  const integrity = rows.find((row) => row[0] === 'Integrity');
  assert.match(integrity[1], /checked again before it loads/);
});

/* Setup and the Settings overview (first-run work package). */
const SETUP_STATUS = {
  runtime: { reachable: false, models: [] },
  readiness: { code: 'setup_incomplete', state: 'attention',
    message: 'Choose a model to finish setting up Refinix.',
    detail: 'No local model is installed yet.',
    action: { kind: 'start_ollama', label: 'Start Ollama' } },
  hardware: { facts: { cpu_brand: 'Test CPU', memory_total_bytes: 16 * 1024 ** 3,
                       disk_free_bytes: 200 * 1024 ** 3 },
              memory: { capacity_bytes: 11 * 1024 ** 3 } },
  ollama: { active: true, reachable: false, installed: true, startable: true },
  setup: { intro_dismissed: false, choice: null },
  models: [], model_choices: {}, categories: [],
};

function allNodes(node) {
  return [node, ...(node.children || []).flatMap(allNodes)];
}

test('setup can always be reopened; only the attention badge depends on readiness', () => {
  const p = page();
  p.run(`renderSetupAction(${JSON.stringify(SETUP_STATUS)})`);
  assert.equal(p.document.getElementById('setup-action').hidden, false);
  assert.equal(p.document.getElementById('settings-attention').hidden, false);
  assert.equal(p.document.getElementById('settings-link').dataset.attention, 'true');
  const ready = Object.assign({}, SETUP_STATUS, { readiness: { state: 'ok', code: 'ready' } });
  p.run(`renderSetupAction(${JSON.stringify(ready)})`);
  assert.equal(p.document.getElementById('setup-action').hidden, false, 'still reopenable');
  assert.equal(p.document.getElementById('settings-attention').hidden, true);
  assert.equal(p.document.getElementById('settings-link').dataset.attention, 'false');
});

test('setup opens by itself once, on the first launch of this data', async () => {
  const p = page();
  const first = p.run(`openSetupOnce(${JSON.stringify(SETUP_STATUS)})`);
  assert.equal(first, true);
  await new Promise((r) => setImmediate(r));
  assert.equal(p.requests[0].path, '/v1/setup');
  assert.deepEqual(p.requests[0].body, { first_opened: true });
  const later = Object.assign({}, SETUP_STATUS,
    { setup: { intro_dismissed: false, first_opened: true } });
  assert.equal(p.run(`openSetupOnce(${JSON.stringify(later)})`), false);
  assert.equal(p.requests.length, 1, 'never again once it has opened');
});

test('the overview answers the three questions and reuses the startup hardware', () => {
  const p = page();
  p.run(`renderOverview(${JSON.stringify(SETUP_STATUS)})`);
  assert.match(p.text('o-ready'), /^Not yet\./);
  assert.match(p.text('o-models'), /None installed yet/);
  assert.match(p.text('o-next'), /No local model is installed yet/);
  assert.match(p.text('o-hardware'), /16\.0 GB memory/);
  assert.match(p.text('o-hardware'), /11\.0 GB usable for models \(estimated\)/);
});

test('a stopped Ollama asks to be started and never claims a model count', () => {
  const p = page();
  p.run(`renderOverview(${JSON.stringify(SETUP_STATUS)})`);
  const panel = p.text('o-ollama');
  assert.match(panel, /Start Ollama to check your models/);
  assert.doesNotMatch(panel, /Found \d/);
  const buttons = allNodes(p.document.getElementById('o-ollama'))
    .filter((n) => n.tag === 'button').map((b) => b.textContent);
  assert.deepEqual(buttons, ['Start Ollama']);
  assert.equal(p.requests.length, 0, 'nothing starts on its own');
});

test('a running Ollama lists what it reported and reuses it without a copy', async () => {
  const p = page();
  const status = Object.assign({}, SETUP_STATUS, {
    ollama: { active: true, reachable: true, installed: true, version: '0.35.1' },
    models: [
      { key: 'ollama|chat-a:1', id: 'chat-a:1', origin: 'ollama', installed: true,
        locality: 'local', enabled: true, eligible_scopes: ['chat', 'code'],
        hints: ['general'], evidence_level: 3 },
      { key: 'ollama|mystery:1', id: 'mystery:1', origin: 'ollama', installed: true,
        locality: 'local', enabled: true, eligible_scopes: ['chat'], hints: [] }],
  });
  p.run(`renderOverview(${JSON.stringify(status)})`);
  const panel = p.text('o-ollama');
  assert.match(panel, /Found 2 models in Ollama on this computer \(Ollama 0\.35\.1\)/);
  assert.match(panel, /does not download another copy/);
  assert.match(panel, /chat-a:1 — Good for: general use/);
  assert.match(panel, /mystery:1 — Strengths not documented/);
  const use = allNodes(p.document.getElementById('o-ollama'))
    .find((n) => n.tag === 'button' && n.textContent === 'Use existing models');
  use.onclick();
  await new Promise((r) => setImmediate(r));
  assert.equal(p.requests[0].path, '/v1/setup');
  assert.deepEqual(p.requests[0].body, { choice: 'existing_models', intro_dismissed: true });
});

test('the explanation can be hidden and brought back, and the choice is stored', async () => {
  const p = page();
  p.run(`renderOverview(${JSON.stringify(SETUP_STATUS)})`);
  const hide = p.document.getElementById('o-intro-actions').children[0];
  assert.equal(hide.textContent, 'Hide this explanation');
  hide.onclick();
  await new Promise((r) => setImmediate(r));
  assert.deepEqual(p.requests[0].body, { intro_dismissed: true });
  const dismissed = Object.assign({}, SETUP_STATUS, { setup: { intro_dismissed: true } });
  p.run(`renderOverview(${JSON.stringify(dismissed)})`);
  assert.equal(p.document.getElementById('o-intro').hidden, true);
  assert.equal(p.document.getElementById('o-intro-actions').children[0].textContent,
               'Show the setup explanation');
});

test('categories offer any combination, mark what is already here, and show progress', () => {
  const p = page();
  const option = (over) => Object.assign({ id: 'm', display_name: 'M', fit: 'good',
    fit_label: 'Good fit (estimated)', storage_bytes: 2 * 1024 ** 3, installed: false,
    download: true, disk_short: false, runtime_label: 'Refinix engine' }, over);
  const status = Object.assign({}, SETUP_STATUS, {
    provisioning: { queued: { model_id: 'queued', kind: 'download', state: 'queued',
                              bytes_done: 0, bytes_total: 10 } },
    categories: [
      { id: 'chat', label: 'Chat', detail: 'Everyday', installed: 1,
        initial: [option({ id: 'here', display_name: 'Here', installed: true,
                           download: false, origin: 'ollama' }),
                  option({ id: 'get', display_name: 'Get' })],
        more: [option({ id: 'huge', display_name: 'Huge', fit: 'too_large' })] },
      { id: 'code', label: 'Code', detail: 'Code', installed: 0,
        initial: [option({ id: 'queued', display_name: 'Queued' }),
                  option({ id: 'full', display_name: 'Full', disk_short: true })], more: [] },
      { id: 'other', label: 'Other models', detail: 'x', installed: 0, initial: [], more: [] },
    ] });
  p.run(`renderCategories(${JSON.stringify(status)})`);
  const host = p.document.getElementById('o-categories');
  const text = host.textContent;
  assert.match(text, /Already here, in Ollama — no download/);
  assert.match(text, /Download \(2\.0 GB\)/);
  assert.match(text, /Waiting to start: downloads run one after another/);
  assert.match(text, /Not enough free disk space/);
  assert.doesNotMatch(text, /Other models/, 'an empty extra group is not shown');
  const more = allNodes(host).find((n) => n.tag === 'button' && /Show more/.test(n.textContent));
  assert.ok(more, 'a model too large for this computer is still offered under Show more');
  assert.equal(p.requests.length, 0, 'nothing downloads until a button is pressed');
});

test('an unsuitable-model readiness opens setup, not a terminal step', () => {
  const p = page();
  const status = Object.assign({}, SETUP_STATUS, { readiness: {
    code: 'no_suitable_model', state: 'attention', message: 'No installed local model is suitable for Chat.',
    detail: 'Choose one yourself, or set up a general model.',
    action: { kind: 'open_setup', target: 'setup', label: 'Set up local AI' } } });
  const labels = p.run(`readinessActions(${JSON.stringify(status)}).map((a) => a.label)`);
  assert.deepEqual(Array.from(labels), ['Set up local AI', 'Check again']);
});
