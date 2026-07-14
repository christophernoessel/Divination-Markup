/* Divmarkup workbench — client logic.
 *
 * Structure:
 *   1. State & helpers        S, $, api(), toast()
 *   2. Progress strip         canvas density rendering + navigation
 *   3. Sentence rendering     context, current sentence, status, committed panel
 *   4. Typed find             the slice-notation heir: buffer → matches → runs
 *   5. Mode bar               phase computation + the "where am I" band
 *   6. Senses pane            word groups, chips, suggestions
 *   7. Actions                navigation, selection, commit, undo, write, Claude
 *   8. Keyboard               one dispatcher; lowercase types, Shift commands
 *   9. Boot
 *
 * Phase model: 'select' (no span yet, text remains) → 'senses' (span set) →
 * commit; 'browse' everywhere there's nothing to annotate. The server is the
 * source of truth for sentence text and synset sessions; this file only holds
 * view state.
 */
'use strict';

/* ================================================= 1. state & helpers */
const S = {
  // document
  total: 0, statuses: '', index: 0,
  // current sentence (server-fed)
  unmarked: '', segments: [], marked: [], meaningful: false,
  // selection
  sel: null,          // {start,end} into unmarked — confirmed span
  editing: null,      // {nth, text} — a committed span whose senses are being edited
  ghost: null,        // {start,end} — Claude suggestion awaiting Tab
  // typed find
  buf: '', matches: [], activeMatch: 0, bufError: '',
  // senses
  kind: 'prognosis',  // what the next commit is reviewed as; g/c set gnome/counsel
  senses: [],         // [{word, senses:[{id,definition,selected}]}]
  numbered: [],       // flat list backing the 1–9 keys
  // misc
  policies: [], canons: [],   // from the document's annotation_policy block
  claudeOn: localStorage.getItem('divmarkup_claude') === '1',
  claudeAvailable: false,
  canUndo: false,
  busy: false,
};

const $ = id => document.getElementById(id);

const api = async (path, body) => {
  const r = await fetch(path, body === undefined ? {} : {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
};

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}

let toastTimer;
function toast(msg, kind) {
  const t = $('toast');
  t.textContent = msg || '';
  t.className = kind || '';
  t.style.opacity = 1;
  clearTimeout(toastTimer);
  if (msg) toastTimer = setTimeout(() => { t.style.opacity = 0; }, 4200);
}

function effectiveStatus() { return S.statuses[S.index] || 't'; }

function setStatusChar(i, c) {
  S.statuses = S.statuses.slice(0, i) + c + S.statuses.slice(i + 1);
}

/* ================================================= 2. progress strip */
const strip = $('strip');
const sctx = strip.getContext('2d');
const STRIP_COLORS = {t: '#d4d2c9', d: '#3a3d44', p: '#b5382d', m: '#e7e6df', e: '#e7e6df'};
const STRIP_HEIGHTS = {t: 24, d: 18, p: 24, m: 8, e: 8};

function drawStrip() {
  const w = strip.clientWidth;
  strip.width = w * devicePixelRatio;
  sctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  sctx.clearRect(0, 0, w, 34);
  if (!S.total) return;
  const per = S.total / w;
  for (let x = 0; x < w; x++) {
    // most urgent status in this pixel's bucket: partial > todo > done > meta
    const a = Math.floor(x * per), b = Math.max(a + 1, Math.floor((x + 1) * per));
    let best = 'm';
    for (let i = a; i < b && i < S.total; i++) {
      const c = S.statuses[i];
      if (c === 'p') { best = 'p'; break; }
      if (c === 't') best = 't';
      else if (c === 'd' && best !== 't') best = 'd';
    }
    sctx.fillStyle = STRIP_COLORS[best];
    const h = STRIP_HEIGHTS[best];
    sctx.fillRect(x, 34 - h - 4, 1, h);
  }
  sctx.fillStyle = STRIP_COLORS.p;                       // current-position tick
  sctx.fillRect(Math.floor(S.index / per), 0, 2, 34);
}

strip.addEventListener('click', e => {
  const frac = e.offsetX / strip.clientWidth;
  goTo(Math.min(S.total - 1, Math.max(0, Math.floor(frac * S.total))));
});
strip.addEventListener('mousemove', e => {
  $('strip-label').textContent =
    `→ sentence ${Math.floor(e.offsetX / strip.clientWidth * S.total)}`;
});
strip.addEventListener('mouseleave', () => { $('strip-label').textContent = ''; });
addEventListener('resize', drawStrip);

/* ================================================= 3. sentence rendering */
function renderContext(container, items) {
  container.replaceChildren();
  for (const c of items) {
    const isMeta = !c.parse && !c.segments.some(g => g.kind === 'marked');
    const p = el('p', 'ctx' + (isMeta ? ' meta' : ''));
    for (const g of c.segments) {
      p.appendChild(g.kind === 'marked'
        ? Object.assign(el('span', 'mark', g.text), {title: g.synsets.join(', ')})
        : el('span', '', g.text));
    }
    p.title = `Go to sentence ${c.index}`;
    p.addEventListener('click', () => goTo(c.index));
    container.appendChild(p);
  }
}

function renderCurrent() {
  renderMode();
  const cur = $('current');
  cur.replaceChildren();

  const status = effectiveStatus();
  if (status === 'm' || status === 'e') {
    cur.appendChild(el('div', 'meta-current',
      S.segments.map(g => g.text).join('') || '(empty line)'));
    $('sentence-hint').textContent =
      'Structural line — nothing to annotate. → for the next sentence, ⇧K for the next unmarked one.';
    renderChips([]);
    return;
  }

  // everything through the last marked span is locked; the tail is live
  let lastMarked = -1;
  S.segments.forEach((g, i) => { if (g.kind === 'marked') lastMarked = i; });
  let markIndex = 0;
  S.segments.forEach((g, i) => {
    if (g.kind === 'marked') {
      cur.appendChild(markedSpan(g, markIndex++));
    } else if (i > lastMarked) {
      cur.appendChild(liveSpan(g.text));
    } else {
      cur.appendChild(el('span', 'locked-plain', g.text));
    }
  });
  if (!S.segments.length) cur.appendChild(liveSpan(S.unmarked));
  updateHint();
}

function markedSpan(segment, which) {
  const m = el('span', 'mark' + (S.editing && S.editing.nth === which ? ' editing' : ''), segment.text);
  m.dataset.count = segment.synsets.length;
  m.title = segment.synsets.join(', ');
  m.style.cursor = 'pointer';
  m.addEventListener('click', () => {         // jump to its Committed entry
    const d = document.querySelectorAll('#committed details')[which];
    if (d) { d.open = true; d.scrollIntoView({block: 'nearest'}); }
  });
  return m;
}

function liveSpan(text) {
  const live = el('span', 'live');
  live.id = 'live';
  const r = S.sel || S.ghost;
  if (r) {
    live.appendChild(el('span', '', text.slice(0, r.start)));
    live.appendChild(el('span', S.sel ? 'sel' : 'ghost', text.slice(r.start, r.end)));
    live.appendChild(el('span', '', text.slice(r.end)));
    return live;
  }
  if (!S.buf) { live.textContent = text; return live; }
  if (!S.matches.length) {                     // nothing matches → red wash
    live.appendChild(el('span', 'nomatch', text));
    return live;
  }
  // flatten possibly-overlapping match intervals into runs; depth shades stacks
  const cuts = new Set([0, text.length]);
  for (const [a, b] of S.matches) { cuts.add(a); cuts.add(b); }
  const pts = [...cuts].sort((x, y) => x - y);
  const act = S.matches[S.activeMatch];
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i], b = pts[i + 1];
    const depth = S.matches.filter(([s, e]) => s <= a && b <= e).length;
    const inAct = act && act[0] <= a && b <= act[1];
    const cls = inAct ? (depth > 1 ? 'hl2 hlact' : 'hlact')
              : depth > 1 ? 'hl2' : depth === 1 ? 'hl' : '';
    live.appendChild(el('span', cls, text.slice(a, b)));
  }
  return live;
}

function updateHint() {
  const h = $('sentence-hint');
  h.replaceChildren();
  if (S.buf) {
    const n = S.matches.length;
    const state = (S.bufError || n === 0) ? 'f-bad' : n === 1 ? 'f-ok' : 'f-multi';
    h.appendChild(el('span', 'find ' + state, '⌕ ' + S.buf));
    h.append('  —  ');
    if (S.bufError) h.appendChild(el('span', 'f-bad', S.bufError));
    else if (n === 0) h.appendChild(el('span', 'f-bad', 'no match'));
    else if (n === 1) h.appendChild(el('span', 'f-ok', '1 match · Enter selects'));
    else h.appendChild(el('span', 'f-multi',
      `${n} matches · Tab cycles (${S.activeMatch + 1}/${n}) · Enter selects green`));
    h.append('  ·  Esc clears');
    return;
  }
  if (S.ghost) {
    h.append('Claude suggests the highlighted span — ');
    h.appendChild(el('span', 'accept', 'Tab to accept'));
    h.append(', Esc to dismiss, or drag your own.');
  } else if (S.sel) {
    h.textContent = 'Span set. Pick senses on the right, then Enter to commit. Esc reselects.';
  } else if (S.meaningful) {
    h.textContent = effectiveStatus() === 'p'
      ? 'This sentence has unmarked text remaining — type or drag to select the next span.'
      : 'Type to find the apodosis, or drag across the text.';
  } else {
    h.textContent = 'Fully marked. → to browse, ⇧K for the next unmarked sentence.';
  }
}

function renderStatus() {
  const st = $('sent-status');
  st.replaceChildren();
  const status = effectiveStatus();
  if (!S.marked.length) {
    if (status === 't') st.textContent = '○ unmarked';
    return;
  }
  const nSenses = S.marked.reduce((a, m) => a + m.synsets.length, 0);
  const sp = S.marked.length;
  const chip = el('span', status === 'd' ? 'done' : '');
  chip.textContent = (status === 'd' ? '● fully marked' : '◐ partially marked')
    + ` · ${sp} span${sp === 1 ? '' : 's'} · ${nSenses} sense${nSenses === 1 ? '' : 's'}`;
  st.appendChild(chip);
}

function renderCommitted() {
  const box = $('committed');
  const wasOpen = [...box.querySelectorAll('details')].map(d => d.open);
  box.replaceChildren();
  if (!S.marked.length) return;
  box.appendChild(el('h3', '', 'Committed in this sentence'));
  S.marked.forEach((m, nth) => {
    const d = el('details');
    if (wasOpen[nth]) d.open = true;
    const sum = el('summary');
    sum.append('“' + (m.text.length > 60 ? m.text.slice(0, 58) + '…' : m.text) + '” ');
    sum.appendChild(el('span', 'cnt', '· ' + m.synsets.length));
    d.appendChild(sum);
    const kindRow = el('div', 'kind-row');
    kindRow.appendChild(el('span', 'kind-label',
      m.span_kind ? 'kind: ' + m.span_kind : 'kind: — unreviewed'));
    const edit = el('button', 'kind-btn', 'edit senses');
    edit.title = 'Load this span’s senses into the panel for editing';
    edit.addEventListener('click', () => startEdit(nth));
    kindRow.appendChild(edit);
    for (const k of ['prognosis', 'gnome', 'counsel']) {
      const btn = el('button', 'kind-btn' + (m.span_kind === k ? ' active' : ''), k);
      btn.title = `Review this span as ${k}`;
      btn.addEventListener('click', async () => {
        try {
          const r = await api('/api/set_kind', {index: S.index, span: nth, kind: k});
          S.canUndo = true;
          applySentence(r);
          renderCurrent(); renderStatus(); renderCommitted();
          toast(`Span reviewed as ${k}.`, 'ok');
        } catch (e) { toast(e.message, 'err'); }
      });
      kindRow.appendChild(btn);
    }
    d.appendChild(kindRow);
    for (const s of m.synsets) {
      const row = el('div', 'csense');
      row.appendChild(el('span', 'sid', s.id));
      row.appendChild(el('span', 'def', s.definition));
      d.appendChild(row);
    }
    box.appendChild(d);
  });
}

/* ================================================= 4. typed find */
function computeMatches() {
  const text = S.unmarked, T = text.toLowerCase();
  S.matches = [];
  S.bufError = '';
  if (!S.buf) return;

  const findAll = q => {
    const out = [], Q = q.toLowerCase();
    let i = T.indexOf(Q);
    while (i !== -1) { out.push(i); i = T.indexOf(Q, i + 1); }
    return out;
  };

  const parts = S.buf.split(':');
  if (parts.length > 2) { S.bufError = 'one colon only'; return; }

  if (parts.length === 1) {
    S.matches = findAll(S.buf).map(i => [i, i + S.buf.length]);
  } else {
    // 'a:b' spans a start-match through the END of a b-match; 'a:' runs to the
    // end of the text, ':b' from its beginning — slice_string_per_content's heir
    const [a, b] = parts;
    if (!a && !b) return;                      // bare ':' so far — neutral
    const starts = a ? findAll(a) : [0];
    const ends = b ? findAll(b) : null;
    const seen = new Set();
    const push = (s, e) => {
      const k = s + ':' + e;
      if (!seen.has(k)) { seen.add(k); S.matches.push([s, e]); }
    };
    for (const s of starts) {
      if (ends === null) { if (s < text.length) push(s, text.length); }
      else for (const e of ends) if (s < e) push(s, e + b.length);
    }
  }
  if (S.activeMatch >= S.matches.length) S.activeMatch = 0;
}

function setBuf(v) {
  S.buf = v;
  S.activeMatch = 0;
  computeMatches();
  renderCurrent();
}

/* ================================================= 5. mode bar */
function currentPhase() {
  if (S.sel || S.editing) return 'senses';
  if (S.meaningful && 'tp'.includes(effectiveStatus())) return 'select';
  return 'browse';
}

function renderMode() {
  const phase = currentPhase();
  document.body.dataset.phase = phase;
  const step = $('mode-step'), what = $('mode-what'), next = $('mode-next');

  if (phase === 'select') {
    step.textContent = '① SELECT SPAN';
    if (S.ghost) {
      what.textContent = 'Claude’s suggestion is outlined in the sentence.';
      next.textContent = 'Tab accepts · Esc dismisses · or drag/type your own';
    } else if (effectiveStatus() === 'p') {
      what.textContent = 'This sentence still has unmarked text — select the next span.';
      next.textContent = 'type to find · drag to select';
    } else {
      what.textContent = 'Find the apodosis in the sentence.';
      next.textContent = 'type to find · drag to select';
    }
  } else if (phase === 'senses') {
    const n = S.numbered.filter(s => s.selected).length;
    const span = activeSpanText() || '';
    step.textContent = S.editing ? '② EDIT SENSES' : '② CHOOSE SENSES';
    what.textContent = (S.editing ? 'of committed ' : '') + '“'
      + span.slice(0, 48) + (span.length > 48 ? '…' : '') + '”';
    const flag = S.kind === 'gnome' ? ' as GNOME ⚑'
               : S.kind === 'counsel' ? ' as COUNSEL ☞' : '';
    next.textContent = S.editing
      ? `${n} selected · Enter saves · Esc cancels`
      : n === 0
      ? `no senses selected yet — add a word or tap a chip${flag ? ' ·' + flag : ''}`
      : `${n} selected · Enter commits${flag} · g/c set kind · Esc reselects`;
  } else {
    const st = effectiveStatus();
    step.textContent = '· BROWSING';
    what.textContent = st === 'd' ? 'This sentence is fully marked.'
      : st === 'm' ? 'Structural line — nothing to annotate.'
      : 'Nothing to annotate here.';
    next.textContent = '⇧K next unmarked · ⇧P next partial · ←→ browse';
  }
}

/* ================================================= 6. senses pane */
const STOPWORDS = new Set(('the and but such very that this which with will would there their them '
  + 'they are was were been from for not one all any his her its our your out into upon when '
  + 'what who whom whose then than thus also may might must can could shall should does did '
  + 'has have had here where these those over under above below about after before while '
  + 'more most much many some each other only same own too now you she him men man himself '
  + 'itself oneself because through against between therefore however').split(' '));

function renderChips(words) {
  const c = $('chips');
  c.replaceChildren();
  for (const w of words) {
    const chip = el('button', 'chip', '+ ' + w);
    chip.addEventListener('click', () => addWord(w));
    c.appendChild(chip);
  }
}

function chipsForText(text) {
  return [...new Set(
    (text.toLowerCase().match(/[a-z][a-z-]{2,}/g) || [])
      .filter(w => !STOPWORDS.has(w))
  )];
}

function activeSpanText() {
  if (S.sel) return S.unmarked.slice(S.sel.start, S.sel.end);
  if (S.editing) return S.editing.text;
  return null;
}

function renderSenses() {
  const list = $('senses-list');
  list.replaceChildren();
  S.numbered = [];

  if (!S.senses.length) {
    list.appendChild(el('div', 'empty-note', S.sel
      ? 'No senses yet. Tap a word chip on the left, type a word below, or press ⇧C for Claude’s suggestions.'
      : 'Select a span first — senses attach to the span you commit.'));
  }

  let n = 0;
  for (const w of S.senses) {
    const g = el('div', 'word-group');
    const head = el('div', 'word-head');
    head.appendChild(el('span', 'w', w.word));
    const syn = el('button', '', 'synonyms');
    syn.title = 'List noun synonyms you can add';
    syn.addEventListener('click', () => showSynonyms(w.word));
    const del = el('button', '', '✕');
    del.title = 'Remove word and its senses';
    del.addEventListener('click', () => delWord(w.word));
    head.append(syn, del);
    g.appendChild(head);

    for (const s of w.senses) {
      n++;
      S.numbered.push(s);
      const row = el('div', 'sense' + (s.selected ? ' on' : ''));
      row.appendChild(el('span', 'num', n <= 9 ? String(n) : ''));
      row.appendChild(el('span', 'dot'));
      const txt = el('span');
      txt.appendChild(el('span', 'sid', s.id + '  '));
      txt.appendChild(el('span', 'def', s.definition));
      row.appendChild(txt);
      row.addEventListener('click', () => toggleSense(s.id, !s.selected));
      g.appendChild(row);
    }
    list.appendChild(g);
  }

  $('commit-btn').disabled = !((S.sel || S.editing) && S.numbered.some(s => s.selected));
  $('commit-btn').textContent = S.editing ? 'Save' : 'Commit';
  const active = activeSpanText();
  $('span-echo').textContent = active ? '“' + active + '”' : '';
  renderGovernance();
  renderMode();
}

function renderGovernance() {
  const box = $('governance');
  box.replaceChildren();
  const active = activeSpanText();
  if (!active) return;
  const span = active.toLowerCase();
  const norm = span.replace(/[.,;:!?"'\s]+/g, ' ').trim();

  for (const p of S.policies) {
    if (p.applies.some(a => span.includes(a))) {
      const row = el('div', 'gov');
      row.appendChild(el('span', 'gid', '⚖ ' + p.id));
      row.appendChild(el('span', 'gtxt',
        p.text.length > 90 ? p.text.slice(0, 88) + '…' : p.text));
      row.title = p.text;
      box.appendChild(row);
    }
  }
  for (const c of S.canons) {
    if (norm === c.formula) {
      const row = el('button', 'gov canon');
      row.appendChild(el('span', 'gid', '⚖ canon'));
      row.appendChild(el('span', 'gtxt', 'apply ' + c.synsets.join(', ')));
      row.title = 'Canonical mapping for this formula — one tap applies it';
      row.addEventListener('click', async () => {
        const problems = [];
        for (const sid of c.synsets) {
          const r = await api('/api/add_synset', {index: S.index, synset: sid});
          S.senses = r.senses;
          if (r.message) problems.push(r.message);
        }
        renderSenses();
        toast(problems.length
          ? 'Canon problem — check the policy block: ' + problems.join(' · ')
          : 'Canonical senses applied.', problems.length ? 'err' : 'ok');
      });
      box.appendChild(row);
    }
  }
}

function renderSuggestions(fresh) {
  const box = $('suggestions');
  box.replaceChildren();
  for (const s of fresh || []) {
    const row = el('div', 'sugg');
    row.appendChild(el('span', 'sid', '✳ ' + s.id));
    row.appendChild(el('span', 'def', s.definition));
    row.title = 'Add this sense';
    row.addEventListener('click', async () => {
      row.remove();
      const r = await api('/api/add_synset', {index: S.index, synset: s.id});
      S.senses = r.senses;
      renderSenses();
      if (r.message) toast(r.message, 'err');
    });
    box.appendChild(row);
  }
}

/* ================================================= 7. actions */
function applySentence(d) {
  // ingest the common payload shape (fetch / commit / undo all return it)
  S.segments = d.segments;
  S.marked = d.marked || [];
  S.unmarked = d.unmarked;
  S.meaningful = d.meaningful;
  if (d.senses !== undefined) S.senses = d.senses;
  setStatusChar(d.index, d.status);
}

function clearSelectionState() {
  S.sel = null;
  S.editing = null;
  S.ghost = null;
  S.buf = '';
  S.matches = [];
  S.activeMatch = 0;
}

function refreshSentenceUI() {
  renderCurrent();
  renderStatus();
  renderCommitted();
  renderSenses();
  renderSuggestions([]);
  renderChips([]);
  drawStrip();
}

async function goTo(i, keepToast) {
  if (S.busy || i < 0 || i >= S.total) return;
  S.busy = true;
  try {
    const d = await api('/api/sentence/' + i);
    S.index = i;
    applySentence(d);
    clearSelectionState();
    renderContext($('ctx-before'), d.context_before);
    renderContext($('ctx-after'), d.context_after);
    refreshSentenceUI();
    $('pos').textContent = S.index;
    if (!keepToast) toast('');
  } catch (e) { toast(e.message, 'err'); }
  S.busy = false;
}

function nextUnmarked(from) {
  for (let i = from; i < S.total; i++) if ('tp'.includes(S.statuses[i])) return i;
  return -1;
}

function nextPartial() {
  for (let j = 1; j <= S.total; j++) {
    const i = (S.index + j) % S.total;
    if (S.statuses[i] === 'p') return i;
  }
  return -1;
}

function setSelection(start, end, snap = true) {
  // snap outward to word boundaries (mouse only), then trim edge whitespace
  const wordChar = ch => /[A-Za-z0-9'’-]/.test(ch || '');
  if (snap) {
    while (start > 0 && wordChar(S.unmarked[start - 1]) && wordChar(S.unmarked[start])) start--;
    while (end < S.unmarked.length && wordChar(S.unmarked[end]) && wordChar(S.unmarked[end - 1])) end++;
  }
  while (start < end && /\s/.test(S.unmarked[start])) start++;
  while (end > start && /\s/.test(S.unmarked[end - 1])) end--;
  if (end - start < 1) return;

  S.sel = {start, end};
  S.ghost = null;
  S.buf = '';
  S.matches = [];
  S.kind = 'prognosis';
  renderCurrent();
  renderChips(chipsForText(S.unmarked.slice(start, end)));
  renderSenses();
}

function captureDrag() {
  const live = $('live');
  if (!live) return;
  const sel = getSelection();
  if (!sel.rangeCount || sel.isCollapsed) return;
  const range = sel.getRangeAt(0);
  if (!live.contains(range.startContainer) || !live.contains(range.endContainer)) return;
  const offsetIn = (node, off) => {           // node+offset → index in live text
    let total = 0;
    const walker = document.createTreeWalker(live, NodeFilter.SHOW_TEXT);
    let t;
    while ((t = walker.nextNode())) {
      if (t === node) return total + off;
      total += t.textContent.length;
    }
    return total;
  };
  let a = offsetIn(range.startContainer, range.startOffset);
  let b = offsetIn(range.endContainer, range.endOffset);
  if (a > b) [a, b] = [b, a];
  sel.removeAllRanges();
  setSelection(a, b);
}
document.addEventListener('mouseup', () => setTimeout(captureDrag, 0));

async function addWord(w) {
  try {
    const r = await api('/api/word', {index: S.index, word: w});
    S.senses = r.senses;
    renderSenses();
    if (r.message) toast(r.message, r.message.includes('→') ? 'ok' : 'err');
  } catch (e) { toast(e.message, 'err'); }
}

async function delWord(w) {
  const r = await api('/api/word/delete', {index: S.index, word: w});
  S.senses = r.senses;
  renderSenses();
}

async function toggleSense(id, on) {
  const r = await api('/api/toggle', {index: S.index, synset: id, selected: on});
  S.senses = r.senses;
  renderSenses();
}

async function showSynonyms(w) {
  const r = await api('/api/synonyms', {word: w});
  if (!r.synonyms.length) return toast(`No noun synonyms for “${w}”.`);
  renderChips(r.synonyms.map(x => x.replace(/ /g, '_')));
  toast(`Noun synonyms for “${w}” are on the left — tap to add.`, 'ok');
}

async function suggest() {
  if (!S.claudeOn) return toast('Claude assists is off — toggle it in the header first.');
  if (!S.claudeAvailable) return toast('No ANTHROPIC_API_KEY on the server.', 'err');
  try {
    if (!S.sel) {                              // phase ①: span suggestion → ghost
      toast('Asking Claude for the apodosis…');
      const r = await api('/api/claude/apodosis', {index: S.index});
      if (r.error) return toast(r.error, 'err');
      S.ghost = {start: r.start, end: r.end};
      renderCurrent();
      toast('');
    } else {                                   // phase ②: sense suggestions → chips
      toast('Asking Claude for senses…');
      const span = S.unmarked.slice(S.sel.start, S.sel.end);
      const r = await api('/api/claude/synsets', {index: S.index, apodosis: span});
      if (r.error) return toast(r.error, 'err');
      renderSuggestions(r.fresh);
      const bits = [];
      if (r.known.length) bits.push(`${r.known.length} already listed`);
      if (r.invalid.length) bits.push(`${r.invalid.length} invalid (${r.invalid.join(', ')})`);
      toast(r.fresh.length
        ? `✳ ${r.fresh.length} suggestion${r.fresh.length > 1 ? 's' : ''} — tap to add.`
          + (bits.length ? ' ' + bits.join('; ') + '.' : '')
        : 'Nothing new. ' + bits.join('; '), 'ok');
    }
  } catch (e) { toast(e.message, 'err'); }
}

async function startEdit(nth) {
  try {
    const r = await api('/api/edit_span', {index: S.index, span: nth});
    S.sel = null; S.buf = ''; S.matches = []; S.ghost = null;
    S.editing = {nth, text: r.span_text};
    S.senses = r.senses;
    renderCurrent();
    renderChips(chipsForText(r.span_text));
    renderSenses();
    if (r.invalid.length) toast('Not in WordNet, dropped from board: ' + r.invalid.join(', '), 'err');
  } catch (e) { toast(e.message, 'err'); }
}

async function saveEdit() {
  if ($('commit-btn').disabled || S.busy) return;
  S.busy = true;
  try {
    const r = await api('/api/rewrite_senses', {index: S.index, span: S.editing.nth});
    S.canUndo = true;
    applySentence(r);
    clearSelectionState();
    refreshSentenceUI();
    toast('Senses rewritten & autosaved.', 'ok');
  } catch (e) { toast(e.message, 'err'); }
  S.busy = false;
}

async function cancelEdit() {
  try { await api('/api/session/reset', {index: S.index}); } catch (e) {}
  S.editing = null;
  S.senses = [];
  refreshSentenceUI();
}

async function commit() {
  if (S.editing) return saveEdit();
  if (!S.sel || $('commit-btn').disabled || S.busy) return;
  S.busy = true;
  try {
    const r = await api('/api/commit', {index: S.index, start: S.sel.start, end: S.sel.end, kind: S.kind});
    S.canUndo = true;
    applySentence(r);
    clearSelectionState();
    if (r.meaningful) {                        // more text to mark — stay here
      refreshSentenceUI();
      toast('Committed — text remains in this sentence.', 'ok');
    } else {                                   // sentence finished — advance
      const n = nextUnmarked(S.index + 1);
      S.busy = false;
      if (n === -1) {
        await goTo(S.index, true);
        toast('Committed — no unmarked sentences remain. 🎉', 'ok');
      } else {
        await goTo(n, true);
        toast('Committed & autosaved.', 'ok');
      }
      return;
    }
  } catch (e) { toast(e.message, 'err'); }
  S.busy = false;
}

async function undo() {
  try {
    const r = await api('/api/undo', {});
    S.canUndo = r.can_undo;
    S.busy = false;
    await goTo(r.index, true);
    toast('Undid the last commit on sentence ' + r.index + '.', 'ok');
  } catch (e) { toast(e.message, 'err'); }
}

async function writeFile() {
  const r = await api('/api/write', {});
  toast('Wrote ' + r.file, 'ok');
}

/* ================================================= 8. keyboard */
// Lowercase always types into the find buffer during span selection, so
// commands live on Shift: one grammar in every phase. Matching is
// case-insensitive, so nothing is lost to the five reserved capitals.
const COMMANDS = {
  K: () => { const n = nextUnmarked(S.index + 1);
             n !== -1 ? goTo(n) : toast('No unmarked sentences ahead.'); },
  P: () => { const n = nextPartial();
             n !== -1 ? goTo(n) : toast('No partially marked sentences remain.', 'ok'); },
  C: suggest,
  U: undo,
  W: writeFile,
};

document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT') {          // the add-word box owns its keys
    if (e.key === 'Enter') {
      const v = $('addword').value.trim();
      if (v) { addWord(v); $('addword').value = ''; }
      e.preventDefault();
    } else if (e.key === 'Escape') {
      $('addword').blur();
    }
    return;
  }

  if (COMMANDS[e.key]) { COMMANDS[e.key](); return; }

  const selPhase = !S.sel && S.meaningful && 'tp'.includes(effectiveStatus());

  switch (e.key) {
    case 'Enter':
      if (selPhase && S.buf) {
        const m = S.matches[S.activeMatch];
        if (m) setSelection(m[0], m[1], false);        // typed = exact, no snap
        else toast('Nothing matches “' + S.buf + '”.', 'err');
      } else if (S.sel || S.editing) {
        commit();
      }
      e.preventDefault();
      break;

    case 'Tab':
      if (S.ghost) setSelection(S.ghost.start, S.ghost.end);
      else if (selPhase && S.matches.length > 1) {
        S.activeMatch = (S.activeMatch + (e.shiftKey ? S.matches.length - 1 : 1))
          % S.matches.length;
        renderCurrent();
      }
      e.preventDefault();
      break;

    case 'Escape':
      if (S.editing) cancelEdit();
      else if (S.buf) setBuf('');
      else {
        S.sel = null;
        S.ghost = null;
        renderCurrent();
        renderChips([]);
        renderSenses();
      }
      break;

    case 'Backspace':
      if (selPhase && S.buf) { setBuf(S.buf.slice(0, -1)); e.preventDefault(); }
      break;

    case 'ArrowLeft': goTo(S.index - 1); break;
    case 'ArrowRight': goTo(S.index + 1); break;

    default:
      if (selPhase) {                          // printable chars build the find
        if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
          setBuf(S.buf + e.key);
          e.preventDefault();
        }
      } else if ((e.key === 'g' || e.key === 'c') && S.sel) {
        const target = e.key === 'g' ? 'gnome' : 'counsel';
        S.kind = S.kind === target ? 'prognosis' : target;
        renderMode();
      } else if (e.key === '/') {
        $('addword').focus();
        e.preventDefault();
      } else if (/^[1-9]$/.test(e.key)) {
        const s = S.numbered[Number(e.key) - 1];
        if (s) toggleSense(s.id, !s.selected);
      }
  }
});

/* ================================================= 9. boot */
$('commit-btn').addEventListener('click', commit);
$('write-btn').addEventListener('click', writeFile);

const claudeToggle = $('claude-toggle');
claudeToggle.checked = S.claudeOn;
$('claude-toggle-label').classList.toggle('on', S.claudeOn);
claudeToggle.addEventListener('change', () => {
  S.claudeOn = claudeToggle.checked;
  localStorage.setItem('divmarkup_claude', S.claudeOn ? '1' : '0');
  $('claude-toggle-label').classList.toggle('on', S.claudeOn);
});

(async function boot() {
  try {
    const d = await api('/api/state');
    S.total = d.total;
    S.statuses = d.statuses;
    S.claudeAvailable = d.claude_available;
    S.policies = d.policies || [];
    S.canons = d.canons || [];
    $('filename').textContent = d.file;
    $('total').textContent = S.total.toLocaleString();
    drawStrip();
    await goTo(d.resume);
    toast(`Resumed at sentence ${d.resume}. Autosaving to ${d.autosave_file}.`, 'ok');
  } catch (e) {
    toast('Could not reach the server: ' + e.message, 'err');
  }
})();
