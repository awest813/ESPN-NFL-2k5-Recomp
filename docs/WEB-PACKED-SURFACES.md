# Packed render-target investigation

**Historical record.** The evidence traces RGB565/ARGB1555 surface ownership and lists the hardware cases used to evaluate candidate fixes.

[Current guide](WEB-STADIUM-FIDELITY.md) · [Documentation index](../PROJECT_STATUS.md)

Recorded November 20, 2026 against `bbcab2d`.

The RGB565 clear and fragment-merge fixes are published. Their regression
results and bounded retail replay are recorded in
[the rendering ledger](WEB-STADIUM-FIDELITY.md#rgb565-software-clears-and-fragment-merging-2026-11-20).
This follow-up identifies remaining format gaps; it adds no renderer behavior.

## Confirmed source gaps

In `external/xboxrecomp/src/kernel/nv2a_pb_exec.c`, `surface_bpp()` correctly
identifies formats `0x01`, `0x02`, `0x03` and `0x0A` as two-byte targets.
However, `put_pixel()` packs every two-byte target as RGB565. Only format
`0x03` enters the new packed clear and fragment-merge paths.

Formats `0x01` (`X1R5G5B5_Z1R5G5B5`) and `0x02`
(`X1R5G5B5_O1R5G5B5`) require five-bit red, green and blue fields, rather
than RGB565's six-bit green. Format `0x0A` (`G8B8`) needs a separate
conversion and support audit. Correct byte size alone does not establish
support for these formats. No captured NFL 2K5 scene has yet been shown to
exercise these particular targets.

## Hardware evidence for the next change

The reference is the
[nxdk hardware-test source](https://github.com/abaire/nxdk_pgraph_tests/blob/58285192866354730dd9450ef066d6209ac0c553/src/tests/blend_surface_tests.cpp)
and its separately published Xbox golden images. `TestDstAlpha` first fills
a target with eight background color/alpha combinations, then blends white
with source factor `DST_ALPHA` and destination factor `ZERO`. It displays
each result twice: the upper half uses the sampled texture alpha; the lower
half forces the final display alpha to one.

In the inspected
[Z1 golden image](https://github.com/abaire/nxdk_pgraph_tests_golden_results/blob/a822689507cce8e8de54d9e170c9369c1a0c7566/results/Blend_surface/DstAlpha_X_Z1RGB5.png),
the lower halves are white and the upper halves remain transparent. In the
[O1 golden image](https://github.com/abaire/nxdk_pgraph_tests_golden_results/blob/a822689507cce8e8de54d9e170c9369c1a0c7566/results/Blend_surface/DstAlpha_X_O1RGB5.png),
both halves are white. The inference from the test and images is that
destination-alpha blending sees one for both X1 variants, while subsequent
texture sampling distinguishes the stored zero/one high bit. Treating the
stored X bit as destination blend alpha would therefore give the wrong
result for the Z1 case.

The corresponding
[surface-format test](https://github.com/abaire/nxdk_pgraph_tests/blob/58285192866354730dd9450ef066d6209ac0c553/src/tests/surface_format_tests.cpp)
and its Z1/O1 golden images were also inspected. These are image-based
observations, not a raw framebuffer-bit capture or an exact rounding oracle.
Local reference copies are in the ignored
`build-web-tests/packed555-hardware` directory.

## Open question and acceptance criteria

The inspected tests do not establish how partial color-write masks interact
with the forced high bit. The separate `color_mask_blend_tests.cpp` fixture
does not select these packed surface formats. In particular, alpha-disabled
RGB writes and alpha-only writes still need evidence. A blanket extension of
the RGB565 path would silently choose unverified behavior here.

The next implementation should distinguish storage conversion, destination
blend alpha and source fragment alpha. It needs independent packed-bit
checks for both variants, all write masks, clears, clipped/padded bounds and
source/destination alpha factors, while retaining the RGB565 and 32-bit
regressions. Hardware precision and dithering remain separate questions.
Broader stadium/staff fidelity, full audio continuity, all-mode coverage and
a sustained 30 FPS floor remain unproven.
