"""Exercise live vertex-program cache identity with colliding NV2A programs."""
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
kernel = root / 'external/xboxrecomp/src/kernel'
cache = (kernel / 'sdlgpu/sdlgpu_vpcache.inc.c').read_text(encoding='utf-8')
runtime = (kernel / 'nv2a_pb_exec.c').read_text(encoding='utf-8')
fixtures = Path(__file__).parent / 'fixtures'
prefix = (fixtures / 'vp_interpreter_test.c').read_text(encoding='utf-8').split('/* LIVE_INTERPRETER */')[0]
begin = runtime.index('/* Decoded instruction fields')
end = runtime.index('/* One transformed vertex', begin)
mask = runtime.index('static uint32_t vp_input_mask(', end)
live = runtime[begin:end] + runtime[mask:runtime.index('static uint32_t s_xf_input_mask', mask)]
cache_types = cache[cache.index('#define SG_VP_CACHE'):cache.index('/* Only sg_vp_worker_start()')]
lookup = cache[cache.index('static SDL_GPUShader *sg_vp_program('):]
harness = r'''
#include <assert.h>
typedef unsigned char Uint8;
typedef int SDL_AtomicInt;
typedef void SDL_Thread,SDL_Mutex,SDL_Condition;
typedef struct { uint32_t mask,program[3][4]; } SDL_GPUShader;
typedef struct { const Uint8 *code; size_t code_size; const char *entrypoint;
    int format,stage,num_uniform_buffers; } SDL_GPUShaderCreateInfo;
enum {SDL_GPU_SHADERFORMAT_WGSL,SDL_GPU_SHADERFORMAT_SPIRV,SDL_GPU_SHADERSTAGE_VERTEX};
static struct { void *dev; } s_sg;
static int SDL_GetAtomicInt(SDL_AtomicInt *p) {return *p;}
static void SDL_SetAtomicInt(SDL_AtomicInt *p,int v) {*p=v;}
static void sg_gpu_error(const char *message) {(void)message;}
static unsigned compiled;
static int reject_shader;
static SDL_GPUShader shaders[16];
static char *sg_vp_translate_wgsl(uint32_t start) {
    (void)start; char *text=malloc(2);memcpy(text,"x",2);return text;
}
static char *sg_vp_translate_line_wgsl(uint32_t start,uint32_t mask) {(void)mask;return sg_vp_translate_wgsl(start);}
static SDL_GPUShader *SDL_CreateGPUShader(void *device,const SDL_GPUShaderCreateInfo *info) {
    (void)device;(void)info;
    if(reject_shader)return NULL;
    assert(compiled<16);
    SDL_GPUShader *shader=&shaders[compiled++];shader->mask=vp_input_mask(s_vp.start);
    memcpy(shader->program,s_vp.prog+s_vp.start,sizeof shader->program);return shader;
}
/* CACHE */
#define program_a vp_cache_collision[0]
#define program_b vp_cache_collision[1]
static void select_program(const uint32_t program[3][4]) {
    s_vp.start=0;memcpy(s_vp.prog,program,sizeof program_a);s_vp_cgen++;
}
int main(void) {
    float input[16][4],a[16][4],b[16][4];
    for(unsigned v=0;v<16;v++)for(unsigned c=0;c<4;c++)input[v][c]=(float)(v*10+c+1);
    select_program(program_a);vp_run(input,a);
    uint32_t mask_a=vp_input_mask(0),slot_a,slot_b;
    SDL_GPUShader *first=sg_vp_program(&slot_a);assert(first);
    assert(s_sg_vp[slot_a].key==0xa3202aa7u);
    select_program(program_b);vp_run(input,b);
    uint32_t mask_b=vp_input_mask(0);
    assert(mask_a!=mask_b && memcmp(a,b,sizeof a));
    SDL_GPUShader *second=sg_vp_program(&slot_b);assert(second);
    assert(first!=second && slot_a!=slot_b);
    assert(s_sg_vp[slot_b].key==s_sg_vp[slot_a].key);
    assert(second->mask==mask_b && !memcmp(second->program,program_b,sizeof program_b));
    assert(first->mask==mask_a && !memcmp(first->program,program_a,sizeof program_a));
    select_program(program_a);
    s_vp.prog[3][1]=0xffffffffu; /* code after FINAL does not affect identity */
    assert(sg_vp_program(&slot_b)==first && slot_b==slot_a && compiled==2);
    puts("ok: colliding programs with different CPU outputs retain separate shaders and input layouts");
    for(unsigned repeat=0;repeat<10000;repeat++) {
        s_vp.prog[3][1]=repeat; /* unchanged executable, mutable words past FINAL */
        assert(sg_vp_program(&slot_b)==first && slot_b==slot_a && compiled==2);
    }
    select_program(program_b); /* same hash, changed executable after a warm lookup */
    assert(sg_vp_program(&slot_b)==second && compiled==2);
    s_vp.start=7;memcpy(s_vp.prog+7,program_b,sizeof program_b);
    SDL_GPUShader *relocated=sg_vp_program(&slot_b);
    assert(relocated && relocated!=second && compiled==3);
    assert(sg_vp_program(&slot_b)==relocated && compiled==3);
    puts("ok: repeated lookups preserve exact identity, FINAL bounds and start-slot changes");
    select_program(program_b);assert(sg_vp_program(&slot_b)==second);
    s_vp.prog[2][3]&=~1u;s_vp.prog[3][3]=1; /* extend past the old FINAL */
    SDL_GPUShader *extended=sg_vp_program(&slot_b);
    assert(extended && extended!=second && compiled==4);
    assert(sg_vp_program(&slot_b)==extended && compiled==4);
    s_vp.prog[1][3]|=1u; /* an earlier FINAL also changes the executable */
    SDL_GPUShader *shortened=sg_vp_program(&slot_b);
    assert(shortened && shortened!=extended && compiled==5);
    assert(sg_vp_program(&slot_b)==shortened && compiled==5);
    puts("ok: moving FINAL in either direction invalidates a warm lookup");
    memset(s_sg_vp,0,sizeof s_sg_vp);
    select_program(program_a);reject_shader=1;assert(!sg_vp_program(&slot_a));
    select_program(program_b);reject_shader=0;assert(sg_vp_program(&slot_b));
    select_program(program_a);assert(!sg_vp_program(&slot_a));
    puts("ok: a failed program does not poison a colliding program");
    s_vp.start=VP_PROG_LEN;slot_a=0x11223344u;
    assert(!sg_vp_program(&slot_a) && slot_a==0x11223344u);
    puts("ok: invalid program starts do not allocate cache entries");
    memset(s_sg_vp,0,sizeof s_sg_vp);compiled=0;
    select_program(program_a);SDL_GPUShader *line_a=sg_vp_line_program(&slot_a);assert(line_a && compiled==2);
    SDL_GPUShader *base_a=s_sg_vp[slot_a].vs;assert(base_a!=line_a);
    select_program(program_b);SDL_GPUShader *line_b=sg_vp_line_program(&slot_b);assert(line_b && line_a!=line_b && slot_a!=slot_b && compiled==4);
    select_program(program_a);assert(sg_vp_line_program(&slot_b)==line_a && compiled==4);
    memset(s_sg_vp,0,sizeof s_sg_vp);compiled=0;
    select_program(program_a);base_a=sg_vp_program(&slot_a);assert(base_a);reject_shader=1;
    assert(!sg_vp_line_program(&slot_a));reject_shader=0;assert(sg_vp_program(&slot_a)==base_a && !sg_vp_line_program(&slot_a));
    select_program(program_b);assert(sg_vp_line_program(&slot_b));
    puts("ok: colliding line programs remain separate; failed line specialization preserves triangle shaders");
}
'''.replace('/* CACHE */', cache_types + lookup)
out = root / 'build-web-tests/vp-cache'
out.mkdir(parents=True, exist_ok=True)
(out / 'test.c').write_text(prefix + live + (fixtures / 'vp_cache_collision.h').read_text() + harness, encoding='utf-8')
subprocess.run([shutil.which('emcc') or 'emcc', str(out / 'test.c'), '-O2',
                '-sENVIRONMENT=node', '-o', str(out / 'test.js')], check=True)
subprocess.run([shutil.which('node') or 'node', str(out / 'test.js')], check=True)
