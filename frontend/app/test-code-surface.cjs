/* Offline regressions for the Code surface. Run: node --test this-file
 *
 * Three defects this protects against, all found in review:
 *   - a fresh Ask-mode project could not be listed at all: the listing
 *     approval was discarded, and every approved non-write action was retried
 *     as a proposal, so it could never match the listing action or digest;
 *   - connecting a folder natively did not clear the previous selection, so a
 *     same-named file could be submitted against the wrong project;
 *   - the file list was fetched without awaiting it or checking which project
 *     was active, so a late answer for project A could land under project B.
 *
 * Everything here is synthetic. No repository is read and no request leaves
 * the harness.
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');

const source = readFileSync(`${__dirname}/app.js`, 'utf8').replace(/^import .*$/m, '');
const tick = () => new Promise(setImmediate);

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
      append(...kids) {
        for (const k of kids) {
          if (k && k.isFragment) this.children.push(...k.children);
          else this.children.push(k);
        }
      },
      replaceChildren(...kids) { this.children = []; this.append(...kids); },
      setAttribute() {}, removeAttribute() {}, addEventListener() {},
      querySelector() { return null; }, querySelectorAll() { return []; },
      getBoundingClientRect() { return { top: 0, left: 0, right: 0, bottom: 0 }; },
      focus() {}, remove() {}, contains() { return false; },
      get isConnected() { return true; },
    };
    return el;
  };
  const byId = new Map();
  const fragment = () => Object.assign(node('#fragment'), { isFragment: true });
  return {
    getElementById(id) {
      if (!byId.has(id)) byId.set(id, node(`#${id}`));
      return byId.get(id);
    },
    createElement: (tag) => node(tag),
    createDocumentFragment: fragment,
    createElementNS: (_ns, tag) => node(tag),
    addEventListener() {},
    body: node('body'),
  };
}

function page({ bridge } = {}) {
  const document = makeDocument();
  const requests = [];
  const notices = [];
  const scope = vm.createContext({
    document,
    window: { addEventListener() {}, location: { port: '8770' },
              pywebview: bridge ? { api: bridge } : undefined },
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
    notices,
  });
  vm.runInContext(source, scope);
  vm.runInContext(`
    notice = (...a) => notices.push(a);
    renderMarkdown = (box, text) => { box.textContent = text; };
    confirmDialog = async () => true;
  `, scope);
  const run = (code) => vm.runInContext(code, scope);
  // Values cross a realm boundary, where deepEqual compares prototypes too.
  // One JSON round trip brings them home.
  const json = (code) => JSON.parse(JSON.stringify(run(code)));
  return { run, json, requests, notices, document,
           state: () => json(`({ activeRepo, selected: [...selectedPaths],
             files: repoFiles.map((file) => file.path) })`) };
}

const MODES = [
  { id: 'partial', label: 'Partial access', summary: 's', confirm: false },
  { id: 'full', label: 'Full access', summary: 's', confirm: true },
  { id: 'ask', label: 'Ask before actions', summary: 's', confirm: false },
];

function stateBody(active, extra = {}) {
  return {
    repositories: [
      { repo_id: 'repo-a', name: 'alpha', mode: 'ask' },
      { repo_id: 'repo-b', name: 'beta', mode: 'ask' },
    ],
    active, modes: MODES, unavailable: [], pending_approvals: [],
    proposal: null, audit: [], limits: { max_files: 20 },
    code_supported: true, writes_supported: true, platform_note: null,
    ...extra,
  };
}

const LISTING_APPROVAL = {
  approval_id: 'appr-list', repo_id: 'repo-a', action: 'repo.list',
  target: 'file listing', expires_at: '2026-09-05T12:00:00Z',
  decision: 'pending', detail: { repo_name: 'alpha', paths: [] },
};

/* Answer every follow-up read so an in-flight operation can finish. Each
 * reply is shaped for the route that asked, so a refresh settles rather than
 * leaving the caller waiting. */
async function drain(p, active, rounds = 5) {
  for (let i = 0; i < rounds; i += 1) {
    while (p.requests.length) {
      const request = p.requests.shift();
      request.reply(request.path.startsWith('/v1/code/state')
        ? stateBody(active) : { files: [] });
    }
    await tick();
  }
}

/* Drive one loadCodeState to completion: state, then files. */
async function activate(p, repoId, { files = [], listing = null, reset = false } = {}) {
  const opening = p.run(`loadCodeState(${JSON.stringify(repoId)}, `
    + `{ reset: ${reset ? 'true' : 'false'} })`);
  await tick();
  p.requests.shift().reply(stateBody(repoId));
  await tick();
  if (p.requests.length) {
    p.requests.shift().reply(listing ? { needs_approval: listing } : { files });
  }
  await tick();
  await opening;
}

test('an Ask-mode listing approval reaches the interface instead of vanishing', async () => {
  const p = page();
  await activate(p, 'repo-a', { listing: LISTING_APPROVAL });
  const shown = p.json('codeState.pending_approvals.map((a) => a.approval_id)');
  assert.deepEqual(shown, ['appr-list']);
  assert.deepEqual(p.state().files, []);
});

test('approving a listing retries the listing, not a proposal', async () => {
  const p = page();
  await activate(p, 'repo-a', { listing: LISTING_APPROVAL });

  const deciding = p.run(
    `decideApproval(codeState.pending_approvals[0], true)`);
  await tick();

  const decision = p.requests.shift();
  assert.equal(decision.path, '/v1/code/decision');
  assert.deepEqual({ ...decision.body }, { approval_id: 'appr-list', approved: true });
  decision.reply({ decision: 'approved' });
  await tick();

  // The retry must be the listing GET carrying that approval, never /propose.
  const retry = p.requests.shift();
  assert.match(retry.path, /^\/v1\/code\/files\?/);
  assert.match(retry.path, /approval_id=appr-list/);
  retry.reply({ files: [{ path: 'src/main.py', bytes: 10 }] });
  await tick();
  assert.deepEqual(p.state().files, ['src/main.py'],
                   'the approved listing is what the interface shows');

  const seen = [...p.requests].map((r) => r.path);
  await drain(p, 'repo-a');
  await deciding;
  assert.equal(seen.filter((path) => path === '/v1/code/propose').length, 0,
               'a listing approval must never be retried as a proposal');
});

test('an approved listing is kept, not thrown away by the refresh', async () => {
  const p = page();
  await activate(p, 'repo-a', { listing: LISTING_APPROVAL });

  const deciding = p.run('decideApproval(codeState.pending_approvals[0], true)');
  await tick();
  p.requests.shift().reply({ decision: 'approved' });      // the decision
  await tick();
  p.requests.shift().reply({ files: [{ path: 'src/main.py', bytes: 10 }] });
  await tick();

  // The refresh that follows must NOT ask for the listing again: that request
  // would carry no approval, raise a fresh card, and discard what was just
  // approved.
  const followUps = p.requests.map((r) => r.path);
  assert.equal(followUps.filter((path) => path.startsWith('/v1/code/files')).length, 0,
               'the listing this approval bought must be kept');
  while (p.requests.length) p.requests.shift().reply(stateBody('repo-a'));
  await tick();
  await deciding;

  assert.deepEqual(p.state().files, ['src/main.py']);
});

test('approving a read-and-send approval still routes to propose', async () => {
  const p = page();
  await activate(p, 'repo-a', { files: [{ path: 'a.py', bytes: 4 }] });
  p.document.getElementById('code-input').value = 'change it';
  p.run("selectedPaths = new Set(['a.py'])");

  const readApproval = { ...LISTING_APPROVAL, approval_id: 'appr-read',
                         action: 'repo.read_and_propose' };
  p.run(`decideApproval(${JSON.stringify(readApproval)}, true)`);
  await tick();
  p.requests.shift().reply({ decision: 'approved' });
  await tick();

  const retry = p.requests.shift();
  assert.equal(retry.path, '/v1/code/propose');
  assert.equal(retry.body.approval_id, 'appr-read');
});

test('approving a write approval routes to apply', async () => {
  const p = page();
  await activate(p, 'repo-a', { files: [] });
  const writeApproval = { ...LISTING_APPROVAL, approval_id: 'appr-write',
                          action: 'canonical.write',
                          detail: { repo_name: 'alpha', proposal_id: 'prop-1' } };
  p.run(`decideApproval(${JSON.stringify(writeApproval)}, true)`);
  await tick();
  p.requests.shift().reply({ decision: 'approved' });
  await tick();

  const retry = p.requests.shift();
  assert.equal(retry.path, '/v1/code/apply');
  assert.equal(retry.body.proposal_id, 'prop-1');
  assert.equal(retry.body.approval_id, 'appr-write');
});

test('connecting a folder natively clears the previous selection', async () => {
  const bridge = {
    choose_repository: async () => ({ repository: { repo_id: 'repo-b', name: 'beta' } }),
  };
  const p = page({ bridge });
  await activate(p, 'repo-a', { files: [{ path: 'shared.py', bytes: 4 }] });
  p.run("selectedPaths = new Set(['shared.py'])");
  assert.deepEqual(p.state().selected, ['shared.py']);

  const connecting = p.run('connectRepository()');
  await tick();
  p.requests.shift().reply(stateBody('repo-b'));
  await tick();
  if (p.requests.length) p.requests.shift().reply({ files: [{ path: 'shared.py', bytes: 4 }] });
  await tick();
  await connecting;

  assert.deepEqual(p.state().selected, [],
                   'a selection made in another project must not carry over');
  assert.equal(p.state().activeRepo, 'repo-b');
});

test('switching projects in the list clears the previous selection', async () => {
  const p = page();
  await activate(p, 'repo-a', { files: [{ path: 'shared.py', bytes: 4 }] });
  p.run("selectedPaths = new Set(['shared.py'])");
  await activate(p, 'repo-b', { files: [{ path: 'shared.py', bytes: 4 }], reset: true });
  assert.deepEqual(p.state().selected, []);
  assert.equal(p.state().activeRepo, 'repo-b');
});

test('a late file list for project A cannot land under project B', async () => {
  const p = page();
  await activate(p, 'repo-a', { files: [] });

  // Start A, then B, and let A's answers arrive last.
  const first = p.run("loadCodeState('repo-a')");
  await tick();
  const stateA = p.requests.shift();
  const second = p.run("loadCodeState('repo-b')");
  await tick();
  const stateB = p.requests.shift();

  stateB.reply(stateBody('repo-b'));
  await tick();
  const filesB = p.requests.shift();
  filesB.reply({ files: [{ path: 'beta-only.py', bytes: 4 }] });
  await tick();

  stateA.reply(stateBody('repo-a'));
  await tick();
  while (p.requests.length) {
    p.requests.shift().reply({ files: [{ path: 'alpha-only.py', bytes: 4 }] });
  }
  await tick();
  await Promise.all([first, second]);

  const shown = p.state();
  assert.equal(shown.activeRepo, 'repo-b');
  assert.deepEqual(shown.files, ['beta-only.py'],
                   'project A answered last and must be ignored');
});

test('a state failure keeps the project already on screen', async () => {
  const p = page();
  await activate(p, 'repo-a', { files: [{ path: 'a.py', bytes: 4 }] });

  const again = p.run("loadCodeState('repo-a')");
  await tick();
  p.requests.shift().fail('coordinator unavailable');
  await tick();
  await again;

  assert.equal(p.state().activeRepo, 'repo-a');
  assert.equal(p.notices.length, 1);
  assert.match(p.notices[0][0], /could not be refreshed/i);
});

test('a browser without the native bridge refuses to fake a connection', async () => {
  const p = page();
  await activate(p, null, { files: [] });
  await p.run('connectRepository()');
  assert.equal(p.state().activeRepo, null);
  assert.match(p.notices[0][0], /needs the Refinix application/);
  assert.equal(p.requests.length, 0, 'nothing is sent without a native selection');
});
