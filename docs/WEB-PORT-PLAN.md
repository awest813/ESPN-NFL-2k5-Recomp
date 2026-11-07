# Web port: audit and plan

Status: plan only, no web code exists yet. Audited 2026-11-06 against
`4ee0613` (this repo) and xboxrecomp `9a31daa` (`nfl2k5-port`).

## Verdict

A browser build is feasible, and the existing POSIX/SDL3 port gets most of
the way there. The recompiled code is plain portable C that reaches guest memory
through one macro (`XBOX_PTR`), and the SDL3 layer already covers windowing,
input and audio on Emscripten. The real work is in four places:

1. **Guest address space.** Guest RAM is at 0x0, but other guest regions sit at
   0x80000000, 0xF0000000 and 0xFD000000 and above. In wasm32 that space
   has to be compacted, which means changing `XBOX_PTR`.
2. **Tricks that rely on faults or the OS.** This covers the AC97 write
   trap (SIGSEGV plus single-step), `process_vm_readv` probing, `shm_open`
   mirrors and `/proc/self/maps`. All of them need a wasm replacement.
3. **GPU backend.** SDL_GPU at the pinned SDL 3.2.20 has no WebGPU backend.
   It needs either a WebGPU backend behind the existing five-function
   renderer contract, or the software rasterizer to start with.
4. **Performance.** About 220 MB of generated C becomes a large wasm module.
   Every guest access is `volatile`, and the APU/NV2A emulation threads
   already use most of a native core each.

Recommended order: get Linux playing end to end first, because the web build
inherits every POSIX bug. Then bring up the browser build with the software
rasterizer behind a cross-origin-isolated page. Add WebGPU after that.

## 1. What was audited

| Area | Finding |
|---|---|
| Generated code | `src/recomp/gen`: 34 chunks, **33,671 functions, 220 MB of C**. The largest file is `recomp_0010.c` at ~30 MB. The largest function is `sub_00EC5E28` at ~1.66 MB of C, then several at ~330 KB. |
| Code model | `void f(void)` functions. Guest registers are `RECOMP_TLS` globals (`g_eax`…`g_edi`, `__thread` on GCC), or locals in the `NFL2K5_REG_LOCALS` copy. Indirect calls go through `recomp_dispatch.c` (a 33.6k-entry table) and fall back to `src/interp/x86_interp.c`. |
| Memory access | `MEM8/16/32/F/D` → `*(volatile T*)XBOX_PTR(addr)`, where `XBOX_PTR = (uint32_t)addr + g_xbox_mem_offset` (`recomp_types.h:389`). There is one choke point and no raw host pointers in generated code. |
| SIMD | A small set of SSE1 intrinsics through `<xmmintrin.h>` (`recomp_types.h`). Emscripten maps these to wasm SIMD with `-msimd128`. There is no inline asm in game or runtime code (the only hits are stb and the D3D11 backend). |
| SEH / setjmp | Guest setjmp/longjmp is bridged onto native `jmp_buf` (`xbox_memory_layout.c:1512`). Emscripten supports this (`-sSUPPORT_LONGJMP=wasm`). |
| Threads | `CreateThread` → `pthread_create` (`platform/win32_compat.c:937`). Timers and threadpool also use pthreads. A perf capture shows the main guest thread, `fb_thread` (present), `sg_vp_compile` (shader compile), an I/O worker (`nfl2k5_io_worker`), APU and vblank/state threads all busy at once. `SuspendThread` is a counter, not a real suspend, which is fine on the web. |
| Guest memory map | 128 MB devkit RAM (`main.c:780`) at guest 0. Contiguous window at 0x80000000 (64 MB), tiled view at 0xF0000000, NV2A aperture at 0xFD000000 (16 MB, plain RAM plus poll threads), MCPX at 0xFE800000 (8 MB), flash at 0xFF000000. Kernel thunks use synthetic VAs at 0xFE000000. |
| OS-specific mechanisms | AC97 trap: `mprotect` + SIGSEGV + TF single-step (`xbox_memory_layout.c:361-500`). `process_vm_readv` probing and a `/proc/self/maps` parse (`platform/guest_memory.c`). `shm_open` file mappings (`win32_compat.c:1861`). On POSIX the NV2A/APU VEH hooks are already inert (`AddVectoredExceptionHandler` is a stub, `win32_compat.c:2173`). 49 `__linux__` guards in 6 runtime files. |
| GPU | `nv2a_pb_exec.c` (pushbuffer executor) has a software rasterizer plus a hardware contract of five functions (`gpu_enabled/draw_batch/clear/flip/cpu_access`; see `xboxrecomp/docs/sdl-gpu-renderer.md`). Backends: D3D11 on Windows and SDL_GPU on Linux (Vulkan, GLSL→SPIR-V at build time with glslang). There is also `d3d8_gl.c` and libepoxy in the Linux deps. |
| Audio | MCPX APU emulation (`apu/`, `mcpx_apu_vp_frame` is the top native hotspot), a WMA decoder, and SDL3 audio output on POSIX. |
| FMV | `video/video_player.c` is Media Foundation only. POSIX has no decoder, so the web has none either. |
| File I/O | Plain POSIX `open/pread` with backslash-to-slash conversion (`kernel_file.c`, `win32_compat.c:1613`). The game expects an extracted disc under `original/`. |
| Windows-only extras | WebView2 HTML presentation host, Direct2D/MF/XAudio2 presentation renderer, Discord RPC, the D3D11 renderer, `.2k5patch` disc overlays (`kernel_overlay.c`), and DDS textures. Linux already stubs these (`src/platform/posix/presentation_stub.cpp`). |
| Tools | The Team Creator, team builder and save converter are Python/Tkinter, and the installer is Inno Setup. None of them are part of the runtime. |
| Linux maturity | `docs/LINUX.md` says the game is "not played end to end yet". The SDL3 GPU path draws menus and the field as of recent commits. Four `NFL2K5_FORCE_UNBLOCK_*` bypasses are required to boot (netpoll, audio lock, 33660 drain, state-9 ready). |

## 2. Portability matrix

Effort scale: S = days, M = 1–3 weeks, L = more than a month (rough,
one developer).

| Component | Web blocker | Approach | Effort |
|---|---|---|---|
| Toolchain | 220 MB of C through `emcc`. Clang's memory use per TU is similar to GCC's (~2 GB for the largest). | Add an `EMSCRIPTEN` branch to the root `CMakeLists.txt` next to the POSIX branch, with `-O2 -msimd128 -fno-strict-aliasing -fwrapv -pthread -sSUPPORT_LONGJMP=wasm`. Build the `REG_LOCALS` copy (fewer TLS accesses). | S |
| Guest address space | wasm32 linear memory is 0…4 GB, shared with the host heap. Guest regions span 0x0–0xFFFFFFFF. | Compact the address space: keep guest RAM (0–128 MB) at a fixed linear offset and remap the high regions (contig, tiled, NV2A, MCPX, flash, thunks) into a ~256 MB block above it. `XBOX_PTR` becomes `addr < RAM_SIZE ? base+addr : base + seg[addr>>22] + (addr & 0x3FFFFF)`. Use a well-predicted branch or a 1024-entry table, chosen by benchmark. Check whether 0x80000000 must alias physical RAM (Xbox semantics) or stays a separate block as it is today. memory64 is a later option that removes this, but it is not on Safari and is slower on V8. | M |
| Mirrors / `shm_open` | No page aliasing in wasm. | `XBOX_MIRROR_SIZE` is already 0. Mask any aliasing range in the `XBOX_PTR` slow path instead of mapping views. Stub `shm_open` mappings with plain allocations. | S |
| Checked guest reads (`guest_memory.c`) | No `process_vm_readv` and no `/proc`. | Add a third implementation: a bounds check plus `memcpy`, because wasm cannot fault inside linear memory. `xbox_guest_memory_direct()` returns true for all RAM. This is simpler than either existing implementation. | S |
| AC97 write trap | No signals, `mprotect` or single-step. Code guarded by `__linux__ && __x86_64__` simply drops out under Emscripten, so audio could hang silently. | Replace the trap with polling of the AC97 page from the audio thread, or override the handful of DSOUND/XAPI functions that touch AC97 in `recomp_manual.c` so they call the device model directly. Add a test next to `tests/ac97_posix`. | M |
| NV2A/MCPX poll threads | Spin threads keep register values in plain RAM, so this works with pthreads. | No change apart from budgeting cores (see Performance). | S |
| Threads and blocking waits | `Atomics.wait` is forbidden on the browser main thread. pthreads need SharedArrayBuffer, which needs COOP/COEP headers. | `-sPROXY_TO_PTHREAD` so the guest main runs on a worker, with `-sPTHREAD_POOL_SIZE` around 12 created up front (pthread creation needs a main-thread turn). Serve with `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp`, using a header-setting service worker (coi-serviceworker) on static hosts. | M |
| Video out (software path) | SDL3 presents to `<canvas>`. Software rasterizer speed is already "too slow for a match" natively. | Use it for bring-up and menus only: `fb_present.c` → SDL3 → canvas. | S |
| GPU (hardware path) | SDL_GPU 3.2.20 has no WebGPU backend, and SPIR-V is not valid WGSL. | Option A (recommended): a WebGPU backend behind the same five-function contract, written against `webgpu.h` (Emscripten's `emdawnwebgpu` port), with the GLSL shaders converted to WGSL at build time (naga or tint). Ownership rules (GUEST/GPU surface owner) carry over unchanged. Option B: if upstream SDL has landed a WebGPU SDL_GPU backend by then, retarget `sdlgpu/` to it and supply WGSL. Check upstream before starting. Option C: WebGL2 by reviving `d3d8_gl.c`/epoxy-style GL ES 3.0. This reaches more browsers but limits w-buffer and fog fidelity. | L |
| Audio out | SDL3 on Emscripten uses Web Audio. The APU mix is CPU-heavy. | SDL3 audio works as is. Unlock audio on first user gesture. Raise the buffer size to absorb worker jitter. Later, move the final mix to an AudioWorklet that reads a SharedArrayBuffer ring (done: [WEB.md](WEB.md), "Video, input and sound"). | S → M |
| Input | Gamepad API and keyboard. | SDL3 maps both. Rumble support depends on the browser (`vibrationActuator`). Disable the F1 browser-help conflict by capturing keys on the canvas. Use Pointer Lock for "mouse as controller". | S |
| Game files | Multi-GB disc. Retail data cannot be hosted. | A first-run page picks the user's ISO/XISO or extracted folder (File System Access API, `<input webkitdirectory>` fallback). Extract in-browser by porting `tools/xiso_read.py` logic to C/JS. Store it in **OPFS**. Expose it to the runtime with WasmFS + OPFS backend (sync access handles work in workers), so `kernel_file.c`'s `open/pread` keep working unchanged. Hash-check `default.xbe` against the retail SHA-256 the build expects. | M |
| Saves / settings / logs | No `%LOCALAPPDATA%`. | WasmFS OPFS directories `/saves`, `/config`, `/logs` survive reloads. Add Export/Import zip buttons (miniz is already linked). Keep the `saves/import/` flow. | S |
| Presentation packages (HTML) | The WebView2 host is Windows-only. | **Natural fit for the web.** Implement `PresentationHost` as a same-origin `<iframe>` overlay above the canvas, and post the existing JSON state/events with `postMessage`. The browser does the compositing, so no off-screen capture is needed. The page messages already use JSON strings (`docs/PRESENTATION-SYSTEM.md`). | M |
| FMV (XMV) | There is no decoder on POSIX either. | Short term: skip FMV as Linux does. Later: an XMV/WMV decoder in C (shared with Linux), or WebCodecs if the streams are transcodable. | M |
| Local music | No folder access by default. | Let the user pick a folder through the File System Access API. Decode MP3/OGG/WAV with `decodeAudioData`. WMA goes through the runtime's existing `wma_decoder.c`. | S |
| Texture packs / mod packs | DDS is unsupported on POSIX. Disc overlays are Windows-only. | PNG/JPEG packs dropped into OPFS `mods/textures` work. Mod packs (`.2k5patch`) wait until `kernel_overlay.c` is made portable, which is shared work with Linux. | M |
| Discord RPC, WebView2, MF, XAudio2, D3D11 | Not applicable. | Leave out of the web target, as the POSIX branch already does. | – |
| Team Creator, installer | Python/Tk and Inno Setup. | Out of scope for the web runtime. A later option is Pyodide, or a JS rewrite of the recolour and roster steps, writing into OPFS `mods/teams`. | – |

## 3. Performance budget

This is the main risk and needs measurement before committing to milestones
beyond M2.

- **Code size and startup.** Expect a wasm module of roughly 60–150 MB, to be
  measured in M1. Mitigations:
  - serve with Brotli and `WebAssembly.compileStreaming`;
  - rely on the browser's code cache across visits;
  - build with `-O2` and no `-g` for release, and keep names in a separate
    `.symbols` file.
  - V8's per-function body limit is about 7.6 MB. `sub_00EC5E28` is about
    1.66 MB of C, so it should fit, but check it in M1.
- **`volatile` on every guest access.** This blocks load/store combining and
  register allocation across accesses. Try a build flag that emits plain
  (non-volatile) `MEM*` for ordinary RAM and keeps volatile only for device
  apertures. That needs a lifter change, and it may also help native builds.
- **TLS registers.** Under Emscripten pthreads every `g_eax` access is
  `__tls_base + off`. The `REG_LOCALS` build already removes most of these.
- **Threads compete for cores.** On native builds the main guest thread,
  `fb_thread`, the APU and `sg_vp_compile` are each close to a full core.
  The web adds roughly 1.3–2× CPU overhead on top. Targets:
  - 60 fps in menus on the software path on an 8-core desktop;
  - 60 fps in a match only with the WebGPU backend, plus a pipeline cache
    (`sg_vp_compile` becomes WGSL pipeline creation, which is already
    asynchronous in WebGPU).
- **Memory.** Declare `-sINITIAL_MEMORY=1GB -sMAXIMUM_MEMORY=4GB` with
  growth. Shared memory growth with pthreads works, but it is slow under JS
  heap views, so start large. This requires a desktop browser; iOS Safari is
  out of scope.

## 4. Milestones

Each milestone has an exit check that can be run in CI or by hand.

**M0: prerequisites (on Linux, no web code)**
- Linux plays a full Quick Game end to end (`docs/LINUX.md` "not played" →
  played).
- Remove, or root-cause, the four `FORCE_UNBLOCK` bypasses that POSIX
  depends on. If they stay, document that the web build carries them.
- Exit: a scripted Linux run reaches kickoff. The generated code builds with
  Clang on Linux (`CC=clang`), which catches GCC-only constructs before
  `emcc` does.

**M1: it compiles and links** (done 2026-11-06; see [WEB.md](WEB.md))
- Add an `EMSCRIPTEN` branch to `CMakeLists.txt` and xboxrecomp's
  `CMakeLists.txt` (link SDL3's Emscripten port with `-sUSE_SDL=3` or a
  pinned SDL build, and drop OpenSSL in favour of the existing
  `kernel_crypto.c` or a small SHA-256).
- Add `__EMSCRIPTEN__` arms for `guest_memory.c`, `xbox_memory_layout.c`
  (allocation, no mprotect/signals) and `win32_compat.c` (`shm_open`,
  `/proc`).
- Exit: `NFL2K5.wasm` links in CI. Record its size, compile time and the
  largest function's wasm size in this document.

**M2: boots to the first menu (software rendering)**. In progress: the
address space, the AC97 replacement, OPFS game files with a disc importer,
the COOP/COEP page (server headers or a service worker), and SDL video, input
and the audio unlock on workers are done (see [WEB.md](WEB.md)). What remains
is booting the retail disc. The
address space uses an identity layout with a fenced host heap, not the
segment table sketched below, so the ~430 runtime sites that add the memory
offset need no change.
- Compact guest address space (`XBOX_PTR` rework), with a unit test next to
  `tests/memory_layout_posix` that runs under Node with
  `--experimental-wasm-threads`.
- WasmFS with an OPFS backend, plus a first-run page that loads the disc
  into OPFS and checks `default.xbe`.
- PROXY_TO_PTHREAD, a COOP/COEP static server script (`tools/serve-web.py`)
  and a coi-serviceworker for GitHub Pages-style hosting.
- AC97 replacement and SDL3 audio.
- Exit: the title screen and main menu render in Chrome and Firefox with
  sound and gamepad, and saves persist across a reload.

**M3: playable, slowly**
- Fix wasm-only stalls. Expect timing-sensitive waits to behave differently
  under worker scheduling.
- Profile with Chrome DevTools. Try the non-volatile `MEM*` build.
- Exit: a Quick Game can be played to the end on the software path. Record
  fps in `docs/BENCHMARKS.md`.

**M4: WebGPU renderer**
- Port `sdlgpu/` to `webgpu.h` behind the five-function contract, converting
  the shaders to WGSL at build time. Present directly from the GPU texture to
  the canvas (the same design as the latest xboxrecomp "present from the GPU"
  commit).
- Exit: 60 fps in a match at 2× internal resolution on a mid-range desktop
  GPU in Chrome. Falls back to software where `navigator.gpu` is missing.

**M5: web-native extras**
- HTML presentation packages as an iframe overlay (FOX/CBS/NBC).
- Local music picker, texture packs in OPFS, save import/export.
- An F1 settings menu that skips the browser shortcuts.
- Exit: the presentation packages in `mods/presentations` work in the
  browser.

**Later:** mod packs (`kernel_overlay.c` made portable), FMV decoder, Team
Creator in the browser, memory64 build.

## 5. Distribution and legal constraints

- As with the Windows installer, the page must never host or fetch retail
  data. Everything from the disc is read from the user's own copy and stays
  in their browser's OPFS.
- The `.wasm` contains the recompiled game code, just as `NFL2K5.exe` does.
  Hosting it publicly is the same distribution question as the current
  GitHub Releases, so decide it the same way. A safer default is to publish
  the build scripts and let users build or self-host.
- COOP/COEP isolation blocks cross-origin embeds without CORP headers.
  Presentation packages must therefore be same-origin (served from OPFS
  through the service worker), which also matches the current
  `presentation.local` virtual-host design.

## 6. Open questions to settle early

1. Does the game rely on 0x80000000 aliasing guest RAM (Xbox physical
   semantics), or is the separate contig block correct? This decides the
   `XBOX_PTR` layout.
2. Which functions touch the AC97 page, and how often? This decides between
   polling and overrides.
3. Has upstream SDL shipped a WebGPU SDL_GPU backend, and with which shader
   format? This decides between options A and B in the GPU row.
4. What wasm size and startup time does M1 actually produce? If it is far
   above 150 MB, consider splitting rarely used chunks with dynamic linking
   (`-sMAIN_MODULE`/side modules), at some cost to indirect calls.

## 7. Repository findings from the audit (not blocking)

- Debug captures are committed despite `.gitignore`: `perf.data.old`
  (5.8 MB), `probe.txt` (745 KB), `uvtrace.txt`, `watch.txt`,
  `xbox_kernel.log`, `xemu.log`, `perf_*.txt`. Consider `git rm --cached`.
- `src/recomp_manual.c.bak` and `src/rebuild/New Text Document.txt` are
  stray files.
- `config/xboxrecomp-revision.txt` says `6bfcc77…`, but the submodule is
  pinned at `9a31daa…`. Update one so they match.
- The README badge and clone URLs point at `BeyondTomrrow/2K5Remade`, not
  this fork.
- `PROJECT_STATUS.md` is 478 KB. A web-port section should go in this file
  instead.
