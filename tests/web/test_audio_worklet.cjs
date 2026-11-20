// Run the production worklet with deterministic producer chunks and clock rates.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../../web/audio-worklet.js'), 'utf8');

function fixture(rate, initial = 0, {cap = 32, afterStartup = true} = {}) {
  let Processor;
  const messages = [];
  const memory = new SharedArrayBuffer(16 + cap * 4);
  const hdr = new Uint32Array(memory, 0, 4), data = new Int16Array(memory, 16);
  hdr[0] = hdr[1] = initial; hdr[2] = cap;
  vm.runInNewContext(source, {
    AudioWorkletProcessor: class { constructor() { this.port = {postMessage(message) {messages.push(message);}}; } },
    sampleRate: rate, Uint32Array, Int16Array, Atomics,
    registerProcessor(name, type) { if (name === 'nfl2k5-output') Processor = type; },
  });
  const processor = new Processor({processorOptions: {memory, ring: 0, rate: 48000}});
  // Most cases exercise a running stream after its initial buffering.
  processor.started = afterStartup;
  let next = 100;
  return {hdr, processor, messages,
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

// Missing output frames distinguish a partial render block from a full gap.
for (const rate of [48000, 96000]) {
  const f = fixture(rate);
  f.put(2);
  const block = f.render(8);
  const missing = block.filter(x => x === 0).length;
  assert.equal(f.processor.underruns, 1);
  assert.equal(f.processor.underrunFrames, missing);
  f.render(8);
  assert.equal(f.processor.underruns, 2);
  assert.equal(f.processor.underrunFrames, missing + 8);
  assert.equal(f.processor.maxUnderrunFrames, missing + 8);
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
console.log('audio worklet: all checks passed');
