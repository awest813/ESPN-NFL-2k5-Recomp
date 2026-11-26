# Build and run on Linux

The Linux target builds a native executable using GCC and SDL3. CI builds the Linux runtime and tests native components. Full retail play on Linux remains experimental.

## Build

Install Git, a C/C++ compiler, CMake, Ninja, Python 3, curl, the SDL3 development package, OpenSSL development headers, and libepoxy. For SDL3 GPU rendering, install a Vulkan driver and `glslangValidator`. Install glslang development libraries as well to build the shader translation path.

```bash
git clone --branch main --recurse-submodules https://github.com/awest813/ESPN-NFL-2k5-Recomp.git
cd ESPN-NFL-2k5-Recomp
git -c core.whitespace=cr-at-eol apply --ignore-space-change --directory=external/xboxrecomp config/xboxrecomp-web.patch
mkdir -p external/xemu-src/util/miniz
for file in miniz.c miniz.h; do
  curl -fL -o "external/xemu-src/util/miniz/$file" "https://raw.githubusercontent.com/xemu-project/xemu/master/util/miniz/$file"
done

cmake -S . -B build-linux-game -G Ninja -DCMAKE_BUILD_TYPE=Release -DNFL2K5_BUILD_GAME=ON
cmake --build build-linux-game --parallel 4
```

Use `-DCMAKE_PREFIX_PATH=/path/to/sdl3-sdk` if SDL3 is installed outside the usual search paths. The checked-in generated C is about 220 MB. Lower the parallel job count if the compiler runs out of memory. `NFL2K5_LINUX_OPT` defaults to `2` and can be set to `0` for debugging.

## Launch

Put the extracted USA Xbox disc under `original/disc/` with `default.xbe` and `vc_53450030/` at its root. [Disc layout](../original/README.md)

```bash
bash tools/run-linux.sh
RECOMP_SDLGPU=1 bash tools/run-linux.sh
```

The second command enables the SDL3 GPU route when built. `SDL_VIDEO_DRIVER=wayland` or `SDL_VIDEO_DRIVER=x11` selects a video backend. The wrapper raises the stack limit and uses `build-linux-game/NFL2K5` by default. Set `NFL2K5_EXE` to run a different build. Logs go to the terminal.

## Compatibility and debugging

- The four `NFL2K5_FORCE_UNBLOCK_*` switches default to ON. Check the CMake cache if an older build still waits in XNetStartup. The switches end in `AUDIO_LOCK`, `33660_DRAIN`, `NETPOLL`, and `STATE9_READY`.
- The POSIX compatibility layer supplies the Win32 calls used by common game code. [Platform source](../src/platform/posix)
- Windows broadcast packages, the Windows exception reporter, and DDS override support are platform-specific. Linux retains the original presentation. Treat Windows mod-pack instructions as Windows-specific.
- Use `-DNFL2K5_BUILD_GAME=OFF` for a runtime-only compile. Native component tests can run with local disc data absent. [Guest-memory tests](../tests/guest_memory_posix/README.md) · [DSP tests](../tests/native-dsp/README.md)

[Project status](../PROJECT_STATUS.md)
