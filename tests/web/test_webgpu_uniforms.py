"""Check real WebGPU uniform recording, immutable history and bounded reuse."""
import argparse
from pathlib import Path
import shutil
import subprocess

root=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--native',action='store_true')
parser.add_argument('--benchmark',action='store_true')
parser.add_argument('--asan',action='store_true')
parser.add_argument('--build-dir',type=Path,default=root/'build-web-tests/webgpu-uniforms')
args=parser.parse_args();out=args.build_dir.resolve();out.mkdir(parents=True,exist_ok=True)
if args.benchmark and (args.native or args.asan):parser.error('Benchmark requires unsanitized Wasm')
runtime=root/'external/xboxrecomp/src/kernel/sdlgpu/webgpu'
text=(runtime/'sdl_gpu_webgpu.c').read_text(encoding='utf-8')
uniform_constants = '\n'.join(
    next(line for line in text.splitlines() if line.startswith(f'#define {name} '))
    for name in ('WG_VS_UNIFORM_BYTES', 'WG_FS_UNIFORM_BYTES', 'WG_UNIFORM_ALIGN', 'WG_UNIFORM_TAIL', 'WG_MAX_SAMPLERS')
)
def function(signature):
    start=text.index(signature);opening=text.index('{',start);depth=1;end=opening+1
    while depth:
        if text[end]=='{':depth+=1
        elif text[end]=='}':depth-=1
        end+=1
    return text[start:end]
start=text.index('struct SDL_GPUCommandBuffer {');end=text.index('\n};',start)+3
production=text[start:end]+'\n'+function('static void cmd_fail(')+'\n'+function('static Op *push(')
production+='\nstatic atomic_int s_uniform_cache_on=-1;\n'+function('static int uniform_cache_enabled(')+'\n'+function('static void push_uniform(')
legacy=function('static void push_uniform(').replace('static void push_uniform(', 'static void legacy_push_uniform(')
legacy=legacy.replace('int cacheable = fragment && uniform_cache_enabled();','int cacheable = 0;')
legacy=legacy.replace('wg_uniform_bytes_equal(c->uniforms + c->last_uniform[fragment].offset, data, len)',
                      '(memcmp(c->uniforms + c->last_uniform[fragment].offset, data, len) == 0)')
production+='\n'+legacy
source=r'''
#include <assert.h>
#include <stdint.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <limits.h>
#include "wg_uniform_cache.h"
#ifdef __EMSCRIPTEN__
#include <emscripten/emscripten.h>
#endif
typedef uint32_t Uint32;
typedef enum {OP_UNIFORM=1} OpKind;
typedef struct {OpKind kind;struct {int fragment;uint32_t off;} uniform;} Op;
typedef struct SDL_GPUCommandBuffer SDL_GPUCommandBuffer;
typedef struct WgTextureStorage WgTextureStorage;
typedef struct SDL_GPUSampler SDL_GPUSampler;
#define SDL_max(a, b) (((a) > (b)) ? (a) : (b))
/* UNIFORM CONSTANTS */
static unsigned errors;
static int SDL_SetError(const char *format,...){(void)format;errors++;return -1;}
static const char *environment;
static const char *audit_getenv(const char *name){assert(!strcmp(name,"RECOMP_WEBGPU_UNIFORM_CACHE"));return environment;}
static struct {void *p;size_t n;} allocations[128];
static int fail_after=-1,always_move=1;
static void *audit_realloc(void *p,size_t n){
 if(fail_after==0){fail_after=-1;return NULL;}if(fail_after>0)fail_after--;
 unsigned slot=0;while(slot<128 && (p?allocations[slot].p!=p:allocations[slot].p!=NULL))slot++;assert(slot<128);
 void *fresh;
 if(always_move){fresh=malloc(n);assert(fresh);memset(fresh,0xcd,n);if(p){memcpy(fresh,p,allocations[slot].n<n?allocations[slot].n:n);free(p);}}
 else {fresh=realloc(p,n);assert(fresh);}
 allocations[slot].p=fresh;allocations[slot].n=n;return fresh;
}
static void audit_free(void *p){if(!p)return;unsigned i=0;while(i<128 && allocations[i].p!=p)i++;assert(i<128);allocations[i].p=NULL;allocations[i].n=0;free(p);}
#define realloc audit_realloc
#define getenv audit_getenv
/* PRODUCTION */
#undef getenv
#undef realloc
static struct {uint32_t len;int stage;uint8_t data[4096];} expected[1024];
static uint8_t payload[256][4096];
static unsigned checks,seed=0x6e69666f;
static unsigned random32(void){seed=seed*1664525u+1013904223u;return seed;}
static void verify(SDL_GPUCommandBuffer *c){
 if(c->ubytes){
   size_t reserved=0;
   for(unsigned i=0;i<128;i++)if(allocations[i].p==c->uniforms)reserved=allocations[i].n;
   assert(reserved >= (((size_t)c->ubytes+3u)&~(size_t)3u) + WG_UNIFORM_TAIL);
 }
 for(unsigned i=0;i<c->n;i++){
   Op *o=c->ops+i;assert(o->kind==OP_UNIFORM && o->uniform.fragment==expected[i].stage);
   assert(!(o->uniform.off&255u) && o->uniform.off<=c->ubytes && expected[i].len<=c->ubytes-o->uniform.off);
   assert(!memcmp(c->uniforms+o->uniform.off,expected[i].data,expected[i].len));checks++;
 }
}
static void emit(SDL_GPUCommandBuffer *c,int stage,const void *data,unsigned len){
 unsigned n=c->n,used=c->ubytes;push_uniform(c,stage,data,len);
 if(!c->failed && len){
   assert(c->uniform_uncached_bytes>=c->ubytes);
   if(!atomic_load(&s_uniform_cache_on))assert(c->uniform_uncached_bytes==c->ubytes);
   assert(c->n==n+1 && n<1024);expected[n].len=len;expected[n].stage=stage;memcpy(expected[n].data,data,len);
   if(c->ubytes>used){unsigned off=c->ops[n].uniform.off;for(unsigned i=used;i<off;i++)assert(!c->uniforms[i]);
     for(unsigned i=0;i<((4u-(len&3u))&3u);i++)assert(!c->uniforms[off+len+i]);}
 }else assert(c->n==n);
}
static void destroy(SDL_GPUCommandBuffer *c){audit_free(c->ops);audit_free(c->uniforms);memset(c,0,sizeof *c);}
static void tests(void){
 for(unsigned alignment=0;alignment<16;alignment++)for(unsigned n=0;n<=129;n++) {
   size_t bytes=n+alignment;uint8_t *pa=malloc(bytes?bytes:1),*pb=malloc(bytes?bytes:1);assert(pa && pb);
   uint8_t *a=pa+alignment,*b=pb+alignment;
   for(unsigned i=0;i<n;i++)a[i]=b[i]=(uint8_t)(i*37+alignment);
   assert(wg_uniform_bytes_equal(a,b,n));
   for(unsigned i=0;i<n;i++){b[i]^=1;assert(!wg_uniform_bytes_equal(a,b,n));b[i]^=1;}
   free(pa);free(pb);
 }
 for(unsigned i=0;i<256;i++)for(unsigned j=0;j<4096;j++)payload[i][j]=(uint8_t)(i*31+j*17+j/7);
 environment="1";atomic_store(&s_uniform_cache_on,-1);assert(uniform_cache_enabled());
 environment="0";atomic_store(&s_uniform_cache_on,-1);assert(!uniform_cache_enabled());
 environment=NULL;atomic_store(&s_uniform_cache_on,-1);assert(uniform_cache_enabled());
 SDL_GPUCommandBuffer c={0};
 for(int enabled=0;enabled<2;enabled++){
   atomic_store(&s_uniform_cache_on,enabled);
   for(int stage=0;stage<2;stage++){
     unsigned other=1;uint64_t key=wg_uniform_key(payload[0],16,stage);
     while(wg_uniform_entry(&c.uniform_cache,key)==wg_uniform_entry(&c.uniform_cache,wg_uniform_key(payload[other],16,stage)))other++;
     emit(&c,stage,payload[0],16);emit(&c,stage,payload[other],16);emit(&c,stage,payload[0],16);
     int reused=enabled && stage;
     assert(reused?(c.ops[0].uniform.off==c.ops[2].uniform.off):(c.ops[0].uniform.off!=c.ops[2].uniform.off));
     assert(c.uniform_cache_hits==(unsigned)reused);emit(&c,stage,payload[0],16);assert(c.uniform_last_hits==1);
     verify(&c);destroy(&c);
   }
   emit(&c,0,payload[0],16);emit(&c,1,payload[0],16);assert(c.ops[0].uniform.off!=c.ops[1].uniform.off);verify(&c);destroy(&c);
   for(unsigned len=1;len<=4096;len++){
     emit(&c,(len>>1)&1,payload[len&255],len);if(c.n==128){verify(&c);destroy(&c);}
   }
   if(c.n){verify(&c);destroy(&c);}
   for(unsigned i=0;i<20000;i++){
     unsigned index=random32()&255,stage=random32()&1,len=(random32()%4096)+1;
     emit(&c,stage,payload[index],len);if(c.n==1000){verify(&c);destroy(&c);}
   }
 }
 atomic_store(&s_uniform_cache_on,1);
 /* Equal sampled fingerprints with different interiors use both ways. */
 uint8_t first[64]={0},second[64]={0},third[64]={0};second[12]=1;third[16]=1;
 assert(wg_uniform_key(first,64,1)==wg_uniform_key(second,64,1));
 emit(&c,1,first,64);emit(&c,1,second,64);emit(&c,1,first,64);emit(&c,1,second,64);
 assert(c.ops[0].uniform.off==c.ops[2].uniform.off && c.ops[1].uniform.off==c.ops[3].uniform.off && c.uniform_cache_hits==2);
 emit(&c,1,third,64);unsigned after_third=c.ubytes;emit(&c,1,first,64);assert(c.ubytes>after_third);verify(&c);destroy(&c);
 /* A forged hash collision still requires exact bytes, stage, size and range. */
 emit(&c,1,payload[0],32);unsigned before=c.ubytes;c.last_uniform[1].valid=0;
 uint64_t key=wg_uniform_key(payload[1],32,1);WgUniformEntry *entry=wg_uniform_entry(&c.uniform_cache,key);
 *entry=(WgUniformEntry){key,c.ops[0].uniform.off,wg_uniform_tag(32,1)};
 emit(&c,1,payload[1],32);assert(c.ubytes>before);verify(&c);
 c.last_uniform[1].valid=0;key=wg_uniform_key(payload[2],32,1);entry=wg_uniform_entry(&c.uniform_cache,key);
 *entry=(WgUniformEntry){key,UINT32_MAX,wg_uniform_tag(32,1)};emit(&c,1,payload[2],32);verify(&c);destroy(&c);
 unsigned other=1;
 while(wg_uniform_entry(&c.uniform_cache,wg_uniform_key(payload[0],4096,1))==wg_uniform_entry(&c.uniform_cache,wg_uniform_key(payload[other],4096,1)))other++;
 emit(&c,1,payload[0],4096);emit(&c,1,payload[other],4096);emit(&c,1,payload[0],4096);
 assert(c.ops[0].uniform.off==c.ops[2].uniform.off);verify(&c);destroy(&c);
 /* Changing client data never mutates earlier records; allocator always moves. */
 uint8_t client[4096];memset(client,17,sizeof client);emit(&c,0,client,sizeof client);
 memset(client,99,sizeof client);emit(&c,0,client,sizeof client);verify(&c);destroy(&c);
 memset(client,17,sizeof client);emit(&c,1,client,sizeof client);
 client[4095]^=1;emit(&c,1,client,sizeof client);client[4095]^=1;emit(&c,1,client,sizeof client);
 assert(c.ops[0].uniform.off==c.ops[2].uniform.off && c.uniform_cache_hits==1);verify(&c);destroy(&c);
 unsigned old_errors=errors;push_uniform(NULL,0,payload[0],4);push_uniform(&c,0,NULL,0);assert(!c.n && !c.failed && errors==old_errors);
 push_uniform(&c,0,NULL,4);assert(c.failed && errors==old_errors+1);destroy(&c);
 push_uniform(&c,0,payload[0],4097);assert(c.failed);destroy(&c);
 c.ubytes=UINT32_MAX-256;push_uniform(&c,0,payload[0],4096);assert(c.failed);destroy(&c);
 c.ubytes=UINT32_MAX-1024;fail_after=0;push_uniform(&c,0,payload[0],16);
 assert(c.failed && fail_after==0);fail_after=-1;destroy(&c); /* reserve the full GPU binding before allocation */
 for(int failure=0;failure<2;failure++){
   fail_after=failure;push_uniform(&c,0,payload[0],16);assert(c.failed && !c.n);
   push_uniform(&c,1,payload[1],16);assert(!c.n);destroy(&c);
 }
 for(unsigned i=0;i<64;i++)emit(&c,0,payload[0],16);
 fail_after=0;push_uniform(&c,0,payload[0],16);assert(c.failed && c.n==64);verify(&c);destroy(&c);
 for(unsigned i=0;i<128;i++)assert(!allocations[i].p);
 printf("PASS uniform recording: %u immutable-history checks, both cache modes/stages, all 4096 sizes, forced collisions, moved allocations, padding and allocation failures\n",checks);
}
#ifdef __EMSCRIPTEN__
typedef void (*Recorder)(SDL_GPUCommandBuffer*,int,const void*,Uint32);
static Recorder volatile recorders[]={legacy_push_uniform,push_uniform,push_uniform};
static void benchmark(void){
 always_move=0;
 for(unsigned trace=0;trace<4;trace++)for(unsigned round=0;round<7;round++)for(unsigned k=0;k<3;k++){
   unsigned mode=(k+round)%3;atomic_store(&s_uniform_cache_on,mode==1);
   Recorder record=recorders[mode];
   uint64_t bytes=0,hits=0;double began=emscripten_get_now();
   for(unsigned frame=0;frame<300;frame++){
     SDL_GPUCommandBuffer c={0};
     for(unsigned i=0;i<256;i++){
       unsigned stage=trace?i&1:0,index=trace==0?0:trace==1?i%8:trace==2?i:stage?(i/2)%8:64+i/2;
       record(&c,stage,payload[index],stage?784:3328);
     }
     bytes+=c.ubytes;hits+=c.uniform_cache_hits;destroy(&c);
   }
   printf("BENCH trace=%u round=%u mode=%u ms=%.4f stored=%llu hits=%llu\n",trace,round,mode,emscripten_get_now()-began,(unsigned long long)bytes,(unsigned long long)hits);
 }
}
#endif
int main(int argc,char **argv){(void)argv;tests();
#ifdef __EMSCRIPTEN__
 if(argc>1)benchmark();
#else
 (void)argc;
#endif
 return 0;}
'''.replace('/* UNIFORM CONSTANTS */', uniform_constants).replace('/* PRODUCTION */',production)
(out/'test.c').write_bytes(source.encode('utf-8'))
if args.native:
    cc=shutil.which('cc') or shutil.which('clang')
    if not cc:parser.error('Native C compiler required')
    target=out/'test';subprocess.run([cc,str(out/'test.c'),'-I',str(runtime),'-O2','-fsanitize=address,undefined','-fno-sanitize-recover=undefined','-o',str(target)],check=True)
    command=[str(target)]
else:
    cc,node=shutil.which('emcc'),shutil.which('node')
    if not cc or not node:parser.error('Emscripten and Node required')
    target=out/'test.js';subprocess.run([cc,str(out/'test.c'),'-I',str(runtime),'-O2','-msimd128',
        *([] if args.benchmark else ['-fsanitize=address,undefined' if args.asan else '-fsanitize=undefined','-fno-sanitize-recover=undefined']),
        *(['-sALLOW_MEMORY_GROWTH=1','-sMAXIMUM_MEMORY=1073741824'] if args.asan else []),
        '-sENVIRONMENT=node','-sINITIAL_MEMORY=67108864','-o',str(target)],check=True)
    command=[node,str(target)]
subprocess.run([*command,*(['--benchmark'] if args.benchmark else [])],check=True,timeout=120)
