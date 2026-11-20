# Native DSP regression and timing checks

These targets run the existing production-core fixtures as native executables.
They require no game assets, SDL, browser, or emulator. They cover cached DSP
dispatch versus the reference dispatcher, full-state cold/warm equivalence,
interrupt retirement, executable uploads, firmware execution and scratch/FIFO DMA.

From an MSVC developer prompt:

```powershell
cmake -S tests/native-dsp -B build/native-dsp -G "Visual Studio 17 2022" -A x64
cmake --build build/native-dsp --config Release --parallel
ctest --test-dir build/native-dsp -C Release --output-on-failure
build/native-dsp/Release/dsp_dispatch.exe --benchmark
```

With a single-configuration native generator, use `-DCMAKE_BUILD_TYPE=Release`
and run `dsp_dispatch` directly from the build directory. Assertions remain
enabled in optimized builds. Windows timing uses QueryPerformanceCounter;
Web timing continues to use emscripten_get_now.

The optional benchmark alternates reference/current execution order across five
rounds of two million instructions for each of two synthetic programs, checking
state equality after each pair. Its numbers diagnose this instruction mix only;
they do not establish retail APU throughput, scheduling latency or gameplay FPS.
The reference is the older dispatcher, not a previous game binary. CI runs the
state checks without a timing threshold.
