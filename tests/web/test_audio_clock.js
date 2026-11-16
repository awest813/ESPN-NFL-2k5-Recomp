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
  const server = spawn('python3', [path.join(root, 'tools/serve-web.py'), dir, '--port', '18769'],
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
    assert.deepEqual(errors, []);
    assert(!await page.evaluate(() => smokeLog.some(line => /AudioWorklet.*(?:failed|could not start)/.test(line))));
    console.log(`ok: exact silence transitions to a ${tone.frequency.toFixed(1)} Hz tone; ${tone.underruns} total underrun blocks`);
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
