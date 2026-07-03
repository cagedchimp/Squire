// TTRPG Ruleset Lookup — static webapp main module.
// Pipeline: browser audio -> energy-VAD chunks -> Whisper (worker) ->
// fuzzy match -> rule cards. Everything runs in this tab.
import { RuleMatcher } from './matcher.js';

const $ = id => document.getElementById(id);

// ---------------------------------------------------------------- state
let matcher = null;
let worker = null;
let workerReady = false;
let loadedModel = null;
let audioCtx = null;
let mediaStream = null;
let listening = false;

// ---------------------------------------------------------------- data
let allEntries = [];
let rulesetList = []; // {name, count, imported}

function loadActiveMap() {
  try { return JSON.parse(localStorage.getItem('activeRulesets') || '{}'); }
  catch { return {}; }
}
function isActive(name) {
  return loadActiveMap()[name] !== false; // default: on
}
function setActive(name, on) {
  const map = loadActiveMap();
  map[name] = on;
  localStorage.setItem('activeRulesets', JSON.stringify(map));
}

async function loadData() {
  const res = await fetch('data/rulesets.json');
  const data = await res.json();
  allEntries = data.entries;
  rulesetList = data.rulesets.map(r => ({ name: r.name, count: r.entries, imported: false }));
  // merge imported custom rulesets (e.g. book content) from localStorage
  for (const rs of loadCustomRulesets()) {
    for (const e of rs.entries) e.ruleset = rs.name;
    allEntries = allEntries.concat(rs.entries);
    rulesetList.push({ name: rs.name, count: rs.entries.length, imported: true });
  }
  buildMatcher();
  renderRulesetChips();
}

function buildMatcher() {
  const entries = allEntries.filter(e => isActive(e.ruleset));
  matcher = new RuleMatcher(entries);
  $('datasets').textContent =
    `${entries.length} entries active — click a ruleset in the header to toggle it`;
}

function renderRulesetChips() {
  const el = $('rulesets');
  el.innerHTML = '';
  for (const rs of rulesetList) {
    const on = isActive(rs.name);
    const chip = document.createElement('span');
    chip.className = 'chip' + (on ? ' active' : '');
    chip.title = (on ? 'Disable ' : 'Enable ') + rs.name + ' matches';
    chip.textContent = `${on ? '✓ ' : ''}${rs.name} (${rs.count})`;
    chip.onclick = () => {
      setActive(rs.name, !isActive(rs.name));
      buildMatcher();
      renderRulesetChips();
    };
    el.appendChild(chip);
  }
}

function loadCustomRulesets() {
  try { return JSON.parse(localStorage.getItem('customRulesets') || '[]'); }
  catch { return []; }
}

$('importBtn').onclick = () => $('importFile').click();
$('importFile').addEventListener('change', async (ev) => {
  const custom = loadCustomRulesets();
  for (const file of ev.target.files) {
    try {
      const raw = JSON.parse(await file.text());
      const list = Array.isArray(raw) ? raw : raw.entries;
      const entries = list.map((r, i) => ({
        id: r.id || `${file.name}:${i}:${(r.name || '').toLowerCase()}`,
        name: r.name, category: r.category || 'Rule',
        subtitle: r.subtitle || '', aliases: r.aliases || [],
        meta: r.meta || {}, body: r.body || [],
        source: r.source || file.name.replace(/\.json$/i, ''),
        guarded: !!r.guarded, triggers: r.triggers || [],
      })).filter(e => e.name);
      const name = file.name.replace(/\.json$/i, '');
      const existing = custom.findIndex(c => c.name === name);
      if (existing >= 0) custom[existing] = { name, entries };
      else custom.push({ name, entries });
    } catch (e) {
      alert(`Could not import ${file.name}: ${e.message}`);
    }
  }
  localStorage.setItem('customRulesets', JSON.stringify(custom));
  ev.target.value = '';
  await loadData();
});

// ---------------------------------------------------------------- STT
function ensureWorker(model) {
  if (worker && loadedModel === model) return;
  if (worker) worker.terminate();
  workerReady = false;
  loadedModel = model;
  worker = new Worker('stt-worker.js', { type: 'module' });
  worker.onmessage = (ev) => {
    const msg = ev.data;
    if (msg.type === 'ready') {
      workerReady = true;
      setStatus('listening', `listening (whisper ${loadedModel} on ${msg.device})`);
    } else if (msg.type === 'progress') {
      setStatus('loading', `downloading model — ${msg.file} ${msg.pct}%`);
    } else if (msg.type === 'status' && msg.status === 'loading') {
      setStatus('loading', 'loading speech model (first time only)…');
    } else if (msg.type === 'transcript') {
      addTranscript(msg.text);
      for (const entry of matcher.match(msg.text)) addCard(entry);
    } else if (msg.type === 'error') {
      setStatus('idle', msg.message);
      stopListening();
    }
  };
  worker.postMessage({ type: 'load', model });
}

// ---------------------------------------------------------------- VAD
// Groups 100ms blocks into utterance-sized chunks (port of SpeechChunker).
class SpeechChunker {
  constructor() {
    this.silenceEndBlocks = 7;   // 0.7s
    this.maxChunkBlocks = 90;    // 9s
    this.minSpeechBlocks = 4;    // 0.4s
    this.prerollBlocks = 3;
    this.noiseFloor = 0.003;
    this.preroll = [];
    this.buf = [];
    this.speechBlocks = 0;
    this.silenceRun = 0;
    this.speaking = false;
  }
  push(block) {
    let sum = 0;
    for (let i = 0; i < block.length; i++) sum += block[i] * block[i];
    const rms = Math.sqrt(sum / block.length);
    const threshold = Math.max(0.006, this.noiseFloor * 3);

    if (!this.speaking) {
      this.noiseFloor = 0.9 * this.noiseFloor + 0.1 * rms;
      this.preroll.push(block);
      if (this.preroll.length > this.prerollBlocks) this.preroll.shift();
      if (rms > threshold) {
        this.speaking = true;
        this.buf = this.preroll.slice();
        this.preroll = [];
        this.speechBlocks = 1;
        this.silenceRun = 0;
      }
      return null;
    }

    this.buf.push(block);
    if (rms > threshold) { this.speechBlocks++; this.silenceRun = 0; }
    else this.silenceRun++;

    const done = this.silenceRun >= this.silenceEndBlocks
              || this.buf.length >= this.maxChunkBlocks;
    if (!done) return null;

    let chunk = null;
    if (this.speechBlocks >= this.minSpeechBlocks) {
      chunk = new Float32Array(this.buf.length * 1600);
      this.buf.forEach((b, i) => chunk.set(b, i * 1600));
    }
    this.buf = []; this.speechBlocks = 0; this.silenceRun = 0;
    this.speaking = false;
    return chunk;
  }
}

// ---------------------------------------------------------------- audio
async function startListening(kind) {
  if (listening) return;
  try {
    if (kind === 'mic') {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false },
      });
    } else {
      // Tab/system audio: user picks a screen/tab and checks "share audio".
      mediaStream = await navigator.mediaDevices.getDisplayMedia({
        video: true, audio: true,
      });
      mediaStream.getVideoTracks().forEach(t => t.stop());
      if (!mediaStream.getAudioTracks().length) {
        setStatus('idle', 'No audio shared — pick a tab/screen and check "share audio".');
        mediaStream = null;
        return;
      }
    }
  } catch (e) {
    setStatus('idle', 'Audio permission denied or cancelled.');
    return;
  }

  listening = true;
  ensureWorker($('model').value);
  if (!workerReady) setStatus('loading', 'loading speech model (first time only)…');
  else setStatus('listening', `listening (whisper ${loadedModel})`);

  audioCtx = new AudioContext({ sampleRate: 16000 });
  await audioCtx.audioWorklet.addModule('audio-worklet.js');
  const source = audioCtx.createMediaStreamSource(mediaStream);
  const node = new AudioWorkletNode(audioCtx, 'capture-processor');
  const chunker = new SpeechChunker();
  node.port.onmessage = (ev) => {
    if (!listening) return;
    const chunk = chunker.push(ev.data);
    if (chunk && workerReady) worker.postMessage({ type: 'transcribe', audio: chunk });
  };
  source.connect(node);
  // keep the worklet pulling without producing sound
  const sink = audioCtx.createGain();
  sink.gain.value = 0;
  node.connect(sink).connect(audioCtx.destination);

  mediaStream.getAudioTracks()[0].addEventListener('ended', stopListening);
  $('micBtn').disabled = $('sysBtn').disabled = true;
  $('stopBtn').disabled = false;
}

function stopListening() {
  listening = false;
  if (mediaStream) { mediaStream.getTracks().forEach(t => t.stop()); mediaStream = null; }
  if (audioCtx) { audioCtx.close(); audioCtx = null; }
  setStatus('idle', 'idle');
  $('micBtn').disabled = $('sysBtn').disabled = false;
  $('stopBtn').disabled = true;
}

// Test/debug hook: transcribe an audio file end-to-end without a mic.
window.processAudioUrl = async (url) => {
  ensureWorker($('model').value);
  await new Promise(res => {
    const t = setInterval(() => { if (workerReady) { clearInterval(t); res(); } }, 200);
  });
  const buf = await (await fetch(url)).arrayBuffer();
  const ctx = new OfflineAudioContext(1, 1, 16000);
  const decoded = await ctx.decodeAudioData(buf);
  const off = new OfflineAudioContext(1, Math.ceil(decoded.duration * 16000), 16000);
  const src = off.createBufferSource();
  src.buffer = decoded; src.connect(off.destination); src.start();
  const rendered = await off.startRendering();
  worker.postMessage({ type: 'transcribe', audio: rendered.getChannelData(0) });
  return 'submitted';
};

// ---------------------------------------------------------------- UI
function setStatus(state, text) {
  $('statusDot').className = state;
  $('statusText').textContent = text;
}

let transcriptLines = [];
function addTranscript(text) {
  transcriptLines.push(text);
  transcriptLines = transcriptLines.slice(-4);
  $('transcript').innerHTML = transcriptLines
    .map((t, i) => i === transcriptLines.length - 1
      ? `<span class="latest">&#127908; ${esc(t)}</span>` : esc(t))
    .join('  &middot;  ');
}

function addCard(card) {
  $('empty').style.display = 'none';
  const cardsEl = $('cards');
  const existing = document.getElementById('card-' + cssId(card.id));
  if (existing) {
    cardsEl.prepend(existing);
    existing.classList.remove('flash'); void existing.offsetWidth;
    existing.classList.add('flash');
    return;
  }
  const el = document.createElement('div');
  el.className = 'card';
  el.id = 'card-' + cssId(card.id);
  const metaKeys = Object.keys(card.meta || {});
  const metaHtml = metaKeys.length
    ? '<div class="meta">' + metaKeys.map(k =>
        `<div><b>${esc(k)}:</b> ${esc(card.meta[k])}</div>`).join('') + '</div>'
    : '';
  el.innerHTML =
    '<div class="head">' +
      `<span class="badge ${esc(card.category.replace(/\s/g, ''))}">${esc(card.category)}</span>` +
      `<h2>${esc(card.name)}</h2>` +
      (card.subtitle ? `<span class="subtitle">${esc(card.subtitle)}</span>` : '') +
      '<button class="close" title="Dismiss">&#10005;</button>' +
    '</div>' + metaHtml +
    `<div class="body">${(card.body || []).map(renderMd).join('')}</div>`;
  el.querySelector('.close').onclick = () => el.remove();
  cardsEl.prepend(el);
  const body = el.querySelector('.body');
  if (body.scrollHeight > 360) {
    body.classList.add('clamp');
    const btn = document.createElement('button');
    btn.className = 'expand';
    btn.textContent = '▼ Show full text';
    btn.onclick = () => {
      const clamped = body.classList.toggle('clamp');
      btn.textContent = clamped ? '▼ Show full text' : '▲ Collapse';
    };
    el.appendChild(btn);
  }
  while (cardsEl.querySelectorAll('.card').length > 30)
    cardsEl.querySelector('.card:last-of-type').remove();
}

// tiny markdown renderer (headers, bold, italics, lists, tables)
function renderMd(text) {
  const lines = String(text).split('\n');
  let html = '', para = [], list = null, table = null;
  const flushPara = () => { if (para.length) { html += '<p>' + inline(para.join(' ')) + '</p>'; para = []; } };
  const flushList = () => { if (list) { html += '<ul>' + list.map(li => '<li>' + inline(li) + '</li>').join('') + '</ul>'; list = null; } };
  const flushTable = () => {
    if (!table) return;
    html += '<table>' + table.filter(r => !/^[\s|:-]+$/.test(r)).map((r, i) => {
      const cells = r.split('|').map(c => c.trim())
        .filter((c, j, a) => !(j === 0 && c === '') && !(j === a.length - 1 && c === ''));
      const tag = i === 0 ? 'th' : 'td';
      return '<tr>' + cells.map(c => `<${tag}>${inline(c)}</${tag}>`).join('') + '</tr>';
    }).join('') + '</table>';
    table = null;
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) { flushPara(); flushList(); flushTable(); continue; }
    const h = line.match(/^(#{1,6})\s+(.*)/);
    if (h) {
      flushPara(); flushList(); flushTable();
      const lvl = Math.min(h[1].length + 2, 5);
      html += `<h${lvl}>${inline(h[2])}</h${lvl}>`;
      continue;
    }
    if (/^[-*]\s+/.test(line)) { flushPara(); flushTable(); (list = list || []).push(line.replace(/^[-*]\s+/, '')); continue; }
    if (line.includes('|') && line.trim().startsWith('|')) { flushPara(); flushList(); (table = table || []).push(line); continue; }
    flushList(); flushTable(); para.push(line);
  }
  flushPara(); flushList(); flushTable();
  return html;
}
function inline(s) {
  return esc(s)
    .replace(/\*\*\*(.+?)\*\*\*/g, '<b><i>$1</i></b>')
    .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
    .replace(/\*(.+?)\*/g, '<i>$1</i>')
    .replace(/_(.+?)_/g, '<i>$1</i>');
}
function esc(s) {
  return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}
function cssId(s) { return s.replace(/[^a-zA-Z0-9_-]/g, '_'); }

// ---------------------------------------------------------------- wire up
$('micBtn').onclick = () => startListening('mic');
$('sysBtn').onclick = () => startListening('system');
$('stopBtn').onclick = stopListening;

function simulate() {
  const text = $('simText').value.trim();
  if (!text) return;
  $('simText').value = '';
  addTranscript(text);
  for (const entry of matcher.match(text)) addCard(entry);
}
$('simBtn').onclick = simulate;
$('simText').addEventListener('keydown', e => { if (e.key === 'Enter') simulate(); });

setStatus('idle', 'loading rules…');
loadData().then(() => setStatus('idle', 'idle'))
  .catch(e => setStatus('idle', 'failed to load rules: ' + e.message));
