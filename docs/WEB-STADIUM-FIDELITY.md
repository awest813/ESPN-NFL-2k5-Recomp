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

## PASSTHRU texture-stage bounds

The GPU shaders previously forwarded texture `PASSTHRU` coordinates directly
to the register combiners. NV2A clamps these values to 0–1 after interpolation;
this behavior is documented by the hardware-tested correction in
[xemu issue 2523](https://github.com/xemu-project/xemu/issues/2523).
Out-of-range values can change later signed combiner mappings even when the
final framebuffer color is clamped. The WebGPU/SDL shader and D3D11 shader
now clamp at the texture-stage boundary. D3D11 also honors PASSTHRU at stage
zero when no texture is enabled. The generated WGSL and HLSL artifacts are
updated; after generated identifier normalization, the WGSL change is solely
the new clamp operation.

The software rasterizer also previously ignored PASSTHRU, using a texture or
white instead of all four original coordinates. It now interpolates the raw
coordinates with perspective weights and clamps them before combiner input
mapping, without an unused texture lookup. This keeps the fallback consistent
with the GPU paths for this mode.

Hardware WebGPU reproduced the old shader result `FFFF0040` where the expected
ARGB value is `80800040`, plus an incorrect red result from negative input.
All four texture stages failed these cases before the fix. The final suite
passes 40 exact-pixel PASSTHRU cases across stages, texture-sampling flags,
signed mappings, in-range inputs, affine interpolation and unequal vertex W.
The native Vulkan suite passes 16 equivalent cases through the actual render
queue and 16 through the actual software rasterizer. The software tests
reproduced eight failures before its correction. The existing renderer scenes
and failure-recovery tests also pass.

D3D11 vertex, pixel and geometry shaders compile with the Windows shader
compiler; D3D11 pixel readback is outside this check. The full browser game
and actual native graphics runtime build successfully, and a fresh pinned
tree reproduces all 76 patched files. Local SwiftShader attempts failed to
obtain an adapter; the successful WebGPU checks used the Intel hardware
adapter, with no recorded WebGPU validation errors.

The 132-second GPU-shader retail check (`passthru-retail/report.json`) reaches
Indianapolis at Kansas City. Examined captures show players/uniforms, sideline
figures and equipment, crowd tiers and readable Mike Doss intro graphics,
with no recorded browser/GPU/DSP faults. It records 148 worklet underrun blocks
and some five-second averages below 30 FPS. This capture precedes the separate
software-fallback correction; its sampled rendering logs report no software
3D draws. An ESPN scene specifically exercising out-of-range PASSTHRU input
has not been isolated, so this is shader conformance and stability evidence,
not proof of a visible stadium correction or complete original-Xbox parity.

## Software alpha rejection before depth and stencil

The software 3D rasterizer previously updated depth and stencil before
evaluating final alpha. A discarded transparent foreground triangle could
therefore hide opaque geometry behind it; stencil-fail, depth-fail and pass
operations could also run for a fragment that alpha testing should reject.
The corrected order follows the alpha → stencil → depth sequence described
in [NVIDIA's stencil pipeline documentation](https://developer.download.nvidia.com/assets/gamedev/docs/stencil.pdf).

Alpha-tested draws now finish texture/combiner shading and reject on the final
8-bit alpha before committing depth/stencil operations. Opaque draws retain
early stencil/depth rejection. Color-masked depth/stencil-only passes still
evaluate enabled alpha testing. The 2D writer and 3D path share one alpha
comparison helper, preserving all eight compare modes and disabled-test
behavior.

The actual software-renderer regression reproduced 20 failures before the
fix (`alpha-order-before.log`), including a blue background remaining visible
because a discarded foreground triangle occluded a green rear triangle.
The final 44 cases check every alpha comparison around reference 128,
stencil-fail/depth-fail/pass writes, color masks, final alpha from textures
and combiners, disabled alpha testing and the two-triangle cutout scene.
The correct scene ends green with the rear triangle's depth. These cases
and the existing native Vulkan/renderer recovery scenes pass both normally
and with address/undefined-behavior sanitizers. Driver leak checking was
disabled for the sanitizer run; invalid memory and undefined-behavior checks
remained enabled.

The complete browser game and actual native graphics runtime build, and
the published patch reproduces all 76 files from a fresh pinned tree. This
change is exercised directly through the software rasterizer; it establishes
no retail FPS or audio improvement. Texture ALPHAKILL was still missing at
this checkpoint; the follow-up below implements it. Full original-Xbox scene
matching and uninterrupted audio remain unfinished.

## Texture alpha-kill across NV2A rendering paths

Texture CONTROL0 bit 2 now reaches all four stages and rejects zero-alpha
texture samples independently of final alpha testing. The bit and behavior
follow the primary [xemu register definitions](https://github.com/xemu-project/xemu/blob/master/hw/xbox/nv2a/nv2a_regs.h)
and [texture-stage shader implementation](https://github.com/xemu-project/xemu/blob/master/hw/xbox/nv2a/pgraph/glsl/psh.c).
GPU checks use floating sample alpha before framebuffer quantization, so a
tiny positive filtered alpha survives. XRGB opacity is applied before the
test. Untextured geometry and non-sampling modes do not trigger alpha-kill.

Flat SDL shaders use two bits of the existing flags word for opaque XRGB
alpha and alpha-kill. Three-dimensional shaders receive per-stage kill bits
in their existing uniforms. D3D11 carries bound/kill flags in the existing
texture word, which its shader-specialization cache already keys in full.
Uniform layouts remain the same size. GPU sampling finishes before discard
so later stages retain derivative evaluation. The software rasterizer defers
depth/stencil operations whenever an active texture may kill a fragment,
including color-masked passes with final alpha testing disabled.

The new checks verify 155 exact pixel outcomes: 47 on hardware WebGPU, 54 on
native Vulkan and 54 through the actual software rasterizer. They cover all
four stages, enabled/disabled kill flags, zero and nonzero source alpha,
XRGB, non-sampling modes, transparent final combiner output, color masks,
flat overlays and a killed foreground/rear geometry scene. Register-recorder
to uniform propagation is checked separately. The WebGPU fixture reproduced
the old opaque red output at all four stages where the background should
have remained untouched. Existing renderer and recovery scenes also pass.

The final native/Vulkan/software suite passes address/undefined-behavior
checks with driver leak checking disabled. The full browser game and actual
native graphics runtime build. D3D11 vertex, pixel and geometry shaders
compile with the Windows compiler; D3D11 pixel readback remains outside this
check. A fresh pinned tree reproduces all 76 patched files.

The initial 132-second retail check (`alpha-kill-retail/report.json`) reaches
Indianapolis at St. Louis. Examined captures retain player uniforms, crowd
tiers, sideline players, standing/kneeling staff and equipment, with no
recorded browser/GPU/DSP faults. It records five worklet underrun blocks and
some five-second frame averages below 30 FPS. The optional texture-state
setting emitted no register dumps, so this capture does not prove that its
scenes exercised alpha-kill. Scene and scheduling differences prevent an
audio/performance comparison with earlier runs.

The final gameplay capture (`alpha-kill-final-gameplay/report.json`) runs
246 seconds and reaches Dallas at Carolina, including active first-quarter
play through fourth-and-12 at 2:06. Examined views retain player models,
sideline staff/equipment, stadium tiers, broadcast overlays and readable
scoreboard text, with no recorded browser/GPU/DSP faults. It records 384
worklet underrun blocks. Five-second averages after 150 seconds range from
25.1 to 30.0 FPS; this disproves a sustained 30 FPS floor for the run. Full
original-Xbox matching and continuous audio remain unfinished. The shader
audit also identifies unimplemented clip-plane and bump-environment texture
stage behavior as remaining fidelity work.


## Texture shader clip-plane comparisons

The transformed 3D paths now decode `NV097_SET_SHADER_CLIP_PLANE_MODE`
(`0x17F8`) and implement texture-shader mode 5. Each stage checks all four
perspective-interpolated raw texture coordinates. A clear comparison bit
rejects a negative coordinate; a set bit rejects a nonnegative coordinate,
including either signed zero. Kept fragments provide a zero RGBA stage result.
These semantics follow the primary [xemu texture-stage implementation](https://github.com/xemu-project/xemu/blob/master/hw/xbox/nv2a/pgraph/glsl/psh.c).

SDL/WebGPU and D3D11 carry the four comparison nibbles in previously unused
uniform words, retaining their existing layouts. Clip-plane stages request no
texture. GPU rejection follows stage sampling so derivatives remain available.
The software 3D rasterizer checks the same coordinates before committing depth
or stencil operations, including when final alpha testing is disabled. D3D11
shader specialization keys include only comparison nibbles belonging to active
clip-plane stages, avoiding variants for unused comparison state.

The pre-fix hardware WebGPU fixture reproduced 384 clipping failures, and the
native fixture confirmed that the comparison register was ignored. The fixed
suite checks 576 WebGPU, 448 native Vulkan and 448 software pixel outcomes,
covering every stage/component, both comparisons, signed zero, every comparison
nibble and single-component violations. Valid bound textures and enabled
alpha-kill cannot change the non-sampling clip-plane behavior. Software checks
also verify untouched depth/stencil on rejection. A separate production-code
fixture checks all 65,536 register values, ignored upper register bits and
1,024 active/inactive shader-cache bit cases, with undefined-behavior checks.

The browser game and actual native kernel build. The native renderer suite also
passes address/undefined-behavior sanitizers with driver leak checking disabled.
All three D3D11 shader stages compile; D3D11 pixel readback remains untested.
A fresh pinned runtime tree reproduces all 77 patched files. This change covers
the transformed 3D pipeline; the simplified flat 2D texture/combiners path and
bump-environment mapping still require broader fidelity work. Component
conformance does not establish original-Xbox scene or audio parity.

The 246-second retail check (`clip-plane-gameplay/report.json`) uses Chrome
157 on the Intel hardware WebGPU adapter and reaches St. Louis at Pittsburgh.
Examined captures show Marshall Faulk's sideline intro, the coin-toss referee,
crowd tiers, banners, sideline staff/equipment and active first-quarter play
with readable broadcast text. No browser/GPU/DSP fault was recorded. The run
records 142 worklet underrun blocks; five-second frame averages after 150
seconds range from 27.4 to 30.1 FPS. It does not establish uninterrupted
audio, a sustained 30 FPS floor or that these retail scenes use clip-plane
texture stages. Original-Xbox scene matching remains unfinished.


## Bump-environment texture stages

Texture-shader modes 6 and 7 previously performed plain texture lookups.
The transformed 3D SDL/WebGPU, D3D11 and software paths now displace two-
dimensional lookups using the selected earlier stage's signed blue/green
channels and the current stage's 2x2 bump matrix. Mode 7 additionally scales
all four sampled channels by source red times luminance scale plus offset.
Bump lookups use raw interpolated XY without division by Q, and respect the
texture's normalized or texel coordinate convention.

The channel conversion and stage behavior follow the primary
[xemu texture-stage implementation](https://github.com/xemu-project/xemu/blob/master/hw/xbox/nv2a/pgraph/glsl/psh.c).
Matrix method words 2/3 require a swap when packing column-major uniforms,
following [xemu's register mapping](https://github.com/xemu-project/xemu/blob/master/hw/xbox/nv2a/pgraph/pgraph.c).
The runtime reads recorded bump coefficients for stages 1..3. The SDL uniform
block grows from 400 to 496 bytes, within the existing 512-byte queue storage;
the adjacent-draw guard regression verifies that complete uniforms survive
queue insertion without overwriting their neighbors. D3D11 bump values remain
runtime uniforms, allowing one shader variant to handle changing coefficients.

The correctly bound baseline WebGPU scene reproduced 96 failures before the
implementation. The final expanded checks pass 207 pixel outcomes each on
hardware WebGPU, native Vulkan and the actual software rasterizer (621 total).
They check every valid earlier-stage selection, every matrix word, positive
and negative displacement, normalized/texel textures, nonunit Q, both modes,
and luminance scaling of RGB and alpha. Zero, negative, tiny positive, half
and excessive luminance gains check clamping and alpha-kill behavior. Zero
sample alpha rejects; a tiny positive alpha survives even when quantization
produces zero. Software cases also verify depth/stencil writes or rejection.
Native tests use the production register recorder, uniform packer, draw queue
and rasterizer. The existing texture decoding/sampler and clip-state tests pass.

The final renderer suite passes address/undefined-behavior sanitizers with
driver leak checking disabled. The complete browser game and actual native
kernel build; Windows vertex/pixel/geometry shaders compile. A fresh pinned
runtime reproduces all 77 patched files. D3D11 pixel readback, volume textures,
the simplified flat 2D texture/combiners path, and original-Xbox scene matching
remain outside this check. Signed displacement is reconstructed from the
existing unsigned decoded/filter results; exact signed-format filtering still
requires hardware-reference validation. No retail FPS or audio improvement is
inferred from these component tests.

The final 246-second retail check (`bump-environment-gameplay/report.json`)
uses Chrome 157 on the Intel hardware WebGPU adapter and reaches New England
at the New York Giants. Examined views include readable Troy Brown intro
text, sideline staff/equipment, the coin-toss referee, player uniforms,
stadium tiers and active first-quarter play. No browser/GPU/DSP fault was
recorded. The run records 354 worklet underrun blocks; five-second frame averages
after 150 seconds range from 24.7 to 30.1 FPS. These scenes do not prove retail
use of bump stages, uninterrupted audio or a sustained 30 FPS floor.
Original-Xbox scene/audio matching remains unfinished. Existing local xemu
Arizona/New Orleans gameplay stills provide a reference for a future matched
scene comparison; this run uses different teams and camera sequences.


## Retail texture-stage tracing and software reflections

`RECOMP_SDLGPU_STAGE_STATS=1` now records per-stage mode counts for accepted
3D GPU batches in each existing five-second statistics interval. It also
counts bound stages using alpha-kill, color keying, volume textures and cube
maps. It is disabled by default and adds no per-stage counting or register
reads while disabled. Counts describe guest batches accepted by the GPU path,
not pixels, post-merge draw calls, or proof of pixel correctness.

The 250-second `texture-stage-retail-trace/report.json` run reaches New York
Jets at Denver in snow/fog. Forty-three complete statistics intervals record
2,055,587 accepted batches. The counts for each stage sum independently to
the interval's batch count. Observed stage programs are NONE, PROJECT2D,
CUBEMAP, DOTPRODUCT, DOT_RFLCT_DIFF and DOT_RFLCT_SPEC. Stage 1 records 200,171
cube-map batches, while stages 2/3 record 59,911 diffuse and 119,822 specular
reflection batches. No counted bound stage uses alpha-kill, color keying or
volume textures, and no bump or clip-plane program appears in these intervals.
This evidence prioritizes reflection fidelity; it does not prove that unused
features never appear in other teams, weather, modes or views.

The trace retains crowd tiers, staff, players, snowy field and live play with
no recorded browser/GPU/DSP fault. Host CPU usage reached 100%, with unrelated
work active; no user processes were stopped. Its 17,399 worklet underrun blocks
and delayed startup do not establish an uncontended performance comparison.
Audio continuity and a sustained 30 FPS floor remain unfinished.

The trace also exposes a software fallback gap: cube and reflection modes
were still plain 2D lookups there. The software 3D rasterizer now samples the
six independently aligned cube faces with the correct major-axis orientation,
and implements dot-only stages plus diffuse/specular reflection directions.
Each dot stage uses its selected earlier stage and signed mapping. Specular
eye components come from the interpolated W values of stages 1..3. Direction
sampling also supports the existing GPU renderer's 2D remapping when a stage
has no cube texture. The stage semantics follow the primary
[xemu texture-stage implementation](https://github.com/xemu-project/xemu/blob/master/hw/xbox/nv2a/pgraph/glsl/psh.c).

Cube sampling moves and restores both the guest texture address and the POSIX
snapshot window, retaining palette data and checking the face offset before
access. Alpha-kill runs on the selected face before depth/stencil writes.
Ordinary 2D stages skip the additional direction-coordinate interpolation.
The remaining software texture stages, filtering and full original-Xbox
scene/audio parity still require broader conformance work.

A controlled baseline with explicit point filtering reproduces 232 incorrect
software results out of 240 direction/reflection scenes; the same scenes have
zero native Vulkan mismatches. The final expanded fixture checks 384 outcomes
each on Vulkan and software (768 total), covering all six face orientations,
four quadrants per face, every cube stage, 2D direction remapping, alpha-kill,
diffuse/specular eye/normal axes and all four currently supported dot mappings.
Software cases also check depth/stencil preservation on rejection. These scenes
and existing renderer checks pass address/undefined-behavior sanitizers with
driver leak checking disabled. The complete browser game and actual native
kernel build, and a fresh pinned tree reproduces all 77 patched files.

The forced-software browser check (`software-direction-retail/report.json`)
runs 246 seconds with `RECOMP_SDLGPU_NO3D=1`, executable DSP audio and combiner
tracing. It shows Houston crowd models/clothing, an enclosed stadium roof,
field, sideline figures and Miami/Houston intro graphics. Logs report zero GPU
3D batches and thousands of software batches per interval. It records no
browser/GPU/DSP fault and zero worklet underrun blocks in this run, but reaches
only the stadium intro. Five-second frame averages after 90 seconds are
0.7–1.1 FPS. This is an integrated fallback stability check, not a playable
software-performance result or proof of original-Xbox graphics/audio parity.
Software filtering, presentation/widescreen behavior and complete texture-
stage conformance remain unfinished. The final polish skips reflection-helper
calls on unrelated modes and rejects an unrepresentable cube-face stride.


## Consistent software presentation and no-device frame pacing

The framebuffer's SDL software presenter previously stretched the entire
scanout into its output. It ignored the video crop, widescreen, aspect and
presentation-filter selection, producing a different picture shape from the
GPU presenter. Both paths, plus the alternate SDL GPU scanout uploader, now
use one shared presentation-layout implementation. The kernel publishes
crop/wide/aspect/filter choices in one atomic word for the framebuffer thread;
the fallback publishes its computed display aspect back for camera widening.
Unconfigured generic framebuffer clients retain their previous behavior.

The actual SDL software renderer reproduces four crop/aspect failures before
the fix. Its final pixel checks verify black bars for a 16:9 picture in a
1280x900 output, removal of horizontal/vertical overscan, 4:3 pillarboxing
without vertical source cropping, stretch after cropping, display-aspect
feedback and linear-filter selection. These checks include the real
`fb_present.c` implementation, rather than a duplicate presentation formula.
The existing shared-layout test retains its 10,000 viewport bounds cases.

Camera updates and browser frame pacing now run even when no SDL GPU device
exists. The no-device camera check follows framebuffer aspect and current
guest dimensions, rather than stale GPU presentation dimensions. A real
flip-dispatch fixture checks 120 variable-work frames at the selected 30 Hz
limit without a GPU; existing lock handoff, slow-frame recovery, uncapped and
cap-toggle checks pass. This preserves the cap; it cannot make an expensive
software frame finish within 33.3 milliseconds.

The 245-second `software-shared-layout/report.json` browser run displays
Seattle crowd models/clothing and stadium intro views with the corrected
letterboxing in the 1280x900 viewport. It records no browser/GPU/DSP fault and
11 worklet underrun blocks. Five-second averages after 90 seconds are
0.7–1.3 FPS, and this slow run does not establish live-game performance,
full software texture filtering or original-Xbox scene/audio parity.

The preceding commit's web CI failed at its fixed 120-second suite deadline
while still reporting passing cube-mip samples. Its maximum interval between
logged checks was 1.46 seconds, with no pixel/validation failure. The expanded
SwiftShader suite now has a five-minute total bound and a 30-second progress-
inactivity bound, measured with a monotonic clock. State reads also have
bounded waits so a frozen renderer cannot bypass either deadline. Deterministic tests verify
completion beyond the old deadline, failure on a stalled/missing startup,
and failure at the total bound despite continuing output. Terminal failures
remain available to the runner's existing failure checks. Hardware WebGPU
checks pass with the new wait policy. Publication CI remains an additional
gate for this change. Both Build and GitHub Pages subsequently passed at
`a186465`.

## Preserve authored texture mip chains

The SDL GPU renderer previously uploaded only the base texture image and
generated replacement lower levels. It now snapshots, hashes, decodes and
uploads the guest's supplied chain, preserving its declared level count
through the queue and cache. Each cube face keeps its independently aligned
chain; decoded uploads group faces within each level. Linear images retain
one level. Level counts stop at the natural 1x1 tail. The layout follows
[xemu's texture sizing](https://github.com/xemu-project/xemu/blob/master/hw/xbox/nv2a/pgraph/texture.c)
and [per-level texture upload](https://github.com/xemu-project/xemu/blob/master/hw/xbox/nv2a/pgraph/gl/texture.c).

Changing only a lower level now invalidates the texture cache. Failed queue
submission invalidates the pending upload so a retry receives the new data.
Queue sizing includes every level and face, checks representable byte counts
before copying, and rejects levels beyond a 1x1 tail. Border-filter coverage
uses the authored last level for partial chains rather than the last level
of an assumed full chain. Guest LOD clamps/bias remain a separate gap.

The initial fixture reproduced 1,681 incorrect mip readbacks and a missed
lower-level cache invalidation. The expanded fixture passes 2,545 full-level
GPU readbacks across 240 texture configurations, including a cache-change
readback after an injected submit failure. It covers all four stages, 2D
and six-face cube textures, 4x4/8x8 chains, 8x2 rectangular chains, palette
textures, DXT1/3/5 and the currently decoded uncompressed formats. Each face
and level has an independently encoded expected color. Vulkan checks also
pass address/undefined-behavior sanitizers with driver leak checks disabled.

Hardware WebGPU pixel checks pass with no validation errors, including two
partial-chain border/minification cases. Standalone checks pass 600 linear
ARGB/XRGB images, 900 randomized DXT images, complete queued mip payloads,
invalid metadata rejection, frame pacing and 10,000 viewport bounds cases.
The actual native kernel and browser game build. A fresh pinned runtime
reproduces all 79 patched files.

The 248-second `authored-mips-retail/report.json` run reaches Cleveland at
Tampa Bay live play, retaining crowd, sideline figures, player clothing and
intro/HUD text. Stage tracing confirms multi-level textures on stages 0..2,
including cube maps. No browser/GPU/DSP fault is recorded. Five-second frame
averages after 150 seconds range from 25.3 to 30.1 FPS, and the run records
135 worklet underrun blocks. This remains a partial retail stability check;
it does not satisfy the requested 30 FPS floor or audio continuity.

This change covers SDL GPU/WebGPU texture uploads. CPU software sampling,
the native D3D11 upload path, remaining formats/volume textures and complete
Xbox LOD behavior still need fidelity work. These component checks do not
establish original-Xbox scene/audio parity or a sustained 30 FPS floor.
Build and GitHub Pages both passed for this change at `e152e4b`.

## Signed texture LOD bias and sampler lifetime

The SDL GPU path ignored the low 13 bits of each texture FILTER register.
These bits encode a signed 5.8 mip-level bias, as described by
[xemu's conversion helper](https://github.com/xemu-project/xemu/blob/master/hw/xbox/nv2a/pgraph/texture.h).
The renderer now passes all four stage biases to the fragment shader and
applies them to both 2D and cube sampling. Shader-side bias works on Vulkan
and WebGPU without separate sampler-cache entries. Border coverage follows
the same biased mip level and minification/magnification decision.

The extra vector brings the 3D uniform block to 512 bytes. The queue's
existing compile-time bound and adjacent-draw canary fixture verify that
the complete block fits without overwriting neighboring draws. The first
72-case GPU fixture reproduced 32 wrong mip selections before the fix.
The final fixture checks 176 exact pixels on each of Vulkan and hardware
WebGPU: all four stages, 2D/cube sampling, two starting LODs, signed extrema,
fractional nearest-level selection and fractional trilinear blending.
The browser suite also checks two biased-border results. Standalone checks
cover all 8,192 bias encodings on each stage. Vulkan checks pass address and
undefined-behavior sanitizers with driver leak checking disabled.

The new browser fixture also exposed an unimplemented sampler-release API:
the call fell through to native SDL with a WebGPU wrapper and aborted with
an invalid function-table index. The adapter now owns that API, retains
samplers in recorded commands and releases them on replay/cancellation.
Final destruction runs on the GPU server, invalidating cached material
bindings before freeing the sampler. This follows
[SDL's deferred-release contract](https://wiki.libsdl.org/SDL3/SDL_ReleaseGPUSampler).
Browser checks cover both 2D and cube draws released before submission,
fresh LOD0 samplers after release, and released samplers in cancelled draws.
The complete WebGPU suite reports no validation errors.

Native kernel and browser game builds pass, and a fresh pinned tree
reproduces all 79 patched files. Guest LOD clamps, software filtering and
the native D3D11 texture path remain separate fidelity gaps.

The 246-second `lod-bias-retail/report.json` run reaches Jacksonville at
Indianapolis live play, including a scoring sequence, stadium roof/crowd,
sideline staff and kickoff views. Negative bias appears in 2,943,009 /
429,332 / 482,084 / 234,762 sampled-stage batches for stages 0..3; no
positive-bias batch appears in these intervals. This confirms use by the
retail title, including its cube/reflection stages. No browser/GPU/DSP
fault is recorded. Five-second frame averages after 150 seconds range from
24.4 to 30.0 FPS, with 237 worklet underrun blocks. Different scenes and
host contention prevent a performance comparison with the preceding run.
The audit remains partial: full Xbox parity, all modes/stadiums, continuous
audio and the 30 FPS floor are not established.

## Fixed-point mip clamps and independent LOD0 filtering

SDL GPU samplers now honor CONTROL0 minimum/maximum LOD as unsigned 4.8
fixed point, including fractional limits. The units follow the primary
[Envytools hardware reference, pages 277–278](https://envytools.readthedocs.io/_/downloads/en/latest/pdf/#page=281).
The current xemu sampler extracts these fields as integer levels; that
interpretation was rejected after the hardware-reference cross-check.
Limits are bounded by the authored chain and an inverted range is normalized
to its effective maximum. Direct Xbox confirmation of unusual/inverted
inputs remains open.

Clamps affect sampling, not physical storage: snapshots, hashes, uploads and
cube face strides retain the complete authored chain. Border coverage uses
the same fractional range. The fields fit unused high bits of the existing
texture uniforms; dot-mapping/input-stage reads mask their independent low
bits. The complete uniform block remains 512 bytes.

Unrestricted and LOD0 samplers retain the existing direct cache. Restricted
fractional ranges use a bounded 64-entry cache with canonical keys. Entries
already assembled for other stages in the current draw stay pinned. Before
evicting another entry, the queue flushes so recorded backend commands retain
its sampler. This avoids an unbounded table over all 12-bit range pairs.
Standalone checks cover 5,850 fractional range/filter combinations, authored
tails, inverted/oversized bounds, cross-stage reuse, eviction beyond capacity,
queued-handle flushes, stage pinning and recoverable allocation failure.

Correctly encoded pixel fixtures against the unchanged `1eb711e` runtime
reproduce 128 incorrect clamp results and 16 LOD0 filter failures. The final
160 clamp cases cover all four stages, 2D/cube textures, forced min/max,
fractional trilinear limits and oversized/inverted ranges. Every native clamp
case also checks that the GPU texture object remains unchanged.

The patterned filter cases expose why sampler max LOD cannot simply be zero:
that forces the magnification filter even on minified images. LOD0 now uses a
positive max below 0.5 and nearest-mip selection, retaining the separate
min/mag choices while always selecting the base image. The 32 patterned
checks cover normalized and linear/rect coordinates at every stage. Four
browser border checks cover maximum LOD0, forced positive minimum,
independent minification filtering and fractional trilinear coverage. The
[Vulkan sampling rules](https://github.com/KhronosGroup/Vulkan-Docs/blob/main/chapters/textures.adoc)
describe the clamped-LOD filter decision.
Additional diffuse/specular reflection pixels check that packed clamp
metadata cannot change the dot mapping or selected input stage.


All of these checks pass on Vulkan and hardware WebGPU. The native suite also
passes address/undefined-behavior sanitizers with driver leak checks disabled.
The actual native kernel and browser game build, and a fresh pinned runtime
reproduces all 79 patched files. Full CPU software filtering, the native
D3D11 texture path and original-Xbox scene/audio parity remain unfinished.

Publication at `1eb711e` passed Windows/Linux builds and Pages, but the web
suite hit its five-minute total deadline while SwiftShader continued passing
CLIPPLANE cases roughly every half second. No pixel or GPU validation failure
appears before the timeout. The 3D fixture now scissors shading to each
assertion's neighbourhood, retaining the full viewport, geometry and 2x2
derivative quad. PASSTHRU keeps its additional x=95/159 interpolation probes.
All 1,374 preceding hardware checks remain; an explicit nonzero source also
strengthens the independent texture-lifetime fixture. The five-minute total
and 30-second inactivity watchdogs are unchanged. The final suite passes
Linux Chromium 147 SwiftShader with the CI adapter flags in 11.46 seconds,
with no WebGPU validation error. This verifies the fixture optimization;
publication `574ce34` subsequently passed both Build and Pages workflows.
The final 246-second `lod-fraction-retail/report.json` run reaches Philadelphia
at Miami live play with players, crowd, sideline staff, field, intro statistics
and HUD text visible. No browser/GPU/DSP fault is recorded. No restricted mip
range appears in these sampled-stage intervals, so the run verifies integrated
stability and ordinary filtering rather than retail clamp usage. Five-second
frame averages after 150 seconds range from 24.1 to 30.1 FPS, with 168 worklet
underrun blocks. Full graphics/audio/gameplay parity and a sustained 30 FPS
floor remain unproven.

### Guest flag inheritance through executable paths

A retail diagnostic at `0010D025` exposed a wrong branch in `sub_0010CFB0`.
The original instructions compare ECX with 1, load a new ECX value, then JNE
using the preceding comparison. Decoded jump-table bytes after a terminating
path contributed a dead predecessor to flag inference. That poisoned the
join and generated a fallback with zero flags, preventing the branch.

The translator now computes executable reachability from function entry,
including recovered switch targets and exact instruction fallthrough edges.
Only unreachable predecessors of reachable blocks are excluded from flag
inheritance. Decoded blocks remain available for emission; real conflicting
paths and loop back edges retain conservative inference. A reachable unresolved
indirect jump disables this pruning. An unresolved jump in dead table bytes
does not prevent a proof on the executable path.

Regenerating the function from the user's original XBE changes exactly the
live JNE to consume its comparison operands. The separate overlapping tail
function still contains an unreachable fallback; this is not a claim that
every literal occurrence of the address has been removed. The corrected path
selects different event words; the semantic role of those events remains
unconfirmed. The XBE is a local ignored test input and is not published.

The browser regression compiles the actual generated retail block and checks
20,081 cases against the original instruction semantics: both branch choices,
the overwritten register, selected event, tail argument, call count and stack
balance. It fails on the old generated branch. Translator integration tests
also cover dead predecessors, genuinely conflicting paths and recovered
switches; dependency-free graph checks cover unknown jumps, loops and gaps.
The full local recompiler suite passes 263 tests and 93 subtests. Three stale
fixtures also failed on the untouched pinned runtime: two standalone C
harnesses lacked the interpreter-gate stub and one FRNDINT assertion expected
the obsolete host rounding expression. These fixtures now match the existing
runtime contract without changing product rounding behavior.

The actual browser game builds, existing gameplay flag-join checks pass, and
a fresh pinned runtime reproduces all 85 patched files. Translator changes
are carried in `config/xboxrecomp-web.patch`; apply that patch to a fresh
submodule before running `tools/analyze.ps1` for regeneration, as the web
build does automatically. The older local patch/revision files do not carry
these changes.

The final 246-second `flag-cfg-retail/report.json` run reaches Pittsburgh at
the Jets live play, with player models, field and HUD text visible. It records
no browser/GPU/DSP fault. Five-second averages after 150 seconds range from
28.8 to 30.2 FPS, with 59 audio worklet underrun blocks. Different teams and
scenes prevent attributing this range to the branch fix. Absence of a flag
diagnostic in this run does not prove that particular branch executed; the
compiled component regression supplies the positive branch evidence. Full
Xbox fidelity, continuous audio and a sustained 30 FPS floor remain open.

### Filtering in pre-transformed HUD/text draws

The pre-transformed SDL GPU fragment shader previously used `texelFetch`
at level zero, bypassing the guest sampler. Unlike the 3D path, these draws
therefore ignored linear filtering, authored mip selection, mirror addressing
and border colours; negative repeat coordinates were clamped before wrapping.
This affected the rendering path used by menus, HUD elements and text.

These draws now sample through the configured GPU sampler with signed LOD
bias, independent min/mag filtering and the authored mip chain. The existing
fractional sampler clamps also apply. Software border coverage follows the
same filter, mip and LOD choices as the 3D shader. Point-filter boundary
correction remains, without shifting bilinear weights. Integer colour
modulation and the final alpha comparison remain after texture sampling.
Texture alpha-kill now tests the floating sample before 8-bit rounding, so
a positive filtered alpha below half an 8-bit step is not discarded.

Native executor and browser shader checks cover 128 patterned pixel cases:
repeat, mirror, edge clamp and coloured border; negative/interior/outside
coordinates; magnification/minification with opposite min/mag settings.
Five more cases check authored mip selection with negative/positive bias.
Two alpha-kill cases distinguish an exact zero from a positive sub-byte alpha.
They create the fractional value through shader border coverage, avoiding
an assumption that every backend retains sub-byte UNORM filter precision.
An independent texel-domain reference supplies the expected patterned pixels.
A controlled comparison with the previously published shader fails 60 of the
128 filter/address cases and three of the five mip cases. The fixed shader
passes, while the existing point-reference scenes remain checked with
explicit point sampler settings. Their negative-repeat reference now wraps
instead of preserving the old software-only clamp behavior.

This change does not implement full register combiners or interpolated vertex
colour in pre-transformed draws. The CPU fallback still uses its simplified
point sampler. Component checks do not establish original-Xbox scene parity.

The corrected shader passes native Vulkan, address/undefined-behavior
sanitizers (driver leak checks disabled), hardware WebGPU and the browser
game build. A fresh pinned runtime reproduces all 86 patched files. The
preceding guest-flag publication `b5c4e99` also passed Build and Pages CI.
The final 246-second `flat-filter-final-retail/report.json` run reaches intro
and live play with stadium crowd, player clothing, field markings and HUD
text visible, without a recorded browser/GPU/DSP fault. Five-second averages
after 150 seconds range from 25.2 to 30.0 FPS, with 170 audio worklet underrun
blocks. This does not establish a performance improvement or a 30 FPS floor;
different scenes and competing host load prevent a controlled comparison.
The preceding `flat-filter-retail` run used the intermediate alpha-kill shader
and overlapped compilation, so it is not final-code or performance evidence.
Full stadium/staff-model fidelity, continuous audio and original-Xbox parity
remain open.

### Smooth colour in pre-transformed draws

The preceding retail trace records `SET_SHADE_MODE` (`037C`) with `1D01`
(smooth) as unhandled. Pre-transformed SDL draws also replicated one packed
colour across each triangle and declared the varying flat, losing colour and
alpha gradients. The software path likewise used one colour per triangle.
The audit follows the distinction exercised by the primary
[nxdk Xbox shade-model tests](https://github.com/abaire/nxdk_pgraph_tests/blob/main/src/tests/shade_model_tests.cpp);
those tests are a reference for the feature, not a matched-scene Xbox result
for this game.

The runtime now records the guest's shade mode. Pre-transformed smooth draws
retain floating per-vertex RGBA through collection and interpolate in screen
space before saturation, eight-bit modulation and final alpha testing. The
software rasterizer applies the same interpolation order. Flat draws retain
their constant packed colour. Initial state remains flat until the guest
programs another mode; the title explicitly selects smooth during startup.

Disabled colour arrays now retain the inline attribute value already returned
by the attribute fetcher. The packed-colour helper also bounds each component
before float-to-integer conversion, avoiding invalid conversions on negative,
oversized or non-finite inputs. Smooth vertex inputs are not prematurely
clamped: an out-of-range endpoint can still contribute a valid interior value.

Native checks compare 144 GPU pixels and 144 software pixels with an analytic
triangle reference. They cover RGBA gradients, saturation after interpolation,
inline colours, flat/smooth transitions, textured modulation and final alpha
testing. Browser fixtures independently check 72 smooth pixels through the
translated WGSL. The published flat shaders fail 33 of the native gradient
checks; the corrected shader passes. Existing point/filtering, alpha-kill and
3D renderer checks remain in the suites.

Primitive-specific provoking-vertex selection, flat shading in the 3D path,
full combiners in pre-transformed draws and non-unit-W fidelity remain open.
This change does not establish those features or original-Xbox scene parity.

The final native suite and address/undefined-behavior sanitizer run pass,
with driver leak checks disabled. Hardware WebGPU and Linux SwiftShader pass
the new smooth-colour checks and preceding rendering cases without a WebGPU
validation error. The actual browser game builds, and a fresh pinned runtime
reproduces all 88 patched files. The preceding HUD-filtering publication
`d6d3a8e` passed both Build and Pages workflows.
The final 246-second `gouraud-retail/report.json` run reaches Seattle at
Houston live play. Intro player clothing, stadium crowd, sideline staff,
field and HUD text remain visible, with no recorded browser/GPU/DSP fault.
Five-second averages after 150 seconds range from 26.4 to 30.1 FPS; the audio
worklet records 190 underrun blocks. Different scenes prevent a controlled
performance comparison. The component tests establish the smooth-colour fix;
this run establishes integrated stability, not a sustained 30 FPS floor,
continuous audio or complete stadium/staff fidelity.

### Flat colours and original provoking vertices

Flat selection now follows the pinned Xbox 1.0
[shade-model captures](https://github.com/abaire/nxdk_pgraph_tests_golden_results/tree/a822689507cce8e8de54d9e170c9369c1a0c7566/results/Shade_model)
and their [test geometry](https://github.com/abaire/nxdk_pgraph_tests/blob/2cfe6073d59ab2a69f98cf4c6ca003c1a02c8c6d/src/tests/shade_model_tests.cpp).
`SET_PROVOKING_VERTEX` (`09FC`) is handled and masks its one-bit setting.
Positions below refer to the original index stream, before winding changes.

| Primitive | First setting | Last setting |
| --- | --- | --- |
| Triangles | group start | group start + 2 |
| Triangle strip | triangle start | triangle start + 2 |
| Triangle fan | first rim vertex | next rim vertex |
| Quads | quad start + 3 | quad start + 3 |
| Quad strip | pair start + 3 | pair start + 3 |
| Polygon | polygon vertex 0 | polygon vertex 0 |

Both triangles of a split quad retain its original selected vertex, including
when that vertex is absent from one host triangle. Pre-transformed GPU and
software draws now fetch its floating RGBA directly; the former packed-colour
helper is no longer needed. This avoids premature truncation. Smooth draws
retain independent vertex colours.

For vertex-program draws, diffuse and specular outputs are copied into local
triangle vertices before clipping. Original cached vertices, position,
texture coordinates and fog stay independent. The near/eye-plane checks
confirm that the selected colour survives even when its original vertex is
clipped away. SDL GPU and software share this preparation. Native D3D11
assembly also duplicates the selected diffuse/specular outputs before the
host GPU clips the triangle.

Flat draws currently use CPU vertex processing, including on the SDL GPU
and native D3D11 paths. Shared indexed GPU VP outputs cannot hold different
flat colours for different primitives using the same vertex. Smooth draws
retain GPU vertex processing. A native GPU flat-output implementation and
its performance cost remain work; the fallback is an accuracy decision,
not a claim that flat-draw performance is solved. Points/lines and two-sided
colour handling are outside these triangle-based checks.

The [reference manifest](references/nv2a-flat-shading.json) pins all 12 image
hashes, the source revision, palette interpretation, projected geometry and
208 interior RGB probes. The PNG files remain local ignored inputs. Recheck
them with `python tools/audit-flat-shade-reference.py <capture-directory>`
(Pillow required); `--write-header` regenerates the runtime fixture header.
These are projected-geometry replays, not execution of the original Xbox test
vertex program or a matched retail scene.
They establish flat colour selection at those probes, not quad depth/texture
interpolation or complete vertex-program arithmetic.

Native rendering compares all 208 probes through both 2D and 3D paths, on
GPU and software: 832 pixel comparisons. Hardware WebGPU and SwiftShader
each compare 416 shader-pipeline pixels against the same captures. A separate
24-state native assembly matrix checks the original selected index, raw
diffuse/specular outputs, smooth preservation and unchanged texture
coordinates. Additional pixel and clipping checks cover non-unit W and
clipped-away selected vertices.

The Wasm regression compiles the actual primitive selector, 2D assembler
and D3D11 triangle macro, checking 23,296 index/vertex cases with shuffled
indices, both modes/settings and capacity guards. The previously published
D3D11 macro fails its new flat-colour check. Native Vulkan, address/undefined
sanitizers (driver leak checks disabled), native kernel/video builds and the
actual browser game build pass. The existing VP-cache regression also passes.
A fresh pinned runtime reproduces all 89 patched files. Native D3D11 driver
rendering still needs direct validation. Windows CI currently compiles the
pinned native variant, so it does not validate the full web-patched Windows
runtime; the D3D11 logic above is checked through the Wasm macro fixture.
Publication `fe38b5e` passed both Build and Pages workflows.
The final 246-second `flat-shade-retail/report.json` run reaches Dallas at
Tampa Bay live play, with player uniforms, field markings and stadium scenes
visible and no recorded browser/GPU/DSP fault. Five-second averages after
150 seconds range from 26.0 to 30.1 FPS, with 200 audio worklet underrun
blocks. The sampled logs do not identify which retail draws used the flat
CPU VP fallback; the replay fixtures provide the positive flat-path evidence.
Different teams/scenes prevent a controlled performance comparison. Full
stadium/staff fidelity, continuous audio and a sustained 30 FPS floor remain
unfinished.

### Pause checkpoint: line primitives (2026-11-17)

SDL rendering now accepts NV line lists, strips and loops in pre-transformed
and vertex-program draws. Previously these batches produced no geometry.
Strips and loops expand to independent line-list edges, including the closing
edge of a two-vertex loop. Smooth GPU vertex programs retain GPU processing;
flat draws select the original first/last endpoint's diffuse and specular
outputs before CPU clipping. Triangle face culling does not reject lines.
The software fallback expands one-pixel lines into narrow quads.

The WebGPU adapter now respects the SDL pipeline primitive type instead of
always creating a triangle-list pipeline. Triangle strips, line lists/strips
and points have pixel checks; indexed strip restart uses the adapter's existing
32-bit index support. This does not add NV point assembly or 16-bit indices.
Native D3D11 line assembly also preserves flat endpoint colours.

Validation at this checkpoint:

- Hardware WebGPU and independent SwiftShader suites pass, including line
  connectivity, perspective colour interpolation, alpha rejection followed by
  a rear line (no erroneous depth occlusion), and invalid topology rejection.
- Native Vulkan checks pass for 2D/3D GPU and software lines, smooth/flat
  colours, non-unit W, culling independence and a ready GPU vertex program.
  Address/undefined sanitizers pass with driver leak detection disabled.
  Where the optional glslang C library is absent, the fixture compiles the
  actual generated vertex shader through the already-required CLI compiler.
- The Wasm regression compiles production line assembly, clipping and D3D11
  colour selection: 228,149 checks cover shuffled indices, short/odd batches,
  closure, capacity guards, clipped-away flat endpoints, varying texture/fog
  values, eye/near planes and rejection of nonfinite positions. Existing
  flat-shading and VP-cache regressions also pass.
- The actual browser game and Linux kernel/video build. A fresh pinned
  runtime reproduces all 89 patched files. No new retail gameplay run was
  performed for this checkpoint; it establishes component behavior and build
  stability, not observed changes in a particular stadium or play-art scene.

Remaining work is deliberately recorded for resumption. Exact Xbox line
coverage, endpoint rules, widths and smoothing have not been established;
the software quad fallback is approximate. The local ignored
`build-web-tests/line-hardware` directory contains a pinned Xbox Line_width
capture and source for a future comparison, but no comparison result is
claimed. The prior flat-shading capture tests do not establish line fidelity.

A separate position discrepancy was identified but left unchanged: native
GLSL GPU VP output and D3D11 truncate screen XY to a 1/16-pixel grid, while
the WGSL VP epilogue and CPU `vp_vertex` use raw output XY. Verify against
Xbox captures and add position/clipping regressions before changing this;
quantizing already-clipped vertices could introduce a different error.
Broader stadium/staff-model fidelity, all-mode gameplay accuracy, continuous
audio and a sustained 30 FPS floor remain unfinished. The last integrated
retail result remains the preceding flat-shade run (26.0–30.1 FPS after
150 seconds, 200 audio underrun blocks), with no controlled performance
claim for these line changes. Full patched Windows runtime validation is
also still outstanding, as described above.

### Original VP screen-coordinate precision

The browser WGSL epilogue and CPU `vp_vertex` now truncate original screen
XY to the same 1/16-pixel grid already used by the native GLSL and D3D11
paths. Negative coordinates truncate toward zero. This happens before adding
the widescreen surface offset and reconstructing homogeneous coordinates;
depth, W, texture coordinates and other vertex outputs retain their original
precision. Newly generated clip intersections are not snapped again.

The external reference is xemu's
[screen-coordinate helper](https://github.com/xemu-project/xemu/blob/49bfab07a50ef4a2b62f45b960c91aa0e67cfb05/hw/xbox/nv2a/pgraph/glsl/vsh.c)
and its [programmable vertex epilogue](https://github.com/xemu-project/xemu/blob/0103939ba4fcd76d3bc5c052d4e27cddc69ac232/hw/xbox/nv2a/pgraph/glsl/vsh-prog.c).
This change aligns the local backends with that documented NV2A behavior;
it is not a new matched Xbox capture or proof of every raster coverage rule.

The previous differential shader test discarded the whole position epilogue
before comparing arithmetic outputs. The new checks execute it completely.
The published shader fails the new test on its first signed fractional
position. Hardware WebGPU and independent SwiftShader now both pass 864
position components across signed 1/16 boundaries, non-unit/negative W and
three surface/offset configurations. Another 20,480 rendered pixels check
fractional rectangle edges with unit/non-unit W and widescreen offsets,
using the production packed vertex layout. The arithmetic comparison still
passes all 2,752 GPU executions. Position comparisons allow a small float32
conversion tolerance, below a grid step for these tested surfaces.

Native Vulkan under address/undefined sanitizers passes the actual CPU VP
output checks, including unchanged depth/W/texture values, and the existing
rendering/capture suite. Driver leak checks remain disabled. The production
line/clipping Wasm fixture passes 228,150 checks, including an interpolated
near-plane intersection that must retain its fractional position. The actual
browser game and native Linux kernel/video libraries build, and a fresh
pinned runtime reproduces all 89 patched files. Publication `1dbb90a` passed
both Build and Pages workflows.

The 246-second `subpixel-retail/report.json` run reaches Washington at Green
Bay live play. Stadium structure/crowd, uniforms, referee, field markings and
intro text remain visible; the harness records no browser/GPU/DSP fatal fault.
Five-second averages after 150 seconds range from 26.9 to 30.1 FPS. Audio
records 2,936 underrun blocks overall, increasing from 2,448 to 2,936 during
the sampled interval after 150 seconds. Startup overlapped independent shader
validation, and the teams/scene differ from the preceding run, so the total
is not a controlled performance comparison. The late underruns still show
that audio continuity is unfinished. These component and integration results
do not establish full stadium/staff fidelity or a sustained 30 FPS floor.

### Diagonal line width and backend coverage

The software line fallback previously expanded endpoints along their minor
axis. That produces less than one pixel of perpendicular width on diagonals.
The shared `nv2a_line.h` helper now expands perpendicular to the segment.
SDL's CPU-prepared 2D and 3D lines use the same explicit triangles, preserving
endpoint colours, texture coordinates and W. Native GPU VP line lists retain
the host line primitive. Browser lines temporarily use CPU VP preparation:
WebGPU's built-in line coverage on the tested adapter missed all 29 diagonal
probes, while explicit geometry passes them. Ordinary triangle batches retain
GPU VP processing. GPU expansion of browser VP lines remains performance work.

The [manifest](references/nv2a-line-width.json) pins the original Xbox
`Line_width/Line_0001.0.png` capture and test-source hashes, 16 loop vertices,
palette, width register 8 and isolated 100x108 crop. The crop contains 1,174
foreground pixels. The original capture executes a VP; the pre-transformed
replays consume its projected 1/16-grid positions. This is not a separate
hardware test of raw pre-transformed input precision.

`python tools/audit-line-reference.py build-web-tests/line-hardware` verifies
the pinned inputs and generated header (Pillow required); `--write-header`
regenerates it. The 29 probes are selected from capture pixels by their
distance to the original geometry, without consulting a renderer output:
they lie inside the perpendicular strip and outside the old minor-axis strip,
away from endpoints and overlapping lines. The old software fallback misses
all 29; the corrected 2D/3D GPU and software replays pass all 116 native probes
within two RGB steps. Hardware WebGPU and independent SwiftShader each pass
the 29 projected line probes and an explicit 3D line interpolation check with
non-unit W.

The full native crop audit remains deliberately separate from these passing
probes. Each corrected native path covers 1,085 of the 1,174 reference pixels,
adds zero outside the reference mask, and matches 1,081 shared pixels within
two RGB steps. The VP software path recovers 104 reference pixels over the
previous 981-pixel result. The GPU/software masks can differ at individual
pixels despite equal totals. The 89 missing reference pixels, exact caps,
widths other than register 8, smoothing and complete interpolation behavior
remain unresolved. Passing the probes does not establish exact line fidelity.

Optional native fixture output `NFL2K5_LINE_REFERENCE_DUMP=<prefix>` writes
four raw replay frames. Compare the full crop with
`python tools/audit-line-reference.py <capture-directory> --replay-prefix <name>`.
The raw images remain ignored local diagnostics. The Wasm regression also
checks perpendicular width across 24 directions, invalid inputs and existing
assembly/colour/clipping behavior: 228,246 checks. Native address/undefined
sanitizers pass with driver leak detection disabled. The actual browser game
and Linux kernel/video build; a fresh pinned runtime reproduces 91 files.
Publication `f67a27e` passed both Build and Pages workflows. No additional
retail gameplay run is claimed for this change; the preceding integration
run still documents the unresolved frame-rate and audio continuity limits.

### Analytic NV2A line coverage and interpolation

The remaining width-register-8 gap was angle-dependent. The inferred
cross-product bound for the sampled Xbox lines is
`(max(abs(dx),abs(dy)) + 0.5*min(abs(dx),abs(dy)))/2`, rather than a
Euclidean half-width. This is an inference from pinned captures, not a
published NV2A hardware specification or proof for arbitrary lines.

The initial manifest also pinned neighboring captures at registers 0, 7, 9, 15 and 24.
Run the audit with `--width-model` to compare the analytic prediction against
all six images. It reproduces their isolated coverage masks at widths 0,
0.875, 1, 1.125 and 1.875 pixels exactly. At width 3 it predicts two extra
pixels, so wider caps/ties remain unresolved. These additional widths test
the inference; runtime width-register decoding was not implemented in that revision.
The width sweep below supersedes that limitation and its two-pixel gap.

A geometric strip alone still depended on host subpixel precision: it lost
one reference pixel on hardware and 31 on SwiftShader, with two SwiftShader
colour samples outside tolerance. SDL lines now draw conservative candidate
triangles and apply the original strip/cap equations in dedicated fragment
shader variants. They reconstruct diffuse/specular colours, texture
coordinates, fog, depth and perspective W from the original endpoints.
Sampling/derivatives precede rejection, so padding does not contribute colour,
depth or stencil writes. Both 2D and 3D lines use CPU VP preparation; normal
triangles retain their vertex layouts, GPU VP and fragment shaders. The line
variants compile lazily, when a line pipeline is first needed.

The generated header contains the complete 100x108 reference mask and all
1,174 foreground RGB values. Native 2D/3D software and SDL GPU replays now
match the whole mask, add zero pixels and match every foreground colour
within two RGB steps. Hardware WebGPU and independent SwiftShader pass the
same full-crop check. No missing-pixel allowance remains. These are projected
geometry replays of one line-loop capture, not execution of its original
Xbox VP or proof of all rasterization rules.

Additional WebGPU checks exercise perspective colour with non-unit W,
screen-linear texture coordinates, texture alpha-kill, single-hit blending
on the conservative quad diagonal, alpha rejection followed by a rear line,
and rear geometry visible through rejected padding. The native rendering
suite and address/undefined sanitizers pass (driver leak checks disabled).
The 228,246-case production line assembly/colour/clipping regression passes.

The largest line fragment uniform is 784 bytes; flat lines use 320 bytes.
Queued fragment storage is now 1,024 bytes, matching the WebGPU binding
capacity, while normal draws still copy only their existing uniform size.
The queue regression checks distinct 784-byte payloads on adjacent draws,
guards against overwriting neighboring storage, and rejects oversized data
before mutation. Each line currently needs its own endpoint-uniform draw;
instancing/GPU line preparation and their performance remain future work.

The expanded fixture also exposed missing WebGPU shader/pipeline release
mappings: cleanup previously fell through to SDL's native driver and crashed
the worker. Both APIs are now mapped. Shader modules release on the GPU
server; recorded pipeline operations retain an atomic reference until command
cleanup. A regression releases shader handles after pipeline creation and
releases the pipeline handle after recording but before submission, then
checks the submitted pixels. It passes on hardware and SwiftShader.

The actual browser game and native Linux kernel/video build. A fresh pinned
runtime reproduces all 91 patched files. Native D3D11's host line path is
outside this SDL change and still needs equivalent fidelity work and direct
driver validation; Windows CI does not validate the full patched runtime.
Arbitrary widths, smoothing, endpoint rules beyond these captures, wider
stadium/staff fidelity, continuous audio and a sustained 30 FPS floor remain
unfinished.

The 246-second `line-analytic-retail/report.json` run reaches Atlanta at
Philadelphia live play in hardware Chrome 157.0.8103.79 (Intel gen-12hp).
Stadium structure/crowd, uniforms, referee, field markings and intro/HUD
text remain visible. No browser/GPU/DSP fatal fault is recorded. Five-second
averages after 150 seconds range from 24.1 to 30.1 FPS. Audio records 158
underrun blocks overall, including 145 additional blocks after 150 seconds.
The scene/teams differ from the preceding run, so these are not controlled
performance comparisons. The trace does not distinguish CPU line batches
from other CPU VP fallbacks; the capture fixtures provide positive line-path
evidence. This is integrated stability evidence, not full scene fidelity,
continuous audio, all-mode accuracy or a sustained 30 FPS floor.


### Fractional and wide lines: register state and boundary sweep

The SDL and software renderers now decode `NV097_SET_LINE_WIDTH` at `0x0380`
as unsigned 6.3 fixed-point state, initially 8 (one pixel). Legal writes are
0 through 511; larger values preserve the preceding state. Method `0x03B8`
remains specular enable. The pinned nxdk register definitions and captured
invalid-write cases are recorded in `docs/references/nv2a-line-width.json`.
Invalid writes after nondefault state are also tested; that preservation
behavior is inferred from the related hardware-test implementation, whereas
the available NV2A captures reset to width 8 before each invalid write.
No new PGRAPH warning or interrupt emulation is claimed.

The reference sweep now includes 34 captures: all eighth-pixel steps from
0 through 1.875 pixels, integer widths 3 through 16, maximum raw width 511
(63.875 pixels), and invalid values 512, 513 and `0xFFFFFFFF`. The inferred
strip bound scales by width. Projection caps use strict `0 < t < 1`; at an
exact strip boundary, the signed cross product times the signed major-axis
delta must be negative. These directional ties eliminate the prior wider-line
extras. Pure axial lines retain the earlier minor-axis bias and still need
independent hardware coverage. Smoothing and arbitrary endpoint conventions
remain unproven.

All 34 cases pass exact isolated coverage masks with zero missing and zero
extra pixels in native 2D/3D SDL GPU and software rendering, and in 2D/3D
hardware WebGPU and independent SwiftShader. The ordinary crop is 100x108.
Maximum width uses a documented 40x50 isolated crop because neighboring
wide primitives overlap the larger region; this does not validate the full
maximum-width frame. Width-8 cases compare every one of 1,174 foreground
RGB values within two steps; other widths compare up to 64 deterministic
capture-derived colour probes. Separately, the mathematical model matches
all foreground colours within that tolerance across the 34 isolated captures.
Model prediction is separate from actual-renderer probe coverage.

Software lines now execute the shared material path once per covered pixel,
using analytic segment weights and a perpendicular helper vertex for texture
derivatives. This removes overlapping triangle shading within one line.
A half-alpha diagonal regression checks a single blend on native GPU and
software, in both 2D and 3D. Existing browser perspective, texture, depth,
alpha rejection, padding and resource-lifetime checks continue to pass.
Address/undefined sanitizers pass with driver leak detection disabled.
The production Wasm line regression passes 232,822 checks, including exhaustive
validity checks for raw values 0 through 1023 from four preceding states.
The browser game and Linux kernel/video targets build successfully.

This extends SDL/software line fidelity. Native D3D11 still needs equivalent
width and analytic coverage work and direct driver validation. No additional
retail gameplay or performance run is claimed for this sweep; the preceding
246-second run remains the integration evidence and still falls below 30 FPS
with audio underruns. Stadium/staff model parity, all-mode accuracy and full
rendering/audio/gameplay parity remain open.


### Warm vertex-program lookups and integrated line-path profiling

Consecutive draws with an unchanged vertex program now reuse the last ready
shader after comparing every executable word through FINAL and its start
slot. This avoids repeating FNV hashing and cache probing. Changed executable
words, a moved FINAL, another start slot, failed entries and hash collisions
still take the ordinary exact-identity lookup. No program words or inputs are
omitted from the identity check. The Wasm cache regression covers colliding
programs with different interpreter outputs/input masks, 10,000 warm lookups,
mutations after FINAL, relocating the program, extending/shortening FINAL,
shader creation failure and invalid starts.

A local synthetic Wasm microbenchmark of one million identical lookups took
15.8 ms before and 8.5 ms after for three instructions, and 448.6 ms before
and 119.4 ms after for 99 instructions. This isolates lookup overhead using
stub shader creation; it is not a game-frame benchmark or a measured retail
FPS gain. The baseline is the preceding published runtime, `af7d4b0`.

Profile output now distinguishes CPU VP preparation for flat shading, line
primitives and unsupported point/other primitives, including input index
counts for flat shading and lines. These draws can still rasterize on the
GPU: CPU VP preparation is separate from software rasterization fallback.
Previously all three reasons were absent from the VP fallback breakdown.

Two approximately 246-second hardware Chrome 157.0.8103.79 / Intel gen-12hp
runs reached live demo gameplay with DSP enabled and a 30 FPS cap:

| Local report | Observed scene | Five-second FPS after 150 s | Worklet underrun blocks |
| --- | --- | --- | --- |
| `line-width-profile-retail/report.json` | Rainy Green Bay/Denver, stadium tiers/crowd, bench player, rain/fog, uniforms and field overlays | 16.5 to 20.8 | 1,049 total; 485 additional after 150 s |
| `vp-lookup-profile-retail/report.json` | Houston/St. Louis, player uniforms, sideline figures/markers, field overlays and live play | 27.1 to 30.1 | 263 total; 259 additional after 150 s |

Neither report records a browser/GPU failure. These are different scenes and
weather, with host load and profiling uncontrolled; the difference is not a
controlled performance or audio comparison. The second trace records 28,539
CPU-prepared line batches across its completed five-second intervals. In one
interval, 708 line batches account exactly for the GPU-3D versus GPU-VP batch
count difference, with zero software rasterization fallbacks and zero flat
shading, affine, pending-program or failed-pipeline reasons. This provides
positive integrated line-path evidence. It does not independently identify
every line as rain, field art or another object, or prove pixel parity with
original Xbox gameplay.

Each line segment still requires its own endpoint-uniform draw. Grouping
segments while preserving their individual analytic coverage, interpolation,
alpha/depth/stencil behavior and primitive order is a concrete next rendering
cost to investigate. Texture decode/submission costs also remain visible.
Full scene/staff fidelity, uninterrupted audio and a sustained 30 FPS floor
remain unfinished. Build and Pages workflows for `af7d4b0` passed.

The final native rendering suite passes address/undefined sanitizers with
GPU-driver leak detection disabled. The actual browser game and Linux
kernel/video targets build. Fresh pinned-source and reverse-application
checks reproduce all 91 runtime files. Documentation encoding introduced in
the preceding width-sweep edit is corrected without changing its evidence.


### Batched analytic lines and compact queued uniforms

SDL lines now group up to 12 consecutive segments into one triangle draw.
Each segment retains its own two original endpoints and a flat vertex-carried
index into the endpoint array. The candidate geometry, inferred NV2A coverage
rule, cap/tie handling and fragment interpolation remain the same. The new
vertex format is 12 bytes (screen XY and segment index); 3D line candidates
previously occupied the ordinary 116-byte transformed-vertex format. Ordinary
triangles retain their existing formats and shaders.

The 3D fragment payload is 3,600 bytes; flat lines use 3,136 bytes. Twelve was
chosen to fit the pinned native SDL Vulkan backend's 4,096-byte descriptor
range (`MAX_UBO_SECTION_SIZE` in
[SDL 3.2.20](https://github.com/libsdl-org/SDL/blob/release-3.2.20/src/gpu/vulkan/SDL_gpu_vulkan.c)).
A preliminary 32-segment implementation passed WebGPU masks but rendered no
native line pixels because its 8,720-byte payload exceeded that range. It
was replaced before publication. WebGPU's fragment binding now spans 4,096
bytes, and the existing oversized-uniform failure regressions reject 4,097
bytes before reading caller data. The uniform allocation reserves sufficient
trailing space for either binding size.

Queued fragment data now lives in the same growing uniform slab as vertex
uniforms, with separate offsets and complete sizes. It no longer reserves a
fixed fragment array in every queued draw. Vertex-uniform deduplication and
fragment-state comparisons for adjacent-draw merging use the stored offsets;
the queue tests retain distinct 3,600-byte payloads across adjacent draws,
check guard bytes, reject oversized data before mutation, and verify merge
boundaries and index order. Each line batch uploads a pending texture once;
later chunks reuse that upload instead of copying it for every segment.

Native 2D/3D SDL GPU and software paths still pass all 34 capture-derived
width masks with zero missing or extra pixels. Hardware WebGPU and independent
SwiftShader pass both the earlier single-line sweep and the new batched
2D/3D sweep, including the reference loop crossing a batch boundary. Colour
coverage retains the previously stated limits: full foreground RGB for width
8, deterministic probes for other widths, and the smaller isolated maximum-
width crop. These checks do not prove arbitrary line or full scene fidelity.

A native half-alpha regression draws 65 overlapping alternating-colour lines
in exactly six queued draws and checks the final blended colour in 2D and 3D.
It passes across all five 12-segment boundaries. New browser probes explicitly
select the final endpoint slot and check texture coordinates, texture alpha-
kill, single-hit diagonal blending, non-unit W colour, conservative padding,
final alpha discard and a visible rear line after that discard. Both browser
backends report zero GPU validation errors. Native address/undefined sanitizers
pass with driver leak detection disabled. The 232,822-case Wasm line regression,
8,192-state pipeline cache checks, actual browser game and Linux kernel/video
builds pass. A fresh pinned source reproduces all 92 runtime files, including
the new candidate vertex shader. Native D3D11 remains outside this SDL path.

The profile's line-draw counter counts queued groups before adjacent merging
and scissor expansion. It is separate from the high-level CPU VP line-batch
counter and from the final number of clipped GPU API draw calls.

The approximately 246-second `line-batch12-retail/report.json` run reaches
Miami at Dallas live play in hardware Chrome 157.0.8103.79 / Intel gen-12hp.
The 130-second frame shows the referee, uniforms, stadium roof/crowd and
readable coin-toss text; the 240-second frame shows live play, sideline
staff/players, equipment, markers and field art. The report records no
browser/GPU failure. DSP, renderer/stage profiling and APU lock/stage profiling
were enabled with the 30 FPS cap. Completed intervals record 1,142,312 line
segments in 110,129 queued groups, averaging 10.37 segments per group. This
is a measured reduction in line draw requests versus one request per segment,
not a count of final post-merge/scissor GPU API calls.

Five-second averages after 150 seconds range from 29.1 to 30.1 FPS. Audio
records 143 worklet underrun blocks overall, including 129 additional blocks
after 150 seconds. The teams/scenes and instrumentation differ from preceding
runs, so FPS/audio differences cannot be attributed to batching. Late APU
profile windows process 7,494, 7,495 and 7,501 32-sample frames over roughly
five seconds, with 2.29 to 2.48 seconds of measured processing time and worst
frames of 2.2 to 3.9 ms. These samples do not establish a specific underrun
cause; front-end trap waits and scheduling still need separate correlation.
Broader rendering/audio/gameplay accuracy, all stadium/staff variants and a
sustained 30 FPS floor remain unfinished. The preceding `a87c62d` publication
passed both Build and Pages workflows.


### Event-driven IRQ waits and exact audio-gap accounting

The POSIX/Wasm `WaitForMultipleObjectsEx` implementation polled all handles
with `usleep(1000)`. The kernel's IRQ/vblank dispatcher uses that API for its
APU interrupt event and next-vblank timer, so setting the interrupt event did
not directly wake this wait. The dispatcher could remain asleep until the
next host polling wake. APU traces exposed repeated roughly frame-sized
front-end waits and discarded throttle phase despite much shorter individual
audio-frame gaps.

Multiple-object waits now block on an object-transition condition variable.
State transitions publish notifications after releasing their object lock;
waiters hold the notification gate across state checks and release it
atomically when sleeping. Timer deadlines are included in the wait, and
rearming a timer wakes a blocked wait to recompute its deadline. APC callbacks
execute outside the gate, and cancellation cleanup releases the gate. The
kernel's existing ISR priority, guest lock and APU throttle policy remain in
place. In particular, startup buffering, sample rate and the 64 ms catch-up
limit are unchanged.

The old wait-all loop also consumed ready auto-reset events, semaphore counts
and mutex acquisitions while other handles were not ready. The new scan locks
the target states and consumes them only when the whole wait succeeds, as
required by [Microsoft's wait semantics](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitformultipleobjectsex).
Wait-any retains lowest-index selection; invalid arrays/counts/duplicates are
rejected before consuming state. The published-baseline regression fails when
an incomplete wait-all consumes its ready auto-reset event; the corrected
implementation passes. This does not establish complete Win32 compatibility
for unrelated primitives such as abandoned mutexes or periodic timers.

The actual POSIX implementation passes native address/undefined sanitizer
checks (leak detection disabled) and a threaded Wasm/Node build. Coverage
includes 256 event signal/acknowledgment races, ordered wait-any, mixed
wait-all acquisition, no partial consumption, invalid-input preservation,
auto/manual timer latching, arming a timer after a wait begins, thread
completion, an APC callback that signals an event, and cancellation followed
by another successful multi-wait. The local native wake median/p95 were
0.012/0.014 ms; Wasm/Node measured 0.008/0.015 ms. Those are synthetic event
wake measurements, not retail ISR latency or a game-frame benchmark.

Opt-in `RECOMP_APU_LOCK_PROFILE` now reports the maximum gap between audio
frame starts, deadline lateness, timeout wake lateness, actual MMIO handoff
wait duration, throttle rebase count/time, and front-end trap count/duration.
Expected explicit idle time is excluded from the frame-gap measurement.
These wall-clock measurements include host scheduling and lock reacquisition;
they do not identify those costs separately. Pacing checks with profiling both
enabled and disabled preserve the exact one-hour schedule, 64 ms catch-up
boundary, long-stall rebase, early wakes and actual sleep accounting, including
a synthetic 10 ms oversleep. The 10,000-write Wasm handoff test also passes
with profiling enabled.

The AudioWorklet now distinguishes affected render blocks from missing output
frames. `underrunFrames` counts missing output frames; `maxUnderrunFrames` is
the longest continuous missing run, including a run crossing render blocks.
Both exclude startup priming and authored silence. Rates use the output
AudioContext clock, so divide by its sample rate to get gap duration. Existing
PCM interpolation and phase behavior are unchanged. Deterministic worklet
checks cover partial/full blocks, cross-block runs, recovery, authored silence,
posted statistics, rate conversion and counter wrapping. The audio bridge and
retail diagnostic classification tests pass. The browser audit records these
fields alongside the earlier block counter.

Before the multi-wait fix, `apu-schedule-retail/report.json` recorded 630
underrun blocks, 24 throttle rebases totaling 1,679.9 ms, 596 completed traps
(up to 18.2 ms), and a maximum frame-start gap of 22.6 ms. A second baseline,
`apu-gap-frames-retail/report.json`, includes the exact counters: 139 affected
blocks represent 17,665 missing output frames (368.0 ms at 48 kHz), with a
longest continuous gap of 2,560 frames (53.3 ms). Its completed profile
intervals contain five rebases totaling 352.6 ms. These reports have no
browser/GPU failure. The different scenes and aggregate five-second windows
prevent treating those numbers as a controlled comparison or exact event-by-
event attribution, but they motivated fixing the interrupt wait directly.

The approximately 246-second `multiwait-irq-retail/report.json` run reaches
San Diego at Atlanta live play in hardware Chrome 157.0.8103.79 / Intel
gen-12hp, with DSP and renderer/APU profiling enabled. The 130-second capture
shows the referee, player uniforms, stadium lighting/crowd and readable coin-
toss text. No browser/GPU failure is reported. Five-second FPS averages after
150 seconds range from 29.2 to 30.1. Output records 92 affected blocks but
11,649 missing output frames (242.7 ms at 48 kHz), including 11,392 frames
after 150 seconds; the longest continuous gap is 1,664 frames (34.7 ms).

Completed profile intervals contain three rebases totaling 218.5 ms, a maximum
frame-start gap of 27.2 ms, maximum timeout wake lateness of 19.3 ms and a
maximum front-end trap of 26.9 ms. Several quieter intervals report
sub-millisecond trap maxima, but long waits persist. Teams/scenes and host
scheduling differ from the baselines; these are integration measurements,
not a controlled numerical before/after result or proof that all audio gaps
are interrupt-dispatch delays. The direct event-wake and atomic wait-all
regressions prove the primitive fixes independently. Longer IRQ/guest-lock
waits and deadline rebases still need correlation. The final browser game and
Linux APU/kernel/video builds pass, and a fresh pinned runtime reproduces all
93 patched files. The preceding `73c0bdc` Build and Pages workflows passed.
Uninterrupted audio, original-Xbox scene/audio parity, all-mode accuracy and
a sustained 30 FPS floor remain unfinished.


### Exact-phase AudioWorklet tail samples

The worklet previously required two source frames at every output phase,
even though an exact phase reads only the current frame. At 48 kHz output
this replaced a valid final queued sample with silence while waiting for a
neighbor that interpolation did not need. A regression with one source frame
fails on that implementation: it outputs zero instead of the authored sample.

Required occupancy now depends on the current phase: an exact phase needs
one sample, a fractional phase needs two, and downsampling still requires its
entire source advance. The consumer never advances into unwritten data.
A 48 kHz regression plays the lone sample, waits only when empty and recovers
with the next authored sample. A 96 kHz case plays an exact sample immediately,
retains fractional phase across a missing neighbor and then resumes the exact
100, 100.5, 101, 101.5 sequence. Existing rate-conversion, wraparound, authored-
silence, gap-duration and posted-statistics checks continue to pass. This
corrects sample availability without changing startup buffering or sample rate.

Producer diagnostics now call zero/one-frame arrivals `low_queue_submissions`.
A single frame may be playable at an exact phase, so that counter cannot
accurately claim exact worklet starvation. Its threshold is unchanged; missing
output duration remains measured by the worklet's separate frame counters.
The producer regression preserves exact PCM for startup/short writes, rejects
full queues and verifies the renamed low-queue report.

The actual hardware-Chrome audio smoke fixture passes the 35-second authored-
silence boundary, measures 7.011 seconds of audio-clock progress over 7.018
seconds of wall time, and transitions to a 439.8 Hz tone with the expected
level, zero affected blocks and zero missing output frames. The bridge and
browser game build also pass. This is a controlled smoke/PCM result, not a
new retail gameplay run, original-Xbox audio parity or a sustained-FPS claim.
The preceding retail trace still contains IRQ-thread waits of 33 to 134 ms
for the guest lock during live play, with a last scheduling-site marker of
`0x00016CEE`. That marker identifies the last observed scheduling point,
not necessarily the host/guest code currently holding the lock; those waits
remain a separate investigation.


### Used-source vertex interpretation and input layouts

An owned headless hardware-Chrome retail capture profiles the page and live
runtime workers at 4 ms sampling over the 150–240 second window. Two temporary
save workers detach before capture; their profiles are unavailable. The
renderer stack repeatedly visits `vp_src` and `vp_run_prepared` through
`vp_vertex`, transformed lines and push-buffer dispatch. Blocking waits also
appear in these profiles, so sample durations are not CPU-utilization totals.
A separate clock-heavy stack reaches `GetTickCount` and `Sleep` through a
thread trampoline. Its pattern is consistent with the NV2A acknowledgement
poller, but the callback name is absent and that attribution is an inference.

A dedicated worker timing probe measures requested 0.05–1 ms `Atomics.wait`
timeouts at roughly 16 ms median on this host. Adding such a timeout to the
acknowledgement poller could delay a fence by a frame. No acknowledgement
polling or guest-clock policy changes are made. The earlier guest-lock marker
`0x00016CEE` follows object dereferencing; it remains a stale scheduling marker,
not proof of the code responsible for a long lock hold.

Prepared vertex instructions now record which of A, B and C their operations
actually read. Interpretation skips unused operands, and packed GPU input
layouts exclude attributes encoded only in unused operand fields. ARL still
reads A without a vector destination, paired MAC/ILU reads happen before
writes, and scalar/shared-C semantics are preserved. Detailed instruction
tracing retains all encoded operands; its D3D11 caller initializes every input
before enabling that trace. Normal rendering retains selective fetching.

Regressions cover unused relative constants, unused vertex inputs, ILU-only
instructions, unmasked ARL and paired operations. The interpreter passes
40,000 byte-for-byte comparisons of outputs, temporaries, address registers,
writable constants and cache invalidation. The actual production input-mask
function drives a GPU fixture with a terminal NOP encoding unused v12: only
v0/v3/v9 enter its 48-byte layout. Intel hardware WebGPU and SwiftShader pass
2,752 differential GPU vertex executions, 864 production position checks and
20,480 rendered edge pixels. Native sanitized SDL/Vulkan rendering, line
coverage/order fixtures, browser game and Linux kernel/video builds pass.
A fresh pinned runtime reproduces all 93 patched files.

A local O2 mixed-instruction benchmark compares the published prepared
interpreter with this change: three-run medians are 27.65 ms and 25.15 ms for
100,000 vertices, with identical checksums. This synthetic result is not a
retail frame-rate measurement or a controlled scene comparison.


The approximately 246-second follow-up retail run uses hardware Intel gen-12hp
Chrome with DSP and renderer/APU diagnostics, without CPU sampling. It reaches
the rainy Miami at Chicago demo: the 130-second capture shows textured players,
the referee, crowd/stadium lighting and coin-toss text; the 240-second capture
shows a player feature overlay with readable statistics and an inset replay.
No browser/GPU failure is reported. Five-second FPS averages after 150 seconds
range from 17.3 to 20.9, below the requested floor. Output records 169 affected
blocks and 21,632 missing output frames (450.7 ms at 48 kHz), with a longest
continuous gap of 2,816 frames (58.7 ms). This differs in teams, rainy scene and
workload from the preceding traces; it does not isolate an optimization's FPS
impact. It demonstrates that substantial performance and audio-continuity work
remain. Original-Xbox scene/audio parity, broader staff/stadium fidelity,
all-mode accuracy and a sustained 30 FPS floor are still unverified.


### Prepared CPU vertex input streams

The rainy Miami/Chicago trace identifies CPU-transformed lines as a material
cost: five-second renderer intervals report approximately 26–29 ms of vertex
preparation per frame, with millions of line indices per interval. GPU
triangles already prepare attribute ranges once per batch; CPU-transformed
lines previously repeated checked address calculations/copies and scanned all
16 attribute slots for each unique vertex.

Both paths now share a prepared input-stream helper. CPU batch setup computes
the maximum submitted index, validates each used stream once and keeps an
active-slot list. Valid float arrays copy directly with default zero/one
components preserved; other formats use the existing decoder. Immediate and
zero-stride constants are sampled once per batch. Unmapped or partially valid
spans retain per-index checked fetching, so valid vertices in a partially
mapped stream remain readable. Windows CPU rendering retains its existing
fetch path; the direct guest-memory optimization is guarded for Linux/Wasm.
No vertex instruction, output, homogeneous clipping or analytic line-coverage
rule changes.

The Wasm regression extracts the actual CPU batch setup/fetch functions and
shared CPU/GPU helpers. It passes 640,000 randomized CPU/GPU vertex cases over
sparse input masks, all supported formats, inline arrays, constants and invalid
ranges against the frozen checked-fetch reference. Explicit cases verify zero
per-vertex checked reads for a fully mapped stream, continued checked reads
and exact values across a partial mapping, index 65535, empty masks,
generation wrap and constants refreshed between batches. The browser game
and Linux kernel/video builds pass. Earlier overlapping local test invocations
were canceled; only the single final regression run is used as evidence.
The preceding `88d5865` Build and Pages workflows both passed.


The final ASAN/UBSAN native SDL/Vulkan renderer suite passes, including the
pinned line-width masks and ordered translucent line batches. The final
platform-guarded browser game and Linux kernel/video builds also pass. A fresh
pinned runtime reproduces all 93 patched files and reverse application checks.

An input-only Wasm O2 benchmark uses three float attributes over 30,000 batches
of 64 vertices. Three-run medians are 86.727 ms for the preceding per-vertex
slot scan/checked fetch and 34.340 ms for prepared fetching, with the same
69,813,072 checksum. The guarded-memory fixture counts 5,760,000 checked reads
in the former and zero in the latter. The prepared timing includes batch input
setup, but the fixture stubs program preparation and guest-memory validation;
it measures input fetching, not full vertex interpretation or retail FPS.

The approximately 246-second owned headless hardware-Chrome integration run
selects dry Seattle at San Francisco. Players, referee, stadium crowd/signage,
lighting and readable coin-toss text are visible in the 130-second capture.
No browser/GPU failure is reported. Five-second FPS averages after 150 seconds
range from 28.5 to 30.1. Output records 283 affected blocks and 36,224 missing
output frames (754.7 ms at 48 kHz); the longest continuous gap is 2,304 frames
(48 ms). The dry scene has far fewer line indices than rainy Miami/Chicago,
so it cannot establish a rain-scene or whole-game performance improvement.
Audio continuity, a sustained 30 FPS floor, original-Xbox fidelity and broader
staff/stadium/all-mode coverage remain unfinished.


### Bit-preserving SIMD vertex operands

The first identity/broadcast branch fast paths passed parity but regressed the
mixed-program benchmark, including a variant that returned unchanged operand
pointers. Those variants are discarded. The retained Wasm path prepares one
16-byte shuffle per operand with each instruction's exact source words. A
SIMD byte swizzle selects all float components; a sign-bit XOR applies
negation. Scalar ILU operations prepare C's broadcast selectors, including
paired MAC/shared-C use. Constant values and relative addresses are still
resolved at execution time. Full four-component register writes use a short
copy; partial write masks retain their existing lane assignments. Native and
non-SIMD Wasm builds use the portable scalar operand implementation.

A new regression makes 196,608 exact operand-bit comparisons against the
frozen scalar reference: every swizzle, both negations, all source banks,
scalar/shared C, R12/oPos, invalid register fallback, relative-address clamps,
quiet/signaling NaN payloads, signed zeros, infinities and subnormal values.
Every write mask is checked separately. The existing 40,000 full-program
comparisons preserve outputs, temporaries, address registers, writable
constants and cache invalidation. Both SIMD and `--scalar` Wasm pass; an
ASAN/UBSAN native build passes the same operand/program comparisons. The
emitted test Wasm contains the intended byte-shuffle and XOR instructions.

Intel hardware WebGPU and SwiftShader each pass 2,752 differential GPU vertex
executions, the production packed-input layout, 864 position checks and 20,480
rendered edge pixels including non-unit W and widescreen offsets. Shader-cache
identity checks, the native sanitized SDL/Vulkan renderer, browser game and
Linux kernel/video builds pass. A fresh pinned checkout reproduces all 93
patched runtime files and passes reverse-application checks.

A frozen mixed MOV/MUL/DP4/MAD benchmark at Wasm O2 compares the preceding
prepared interpreter with the retained changes. Three-run medians are 25.89 ms
and 21.60 ms per 100,000 vertices, with identical 1,365,000 checksums. This
approximately 17% reduction measures synthetic interpreter work, not retail
FPS. A native scalar O2 comparison is effectively unchanged in this small
sample (52.10 versus 52.52 ms medians); no native speedup is claimed.

Separately, the preceding dry Seattle/San Francisco audio trace records ten
completed-interval deadline rebases totaling 737.7 ms, versus 754.7 ms of
missing output frames. Its large missing-frame increments overlap the rebase
intervals near 166.7, 186.7, 216.7 and 236.7 seconds. This correlation motivates
examining accumulated scheduling debt: it does not prove individual gap
causality or justify changing the 64 ms catch-up limit. No audio pacing,
buffering, sample rate or interrupt policy changes are made in this pass.


Static inspection also finds four host-clock reads in each acknowledgement
poll iteration: frame-counter maintenance, framebuffer tracing (before its
disabled-trace check), KeTickCount publication and the Wasm unrouted-write
scan. Sharing one fresh time sample across those operations is a concrete
follow-up to the clock-heavy profile. It has not been implemented here; the
acknowledgement loop and timing semantics remain unchanged.


The approximately 246-second owned hardware-Chrome integration run selects
Pittsburgh at Arizona. The 130-second coin-toss view renders players, referee,
field and stadium/crowd; the 240-second sideline close-up renders a bench
player, uniform/face and sideline coolers/equipment with stadium advertising.
No browser/GPU failure is reported. Five-second FPS averages after 150 seconds
range from 27.6 to 30.1, so the requested floor remains unmet. Audio records
123 affected blocks and 15,744 missing output frames (328 ms at 48 kHz), with
a longest continuous gap of 1,664 frames (34.7 ms). Completed schedule
intervals contain four rebases totaling 294.7 ms. Different teams/scenes and
host scheduling prevent treating this as a controlled retail performance or
audio improvement. Rain-scene throughput, uninterrupted audio, original-Xbox
scene matching and full stadium/staff/game-mode fidelity remain unfinished.
The preceding `53e66a6` Build and Pages workflows both passed.


### Shared acknowledgement maintenance clock

The acknowledgement poller previously read the host clock separately for
frame-counter maintenance, framebuffer tracing, KeTickCount publication and
the Wasm unrouted-write scan. The framebuffer trace read occurred even when
tracing was disabled. The earlier clock-heavy worker profile motivated this
change; its trampoline-only callback attribution remains an inference.

Each acknowledgement iteration now obtains one fresh millisecond timestamp,
publishes KeTickCount before diagnostic scans and supplies that timestamp to
all three maintenance functions. Register acknowledgements, fence/counter
mirrors and the zero-duration yield still run every iteration. No timed wait,
clock rate, frame period, audio catch-up limit or guest interrupt policy is
added or changed. Sharing clock reads removes redundant work per iteration;
the worker still busy-polls, so lower total CPU utilization is not established.

The new regression extracts the actual maintenance and live-flip functions.
Actual Wasm checks and native ASAN/UBSAN maintenance checks pass: exactly one
host-clock read per entry, fresh guest-tick visibility during diagnostics,
16 ms fallback counters, suppression during live flips, resumption after the
two-second grace period, invalid device pointers, unsigned millisecond wrap,
50 ms unrouted-write scan cadence, exempt DSP windows, one-shot warnings,
1 MiB tile slices and a short final slice, trace suppression and framebuffer
bounds. Native sanitizer compilation exercises the Wasm scan branch as C;
the Linux kernel/video build separately compiles the native host branch.
GPU fence notified-wait/spurious-wake/wrap/stale-publication/guest-lock checks
and QEMU device-clock overflow/frequency checks also pass. The full browser
game builds, and a fresh pinned checkout reproduces all 93 runtime files.

The acknowledgement fixture is included in the web test script and Linux
sanitizer CI. The portable scalar vertex-operand regression from the preceding
SIMD change also joins the web test script. Shell syntax validation passes.


The approximately 246-second owned hardware-Chrome integration run reaches
rainy Tampa Bay at Cincinnati. The 130-second view renders the referee and
players over midfield; the 240-second view shows rain/fog, the quarterback,
score/clock/down overlay and readable defensive-player names. It reaches
third-and-19, first quarter 2:20. No browser/GPU failure is reported. FPS
averages after 150 seconds range from 17.3 to 24.7. Audio records 99 affected
blocks and 12,672 missing output frames (264 ms at 48 kHz); its longest
continuous gap is 7,680 frames (160 ms). The 30 FPS floor and uninterrupted
audio remain unmet. CPU sampling and different teams/scenes prohibit a
controlled comparison with the preceding retail runs.

The 4 ms, approximately 150–240 second owned-worker capture saves 20 live
worker profiles plus the page. Two temporary save workers detach before
profiling and have no profile. The exact Wasm hash and symbol map are retained
with the local capture. In the clock-heavy worker, sampled inclusive time
beneath GetTickCount is 45.45 s of 89.90 s, compared with 71.40 s of 89.96 s
in the earlier `2bfd8e8` capture. Total self time in `_emscripten_get_now` and
its `now` child stays high (about 67.73 versus 66.49 s). The callback remains
hidden by a trampoline, so acknowledgement-worker identity is still inferred.
These profiles include waits and are not CPU-utilization accounting or a
controlled before/after FPS test.

Inspection of the installed SDK's `sched_yield.c` explains a remaining hot
path: Wasm `Sleep(0)` calls `_emscripten_yield(emscripten_get_now())`. Thus the
Wasm poll loop still has a separate yield-clock read in addition to its one
maintenance-clock read. This change reduces the four maintenance queries to
one; it does not remove busy polling or establish lower total CPU use. The
renderer profile still spends substantial sampled time in prepared vertex
interpretation and source fetches, while rainy line indices remain numerous.
Further throughput work needs structural polling/line-transformation changes,
with original-Xbox fidelity and full stadium/staff/mode coverage still open.
The preceding `deed844` Build and Pages workflows both passed.


### Instanced inputs for GPU line batching

Moving line vertex programs off the CPU needs one endpoint-pair input record
per segment. Inspection found prerequisites missing in the WebGPU bridge:
it forced vertex stepping for all streams, bound only the first supplied
vertex buffer at slot zero, assumed each slot's attributes were contiguous
in the declaration and assigned layouts by description order. Those mappings
now honor instance/vertex rates, every binding and its first-slot offset,
interleaved attribute declarations and sparse/unordered buffer slots. Unused
slots use the SDK's null-layout representation, which the first fixture run
exposed as necessary. Layouts beyond the bridge's eight-buffer/sixteen-attribute
limits are rejected instead of truncated. Duplicate/missing slots, duplicate
shader locations, unknown formats/rates, reserved divisors and misaligned
supported attributes/bindings are rejected before WebGPU replay.

The renderer's production queue now retains explicit instance counts and uses
them in indexed and unindexed submissions. Ordinary draws keep their existing
single instance. Instanced uploads are copied independently and kept separate
from ordinary adjacent-vertex merging, which would change instance addressing.
Line vertex programs still execute on the CPU pending GPU shader integration;
this establishes the required input/submission path without an FPS claim.

The published bridge fails the new regression in an isolated baseline build.
Intel hardware WebGPU and SwiftShader pass the new full-frame fixtures:
indexed/unindexed instanced draws each match all 76,800 expected pixels,
including per-instance positions/scales/colors, first instance 1, nonzero
vertex/index/base-vertex and buffer offsets, nonzero binding slots, sparse
slots and interleaved attributes. Indexed recording retains all released
vertex/instance/index buffers and its pipeline until submission. Invalid
layout/binding cases are rejected without GPU validation errors; the full
existing shader, pinned line-coverage, lifetime and presentation suites pass.

The ASAN/UBSAN native Vulkan fixture drives the actual production draw queue:
three instances retain their uploaded data after the caller's array is
mutated, with zero errors across all 76,800 target pixels. Queue unit checks
also preserve instance counts/copies and reject unsafe merges. The complete
native renderer, Linux kernel/video and browser game builds pass. A fresh
pinned checkout reproduces all 93 patched runtime files, with reverse checks.
The preceding `0a41e79` Build and Pages workflows both passed.


The final sparse-layout fixture additionally renders through highest supported
buffer slot 7 on hardware WebGPU and SwiftShader. The approximately 246-second
owned headless retail integration selects Baltimore at Indianapolis. Coin,
referee/player uniforms and readable coin-toss text render at 130 seconds;
the 240-second view shows a pass in flight, players, referee, field numbers
and line overlays. No browser/GPU failure is reported. FPS averages after
150 seconds range from 28.6 to 30.1. Audio records 144 affected blocks and
18,432 missing output frames (384 ms at 48 kHz), with a longest continuous gap
of 2,688 frames (56 ms). This dry matchup is not a rain throughput test or a
controlled performance comparison. Full scene/audio/game-mode fidelity,
broader stadium/staff parity and a sustained 30 FPS floor remain unfinished.


### GPU line vertex programs and endpoint batching

WebGPU now executes supported line vertex programs on paired endpoint inputs.
Each instance supplies one segment; the generated vertex shader transforms
both endpoints, applies the CPU path's homogeneous W/near-plane clipping and
flat provoking color/specular rules, and emits conservative triangle candidates.
The existing analytic fragment coverage determines the final pixels. Endpoint
colors, four texture coordinates and fog travel in 58 flat varying components,
within baseline WebGPU limits. Explicit varying declarations avoid a Naga GLSL
array-interface translation issue found by actual pipeline validation.

Line lists, strips and loops preserve submission order in a single instanced
batch, replacing CPU vertex interpretation and twelve-segment uniform groups.
Programs using more than eight input attributes, unsupported programs and
allocation/pipeline failures retain the CPU route. Native backends continue
using CPU line preparation. `RECOMP_SDLGPU_CPU_LINES=1` selects that route on
WebGPU for comparison; `RECOMP_SDLGPU_NOVP=1` still disables all GPU VPs. The
shared generated instruction arithmetic and triangle uniforms are reused.
GPU candidates execute each endpoint program for six corners, so this change
alone does not establish a throughput improvement.

The new fixture extracts production input fetching, primitive assembly,
paired packing, WGSL translation, CPU vertex interpretation, homogeneous line
clipping and vertex layout generation. Intel hardware WebGPU and SwiftShader
pass 78 full-frame differential cases against CPU-prepared endpoints, with
exact coverage and channel differences at most two. All 34 pinned Xbox line
width masks pass; the default width also checks the full 1,174-pixel RGB
reference. Cases include relative constants/address registers, dot products,
partial writes, non-unit/negative/invalid W, near clipping, degenerate and
zero-width segments, texture alpha kill, specular and fog, flat list/strip/loop
provoking rules, overlapping depth layers and 65 ordered translucent segments.
Validation error scopes also reject silent GPU errors. Exact cache collision
checks cover line specialization; failed line shaders preserve working triangle
shaders.

The shared translator retains 2,752 GPU instruction/register comparisons,
864 position checks and 20,480 rendered edge-pixel checks on hardware WebGPU.
The sanitized native Vulkan renderer suite, Linux kernel/video builds, browser
game build and fetch/queue/uniform regressions pass. The fresh pinned runtime
patch reproduces all 94 files and passes the reverse check. The preceding
`db45c59` Build and Pages workflows both passed.


The owned headless retail integration selects a rainy Kansas City/St. Louis
matchup. The 100-second bench view shows player faces, uniform numerals and
sideline equipment; the 130-second coin-toss view shows rain, stadium tiers,
players/referee and readable overlay text. A representative five-second
interval processes 3,044,850 line segments in 4,500 draws with zero CPU line
VP fallbacks, confirming that the real game uses the new path. This visual
inspection is not original-Xbox stadium/staff parity proof.


The complete approximately 246-second retail run reports no browser/GPU
failures. Its 20 five-second FPS averages after 150 seconds range from
26.5 to 30.0. Audio records 12 affected blocks and 1,536 missing
output frames (32 ms at 48 kHz), with a longest continuous gap of 512 frames
(10.7 ms). Gameplay captures show the lineup, scoreboard and field markings
through rain. Different teams/scenes and instrumentation prevent a controlled
performance comparison with earlier captures. The 30 FPS floor, uninterrupted
audio, full game-mode coverage and original-Xbox stadium/staff fidelity remain
unfinished.


### Same-frame texture rewrites

The direct-guest texture hash memo previously reused a content hash until the
next flip. Changing a texture after its first draw in the same frame could
therefore sample the old image. The new regression reproduces that failure
against the preceding published runtime. A hash is now reused only after a
full-byte equality check against a frame-local copy; changed images receive
new hashes and GPU uploads immediately. The copy arena is capped at 16 MiB.
Allocation failure or arena exhaustion retains accurate per-bind hashing;
frame transitions reclaim the copy space and counter wrap invalidates old
memo entries. Owned snapshots and palettes retain their existing checks.

WebAssembly uses bounded unaligned SIMD loads for equality, checking 64 bytes
per iteration and handling short tails separately. Native builds use libc
`memcmp`. This avoids the installed SDK's four-byte comparison loop without
sampling or skipping any texture bytes. Renderer profiling now reports
nominal verification spans in MiB/frame alongside hashed bytes; early mismatch
returns can read fewer bytes than the reported comparison span.

The production-code fixture passes with SIMD Wasm, scalar Wasm and native
ASAN/UBSAN. It checks every byte of a 4 KiB same-frame rewrite, stage aliases,
copy allocation failure/exhaustion, frame wrap, palette/mip changes and
unaligned ranges of every length from zero through 131, including exact
allocation ends and bytes outside the requested span. The real native Vulkan
renderer retains two draws in its queue across a CPU texture rewrite: the
first produces red pixels and the second blue pixels without a flip. The
full sanitized renderer, Linux kernel/video and browser game builds pass.
These regressions now run in Web CI and native sanitizer CI.

A local Wasm/Node microbenchmark compares 1,000 equal 1 MiB spans in three
passes: the installed SDK comparison takes 81.98–86.79 ms and the SIMD equality
helper 30.84–31.99 ms. This measures the helper on warm equal buffers, not game
FPS or a whole-frame improvement. The preceding `d4b4831` Build and Pages
workflows both passed.


An intermediate browser build using libc equality completed a roughly
246-second Miami/Detroit dry retail run without browser/GPU failures. Its
five-second averages after 150 seconds range from 16.1 to 30.0 FPS.
It records 18,048 missing output frames (376 ms at 48 kHz), with a longest
gap of 4,224 frames (88 ms). This motivated the SIMD equality helper; the
intermediate measurement is retained as evidence, not a controlled comparison
with a different matchup or scene.


The final SIMD build completes a separate roughly 246-second Miami/Chicago
dry retail run without browser/GPU failures. Player-card text and portraits,
field markings, shadows, scoreboard and lineup overlays render in the checked
views. Its 19 five-second averages after 150 seconds range from 21.8 to
30.0 FPS. Audio records 556 affected blocks and 71,168 missing output frames
(1,482.7 ms at 48 kHz), with a longest continuous gap of 2,816 frames (58.7 ms).
The game reaches first-and-ten at 2:07 in the first quarter. These different
matchups/scenes cannot establish a whole-game performance improvement; full
content verification adds memory traffic, and the observed FPS/audio gaps
remain unresolved. Local evidence and Wasm/JS/patch hashes are saved under
`build-web-tests/texture-coherence-simd-retail`. The 30 FPS floor,
uninterrupted/reference-matched audio, complete stadium/staff and game-mode
fidelity remain unfinished.


### Full-content texture hashing throughput

The previous Web CI run exposed a stale fixture boundary: frame pacing's
texture-hint extraction ended at a comment that the coherence fix had changed.
Commit `cd6d4f8` anchors the fixture to `SG_HASH_MEMO` instead; its Build workflow
passes all three platform jobs. The local ordinary Web Python unit sequence
also passes every test. This was a fixture extraction failure, not a reported
browser runtime failure.

Texture keys now use a compact one-shot XXH64 implementation adapted from
upstream xxHash v0.8.3. Four independent 64-bit lanes replace the old serial
multiply/xorshift chain for long images. The process-local keys are rebuilt
at startup; full-byte equality checks, shape/mip/palette inputs, same-frame
rewrite visibility and CPU fallback behavior are retained. The helper reads
unaligned little-endian words without aliasing or alignment assumptions.
Source attribution and the BSD two-clause license accompany the implementation
and the allowlisted Pages artifact; the launcher links the notice.

Pinned golden outputs are generated with the unmodified upstream header
(SHA256 `17973c0dc49d9854ca26caa191f0e12f7a424b68858d9a78de3860d959d85e4b`).
The production helper matches 19,584 cases in SIMD Wasm, scalar Wasm and native
ASAN/UBSAN: every short length through 131, larger word/block/power-of-two tails,
32 alignments, four seeds, exact allocation ends and null/empty input. The
full-content memo fixture and sanitized native GPU renderer remain passing,
including queued old/new images across a same-frame rewrite. Linux kernel/video
and browser game builds pass. A fresh pinned checkout reproduces all 95 patched
runtime files and passes the reverse check.

A local Wasm/Node benchmark hashes 1,000 1 MiB buffers with changing seeds and
leading bytes. Across three passes, the old serial hash takes 159.34–161.06 ms
and XXH64 takes 53.36–54.44 ms. This establishes helper throughput on that host,
not a whole-game FPS improvement. The complete browser page suite passes,
including image/folder import, saved data and static-host isolation. A packaged
Pages smoke test passes isolation/OPFS, linked license availability, Wasm MIME,
byte count, SHA256 and compilation, save-worker loading and mobile layout.


The roughly 246-second retail integration runs the exact allowlisted Pages
artifact from a server without COOP/COEP headers, exercising service-worker
isolation with the installed disc. Tampa Bay/Arizona reaches first-and-ten
at 1:57 in the first quarter. The checked views show players, shadow geometry,
stadium seating/crowd, sideline staff/equipment and readable roster/scoreboard
overlays. No browser/GPU failure is reported. The 19 five-second FPS averages
after 150 seconds range from 24.6 to 30.1. Audio records 218 affected blocks
and 27,904 missing output frames (581.3 ms at 48 kHz), with a longest continuous
gap of 2,432 frames (50.7 ms). Different matchups/camera states prevent a
controlled FPS or audio comparison with preceding runs. Evidence and exact
Wasm/JS/patch hashes are retained in `build-web-tests/xxh64-retail`. Original-Xbox
scene/audio parity, all modes/stadium/staff variants and a sustained 30 FPS
floor remain unfinished.


### Persistent checked texture copies and consistent decoding

The checked-image arena now retains copies across flips within the same
16 MiB budget. Every bind still compares the complete current image before
reusing its hash. Unchanged images no longer require a new hash and copy just
because a frame ended. A monotonic allocation serial detects full or partial
ring overwrite before any retained bytes are read. Oversized images and copy
allocation failure continue through uncached hashing. Cursor overflow clears
memo identities before storage reuse. The collision window is searched fully
for an exact pointer/size/shape identity before a cold entry is replaced;
frame counters now track use rather than copy validity.

The production fixture keeps 64 textures through 32 additional flips without
increasing the hash-byte counter, while the preceding runtime fails that
assertion. Tests retain per-byte same/new-frame mutations and stage aliases,
plus deliberately colliding identities, capacity churn, oversized images,
partial ring overwrite and frame/64-bit cursor wrap. Disabling copy-serial
validation in an isolated fixture makes the partial-overwrite test fail.
SIMD Wasm, scalar Wasm, native ASAN/UBSAN and the complete ordinary Web Python
unit sequence pass.

Review also found that hashing guest RAM, copying it and later decoding it
could select different byte versions if a write intervened. Retained images
now copy first, hash that copy and decode from the same copy. Owned executor
snapshots already have their own storage; images that cannot be retained
continue using the existing direct uncached path. Decode temporarily selects
the retained source and restores the executor's guest pointer on success or
failure, preserving later draws and software fallback.

A real native GPU fixture injects a guest rewrite during an eviction flush,
after key selection and before decoding. With decoding deliberately switched
back to live guest RAM, both draws incorrectly show the newer color. The fix
renders the selected first snapshot (`FFA13579`) and the next rewrite
(`FF2468AC`) separately. The complete sanitized native Vulkan renderer and
Linux kernel/video/browser builds pass. A fresh pinned checkout reproduces
all 95 patched runtime files, with a reverse check. The preceding `d84a5b8`
Build and Pages workflows both passed.

An intermediate approximately 246-second retail pass, before the decoding
consistency change, reports no browser/GPU failures and 27.7–30.1 FPS across
19 five-second intervals after 150 seconds. It records 12,544 missing output
frames (261.3 ms at 48 kHz), with a longest gap of 1,280 frames (26.7 ms).
Representative busy intervals hash 0.17 MiB/frame while checking about
61 MiB/frame. These are observations from that scene rather than a controlled
comparison with earlier matchups. Its evidence is retained separately in
`build-web-tests/persistent-texture-retail`. The final snapshot-consistent
build also passes the packaged Pages isolation, save-worker, Wasm integrity,
linked notice and mobile-layout smoke checks.


The final approximately 246-second Pages-artifact run selects rainy New Orleans
at Denver. The coin-toss view shows rain, floodlights, stadium seating,
players/referee and readable text. Later gameplay keeps players, field
markings and overlays visible. No browser/GPU failure is reported. The
19 five-second FPS averages after 150 seconds range from 25.7 to 30.1.
Audio records 114 affected blocks and 14,592 missing
output frames (304.0 ms at 48 kHz), with a longest gap of
2,304 frames (48.0 ms). A busy interval checks
120.43 MiB/frame, hashes 0.20 MiB/frame and processes 2,883,168 line segments
in 4,402 draws. The evidence and exact served Wasm/JS/patch hashes are retained
in `build-web-tests/persistent-snapshot-retail`. Different teams/scenes prevent
a controlled whole-game performance comparison. Original-Xbox scene/audio
parity, all modes/stadium/staff variants, uninterrupted audio and the 30 FPS
floor remain unfinished.


### Bounded APU register-write handoff

The preceding rainy run records four APU deadline rebases totaling about
269.3 ms, alongside 304 ms of missing output. That correlation does not prove
a single cause. Inspection did reveal an unbounded condition wait: between
voice frames, the mixer waited until `mmio_waiters` became zero. Continuing
arrivals could extend that target indefinitely even after earlier writes
completed.

The handoff now snapshots the pending count and waits for that number of
write completions, then resumes the frame when it regains the lock. Later
arrivals do not increase the target and are considered at the next boundary.
A protected 32-bit completion sequence uses unsigned wrap-safe subtraction.
Every completed write signals the condition, including when other writers
remain pending. Register dispatch and voice processing still share the mutex,
so a write cannot modify voices partway through a frame. OS scheduling and
mutex reacquisition can still delay either side; this is not a hard real-time
latency guarantee. The existing 64 ms catch-up bound, sample cadence and
output-buffer targets are retained.

The actual production functions are exercised in Wasm and native ASAN/UBSAN.
A deterministic continuous-arrival case keeps two writers pending indefinitely,
includes a spurious wake and crosses completion-counter wrap. The old function
fails because it cannot return within the bounded handoff. The fixture also
checks notification while another writer remains queued, 10,000 real contended
writes, frame-boundary exclusion, uncontended operation, continued mixing and
shutdown. The full ordinary Web Python unit sequence, Linux APU/kernel/video
builds and browser game link pass. Native handoff coverage is now part of CI.
A fresh pinned runtime patch reproduces all 95 files and passes the reverse
check. The preceding `ff81723` Build and Pages workflows both passed.


The approximately 246-second packaged retail run selects rainy Green Bay/Miami.
No browser/GPU failure is reported. Coin-toss/stadium lighting, players,
referee and overlay text remain visible. Its 19 five-second FPS averages
after 150 seconds range from 26.3 to 30.0. Audio records
279 affected blocks and 35,712 missing output frames
(744.0 ms at 48 kHz), with a longest gap of 2,304 frames
(48.0 ms). Logged schedule windows contain 10 rebases totaling
717.3 ms; numerous front-end traps remain visible during the bursts.
Different teams/scenes and scheduling prevent a controlled before/after
continuity claim. The bounded-wait regression is fixed, but uninterrupted
audio is not established. Evidence and exact served Wasm/JS/patch hashes are
retained in `build-web-tests/apu-cohort-retail`. Original-Xbox fidelity,
complete mode/stadium/staff coverage, default DSP output matching and a 30 FPS
floor remain unfinished.


### DSP-read completion accounting follow-up

The next audit found an omitted path in `49d2558`: protected GP/EP memory reads
incremented the same waiter count as writes but did not increment the newly
added completion sequence. A read-only group could leave the mixer waiting
for a subsequent write. A shared completion helper now handles both protected
reads and writes under the APU lock, advances the sequence, decrements the
waiter count and signals progress. Ordinary register/voice reads and disabled
DSP reads keep their prior routing and do not join this handoff.

The published predecessor fails the new DSP-read completion assertion. The
expanded production-function fixture passes Wasm and native ASAN/UBSAN with
10,000 write-only, 10,000 GP/EP read-only and 10,000 mixed accesses, plus
continuous arrivals, spurious wakes, wrap and shutdown checks. Read return
values and frame-boundary exclusion are checked. The GP/EP firmware fixture
now includes the production completion helper and passes. The other ordinary
Web Python checks pass, and browser/native APU/kernel/video builds pass.
The correction addresses this accounting defect; it does not establish audio
continuity or original-Xbox output matching.


The corrected packaged build completes an approximately 246-second dry
Detroit/San Diego demo run with executable DSP enabled and both APU and
renderer timing diagnostics disabled. No browser/GPU failure is reported.
The 20 basic five-second FPS averages after 150 seconds range from 27.5 to
30.1. Audio records 69 affected blocks and 8,832 missing output frames
(184 ms at 48 kHz), with a longest gap of 2,816 frames (58.7 ms). The final
view reaches fourth-and-seven at 2:28 in the first quarter, with stadium
seating, banners, video board, field, players and readable overlays visible.
The matchup and diagnostic settings differ from earlier runs, so these values
cannot prove a controlled continuity/performance improvement. Evidence and
exact served Wasm/JS/patch hashes are retained in
`build-web-tests/apu-read-handoff-retail`. The correction's `2a0235b` Build
workflow passes; Pages deployment is still in progress at this observation.
Audio continuity, original-Xbox fidelity, complete modes/stadium/staff coverage
and a sustained 30 FPS floor remain unfinished.


### IRQ signal-age phase measurements

`RECOMP_IRQ_PROFILE=1` adds opt-in timing around the existing IRQ/DPC worker.
It records the first coalesced notification's timestamp and worker phase in
one atomic word, then measures signal age at APU service, overlap with GGL
acquisition and vblank work, ISR duration and DPC-drain duration. The stage
components printed with `max-age` belong to the same worst timed signal;
`max-isr` and `max-dpc` are independent maxima. A signal raised while a prior
DPC is running can appear in the next iteration's `prelock` interval, with
`raised=dpc` identifying that context. This is notification timing, not a
measurement of every hardware line assertion.

The `missing` field counts service calls without a fresh retained timestamp.
An asserted level can be serviced again without a new rising notification,
and a notification can race the observation boundary. Thus this count does
not by itself demonstrate lost interrupts. Discarded notifications, coalescing
and declined/uncallable handlers are reported separately. Profile reports
preserve pending notifications across their statistics resets. IRQ/vblank/DPC
order and guest priorities are unchanged. The normal path performs no added
QPC or frequency queries from these helpers.

Deterministic Wasm and native ASAN/UBSAN fixtures use the real wake callback,
real platform atomic/initialization primitives and a fake QPC. They cover
stage overlap and clipping, signals during GGL/vblank/DPC work, a later faster
signal with a slower ISR (without mixing worst-sample components), concurrent
atomic publication, coalescing, missing/discarded observations, report reset,
pending-notification preservation and the disabled path's zero clock queries
with continued event signaling. The complete ordinary Web Python sequence,
native APU/kernel/video builds and browser game link pass. CI runs the new
fixture in Wasm and native sanitizer builds. The portable patch now reproduces
97 files, including the previously unmodified pinned kernel bridge, with a
fresh application and reverse check.

The approximately 246-second rainy Jacksonville/Chicago capture reports no
browser/GPU failures. Its 19 five-second FPS averages after 150 seconds range
from 25.4 to 30.1. Audio records 130 affected blocks and 16,640 missing output
frames (346.7 ms at 48 kHz), with a longest continuous gap of 1,920 frames
(40 ms). The final checked view reaches second-and-ten at 2:09 in the first
quarter, with players and readable overlays visible through rain/fog.

Reported profile windows contain 612 ISR calls, of which 249 have a fresh
notification timestamp and 363 do not; no discarded/coalesced notifications
or declined/uncallable handlers are reported in those windows. The largest
timed signal age is 1.920 ms, comprising 0.030 ms before lock acquisition and
1.890 ms acquiring GGL, with its associated ISR taking 0.036 ms. Independent
maxima are 2.295 ms in an ISR and 7.580 ms in a DPC drain. This does not bound
the untimed calls or prove the cause of every front-end trap. The next
investigation needs to distinguish repeated asserted-line service from
notification-boundary races and measure the APU condition-wait wake path;
these samples do not justify an IRQ-priority reorder. Profiling and different
scenes prevent controlled comparison with the preceding unprofiled run.
Evidence and served artifact/patch hashes are retained in
`build-web-tests/irq-phase-retail`. The preceding correction's Build and Pages
workflows passed. Uninterrupted/reference-matched audio, complete scene/mode
fidelity and a sustained 30 FPS floor remain unfinished.


### Host condition-wait precision baseline

`tools/benchmark-web-waits.py` now builds an isolated Wasm pthread probe
against the production `win32_compat.c`. It measures 200 samples for each
1, 2 and 5 ms production critical-section condition timeout, alongside raw
pthread conditions using realtime and monotonic deadlines. A separate
producer measures signal-to-return latency with the predicate protected by
the same critical section. The harness checks timeout status and the signal
handshake, and reports distributions without a machine-specific performance
pass/fail threshold. It does not run the game or change runtime scheduling.

Run from an Emscripten environment with Playwright available to Node:

```powershell
python -I tools/benchmark-web-waits.py --executable "C:/Program Files/Google/Chrome/Application/chrome.exe"
python -I tools/benchmark-web-waits.py --target node --build-dir build-web-tests/condition-waits-node
```

The browser runner owns its HTTP server and headless browser, enables the
required isolation headers, saves browser metadata and completion/errors in
`browser-report.json`, and closes its handles. Build evidence records source,
platform/header/patch hashes and tool versions. Node output is saved separately
in `node.log`. These measurements are diagnostics, not part of ordinary CI
because host scheduling and clock precision vary.

On this Windows host with isolated headless Chrome 157, the verified browser
run's production timeout medians were 15.885, 15.995 and 15.870 ms for requested
1, 2 and 5 ms waits respectively. The corresponding raw-monotonic medians were
15.940, 15.925 and 15.925 ms: changing the deadline clock alone did not remove
the delay. Explicit signal-to-return latency had a 0.145 ms median, 0.380 ms
95th percentile and 0.665 ms maximum. A separate initial Node probe also
showed roughly 16 ms timeout medians and prompt explicit notifications.
The reproducible browser report is in `build-web-tests/condition-waits`.

This establishes coarse short-timeout behavior without the game's workload;
it does not prove which retail gaps it causes. The APU currently uses these
relative waits for throttle, front-end traps and locked voices, so a requested
1 ms retry is not a reliable 1 ms bound on this host. A separate exploratory
audio-thread notification probe reduced the maximum observed 5 ms requested
wait to 10.700 ms, but audio callbacks were still batched (8.625 ms median).
It did not exercise the production condition predicate, MMIO handoff or
shutdown paths and is not a validated runtime replacement. Any implementation
must preserve those wakes, avoid lost notifications, handle suspended or
failed audio contexts and be checked under actual gameplay load. No IRQ
priority/order or APU catch-up limit changed in this measurement checkpoint.
Build and Pages workflows for the preceding `b9cd175` diagnostic commit both
passed. Sustained 30 FPS, continuous reference-matched audio and the broader
rendering/mode fidelity requirements remain unproven.


### Experimental audio-thread wake path

`RECOMP_APU_AUDIO_WAKE=1` opts into advisory audio-thread pulses for the APU's
positive finite condition waits. It remains disabled by default. The worklet
increments/notifies the ring header's previously reserved 32-bit word once
per render callback, including startup priming. PCM and both queue indices
retain their layout and behavior. No extra audio frames, silence padding or
new queue cushion is added. Existing rational 48 kHz deadlines and the 64 ms
catch-up limit remain in force.

The APU snapshots the wake sequence while holding its mutex, releases the
mutex, waits only if that sequence still matches, then reacquires the mutex.
Both ordinary APU condition signals and broadcasts notify this sequence and
the original condition variable, so MMIO completion and shutdown still wake
the mixer when the audio context is suspended or has failed. Infinite waits
retain the original condition path. Until a worklet has produced its first
pulse, or when the option/backend is unavailable, finite waits also retain
that path. A zero sequence on counter wrap briefly uses the same fallback;
the next pulse restarts the clock path. Closing preserves the existing ring
allocation lifetime, allowing saved wait addresses to remain valid. Native
runtime behavior is unchanged by the Web-only shim branch.

Wasm and native ASAN/UBSAN fixtures execute the production wait helper,
notification wrappers, backend helpers, close path and platform mutexes. They
cover opt-out/unavailable/startup fallback, nonpositive waits, signed/unsigned
counter wrap, a notification exactly at mutex release, ordinary signal and
broadcast wakes without any audio callbacks, advisory/spurious pulses,
timeout, infinite condition waits and close. A mutant which snapshots the
sequence after releasing the mutex fails the race assertion. Worklet tests
verify notifications target the reserved word, preserve samples/indices,
include priming and stop at shutdown. Bridge tests check option transfer
through deferred loads and retain replacement-ring/shutdown coverage. The
DSP integration fixture now links the real dormant audio backend to satisfy
its added notification dependency; its firmware/PCM assertions pass. The
ordinary Python audit initially exposed that link omission; the corrected
fixture and then the complete ordinary Python audit were rerun successfully.
Full Web game and Linux runtime builds pass,
and fresh patch application reproduces all 97 runtime files.

Two serial approximately 246-second retail DSP captures use the same frozen
Wasm/JS/worklet/patch hashes, the 30 FPS limit and identical profiling options.
Only the first enables the wake experiment. The randomized attract-mode
matchups differ, so they do not provide a controlled performance comparison.
The opt-in capture reaches Cleveland/Chicago, first-and-ten at 2:02 in the
first quarter, with players, a referee and readable scoreboard visible.
It records no browser/GPU failures; its 20 five-second FPS windows after
150 seconds range from 24.0 to 30.1. Audio records 634 affected blocks and
81,152 missing frames (1,690.7 ms at 48 kHz), with a longest continuous gap
of 2,816 frames (58.7 ms). Reported schedule windows contain 24 deadline
rebases totaling 1,670.0 ms, with maximum wake overshoot 13.2 ms. Shorter waits
do not establish uninterrupted audio, and this run does not support enabling
the experiment by default. Evidence is in
`build-web-tests/apu-audio-wake-on-retail` and its off comparison directory.


The default-path comparison reaches Houston/Minnesota, first-and-ten at 1:58
in the first quarter. It also records no browser/GPU failures. Its 19 FPS
windows after 150 seconds range from 23.4 to 30.1. Audio records 168 affected
blocks and 21,504 missing frames (448.0 ms), with a longest gap of 2,944 frames
(61.3 ms). Reported schedule windows contain six rebases totaling 442.6 ms;
maximum wake overshoot is 19.9 ms. Different matchups, playback timing and host
scheduling prevent attributing these differences to the option. Both traces
leave substantial deadline loss despite a different wake mechanism. The sums
of missing output and rebased time are close in both runs; that association
needs finer frame-work/MMIO/trap attribution before changing catch-up policy.
This experiment remains opt-in, with full audio fidelity, all modes/stadiums
and the 30 FPS floor still unfinished. Owned audit browsers and server were
closed after the serial captures.


### Web DSP link-time optimization

The existing lock-profile option also enables per-frame pipeline profiling;
`[APU-PERF]` and `[APU-STAGES]` were already present in the preceding captures.
Their pipeline totals often measured 2.2–2.7 seconds per five-second window,
with DSP dominating many worst-frame samples. These are elapsed wall times
inside the pipeline, including descheduling, rather than exclusive CPU time.
A separate `RECOMP_APU_PROFILE` flag is not implemented and is unnecessary.

Web builds now compile only `dsp.c`, `dsp_cpu.c` and `dsp_dma.c` as LLVM bitcode
and propagate `-flto` to their final link. This lets the linker optimize the
instruction loop across the DSP translation units. The other APU objects keep
their normal compilation, and the conditional leaves native builds unchanged.
Actual game object headers confirm the three DSP files contain LLVM bitcode
while `apu_core.c` remains a Wasm object. No fast-math flag, DSP instruction
semantics, frame/cycle budget, catch-up limit or audio queue policy changes.
The optional audio-clock wake experiment remains disabled by default.

A local benchmark replays one captured GP and one captured EP firmware frame.
Both variants use `-O3 -DNDEBUG -pthread -msimd128`; only the three DSP sources
in the optimized variant use LTO. Seven paired rounds alternate execution
order after warmup. Each round runs 1,000 frames, restoring the captured input
before each frame and checking its resulting DSP core, DMA registers and all
scratch/FIFO transfer data against the recorded result. Private decoded-handler
and callback addresses are normalized for state comparison. The replay harness
uses a checked 1 MiB stack for its full core snapshots; retail stack settings
are unchanged. Captured title data remains local and is not published.

| Captured frame | Baseline median, 1,000 frames | DSP LTO median | Reduction |
| --- | ---: | ---: | ---: |
| GP | 95.858 ms | 82.343 ms | 14.1% |
| EP | 95.413 ms | 80.656 ms | 15.5% |

The goldens come from earlier emulator runs; original-Xbox audio matching
remains unverified. The paired data, exact input hashes and compiler flags are retained in
`build-web-tests/dsp-lto/production-mode`. These results describe those replay
workloads on this host; they do not establish the speedup in every game scene.
The optimized `-O3 -flto` dispatcher passes 141,664 cold/warm full-state cases,
including software interrupt retirement and cross-family instruction uploads.
The optimized firmware/MMIO/PCM fixture also passes with undefined-behavior
sanitization. Ordinary and LTO fixture variants are now both in the Web test
script. The complete ordinary Python audit (including the new firmware LTO
variant), the separately added optimized dispatcher fixture, the full Web game
link and the native APU configure/build pass. Fresh patch application reproduces
97 files. The preceding `3a4fc2e` Build and Pages workflows both passed.


The approximately 246-second optimized retail capture reaches Green Bay/New
Orleans, third-and-fifteen at 2:11 in the first quarter. Checked frames show
players, sideline staff, stadium/crowd geometry and readable scoreboard/lineup
text. No browser/GPU failures are reported. Its 20 five-second FPS averages
after 150 seconds range from 19.7 to 30.1, so the requested floor is not met.
Audio records 190 affected blocks and 24,320 missing frames (506.7 ms at 48 kHz),
with a longest continuous gap of 3,200 frames (66.7 ms). Reported schedule
windows contain seven rebases totaling 501.0 ms, maximum wake overshoot 21.0 ms
and maximum trap delay 26.3 ms. Different matchups and timing prevent a
controlled comparison with preceding gameplay captures; the paired replay
benchmark is the evidence for the isolated DSP speedup. This does not prove
continuous audio, all-mode/stadium fidelity or sustained 30 FPS. The next
performance work still needs to attribute whole-frame and guest scheduling
stalls. Exact served artifact/patch hashes, screenshots and reports are in
`build-web-tests/dsp-lto/retail`; hashes match the frozen current artifacts.
The owned audit browser and server were closed after capture.


### Bulk Morton texture uploads

A fresh worker sample of the DSP-LTO build saved profiles for 20 live workers
and the page during approximately 150–240 seconds of retail execution. Two
short-lived save workers had already detached before sampling. The symbol map
and served Wasm/JS/patch hashes were retained with the capture in
`build-web-tests/current-workers-lto`. The acknowledgement worker's clock and
`Sleep(0)` stacks dominated its recorded samples. On the GPU command worker,
`sg_texture_for_stage` and `sample_texture` accounted for about 20.052 and
13.434 seconds of self sample weight respectively. Wait stacks were separated
in analysis; these sample-weighted elapsed measurements include scheduling
and profiler effects and are not exclusive CPU utilization. No acknowledgement
cadence or frame-pacing change was made from this sample.

Swizzled texture uploads now walk their Morton masks once per image, using
masked coordinate increments instead of recalculating the masks/deposits for
every sampled pixel. Format dispatch stays outside the hot pixel loop, with
unaligned-safe input loads and the existing exact channel expansion. The fast
path covers L8, A8, palette I8, A1R5G5B5, X1R5G5B5, A4R4G4B4, R5G6B5,
A8R8G8B8 and X8R8G8B8. Other formats and non-power-of-two images retain the
sampler fallback. Dimensions, byte bounds and palette availability are checked
before writes. Mip/face iteration, frozen source snapshots, palette hashing,
texture-cache keys and upload ordering remain in their existing paths.

The new fixture executes the actual software sampler as its oracle. Wasm
undefined-behavior checks and native ASAN/UBSAN pass 635 images across all four
stages, power-of-two rectangles through 4096 x 4096, all 65,536
possible words for each supported 16-bit format, random channels/palettes,
unaligned sources, truncated inputs and output guards. Separate checks cover
palette changes, index 255 and unchanged output on rejected input. These are
optimization-equivalence checks against the current software renderer;
original-Xbox fidelity remains a separate requirement.

Five paired rounds each decode 24 images of 256 x 256 pixels, alternating the
order after warmup. Every output pixel contributes to a checksum outside the
timed decode region. Median Wasm results on this host are:

| Format | Sampler, ms | Bulk, ms | Speedup |
| --- | ---: | ---: | ---: |
| L8 | 32.251 | 1.006 | 32.1x |
| A1R5G5B5 | 37.017 | 4.241 | 8.7x |
| X1R5G5B5 | 37.185 | 4.120 | 9.0x |
| A4R4G4B4 | 35.119 | 1.865 | 18.8x |
| R5G6B5 | 37.448 | 3.997 | 9.4x |
| A8R8G8B8 | 32.063 | 1.432 | 22.4x |
| X8R8G8B8 | 32.285 | 1.495 | 21.6x |
| Palette I8 | 32.373 | 1.413 | 22.9x |
| A8 | 32.120 | 1.035 | 31.0x |

Reproduce with `python -I tests/web/test_texture_swizzled.py --benchmark`
from an Emscripten environment. Results/input hashes are retained under
`build-web-tests/texture-swizzled-bench*`. The complete ordinary Python audit,
including existing DXT/linear decoders, passes. The native sanitized Vulkan
renderer fixture passes, including same-frame rewrites, frozen-key/decode
consistency, authored mips/cube faces and injected failure handling. Actual
Chrome WebGPU integration also passes with no validation errors. The Web game
link and fresh 97-file patch application/reverse check pass. CI now includes
the new decoder fixture in Wasm and native sanitizer jobs.

The approximately 246-second unprofiled DSP-enabled retail capture reaches
Minnesota/Oakland, third-and-four at 2:33 in the first quarter. Checked frames
show stadium tiers/crowds, sideline staff, players and readable text. No browser
or GPU failures are reported. Its 20 five-second FPS averages after 150 seconds
range from 28.7 to 30.1. Audio records 36 affected blocks and 4,608 missing
frames (96.0 ms at 48 kHz), with a longest gap of 1,024 frames (21.3 ms). Different
matchups and disabled profiling prevent controlled comparison with preceding
runs; the paired decoder benchmark supports the isolated speedup. Exact served
artifact/patch hashes match the current frozen build and are saved with the
capture in `build-web-tests/texture-swizzled-retail`. Owned browsers/server were
closed. All-mode/stadium/staff reference fidelity, continuous audio and a
sustained 30 FPS floor remain unfinished. The preceding `c0e5c18` Build and Pages
workflows passed.


### Direct Web host clock conversion

Web `GetTickCount64`/`GetTickCount` and `QueryPerformanceCounter` now read the
SDK's monotonic millisecond clock directly, preserving its common pthread
origin. A shared helper performs the same two successive multiplications by
1,000 and positive nanosecond rounding as the inspected SDK's
`clock_time_get`, then returns the existing integer units. This removes the
JavaScript BigInt/timespec conversion and reconstruction from these APIs.
QPC frequency remains 1 GHz, DWORD tick wrap remains unchanged, and native
builds retain their existing POSIX implementation. Sleep, acknowledgement
polling and frame-pacing code are unchanged. A busy polling worker still
needs separate work; lower call cost does not imply that it stops using a core.

The new fixture extracts the production clock functions. It compares 103,292
nonnegative, representable timestamp values with JavaScript's SDK conversion,
covering half-nanosecond cases, adjacent floating-point values around precision
boundaries, epoch-sized values, DWORD wrap and worker calls. It verifies one
clock read per API call, the unchanged frequency, live reads bracketed by the
old SDK path in both main and worker contexts, monotonicity, and a parent/worker
clock-origin bracket. Undefined-behavior checking and the ordinary Web Python
suite pass. The full Web game link, native kernel/APU/video build, fresh
97-file patch application and reverse check also pass.

Seven warmed paired rounds alternate the order of 200,000 calls per API path.
Both benchmark paths use the real SDK clock; the direct variant uses the
extracted production implementation without the controlled-clock test shim.
Median call-loop times on this host are:

| API | Prior timespec path | Direct path | Lower call time |
| --- | ---: | ---: | ---: |
| Tick count | 17.983 ms | 9.836 ms | 45.3% |
| Performance counter | 17.919 ms | 10.100 ms | 43.6% |

Run `python -I tests/web/test_web_host_clock.py --benchmark` to reproduce the
comparison. Results are retained in `build-web-tests/web-host-clock-bench*`.
These are isolated call costs, not a whole-game performance improvement.

The approximately 246-second unprofiled retail DSP capture reaches
Seattle/Oakland, first-and-ten at 2:38 in the first quarter. Checked frames
show players, stadium/crowds, sideline staff and readable overlays. No browser
or GPU failures are reported. Its 19 five-second FPS averages after 150 seconds
range from 22.3 to 30.0. Audio records 37 affected blocks and 4,736 missing
frames (98.7 ms at 48 kHz), with a longest gap of 1,152 frames (24.0 ms).
Matchup differences prevent controlled comparison with preceding captures.
Exact served Wasm/JS/worklet/patch hashes match the frozen current build and
are saved with screenshots and logs in `build-web-tests/web-host-clock-retail`.
Owned audit browser and server were closed. This retains the existing clock
contract but does not establish continuous audio, all-mode/stadium/staff
reference fidelity or a sustained 30 FPS floor. The preceding `a91d540` Build
and Pages workflows passed.

### SDK-independent host clock validation

The first `b0927c3` CI Build failed in the live clock bracket. Emscripten 7
uses `Math.round(now * 1e6)` in its WASI clock, while the locally installed
SDK and our direct clock use `Math.round(now * 1000 * 1000)`. At epoch-sized
pthread timestamps those conversions can differ by one floating-point ULP
(256 ns at the current epoch). The original exact SDK bracket incorrectly
assumed that both SDK versions performed identical rounding.

The fixture now retains an exact live bracket against the specified direct
conversion and checks SDK compatibility separately within one ULP, with a
minimum allowance of one nanosecond for integer rounding. Tick-count bounds
are derived from the same nanosecond interval before division, including
millisecond boundaries. All 103,292 controlled inputs also compare both
JavaScript conversions within that bound. The local undefined-behavior run
passes. Runtime clock, sleep and guest scheduling behavior are unchanged.

A read-only Downloads recheck also confirms `mcpx_1.0.bin` under
`Xbox-Emulator-Files/mcpx`: it is 512 bytes, matches the isolated reference
copy, and has SHA-256
`e99e3a772bf5f5d262786aee895664eb96136196e37732fe66e14ae062f20335`.
The previous missing-ROM note is stale. Existing reference stills and the
isolated BIOS/HDD/DVD configuration are available; this check did not launch
or change xemu and does not establish matched-scene fidelity.

### Real host frame-pacing waits

`tools/benchmark-web-frame-pacing.py` now extracts the production pacer and
links the installed SDL Wasm archive. An owned isolated headless browser runs
90 completed frames for each of six synthetic workloads: 0, 10, 20, 28 and
40 ms, plus repeating 10/14/18/22 ms work. It uses the real SDL sleep and
production deadline logic. Stub guest-lock functions verify balanced
release/reacquire pairs and assert that the lock is released during sleep;
they do not measure real guest contention. An independent
`emscripten_get_now` clock measures work, waits and completed intervals.
Logging is deferred until each scenario finishes to avoid stdout proxying
inside the measured loop. Source/library/generated-code hashes, browser
identity, per-frame samples and summary statistics are retained locally.

On this Windows 11 / headless Chrome 157 host, the final 540-frame run completes
without browser errors. Its under-budget scenarios average 29.918-29.981 FPS,
but their 95th-percentile frame intervals are 47.805-48.190 ms. Median real
wait overshoot ranges from 5.452 to 9.183 ms; the largest observed overshoot is
16.433 ms. The 40 ms workload averages 24.999 FPS and performs no pacer waits,
as expected when work alone exceeds the budget. Results are diagnostic and
host-specific, not a CI timing gate or a retail-game performance claim.
They demonstrate that the existing absolute deadline compensates average
host oversleep while still allowing substantial interval jitter. They do not
prove the cause of every gameplay stall. Runtime sleep policy is unchanged;
a precision-wait replacement must also account for CPU use, audio and guest
lock contention before adoption.

Run `python -I tools/benchmark-web-frame-pacing.py --executable <Chrome-path>`
with Emscripten and Node on PATH and Playwright available to Node. Artifacts
are in `build-web-tests/frame-pacing-host`. The owned browser and HTTP server
were closed after measurement. The preceding `b0927c3` Pages deployment
succeeded; the SDK compatibility fix's workflows were still running when
this benchmark was recorded.

### Supported monotonic clock in SDL's Web timer

SDL 3.2.20 selects `CLOCK_MONOTONIC_RAW` whenever that macro exists.
Emscripten defines it as clock ID 4 but rejects that ID; the inspected libc
only accepts IDs 0 through 3. SDL then falls back to `gettimeofday`, making
its performance counter depend on millisecond wall time. The original local
archive reports a 1 MHz frequency, and a direct raw-clock probe returns
`EINVAL`. This affects SDL elapsed-time users separately from the already
corrected Win32 compatibility clock.

`config/sdl-web.patch` makes only the Emscripten branch select the supported
`CLOCK_MONOTONIC`; native raw-clock selection is unchanged. The linked Web
SDL now reports 1 GHz and retains the SDK's common worker time origin.
`tools/build-web.sh` applies the patch idempotently and records a pin/patch
revision after successful installation. An existing unstamped SDK rebuilds;
a second invocation of the actual dependency-build block skips recompilation.
Fresh/reverse patch checks reproduce the exact built source, and shell syntax
checks pass. Configuration also checks that SDL really enabled its pthread
backend before building/installing it.

The linked-archive fixture creates and joins a real SDL worker, checks the
common time origin and frequency, and performs 6,000 exact monotonic brackets
while moving `Date.now` forward/backward by an hour and a day. SDL elapsed
ticks must remain monotonic. It passes in Node and an owned isolated Chrome;
the ordinary Web Python suite passes too. Pages now runs the browser clock
fixture before publishing. The full Web game links, and the WebGPU renderer
fixture passes with no validation errors.

Validation exposed a stale local build directory with a cached failed pthread
probe. The first local rebuild used that directory and made the audio smoke
worker fail to start. Rebuilding from the working pthread-enabled configuration
restored it; the standard directory's stale probe has also been cleared and
successfully reconfigured. The smoke fixture now reports thread-creation
failure explicitly, and the clock fixture's real worker detects this case.
The long-silence audio check then passes: its clock advances 7.019 seconds in
7.012 seconds, followed by a 439.8 Hz tone, with zero affected blocks or missing
output frames in that fixture.

The final 540-frame real-wait benchmark confirms a 1 GHz SDL counter but still
shows host sleep jitter: under-budget scenarios average 29.896-29.979 FPS,
95th-percentile completed intervals are 47.630-47.735 ms, and the largest wait
overshoot is 16.977 ms. The 40 ms workload averages 24.992 FPS without pacer
waits. This fixes clock source/precision and wall-clock-jump correctness; it
does not establish a performance gain, continuous retail audio, full reference
fidelity or a sustained 30 FPS floor. Results and exact library/source hashes
are retained in `build-web-tests/frame-pacing-monotonic`. The preceding
`d5d6931` and `1e14ea1` Build workflows and `d5d6931` Pages deployment passed.

The approximately 246-second unprofiled retail run on this frozen build reaches
New England/Houston, third-and-seven at 2:31 in the first quarter. Checked
frames show player models, stadium tiers/crowds, sideline staff and readable
intro/HUD text. No browser or GPU failures are reported. Its 20 five-second
FPS averages after 150 seconds range from 26.9 to 30.1. Audio records 104
affected blocks and 13,312 missing frames (277.3 ms at 48 kHz), with a longest
gap of 6,656 frames (138.7 ms). The largest increase in the audio telemetry
is around 196.1 seconds; a future targeted profile should include that part
of play. Matchup differences prevent a controlled comparison with earlier
runs, and this unprofiled capture cannot establish APU rebase counts.

The served Wasm/JS/worklet, both patches and SDL archive hashes match the
saved manifest in `build-web-tests/sdl-monotonic-retail`. Its screenshots,
console/audio samples and summary are retained there. The owned browser and
HTTP server were closed. The new Build and Pages workflows were still running
when the capture completed. Continuous audio, a sustained 30 FPS floor and
all-mode/stadium/staff reference fidelity remain unfinished.

### Explicit Release Web link optimization

The local game cache still contained `CMAKE_EXE_LINKER_FLAGS=-O1
--emit-symbol-map`. That option followed the Release `-O3` compiler flags in
the actual link command, downgrading final Wasm optimization and DSP LTO.
Pages uses a fresh Release configuration without that local override.
The preceding SDL retail capture therefore describes its saved local `-O1`
artifact, not a byte-identical Pages build. The local SDK is 6.0.10, while
CI uses 7.0.0; matching optimization policy does not erase that difference.

The Web game target now explicitly selects final `-O3` linking for Release.
The generated command shows this target option after the stale global `-O1`,
so the intended optimization wins. A complete build succeeds. Its Wasm is
50,679,467 bytes versus the preserved 53,887,423-byte local baseline, a 5.95%
reduction. This is a code-size result, not an established FPS gain. Baseline
public files, symbols and hashes remain in `build-web-tests/link-o1-baseline`.
The new artifact and its exact symbol map are frozen for a fresh worker
profile. The preceding `64597b5` Build/Pages and `82bf536` Build all passed.

Additional disposable browser wait probes did not justify a runtime wait
replacement. Creating a timer helper from the blocked Wasm worker did not
complete its handshake before the probe deadline; creating it on the browser
main thread did. One-shot 1/2 ms timers had medians of 1.095/2.245 ms in one
run, but 10 ms chunking with deadline checks still yielded roughly 16 ms short
waits and a 47.945 ms median for a 33 ms request. Refresh notifications gave
33.33 ms median completed intervals in the synthetic pacer test, with
under-budget 95th percentiles of 34.290-45.630 ms and a 49.215 ms maximum.
These host-specific observations do not establish sufficiently reliable
precision or a 30 FPS floor; production wait policy is unchanged. Probe
artifacts remain in `build-web-tests/browser-timer-probe` and
`build-web-tests/raf-pacer-probe`.

The fresh optimized retail capture completes without browser or GPU failures.
It saves 20 worker profiles plus the page profile, sampled at 4,000 microseconds
from approximately 150 to 240 seconds. Two earlier short-lived workers have
expired CDP sessions before sampling; their metadata records that condition.
The copied symbol map and all served/build-input hashes still match the frozen
artifact. Owned browser/server processes have been closed. Profiles, metadata,
screenshots, telemetry and analysis are in `build-web-tests/current-workers-o3`.

The analyzer excludes explicitly named futex/condition/mutex waits and idle
stacks. Its remaining sample weights are not exclusive CPU time. In particular,
a timer worker has 89.9 seconds attributed to a single `timer_thread` frame
without separate wait frames; that observation cannot establish that it burns
a core and is excluded from hotspot conclusions below.

The acknowledgement polling worker still has about 89.8 seconds of identifiable
active-stack weight; its clock calls dominate, split between tick-count reads
and `Sleep(0)`/yield. It must continue observing unsignalled MMIO/guest-memory
changes, so adding an arbitrary millisecond sleep remains unjustified. The GPU
command worker has 38.1 seconds after named-wait filtering. `sg_texture_for_stage`
accounts for 18.8 seconds of self-sample weight, while Morton per-texel sampling
is no longer prominent. Other identified work includes draw batching, vertex
attribute decoding, queue operations and uniform uploads. The WebGPU driver
has 15.0 seconds after filtering, including 8.0 seconds in `writeBuffer`.
The APU has 26.2 seconds after filtering, led by DSP dispatch and parallel moves.
These locate the next rendering targets: binding/cache lookup and buffer upload
overhead, while retaining every-byte texture coherence and immutable queued
resources. Different matchups, compiler versions and profiling prevent treating
these samples as a controlled FPS/audio improvement. Continuous audio, the
30 FPS floor and complete reference fidelity remain unproven.

### Committed texture-cache index

The texture cache now indexes committed slots by key bucket, with fixed-size
links for constant-cost removal on eviction. Lookups still compare the full
key, width, height and layer count. A verified hot hint remains available.
Small collision buckets use their index; buckets larger than four entries use
the previous contiguous-array scan, avoiding the measured cost of long pointer
chains. The metadata adds 11 KiB of static storage and performs no allocation.

A slot enters the index only when its upload is committed. Reservation,
allocation failure and rejected queue epochs remove it again; empty/pending
keys are invisible. Pixel hashing, every-byte source comparisons, private
snapshot ownership, palette/mip keys, upload data and GPU resource lifetime
rules are unchanged. This addresses binding lookup overhead without relaxing
texture coherence.

The new fixture runs 548,751 lookups against a linear oracle, covering all
512 entries in one collision bucket, head/middle/tail removal, sparse/dense
transitions, duplicate identities, equal keys with different dimensions and
layers, pending commits, epoch invalidation/wrap and 200,000 mutation/query
operations. It also checks index-link/count/hint consistency. Wasm undefined-
behavior and native address/undefined-behavior runs pass. The ordinary Web
Python suite and full Release Web game link pass, as does the native kernel.
Fresh/reverse application reproduces the same 97-file runtime patch and
preserves the pinned runtime commit.

The real Vulkan renderer passes under sanitizers, including same-frame rewrites,
private snapshots across eviction, authored mip chains and queue-failure
recovery. Its rejected-submission test now forces a previously unseen texture:
the failed upload must remain absent from the index, and the successful retry
must become a cache hit. The browser WebGPU API fixture also passes with no
validation errors. Native CI and the ordinary Web script include the new
lookup fixture.

Seven warmed paired rounds alternate the prior and current lookup order.
Each timed trace performs 200,000 lookups; churn also includes publication.
Identical returned-content checksums are verified outside the timing result.
Median Wasm/Node times on this host are:

| Synthetic trace | Prior hint/scan | Indexed | Ratio, prior/current |
| --- | ---: | ---: | ---: |
| Distributed hits | 3.452 ms | 0.898 ms | 3.85x |
| Distributed hits with 5% misses | 4.523 ms | 1.152 ms | 3.93x |
| All 512 keys in one bucket | 14.129 ms | 15.066 ms | 0.94x |
| Replace a slot every 16 lookups | 3.465 ms | 1.070 ms | 3.24x |
| One hot texture in the dense bucket | 0.604 ms | 0.607 ms | 1.00x |

The dense collision stress case remains about 6.6% slower in this isolated
lookup benchmark; the simple linked-list-only candidate had been substantially
worse and was replaced before publication. These synthetic results do not
establish a whole-game FPS gain. Run `python -I tests/web/test_texture_lookup.py
--benchmark` to reproduce them. Logs and medians are retained in
`build-web-tests/texture-lookup-bench*`. The preceding `20fb932` Build/Pages
and `b0c1e44` Build workflows passed.
