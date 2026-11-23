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
transfers, pass encoding and final submission. These are elapsed times on
the worker and can include browser or OS scheduling delays.

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
the recorded range sends the full payload. Offset writes and uploads larger
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
