/* Markdown renderer for model output.
 *
 * A two-stage tokenizer — blocks, then inline spans — not a pile of regexes
 * over whole documents. Every node is built with createElement/textContent, so
 * `innerHTML` is never used and raw HTML in model output stays inert text.
 *
 * Deliberately excluded: raw HTML, images, reference links, footnotes, HTML
 * entities. Unsupported syntax degrades to literal text rather than guessing.
 *
 * No dependency, no vendored asset, no network.
 */
'use strict';

const SAFE_SCHEME = /^(https?:|mailto:)/i;

/* ---- inline ---------------------------------------------------------- */

/* Ordered by marker length so `**` is tried before `*`. */
const INLINE = [
  { open: '`',   close: '`',   tag: 'code',   raw: true },
  { open: '**',  close: '**',  tag: 'strong' },
  { open: '__',  close: '__',  tag: 'strong' },
  { open: '*',   close: '*',   tag: 'em' },
  { open: '_',   close: '_',   tag: 'em' },
  { open: '~~',  close: '~~',  tag: 'del' },
];

function appendInline(parent, text) {
  let i = 0, plain = '';
  const flush = () => { if (plain) { parent.append(plain); plain = ''; } };

  while (i < text.length) {
    // Link: [label](destination)
    if (text[i] === '[') {
      const close = text.indexOf('](', i);
      if (close !== -1) {
        // Destinations may contain balanced parens, e.g. alert(1) or a
        // Wikipedia URL ending in (disambiguation).
        let end = -1, depth = 0;
        for (let k = close + 2; k < text.length; k += 1) {
          if (text[k] === '(') depth += 1;
          else if (text[k] === ')') { if (depth === 0) { end = k; break; } depth -= 1; }
        }
        if (end !== -1) {
          const label = text.slice(i + 1, close);
          const href = text.slice(close + 2, end).trim();
          flush();
          if (SAFE_SCHEME.test(href)) {
            const a = document.createElement('a');
            a.href = href;
            a.rel = 'noopener noreferrer nofollow';
            a.target = '_blank';
            // Destination is visible, so a link is never a bare claim.
            a.title = href;
            appendInline(a, label);
            const hint = document.createElement('span');
            hint.className = 'link-host';
            try { hint.textContent = ` (${new URL(href).host})`; } catch { hint.textContent = ''; }
            parent.append(a, hint);
          } else {
            // Unsafe or unknown scheme: show it, never make it clickable.
            const span = document.createElement('span');
            span.className = 'link-blocked';
            span.textContent = `${label} [link not shown: ${href.slice(0, 40)}]`;
            parent.append(span);
          }
          i = end + 1;
          continue;
        }
      }
    }

    let matched = false;
    for (const rule of INLINE) {
      if (!text.startsWith(rule.open, i)) continue;
      const from = i + rule.open.length;
      const end = text.indexOf(rule.close, from);
      if (end === -1 || end === from) continue;
      flush();
      const el = document.createElement(rule.tag);
      const inner = text.slice(from, end);
      if (rule.raw) el.textContent = inner; else appendInline(el, inner);
      parent.append(el);
      i = end + rule.close.length;
      matched = true;
      break;
    }
    if (matched) continue;

    plain += text[i];
    i += 1;
  }
  flush();
}

/* ---- blocks ---------------------------------------------------------- */

function codeBlock(language, lines, unterminated) {
  const wrap = document.createElement('div');
  wrap.className = 'code-block';
  const head = document.createElement('div');
  head.className = 'code-head';
  const label = document.createElement('span');
  label.className = 'code-lang';
  label.textContent = language || 'text';
  const copy = document.createElement('button');
  copy.type = 'button';
  copy.className = 'code-copy';
  copy.textContent = 'Copy';
  const source = lines.join('\n');
  copy.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(source);   // literal source, not rendered
      copy.textContent = 'Copied';
    } catch {
      copy.textContent = 'Copy failed';
    }
    setTimeout(() => { copy.textContent = 'Copy'; }, 1500);
  });
  head.append(label, copy);
  const pre = document.createElement('pre');
  const code = document.createElement('code');
  code.textContent = source;
  pre.append(code);
  wrap.append(head, pre);
  if (unterminated) {
    const note = document.createElement('p');
    note.className = 'code-open';
    note.textContent = 'code block still streaming…';
    wrap.append(note);
  }
  return wrap;
}

function table(rows) {
  const el = document.createElement('table');
  const head = document.createElement('thead');
  const hr = document.createElement('tr');
  for (const cell of rows[0]) {
    const th = document.createElement('th');
    appendInline(th, cell);
    hr.append(th);
  }
  head.append(hr);
  const body = document.createElement('tbody');
  for (const row of rows.slice(1)) {
    const tr = document.createElement('tr');
    for (const cell of row) {
      const td = document.createElement('td');
      appendInline(td, cell);
      tr.append(td);
    }
    body.append(tr);
  }
  el.append(head, body);
  const scroll = document.createElement('div');
  scroll.className = 'table-scroll';
  scroll.append(el);
  return scroll;
}

const splitRow = (line) =>
  line.replace(/^\||\|$/g, '').split('|').map((c) => c.trim());

const isDivider = (line) => /^\|?[\s:|-]+\|[\s:|-]*$/.test(line) && line.includes('-');

/* Nested lists are built by indentation depth. */
function buildList(items, start) {
  const depth = items[start].depth;
  const ordered = items[start].ordered;
  const list = document.createElement(ordered ? 'ol' : 'ul');
  let i = start;
  while (i < items.length && items[i].depth >= depth) {
    if (items[i].depth > depth) {
      const [child, next] = buildList(items, i);
      (list.lastElementChild || list).append(child);
      i = next;
      continue;
    }
    const li = document.createElement('li');
    appendInline(li, items[i].text);
    list.append(li);
    i += 1;
  }
  return [list, i];
}

export function renderMarkdown(target, source) {
  target.replaceChildren();
  const lines = String(source ?? '').split('\n');
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) { i += 1; continue; }

    // Fenced code
    const fence = trimmed.match(/^(`{3,}|~{3,})\s*([\w+-]*)/);
    if (fence) {
      const marker = fence[1][0].repeat(3);
      const body = [];
      i += 1;
      let closed = false;
      while (i < lines.length) {
        if (lines[i].trim().startsWith(marker)) { closed = true; i += 1; break; }
        body.push(lines[i]);
        i += 1;
      }
      target.append(codeBlock(fence[2], body, !closed));
      continue;
    }

    // Heading
    const heading = trimmed.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      const level = Math.min(heading[1].length + 1, 6);   // h1 stays the page's
      const h = document.createElement(`h${level}`);
      appendInline(h, heading[2]);
      target.append(h);
      i += 1;
      continue;
    }

    // Horizontal rule
    if (/^(\*{3,}|-{3,}|_{3,})$/.test(trimmed)) {
      target.append(document.createElement('hr'));
      i += 1;
      continue;
    }

    // Table: header row followed by a divider
    if (trimmed.includes('|') && i + 1 < lines.length && isDivider(lines[i + 1].trim())) {
      const rows = [splitRow(trimmed)];
      i += 2;
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) {
        rows.push(splitRow(lines[i].trim()));
        i += 1;
      }
      target.append(table(rows));
      continue;
    }

    // Blockquote
    if (trimmed.startsWith('>')) {
      const quote = document.createElement('blockquote');
      const body = [];
      while (i < lines.length && lines[i].trim().startsWith('>')) {
        body.push(lines[i].trim().replace(/^>\s?/, ''));
        i += 1;
      }
      const para = document.createElement('p');
      appendInline(para, body.join(' '));
      quote.append(para);
      target.append(quote);
      continue;
    }

    // Lists, including nesting by indentation
    const bullet = line.match(/^(\s*)([*+-]|\d+[.)])\s+(.*)$/);
    if (bullet) {
      const items = [];
      while (i < lines.length) {
        const m = lines[i].match(/^(\s*)([*+-]|\d+[.)])\s+(.*)$/);
        if (!m) {
          if (lines[i].trim() === '') { i += 1; break; }
          break;
        }
        items.push({
          depth: Math.floor(m[1].length / 2),
          ordered: /\d/.test(m[2]),
          text: m[3],
        });
        i += 1;
      }
      const [list] = buildList(items, 0);
      target.append(list);
      continue;
    }

    // Paragraph: consume until a blank line or a new block starts
    const para = document.createElement('p');
    const body = [];
    while (i < lines.length && lines[i].trim()
           && !/^(#{1,6}\s|>|\s*([*+-]|\d+[.)])\s)/.test(lines[i])
           && !/^(`{3,}|~{3,})/.test(lines[i].trim())) {
      body.push(lines[i].trim());
      i += 1;
    }
    if (!body.length) { body.push(trimmed); i += 1; }
    appendInline(para, body.join(' '));
    target.append(para);
  }
}
