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
    const handlers = {};
    const listenerCounts = {};
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
      addEventListener(type, fn) {
        handlers[type] = fn;
        listenerCounts[type] = (listenerCounts[type] || 0) + 1;
      },
      dispatch(type) { if (handlers[type]) handlers[type](); },
      listenerCount(type) { return listenerCounts[type] || 0; },
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
    codeConversation = 'test-conversation';
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
  // Execution 4B moved the conversation into the right column. The audit is
  // still there and still collapsed — removing the panel must not remove the
  // record it held.
  const rail = codeHtml.slice(codeHtml.indexOf('<aside'));
  assert.match(rail, /id="audit-list"/);
  assert.match(rail, /<details[\s\S]*?id="audit-list"/);
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
  assert.match(source, /Plain Chat reads only the files sent with this request/);
  assert.doesNotMatch(source, /Plain Chat saved them[\s\S]*did not read them/);
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
  p.requests.shift().reply({ chat_id: 'test-conversation', repo_id: 'repo-b',
                             open_path: null });
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

test('the model selector lists inventory and offers Auto as a real choice', () => {
  assert.match(source, /for \(const candidate of models\)/,
    'the selector is populated from the coordinator inventory');
  assert.match(source, /body: JSON\.stringify\(\{ scope, model: 'auto' \}\)/,
    'choosing Auto stores Auto, not a model');
  assert.doesNotMatch(source, /after internal hackathon/);
  assert.match(source, /skill\?\.id === 'search-documents'\) return null/,
    'search does not claim to select a model it never runs');
});

test('reading scanned pages is labelled Beta wherever its model is chosen or named', () => {
  assert.match(source, /appendModelChoices\(box, 'documents\.ocr', 'Document OCR model \(Beta\)'\)/);
  assert.match(source, /'documents\.ocr': 'Page reading \(Beta\)'/);
});

test('Auto says which model it would use now, by its display name', () => {
  const p = page();
  p.run(`
    models = [{ id: 'gemma-3-4b-it-q4_k_m', key: 'llama.cpp|gemma-3-4b-it-q4_k_m',
                display_name: 'Gemma 3 4B instruct (Q4_K_M)', installed: true,
                runtime_label: 'Refinix engine',
                eligible_scopes: ['chat'], locations: ['this computer'] }];
    modelSelections = { chat: 'auto' };
    modelChoices = { chat: { key: 'llama.cpp|gemma-3-4b-it-q4_k_m',
                             reason: 'Auto: Chat → Gemma', refusal: null } };
    appendModelChoices(document.body, 'chat', 'Chat model');
  `);
  const group = p.document.body.children[0];
  const auto = group.children[1];
  assert.equal(auto.children[1].textContent, 'Auto');
  assert.match(auto.children[2].textContent, /now Gemma 3 4B instruct/);
  assert.equal(auto.getAttribute('aria-checked'), 'true');
  const row = group.children[2];
  assert.match(row.children[2].textContent, /Refinix engine/);
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
  assert.equal(auto.children[1].textContent, 'Auto');
  assert.deepEqual(selected.children.map((node) => node.className),
                   ['mp-tick', 'mp-model-name', 'mp-tag']);
  assert.equal(selected.children[1].textContent, 'qwen3.5:4b-q4_K_M');
  assert.equal(selected.getAttribute('aria-checked'), 'true');
});

test('a model Auto avoids says why in the menu, before it is chosen', () => {
  const p = page();
  p.run(`
    models = [{
      id: 'reader:1', key: 'ollama|reader:1', installed: true,
      eligible_scopes: ['chat'], locations: ['this computer'],
      auto_excluded: { chat: 'did not finish its answer within the check limit' }
    }, {
      id: 'plain:1', key: 'ollama|plain:1', installed: true,
      eligible_scopes: ['chat'], locations: ['this computer'], hints: ['general']
    }];
    modelSelections = { chat: 'auto' };
    appendModelChoices(document.body, 'chat', 'Chat model');
  `);
  const group = p.document.body.children[0];
  const reader = group.children[2];
  const plain = group.children[3];
  assert.equal(reader.disabled, false, 'still the person\'s to choose');
  assert.match(reader.textContent, /Auto does not use it for Chat: its check here did not finish/);
  assert.doesNotMatch(plain.textContent, /Auto does not use it/);
});

test('a Chat-backed document skill is not told its model is unavailable', () => {
  // On the limited route the model selected for Documents runs under its Chat
  // profile. The capability row says so with model_scope, and the pill must
  // check that scope rather than documents.generate, which the model rightly
  // lacks.
  const p = page();
  // The Chat surface: there is no Code composer on this page.
  const byId = p.document.getElementById.bind(p.document);
  p.document.getElementById = (id) => (id === 'code-composer' ? null : byId(id));
  const title = (row) => p.run(`
    models = [{ id: 'qwen3.5:4b-q4_K_M', installed: true, reasoning: false,
                eligible_scopes: ['chat', 'code'] }];
    modelSelections = { chat: 'qwen3.5:4b-q4_K_M',
                        'documents.generate': 'qwen3.5:4b-q4_K_M' };
    skillByChat.set(currentSlot(), ${JSON.stringify(row)});
    renderModelPill();
    document.getElementById('model-pill').title;
  `);
  const base = { id: 'read-document', name: 'Read a document', kind: 'document',
                 state: 'available', icon: 'document' };
  assert.equal(title({ ...base, model_scope: 'chat' }), '');
  assert.equal(title(base), 'This model is not available for this workflow.',
    'without the Chat-backed scope the structured requirement still applies');
});

test('Write Document offers an explicit Word or PDF choice', () => {
  const p = page();
  p.run(`appendDocumentChoices(document.body);`);
  const groups = p.document.body.children.filter(
    (node) => node.className === 'mp-choices');
  assert.equal(groups.length, 2, 'a format group and a workflow group');
  const [format, workflow] = groups;
  assert.equal(format.getAttribute('aria-label'), 'Save as');
  assert.equal(workflow.getAttribute('aria-label'), 'Workflow');
  const names = (group) => group.children[1].children.map(
    (row) => row.children[1].textContent);
  assert.deepEqual(names(format), ['Word (.docx)', 'PDF (.pdf)']);
  assert.deepEqual(names(workflow),
                   ['General document', 'Inspection approval note']);
});

test('the document choices start on Word and the general workflow', () => {
  const p = page();
  p.run(`appendDocumentChoices(document.body);`);
  const groups = p.document.body.children.filter(
    (node) => node.className === 'mp-choices');
  const checked = (group) => group.children[1].children
    .filter((row) => row.getAttribute('aria-checked') === 'true')
    .map((row) => row.children[1].textContent);
  assert.deepEqual(checked(groups[0]), ['Word (.docx)']);
  assert.deepEqual(checked(groups[1]), ['General document']);
});

/* A format this computer cannot write.
 *
 * Word is portable and is the required artifact; PDF writing still needs the
 * macOS frameworks. The picker used to offer PDF everywhere, which meant a
 * Windows or Linux user chose it, pressed Send, and only then learned it was
 * impossible. The coordinator now says which formats it can write. */
test('a format this computer cannot write is shown disabled with a reason', () => {
  const p = page();
  p.run(`lastStatus = { documents: { generates: ['docx'],
    generate_detail: { pdf: 'Writing a PDF needs the macOS frameworks.' } } };
    appendDocumentChoices(document.body);`);
  const format = p.document.body.children.filter(
    (node) => node.className === 'mp-choices')[0];
  const rows = format.children[1].children;
  assert.equal(rows[0].disabled, false, 'Word is always writable');
  assert.equal(rows[1].disabled, true, 'PDF is not writable here');
  assert.equal(rows[1].children[2].textContent, 'unavailable here');
});

test('an unwritable format cannot become the selection', () => {
  const p = page();
  p.run(`outputFormat = 'pdf';
    lastStatus = { documents: { generates: ['docx'], generate_detail: {} } };
    appendDocumentChoices(document.body);`);
  assert.equal(p.run('outputFormat'), 'docx',
    'a selection that cannot be written must not survive to Send');
});

test('clicking a disabled format changes nothing', () => {
  const p = page();
  p.run(`lastStatus = { documents: { generates: ['docx'], generate_detail: {} } };
    appendDocumentChoices(document.body);`);
  const format = p.document.body.children.filter(
    (node) => node.className === 'mp-choices')[0];
  format.children[1].children[1].onclick();
  assert.equal(p.run('outputFormat'), 'docx');
});

test('before any status arrives nothing is switched off', () => {
  // Guessing "unavailable" from a missing answer would disable a format that
  // works. The coordinator still refuses an impossible one at Send.
  const p = page();
  p.run(`lastStatus = null; appendDocumentChoices(document.body);`);
  const rows = p.document.body.children.filter(
    (node) => node.className === 'mp-choices')[0].children[1].children;
  assert.deepEqual(rows.map((row) => row.disabled), [false, false]);
});

test('both formats stay offered where the computer can write both', () => {
  const p = page();
  p.run(`lastStatus = { documents: { generates: ['docx', 'pdf'],
                                     generate_detail: {} } };
    appendDocumentChoices(document.body);`);
  const rows = p.document.body.children.filter(
    (node) => node.className === 'mp-choices')[0].children[1].children;
  assert.deepEqual(rows.map((row) => row.disabled), [false, false]);
});

test('the document choices travel with the request, not just the page', () => {
  assert.match(source,
    /output_format: skill\?\.id === 'write-document' \? sentFormat : undefined/,
    'the chosen format is submitted with the request');
  assert.match(source,
    /doc_workflow: skill\?\.id === 'write-document' \? sentWorkflow : undefined/,
    'the chosen workflow is submitted with the request');
  assert.match(source, /appendDocumentChoices\(box\)/,
    'the choices are offered where the model is chosen');
});

for (const scenario of ['accepted', 'rejected', 'changed', 'switched', 'new', 'new-changed', 'new-switched']) {
  test(`one-shot skill: ${scenario}`, async () => {
    const p = page();
    const isNew = scenario.startsWith('new');
    p.run(`chatId = ${isNew ? 'null' : "'chat-1'"};
      capabilities = [{id:'write-document',kind:'document',name:'Write'},
                      {id:'read-document',kind:'document',name:'Read'}];
      renderModelPill = () => {};
      saveDraftSoon = async () => {}; openChat = async () => {};
      loadChats = async () => {}; refreshContext = () => {};
      chooseSkill('write-document');`);
    const sending = p.run("send('request')");
    await tick();
    if (isNew) { p.requests.shift().reply({chat_id:'chat-new'}); await tick(); }
    const request = p.requests.shift();
    assert.equal(request.body.skill_id, 'write-document');
    if (scenario.endsWith('changed')) p.run("chooseSkill('read-document')");
    if (scenario.endsWith('switched')) p.run("chatId = 'chat-2'; chooseSkill('read-document')");
    if (scenario === 'rejected') {
      request.fail('rejected'); await assert.rejects(sending);
      assert.equal(p.run('selectedSkill().id'), 'write-document');
    } else {
      request.reply({job_id:'job-1'}); await sending;
      assert.equal(p.run('selectedSkill()?.id || null'),
        scenario.endsWith('changed') || scenario.endsWith('switched') ? 'read-document' : null);
      if (scenario === 'switched') assert.equal(p.run("skillByChat.get('chat-1') || null"), null);
      if (isNew) assert.equal(p.run('skillByChat.get(NEW_CHAT_DRAFT) || null'), null);
      if (scenario === 'new-changed') {
        assert.equal(p.document.getElementById('skill-chip').hidden, false);
        const next = p.run("send('next request')");
        await tick();
        const followup = p.requests.shift();
        assert.equal(followup.body.skill_id, 'read-document');
        followup.reply({job_id:'job-2'}); await next;
      }
      if (scenario === 'new-switched') assert.equal(p.run('chatId'), 'chat-2');
    }
  });
}

test('an earlier source is sent explicitly and remains scoped to its chat', async () => {
  const p = page();
  p.run(`chatId='chat-1'; renderStaged=()=>{}; saveDraftSoon=async()=>{};
    openChat=async()=>{}; loadChats=async()=>{}; refreshContext=()=>{};
    chooseReuse({attachment_id:'11111111-1111-1111-1111-111111111111', filename:'scan.png'});`);
  const sending = p.run("send('Complete the OCR')");
  await tick();
  assert.deepEqual(p.requests[0].body.reuse_source_ids,
                   ['11111111-1111-1111-1111-111111111111']);
  p.requests.shift().reply({job_id:'job-1'}); await sending;
  assert.equal(p.run("(reusedByChat.get('chat-1') || []).length"), 0);
});

/* ------------------------------------------------------------------------
 * The document workflow, chosen in the composer.
 *
 * The control and the payload were already correct; the control lived inside
 * the model-settings popover, where nobody looks for it. A real run attached
 * an inspection report and an SOP, asked in plain English for a grounded
 * approval note, and got the general route — because the composer never
 * offered the choice. These checks are about the choice being visible and the
 * chosen value being what is sent, not about the backend workflow.
 * --------------------------------------------------------------------- */

const APPROVAL = 'inspection_report_to_approval_note';

/* A page with Write a document selected, as the + menu leaves it. */
function writing() {
  const p = page();
  p.run(`chatId='chat-1'; renderStaged=()=>{}; saveDraftSoon=async()=>{};
    openChat=async()=>{}; loadChats=async()=>{}; refreshContext=()=>{};
    capabilities=[{id:'write-document', name:'Write a document', icon:'doc',
                   kind:'document', state:'available', detail:''}];
    skillByChat.set('chat-1', capabilities[0]);
    renderSkill();`);
  return p;
}

test('choosing Write a document shows the workflow, defaulting to general', () => {
  const p = writing();
  assert.equal(p.run("document.getElementById('workflow-chip').hidden"), false,
               'the workflow is visible before Send');
  assert.equal(p.run("document.getElementById('workflow-select').value"),
               'general_document');
  // Both workflows are offered, by name rather than by identifier. Joined
  // rather than compared as arrays: the vm returns another realm's Array, so
  // a strict deep-equal fails on the prototype even when the contents match.
  assert.equal(
    p.run("Array.from(document.getElementById('workflow-select').children)"
          + ".map(o => o.textContent).join('|')"),
    'General document|Inspection approval note');
  assert.equal(
    p.run("Array.from(document.getElementById('workflow-select').children)"
          + ".map(o => o.value).join('|')"),
    `general_document|${APPROVAL}`);
});

test('the approval note can be chosen and stays chosen', () => {
  const p = writing();
  p.run(`document.getElementById('workflow-select').value = '${APPROVAL}';
         document.getElementById('workflow-select').dispatch('change');`);
  assert.equal(p.run('docWorkflow'), APPROVAL);
  assert.equal(p.run("document.getElementById('workflow-select').value"), APPROVAL);
  // The positional rule is stated only for the workflow that depends on it.
  assert.equal(p.run("document.getElementById('workflow-hint').hidden"), false);
  assert.match(p.run("document.getElementById('workflow-hint').textContent"),
               /First attachment is treated as the inspection report/);
});

test('rendering the skill repeatedly wires the workflow only once', () => {
  const p = writing();
  p.run('renderSkill(); renderSkill(); renderSkill();');
  assert.equal(
    p.run("document.getElementById('workflow-select').listenerCount('change')"),
    1,
    'real DOM elements expose no test-harness handlers field, so wiring needs '
      + 'its own idempotent marker');
});

test('the general workflow carries no attachment-order instruction', () => {
  const p = writing();
  assert.equal(p.run("document.getElementById('workflow-hint').hidden"), true);
});

test('the chosen workflow is what the request actually sends', async () => {
  const p = writing();
  p.run(`document.getElementById('workflow-select').value = '${APPROVAL}';
         document.getElementById('workflow-select').dispatch('change');`);
  const sending = p.run("send('Draft the approval note')");
  await tick();
  assert.equal(p.requests[0].body.skill_id, 'write-document');
  assert.equal(p.requests[0].body.doc_workflow, APPROVAL);
  p.requests.shift().reply({ job_id: 'job-1' }); await sending;
});

test('the default workflow sends general_document, not the approval note', async () => {
  const p = writing();
  const sending = p.run("send('Write me a document explaining machine learning')");
  await tick();
  assert.equal(p.requests[0].body.doc_workflow, 'general_document');
  p.requests.shift().reply({ job_id: 'job-1' }); await sending;
});

test('attaching and removing files does not change the chosen workflow', () => {
  const p = writing();
  p.run(`document.getElementById('workflow-select').value = '${APPROVAL}';
         document.getElementById('workflow-select').dispatch('change');
         chooseReuse({attachment_id:'11111111-1111-1111-1111-111111111111',
                      filename:'scan.png'});
         renderSkill();`);
  assert.equal(p.run('docWorkflow'), APPROVAL, 'adding a source kept it');
  p.run(`reusedByChat.set('chat-1', []); renderSkill();`);
  assert.equal(p.run('docWorkflow'), APPROVAL, 'removing a source kept it');
});

test('removing the skill hides the workflow and stops sending one', async () => {
  const p = writing();
  p.run(`document.getElementById('workflow-select').value = '${APPROVAL}';
         document.getElementById('workflow-select').dispatch('change');
         skillByChat.delete('chat-1'); renderSkill();`);
  assert.equal(p.run("document.getElementById('workflow-chip').hidden"), true);
  assert.equal(p.run("document.getElementById('workflow-hint').hidden"), true);
  const sending = p.run("send('an ordinary question')");
  await tick();
  // No stale document workflow contaminates an ordinary turn.
  assert.equal(p.requests[0].body.doc_workflow, undefined);
  assert.equal(p.requests[0].body.skill_id, undefined);
  p.requests.shift().reply({ job_id: 'job-1' }); await sending;
});

test('the other document skills neither show nor send a workflow', async () => {
  for (const id of ['read-document', 'search-documents']) {
    const p = page();
    p.run(`chatId='chat-1'; renderStaged=()=>{}; saveDraftSoon=async()=>{};
      openChat=async()=>{}; loadChats=async()=>{}; refreshContext=()=>{};
      capabilities=[{id:'${id}', name:'${id}', icon:'doc', kind:'document',
                     state:'available', detail:''}];
      skillByChat.set('chat-1', capabilities[0]); renderSkill();`);
    assert.equal(p.run("document.getElementById('workflow-chip').hidden"), true,
                 `${id} must not offer a document workflow`);
    const sending = p.run("send('read it')");
    await tick();
    assert.equal(p.requests[0].body.doc_workflow, undefined, id);
    p.requests.shift().reply({ job_id: 'job-1' }); await sending;
  }
});

test('the composer and the model popover are two views of one value', () => {
  const p = writing();
  p.run(`document.getElementById('workflow-select').value = '${APPROVAL}';
         document.getElementById('workflow-select').dispatch('change');`);
  // The popover writes the same state the chip reads, so they cannot disagree.
  p.run("docWorkflow = 'general_document'; renderWorkflowChip();");
  assert.equal(p.run("document.getElementById('workflow-select').value"),
               'general_document');
});

/* ------------------------------------------------------------------------
 * Composer hierarchy.
 *
 * The skill chip, the workflow chip and the prompt shared one flex row, so
 * each control took width away from the thing the person was trying to write
 * in — with two chips the prompt became a narrow column beside them. The
 * guidance line also inherited `skill-status`, which is the caution colour
 * reserved for a capability that is unavailable, so ordinary advice about
 * attachment order read as a warning.
 * --------------------------------------------------------------------- */

test('configuration sits on its own row, not in the prompt row', () => {
  // The prompt no longer shares a flex row with controls that can shrink it:
  // the chips live in `composer-task`, and `composer-line` holds the textarea
  // alone. Asserted against the markup, which is where the structure lives.
  const task = chatHtml.match(
    /<div class="composer-task"[\s\S]*?<\/div>\s*<div class="composer-line"/);
  assert.ok(task, 'the task row precedes the prompt row');
  assert.match(task[0], /id="skill-chip"/);
  assert.match(task[0], /id="workflow-chip"/);
  const line = chatHtml.match(/<div class="composer-line">[\s\S]*?<\/div>/);
  assert.ok(line);
  assert.doesNotMatch(line[0], /skill-chip|workflow-chip/,
                      'no control shares the prompt row');
  assert.match(line[0], /id="input"/);

  const p = writing();
  assert.equal(p.run("document.getElementById('composer-task').hidden"), false,
               'the task row is shown while a skill is selected');
});

test('the task row disappears when nothing configures the request', () => {
  const p = writing();
  p.run("skillByChat.delete('chat-1'); renderSkill();");
  assert.equal(p.run("document.getElementById('composer-task').hidden"), true,
               'an empty configuration row would leave a band above the prompt');
});

test('the attachment-order line is guidance, not a warning', () => {
  const p = writing();
  p.run(`document.getElementById('workflow-select').value = '${APPROVAL}';
         document.getElementById('workflow-select').dispatch('change');`);
  // The class is declared in the markup, so it is asserted there — the
  // harness's document does not parse index.html. `skill-status` is the
  // caution tier and belongs to an unavailable capability; nothing has gone
  // wrong here, so the guidance must not wear it.
  assert.match(chatHtml, /class="composer-hint" id="workflow-hint"/);
  assert.doesNotMatch(chatHtml, /class="skill-status" id="workflow-hint"/);
  assert.doesNotMatch(
    p.run("document.getElementById('workflow-hint').textContent"),
    /must|error|invalid|required/i,
    'it explains how files are read; it does not report a failure');
});

test('the workflow control is described by its own guidance', () => {
  // Read with the select rather than only reachable by scanning the page.
  // When the guidance is hidden — the general workflow — assistive tech
  // ignores the hidden target, so nothing extra is announced.
  assert.match(chatHtml,
               /id="workflow-select"[\s\S]{0,80}aria-describedby="workflow-hint"/);
  assert.match(chatHtml, /<label class="workflow-label" for="workflow-select"/);
});

test('the guidance is absent for the general workflow', () => {
  const p = writing();
  assert.equal(p.run("document.getElementById('workflow-hint').hidden"), true);
  assert.equal(p.run("document.getElementById('workflow-hint').textContent"), '');
});

test('the task row survives attachments being added and removed', () => {
  const p = writing();
  p.run(`document.getElementById('workflow-select').value = '${APPROVAL}';
         document.getElementById('workflow-select').dispatch('change');
         chooseReuse({attachment_id:'11111111-1111-1111-1111-111111111111',
                      filename:'scan.png'});
         chooseReuse({attachment_id:'22222222-2222-2222-2222-222222222222',
                      filename:'sop.txt'});
         renderSkill();`);
  assert.equal(p.run("document.getElementById('composer-task').hidden"), false);
  assert.equal(p.run('docWorkflow'), APPROVAL);
  assert.equal(p.run("(reusedByChat.get('chat-1') || []).length"), 2,
               'both attachments are held');
});

test('sending still works unchanged from the new layout', async () => {
  const p = writing();
  p.run(`document.getElementById('workflow-select').value = '${APPROVAL}';
         document.getElementById('workflow-select').dispatch('change');`);
  const sending = p.run("send('Draft the approval note')");
  await tick();
  assert.equal(p.requests[0].body.doc_workflow, APPROVAL);
  assert.equal(p.requests[0].body.text, 'Draft the approval note');
  p.requests.shift().reply({ job_id: 'job-1' }); await sending;
});

test('the context indicator opens its details and Escape closes them', async () => {
  const p = page();
  await estimate(p, OK_ESTIMATE);
  p.run('openContextPopover()');
  const meter = p.document.getElementById('context-meter');
  assert.equal(meter.getAttribute('aria-expanded'), 'true');
  assert.ok(p.run('contextPopover !== null'));
  p.run('closeContextPopover(true)');
  assert.equal(meter.getAttribute('aria-expanded'), 'false');
  assert.ok(p.run('contextPopover === null'));
  // The page wires the meter to open them, and typing to refresh the estimate.
  assert.match(source, /meter\.addEventListener\('click'[\s\S]*?openContextPopover\(\)/);
  assert.match(source, /saveDraftSoon\(\);\s*\/\/[^\n]*\n\s*refreshContextSoon\(\);/);
  assert.match(source, /e\.key === 'Escape' && contextPopover\) closeContextPopover\(true\)/);
});
