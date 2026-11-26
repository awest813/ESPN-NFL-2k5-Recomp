# Native DSP regression and timing checks

These targets run the existing production-core fixtures as native executables.
They require no game assets, SDL, browser, or emulator. They cover cached DSP
dispatch versus the reference dispatcher, full-state cold/warm equivalence,
interrupt retirement, executable uploads, firmware execution and scratch/FIFO DMA.

## Run the Windows checks

From an MSVC developer prompt at the repo root:

```powershell
cmake -S tests/native-dsp -B build/native-dsp -G "Visual Studio 17 2022" -A x64
cmake --build build/native-dsp --config Release --parallel
ctest --test-dir build/native-dsp -C Release --output-on-failure
build/native-dsp/Release/dsp_dispatch.exe --benchmark
```

## Run the Linux checks

```bash
cmake -S tests/native-dsp -B build/native-dsp-linux -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/native-dsp-linux --parallel
ctest --test-dir build/native-dsp-linux --output-on-failure
./build/native-dsp-linux/dsp_dispatch --benchmark
```

## Interpret timing

Assertions remain enabled in optimized builds. Windows timing uses `QueryPerformanceCounter`. Web timing uses `emscripten_get_now`.

The optional benchmark alternates reference/current execution order across five
rounds of two million instructions for each of two synthetic programs, checking
state equality after each pair. Its numbers diagnose this instruction mix only;
they do not establish retail APU throughput, scheduling latency or gameplay FPS.
The reference is the older dispatcher, not a previous game binary. CI runs the
state checks without a timing threshold.

[Native verification checkpoints](../../docs/HANDOFF-PERF.md#current-native-verification-checkpoint-2026-11-20)
