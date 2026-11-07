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
  await page.click('#play');
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
      check(await page.$eval('#play', (b) => b.disabled), 'Play disabled before a disc is imported');
      await page.setInputFiles('#file-image', path.join(TMP, 'test.xiso'));
      check(!!(await waitLog(page, /^Imported 7 files/, 60000)), 'image import finished');
      check(sameDisc(await opfsDisc(page), want, true), 'image: every file in OPFS matches the disc, empty dirs kept');
      check(!(await page.$eval('#play', (b) => b.disabled)), 'Play enabled after import');
      await playAndCheckXbe(page, want, 'image');
      await page.reload();
      await page.waitForSelector('body[data-ready="1"]');
      check(await page.isVisible('#disc-installed') &&
            /7 files/.test(await page.textContent('#disc-summary')), 'disc still installed after reload');
      check(/not one this build runs/.test(await page.textContent('#disc-xbe')),
            'non-retail default.xbe is flagged');
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
