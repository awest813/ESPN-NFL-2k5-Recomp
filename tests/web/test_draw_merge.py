"""Exercise production draw merging: preserve ordering and every state boundary."""
from pathlib import Path
import shutil
import subprocess
root=Path(__file__).resolve().parents[2]
kernel=root/'external/xboxrecomp/src/kernel/sdlgpu'
core=(kernel/'sdlgpu.inc.c').read_text(encoding='utf-8')
start=core.index('typedef struct {\n    SDL_GPUGraphicsPipeline *pipe;')
types=core[start:core.index('static SgQueue s_sg_queue',start)]
draw=(kernel/'sdlgpu_draw.inc.c').read_text(encoding='utf-8')
merge=draw[draw.index('static int sg_queue_merge('):draw.index('/* Add one draw to the queue:')]
harness=r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
typedef void SDL_GPUGraphicsPipeline,SDL_GPUTexture,SDL_GPUSampler,SgSurface;
typedef uint8_t Uint8;
typedef struct {int x,y,w,h;} SDL_Rect;
typedef struct {float r,g,b,a;} SDL_FColor;
typedef struct {uint32_t x[8],y[8],exclusive;} SgWindowClip;
/* PRODUCTION */
int main(void) {
    SgQueuedDraw draws[2]={{0}};
    uint32_t indices[9]={0,1,2,2,0,1,0,2,1};
    SgQueue q={.draws=draws,.count=1,.idata=(uint8_t*)indices};
    SgQueuedDraw a={.pipe=(void*)1,.vertex_count=3,.vertex_stride=16,.index_count=3,.vs_size=16,.fs_size=24};
    SgQueuedDraw b=a; b.vertex_offset=48;b.index_offset=12;
    draws[0]=a;
#define REJECT(change) do {SgQueuedDraw x=b;change;uint32_t before[9];memcpy(before,indices,sizeof before);assert(!sg_queue_merge(&q,&x));assert(!memcmp(before,indices,sizeof before));} while(0)
    REJECT(x.pipe=(void*)2); REJECT(x.vertex_stride=32); REJECT(x.vertex_offset++);
    REJECT(x.index_count=0); REJECT(x.index_offset++);
    REJECT(x.tex_count=1); REJECT(x.vs_offset=16); REJECT(x.vs_size++);
    REJECT(x.fs_size++); REJECT(x.fs[0]=1); REJECT(x.stencil_ref=1);
    REJECT(x.scissor.x=1); REJECT(x.window_clip.x[3]=1); REJECT(x.window_clip.exclusive=1);
    REJECT(x.blend_constant.r=1);
    draws[0].tex_count=b.tex_count=1;
    REJECT(x.tex[0]=(void*)2); REJECT(x.sampler[0]=(void*)2);
    draws[0].tex_count=b.tex_count=0;
    assert(sg_queue_merge(&q,&b));
    assert(draws[0].vertex_count==6 && draws[0].index_count==6);
    assert(indices[3]==5 && indices[4]==3 && indices[5]==4);
    b.vertex_offset=96;b.index_offset=24;
    assert(sg_queue_merge(&q,&b));
    assert(draws[0].vertex_count==9 && draws[0].index_count==9);
    assert(indices[6]==6 && indices[7]==8 && indices[8]==7);
    puts("ok: adjacent indexed triangles preserve order across repeated merges");
    draws[0]=a;draws[0].index_count=0;b=a;b.index_count=0;b.vertex_offset=48;
    assert(sg_queue_merge(&q,&b));assert(draws[0].vertex_count==6);
    q.count=0;assert(!sg_queue_merge(&q,&b));
    puts("ok: unindexed triangles merge; pipeline, uniforms, textures, clipping, blending and stencil boundaries do not");
}
'''.replace('/* PRODUCTION */',types+merge)
out=root/'build-web-tests/draw-merge';out.mkdir(parents=True,exist_ok=True)
(out/'test.c').write_text(harness,encoding='utf-8')
subprocess.run([shutil.which('emcc') or 'emcc',str(out/'test.c'),'-O2','-sENVIRONMENT=node','-o',str(out/'test.js')],check=True)
subprocess.run([shutil.which('node') or 'node',str(out/'test.js')],check=True)
