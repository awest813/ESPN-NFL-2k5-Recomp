"""Compare prepared CPU/GPU input streams with the original checked fetch path."""
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
    prepared += xf[xf.index("static uint32_t sg_vp_vertex("):xf.index("/* Draw the batch with its vertex program")]
    cpu = core[core.index("static uint32_t s_xf_input_mask"):core.index("static const XfVert *vp_vertex(")]
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
static struct { VertexAttr attr[16]; int inline_active; unsigned inline_count; void *inline_buf; uint16_t idx[64]; uint32_t idx_count; } s_gpu;
static float s_attr_inline[16][4];
/* VERTEX_INPUTS_TYPE */
static struct { unsigned inmask; VertexInputs inputs; float *in; uint32_t input_stride, linear_first, nv, gen, map[65536], map_gen[65536]; int linear; } s_sgvp;
static float packed_input[64*16*4];
static uint8_t memory[65536], inline_memory[8192];
static unsigned checked_reads;
static void *xbox_GetMemoryOffset(void) { return memory; }
static bool xbox_guest_memory_direct(uintptr_t base, uint64_t address, size_t bytes, bool writable) {
    return address >= 16 && address < sizeof memory && bytes <= sizeof memory - address;
}
static bool xbox_guest_memory_read(uintptr_t base, uint64_t address, void *dst, size_t bytes) {
    checked_reads++;
    if (!xbox_guest_memory_direct(base, address, bytes, false)) return false;
    memcpy(dst, (const void *)(base + address), bytes); return true;
}
/* LIVE_FETCH */
/* REFERENCE_FETCH */
/* PREPARED_FETCH */
static struct { unsigned start; } s_vp;
static uint32_t s_xf_gen=1, s_xf_stamp[65536], test_input_mask, prepare_calls;
static void vp_prepare_program(void) { prepare_calls++; }
static uint32_t vp_input_mask(uint32_t start) { return test_input_mask; }
/* CPU_FETCH */
static uint32_t seed = 0x73519fab;
static uint32_t rng(void) { seed ^= seed << 13; seed ^= seed >> 17; seed ^= seed << 5; return seed; }
int main(void) {
    for (unsigned i = 0; i < sizeof memory; i++) memory[i] = rng();
    for (unsigned i = 0; i < sizeof inline_memory; i++) inline_memory[i] = rng();
    for (unsigned i = 0; i < 16; i++) for (unsigned k = 0; k < 4; k++) s_attr_inline[i][k] = (float)(i + k);
    // A complete float stream is validated once for the actual CPU batch;
    // a stream crossing the mapping boundary must retain per-index fallback.
    test_input_mask=1u<<3;s_gpu.idx_count=2;s_gpu.idx[0]=63;s_gpu.idx[1]=0;
    s_gpu.attr[3]=(VertexAttr){256,2,4,16};
    vp_begin_batch();
    assert(s_xf_inputs.attr[3].base==memory+256);
    unsigned reads_before=checked_reads;
    for(unsigned i=0;i<64;i++){float v[16][4];vp_fetch_inputs(i,v);assert(!memcmp(v[3],memory+256+i*16,16));}
    assert(checked_reads==reads_before);
    s_gpu.attr[3].offset=65504;vp_begin_batch();assert(!s_xf_inputs.attr[3].base);
    for(unsigned i=0;i<64;i++) {
        float v[16][4],expected[4];
        unsigned before=checked_reads;vp_fetch_inputs(i,v);assert(checked_reads==before+1);
        reference_fetch_attr(&s_gpu.attr[3],i,expected);assert(!memcmp(v[3],expected,16));
    }
    // Empty masks fetch no attributes; 16-bit maximum indices cannot wrap
    // validation into a smaller range. Zero-stride constants refresh per batch.
    test_input_mask=0;vp_begin_batch();assert(!s_xf_inputs.active_count);
    float untouched[16][4];memset(untouched,0x5a,sizeof untouched);vp_fetch_inputs(0,untouched);
    for(unsigned i=0;i<sizeof untouched;i++)assert(((uint8_t*)untouched)[i]==0x5a);
    test_input_mask=1u<<3;s_gpu.idx[0]=65535;vp_begin_batch();assert(!s_xf_inputs.attr[3].base);
    s_gpu.idx[0]=63;s_gpu.attr[3]=(VertexAttr){256,2,4,0};
    for(unsigned batch=0;batch<2;batch++) {
        float value[4]={(float)batch,2,3,4},out[16][4];memcpy(memory+256,value,16);
        vp_begin_batch();vp_fetch_inputs(63,out);assert(!memcmp(value,out[3],16));
    }
    s_gpu.attr[3]=(VertexAttr){0};
    s_sgvp.inmask = 1u << 3;
    for (unsigned trial = 0; trial < 10000; trial++) {
        s_sgvp.inmask = (rng() & 0xffffu) | (1u << 3);
        VertexAttr *a = &s_gpu.attr[3];
        a->type = rng() % 8; a->size = rng() % 7; a->stride = (unsigned[]){0,7,16,32}[rng() % 4];
        a->offset = (unsigned[]){0,16,53,2048,65000,0xfffffff0u}[rng() % 6];
        s_gpu.inline_active = rng() & 1; s_gpu.inline_count = rng() % 2049; s_gpu.inline_buf = inline_memory;
        sg_vp_prepare_inputs(63);
        test_input_mask=s_sgvp.inmask;
        s_gpu.idx_count=64;
        for(unsigned i=0;i<64;i++)s_gpu.idx[i]=(uint16_t)(63-i);
        unsigned calls_before=prepare_calls;
        if(trial==0){s_xf_gen=UINT32_MAX;memset(s_xf_stamp,0xff,sizeof s_xf_stamp);}
        vp_begin_batch();
        assert(prepare_calls==calls_before+1);
        if(trial==0){assert(s_xf_gen==1);for(unsigned i=0;i<65536;i++)assert(!s_xf_stamp[i]);}
        for(unsigned index=0;index<64;index++) {
            float inputs[16][4];
            for(unsigned a=0;a<16;a++)for(unsigned k=0;k<4;k++)inputs[a][k]=-1234.0f;
            vp_fetch_inputs(index,inputs);
            for(unsigned a=0;a<16;a++) {
                float expected[4];
                if(test_input_mask&(1u<<a))reference_fetch_attr(&s_gpu.attr[a],index,expected);
                else for(unsigned k=0;k<4;k++)expected[k]=-1234.0f;
                assert(!memcmp(expected,inputs[a],16));
            }
        }
        unsigned count=0;
        for (unsigned slot=0;slot<16;slot++) if (s_sgvp.inmask & (1u<<slot)) assert(s_sgvp.inputs.active[count++]==slot);
        assert(count==s_sgvp.inputs.active_count);
        s_sgvp.in=packed_input; s_sgvp.input_stride=count*16;
        sg_vp_pack_range(3,32);
        assert(s_sgvp.linear && s_sgvp.linear_first==3 && s_sgvp.nv==32);
        for (unsigned index=0;index<32;index++) for (unsigned slot=0;slot<count;slot++) {
            float expected[4];
            reference_fetch_attr(&s_gpu.attr[s_sgvp.inputs.active[slot]],index+3,expected);
            assert(sg_vp_vertex(index+3)==index);
            assert(!memcmp(expected,packed_input+sg_vp_vertex(index+3)*count*4+slot*4,16));
        }
        s_sgvp.linear=0; s_sgvp.nv=0; s_sgvp.gen++;
        for (unsigned index=0;index<64;index++) {
            unsigned mapped=sg_vp_vertex(index);
            assert(sg_vp_vertex(index)==mapped);
            for (unsigned slot=0;slot<count;slot++) {
                float expected[4];
                reference_fetch_attr(&s_gpu.attr[s_sgvp.inputs.active[slot]],index,expected);
                assert(!memcmp(expected,packed_input+mapped*count*4+slot*4,16));
            }
        }
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
    puts("PASS 640000 CPU/GPU vertex fetches, sparse masks, generation wrap, all formats, constants, inline arrays and invalid ranges");
    return 0;
}
'''
    type_begin = live.index("typedef struct {")
    type_end = live.index("} VertexInputs;",type_begin) + len("} VertexInputs;")
    inputs_type = live[type_begin:type_end]
    live = live[:type_begin] + live[type_end:]
    harness = harness.replace("/* VERTEX_INPUTS_TYPE */",inputs_type)
    text = harness.replace("/* LIVE_FETCH */", live).replace("/* REFERENCE_FETCH */", reference.replace("fetch_attr(", "reference_fetch_attr("))
    text = text.replace("/* PREPARED_FETCH */", prepared).replace("/* CPU_FETCH */",cpu)
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
