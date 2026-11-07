// Video, input and sound of the web build, in headless Chromium, through the
// smoke module (tests/web/smoke): the game's real presenter, input and audio
// code without the game.
//
//   1. Start (a click) -> the guest framebuffer reaches the canvas (left half
//      red, right half blue) through the presenter on its worker thread;
//   2. the AudioContext the page created in the click is running, and the
//      APU output's 440 Hz tone reaches Web Audio's output buffers;
//   3. keys go to the game while the canvas has focus, and not otherwise;
//   4. a controller that appears after startup (Gamepad API connect event)
//      is seen and its buttons read;
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
  window.__connectPad = () => {
    const pad = { id: 'Test Pad (STANDARD GAMEPAD)', index: 0, connected: true, mapping: 'standard',
                  timestamp: performance.now(), axes: [0, 0, 0, 0],
                  buttons: Array.from({ length: 17 }, () => ({ pressed: false, touched: false, value: 0 })) };
    window.__pads = [pad];
    const e = new Event('gamepadconnected');
    e.gamepad = pad;
    window.dispatchEvent(e);
  };
  window.__pressPad = (i, down) => {
    const pad = window.__pads[0];
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
      check(!!(await until(page, () => window.nfl2k5Module.SDL3.audioContext === window.smokeAudio, 2000)),
            'sound: SDL uses the page\'s AudioContext');
      const peak = await until(page, () => {
        const b = window.nfl2k5Module.SDL3.audio_playback && window.nfl2k5Module.SDL3.audio_playback.currentPlaybackBuffer;
        if (!b) return null;
        let m = 0;
        for (const v of b.getChannelData(0)) m = Math.max(m, Math.abs(v));
        return m > 0.2 ? m : null;
      }, 15000);
      check(!!peak, `sound: the tone reaches Web Audio (peak ${peak && peak.toFixed(2)})`);

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
  } finally {
    await browser.close();
    server.kill();
  }
  console.log(failures ? `${failures} failure(s)` : 'web audio/video: all checks passed');
  process.exit(failures ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
