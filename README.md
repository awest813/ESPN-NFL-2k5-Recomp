# ESPN NFL 2K5 Recomp

[![Build check](https://github.com/awest813/ESPN-NFL-2k5-Recomp/actions/workflows/build-check.yml/badge.svg?branch=main)](https://github.com/awest813/ESPN-NFL-2k5-Recomp/actions/workflows/build-check.yml?query=branch%3Amain)
[![GitHub Pages](https://github.com/awest813/ESPN-NFL-2k5-Recomp/actions/workflows/deploy-pages.yml/badge.svg?branch=main)](https://github.com/awest813/ESPN-NFL-2k5-Recomp/actions/workflows/deploy-pages.yml?query=branch%3Amain)

This community project recompiles the USA Xbox release of **ESPN NFL 2K5** for Windows and the web. The Windows build uses Direct3D 11. The browser preview uses WebAssembly and WebGPU. Both require game files from your own USA Xbox disc.

**[Play in your browser](https://awest813.github.io/ESPN-NFL-2k5-Recomp/)** · [Build for Windows](#build-for-windows) · [Project status](#project-status)

## Get on the field

1. Open the launcher in desktop Chrome with hardware acceleration enabled. The page may reload once on your first visit to enable shared memory.
2. Under **Game files**, choose a USA Xbox ISO or XISO, or choose the extracted disc folder containing both `default.xbe` and `vc_53450030`. Allow several gigabytes for the browser's local copy.
3. Select **Play game** after import. Press any controller button to let the browser detect it, or use **Focus game** for keyboard input. If **Enable game sound** appears, select it to start audio.

Import once per browser profile and site address. The disc and saves stay in that browser's local storage. If **Play game** stays disabled, open **Browser & diagnostics** and check the game files, runtime, shared memory, and hardware graphics entries.

### Controls

Use **Controls → Test controller** in the launcher to check buttons, triggers, and sticks before starting. On Team Select, move the left stick to assign a controller to a side. On the keyboard, use **A** or **D**.

| Xbox control | Default keys |
| --- | --- |
| Left stick | W, A, S, D |
| Right stick | I, J, K, L |
| D-pad | Arrow keys |
| A / B / X / Y | Z / X / C / V |
| Start / Back | Enter / Backspace |
| Left / right trigger | Q / E |
| White / Black | R / F |
| Left / right stick click | T / G |

### Keep your saves

- Save and load through the game's menus. Finish saving before choosing **Exit to launcher**.
- To move progress to another browser or device, use **Saves → Download backup**, then **Saves → Restore backup** in the destination launcher. The backup contains saves and settings. Restore replaces files with matching names and keeps other files.
- **Remove game files** keeps saves. Clearing the site's browser data removes both saves and imported game files. **Keep storage on this device** asks the browser to retain the site's data.

### NFL 2027 Week 1 roster and franchise

1. Download the [NFL 2027 Week 1 browser backup](mods/saves/NFL2027Week1-Browser.json) and import it with **Saves → Restore backup** in the launcher.
2. In the game, open **Options → Load/Save → Load**. Choose `NFL27Ros` for the exhibition roster or `NFL27Fra` to open the Week 1 franchise.

Roster and franchise by the NFL2K5 Modding Community, including LostsouL, BAD_AL, egb11, seskid, and djsteveo627.

## Project status

| Area | What has been verified |
| --- | --- |
| Gameplay | Retail browser tests reached kickoff and scrimmage in Quick Game and exercised Franchise, Tournament, Practice, Situation, First Person Football, the Ice Bowl challenge, and The Crib. Coverage is recorded by mode in the [game-mode audit](docs/WEB-GAME-MODES.md). |
| Rendering | Retail checks cover stadium flyovers, intro titles, players, and selected sideline scenes. Reference comparisons for more stadiums and staff models are pending. See the [stadium fidelity notes](docs/WEB-STADIUM-FIDELITY.md). |
| Performance and audio | **30 FPS lock** is the default maximum. Select **Uncapped** in the launcher or in-game toolbar to lift it. Heavy scenes can still dip below 30 FPS, and recent startup captures recorded audio underruns. See the [performance measurements](docs/HANDOFF-PERF.md). |
| Online play | Xbox Live matchmaking is unavailable in the browser. |

## Build for Windows

Use 64-bit Windows, Visual Studio 2022 with **Desktop development with C++**, CMake, Ninja, Python 3, Git, and the x64 SDL3 development SDK. CI builds against SDL 3.2.20. Start with a fresh checkout and replace `C:/SDKs/SDL3` with the path to your SDK.

```powershell
git clone --branch main --recurse-submodules https://github.com/awest813/ESPN-NFL-2k5-Recomp.git
cd ESPN-NFL-2k5-Recomp
git -c core.whitespace=cr-at-eol apply --ignore-space-change --directory=external/xboxrecomp config/xboxrecomp-web.patch
.\tools\get-webview2-sdk.ps1
$minizPath = 'external/xemu-src/util/miniz'
New-Item -ItemType Directory -Force $minizPath | Out-Null
foreach ($file in 'miniz.c', 'miniz.h') {
    Invoke-WebRequest "https://raw.githubusercontent.com/xemu-project/xemu/master/util/miniz/$file" -OutFile "$minizPath/$file"
}
$env:NFL2K5_CMAKE_EXTRA = '-DCMAKE_PREFIX_PATH=C:/SDKs/SDL3'
.\tools\build.ps1 -Configuration Release -Game
```

Extract the full disc to `original\disc` and check that `original\disc\default.xbe` and `original\disc\vc_53450030` are present. If you use a shared SDL3 SDK, add its `bin` directory to `PATH`. Run `build\Release\NFL2K5.exe`.

Press **F1** or **Back + Start** for native settings. Source builds keep saves and settings in the project directory. Installed builds use `%LOCALAPPDATA%\NFL2K5-PC` by default. To keep them with an installed copy, place `portable.txt` beside its `original` folder.

- [Build the installer](installer/README.md) for guided disc extraction.
- [Install mods](mods/README.md), [create a team](tools/team-creator/README.md), or [set up broadcast presentations](docs/PRESENTATION-SYSTEM.md).
- [Manage Windows save backups](docs/SAVE-LIBRARY.md) or [add local music](docs/LOCAL-MUSIC.md).
- [Build the experimental Linux target](docs/LINUX.md).

## Build the browser preview

Start from the same recursive checkout. In Bash, activate Emscripten **7.0.0** and have Git, CMake, Ninja, curl, Python 3, and Node.js available. The build script fetches the dependencies and applies the runtime patch when needed.

```bash
bash tools/build-web.sh
python3 tools/serve-web.py
```

Open the [local launcher](http://127.0.0.1:8080/). Localhost and GitHub Pages use separate browser storage. Use a launcher backup to move saves between them.

Run `bash tools/test-web.sh` for web tests. Run `node tools/prepare-pages.mjs` to create the static package in `dist-pages/`. The GitHub Pages workflow builds, tests, and publishes changes to the web launcher and runtime from `main`. See the [web build and hosting guide](docs/WEB.md).

## Report a problem

Include your browser or Windows version, GPU, and input device. For gameplay issues, add the mode, menu path, teams, stadium, and game clock or the last action before the issue. On the web, attach the log from **Browser & diagnostics → Download log**. On Windows, attach the relevant runtime log. Keep disc images and personal saves private. [Open an issue](https://github.com/awest813/ESPN-NFL-2k5-Recomp/issues/new)

## Credits

This fork builds on 2K5Remade and xboxrecomp. The installer uses extract-xiso, optional mod tools use codecs from 2K Football Mod Tools, and controller prompts are by Kenney. [2K5Remade](https://github.com/BeyondTomrrow/2K5Remade) · [xboxrecomp](https://github.com/BeyondTomrrow/xboxrecomp) · [Third-party notices](docs/third-party/)

Game files come from your own disc. This independent community project is unaffiliated with Sega, Visual Concepts, 2K, ESPN, and the NFL.
