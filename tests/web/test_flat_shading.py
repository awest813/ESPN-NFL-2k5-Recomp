"""Exercise production primitive selection and D3D11 vertex assembly in Wasm."""
from pathlib import Path
import re
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
kernel = root / 'external/xboxrecomp/src/kernel'
source = (kernel / 'nv2a_pb_exec.c').read_text(encoding='utf-8')
d3d = (kernel / 'nv2a_gpu_d3d11.inc.c').read_text(encoding='utf-8')


def function(signature):
    start = source.index(signature)
    return source[start:source.index('\n}\n', start) + 3]


constants = '\n'.join(re.findall(r'^#define NV_PRIM_\w+\s+\d+.*$', source, re.M))
callback = next(line for line in source.splitlines() if line.startswith('typedef void (*BatchTriFn)'))
macro = d3d[d3d.index('#define GPU_TRI('):d3d.index('    /* Lines (NV097', d3d.index('#define GPU_TRI('))]
prefix = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "flat_shade_reference.h"
static struct {uint32_t prim,shade_mode,provoking_vertex,idx_count;uint16_t idx[16];} s_gpu;
'''
harness = r'''
typedef struct {int ok;float col[4],spec[4],pos[4];} XfVert;
typedef struct {float d0[4],d1[4],pos[4];} GpuVertex;
#define GPU_MAX_VERTS 64
static struct {GpuVertex verts[GPU_MAX_VERTS];} s_gpu11;
static struct {unsigned rej_bad;} s_vp;
static XfVert inputs[16];
static const XfVert *get(uint32_t index) {assert(index<16);return &inputs[index];}
static void gpu_tri_dump(const XfVert*a,const XfVert*b,const XfVert*c,unsigned x,unsigned y,unsigned z) {}
static void gpu_log_rejected(unsigned id,const XfVert*v) {}
static void gpu_vertex(GpuVertex*out,const XfVert*in,unsigned w,unsigned h) {
    memcpy(out->d0,in->col,16);memcpy(out->d1,in->spec,16);memcpy(out->pos,in->pos,16);
}
/* D3D_MACRO */
static const FlatShadeReference *ref;
static unsigned emitted,checks;
static void check_triangle(void *context,uint32_t a,uint32_t b,uint32_t c,uint32_t provoking) {
    (void)context;assert(emitted<ref->triangles);
    unsigned position=(s_gpu.provoking_vertex?ref->first:ref->last)[emitted++];
    assert(provoking==s_gpu.idx[position]);checks++;
}
int main(void) {
    uint32_t seed=0x09FC037Cu;
    for(unsigned id=0;id<16;id++) {
        inputs[id].ok=1;
        for(unsigned ch=0;ch<4;ch++) {
            inputs[id].col[ch]=(id*4+ch)/128.0f;
            inputs[id].spec[ch]=(id*4+ch+1)/256.0f;
            inputs[id].pos[ch]=(float)(id*10+ch);
        }
    }
    for(unsigned permutation=0;permutation<64;permutation++) {
        for(unsigned k=0;k<16;k++)s_gpu.idx[k]=(uint16_t)k;
        for(unsigned k=15;k>0;k--) {
            seed=seed*1664525u+1013904223u;unsigned p=seed%(k+1);
            uint16_t value=s_gpu.idx[k];s_gpu.idx[k]=s_gpu.idx[p];s_gpu.idx[p]=value;
        }
        for(unsigned ci=0;ci<sizeof flat_shade_cases/sizeof *flat_shade_cases;ci++) {
            ref=&flat_shade_cases[ci];s_gpu.prim=ref->primitive;s_gpu.idx_count=ref->count;
            for(unsigned first=0;first<2;first++) {
                s_gpu.provoking_vertex=first;emitted=0;batch_triangles(check_triangle,NULL);assert(emitted==ref->triangles);
                for(unsigned flat=0;flat<2;flat++)for(unsigned triangle=0;triangle<ref->triangles;triangle++) {
                    s_gpu.shade_mode=flat?0x1D00:0x1D01;
                    unsigned i=ref->primitive==5?triangle*3:ref->primitive==6?triangle:
                        ref->primitive==8?(triangle/2)*4:ref->primitive==9?(triangle/2)*2:triangle+1;
                    unsigned nv=0,rw=64,rh=64;const uint16_t *ix=s_gpu.idx;
                    GPU_TRI(0,1,2);
                    assert(nv==3);
                    unsigned expected=ix[(first?ref->first:ref->last)[triangle]];
                    for(unsigned k=0;k<3;k++) {
                        const XfVert *color=&inputs[flat?expected:ix[k]],*position=&inputs[ix[k]];
                        assert(!memcmp(s_gpu11.verts[k].d0,color->col,16));
                        assert(!memcmp(s_gpu11.verts[k].d1,color->spec,16));
                        assert(!memcmp(s_gpu11.verts[k].pos,position->pos,16));checks++;
                    }
                    nv=GPU_MAX_VERTS-1;unsigned rejected=s_vp.rej_bad;
                    GPU_TRI(0,1,2);assert(nv==GPU_MAX_VERTS-1 && s_vp.rej_bad==rejected+1);
                }
            }
        }
    }
    printf("PASS %u primitive/vertex checks: hardware-derived first/last table, shuffled indices, D3D11 diffuse/specular, smooth preservation and capacity guards\n",checks);
}
'''.replace('/* D3D_MACRO */', macro)
out = root / 'build-web-tests/flat-shading'
out.mkdir(parents=True, exist_ok=True)
(out / 'test.c').write_text(prefix + constants + '\n' + callback + '\n'
                          + function('static uint32_t flat_vertex_position(')
                          + function('static void batch_triangles(') + harness, encoding='utf-8')
subprocess.run([shutil.which('emcc') or 'emcc', str(out / 'test.c'), '-O2',
                '-I' + str(root / 'external/xboxrecomp/tests/sdlgpu_web'),
                '-sENVIRONMENT=node', '-o', str(out / 'test.js')], check=True)
subprocess.run([shutil.which('node') or 'node', str(out / 'test.js')], check=True, timeout=30)
