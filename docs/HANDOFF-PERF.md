# Performance handoff (2026-10-03)

## Current native verification checkpoint (2026-11-20)

The October measurements below are historical runs, not current proof of a
30 FPS floor or of the present runtime's native gameplay behavior. Current
retail browser captures still show stalls and audio starvation; see
`docs/WEB-STADIUM-FIDELITY.md` for those failures.

Windows CI previously built the pinned runtime without the published
`config/xboxrecomp-web.patch`, whereas Linux/Web applied that overlay. The
Windows job now applies the same cross-platform fixes before building. The
submodule remains pinned to `9a31daa67c22893f5b0ebed8f3f7b01970d364ef`.

Local optimized Windows runtime and tools build successfully with MSVC
19.44.35228 and SDL 3.2.20. The initial runtime/tools check disabled the game
target. The full executable was linked and exercised later in this checkpoint.
Compiler warnings, including existing NV2A macro redefinitions, remain in the log.

`tests/native-dsp` reuses the production-core DSP fixtures for native builds.
Optimized MSVC passes 141,664 cold/warm full-state dispatch comparisons,
software interrupt retirement, executable upload invalidation, firmware,
bootstrap, idle and scratch/FIFO DMA checks. Release assertions stay enabled.
Windows and Linux CI run these checks. See its README for reproducible commands.

The optional dispatch benchmark now uses QueryPerformanceCounter on Windows
instead of millisecond-resolution `clock()`. In the local five-round sample,
reference/current medians for two million instructions are 25.999/25.205 ms
for program 0 and 27.104/25.104 ms for program 1. Individual pairs are noisy,
including a regression in program 1's first pair. This compares the existing
handler cache with the older reference dispatcher on synthetic programs;
there is no new runtime optimization in this checkpoint and no inferred FPS
gain. It supplies a native correctness and measurement baseline for further
profiling. Raw logs remain local under `build-web-tests/native-msvc-build.log`
and `build-web-tests/native-dsp-msvc-final.log`.

The next DSP change caches a dedicated handler for moves from X memory into
X0, X1, Y0 or Y1 using post-increment and no parallel ALU operation. These
loads accounted for 15.5% and 7.2% of instructions in two captured GP
and EP frames, respectively. The handler uses the existing address update and
memory read, including modulo and bit-reversed addressing and mix-buffer aliases.
Full-state dispatch checks now cover all eight address registers and four
destinations across four address modifier settings and three memory ranges.

Two runs of seven paired rounds, each with 1,000 frames per round, measured
2.9–4.2% lower GP median execution time and 0.7–2.8% lower EP median execution
time in the Wasm replay. The replay checks complete DSP state and all DMA
transfers against the captures. The measurements cover those two frames.
A retirement shortcut produced gains below 1%, and a memory-range reorder
slowed GP while speeding up EP. Both candidates were dropped. The replay logs
are under `build-web-tests/retire-fast-check`.

Optimized MSVC also ran seven paired rounds of ten million instructions with
matching final register checksums. The targeted load loop dropped from 123.8
to 89.4 ms median. A mixed loop with three arithmetic instructions per load
dropped from 115.1 to 112.0 ms. These synthetic programs isolate dispatch cost.
The native APU build, native and Wasm DSP fixtures, optimized Web build and
headless launcher checks passed. Retail gameplay FPS and audio continuity
still need measurement on this build.

### Retail WebGPU check on `f5465c8`

The default 30 FPS cap and DSP path ran a CPU-controlled Raiders at 49ers
game in Chrome 157. Team selection, the stadium intro, the coin toss, kickoff
and two scrimmage plays completed. The final capture shows 3rd and 1, Q1
4:17, 0–0. Screenshots, audio snapshots, raw logs and all 17 verified build
hashes are under `build-web-tests/postinc-retail`.

The 21 complete renderer windows between the kickoff formation and the final
capture range from 6.7 to 17.7 FPS, with a 12.3 FPS median. All 755,686 3D
batches in those windows used the GPU. That count does not separate guest
command processing from GPU execution or establish the cause of the stalls.
The CPU-controlled sequence includes between-play cameras and replays.

The worklet missed 13,824 source frames during the same interval. From launch
through the final snapshot it missed 71,936 frames, with a longest gap of
1,664 frames (34.7 ms at 48 kHz). The audit failed on audio and presentation
rate. The test used one matchup, one browser and one local build, with no
matched run of the preceding runtime. It establishes a remaining failure
after the DSP change and leaves the size of any retail improvement unknown.

### Native Windows function ranges

Windows CMake generates the interpreter range table from the numbered C chunks
selected for compilation, including the register-local version used in optimized
builds. A clean build with generated C can proceed without a separate analysis
directory. The range generator rejects missing metadata, mismatched start
addresses and duplicate definitions. Windows CI exercises the checked-in chunks
and verifies that register localization preserves the first chunk's ranges.

The raw and register-local retail sources produce identical tables with 33,530
ranges. A fresh analysis of the local retail disc found 33,055 ranges, omitting
481 translated entries and giving different ends for 427 shared starts. Using
the compiled source keeps the interpreter table tied to the actual build even
when the available analysis came from a different conversion run.

### Linear render-target snapshots

The SDL GPU renderer previously generated every mip level whenever a draw
sampled a GPU-owned linear render target. Both formats accepted by that path
use level zero, even when the guest filter requests mipmapping. The snapshot
now allocates and copies one level. The surface is still copied before
sampling, including when the guest reads its current draw target.

All 16 measured Superdome drive windows recorded one GPU snapshot per frame.
The Vulkan fixture checks exact ARGB and XRGB pixels with stale guest RAM and
minification enabled. On the old renderer the pixels match and the fixture
fails on the two unused mip chains. The saved logs use the `linear-rtt` prefix.
The complete Vulkan and Chromium GPU suites pass with this change.

An isolated hardware WebGPU benchmark runs the two production snapshot
functions against a synthetic 720×480 source. It checks both base-level
pixels and measures seven alternating pairs of 64 copies, including a queue
fence at the end of each batch. Median time falls from 13.73 ms to 6.76 ms.
This isolates snapshot work from gameplay, texture uploads and draw batching.
The raw output is in `build-web-tests/linear-rtt-bench/run-final.log`.

### Windows executable link and vertex programs

The complete optimized MSVC link exposed two GCC intrinsics in the APU that
the earlier static library build could leave unresolved. The environment
cache now uses acquire/release publication with Windows SDK primitives on
Windows and C atomics elsewhere. The MMIO decoder computes low-byte parity
without a compiler intrinsic. A Windows CI executable links the real APU
objects and checks all 256 byte results through the decoder. The Linux MMIO
CPU differential fixture also passes.

The linked Windows game mounted the local retail disc, loaded through
Direct3D 11 and completed kickoff and scrimmage plays. During this initial
run, five raw vertex programs failed with an undeclared `vmax`. The raw
path copied HLSL helpers starting after the new comparison functions.
Both input layouts now include the complete shared helper block. The real
D3D compiler rejected MIN, MAX, SLT and SGE with raw inputs before the fix;
all four now compile with both raw and classic inputs. CI runs this check.

The rebuilt executable ran Jaguars at 49ers through kickoff and into the
first quarter at second and eight. The intro showed the Deon Grant graphic,
sideline staff and crowd. Five vertex programs compiled, including two that
failed in the first run. The retest logged no vertex-program compile failures.
After the stadium loaded, the one-second FPS samples printed every ten seconds
were 50–60, with a 20 FPS sample during a mode transition. The two runs used
different teams. Captures and logs are in `build-web-tests/native-retail-vp-fixed`.

### WebGPU vertex program constants

The WebGPU vertex translator now packs the constant registers actually read by
each program. Its triangle and line shaders share the layout stored with the
shader cache entry. A relative operand can use that layout while the address
register is known to be zero, before the first ARL takes effect.
Programs with a live relative operand after an ARL keep the full 192-register
bank. The Linux Vulkan shader continues to use the original bank layout.

The sparse-register fixture reduces the vertex uniform block from 3,136 to
112 bytes. Browser checks run 2,880 GPU vertex executions against the CPU
interpreter, including an out-of-range static index and relative reads before
and after an ARL. The position, coverage, D16/D24, GPU line and native Vulkan
fixtures pass. The packaged launcher smoke test also passes.

Set `RECOMP_WEBGPU_UNIFORM_PROFILE=1` to report the constant bytes eliminated
per five-second renderer window. The count covers queued draws before
deduplication and merging. `RECOMP_SDLGPU_FULL_VP_CONSTANTS=1` selects the
full-bank layout for comparison.

In Raiders at 49ers, the first conservative implementation saved 0.41%
of requested constant bytes across seven complete stadium intro windows.
The revised analysis saved 0.46% across six intro windows. Both menu runs
showed zero savings. These counters quantify the packed data before upload
caching. The two captures had different scene timing, and a separate host
compiler competed for CPU time during the revised run. Raw evidence is in
`build-web-tests/vp-constant-compact-retail` and
`build-web-tests/vp-constant-address-retail`.

The revised run reached second and inches at 4:44 in the first quarter.
Four complete opening-drive windows ranged from 21.3 to 28.8 FPS with a
26.8 FPS median and no software draws. Packing saved 4,617,600 of
813,594,624 requested constant bytes (0.57%). The worklet missed 27,264
source frames during the 26.4-second sample interval, with larger
starvation earlier in the session. The 30 FPS floor and continuous audio
remain unmet.

### NV2A completion mirrors and vblank acknowledgement

The poller now takes one shared completion lock when a mirror is registered.
It publishes the fence and frame counter from the same completed submission.
The executor publishes directly from the submission it just retired. Guest
device pointers are still followed on every poll, and a late poll cannot
replace a newer completion while the lock is held.

A Web idle-wait trial on the same binary spent 32.6 of the first 40.3 seconds
holding the guest lock in the timer/DPC thread. The zero-duration yield
control spent 1.2 of the first 40.4 seconds there. The timed trial took
longer to reach the title screen, and its later startup windows ranged from
1.5 to 2.6 FPS. The captures used Chrome 157 and the private retail disc.

Two generated handlers write PCRTC's vblank acknowledgement and then wait
for PMC's summary bit to clear. They now route the write to the NV2A handler,
which clears the selected PCRTC bit and the summary when no bits remain.
The generated fallback still handles other addresses or values through
the poller. Both hooks survive regeneration. Tests exercise pending and
completed snapshots, remapped fences, register acknowledgement, and
preservation of unrelated interrupt bits.

With both handlers in place, the timed trial recorded 155 ms of timer/DPC
lock holds in the first 40.4 seconds. It reached the first title-mode
transition 45.3 seconds after the guest entry, against 42.4 seconds in the
earlier yield control. These startup captures establish the change in lock
behavior. Their scene timing differed.

The timed trial with inline handlers reached the Bears at 49ers opening
drive. One presentation window averaged 2.4 FPS and the worklet's longest
gap was 49,920 frames. Timer/DPC lock holds stayed low during that stall.
The change retains the inline handlers and zero-duration poll yield.
Capture logs and CPU counters are under `build-web-tests/ack-idle-park`,
`build-web-tests/ack-idle-yield` and `build-web-tests/ack-idle-inline-park`.

The final build used the default launcher settings and reached the first
title-mode transition 42.8 seconds after guest entry. It loaded VIP1 from
the virtual hard disk. The timer/DPC thread held the guest lock for 155 ms
in the first 40.4 seconds, compared with 1,218 ms in the earlier yield
control. Six startup windows ranged from 29.4 to 30.1 FPS. The audit still
recorded audio underruns. It covered startup, with no live-drive FPS
measurement for this build. See `build-web-tests/ack-idle-inline-final`.
The rebuilt Windows executable passed retail-disc validation, and both
native and Wasm acknowledgement regressions passed.

## Historical measurements

The goal: gameplay at a locked 60 FPS (the original Xbox runs at 60), including at high
internal resolutions (the menu maximum stays at 9×, i.e. 6480×4320; no 16×). There is also a
frame-rate cap option (30/60/120/Unlimited).

Test machine: RTX 2060 SUPER (8 GB) under Windows 11.

## How the frame rate works (read this first)

- The game decides its own rate. If a frame is ready by the next 60 Hz vblank it shows it
  (60 FPS); otherwise it drops to its 30 FPS tier. The simulation is tied to the vblank, so
  **the game never makes more than 60 distinct frames a second**. Caps of 120 or Unlimited
  can only remove the host-side limit. Real 120 would need frame interpolation, which is not
  implemented.
- The pushbuffer (NV2A command stream) runs synchronously on the game thread inside
  `xbox_Nv2aKick` (`external/xboxrecomp/src/kernel/xbox_memory_layout.c`). Every millisecond
  of draw-path CPU time is game-thread time.
- The emulated vblank comes from the timer/DPC thread (`kernel_timer_thread` in
  `kernel_bridge.c`), which must take the global guest lock (GGL). That lock lets only one
  guest thread run at a time.

## Done this session (all measured)

| Change | Where | Effect |
|---|---|---|
| Raw vertex path (ByteAddressBuffer and per-draw attribute table, decoded on the GPU) | `nv2a_gpu_vp.inc.c`, `RECOMP_GPU_RAWVB` (default on) | Draw path 15.7 → 11.4 ms/frame |
| Env lookups cached; lighter texture change check | `nv2a_pb_exec.c`, `apu_env.h`, `nv2a_gpu_d3d11.inc.c` | → 9.9 ms |
| Guest packed SSE runs on host SSE | `recomp_types.h` (both copies) | → 9.0 ms; gameplay averages 38 FPS with stretches of 56–60 at 2× |
| Render target copied only when it changed | `nv2a_gpu_d3d11.inc.c` (`gen` / `copy_gen`) | Removes a ~90 MB copy per sampling draw at 8× |
| **Vblank on time** (high-resolution waitable timer at the deadline instead of a 10 ms poll) | `kernel_bridge.c` `kernel_timer_thread` | Vblanks used to land 10/20/10 ms apart, so every third frame had a 10 ms window and fell to the 30 tier |
| **Specialised pixel shaders** (the combiner and texture-stage state is compiled in; worker threads; disk cache `cache\ps`) | new `nv2a_gpu_ps.inc.c`, marker `//@PS_SPEC@` in `nv2a_gpu_d3d11.hlsl` | 8× menus 22 → 60 FPS. The generic shader indexed `R[16]` at run time (local memory) and writes SV_Depth (no early Z) |
| Frame-rate cap 30/60/120/Unlimited | `nv2a_gpu_present.inc.c` `pr_frame_limit`, F1 menu and in-game Video Settings, `fps_limit` in `nfl2k5_video.ini` | 0 = Unlimited (the default, same as before) |

Switches: `RECOMP_GPU_PS_SPEC=0` turns specialised shaders off (falls back to the generic
shader). `RECOMP_GPU_RAWVB=0` turns the old vertex path back on.

## Remaining bottlenecks, in order

1. **Game logic CPU time, about 11 ms/frame.** Profiles are flat across generated code. The
   generic overhead comes from:
   - guest registers kept as `__declspec(thread)` TLS globals (`g_eax` and the rest, via
     `#define eax g_eax` in `recomp_types.h` under `RECOMP_GENERATED_CODE`)
   - volatile `MEM32`
   - x87 stack emulation (`g_fp_stack` / `g_fp_top` in TLS)

   **Planned fix:** keep the registers in locals. Under a `RECOMP_REG_LOCALS` mode:
   1. Declare locals initialised from the globals at each `sub_` start.
   2. Write them back before each call or return, and reload them after each call.
   3. Rewrite `RECOMP_ICALL` / `RECOMP_ITAIL` / `RECOMP_ABI_CALL` to sync the same way.

   This is done by an idempotent post-processor at build time, after
   `tools/apply-gen-patches.py`. Facts that make it possible:
   - no setjmp/longjmp or __try in gen
   - no `return <value>`
   - 19,880 direct calls and 3,470 ICALL sites

   A full rebuild of the generated code takes about 8 minutes.
2. **GGL contention.** The DirectSound guest thread holds the lock about 9% of the time.
   The vblank ISR can only run when the game thread reaches a bridge point.
3. **Draw path, about 9 ms/frame at 2×.** Split: build ~16%, textures ~25%, upload+bind
   ~29%, state ~7%. Async render thread mode (`RECOMP_GPU_ASYNC`) exists but stalls with the
   raw vertex path. The game spins in BlockOnFence (`sub_004262F0`, `loc_00426427`), even
   with the 0x1D70 semaphore release wired to `xbox_Nv2aSemaphoreRelease`.
4. **GPU at very high scales:** depth is `D32_FLOAT_S8X24` (8 bytes/pixel), and the
   geometry shader runs on every draw.

## Measuring

Build:

```
tools\build.ps1 -Game
```

Benchmark: CPU vs CPU quick game, logs in `logs\<tag>.stderr.log`:

```
$env:RECOMP_GPU_PROFILE='1'; $env:NFL2K5_RENDER_SCALE='8'
tools\drive-quickgame.ps1 -Tag scale8 -PlaySeconds 150 -ShotEvery 50
```

What to read in the log:
- `[FPS]` every 10 s
- `[GPUPERF]` kickoff totals
- `[DRAWPERF]` stage split, target copies and new targets
- `[TEXUP]` uploads
- `[GPUPS]` shader variants

GPU load: `nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv -l 1`.

CPU profile: `tools/stackdump/sampleprof.exe`.

Visual check: `NFL2K5_PRESENT_SHOT=<prefix>` saves presented frames.

## Results log

(see the bottom of this file; it is updated as runs finish)

### 2026-10-03 overnight results

- **Measurement caveat:** HITMAN 3 was running alongside the whole time, using about 78% of
  the GPU's 3D engine and 4 GB of VRAM (Windows counter
  `\GPU Engine(*engtype_3D)\Utilization Percentage`). Every FPS number below competed with
  it. Re-measure with nothing else on the GPU.
- **8× (5760×3840) before** specialised shaders: menus 22 FPS, gameplay 3–22 FPS, GPU at
  100%.
- **8× after** specialised shaders: menus 60 FPS (with HITMAN still running). Gameplay was
  still GPU-bound under contention (kickoff mostly waiting on the GPU; Present calls of
  200+ ms).
- Specialised shaders were checked visually at 2× (coin toss, players, field, HUD): no
  differences seen.
- **Registers in locals:** `tools/gen-reg-locals.py` writes `build/gen-locals`, and CMake
  compiles it when `NFL2K5_REG_LOCALS=ON` (the default). Patch blocks are wrapped in
  `src/recomp_patch_begin.h` / `src/recomp_patch_end.h`. Turn it off with
  `-DNFL2K5_REG_LOCALS=OFF` (or delete `build/gen-locals`) to compare.

### 2026-10-03 later (HITMAN closed, clean GPU)

- **The 30 FPS segments were the game's own design.** `sub_0009F570` picks 1 or 2 vblanks
  per frame per camera mode (table at 0x9F5B4). The chain is `sub_00064B30` → setter
  `sub_00027880` → `0xA6A9AC`; `0xA6A9B0` is the vblank countdown polled with
  Sleep(1) in `sub_00028DE0`. With the original behaviour the port now holds exactly 60 or
  exactly 30, as the game asks.
- **New gen patch FRAME_INTERVAL** with `nfl2k5_frame_interval` in `src/main.c` applies the
  Frame Rate Cap setting:
  - 30 → 2 vblanks per frame
  - 60 / 120 / Unlimited → 1 (60 FPS in every camera)
  - Original → the game's choice

  Game speed was verified with `NFL2K5_CLOCK_LOG=1`: the play clock runs at 1.000
  game-seconds per wall second when forced to 60.
- **Bulk pushbuffer runs:** `nv2a_pb_exec_run` (`nv2a_pb_exec.c`), called from
  `nv2a_pb_scan`, handles transform constants, program words, INLINE_ARRAY and
  ARRAY_ELEMENT16 runs in one call.
- **Gameplay averages, 60 s windows with the default settings:**

  | Run | Scale | Avg FPS | 10 s windows |
  |---|---|---|---|
  | `locals2` (registers in locals, game's own 30/60) | 2× | 45.8 | |
  | `def4` (60 locked) | 4× | 53.5 | |
  | `def8` | 8× | 54.5 | |
  | `bulk1` (with bulk runs) | 2× | 58.5 | 60 60 53 60 60 58 |
  | `bulk8` | 8× | 55.5 | 60 60 51 52 59 51 |

  Before tonight: 2× averaged 38 and 8× ran at 3–22.
- **Remaining:** the heaviest wide stadium shots (crowd) run at 50–55 FPS at any
  resolution. They are game-thread CPU-bound: kickoff is ~57% of the busy time and the draw
  path ~21% of samples (`logs/prof60b.txt`).
- **Async render (`RECOMP_GPU_ASYNC=1`) is still broken.** The render thread reads garbage
  surface state (for example `software surface 83878000 19445x81349 bpp 0` and
  `09FF186A 10240x8192 pitch 26`), so draws fall back to the CPU rasteriser while the game
  thread spins in BlockOnFence (`sub_004262F0`). The pushbuffer is likely consumed after
  the game has reused it, or the coalesced PUT walk is wrong across ring wraps. Fixing this
  is the next big structural win: the kickoff would run in parallel with game logic.

### 2026-10-03: async render thread fixed and made the default (locked 60)

- **Root cause of the async garbage:** the render thread walked guest memory late. D3D
  patches the jump that ends a submitted chunk to point at its next chunk, and reuses ring
  and chunk memory, so a late walk followed patched jumps into chunks still being written.
- **Fix: capture at kick.** `nv2a_pb_capture` (`nv2a_pb_scan.c`) runs on the game thread
  inside `xbox_Nv2aKick`. It copies the submitted segment as headers + data, following
  jumps, calls and returns exactly as the synchronous walk reads them. GET is set to PUT
  at once, because the commands are already copied.
- The render thread (`pb_async_thread`, `xbox_memory_layout.c`) executes the copies
  (`nv2a_pb_exec_linear`) from a queue of up to 48. Fence and counter mirrors are
  published only after a copy has been executed, so D3D's resource waits stay honest.
- `RECOMP_GPU_ASYNC` now defaults to 1 (`src/main.c`); set `RECOMP_GPU_ASYNC=0` to go back.
- **Results:**

  | Run | Scale | Avg FPS | 10 s windows | Desyncs |
  |---|---|---|---|---|
  | `async7` | 2× | 59.2 | 60 60 60 60 55 60 | 0 |
  | `async8x` | 8× | 60.0 | 60 60 60 60 60 60 | — |

  The heavy wide stadium shots, which the game used to cap at 30, also hold 60. The only
  "lost stream" is one capture during D3D init (`03FCC000 → 010A0000`, 0 words), the
  same garbage walk sync mode also does there; it is harmless.
- **Files changed in `external/xboxrecomp`** (left uncommitted there by convention):
  - `src/kernel/nv2a_pb_scan.c` (bulk runs, live-PUT stop, capture, linear execution)
  - `src/kernel/nv2a_pb_exec.c` (`nv2a_pb_exec_run`)
  - `src/kernel/xbox_memory_layout.c` (async queue)
  - `src/kernel/kernel_bridge.c` (exact vblank timer)
  - `src/kernel/nv2a_gpu_d3d11.inc.c`, `nv2a_gpu_ps.inc.c` (new), `nv2a_gpu_d3d11.hlsl`,
    `nv2a_gpu_d3d11_hlsl.inc` (specialised pixel shaders, target-copy generation)
  - `src/kernel/nv2a_gpu_present.inc.c` (frame-rate cap)
  - `templates/runtime/recomp_types.h` (register-locals macros)

### Final checks (2026-10-03 morning)

- **9× (6480×4320), async:** 58.3 FPS average (60 59 60 60 51 60). The one dip is in the
  heaviest wide shot; at 28 Mpixels the RTX 2060 SUPER is near its limit.
- **12-minute run at 4× (`long4`), async default:** no crash and no desync, 60 FPS almost
  throughout, with occasional transition dips (43–51) into the second quarter.
- **Frame Rate Cap = 30:** locked 30 (`cap30`).
- **Frame Rate Cap = 120 / Unlimited:** the same as 60 in practice. The game simulates
  60 frames a second, so more distinct frames would need interpolation, which is not
  implemented.

### Next ideas, if more is wanted

- Draw path micro-work (texture hash, upload+bind) for headroom at 9× and on slower CPUs.
- Depth format `D32_FLOAT_S8X24` (8 B/px) → `D24S8` where integer depth suffices; would
  cut GPU bandwidth at 8–9×.
- x87 stack in TLS (`g_fp_stack` / `g_fp_top`): the same locals idea as the registers.
