#!/usr/bin/env bash
# Build the Emscripten (WebAssembly) target. See docs/WEB.md.
#
#   tools/build-web.sh             # runtime + game, links build-web/NFL2K5.{js,wasm}
#   tools/build-web.sh --no-gen    # runtime + hand-written game sources only (fast check)
#
# Needs an activated emsdk (source <emsdk>/emsdk_env.sh), cmake, ninja, git,
# curl and python3. Pinned dependencies go to dependencies/ (gitignored):
#   dependencies/SDL          SDL 3.2.20 source (same commit as CI)
#   dependencies/sdl3-wasm    SDL3 built for Emscripten with pthreads
# The xboxrecomp changes the web build needs are in config/xboxrecomp-web.patch
# until they land in the submodule; this script applies them if missing.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="${NFL2K5_WEB_BUILD_DIR:-$ROOT/build-web}"
JOBS="${JOBS:-$(nproc)}"
SDL_COMMIT=96292a5b464258a2b926e0a3d72f8b98c2a81aa6   # 3.2.20, as in build-check.yml
NO_GEN=0
for arg in "$@"; do
  case "$arg" in
    --no-gen) NO_GEN=1 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

command -v emcc >/dev/null || { echo "emcc not found: source <emsdk>/emsdk_env.sh first" >&2; exit 1; }
cd "$ROOT"

# xboxrecomp: submodule plus the web patch.
[ -f external/xboxrecomp/CMakeLists.txt ] || git submodule update --init external/xboxrecomp
# Apply from the parent worktree so this also works when the submodule's Git
# metadata is inaccessible. Accept Windows checkouts with CRLF line endings.
web_patch=(git -c core.whitespace=cr-at-eol apply --ignore-space-change --directory=external/xboxrecomp)
if "${web_patch[@]}" --check config/xboxrecomp-web.patch 2>/dev/null; then
  "${web_patch[@]}" config/xboxrecomp-web.patch
  echo "applied config/xboxrecomp-web.patch"
elif "${web_patch[@]}" --reverse --check config/xboxrecomp-web.patch 2>/dev/null; then
  : # already applied
else
  echo "config/xboxrecomp-web.patch does not apply to external/xboxrecomp" >&2
  exit 1
fi

# miniz from xemu's tree, as in docs/LINUX.md.
MINIZ=external/xemu-src/util/miniz
if [ ! -f "$MINIZ/miniz.c" ]; then
  mkdir -p "$MINIZ"
  for f in miniz.c miniz.h; do
    curl -fsSL -o "$MINIZ/$f" "https://raw.githubusercontent.com/xemu-project/xemu/master/util/miniz/$f"
  done
fi

# SDL3 for Emscripten (static, pthreads).
SDL_PREFIX="$ROOT/dependencies/sdl3-wasm"
if [ ! -f "$SDL_PREFIX/lib/cmake/SDL3/SDL3Config.cmake" ]; then
  if [ ! -d dependencies/SDL/.git ]; then
    git clone --filter=blob:none https://github.com/libsdl-org/SDL.git dependencies/SDL
  fi
  git -C dependencies/SDL checkout -q "$SDL_COMMIT"
  emcmake cmake -S dependencies/SDL -B dependencies/build-sdl-wasm -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$SDL_PREFIX" \
    -DSDL_SHARED=OFF -DSDL_STATIC=ON -DSDL_TESTS=OFF -DSDL_EXAMPLES=OFF \
    -DSDL_PTHREADS=ON -DCMAKE_C_FLAGS=-pthread
  cmake --build dependencies/build-sdl-wasm -j "$JOBS"
  cmake --install dependencies/build-sdl-wasm
fi

emcmake cmake -B "$BUILD" -G Ninja -DCMAKE_BUILD_TYPE=Release -DNFL2K5_BUILD_GAME=ON \
  -DSDL3_DIR="$SDL_PREFIX/lib/cmake/SDL3" \
  -DCMAKE_C_FLAGS="-pthread -msimd128" -DCMAKE_CXX_FLAGS="-pthread -msimd128"

if [ "$NO_GEN" = 1 ]; then
  objs=$(ninja -C "$BUILD" -t targets all | grep -o '^CMakeFiles/NFL2K5.dir/[^:]*\.o' | grep -v '/recomp/gen' || true)
  ninja -C "$BUILD" -j "$JOBS" platform xbox_kernel xbox_d3d8 xbox_dsound xbox_input xbox_usb \
    xbox_apu xbox_nv2a xbox_video $objs
  echo "runtime and hand-written game sources compiled (generated code skipped)"
else
  # The largest generated files need ~2 GB of RAM each to compile.
  ninja -C "$BUILD" -j "$JOBS" NFL2K5
  ls -l "$BUILD"/NFL2K5.js "$BUILD"/NFL2K5.wasm
fi
