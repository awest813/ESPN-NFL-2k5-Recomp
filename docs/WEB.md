# WebAssembly build (experimental)

Milestone M1 of [WEB-PORT-PLAN.md](WEB-PORT-PLAN.md) is done: the game
**compiles and links** with Emscripten. Two of the M2 runtime pieces are in:
the guest address space ([below](#guest-address-space)) and APU/AC97
register routing without faults ([below](#audio-registers-without-faults)).
Nothing has booted yet, because that needs OPFS game files and a page served
with COOP/COEP.

## Result (2026-11-06, emsdk 7.0.0, 4-core container)

| | |
|---|---|
| `NFL2K5.wasm` | 37.9 MB (8.9 MB gzip -9), 36,377 functions, 37.3 MB of code. With the address-space and APU work (2026-11-07) it is 49.5 MB with 48.8 MB of code; see "Cost" below. |
| `NFL2K5.js` | 167 KB of Emscripten glue (pthreads, WasmFS) |
| Largest function body | 76 KB (117 KB after the address fold). V8's per-function limit is 7.6 MB, so this concern from the plan is settled. |
| V8 compile, whole module, eager | 0.26 s Liftoff, 4.1 s TurboFan (Node 24). The browser compiles lazily and in tiers. |
| `tools/build-web.sh` from scratch | 143 s (SDL3, runtime, game; the 34 generated chunks take about 90 s with `-j4`) |

`WebAssembly.validate` passes and the module compiles in V8. The game itself
has not run yet, but the runtime's real memory-layout init does, under Node,
in `tools/test-web.sh`.

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

`tools/test-web.sh` then runs the web tests (Node, from the same emsdk):
the DirectSound rewrite, the APU accessors, fixed-address mappings with the
heap ceiling, and the real `xbox_MemoryLayoutInit` on a minimal XBE. CI runs
it on every push.

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
| `config/game.cmake` | No OpenSSL. `src/platform/web/` goes first on the include path. Link flags: `-pthread -sPROXY_TO_PTHREAD` (the guest main runs on a worker; blocking waits are not allowed on the browser main thread), `-sPTHREAD_POOL_SIZE=16`, 1 GB initial memory growing to 4 GB, `-fwasm-exceptions` (C++ sources throw), `-sSUPPORT_LONGJMP=wasm` (guest setjmp/SEH bridge), `-sWASMFS`. |
| `src/main.c` | `install_audio_mmio_handler()` is a no-op on Emscripten. There is no SIGSEGV/SIGTRAP to catch, and the Linux handler decodes x86-64 `ucontext` registers. |
| `src/nfl2k5_save_library.cpp` | Use `getentropy()` for save container IDs. Emscripten declares `getrandom()` but does not implement it. |
| `src/platform/web/` | `openssl/{sha,evp,hmac}.h` and `web_crypto.c`: the two OpenSSL calls the game makes (`SHA256` for the XBE check, `HMAC(EVP_sha1())` for save signatures), checked against the FIPS 180 and RFC 2202 vectors. |
| `src/nfl2k5_controller_art.cpp`, `src/nfl2k5_texture_packs.cpp` | Add the missing `<stdlib.h>` for `getenv`. glibc pulled it in transitively; Emscripten's libc does not. |
| xboxrecomp, via `config/xboxrecomp-web.patch` | `platform/guest_memory.c` gets an Emscripten implementation. wasm cannot fault inside linear memory, so a checked copy is a bounds check plus `memcpy`. `nv2a_pb_exec.c` and `nv2a_gpu_sdl3.inc.c` take the checked-copy (Linux) paths on Emscripten as well. The kernel no longer requires OpenSSL there (it never called it). `platform/CMakeLists.txt` builds `guest_memory.c` for Emscripten. `win32_compat.c` gets a `GlobalMemoryStatusEx` from the wasm heap limits, because there is no `sysinfo(2)`. `sdlgpu_vpcache.inc.c` now guards `sg_vp_worker` with `SG_HAVE_GLSLANG`, like its only caller. This last fix also applies to a Linux build without the glslang library. |

## Guest address space

A native host maps each guest region at `base + guest address` and turns a
guest address into a host pointer by adding one offset. Around 430 places in
the runtime do exactly that (`xbox_GetMemoryOffset() + va`, `XBOX_TO_NATIVE`,
the GPU, APU and USB device models), as does every `MEM*` access in the
generated code. So the web build keeps the arithmetic and makes the linear
memory the address space.

- **Identity layout.** Guest address `va` is wasm address `va + 0x10000` (the
  offset the layout init picks, as on Linux). This covers:
  - RAM at 0x10000;
  - the contiguous window at 0x80010000;
  - the tiled aperture, NV2A, MCPX and flash at 0xF0010000 to 0xFF110000.
- **Host kept out.** The host's static data, stack and heap start at
  `-sGLOBAL_BASE=0x08100000`, above 128 MB of RAM. `sbrk` is wrapped
  (`-Wl,--wrap=sbrk`) so the heap stops below 0x80000000, which leaves
  about 1.86 GB for the host.
- **The mapping shims.** In `platform/wasm_fixed.{h,c}`, a
  `VirtualAlloc`/`MapViewOfFileEx` at an address succeeds exactly when the
  range lies in one of those windows and no other mapping holds it. Memory
  grows to cover it. Memory is reserved virtually but only resident where
  touched, as with mmap.
- **No aliasing.** Linear memory cannot alias, so there are no RAM mirrors
  and the tiled aperture is separate memory. Generated code folds mirror
  addresses itself: `XBOX_PTR` takes any address below 2 GB modulo 128 MB,
  in four branchless integer operations. That is the hardware wrap, and it
  also keeps a stray guest pointer out of the host heap.
  `-DNFL2K5_WEB_TILED_FOLD=ON` also folds 0xF0000000..0xF3FFFFFF onto the
  contiguous window. It is off by default, because nothing shows NFL 2K5
  using tiled addresses.
- **Checked copies** (`guest_memory.c`) accept only ranges inside a fixed
  mapping, so a device model that follows a bad pointer is refused as on a
  native host, and does not read the host heap.

**Cost.** The fold and the APU accessors together made the module 31%
larger, 37.9 to 49.5 MB. Most of that is presumably the fold, which is on
every guest access, whereas the accessors are in 729 of 33,671 functions;
the split was not measured. Neither has the run-time cost; that is M3.

## Audio registers without faults

Natively, the APU's register window (0xFE800000..0xFE87FFFF) faults on every
access, and the fault handler replays the instruction into the emulated APU.
Many of those accesses are voice-processor command writes, so polling would
lose them. On the web, `tools/gen-web-devices.py` runs at configure time and
rewrites the guest's DirectSound code instead:

- **What it selects.** Every function that names an APU register address,
  plus every function in the library they cluster in. That is 729 functions
  (0x443679..0x453C6C), and the rewrite routes 6,595 reads and 2,712 writes.
- **What the rewrite does.** Each `MEM*` access in those functions becomes a
  `RECOMP_DEV_*` accessor (`src/platform/web/recomp_web_dev.h`). The
  accessor sends the APU window to `mcpx_apu_mmio_read/write` and anything
  else to memory, with the same exemptions as the native trap (the GP/EP DSP
  memory windows stay plain).
- **How it guards itself.** Every rewritten function is checked by undoing
  the rewrite and comparing, so a construct the script does not understand
  fails the build.
- **What it catches at run time.** If the APU window or the tiled aperture
  is ever written as plain memory, the runtime warns once
  (`wasm_unrouted_check`), which would mean an access the rewrite missed.

AC97 needs no rewrite. The native trap only makes a channel reset's RR bit
read back clear, and NFL 2K5's reset site already does that through the
`AC97_RESET_ACK` generated-code patch. On the web the trap is skipped with a
message instead of failing boot.

## The xboxrecomp patch

The submodule points at `BeyondTomrrow/xboxrecomp` (`nfl2k5-port`). Until its
changes are committed there and the submodule is bumped, they live in
`config/xboxrecomp-web.patch`. To regenerate the patch after editing the
submodule:

    git -C external/xboxrecomp add -A
    git -C external/xboxrecomp diff --cached > config/xboxrecomp-web.patch
    git -C external/xboxrecomp reset -q

(`--cached` so new files such as `platform/wasm_fixed.c` are included.)

Once the fork carries the changes, delete the patch and its step in
`tools/build-web.sh`.

## Known gaps (M2 and later)

These compile today but are inert or wrong at run time:

- **Aliasing.** There are no RAM mirrors and no tiled alias for *runtime*
  code that adds the memory offset to such an address by hand; generated
  code is covered by the fold. Nothing in NFL 2K5 is known to need this.
- **Audio has not been heard.** The APU routing is tested against a fake
  APU, and the layout init with the APU path runs under Node. The real
  DirectSound handshake can only be exercised once the game boots.
- **Renderer.** SDL_GPU 3.2.20 has no WebGPU backend, so `RECOMP_SDLGPU`
  finds no device and drawing stays on the software rasterizer.
- **Game files.** These need WasmFS on OPFS and a first-run disc import page.
  There is no HTML page yet: the build emits only `NFL2K5.js` and `.wasm`.
- **Presentation packages, FMV, mod-pack overlays, Discord.** These are off,
  as on Linux. Mod packs also run through `x86_interp`, whose memory accesses
  are not routed to the APU.
