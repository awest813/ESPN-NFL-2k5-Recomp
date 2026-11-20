'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const {drainApuTraceRows}=require('../../tools/web-audit-apu-trace.cjs');
const {caseDiagnostics}=require('../../tools/web-audit-diagnostics.cjs');
const dir=path.resolve(process.argv[2]);
const read=name=>{const b=fs.readFileSync(path.join(dir,name));const memory=new SharedArrayBuffer(b.length);new Uint8Array(memory).set(b);return {memory,offset:0};};
const window={nfl2k5Module:{nfl2k5ApuTrace:read('trace.bin')}};
const ctx=vm.createContext({window,SharedArrayBuffer,performance:{now:()=>1234}});
const drain=()=>JSON.parse(JSON.stringify(vm.runInContext(`(${drainApuTraceRows.toString()})()`,ctx)));
const events=rows=>rows.filter(r=>r.kind==='apu-trace').map(r=>JSON.parse(r.line.slice('[APU-TRACE] '.length)));
let rows=drain();assert.equal(rows.length,4097);
assert.equal(caseDiagnostics('pass',rows).result,'fail','lost records must not masquerade as complete history');
assert.ok(rows[0].line.includes('skipped=45904'));
let entries=events(rows);assert.equal(entries.length,4096);
for(const e of entries){const n=BigInt(e.sequence);assert.equal(BigInt(e.startUs),1795210000000000n+n*17n);assert.equal(BigInt(e.endUs)-BigInt(e.startUs),2000n+n%1000n);}
assert.deepEqual(drain(),[]);
// An in-progress overwrite cannot be acknowledged or read as a completed slot.
const trace=window.nfl2k5Module.nfl2k5ApuTrace,u64=new BigUint64Array(trace.memory);
window.auditApuTraceCursor=49999n;
const slot=2+Number(49999n%4096n)*4,guard=Atomics.load(u64,slot);
Atomics.store(u64,slot,guard+1n);rows=drain();assert.equal(events(rows).length,0);assert.equal(window.auditApuTraceCursor,49999n);
assert.equal(rows[0].kind,'apu-trace-status');
Atomics.store(u64,slot,guard);assert.equal(events(drain()).length,1);
// Change the guard during payload reads: the second validation must reject it.
window.auditApuTraceCursor=49999n;let raced=false;
ctx.Atomics={load:(view,index)=>{const value=Atomics.load(view,index);if(!raced&&view.BYTES_PER_ELEMENT===8&&index===slot+1){raced=true;Atomics.store(u64,slot,guard+1n);}return value;}};
assert.equal(events(drain()).length,0);assert.equal(window.auditApuTraceCursor,49999n);
ctx.Atomics=Atomics;Atomics.store(u64,slot,guard);assert.equal(events(drain()).length,1);
window.nfl2k5Module.nfl2k5ApuTrace=read('trace-wrap.bin');window.auditApuTraceSource=window.nfl2k5Module.nfl2k5ApuTrace;
window.auditApuTraceCursor=0xfffffffen;entries=events(drain());assert.deepEqual(entries.map(e=>e.sequence),['4294967295','4294967296']);
assert.equal(entries[0].event,'wake');assert.equal(entries[0].detail,1000);assert.equal(entries[1].event,'vp');
assert.deepEqual(drain(),[]);
window.nfl2k5Module.nfl2k5ApuTrace={memory:new SharedArrayBuffer(16),offset:0};
assert.equal(caseDiagnostics('pass',drain()).result,'fail');
delete window.nfl2k5Module.nfl2k5ApuTrace;assert.deepEqual(drain(),[]);
console.log('PASS serialized APU trace reader: production payloads, explicit loss, once-only draining, busy/torn publication retry, 32-bit crossing and invalid/absent descriptors');
