// Browser saves through the real C/WasmFS OPFS mount, plus portable backup,
// validation, rollback, crash recovery and origin-wide session exclusion.
// node tests/web/test_browser_saves.js <smoke build directory>
'use strict';
const {chromium} = require('playwright');
const {spawn} = require('child_process');
const path = require('path');
const fs = require('fs');
const assert = require('assert/strict');
const ROOT = path.resolve(__dirname, '../..');
const DIR = path.resolve(process.argv[2] || path.join(ROOT, 'build-web-tests/smoke'));
const URL = 'http://127.0.0.1:18768';
const SAVE = 'saves/UDATA/53450030/0123456789ab/SAVEGAME.DAT';
const EXPECTED = [0,255,128,1,2,13,10,42];
const check = (value, label) => { assert.ok(value, label); console.log('ok:', label); };
async function put(page, files) {
  await page.evaluate(async files => {
    const root = await navigator.storage.getDirectory();
    for (const [path, bytes] of Object.entries(files)) {
      const parts = path.split('/'), name = parts.pop(); let dir = root;
      for (const p of parts) dir = await dir.getDirectoryHandle(p, {create:true});
      const w = await (await dir.getFileHandle(name, {create:true})).createWritable();
      await w.write(new Uint8Array(bytes)); await w.close();
    }
  }, files);
}
async function get(page, path) {
  return page.evaluate(async path => {
    try {
      const parts = path.split('/'), name = parts.pop(); let dir = await navigator.storage.getDirectory();
      for (const p of parts) dir = await dir.getDirectoryHandle(p);
      return Array.from(new Uint8Array(await (await (await dir.getFileHandle(name)).getFile()).arrayBuffer()));
    } catch (e) { if (e.name === 'NotFoundError') return null; throw e; }
  }, path);
}
async function run(page, action, archive) {
  return page.evaluate(async ({action,archive}) => {
    const progress = [];
    try { return {result:await NFL2K5Storage.withLock(() => NFL2K5Storage.run(action,
      archive ? new File([JSON.stringify(archive)], 'backup.json') : undefined, text => progress.push(text)))}; }
    catch (e) { return {error:e.message, code:e.code, progress}; }
  }, {action,archive});
}
async function cStorage(page, mode) {
  await page.goto(`${URL}/smoke.html?env=SMOKE_STORAGE=${mode}`);
  await page.click('#start');
  await page.waitForFunction(mode => smokeLog.some(s => s === `[SMOKE] storage ${mode === 'write' ? 'write durable' : 'read exact'}`), mode, {timeout:30000});
}
(async () => {
  const server = spawn('python3', [path.join(ROOT, 'tools/serve-web.py'), DIR, '--port', '18768'],
    {env:{...process.env,NFL2K5_SERVE_QUIET:'1'},stdio:['ignore','pipe','inherit']});
  let browser;
  try {
    await new Promise((resolve,reject) => {server.stdout.on('data',d => /Serving/.test(d) && resolve()); server.on('error',reject);});
    browser = await chromium.launch();
    const context = await browser.newContext(), page = await context.newPage();
    await cStorage(page, 'write');
    check(JSON.stringify(await get(page,SAVE)) === JSON.stringify(EXPECTED), 'C runtime writes exact binary bytes into persistent OPFS');
    await cStorage(page, 'read');
    check(true,'C runtime reads the save after navigation and a fresh WasmFS mount');
    // Leave the runtime before managing saves, as the launcher requires.
    await page.goto(`${URL}/smoke.html`);
    await page.addScriptTag({url:URL+'/save-format.js'});
    check(await page.evaluate(() => {
      const bytes = new Uint8Array(4*1024*1024), F = NFL2K5SaveFormat;
      return F.validate({type:'nfl2k5-browser-save',version:1,files:[{path:'saves/large',size:bytes.length,sha256:'0'.repeat(64),data:F.encode(bytes)}]}).bytes === bytes.length;
    }), 'multi-megabyte base64 validation stays within browser regexp limits');
    await put(page, {'controls.ini':[65,10], 'saves/日本語/empty':[], 'original/disc/sentinel':[7,8,9]});
    const archive = await page.evaluate(async () => {
      const result = await NFL2K5Storage.withLock(() => NFL2K5Storage.run('export'));
      return JSON.parse(await result.blob.text());
    });
    check(archive.files.length === 3 && archive.files.every(f => !f.path.startsWith('original/')), 'backup includes binary saves, settings and empty Unicode files; excludes disc');
    await put(page, {[SAVE]:[99], 'controls.ini':[66], 'saves/unrelated':[11]});
    check(!(await run(page,'restore',archive)).error,'restore validates and commits backup');
    assert.deepEqual(await get(page,SAVE),EXPECTED);
    assert.deepEqual(await get(page,'saves/unrelated'),[11]);
    assert.deepEqual(await get(page,'original/disc/sentinel'),[7,8,9]);
    check(true,'restore replaces matching bytes and preserves unrelated saves and disc');
    await cStorage(page, 'read');
    check(true,'C runtime loads browser-restored save after a fresh mount');
    await page.goto(`${URL}/smoke.html`);
    for (const [label, mutate] of [
      ['path traversal', a => a.files[0].path = 'saves/../original/disc/sentinel'],
      ['disc path', a => a.files[0].path = 'original/disc/sentinel'],
      ['duplicate path', a => a.files.push({...a.files[0]})],
      ['case alias', a => a.files.push({...a.files[1],path:a.files[0].path.toUpperCase()})],
      ['parent-file collision', a => a.files.push({...a.files[0],path:SAVE+'/child'})],
      ['oversize metadata', a => a.files[0].size = 33*1024*1024],
      ['invalid base64', a => a.files[0].data = '!'.repeat(a.files[0].data.length)],
      ['corrupt checksum', a => a.files[0].sha256 = '0'.repeat(64)],
    ]) {
      const bad = structuredClone(archive); mutate(bad);
      check(!!(await run(page,'restore',bad)).error, 'rejects '+label);
      assert.deepEqual(await get(page,SAVE),EXPECTED);
    }
    // Inject a failure only on the first live-file write, after verified staging.
    await context.route('**/save-worker.js', route => route.fulfill({contentType:'text/javascript',headers:{'Cross-Origin-Embedder-Policy':'require-corp'},body:`
      const realWritable = FileSystemFileHandle.prototype.createWritable;
      let injected = false;
      FileSystemFileHandle.prototype.createWritable = function(...args) {
        if (this.name === 'SAVEGAME.DAT' && !injected) { injected=true; throw new DOMException('Injected quota failure','QuotaExceededError'); }
        return realWritable.apply(this,args);
      };\n` + fs.readFileSync(path.join(DIR,'save-worker.js'),'utf8')}));
    const failed = await run(page,'restore',archive);
    if (!failed.error?.includes('Previous saves have been restored')) console.log('write failure result:',failed);
    check(failed.error?.includes('Previous saves have been restored'), 'mid-commit write failure rolls back the whole restore');
    assert.deepEqual(await get(page,SAVE),EXPECTED);
    await context.unroute('**/save-worker.js');
    // Simulate a tab dying with a durable writing journal and partial output.
    const stage = '.nfl2k5-save-restore';
    const journal = {type:'nfl2k5-restore',version:1,state:'writing',files:[
      {path:SAVE,hadOriginal:true},{path:'saves/new-dir/partial',hadOriginal:false}],directories:['saves/new-dir']};
    await put(page,{[SAVE]:[22], 'saves/new-dir/partial':[33], [stage+'/old/0']:EXPECTED,
      [stage+'/journal.json']:Array.from(Buffer.from(JSON.stringify(journal)))});
    await page.reload();
    check(!(await run(page,'status')).error,'fresh page recovers an interrupted restore before using storage');
    assert.deepEqual(await get(page,SAVE),EXPECTED);
    assert.equal(await get(page,'saves/new-dir/partial'),null);
    check(true,'recovery restores retained originals and removes newly created partial files');
    journal.state = 'committed';
    await put(page,{[stage+'/journal.json']:Array.from(Buffer.from(JSON.stringify(journal))), [SAVE]:[44]});
    check(!(await run(page,'recover')).error,'committed journal is cleaned up without rollback');
    assert.deepEqual(await get(page,SAVE),[44]);
    const other = await context.newPage(); await other.goto(`${URL}/smoke.html`);
    await page.evaluate(async () => {window.releaseSession = await NFL2K5Storage.acquireSession();});
    check((await run(other,'restore',archive)).code === 'BUSY','another tab cannot restore during a game session');
    await page.evaluate(() => window.releaseSession());
    check(!(await run(other,'restore',archive)).error,'storage becomes available when the game session releases its lock');
    journal.state = 'writing';
    await put(other,{[stage+'/journal.json']:Array.from(Buffer.from(JSON.stringify(journal)))});
    const broken = await run(other,'recover');
    check(broken.code === 'RECOVERY' && !!(await get(other,stage+'/journal.json')), 'failed recovery reports a stable error code and retains the recovery journal');
    assert.deepEqual(await get(other,SAVE),EXPECTED);
    await context.close();
    console.log('browser save tests passed');
  } finally { await browser?.close(); server.kill(); }
})().catch(e => {console.error(e);process.exitCode=1;});
