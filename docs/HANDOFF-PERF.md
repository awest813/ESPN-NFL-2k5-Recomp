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
recorded audio underruns. See `build-web-tests/ack-idle-inline-final`. The
rebuilt Windows executable passed retail-disc validation, and both native
and Wasm acknowledgement regressions passed.

The same default retail WebGPU build (`6825d54`) completed a Rams–49ers
kickoff and the first scrimmage play, a one-yard loss by Kevan Barlow. The
final capture shows 2nd and 11 at the SF 19, Q1 4:44, 0–0. There were 18
complete presentation windows between the kick-return selection and that
capture, ranging from 10.2 to 29.6 FPS at a 20.6 FPS median. This interval
includes play selection and between-play cameras. No draw fell back to
software. The worklet missed 76,800 source frames in 95.2 seconds. The
timer/DPC thread held the guest lock for another 13–40 ms per statistics
interval across those samples. Neither the 30 FPS floor nor continuous
audio passed. The short initial harness title timeout recovered with a
60-second timeout. Logs, screenshots and the exact Wasm hash are under
`build-web-tests/ack-default-opening-drive`.

### WebGPU draw uniform buffer reuse

The WebGPU server reuses a draw uniform buffer and its vertex and fragment
bind groups. It allocates larger storage on demand and reuses one empty
bind group. Copy, blit and readback submissions skip draw uniform setup.
Queue ordering keeps earlier draws ahead of later writes. Shorter uploads
clear reachable stale bytes so shaders see the same zero-filled binding
tail as they would with a fresh buffer.

The hardware Chrome fixture checks six exact pixel values after queuing
all six draws before readback. It covers growth, shorter uploads, a draw
without uniforms, and a binding whose tail extends beyond a previous
clear. The full renderer pixel and presentation suite also passed.

Seven alternating pairs ran both versions of the production driver in
Chrome. Median CPU recording and submission time fell from 14.26 to
10.83 ms for 300 copies, from 17.32 to 14.52 ms for 300 four-draw passes,
and from 17.49 to 15.73 ms for 120 passes of 48 larger uploads. Median
time through the final queue fence also improved, with a slow outlier on
the reused version. These are isolated workloads. Sustained retail
gameplay FPS and uninterrupted audio remain open. Raw samples are in
`build-web-tests/uniform-buffer-replay/samples.json`.

### WebGPU texture and sampler binding changes

Each render pass tracks its current texture storage and sampler per slot.
The WebGPU recorder omits identical binds and retains only the resources
whose bindings changed. Earlier records keep their resources alive if a
texture cycles or its public handle is released. A new pass starts with
empty bindings.

The hardware renderer fixture checks six exact pixels across partial
updates, a sampler-only change, a slot reset, texture cycling and pass
boundaries. The full hardware renderer suite and native and Wasm uniform
recording checks passed.

Seven alternating pairs replayed 100 submissions of 200 draws on hardware
Chrome. Median recording and submission time changed from 10.64 to 7.51 ms
for identical binds, 9.56 to 7.93 ms when one texture changed, 9.74 to
8.45 ms for four changes, and 9.34 to 8.37 ms for eight changes. Replacing
all eight textures and all eight samplers together increased median time
from 9.19 to 10.49 ms. These synthetic workloads measure submission cost.
Raw samples are in `build-web-tests/sampler-delta-bench/samples.json`.

The retail sampler build reached the Chiefs–49ers kickoff and completed a
23-yard return to the SF 22 at 4:56 in the first quarter. It paused and resumed
at the first play call. The audit recorded audio underruns throughout the
session. It logged no browser exceptions or WebGPU validation errors.
A separate local link overlapped the capture, so the frame samples are
unsuitable for a performance comparison. See
`build-web-tests/retail-launch-stability`.

### DSP accumulator moves and retail audio starvation

A local Chrome 157 capture of the `5ae46f1` build used the default 30 FPS cap
and APU timing diagnostics with no compiler running. Several title-screen
windows processed roughly 950–1,230 of the 1,500 audio subframes required each
second. One 32.9 ms subframe spent almost its entire measured duration in the
DSP stage. That elapsed time includes any host scheduling delay. The worklet
logged 381,440 missing 48 kHz frames by the first title sample. Underruns
continued through the Baltimore–Washington attract game. The capture and
timing summary are under `build-web-tests/retail-stability-apu-profile`.

The dispatcher now caches dedicated handlers for X-memory loads into either
accumulator and for accumulator stores with post-increment. These two moves
accounted for 19.4% of the captured GP instructions and 7.2% of the EP
instructions. The handlers use the existing memory access and address update
rules, including accumulator saturation on stores and sign extension on loads.
The full-state fixture covers all eight address registers, both accumulators,
three X-memory ranges and four modifier settings, including bit-reversed and
modulo addressing.

In two optimized Wasm replay runs of seven alternating pairs with 1,000
frames per round, GP median execution time fell 5.2–13.1% and EP median time
fell 2.3–10.4%. Individual rounds varied. All runs matched the captured DSP
state and DMA events. The replay logs are under `build-web-tests/dsp-accu-moves`.

Optimized Windows and Linux DSP fixtures, Wasm UBSan dispatch and GP/EP MMIO,
the Windows retail executable validation, and the static-host launcher checks
passed. The new Chrome build reached Press START and the attract-mode stadium
intro. At the first title sample the worklet had missed 115,072 frames, down
from 381,440 in the preceding build's run. The browser reached the title about
eight seconds sooner, and each build was sampled once. The retail difference
cannot be attributed to the DSP change alone. The following 25 seconds missed
another 120,704 frames, with a longest contiguous gap of 3,200 frames (66.7 ms).
Renderer windows during the title-to-intro transition ranged from 2.7 to 29.8
FPS. Audio underruns were the only audit failures. The report and screenshots
are under `build-web-tests/dsp-accu-moves/retail`.

### Stadium intro submission stalls

The `4270757` Chrome capture hit 6.4 FPS entering attract mode. Draw submission
averaged 109.08 ms per frame in that window. Texture and vertex preparation
together averaged 5.16 ms. Later, a 13.4 FPS window spent 25.99 ms per frame in
texture preparation and requested 90.44 MiB of texture verification per frame.
That span counts all eligible bytes, including any skipped on early mismatch.
See `build-web-tests/retail-intro-gpu-profile`.

The draw queue now binds its shared index buffer once per pass and selects each
draw's range with the first index. Native Vulkan verifies all 76,800 pixels
across two indexed draws using different ranges, with an unindexed draw between
them. The WebGPU suite checks nonzero index offsets, indexed instances, upload
order, resource lifetime and pixels. With 100 submissions per round and nine
alternating pairs on hardware Chrome, median recording and submission took
5.640 to 3.635 ms at 80 indexed draws per pass, 8.145 to 4.705 ms at 240, and
15.345 to 6.375 ms at 600. The corresponding queue-fence medians also fell.
These draws isolate the binding change. See `build-web-tests/submit-profile/index-bench`.

`RECOMP_SDLGPU_PROFILE=1` now separates staging, recording and backend
submission. It also reports the time spent comparing texture bytes.
`RECOMP_WEBGPU_SUBMIT_PROFILE=1` samples submissions at or above 16 ms and
separates dispatch, replay, and return. Replay reports uniform preparation,
geometry uploads, texture uploads, encoder flushes before uploads, pass
encoding, and final submission. All submissions at or above 100 ms are
logged. These are elapsed times on the worker and can include browser or
OS scheduling delays.

On the instrumented build, one stadium-intro flush took 3,026.88 ms. The
backend logged 3,022.99 ms in uniform preparation and 0.25 ms in render pass
encoding. Another submit spent 313.38 ms in transfers, and a third spent
316.22 ms in uniform preparation. In a later 16.8 FPS window, byte verification
averaged 8.78 ms of the 16.96 ms of texture time per frame. The worklet also
reported underruns, with the longest gap logged before the 3-second submit.
The retail run reached the intro and logged no software draw fallback or
WebGPU validation errors. It did not meet 30 FPS or continuous audio. The
capture is under `build-web-tests/submit-profile/retail`.

### Presentation upload recovery and uniform writes

The presenting thread keeps the previous snapshot until a replacement copy
has been submitted successfully. If an upload from guest memory is rejected,
the guest copy stays authoritative and the next flip uploads it again. The
native Vulkan fixture injects failures during both a same-size update and a
resize, then reads the complete snapshots before and after retry. It reproduces
stale or incorrect pixels on `7c36fff` and passes with the recovery fix. The
Linux protected-memory staging fixture also passes.

An isolated hardware Chrome transfer benchmark copied from shared Wasm memory
and drew after each of 140 writes. With 384 KiB per submission, median CPU
submission was 17.88 ms for one queue write and 10.29 ms for mapped staging.
Waiting through the final queue fence took 20.94 ms and 33.47 ms, respectively.
At 5 MiB per submission, the single write had the shortest median submission
and fence times among the tested methods. Splitting into 128, 256 or 512 KiB
writes gave mixed results across sizes. The game keeps its existing upload
method. Raw samples are under `build-web-tests/upload-stall/upload-methods.json`.

The opt-in WebGPU submit trace now separates uniform setup from the queue write
and reports the written bytes and backing buffer capacity.

The first retail capture with these timings logged a 1,968.66 ms submission
entering the stadium. It wrote 867,840 uniform bytes in 0.44 ms. Chrome's trace
shows 1,964.77 ms in `CommandBufferProxyImpl::WaitForToken` on the WebGPU worker,
overlapping a 1,831.51 ms WebGPU request on the GPU process. Two later transfers
of about 230 ms also line up with a command-buffer wait. The transfer call can
therefore be where the renderer waits for earlier GPU work. The timings do not
isolate the operation inside the GPU process. The capture is under
`build-web-tests/upload-stall/retail-chrome-trace`.

A follow-up with Dawn tracing reproduced a 1.99-second submit. Dawn's client
spent 1.986 seconds obtaining space for a 2,123,872-byte command, including
1.982 seconds waiting for a token while the GPU process handled earlier Dawn
commands. In the same run, a 301.02 ms uniform write spent 298.55 ms obtaining
command space, including 298.41 ms in the token wait. These two examples put
both stalls at the browser's command buffer. The work inside the preceding
GPU-process commands still needs attribution. Stadium-intro windows ranged
from 14.3 to 29.6 FPS, and audio underruns remained. The follow-up capture is
under `build-web-tests/upload-stall/retail-dawn-trace`. The WebGPU pixel and
presentation suite passed on this build.

### Stadium draw uniforms and GPU-process CPU time

An experimental SDL GPU draw queue reused adjacent fragment constants and
skipped pushes when the last visible draw already used the same immutable
uniform block. The native Vulkan pixel fixture and the WebAssembly queue and
merge tests passed, including a one-byte change to a 3,600-byte block.

Three sequential hardware Chrome captures ran the same title and attract-mode
script on the same profile with renderer timing enabled. The reference was
the retained `56bb7305` release. The candidate included the subsequent
offscreen clipping fix. Samples below start with the first renderer report
after the stadium mode push. Each FPS sample covers roughly five seconds.
Audio frames lost are the increase between the title and final audio samples.

| Run order | Adjacent uniform hits in WebGPU recorder | Lowest sampled FPS | Longest flush | Audio frames lost |
| --- | ---: | ---: | ---: | ---: |
| Candidate | 0 | 15.4 | 1,857 ms | 52,224 |
| Reference | 242,161 | 16.7 | 2,760 ms | 7,040 |
| Candidate repeat | 0 | 11.2 | 2,945 ms | 112,768 |

The candidate removed repeated updates. The captures covered different draw
counts and showed no repeatable frame-time gain. Both candidate runs lost
more audio. The production queue still uses the reference uniform behavior.
Private captures are under `build-web-tests/upload-stall/retail-uniform-*`.

In the earlier Dawn trace, the GPU-process thread consumed **1,760.4 ms of
CPU time during the 1,768.2 ms** it spent handling the 64,192-byte command
batch. The next two longest batches used 509.4 of 511.4 ms and 440.4 of
442.4 ms on that thread. This narrows the remaining investigation to CPU
work inside the GPU process while the WebGPU worker waits for command space.
A CPU stack sample from that process during stadium entry would distinguish
the decoder, graphics driver and pipeline creation paths.

### DirectX shader compilation at stadium entry

On Intel Gen-12HP with hardware Chrome, the first stadium line pipeline is
responsible for most of the previously observed two-second stall. A local
sampler followed the audit browser's GPU process and sampled its
`CrGpuMain` instruction pointer. The 64,192-byte Dawn command batch took
2,198.6 ms elapsed and 2,170.7 ms of thread CPU. Of 139 samples in that
interval, 118 landed in `dxcompiler.dll`. The next three longest batches
also spent most of their samples in that module.

An independent capture recorded the descriptors on the game's WebGPU device.
Replaying them in order with `createRenderPipelineAsync` in two fresh browser
processes took 1,797 and 1,604 ms for the first instanced vertex-program line
pipeline. It pairs the translated endpoint vertex program with
`k_sg_xf_linevp_frag_wgsl`. The first ordinary 3D pipeline took 1,163 and
1,048 ms earlier in the sequence. Both replays completed without validation
errors. Warming the line fragment shader with a substitute vertex program
still left over 2,200 ms of compilation for the real pipeline in both trials.

The private retail experiment compiled the exact line descriptor asynchronously
before stadium entry and retained the resulting pipeline on the same device.
It checked shader source, layout identity and pipeline state before returning
the compiled object. The captured shader sources and altered browser bundle
stay local. The reference renderer created this pipeline on first use.

| Intel hardware Chrome capture | Longest Dawn command batch | First stadium FPS window | Lowest stadium FPS window | Audio frames lost at final sample |
| --- | ---: | ---: | ---: | ---: |
| Production, CPU sampling | 2,199 ms | 14.1 | 14.1 | 15,104 |
| Production, descriptor capture | 2,028 ms | 14.4 | 14.4 | 128 |
| Exact pipeline prepared early | 417 ms | 26.7 | 26.7 | 0 |
| Exact pipeline prepared early, repeat | 854 ms | 24.3 | 22.3 | 0 |

Each row is a fresh launch through the title and 45 seconds of attract mode.
The two private test runs both logged a matching pipeline at first use and
passed the audio checks. The remaining long batches and sub-30 FPS windows
still need work. Captures and isolated timings
are in `build-web-tests/upload-stall/retail-{gpu-cpu-samples,pipeline-descriptors,warm-exact-line*}`.

### First-launch stadium line preparation

The title loads the vertex program used later for stadium lines. On the first
transformed triangle draw, the WebGPU renderer translates the live program's
line variant and requests asynchronous compilation with the stadium's blend and
depth state. The first matching draw claims the result only if compilation
has completed. Other states and an unfinished or failed preparation use the
ordinary pipeline creation path. No captured shader or disc data is bundled.

The browser pixel suite exercised both early release and rendering after
asynchronous compilation and shader release. The native Vulkan suite also
passed. The first retail capture matched the prepared pipeline at stadium
entry, averaged 26.6 FPS in the opening window, and had zero audio underruns.
Its longest traced Dawn command batch took 418 ms. A second capture on the
final release build matched at first use and opened at 26.8 FPS. Its six
stadium windows ranged from 26.6 to 30.0 FPS. The longest Dawn batch was
415 ms and both audio samples reported zero frames lost. The private captures
are under `build-web-tests/upload-stall/retail-live-line-{first,final}`.

### Vertex buffer binding during field draws

The SDL GPU queue now keeps the vertex buffer bound while successive draws
can address their packed vertex data using an integral vertex offset. Indexed
draws use base vertex and unindexed draws use first vertex. An incompatible
stride starts a new binding. Instanced line draws still bind their endpoint
data at its exact byte offset and start vertex numbering at zero. A native
Vulkan regression checks all 76,800 pixels after alternating these cases.

An Intel Gen-12HP hardware Chrome benchmark alternated both binding patterns
for nine rounds. Each sample issued 100 submissions with one indexed pass
per submission. These are median milliseconds for the entire sample.

| Draws per pass | Previous submit | Shared binding submit | Previous through GPU fence | Shared binding through GPU fence |
| ---: | ---: | ---: | ---: | ---: |
| 80 | 5.50 | 4.19 | 13.85 | 11.53 |
| 240 | 8.09 | 4.79 | 14.75 | 13.50 |
| 600 | 14.79 | 6.58 | 21.36 | 16.31 |

The retail Quick Game script reached opening possession in both builds. The
six complete five-second windows after the first play-selection transition
ranged from 27.8 to 30.1 FPS on the candidate and 28.8 to 30.0 on the
reference. The game selected different visiting teams and the windows
contained 585,000 and 744,000 guest draws respectively. This comparison
cannot establish a retail FPS gain. The candidate finished the kickoff
return at SF 24 with 4:56 in the first quarter and zero audio frames lost.
The reference recorded 4,096 frames lost before its first audio sample.
Private captures are under `build-web-tests/upload-stall/quick-game-vertex-*`
and benchmark samples under `build-web-tests/submit-profile/vertex-bench`.

Three subsequent attract-mode runs all had audio underruns. The slowest
stadium windows were 2.6 FPS on the candidate, 7.9 on the reference, and
18.4 on the candidate repeat. The candidate's first slow run also spent
17.5 ms per frame processing vertices and 65.3 ms processing textures in
its 2.6 FPS window. A host sample during the comparison found other emulation
processes using about five CPU cores. Their contribution to the individual
stalls is unresolved. Captures are under
`build-web-tests/upload-stall/{retail-shared-vertex,retail-vertex-countercheck,retail-vertex-repeat}`.

## Packers at 49ers browser benchmark (2026-11-23)

The [Quick Game fixture](WEB-GAME-MODES.md#repeatable-retail-quick-game-benchmark)
reached kickoff and opening possession on the Intel Gen-12HP Chrome adapter.
The repeat began with visiting club code 14 and used controller inputs to reach
Green Bay (10) at San Francisco (25). Both clubs reported roster category zero.
The table includes only complete reporting windows after the first kickoff
play-selection transition (0050FF70), excluding the window containing it.
Audio losses are cumulative at the end of each run.

| Timing enabled | Windows | Five-second averages (FPS) | Worst flip | Missing audio frames |
| --- | ---: | ---: | ---: | ---: |
| Flip intervals | 7 | 19.9–30.0 | 212.92 ms | 283,904 |
| Flip intervals, repeat | 6 | 18.3–30.0 | 125.30 ms | 215,936 |
| Detailed draw and WebGPU submission | 7 | 6.0–27.2 | 681.68 ms | 286,336 |

In the 6.0 FPS window, texture verification averaged 77.28 ms and 117.65 MiB
per frame. Texture decoding averaged 1.37 ms. The longest flip spent 409.48 ms
in texture processing, 126.23 ms in vertex processing and 85.92 ms in submission.
Texture verification warrants a controlled comparison using the same scene and
retail pixels. Detailed timers add overhead, and the timing-only runs do not
attribute individual stalls to a renderer phase. The private captures are under
`build-web-tests/upload-stall/{fixed-matchup-1,fixed-matchup-2,fixed-matchup-phases-confirm}`.

## Measuring individual stadium stalls

Open the launcher with `?env=RECOMP_SDLGPU_FRAME_PROFILE=1`, enter the stadium,
and inspect the `[SDLGPU] 5s` lines in the runtime log. Each line reports the
number of intervals between guest GPU flips, how many exceeded 33⅓, 50, and
100 ms, and the duration of the longest interval. The counts overlap. An
interval crossing a reporting boundary belongs to the window in which it ends.
Browser presentation can introduce additional delays after a guest flip.

For a second pass, use `?env=RECOMP_SDLGPU_PROFILE=1`. This also records the
texture, vertex, and submission time for the longest interval in each window.
Detailed timers run on the draw path and can affect the result. Both profiling
modes are opt-in.

The detailed texture report labels successful byte-for-byte checks as
`texture match`, with time per frame and MiB per frame by hexadecimal NV2A
texture format. The existing `verify` byte total counts the requested span
of every comparison, including mismatches that may exit early. The matched
bytes are the portion known to have required a complete comparison.

The first local profiling package replaced its runtime files while retaining
the reference launcher's build URL. Both packages therefore shared cache keys,
and the subsequent reference run reported an Emscripten `ASM_CONSTS` error.
Those runs are excluded. The deployment packager now supports separate output
directories for A/B tests, and each package uses a digest of its JS/Wasm pair.

With the corrected package, the instrumented Packers at 49ers run reached the
kickoff return. The screenshot confirmed gameplay even though the script timed
out waiting for the kickoff play-selection descriptor. Across 16 complete
stadium windows, five-second averages ranged from 4.0 to 10.3 FPS and the
longest flip was 855.03 ms. Successful comparisons took 5.71 to 88.97 ms
per frame. Swizzled `A8R8G8B8` (`06`) accounted for 70.2% of the verified
bytes, with paletted `0B` accounting for 23.2%. The run also reported audio
underruns. The capture is under
`build-web-tests/upload-stall/fixed-matchup-texture-formats-probe`.

A repeat with flip timing only completed the script and captured a kickoff
return. Seven complete windows after the kickoff play-selection transition
averaged 7.3 to 25.0 FPS, with a longest flip of 395.39 ms. The final audio
sample counted 1,750,912 missing frames since launch. The capture is under
`build-web-tests/upload-stall/fixed-matchup-stadium-entry-branches`.

### SIMD decode for swizzled 32-bit textures

The Wasm upload decoder uses two 16-byte loads per 4×2 Morton tile. Two SIMD
shuffles assemble the output rows and rearrange the color channels. The
X8 format still forces opaque alpha. Narrow textures use the scalar decoder.

Both implementations produced identical bytes in a paired Wasm benchmark with
unaligned, randomized images. At 512×512, the median time for 96 decodes went
from 27.23 to 6.32 ms for format `06` and from 27.28 to 6.27 ms for `07`.
The sampler regression fixture also passed all 635 cases. These measurements
cover texture decoding after a cache miss. Full-texture comparison work on a
cache hit remains a separate cost.

The full optimized build linked and ran in Chrome. Packers at 49ers took the
alternate kickoff transition and the final capture showed the kick meter at
5:00. Seven complete windows after the transition averaged 6.5 to 8.5 FPS,
with a longest flip of 525.14 ms. The audit failed on audio underruns and
counted 3,002,880 missing frames since launch. This scene differs from the
reference kickoff return, so the isolated decode benchmark is the measured
speedup. The capture is under
`build-web-tests/upload-stall/fixed-matchup-morton-simd`.

### Palette verification on image cache hits

The P8 texture path can reuse a stage's last seeded palette hash after matching
all 256 palette entries and the image hash. Changed and uncached images still
hash their palettes directly. Palette changes within a draw sequence continue
to produce the same keys as the previous implementation.

In a paired Wasm benchmark of 250,000 lookups, a stable palette and image hash
took a median of 8.33 ms with the memo, down from 49.64 ms. When a palette
entry changed every 64 inputs across four stages, the medians were 11.21 and
46.46 ms. Changing the palette on every stage lookup made the memo slower
in the synthetic test. The timing excludes image verification and rendering.

The full palette build reached the kickoff play-selection screen in a
Packers at 49ers Chrome run. The six complete windows after the kickoff
transition averaged 2.3 to 7.0 FPS, with a longest flip of 658.83 ms. The
audit failed on audio underruns and counted 3,146,496 missing frames since
launch. The capture ended in a different lighting and camera configuration
from the previous kickoff-meter run, so this timing does not isolate the
memo's effect on gameplay. The capture is under
`build-web-tests/upload-stall/fixed-matchup-palette-memo-repeat`.

In two retail Chrome attract-mode runs on November 23, the window containing
stadium entry and the next four windows showed the following results.

| Capture | Window averages (FPS) | Longest guest flip interval | Audio audit |
| --- | --- | --- | --- |
| Flip timing only | 25.7, 22.3, 27.7, 30.0, 29.3 | 967.48 ms | 1,408 missing audio frames |
| Detailed draw timing | 26.3, 28.0, 23.7, 26.6, 30.0 | 398.41 ms | No underrun reported |

In the detailed run, submission accounted for 359, 325, and 338 ms of the
longest intervals in the first three windows (398, 347, and 369 ms).
Submission is the next place to investigate. The 967 ms interval occurred
in the timing-only run, so its cause is unknown. These two runs establish
neither the production FPS floor nor the overhead of detailed profiling.

### Stadium buffer-write comparison

Three sequential runs on the same Intel Gen-12HP Chrome profile used the same
attract-mode script and enabled the renderer, WebGPU submission, and APU lock
timers. The private experiment split buffer writes larger than 256 KiB into
ordered chunks. The reference used the released backend. The table includes
the reporting window containing stadium entry and all subsequent complete
reports before the script ended. Audio counters are cumulative at each sample.

| Run order | Windows | Lowest window FPS | Longest flip (ms) | Flips over 100 ms | Missing audio frames at title / end |
| --- | ---: | ---: | ---: | ---: | ---: |
| Reference | 5 | 19.6 | 626.79 | 14 | 3,712 / 3,712 |
| 256 KiB writes | 4 | 8.0 | 1,050.56 | 39 | 0 / 0 |
| Reference repeat | 6 | 14.3 | 474.72 | 9 | 11,392 / 14,464 |

In the first reference run, a 536.49 ms submission spent 535.17 ms in
transfers. A separate 159.59 ms submission spent 157.96 ms writing uniforms.
These are CPU-side waits observed at the API call. Splitting the buffer writes
failed to improve stadium frame times in this comparison. The release retains
the original writes.

A fourth run timed individual browser queue calls with the original write
sizes. After the stadium marker, 48 buffer writes and two texture writes took
at least 50 ms. No queue submit call crossed that threshold. The 26 vertex
buffer waits peaked at 582.59 ms for 2,544,544 bytes. The ten index buffer
waits peaked at 370.22 ms for 73,584 bytes, and the twelve uniform buffer
waits peaked at 400.81 ms for 1,472,768 bytes. Texture writes peaked at
70.74 ms. The audit reported 4,224 missing audio frames. These durations
include time waiting for the browser to accept earlier queued work. The cause
of that backpressure still needs verification.

When flip timing is enabled, the mode audit saves `frameWindows` in each
completed case in `report.json`. Each entry contains the average FPS, interval
counts, longest flip, and mode transitions observed since the previous report
within that case. Detailed profiling also records phase times for that flip.
The phase timers can overlap.

### Reusing unchanged geometry in WebGPU

Successive stadium frames often write identical vertex and index data to the
same addresses. In three complete five-second stadium windows, 43–50% of the
vertex bytes matched the previous contents in 4 KiB blocks. A private browser
prototype reduced geometry traffic from 2,144,377,220 to 1,009,867,388 bytes
over five windows including entry. Queue calls rose from 2,562 to 2,880.

The WebGPU backend compares aligned uploads at offset zero against an exact
copy owned by the destination buffer backing. It uploads changed 4 KiB
regions, joining them across unchanged gaps smaller than 32 KiB. Growing
the recorded range initially sent the full payload. Offset writes and uploads larger
than 16 MiB discard the copy. Cycling starts with a fresh backing, and an
allocation failure falls back to a full write. The hardware Chrome pixel
suite checks two separated changes and verifies that an earlier draw can
still use the old index backing after a later draw uses the new one.

Two reference/candidate pairs used the same retail Chrome attract sequence.
Each row covers the window containing stadium entry and four subsequent
windows. The detailed pair used renderer, submission, and APU lock timing.
The lighter pair used only guest flip timing.

| Timing | Renderer | Lowest window FPS | Longest flip (ms) | Flips over 100 ms | Missing audio frames at title / end |
| --- | --- | ---: | ---: | ---: | ---: |
| Detailed | Reference | 20.6 | 1,159.24 | 2 | 2,304 / 2,432 |
| Detailed | Changed-region uploads | 26.3 | 461.82 | 3 | 0 / 0 |
| Flip only | Reference | 21.7 | 938.21 | 3 | 0 / 0 |
| Flip only | Changed-region uploads | 22.9 | 1,141.71 | 3 | 0 / 0 |

The lowest five-second average improved in both pairs. The longest individual
stall moved in opposite directions. Stadium entry still misses the 30 FPS
target under both timing configurations.

A separate St. Louis at San Francisco Quick Game reached second-and-ten at
the STL 20 with 4:55 left in the first quarter. From the window containing
kickoff onward, eight windows averaged 24.8–30.1 FPS, with a longest flip
of 239.94 ms and zero missing audio frames. The capture and opening-drive
image are under `build-web-tests/upload-stall/quick-game-geometry-candidate`.

### SIMD verification of geometry upload blocks

WebGPU's geometry upload cache now uses the renderer's exact SIMD byte
comparison for each 4 KiB block. The scalar fallback retains `memcmp`.
Replay kept identical destination bytes and write counts, including short
and offset writes, separated changes, and allocation failure.

In an alternating Wasm replay of 120 submissions with 2,544,544-byte
buffers, unchanged uploads took a median 10.38 ms with SIMD, down from
25.70 ms. When half of the blocks changed per submission, the median went
from 88.58 to 78.59 ms. With one in sixteen blocks changed, it went from
27.03 to 12.84 ms. This replay measures CPU comparison and copying with a
memory-backed queue write. It does not time browser submission or gameplay.

The SIMD-enabled hardware Chrome pixel suite passed, including separated
geometry changes and cycled index backing. The forced SwiftShader attempt
crashed at browser startup on this Windows host.

Both retail captures verified Packers at 49ers and ended at the kickoff
meter at 5:00. The preceding build timed out on its first attempt and
reached kickoff after an extra 35-second startup wait. Seven full windows
after kickoff entry measured the following.

| Build | Five-second FPS averages | Worst flip | Missing audio frames after kickoff |
| --- | ---: | ---: | ---: |
| SIMD comparison | 7.8–10.0 | 187.77 ms | 1,048,832 |
| Preceding build | 6.3–12.1 | 230.36 ms | 1,038,080 |

The minimum window average was higher with SIMD, while the highest was
lower. Audio underruns failed both audits. This pair provides no consistent
gameplay speedup. Captures are under
`build-web-tests/upload-stall/{fixed-matchup-geometry-simd,fixed-matchup-geometry-simd-reference-retry}`.

### Controller polling during gameplay

The port discovery call now updates SDL once and checks which slots are
connected. A Windows SDL run compared 1,000 calls per round, reversing the
order for a second round. With four virtual controllers the mean fell from
8.95 to 0.50 µs per query. With two it fell from 3.65 to 0.30 µs. Both paths
returned identical masks with zero through four controllers. Input state
queries still sample buttons, triggers and sticks.

The binding menu starts its capture thread on the first remapping request.
After a capture it waits on a semaphore until another request arrives. A
native SDL test exercised controller capture, keyboard capture, cancellation,
and the six-second timeout. It observed zero polls during a 160 ms idle check.
The browser SDL renderer has no binding-menu callbacks, so it no longer starts
this worker. Game-thread lock statistics now use the runtime thread ID from
the input poll, matching the ID used when the guest lock records wait time.

Three sequential retail Chrome Quick Games used the same script. Each row
includes the window containing kickoff and the next seven reports.

| Run | Window FPS range | Longest flip (ms) | Missing audio frames at title / end |
| --- | ---: | ---: | ---: |
| Local candidate | 13.3–28.2 | 215.58 | 0 / 6,400 |
| Published release `3a57761` | 22.2–29.3 | 257.82 | 640 / 640 |
| Local candidate repeat | 23.4–29.4 | 216.12 | 0 / 0 |

The runs cover different matchups and the reference came from the Pages
build. They establish no consistent gameplay FPS gain from the input change.
In the first candidate's 13.3 FPS window, texture verification compared
148.19 MiB per frame and averaged 24.58 ms per frame. The maximum queue flush
in that window was 24.08 ms. The hardware Chrome controller and A/V suite
passed connection, disconnection, reconnection, and presenter checks. The
forced SwiftShader configuration on the same Windows installation failed
to claim the presenter.

### Which texture bytes Quick Game verifies

A private Wasm probe counted the bytes compared against retained texture
copies. Across seven complete five-second windows after the kickoff transition,
the four texture stages accounted for 27.28%, 47.91%, 23.47%, and 1.34% of
94.58 billion compared bytes. The probe found zero bytes from secondary
stages that its conservative combiner analysis could prove unused. It also
found zero bytes from lower 2D mip levels behind a sampler clamped to level
zero. These observations apply to the sampled draws.

Of those bytes, 20.51% belonged to 1 KiB blocks containing a repeating
16-byte value. A second Quick Game measured one long contiguous span per
retained image. Spans of at least 4 KiB covered 8.96% of verified bytes
across seven complete kickoff windows. This measures the portion for which
a comparator can reuse an expected vector. The guest side still requires a
full read to detect writes anywhere in the texture.

A private paired probe ran both comparators on the same texture bytes for
one in sixteen eligible calls, alternating which ran first. They agreed on
all 19,812 sampled calls. In the seven complete kickoff windows, the old
comparator took 347.942 ms over 8,215 calls and the new one took 300.403 ms
(13.7% less time). The new routine was faster in five windows. This measures
eligible comparisons only and excludes the cost of finding a pattern when
the retained copy changes.

The release build with frame timing enabled reached second and ten in a
Chargers–49ers Quick Game. Eight five-second windows from kickoff through
the opening drive measured 28.8–30.1 FPS, with a worst frame of 251.53 ms.
Both audio samples reported zero underrun frames. The detailed paired probe
did encounter audio underruns. The release capture still falls below the
30 FPS target, and this single matchup does not establish a change in
end-to-end frame rate.

### Kickoff timing without browser screenshots

Use `--skip-screenshots` with `tools/audit-web-modes.cjs` to run the same
script without capturing the browser surface. The report records
`screenshotsDisabled: true`. Keep the usual screenshot run for visual checks.

In six of eight prior Quick Game captures, the scrimmage PNG's write time
fell inside the five-second window containing the longest kickoff or opening
drive frame. In the 251.53 ms case, that window also contained a 256 ms
guest-lock wait. Neither timestamp identifies what caused that frame.
Two further Chrome runs on the same release removed every screenshot.
Each had eight windows from kickoff through the opening possession.

| Timing | Lowest window FPS | Longest flip | Missing audio frames at kickoff / end |
| --- | ---: | ---: | ---: |
| Flip timing only | 22.3 | 130.30 ms | 6,144 / 13,824 |
| Detailed draw timing | 19.9 | 180.85 ms | 3,456 / 17,280 |

Both audits failed on audio underruns. During the 180.85 ms flip, texture
handling took 94.10 ms, vertex processing 27.25 ms and submission 48.42 ms.
These timers can overlap. This identifies texture handling as a substantial
cost in a long frame during play with screenshot capture disabled. The
timing-only run did not collect the phase data needed to attribute its stall.

### Texture snapshot layout cost

The renderer calculates how many guest bytes each texture snapshot spans
before it checks those bytes. A two-dimensional power-of-two swizzled
rectangle contains exactly width × height texels. Using that count avoids
rebuilding Morton masks for its last texel at each mip level. Irregular
dimensions retain the last-texel calculation. Cube snapshots now calculate
the aligned face chain once, and an authored mip count that fits the
dimensions can be accepted without walking the chain to find the maximum.

A private Wasm harness compared snapshot sizes and acceptance against
the previous release for 509,600 inputs. It covered power-of-two and
irregular dimensions, pitched images, mip counts, cubes, unsupported
formats and guest address limits. All results matched. Over twelve timed
pairs with alternating order, the medians for 500,000 synthetic snapshots
were 37.36 ms before and 10.23 ms after. The benchmark isolates layout
calculation with direct guest memory and excludes texture verification,
uploads and drawing.

With the optimized layout, a screenshot-free retail Quick Game produced
eight kickoff/opening-drive windows at 28.8–30.1 FPS. The longest flip was
98.27 ms. The audio counter rose from 22,400 missing frames at kickoff to
22,912 at the end, failing the audit. The preceding release's timing-only
run bottomed out at 22.3 FPS with a 130.30 ms flip. The two games did not
replay identical draws, so the isolated benchmark is the evidence for the
layout speedup. The 30 FPS floor remains open.

### Native-rate browser audio output

An experimental AudioWorklet copied published 48 kHz stereo samples directly when the
AudioContext also ran at 48 kHz. When a render block ran short, it still
checked for newly published frames before reporting an underrun. Other output
rates used the existing interpolation and phase rules.

In a Node benchmark of the production processor, 80,000 fully supplied
128-frame stereo blocks took a median of 78.92 ms before and 36.22 ms
after, over nine alternating measured pairs. This isolates consumer work
with source frames already present. It does not measure APU production time.
In Chrome's OfflineAudioContext, rendering 262,144 frames took median
times of 12.65 and 9.93 ms over seven alternating pairs. Every sample in
both output channels matched the signed 16-bit source divided by 32,768,
and both processors consumed the exact published frame count.

A separate Quick Game capture with the previous worklet enabled APU
scheduling diagnostics. Between kickoff and the final sample, the worklet
missed 80,000 frames. The producer rebased its clock 25 times and was up
to 81.88 ms behind. The longest measured DSP stage was 27.18 ms, and the
longest gap between producer frames was 30.67 ms. These wall-clock
intervals include host scheduling delays and tracing overhead.

In a screenshot-free retail comparison using the same Wasm, menu script and
Chrome profile, the candidate missed 61,952 additional frames from kickoff
through the opening drive, against 128 for the released worklet. The lowest
five-second averages were 14.0 and 23.7 FPS respectively. Draw workloads
differed, peaking at 1,457 and 848 GPU draws per frame averaged over a
window. Two other candidate attempts timed out before team selection.
These runs do not isolate a worklet regression or establish a gameplay
benefit. The release keeps its current processor. A regression test covers
stereo PCM and signal diagnostics across ring wrap and partial starvation.

### Effects-processor parallel Y-memory loads

In the captured Xbox effects-processor (EP) frame, 1,536 of 7,119
instructions loaded a data register from Y memory while incrementing an
address register. This family did not occur in the captured global-processor
(GP) frame. The cached instruction handler reads the source, runs the parallel
ALU operation on the original register values, then commits the destination.
It uses the existing DSP address-update and memory-access routines.

Two optimized Wasm comparisons alternated old and new implementations for
seven pairs of 1,000 captured frames each. Median EP execution fell from
96.82 to 87.77 ms and from 101.79 to 95.84 ms. GP medians moved in opposite
directions. Each iteration reproduced the captured register and memory state,
DMA metadata and transfers. The comparison covers these two captured frames.

In sequential hardware Chrome Quick Games, the local candidate missed
109,312 additional audio frames between kickoff and the final sample. Its
lowest five-second average was 14.9 FPS and its longest flip was 142.28 ms.
The published build from `38a912f`, verified against its Pages manifest,
missed 500,352 additional audio frames, bottomed out at 4.2 FPS and had a
459.06 ms flip. Both failed the audio audit. The games exercised different
draw workloads and the two builds came from different build environments.
Only the paired DSP replay isolates the handler's performance.

### Parallel X/Y loads in the effects processor

The DSP dispatcher now caches a specialized handler for the parallel
`X:(Rn)+Nn` and `Y:(Rm)+` loads into data registers. Both address updates and
memory reads precede the ALU operation. Both destinations are written after
it, preserving ALU reads of their old values. The general memory accessors
still handle the X mix-buffer aliases and peripheral addresses.

The paired captured firmware replay reproduced the original state and DMA
transfers. Over seven alternating pairs of 1,000 frames, the EP median went
from 74.02 to 69.68 ms. The GP median was 73.56 and 74.13 ms. The dispatch
fixture passed 149,024 cold and warm comparisons in Wasm and native Windows,
and the GP/EP fixture passed its PCM, timing and reset checks.

The retail reference with APU tracing measured 6.5 to 16.7 FPS across
seven complete windows after kickoff entry. It missed 623,232 audio frames
between kickoff and the final sample. Post-kickoff trace reports reached
123 ms between producer frames, 66 ms of wake lateness, and 34 ms waiting
for a register-access handoff. DSP stage durations reached 121 ms and
include time when the worker was descheduled. The reference trace is in the
local temporary archive `nfl2k5-captures-20261124/fixed-matchup-current-apu-lock`.

Using the AudioContext output timestamp to estimate each report's last missing
sample, 22 of 42 post-transition samples overlapped a traced DSP stage. One
overlapped a timed wake wait and one overlapped an MMIO handoff. These counts
describe sampled points, and intervals can overlap. They do not assign a
cause to all missing audio samples or measure DSP CPU time.

The optimized Wasm build linked and reached Team Select in Chrome. The
controller script failed to advance the away team. A second run timed out
at startup. Both reported audio underruns. The initial captures are under
`build-web-tests/upload-stall/{fixed-matchup-dsp-dual-load,dsp-dual-load-retail-smoke}`.

The fixture now allows up to four trigger pulses per team change. The failed
capture showed the correct controller side and a team card mid-animation.
With the longer retry window, three sequential Chrome runs verified Green
Bay at San Francisco and reached first-and-ten. Frame windows start after
the kickoff transition's reporting window. Missing audio frames are the
increase between the kickoff and final samples.

| Build | Full windows | Five-second FPS averages | Worst flip | Missing audio frames |
| --- | ---: | ---: | ---: | ---: |
| Specialized DSP handler | 7 | 10.6–22.1 | 378.70 ms | 510,976 |
| Preceding runtime | 7 | 15.3–23.7 | 172.38 ms | 190,464 |
| Specialized DSP handler, repeat | 6 | 12.2–27.7 | 181.64 ms | 261,632 |

The return ended at the SF 20, 16 and 22 respectively. The draws per frame
and camera cuts differed. Both handler runs had a lower minimum average and
more missing audio frames than the reference. The retail measurements do
not show an end-to-end improvement. Captures are under
`build-web-tests/upload-stall/{fixed-matchup-dsp-retimed,fixed-matchup-palette-retimed-reference,fixed-matchup-dsp-retimed-repeat}`.

### Comparing browser builds in an existing profile

After serving a published runtime and switching back to a local build on
the same origin, Chrome twice stopped during Wasm initialization. The browser
response for the JavaScript loader matched the preceding Pages build, while
the local server contained a different loader. The mode audit now records
the launcher's fatal error and stack when available. A pending transition
wait ends immediately on that error.

The Pages package keys the loader and Wasm requests with one digest of both
files. The browser workers inherit the loader URL. In the same profile, the
browser then fetched the intended loader and reached the opening drive using
the existing imported disc. The deployment check verifies both response
hashes and compiles the Wasm at its versioned URL.

The recovered run's five-second windows ranged from 17.4 to 28.9 FPS, with
a 211.74 ms worst flip and 75,520 additional missing audio frames from
kickoff to the final sample. During that interval a separate pair of
emulator processes averaged 5.78 CPU-seconds per second and all Chrome
processes together averaged 3.38, on a host with 20 logical processors.
These simultaneous measurements establish competing activity, but do
not quantify its effect on game performance.

### Time spent handing off the guest lock at 30 FPS

The browser frame limiter releases the guest execution lock before sleeping
until the next frame deadline. It now samples the clock again after releasing
the lock. A worker that resumes after its deadline immediately proceeds to
reacquisition. Uncapped frames also skip the limiter's clock read.

The deterministic Wasm fixture starts with 10 ms of frame work. An 8 ms
handoff leaves 15.33 ms to sleep before the 33.33 ms deadline. With a 45 ms
handoff, the frame is already late and the limiter requests zero sleep.
Both paths restore the original lock depth.

The release build reached the opening drive in hardware Chrome. Its eight
five-second windows from kickoff ranged from 10.4 to 24.2 FPS, with a
364.90 ms worst flip. The worklet missed 90,274 additional audio frames.
The retail run did not time lock handoffs individually, so it establishes
neither their frequency nor an end-to-end speedup.

### WebGPU presentation between guest flips

The framebuffer thread waits for each browser animation frame. WebGPU can
keep compositing the last canvas image between game flips. The presenter
redraws on a successful flip, a window-size or video-setting change, or
after an unsuccessful presentation. On other animation frames it cancels
the empty command before the backend acquires the actual canvas texture.

The hardware Chrome pixel fixture changed the canvas aspect twice, drew a
known green frame, then cancelled four successive idle presentation commands.
The composited canvas still read back exactly `[0,192,48,255]` at its centre,
and the fixture reported zero WebGPU validation errors.

In two retail Quick Games an instrumented JavaScript loader counted actual
WebGPU canvas texture acquisitions. Seven complete windows after kickoff
recorded 1,765 acquisitions in 35.08 s before the change (50.3/s) and 523
in 35.27 s after it (14.8/s). Guest flip reports averaged 16.1 and 14.9 FPS
respectively over their own seven complete windows. Different matchups
prevent a direct gameplay speed comparison.

The changed build showed Philadelphia–San Francisco at first and ten on the
SF 20. Across all eight windows including kickoff it ranged from 11.7 to
25.4 FPS with a worst flip of 257.49 ms. The audio counter rose by 159,232
missing frames between kickoff and the last sample.

### Reusing the WebGPU presentation binding

The canvas blit retains one bind group for the current texture view, filter
and source rectangle. Consecutive flips reuse the binding and the immutable
crop uniform. The cache holds its own view reference until replacement.
Offscreen blits and mipmap passes use the shared layout without displacing
the presentation binding.

A Wasm fixture with mock WebGPU calls exercised 121 successive cropped
presentations using one bind group creation, one crop buffer creation and
one crop upload. Previously each cropped presentation rebuilt all three.
The fixture also checked crop and filter changes, view replacement, and
allocation failure. Hardware Chrome passed the resize and crop/filter
switches, with exact green pixels at both the canvas center and corner
after the final crop and four idle presentation cancels.

The local preview initially served a `304` for the cached launcher after
switching to the older benchmark directory. Chrome then used the newer
loader with the older Wasm. The preview server now ignores modification-time
validators and sends `Cache-Control: no-store`. A retry fetched the reference
loader at its own versioned URL and entered the match.

Both hardware Chrome runs selected Green Bay at San Francisco. The cached
build ended on the kickoff meter. Its seven complete windows after the
kickoff transition averaged 25.2–30.1 FPS, with a 152.09 ms longest flip and
53,120 additional missing audio frames. The preceding renderer reached the
return and averaged 11.6–28.2 FPS across seven complete windows, with a
2,809.22 ms longest flip and 294,144 additional missing audio frames. The
different stages limit the comparison to the presentation call counts and
pixel tests above. Both runs dipped below 30 FPS.

### Measuring the CPU-vs-CPU opening drive

The fixed Packers–49ers fixture centers the controller and lets the intro
and kickoff run. It starts sampling once guest memory shows first-quarter
scrimmage, a valid down and time elapsed on the quarter clock. The report
records that timestamp so the window that straddles it can be excluded.

With the presentation binding cache on Intel hardware Chrome, the fixture
found first down at 295.17 seconds on the quarter clock. The next six
complete windows averaged 27.0, 14.9, 17.7, 19.0, 19.2 and 13.3 FPS.
The worst flip was 147.53 ms, with 24 intervals over 100 ms across those
windows. The worklet missed 167,552 additional source frames over the
36-second sampling period. The final screenshot shows the native Ulbrich
player card between plays. The audit failed on audio underruns. The local
report and capture are under
`build-web-tests/upload-stall/packers-49ers-opening-drive-final`.

The detailed pass reached first down at 296.76 seconds and logged six
complete opening-drive windows at 7.6–22.7 FPS. The longest flip took
269.08 ms, including 214.75 ms in texture processing. In the 7.6 FPS
window the renderer checked 120.27 MiB of guest texture data per frame
and spent 59.27 ms per frame verifying it and 1.23 ms decoding new data.
The worklet missed another 332,544 source frames during the sample. The
detailed timers add draw-path overhead. The capture is under
`build-web-tests/upload-stall/packers-49ers-verified-drive-phase-profile`.

A private Wasm fixture tried reusing one expected 16-byte vector for up to
four periodic spans per texture while still reading every guest byte. It
detected a mutation at every byte position of each test layout. Across
paired runs, the 64 KiB textures with three spans ranged from about 5.5%
faster to 1.1% slower despite more repeated bytes being covered. The
single-span and no-span layouts also showed small slowdowns. The runtime
retains the existing comparator.

### File-read logging on the streaming path

The shared `NtReadFile` bridge now flushes stderr only when it emits a
verbose read log. A Wasm fixture ran 1,000 sequential and explicit-offset
reads in each logging mode. Quiet reads made zero flush calls. Verbose
reads retained their 1,000 log writes and flushes. The fixture checked
status, byte counts and completion order for successful reads and EOF.

The pre-cache renderer's opening-drive comparison ended at the game's
disc-read error dialog before the first-down marker. A subsequent check
found the original disc import absent from the test profile. That run
provided no opening-drive timing comparison.

Both runtimes subsequently completed the Packers–49ers sampling route
using a fresh import of the same image in one Chrome profile. The preceding
runtime's seven complete post-marker windows averaged 16.2–29.3 FPS, with
a 287.12 ms worst flip and 103,040 additional missing audio frames. The
quiet-read runtime's six windows averaged 13.5–29.9 FPS, with a 183.11 ms
worst flip and 49,792 additional missing audio frames. These games had
different play sequences. Both dipped below 30 FPS and lost audio.

### Computing rectangular mip footprints

For a power-of-two texture, the snapshot size now sums the mip levels whose
two axes shrink together, then the levels whose longer axis still shrinks.
For DXT, this uses the block dimensions and counts the final levels that
each occupy one block. Irregular sizes, cube faces and pitched rows keep
their existing calculations. Every draw still checks guest allocation bounds
and texture contents.

The Wasm regression test covers 7,680 rectangular footprints, including DXT
block tails. A separate fixture compared the new snapshot calculation with
the old loop on 481,920 calls, including formats, irregular sizes, mip changes
and cube states. It found identical footprints. For 500,000 calls with
varying amounts of repeated state, medians were 8.21–8.84 ms with the loop
and 3.34–3.64 ms with the new calculation. This measures footprint computation.

### Texture checks repeated within one frame

Private Wasm trials grouped full comparisons into 256-byte, 1 KiB and 4 KiB
tiles. All three detected mutations at every tested byte position, including
unaligned windows and tile boundaries. A separate trial reduced an all-zero
span directly, without XORing each guest vector against the expected zero
vector. Both approaches produced mixed timings across image sizes and
content layouts. The game retains the existing comparison loop.

Detailed renderer reports now count complete matches against a retained
copy used earlier in the frame. They count same-frame mismatches and the
requested spans separately. The match total bounds the bytes that reliable
write tracking might save. Every current draw still verifies the span.

In retail Quick Game, the fixture now reads the first controller's assignment
and retries until Team Select confirms neutral. A previous attempt sent the
direction once and stalled at the human-controlled coin toss. The updated
fixture confirmed Green Bay at San Francisco and reached first down with
296.86 seconds on the quarter clock.

The seven complete five-second opening-drive windows averaged 20.1–30.1 FPS.
The longest flip was 143.98 ms, and the worklet missed 4,224 source frames
during the 36-second sample. Weighted by frame count, the renderer requested
124.70 MiB of comparisons per frame and found 115.86 MiB of exact same-frame
matches (92.9%). Comparisons cost 10.20 ms per frame on average and caught
31 same-frame mismatches. Texture processing, vertex work and submission
averaged 14.49, 5.55 and 8.23 ms per frame. The detailed profile adds timing
overhead. The local capture is under
`build-web-tests/upload-stall/packers-49ers-same-frame-texture-reuse-verified-neutral`.
Swizzled A8R8G8B8 (`0x06`) accounted for 99.68 MiB per frame, or 80.1% of
the matched bytes across all comparisons. Paletted `0x0B` contributed another
21.88 MiB per frame.

The same build with only flip timing enabled averaged 20.6–29.4 FPS over
seven complete opening-drive windows. The longest flip was 148.18 ms. The
worklet missed 9,600 source frames during the 36-second sample. The run used
the 30 FPS lock and completed a different sequence of plays. Its report is
under `build-web-tests/upload-stall/packers-49ers-verified-neutral-frame-only`.

A private Wasm fixture with instrumented writers compared 12,000 unchanged
256 KiB texture checks. Median time was 334.69 ms to compare the bytes and
0.43 ms to validate the page versions. It also detected 6,144 page mutations
and rejected pages with overlapping writes in progress. This fixture measures
the reader and has complete control over its writers.
In a separate run, 750,000 byte writes took 2.64 ms directly and 9.41 ms
with both page-version updates. Those measurements motivate limiting
tracking to texture pages while preserving coverage for every writer.

A second fixture filtered tracked stores to one fixed address window. With
one in 32 of 750,000 writes in that window, direct writes took 2.71 ms,
tracking every write took 10.13 ms, and the filter took 4.18 ms. With every
write in the window, the filter took 11.53 ms. The test controls the share of
writes in the window. Retail coverage still needs to include typed stores,
stack pushes, string operations, atomics and runtime writers.

xemu's Vulkan renderer checks dirty physical pages for both textures and
palettes. Its CPU memory implementation marks writes and its surface backend
marks downloaded render targets. This recomp needs coverage for translated
stores, guest RAM aliases, kernel copies and device writes before a clean
page can stand in for a byte comparison. [Texture dirty checks](https://github.com/xemu-project/xemu/blob/master/hw/xbox/nv2a/pgraph/vk/texture.c) · [CPU memory writes](https://github.com/xemu-project/xemu/blob/master/system/memory_ldst.c.inc) · [Surface downloads](https://github.com/xemu-project/xemu/blob/master/hw/xbox/nv2a/pgraph/gl/surface.c)

### Publishing WebAssembly fixed memory claims atomically

The fixed-memory table now publishes both wasm32 bounds in one atomic
value. This keeps a range check from combining an old upper bound with a
new lower bound when a mapping slot is reused. A forced interleaving
reproduced the old check falsely accepting a gap. The threaded Wasm test
ran 40,000 map and unmap cycles with a simultaneous reader and also
checked the mapping endpoints, heap ceiling and zeroing on reuse.
In a paired Wasm fixture, 98,304 boundary checks agreed across both versions.
Median time for 1.2 million reads rose from 6.22 to 7.33 ms when looking up
RAM and the contiguous window, and from 13.32 to 13.51 ms across six claims.

The patched runtime reached first down with 298.78 seconds left on the
quarter clock and completed a 36-second sample with the 30 FPS lock and only
flip timing enabled. Six complete windows averaged 18.4–27.7 FPS, with a
242.85 ms longest flip. The worklet missed another 22,528 source frames.
The audit recorded only audio-underrun failures. This game ran a different
sequence of plays from the baseline. The local capture is under
`build-web-tests/upload-stall/packers-49ers-atomic-fixed-claims`.

### Preparing WebGPU triangle indices

The vertex path reads eight unsigned 16-bit indices at a time when finding
the bounds of a batch with at least 32 indices. Dense triangle lists subtract
the lowest guest index in bulk and widen the result to the existing 32-bit
index format. Tests cover every count through 4,096, including high unsigned
indices, unaligned batches and incomplete triangles. The scalar Wasm,
instrumented Wasm SIMD and native Linux fixtures produced identical outputs.

In an alternating Wasm comparison at `-O2`, checking the bounds of roughly
2.4 million indices in 255-index batches took median times of 0.29 ms before
and 0.15 ms after. Dense triangle index remapping fell from 3.34 to 0.18 ms.
The replay measures CPU index preparation with fixed input and excludes
vertex attributes, texture verification, GPU submission and presentation.

The candidate's retail Chrome run reached first down and finished its
36-second sample with hardware WebGPU. The six complete windows averaged
10.6–20.2 FPS, with a 289.37 ms longest flip. The renderer counted 272,235
GPU vertex-program draws and zero software 3D draws. Audio missed another
437,376 source frames during the sample. The final scanout shows the native
Smith career-stat card over the field. The capture is under
`build-web-tests/upload-stall/packers-49ers-dense-triangle-indices`.

The next run used the unchanged runtime from the same Chrome profile.
Five windows averaged 29.9–30.0 FPS and one fell to 20.8 FPS. Its longest
flip was 1,951.49 ms, and the worklet lost zero additional frames during
the opening-drive sample. The two runs played different sequences. The
reference recheck is under
`build-web-tests/upload-stall/packers-49ers-dense-triangle-reference-recheck`.

The candidate recheck averaged 29.1–30.0 FPS across six complete windows,
with a 113.65 ms longest flip and 4,352 additional missing audio frames.
Both rechecks drew roughly 600,000 GPU vertex-program batches in the sampled
windows. The rechecks varied in play sequence and audio, so only the fixed
index replay isolates the optimization's effect. The candidate recheck is
under `build-web-tests/upload-stall/packers-49ers-dense-triangle-candidate-recheck`.

### Decoding packed vertex normals

The scalar 11:11:10 reader now loads unaligned words safely and extracts
signed fields without shifting signed values. Linux UndefinedBehaviorSanitizer
flagged the previous Z shift. The corrected scalar reader passed 18,432
checks across eight array strides and constant attributes.

WebAssembly SIMD decodes four normals at a time from validated streams.
The test checks the exact floating-point results, including clamp behavior
for constant inputs, distinct source and destination strides, unaligned
reads, partial groups and retained padding. Native Linux, scalar Wasm
and instrumented SIMD Wasm produced the same outputs.
The normalized array values and the constant endpoint clamp follow xemu's
separate paths. [Array decode](https://github.com/xemu-project/xemu/blob/master/hw/xbox/nv2a/pgraph/glsl/vsh.c) · [Constant decode](https://github.com/xemu-project/xemu/blob/master/hw/xbox/nv2a/pgraph/vertex.c)

The integrated Wasm replay packed 1.28 million normals into 64-vertex
batches with a 16-byte source stride. Median times went from 5.20–5.25 ms
with per-vertex fetches to 1.00–1.01 ms with the new stream path. This replay
measures normal decoding and packing on the CPU.

A 600-draw retail stadium trace found 338 draws with packed normals bound.
All 338 were triangle strips. Their bound normal streams used 8-, 10- and
16-byte strides. The trace finished before the timed opening drive.

The retail run reached first down and averaged 29.9–30.0 FPS in six complete
opening-drive windows. Its longest flip was 70.41 ms. The worklet lost
no frames during the 36-second sample. Six earlier underrun reports still
failed the full audit. The renderer processed 610,103 GPU vertex-program
draws in the sampled windows with zero software 3D draws. The capture is
under `build-web-tests/upload-stall/packers-49ers-packed-normal-simd`.

### Reusing remapped triangle-strip indices

The vertex path now carries the two shared indices forward when expanding a
strip into triangles. It remaps each source index once and preserves the
original winding, order and first-encounter vertex assignment. Scalar Wasm,
instrumented SIMD Wasm and native Linux tests check every strip length from
zero through 4,096 in both dense and sparse modes, including repeated indices.

An alternating Wasm replay processed about 2.4 million indices in 395-index
batches. Median preparation dropped from 12.81 to 6.03 ms in the sparse case
and from 35.52 to 8.99 ms in the dense case. The replay used the integrated
expansion and checked identical indices. It measures the CPU step with
fixed input.

The first retail run reached first down and completed its 36-second sample.
The six complete windows averaged 15.2–21.5 FPS, with a 271.82 ms longest
flip and 334,208 additional missing audio frames. All 342,281 sampled 3D
draws used GPU vertex programs. The final scanout shows players and the
referee during a play. The capture is under
`build-web-tests/upload-stall/packers-49ers-reused-strip-indices`.

The recheck on the same Chrome profile averaged 29.7–30.1 FPS across six
complete opening-drive windows. Its longest flip was 83.24 ms, with zero
intervals over 100 ms and 128 additional missing audio frames. All 563,945
sampled 3D draws used GPU vertex programs. The play sequences differed, so
the fixed-input replay is the isolated performance comparison. The recheck
is under `build-web-tests/upload-stall/packers-49ers-reused-strip-indices-recheck`.

### Separating frame pacing from renderer stalls

The opt-in pacing profile records elapsed guest-lock release, scheduled
sleep, elapsed sleep and guest-lock reacquisition. The interval timing
consumes the previous flip's pacing and retains it across window boundaries.
The test injects lock delays and sleep overshoot and checks the resulting
worst-interval and average records. Production timing policy is unchanged.

In the retail Packers–49ers trace with pacing and per-draw renderer timers,
six complete opening-drive windows averaged 27.7–30.1 FPS with no new
missing audio frames. The worst interval took 72.55 ms. The pacer requested
12.32 ms and spent 27.33 ms in sleep, plus 0.01 ms on each lock handoff.
Texture, vertex and submission timings in that same interval were 18.92,
6.76 and 15.63 ms. The average requested and elapsed waits were 6.31 and
11.89 ms across all intervals, weighted by interval count.

The same trace caught a 1,397.66 ms interval during stadium presentation
with zero pacing time. Submission accounted for 1,072.23 ms in that
interval, and the largest flush in its reporting window took 1,066.71 ms.
The known stadium line pipeline was ready before this stall. Earlier audio
underruns still failed the full audit. The capture is under
`build-web-tests/upload-stall/packers-49ers-pace-phase-breakdown`.

A second stadium capture enabled the WebGPU backend's slow-submission log.
The window containing a 1,108.92 ms flip included a logged 1,019.08 ms
submission, with 1,013.78 ms inside transfer replay. A separate 320.17 ms
submission spent 286.08 ms writing uniforms. These are measured CPU-side
calls into WebGPU and include any wait for the browser to accept earlier
work. The shorter capture stopped during the pregame route and failed on
audio underruns. It is under
`build-web-tests/upload-stall/packers-49ers-stadium-submit-attribution`.

### Reusing verified geometry prefixes on upload growth

An upload that grows on an existing WebGPU buffer backing keeps the shadow
of its verified prefix. It updates changed prefix blocks and writes the new
suffix. Offset writes, large bypass uploads and allocation failure still
invalidate the shadow. The scalar and SIMD fixtures check byte ranges and
the exact resulting contents. A hardware Chrome pixel check draws with
appended indices and verifies the old backing after a subsequent cycle.

In a paired Wasm replay of 120 uploads growing from 2 MiB in 4 KiB steps,
unchanged prefixes reduced written data from 281,395,200 to 491,520 bytes
with the same 120 queue calls. With one changing prefix block per update,
written data fell to 983,040 bytes and calls increased to 240. Fixed-size
uploads had identical byte and call counts. The growing-prefix medians
fell from 34.70 to 8.04 ms with a memory-backed queue, which excludes the
browser's transfer and queue-wait time.

The retail candidate completed the 36-second opening-drive sample with six
windows at 27.4–30.0 FPS. The longest interval in that sample took 111.56 ms
with no pacing time. The worklet missed another 18,304 frames. The largest
logged pregame submission took 368.20 ms, of which 367.78 ms was transfer
replay. The capture used flip, pacing and slow-submission timing. Different
play sequences prevent attributing the retail differences to prefix reuse.
The local capture is `build-web-tests/upload-stall/packers-49ers-geometry-prefix-retail`.

An isolated Intel Gen-12HP Chrome replay alternated 48 direct writes and
48 uploads through staging buffers mapped at creation. Readbacks matched
the input after each replay. At 2,544,544 bytes per upload, the median CPU
API time went from 48.46 to 17.04 ms and time through the queue fence went
from 75.70 to 64.07 ms. At 73,584 bytes, time through the fence was nearly
the same at 20.95 and 21.32 ms. This JavaScript replay excludes the game's
Wasm bridge and render workload. The staging prototype remains local.

### Mapped geometry through the Wasm bridge

On the Intel Chrome adapter, the Emdawn C API benchmark sent 48 uploads
of 2,544,544 bytes per arm and waited for the queue every eight uploads.
One-shot mapped staging cut median CPU submission from 59.86 to 32.16 ms,
while median wall time through the fences rose from 118.15 to 133.78 ms.
Final readback matched the last upload. At 73,584 bytes per upload, fence
time was 36.34 ms for direct writes and 36.81 ms for one-shot staging.

A separate three-arm run measured 198.54 ms through the fences for direct
writes, 216.62 ms for one-shot staging, and 123.23 ms for a pool of eight
staging buffers remapped after each batch. Median CPU submission was
91.50, 52.28, and 18.64 ms respectively. The pool test waited for both the
fence and the remaps, and verified the last upload by readback. The pool remains a
benchmark with bounded reuse. It has yet to run under the retail renderer.
Raw results are in `build-web-tests/verify-vector-width/{mapped-bridge,mapped-stage-pool}`.

Two 50-second Packers at 49ers pregame captures used the same instrumented
runtime and toggled one-shot staging. The direct run's nine complete windows
ranged from 16.0 to 29.0 FPS, with a 1,396.22 ms longest frame interval.
The staging run ranged from 23.0 to 30.0 FPS, with a 1,173.46 ms longest
interval. The slowest submissions spent 1,175.93 ms and 1,028.56 ms in transfer
replay respectively. That staging submission copied 4,979,120 bytes from
mapped buffers. Cumulative audio underruns were 241,536 and 13,952 frames
from startup through the sample. Each path had one retail capture, so the
frame pacing and audio differences need replication. The pregame stall
persisted on both paths. The default continues to use direct writes.
Captures are in `build-web-tests/upload-stall/packers-49ers-stadium-{direct,mapped}-geometry`.

### Identifying which uploads block pregame submissions

The retail direct-write run with the split timings logged a 368.56 ms
submission 15 seconds into stadium presentation. Geometry replay took
365.62 ms, texture uploads took 0.19 ms, and encoder flush time rounded to
0.00 ms. An earlier 310.01 ms submission spent 307.44 ms in the uniform
queue write. These timings identify where the worker waited. The earlier
Chrome traces show that calls can block behind work the browser already
received.

Nine complete pregame windows ranged from 21.0 to 29.9 FPS. The longest
interval was 442.84 ms, and the audio worklet missed 211,200 frames from
startup through the sample. The audit reported audio underruns and no
WebGPU errors. The capture is in
`build-web-tests/upload-stall/packers-49ers-stadium-transfer-phases-retail`.

### Reusing mapped geometry staging in the retail renderer

The local candidate uses eight staging slots with capacities rounded to
64 KiB and capped at 4 MiB each. A geometry write of at least 1 MiB starts
staging. Subsequent writes may share its encoder. After submission, each
slot remaps asynchronously. When staging is unavailable, the renderer
submits any earlier recorded copies and then uses a direct queue write.

Intel Chrome pixel tests confirmed allocation, remapping and reuse, and
fallback after exhausting all eight slots. The test overwrites a staged
vertex upload and checks the resulting triangles and both index backings.
The scalar and SIMD geometry shadow tests also passed. The candidate
overlay and the fixture are under
`build-web-tests/verify-vector-width/geometry-pool-retail`.

In two 50-second Packers at 49ers pregame captures with the same Wasm
package, direct writes averaged 29.40 FPS across nine complete windows
and pooled staging averaged 29.06 FPS. The number of intervals over
100 ms increased from two to ten. The longest interval across those
windows decreased from 475.83 to 409.36 ms. Audio samples at both ends
of the segment recorded zero new missing frames on the direct run and
54,144 on the pooled run. Both full audits failed on audio underruns.

A 190-operation submission with 86,784 uniform bytes took 435.45 ms
in geometry replay in the direct run. The pooled run logged two
submissions with the same operation count and uniform size, with
376.67 and 279.78 ms in geometry replay. Another pooled submission
spent 449.41 ms outside the replay phases currently timed. Chrome
confirmed pool reuse on the retail path. The runs leave direct writes
as the default. Captures are under
`build-web-tests/upload-stall/packers-49ers-stadium-geometry-pool*`.

### Trimming consecutive uniform uploads

The candidate retains the previous uniform payload on the WebGPU worker
and trims byte-identical 4 KiB blocks from the edges. It issues at most
one queue write and retains at most 8 MiB plus shader padding. The Wasm
sanitizer fixture checked exact contents, zero tails and buffer growth.
The hardware Chrome rendering suite passed with reuse enabled.

During the reported title, menus and loading windows before the stadium
marker, reuse saved 50,997,504 of 418,473,216 requested bytes (12.19%)
and skipped 23 queue writes. In nine complete pregame reporting windows,
all 1,042,600,480 requested bytes were sent across 1,570 submissions.
Each of those windows reported zero skipped uniform writes. The candidate
remains local because the savings stopped when the stadium workload began.
Source and replay fixture are under
`build-web-tests/verify-vector-width/uniform-upload-retail`.

The same-build control averaged 29.50 FPS with 768 new missing audio
frames during the sampled pregame. The reuse run averaged 17.22 FPS
with 813,184 new missing frames. The runs had different stage speeds
and submission counts, so these samples do not isolate the cause of the
frame pacing difference. Both logged a 190-operation submission that
spent more than 400 ms in geometry replay. Captures are under
`build-web-tests/upload-stall/packers-49ers-stadium-uniform-upload-{reuse,control}`.

### Shader compilation behind upload stalls

The retail direct-write build was traced on Intel hardware Chrome. A 996.42 ms
client token wait overlapped three GPU-process Dawn decoder batches totaling
about 1,002 ms of elapsed time and 979 ms of thread CPU. During the two longest
batches, 47 of 57 instruction-pointer samples landed in `dxcompiler.dll`.
The game logged 1,014.93 ms in texture upload replay for that submission.
A separate 392.66 ms token wait overlapped another shader compiler batch and
appeared as a 404.47 ms geometry upload stall.

A second capture marked pipeline creation and first use from the WebGPU
worker. Shader compiler batches again overlapped waits from uniform and
geometry queue writes. The first long batch began alongside first use of
several transformed-triangle pipeline variants and the existing prepared
line pipeline. The capture also found 334 module creations using 17 distinct
WGSL sources. Normalizing shader references by exact source left 43 distinct
descriptors among 718 pipeline requests. This census preserves layout identity,
vertex attributes, depth/stencil, blend and rasterizer state.

Four fresh-browser replays issued that recorded sequence twice per path.
Direct creation completed through the final queue fence in 4.31 and 6.34 s.
Exact descriptor reuse completed in 4.93 and 6.50 s. Reuse avoided 317 shader
module requests and 675 pipeline requests with zero validation errors. These
replays cover pipeline creation and queue completion. They have no draws or
retail frame pacing, and give no evidence of a wall-time gain from deduplication.

Two replays timing the distinct descriptors separately identified three
transformed-triangle pipelines that first appeared well into pregame. The
pipeline first used about 6.92 s after the stadium marker took 424–460 ms
to compile in replay. Its first-use mark falls inside the 399 ms decoder
batch that delayed geometry upload. Two more first used near 15.80 s took
183–191 ms and 223–232 ms in isolation. Both first-use marks fall inside
the 493 ms decoder batch that delayed a uniform write. The already
prepared line pipeline was the most expensive in cold replay and was
available at first use in the retail trace.

The traced retail captures are under
`build-web-tests/upload-stall/packers-49ers-stadium-{gpu-process,pipeline-census}`.
They still had audio underruns and frame intervals beyond the 30 FPS budget.

### Preparing the three pregame triangle pipelines early

The local proof of concept uses the three descriptors identified in the
previous trace. It compiles them asynchronously on the live device after
the existing line preparation. It returns a prepared object only when the
live layout, complete shader sources and pipeline state match. Both browser
packages use identical Wasm and the same descriptor checks. The control
skips the extra compilation. The captured shader sources stay local.

All three prepared pipelines matched at first use. In the control, the
first-use markers preceded Dawn decoder batches of 388.55 and 522.00 ms.
With early compilation, the largest decoder batch across the pregame
sample took 236.15 ms. Across nine complete windows the mean increased
from 29.32 to 29.83 FPS. The longest interval fell from 503.00 to 282.38 ms,
and new missing audio frames fell from 9,856 to zero. The warm run still
had startup underruns and pregame windows below 30 FPS. Each arm ran once,
and the cameras reached the first-use points at different times. The
match and decoder evidence support the effect on compilation stalls.
The frame and audio measurements need repetition.

The original census logged the first creation of each target vertex module
less than 0.74 ms before pipeline creation. The shared fragment module was
available during the title. A release implementation needs to obtain each
vertex program earlier or learn the recipes locally. The experiment did
not add captured shaders to the runtime. Traces are under
`build-web-tests/upload-stall/packers-49ers-stadium-exact-precompile-{warm,cold}`.

A separate instrumented Wasm build timed the most recent changed word
of each complete NV2A vertex program. Repeated writes of the same word
kept the original timestamp. Hashes of the generated WGSL matched all
three target shaders from the earlier census. Their exact program words
had been stable in the active NV2A slots for 0.630, 1.175 and 0.275 ms
at first translation. The maximum across repetitions of the first
shader was 3.340 ms. Watching the active-slot writes gives much less
lead time than these pipelines need to compile. The measurement covers
NV2A program memory and leaves earlier copies in guest RAM unmeasured.
Probe and capture are under
`build-web-tests/upload-stall/{guest-program-lead,packers-49ers-stadium-guest-program-lead}`.

### Learning pregame pipelines across browser launches

A local browser probe matches slow submissions to recently used
transformed-triangle pipelines and stores up to eight descriptors in
IndexedDB. The cache is keyed by runtime revision and layout. On a new
launch it prepares the saved descriptors asynchronously after the existing
line preparation. Live requests reuse a prepared object only when the
shader sources, render state and layout object match. The test packages
learn from the local game and include no captured shader data.

A hardware Chrome fixture reopened the same profile and read back exactly
`[64, 128, 191, 255]`. It verified reuse in the same revision and fallback
for a changed revision, shader, state or layout object.

The first retail run saved six recipes and the next launch compiled all
six before stadium entry. All six matched live pregame requests. The
longest GPU-process decoder batch fell from 5.73 s on the learning run to
2.31 s on the warm run. Complete pregame windows averaged 16.56 and 24.50
FPS and the worklet missed 529,792 and 301,824 frames during those samples.
The learning run hit an unusually long stall, and the warm run still had
an early 2.41 s submission and many late frames. Preparing the six recipes
also took about 14.34 s in this launch. The pair proves that learning and
reuse work through the retail path and leaves the performance benefit unproven.

A repeat warm launch again matched all six recipes. Preparation took
0.26 s. Its nine complete pregame windows averaged 29.94 FPS, with a
75.27 ms longest interval and zero new missing audio frames. The full audit
recorded one startup underrun. A subsequent direct-write control used the
same Wasm and Chrome profile with application recipe preparation disabled.
It averaged 29.47 FPS, with a 431.90 ms longest interval and 5,760 new
missing audio frames. The longest pregame decoder batch was 116.03 ms in
the warm repeat and 410.87 ms in the subsequent control. The fixed-order
comparison leaves browser-cache and workload variation as possible influences.
The prototype remains local.

The local probe, fixture and captures are under
`build-web-tests/upload-stall` as `learned-pipeline-cache.js`,
`test-learned-pipeline-cache.cjs` and
`packers-49ers-stadium-learned-pipelines-*`.

The packaged runtime now includes an opt-in implementation. The WebGPU
worker identifies slow replays directly, and the launcher supplies the
build fingerprint for cache invalidation. It stores a single bounded
record per origin and stops issuing additional compilations after its
1.2-second preparation budget. An individual in-flight compile may
extend beyond that budget. The hardware fixture verifies exact readback
and fallback for a stale version, a changed shader, layout or render state,
unavailable storage, and an invalid stored shader.

On the integrated retail build, the first launch saved six recipes from
slow submissions. The next launch prepared all six in 0.75 s and all
matched live pregame requests. The longest interval in the complete
pregame windows fell from 528.36 to 347.64 ms. Average FPS fell from
29.33 to 28.13, and the warm run missed 125,312 pregame audio frames
compared with zero in the learning run. The learning run reported audio
underruns before pregame. The paired run verifies operation
through the launcher. The feature remains off by default. Captures are
under `build-web-tests/upload-stall/packers-49ers-stadium-runtime-pipeline-cache-*`.

### Opening-drive audio and frame timing with warm pipelines

The packaged cache build reached first-and-ten at 4:54.5 of Q1 in
Packers at 49ers. Across the next 36 seconds, all six complete windows
fell below 30 FPS (16.7–28.7 FPS), and the worklet missed 171,392 frames.
The only WebGPU submissions over 100 ms came within eight seconds of
stadium entry, before the sampled drive. Audio timing captured 33,232
producer records through the full session without a trace loss report.

During the drive, producer deadlines ran up to 113.77 ms late. The
largest VP stage took 108.18 ms with zero recorded voice-lock waits.
The longest DSP span was 55.01 ms, the longest MMIO handoff was
55.88 ms, and the longest measured wake overshoot was 56.72 ms.
These elapsed durations include host scheduling. They show that
opening-drive audio starvation persists after the compilation stalls.
The capture is `build-web-tests/upload-stall/packers-49ers-warm-stadium-opening-apu`.

### Reducing pipeline cache lookup cost

The warm cache compares shader sources before encoding render state.
Learning compares the same fields directly and keeps a bounded history
of candidates without building composite strings containing the shaders.

Seven alternating pairs replayed 22,944 recorded synchronous pipeline
requests per arm with GPU calls stubbed out. Both warm lookups returned
4,608 prepared objects. Median time dropped from 2.37 s to 0.38 s, and
serialized text dropped from 1.54 billion to 14.22 million characters.
The learning pass replayed the same requests and first uses in a separate
comparison. Its median fell from 3.63 s to 1.04 s.
This measures JavaScript lookup work, including instrumentation, with
no GPU compilation or frame-time claim.

The retail package with the new warm lookup reused all six saved
recipes. This check used the previous build's cache key explicitly to
hold the saved recipes fixed while changing the lookup code. The nine
complete windows averaged 29.56 FPS, the longest interval was 486.13 ms,
and the worklet missed 2,176 frames during the segment. The capture is
`build-web-tests/upload-stall/packers-49ers-stadium-pipeline-lookup`.

### Draw preparation during the opening drive

A follow-up capture enabled detailed renderer counters and APU tracing
with the warm cache. It reached first-and-ten at 4:56.1 in Q1. In the
36-second sample, six complete windows ranged from 10.5 to 25.4 FPS.
Frame-weighted texture work took 29.10 ms per frame, including 19.95 ms
for byte verification. Vertex preparation took 7.93 ms, and submission
took 16.26 ms. Same-frame matches covered 88.54 MiB per frame. The
renderer still observed same-frame changes, including three reported
changes in the 16.1 FPS window, so frame identity alone cannot justify
skipping verification.

One 2,166.16 ms submission spent 2,163.04 ms in the uniform queue write.
The earlier opening-drive capture had no submission over 100 ms, and
the follow-up shows that these stalls can occur during gameplay as well
as pregame. The follow-up missed another 348,800 worklet frames during
the sampled drive. Profiling and match progression differ between
captures. The raw report is under
`build-web-tests/upload-stall/packers-49ers-opening-cpu-and-apu`.

### Standalone X-memory data-register loads

The DSP dispatcher now uses dedicated handlers for standalone X-memory
loads from `(Rn)` and `(Rn)+Nn` into X0 through Y1. They use the same
24-bit memory reads and address update logic as the general dispatcher.
The captured GP frame executed these forms 734 times in 8,351 instructions.
The captured EP frame used neither.

Two Wasm replays of seven alternating pairs reproduced the captured state
and DMA transfers on every iteration. For 1,000 GP frames, the medians
went from 73.74 to 71.52 ms and from 73.14 to 72.60 ms. EP medians moved
in opposite directions across the two comparisons. The dispatch fixture
passed 151,328 exact state checks in Windows and Wasm with UBSan, including
all destination/address register encodings and positive and negative N
modifiers. Timings are under `build-web-tests/dsp-x-data-load`.

The rebuilt retail runtime reached first-and-ten at 4:56.2 of Q1 with
the default cache and audio settings. Six complete windows over the
following 36 seconds averaged 29.9–30.0 FPS, the longest interval was
52.87 ms, and the worklet reported zero additional missed audio frames.
The last frame shows the referee calling a penalty and a legible scorebug.
The full audit still failed on earlier audio underruns. Changes in the
play sequence and profiling prevent attributing the retail result to
the DSP specialization. The capture is
`build-web-tests/upload-stall/packers-49ers-opening-dsp-x-data-load`.

### Finding retained texture copies

The texture hash memo now inserts at the first empty slot in its bounded
probe window. A slot stays occupied until the whole table resets, so lookup
can stop at the first empty slot. A full window still replaces its oldest
entry. Native sanitizer checks and both Wasm test modes passed the wraparound
collision case, ring eviction, and same-frame mutations at every byte position.
Every memo hit still verifies the guest bytes before using its retained hash.

Ten alternating pairs compared the prior and updated binding paths in Wasm
with 192 aligned textures. Each arm verified 256 MiB of unchanged data per
sample and produced the same key checksum. At 256-byte textures the median
fell from 38.40 to 15.91 ms, and at 4 KiB it fell from 8.30 to 7.05 ms.
At 64 KiB the timings overlapped. This measures synthetic binding loops
with full comparisons. The local fixture is under
`build-web-tests/memo-first-vacant`.

Three sequential hardware Chrome runs used the same profile, 30 FPS cap,
and Packers–49ers CPU-versus-CPU route. Each reached first-and-ten and
sampled the next 36 seconds. The table uses the six complete five-second
windows in each sample.

| Run | FPS range | Worst flip | New missing audio frames |
| --- | ---: | ---: | ---: |
| First candidate | 15.7–26.1 | 252.61 ms | 448,000 |
| Previous build | 27.5–30.0 | 212.76 ms | 24,448 |
| Candidate repeat | 27.9–30.0 | 142.01 ms | 24,576 |

All three audits failed on audio underruns, and the different play sequences
and spread between runs leave the gameplay speed effect unproven. The repeat
reached second-and-five at 4:44 with player models, field markings, the
scorebug and lineup text visible. The local reports and scanout frames are
under `build-web-tests/upload-stall/packers-49ers-opening-texture-memo-*`.

### Testing two alternatives to SDL frame sleeps

A Chrome 157 fixture kept the 30 FPS deadline and compared SDL sleep, a
dedicated JavaScript timer worker with a notification and timeout fallback,
and a direct `Atomics.wait` timeout. Three rounds rotated the order of all
three arms for each of six simulated workloads, recording 135 frames per
workload and arm. All arms released the stub guest lock during waits. The
timer worker used its timeout fallback in 100 of 571 waits.

Across the five workloads below the 33.33 ms work budget, 95th-percentile
frame intervals were 46.36–50.03 ms with SDL, 44.98–58.85 ms with the timer
worker, and 47.68–49.81 ms with direct waits. The 40 ms workload never used
the pacer. A separate SDL-versus-worker run had similarly overlapping
results. Neither alternative consistently reduced frame jitter, so the
runtime keeps SDL pacing. The private fixture and full browser reports are
under `build-web-tests/frame-pacing-worker-timer`.

Among the three texture-memo Quick Game runs, eight complete opening-drive
windows had a worst interval above 100 ms. Six of those intervals recorded
zero pacing time, including the repeat's 142.01 ms interval and the control's
212.76 ms interval. The other two recorded 55.29 ms in a 116.31 ms interval
and 15.66 ms in a 207.02 ms interval. Pacing can contribute to individual
stalls, while the six unpaced intervals point to work or scheduling delays
elsewhere in the runtime.

### Omitting repeated uniform commands within a render pass

The WebGPU recorder already reused the stored bytes for consecutive identical
shader uniforms. It now skips the command too when the stage has already
set that offset in the active render pass. The first push for each stage in
a new pass still records the offset. The byte comparisons and upload layout
remain the same.

The Wasm sanitizer fixture verifies both stages, repeated pushes, changes
within a pass, and the first push after resetting pass state. The Chrome
hardware suite rendered two passes in the same command buffer and verified
both readback pixels at the retained nonzero uniform offset. The full suite
passed with zero WebGPU validation errors. In nine
alternating recording samples, 300 passes with 128 draws each recorded 600
uniform operations instead of 76,800 when both stages repeated. When both
stages changed every eight draws, the count fell to 9,600. When the vertex
stage changed every draw and the fragment stage changed every eight, it fell
to 43,200. Both recordings stored identical byte counts for every workload.
Wall time improved for the two most repetitive sequences and varied on the
others. The private fixture is under `build-web-tests/uniform-pass-elision`.

The retail package reached first-and-ten at 4:56.3 of Q1. The next seven
complete five-second windows ran at 15.9–27.3 FPS, with a 156.68 ms worst
flip. The worklet missed 51,712 additional source frames in the sampled
36 seconds. The final scanout showed the Favre and Driver player cards with
legible text. An earlier pregame window had a 2,751.49 ms worst flip with
zero pacing time and a 2,495.37 ms submission that spent 2,485.96 ms in
texture upload calls. These are elapsed browser call times. The audit
failed on audio underruns, and the single retail run cannot establish a
gameplay speedup. The capture is under
`build-web-tests/upload-stall/packers-49ers-opening-uniform-pass-elision`.

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
