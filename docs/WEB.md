# WebAssembly build (experimental)

Milestone M1 of [WEB-PORT-PLAN.md](WEB-PORT-PLAN.md): the game **compiles and
links** with Emscripten. It does not run yet. Booting is milestone M2, which
needs the compacted guest address space, OPFS game files, a page served with
COOP/COEP, and the AC97 replacement.

## Build

You need emsdk (verified with **7.0.0**), cmake, ninja, git, curl and
python3:

    git clone https://github.com/emscripten-core/emsdk.git
    emsdk/emsdk install 7.0.0 && emsdk/emsdk activate 7.0.0
    source emsdk/emsdk_env.sh
    tools/build-web.sh            # full link: build-web/NFL2K5.js + NFL2K5.wasm
    tools/build-web.sh --no-gen   # runtime + hand-written sources only (minutes)

The script does four things:
- fetches and builds SDL 3.2.20 for Emscripten into `dependencies/`, at
  the same commit CI uses;
- fetches miniz, as `docs/LINUX.md` describes;
- applies `config/xboxrecomp-web.patch` to the submodule if it is not
  applied yet;
- configures `build-web/`.

The generated code is about 220 MB of C. As on Linux, each of the largest
files needs about 2 GB of RAM to compile, so set `JOBS=` to match your
memory. CI compiles everything except the generated code on every push. The
full link runs on manual dispatch and uploads the `.js`/`.wasm` as an
artifact.

## What the web target changes

The web build is the POSIX build (`config/game.cmake`'s non-Windows branch)
plus the following:

| Where | Change |
|---|---|
| `config/game.cmake` | No OpenSSL. `src/platform/web/` goes first on the include path. Link flags: `-pthread -sPROXY_TO_PTHREAD` (the guest main runs on a worker; blocking waits are not allowed on the browser main thread), `-sPTHREAD_POOL_SIZE=16`, 1 GB initial memory growing to 4 GB, `-sSUPPORT_LONGJMP=wasm` (guest setjmp/SEH bridge), `-sWASMFS`. |
| `src/platform/web/` | `openssl/{sha,evp,hmac}.h` and `web_crypto.c`: the two OpenSSL calls the game makes (`SHA256` for the XBE check, `HMAC(EVP_sha1())` for save signatures), checked against the FIPS 180 and RFC 2202 vectors. |
| `src/nfl2k5_controller_art.cpp`, `src/nfl2k5_texture_packs.cpp` | Add the missing `<stdlib.h>` for `getenv`. glibc pulled it in transitively; Emscripten's libc does not. |
| xboxrecomp, via `config/xboxrecomp-web.patch` | `platform/guest_memory.c` gets an Emscripten implementation. wasm cannot fault inside linear memory, so a checked copy is a bounds check plus `memcpy`. `nv2a_pb_exec.c` and `nv2a_gpu_sdl3.inc.c` take the checked-copy (Linux) paths on Emscripten as well. The kernel no longer requires OpenSSL there (it never called it). `sdlgpu_vpcache.inc.c` now guards `sg_vp_worker` with `SG_HAVE_GLSLANG`, like its only caller. This last fix also applies to a Linux build without the glslang library. |

## The xboxrecomp patch

The submodule points at `BeyondTomrrow/xboxrecomp` (`nfl2k5-port`). Until its
changes are committed there and the submodule is bumped, they live in
`config/xboxrecomp-web.patch`. To regenerate the patch after editing the
submodule:

    git -C external/xboxrecomp diff > config/xboxrecomp-web.patch

Once the fork carries the changes, delete the patch and its step in
`tools/build-web.sh`.

## Known gaps (M2 and later)

These compile today but are inert or wrong at run time:

- **Guest address space.** `XBOX_PTR` is still `addr + offset`, so guest
  regions above 0x80000000 do not fit in wasm32 memory (plan §2, "Guest
  address space").
- **AC97 trap.** The code is guarded by `__linux__ && __x86_64__`, so on
  the web it is compiled out. Audio will stall until it is replaced.
- **Renderer.** SDL_GPU 3.2.20 has no WebGPU backend, so `RECOMP_SDLGPU`
  finds no device and drawing stays on the software rasterizer.
- **Game files.** These need WasmFS on OPFS and a first-run disc import page.
  No HTML shell exists yet; Emscripten's default output is used.
- **Presentation packages, FMV, mod-pack overlays, Discord.** These are off,
  as on Linux.
