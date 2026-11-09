# Rendering and performance comparisons

## Stadium and intro rendering — November 8, 2026

The SDL GPU renderer now honors guest face culling by default; the previous
opt-in left the backs of near-side stands visible over stadium views.
`RECOMP_CULL=0` remains available for comparisons. CPU-transformed and GPU
vertex draws use the same policy; two-sided affine intro geometry is preserved
when the game disables culling.

Texture minification no longer inherits the magnification filter. The seven
NV2A minification modes select texel and mip filtering separately; linear RTTs
and LOD0 filters do not sample generated mip levels. The fragment shader also
emulates per-stage clamp-to-border colours, which SDL/WebGPU samplers cannot
express, rather than repeating the last texel of intro text/glow textures.
These mappings were checked against [xemu's sampler implementation](https://github.com/xemu-project/xemu/blob/master/hw/xbox/nv2a/pgraph/vk/texture.c).

Exact browser pixels cover transparent edges/corners, custom border colours
and XRGB alpha. Native tests cover culling and uniform packing. This is not
verification of every stadium or every staff model, and authored mip images,
LOD bias/clamp fidelity and matched Xbox reference captures still need work.

The [expanded stadium/staff check](WEB-STADIUM-FIDELITY.md) adds Minnesota's
enclosed roof and close replay views of photographers, a kneeling cameraman
and event staff. It records the exercised views and remaining fidelity limits.

## Earlier comparisons — November 7, 2026

Reviewed November 7, 2026, while fixing player lighting and measuring the
WebGPU port. These are architectural comparisons, not FPS comparisons
between different games or machines.

| Project | Relevant approach | Implication for NFL 2K5 |
| --- | --- | --- |
| [Ninja Gaiden Black recomp](https://github.com/gamboozino/ngbrecomp/blob/master/docs/renderer.md) | Hooks Xbox Direct3D calls and translates vertex programs for a Vulkan renderer. Its documentation measures which calls and inlined state the game actually uses. | GPU vertex-program execution is the main remaining opportunity here. Moving to Direct3D hooks would require a separate audit of NFL 2K5's pushbuffer writes and device state. |
| [GTA3-WASM](https://github.com/Antriksh1984/GTA3-WASM/blob/main/manual.md) | Builds the reverse-engineered re3 engine for WebAssembly and WebGL2, with local game-data import. | Useful browser integration reference. Its renderer starts from engine source, so it does not establish the cost of interpreting NV2A vertex programs. |
| [Devil May Cry 3 recomp preview](https://github.com/sindufha/Devil-may-cry-3-recomp/blob/main/docs/TROUBLESHOOTING.md) | Android project targeting a specific PC executable. Its performance guidance compares matching gameplay scenes and records driver, resolution and device conditions. | Record the matchup, camera and presentation state when comparing profiles. Menu FPS cannot establish gameplay performance. |

## Current NFL 2K5 measurements

`RECOMP_SDLGPU_PROFILE=1` separates texture preparation, CPU vertex
processing and submission timings. Texture preparation can flush draws,
so those timings can overlap. The log also reports rendered frames.

The browser now translates NV2A vertex programs directly to WGSL and runs
them on WebGPU. The profiler's `vp` count reports these draws. Programs
that write constants and affine presentation programs retain the CPU path.
Use `RECOMP_SDLGPU_NOVP=1` for a comparison with CPU processing.

GPU inputs contain only referenced attributes, packed without gaps.
Compatible render-target textures stay on the GPU, including snapshots of
the current target, with XRGB alpha preserved. Texture hash memoization
handles aligned guest addresses; material bindings survive across frames
and are invalidated on texture destruction.

The CPU fallback decodes instruction fields once per batch and avoids
redundant uniform uploads and bindings. `tests/web/test_vp_interpreter.py` compares the live
interpreter against a frozen pre-optimization reference. The focused
24-instruction benchmark measured about 1.23–1.25 times the throughput
in local runs. This is not an end-to-end game FPS measurement.
`tests/web/test_vp_wgsl.py` and its JavaScript runner compare 2,048 GPU
vertex executions against the CPU oracle, including temporary registers,
and render through the production packed attribute layout.

## Gameplay verification

A two-minute local Chrome test on November 7, 2026 averaged **37.2 FPS**
across the kickoff return and first offensive plays of Indianapolis at
San Francisco. The 24 five-second samples ranged from **28.5 to 51.9 FPS**.
This exceeds 30 FPS on average; heavy views still briefly dip below 30.
Later offensive views in the extended run reached 26.1 FPS, so this is
not a locked 30 FPS result.
The test used hardware WebGPU on Intel `gen-12hp`, default web video/crop
settings and `RECOMP_SDLGPU_PROFILE=1`. It recorded zero CPU vertex
fallbacks and zero render-target readbacks throughout the sample.
[Recorded samples](performance/2026-11-07-web-gameplay.json) preserve the
frame counts and stage timings. This covers the tested sequence rather
than a complete match or every hardware configuration.

The final fixes include direct WGSL vertex programs, packed and validated
input streams, GPU surface snapshots and material reuse, and an 8,192-entry
pipeline pool with hashed lookup. The old 1,024-entry pool filled during
offensive gameplay and forced draws back onto CPU vertex processing.

Player lighting now implements the retail dependent dot-product stages
and true cube textures. Chrome captures confirm visible jersey folds and
lighting, but full fidelity still requires matched Xbox or xemu captures.
Presentation sequences and gameplay also need broader performance work.

## Further browser CPU reductions

The next pass adds verified texture-cache hints, defers CPU-fallback pipeline
creation until needed, packs dense vertex ranges as streams, and coalesces
adjacent draws whose pipeline, uniforms, textures, clipping, blend and stencil
state all match. It also avoids redundant blend/stencil/scissor commands.
`merged` in the profile reports saved draw calls per frame; `decode-ms`
separates texture decoding from texture preparation's overlapping flush time.

Full DXT uploads now decode each 4×4 block once, retaining the original
sampler as an oracle. Randomized tests compare 900 DXT1/3/5 images, including
partial blocks and alpha edge cases. Another 600 cases verify linear
ARGB/XRGB uploads with padded, unaligned and zero-pitch rows. The local
DXT5 upload microbenchmark measured about **3.4×** faster decoding; this is
not an end-to-end FPS result.

The launcher now offers a live 30 FPS cap. The host pacer releases the guest
lock while waiting and avoids adding a second guest-vblank wait. Longer
gameplay tests still exposed sub-30 samples, so the minimum-FPS target is
not considered met. Short samples above 30 do not establish a sustained
floor, and CPU profiles/builds must not run alongside acceptance measurements.

The handle registry now widens
pointer keys before its 33-bit hash shifts, which were undefined on wasm32.
Tests cover 10,000 aligned handles through
registry growth, invalid lookups, removal and tombstone reuse.

A direct browser-clock path was faster in isolation but did not improve
the menu comparison, so clock reads retain the existing timespec path.

The background MMIO acknowledgement thread remains a CPU hotspot:
Emscripten's `sched_yield` only processes its event queue. A one-millisecond
sleep was tested and removed after it caused severe startup stalls while
guest interrupt handlers waited for register acknowledgements. Replacing
this poller requires preserving that handshake's latency.

## Device timer overflow and gameplay stalls

The QEMU compatibility clocks scaled QPC with `counter * units / frequency`.
The browser's epoch-based nanosecond counter overflows that signed 64-bit
intermediate, corrupting the APU free-running timer and GPU PTIMER. They now
scale whole seconds and the remaining fraction separately. Regression tests
run the production conversions under undefined-behavior checks with epoch
values, three QPC frequencies, the old overflow boundary, and the APU's
expected 32-bit timer wrap. The old conversion fails this test.

Browser D3D fence waits now park on the shared semaphore and release the
guest lock until the renderer publishes progress. Fence publication uses an
atomic compare/exchange: a completed-kick snapshot cannot overwrite a newer
semaphore release. Wrap-aware comparisons also accept a renderer which has
already progressed beyond the requested fence. Wasm pthread tests cover
publication races, stale snapshots, multiple waiters, spurious wakes and
restoring the guest lock after wakeup.

`RECOMP_APU_LOCK_PROFILE=1` logs audio processing time and per-thread waits
for the audio register lock, separating mixer contention from GPU waits.
It exposed a 733 ms register-write wait during gameplay. The mixer now
hands pending MMIO writers the mutex between voice frames, even while
catching up without a throttle sleep. Writes still serialize against each
complete voice frame. A threaded test reproduces that continuously busy
mixer and verifies 10,000 writes, continued mixing and shutdown.
