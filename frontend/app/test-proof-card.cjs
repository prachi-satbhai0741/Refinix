/* Offline regressions for the AF-014 Proof Card.
 * Run: node --test this-file
 *
 * The card's only job is to show what the coordinator recorded, with the
 * source of each value, and to make an absence visible as an absence. The
 * failures worth testing are therefore all of one shape: the page turning
 * "not observed" into something that reads like a measurement — a queue time
 * of 0, a validation that looks failed rather than unrecorded, a Pod row on a
 * local attempt, or a network claim from a NetworkPolicy.
 *
 * Everything is synthetic. No coordinator, no worker, no request leaves here.
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
      focus() {}, remove() {}, reset() {}, contains() { return false; },
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
  };
}

const NETWORK_NOTE =
  'Network evidence is unavailable. Nothing has observed this run\'s traffic: '
  + 'the C11 observation window has not been recorded. A default-deny '
  + 'NetworkPolicy is a configuration, not a measurement, and is never '
  + 'reported here as zero egress.';

function emptyNetwork() {
  return {
    public_egress_policy: 'unavailable', enforcer: null, observer: null,
    started_at: null, ended_at: null, node_ids: [], interfaces: [],
    public_outbound_flows: null, external_ai_calls: null,
    blocked_attempts: null, trusted_lan_connections: null,
  };
}

function localAttempt(over = {}) {
  return Object.assign({
    where: 'macOS coordinator',
    state: 'completed',
    route_reason: 'local coordinator: Documents runs on this Mac',
    validation_detail: null,
    proof: {
      proof_id: 'aaaaaaaa-1111-4111-8111-111111111111',
      attempt_id: 'aaaaaaaa-1111-4111-8111-111111111111',
      node_id: 'mac', model: null, pod: null,
      queue_ms: null, runtime_ms: 4200,
      validation: 'unavailable', validation_source: null,
      artifacts: [], citations: [], approval_id: null,
      network: emptyNetwork(),
    },
    sources: {
      state: 'coordinator SQLite',
      route_reason: 'coordinator SQLite',
      queue_ms: 'unavailable — queue time was not recorded',
      runtime_ms: 'coordinator SQLite',
      model: 'unavailable — no model manifest was recorded',
      pod: 'not applicable — this attempt ran on the coordinator',
      validation: 'No sandbox validation result has been recorded for this attempt.',
      artifacts: 'coordinator SQLite',
      citations: 'coordinator SQLite',
      approval: 'unavailable — no approval is bound to this attempt',
      network: NETWORK_NOTE,
    },
  }, over);
}

function validationAttempt(over = {}) {
  return Object.assign({
    where: 'Ubuntu worker',
    state: 'completed',
    route_reason: 'paired worker ubuntu-worker: healthy',
    validation_detail: {
      command: ['python3', '-m', 'unittest'], exit_status: 0,
      observed: true, passed: true, job_name: 'af-validate-x',
      job_uid: 'job-uid-1', stdout: 'OK', stderr: '', detail: null,
    },
    proof: {
      proof_id: 'bbbbbbbb-2222-4222-8222-222222222222',
      attempt_id: 'bbbbbbbb-2222-4222-8222-222222222222',
      node_id: 'ubuntu', model: null,
      pod: { namespace: 'aegisforge', pod_name: 'af-validate-x',
             pod_uid: 'pod-uid-1', image_digest: 'b'.repeat(64),
             ready: false, restarts: 0, observed_at: '2026-09-05T10:00:05Z' },
      queue_ms: 120, runtime_ms: 5000,
      validation: 'passed',
      validation_source: 'sandbox validation result dddddddddddddddd…',
      artifacts: [], citations: [], approval_id: null,
      network: emptyNetwork(),
    },
    sources: {
      state: 'coordinator SQLite', route_reason: 'coordinator SQLite',
      queue_ms: 'coordinator SQLite', runtime_ms: 'coordinator SQLite',
      model: 'not applicable — this attempt ran no model',
      pod: 'Kubernetes API (observed)',
      validation: 'sandbox validation result dddddddddddddddd…',
      artifacts: 'coordinator SQLite', citations: 'coordinator SQLite',
      approval: 'unavailable — no approval is bound to this attempt',
      network: NETWORK_NOTE,
    },
  }, over);
}

function card(attempts, over = {}) {
  return Object.assign({
    job_id: 'cccccccc-3333-4333-8333-333333333333',
    workflow_id: 'w', task_type: 'code', state: 'completed',
    created_at: '2026-09-05T10:00:00Z',
    attempts,
    network: NETWORK_NOTE,
    evidence_note: 'Every value on this card was read from a record of '
      + 'something observed. Anything not observed is shown as unavailable '
      + 'rather than as zero, false or healthy.',
  }, over);
}

function render(payload) {
  const p = page();
  p.run(`renderProofCard(${JSON.stringify(payload)})`);
  return p;
}

test('a local attempt shows no Pod and says why', () => {
  const p = render(card([localAttempt()]));
  const shown = p.text('c-proof');
  assert.match(shown, /macOS coordinator/);
  assert.match(shown, /ran on the coordinator/);
  assert.doesNotMatch(shown, /pod-uid/);
});

test('a queue time that was never recorded is unavailable, not zero', () => {
  const p = render(card([localAttempt()]));
  const shown = p.text('c-proof');
  assert.match(shown, /queue time was not recorded/);
  assert.doesNotMatch(shown, /\b0 ms\b/);
});

test('an unrecorded validation reads as unrecorded, not as failed', () => {
  const p = render(card([localAttempt()]));
  const shown = p.text('c-proof');
  assert.match(shown, /No sandbox validation result has been recorded/);
  assert.doesNotMatch(shown, /\bfailed\b/);
});

test('a validation attempt shows no model and says the step ran none', () => {
  const p = render(card([validationAttempt()]));
  const shown = p.text('c-proof');
  assert.match(shown, /ran no model/);
  assert.doesNotMatch(shown, /qwen/);
});

test('observed Pod facts are shown with the Kubernetes source', () => {
  const p = render(card([validationAttempt()]));
  const shown = p.text('c-proof');
  assert.match(shown, /pod-uid-1/);
  assert.match(shown, new RegExp('b'.repeat(32)));
  assert.match(shown, /Kubernetes API \(observed\)/);
});

test('a value that IS present still names where it came from', () => {
  /* A measurement with no stated origin is the failure AF-014 exists to
     prevent, and it is invisible unless the present values are checked too. */
  const shown = render(card([validationAttempt()])).text('c-proof');
  assert.match(shown, /5000 ms — source: coordinator SQLite/);
  assert.match(shown, /passed — source: sandbox validation result/);
});

test('network evidence is always unavailable and never claims zero egress', () => {
  for (const attempts of [[localAttempt()], [validationAttempt()]]) {
    const shown = render(card(attempts)).text('c-proof');
    assert.match(shown, /Network evidence is unavailable/);
    assert.match(shown, /not a measurement/);
    assert.doesNotMatch(shown, /zero outbound|no traffic left|0 flows/);
  }
});

test('two attempts render as two separate blocks, not one merged claim', () => {
  const p = render(card([localAttempt(), validationAttempt()]));
  const blocks = p.document.getElementById('c-proof').children
    .filter((child) => child.className === 'proof-attempt');
  assert.equal(blocks.length, 2);
  assert.match(blocks[0].textContent, /macOS coordinator/);
  assert.match(blocks[1].textContent, /Ubuntu worker/);
});

test('the card never invents an approval that is not bound to the attempt', () => {
  const shown = render(card([localAttempt()])).text('c-proof');
  assert.match(shown, /no approval is bound to this attempt/);
});

test('artifacts are listed with their recorded hash', () => {
  const attempt = localAttempt();
  attempt.proof.artifacts = [{
    resource_id: 'r', sha256: 'e'.repeat(64), size_bytes: 4096,
    media_type: 'application/vnd.openxmlformats-officedocument.'
      + 'wordprocessingml.document',
  }];
  const shown = render(card([attempt])).text('c-proof');
  assert.match(shown, /4096 bytes/);
  assert.match(shown, new RegExp('e'.repeat(16)));
});

test('a failed proof request says so instead of rendering an empty card', async () => {
  const p = page();
  const pending = p.run('showProof("cccccccc-3333-4333-8333-333333333333")');
  assert.equal(p.requests.length, 1);
  assert.match(p.requests[0].path, /\/v1\/proof\?job_id=/);
  p.requests[0].fail('coordinator unreachable');
  await pending;
  assert.match(p.text('c-proof'), /No proof could be read/);
});

test('the card renders exactly the attempts the coordinator returned', async () => {
  const p = page();
  const pending = p.run('showProof("cccccccc-3333-4333-8333-333333333333")');
  p.requests[0].reply(card([validationAttempt()]));
  await pending;
  assert.match(p.text('c-proof'), /Ubuntu worker/);
  assert.match(p.text('c-proof'), /python3 -m unittest → exit 0/);
});
