// End-to-end test of the web page in headless Chromium (Playwright):
//
//   1. served with COOP/COEP (tools/serve-web.py): the page is cross-origin
//      isolated; a disc image imports into OPFS byte for byte; Play starts
//      the real NFL2K5 module, which mounts OPFS, reads default.xbe and stops
//      at its hash check -- printing the SHA-256 of the bytes it read, which
//      must be the image's; after a reload the disc is still installed;
//   2. an extracted folder (chosen one level above the disc) imports the same
//      files (empty directories cannot come through a folder picker);
//   3. a file that is not a disc image is refused and leaves nothing behind;
//   4. served without the headers (a static host): the service worker makes
//      the page isolated after one reload, and the module still starts.
//
//   node tests/web/test_web_page.js <build-web dir>
// Needs a full web build (tools/build-web.sh). Uses the preinstalled
// Playwright and Chromium; Python 3 for the fixture and the server.
'use strict';
const { chromium } = require('playwright');
const { spawn, execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const BUILD = path.resolve(process.argv[2] || path.join(ROOT, 'build-web'));
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'nfl2k5-web-'));
let failures = 0;
const check = (cond, what) => { if (!cond) { failures++; console.log('FAIL:', what); } else console.log('ok:', what); };

function serve(port, extra) {
  const p = spawn('python3', [path.join(ROOT, 'tools/serve-web.py'), BUILD, '--port', String(port), ...extra],
                  { env: { ...process.env, NFL2K5_SERVE_QUIET: '1' }, stdio: ['ignore', 'pipe', 'inherit'] });
  return new Promise((resolve) => p.stdout.on('data', (d) => { if (/Serving/.test(d)) resolve(p); }));
}

async function newPage(browser, url) {
  const context = await browser.newContext();
  const page = await context.newPage();
  page.on('pageerror', (e) => console.log('  [pageerror]', e.message));
  await page.goto(url);
  await page.waitForSelector('body[data-ready="1"]', { timeout: 30000 });
  return { context, page };
}

const logs = (page) => page.evaluate(() => window.nfl2k5Log.slice());
async function waitLog(page, re, ms) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    const hit = (await logs(page)).find((l) => re.test(l));
    if (hit) return hit;
    await page.waitForTimeout(200);
  }
  return null;
}

// SHA-256 of every file under OPFS original/disc, and the directories.
const opfsDisc = (page) => page.evaluate(async () => {
  const hex = (b) => Array.from(new Uint8Array(b), (x) => x.toString(16).padStart(2, '0')).join('');
  const out = { files: {}, dirs: [] };
  const root = await navigator.storage.getDirectory();
  let disc;
  try { disc = await (await root.getDirectoryHandle('original')).getDirectoryHandle('disc'); } catch { return null; }
  const walk = async (dir, prefix) => {
    for await (const [name, h] of dir.entries()) {
      if (h.kind === 'directory') { out.dirs.push(prefix + name); await walk(h, prefix + name + '/'); }
      else out.files[prefix + name] = hex(await crypto.subtle.digest('SHA-256', await (await h.getFile()).arrayBuffer()));
    }
  };
  await walk(disc, '');
  return out;
});

// A folder picker hands the page files only, so an empty directory cannot
// come through it (a disc image keeps them): `withEmptyDirs` is for images.
function sameDisc(got, want, withEmptyDirs) {
  if (!got) return false;
  const a = Object.keys(got.files).sort(), b = Object.keys(want.files).sort();
  return JSON.stringify(a) === JSON.stringify(b) && b.every((k) => got.files[k] === want.files[k]) &&
         (!withEmptyDirs || want.dirs.every((d) => got.dirs.includes(d)));
}

async function playAndCheckXbe(page, want, label) {
  // Let the synthetic fixture through the UI compatibility check so this
  // integration test still reaches the runtime's independent hash guard.
  await page.evaluate(hash => { KNOWN_XBE[hash] = 'synthetic test fixture'; renderDisc(); }, want.xbe_sha256);
  await page.click('#play');
  if (label === 'image') {
    const target = await page.evaluate(async () => {
      await document.querySelector('#canvas').requestFullscreen();
      const id = document.fullscreenElement?.id;
      await document.exitFullscreen();
      return id;
    });
    check(target === 'screen', 'SDL fullscreen keeps both presentation canvases on screen');
  }
  const mount = await waitLog(page, /\[WEB\] Game files: OPFS at \/nfl2k5/, 60000);
  check(!!mount, `${label}: module mounted OPFS`);
  check(!!(await waitLog(page, /Mounted game disc root: \/nfl2k5\/original\/disc/, 30000)),
        `${label}: game found the disc in OPFS`);
  const hit = await waitLog(page, /XBE hash mismatch/, 30000);
  const got = hit && (hit.match(/got ([0-9a-f]{64})/) || [])[1];
  check(got === want.xbe_sha256, `${label}: module read default.xbe from OPFS (SHA-256 ${got})`);
}

(async () => {
  execFileSync('python3', ['-I', path.join(__dirname, 'make_test_disc.py'), TMP], { stdio: 'inherit' });
  const want = JSON.parse(fs.readFileSync(path.join(TMP, 'expected.json')));
  fs.writeFileSync(path.join(TMP, 'not-a-disc.iso'), Buffer.alloc(200000, 7));

  const isolated = await serve(18765, []);
  const plain = await serve(18766, ['--no-isolation']);
  const browser = await chromium.launch();
  try {
    // 1. Disc image, isolated server.
    {
      const { context, page } = await newPage(browser, 'http://127.0.0.1:18765/');
      check(await page.evaluate(() => self.crossOriginIsolated), 'isolated server: crossOriginIsolated');
      const gpuLayout = await page.evaluate(() => {
        const stage = document.querySelector('#stage');
        const input = document.querySelector('#canvas');
        const gpu = document.querySelector('#gpucanvas');
        const original = [input.width, input.height, gpu.width, gpu.height];
        stage.hidden = false;
        input.width = input.height = 0;
        gpu.width = 1280;
        gpu.height = 720;
        gpu.hidden = false;
        gpu.scrollIntoView({ block: 'center' });
        const bounds = gpu.getBoundingClientRect();
        const point = [bounds.x + bounds.width / 2, bounds.y + bounds.height / 2];
        const target = document.elementFromPoint(...point);
        gpu.style.pointerEvents = 'auto';
        const gpuOnTop = document.elementFromPoint(...point) === gpu;
        gpu.style.removeProperty('pointer-events');
        gpu.hidden = stage.hidden = true;
        [input.width, input.height, gpu.width, gpu.height] = original;
        return { width: bounds.width, height: bounds.height, inputActive: target === input, gpuOnTop };
      });
      check(gpuLayout.width > 0 && gpuLayout.height > 0, 'GPU canvas sizes the screen when SDL releases its buffer');
      check(gpuLayout.inputActive, 'SDL canvas still receives pointer input over the GPU frame');
      check(gpuLayout.gpuOnTop, 'GPU canvas paints above the SDL input canvas');
      check(await page.$eval('#play', (b) => b.disabled), 'Play disabled before a disc is imported');
      await page.setInputFiles('#file-image', path.join(TMP, 'test.xiso'));
      check(!!(await waitLog(page, /^Imported 7 files/, 60000)), 'image import finished');
      check(sameDisc(await opfsDisc(page), want, true), 'image: every file in OPFS matches the disc, empty dirs kept');
      check(await page.$eval('#play', (b) => b.disabled), 'unsupported XBE cannot launch from the page');
      check(/Check your game files/.test(await page.textContent('#launch-label')), 'unsupported disc explains the next step');
      await playAndCheckXbe(page, want, 'image');
      await page.reload();
      await page.waitForSelector('body[data-ready="1"]');
      check(await page.isVisible('#disc-installed') &&
            /7 files/.test(await page.textContent('#disc-summary')), 'disc still installed after reload');
      check(/not one this build runs/.test(await page.textContent('#disc-xbe')),
            'non-retail default.xbe is flagged');
      await context.close();
    }
    // Missing runtime, worker failures and mobile layout are launcher states,
    // independent of the retail game binary.
    {
      const {context, page} = await newPage(browser, 'http://127.0.0.1:18765/');
      await page.evaluate(() => {
        const transfer = new DataTransfer(); transfer.items.add(new File(['bad'], 'readme.txt'));
        document.querySelector('#drop-zone').dispatchEvent(new DragEvent('drop', {dataTransfer: transfer, bubbles: true}));
      });
      check(/Drop one ISO/.test(await page.textContent('#library-message')), 'invalid dropped files explain supported imports');
      await page.evaluate(() => {
        const input = document.createElement('input'); input.type = 'file'; input.id = 'drop-fixture'; input.hidden = true;
        document.body.appendChild(input);
      });
      await page.setInputFiles('#drop-fixture', path.join(TMP, 'test.xiso'));
      await page.evaluate(() => {
        const transfer = new DataTransfer(); transfer.items.add(document.querySelector('#drop-fixture').files[0]);
        document.querySelector('#drop-zone').dispatchEvent(new DragEvent('drop', {dataTransfer: transfer, bubbles: true}));
        document.querySelector('#drop-fixture').remove();
      });
      check(!!(await waitLog(page, /^Imported 7 files/, 60000)), 'drag-and-drop disc import finished');
      check(sameDisc(await opfsDisc(page), want, true), 'dropped image imports byte for byte');
      await context.close();
    }
    {
      const context = await browser.newContext({ viewport: {width: 390, height: 844} });
      const page = await context.newPage();
      await page.route('**/NFL2K5.wasm', route => route.fulfill({status: 404, body: ''}));
      await page.goto('http://127.0.0.1:18765/');
      await page.waitForSelector('body[data-ready="1"]');
      check(await page.$eval('#play', b => b.disabled) && /runtime missing/i.test(await page.textContent('#launch-label')),
            'missing runtime blocks launch with a recovery message');
      check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'mobile launcher fits without horizontal scrolling');
      await context.close();
    }
    {
      const context = await browser.newContext();
      await context.addInitScript(() => {
        navigator.getGamepads = () => { throw new DOMException('blocked','SecurityError'); };
        navigator.storage.persist = async () => false;
      });
      const page = await context.newPage();
      await page.goto('http://127.0.0.1:18765/');
      await page.waitForSelector('body[data-ready="1"]');
      check(/Keyboard controls remain available/.test(await page.textContent('#controller-status')), 'denied controller access does not break launcher setup');
      await page.evaluate(async () => {
        const saves = await (await navigator.storage.getDirectory()).getDirectoryHandle('saves',{create:true});
        const w = await (await saves.getFileHandle('season.dat',{create:true})).createWritable();
        await w.write(new Uint8Array([0,255,42])); await w.close();
      });
      await page.click('#refresh-saves');
      await page.waitForFunction(() => !document.querySelector('#export-saves').disabled);
      const [backup] = await Promise.all([page.waitForEvent('download'),page.click('#export-saves')]);
      const bytes = fs.readFileSync(await backup.path());
      const archive = JSON.parse(bytes);
      check(archive.files.length === 1 && archive.files[0].path === 'saves/season.dat', 'launcher downloads a portable save backup');
      await page.waitForFunction(() => !document.querySelector('#import-saves').disabled);
      page.once('dialog', d => d.accept());
      await page.setInputFiles('#file-saves',{name:'backup.json',mimeType:'application/json',buffer:bytes});
      await page.waitForFunction(() => document.querySelector('#save-message').textContent.startsWith('Restored 1 files'));
      check(true,'launcher restores backup and reports success');
      await page.waitForFunction(() => !document.querySelector('#persist-storage').disabled);
      await page.click('#persist-storage');
      check(/did not grant/.test(await page.textContent('#save-message')), 'persistent-storage refusal explains how to protect saves');
      await page.evaluate(async () => { window.releaseTestSession = await NFL2K5Storage.acquireSession(); });
      const other = await context.newPage(); await other.goto('http://127.0.0.1:18765/');
      await other.waitForSelector('body[data-ready="1"]');
      check(/Another NFL 2K5 tab/.test(await other.textContent('#save-summary')), 'launcher explains cross-tab storage exclusion');
      await page.evaluate(() => releaseTestSession());
      await other.click('#refresh-saves');
      await other.waitForFunction(() => !document.querySelector('#export-saves').disabled);
      check(true,'launcher can refresh saves after another session closes');
      await context.close();
    }
    {
      const {context, page} = await newPage(browser, 'http://127.0.0.1:18765/');
      await page.evaluate(() => { window.Worker = class { constructor() { throw Error('worker unavailable'); } }; });
      await page.setInputFiles('#file-image', path.join(TMP, 'test.xiso'));
      await page.waitForFunction(() => !document.querySelector('#library-message').hidden);
      check(/worker unavailable/.test(await page.textContent('#library-message')) &&
            !(await page.$eval('#import-image', b => b.disabled)), 'worker startup failure is visible and import can be retried');
      await context.close();
    }
    {
      const {context, page} = await newPage(browser, 'http://127.0.0.1:18765/');
      await page.setInputFiles('#file-image', path.join(TMP, 'test.xiso'));
      await waitLog(page, /^Imported 7 files/, 60000);
      await page.evaluate(async () => {
        const root = await navigator.storage.getDirectory();
        const saves = await root.getDirectoryHandle('saves', {create: true});
        await saves.getFileHandle('keep.dat', {create: true});
      });
      page.once('dialog', dialog => dialog.accept());
      await page.click('#remove');
      await page.waitForFunction(() => document.querySelector('#disc-installed').hidden);
      check(await page.evaluate(async () => {
        const root = await navigator.storage.getDirectory();
        const saves = await root.getDirectoryHandle('saves');
        return !!(await saves.getFileHandle('keep.dat'));
      }), 'removing game files preserves saves');
      await page.setInputFiles('#file-image', path.join(TMP, 'test.xiso'));
      await page.waitForFunction(() => !document.querySelector('#disc-installed').hidden);
      await page.evaluate(hash => {
        KNOWN_XBE[hash] = 'synthetic test fixture'; renderDisc();
        NFL2K5Launch.start = async options => { options.onAbort('simulated startup failure'); return {}; };
      }, want.xbe_sha256);
      await page.click('#play');
      await page.waitForFunction(() => !document.querySelector('#reload').hidden);
      check(await page.$eval('#play', b => b.disabled) && /simulated startup failure/.test(await page.textContent('#launch-status')),
            'aborted startup offers reload and prevents a duplicate runtime');
      await page.click('#diagnostics summary');
      const [download] = await Promise.all([page.waitForEvent('download'), page.click('#download-log')]);
      check(download.suggestedFilename() === 'nfl2k5-web-log.txt', 'diagnostic log can be downloaded');
      await context.close();
    }
    {
      const context = await browser.newContext();
      await context.addInitScript(() => {
        window.testPad = {id:'Launcher test controller',connected:true,mapping:'standard',
          buttons:[{pressed:true,value:1},...Array.from({length:5},()=>({pressed:false,value:0})),{pressed:true,value:0.5}],axes:[0.25,-0.5,0,0]};
        navigator.getGamepads = () => [testPad];
      });
      const page = await context.newPage(); await page.goto('http://127.0.0.1:18765/');
      await page.waitForSelector('body[data-ready="1"]');
      await page.click('#controller-test summary');
      await page.waitForFunction(() => document.querySelector('#controller-readout').textContent.includes('LT: 0.50'));
      check(/A \/ Cross: 1.00/.test(await page.textContent('#controller-readout')) &&
        /0.25, -0.50/.test(await page.textContent('#controller-readout')), 'controller tester displays named buttons, analog triggers and stick values');
      await page.evaluate(() => {testPad.connected=false;dispatchEvent(new Event('gamepaddisconnected'));});
      check(/No controller detected/.test(await page.textContent('#controller-status')), 'launcher excludes disconnected controller objects');
      await context.close();
    }
    // 2. Extracted folder, chosen one level above the disc.
    {
      const { context, page } = await newPage(browser, 'http://127.0.0.1:18765/');
      await page.setInputFiles('#file-folder', path.join(TMP, 'folder'));
      check(!!(await waitLog(page, /^Imported 7 files/, 60000)), 'folder import finished');
      check(sameDisc(await opfsDisc(page), want, false), 'folder: every file in OPFS matches the disc');
      await context.close();
    }
    // 3. Not a disc image.
    {
      const { context, page } = await newPage(browser, 'http://127.0.0.1:18765/');
      await page.setInputFiles('#file-image', path.join(TMP, 'not-a-disc.iso'));
      check(!!(await waitLog(page, /Import failed: This is not an Xbox disc image/, 30000)), 'non-disc refused');
      check(await page.$eval('#play', (b) => b.disabled) && !(await page.isVisible('#disc-installed')),
            'nothing installed after a refused import');
      await context.close();
    }
    // 4. No COOP/COEP from the server: service worker fallback.
    {
      const { context, page } = await newPage(browser, 'http://127.0.0.1:18766/');
      check(await page.evaluate(() => self.crossOriginIsolated), 'static host: isolated via the service worker');
      await page.setInputFiles('#file-image', path.join(TMP, 'test.xiso'));
      check(!!(await waitLog(page, /^Imported 7 files/, 60000)), 'static host: image import finished');
      await playAndCheckXbe(page, want, 'static host');
      await context.close();
    }
  } finally {
    await browser.close();
    isolated.kill();
    plain.kill();
    fs.rmSync(TMP, { recursive: true, force: true });
  }
  console.log(failures ? `${failures} failure(s)` : 'web page: all checks passed');
  process.exit(failures ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
