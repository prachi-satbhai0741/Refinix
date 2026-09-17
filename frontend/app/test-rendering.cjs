/* Offline regressions for the conversation pane. Run: node --test this-file
 *
 * The failure this protects against: the pane went blank while both
 * conversations were still listed and the job read `completed / stop / 248
 * output tokens / limit 2048`. The old openChat() cleared the live thread
 * BEFORE rendering, so any throw after the clear — a formatter defect, a
 * malformed optional field — left an empty pane behind a perfectly good
 * conversation. Comparing only chatId also could not tell two concurrent
 * loads of the same chat apart.
 *
 * Every message here is synthetic. Nothing reads the requester's saved text.
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');

const source = readFileSync(`${__dirname}/app.js`, 'utf8').replace(/^import .*$/m, '');
const tick = () => new Promise(setImmediate);

/* A DOM small enough to read and real enough to show the defect: nodes have
 * children, and replaceChildren actually replaces them. */
function makeDocument() {
  const created = [];
  const node = (tag = 'div') => {
    const el = {
      tag, children: [], dataset: {}, classList: { add() {}, remove() {} },
      style: {}, hidden: false, _text: '',
      set textContent(v) { this._text = String(v); this.children = []; },
      get textContent() {
        return this._text + this.children.map((c) => c.textContent).join('');
      },
      // replaceChildren(fragment) inserts the fragment's children, exactly
      // as a real DOM does; that is the whole point of the commit step.
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
    created.push(el);
    return el;
  };
  const fragment = () => {
    const f = node('#fragment');
    f.isFragment = true;
    return f;
  };
  const byId = new Map();
  return {
    node, fragment, byId, created,
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

function page({ markdown } = {}) {
  const document = makeDocument();
  const requests = [];
  const notices = [];
  const scope = vm.createContext({
    document,
    window: {
      addEventListener() {},
      location: { port: '8770' },
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
      reply(body = {}, ok = true) { resolve({ ok, json: async () => body }); },
      fail(message) { reject(new Error(message)); },
    })),
    setTimeout: (fn) => { scope.timer = fn; return 1; },
    clearTimeout() {}, setInterval() { return 1; },
    console: { error() {}, log() {}, warn() {} },
    notices,
  });
  vm.runInContext(source, scope);
  // Replace only what this file is not testing.
  vm.runInContext(`
    notice = (...a) => notices.push(a);
    renderMarkdown = (box, text) => { box.textContent = text; };
    renderLife = () => {}; setJobChip = () => {}; setActive = () => {};
    loadChats = async () => {}; loadDraft = () => {}; loadStaged = () => {};
    saveDraftSoon = () => {}; renderSkill = () => {}; publishSlot = () => {};
    refreshAttempt = () => {}; replayEvents = () => {}; pushEvent = () => {};
    maybeFollow = () => {};
  `, scope);
  if (markdown) vm.runInContext(`renderMarkdown = ${markdown};`, scope);
  const run = (code) => vm.runInContext(code, scope);
  const threadText = () => document.getElementById('thread').textContent;
  const threadCount = () => document.getElementById('thread').children.length;
  return { run, requests, notices, document, threadText, threadCount, scope };
}

const MESSAGES = [
  { role: 'user', text: 'first question', message_id: 'm1', job_id: 'j1' },
  { role: 'assistant', text: 'first answer', message_id: 'm2', job_id: 'j1' },
];

/* The job in the screenshot: finished normally, well under the reply limit. */
const COMPLETED_JOB = {
  job_id: 'j1', state: 'completed', created_at: '2026-09-05T10:00:00Z',
  original_request: 'first question',
};

/* Answer every follow-up read so an invocation can finish. The follow-ups are
 * the technical rail; the assertions are about the conversation. */
async function drain(p, rounds = 4) {
  for (let i = 0; i < rounds; i += 1) {
    while (p.requests.length) {
      p.requests.shift().reply({ jobs: [], events: [], attempts: [], messages: [] });
    }
    await tick();
  }
}

async function openWith(p, { messages = MESSAGES, jobs = [COMPLETED_JOB] } = {}) {
  const opening = p.run("openChat('chat-1')");
  await tick();
  p.requests.shift().reply({ messages });
  await tick();
  if (p.requests.length) p.requests.shift().reply({ jobs });
  await tick();
  if (p.requests.length) p.requests.shift().reply({ events: [], attempts: [], job: COMPLETED_JOB });
  await tick();
  await opening;
}

test('a normal completed job under the reply limit renders both turns', async () => {
  const p = page();
  await openWith(p);
  assert.match(p.threadText(), /first question/);
  assert.match(p.threadText(), /first answer/);
  assert.equal(p.threadCount(), 2);
});

test('a markdown failure costs one message its formatting, not the conversation', async () => {
  const p = page({
    markdown: `(box, text) => {
      if (text === 'first answer') throw new Error('formatter defect');
      box.textContent = text;
    }`,
  });
  await openWith(p);
  const text = p.threadText();
  assert.match(text, /first question/);
  assert.match(text, /first answer/, 'the literal text survives');
  assert.match(text, /Formatting unavailable/);
  assert.equal(p.threadCount(), 2);
});

test('a later message still renders after an earlier one fails to format', async () => {
  const p = page({
    markdown: `(box, text) => {
      if (text === 'first answer') throw new Error('boom');
      box.textContent = text;
    }`,
  });
  await openWith(p, {
    messages: [...MESSAGES,
      { role: 'user', text: 'second question', message_id: 'm3' },
      { role: 'assistant', text: 'second answer', message_id: 'm4' }],
  });
  assert.match(p.threadText(), /second answer/);
  assert.equal(p.threadCount(), 4);
});

test('malformed optional fields cannot blank an otherwise valid message', async () => {
  const p = page();
  await openWith(p, {
    messages: [
      { role: 'user', text: 'kept', message_id: 'm1', error_json: '{not json' },
      { role: 'assistant', text: 'also kept', message_id: 'm2',
        error_json: '{"message":42}', attachments: 'not-an-array' },
    ],
  });
  assert.match(p.threadText(), /kept/);
  assert.match(p.threadText(), /also kept/);
  assert.equal(p.threadCount(), 2);
});

test('a well-formed error note is still shown', async () => {
  const p = page();
  await openWith(p, {
    messages: [{ role: 'assistant', text: 'partial', message_id: 'm1',
                 error_json: '{"message":"Incomplete reply"}' }],
  });
  assert.match(p.threadText(), /Incomplete reply/);
});

test('a failed message refresh keeps the rendered conversation and warns', async () => {
  const p = page();
  await openWith(p);
  const before = p.threadText();

  const again = p.run("openChat('chat-1')");
  await tick();
  p.requests.shift().fail('network down');
  await tick();
  await again;

  assert.equal(p.threadText(), before, 'the previous pane is still there');
  assert.equal(p.notices.length, 1);
  assert.match(p.notices[0][0], /Could not refresh/);
});

test('two overlapping loads of the SAME chat commit only the newer one', async () => {
  const p = page();
  const first = p.run("openChat('chat-1')");
  await tick();
  const second = p.run("openChat('chat-1')");
  await tick();

  const [reqA, reqB] = p.requests.splice(0, 2);
  // The newer invocation answers first, the older one answers last.
  reqB.reply({ messages: [{ role: 'assistant', text: 'NEWER', message_id: 'b' }] });
  await tick();
  reqA.reply({ messages: [{ role: 'assistant', text: 'OLDER', message_id: 'a' }] });
  await tick();
  await drain(p);
  await Promise.all([first, second]);

  assert.match(p.threadText(), /NEWER/);
  assert.doesNotMatch(p.threadText(), /OLDER/);
});

test('two overlapping loads of different chats cannot cross-render', async () => {
  const p = page();
  const first = p.run("openChat('chat-1')");
  await tick();
  const second = p.run("openChat('chat-2')");
  await tick();

  const [reqA, reqB] = p.requests.splice(0, 2);
  reqB.reply({ messages: [{ role: 'assistant', text: 'CHAT TWO', message_id: 'b' }] });
  await tick();
  reqA.reply({ messages: [{ role: 'assistant', text: 'CHAT ONE', message_id: 'a' }] });
  await tick();
  await drain(p);
  await Promise.all([first, second]);

  assert.match(p.threadText(), /CHAT TWO/);
  assert.doesNotMatch(p.threadText(), /CHAT ONE/);
  assert.equal(p.run('chatId'), 'chat-2');
});

test('a job-history failure leaves the fetched messages visible', async () => {
  const p = page();
  const opening = p.run("openChat('chat-1')");
  await tick();
  p.requests.shift().reply({ messages: MESSAGES });
  await tick();
  p.requests.shift().fail('jobs unavailable');
  await tick();
  await opening;

  assert.match(p.threadText(), /first answer/);
  assert.equal(p.threadCount(), 2);
});

test('a job-detail failure leaves the fetched messages visible', async () => {
  const p = page();
  const opening = p.run("openChat('chat-1')");
  await tick();
  p.requests.shift().reply({ messages: MESSAGES });
  await tick();
  p.requests.shift().reply({ jobs: [COMPLETED_JOB] });
  await tick();
  p.requests.shift().fail('detail unavailable');
  await tick();
  await opening;

  assert.match(p.threadText(), /first answer/);
});

test('reopening the same chat repeatedly keeps every message and adds no duplicate', async () => {
  const p = page();
  for (let i = 0; i < 4; i += 1) {
    await openWith(p);
    assert.equal(p.threadCount(), 2, `pass ${i} rendered ${p.threadCount()} turns`);
    assert.match(p.threadText(), /first answer/);
  }
});

test('a genuinely empty chat shows its explicit empty state', async () => {
  const p = page();
  await openWith(p, { messages: [], jobs: [] });
  assert.match(p.threadText(), /No messages in this conversation yet/);
});

test('the repair sends no write to the message store', async () => {
  const p = page();
  const opening = p.run("openChat('chat-1')");
  await tick();
  p.requests.shift().reply({ messages: MESSAGES });
  await tick();
  while (p.requests.length) p.requests.shift().reply({ jobs: [] });
  await tick();
  await opening;
  // Every request this path made was a read.
  const writes = p.requests.filter((r) => r.options && r.options.method === 'POST');
  assert.equal(writes.length, 0);
});

test('artifact cards ignore user rows while preserving uploaded attachments', () => {
  const p = page();
  p.run(`turn('user', 'upload', [{filename:'scan.txt',byte_size:10}], false,
              $('thread'), null, [{filename:'generated.docx',byte_size:10,validation:{paragraphs:1}}]);`);
  const nodes = p.document.created;
  assert.equal(nodes.filter(n => n.className === 'artifact').length, 0);
  assert.equal(nodes.filter(n => n.className === 'attachment').length, 1);
});

test('markdown preserves starts, continuation paragraphs, nesting, mixed lists and restarts', () => {
  const document = makeDocument();
  const scope = vm.createContext({ document, navigator:{}, URL, setTimeout(){} });
  // These two properties are native DOM features used by the renderer.
  const create = document.createElement;
  document.createElement = tag => {
    const el = create(tag);
    Object.defineProperty(el, 'lastElementChild', {get(){ return this.children.at(-1); }});
    el.attributes = {};
    el.setAttribute = (k,v) => { el.attributes[k] = String(v); };
    return el;
  };
  vm.runInContext(readFileSync(`${__dirname}/markdown.js`, 'utf8').replace('export function', 'function'), scope);
  const root = document.createElement('div'); scope.root = root;
  scope.input = '3. third\n\n   continued paragraph\n\n4. fourth\n  - nested\n  7. nested ordered\n\n1. deliberate restart\n- mixed\n\n<script>inert</script>';
  vm.runInContext('renderMarkdown(root, input)', scope);
  const all = el => [el, ...el.children.filter(c => typeof c !== 'string').flatMap(all)];
  const nodes = all(root);
  assert.equal(nodes.filter(n => n.tag === 'ol')[0].attributes.start, '3');
  assert.ok(nodes.some(n => n.tag === 'ol' && n.attributes.start === '7'));
  assert.ok(nodes.some(n => n.tag === 'p' && n.children.includes('continued paragraph')));
  assert.equal(nodes.filter(n => n.tag === 'script').length, 0);
  assert.ok(nodes.some(n => n.children.includes('<script>inert</script>')));
  assert.equal(root.children.filter(n => n.tag === 'ol').length, 2);
  assert.equal(root.children.at(-2).tag, 'ul');
});
