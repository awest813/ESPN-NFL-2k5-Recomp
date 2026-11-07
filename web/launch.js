// Starting a web build module: sound unlock, focus, and the module factory.
// Shared by the page (web/app.js) and the browser tests (tests/web/).
//
// Sound: browsers start an AudioContext suspended unless it is created or
// resumed while handling a user gesture (Safari insists on the handler
// itself; Chrome and Firefox also accept any later moment once the page has
// been clicked). SDL creates its context lazily, when the game opens audio,
// which is long after the click -- so the page creates one *in* the click,
// resumes it there, and hands it to SDL (SDL uses Module.SDL3.audioContext
// when one exists). If sound is still blocked -- the game was started
// without a click, or the browser said no -- a prompt asks for one, and the
// next click or key press anywhere resumes it.
'use strict';

window.NFL2K5Launch = (() => {
  // Call synchronously from the click/key handler, before any await. 48 kHz
  // is the APU's own rate, so the game's sound plays without resampling
  // (web/audio-worklet.js resamples if the browser picks another rate).
  function createAudio(sampleRate = 48000) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    let ctx;
    try { ctx = new Ctx({ latencyHint: 'interactive', sampleRate }); }
    catch { ctx = new Ctx({ latencyHint: 'interactive' }); }
    if (ctx.state !== 'running') ctx.resume().catch(() => {});
    return ctx;
  }

  // Shows `prompt` while sound is blocked; resumes on the next gesture.
  function watchSound(ctx, prompt, onChange) {
    if (!ctx) return;
    const update = () => {
      if (prompt) prompt.hidden = ctx.state === 'running' || ctx.state === 'closed';
      if (onChange) onChange(ctx.state);
    };
    const unlock = () => { if (ctx.state === 'suspended') ctx.resume().then(update, update); };
    for (const type of ['pointerdown', 'keydown', 'touchend'])
      document.addEventListener(type, unlock, { capture: true });
    ctx.addEventListener('statechange', update);
    update();
    // Some browsers settle the state a moment after creation.
    setTimeout(update, 250);
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src;
      s.onload = resolve;
      s.onerror = () => reject(new Error('Could not load ' + src));
      document.head.appendChild(s);
    });
  }

  // script: the module's .js; factory: its EXPORT_NAME. Resolves to the
  // module once it is running (its main runs on a worker meanwhile).
  // onGpuPresent(on): the WebGPU renderer took over (or gave back) the screen.
  async function start({ script, factory, canvas, audioContext, env = [], print, printErr, onAbort, onGpuPresent }) {
    if (typeof window[factory] !== 'function') await loadScript(script);
    if (canvas) canvas.focus();
    const mod = await window[factory]({
      canvas,
      SDL3: audioContext ? { audioContext } : undefined,
      print, printErr, onAbort, onGpuPresent,
      preRun: [(m) => {
        for (const kv of env) {
          const i = kv.indexOf('=');
          if (i > 0) m.ENV[kv.slice(0, i)] = kv.slice(i + 1);
        }
      }],
    });
    window.nfl2k5Module = mod;
    return mod;
  }

  return { createAudio, watchSound, start };
})();
