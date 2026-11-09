// Exercise the real audit CLI against browser errors without any retail data.
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../..');
const parent=path.join(root,'build-web-tests/audit-browser');
fs.mkdirSync(parent,{recursive:true});
const out=fs.mkdtempSync(path.join(parent,'case-'));
const fixture=`<!doctype html><link rel="icon" href="/favicon.ico"><body data-ready="1">
<p id="disc-summary">Audit fixture</p><button id="play">Play</button><script>
const state={running:false}; const nfl2k5Log=[]; function log(line){nfl2k5Log.push(line);}
document.getElementById('play').onclick=()=>{
  const splice=auditPending.splice.bind(auditPending);
  auditPending.splice=async(...args)=>{
    await new Promise(resolve=>setTimeout(resolve,1500));
    return splice(...args);
  };
  log('[FILE] open failed: CACHE/LocalCache08.bin','stderr');
  log('[WebGPU] device ready (depth32float-stencil8 yes)','stderr');
  log('[TODO] guest site 0042E694','stderr');
  log('[WebGPU] device error 1: Audit fixture runtime failure','stderr');
  console.warn('WebGPU is experimental');
  console.warn('Error while validating [RenderPipelineDescriptor]');
  console.error('Audit fixture console failure');
  setTimeout(()=>{throw Error('Audit fixture page failure');},0);
};</script>`;
const server=http.createServer((req,res)=>{
  if(req.url==='/favicon.ico'){res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type','text/html');res.end(fixture);
});
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  try{
    const script=path.join(out,'commands.json');
    fs.writeFileSync(script,JSON.stringify([
      {action:'begin',id:'injected-errors'}, {action:'play'}, {action:'wait',ms:1500},
      {action:'end',result:'pass'}, {action:'close'},
    ]));
    const args=[path.join(root,'tools/audit-web-modes.cjs'),
      '--profile',path.join(out,'profile'),'--out',out,'--script',script,
      '--url',`http://127.0.0.1:${server.address().port}/`,
      '--executable',process.env.CHROME_BIN||chromium.executablePath()];
    const result=await new Promise((resolve,reject)=>{
      const child=spawn(process.execPath,args,{cwd:root,env:process.env,stdio:['ignore','pipe','pipe'],timeout:120000});
      let output='';
      child.stdout.on('data',chunk=>{output+=chunk;});child.stderr.on('data',chunk=>{output+=chunk;});
      child.on('error',reject);child.on('close',code=>resolve({code,output}));
    });
    assert.equal(result.code,1,result.output);
    const report=JSON.parse(fs.readFileSync(path.join(out,'report.json'),'utf8'));
    assert.ok(report.browserVersion);
    assert.equal(report.cases[0].requestedResult,'pass');
    assert.equal(report.cases[0].result,'fail');
    for(const text of ['RenderPipelineDescriptor','console failure','page failure','runtime failure'])
      assert.ok(report.cases[0].failures.some(row=>row.line.includes(text)),text);
    assert.ok(report.cases[0].diagnostics.some(row=>row.line.includes('[TODO]')));
    assert.ok(!report.failures.some(row=>/CACHE|device ready|experimental|TODO/.test(row.line)));
    assert.ok(!report.failures.some(row=>(row.url||'').endsWith('/favicon.ico')));
    const log=fs.readFileSync(path.join(out,'runtime.ndjson'),'utf8').trim().split('\n').map(JSON.parse);
    assert.ok(log.some(row=>row.kind==='browser-warning'&&(row.url||'').endsWith('/favicon.ico')));
    console.log('PASS real audit CLI records browser failures, rejects a false pass, and exits unsuccessfully');
  }finally{await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
