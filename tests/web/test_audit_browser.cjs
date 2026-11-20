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
let playCount=0;
document.getElementById('play').onclick=()=>{
  const retry=new URLSearchParams(location.search).get('retry');
  if(retry==='1'||retry==='delayed'){
    void (async()=>{
      const root=await navigator.storage.getDirectory();let presses=0,checking=false;
      const timer=setInterval(async()=>{
        if(checking)return;checking=true;
        try{
          const file=await root.getFileHandle('mode-audit-press.txt');
          const text=await (await file.getFile()).text();await root.removeEntry('mode-audit-press.txt');
          if(text==='start'&&++presses===3){
            clearInterval(timer);
            setTimeout(()=>log('[MODE] retry-ready presses=3','stderr'),retry==='delayed'?1200:0);
          }
        }catch{}finally{checking=false;}
      },50);
    })();return;
  }
  if(new URLSearchParams(location.search).get('wait')==='1'){
    const phase=++playCount;setTimeout(()=>log('[MODE] phase='+phase,'stderr'),50);return;
  }
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
  function auditPageFailure(){throw Error('Audit fixture page failure');}
  setTimeout(auditPageFailure,0);
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
      {action:'begin',id:'injected-errors'}, {action:'play'},
      {action:'wait-log',pattern:'Audit fixture runtime failure',ms:10000},
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
    assert.ok(report.cases[0].failures.some(row=>row.line.includes('auditPageFailure')), 'page exception stack retained');
    assert.ok(report.cases[0].diagnostics.some(row=>row.line.includes('[TODO]')));
    assert.ok(!report.failures.some(row=>/CACHE|device ready|experimental|TODO/.test(row.line)));
    assert.ok(!report.failures.some(row=>(row.url||'').endsWith('/favicon.ico')));
    const log=fs.readFileSync(path.join(out,'runtime.ndjson'),'utf8').trim().split('\n').map(JSON.parse);
    assert.ok(log.some(row=>row.kind==='browser-warning'&&(row.url||'').endsWith('/favicon.ico')));
    console.log('PASS real audit CLI records browser failures, rejects a false pass, and exits unsuccessfully');

    async function runWaitAudit(name,commands,interactive=false,query='wait=1'){
      const dir=path.join(out,name);fs.mkdirSync(dir);
      const script=path.join(dir,'commands.json');fs.writeFileSync(script,JSON.stringify(commands));
      const args=[path.join(root,'tools/audit-web-modes.cjs'),'--profile',path.join(dir,'profile'),
        '--out',dir,'--url',`http://127.0.0.1:${server.address().port}/?${query}`,
        '--executable',process.env.CHROME_BIN||chromium.executablePath(),
        ...(!interactive?['--script',script]:[])];
      const result=await new Promise((resolve,reject)=>{
        const child=spawn(process.execPath,args,{cwd:root,env:process.env,stdio:[interactive?'pipe':'ignore','pipe','pipe'],timeout:30000});
        let output='';child.stdout.on('data',chunk=>{output+=chunk;});child.stderr.on('data',chunk=>{output+=chunk;});
        child.on('error',reject);child.on('close',code=>resolve({code,output}));
        // Leave stdin open: the CLI's close command must release its own handle.
        if(interactive)child.stdin.write(commands.map(c=>JSON.stringify(c)).join('\n')+'\n');
      });
      return {...result,report:JSON.parse(fs.readFileSync(path.join(dir,'report.json'),'utf8'))};
    }
    const waiting=await runWaitAudit('transitions',[
      {action:'begin',id:'first'}, {action:'play'}, {action:'wait-log',pattern:'phase=1',ms:5000}, {action:'end',result:'pass'},
      {action:'begin',id:'second'}, {action:'play'}, {action:'wait-log',pattern:'phase=',ms:5000}, {action:'end',result:'pass'},
      {action:'begin',id:'stale-must-fail'}, {action:'play'}, {action:'wait-log',pattern:'phase=1',ms:500},
      {action:'end',result:'pass'}, {action:'close'},
    ]);
    assert.equal(waiting.code,1,waiting.output);
    assert.equal(waiting.report.cases[0].result,'pass');assert.equal(waiting.report.cases[1].result,'pass');
    const matches=waiting.output.split(/\r?\n/).filter(l=>l.startsWith('RESULT ')).map(l=>JSON.parse(l.slice(7))).filter(x=>x?.matched);
    assert.deepEqual(matches.map(x=>x.matched),['[MODE] phase=1','[MODE] phase=2']);
    assert.ok(waiting.report.failures.some(row=>row.kind==='audit-error'&&row.line.includes('timed out')));
    assert.equal(waiting.report.cases[2].requestedResult,undefined,'timeout must stop the remaining script');
    const closed=await runWaitAudit('interactive-close',[
      {action:'begin',id:'interactive'}, {action:'play'}, {action:'wait-log',pattern:'phase=1',ms:5000},
      {action:'end',result:'pass'}, {action:'close'},
    ],true);
    assert.equal(closed.code,0,closed.output);assert.ok(closed.report.ended);
    for(const delay of [false,true]){
      const retry=await runWaitAudit('retry-transition'+(delay?'-delayed':''),[
        {action:'begin',id:'retry'}, {action:'play'},
        {action:'wait-log',pattern:'retry-ready',button:'start',everyMs:800,ms:10000},
        {action:'end',result:'pass'}, {action:'close'},
      ],false,'retry='+(delay?'delayed':'1'));
      assert.equal(retry.code,0,retry.output);assert.equal(retry.report.cases[0].result,'pass');
      const row=retry.output.split(/\r?\n/).filter(l=>l.startsWith('RESULT ')).map(l=>JSON.parse(l.slice(7))).find(x=>x?.matched);
      assert.equal(row.matched,'[MODE] retry-ready presses=3');
      // The result counts writes; the marker counts consumed inputs. OPFS,
      // browser scheduling and log delivery can leave another write in flight.
      assert.ok(Number.isInteger(row.presses)&&row.presses>=3&&row.presses<=Math.ceil(10000/800),retry.output);
    }
    console.log('PASS fresh transition waits, stale-marker timeout, bounded button retries, and interactive close with open stdin');
  }finally{await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
