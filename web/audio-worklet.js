// The game's sound output: an AudioWorkletProcessor that plays the APU's
// mix straight out of wasm's shared memory, on the browser's audio thread.
//
// The APU mixer (xboxrecomp apu/apu_web_audio.c) writes 48 kHz 16-bit stereo
// frames into a ring in wasm memory; this reads them. Ring layout (bytes from
// `ring`): 0 write index, 4 read index (frame counters, wrapping at 2^32),
// 8 capacity in frames (power of two), 16.. interleaved int16 samples.
// Indices go through Atomics so a frame is only read once fully written.
//
// When the AudioContext does not run at 48 kHz, frames are resampled
// linearly. Stats go back to the page about twice a second:
// { played, underruns, queued, peak, frequency } -- underruns counts render
// blocks that ran dry after sound first started; frequency is estimated from
// zero crossings of the left channel (useful for tests and diagnostics).
'use strict';

class NFL2K5Output extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const o = options.processorOptions;
    this.hdr = new Uint32Array(o.memory, o.ring, 4);
    this.cap = this.hdr[2];
    this.mask = this.cap - 1;
    this.data = new Int16Array(o.memory, o.ring + 16, this.cap * 2);
    this.step = o.rate / sampleRate;     // source frames per output frame
    this.frac = 0;
    this.started = false;
    this.stopped = false;
    this.played = 0;
    this.underruns = 0;
    this.peak = 0;
    this.crossings = 0;
    this.prev = 0;
    this.windowFrames = 0;
    this.port.onmessage = (e) => { if (e.data === 'stop') this.stopped = true; };
  }

  process(inputs, outputs) {
    if (this.stopped) return false;
    const out = outputs[0];
    const L = out[0], R = out[1] || out[0];
    const n = L.length, hdr = this.hdr, data = this.data, mask = this.mask;
    const w = Atomics.load(hdr, 0);
    let r = Atomics.load(hdr, 1);
    let dry = false;
    // Interpolation reads frames r and r + 1, so one frame always waits.
    for (let i = 0; i < n; i++) {
      if (((w - r) >>> 0) < 2) {
        L[i] = R[i] = 0;
        dry = true;
        continue;
      }
      const a = (r & mask) * 2, b = ((r + 1) & mask) * 2, f = this.frac;
      const l = f ? data[a] + (data[b] - data[a]) * f : data[a];
      const rr = f ? data[a + 1] + (data[b + 1] - data[a + 1]) * f : data[a + 1];
      L[i] = l / 32768;
      R[i] = rr / 32768;
      this.frac += this.step;
      while (this.frac >= 1) { this.frac -= 1; r = (r + 1) >>> 0; this.played++; }
      this.started = true;
      const v = L[i], av = v < 0 ? -v : v;
      if (av > this.peak) this.peak = av;
      if ((this.prev < 0) !== (v < 0)) this.crossings++;
      this.prev = v;
    }
    Atomics.store(hdr, 1, r);
    if (dry && this.started) this.underruns++;

    this.windowFrames += n;
    if (this.windowFrames >= sampleRate / 2) {
      this.port.postMessage({
        played: this.played, underruns: this.underruns,
        queued: (Atomics.load(hdr, 0) - r) >>> 0,
        peak: this.peak,
        frequency: this.crossings / 2 / (this.windowFrames / sampleRate),
      });
      this.windowFrames = 0;
      this.peak = 0;
      this.crossings = 0;
    }
    return true;
  }
}

registerProcessor('nfl2k5-output', NFL2K5Output);
