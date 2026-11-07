// ESPN NFL 2K5 web page: checks the browser, imports the player's disc into
// OPFS (import-worker.js), and starts the game (NFL2K5.js, built by
// tools/build-web.sh) when the player presses Play.
//
// URL parameters, for development:
//   ?env=NAME=VALUE   set an environment variable for the game (repeatable),
//                     e.g. ?env=RECOMP_APU_TRACE=1
//   ?autoplay=1       press Play as soon as a disc is installed
'use strict';

const MARKER = 'web-import.json';
// default.xbe hashes this build accepts (src/main.c): the retail disc's, and
// the widescreen-patched one it also accepts directly.
const KNOWN_XBE = {
  '73105b17a3161c546fea792a1c84ce37f9966a67c416f474cdbfab74b911a4a9': 'retail ESPN NFL 2K5',
  '81d6e16c25ca7ea1014d0ced915f910f5d354eaeabeb9adfcbb6956e2a0b54f8': 'ESPN NFL 2K5 (widescreen patch)',
};

const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
const state = { installed: null, importing: false, running: false };

// ---- log ---------------------------------------------------------------------

const logLines = [];
function log(text, kind) {
  const line = document.createElement('div');
  if (kind) line.className = kind;
  line.textContent = text;
  const box = $('log');
  box.appendChild(line);
  logLines.push(text);
  while (box.childNodes.length > 2000) box.removeChild(box.firstChild);
  box.scrollTop = box.scrollHeight;
}
window.nfl2k5Log = logLines;   // read by tests/web/test_web_page.js

function setCheck(id, ok, text) {
  const el = $(id);
  el.dataset.ok = ok ? 'yes' : 'no';
  el.querySelector('.value').textContent = text;
}

// ---- cross-origin isolation --------------------------------------------------

async function ensureIsolation() {
  if (self.crossOriginIsolated) {
    sessionStorage.removeItem('coi-reload');
    return true;
  }
  // No COOP/COEP from the server: add them with a service worker and reload
  // once. A second miss means the browser refused; say so rather than loop.
  if ('serviceWorker' in navigator && !sessionStorage.getItem('coi-reload')) {
    try {
      await navigator.serviceWorker.register('coi-sw.js');
      await navigator.serviceWorker.ready;
      sessionStorage.setItem('coi-reload', '1');
      location.reload();
      return new Promise(() => {});   // reloading
    } catch (e) {
      log('Service worker registration failed: ' + e.message, 'error');
    }
  }
  return false;
}

// ---- disc state --------------------------------------------------------------

async function readMarker() {
  try {
    const root = await navigator.storage.getDirectory();
    const f = await (await root.getFileHandle(MARKER)).getFile();
    return JSON.parse(await f.text());
  } catch {
    return null;
  }
}

function mb(n) { return (n / (1024 * 1024)).toFixed(n < 10 * 1024 * 1024 ? 1 : 0) + ' MB'; }

async function refreshStorage() {
  try {
    const est = await navigator.storage.estimate();
    const persisted = navigator.storage.persisted ? await navigator.storage.persisted() : false;
    setCheck('chk-storage', true, `${mb(est.usage || 0)} used of ${mb(est.quota || 0)}` +
             (persisted ? ', persistent' : ', may be cleared by the browser under pressure'));
  } catch (e) {
    setCheck('chk-storage', false, 'unavailable: ' + e.message);
  }
}

function renderDisc() {
  const info = state.installed;
  $('disc-none').hidden = !!info;
  $('disc-installed').hidden = !info;
  if (info) {
    const known = KNOWN_XBE[info.xbeSha256];
    $('disc-summary').textContent =
      `${info.files} files, ${mb(info.bytes)}, from ${info.source.kind === 'image' ? 'image' : 'folder'} ` +
      `"${info.source.name}" on ${new Date(info.importedAt).toLocaleString()}`;
    $('disc-xbe').textContent = known ? `default.xbe: ${known}` :
      `default.xbe is not one this build runs (SHA-256 ${info.xbeSha256.slice(0, 16)}…). ` +
      'The game will refuse it; mod-pack discs are not supported on the web yet.';
    $('disc-xbe').className = known ? 'ok' : 'warn';
    if (!info.hasVc53450030)
      $('disc-xbe').textContent += ' The disc has no vc_53450030 folder, so it is probably incomplete.';
  }
  const ready = !!info && self.crossOriginIsolated && !state.importing && !state.running;
  $('play').disabled = !ready;
  $('import-image').disabled = $('import-folder').disabled = state.importing || state.running;
  $('remove').disabled = state.importing || state.running;
}

// ---- import ------------------------------------------------------------------

function runImport(msg) {
  state.importing = true;
  renderDisc();
  $('progress').hidden = false;
  $('progress-bar').value = 0;
  $('progress-text').textContent = 'Reading the disc…';
  if (navigator.storage.persist) navigator.storage.persist().catch(() => {});
  const started = performance.now();
  const worker = new Worker('import-worker.js');
  return new Promise((resolve) => {
    worker.onmessage = async (e) => {
      const m = e.data;
      if (m.type === 'progress') {
        $('progress-bar').max = m.total || 1;
        $('progress-bar').value = m.done;
        $('progress-text').textContent = `${mb(m.done)} of ${mb(m.total)}` + (m.file ? ` — ${m.file}` : '');
        return;
      }
      worker.terminate();
      state.importing = false;
      $('progress').hidden = true;
      if (m.type === 'done') {
        const secs = ((performance.now() - started) / 1000).toFixed(1);
        log(`Imported ${m.info.files} files (${mb(m.info.bytes)}) in ${secs} s; ` +
            `default.xbe SHA-256 ${m.info.xbeSha256}`, 'ok');
        state.installed = m.info;
      } else {
        log('Import failed: ' + m.message, 'error');
        state.installed = await readMarker();
      }
      renderDisc();
      refreshStorage();
      resolve(m);
    };
    worker.postMessage(msg);
  });
}

async function removeDisc() {
  if (!confirm('Remove the imported game files from this browser? Saves are kept.')) return;
  const root = await navigator.storage.getDirectory();
  await root.removeEntry(MARKER).catch(() => {});
  const original = await root.getDirectoryHandle('original', { create: true });
  await original.removeEntry('disc', { recursive: true }).catch(() => {});
  state.installed = null;
  log('Removed the imported game files.');
  renderDisc();
  refreshStorage();
}

// ---- game --------------------------------------------------------------------

// Synchronous up to the AudioContext: browsers only allow sound that starts
// inside the click (see web/launch.js).
function play() {
  const audio = NFL2K5Launch.createAudio();
  state.running = true;
  renderDisc();
  $('stage').hidden = false;
  NFL2K5Launch.watchSound(audio, $('sound'), (st) => log('Sound: ' + st));
  log('Starting the game…');
  NFL2K5Launch.start({
    script: 'NFL2K5.js', factory: 'createNFL2K5', canvas: $('canvas'), audioContext: audio,
    env: params.getAll('env'),
    print: (t) => log(t),
    printErr: (t) => log(t, 'stderr'),
    onAbort: (what) => log('Aborted: ' + what, 'error'),
    onGpuPresent: (on) => log(on ? 'Video: WebGPU' : 'Video: software'),
  }).catch((e) => {
    log('The game stopped: ' + (e && e.message ? e.message : e), 'error');
    state.running = false;
    renderDisc();
  });
}

// ---- start -------------------------------------------------------------------

async function main() {
  const wasm = typeof WebAssembly === 'object';
  setCheck('chk-wasm', wasm, wasm ? 'available' : 'missing');
  const isolated = await ensureIsolation();
  setCheck('chk-isolation', isolated, isolated
    ? 'on (SharedArrayBuffer available)'
    : 'off — the server must send COOP/COEP headers (tools/serve-web.py does), or allow the service worker');
  const opfs = !!(navigator.storage && navigator.storage.getDirectory);
  setCheck('chk-opfs', opfs, opfs ? 'available' : 'missing — this browser cannot store the game files');
  await refreshStorage();
  state.installed = opfs ? await readMarker() : null;
  renderDisc();

  $('file-image').onchange = (e) => {
    const f = e.target.files[0];
    e.target.value = '';
    if (f) runImport({ kind: 'image', file: f });
  };
  $('file-folder').onchange = (e) => {
    const files = Array.from(e.target.files);
    e.target.value = '';
    if (files.length) runImport({ kind: 'folder', files });
  };
  $('import-image').onclick = () => $('file-image').click();
  $('import-folder').onclick = () => $('file-folder').click();
  $('remove').onclick = removeDisc;
  $('play').onclick = play;
  $('canvas').addEventListener('contextmenu', (e) => e.preventDefault());

  document.body.dataset.ready = '1';
  if (params.get('autoplay') === '1' && !$('play').disabled) play();
}

main().catch((e) => log('Page error: ' + e.message, 'error'));
