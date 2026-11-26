# Runtime architecture

ESPN NFL 2K5 Recomp builds the translated Xbox game into a host executable or WebAssembly module. The runtime verifies and opens the player's retail disc files locally. The repository carries the C translation, compatibility code, build tools, and community add-ons.

## From Xbox code to a game session

| Layer | Location | Responsibility |
| --- | --- | --- |
| Guest translation | [`src/recomp/gen/`](../src/recomp/gen) | Checked-in C chunks store the translated retail game and dispatch metadata. |
| Persistent fixes | [`tools/apply-gen-patches.py`](../tools/apply-gen-patches.py), [`src/recomp_manual.c`](../src/recomp_manual.c) | Preserve verified control-flow and runtime corrections across rebuilds. |
| Boot and platform integration | [`src/main.c`](../src/main.c), [`config/game.cmake`](../config/game.cmake), [`src/platform/`](../src/platform) | Verify disc identity, select the host, initialize guest memory, and start the game. |
| Xbox runtime | [`external/xboxrecomp/`](../external/xboxrecomp), [published patch](../config/xboxrecomp-web.patch) | Implement Xbox kernel, file, input, graphics, APU, and scheduling behavior on the host. |
| Browser launcher | [`web/`](../web) | Check browser capabilities, import disc files into OPFS, restore backups, start the worker-based runtime, and show controls and diagnostics. |

## Platform rendering and storage

- Windows uses the native D3D11 path. Source and installed builds resolve their user data as described in the [Windows guide](../README.md#build-for-windows).
- Linux builds the POSIX runtime and can enable its SDL3 GPU path. [Linux build and launch](LINUX.md)
- The browser uses Emscripten workers, WasmFS, and WebGPU. The launcher and Wasm runtime share origin-private disc and save files. Use the web guide for the memory map, APU register dispatch, and hosting architecture. [Browser implementation](WEB.md)

Native build instructions use the checked-in retail C. The local analysis pipeline is useful when regenerating code or inspecting a different executable. Regeneration decisions must preserve the reviewed retail integration and its range-table inputs. [Early XBE and boot notes](bringup.md)

[Project status and documentation index](../PROJECT_STATUS.md)
