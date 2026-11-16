# Stadium and staff rendering checks

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
guest TODO diagnostics remain. GPU destination-resource cycling remains a
separate open check.

The supplied files in Downloads now allow a local xemu reference boot. An
isolated configuration and copied EEPROM/ROM files are under ignored
`build-web-tests/xemu-reference`; the original HDD is used with `-snapshot`.
The first reference run reached Arizona at New Orleans gameplay and produced
`xemu-2026-11-15-19-42-36.png`, a raw 640×480 game frame without desktop UI.
That run used 128 MB and surface scale 2; a later configuration explicitly
selects 64 MB and scale 1 for repeatable checks. Desktop interaction stopped
when the user pressed Escape. A controlled scene-matched comparison has not
yet been completed, so these captures do not establish rendering/audio parity.
