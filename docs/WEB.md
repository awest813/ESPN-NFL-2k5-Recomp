# WebAssembly build (experimental)

Milestone M1 of [WEB-PORT-PLAN.md](WEB-PORT-PLAN.md) is done: the game
**compiles and links** with Emscripten. Two of the M2 runtime pieces are in:
the guest address space ([below](#guest-address-space)) and APU/AC97
register routing without faults ([below](#audio-registers-without-faults)),
the page itself, with game files in the browser's private file system
([below](#playing-in-a-browser)), and video, input and sound in the browser
([below](#video-input-and-sound)), and the hardware renderer on WebGPU
([below](#hardware-rendering-webgpu)). In a browser, the module mounts the
imported disc and reads `default.xbe` from it. Booting further needs the
retail disc, which this has not been tried with yet.

## Result (2026-11-06, emsdk 7.0.0, 4-core container)

| | |
|---|---|
| `NFL2K5.wasm` | 37.9 MB (8.9 MB gzip -9), 36,377 functions, 37.3 MB of code. With the address-space and APU work (2026-11-07) it is 49.5 MB with 48.8 MB of code; see "Cost" below. |
| `NFL2K5.js` | 167 KB of Emscripten glue (pthreads, WasmFS) |
| Largest function body | 76 KB (117 KB after the address fold). V8's per-function limit is 7.6 MB, so this concern from the plan is settled. |
| V8 compile, whole module, eager | 0.26 s Liftoff, 4.1 s TurboFan (Node 24). The browser compiles lazily and in tiers. |
| `tools/build-web.sh` from scratch | 143 s (SDL3, runtime, game; the 34 generated chunks take about 90 s with `-j4`) |

`WebAssembly.validate` passes and the module compiles in V8. The game itself
has not run yet, but the runtime's real memory-layout init does, under Node,
in `tools/test-web.sh`.

## Build

You need emsdk (verified with **7.0.0**), cmake, ninja, git, curl and
python3:

    git clone https://github.com/emscripten-core/emsdk.git
    emsdk/emsdk install 7.0.0 && emsdk/emsdk activate 7.0.0
    source emsdk/emsdk_env.sh
    tools/build-web.sh            # full link: build-web/NFL2K5.js + NFL2K5.wasm
    tools/build-web.sh --no-gen   # runtime + hand-written sources only (minutes)

The script does four things:
- fetches and builds SDL 3.2.20 for Emscripten into `dependencies/`, at
  the same commit CI uses;
- fetches miniz, as `docs/LINUX.md` describes;
- applies `config/xboxrecomp-web.patch` to the submodule if it is not
  applied yet;
- configures `build-web/`.

`tools/test-web.sh` then runs the web tests (Node, from the same emsdk):
the DirectSound rewrite, the APU accessors, fixed-address mappings with the
heap ceiling, and the real `xbox_MemoryLayoutInit` on a minimal XBE. CI runs
it on every push.

The generated code is about 220 MB of C. As on Linux, each of the largest
files needs about 2 GB of RAM to compile, so set `JOBS=` to match your
memory. CI compiles everything except the generated code on every push. The
full link runs on manual dispatch and uploads the `.js`/`.wasm` as an
artifact.

## What the web target changes

The web build is the POSIX build (`config/game.cmake`'s non-Windows branch)
plus the following:

| Where | Change |
|---|---|
| `config/game.cmake` | No OpenSSL. `src/platform/web/` goes first on the include path. Link flags: `-pthread -sPROXY_TO_PTHREAD` (the guest main runs on a worker; blocking waits are not allowed on the browser main thread), `-sPTHREAD_POOL_SIZE=16`, 1 GB initial memory growing to 4 GB, `-fwasm-exceptions` (C++ sources throw), `-sSUPPORT_LONGJMP=wasm` (guest setjmp/SEH bridge), `-sWASMFS`. |
| `src/main.c` | `install_audio_mmio_handler()` is a no-op on Emscripten. There is no SIGSEGV/SIGTRAP to catch, and the Linux handler decodes x86-64 `ucontext` registers. |
| `src/nfl2k5_save_library.cpp` | Use `getentropy()` for save container IDs. Emscripten declares `getrandom()` but does not implement it. |
| `src/platform/web/` | `openssl/{sha,evp,hmac}.h` and `web_crypto.c`: the two OpenSSL calls the game makes (`SHA256` for the XBE check, `HMAC(EVP_sha1())` for save signatures), checked against the FIPS 180 and RFC 2202 vectors. |
| `src/nfl2k5_controller_art.cpp`, `src/nfl2k5_texture_packs.cpp` | Add the missing `<stdlib.h>` for `getenv`. glibc pulled it in transitively; Emscripten's libc does not. |
| xboxrecomp, via `config/xboxrecomp-web.patch` | `platform/guest_memory.c` gets an Emscripten implementation. wasm cannot fault inside linear memory, so a checked copy is a bounds check plus `memcpy`. `nv2a_pb_exec.c` and `nv2a_gpu_sdl3.inc.c` take the checked-copy (Linux) paths on Emscripten as well. The kernel no longer requires OpenSSL there (it never called it). `platform/CMakeLists.txt` builds `guest_memory.c` for Emscripten. `win32_compat.c` gets a `GlobalMemoryStatusEx` from the wasm heap limits, because there is no `sysinfo(2)`. `sdlgpu_vpcache.inc.c` now guards `sg_vp_worker` with `SG_HAVE_GLSLANG`, like its only caller. This last fix also applies to a Linux build without the glslang library. |

## Playing in a browser

    tools/build-web.sh                 # build-web/: index.html, app.js, NFL2K5.js/.wasm, ...
    python3 tools/serve-web.py         # http://127.0.0.1:8080/

Open the page, import your disc, press Play.

- **Cross-origin isolation.** The game's threads share one wasm memory,
  which needs `SharedArrayBuffer`, which browsers only give a page served
  with `Cross-Origin-Opener-Policy: same-origin` and
  `Cross-Origin-Embedder-Policy: require-corp`. `tools/serve-web.py` sends
  them. On a static host that cannot (GitHub Pages and the like), the page
  registers `web/coi-sw.js`, a service worker that adds them, and reloads
  once. Off `localhost`, the page must be served over HTTPS.
- **Game files.** The page imports the player's disc into the origin's
  private file system (OPFS):
  - Sources: an Xbox disc image (`.iso`/`.xiso`, XDVDFS, including
    redump-style images with the game partition at an offset) or an
    extracted disc folder. For a folder, either the disc folder or the
    folder above it works.
  - How it is copied: `web/import-worker.js` copies it once, in a worker,
    through sync access handles. Nothing is uploaded.
  - Layout: `original/disc/...` plus `web-import.json`. The marker is
    written last, so an interrupted import never counts as installed.
  - The page shows whether `default.xbe` is the retail one this build runs.
  - A folder picker passes files only, so empty directories on the disc
    come through an image but not through a folder.
- **The game's view.** `src/platform/web/web_fs.c` mounts OPFS at `/nfl2k5`
  through WasmFS's OPFS backend and defaults `NFL2K5_ROOT` to it in
  portable mode. The disc is `/nfl2k5/original/disc`, and saves, logs and
  settings are written beside it in OPFS. The OPFS layout is the same one
  the importer writes. Re-importing replaces only `original/disc`; saves
  stay.
- **Launch.** The module is a factory (`-sMODULARIZE`, `createNFL2K5`) that
  the page calls on Play. `?env=NAME=VALUE` sets an environment variable for
  the game (for example `?env=RECOMP_APU_TRACE=1`), and `?autoplay=1` presses
  Play.

`tests/web/test_web_page.js` drives all of this in headless Chromium, and
`tools/test-web.sh` runs it when a full build exists. It checks:

- a synthetic disc (`tests/web/make_test_disc.py`) imports byte for byte
  from an image and from a folder;
- a non-disc file is refused;
- the page is isolated with the headers and through the service worker;
- the real module mounts OPFS, finds the disc, and stops at its hash check
  with the SHA-256 of the bytes it read, which must equal the imported
  `default.xbe`'s;
- the install survives a reload.

## Video, input and sound

The game's own SDL code runs unchanged; on the web it runs on workers
(PROXY_TO_PTHREAD), which changes four things.

- **Video.** The presenter thread (`video/fb_present.c`) creates the window
  on the canvas `#canvas`. SDL proxies the DOM work to the page's thread.
  WebGL can't be created on a worker without handing it the canvas, so the
  presenter uses SDL's software renderer, which draws each frame with
  `putImageData` (`SDL_HINT_RENDER_DRIVER=software` by default on the web).
  SDL's framebuffer code needs Emscripten's `Browser` library but doesn't
  declare it, so `fb_present.c` does (`EM_JS_DEPS`).
- **Window and keyboard events.** The browser delivers these to the thread
  that created the window as queued calls. A worker runs those only when it
  returns to its event loop, which the presenter loop never does, so the
  loop now runs its queue each pass. Keys are taken from the canvas only
  (`SDL_HINT_EMSCRIPTEN_KEYBOARD_ELEMENT=#canvas`). The page focuses the
  canvas at start, and clicking it gives the game the keyboard.
- **Controllers.** Browsers only reveal a gamepad after one of its buttons
  is pressed, through a connect event delivered the same queued way to the
  thread that initialised SDL's gamepad subsystem. On the web that is a
  small pump thread (`src/platform/web/web_sdl.c`), started first in
  `main()`. It initialises the subsystem before any game code can and runs
  its queue, so a pad that appears mid-game is seen.
- **Sound.** Browsers keep an `AudioContext` suspended unless it starts in a
  user gesture, and SDL creates its own context long after the click. So
  `web/launch.js` creates and resumes one inside the Play click, before any
  `await` (Safari requires that), and hands it to SDL as
  `Module.SDL3.audioContext`. If sound is still blocked, for example after
  `?autoplay=1`, a "Sound is off" prompt shows over the game and the next
  click or key press anywhere turns sound on. The context runs at 48 kHz,
  the APU's own rate.
- **Sound output: an AudioWorklet.** SDL's Emscripten audio pulls samples
  through a `ScriptProcessorNode` on the page's main thread, which is
  deprecated and stalls whenever that thread is busy. So the APU output
  (`apu/apu_xaudio2.c`) bypasses SDL on the web:
  - it writes its 48 kHz 16-bit stereo frames into a lock-free ring in
    wasm's shared memory (`apu/apu_web_audio.c`);
  - `web/audio-worklet.js`, an `AudioWorkletProcessor` on the browser's
    audio rendering thread, reads them straight from that memory, which a
    cross-origin isolated page may share with its worklet. Indices go
    through `Atomics`, and no wasm runs in the worklet;
  - if the browser runs the context at another rate, the worklet resamples
    linearly;
  - queue limits are unchanged from SDL's path: about 128 ms, with the
    1024-frame underrun cushion;
  - the worklet reports frames played, underruns, peak level and an
    estimated frequency, kept as `Module.nfl2k5Audio`;
  - browsers without `AudioWorklet`, or `?env=RECOMP_WEB_SDL_AUDIO=1`, use
    SDL's output as before.

Bug found on the way, affecting Linux too: the presenter's software
fallback called the GPU presenter function pointer in the branch where it
is NULL. That is a crash whenever the SDL GPU renderer is off, Linux's
default. The call is gone.

`tests/web/test_web_av.js` checks all of this in headless Chromium,
through a smoke module (`tests/web/smoke`) that runs the real presenter,
input and APU audio output without the game. It needs no generated code,
so CI runs it on every push. It checks:

- a guest framebuffer reaches the canvas;
- the APU output's 440 Hz tone plays through the AudioWorklet on the page's
  `AudioContext`, at 48 kHz and resampled at 44.1 kHz, with the right
  pitch (within 2%) and level, no underruns over 3 s, and SDL's output
  unused;
- with `RECOMP_WEB_SDL_AUDIO=1`, the tone goes through SDL's output instead;
- keys reach the game only while the canvas has focus;
- a controller connected after startup is seen and its button read (a
  Gamepad API stand-in fires the browser's real connect event);
- with no click, the prompt shows and a click turns sound on.

The last check emulates the autoplay block at the API, because Playwright's
navigation itself counts as user activation, so a real block cannot be
produced.

## Hardware rendering: WebGPU

The native builds' hardware renderer (xboxrecomp `src/kernel/sdlgpu/`, design
in its `docs/sdl-gpu-renderer.md`) draws through SDL 3's GPU API. SDL has no
WebGPU backend for that API (not in 3.2.20, and not on SDL's main branch as
of 2026-11-06). So the web build implements the part of the API the
renderer uses, 46 functions on SDL's own types, on WebGPU: Dawn's
`webgpu.h`, through Emscripten's `emdawnwebgpu` port.
`sdlgpu/webgpu/sdl_gpu_webgpu.h` redirects the renderer's calls there. The
renderer itself is unchanged except that it loads WGSL; 2D, 3D, the texture
cache, pipelines and presenting all come along.

- **One GPU thread.** A WebGPU device belongs to the JavaScript context that
  made it, and it only makes progress when that context returns to its event
  loop, which none of the game's threads do. So a server thread owns the
  device and stays in its event loop, and every call runs there through
  Emscripten's proxying queue. That makes the renderer's two caller threads
  (the pushbuffer executor and the window presenter) safe.
- **Commands.**
  - Command buffers are recorded on the caller's side and replayed into a
    `GPUCommandEncoder` at submit.
  - Submits are synchronous: upload data is copied into WebGPU before they
    return, and they wait for any downloads in them through `mapAsync`.
  - Queue writes run ahead of encoded commands, so an upload that follows
    GPU work splits the submission. That keeps SDL's ordering.
- **Binding layout.** Bind groups follow SDL's convention:
  - group 1: vertex uniforms;
  - group 2: four textures at bindings 0–3, their samplers at 4–7;
  - group 3: fragment uniforms;
  - uniforms are dynamic offsets into one buffer per submit.
- **Blits and mipmaps,** which WebGPU doesn't have, are small fullscreen
  render passes.
- **Shaders.** `tools/gen-wgsl.py` (in xboxrecomp) translates the four GLSL
  shaders with naga into `sdlgpu/webgpu/sg_wgsl.h`, which is committed.
  Rerun it after changing a shader (`cargo install naga-cli`). It splits
  combined samplers, rewrites the alpha-test switches as `if` chains (naga
  refuses `return` in a case), and turns off WGSL's derivative-uniformity
  check, since the per-stage branches are uniform per draw. Vertex programs
  compiled at run time need glslang, which the web build doesn't have, so
  they stay on the CPU, as on any Linux build without glslang.
- **Presenting.** The page has a `<canvas id="gpucanvas">` over SDL's canvas
  (with `pointer-events: none`, so input stays with SDL's).
  - `-sOFFSCREENCANVASES_TO_PTHREAD=#gpucanvas` hands it to the program's
    main thread at startup, and `wg_server_start()` passes it on to the GPU
    thread (by bare id: that's how a thread keys a canvas it holds).
  - Claiming the window shows it.
  - A frame appears when the GPU thread returns to its event loop after the
    submit that drew it. The canvas's texture is fetched in that same task,
    since it expires at the end of the task.
  - Acquiring a swapchain texture waits for the next animation frame, which
    paces the presenter at the display rate where natively it waits for
    vsync.
- **On by default.** At startup `src/platform/web/web_sdl.c` starts the GPU
  thread. With a device, `RECOMP_SDLGPU=1` is the default; without WebGPU
  the game draws in software. `?env=RECOMP_SDLGPU=0` forces software.

Every page that loads a module with this kernel needs a `#gpucanvas`, and the
module links with em++, because the WebGPU port's library is C++.

Tests, in headless Chromium with WebGPU on SwiftShader (flags in the tests):

- `external/xboxrecomp/tests/sdlgpu_web` drives the redirected API as the
  renderer does: the generated WGSL, its vertex layout and formats, its pass
  structure. 20 checks:
  - clear and download, byte for byte;
  - unaligned upload/download;
  - flat 2D orientation, texturing with point sampling and wrap, alpha
    test, blending, scissor including out-of-range rectangles;
  - depth load and clear ops and the depth test;
  - mipmap generation;
  - the 3D pipeline with stencil;
  - presenting, with the canvas read back;
  - no WebGPU validation errors.
- `tests/web/test_web_av.js` registers a presenter written like the
  renderer's in the smoke module. `fb_present.c` hands it the window, the
  overlay shows its frame, and presents run at 60 per second, paced by
  animation frames.

The renderer's own test (`tests/sdlgpu_posix`) no longer compiles against
the renderer upstream: the renderer reads executor state (`s_vp`,
`s_stage`, `Texture`, `VP_CONSTS`, …) that the test doesn't stand in for.
So the renderer's logic on WebGPU is tested only through the game, once it
boots.

## Guest address space

A native host maps each guest region at `base + guest address` and turns a
guest address into a host pointer by adding one offset. Around 430 places in
the runtime do exactly that (`xbox_GetMemoryOffset() + va`, `XBOX_TO_NATIVE`,
the GPU, APU and USB device models), as does every `MEM*` access in the
generated code. So the web build keeps the arithmetic and makes the linear
memory the address space.

- **Identity layout.** Guest address `va` is wasm address `va + 0x10000` (the
  offset the layout init picks, as on Linux). This covers:
  - RAM at 0x10000;
  - the contiguous window at 0x80010000;
  - the tiled aperture, NV2A, MCPX and flash at 0xF0010000 to 0xFF110000.
- **Host kept out.** The host's static data, stack and heap start at
  `-sGLOBAL_BASE=0x08100000`, above 128 MB of RAM. `sbrk` is wrapped
  (`-Wl,--wrap=sbrk`) so the heap stops below 0x80000000, which leaves
  about 1.86 GB for the host.
- **The mapping shims.** In `platform/wasm_fixed.{h,c}`, a
  `VirtualAlloc`/`MapViewOfFileEx` at an address succeeds exactly when the
  range lies in one of those windows and no other mapping holds it. Memory
  grows to cover it. Memory is reserved virtually but only resident where
  touched, as with mmap.
- **No aliasing.** Linear memory cannot alias, so there are no RAM mirrors
  and the tiled aperture is separate memory. Generated code folds mirror
  addresses itself: `XBOX_PTR` takes any address below 2 GB modulo 128 MB,
  in four branchless integer operations. That is the hardware wrap, and it
  also keeps a stray guest pointer out of the host heap.
  `-DNFL2K5_WEB_TILED_FOLD=ON` also folds 0xF0000000..0xF3FFFFFF onto the
  contiguous window. It is off by default, because nothing shows NFL 2K5
  using tiled addresses.
- **Checked copies** (`guest_memory.c`) accept only ranges inside a fixed
  mapping, so a device model that follows a bad pointer is refused as on a
  native host, and does not read the host heap.

**Cost.** The fold and the APU accessors together made the module 31%
larger, 37.9 to 49.5 MB. Most of that is presumably the fold, which is on
every guest access, whereas the accessors are in 729 of 33,671 functions;
the split was not measured. Neither has the run-time cost; that is M3.

## Audio registers without faults

Natively, the APU's register window (0xFE800000..0xFE87FFFF) faults on every
access, and the fault handler replays the instruction into the emulated APU.
Many of those accesses are voice-processor command writes, so polling would
lose them. On the web, `tools/gen-web-devices.py` runs at configure time and
rewrites the guest's DirectSound code instead:

- **What it selects.** Every function that names an APU register address,
  plus every function in the library they cluster in. That is 729 functions
  (0x443679..0x453C6C), and the rewrite routes 6,595 reads and 2,712 writes.
- **What the rewrite does.** Each `MEM*` access in those functions becomes a
  `RECOMP_DEV_*` accessor (`src/platform/web/recomp_web_dev.h`). The
  accessor sends the APU window to `mcpx_apu_mmio_read/write` and anything
  else to memory, with the same exemptions as the native trap (the GP/EP DSP
  memory windows stay plain).
- **How it guards itself.** Every rewritten function is checked by undoing
  the rewrite and comparing, so a construct the script does not understand
  fails the build.
- **What it catches at run time.** If the APU window or the tiled aperture
  is ever written as plain memory, the runtime warns once
  (`wasm_unrouted_check`), which would mean an access the rewrite missed.

AC97 needs no rewrite. The native trap only makes a channel reset's RR bit
read back clear, and NFL 2K5's reset site already does that through the
`AC97_RESET_ACK` generated-code patch. On the web the trap is skipped with a
message instead of failing boot.

## The xboxrecomp patch

The submodule points at `BeyondTomrrow/xboxrecomp` (`nfl2k5-port`). Until its
changes are committed there and the submodule is bumped, they live in
`config/xboxrecomp-web.patch`. To regenerate the patch after editing the
submodule:

    git -C external/xboxrecomp add -A
    git -C external/xboxrecomp diff --cached > config/xboxrecomp-web.patch
    git -C external/xboxrecomp reset -q

(`--cached` so new files such as `platform/wasm_fixed.c` are included.)

Once the fork carries the changes, delete the patch and its step in
`tools/build-web.sh`.

## Known gaps (M2 and later)

These compile today but are inert or wrong at run time:

- **Aliasing.** There are no RAM mirrors and no tiled alias for *runtime*
  code that adds the memory offset to such an address by hand; generated
  code is covered by the fold. Nothing in NFL 2K5 is known to need this.
- **Audio has not been heard.** The APU routing is tested against a fake
  APU, and the layout init with the APU path runs under Node. The real
  DirectSound handshake can only be exercised once the game boots.
- **Not booted with the retail disc.** Past the XBE check, expect whatever
  stalls the browser's thread scheduling brings out. Neither renderer's
  speed in a browser has been measured. The WebGPU renderer has run the
  API checks above but not a game frame. Every create and submit is a
  round trip to the GPU thread (about 80 µs), which may matter with many
  small submits.
- **Audio latency** is the native build's: about 128 ms queued, which is
  generous for a browser. It hasn't been tuned against real game load.
- **Not tried on the web yet:** fullscreen, pointer lock for "mouse as
  controller", rumble, and a remapping of F1/F2 away from browser
  shortcuts. Keys still work while the canvas has focus.
- **Storage.** The import needs room for the whole disc. The page asks for
  persistent storage; if the browser declines, it may clear the disc (and
  saves) under storage pressure. There is no save export yet.
- **Running twice.** The game's exit is not reported to the page (the
  runtime stays alive for its threads), so after a run ends, reload to run
  again.
- **Presentation packages, FMV, mod-pack overlays, Discord.** These are off,
  as on Linux. Mod packs also run through `x86_interp`, whose memory accesses
  are not routed to the APU.
