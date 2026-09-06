/* Offline regressions for the Execution 3 composers. Run: node --test this-file
 *
 * What these protect:
 *   - the Code surface no longer holds three permanent dashboard panels, and
 *     the safety information they carried is still reachable — access in the
 *     composer, diffs and approvals as results, audit under Details;
 *   - the project chooser sits above the prompt box and uses the native
 *     dialog, never a typed path;
 *   - both prompt boxes grow, cap, scroll and shrink;
 *   - the context indicator reads the coordinator's estimate rather than
 *     counting tokens in the page.
 *
 * Everything is synthetic. No request leaves the harness.
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');

const DIR = __dirname;
const source = readFileSync(`${DIR}/app.js`, 'utf8').replace(/^import .*$/m, '');
const codeHtml = readFileSync(`${DIR}/code.html`, 'utf8');
const chatHtml = readFileSync(`${DIR}/index.html`, 'utf8');
const tick = () => new Promise(setImmediate);

/* A textarea whose scrollHeight follows its content, so the growth rule can be
 * exercised without a browser. */
function makeDocument() {
  const node = (tag = 'div') => {
    const el = {
      tag, children: [], dataset: {}, style: {}, hidden: false, disabled: false,
      value: '', checked: false, className: '', title: '', rows: 3, _text: '',
      attributes: {}, classList: { add() {}, remove() {} },
      set textContent(v) { this._text = String(v); this.children = []; },
      get textContent() {
        return this._text + this.children.map((c) => c.textContent).join('');
      },
      // 20px per line, as a real textarea roughly behaves.
      get scrollHeight() {
        const lines = String(this.value || '').split('\n').length;
        return Math.max(1, lines) * 20 + 12;
      },
      append(...kids) {
        for (const k of kids) {
          if (k && k.isFragment) this.children.push(...k.children);
          else this.children.push(k);
        }
      },
      replaceChildren(...kids) { this.children = []; this.append(...kids); },
      setAttribute(name, value) { this.attributes[name] = String(value); },
      getAttribute(name) { return this.attributes[name]; },
      removeAttribute(name) { delete this.attributes[name]; },
      addEventListener(type, fn) { (this.handlers ||= {})[type] = fn; },
      dispatch(type) { if (this.handlers && this.handlers[type]) this.handlers[type](); },
      querySelector() { return null; }, querySelectorAll() { return []; },
      getBoundingClientRect() { return { top: 100, left: 10, right: 60, bottom: 120 }; },
      focus() {}, remove() {}, contains() { return false; },
      get isConnected() { return true; },
    };
    return el;
  };
  const byId = new Map();
  return {
    byId,
    getElementById(id) {
      if (!byId.has(id)) byId.set(id, node(`#${id}`));
      return byId.get(id);
    },
    createElement: (tag) => node(tag),
    createDocumentFragment: () => Object.assign(node('#fragment'), { isFragment: true }),
    createElementNS: (_ns, tag) => node(tag),
    addEventListener() {},
    body: node('body'),
  };
}

function page({ bridge } = {}) {
  const document = makeDocument();
  const requests = [];
  const notices = [];
  const listeners = {};
  const scope = vm.createContext({
    document,
    window: {
      addEventListener(type, fn) { listeners[type] = fn; },
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
  `, scope);
  const run = (code) => vm.runInContext(code, scope);
  const json = (code) => JSON.parse(JSON.stringify(run(code)));
  return { run, json, requests, notices, document, listeners,
           state: () => json(`({ activeRepo, selected: [...selectedPaths],
             files: repoFiles.map((file) => file.path) })`) };
}

// --------------------------------------------------------------------------
// Markup requirements
// --------------------------------------------------------------------------

test('the three permanent dashboard panels are gone from Code', () => {
  // The old surface kept Access mode, Proposed change and What Refinix did as
  // permanent central sections. None of them may be markup any more.
  assert.doesNotMatch(codeHtml, /id="mode-card"/);
  assert.doesNotMatch(codeHtml, /id="mode-choices"/);
  assert.doesNotMatch(codeHtml, /id="code-body"/);
  assert.doesNotMatch(codeHtml, /<h2>Access mode<\/h2>/);
});

test('the project chooser sits immediately above the Code prompt box', () => {
  const chooser = codeHtml.indexOf('id="connect-btn"');
  const box = codeHtml.indexOf('id="composer-box"');
  const input = codeHtml.indexOf('id="code-input"');
  assert.ok(chooser > 0 && box > 0 && input > 0);
  assert.ok(chooser < box, 'the chooser comes before the prompt box');
  assert.ok(chooser < input, 'the chooser comes before the prompt');
  assert.match(codeHtml, /class="project-row"/);
});

test('the access selector lives in the composer, beside +', () => {
  const bar = codeHtml.slice(codeHtml.indexOf('class="composer-bar"'));
  assert.match(bar, /id="plus-btn"/);
  assert.match(bar, /id="mode-pill"/);
  assert.ok(bar.indexOf('id="plus-btn"') < bar.indexOf('id="mode-pill"'),
            'the access pill sits after + in the lower-left group');
});

test('the audit history is behind Details, not in the work area', () => {
  const rail = codeHtml.slice(codeHtml.indexOf('<aside'));
  assert.match(rail, /id="audit-list"/);
  assert.match(codeHtml, /id="rail-toggle"[\s\S]*?Details/);
});

test('both prompt boxes start at one row', () => {
  assert.match(codeHtml, /id="code-input"[\s\S]*?rows="1"/);
  assert.match(chatHtml, /id="input"[\s\S]*?rows="[12]"/);
});

test('the Chat composer carries a context indicator', () => {
  assert.match(chatHtml, /id="context-meter"/);
  assert.match(chatHtml, /id="context-figure"/);
});

test('no page counts tokens for itself', () => {
  // One estimator, in context.py. A second one in JavaScript would eventually
  // disagree with the request that actually gets sent.
  assert.match(source, /\/v1\/context/);
  assert.doesNotMatch(source, /CHARS_PER_TOKEN/);
});

test('Code file loading is not gated by a removed dashboard element', () => {
  assert.doesNotMatch(source, /if \(!\$\('file-list'\)\) return null/);
});

test('the attachment notice describes the selected document skill truthfully', () => {
  assert.doesNotMatch(source, /cannot read documents yet/);
  assert.match(source, /Plain Chat saved them[\s\S]*did not read them/);
});

test('artifact approval ids travel in a POST body, not a logged URL', () => {
  assert.doesNotMatch(source, /artifact\/export\?artifact_id/);
  assert.match(source, /fetch\('\/v1\/artifact\/export',[\s\S]*method: 'POST'/);
});

// --------------------------------------------------------------------------
// Composer growth
// --------------------------------------------------------------------------

test('a prompt box grows with its lines, caps, scrolls and shrinks again', () => {
  const p = page();
  const input = p.document.getElementById('code-input');
  p.run("wireAutogrow(document.getElementById('code-input'))");

  input.value = 'one line';
  p.run("autogrow(document.getElementById('code-input'))");
  const small = parseInt(input.style.height, 10);
  assert.ok(small > 0 && small < 100, `one line measured ${small}px`);
  assert.equal(input.style.overflowY, 'hidden');

  input.value = Array.from({ length: 6 }, (_, i) => `line ${i}`).join('\n');
  p.run("autogrow(document.getElementById('code-input'))");
  const medium = parseInt(input.style.height, 10);
  assert.ok(medium > small, 'it grows with the text');

  input.value = Array.from({ length: 80 }, (_, i) => `line ${i}`).join('\n');
  p.run("autogrow(document.getElementById('code-input'))");
  const capped = parseInt(input.style.height, 10);
  assert.equal(capped, p.run('COMPOSER_MAX_PX'), 'it stops at the maximum');
  assert.equal(input.style.overflowY, 'auto', 'and scrolls inside itself');

  input.value = 'one line';
  p.run("autogrow(document.getElementById('code-input'))");
  assert.equal(parseInt(input.style.height, 10), small, 'and shrinks back');
  assert.equal(input.style.overflowY, 'hidden');
});

test('the box is never manually resizable', () => {
  const p = page();
  p.run("wireAutogrow(document.getElementById('input'))");
  assert.equal(p.document.getElementById('input').style.resize, 'none');
});

test('a window resize re-measures the box', () => {
  const p = page();
  const input = p.document.getElementById('input');
  p.run("wireAutogrow(document.getElementById('input'))");
  input.value = 'a\nb\nc\nd';
  input.style.height = '0px';
  p.listeners.resize();
  assert.ok(parseInt(input.style.height, 10) > 0);
});

// --------------------------------------------------------------------------
// Context indicator
// --------------------------------------------------------------------------

async function estimate(p, body) {
  const pending = p.run('refreshContext()');
  await tick();
  const request = p.requests.shift();
  request.reply(body);
  await tick();
  await pending;
  return request;
}

const OK_ESTIMATE = {
  used_tokens: 1200, budget_tokens: 5200, context_window: 8192,
  reply_allowance: 2048, omitted_count: 0, newest_fits: true, level: 'ok',
  counting_method: 'estimate: characters / 4', estimate: true, note: null,
  draft_counted: true, policy: 'Saved history is never changed.',
};

test('the indicator shows a compact estimate from the coordinator', async () => {
  const p = page();
  p.run("chatId = 'chat-1'");
  p.document.getElementById('input').value = 'a draft';
  const request = await estimate(p, OK_ESTIMATE);
  assert.equal(request.path, '/v1/context');
  assert.equal(request.options.method, 'POST');
  assert.deepEqual(request.body, { chat_id: 'chat-1', draft: 'a draft' });
  assert.doesNotMatch(request.path, /a draft|chat-1/);
  const figure = p.document.getElementById('context-figure').textContent;
  assert.match(figure, /Context ≈ 1\.2k \/ 5\.2k/);
  assert.equal(p.document.getElementById('context-meter').hidden, false);
});

test('the indicator warns before earlier turns start being left out', async () => {
  const p = page();
  await estimate(p, { ...OK_ESTIMATE, used_tokens: 4600, level: 'near' });
  const meter = p.document.getElementById('context-meter');
  assert.equal(meter.dataset.level, 'near');
  assert.match(meter.title, /close to the amount/);
});

test('once turns are omitted it says they stay saved and suggests a new chat', async () => {
  const p = page();
  await estimate(p, { ...OK_ESTIMATE, omitted_count: 6, level: 'omitting' });
  const meter = p.document.getElementById('context-meter');
  assert.equal(meter.dataset.level, 'omitting');
  assert.match(meter.title, /stay saved/);
  assert.match(meter.title, /new chat/);
});

test('a message too long to send on its own says so', async () => {
  const p = page();
  await estimate(p, { ...OK_ESTIMATE, newest_fits: false, level: 'over' });
  assert.match(p.document.getElementById('context-meter').title, /too long/);
});

test('the indicator hides rather than guessing when the estimate fails', async () => {
  const p = page();
  const pending = p.run('refreshContext()');
  await tick();
  p.requests.shift().fail('unavailable');
  await tick();
  await pending;
  assert.equal(p.document.getElementById('context-meter').hidden, true);
});

// --------------------------------------------------------------------------
// Code composer behaviour
// --------------------------------------------------------------------------

const MODES = [
  { id: 'partial', label: 'Partial access', summary: 'partial', confirm: false },
  { id: 'full', label: 'Full access', summary: 'full', confirm: true },
  { id: 'ask', label: 'Ask before actions', summary: 'ask', confirm: false },
];

function stateBody(active, extra = {}) {
  return {
    repositories: [{ repo_id: 'repo-a', name: 'alpha', mode: 'ask' },
                   { repo_id: 'repo-b', name: 'beta', mode: 'partial' }],
    active, modes: MODES, unavailable: [], pending_approvals: [],
    proposal: null, audit: [], limits: { max_files: 20 },
    code_supported: true, writes_supported: true, platform_note: null,
    ...extra,
  };
}

async function activate(p, repoId, { files = [], reset = false, extra = {} } = {}) {
  const opening = p.run(`loadCodeState(${JSON.stringify(repoId)}, `
    + `{ reset: ${reset ? 'true' : 'false'} })`);
  await tick();
  p.requests.shift().reply(stateBody(repoId, extra));
  await tick();
  if (p.requests.length) p.requests.shift().reply({ files });
  await tick();
  await opening;
}

test('the access pill shows the Codex-style label for the stored mode id', async () => {
  const p = page();
  await activate(p, 'repo-a');
  assert.equal(p.document.getElementById('mode-name').textContent, 'Ask for approval');
  assert.equal(p.document.getElementById('mode-pill').dataset.mode, 'ask');
  // The backend ids are untouched: only the words the user reads changed.
  assert.deepEqual(p.json('Object.keys(MODE_LABELS).sort()'),
                   ['ask', 'full', 'partial']);
});

test('choosing a mode sends the existing backend id', async () => {
  const p = page();
  await activate(p, 'repo-a');
  p.run("changeMode({ id: 'partial', confirm: false })");
  await tick();
  const request = p.requests.shift();
  assert.equal(request.path, '/v1/code/mode');
  assert.equal(request.body.mode, 'partial');
  assert.equal(request.body.repo_id, 'repo-a');
});

test('Full access still asks for its confirmation', async () => {
  const p = page();
  await activate(p, 'repo-a');
  p.run('confirmDialog = async () => false');
  p.run("changeMode({ id: 'full', confirm: true })");
  await tick();
  assert.equal(p.requests.length, 0, 'a declined confirmation changes nothing');
});

test('the project name replaces Choose project once a folder is connected', async () => {
  const p = page();
  await activate(p, null);
  assert.equal(p.document.getElementById('project-name').textContent, 'Choose project');
  await activate(p, 'repo-a');
  assert.equal(p.document.getElementById('project-name').textContent, 'alpha');
  assert.equal(p.document.getElementById('switch-btn').hidden, false);
});

test('connecting a folder uses the native dialog and never a typed path', async () => {
  let called = 0;
  const bridge = {
    choose_repository: async () => {
      called += 1;
      return { repository: { repo_id: 'repo-b', name: 'beta' } };
    },
  };
  const p = page({ bridge });
  await activate(p, 'repo-a', { files: [{ path: 'shared.py', bytes: 4 }] });
  p.run("selectedPaths = new Set(['shared.py'])");

  const connecting = p.run('connectRepository()');
  await tick();
  p.requests.shift().reply(stateBody('repo-b'));
  await tick();
  if (p.requests.length) p.requests.shift().reply({ files: [] });
  await tick();
  await connecting;

  assert.equal(called, 1);
  // No request carried a filesystem path.
  for (const request of p.requests) {
    assert.doesNotMatch(JSON.stringify(request.body || {}), /\/Users\//);
  }
  assert.deepEqual(p.state().selected, [], 'the previous selection is cleared');
});

test('switching projects clears selected context and previous results', async () => {
  const p = page();
  await activate(p, 'repo-a', { files: [{ path: 'shared.py', bytes: 4 }] });
  p.run("selectedPaths = new Set(['shared.py']); shownResults.add('proposal:old')");
  await activate(p, 'repo-b', { files: [], reset: true });
  assert.deepEqual(p.state().selected, []);
  assert.deepEqual(p.state().files, []);
  assert.equal(p.json('shownResults.size'), 0, 'stale results do not carry over');
});

test('a late file list for one project cannot land under another', async () => {
  const p = page();
  await activate(p, 'repo-a', { files: [] });
  const first = p.run("loadCodeState('repo-a')");
  await tick();
  const stateA = p.requests.shift();
  const second = p.run("loadCodeState('repo-b')");
  await tick();
  const stateB = p.requests.shift();

  stateB.reply(stateBody('repo-b'));
  await tick();
  p.requests.shift().reply({ files: [{ path: 'beta-only.py', bytes: 4 }] });
  await tick();
  stateA.reply(stateBody('repo-a'));
  await tick();
  while (p.requests.length) {
    p.requests.shift().reply({ files: [{ path: 'alpha-only.py', bytes: 4 }] });
  }
  await tick();
  await Promise.all([first, second]);

  assert.equal(p.state().activeRepo, 'repo-b');
  assert.deepEqual(p.state().files, ['beta-only.py']);
});

test('a proposal and its complete diff arrive as a result, not a panel', async () => {
  const p = page();
  const proposal = {
    proposal_id: 'prop-1', summary: 'Renamed a function.', state: 'proposed',
    edits: [{ path: 'a.py', diff: '--- a/a.py\n+++ b/a.py\n-old\n+new\n',
              state: 'proposed', detail: null }],
  };
  await activate(p, 'repo-a', { extra: { proposal } });
  const thread = p.document.getElementById('thread');
  assert.ok(thread.children.length > 0, 'the proposal is appended to the thread');
  assert.match(thread.textContent, /Renamed a function\./);
  assert.match(thread.textContent, /\+new/, 'the diff is present in full');
  assert.doesNotMatch(thread.textContent, /more diff lines not shown/);
});

test('an approval appears inline where the work paused', async () => {
  const p = page();
  const approval = {
    approval_id: 'appr-1', action: 'canonical.write', target: 'a.py',
    expires_at: '2026-09-05T12:00:00Z',
    detail: { repo_name: 'alpha', paths: ['a.py'], proposal_id: 'prop-1' },
  };
  await activate(p, 'repo-a', { extra: { pending_approvals: [approval] } });
  const thread = p.document.getElementById('thread');
  assert.match(thread.textContent, /Approve this change\?/);
  assert.match(thread.textContent, /waiting for you/);
});

test('the same result is not appended twice when state is polled again', async () => {
  const p = page();
  const proposal = { proposal_id: 'prop-1', summary: 'One.', state: 'proposed',
                     edits: [] };
  await activate(p, 'repo-a', { extra: { proposal } });
  const first = p.document.getElementById('thread').children.length;
  await activate(p, 'repo-a', { extra: { proposal } });
  assert.equal(p.document.getElementById('thread').children.length, first);
});

test('an unsupported platform offers no connect button', async () => {
  const p = page();
  await activate(p, null, { extra: { code_supported: false,
                                     platform_note: 'Code is unavailable here.' } });
  assert.equal(p.document.getElementById('connect-btn').disabled, true);
  assert.match(p.document.getElementById('thread').textContent, /unavailable here/);
});

test('the model selector lists inventory and keeps Auto disabled for now', () => {
  assert.match(source, /for \(const candidate of models\)/,
    'the selector is populated from the coordinator inventory');
  assert.match(source,
    /appendModelChoiceParts\(auto, false, 'Auto model', 'after internal hackathon'\)/);
  assert.match(source, /auto\.disabled = true/);
  assert.match(source, /skill\?\.id === 'search-documents'\) return null/,
    'search does not claim to select a model it never runs');
});

test('model choices fill the three grid columns instead of the tick column', () => {
  const p = page();
  p.run(`
    models = [{
      id: 'qwen3.5:4b-q4_K_M', installed: true,
      eligible_scopes: ['chat'], locations: ['this computer']
    }];
    modelSelections = { chat: 'qwen3.5:4b-q4_K_M' };
    appendModelChoices(document.body, 'chat', 'Chat model');
  `);
  const group = p.document.body.children[0];
  const auto = group.children[1];
  const selected = group.children[2];
  assert.deepEqual(auto.children.map((node) => node.className),
                   ['mp-tick', 'mp-model-name', 'mp-tag']);
  assert.equal(auto.children[1].textContent, 'Auto model');
  assert.deepEqual(selected.children.map((node) => node.className),
                   ['mp-tick', 'mp-model-name', 'mp-tag']);
  assert.equal(selected.children[1].textContent, 'qwen3.5:4b-q4_K_M');
  assert.equal(selected.getAttribute('aria-checked'), 'true');
});
