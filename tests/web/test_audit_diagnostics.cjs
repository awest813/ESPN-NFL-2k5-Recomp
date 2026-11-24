'use strict';
const assert=require('node:assert/strict');
const {isAuditFailure,caseDiagnostics}=require('../../tools/web-audit-diagnostics.cjs');

// Representative retail probes/counters must not mask genuine errors or
// cause every completed game case to fail because a cache file is absent.
const benign=[
  {line:"[FILE] -> 0xC0000034 FAILED path='/disc/CACHE/LocalCache08.bin'"},
  {line:'[AUDIO] submits=31272 dropped=104 underruns=0'},
  {line:'[WebGPU] device ready (depth32float-stencil8 yes, surface format 27)'},
  {line:'[TODO] guest site 0042E694'},
  {line:'WebGPU is experimental',kind:'browser-warning'},
  {line:'BROWSER ERROR Failed to load resource: 404',kind:'browser-warning',url:'http://localhost/favicon.ico'},
];
assert.ok(benign.every(row=>!isAuditFailure(row)));
const good=caseDiagnostics('pass',benign);
assert.equal(good.result,'pass');
assert.equal(good.failures.length,0);
assert.deepEqual(good.diagnostics,[benign[3]]);
assert.equal(good.frameWindows,undefined);
const transition={at:10,line:'[MODE-FSM] #4 push object=00A84B18 descriptor=004E7EC0'};
const timing='  [SDLGPU] 5s: frames 150 30.0 fps | flip intervals 149 over-budget 31 over-50ms 3 over-100ms 1 worst 124.20 ms';
const timed=caseDiagnostics('pass',[transition,{at:11,line:timing},{at:5012,line:timing+' (texture 1.00 vertex 2.00 submit 100.00)'}]);
assert.deepEqual(timed.frameWindows[0],{at:11,frames:150,fps:30,intervals:149,overBudget:31,
  over50ms:3,over100ms:1,worstMs:124.2,transitions:[transition]});
assert.deepEqual(timed.frameWindows[1].transitions,[]);
assert.deepEqual(timed.frameWindows[1].worstFrameMs,{texture:1,vertex:2,submit:100});
assert.equal(timed.result,'pass');
const detailedTiming='  [SDLGPU] 5s: frames 38 7.6 fps | ms/frame texture 79.36 vertex 23.26 submit 22.67'
  +' | hash 0.25 MiB/frame verify 120.27 decode 2.03 readback 0.00 gpu-copy 1.00'
  +' | texture-ms/frame verify 59.27 decode 1.23 | flip intervals 38 over-budget 38 over-50ms 38 over-100ms 25'
  +' worst 239.83 ms (texture 141.18 vertex 5.57 submit 81.57)';
const [detailed]=caseDiagnostics('pass',[{at:5020,line:detailedTiming}]).frameWindows;
assert.deepEqual(detailed.rendererMsPerFrame,{texture:79.36,vertex:23.26,submit:22.67});
assert.deepEqual(detailed.texturePerFrame,{hashMiB:0.25,verifyMiB:120.27,verifyMs:59.27,decodeMs:1.23});
assert.deepEqual(detailed.worstFrameMs,{texture:141.18,vertex:5.57,submit:81.57});

for(const failure of [
  {line:'The game stopped: RuntimeError: unreachable',kind:'error'},
  {line:'AUDIT wait-log timed out after 1000 ms: mode-ready',kind:'audit-error'},
  {line:'[WebGPU] device error 1: Attachment format does not match pipeline'},
  {line:'[WebGPU] device lost: Unknown'},
  {line:'[WebGPU] download: mapped range unavailable'},
  {line:'[WebGPU] fence: work completion failed'},
  {line:'[SDLGPU] queued draws dropped: rejected command buffer'},
  {line:'[AUDIO] AudioWorklet could not start (audio-worklet.js): network error'},
  {line:'[AUDIO] AudioWorklet processor failed'},
  {line:'[AUDIO-UNDERRUN] {"blocks":1,"missingFrames":128}'},
  {line:'missing output frames',kind:'audio-underrun'},
  {line:'[AUDIO] SDL_OpenAudioDeviceStream failed: no device'},
  {line:'[APU-DSP] GP frame did not idle; pc=000123 overruns=1'},
  {line:'[APU-DSP] unsupported EP PCM packet: 4096 bytes'},
  {line:'[APU-DSP] invalid EP FIFO range 00000000..00000000'},
  {line:'PAGEERROR TypeError: worker is undefined'},
  {line:'Error while validating [RenderPipelineDescriptor]',kind:'browser-warning'},
  {line:'Failed to load resource',kind:'browser-error'},
  {line:'Aborted(out of memory)'},
  {line:'RuntimeError: unreachable executed'},
]) {
  const rows=[...benign,failure];
  const result=caseDiagnostics('pass',rows);
  assert.equal(result.result,'fail',failure.line);
  assert.deepEqual(result.failures,[failure]);
  assert.ok(result.diagnostics.includes(failure));
  assert.equal(caseDiagnostics('partial',rows).result,'fail');
  assert.equal(caseDiagnostics('blocked',rows).result,'blocked');
}
assert.equal(caseDiagnostics('fail',benign).result,'fail');
assert.equal(caseDiagnostics('pass',[]).result,'pass'); // previous case errors stay in their own case
console.log('PASS retail diagnostics retain expected probes and reject browser/GPU/audio false passes');

// Run the same serialized callback as Playwright, with page-owned state.
{
  const vm=require('node:vm');
  const {drainAuditRows}=require('../../tools/web-audit-audio.cjs');
  const window={auditPending:[{line:'[TODO] guest site 00000001'}]};
  let clocks=0;
  const context=vm.createContext({window,performance:{timeOrigin:1000000,now:()=>31000+clocks++/4}});
  const drain=(snapshot=false)=>JSON.parse(JSON.stringify(vm.runInContext(`(${drainAuditRows.toString()})(${snapshot})`,context)));
  assert.equal(drain().length,1);assert.deepEqual(drain(),[]);assert.equal(clocks,0);
  const stats={state:'running',underruns:0,underrunFrames:0,maxUnderrunFrames:0};
  const ctx={state:'running',sampleRate:48000,currentTime:30,baseLatency:0.01,outputLatency:0.04,
    getOutputTimestamp:()=>({contextTime:29.95,performanceTime:30950})};
  window.nfl2k5Module={nfl2k5Audio:stats,nfl2k5AudioContext:ctx};
  assert.deepEqual(drain(),[]);assert.equal(clocks,0,'no clock sampling on unchanged periodic polls');
  Object.assign(stats,{underruns:1,underrunFrames:128,maxUnderrunFrames:128,
    firstUnderrunTime:29.01,lastUnderrunTime:29.02,lastUnderrunQueued:0,lastUnderrunRequired:1,queued:1024});
  window.auditPending.push({line:'[APU-SCHEDULE] retained'});
  const snapshot=drain(true);
  assert.equal(snapshot.output.underruns,1);assert.equal(snapshot.context.time,30);
  assert.deepEqual(snapshot.clock,{originMs:1000000,readBeginMs:31000,readEndMs:31000.25,
    outputTimestamp:{contextTime:29.95,performanceTime:30950}});
  assert.equal(window.auditPending.length,1);assert.equal(window.auditAudioUnderruns,0,'snapshot must not acknowledge a new gap');
  let rows=drain();assert.equal(rows.length,2);assert.equal(rows[1].at,31000.75);
  assert.equal(caseDiagnostics('pass',rows).result,'fail');
  const detail=JSON.parse(rows[1].line.slice('[AUDIO-UNDERRUN] '.length));
  assert.deepEqual(detail,{blocks:1,missingFrames:128,maxGapFrames:128,contextTime:30,
    clock:{originMs:1000000,readBeginMs:31000.5,readEndMs:31000.75,outputTimestamp:{contextTime:29.95,performanceTime:30950}},
    firstGapTime:29.01,lastGapTime:29.02,available:0,required:1,queued:1024});
  const oldClocks=clocks;assert.deepEqual(drain(),[]);assert.equal(clocks,oldClocks);
  for(const timestamp of [undefined,()=>{throw Error('unsupported diagnostic');},()=>({contextTime:NaN,performanceTime:1})]) {
    ctx.getOutputTimestamp=timestamp;stats.underruns++;
    rows=drain();assert.equal(caseDiagnostics('pass',rows).result,'fail');
    assert.equal(JSON.parse(rows[0].line.slice('[AUDIO-UNDERRUN] '.length)).clock.outputTimestamp,null);
  }
  ctx.getOutputTimestamp=()=>({contextTime:0,performanceTime:0});stats.underruns++;
  assert.deepEqual(JSON.parse(drain()[0].line.slice('[AUDIO-UNDERRUN] '.length)).clock.outputTimestamp,{contextTime:0,performanceTime:0});
  // A replacement stream may already have gaps at the first poll, even if
  // its cumulative count is equal to or lower than the previous stream's.
  window.nfl2k5Module={nfl2k5Audio:{underruns:1}};assert.equal(drain().length,1);
  window.nfl2k5Module={nfl2k5Audio:{underruns:1}};
  drain(true);assert.equal(drain().length,1,'snapshot must not acknowledge replacement stream');
  window.nfl2k5Module.nfl2k5AudioContext={currentTime:0};
  assert.equal(drain().length,1,'replacement context with retained stats needs a new baseline');
  window.nfl2k5Module={nfl2k5Audio:{underruns:0}};assert.deepEqual(drain(),[]);
  window.nfl2k5Module.nfl2k5Audio.underruns=1;assert.equal(drain().length,1);
  delete window.nfl2k5Module;
  const empty=drain(true);assert.equal(empty.context,null);assert.equal(empty.output,null);
  console.log('PASS audio observation preserves clock anchors, raw output timestamps, failures with unavailable diagnostics, replacement streams and snapshot/drain separation');
}
