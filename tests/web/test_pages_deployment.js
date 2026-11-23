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
    assert.equal(await page.locator('footer a[href="third-party-notices.txt"]').count(),1);
    const notices=await page.request.get(new URL('third-party-notices.txt',base).href);
    assert.ok(notices.ok() && (await notices.text()).includes('Copyright (C) 2012-2023 Yann Collet'));
    console.log('ok: published runtime includes its linked XXH64 license notice');
    const result=await page.evaluate(async()=>{
      const manifest=await (await fetch('runtime.json',{cache:'no-cache'})).json();
      const urls=['NFL2K5.js','NFL2K5.wasm'].map(name=>new URL(NFL2K5Launch.runtimeAsset(name),document.baseURI));
      const [js,response]=await Promise.all(urls.map(url=>fetch(url)));
      const type=response.headers.get('Content-Type'), bytes=await response.arrayBuffer();
      const digest=async data=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data)),x=>x.toString(16).padStart(2,'0')).join('');
      const hash=await digest(bytes),jsHash=await digest(await js.arrayBuffer());
      const compiled=await WebAssembly.compile(bytes);
      const storage=await NFL2K5Storage.withLock(()=>NFL2K5Storage.run('status'));
      return {type,size:bytes.byteLength,hash,jsHash,builds:urls.map(url=>url.searchParams.get('build')),
        manifest,imports:WebAssembly.Module.imports(compiled).length,storage};
    });
    assert.ok(result.type.startsWith('application/wasm'));
    assert.equal(result.size,result.manifest.wasmBytes); assert.equal(result.hash,result.manifest.sha256);
    assert.equal(result.jsHash,result.manifest.jsSha256);
    assert.match(result.manifest.runtimeBuild,/^[a-f0-9]{64}$/);
    assert.deepEqual(result.builds,[result.manifest.runtimeBuild,result.manifest.runtimeBuild]);
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
