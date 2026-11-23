// Run the production worklet with deterministic producer chunks and clock rates.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../../web/audio-worklet.js'), 'utf8');

function fixture(rate, initial = 0, {cap = 32, afterStartup = true, wakeProducer = false} = {}) {
  let Processor;
  let loadHook;
  let renderedFrames=0;
  const messages = [], notifications = [];
  const observedAtomics = {load(array,index) {
      const value=Atomics.load(array,index);loadHook?.(array,index,value);return value;
    }, store:Atomics.store, add:Atomics.add,
    notify(array, index, count) {
      notifications.push({offset:array.byteOffset, index, value:Atomics.load(array,index)});
      return Atomics.notify(array,index,count);
    }};
  const memory = new SharedArrayBuffer(16 + cap * 4);
  const hdr = new Uint32Array(memory, 0, 4), data = new Int16Array(memory, 16);
  hdr[0] = hdr[1] = initial; hdr[2] = cap;
  vm.runInNewContext(source, {
    AudioWorkletProcessor: class { constructor() { this.port = {postMessage(message) {messages.push(message);}}; } },
    sampleRate: rate, get currentTime() {return renderedFrames/rate;}, Uint32Array, Int16Array, Atomics:observedAtomics,
    registerProcessor(name, type) { if (name === 'nfl2k5-output') Processor = type; },
  });
  const processor = new Processor({processorOptions: {memory, ring: 0, rate: 48000, wakeProducer}});
  // Most cases exercise a running stream after its initial buffering.
  processor.started = afterStartup;
  let next = 100;
  return {hdr, processor, messages, notifications,
    onLoad(hook) { loadHook=hook; },
    put(count) {
      let w = hdr[0];
      assert(count <= cap - ((w - hdr[1]) >>> 0));
      for (let i = 0; i < count; i++, w = (w + 1) >>> 0, next++) {
        data[(w & (cap - 1)) * 2] = next;
        data[(w & (cap - 1)) * 2 + 1] = -next;
      }
      Atomics.store(hdr, 0, w);
    },
    render(count) {
      const left = new Float32Array(count), right = new Float32Array(count);
      assert(processor.process([], [[left, right]]));
      renderedFrames+=count;
      assert(((hdr[0] - hdr[1]) >>> 0) <= cap, `read cursor passed producer at ${rate} Hz`);
      for (let i = 0; i < count; i++) assert(left[i] === -right[i]);
      return Array.from(left);
    },
  };
}

// The terminal clock monitor consumes no ring data and never writes PCM.
{
  let Monitor;
  const messages = [];
  vm.runInNewContext(source, {
    AudioWorkletProcessor: class { constructor() { this.port = {postMessage: message => messages.push(message)}; } },
    sampleRate: 48000,
    registerProcessor(name, type) { if (name === 'nfl2k5-audio-clock') Monitor = type; },
  });
  const monitor = new Monitor();
  const pcm = new Float32Array(128); pcm[10] = 0.25;
  const original = Float32Array.from(pcm);
  for (let i = 0; i < 188; i++) assert(monitor.process([[pcm]]));
  assert.deepEqual(pcm, original);
  assert.equal(messages[0].rendered, 24064);
  monitor.port.onmessage({data: 'stop'});
  assert.equal(monitor.process([[pcm]]), false);
  console.log('ok: terminal monitor reports rendered frames without changing PCM and stops on shutdown');
}

// Buffer source audio at startup without consuming it or injecting samples.
{
  const f = fixture(48000, 0, {cap:4096, afterStartup:false});
  f.put(1024);
  assert(f.render(128).every(x => x === 0));
  assert.equal(f.hdr[1], 0);
  assert.equal(f.processor.underruns, 0);
  assert.equal(f.processor.underrunFrames, 0);
  assert.equal(f.processor.maxUnderrunFrames, 0);
  f.put(1024);
  assert.deepEqual(f.render(8).map(x => x * 32768), [100,101,102,103,104,105,106,107]);
  assert.equal(f.hdr[1], 8);
  assert.equal(f.processor.underruns, 0);
  console.log('ok: startup buffering preserves the first samples without underruns');
}

// An integer phase reads only its current source sample. Retain the next
// sample requirement only when interpolation actually needs that neighbor.
{
  const f=fixture(48000);f.put(1);
  assert.deepEqual(f.render(1).map(x=>x*32768),[100]);
  assert.equal(f.hdr[1],1);assert.equal(f.processor.underrunFrames,0);
  assert.deepEqual(f.render(1),[0]);assert.equal(f.processor.underrunFrames,1);
  f.put(1);assert.deepEqual(f.render(1).map(x=>x*32768),[101]);
  assert.equal(f.processor.played,2);assert.equal(f.processor.underrunFrames,1);
}
{
  const f=fixture(96000);f.put(1);
  const output=f.render(2); // exact first sample, then wait for its neighbor
  assert.equal(f.processor.frac,.5);assert.equal(f.hdr[1],0);
  f.put(1);output.push(...f.render(3));
  assert.equal(f.processor.frac,.5);assert.equal(f.hdr[1],1);
  f.put(2);output.push(...f.render(4));
  assert.deepEqual(output.map(x=>x*32768),[100,0,100.5,101,0,101.5,102,102.5,103]);
}
console.log('ok: exact phases play a lone source frame; fractional phases retain interpolation state across gaps');

// A release publication after the consumer's initial acquire must be usable
// within the same render block, without replaying or skipping source frames.
for(const rate of [8000,44100,48000,96000])for(const initial of [0,0xfffffffc]) {
  const reference=fixture(rate,initial,{cap:128});reference.put(64);
  const expected=reference.render(8);
  const concurrent=fixture(rate,initial,{cap:128});concurrent.put(2);
  let published=false;
  concurrent.onLoad((array,index)=>{
    if(array===concurrent.processor.hdr && index===0 && !published) {
      published=true;concurrent.put(62);
    }
  });
  assert.deepEqual(concurrent.render(8),expected,`late PCM publication at ${rate} Hz / ${initial}`);
  assert.equal(concurrent.processor.played,reference.processor.played);
  assert.equal(concurrent.processor.frac,reference.processor.frac);
  assert.equal(concurrent.processor.underrunFrames,0);
}
console.log('ok: PCM published during a render block is consumed without a stale-snapshot gap');

// Exact-rate output carries peak and crossing history across a ring wrap
// and from the published prefix into a partially dry render block.
{
  const f = fixture(48000, 0xfffffffe);
  f.put(5);
  const samples = [-200, 300, -400, -500, 100];
  for (let i = 0; i < samples.length; i++) {
    const a = ((0xfffffffe + i) & f.processor.mask) * 2;
    f.processor.data[a] = samples[i];
    f.processor.data[a + 1] = -samples[i];
  }
  assert.deepEqual(f.render(2).concat(f.render(4)).map(v => v * 32768), [...samples, 0]);
  assert.equal(f.processor.peak, 500 / 32768);
  assert.equal(f.processor.crossings, 4);
  assert.equal(f.processor.prev, 100 / 32768);
  assert.equal(f.processor.played, 5);
  assert.equal(f.processor.underrunFrames, 1);
}

// Missing output frames distinguish a partial render block from a full gap.
for (const rate of [48000, 96000]) {
  const f = fixture(rate);
  f.put(2);
  const block = f.render(8);
  const missing = block.filter(x => x === 0).length;
  assert.equal(f.processor.underruns, 1);
  assert.equal(f.processor.underrunFrames, missing);
  assert.equal(f.processor.firstUnderrunTime,(8-missing)/rate);
  assert.equal(f.processor.lastUnderrunTime,7/rate);
  assert(f.processor.lastUnderrunQueued<f.processor.lastUnderrunRequired);
  f.render(8);
  assert.equal(f.processor.underruns, 2);
  assert.equal(f.processor.underrunFrames, missing + 8);
  assert.equal(f.processor.maxUnderrunFrames, missing + 8);
  assert.equal(f.processor.lastUnderrunTime,15/rate);
  f.put(12);f.render(4);
  assert.equal(f.processor.underrunRun, 0);
  assert.equal(f.processor.maxUnderrunFrames, missing + 8);
  // A valid zero-valued PCM sample is not an underrun.
  const memory = f.processor.data;memory.fill(0);
  f.render(2);
  assert.equal(f.processor.underrunFrames, missing + 8);
  f.render(rate / 2);
  assert.equal(f.messages.at(-1).underrunFrames, f.processor.underrunFrames);
  assert.equal(f.messages.at(-1).maxUnderrunFrames, f.processor.maxUnderrunFrames);
  assert.equal(f.messages.at(-1).firstUnderrunTime,f.processor.firstUnderrunTime);
  assert.equal(f.messages.at(-1).lastUnderrunTime,f.processor.lastUnderrunTime);
}
console.log('ok: exact missing-frame counts span blocks, reset on recovery and exclude authored silence');

// Repeated starvation must never turn unsigned ring occupancy into billions.
for (const rate of [8000, 11025, 16000, 22050, 24000, 44100, 48000, 96000]) {
  for (const initial of [0, 0xfffffffc]) {
    const f = fixture(rate, initial);
    f.put(2); f.render(8);
    f.put(12); f.render(8);
    f.render(8);
    f.put(16); f.render(12);
    console.log(`ok: ${rate} Hz preserves ring bounds through starvation and counter wrap (${initial})`);
  }
}

// The source positions are 0,6,12... at 8 kHz. Incomplete producer chunks
// must preserve this phase instead of playing stale samples or skipping ahead.
{
  const f = fixture(8000);
  f.put(2); const first = f.render(4);
  f.put(12); const second = f.render(4);
  const played = first.concat(second).filter(x => x !== 0).map(x => x * 32768);
  assert.deepEqual(played, [100, 106]);
  assert.equal(f.processor.played, 12);
}
// Interpolation and phase across render blocks remain correct at 96 kHz.
{
  const f = fixture(96000);
  f.put(8);
  const actual = f.render(3).concat(f.render(5)).map(x => x * 32768);
  assert.deepEqual(actual, [100, 100.5, 101, 101.5, 102, 102.5, 103, 103.5]);
  assert.equal(f.processor.played, 4);
}

// Optional clock pulses never alter the PCM indices and stop with the processor.
{
  const off = fixture(48000); off.put(8); off.render(4); assert.equal(off.hdr[3], 0); assert.deepEqual(off.notifications, []);
  const f = fixture(48000, 0, {cap:4096, afterStartup:false, wakeProducer:true});
  f.render(128); assert.equal(f.hdr[3], 1); assert.equal(f.hdr[1], 0);
  f.put(2048); assert.deepEqual(f.render(4).map(x=>x*32768), [100,101,102,103]);
  assert.equal(f.hdr[3], 2); assert.equal(f.hdr[1], 4);
  f.hdr[3] = 0x7fffffff; f.render(4); assert.equal(f.hdr[3], 0x80000000);
  f.hdr[3] = 0xffffffff; f.render(4); assert.equal(f.hdr[3], 0);
  f.render(4); assert.equal(f.hdr[3], 1);
  f.processor.port.onmessage({data:'stop'});
  assert.equal(f.processor.process([], [[new Float32Array(4), new Float32Array(4)]]), false);
  assert.equal(f.hdr[3], 1);
  assert.equal(f.notifications.length, 5);
  assert(f.notifications.every(x=>x.offset===12 && x.index===0));
  assert.deepEqual(f.notifications.map(x=>x.value), [1,2,-2147483648,0,1]);
  console.log('ok: optional producer wakes include startup, preserve PCM, wrap and stop');
}

console.log('audio worklet: all checks passed');
