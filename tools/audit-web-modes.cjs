// Interactive or JSON-scripted retail mode audit against a locally built game.
// Reuses a dedicated Playwright profile with an already imported user-owned disc.
// node tools/audit-web-modes.cjs --profile build-web-render-lab --url http://127.0.0.1:8081/
'use strict';
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),readline=require('node:readline');
const {isAuditFailure,caseDiagnostics}=require('./web-audit-diagnostics.cjs');
const args=process.argv.slice(2);
const option=(name,fallback)=>{const i=args.indexOf('--'+name);return i<0?fallback:args[i+1];};
const origin=option('url','http://127.0.0.1:8080/');
const out=path.resolve(option('out','build-web-tests/mode-audit'));
const profile=path.resolve(option('profile','build-web-mode-audit'));
const executablePath=option('executable',process.env.CHROME_BIN);
const script=option('script');
const captureMemory=args.includes('--capture-memory');
fs.mkdirSync(out,{recursive:true});
const report={started:new Date().toISOString(),url:origin,cases:[]};
const events=[];
let context,page,flushing=null,currentCase=null;
const reportPath=path.join(out,'report.json');
const writeReport=()=>{
  report.failures=events.filter(isAuditFailure);
  fs.writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n');
};
function browserEvent(line,kind,location){
  const row={hostTime:new Date().toISOString(),line,kind,...(location?.url?{url:location.url}:{})};
  events.push(row);fs.appendFileSync(path.join(out,'runtime.ndjson'),JSON.stringify(row)+'\n');
}
function flush(){
  // Case boundaries must wait for an existing timer-driven drain. Returning
  // early here could mark a case passed before its queued GPU error arrived.
  if(flushing)return flushing;
  if(!page||page.isClosed())return Promise.resolve();
  flushing=(async()=>{
    try{
      const rows=await page.evaluate(()=>window.auditPending?.splice(0)||[]);
      for(const row of rows){
        row.hostTime=new Date().toISOString();events.push(row);
        const offset=/offset ([+-]\d+) from Xbox base/.exec(row.line);
        if(offset)report.guestMemoryOffset=Number(offset[1]);
      }
      if(rows.length)fs.appendFileSync(path.join(out,'runtime.ndjson'),rows.map(r=>JSON.stringify(r)+'\n').join(''));
    }catch{}
  })().finally(()=>{flushing=null;});
  return flushing;
}
async function prepare(url=origin){
  await flush();
  const target=new URL(url);
  target.searchParams.append('env','NFL2K5_MODE_TRACE=1');
  target.searchParams.append('env','NFL2K5_NO_HOST_PAD=1');
  target.searchParams.append('env','NFL2K5_PRESS_FILE=/nfl2k5/mode-audit-press.txt');
  await page.goto(target.href);
  await page.waitForSelector('body[data-ready="1"]',{timeout:60000});
  report.gpu=await page.evaluate(async()=>{
    try{
      const adapter=await navigator.gpu?.requestAdapter();
      if(!adapter)return null;
      const info=adapter.info;
      return {vendor:info?.vendor,architecture:info?.architecture,device:info?.device,
        description:info?.description,isFallbackAdapter:info?.isFallbackAdapter};
    }catch{return null;}
  });
  await page.evaluate(()=>{
    window.auditPending=[];
    const previous=log;
    log=function(line,kind){auditPending.push({at:performance.now(),line,kind});previous(line,kind);};
  });
  if(captureMemory){
    await page.addScriptTag({url:new URL('NFL2K5.js',target).href});
    await page.evaluate(()=>{
      const factory=createNFL2K5;
      window.createNFL2K5=options=>factory({...options,instantiateWasm:(imports,receive)=>{
        window.auditMemory=Object.values(imports).flatMap(v=>Object.values(v)).find(v=>v instanceof WebAssembly.Memory);
        WebAssembly.instantiateStreaming(fetch('NFL2K5.wasm'),imports).then(r=>receive(r.instance,r.module)).catch(e=>options.onAbort?.(e.message));
        return {};
      }});
    });
  }
  return {disc:await page.locator('#disc-summary').textContent(),ready:!(await page.locator('#play').isDisabled())};
}
async function press(buttons){
  if(!/^(?:a|b|x|y|start|back|up|down|left|right|lt|rt|lb|rb|black|white|l3|r3)(?:\s+(?:a|b|x|y|start|back|up|down|left|right|lt|rt|lb|rb|black|white|l3|r3))*$/i.test(buttons))throw Error('Unknown scripted button');
  await page.evaluate(async text=>{
    const root=await navigator.storage.getDirectory();
    const file=await root.getFileHandle('mode-audit-press.txt',{create:true});
    const writer=await file.createWritable();await writer.write(text);await writer.close();
  },buttons);
  await page.waitForTimeout(700);
}
async function act(c){
  let result;
  switch(c.action){
    case 'play':await page.click('#play');result='started';break;
    case 'press':await press(c.buttons);result='sent';break;
    case 'key':
      await page.focus('#canvas');
      await page.keyboard.down(c.key);
      try{await page.waitForTimeout(Math.min(c.ms||200,5000));}
      finally{await page.keyboard.up(c.key);}
      await page.waitForTimeout(Math.min(c.gap ?? 700,5000));result='key sent';break;
    case 'wait':await page.waitForTimeout(Math.min(c.ms||1000,60000));result='waited';break;
    case 'begin':
      await flush();currentCase={id:c.id,title:c.title||c.id,started:new Date().toISOString(),eventStart:events.length,screenshots:[]};
      report.cases.push(currentCase);writeReport();result='case started';break;
    case 'shot':{
      const tag=String(c.tag||currentCase?.id||'screen').replace(/[^a-zA-Z0-9_.-]/g,'-');
      const file=tag+'.png';await page.locator('#screen').screenshot({path:path.join(out,file)});
      if(currentCase)currentCase.screenshots.push(file);writeReport();result={screenshot:file};break;
    }
    case 'end':
      if(!currentCase)throw Error('No active case');
      if(!['pass','fail','partial','blocked'].includes(c.result))throw Error('Result must be pass, fail, partial, or blocked');
      await flush();Object.assign(currentCase,{requestedResult:c.result,detail:c.detail||'',ended:new Date().toISOString(),
        ...caseDiagnostics(c.result,events.slice(currentCase.eventStart))});
      writeReport();result=currentCase;currentCase=null;break;
    case 'reload':result=await prepare(c.url||origin);break;
    case 'peek':
      await flush();
      if(report.guestMemoryOffset===undefined)throw Error('Guest memory offset has not been reported yet');
      result=await page.evaluate(({va,words,offset})=>{
        if(!window.auditMemory)throw Error('Restart the harness with --capture-memory');
        const view=new DataView(auditMemory.buffer),n=Math.min(words||8,256),rows=[];
        for(let i=0;i<n;i++)rows.push({va:((va+i*4)>>>0).toString(16),value:view.getUint32(((va+i*4)>>>0)+offset,true)});
        return rows;
      },{...c,offset:report.guestMemoryOffset});break;
    case 'status':
      await flush();result=await page.evaluate(()=>({running:state.running,status:document.querySelector('#launch-status').textContent,
        recent:nfl2k5Log.slice(-12)}));break;
    case 'close':{
      await flush();report.ended=new Date().toISOString();writeReport();
      if(report.failures.length||report.cases.some(c=>c.result==='fail'))process.exitCode=1;
      const closing=context;context=null;await closing.close();return false;
    }
    default:throw Error('Unknown action: '+c.action);
  }
  console.log('RESULT',JSON.stringify(result));return true;
}
(async()=>{
  context=await chromium.launchPersistentContext(profile,{executablePath,headless:!args.includes('--headed'),viewport:{width:1280,height:900}});
  page=await context.newPage();for(const old of context.pages())if(old!==page)await old.close();
  page.on('pageerror',e=>browserEvent('PAGEERROR '+e.message,'pageerror'));
  page.on('crash',()=>browserEvent('PAGEERROR browser page crashed','pageerror'));
  page.on('console',message=>{
    if(!['warning','error'].includes(message.type()))return;
    const location=message.location();
    // Chrome may request an optional favicon even though the launcher declares none.
    const favicon=/\/favicon\.ico(?:[?#]|$)/.test(location.url||'');
    const kind=message.type()==='error'&&!favicon?'browser-error':'browser-warning';
    browserEvent(`BROWSER ${message.type().toUpperCase()} ${message.text()}`,kind,location);
  });
  report.browserVersion=context.browser()?.version();
  report.viewport={width:1280,height:900};
  console.log('READY',JSON.stringify(await prepare()));writeReport();
  const timer=setInterval(flush,1000);
  try{
    if(script){for(const c of JSON.parse(fs.readFileSync(script,'utf8')))if(!await act(c))return;await act({action:'close'});}
    else{for await(const line of readline.createInterface({input:process.stdin,terminal:false})){
      try{if(!await act(JSON.parse(line)))return;}catch(e){console.log('ERROR',e.message);}
    }}
  }finally{clearInterval(timer);await flush();if(context)await context.close();}
})().catch(async e=>{
  console.error(e);process.exitCode=1;
  // Startup can fail before the command loop's finally block is reached.
  if(context){const closing=context;context=null;await closing.close();}
});
