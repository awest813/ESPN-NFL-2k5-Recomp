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

for(const failure of [
  {line:'[WebGPU] device error 1: Attachment format does not match pipeline'},
  {line:'[WebGPU] device lost: Unknown'},
  {line:'[WebGPU] download: mapped range unavailable'},
  {line:'[WebGPU] fence: work completion failed'},
  {line:'[SDLGPU] queued draws dropped: rejected command buffer'},
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
console.log('PASS retail diagnostics retain expected probes and reject browser/GPU false passes');
