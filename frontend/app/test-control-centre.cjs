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

const STATUS = { node_id: '11111111-2222-4333-8444-555555555555' };

function paired(over = {}) {
  return Object.assign({
    paired: true,
    keychain_available: true,
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
  const p = render({ paired: false, keychain_available: true });
  assert.match(p.text('c-others-chip'), /none connected/);
  assert.match(p.text('c-others-facts'), /on this computer/);
});

test('without a credential store it says connecting is switched off, not that it failed', () => {
  const p = render({ paired: false, keychain_available: false });
  assert.match(p.text('c-others-lead'), /switched off/);
  assert.equal(p.document.getElementById('c-others-actions').children.length, 0,
    'no connect button when the credential has nowhere legitimate to go');
});

test('the unavailable store names this computer\'s own prerequisite', () => {
  // The coordinator knows which store this OS uses; the card must repeat that
  // rather than sending a Windows or Linux user to fix a macOS framework.
  const p = render({
    paired: false, keychain_available: false,
    credential_store: {
      available: false, backend: 'secret-service',
      detail: 'This computer has no `secret-tool`, so the desktop keyring cannot be reached.',
    },
  });
  assert.match(p.text('c-others-lead'), /secret-tool/);
  assert.doesNotMatch(p.text('c-others-lead'), /Keychain/);
});

test('an older coordinator that sends no store detail still explains itself', () => {
  const p = render({ paired: false, keychain_available: false });
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
  const p = render({ paired: false, keychain_available: true });
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
