"""Compare bulk DXT uploads with the existing per-texel Xbox decoder."""
from pathlib import Path
import shutil
import subprocess
root=Path(__file__).resolve().parents[2]
kernel=root/'external/xboxrecomp/src/kernel/sdlgpu'
text=(kernel/'sdlgpu_texture.inc.c').read_text(encoding='utf-8')
decoder=text[text.index('static int sg_decode_dxt_image('):text.index('/* Decode a stage into')]
header=(root/'external/xboxrecomp/src/d3d/d3d8_swizzle.h').as_posix()
harness=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "HEADER"
/* DECODER */
static uint32_t seed=0x2a050d17;
static uint32_t rng(void) {seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;return seed;}
static uint32_t rgba(uint32_t c) {return ((c>>16)&255u)|(c&0xff00u)|((c&255u)<<16)|(c&0xff000000u);}
static void reference(const uint8_t *src,uint32_t fmt,uint32_t w,uint32_t h,uint32_t *out) {
    for(uint32_t y=0;y<h;y++) for(uint32_t x=0;x<w;x++) {
        uint32_t argb;assert(d3d8_dxt_decode_texel(src,fmt,x,y,w,&argb));out[y*w+x]=rgba(argb);
    }
}
static uint32_t sum(const uint32_t *p,size_t n) {uint32_t s=0;for(size_t i=0;i<n;i++)s=(s^p[i])*16777619u;return s;}
int main(void) {
    unsigned cases=0;
    const uint32_t formats[]={0x0c,0x0e,0x0f};
    for(unsigned f=0;f<3;f++) for(unsigned trial=0;trial<300;trial++) {
        uint32_t w=1+rng()%97,h=1+rng()%113,fmt=formats[f];
        size_t n=(size_t)w*h,bytes=(size_t)((w+3)/4)*((h+3)/4)*d3d8_format_dxt_block_bytes(fmt);
        uint8_t *src=malloc(bytes);uint32_t *expected=malloc(n*4),*guard=malloc((n+2)*4),*actual=guard+1;
        assert(src&&expected&&guard);
        for(size_t i=0;i<bytes;i++)src[i]=(uint8_t)rng();
        guard[0]=guard[n+1]=0xdeadbeef;
        assert(sg_decode_dxt_image(src,bytes,fmt,w,h,actual));
        reference(src,fmt,w,h,expected);assert(!memcmp(expected,actual,n*4));
        assert(guard[0]==0xdeadbeef && guard[n+1]==0xdeadbeef);
        assert(!sg_decode_dxt_image(src,bytes-1,fmt,w,h,actual));
        free(src);free(expected);free(guard);cases++;
    }
    uint8_t block[16]={0};uint32_t out[16];
    for(unsigned fmt=0;fmt<3;fmt++) for(unsigned endpoints=0;endpoints<4;endpoints++) {
        memset(block,0xff,sizeof block);block[0]=endpoints&1?0:255;block[1]=endpoints&2?0:255;
        unsigned offset=fmt?8:0;memset(block+offset,0,4);
        uint32_t want[16];assert(sg_decode_dxt_image(block,sizeof block,formats[fmt],4,4,out));
        reference(block,formats[fmt],4,4,want);assert(!memcmp(out,want,sizeof out));
    }
    assert(!sg_decode_dxt_image(block,sizeof block,0x12,4,4,out));
    assert(!sg_decode_dxt_image(block,sizeof block,0x0c,0,4,out));
    assert(!sg_decode_dxt_image(block,sizeof block,0x0c,4,0,out));
    for(unsigned trial=0;trial<300;trial++) {
        uint32_t w=1+rng()%91,h=1+rng()%71,pitch=(trial%4) ? w*4+(rng()%17) : 0;
        size_t bytes=(size_t)(h-1)*pitch+w*4;
        uint8_t *src=malloc(bytes);uint32_t *actual=malloc((size_t)w*h*4);
        for(size_t i=0;i<bytes;i++)src[i]=(uint8_t)rng();
        for(unsigned fmt=0;fmt<2;fmt++) {
            assert(sg_decode_linear32(src,bytes,fmt?0x1e:0x12,w,h,pitch,actual));
            for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++){
                uint32_t expected;memcpy(&expected,src+(size_t)y*pitch+x*4,4);
                if(fmt)expected|=0xff000000u;
                assert(actual[(size_t)y*w+x]==rgba(expected));
            }
            assert(!sg_decode_linear32(src,bytes-1,fmt?0x1e:0x12,w,h,pitch,actual));
        }
        free(src);free(actual);
    }
    puts("PASS 600 ARGB/XRGB images, padded/zero pitch, unaligned rows and truncated input");
    printf("PASS %u randomized DXT1/3/5 images, partial blocks, alpha endpoints, truncated input and output guards\n",cases);
    enum {W=256,H=256,REPS=24};
    static uint8_t src[W*H];uint32_t *image=malloc(W*H*4);volatile uint32_t checksum=0;
    for(unsigned i=0;i<sizeof src;i++)src[i]=(uint8_t)rng();
    double start=(double)clock()/CLOCKS_PER_SEC;
    for(unsigned i=0;i<REPS;i++){src[i]^=(uint8_t)(i+1);reference(src,0x0f,W,H,image);checksum^=sum(image,W*H);}
    double old=(double)clock()/CLOCKS_PER_SEC-start;start=(double)clock()/CLOCKS_PER_SEC;
    for(unsigned i=0;i<REPS;i++){src[i]^=(uint8_t)(i+1);assert(sg_decode_dxt_image(src,sizeof src,0x0f,W,H,image));checksum^=sum(image,W*H);}
    double fast=(double)clock()/CLOCKS_PER_SEC-start;
    printf("DXT5 upload benchmark: reference %.2f ms, bulk %.2f ms, %.2fx (checksum %u)\n",old*1000,fast*1000,old/fast,checksum);
    free(image);return 0;
}
'''.replace('HEADER',header).replace('/* DECODER */',decoder)
out=root/'build-web-tests/texture-decode';out.mkdir(parents=True,exist_ok=True)
(out/'test.c').write_text(harness,encoding='utf-8')
subprocess.run([shutil.which('emcc') or 'emcc',str(out/'test.c'),'-O3','-msimd128','-sENVIRONMENT=node','-o',str(out/'test.js')],check=True)
subprocess.run([shutil.which('node') or 'node',str(out/'test.js')],check=True)
