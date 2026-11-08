// Video, input and sound of the web build, in headless Chromium, through the
// smoke module (tests/web/smoke): the game's real presenter, input and audio
// code without the game.
//
//   1. Start (a click) -> the guest framebuffer reaches the canvas (left half
//      red, right half blue) through the presenter on its worker thread;
//   2. the AudioContext the page created in the click is running, and the
//      APU output's 440 Hz tone plays through the AudioWorklet
//      (web/audio-worklet.js): right pitch and level, no underruns once
//      started, SDL's audio not used; at 44.1 kHz it is resampled to the same
//      pitch; with RECOMP_WEB_SDL_AUDIO=1 it falls back to SDL's output;
//   3. keys go to the game while the canvas has focus, and not otherwise;
//   4. a controller that appears after startup (Gamepad API connect event)
//      is seen and its buttons read;
//   6. with WebGPU (a second browser, SwiftShader), a GPU presenter written as
//      the SDL GPU renderer's takes the window over through the WebGPU shim:
//      the overlay canvas shows its frame, paced by animation frames; the
//      first browser has no WebGPU, so everything above ran the software
//      fallback;
//   5. started without a click (under a stand-in for the autoplay block, see
//      AUTOPLAY_BLOCK), the "sound is off" prompt shows and the next click
//      turns sound on and hides it.
//
//   node tests/web/test_web_av.js <smoke build dir>
'use strict';
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const DIR = path.resolve(process.argv[2] || path.join(ROOT, 'build-web-tests', 'smoke'));
let failures = 0;
const check = (cond, what) => { if (!cond) { failures++; console.log('FAIL:', what); } else console.log('ok:', what); };

// A Gamepad API stand-in the test controls: navigator.getGamepads() returns
// window.__pads, and __connectPad() fires the browser's connect event.
const PAD_STUB = () => {
  window.__pads = [];
  navigator.getGamepads = () => window.__pads;
  window.__connectPad = (index = 0) => {
    const pad = { id: 'Test Pad ' + index + ' (STANDARD GAMEPAD)', index, connected: true, mapping: 'standard',
                  timestamp: performance.now(), axes: [0, 0, 0, 0],
                  buttons: Array.from({ length: 17 }, () => ({ pressed: false, touched: false, value: 0 })) };
    window.__pads[index] = pad;
    const e = new Event('gamepadconnected');
    e.gamepad = pad;
    window.dispatchEvent(e);
  };
  window.__pressPad = (i, down, index = 0) => {
    const pad = window.__pads[index];
    pad.buttons[i] = { pressed: down, touched: down, value: down ? 1 : 0 };
    pad.timestamp = performance.now();
  };
};

// A desktop browser's autoplay block. Automation cannot produce the real
// one: a Playwright navigation already counts as user activation, so every
// AudioContext starts running. This stand-in applies the policy at the API:
// a new context starts suspended, and resume() works only once the page has
// had a trusted pointer or key gesture.
const AUTOPLAY_BLOCK = () => {
  const Real = window.AudioContext;
  let gesture = false;
  for (const t of ['pointerdown', 'keydown'])
    addEventListener(t, (e) => { if (e.isTrusted) gesture = true; }, true);
  window.AudioContext = class extends Real {
    constructor(o) { super(o); super.suspend(); }
    resume() { return gesture ? super.resume() : Promise.resolve(); }
  };
};

// The worklet's own report (apu_web_audio.c keeps it as Module.nfl2k5Audio).
async function checkWorklet(page, rate, label) {
  const audio = () => window.nfl2k5Module && window.nfl2k5Module.nfl2k5Audio;
  const st = await until(page, (f) => { const s = new Function('return ' + f)()(); return s && s.played > 48000 ? s : null; },
                         20000, audio.toString());
  check(!!st && st.state === 'running', `${label}: AudioWorklet output running`);
  if (!st) return;
  check(st.contextRate === rate, `${label}: AudioContext at ${st.contextRate} Hz`);
  check(Math.abs(st.frequency - 440) < 440 * 0.02, `${label}: tone at ${st.frequency.toFixed(1)} Hz (440 expected)`);
  check(st.peak > 0.33 && st.peak < 0.40, `${label}: level ${st.peak.toFixed(3)} (0.366 expected)`);
  const u0 = st.underruns, p0 = st.played;
  await page.waitForTimeout(3000);
  const st2 = await page.evaluate(() => window.nfl2k5Module.nfl2k5Audio);
  check(st2.played - p0 > 48000 * 2, `${label}: kept playing (${st2.played - p0} frames in 3 s)`);
  check(st2.underruns - u0 <= 1, `${label}: no underruns while fed (${st2.underruns - u0} in 3 s)`);
  check(await page.evaluate(() => !(window.nfl2k5Module.SDL3 && window.nfl2k5Module.SDL3.audio_playback)),
        `${label}: SDL's ScriptProcessor output not used`);
  check(await page.evaluate(() => window.nfl2k5Module.nfl2k5AudioContext === window.smokeAudio),
        `${label}: plays through the page's AudioContext`);
}

async function until(page, fn, ms, arg) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    const v = await page.evaluate(fn, arg).catch(() => null);
    if (v) return v;
    await page.waitForTimeout(100);
  }
  return null;
}
const hasLog = (page, re, ms) => until(page, (src) => window.smokeLog.some((l) => new RegExp(src).test(l)), ms, re.source);

(async () => {
  const server = spawn('python3', [path.join(ROOT, 'tools/serve-web.py'), DIR, '--port', '18767'],
                       { env: { ...process.env, NFL2K5_SERVE_QUIET: '1' }, stdio: ['ignore', 'pipe', 'inherit'] });
  await new Promise((r) => server.stdout.on('data', (d) => /Serving/.test(d) && r()));
  const browser = await chromium.launch();
  try {
    {
      const page = await (await browser.newContext()).newPage();
      page.on('pageerror', (e) => console.log('  [pageerror]', e.message));
      await page.addInitScript(PAD_STUB);
      await page.goto('http://127.0.0.1:18767/smoke.html');
      await page.click('#start');
      check(!!(await hasLog(page, /^\[SMOKE\] ready$/, 30000)), 'module started');

      const px = await until(page, () => {
        const c = document.getElementById('canvas'), g = c.getContext('2d');
        if (!g || !c.width) return null;
        const l = Array.from(g.getImageData(c.width / 4, c.height / 2, 1, 1).data);
        const r = Array.from(g.getImageData(c.width * 3 / 4, c.height / 2, 1, 1).data);
        return l[0] === 255 && l[2] === 0 && r[0] === 0 && r[2] === 255 ? { l, r } : null;
      }, 15000);
      check(!!px, 'video: guest framebuffer on the canvas (red | blue)');

      check((await page.evaluate(() => window.smokeAudio.state)) === 'running', 'sound: AudioContext running after the click');
      await checkWorklet(page, 48000, 'sound');

      await page.focus('#start');
      await page.keyboard.press('KeyB');
      await page.click('#canvas');
      await page.keyboard.press('KeyA');
      check(!!(await hasLog(page, /^\[SMOKE\] key vk=65$/, 5000)), 'keys: reach the game when the canvas has focus');
      check(!(await page.evaluate(() => window.smokeLog.includes('[SMOKE] key vk=66'))),
            'keys: not taken while another element has focus');

      await page.evaluate(() => window.__connectPad());
      check(!!(await hasLog(page, /^\[SMOKE\] gamepads: 1$/, 5000)), 'controller: connected after startup is seen');
      check(!!(await hasLog(page, /^\[SMOKE\] opened /, 5000)), 'controller: opens as a gamepad');
      await page.evaluate(() => window.__pressPad(0, true));
      check(!!(await hasLog(page, /^\[SMOKE\] pad A down$/, 5000)), 'controller: button press read');
      check(!!(await hasLog(page, /^\[SMOKE\] controls disabled neutral: 1$/, 1000)), 'scripted input: disabled controller on port 2 is neutral');
      check(!!(await hasLog(page, /^\[SMOKE\] controls 0: connected=1 buttons=0 A=255 LT=0 RT=0 sticks=0,0,0,0$/, 5000)), 'game controls read a pad already opened by another SDL caller');
      await page.evaluate(() => { __pressPad(0,false); __pressPad(6,true); __pressPad(7,true); __pressPad(9,true); __pressPad(12,true); __pads[0].axes = [1,0,0,-1]; });
      const mapped = await hasLog(page, /^\[SMOKE\] controls 0: connected=1 buttons=17 A=0 LT=255 RT=255 sticks=32767,0,0,32767$/, 5000);
      if (!mapped) console.log('controller states:',await page.evaluate(() => smokeLog.filter(l => l.includes('[SMOKE] controls 0:'))));
      check(!!mapped, 'game controls: Start, D-pad, triggers and both stick directions');
      await page.evaluate(() => { smokeLog = smokeLog.filter(l => !l.includes('[SMOKE] controls 0:')); for (let i=0;i<17;i++) __pressPad(i,false); __pads[0].axes=[0,0,0,0]; });
      check(!!(await hasLog(page, /^\[SMOKE\] pad A up$/, 5000)), 'controller: release reaches SDL');
      check(!!(await hasLog(page, /^\[SMOKE\] controls 0: connected=1 buttons=0 A=0 LT=0 RT=0 sticks=0,0,0,0$/, 5000)), 'game controls: releasing everything returns an exact neutral state');
      await page.evaluate(() => __connectPad(1));
      await page.evaluate(() => __pressPad(0,true,1));
      check(!!(await hasLog(page, /^\[SMOKE\] controls 1: connected=1 buttons=0 A=255 LT=0 RT=0 sticks=0,0,0,0$/, 5000)), 'second controller maps to a separate Xbox port');
      await page.evaluate(() => {
        const pad = __pads[1]; pad.connected=false; __pads[1]=null;
        const e = new Event('gamepaddisconnected'); e.gamepad=pad; dispatchEvent(e);
      });
      check(!!(await hasLog(page, /^\[SMOKE\] controls 1: connected=0 buttons=0 A=0 LT=0 RT=0 sticks=0,0,0,0$/, 5000)), 'unplugging clears held buttons and sticks');
      await page.evaluate(() => { smokeLog = smokeLog.filter(l => !l.includes('[SMOKE] controls 1:')); __connectPad(1); __pressPad(0,true,1); });
      check(!!(await hasLog(page, /^\[SMOKE\] controls 1: connected=1 buttons=0 A=255 LT=0 RT=0 sticks=0,0,0,0$/, 5000)), 'controller reconnects and resumes input on the second port');
      await page.close();
    }
    {
      const page = await (await browser.newContext()).newPage();
      await page.goto('http://127.0.0.1:18767/smoke.html?rate=44100');
      await page.click('#start');
      await checkWorklet(page, 44100, 'sound at 44.1 kHz');
      await page.close();
    }
    {
      const page = await (await browser.newContext()).newPage();
      await page.goto('http://127.0.0.1:18767/smoke.html?env=RECOMP_WEB_SDL_AUDIO=1');
      await page.click('#start');
      const peak = await until(page, () => {
        const a = window.nfl2k5Module && window.nfl2k5Module.SDL3 && window.nfl2k5Module.SDL3.audio_playback;
        const b = a && a.currentPlaybackBuffer;
        if (!b) return null;
        let m = 0;
        for (const v of b.getChannelData(0)) m = Math.max(m, Math.abs(v));
        return m > 0.2 ? m : null;
      }, 15000);
      check(!!peak, `SDL fallback: the tone reaches Web Audio through SDL (peak ${peak && peak.toFixed(2)})`);
      await page.close();
    }
    {
      const page = await (await browser.newContext()).newPage();
      await page.addInitScript(AUTOPLAY_BLOCK);
      await page.goto('http://127.0.0.1:18767/smoke.html?auto=1');
      check(!!(await hasLog(page, /^\[SMOKE\] audio open$/, 30000)), 'no click: module started');
      check(!!(await until(page, () => window.smokeAudio.state === 'suspended', 3000)), 'no click: sound blocked');
      check(!!(await until(page, () => !document.getElementById('sound').hidden, 3000)),
            'no click: "sound is off" prompt shown');
      await page.click('#sound');
      check(!!(await until(page, () => window.smokeAudio.state === 'running', 5000)), 'after a click: sound on');
      check(!!(await until(page, () => document.getElementById('sound').hidden, 5000)), 'after a click: prompt hidden');
      await page.close();
    }
    await browser.close();
    // 6. WebGPU: SwiftShader's Vulkan, and ANGLE so WebGPU canvases composite.
    const gpu = await chromium.launch({ channel: 'chromium', args: ['--enable-unsafe-webgpu', '--use-gl=angle',
      '--use-angle=swiftshader', '--enable-features=Vulkan', '--use-vulkan=swiftshader'] });
    try {
      const page = await (await gpu.newContext()).newPage();
      await page.goto('http://127.0.0.1:18767/smoke.html?env=SMOKE_GPU=1');
      await page.click('#start');
      check(!!(await hasLog(page, /^\[SMOKE\] gpu present claimed$/, 30000)), 'WebGPU: presenter claimed the window');
      const view = await until(page, () => {
        const c = document.getElementById('gpucanvas');
        const k = document.createElement('canvas'); k.width = c.width; k.height = c.height;
        const g = k.getContext('2d'); g.drawImage(c, 0, 0);
        const l = Array.from(g.getImageData(c.width / 4, c.height / 2, 1, 1).data);
        const r = Array.from(g.getImageData(c.width * 3 / 4, c.height / 2, 1, 1).data);
        return !c.hidden && l[1] === 192 && l[0] === 0 && r[0] === 192 && r[2] === 192 ? { l, r } : null;
      }, 10000);
      check(!!view, 'WebGPU: overlay canvas shows the presented frame (green | magenta)');
      check(await page.evaluate(() => window.gpuPresent === true), 'WebGPU: page told the GPU presents (onGpuPresent)');
      await page.waitForTimeout(2500);
      const rates = (await page.evaluate(() => window.smokeLog.slice()))
        .map((l) => /presents\/s: (\d+)/.exec(l)).filter(Boolean).map((m) => +m[1]).slice(1);
      const last = rates[rates.length - 1];
      check(last >= 20 && last <= 130, `WebGPU: presents paced by animation frames (${rates.join(', ')}/s)`);
    } finally {
      await gpu.close();
    }
  } finally {
    if (browser.isConnected()) await browser.close().catch(() => {});
    server.kill();
  }
  console.log(failures ? `${failures} failure(s)` : 'web audio/video: all checks passed');
  process.exit(failures ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
