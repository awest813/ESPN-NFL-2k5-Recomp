# ESPN NFL 2K5 Recomp

[![Build check](https://github.com/awest813/ESPN-NFL-2k5-Recomp/actions/workflows/build-check.yml/badge.svg?branch=main)](https://github.com/awest813/ESPN-NFL-2k5-Recomp/actions/workflows/build-check.yml?query=branch%3Amain)
[![GitHub Pages](https://github.com/awest813/ESPN-NFL-2k5-Recomp/actions/workflows/deploy-pages.yml/badge.svg?branch=main)](https://github.com/awest813/ESPN-NFL-2k5-Recomp/actions/workflows/deploy-pages.yml?query=branch%3Amain)

A community recompilation of the original Xbox version of **ESPN NFL 2K5**.
The browser preview runs on WebAssembly and WebGPU. The native Windows
build uses Direct3D 11. Both use game data from your own USA Xbox disc.

**[Open the browser launcher](https://awest813.github.io/ESPN-NFL-2k5-Recomp/)** · [Build for Windows](#build-for-windows) · [Report a problem](#report-a-problem)

## Play in your browser

1. Open the launcher in desktop Chrome with hardware acceleration enabled.
   The first visit may reload once to enable shared memory.
2. In **Game files**, select **Choose disc image** for a USA Xbox ISO/XISO
   or **Choose folder** for an extracted disc containing both
   `default.xbe` and `vc_53450030`. Allow several gigabytes of browser storage.
3. When the import completes, select **Play game**. Press a button on your
   controller, or click **Focus game** to use the keyboard.

The browser stores the imported disc locally. On the next visit in the
same browser profile, you can launch the game from that copy. Open
**Browser & diagnostics** to check WebAssembly, shared memory, storage, and
hardware graphics if the launcher cannot start the game.

### Controls

Press a button on a connected controller to make it visible to the browser.
Use **Controls → Test controller** to check buttons and axes. With the
keyboard, use **A** or **D** on Team Select to assign yourself to a side.

| Xbox input | Default keyboard control |
| --- | --- |
| Left stick / move | W, A, S, D |
| Right stick / look | I, J, K, L |
| D-pad / menus | Arrow keys |
| A, B, X, Y | Z, X, C, V |
| Start, Back | Enter, Backspace |
| Left and right triggers | Q, E |
| White, Black | R, F |
| Left and right stick clicks | T, G |

### Save, back up, and restore

Save and load from the original in-game menus. After saving, choose
**Exit to launcher**, then **Saves → Download backup**. To move your progress
to another browser or device, import the disc there and use
**Saves → Restore backup**. Backups include saves and settings. Restoring a
backup replaces files with matching names.

**Remove game files** keeps saves. Clearing the site's browser data removes
both the imported game and saves, so keep a downloaded backup.

### Compatibility and performance

- Quick Game has reached kickoff and scrimmage in retail browser tests.
  The audit also covers representative Franchise and Tournament saves,
  Practice drills, Situation, First Person Football, an ESPN 25th Anniversary
  challenge, and The Crib. [Game-mode audit](docs/WEB-GAME-MODES.md)
- The default **30 FPS lock** caps the maximum. The toolbar also offers
  **Uncapped**. Demanding scenes can still fall below 30 FPS or lose audio.
  [Performance results](docs/HANDOFF-PERF.md)
- Stadium and staff rendering still have outstanding reference checks.
  Xbox Live matchmaking is unavailable in the browser.
  [Rendering notes](docs/WEB-RENDERING-NOTES.md)

## Build for Windows

Use 64-bit Windows, Visual Studio 2022 with **Desktop development with C++**,
CMake, Ninja, Python 3, Git, and the x64 SDL3 development SDK. CI uses SDL
3.2.20. Build from a fresh recursive checkout of this fork.

```powershell
git clone --branch main --recurse-submodules https://github.com/awest813/ESPN-NFL-2k5-Recomp.git
cd ESPN-NFL-2k5-Recomp
git -c core.whitespace=cr-at-eol apply --ignore-space-change --directory=external/xboxrecomp config/xboxrecomp-web.patch
.\tools\get-webview2-sdk.ps1
$minizPath = "external/xemu-src/util/miniz"
New-Item -ItemType Directory -Force $minizPath | Out-Null
foreach ($file in "miniz.c", "miniz.h") {
    Invoke-WebRequest "https://raw.githubusercontent.com/xemu-project/xemu/master/util/miniz/$file" -OutFile "$minizPath/$file"
}
$env:NFL2K5_CMAKE_EXTRA = "-DCMAKE_PREFIX_PATH=C:/SDKs/SDL3"
.\tools\build.ps1 -Configuration Release -Game
```

Replace `C:/SDKs/SDL3` with your SDL3 installation directory. For a shared
SDL3 SDK, add its `bin` directory to `PATH`. Extract the full disc to
`original\disc` so that `original\disc\default.xbe` and
`original\disc\vc_53450030` are present. Run `build\Release\NFL2K5.exe`.

Press **F1** or **Back + Start** for native settings. Source builds keep
settings and saves in the project directory. Installed builds use
`%LOCALAPPDATA%\NFL2K5-PC`. Place `portable.txt` beside the `original`
folder to use local storage in an installed copy.

- [Build the Windows installer](installer/README.md) for guided disc extraction.
- [Install native mods](mods/README.md) or make a team with the [Team Creator](tools/team-creator/README.md).
- [Manage native save backups](docs/SAVE-LIBRARY.md), [broadcast packages](docs/PRESENTATION-SYSTEM.md), and [local music](docs/LOCAL-MUSIC.md).

## Build and test the web port

From a recursive checkout of `main`, activate **Emscripten 7.0.0** in a Bash
environment with Git, CMake, Ninja, curl, Python 3, and Node.js. The build
script applies the runtime patch when needed and builds SDL3 for WebAssembly.

```bash
bash tools/build-web.sh
python3 tools/serve-web.py
```

Open [the local launcher](http://127.0.0.1:8080/). The local site has its own
imported game and saves. Run `bash tools/test-web.sh` for the web checks.
Use `node tools/prepare-pages.mjs` to package the runtime for static hosting.
The Pages workflow builds and deploys browser changes from `main`.

[Web build and hosting guide](docs/WEB.md) · [Experimental Linux build](docs/LINUX.md)

## Report a problem

Include the platform, browser or Windows version, GPU, and input device.
For gameplay issues, include the mode, menu path, teams, stadium, and game
clock. Send **Browser & diagnostics → Download log** output or the relevant
Windows log. Keep disc images and personal saves private.
[Open an issue](https://github.com/awest813/ESPN-NFL-2k5-Recomp/issues/new)

## Credits and game files

This fork builds on [2K5Remade](https://github.com/BeyondTomrrow/2K5Remade)
and [xboxrecomp](https://github.com/BeyondTomrrow/xboxrecomp). The installer
uses extract-xiso. The optional mod tools use codecs from
[2K Football Mod Tools](https://github.com/cruuz/2k-football-mod-tools).
Button prompts are by Kenney. [Third-party notices](docs/third-party/)

The project distributes the recompilation and launcher. Supply the original
game files from your own disc. This independent community project has no
affiliation with Sega, Visual Concepts, 2K, ESPN, or the NFL.
