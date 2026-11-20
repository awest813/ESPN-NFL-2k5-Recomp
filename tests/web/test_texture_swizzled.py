"""Compare bulk Morton uploads byte-for-byte with the production texture sampler."""
import argparse
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--native', action='store_true')
parser.add_argument('--benchmark', action='store_true')
parser.add_argument('--build-dir', type=Path, default=root / 'build-web-tests/texture-swizzled')
args = parser.parse_args()
out = args.build_dir.resolve()
out.mkdir(parents=True, exist_ok=True)
kernel = root / 'external/xboxrecomp/src/kernel'
sampler = (kernel / 'nv2a_pb_exec.c').read_text(encoding='utf-8')
texture = (kernel / 'sdlgpu/sdlgpu_texture.inc.c').read_text(encoding='utf-8')


def function(source, signature):
    start = source.index(signature)
    return source[start:source.index('\n}\n', start) + 2]


code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#ifdef __EMSCRIPTEN__
#include <emscripten/emscripten.h>
#endif
#include "d3d/d3d8_swizzle.h"
typedef struct {uint32_t valid,width,height,color,pitch,palette,offset,addr_u,addr_v;} Texture;
typedef struct {int ready;uint8_t *pixels;uint32_t palette[256];} TextureSnapshot;
static struct {Texture tex;} s_gpu;
static TextureSnapshot s_texture_snapshot[4];
static int s_sampler_stage;
static unsigned visited_stages;
/* ORACLE */
/* BULK */
static uint32_t seed=0x2a050b19,cases;
static uint32_t random32(void){seed=seed*1664525u+1013904223u;return seed;}
static uint32_t bpp(uint32_t fmt){return fmt==6 || fmt==7?4:fmt>=2 && fmt<=5?2:1;}
static uint32_t rgba(uint32_t a){return ((a>>16)&255u)|(a&0xff00ff00u)|((a&255u)<<16);}
static void setup(uint32_t fmt,uint32_t w,uint32_t h,uint8_t *pixels,uint32_t stage) {
    visited_stages|=1u<<stage;s_sampler_stage=stage;s_texture_snapshot[stage].ready=1;s_texture_snapshot[stage].pixels=pixels;
    s_gpu.tex=(Texture){.valid=1,.width=w,.height=h,.color=fmt,.palette=1,.addr_u=1,.addr_v=3};
    for(unsigned i=0;i<256;i++)s_texture_snapshot[stage].palette[i]=random32();
}
static void check(uint32_t fmt,uint32_t w,uint32_t h,int exhaustive) {
    size_t n=(size_t)w*h,bytes=n*bpp(fmt);
    uint8_t *allocation=malloc(bytes+4),*src=allocation+1,*aligned=malloc(bytes);
    uint32_t *guard=malloc((n+2)*4);assert(allocation && aligned && guard);
    for(size_t i=0;i<bytes;i++)src[i]=(uint8_t)(random32()>>24);
    if(exhaustive)for(uint32_t i=0;i<65536;i++){uint16_t v=(uint16_t)i;memcpy(src+i*2,&v,2);}
    memcpy(aligned,src,bytes);setup(fmt,w,h,aligned,random32()&3u);
    uint32_t *palette=s_texture_snapshot[s_sampler_stage].palette;
    guard[0]=0x12345678;guard[n+1]=0xdeadbeef;
    assert(sg_decode_swizzled_image(src,bytes,fmt,w,h,palette,guard+1));
    for(uint32_t y=0;y<h;y++)for(uint32_t x=0;x<w;x++) {
        uint32_t expected;assert(sample_texture(x,y,&expected));
        if(guard[1+(size_t)y*w+x]!=rgba(expected)) {
            fprintf(stderr,"FAIL fmt=%02X %ux%u at %u,%u got=%08X expected=%08X\n",fmt,w,h,x,y,guard[1+(size_t)y*w+x],rgba(expected));abort();
        }
    }
    assert(guard[0]==0x12345678 && guard[n+1]==0xdeadbeef && !memcmp(src,aligned,bytes));
    memset(guard+1,0xa5,n*4);
    assert(!sg_decode_swizzled_image(src,bytes-1,fmt,w,h,palette,guard+1));
    for(size_t i=0;i<n;i++)assert(guard[i+1]==0xa5a5a5a5u);
    assert(guard[0]==0x12345678 && guard[n+1]==0xdeadbeef);
    free(allocation);free(aligned);free(guard);cases++;
}
static double now(void) {
#ifdef __EMSCRIPTEN__
    return emscripten_get_now();
#else
    struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec*1000.0+t.tv_nsec/1000000.0;
#endif
}
static volatile uint32_t checksum;
static double measure(uint32_t fmt,int fast,uint8_t *src,uint32_t *dst) {
    double elapsed=0;
    for(unsigned rep=0;rep<24;rep++) {
        src[rep]^=(uint8_t)(rep+1);
        double start=now();
        if(fast)assert(sg_decode_swizzled_image(src,256u*256u*bpp(fmt),fmt,256,256,s_texture_snapshot[0].palette,dst));
        else for(unsigned y=0;y<256;y++)for(unsigned x=0;x<256;x++){
            uint32_t argb;assert(sample_texture(x,y,&argb));dst[y*256+x]=rgba(argb);
        }
        elapsed+=now()-start;
        uint32_t sum=0;for(unsigned i=0;i<256u*256u;i++)sum=(sum^dst[i])*16777619u;
        checksum^=sum;
    }
    return elapsed;
}
int main(int argc,char **argv) {
    (void)argv;const uint32_t formats[]={0,2,3,4,5,6,7,0x0b,0x19};
    for(unsigned f=0;f<sizeof formats/sizeof formats[0];f++) {
        for(unsigned x=0;x<=7;x++)for(unsigned y=0;y<=7;y++)check(formats[f],1u<<x,1u<<y,0);
        const uint32_t sizes[][2]={{1,4096},{4096,1},{16,4096},{4096,16},{256,512},{512,256}};
        for(unsigned i=0;i<sizeof sizes/sizeof sizes[0];i++)check(formats[f],sizes[i][0],sizes[i][1],0);
        if(formats[f]>=2 && formats[f]<=5)check(formats[f],256,256,1);
    }
    check(0x00,4096,4096,0); /* Full 24-bit Morton address span within the supported limit. */
    uint8_t src[64]={0};uint32_t dst[64],palette[256]={0};memset(dst,0x3c,sizeof dst);
    assert(!sg_decode_swizzled_image(NULL,64,6,4,4,palette,dst));
    assert(!sg_decode_swizzled_image(src,64,6,4,4,palette,NULL));
    assert(!sg_decode_swizzled_image(src,64,0xb,4,4,NULL,dst));
    assert(!sg_decode_swizzled_image(src,64,0xc,4,4,palette,dst));
    assert(!sg_decode_swizzled_image(src,64,0x12,4,4,palette,dst));
    assert(!sg_decode_swizzled_image(src,64,6,3,4,palette,dst));
    assert(!sg_decode_swizzled_image(src,64,6,4,5,palette,dst));
    assert(!sg_decode_swizzled_image(src,64,6,0,4,palette,dst));
    assert(!sg_decode_swizzled_image(src,64,6,8192,1,palette,dst));
    for(unsigned i=0;i<64;i++)assert(dst[i]==0x3c3c3c3cu);
    assert(visited_stages==15);
    memset(src,0,sizeof src);palette[0]=0x11223344u;
    assert(sg_decode_swizzled_image(src,16,0xb,4,4,palette,dst));
    for(unsigned i=0;i<16;i++)assert(dst[i]==0x11443322u);
    palette[0]=0xa1b2c3d4u;palette[255]=0xffaabbccu;src[15]=255;
    assert(sg_decode_swizzled_image(src,16,0xb,4,4,palette,dst));
    for(unsigned i=0;i<15;i++)assert(dst[i]==0xa1d4c3b2u);
    assert(dst[15]==0xffccbbaau);
    printf("PASS %u Morton images against the live sampler: nine formats, four stages, exhaustive 16-bit words, rectangular masks, unaligned input, truncation and guards\n",cases);
    if(argc>1)for(unsigned f=0;f<sizeof formats/sizeof formats[0];f++) {
        uint32_t fmt=formats[f];uint8_t *pixels=malloc(256u*256u*bpp(fmt));uint32_t *output=malloc(256u*256u*4);
        assert(pixels && output);for(size_t i=0;i<256u*256u*bpp(fmt);i++)pixels[i]=(uint8_t)(random32()>>24);
        setup(fmt,256,256,pixels,0);measure(fmt,0,pixels,output);measure(fmt,1,pixels,output);
        for(unsigned rep=0;rep<5;rep++) {
            double a,b;if(rep&1){b=measure(fmt,1,pixels,output);a=measure(fmt,0,pixels,output);}
            else{a=measure(fmt,0,pixels,output);b=measure(fmt,1,pixels,output);}
            printf("BENCH fmt=%02X round=%u sampler=%.4fms bulk=%.4fms checksum=%u\n",fmt,rep,a,b,checksum);
        }
        free(pixels);free(output);
    }
}
'''
code = code.replace('/* ORACLE */', '\n'.join(function(sampler, s) for s in
    ['static uint32_t wrap_coord(', 'static uint32_t expand(', 'static uint32_t linear_twin(', 'static int sample_texture(']))
code = code.replace('/* BULK */', function(texture, 'static int sg_decode_swizzled_image('))
(out / 'test.c').write_bytes(code.encode())
compiler = (shutil.which('clang') or shutil.which('cc')) if args.native else shutil.which('emcc')
if not compiler: parser.error('Compiler not found')
binary = out / ('test' if args.native else 'test.js')
flags = ['-O3'] if args.benchmark else ['-O2', '-fsanitize=undefined', '-fno-sanitize-recover=undefined']
if args.native and not args.benchmark: flags += ['-fsanitize=address', '-fno-omit-frame-pointer']
if not args.native: flags += ['-msimd128', '-sINITIAL_MEMORY=128MB', '-sENVIRONMENT=node']
subprocess.run([compiler, str(out / 'test.c'), '-I', str(root / 'external/xboxrecomp/src'),
                *flags, '-o', str(binary)], check=True)
runner = [str(binary)] if args.native else [shutil.which('node') or 'node', str(binary)]
subprocess.run([*runner, *(['--benchmark'] if args.benchmark else [])], check=True, timeout=120)
