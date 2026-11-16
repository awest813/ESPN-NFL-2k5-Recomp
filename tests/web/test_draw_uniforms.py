"""Exercise real queue insertion with complete 3D uniforms and guarded storage."""
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
kernel = root / 'external/xboxrecomp/src/kernel/sdlgpu'
core = (kernel / 'sdlgpu.inc.c').read_text(encoding='utf-8')
draw = (kernel / 'sdlgpu_draw.inc.c').read_text(encoding='utf-8')
xf = (kernel / 'sdlgpu_xf.inc.c').read_text(encoding='utf-8')
types_start = core.index('typedef struct {\n    SDL_GPUGraphicsPipeline *pipe;')
types = core[types_start:core.index('static SgQueue s_sg_queue', types_start)]
draw_start = draw.index('typedef struct {\n    SgSurface *surface;')
draw_type = draw[draw_start:draw.index('#ifdef SG_HAVE_SHADERS', draw_start)]
shade_start = xf.index('typedef struct {', xf.index('std140 mirror'))
shade = xf[shade_start:xf.index('} SgXfShade;', shade_start) + len('} SgXfShade;')]
grow_start = draw.index('static void *sg_grow(')
functions = draw[grow_start:draw.index('/* Submit everything queued:', grow_start)]
harness = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
typedef void SDL_GPUGraphicsPipeline, SDL_GPUTexture, SDL_GPUSampler;
typedef uint8_t Uint8;
typedef struct { int x,y,w,h; } SDL_Rect;
typedef struct { float r,g,b,a; } SDL_FColor;
typedef struct { uint32_t x[8],y[8],exclusive; } SgWindowClip;
typedef struct { int owner; } SgSurface;
enum { SG_OWNER_GUEST, SG_OWNER_GPU, SG_QUEUE_MAX_DRAWS=8192 };
typedef struct { SDL_GPUTexture *tex; SDL_GPUSampler *sampler;
    void *upload; uint32_t w,h,layers; } SgTextureUse;
/* TYPES */
static SgQueue s_sg_queue;
static struct { uint32_t clip_x,clip_y,clip_w,clip_h,window_clip_x[8],window_clip_y[8];
    uint32_t window_clip_type,blend_color; } s_gpu;
static struct { uint32_t stencil_ref; } s_vp;
static struct { uint64_t vertex_upload_bytes,merged_draws; } s_sg_stats;
static struct { SDL_GPUTexture *white,*white_cube; SDL_GPUSampler *point; } s_sg;
static void sg_texture_commit(SgTextureUse *t) { (void)t; }
static int sg_queue_flush(void) { abort(); }
/* FUNCTIONS */
int main(void) {
    struct { SgQueuedDraw draws[2]; uint8_t guard[64]; } storage;
    memset(&storage,0,sizeof storage);
    memset(storage.guard,0xA7,sizeof storage.guard);
    s_sg_queue.draws=storage.draws; s_sg_queue.cap=2;
    SgSurface surface={0}; SgTextureUse textures[8]={{0}};
    float vertex[4]={0},uniform[4]={0};
    SgXfShade first,second;
    memset(&first,0x39,sizeof first); memset(&second,0xC5,sizeof second);
    SgDraw d={.surface=&surface,.pipe=(void*)1,.vertices=vertex,
        .vertex_bytes=sizeof vertex,.vertex_count=1,.tex=textures,.tex_count=8,
        .vs_uniform=uniform,.vs_uniform_size=sizeof uniform,
        .fs_uniform=&first,.fs_uniform_size=sizeof first};
    assert(sg_queue_draw(&d));
    d.pipe=(void*)2; d.fs_uniform=&second;
    assert(sg_queue_draw(&d));
    assert(s_sg_queue.count==2);
    assert(!memcmp(storage.draws[0].fs,&first,sizeof first));
    assert(!memcmp(storage.draws[1].fs,&second,sizeof second));
    for(unsigned i=0;i<sizeof storage.guard;i++) assert(storage.guard[i]==0xA7);
    printf("ok: %zu-byte 3D uniforms survive adjacent draws without overwriting the queue\n",sizeof first);
    uint32_t old_count=s_sg_queue.count,old_bytes=s_sg_queue.vbytes;
    d.fs_uniform_size=sizeof storage.draws[0].fs+1;
    assert(!sg_queue_draw(&d));
    assert(s_sg_queue.count==old_count && s_sg_queue.vbytes==old_bytes);
    puts("ok: oversized fragment uniforms are rejected before queue mutation");
    free(s_sg_queue.vdata);free(s_sg_queue.udata);free(s_sg_queue.uploads);
}
'''.replace('/* TYPES */', types + draw_type + shade).replace('/* FUNCTIONS */', functions)
out = root / 'build-web-tests/draw-uniforms'
out.mkdir(parents=True, exist_ok=True)
(out / 'test.c').write_text(harness, encoding='utf-8')
subprocess.run([shutil.which('emcc') or 'emcc', str(out / 'test.c'), '-O2',
                '-sENVIRONMENT=node', '-o', str(out / 'test.js')], check=True)
subprocess.run([shutil.which('node') or 'node', str(out / 'test.js')], check=True)
