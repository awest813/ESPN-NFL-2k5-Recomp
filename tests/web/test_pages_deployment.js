// Verify the real project URL, its isolation service worker and runtime bytes.
// Uses fresh browser storage; no visitor's existing library is accessed.
'use strict';
const {chromium}=require('playwright');
const assert=require('assert/strict');
const base=process.argv[2] || 'https://awest813.github.io/ESPN-NFL-2k5-Recomp/';
(async()=>{
  const browser=await chromium.launch();
  try {
    const context=await browser.newContext(), page=await context.newPage();
    const errors=[]; page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base);
    await page.waitForSelector('body[data-ready="1"]',{timeout:60000});
    assert.ok(await page.evaluate(()=>crossOriginIsolated && !!navigator.storage?.getDirectory));
    console.log('ok: published project URL is isolated and OPFS is available');
    assert.equal(await page.locator('#chk-build').getAttribute('data-ok'),'yes');
    const result=await page.evaluate(async()=>{
      const manifest=await (await fetch('runtime.json',{cache:'no-cache'})).json();
      const response=await fetch('NFL2K5.wasm',{cache:'no-cache'});
      const type=response.headers.get('Content-Type'), bytes=await response.arrayBuffer();
      const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('');
      const compiled=await WebAssembly.compile(bytes);
      const storage=await NFL2K5Storage.withLock(()=>NFL2K5Storage.run('status'));
      return {type,size:bytes.byteLength,hash,manifest,imports:WebAssembly.Module.imports(compiled).length,storage};
    });
    assert.ok(result.type.startsWith('application/wasm'));
    assert.equal(result.size,result.manifest.wasmBytes); assert.equal(result.hash,result.manifest.sha256);
    assert.ok(result.imports>0);
    console.log('ok: published Wasm MIME type, byte count, SHA-256 and browser compilation');
    assert.equal(result.storage.files,0);
    console.log('ok: project-relative save worker loads under the isolation service worker');
    await page.setViewportSize({width:390,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    assert.deepEqual(errors,[]);
    console.log('ok: mobile layout fits and no page errors');
    console.log('Pages deployment checks passed:',base);
    await context.close();
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
