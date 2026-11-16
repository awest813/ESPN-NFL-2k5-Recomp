# Stadium and staff rendering checks

Original-Xbox scene/audio matching, complete game-mode fidelity and a sustained
30 FPS floor remain unfinished. Default audio still bypasses DSP programs.
An opt-in GP/EP path now executes uploaded programs, but its continuity and
original-Xbox output matching remain unfinished. The chronological checks
below document specific behavior and limitations.

November 8, 2026. Retail USA disc in Chrome 156 on Windows, hardware WebGPU
on Intel `gen-12hp`, development O1 link and the default 30 FPS cap. The
renderer under test is the published `e410571` runtime. This records observed
rendering, not pixel identity with an Xbox capture or a minimum-FPS benchmark.

| Scene | Views checked | Result and scope |
| --- | --- | --- |
| Atlanta at San Francisco | Outdoor stadium flyover, crowd, team/stadium/location titles, coin toss, referee and players | Rendered in the preceding pass; no GPU validation error observed. |
| New England at Minnesota | Enclosed roof, suspended lights/fixtures, flag, crowd tiers, banners, field, intro overlays, kickoff and first possession at NE23 | Roof and stands remained visible through camera changes; textures and overlays rendered. Kickoff advanced to first-and-10 at 4:57. |
| Minnesota sideline replay | Standing photographers, straps/lenses, kneeling cameraman, suited sideline figure, yellow EVENT STAFF clothing, water containers, markers and wall banners | Examined from several close and oblique camera views. No missing limbs, detached model geometry or missing clothing textures observed in these views. |

The runtime log for the Minnesota pass contains no WebGPU device errors,
device loss, failed downloads/fences, dropped queued draws, page exceptions
or crash diagnostics. Expected absent cache-file probes and known guest TODO
sites remain recorded; those are not treated as rendering failures by themselves.

Faces, silhouettes and clothing are visible, but polygon density and texture
detail have not been matched against original Xbox footage. Night, rain, snow,
other enclosed stadiums and every staff/model variant remain outside this pass.
The work stopped after the indoor/staff case at the user's request.

## Local evidence

Captures and logs stay in ignored build directories; no disc or model assets
are added to the repository.

- `build-web-tests/stadium-render-fixed/report.json`: preceding outdoor case.
- `build-web-tests/stadium-fidelity-expanded/report.json` and `runtime.ndjson`:
  indoor/staff case and diagnostics.
- `metrodome-roof.png`, `metrodome-overlay.png`, `metrodome-field.png`: indoor
  roof, fixture, crowd, banner and field views.
- `metrodome-live-now.png`: first possession after kickoff.
- `metrodome-photographers.png`, `metrodome-staff-side.png`,
  `metrodome-staff-reverse.png`: close staff and equipment views.

## Reproduction and reporting

Use `tools/audit-web-modes.cjs` with a dedicated browser profile and an already
imported disc; see [the mode audit](WEB-GAME-MODES.md#evidence-and-reproduction).
Record the team-selection screen before starting each stadium case.

For replay, finish a play, pause, select Replay and press Xbox X to show help.
The left stick rotates the camera, the D-pad moves its aim, Y zooms in and B
zooms out. Default keyboard bindings are WASD, arrow keys, V and X respectively.
This provides close staff views without changing the game assets or renderer.

The audit tool now records browser warnings/errors and uncaught page errors,
plus browser version, viewport and adapter metadata. GPU failures, rejected
submissions and browser exceptions override a requested `pass`/`partial` with
`fail`, stay in the report and produce a nonzero CLI exit status. A real-browser
fixture injects failures to verify this behavior; it requires no retail data.
Case boundaries also wait for an in-flight log drain. The browser regression
reproduces the former race with a delayed log read and verifies that its queued
runtime GPU error reaches the case report before it is finalized.

```sh
node tests/web/test_audit_diagnostics.cjs
node tests/web/test_audit_browser.cjs
```

## Widescreen stopping point — November 15, 2026

The SDL/WebGPU presenter now distinguishes display aspect from guest pixel
aspect. Its default crop (640×448 from 720×480) fills a 16:9 GPU canvas;
fullscreen fits that canvas inside the window. The portable presentation
callback identifies match views using checked guest reads, including pregame,
and excludes pause/play-call states. The camera patch uses the visible source
area (default stretch 56/45); menu/flat-card constants return to 1/1/0.

The presentation texture also stays locked through synchronous submission.
Previously the flip thread could replace/release it between recording a blit
and replaying the command buffer. Minimized windows cancel the unused buffer.

Validation at this stopping point:

- Live layout helper: default crop, 4:3, 16:9, ultrawide, zoom, empty inputs,
  and bounds across 10,000 window sizes. The actual portable match callback
  rejects invalid pointers, scores, timeouts, periods and non-finite clocks.
- Native renderer suite: camera constants, menu/flat transitions, patch-header
  validation, and the existing GPU/reference and failure-recovery scenes.
- Hardware Chrome 156 and CI Chromium 153/SwiftShader: exact rendered pixels,
  no GPU validation errors, and canvas changes 640×360 → 640×480 → 640×360.
- Full launcher browser suite: imports, OPFS mounting, disc reads and static-host
  isolation fallback. A fresh pinned checkout reproduces all 51 patched runtime
  files without changing the submodule revision.

The retail diagnostic run (`build-web-tests/widescreen-handle-debug`) rendered
Carolina at San Francisco, intro titles, kickoff and pause. A fresh attract
run also rendered stadium tiers, sideline players, staff/equipment and coin
toss. Logs confirm the world-camera transition from 1.0000 to 1.2444.

The preceding run (`build-web-tests/widescreen-final-retail`) **failed** during
an attract match with an undefined vertex shader module/resource at WebGPU
pipeline/bind-group creation and a black screen. This exception did not repeat
in the two fresh diagnostic cases. Its exact cause is unresolved; the texture
handoff fix closes a concrete lifetime race, but is not proof that this specific
exception is fixed. The failed evidence remains separate from later cases. A later final-build
attempt (`build-web-tests/widescreen-publish-retail`) also failed on stadium
entry with a WebAssembly out-of-bounds exception. Stadium-entry stability
therefore remains an open failure, not a passed check. The audit now retains
full exception stacks to support the next debugging pass.

Audio drops and intervals below 30 FPS occurred during the diagnostic run.
Original-Xbox pixel/audio/gameplay comparisons, every stadium/staff variant,
weather/night combinations, software-presenter widescreen parity, and a
sustained 30 FPS floor remain unverified. This is a tested implementation
checkpoint, not a claim of complete graphics, audio or gameplay accuracy.

## Recorded resource ownership follow-up

The next retail reproduction captured an undefined texture in
`copyTextureToTexture`, with the stack resolving to the WebGPU shim's `replay`
and `do_submit`. Evidence is in `build-web-tests/stadium-crash-stack-2`.
A standalone regression then reproduced the same exception by recording a
copy, releasing its source, allowing the queued destruction to run, and
submitting the recorded copy. This is valid deferred-destruction use under
[SDL's release contract](https://wiki.libsdl.org/SDL3/SDL_ReleaseGPUTexture).

The shim now retains textures, GPU buffers and transfer storage referenced by
recorded operations. Submission releases those references after replay and
readbacks complete; cancellation and rejected recordings release them too.
The application reference can be released independently. This replaces
immediate wrapper destruction while pending commands still hold raw pointers.

The regression fails on the preceding implementation with the retail copy
exception. Hardware WebGPU and Chromium/SwiftShader pass the fixed version,
including shared/cancelled/rejected recordings, early texture and upload-buffer
release, mip generation, blits, sampled textures, color/depth targets, indexed
vertex/index buffers, and exact readback pixels. Launcher/OPFS and audio/video/
input integration checks also exercise the rebuilt shim.

Post-fix retail evidence is in `build-web-tests/resource-lifetime-retail`.
Stadium entry, intro overlays, players and coin toss rendered without the
recorded-copy exception in the first run; repeated entry is recorded separately.
These checks identify and fix one demonstrated resource lifetime fault. They
do not establish that every previously observed shader-handle or out-of-bounds
exception shares this cause. Full graphics/audio/gameplay reference fidelity
and a sustained 30 FPS floor remain open.

## Transfer-buffer versions and emulator reference setup

A second data-integrity defect was reproduced with exact pixels: recording a
red draw/upload, cycling its bound staging buffer to blue, then submitting the
commands in reverse order changed the earlier result to blue. The preceding
implementation ignored `SDL_MapGPUTransferBuffer(..., cycle=true)`.

Each recorded upload/download now retains its backing allocation. Cycling a
bound mapping creates a fresh allocation; old commands keep their captured
bytes. Non-cycling maps continue to share the current storage. Allocation
failure leaves the previous mapping intact. This follows the pinned SDL
[transfer mapping contract](https://wiki.libsdl.org/SDL3/SDL_MapGPUTransferBuffer).

The failing-before logs are `build-web-tests/transfer-cycle-before.log`.
Fixed hardware/SwiftShader results are in `transfer-cycle-checked-hardware.log`
and `transfer-cycle-checked-linux.log`. They check vertex and texture pixels,
reverse submission, application release, cancelled/rejected older generations,
non-cycling writes to unreferenced ranges, and an old readback completing after a newer mapping.
Launcher/OPFS and audio/video/input integration run against the rebuilt game.
The headless retail case in `build-web-tests/transfer-cycle-retail/report.json`
rendered the stadium, intro and players without browser/GPU exceptions. Known
guest TODO diagnostics remain. GPU destination-resource cycling was still a
separate open check at that checkpoint; the follow-up below covers it.

The supplied files in Downloads now allow a local xemu reference boot. An
isolated configuration and copied EEPROM/ROM files are under ignored
`build-web-tests/xemu-reference`; the original HDD is used with `-snapshot`.
The first reference run reached Arizona at New Orleans gameplay and produced
`xemu-2026-11-15-19-42-36.png`, a raw 640×480 game frame without desktop UI.
That run used 128 MB and surface scale 2; a later configuration explicitly
selects 64 MB and scale 1 for repeatable checks. Desktop interaction stopped
when the user pressed Escape. A controlled scene-matched comparison has not
yet been completed, so these captures do not establish rendering/audio parity.

## Destination texture and buffer versions

The destination follow-up reproduced two more exact-pixel failures on both
hardware WebGPU and SwiftShader: cycling a texture upload changed a previously
bound red texture to blue, and cycling a vertex upload changed an earlier red
draw to blue. The failing logs are
`build-web-tests/destination-cycle-probe-expanded-before.log` and
`destination-cycle-probe-expanded-linux-before.log`.

Public texture/buffer handles now select a current backing allocation. Recorded
operations retain that specific backing, independently of subsequent cycling
and public-handle release. A cycling write creates a new allocation when the
current one is referenced by a recording; allocation failure preserves the old
allocation and rejects the recording. Copy/blit sources are retained before
rotating their destination, including when the handles alias. Bind-group cache
entries identify the captured texture version. Clear passes capture their
color/depth versions, while LOAD passes retain their existing contents.

Permanent exact-pixel tests cover texture, vertex and index uploads, texture
copies, blits, color clears and depth-stencil clears. They submit old and new
recordings in reverse order and release public handles before replay. The full
suite passes on hardware Chrome and Chromium/SwiftShader without WebGPU
validation errors (`destination-cycle-final-hardware.log` and
`destination-cycle-final-linux.log`). Launcher/OPFS and audio/video/controller
integration checks pass against the rebuilt game. A fresh pinned checkout
reproduces all 51 patched files without changing the submodule revision.

The retail case in `build-web-tests/destination-cycle-retail/report.json`
completed stadium entry, a sideline coach shot and coin toss without recorded
browser/GPU exceptions on hardware Chrome 157. Visual inspection found large
stray polygons behind the coach in `stadium-intro.png`; this is an unresolved
geometry fault, and its relationship to resource cycling is unproven. The
later `players-gameplay.png` shows players, referee, stadium and Demo Mode text
at coin toss. This run is partial, not a visual-fidelity pass. Frame-rate
samples below 30 FPS and audio drops also remain in the runtime log.

These checks establish resource-version correctness for the covered cases.
They do not establish full stadium/staff-model fidelity, audio/gameplay parity,
or a sustained 30 FPS floor.

## Queued fragment-uniform overrun

The geometry investigation found a separate memory corruption defect: the
current `SgXfShade` block is 400 bytes, but `SgQueuedDraw.fs` reserved only 384.
Queue insertion copied all 400 bytes. A later adjacent draw overwrote the
previous draw's final uniform values; a final draw could write past the allocated
draw array. This affects the shared SDL GPU queue, including the web backend.

`tests/web/test_draw_uniforms.py` extracts the production queue insertion,
structures and shader uniform block. On the preceding implementation it fails
when the second insertion changes the first draw's uniforms
(`build-web-tests/draw-uniforms-before.log`). The fix reserves 512 bytes,
statically checks the 3D uniform structure against that capacity, and rejects
oversized blocks before any queue mutation. The regression now verifies both
complete adjacent uniform blocks and a guard after the final record, plus
oversized-input rejection. It runs in the regular web CI suite.

A pre-fix comparison with draw merging disabled rendered New York at Miami
intro players, staff, sideline equipment and text without recorded browser/GPU
exceptions (`build-web-tests/stadium-nomerge`). It did not reproduce the earlier
coach shot, so it cannot establish that merging caused the polygons. Likewise,
the demonstrated uniform overrun is not proof that every geometry or earlier
shader-handle exception has the same cause.

With the fix and normal merging enabled, the retail run in
`build-web-tests/draw-uniforms-retail/report.json` completed Baltimore stadium
entry, Ray Lewis's player intro with readable career text, and coin toss without
recorded browser/GPU exceptions. The four captured scenes show no large stray
polygons, but do not match the earlier coach shot. Launcher/OPFS and
audio/video/controller integration checks pass against the rebuilt runtime.
Audio drops and sub-30 FPS samples remain; this is not a full fidelity or
performance pass.

## Exact vertex-program identity and exceptional math

Two three-instruction MOV programs with hash `A3202AA7` at start slot zero
reproduced incorrect cache reuse. Their CPU outputs and input masks differ,
but the old cache returned the first program's shader for both. The fixture is
`tests/web/fixtures/vp_cache_collision.h`; the failing production-lookup result
is `build-web-tests/vp-cache-before.log`.

The SDL GPU cache now retains and compares the exact instruction words through
FINAL, using the hash to select the probe sequence. Code after FINAL does not
change identity, and a failed program does not poison a colliding program.
The fixed snapshots add about 2.1 MiB at the current cache capacity. Invalid
start offsets return to the interpreter. Rare collisions are logged so retail
evidence can distinguish this defect from other geometry faults.

The expanded GPU differential check exposed two math/reference problems.
SwiftShader's zero-base LIT result differed from the CPU, so WGSL now handles
zero-base negative, zero and positive exponents explicitly. Separately, the
CPU expected NaN for zero times infinity. xemu's
[NV2A shader generator](https://github.com/xemu-project/xemu/blob/master/hw/xbox/nv2a/pgraph/glsl/vsh-prog.c)
documents that MUL returns zero when either operand is zero, including exceptional
operands; MAD uses that product before addition. The interpreter and WGSL,
GLSL and HLSL translations now implement that rule. The baseline decoder was
corrected independently, and explicit expected-value cases check positive zero,
infinity/NaN operands, both operand orders and MAD's addend.

Validation: 40,000 interpreter comparisons pass; hardware WebGPU and Linux
SwiftShader pass 2,272 vertex executions across 71 programs, comparing outputs
and temporary registers. The latter includes both colliding programs, zero-base
LIT and zero-product cases (`nv2a-zero-math-hardware.log`,
`nv2a-zero-math-linux.log`). The harness uses explicit compute layouts so valid
MOV-only programs need not access constants. CPU/cache and GPU comparisons now
run in the normal web CI workflow. Browser audio/video/controller checks and the
native Vulkan renderer suite pass. A fresh pinned checkout reproduces all 52
patched runtime files, including the native HLSL translation change.

The final retail case in `build-web-tests/vp-identity-math-retail/report.json`
renders Saints player intros, readable career overlays, staff with clipboards,
sideline equipment and stadium tiers without recorded browser/GPU exceptions.
No shader-hash collision was logged in this case. These fixes therefore do not
establish the cause or resolution of the earlier coach-shot polygons. Audio
queue drops/underruns, full original-Xbox reference parity and a sustained
30 FPS floor remain open.

## Browser audio resampling bounds

An independent audio correctness check reproduced a ring-buffer fault at an
8 kHz AudioContext rate. The producer writes 48 kHz frames, so the worklet
advances six source frames for each output frame. It previously checked only
that two frames were available for interpolation. A short producer chunk could
therefore advance the read cursor past the write cursor, wrapping unsigned
occupancy to billions of frames and allowing stale samples to play.

The worklet now waits for both interpolation samples and the complete next
source advance. Starvation preserves its position and fractional phase. The
production-worklet regression fails before the fix at 8 kHz
(`build-web-tests/audio-worklet-before.log`) and passes afterward at 8, 11.025,
16, 22.05, 24, 44.1, 48 and 96 kHz, including counter wrap and chunked refill.
Exact ramp checks cover downsampling and interpolation across render blocks.
The regular browser integration test also checks actual AudioWorklet pitch,
level and continuous playback at 8, 44.1, 48 and 96 kHz.

Windows hardware Chrome and Linux CI Chromium pass those audio checks
(`audio-resampler-hardware.log`, `audio-resampler-linux-checked.log`). The first
Linux run passed audio but failed the controller reconnect assertion. Its
gamepad test double could reuse a rounded timestamp for an immediate connect
and press; SDL ignores unchanged timestamps. Simulated updates now advance
monotonically, and failures retain reconnect state/logs. The checked Linux run
passes the full integration suite, including reconnect.

This fixes a demonstrated resampling fault. It does not establish the cause
of the retail queue drops at 48 kHz or original-Xbox audio/gameplay parity.

## Exact audio submission and playback clock diagnostics

The retail audit's `audio` action now records AudioContext time/rate/state,
latencies and worklet playback/queue/underrun/level counters. In
`build-web-tests/audio-clock-retail/report.json`, one 10.00-second wall-clock
interval advanced the context by 6.79 seconds, with zero output peaks at both
sampled boundaries. The
APU continued submitting at its normal rate and the runtime drop count grew.
After nonzero audio began, subsequent context intervals tracked wall time.
This separates playback-clock slowdown from producer starvation. Chromium's
[current renderer source](https://chromium.googlesource.com/chromium/src/+/HEAD/content/renderer/media/renderer_webaudiodevice_impl.cc)
installs a silent-sink suspender with a 30-second threshold. That is a plausible
lead for this observation, not proof of the exact browser mechanism or a
reason to dismiss the drops.

A separate production-code regression found that low-queue worklet submissions
inserted 1,024 zero frames before each real APU block. Those added ~21 ms gaps
were absent from the APU output. The worklet submission path now preserves the
exact PCM. Startup buffers two real submissions before playback; it does not
insert samples into the producer stream. The SDL fallback retains its existing
behavior. `tests/web/test_audio_submission.py` fails on the preceding path and
verifies exact startup, low-queue and short submissions after the fix, plus
full-queue rejection. Worklet tests also check that priming retains the first
samples and does not count startup buffering as an underrun.

The browser reconnect regression also needed a fresh observation boundary:
an initial disconnected-state log could satisfy its later unplug assertion.
The test clears that port's old state logs before unplugging and waits for the
new neutral state before reconnecting. Monotonic simulated timestamps alone
did not close this race. This corrects test evidence; it does not change the
game's controller implementation.

The final exact-PCM/priming build passes Windows hardware Chrome and Linux CI
Chromium integration (`audio-priming-hardware.log`, `audio-priming-linux.log`).
The retail case in `build-web-tests/audio-priming-retail/report.json` reaches
Minnesota at Pittsburgh, readable career and coin-toss overlays, sideline
equipment, players/referee and stadium tiers without recorded browser/GPU
exceptions. Its worklet reports one underrun, and runtime queue drops remain.
This does not prove original-Xbox audio parity, resolution of the earlier
coach geometry fault, or a sustained 30 FPS floor.

## Reciprocal signs, exact bounds and complete zero products

The next bit-pattern regression fails on the preceding interpreter:
`RCP(-0)` returns `7F800000` instead of `FF800000`
(`build-web-tests/vp-reciprocal-before.log`). Reciprocal signs are now preserved.
RCC uses the exact signed IEEE bounds specified in
[NVIDIA's vertex-program 1.1 specification](https://registry.khronos.org/OpenGL/extensions/NV/NV_vertex_program1_1.txt),
including the distinction between positive and negative zero.

The [base NVIDIA specification](https://registry.khronos.org/OpenGL/extensions/NV/NV_vertex_program.txt)
also applies the zero-product rule to dot, distance and lighting operations.
Those paths now share the corrected multiplication behavior. LIT uses the
exact exponent limit of 128 minus 1/256, preserves diffuse signed zero, and
returns one for a zero exponent, including a zero base. This corrects the
earlier LIT zero-exponent behavior. CPU, WGSL, GLSL and HLSL translations were
updated together.

The baseline decoder implements these rules independently. Explicit expected
values cover reciprocal signs, RCC bounds, exceptional zero products and LIT
limits. Selected GPU cases use exact comparisons, so a loose absolute tolerance
cannot accept a wrong tiny bound or zero sign. NaN payloads are not compared.
The expanded suite passes 40,000 interpreter comparisons and 2,560 vertex
executions across 80 programs on hardware WebGPU and Linux SwiftShader
(`vp-precision-cpu.log`, `vp-precision-hardware.log`, `vp-precision-linux.log`).
The native Vulkan renderer suite, actual generated GLSL-to-SPIR-V compilation,
and browser audio/video/controller integration pass. All 52 patched runtime
files reproduce from the pinned checkout.

The retail capture in `build-web-tests/vp-precision-retail/report.json` renders
Houston at Cleveland, stadium tiers/lights, sideline staff/equipment and readable
Gerard Warren/Gary Walker intro overlays without recorded browser/GPU exceptions.
Audio queue drops and five worklet underruns remain in this run. Full NV2A
comparison ordering, denormal handling and rounding conformance remain
incomplete, as do controlled original-Xbox scene matching and sustained 30 FPS.

## Ordered comparisons and portable operand negation

The next regression fails on the preceding interpreter: `SLT(-NaN, -Infinity)`
returns zero instead of one (`build-web-tests/vp-comparison-before.log`). The
[NVIDIA vertex-program specification](https://registry.khronos.org/OpenGL/extensions/NV/NV_vertex_program.txt)
orders negative NaNs below negative infinity, positive NaNs above positive
infinity, and negative zero below positive zero for SLT/SGE. CPU, WGSL, GLSL
and HLSL translations now implement that ordering. NaN payloads are collapsed
to signed classes; the tests do not assert same-class NaN self-order.

MIN/MAX use their specified operand selection, including MAX choosing the
first operand on equal values. Signed-zero tie cases check the selected bits.
GPU fixture inputs and constants cross the Playwright boundary as raw bytes,
preserving negative NaNs that numeric serialization can canonicalize.

The first Linux run then exposes an additional issue in negated operands:
case 82 differs from the CPU despite passing hardware Chrome. WGSL operand
negation now flips the sign bit explicitly, preserving zero and NaN signs
through that backend. Both hardware WebGPU and Linux SwiftShader pass all
2,752 executions across 86 programs after this correction
(`vp-comparison-final-hardware.log`, `vp-comparison-final-linux.log`).
The 40,000-case interpreter suite, vertex cache checks, native Vulkan suite,
generated GLSL-to-SPIR-V validation, game build and browser integration pass.
All 52 runtime patch files reproduce from a fresh pinned checkout.

The final retail run (`build-web-tests/vp-comparison-final-retail/report.json`)
reaches Baltimore at Oakland sideline players, field markings and the coin toss
with players/referee rendered and no recorded browser/GPU exceptions. This run
reports 201 worklet underruns; it remains a partial fidelity check. Its scenes
do not provide a controlled check of the earlier coach geometry fault.

These arithmetic checks do not establish full NV2A conformance. Denormal and
rounding behavior, original-Xbox scene/audio matching, all-mode gameplay
coverage and a sustained 30 FPS floor remain open.

## Silent audio clock drift

The final comparison capture's worklet underruns rise from 2 to 201 between
31 and 41 seconds while the sampled output remains silent. A separate
wall-clock-driven PCM producer reproduces clock drift without the game or APU:
after 30 seconds of zero PCM, Chrome's context advances about 0.65 seconds per
wall second. Both the default muted launch and an unmuted launch drop 80
1024-frame chunks before the tone restores steady consumption
(`build-web-tests/audio-silence-muted.json`, `audio-silence-unmuted.json`).

Chromium's [Web Audio device implementation](https://raw.githubusercontent.com/chromium/chromium/main/content/renderer/media/renderer_webaudiodevice_impl.cc)
uses a 30-second silent-sink timeout. Its
[destination handler](https://raw.githubusercontent.com/chromium/chromium/main/third_party/blink/renderer/modules/webaudio/realtime_audio_destination_handler.cc)
disables that transition for an interactive graph with automatically pulled
nodes. A [terminal worklet](https://raw.githubusercontent.com/chromium/chromium/main/third_party/blink/renderer/modules/webaudio/audio_worklet_handler.cc)
with no connected output belongs to that pull list. This source behavior and
the isolated timing experiment identify a browser clock problem independent
of APU computation.

The output now also feeds a terminal worklet monitor. It counts rendered frames
and has no output, leaving the speaker PCM unchanged. The same standalone
experiment keeps its clock steady and drops zero chunks with this branch.
The real Wasm bridge regression passes on hardware Chrome and Linux Chromium:
about 7.01 context seconds per 7.01 wall seconds across the silence boundary,
followed by the expected 440 Hz tone and level, with zero worklet underruns in
both runs (`audio-clock-monitor-hardware.log`, `audio-clock-monitor-linux.log`).

Both processors stop on shutdown. Deferred module loads cannot recreate output
after close or attach an old ring after replacement; bridge regressions exercise
those cases and partial-construction cleanup. Worklet startup/processor failures
now fail retail audits explicitly. These checks address a specific consumer-clock
fault and do not establish full game audio parity.

The retail capture (`build-web-tests/audio-clock-monitor-retail/report.json`)
keeps the audio clock steady through more than 60 seconds of zero output and
reports zero dropped submissions through the final runtime counter. It records
11 worklet underrun blocks, including a later burst outside the silence
transition; those stalls remain unresolved. The images show Indianapolis at
St. Louis, the stadium roof/tiers/lights, sideline players/equipment and readable
Mike Doss and Aeneas Williams overlays, without recorded browser/GPU/audio
processor failures. Different attract scenes prevent a controlled visual or
overall-underrun comparison with the preceding run.

Normal audio/resampling/controller/WebGPU integration passes on a repeat. The
first full run timed out on SDL fallback output, while an isolated fallback
probe and the repeated full sequence render the expected tone. Failure
diagnostics were added; an underlying SDL fallback fault has not been proven
or fixed. Full fidelity and sustained frame-rate guarantees remain unverified.

## Sequencer sample time and remaining producer stalls

The next profiled retail run (`build-web-tests/audio-stalls-profile/report.json`)
keeps the consumer clock steady and drops zero submissions, but records 35
worklet underrun blocks. Existing APU profiles record a 25.9 ms maximum pipeline
frame and an ISR wait as long as 307.1 ms, including the current 40 ms fallback.
These observations identify producer/interrupt-service delays beyond the former
silent-consumer-clock fault. The fallback can also submit zero PCM while the
front end remains trapped, so worklet underrun counts alone cannot prove audio
continuity. Interrupt latency and that fallback remain open fidelity work.

The counter audit finds a separate, deterministic error. `NV_PAPU_XGSCNT`
returns host nanoseconds divided by 100: at one second of host uptime, even a
reset sequencer returns 10,000,000. The real MMIO regression fails with that
value (`build-web-tests/apu-sample-counter-before.log`). NFL 2K5's generated
`sub_00443679` reads this register directly at guest address `0xFE80200C`.

[Xemu's APU implementation](https://raw.githubusercontent.com/xemu-project/xemu/master/hw/xbox/mcpx/apu/apu.c)
derives the register from 32-sample sequencer frames. The updated
[upstream xboxrecomp implementation](https://raw.githubusercontent.com/sp00nznet/xboxrecomp/main/src/apu/apu_core.c)
also corrects the former host-clock division and supports counter writes.
The local runtime now maintains a separate 32-bit sample counter, advances it
for each executed sequencer frame, and honors register writes and device reset.
Host time and monitor-only output do not advance that counter. Interlocked
operations keep its frame-thread updates and MMIO reads atomic.

The regression executes the production MMIO read/write, pipeline frame and reset
functions. It verifies 48,000 samples after 1,500 frames, independence from host
clock changes, register writes, both signed and unsigned rollover boundaries,
and device reset. The old clock test incorrectly described a scaled host clock
as XGSCNT; that assertion was removed while retaining the actual QPC conversion
and overflow tests. The sample-counter, host-clock and 10,000-write APU locking
tests pass, as do the game build and native renderer suite. All 52 runtime patch
files reproduce from the pinned checkout. This does not establish full MCPX
conformance or resolve the interrupt-service stalls.

The actual native APU library also builds (`apu-sample-counter-native-apu-build.log`),
and the counter regression passes under the native compiler with undefined-behavior
sanitization. The initial retail run ends during the St. Louis/Miami transition
with 34 worklet underrun blocks and zero dropped submissions. An extended run
(`build-web-tests/apu-sample-counter-extended/report.json`) reaches the Washington
at Oakland stadium intro and sideline players/equipment, with 12 underrun blocks,
zero dropped submissions and no recorded browser/GPU/audio processor failures.
The changing attract scenes do not support an overall-underrun comparison.

The extended run also records renderer intervals below 30 FPS, including 4 FPS.
Other native compiler processes were active during that capture. Their presence
does not establish the sole cause of the slowdown; the requested frame-rate
floor is still unmet in this environment. These captures establish progression,
not full gameplay or original-Xbox scene/audio parity.

## Interrupt preemption between translated calls

The guest lock already prioritizes the timer/interrupt worker, but checks for
preemption only at kernel calls. A translated call sequence can therefore hold
the guest CPU despite a queued interrupt. A regression using the actual guest
lock, native threading primitives and `RECOMP_INTERP_GATE` reproduces the gap:
the interrupt waits about 212 ms while translated calls continue
(`build-web-tests/irq-preemption-before.log`).

The lock now publishes an interrupt-priority waiter flag. Translated function
entries check it and invoke the existing scheduling point only while such a
worker is queued. Ordinary entries add no clock reads or guest-lock handoffs;
they still pay the flag load/check. The publisher updates the waiter count
before publishing the request. Wasm/native atomics publish and observe the
flag; the Win32/x86 path pairs its volatile load with Interlocked publication.

The regression services the queued interrupt in about 0.2 ms on Wasm/Node and
0.06 ms natively. It also checks recursive lock-depth restoration, guest TLS
register preservation, no extra lock grants for 10,000 uncontended calls, and
the mod interpreter gate. These are measured fixture results, not a latency
guarantee under arbitrary load. The full translated game rebuilds and all 54
runtime patch files reproduce from the pinned checkout.

This closes a function-boundary scheduling gap. A single translated loop with
no function or kernel call still lacks a preemption point, and an interrupt
worker already executing a long callback cannot preempt itself through this
flag. Those limitations, delayed interrupt/DPC service and full gameplay/audio
parity remain open.

The four-minute retail profile (`build-web-tests/irq-entry-profile/report.json`)
reaches Baltimore at Kansas City, the coin toss and active gameplay, with
stadium tiers/fog, players, sideline staff/equipment and readable broadcast
text. No browser/GPU/audio processor failures are recorded. The largest logged
ISR wait is 18.8 ms, with no logged 40 ms ISR fallback; different attract scenes
and the counter correction prevent a controlled comparison against the earlier
307 ms observation.

The same run still records 703 worklet underrun blocks and a maximum 184.5 ms
APU pipeline interval, despite zero dropped output submissions. Profiling can
perturb timing, and these wall-time measurements do not identify whether the
remaining spikes are computation, locking, scheduling or diagnostic overhead.
This is not evidence of resolved audio continuity or a sustained 30 FPS floor.
The function-entry change fixes the deterministic scheduling gap demonstrated
by the regression; remaining producer stalls require separate diagnosis.

## Audio stage timing and diagnostic-induced stalls

Opt-in `RECOMP_APU_LOCK_PROFILE=1` now records VP, DSP and output wall time,
plus voice-lock wait time/count, for the same worst pipeline frame in each
five-second interval. These correlated values avoid adding independent stage
maxima that might belong to different frames. Normal playback does not take
these extra timing samples.

The stage-only retail run (`build-web-tests/apu-stages-retail/report.json`)
reaches gameplay with five worklet underrun blocks, zero dropped submissions
and no recorded browser/GPU/audio processor failures. Its largest logged
pipeline frame is 6.7 ms, attributed to VP, with no voice-lock wait in that
frame. This does not support the initial hypothesis that accumulated voice
waits alone caused the previous 184.5 ms observation.

The source audit then finds expensive diagnostics under
`RECOMP_APU_VOICE_LOG`: each ADPCM voice can scan its full buffer and search
36 byte alignments while holding the APU frame lock. Those scans are a source
of measurement overhead in the previous verbose captures. A regression fails
on the old code because ordinary metadata logging reads ADPCM payload
locations (`build-web-tests/audio-diagnostics-before.log`).

Pitch/rate/format/cursor and initial-page metadata remain under
`RECOMP_APU_VOICE_LOG=1`. Full-buffer validation, alignment searches and full
scatter-gather inspection now require `RECOMP_APU_VOICE_SCAN=1`, which also
enables metadata logging. Explicit scan mode can still stall playback and is
unsuitable for real-time timing measurements. The regression verifies zero
payload scan reads with metadata logging and retained scan reads with the
explicit flag. The actual native APU builds; sample-counter and 10,000-write
frame-boundary locking tests pass. All 55 runtime patch files reproduce from
the pinned checkout.

The GP/EP code remains a DSP bypass rather than a DSP56300 program executor.
Transport continuity and tone tests therefore cannot establish original-Xbox
effects, reverb or complete audio parity. That implementation gap remains
part of the full fidelity goal.

The follow-up metadata-log capture with scan mode disabled
(`build-web-tests/audio-light-log-retail/report.json`) still records 2,256
worklet underrun blocks, zero dropped producer submissions and no recorded
browser/GPU/audio processor failures. VP intervals still spike while measured
voice-lock waits are zero. Separating the scans removes verified diagnostic
work; it does not resolve all stalls. Different attract scenes and host load
also prevent interpreting the five-versus-2,256 block counts as a controlled
performance comparison. Metadata logging remains unsuitable as proof of
normal-playback timing.

## Fractional audio pacing

The sequencer throttles every eight 32-sample frames. At 48 kHz those 256
samples take 5,333 1/3 microseconds, but the old deadline increment discarded
the fraction every batch. Its nominal clock therefore ran 62.5 ppm fast,
accumulating 225 ms of deadline error per hour. The deadline now carries the
fraction between batches and clears that phase when resynchronizing after a
long stall. Catch-up limits and voice/PCM processing are unchanged.

`tests/web/test_apu_pacing.py` executes the production throttle against a
deterministic clock. The old interval fails at batch three with a one-microsecond
deadline error; the correction produces exact aggregate deadlines across an
hour and also exercises the eight-frame divisor, bounded catch-up, resync and
timed waiting. This establishes arithmetic pacing accuracy, not a guarantee
against host scheduling jitter. Browser and actual native APU targets build,
and sample-counter, diagnostic scan isolation and 10,000-write frame-boundary
locking regressions pass.

The four-minute follow-up (`build-web-tests/audio-fractional-pacing-retail/report.json`)
reaches San Francisco at Tampa Bay, the stadium introduction, coin toss and
active gameplay. The sampled views retain stadium tiers, flags, sideline
figures, player/referee models and readable intro/scoreboard text. No
browser/GPU/audio processor failures are recorded. The final worklet count is
935 underrun blocks, with zero dropped producer submissions and a largest
logged pipeline interval of 86.3 ms. Three independent `ps2EntryRunner`
processes were consuming substantial CPU during this run. These wall-time
results are contaminated by host contention and do not establish a performance
improvement, uninterrupted audio, original-Xbox parity or a sustained 30 FPS
floor. The fractional-deadline correction is established independently by the
deterministic regression.

## Executable DSP core and DMA groundwork

The runtime now compiles the standalone DSP56300 interpreter, processor wrapper
and DMA engine from xemu revision
`a34bb0f8c229a9aabda46ac69184285112f65841`. The imported files retain their
upstream notices and GPL/LGPL license texts. Canonical core/DMA headers replace
the APU's incomplete duplicate structures; QEMU host helpers and trace hooks
are adapted for standalone Windows, Linux and Wasm builds.

The first Wasm DMA test reproduces a null-buffer read: an unsigned transfer
size compares against a signed `-1` capacity as an unsigned maximum on 32-bit
hosts, skipping allocation. Transfer storage now uses a zero-initialized
`size_t` capacity, checked growth, per-processor ownership and destruction.
Interleaved size is calculated before allocation.

`tests/web/test_dsp56300.c` uploads a real 24-bit sample-processing program
(memory moves, clear, REP, arithmetic and output saturation), verifies 1,032
signed vectors, then replaces an instruction and verifies decoded-code cache
invalidation. It also exercises bootstrap high-byte masking, frame-interrupt
acknowledgement, idle, scratch DMA, interleaved 16-bit FIFO output and circular
wrap/offset writeback. Wasm undefined-behavior checks, Linux address/undefined-
behavior sanitizers and native Windows/MSVC all pass this regression. The
actual native APU library builds with the new shared structures.
The complete browser game also links, and a fresh pinned-runtime application
reproduces all 72 patched files exactly after line-ending normalization.

This is executable processor groundwork for the missing effects path. Retail
GP/EP MMIO, scratch/FIFO wiring, reset/bootstrap transitions and frame dispatch
still use the previous bypass and need integration. These tests do not prove
all DSP instructions, complete retail audio, original-Xbox parity or a minimum
frame rate. No retail effects or performance improvement is claimed here.

## Opt-in GP/EP execution bridge

`RECOMP_APU_DSP=1` now connects the executable processors to the APU. The bridge
adapts xemu's pinned `gp_ep.c`: GP/EP X/Y/P windows, the GP mixbuffer alias,
reset/bootstrap transitions, page-scattered scratch transfers, circular FIFOs,
GP processing each VP frame and EP processing every eight frames. Transfers
use `apu_phys` so contiguous Xbox allocations resolve through the physical
window. DSP memory reads take the same frame-boundary lock handoff as writers.
Processor allocations are released after the APU thread stops, and partial
initialization failure is cleaned up.

Unused DSP execution credit now expires at idle. The old `dsp_run` retained
positive cycle credit after early idle, accumulating extra credit across
frames. Intentionally non-idling firmware hits an explicit diagnostic ceiling
instead of keeping the APU lock forever; processor state is retained and the
overrun is reported. That ceiling is not a hardware clock model or a complete
DMA timing implementation. Unsupported EP PCM packet sizes and invalid FIFO
ranges are reported, and retail audit classification treats these DSP faults
as failures.

The production bridge/MMIO regression runs uploaded firmware that doubles all
32 left/right GP samples and idles, then runs EP firmware that starts planar-
to-interleaved DMA and produces an exact 256-sample stereo PCM packet. It checks
24-bit memory windows, a two-page noncontiguous bootstrap, disabled-mode
isolation, code upload, idle credit, EP scheduling, FIFO cursor wrap, reset and
non-idling firmware reporting. Wasm undefined-behavior checks, Linux address/
undefined-behavior sanitizers, native Windows/MSVC and the actual native APU
build pass. The full browser game links.

The four-minute retail capture (`build-web-tests/gp-ep-retail/report.json`)
reaches New York at Cincinnati, its stadium introduction, coin toss and active
gameplay. It records no browser/GPU/audio processor failures or logged DSP
faults, but 16,745 worklet underrun blocks, zero dropped producer submissions
and a maximum 132.0 ms pipeline interval. This is seriously discontinuous
playback, not acceptable real-time audio.

A second capture (`build-web-tests/gp-ep-instruction-profile/report.json`)
adds instruction counts correlated with the same worst pipeline frame. It
confirms actual guest program execution: steady GP samples show approximately
8,350 instructions, with about 7,100 EP instructions on its scheduled frames.
It still records 1,796 underrun blocks in 132 seconds and a largest 26.5 ms
pipeline interval, with no logged DSP faults. Capture durations, scenes and
host load differ; these counts do not establish a performance improvement.
The path stays opt-in. Full DSP instruction/effects conformance, original-Xbox
audio matching, continuity and a sustained 30 FPS floor remain open.
Legacy bed/commentary gain controls also still need mapping to the executable
DSP's routing; this path currently outputs the guest program's PCM directly.

## DSP multiplication cost and exact replacement

A retail worker CPU capture (`build-web-tests/dsp-worker-profiles`) samples the
workers for about 40 seconds at a 1 ms interval. Wasm function IDs are decoded
with the matching `NFL2K5.js.symbols`, retained beside the profiles. Interpreter
dispatch dominates; multiply/MAC wrappers account for about 2.9 seconds of
sampled self attribution. Sampling and host scheduling affect these values;
they are not a hardware instruction timing model.

The fractional multiply helper now forms one signed 64-bit product instead
of four 12-bit partial products and carry/negation steps. Both signed 24-bit
operands, their product shifted once, and its negation fit in 64 bits,
including the most-negative operands. The same 8/24/24-bit accumulator words
are written, preserving the input to existing rounding and flag updates.

`tests/web/test_dsp_multiply.py` generates 17,000 exact Python-integer vectors
covering sign combinations, extrema, bit boundaries and randomized operands.
The compiled production helper also matches the original limb implementation
in two million additional cases. Wasm undefined-behavior checks, native Linux
address/undefined-behavior checks and native Windows/MSVC pass. Uploaded DSP
program and GP/EP bridge regressions pass, and the complete browser game links.

The optional `--benchmark` builds without sanitizer instrumentation. Five
alternating measurements of two million multiplies have median times of
20.911 ms for the original routine and 7.886 ms for the replacement, about
2.7x for this isolated workload. Instrumented timings are recorded separately
and are not used as the release performance estimate.

The follow-up retail capture (`build-web-tests/dsp-mul64-retail/report.json`)
records no browser/GPU/DSP faults, but still has 737 worklet underrun blocks
in 132 seconds. The preceding profiled capture recorded 4,445 blocks; attract
scenes, host contention and profiling effects are uncontrolled, so that change
is not a proven retail speedup. The executable DSP stays opt-in. This does not
establish uninterrupted audio, full original-Xbox fidelity or a 30 FPS floor.

## DSP mix controls and continuity without profiling

The executable DSP path now reads the same bed/commentary gain controls as
the legacy path. Bin 2 retains the existing commentary convention; the other
mixbins use bed gain. Gains are applied to GP input, leaving the raw VP mix
unchanged and retaining the guest program's routing/effects. Unity gains
preserve the guest input. Gain changes affect incoming samples; existing DSP
effect tails follow the program's decay.

Both paths now use one raw commentary RMS meter with the existing fast-attack/
slow-release smoothing. Previously the executable path returned before that
meter was updated and never consumed either gain. The firmware regression
fails on the old path when a half bed gain leaves the stereo PCM unchanged
(`build-web-tests/dsp-gain-controls-before.log`). It now checks actual control
setters/getter, clamping, independent bed/commentary gains, effect-send input,
raw VP preservation, meter attack/release and unchanged unity-gain PCM. Wasm,
native Linux address/undefined-behavior checks, native Windows/MSVC, the actual
native APU build and the complete browser game build pass.

The four-minute capture (`build-web-tests/dsp-unprofiled-gameplay/report.json`)
uses executable DSP with no voice, stage-timing or worker CPU profiling. It
reaches New York at Baltimore, the stadium introduction and active gameplay,
with readable scoreboard text and rendered player models. The runtime has
zero stage/voice log entries and no recorded browser/GPU/DSP faults, but still
records 2,122 worklet underrun blocks and zero dropped producer submissions.
A host snapshot during the capture finds three independent native runner
processes each consuming more than one CPU core. This limits conclusions about
scheduling cost; it does not erase the observed discontinuities. The DSP path
remains opt-in, and full original-Xbox matching, smooth playback and a sustained
30 FPS floor remain unfinished.

## Cached DSP execution handlers

The interpreter now caches typed execution handlers for every program word,
including parallel moves. Pure ALU, register-update and move-family selection
is resolved on cache misses. Operand reads, addressing, instruction effects,
cycle accounting, REP/DO and interrupt retirement still execute normally.
Program writes invalidate their slot before the next execution; this includes
DMA uploads and instructions that overwrite themselves. Bootstrap clears the
cache. The cache occupies the same number of pointer slots as before.

The new dispatch regression compares all core state except the private cache
against the previous dispatcher in 141,664 cold/warm cases and two 2,000-step
programs. It also checks software interrupts, changed extension words,
cross-family uploads and self-modifying MOVEM. A separate wrapper regression
checks DMA invalidation of an already executed program word. Wasm undefined-
behavior checks, native Linux address/undefined-behavior checks, Windows/MSVC,
the native APU build, GP/EP integration and the complete browser build pass.
The persisted runtime patch reproduces all 74 files from a fresh pinned tree.

Two private retail snapshots contain an 8,351-instruction GP frame and a
7,119-instruction EP frame, with their scratch/FIFO transactions and complete
before/after state. Both published and candidate release Wasm cores replay
every transaction with identical output bytes, memory, registers, DMA state
and cycle counts. Repeated replay retains only valid decoded handlers; all
comparisons remain enabled independently of NDEBUG. These snapshots contain
game data and are not published. Temporary capture instrumentation and its
filesystem export were removed before the normal browser rebuild.

Seven alternating same-process rounds of 1,000 frame replays give a GP median
of 129.684 ms before and 104.369 ms after, about 19.5% less execution time.
EP improves in every pair, but host contention makes timing noisy: paired
reductions range from roughly 12% to 42%. This measures captured-frame DSP
execution with checked I/O, not whole-game performance or hardware accuracy.

The four-minute browser capture (`dsp-cached-dispatch-gameplay/report.json`)
records no browser/GPU/DSP faults but still reports 2,632 worklet underrun
blocks. Scene and host load are uncontrolled; it establishes no retail
continuity improvement. Executable DSP remains opt-in. Original-Xbox output
matching, complete stadium/staff fidelity and a sustained 30 FPS floor remain
unfinished.

## Audio timing diagnostics and remaining stalls

The APU utilization counter now accumulates elapsed time around each actual
condition-variable wait. Previously it sampled the clock after refreshing the
loop's timestamp, usually recording zero sleep. The deterministic production-
throttle test now checks a complete 5 ms wait, repeated early wakeups,
accumulation across frames and no fictitious sleep during paused/late frames,
alongside the existing exact one-hour pacing test. Removing the new accounting
makes the 5 ms assertion fail (`apu-pacing/before.log`).

The producer diagnostic also recognizes a one-frame WebAudio queue as dry:
the worklet needs a second source frame for interpolation. Its old zero-only
check could report no underruns while the worklet repeatedly ran dry with four
queued bytes. The counter is now named `starved_submissions` to distinguish
producer arrivals from worklet underrun blocks. Tests execute the real PCM
submission function after startup and verify starvation counts of 1, 1, 2 for
queue depths of 1, 2, 0 frames, preserving the supplied samples. The worklet
remains the authoritative measure of dry render blocks at its output rate.
Wasm pacing/submission/worklet tests, native APU compilation, browser linking
and fresh 74-file runtime patch reproduction pass.

The 132-second profiled capture (`dsp-dispatch-stall-profile/report.json`)
reaches Tennessee player introductions with rendered uniforms and readable
career graphics. It reports no browser/GPU/DSP faults but ends with 778
worklet underrun blocks. Around 97–112 seconds, five-second windows process
only 6,663–6,702 APU frames against the required 7,500, with 4.4–4.8 seconds
spent processing frames. The recorded worst frame includes 29.1 ms in VP;
other windows record DSP delays, and shorter IRQ waits also occur. Host
scheduling and instrumentation remain uncontrolled. This narrows the next
investigation to frame-processing throughput and scheduling as well as IRQ
latency; it does not establish an audio-continuity fix or complete fidelity.

## Exact voice attenuation cache

The serialized voice mixer now retains the original `powf` result for each
12-bit attenuation value. Mixing, voice dumps and VP monitoring share these
gains. The muted value still returns zero directly; every other gain is
positive, allowing zero-initialized entries to be populated on first use.
The cache uses 16,380 bytes and avoids a full-table initialization burst.

The production helper regression checks all 65,536 possible input words,
including masked upper bits, in forward and reverse order. Every result has
the original float bits. It also checks exact sample/gain/headroom arithmetic
and confirms only 4,095 exponentiations across the full warmed domain. Wasm
undefined-behavior checks, native Linux address/undefined-behavior checks and
Windows/MSVC pass. The actual native APU and full browser game build, and the
persisted runtime patch reproduces all 74 files from a fresh pinned tree.

Seven alternating release-Wasm measurements of two million calls have
medians of 19.173 ms for the original helper and 9.942 ms for the cache, about
1.9x for this isolated calculation. This does not measure total mixer speed.

The 132-second retail capture (`voice-attenuation-retail/report.json`) reaches
player introductions with no recorded browser/GPU/DSP faults. It still records
5,242 worklet underrun blocks. Three independent native runner processes
started during the capture and each consumed more than one CPU core; they
were left running. Scene and scheduling differences prevent a retail timing
comparison. The corrected producer diagnostic now also reports starved
submissions at four queued bytes, confirming the former zero-only counter
missed that dry state. Uninterrupted audio, original-Xbox matching and the
sustained 30 FPS floor remain unfinished.
