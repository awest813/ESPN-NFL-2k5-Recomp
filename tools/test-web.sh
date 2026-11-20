#!/usr/bin/env bash
# Tests for the WebAssembly build (docs/WEB.md). Run after tools/build-web.sh
# (it builds SDL3 for Emscripten into dependencies/). Needs an activated emsdk.
#
#   gen-web-devices   the DirectSound rewrite (tools/gen-web-devices.py)
#   recomp_web_dev    the APU device accessors (under node)
#   wasm_fixed        fixed-address claims and the host heap ceiling
#   wasm_layout       the real xbox_MemoryLayoutInit on a minimal XBE
#   sdlgpu web        the SDL GPU renderer's API on WebGPU, in headless
#                     Chromium with SwiftShader (needs Playwright)
#   web audio/video   the presenter, input and sound paths in headless
#                     Chromium via tests/web/smoke (needs Playwright)
#   web page          the page in headless Chromium: disc import into OPFS,
#                     COOP/COEP and the service-worker fallback, and the real
#                     module reading the disc (needs a full link in build-web/
#                     and Playwright; skipped otherwise)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NFL2K5_WEB_TEST_DIR:-$ROOT/build-web-tests}"
SDL_DIR="$ROOT/dependencies/sdl3-wasm/lib/cmake/SDL3"
command -v emcc >/dev/null || { echo "emcc not found: source <emsdk>/emsdk_env.sh first" >&2; exit 1; }
[ -f "$SDL_DIR/SDL3Config.cmake" ] || { echo "SDL3 for Emscripten missing: run tools/build-web.sh --no-gen first" >&2; exit 1; }
mkdir -p "$OUT"

python3 -I "$ROOT/tests/web/test_gen_web_devices.py"
python3 -I "$ROOT/tests/web/test_frame_pacing.py"
python3 -I "$ROOT/tests/web/test_vertex_fetch.py"
python3 -I "$ROOT/tests/web/test_vp_cache.py"
python3 -I "$ROOT/tests/web/test_vp_interpreter.py" --build-dir "$OUT/vp-interpreter"
python3 -I "$ROOT/tests/web/test_vp_interpreter.py" --scalar --build-dir "$OUT/vp-interpreter-scalar"
python3 -I "$ROOT/tests/web/test_draw_merge.py"
python3 -I "$ROOT/tests/web/test_draw_uniforms.py"
python3 -I "$ROOT/tests/web/test_clip_plane_state.py"
python3 -I "$ROOT/tests/web/test_texture_hash_algo.py" --build-dir "$OUT/texture-hash-algo"
python3 -I "$ROOT/tests/web/test_texture_hash_algo.py" --scalar --build-dir "$OUT/texture-hash-algo-scalar"
python3 -I "$ROOT/tests/web/test_texture_hash.py" --build-dir "$OUT/texture-hash"
python3 -I "$ROOT/tests/web/test_texture_hash.py" --scalar --build-dir "$OUT/texture-hash-scalar"
python3 -I "$ROOT/tests/web/test_texture_decode.py"
python3 -I "$ROOT/tests/web/test_texture_swizzled.py" --build-dir "$OUT/texture-swizzled"
python3 -I "$ROOT/tests/web/test_texture_samplers.py"
python3 -I "$ROOT/tests/web/test_widescreen.py"
python3 -I "$ROOT/tests/web/test_handle_registry.py"
python3 -I "$ROOT/tests/web/test_qemu_clock.py"
python3 -I "$ROOT/tests/web/test_nv2a_ack_clock.py" --build-dir "$OUT/nv2a-ack-clock"
python3 -I "$ROOT/tests/web/test_gpu_fence_wait.py"
python3 -I "$ROOT/tests/web/test_gameplay_flag_joins.py"
python3 -I "$ROOT/tests/web/test_flag_cfg_reachability.py"
python3 -I "$ROOT/tests/web/test_flat_shading.py"
python3 -I "$ROOT/tests/web/test_line_primitives.py"
python3 -I "$ROOT/tests/web/test_apu_audio_wake.py" --build-dir "$OUT/apu-audio-wake"
python3 -I "$ROOT/tests/web/test_apu_lock_handoff.py"
python3 -I "$ROOT/tests/web/test_apu_sample_counter.py"
python3 -I "$ROOT/tests/web/test_apu_pacing.py"
python3 -I "$ROOT/tests/web/test_dsp56300.py"
python3 -I "$ROOT/tests/web/test_dsp_multiply.py"
python3 -I "$ROOT/tests/web/test_dsp_dispatch.py"
python3 -I "$ROOT/tests/web/test_dsp_dispatch.py" --lto
python3 -I "$ROOT/tests/web/test_gp_ep.py"
python3 -I "$ROOT/tests/web/test_gp_ep.py" --lto --build-dir "$OUT/gp-ep-lto"
python3 -I "$ROOT/tests/web/test_irq_preemption.py"
python3 -I "$ROOT/tests/web/test_irq_profile.py" --build-dir "$OUT/irq-profile"
python3 -I "$ROOT/tests/web/test_audio_submission.py"
python3 -I "$ROOT/tests/web/test_voice_attenuation.py"
python3 -I "$ROOT/tests/web/test_audio_diagnostics.py"
node "$ROOT/tests/web/test_audit_diagnostics.cjs"
node "$ROOT/tests/web/test_sdlgpu_wait.cjs"
node "$ROOT/tests/web/test_audio_worklet.cjs"
node "$ROOT/tests/web/test_audio_bridge.cjs"

emcc -O2 -I"$ROOT/src/platform/web" "$ROOT/tests/web/test_recomp_web_dev.c" -o "$OUT/test_recomp_web_dev.js"
node "$OUT/test_recomp_web_dev.js"

for t in wasm_fixed wasm_layout; do
  emcmake cmake -S "$ROOT/external/xboxrecomp/tests/$t" -B "$OUT/$t" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DSDL3_DIR="$SDL_DIR" -DCMAKE_C_FLAGS="-pthread -msimd128" >/dev/null
  cmake --build "$OUT/$t" -j "${JOBS:-$(nproc)}"
  ctest --test-dir "$OUT/$t" --output-on-failure
done
HAVE_PW=0
node -e "require('playwright')" 2>/dev/null && HAVE_PW=1
emcmake cmake -S "$ROOT/tests/web/smoke" -B "$OUT/smoke" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DSDL3_DIR="$SDL_DIR" -DCMAKE_C_FLAGS="-pthread -msimd128" >/dev/null
cmake --build "$OUT/smoke" -j "${JOBS:-$(nproc)}"
emcmake cmake -S "$ROOT/external/xboxrecomp/tests/sdlgpu_web" -B "$OUT/sdlgpu_web" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DSDL3_DIR="$SDL_DIR" -DCMAKE_C_FLAGS="-pthread" -DCMAKE_CXX_FLAGS="-pthread" >/dev/null
cmake --build "$OUT/sdlgpu_web" -j "${JOBS:-$(nproc)}"
if [ "$HAVE_PW" = 1 ]; then
  python3 -I "$ROOT/tests/web/test_vp_wgsl.py" --build-dir "$OUT/vp-wgsl"
  node --require "$ROOT/tests/web/browser-ci.cjs" "$ROOT/tests/web/test_vp_wgsl.js" "$OUT/vp-wgsl"
  python3 -I "$ROOT/tests/web/test_gpu_lines.py" --build-dir "$OUT/gpu-lines"
  node --require "$ROOT/tests/web/browser-ci.cjs" "$ROOT/tests/web/test_gpu_lines.cjs" "$OUT/gpu-lines"
  node "$ROOT/tests/web/test_audit_browser.cjs"
  node --require "$ROOT/tests/web/browser-ci.cjs" "$ROOT/external/xboxrecomp/tests/sdlgpu_web/test_page.js" "$OUT/sdlgpu_web"
  node --require "$ROOT/tests/web/browser-ci.cjs" "$ROOT/tests/web/test_web_av.js" "$OUT/smoke"
  node --require "$ROOT/tests/web/browser-ci.cjs" "$ROOT/tests/web/test_audio_clock.js" "$OUT/smoke"
  node "$ROOT/tests/web/test_browser_saves.js" "$OUT/smoke"
else
  echo "web audio/video test skipped (needs Playwright)"
fi
if [ -f "$ROOT/build-web/NFL2K5.wasm" ] && [ "$HAVE_PW" = 1 ]; then
  node "$ROOT/tests/web/test_web_page.js" "$ROOT/build-web"
else
  echo "web page test skipped (needs build-web/NFL2K5.wasm from tools/build-web.sh, and Playwright)"
fi
echo "web tests passed"
