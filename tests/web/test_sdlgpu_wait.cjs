// Verify the real browser-suite wait policy with a deterministic clock.
'use strict';
const assert=require('node:assert/strict');
const {waitForSuiteProgress}=require('../../external/xboxrecomp/tests/sdlgpu_web/test_wait.cjs');
(async()=>{
  let time=0;
  const clock={now:()=>time,sleep:async ms=>{time+=ms;}};
  await waitForSuiteProgress(async()=>({count:Math.floor(time/130),done:time>=130000}),clock);
  assert(time>=130000 && time<300000);
  console.log('ok: progressing software-GPU suite can finish beyond the former 120-second deadline');
  time=0;
  await assert.rejects(waitForSuiteProgress(async()=>({count:3,done:false}),{...clock,idleMs:1000,totalMs:5000}),/no progress/);
  assert.equal(time,1000);
  console.log('ok: stalled suite fails at the idle limit');
  time=0;
  await assert.rejects(waitForSuiteProgress(async()=>({count:Math.floor(time/250),done:false}),{...clock,idleMs:1000,totalMs:1500}),/total time/);
  assert.equal(time,1500);
  console.log('ok: continuing log output cannot evade the absolute suite limit');
  time=0;
  await assert.rejects(waitForSuiteProgress(async()=>null,{...clock,idleMs:1000,totalMs:5000}),/no progress/);
  const failure=await waitForSuiteProgress(async()=>({count:1,done:true,error:'FAILED fixture'}),clock);
  assert.equal(failure.error,'FAILED fixture');
  console.log('ok: missing startup progress fails and terminal failure state remains available to the runner');
  await assert.rejects(waitForSuiteProgress(()=>new Promise(()=>{}),{idleMs:10,totalMs:100}),/no progress.*state read/);
  await assert.rejects(waitForSuiteProgress(()=>new Promise(()=>{}),{idleMs:100,totalMs:10}),/total time.*state read/);
  console.log('ok: a hung browser-state read cannot evade either deadline');
})().catch(error=>{console.error(error);process.exitCode=1;});
