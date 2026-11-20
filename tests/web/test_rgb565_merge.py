"""Execute production fragment merging against independent packed-color vectors."""
import argparse
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--native', action='store_true')
parser.add_argument('--build-dir', type=Path, default=root/'build-web-tests/rgb565-merge')
args = parser.parse_args()
source = (root/'external/xboxrecomp/src/kernel/nv2a_pb_exec.c').read_text(encoding='utf-8')


def function(signature):
    start = source.index(signature)
    return source[start:source.index('\n}\n', start)+3]


live = '\n'.join(function(s) for s in [
    'static void put_pixel(', 'static uint32_t blend_factor(',
    'static int alpha_test_pass(', 'static void shade_pixel('])
if 'static uint32_t surface_rgb565_load(' in source:
    live = function('static uint32_t surface_rgb565_load(') + live
code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "d3d/d3d8_swizzle.h"
static struct {uint32_t format,pitch,clip_x,clip_y,clip_w,clip_h,pixels,pixel_max;
    uint32_t alpha_test,alpha_ref,alpha_func,blend,blend_sf,blend_df,blend_eq,blend_color;} s_gpu;
static uint32_t g_color_mask=0x01010101u;
static uint8_t *s_surface;
static unsigned dirty;
static void surface_stage_dirty(uint32_t y,uint32_t first,uint32_t end) {
    assert(y==1 && first==2 && end==3);dirty++;
}
/* LIVE */
static uint32_t rng=0x52d14f3;
static uint32_t next(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static uint32_t packed(uint32_t c) {
    return (((c>>16)&255)/8)*2048+(((c>>8)&255)/4)*32+(c&255)/8;
}
static void channels(uint32_t c,unsigned out[4]) {
    for(unsigned i=0;i<4;i++)out[i]=(c>>(i==3?24:16-8*i))&255;
}
static uint32_t unpack(unsigned c) {
    return 0xFF000000u+((c/2048)*255/31)*65536+(((c/32)%64)*255/63)*256+(c%32)*255/31;
}
static unsigned factor(unsigned f,unsigned ch,const unsigned *s,const unsigned *d,const unsigned *k) {
    if(f==0)return 0;if(f==1)return 255;
    if(f==0x300)return s[ch];if(f==0x301)return 255-s[ch];
    if(f==0x302)return s[3];if(f==0x303)return 255-s[3];
    if(f==0x304)return d[3];if(f==0x305)return 255-d[3];
    if(f==0x306)return d[ch];if(f==0x307)return 255-d[ch];
    if(f==0x308)return ch==3?255:(s[3]<255-d[3]?s[3]:255-d[3]);
    if(f==0x8001)return k[ch];if(f==0x8002)return 255-k[ch];
    assert(0);return 0;
}
static uint32_t reference(uint32_t src,uint32_t dst) {
    unsigned s[4],d[4],k[4];channels(src,s);channels(dst,d);channels(s_gpu.blend_color,k);
    uint32_t out=0;
    for(unsigned ch=0;ch<4;ch++) {
        int a=s[ch]*factor(s_gpu.blend_sf,ch,s,d,k)/255;
        int b=d[ch]*factor(s_gpu.blend_df,ch,s,d,k)/255;
        int v=a+b;
        if(s_gpu.blend_eq==0x800A)v=a-b;
        if(s_gpu.blend_eq==0x800B)v=b-a;
        if(s_gpu.blend_eq==0x8007)v=s[ch]<d[ch]?s[ch]:d[ch];
        if(s_gpu.blend_eq==0x8008)v=s[ch]>d[ch]?s[ch]:d[ch];
        if(v<0)v=0;if(v>255)v=255;
        unsigned sh=ch==3?24:16-8*ch;
        if(!(g_color_mask&(1u<<sh)))v=d[ch];
        out|=(uint32_t)v<<sh;
    }
    return out;
}
static void check(unsigned bits,uint32_t src,uint32_t dst) {
    uint32_t storage[24];memset(storage,0xA5,sizeof storage);s_surface=(uint8_t *)storage;
    unsigned bpp=bits/8;size_t at=32+2*bpp;
    s_gpu.pitch=32;s_gpu.format=bits==16?0x103:0x108;
    s_gpu.clip_x=2;s_gpu.clip_y=1;s_gpu.clip_w=s_gpu.clip_h=1;
    uint32_t expected=reference(src,dst);if(bits==16){dst=packed(dst);expected=packed(expected);}
    memcpy(s_surface+at,&dst,bpp);dirty=0;
    shade_pixel(NULL,bpp,2,1,src);
    uint32_t actual=0;memcpy(&actual,s_surface+at,bpp);assert(actual==expected);
    for(size_t i=0;i<sizeof storage;i++)if(i<at||i>=at+bpp)assert(s_surface[i]==0xA5);
    assert(dirty==(g_color_mask!=0));
    uint32_t saved[24];memcpy(saved,storage,sizeof storage);dirty=0;
    shade_pixel(NULL,bpp,-1,1,src);shade_pixel(NULL,bpp,3,1,src);
    shade_pixel(NULL,bpp,2,0,src);shade_pixel(NULL,bpp,2,2,src);
    s_gpu.alpha_test=1;s_gpu.alpha_func=0x200;shade_pixel(NULL,bpp,2,1,src);s_gpu.alpha_test=0;
    assert(!dirty && !memcmp(storage,saved,sizeof storage));
}
int main(void) {
    const unsigned pairs[][2]={{1,0},{0,1},{0x302,0x303},{0x304,0x305},
        {0x305,0x304},{0x306,0x300},{0x8001,0x8002},{0x308,1},
        {0x300,0x306},{0x301,0x307}};
    const unsigned equations[]={0x8006,0x800A,0x800B,0x8007,0x8008};
    unsigned cases=0;s_gpu.blend=1;
    for(unsigned v=0;v<65536;v++) {
        g_color_mask=0x01010101u;s_gpu.blend_sf=0;s_gpu.blend_df=1;s_gpu.blend_eq=0x8006;
        check(16,next(),unpack(v));cases++;
        unsigned pair=(v/16)%10,mask=v%16;
        s_gpu.blend_sf=pairs[pair][0];s_gpu.blend_df=pairs[pair][1];
        s_gpu.blend_eq=equations[(v/160)%5];s_gpu.blend_color=next();
        g_color_mask=((mask&1)?0x10000:0)|((mask&2)?0x100:0)|((mask&4)?1:0)|((mask&8)?0x1000000:0);
        uint32_t src=next(),dst=unpack(v);check(16,src,dst);check(32,src,dst);cases+=2;
    }
    puts("PASS 196608 packed/32-bit fragment cases: all RGB565 destinations, ten factor pairs, five equations, all channel masks, alpha rejection and clipped guards");
    assert(cases==196608);return 0;
}
'''.replace('/* LIVE */', live)
out=args.build_dir.resolve();out.mkdir(parents=True,exist_ok=True)
(out/'test.c').write_bytes(code.encode('utf-8'))
compiler=(shutil.which('clang') or shutil.which('cc')) if args.native else shutil.which('emcc')
if not compiler:parser.error('Compiler required')
binary=out/('test' if args.native else 'test.js')
flags=['-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined']
if args.native:flags+=['-fsanitize=address','-fno-omit-frame-pointer']
else:flags+=['-sENVIRONMENT=node']
subprocess.run([compiler,str(out/'test.c'),'-I'+str(root/'external/xboxrecomp/src'),*flags,'-o',str(binary)],check=True)
subprocess.run([str(binary)] if args.native else [shutil.which('node') or 'node',str(binary)],check=True,timeout=60)
