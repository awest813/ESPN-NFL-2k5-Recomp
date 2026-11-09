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
