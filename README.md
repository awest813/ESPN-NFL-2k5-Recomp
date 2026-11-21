# ESPN NFL 2K5 Recomp

[![Build check](https://github.com/awest813/ESPN-NFL-2k5-Recomp/actions/workflows/build-check.yml/badge.svg?branch=main)](https://github.com/awest813/ESPN-NFL-2k5-Recomp/actions/workflows/build-check.yml?query=branch%3Amain)
[![GitHub Pages](https://github.com/awest813/ESPN-NFL-2k5-Recomp/actions/workflows/deploy-pages.yml/badge.svg?branch=main)](https://github.com/awest813/ESPN-NFL-2k5-Recomp/actions/workflows/deploy-pages.yml?query=branch%3Amain)

A community recompilation of the original Xbox version of ESPN NFL 2K5. It
runs as a native Windows program or in a browser via WebAssembly and WebGPU.
Bring your own USA Xbox disc image or extracted game folder. The project
distributes the launcher and recompilation. Retail game files come from your
own disc.

**[Play in your browser](https://awest813.github.io/ESPN-NFL-2k5-Recomp/)** ·
**[Build for Windows](#windows)** · **[Report an issue](https://github.com/awest813/ESPN-NFL-2k5-Recomp/issues/new)**

## Play in a browser

1. Open the [web launcher](https://awest813.github.io/ESPN-NFL-2k5-Recomp/)
   in a desktop browser with WebGPU, such as Chrome. On the first visit, the
   page may reload once to enable shared memory.
2. Choose your Xbox ISO/XISO or an extracted folder containing `default.xbe`
   and `vc_53450030`. Allow several gigabytes of local browser storage. Wait
   for the launcher to finish checking the disc.
3. Click **Play game**. Press a controller button to connect it, or click the
   game to use your keyboard. **Enter** is Start, **Z** is A, **X** is B, and
   the arrow keys navigate menus. The launcher lists the other bindings.

Save and load through the original in-game menus. After saving, choose
**Exit to launcher** and download a backup from **Saves**. You can restore
that backup in another browser or on another device. The disc and saves stay
in your browser profile. Removing the imported game preserves saves, while
clearing browser site data removes both.

The game toolbar has fullscreen, keyboard focus, and the frame-rate cap.
**30 FPS lock** is the default cap. **Uncapped** is available in the same
menu. The WebGPU readout shows the measured rate over the last reporting
window. Demanding scenes can run below 30 FPS, and audio can drop out.
Quick Game has been verified through kickoff and scrimmage. The mode audit
tracks the remaining failures and unverified paths.
[Game-mode audit](docs/WEB-GAME-MODES.md) · [Performance measurements](docs/HANDOFF-PERF.md)

## Windows

The native build uses Direct3D 11. You need 64-bit Windows, Visual Studio 2022
with the C++ desktop workload, CMake, Ninja, Python 3, and an x64 SDL3
development SDK. CI uses SDL 3.2.20. Windows builds for this fork are currently
built from source.

```powershell
git clone --branch main --recurse-submodules https://github.com/awest813/ESPN-NFL-2k5-Recomp.git
cd ESPN-NFL-2k5-Recomp
git -c core.whitespace=cr-at-eol apply --ignore-space-change --directory=external/xboxrecomp config/xboxrecomp-web.patch
$env:NFL2K5_CMAKE_EXTRA = "-DCMAKE_PREFIX_PATH=C:/SDKs/SDL3"
.\tools\build.ps1 -Configuration Release -Game
```

Replace the SDL3 path with your SDK's installation directory. The patch
command is for a fresh checkout. The browser build script also applies the
patch and detects an already patched runtime.

Extract the complete disc into `original\disc`, then run
`build\Release\NFL2K5.exe`. If using a shared SDL SDK, make its `bin` directory
available on `PATH`. Settings, caches, logs, and saves use
`%LOCALAPPDATA%\NFL2K5-PC` by default. Add `portable.txt` beside the
`original` folder to keep them in the game directory. For ISO/XISO
extraction during setup, build the Windows installer.
[Installer instructions](installer/README.md)

Press **F1** or **Back + Start** for video settings, controller remapping,
dead zones, button prompts, and save backup preferences. The native port
also supports historical and custom teams in exhibition modes, texture
packs, native mod packages, and configurable broadcast presentations.
Select an installed native mod in **Extras > Mods** and a broadcast package
under **Coach Match Up > Presentation**.

- [Mods and installation](mods/README.md)
- [Team Creator](tools/team-creator/README.md)
- [Save imports and backups](docs/SAVE-LIBRARY.md)
- [Broadcast presentations](docs/PRESENTATION-SYSTEM.md)
- [Local music](docs/LOCAL-MUSIC.md)

## Build the browser version locally

With Emscripten 7.0.0 activated and Git, CMake, Ninja, curl, Python 3, and Node.js
available, run the following from a recursive checkout of `main`.

```bash
tools/build-web.sh
python3 tools/serve-web.py
```

Open [localhost:8080](http://127.0.0.1:8080/). This local origin has its own game
library and saves. The tests run with `tools/test-web.sh`. Run
`node tools/prepare-pages.mjs` to package the launcher and runtime for static
hosting. The Pages workflow builds, tests, and deploys `main`.
[Browser build and hosting details](docs/WEB.md) · [Experimental Linux build](docs/LINUX.md)

## Report a problem

Include your platform, browser or Windows version, GPU, and controller. For
gameplay issues, include the menu path, teams, stadium, and game clock.
Download the browser log under **Diagnostics**, or attach the relevant
Windows log. Keep retail game files and personal saves out of the report.
[Open an issue](https://github.com/awest813/ESPN-NFL-2k5-Recomp/issues/new)

## Credits

This fork builds on [2K5Remade](https://github.com/BeyondTomrrow/2K5Remade)
and [xboxrecomp](https://github.com/BeyondTomrrow/xboxrecomp). The installer
uses extract-xiso. The optional mod tools use codecs from
[2K Football Mod Tools](https://github.com/cruuz/2k-football-mod-tools).
Button prompts are by Kenney. See [third-party notices](docs/third-party/)
for licenses and attribution.

This independent community project has no affiliation with Sega, Visual
Concepts, 2K, ESPN, the NFL, or the associated broadcasters.
