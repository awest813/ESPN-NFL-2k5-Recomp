#!/usr/bin/env bash
# Tests for the WebAssembly build (docs/WEB.md). Run after tools/build-web.sh
# (it builds SDL3 for Emscripten into dependencies/). Needs an activated emsdk.
#
#   gen-web-devices   the DirectSound rewrite (tools/gen-web-devices.py)
#   recomp_web_dev    the APU device accessors (under node)
#   wasm_fixed        fixed-address claims and the host heap ceiling
#   wasm_layout       the real xbox_MemoryLayoutInit on a minimal XBE
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

emcc -O2 -I"$ROOT/src/platform/web" "$ROOT/tests/web/test_recomp_web_dev.c" -o "$OUT/test_recomp_web_dev.js"
node "$OUT/test_recomp_web_dev.js"

for t in wasm_fixed wasm_layout; do
  emcmake cmake -S "$ROOT/external/xboxrecomp/tests/$t" -B "$OUT/$t" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DSDL3_DIR="$SDL_DIR" -DCMAKE_C_FLAGS="-pthread -msimd128" >/dev/null
  cmake --build "$OUT/$t" -j "${JOBS:-$(nproc)}"
  ctest --test-dir "$OUT/$t" --output-on-failure
done
if [ -f "$ROOT/build-web/NFL2K5.wasm" ] && node -e "require('playwright')" 2>/dev/null; then
  node "$ROOT/tests/web/test_web_page.js" "$ROOT/build-web"
else
  echo "web page test skipped (needs build-web/NFL2K5.wasm from tools/build-web.sh, and Playwright)"
fi
echo "web tests passed"
