/* Offline asynchronous regressions against app.js. Run: node --test this-file */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');
const source = readFileSync(`${__dirname}/app.js`, 'utf8').replace(/^import .*$/m, '');
const tick = () => new Promise(setImmediate);

function page() {
  const nodes = new Map(), requests = [], notices = [];
  const node = (id) => {
    if (!nodes.has(id)) nodes.set(id, { value: '', hidden: false, clears: 0,
      style: {}, scrollHeight: 24,
      replaceChildren() { this.clears++; } });
    return nodes.get(id);
  };
  const scope = vm.createContext({
    document: { getElementById: node },
    window: {
      addEventListener() {},
      /* app.js evaluates matchMedia at module scope: the panel breakpoints and
         the theme's system preference. Answering "no match" gives the wide
         window and the light default, both of which are ordinary states. */
      matchMedia: () => ({ matches: false, addEventListener() {},
                           removeEventListener() {}, addListener() {},
                           removeListener() {} }),
    },
    fetch: (path, options) => new Promise(resolve => requests.push({ path, options,
      reply(body = {}, ok = true) { resolve({ ok, json: async () => body }); } })),
    setTimeout: fn => { scope.timer = fn; return 1; },
    clearTimeout: () => { scope.timer = null; }, notices, console,
  });
  const run = code => vm.runInContext(code, scope);
  run(source);
  run('notice = (...args) => notices.push(args); renderLife = () => {}; turn = () => {};');
  return { run, node, requests, notices, scope };
}

test('late draft A cannot replace newer typing in chat B', async () => {
  const p = page();
  const a = p.run("chatId = 'A'; loadDraft('A')"); await tick();
  const b = p.run("chatId = 'B'; loadDraft('B')"); await tick();
  p.requests[1].reply({ text: 'draft B' }); await b;
  p.node('input').value = 'new B typing'; p.run('++draftVersion');
  p.requests[0].reply({ text: 'old A draft' }); await a;
  assert.equal(p.node('input').value, 'new B typing');
});

test('typing while its own draft loads wins over the saved text', async () => {
  const p = page();
  const loading = p.run("chatId = 'A'; loadDraft('A')"); await tick();
  p.node('input').value = 'new typing'; p.run('++draftVersion; draftReady = true');
  p.requests[0].reply({ text: 'older saved text' }); await loading;
  assert.equal(p.node('input').value, 'new typing');
});

test('draft writes capture chat/text and remain ordered', async () => {
  const p = page();
  p.run("chatId = 'A'; draftReady = true"); p.node('input').value = 'text A';
  const a = p.run('saveDraftSoon(true)'); await tick();
  p.run("chatId = 'B'"); p.node('input').value = 'text B';
  const b = p.run('saveDraftSoon(true)'); await tick();
  assert.equal(p.requests.length, 1);
  assert.deepEqual(JSON.parse(p.requests[0].options.body), { chat_id: 'A', text: 'text A' });
  p.requests[0].reply(); await a; await tick();
  assert.deepEqual(JSON.parse(p.requests[1].options.body), { chat_id: 'B', text: 'text B' });
  p.requests[1].reply(); await b;
});

test('New chat flushes the old draft before restoring the new-chat slot', async () => {
  const p = page();
  p.run("chatId = 'A'; draftReady = true"); p.node('input').value = 'keep A';
  p.run('saveDraftSoon(); newChat()'); await tick();
  // Reading the pending attachment selection also happens here; the ordering
  // this test protects is between the draft save and the draft restore.
  const drafts = () => p.requests.filter((r) => r.path.startsWith('/v1/draft'));
  assert.deepEqual(JSON.parse(drafts()[0].options.body), { chat_id: 'A', text: 'keep A' });
  drafts()[0].reply(); await tick();
  assert.equal(drafts()[1].path, '/v1/draft?chat_id=__new__');
  drafts()[1].reply({ text: 'new-chat draft' }); await tick();
  assert.equal(p.node('input').value, 'new-chat draft');
});

test('delete error keeps the selected chat, job, draft and rendered history', async () => {
  const p = page();
  p.run("chatId = 'A'; activeJob = 'job-A'; confirmDialog = async () => true");
  p.node('input').value = 'unsent';
  const deleting = p.run("deleteChat({ chat_id: 'A', title: 'A' })"); await tick();
  p.requests[0].reply({ error: 'Stop the response first' }, false); await deleting;
  assert.equal(p.run('chatId'), 'A');
  assert.equal(p.run('activeJob'), 'job-A');
  assert.equal(p.node('input').value, 'unsent');
  assert.equal(p.node('thread').clears, 0);
  assert.match(p.notices[0][0], /Could not delete/);
});

test('failed submission preserves the exact draft', async () => {
  const p = page();
  p.run("chatId = 'A'; draftReady = true"); p.node('input').value = '  prompt\n';
  const sending = p.run("send('prompt', { draftText: '  prompt\\n' })");
  const rejected = assert.rejects(sending, /busy/);
  await tick(); p.requests[0].reply(); await tick();
  assert.equal(JSON.parse(p.requests[1].options.body).draft_text, '  prompt\n');
  p.requests[1].reply({ error: 'busy' }, false); await rejected;
  assert.equal(p.node('input').value, '  prompt\n');
});

test('accepted submission never clears newer typing', async () => {
  const p = page();
  p.run("chatId = 'A'; draftReady = true; openChat = async () => {}");
  p.node('input').value = 'sent';
  const sending = p.run("send('sent', { draftText: 'sent' })");
  await tick(); p.requests[0].reply(); await tick();
  p.node('input').value = 'newer typing'; p.run('++draftVersion');
  p.requests[1].reply({ job_id: 'job-A' }); await sending;
  assert.equal(p.node('input').value, 'newer typing');
});

test('new-chat submission clears its original slot and only its accepted text', async () => {
  const p = page();
  p.run('draftReady = true; openChat = async () => {}'); p.node('input').value = 'new';
  const sending = p.run("send('new', { draftText: 'new' })");
  await tick(); p.requests[0].reply(); await tick();
  p.requests[1].reply({ chat_id: 'created' }); await tick();
  const body = JSON.parse(p.requests[2].options.body);
  assert.equal(body.chat_id, 'created'); assert.equal(body.draft_id, '__new__');
  p.requests[2].reply({ job_id: 'job' }); await sending;
  assert.equal(p.run('chatId'), 'created');
  assert.equal(p.node('input').value, '');
});
