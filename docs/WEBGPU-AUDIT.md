# WebGPU stability audit

2026-11-08. The renderer's SDL GPU subset was checked with hardware WebGPU
on Windows and CI's Playwright 1.63.0 / Chromium 153 / SwiftShader on Linux.

## Corrections

- The first 3D draw exceeded the 120-second test timeout on SwiftShader.
  Register-combiner input/output mappings now use vector selects instead of
  repeated switch trees. General stages calculate RGB and alpha before
  committing either result, avoiding two whole-register-file copies per stage.
  The full workload and timeout are retained; no rendering checks are skipped.
- Fences now observe actual asynchronous queue completion. Each submission
  has its own fence, wait-any and wait-all use completion notifications,
  and a callback reference keeps early-released fences alive safely.
- Incomplete recordings fail submission instead of replaying a partial command
  stream or returning a successful fence. Uniform limits, transfer bounds and
  buffer-write alignment are checked before host memory is read or written.
- Texture transfers compute the exact final-row span, with overflow-safe range
  checks. Padded uploads need no trailing padding beyond the final texel.
  Readbacks and texture copies preserve the selected cube layer.
- Readback allocation/map failures propagate to submission results. Object
  allocation failures are checked and surface-capability arrays are released.
- Browser test failures retain module logs and print browser errors, adapter
  information and elapsed time. Startup aborts are reported directly.
- Linux CI applies the published runtime patch. Its native GPU fixture now
  uses the real executor, vertex decoding and guest-memory accessors rather
  than stale duplicate structures. Texture rewrites follow the real frame
  hash lifetime, and depth/stencil clears use the implemented behavior.
- The launcher preserves its original terminal error when late worker
  progress, video or secondary-abort messages arrive.

## Regression coverage

The standalone browser regression checks exact pixels for all eight input
mappings and all eight output mappings; simultaneous RGB/alpha updates;
eight general stages; dot products; both mux selectors; final combiners;
depth bias; culling; alpha tests/blending; texture caches and render-target
copies; window clipping; all six cube layers and generated mips; cropped
presentation; transfer bounds; failed-recording atomicity; and fence lifetimes.
GPU validation errors fail the test.

The expanded full browser suite completed locally in 6.4 seconds on Linux
SwiftShader and 3.7 seconds on Windows hardware WebGPU. The original first
3D draw timed out after 120 seconds. These are test-suite times, not gameplay
frame-rate measurements.

```sh
node --require ./tests/web/browser-ci.cjs external/xboxrecomp/tests/sdlgpu_web/test_page.js build-web-tests/sdlgpu_web
node tests/web/test_web_av.js build-web-tests/smoke
node tests/web/test_browser_saves.js build-web-tests/smoke
node tests/web/test_web_page.js build-web
```

The native staging and Vulkan regressions and the full Linux runtime build
are also checked. The published runtime patch must reproduce the local
runtime from the pinned submodule; do not publish an unpublished submodule
commit instead. WGSL regenerates with naga-cli 27.0.0 through
`external/xboxrecomp/tools/gen-wgsl.py`.

This remains the SDL GPU subset used by this game, with one device per
runtime. Device recreation/automatic recovery after GPU loss and the full
SDL GPU API are outside this verification. A sustained 30 FPS floor is not
established by these rendering tests.
