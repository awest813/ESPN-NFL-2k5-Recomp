"""Compare prepared GPU input streams with the original checked fetch path."""
from pathlib import Path
import shutil
import subprocess


def main():
    root = Path(__file__).resolve().parents[2]
    kernel = root / "external/xboxrecomp/src/kernel"
    core = (kernel / "nv2a_pb_exec.c").read_text(encoding="utf-8")
    live = core[core.index("static size_t vertex_attr_bytes("):core.index("static uint32_t surface_bpp(")]
    xf = (kernel / "sdlgpu/sdlgpu_xf.inc.c").read_text(encoding="utf-8")
    prepared = xf[xf.index("static void sg_vp_prepare_inputs("):xf.index("/* RECOMP_SDLGPU_NOVP")]
    reference = (Path(__file__).parent / "fixtures/vertex_fetch_reference.inc.c").read_text(encoding="utf-8")
    harness = r'''
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define NV_VERTEX_ATTRS 16
typedef struct { uint32_t offset, type, size, stride; } VertexAttr;
static struct { VertexAttr attr[16]; int inline_active; unsigned inline_count; void *inline_buf; } s_gpu;
static float s_attr_inline[16][4];
static struct { unsigned inmask; uint8_t active[16], active_count; struct { const uint8_t *base; float value[4]; int constant; } attr[16]; } s_sgvp;
static uint8_t memory[65536], inline_memory[8192];
static void *xbox_GetMemoryOffset(void) { return memory; }
static bool xbox_guest_memory_direct(uintptr_t base, uint64_t address, size_t bytes, bool writable) {
    return address >= 16 && address < sizeof memory && bytes <= sizeof memory - address;
}
static bool xbox_guest_memory_read(uintptr_t base, uint64_t address, void *dst, size_t bytes) {
    if (!xbox_guest_memory_direct(base, address, bytes, false)) return false;
    memcpy(dst, (const void *)(base + address), bytes); return true;
}
/* LIVE_FETCH */
/* REFERENCE_FETCH */
/* PREPARED_FETCH */
static uint32_t seed = 0x73519fab;
static uint32_t rng(void) { seed ^= seed << 13; seed ^= seed >> 17; seed ^= seed << 5; return seed; }
int main(void) {
    for (unsigned i = 0; i < sizeof memory; i++) memory[i] = rng();
    for (unsigned i = 0; i < sizeof inline_memory; i++) inline_memory[i] = rng();
    for (unsigned i = 0; i < 16; i++) for (unsigned k = 0; k < 4; k++) s_attr_inline[i][k] = (float)(i + k);
    s_sgvp.inmask = 1u << 3;
    for (unsigned trial = 0; trial < 10000; trial++) {
        s_sgvp.inmask = (rng() & 0xffffu) | (1u << 3);
        VertexAttr *a = &s_gpu.attr[3];
        a->type = rng() % 8; a->size = rng() % 7; a->stride = (unsigned[]){0,7,16,32}[rng() % 4];
        a->offset = (unsigned[]){0,16,53,2048,65000,0xfffffff0u}[rng() % 6];
        s_gpu.inline_active = rng() & 1; s_gpu.inline_count = rng() % 2049; s_gpu.inline_buf = inline_memory;
        sg_vp_prepare_inputs(63);
        unsigned count=0;
        for (unsigned slot=0;slot<16;slot++) if (s_sgvp.inmask & (1u<<slot)) assert(s_sgvp.active[count++]==slot);
        assert(count==s_sgvp.active_count);
        for (unsigned index = 0; index < 64; index++) {
            float expected[4], actual[4], checked[4];
            reference_fetch_attr(a, index, expected);
            fetch_attr(a, index, checked);
            sg_vp_fetch_input(3, index, actual);
            if (memcmp(expected, actual, 16) || memcmp(expected, checked, 16)) {
                fprintf(stderr, "FAIL trial %u index %u type %u size %u stride %u offset %08x inline %d\n",
                        trial, index, a->type, a->size, a->stride, a->offset, s_gpu.inline_active); return 1;
            }
        }
    }
    puts("PASS 640000 vertex fetches, all formats, constants, inline arrays and invalid ranges");
    return 0;
}
'''
    text = harness.replace("/* LIVE_FETCH */", live).replace("/* REFERENCE_FETCH */", reference.replace("fetch_attr(", "reference_fetch_attr("))
    text = text.replace("/* PREPARED_FETCH */", prepared)
    build = root / "build-web-tests/vertex-fetch"
    build.mkdir(parents=True, exist_ok=True)
    source, output = build / "test.c", build / "test.js"
    source.write_text(text, encoding="utf-8")
    emcc, node = shutil.which("emcc"), shutil.which("node")
    if not emcc or not node:
        raise SystemExit("Emscripten emcc and Node must be on PATH")
    subprocess.run([emcc, str(source), "-O3", "-msimd128", "-sENVIRONMENT=node", "-o", str(output)], check=True)
    subprocess.run([node, str(output)], check=True)


if __name__ == "__main__":
    main()
