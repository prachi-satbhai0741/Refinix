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
      attributes: {},
      setAttribute(name, value) { this.attributes[name] = String(value); },
      getAttribute(name) {
        return Object.prototype.hasOwnProperty.call(this.attributes, name)
          ? this.attributes[name] : null;
      },
      removeAttribute(name) { delete this.attributes[name]; },
      addEventListener() {},
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
    window: {
      addEventListener() {},
      location: { port: '8770' },
      pywebview: bridge ? { api: bridge } : undefined,
      /* app.js evaluates matchMedia at module scope: the panel breakpoints and
         the theme's system preference. Answering "no match" gives the wide
         window and the light default, both of which are ordinary states. */
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
    notices,
  });
  vm.runInContext(source, scope);
  vm.runInContext(`
    notice = (...a) => notices.push(a);
    renderMarkdown = (box, text) => { box.textContent = text; };
    confirmDialog = async () => true;
    codeConversation = 'test-conversation';
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
  assert.deepEqual({ ...decision.body }, {
    approval_id: 'appr-list', approved: true,
    conversation_id: 'test-conversation' });
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
  p.requests.shift().reply({ chat_id: 'test-conversation', repo_id: 'repo-b',
                             open_path: null });
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

/* ---- Execution 4B: Explorer, file viewer and Code conversations --------- */

const codeHtml = readFileSync(`${__dirname}/code.html`, 'utf8');

const TREE_FILES = [
  { path: 'README.md', byte_size: 10 },
  { path: 'pumpcheck/limits.py', byte_size: 805 },
  { path: 'pumpcheck/__init__.py', byte_size: 80 },
  { path: 'tests/test_limits.py', byte_size: 1286 },
];

function explorerPage() {
  const p = page();
  p.run(`
    codeState = ${JSON.stringify(stateBody('repo-a'))};
    activeRepo = 'repo-a';
    repoFiles = ${JSON.stringify(TREE_FILES)};
  `);
  return p;
}

const rows = (p) => p.document.getElementById('explorer').children
  .flatMap(function walk(node) {
    return [node, ...(node.children || []).flatMap(walk)];
  })
  .filter((node) => node.className === 'tree-row');

test('the tree is built from relative paths, folders before files', () => {
  const p = explorerPage();
  const tree = p.json(`buildTree(${JSON.stringify(TREE_FILES)})`);
  assert.deepEqual(tree.map((n) => `${n.kind}:${n.path}`),
                   ['folder:pumpcheck', 'folder:tests', 'file:README.md']);
  assert.deepEqual(tree[0].children.map((n) => n.path),
                   ['pumpcheck/__init__.py', 'pumpcheck/limits.py']);
});

test('no absolute path is ever asked for or rendered', () => {
  const p = explorerPage();
  p.run('renderExplorer();');
  const text = rows(p).map((r) => r.textContent).join(' ');
  assert.ok(!text.includes('/Users/'), text);
  assert.ok(!text.includes('/home/'), text);
  // The viewer asks by repo id and relative path, never by a real location.
  assert.match(source, /\/v1\/code\/view\?repo_id=/);
  assert.match(source, /path=\$\{encodeURIComponent\(path\)\}/);
});

test('folders expand and collapse, and the state survives a redraw', () => {
  const p = explorerPage();
  p.run('renderExplorer();');
  const folder = rows(p).find((r) => r.dataset.kind === 'folder');
  assert.equal(folder.getAttribute('aria-expanded'), 'false');
  folder.onclick();
  const open = rows(p).find((r) => r.dataset.kind === 'folder');
  assert.equal(open.getAttribute('aria-expanded'), 'true');
  p.run('renderExplorer();');
  assert.equal(rows(p).find((r) => r.dataset.kind === 'folder')
                 .getAttribute('aria-expanded'), 'true');
});

test('opening a file reads it through the coordinator and shows it', async () => {
  const p = explorerPage();
  p.run(`openFileInViewer('repo-a', 'pumpcheck/limits.py');`);
  await tick();
  const call = p.requests.pop();
  assert.match(call.path, /^\/v1\/code\/view\?/);
  assert.match(call.path, /repo_id=repo-a/);
  assert.match(call.path, /path=pumpcheck%2Flimits\.py/);
  call.reply({ repo_id: 'repo-a', path: 'pumpcheck/limits.py',
               name: 'limits.py', lines: ['one', 'two'], line_count: 2,
               sent_to_model: false });
  await tick();
  const body = p.document.getElementById('viewer-body');
  assert.equal(body.children[0].className, 'code-lines');
  // Line numbers are their own column, and the text is inserted as text.
  assert.deepEqual(body.children[0].children.map((c) => c.textContent),
                   ['1', 'one', '2', 'two']);
});

test('opening a file sends nothing to the model', async () => {
  const p = explorerPage();
  p.run(`openFileInViewer('repo-a', 'README.md');`);
  await tick();
  p.requests.pop().reply({ path: 'README.md', lines: ['hello'],
                           sent_to_model: false });
  await tick();
  const sent = p.requests.filter((r) => /propose/.test(r.path));
  assert.deepEqual(sent, [], 'viewing must not propose anything');
  assert.deepEqual(p.state().selected, [],
                   'viewing must not add the file to the request selection');
});

test('an ask-mode view says approval is needed and does not claim a send', async () => {
  const p = explorerPage();
  p.run(`openFileInViewer('repo-a', 'README.md');`);
  await tick();
  p.requests.pop().reply({ needs_approval: {
    approval_id: 'ap-1', action: 'repo.view', target: 'README.md',
    expires_at: 'later', detail: { repo_name: 'alpha', paths: ['README.md'] },
  } });
  await tick();
  const shown = p.document.getElementById('viewer-body').textContent;
  assert.match(shown, /approval/i);
  assert.match(shown, /does not send it to the model/i);
});

test('a late file response never paints under another project', async () => {
  const p = explorerPage();
  p.run(`openFileInViewer('repo-a', 'README.md');`);
  await tick();
  const slow = p.requests.pop();
  // The person moves on before the answer arrives.
  p.run('codeGeneration += 1; viewerToken += 1;');
  slow.reply({ path: 'README.md', lines: ['STALE CONTENT'] });
  await tick();
  assert.ok(!p.document.getElementById('viewer-body').textContent
              .includes('STALE CONTENT'));
});

test('switching project clears the open file and the selection', async () => {
  const p = explorerPage();
  p.run(`openFile = { repo_id: 'repo-a', path: 'README.md' };
         selectedPaths = new Set(['README.md']);
         resetRepositoryState();`);
  assert.equal(p.json('openFile === null'), true);
  assert.deepEqual(p.state().selected, []);
});

test('removing a project disconnects it and never deletes files', async () => {
  const p = explorerPage();
  p.run(`window.confirm = () => true;
         removeProject({ repo_id: 'repo-a', name: 'alpha' });`);
  await tick();
  const call = p.requests.shift();
  assert.equal(call.path, '/v1/code/forget');
  assert.deepEqual(call.body, { repo_id: 'repo-a', discard_undo: false });
  // Nothing in the surface asks for a delete, rename or move.
  assert.doesNotMatch(source, /\/v1\/code\/delete|file\.delete|file\.rename/);
});

test('removal is refused while a request for that project is running', async () => {
  const p = explorerPage();
  p.run(`proposing = true; window.confirm = () => true;
         removeProject({ repo_id: 'repo-a', name: 'alpha' });`);
  await tick();
  assert.deepEqual(p.requests.filter((r) => /forget/.test(r.path)), []);
  assert.ok(p.notices.length, 'the refusal is explained');
});

test('removal sends an explicit second acknowledgement for repository-wide Undo loss', async () => {
  const p = explorerPage();
  p.run(`window.confirm = () => true;
         removeProject({ repo_id: 'repo-a', name: 'alpha' });`);
  await tick();
  const first = p.requests.shift();
  first.reply({ confirmation_required: true, undo_lost: 3 });
  await tick();
  const second = p.requests.shift();
  assert.deepEqual(second.body, { repo_id: 'repo-a', discard_undo: true });
});

test('removal explains that the folder and its files are untouched', () => {
  assert.match(source, /This disconnects the folder from Refinix/);
  assert.match(source, /Your files are not deleted/);
  assert.match(source, /the folder stays exactly where it is/);
});

test('a new Code conversation is created and clears only the work area', async () => {
  const p = explorerPage();
  p.run('newCodeConversation();');
  await tick();
  const call = p.requests.shift();
  assert.equal(call.path, '/v1/code/conversation');
  call.reply({ chat_id: 'conv-1', title: 'New code conversation' });
  await tick();
  assert.equal(p.json('codeConversation'), 'conv-1');
  // Projects stay connected: a new conversation is not a disconnection.
  assert.equal(p.json('codeState.repositories.length'), 2);
});

test('startup creates or selects a conversation before requesting Code state', async () => {
  const p = page();
  const opening = p.run(`codeConversation = null; codeConversations = [];
                         codeState = null; initializeCode();`);
  await tick();
  const history = p.requests.shift();
  assert.equal(history.path, '/v1/code/conversations');
  history.reply({ conversations: [] });
  await tick();
  const create = p.requests.shift();
  assert.equal(create.path, '/v1/code/conversation');
  assert.deepEqual(p.requests.filter((r) => /code\/state/.test(r.path)), []);
  create.reply({ chat_id: 'fresh', title: 'Code conversation', repo_id: null });
  await tick();
  p.requests.shift().reply({ conversations: [
    { chat_id: 'fresh', title: 'Code conversation', repo_id: null,
      project_available: false }] });
  await tick();
  const state = p.requests.shift();
  assert.match(state.path, /conversation_id=fresh/);
  state.reply(stateBody(null, { conversation: {
    chat_id: 'fresh', repo_id: null, open_path: null,
    project_available: false } }));
  await opening;
});

test('a code request carries its conversation so work cannot cross over', () => {
  assert.match(source, /conversation_id: codeConversation \|\| undefined/);
});

test('history lists Code conversations and marks an unavailable project', async () => {
  const p = explorerPage();
  p.run(`codeConversations = [
    { chat_id: 'c1', title: 'Fix limits', repo_id: 'repo-a',
      repo_name: 'alpha', project_available: true },
    { chat_id: 'c2', title: 'Old work', repo_id: 'gone',
      repo_name: null, project_available: false }];
    codeConversation = 'c1';
    document.getElementById('conv-history-list').hidden = false;
    renderConversationHead();`);
  const items = p.document.getElementById('conv-history-list').children;
  assert.deepEqual(items.map((i) => i.children[0].textContent),
                   ['Fix limits', 'Old work']);
  assert.match(items[1].children[1].textContent, /no longer connected/i);
  assert.equal(items[0].getAttribute('aria-current'), 'true');
});

test('the three columns exist with the conversation on the right', () => {
  assert.match(codeHtml, /<nav class="nav"[\s\S]*id="explorer"/);
  assert.match(codeHtml, /<main class="main"[\s\S]*id="viewer"/);
  assert.match(codeHtml, /<aside class="rail rail-conversation"[\s\S]*id="code-composer"/);
  // The tree, tabs and history carry their roles rather than looking the part.
  assert.match(codeHtml, /id="explorer" role="tree"/);
  assert.match(codeHtml, /id="viewer-tabs" role="tablist"/);
  assert.match(codeHtml, /id="conv-history-list" role="dialog"/);
});

test('both walls stay reachable in a narrow window', () => {
  const css = readFileSync(`${__dirname}/refinix.css`, 'utf8');
  assert.match(css, /@media \(max-width: 1180px\)[\s\S]*rail-conversation/);
  // The file scrolls inside its own box, so the page never scrolls sideways.
  assert.match(css, /\.viewer-body \{[\s\S]*overflow: auto/);
  assert.match(codeHtml, /id="nav-toggle"[\s\S]*aria-controls="nav"/);
  assert.match(codeHtml, /id="rail-toggle"[\s\S]*aria-controls="rail"/);
});

test('closing the file empties the viewer without touching the project', () => {
  const p = explorerPage();
  p.run(`openFile = { repo_id: 'repo-a', path: 'README.md' }; closeViewer();`);
  assert.equal(p.json('openFile === null'), true);
  assert.equal(p.json('codeState.repositories.length'), 2);
  assert.equal(p.document.getElementById('viewer-tabs').hidden, true);
});

/* ---- Execution 4C: local apply, reject and undo ------------------------- */

function localPage(extra = {}) {
  const p = page();
  p.run(`
    codeState = ${JSON.stringify({
      ...stateBody('repo-a'),
      execution_target: 'this_device',
      validation_note: 'Not sandbox tested — local device mode',
      ...extra,
    })};
    activeRepo = 'repo-a';
    codeConversation = 'conv-a';
  `);
  return p;
}

test('the execution target is chosen and travels with the request', () => {
  assert.match(source, /let executionTarget = 'this_device'/);
  assert.match(source, /execution_target: executionTarget/);
  // Both destinations are offered, and each says what it costs.
  assert.match(source, /id: 'this_device'[\s\S]*?no sandbox tests/);
  assert.match(source, /id: 'distributed'[\s\S]*?sandbox tested/);
});

test('a local proposal is labelled as not sandbox tested', () => {
  const p = localPage();
  const card = p.json(`(() => {
    const card = proposalCard({ proposal_id: 'p1', digest: 'd', state: 'proposed',
      summary: 's', edits: [{ path: 'a.py', diff: '- x\\n+ y' }] });
    const find = (node) => node.dataset && node.dataset.state === 'unvalidated'
      ? node.textContent
      : (node.children || []).map(find).find(Boolean);
    return { note: find(card) || null };
  })()`);
  assert.match(card.note, /Not sandbox tested/);
});

test('a local proposal offers Accept and Reject, not sandbox validation', () => {
  const p = localPage();
  const labels = p.json(`(() => {
    const card = proposalCard({ proposal_id: 'p1', digest: 'd', state: 'proposed',
      summary: 's', edits: [{ path: 'a.py', diff: 'one line' }] });
    const out = [];
    const walk = (n) => { if (n.tag === 'button') out.push(n.textContent);
                          (n.children || []).forEach(walk); };
    walk(card); return out;
  })()`);
  assert.deepEqual(labels, ['Accept and apply', 'Reject']);
  assert.ok(!labels.includes('Validate in sandbox'));
});

test('a distributed proposal still routes through sandbox validation', () => {
  const p = page();
  p.run(`codeState = ${JSON.stringify({ ...stateBody('repo-a'),
    execution_target: 'distributed' })}; activeRepo = 'repo-a';`);
  const labels = p.json(`(() => {
    const card = proposalCard({ proposal_id: 'p1', digest: 'd', state: 'proposed',
      summary: 's', edits: [{ path: 'a.py', diff: 'one line' }] });
    const out = [];
    const walk = (n) => { if (n.tag === 'button') out.push(n.textContent);
                          (n.children || []).forEach(walk); };
    walk(card); return out;
  })()`);
  assert.ok(labels.includes('Validate in sandbox'), labels.join(','));
});

test('Undo appears only after a local apply that has a stored original', () => {
  const withBackup = localPage({ can_undo: true });
  const labels = (p) => p.json(`(() => {
    const card = proposalCard({ proposal_id: 'p1', digest: 'd', state: 'applied',
      summary: 's', edits: [{ path: 'a.py', diff: 'one line' }] });
    const out = [];
    const walk = (n) => { if (n.tag === 'button') out.push(n.textContent);
                          (n.children || []).forEach(walk); };
    walk(card); return out;
  })()`);
  assert.deepEqual(labels(withBackup), ['Undo this change']);
  assert.deepEqual(labels(localPage({ can_undo: false })), []);
});

test('Reject sends a decision and writes nothing', async () => {
  const p = localPage();
  p.run(`rejectProposal('p1');`);
  await tick();
  const call = p.requests.shift();
  assert.equal(call.path, '/v1/code/reject');
  assert.equal(call.body.conversation_id, 'conv-a');
  assert.deepEqual(p.requests.filter((r) => /apply/.test(r.path)), []);
});

test('the file view is re-read from disk after Apply and after Undo', async () => {
  for (const start of ["applyProposal('p1', null)", "undoProposal('p1')"]) {
    const p = localPage({ can_undo: true });
    p.run(`openFile = { repo_id: 'repo-a', path: 'a.py', lines: ['old'] };`);
    p.run(`${start};`);
    // Answer each call in turn — the write, the state refresh, the listing —
    // until the surface asks to re-read the open file.
    let view = null;
    for (let step = 0; step < 12 && !view; step += 1) {
      await tick();
      const call = p.requests.shift();
      if (!call) continue;
      if (/\/v1\/code\/view/.test(call.path)) { view = call; break; }
      if (/\/v1\/code\/state/.test(call.path)) {
        call.reply({ ...JSON.parse(p.run('JSON.stringify(codeState)')) });
      } else if (/\/v1\/code\/files/.test(call.path)) {
        call.reply({ files: [], limits: { max_files: 20 } });
      } else {
        call.reply({ state: 'applied', applied: 1, total: 1, results: [],
                     restored: 1, total_files: 1, files: [] });
      }
    }
    assert.ok(view, `${start} must re-read the open file`);
    view.reply({ path: 'a.py', lines: ['new from disk'] });
    await tick();
    assert.match(p.document.getElementById('viewer-body').textContent,
                 /new from disk/);
  }
});

test('a failed Apply or Undo never blanks the file view', async () => {
  const p = localPage({ can_undo: true });
  p.run(`openFile = { repo_id: 'repo-a', path: 'a.py', lines: ['keep me'] };
         paintFile(['keep me']);`);
  p.run(`undoProposal('p1');`);
  await tick();
  p.requests.shift().fail('the write failed');
  await tick();
  assert.match(p.document.getElementById('viewer-body').textContent, /keep me/);
  assert.ok(p.notices.length, 'the failure is reported');
});

test('turning on Full access warns that sandbox tests will not run', () => {
  // The sentence comes from the coordinator, so the warning cannot drift
  // from the policy it describes.
  assert.match(source, /mode\.confirm_note \? `\$\{mode\.confirm_note\} ` : ''/);
  assert.match(source, /Turn on Full access for this folder\?/);
});

/* ---- Review corrections ------------------------------------------------ */

test('approving a view reopens that exact file, never a proposal', async () => {
  const p = localPage();
  p.run(`openFileInViewer('repo-a', 'pkg/limits.py');`);
  await tick();
  p.requests.shift().reply({ needs_approval: {
    approval_id: 'ap-view', repo_id: 'repo-a', action: 'repo.view',
    target: 'pkg/limits.py',
    expires_at: 'later', detail: { repo_name: 'alpha', paths: ['pkg/limits.py'] },
  } });
  await tick();
  // The durable approval itself carries the exact file, so a refresh does not
  // lose what Approve is meant to open.
  assert.equal(p.json('codeState.pending_approvals.length'), 1);

  p.run(`decideApproval({ approval_id: 'ap-view', repo_id: 'repo-a',
                          action: 'repo.view', target: 'pkg/limits.py',
                          detail: { paths: ['pkg/limits.py'] } }, true);`);
  await tick();
  const decision = p.requests.shift();
  assert.equal(decision.path, '/v1/code/decision');
  decision.reply({});
  await tick();
  const view = p.requests.find((r) => /\/v1\/code\/view/.test(r.path));
  assert.ok(view, 'approving repo.view must reopen the file');
  assert.match(view.path, /path=pkg%2Flimits\.py/);
  assert.match(view.path, /approval_id=ap-view/);
  assert.deepEqual(p.requests.filter((r) => /propose/.test(r.path)), [],
                   'it must never fall through to proposeChange');
});

test('code state requests name the conversation they are for', () => {
  assert.match(source, /conversation_id=\$\{encodeURIComponent\(codeConversation\)\}/);
});

test('switching conversation reloads and restores its saved messages', async () => {
  const p = localPage();
  p.run(`codeConversations = [{ chat_id: 'c2', title: 'Other', repo_id: null,
                                project_available: false }];
         openFile = { repo_id: 'repo-a', path: 'a.py' };
         selectConversation('c2');`);
  await tick();
  assert.equal(p.json('openFile === null'), true,
               'another conversation must not keep this one’s open file');
  const state = p.requests.find((r) => /\/v1\/code\/state/.test(r.path));
  assert.ok(state, 'the newly selected conversation is loaded');
  assert.match(state.path, /conversation_id=c2/);
  p.requests.splice(p.requests.indexOf(state), 1);
  state.reply(stateBody(null, { conversation: {
    chat_id: 'c2', repo_id: null, open_path: null,
    project_available: false } }));
  await tick();
  const messages = p.requests.shift();
  assert.match(messages.path, /\/v1\/messages\?chat_id=c2/);
  messages.reply({ messages: [
    { message_id: 'm1', role: 'user', text: 'saved request' },
    { message_id: 'm2', role: 'assistant', text: 'saved answer' }] });
  await tick();
  assert.match(p.document.getElementById('thread').textContent, /saved request/);
  assert.match(p.document.getElementById('thread').textContent, /saved answer/);
});

test('a removed project is not reconnected by reopening its history', () => {
  assert.match(source,
    /const project = entry && entry\.project_available \? entry\.repo_id : null/);
});

test('opening a file persists its relative path in the conversation', async () => {
  const p = localPage();
  p.run(`openFileInViewer('repo-a', 'README.md');`);
  await tick();
  p.requests.shift().reply({ repo_id: 'repo-a', path: 'README.md',
                             lines: ['hello'], sent_to_model: false });
  await tick();
  const saved = p.requests.shift();
  assert.equal(saved.path, '/v1/code/conversation/context');
  assert.equal(saved.body.conversation_id, 'conv-a');
  assert.equal(saved.body.open_path, 'README.md');
});

test('removal requires the coordinator count before discarding Undo', () => {
  assert.match(source, /result\.confirmation_required/);
  assert.match(source, /result\.undo_lost/);
  assert.match(source, /discard_undo: true/);
});
