'use strict';

// Serialized by Playwright. Reads the versioned atomic layout in
// apu_schedule_trace.h. Never waits for a producer or acknowledges a busy slot.
function drainApuTraceRows() {
  const trace=window.nfl2k5Module?.nfl2k5ApuTrace;
  if(!trace)return [];
  const rows=[],at=performance.now();
  const failure=line=>rows.push({at,kind:'audit-error',line:'[APU-TRACE-LOSS] '+line});
  try {
    const {memory,offset}=trace;
    if(!(memory instanceof SharedArrayBuffer)||!Number.isInteger(offset)||offset<0||offset%8||offset+16>memory.byteLength)
      throw Error('invalid shared trace descriptor');
    const u32=new Uint32Array(memory),u64=new BigUint64Array(memory),header=offset/8;
    const capacity=Atomics.load(u32,offset/4+2),stride=Atomics.load(u32,offset/4+3);
    if(!capacity||capacity>4096||(capacity&(capacity-1))||stride!==32||offset+16+capacity*stride>memory.byteLength)
      throw Error('invalid shared trace layout');
    let cursor=window.auditApuTraceSource===trace?window.auditApuTraceCursor:0n;
    const published=Atomics.load(u64,header);
    if(published<cursor){failure('counter reset without a replacement descriptor');cursor=0n;}
    if(published-cursor>BigInt(capacity)){
      failure('skipped='+String(published-cursor-BigInt(capacity)));
      cursor=published-BigInt(capacity);
    }
    const names=['unknown','gap','wake','mmio','late','rebase','vp','dsp','output'];
    for(let sequence=cursor+1n;sequence<=published;sequence++) {
      const base=header+2+Number((sequence-1n)%BigInt(capacity))*4,guard=sequence*2n;
      const before=Atomics.load(u64,base);
      if(before!==guard){rows.push({at,kind:'apu-trace-status',line:'[APU-TRACE-RETRY] sequence='+sequence});break;}
      const start=Atomics.load(u64,base+1),end=Atomics.load(u64,base+2);
      const kind=Atomics.load(u32,(base+3)*2),detail=Atomics.load(u32,(base+3)*2+1);
      if(Atomics.load(u64,base)!==guard){rows.push({at,kind:'apu-trace-status',line:'[APU-TRACE-RETRY] sequence='+sequence});break;}
      if(end<start)throw Error('negative trace interval');
      rows.push({at,kind:'apu-trace',line:'[APU-TRACE] '+JSON.stringify({sequence:String(sequence),
        event:names[kind]||'unknown',startUs:String(start),endUs:String(end),detail})});
      cursor=sequence;
    }
    window.auditApuTraceSource=trace;window.auditApuTraceCursor=cursor;
  }catch(error){failure(String(error.message||error));}
  return rows;
}
module.exports={drainApuTraceRows};
