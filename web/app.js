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
const state = { installed: null, importing: false, running: false, launched: false,
  checked: false, supported: false, build: false, gpu: false, launchError: '' };

// ---- log ---------------------------------------------------------------------

const logLines = [];
function log(text, kind) {
  const line = document.createElement('div');
  if (kind) line.className = kind;
  line.textContent = text;
  const box = $('log');
  box.appendChild(line);
  logLines.push(text);
  if (logLines.length > 2000) logLines.shift();
  while (box.childNodes.length > 2000) box.removeChild(box.firstChild);
  if ($('diagnostics').open) box.scrollTop = box.scrollHeight;
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
    const info = JSON.parse(await f.text());
    return info && info.version === 1 && typeof info.xbeSha256 === 'string' &&
      Number.isFinite(info.files) && Number.isFinite(info.bytes) && info.source &&
      typeof info.source.name === 'string' && typeof info.importedAt === 'string' ? info : null;
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
  const valid = !!info && !!KNOWN_XBE[info.xbeSha256] && info.hasVc53450030;
  const ready = valid && state.checked && state.supported && state.build && !state.importing && !state.launched;
  $('play').disabled = !ready;
  $('import-image').disabled = $('import-folder').disabled = !state.checked || !state.supported || state.importing || state.launched;
  $('remove').disabled = !info || state.importing || state.launched;
  $('library').setAttribute('aria-busy', String(state.importing));
  $('disc-badge').textContent = state.importing ? 'Importing' : info ? (valid ? 'Imported' : 'Needs attention') : 'Not imported';
  $('disc-badge').dataset.state = state.importing ? 'busy' : valid ? 'ready' : info ? 'error' : '';
  let label = 'Getting ready', badge = 'Checking browser', message = 'Checking your browser and game files…', status = 'busy';
  if (state.launchError) {
    label = 'Launch interrupted'; badge = 'Reload to retry'; message = state.launchError; status = 'error';
  } else if (state.launched) {
    label = state.running ? 'Game running' : 'Starting game'; badge = state.running ? 'In session' : 'Loading';
    message = 'Your game is below. Click the screen to use keyboard controls.'; status = 'ready';
  } else if (state.checked && !state.supported) {
    label = 'Browser setup needed'; badge = 'Unavailable'; status = 'error';
    message = 'This browser needs WebAssembly, shared memory and private game storage. Open Browser & diagnostics for details.';
  } else if (state.checked && !state.build) {
    label = 'Game runtime missing'; badge = 'Unavailable'; status = 'error';
    message = 'The game runtime could not be loaded. Check the server or build, then reload the launcher.';
  } else if (state.importing) {
    label = 'Importing your game'; badge = 'Please wait'; message = 'Keep this tab open while the game files are copied into local storage.';
  } else if (state.checked && !info) {
    label = 'Add your game to get started'; badge = 'Step 1 of 2'; status = '';
    message = 'Choose your Xbox ISO or extracted game folder below. Import is only needed once.';
  } else if (state.checked && !valid) {
    label = 'Check your game files'; badge = 'Unsupported disc'; status = 'error';
    message = 'This build needs a complete retail USA disc or the supported widescreen-patched version. See your library below.';
  } else if (ready) {
    label = 'Ready for kickoff'; badge = state.gpu ? 'WebGPU ready' : 'Software graphics'; status = state.gpu ? 'ready' : 'busy';
    message = state.gpu ? 'Your game is installed. Launch when you’re ready.' : 'Hardware graphics are unavailable. The software renderer may be very slow.';
  }
  $('launch-label').textContent = label;
  $('launch-badge').textContent = badge;
  $('launch-badge').dataset.state = status;
  $('launch-status').textContent = message;
  $('reload').hidden = !state.launchError && !(state.checked && !state.build);
}

function libraryMessage(text, kind = 'error') {
  $('library-message').textContent = text;
  $('library-message').className = kind;
  $('library-message').hidden = !text;
}

// ---- import ------------------------------------------------------------------

function runImport(msg) {
  if (state.importing || state.launched || !state.supported) return Promise.resolve(null);
  state.importing = true;
  libraryMessage('');
  renderDisc();
  $('progress').hidden = false;
  $('progress-bar').value = 0;
  $('progress-percent').textContent = '0%';
  $('progress-text').textContent = 'Reading the disc…';
  if (navigator.storage.persist) navigator.storage.persist().catch(() => {});
  const started = performance.now();
  return new Promise((resolve) => {
    let worker, finished = false;
    const finish = async (m) => {
      if (finished) return;
      finished = true;
      if (worker) worker.terminate();
      state.importing = false;
      $('progress').hidden = true;
      if (m.type === 'done') {
        const secs = ((performance.now() - started) / 1000).toFixed(1);
        log(`Imported ${m.info.files} files (${mb(m.info.bytes)}) in ${secs} s; default.xbe SHA-256 ${m.info.xbeSha256}`, 'ok');
        state.installed = m.info;
        libraryMessage('Game files imported. Compatibility details are shown above.', 'ok');
      } else {
        log('Import failed: ' + m.message, 'error');
        libraryMessage('Import failed: ' + m.message);
        state.installed = await readMarker();
      }
      renderDisc();
      refreshStorage();
      resolve(m);
    };
    try { worker = new Worker('import-worker.js'); }
    catch (e) { finish({ type: 'error', message: e.message }); return; }
    worker.onerror = (e) => { e.preventDefault(); finish({ type: 'error', message: e.message || 'The import worker stopped. Please try again.' }); };
    worker.onmessageerror = () => finish({ type: 'error', message: 'The import worker returned an unreadable response. Please try again.' });
    worker.onmessage = (e) => {
      const m = e.data;
      if (m.type === 'progress') {
        $('progress-bar').max = m.total || 1;
        $('progress-bar').value = m.done;
        $('progress-percent').textContent = m.total ? Math.min(100, Math.floor(m.done / m.total * 100)) + '%' : '…';
        $('progress-text').textContent = `${mb(m.done)} of ${mb(m.total)}` + (m.file ? ` — ${m.file}` : '');
        return;
      }
      finish(m);
    };
    try { worker.postMessage(msg); } catch (e) { finish({ type: 'error', message: e.message }); }
  });
}

async function removeDisc() {
  if (!state.installed || state.importing || state.launched) return;
  if (!confirm('Remove the imported game files from this browser? Saves are kept.')) return;
  try {
    const root = await navigator.storage.getDirectory();
    try {
      const original = await root.getDirectoryHandle('original');
      await original.removeEntry('disc', { recursive: true });
    } catch (e) { if (e.name !== 'NotFoundError') throw e; }
    await root.removeEntry(MARKER);
    state.installed = null;
    libraryMessage('Game files removed. Your saves and settings are still stored here.', 'ok');
    log('Removed the imported game files.');
  } catch (e) { libraryMessage('Could not remove game files: ' + e.message); }
  renderDisc();
  refreshStorage();
}

// ---- game --------------------------------------------------------------------

// Synchronous up to the AudioContext: browsers only allow sound that starts
// inside the click (see web/launch.js).
function play() {
  if ($('play').disabled || state.launched) return;
  const audio = NFL2K5Launch.createAudio();
  const canvas = $('canvas');
  const screen = $('screen');
  // SDL requests fullscreen on its canvas. Keep both canvases in the
  // fullscreen element so a renderer handoff cannot hide the visible frame.
  if (typeof screen.requestFullscreen === 'function')
    canvas.requestFullscreen = (options) => screen.requestFullscreen(options);
  state.launched = true;
  renderDisc();
  $('stage').hidden = false;
  $('stage').scrollIntoView({ block: 'start' });
  NFL2K5Launch.watchSound(audio, $('sound'), (st) => log('Sound: ' + st));
  log('Starting the game…');
  NFL2K5Launch.start({
    script: 'NFL2K5.js', factory: 'createNFL2K5', canvas, audioContext: audio,
    // Use the game's skip path for the unsupported startup movie.
    env: ['NFL2K5_SKIP_INTRO=1', ...params.getAll('env')],
    print: (t) => log(t),
    printErr: (t) => log(t, 'stderr'),
    onProgress: (text) => { if (text) $('game-status').textContent = text; },
    onAbort: (what) => launchFailed('Aborted: ' + what),
    onGpuPresent: (on) => { log(on ? 'Video: WebGPU' : 'Video: software'); $('game-status').textContent = on ? 'Playing · WebGPU' : 'Playing · software graphics'; },
  }).then(() => {
    if (!state.launchError) {
      state.running = true;
      if (!$('game-status').textContent.startsWith('Playing')) $('game-status').textContent = 'Game running';
      renderDisc();
    }
  }).catch((e) => {
    log('The game stopped: ' + (e && e.message ? e.message : e), 'error');
    launchFailed(e && e.message ? e.message : String(e));
  });
}

function launchFailed(message) {
  state.running = false;
  state.launchError = message;
  $('game-status').textContent = 'Game stopped · reload to try again';
  renderDisc();
}

async function checkBuild() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const results = await Promise.all(['NFL2K5.js', 'NFL2K5.wasm'].map(file =>
      fetch(file, { method: 'HEAD', cache: 'no-store', signal: controller.signal })));
    return results.every(r => r.ok && !/text\/html/.test(r.headers.get('content-type') || ''));
  } catch { return false; } finally { clearTimeout(timer); }
}

function updateControllers() {
  const pads = navigator.getGamepads ? Array.from(navigator.getGamepads()).filter(Boolean) : [];
  $('controller-status').textContent = pads.length ? 'Connected: ' + pads.map(p => p.id).join(', ') :
    'No controller detected. Press a button on your controller to connect.';
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
  state.supported = wasm && isolated && opfs;
  state.build = await checkBuild();
  setCheck('chk-build', state.build, state.build ? 'available' : 'missing or unreachable — reload after checking the build/server');
  try {
    state.gpu = !!navigator.gpu && !!(await Promise.race([
      navigator.gpu.requestAdapter(), new Promise(resolve => setTimeout(() => resolve(null), 5000))]));
  } catch { state.gpu = false; }
  setCheck('chk-gpu', state.gpu, state.gpu ? 'WebGPU available' : 'unavailable — software rendering will be slow');
  await refreshStorage();
  state.installed = opfs ? await readMarker() : null;
  state.checked = true;
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
  $('reload').onclick = () => location.reload();
  $('restart').onclick = () => { if (confirm('Restart the game? Unsaved progress will be lost.')) location.reload(); };
  $('fullscreen').onclick = async () => {
    try { if (document.fullscreenElement) await document.exitFullscreen(); else await $('screen').requestFullscreen(); }
    catch (e) { log('Fullscreen unavailable: ' + e.message, 'error'); }
  };
  document.addEventListener('fullscreenchange', () => { $('fullscreen').textContent = document.fullscreenElement ? 'Exit fullscreen' : 'Fullscreen'; });
  $('download-log').onclick = () => {
    const url = URL.createObjectURL(new Blob([logLines.join('\n')], { type: 'text/plain' }));
    const link = document.createElement('a'); link.href = url; link.download = 'nfl2k5-web-log.txt'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const drop = $('drop-zone');
  for (const type of ['dragover', 'dragleave', 'drop']) drop.addEventListener(type, e => {
    e.preventDefault(); drop.dataset.dragging = String(type === 'dragover' && !state.importing && !state.launched);
    if (type !== 'drop' || state.importing || state.launched) return;
    const files = Array.from(e.dataTransfer.files);
    if (files.length !== 1 || !/\.(iso|xiso|img)$/i.test(files[0].name)) {
      libraryMessage('Drop one ISO/XISO image here. Use Choose folder for an extracted disc.'); return;
    }
    runImport({ kind: 'image', file: files[0] });
  });
  window.addEventListener('dragover', e => e.preventDefault());
  window.addEventListener('drop', e => e.preventDefault());
  window.addEventListener('gamepadconnected', updateControllers);
  window.addEventListener('gamepaddisconnected', updateControllers);
  updateControllers();
  $('canvas').addEventListener('contextmenu', (e) => e.preventDefault());

  document.body.dataset.ready = '1';
  if (params.get('autoplay') === '1' && !$('play').disabled) play();
}

main().catch((e) => { log('Page error: ' + e.message, 'error'); $('launch-status').textContent = 'Launcher setup failed: ' + e.message; $('reload').hidden = false; $('reload').onclick = () => location.reload(); });
