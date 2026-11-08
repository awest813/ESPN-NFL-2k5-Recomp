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
  node "$ROOT/external/xboxrecomp/tests/sdlgpu_web/test_page.js" "$OUT/sdlgpu_web"
  node "$ROOT/tests/web/test_web_av.js" "$OUT/smoke"
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
