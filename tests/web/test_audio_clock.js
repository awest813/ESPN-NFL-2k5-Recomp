// Exercise the production audio bridge across Chromium's 30 s silence boundary.
// The smoke producer supplies 35 s of exact zero PCM, then a 440 Hz tone.
'use strict';
const assert = require('node:assert/strict');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '../..');
const dir = path.resolve(process.argv[2] || 'build-web-tests/smoke');

(async () => {
  const server = spawn(process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3'), [path.join(root, 'tools/serve-web.py'), dir, '--port', '18769'],
    {env: {...process.env, NFL2K5_SERVE_QUIET: '1'}, stdio: ['ignore', 'pipe', 'inherit']});
  let browser;
  try {
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(Error('Audio test server did not start')), 15000);
      server.on('error', reject);
      server.on('exit', code => { clearTimeout(timer); reject(Error(`Audio test server exited: ${code}`)); });
      server.stdout.on('data', data => { if (/Serving/.test(data)) { clearTimeout(timer); resolve(); } });
    });
    browser = await chromium.launch();
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('http://127.0.0.1:18769/smoke.html?env=SMOKE_SILENCE_MS=35000');
    await page.click('#start');
    await page.waitForFunction(() => window.nfl2k5Module?.nfl2k5Audio?.played > 48000, null, {timeout: 30000});
    const sample = () => page.evaluate(() => {
      const m = window.nfl2k5Module, s = m.nfl2k5Audio;
      return {wall: performance.now() / 1000, context: m.nfl2k5AudioContext.currentTime,
        state: s.state, played: s.played, rendered: s.rendered, underruns: s.underruns,
        underrunFrames: s.underrunFrames, maxUnderrunFrames: s.maxUnderrunFrames,
        peak: s.peak, frequency: s.frequency};
    });
    assert.equal((await sample()).peak, 0, 'the silence fixture must start silent');
    // Measure both sides of 30 s, rather than accepting steady playback only
    // after the browser has switched back from its silent sink.
    await page.waitForTimeout(27000);
    const before = await sample();
    await page.waitForTimeout(7000);
    const after = await sample();
    const wall = after.wall - before.wall, audio = after.context - before.context;
    assert(audio / wall > 0.95 && audio / wall < 1.05,
      `audio clock advanced ${audio.toFixed(3)} s in ${wall.toFixed(3)} s across silence`);
    assert(after.rendered - before.rendered > wall * 48000 * 0.85,
      'the terminal monitor must continue processing the silent graph');
    assert.equal(after.state, 'running');
    console.log(`ok: silent audio clock advances ${audio.toFixed(3)} s in ${wall.toFixed(3)} s`);
    await page.waitForFunction(() => window.nfl2k5Module.nfl2k5Audio.peak > 0.3, null, {timeout: 10000});
    // The first nonzero report includes the preceding silence in its crossing
    // count. Check pitch after a whole reporting window contains the tone.
    await page.waitForTimeout(1000);
    const tone = await sample();
    assert(Math.abs(tone.frequency - 440) < 9, `tone pitch after silence: ${tone.frequency}`);
    assert(tone.peak > 0.33 && tone.peak < 0.40, `tone level after silence: ${tone.peak}`);
    assert(Number.isInteger(tone.underrunFrames) && tone.underrunFrames >= 0);
    assert(Number.isInteger(tone.maxUnderrunFrames) && tone.maxUnderrunFrames <= tone.underrunFrames);
    assert.deepEqual(errors, []);
    assert(!await page.evaluate(() => smokeLog.some(line => /AudioWorklet.*(?:failed|could not start)/.test(line))));
    console.log(`ok: exact silence transitions to a ${tone.frequency.toFixed(1)} Hz tone; ${tone.underruns} affected blocks / ${tone.underrunFrames} missing output frames`);

    // Exercise real worklet starvation separately from the running producer.
    // Known PCM drains once; the following gap must have exact frame timing.
    await page.close();
    const gap=await browser.newPage();
    await gap.goto('http://127.0.0.1:18769/smoke.html');
    await gap.evaluate(()=>{
      const button=document.createElement('button');button.id='gap-start';button.textContent='Start controlled gap';
      document.body.replaceChildren(button);
      button.onclick=async()=>{
        try {
          const ctx=window.gapContext=new AudioContext({sampleRate:48000});await ctx.resume();
          await ctx.audioWorklet.addModule('audio-worklet.js');
          const memory=new SharedArrayBuffer(16+4096*4),hdr=window.gapHeader=new Uint32Array(memory,0,4);
          const pcm=new Int16Array(memory,16);hdr[2]=4096;
          for(let i=0;i<2048;i++){pcm[i*2]=1000;pcm[i*2+1]=-1000;}
          Atomics.store(hdr,0,2048);
          const node=window.gapNode=new AudioWorkletNode(ctx,'nfl2k5-output',{
            numberOfInputs:0,numberOfOutputs:1,outputChannelCount:[2],processorOptions:{memory,ring:0,rate:48000}});
          node.port.onmessage=e=>{window.gapStats=e.data;};node.connect(ctx.destination);
        }catch(e){window.gapError=String(e);}
      };
    });
    await gap.click('#gap-start');
    await gap.waitForFunction(()=>window.gapError||window.gapStats?.underrunFrames>0,null,{timeout:10000});
    const observed=await gap.evaluate(()=>({error:window.gapError,stats:window.gapStats,
      time:window.gapContext.currentTime,rate:window.gapContext.sampleRate,read:Atomics.load(window.gapHeader,1)}));
    assert(!observed.error,observed.error);const s=observed.stats;
    assert.equal(s.played,2048);assert.equal(observed.read,2048);
    assert(s.firstUnderrunTime>0 && s.lastUnderrunTime>=s.firstUnderrunTime && s.lastUnderrunTime<=observed.time);
    assert(Math.abs((s.lastUnderrunTime-s.firstUnderrunTime)*observed.rate-(s.underrunFrames-1))<1e-6,
      'continuous gap timestamps must match the exact missing-frame count');
    assert.equal(s.lastUnderrunQueued,0);assert.equal(s.lastUnderrunRequired,1);
    assert.equal(s.maxUnderrunFrames,s.underrunFrames);
    await gap.evaluate(async()=>{gapNode.disconnect();gapNode.port.postMessage('stop');await gapContext.close();});
    await gap.close();
    console.log('ok: actual AudioWorklet gap times match missing output frames and preserve all published PCM');
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
