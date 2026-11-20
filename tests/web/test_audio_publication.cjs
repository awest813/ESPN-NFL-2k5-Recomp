'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const dir=path.resolve(process.argv[2]),stallMs=Number(process.argv[3]),phase=Number(process.argv[4]);
const source=fs.readFileSync(path.join(__dirname,'../../web/audio-worklet.js'),'utf8');
function run(mode){
  const packets=JSON.parse(fs.readFileSync(path.join(dir,mode+'.json'),'utf8'));
  const pcm=fs.readFileSync(path.join(dir,mode+'.pcm'));
  for(let i=0;i<16384;i++){const s=i%8191+1;assert.equal(pcm.readInt16LE(i*4),s);assert.equal(pcm.readInt16LE(i*4+2),-s);}
  let Processor;
  const context=vm.createContext({sampleRate:48000,currentTime:0,Atomics,
    AudioWorkletProcessor:class {constructor(){this.port={postMessage(){}};}},
    registerProcessor(name,type){if(name==='nfl2k5-output')Processor=type;}});
  vm.runInContext(source,context);
  const memory=new SharedArrayBuffer(16+16384*4),header=new Uint32Array(memory,0,4),data=new Int16Array(memory,16);
  header[2]=16384;const processor=new Processor({processorOptions:{memory,ring:0,rate:48000}});
  let next=0,written=0,peakQueued=0,firstPlayback=null;const rendered=[];
  for(let frame=0;frame<32768 && processor.played<16384;frame+=128){
    while(next<packets.length && packets[next].readyFrame<=frame){
      const packet=packets[next++];assert.ok(written+packet.frames-Atomics.load(header,1)<=16384);
      for(let i=0;i<packet.frames;i++){data[((written+i)&16383)*2]=pcm.readInt16LE((written+i)*4);data[((written+i)&16383)*2+1]=pcm.readInt16LE((written+i)*4+2);}
      written+=packet.frames;peakQueued=Math.max(peakQueued,written-Atomics.load(header,1));
      assert.ok(peakQueued<=6144,'controlled schedule must respect the existing submission queue ceiling');
      Atomics.store(header,0,written);
    }
    const l=new Float32Array(128),r=new Float32Array(128);context.currentTime=frame/48000;
    processor.process([],[ [l,r] ]);
    if(processor.started && firstPlayback===null)firstPlayback=frame;
    // The fixture's source samples are all nonzero. Recover every real
    // sample, excluding startup/underrun zeros, and check order bit-for-bit.
    for(let i=0;i<128;i++)if(l[i]!==0){rendered.push(l[i]*32768,r[i]*32768);}
  }
  assert.equal(processor.played,16384);assert.equal(rendered.length,32768);
  for(let i=0;i<16384;i++){assert.equal(rendered[i*2],pcm.readInt16LE(i*4));assert.equal(rendered[i*2+1],pcm.readInt16LE(i*4+2));}
  console.log(`PASS ${mode}: exact monitor/worklet PCM order, first playback frame ${firstPlayback}, missing ${processor.underrunFrames}`);
  return {packets,firstPlayback,peakQueued,missing:processor.underrunFrames};
}
const native=run('native'),web=run('web');
assert.equal(web.firstPlayback,native.firstPlayback,'earlier publication must not raise the priming target or add startup latency');
assert.equal(web.firstPlayback,1792,'the unchanged 2048-frame priming threshold must start at the eighth ready block');
assert.ok(web.missing<=native.missing,'earlier publication must not increase missing frames');
if(stallMs===28 && phase===11){assert.equal(native.missing,384);assert.equal(web.missing,0);}
if(stallMs===0){assert.equal(native.missing,0);assert.equal(web.missing,0);}
assert.ok(web.packets.every(p=>p.frames===256));assert.ok(native.packets.every(p=>p.frames===1024));
assert.equal(web.packets.length,64);assert.equal(native.packets.length,16);
console.log(`PASS ${stallMs}ms stall at batch ${phase}: native missing ${native.missing}, Web missing ${web.missing}; PCM, capacity and priming preserved`);
