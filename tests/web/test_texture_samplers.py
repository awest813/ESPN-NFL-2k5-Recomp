"""Check the live sampler mapping used by stadium materials and intro text."""
from pathlib import Path
import shutil
import subprocess


def main():
    root = Path(__file__).resolve().parents[2]
    source = (root / "external/xboxrecomp/src/kernel/sdlgpu/sdlgpu_texture.inc.c").read_text(encoding="utf-8")
    live = source[source.index("#define SG_SAMPLER_KEYS"):source.index("static int sg_stage_sample(")]
    harness = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#define NV_TEX_FIRST 0x1B00
enum { SDL_GPU_FILTER_NEAREST, SDL_GPU_FILTER_LINEAR,
       SDL_GPU_SAMPLERMIPMAPMODE_NEAREST, SDL_GPU_SAMPLERMIPMAPMODE_LINEAR,
       SDL_GPU_SAMPLERADDRESSMODE_REPEAT, SDL_GPU_SAMPLERADDRESSMODE_MIRRORED_REPEAT,
       SDL_GPU_SAMPLERADDRESSMODE_CLAMP_TO_EDGE };
typedef int SDL_GPUSamplerAddressMode;
typedef struct { int min_filter, mag_filter, mipmap_mode, address_mode_u, address_mode_v, address_mode_w;
                 float min_lod, max_lod; } SDL_GPUSamplerCreateInfo;
typedef struct { SDL_GPUSamplerCreateInfo info; int released; } SDL_GPUSampler;
typedef struct { uint32_t color, addr_u, addr_v; } Texture;
static Texture tx[4];
static uint32_t s_tex_reg[256];
static struct { void *dev; SDL_GPUSampler *point; } s_sg;
static SDL_GPUSampler objects[32768];
static unsigned created,releases,flushes;
static int fail_next_create;
static int sg_queue_flush(void) {flushes++;return 1;}
static void SDL_ReleaseGPUSampler(void *dev,SDL_GPUSampler *sampler);
static const Texture *sg_stage_texture(int st) { return &tx[st]; }
static unsigned authored_levels=4;
static uint32_t texture_mip_levels(int st,const Texture *texture) { (void)st;(void)texture;return authored_levels; }
static int tex_size_from_format(uint32_t format) { return format == 0x06; }
static SDL_GPUSampler *SDL_CreateGPUSampler(void *dev, const SDL_GPUSamplerCreateInfo *info) {
    (void)dev; if (created == 32768) abort();
    if(fail_next_create){fail_next_create=0;return NULL;}
    objects[created].info = *info; return &objects[created++];
}
/* LIVE */
static void SDL_ReleaseGPUSampler(void *dev,SDL_GPUSampler *sampler) {
    (void)dev;if(flushes<=releases || sampler->released)abort();
    for(unsigned st=0;st<4;st++)if(s_sg_lod_stage[st] && s_sg_lod_stage[st]->sampler==sampler)abort();
    sampler->released=1;releases++;
}
#define CHECK(c) do { if (!(c)) { fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#c); return 1; } } while (0)
static SDL_GPUSampler *get(int st, unsigned min, unsigned mag, unsigned format, unsigned u, unsigned v) {
    tx[st] = (Texture){format,u,v};
    s_tex_reg[(0x1B14 + st*0x40 - NV_TEX_FIRST)/4] = (mag<<24)|(min<<16);
    s_tex_reg[(0x1B0C + st*0x40 - NV_TEX_FIRST)/4] = 0x4003FFC0u;
    return sg_sampler_for_stage(st);
}
int main(void) {
    /* A bilinear, non-mipmapped font must stay at level zero even when
     * minified; a nearest magnifier must not change its minification mode. */
    SDL_GPUSampler *font = get(0,2,1,0x06,3,3);
    CHECK(font->info.min_filter == SDL_GPU_FILTER_LINEAR);
    CHECK(font->info.mag_filter == SDL_GPU_FILTER_NEAREST);
    CHECK(font->info.max_lod == 0.25f && font->info.mipmap_mode == SDL_GPU_SAMPLERMIPMAPMODE_NEAREST);
    SDL_GPUSampler *mixed = get(0,1,2,0x06,3,3);
    CHECK(mixed != font && mixed->info.min_filter == SDL_GPU_FILTER_NEAREST);
    CHECK(mixed->info.mag_filter == SDL_GPU_FILTER_LINEAR && mixed->info.max_lod == 0.25f);
    for (unsigned mode=1; mode<=7; mode++) for (unsigned mag=1; mag<=2; mag++) {
        SDL_GPUSampler *s = get(0,mode,mag,0x06,1,2);
        CHECK(s->info.min_filter == ((mode==1||mode==3||mode==5)?SDL_GPU_FILTER_NEAREST:SDL_GPU_FILTER_LINEAR));
        CHECK(s->info.mag_filter == (mag==1?SDL_GPU_FILTER_NEAREST:SDL_GPU_FILTER_LINEAR));
        CHECK(s->info.mipmap_mode == (mode==5||mode==6?SDL_GPU_SAMPLERMIPMAPMODE_LINEAR:SDL_GPU_SAMPLERMIPMAPMODE_NEAREST));
        CHECK((s->info.max_lod > 0.5f) == (mode>=3 && mode<=6));
        CHECK(s->info.address_mode_u == SDL_GPU_SAMPLERADDRESSMODE_REPEAT);
        CHECK(s->info.address_mode_v == SDL_GPU_SAMPLERADDRESSMODE_MIRRORED_REPEAT);
        CHECK(get(2,mode,mag,0x06,1,2) == s);
    }
    SDL_GPUSampler *rect = get(0,6,2,0x12,3,3);
    CHECK(rect->info.max_lod == 0.25f && rect->info.mipmap_mode == SDL_GPU_SAMPLERMIPMAPMODE_NEAREST); /* linear RTTs have no guest mip chain */
    CHECK(get(0,6,2,0x06,3,3) != rect); /* format affects sampler key */
    CHECK(get(3,2,1,0x06,3,3) == font);
    const unsigned limits[]={0,1,64,192,255,256,257,320,448,512,768,2048,3072,3328,4095};
    for(unsigned count=1;count<=13;count++)for(unsigned a=0;a<15;a++)for(unsigned b=0;b<15;b++) {
        authored_levels=count;
        for(unsigned mode=3;mode<=6;mode+=3) {
            get(0,mode,1,0x06,3,3);
            s_tex_reg[(0x1B0C-NV_TEX_FIRST)/4]=0x40000000u|(limits[a]<<18)|(limits[b]<<6);
            SDL_GPUSampler *s=sg_sampler_for_stage(0);
            unsigned last=(count-1)*256,hi=limits[b]<last?limits[b]:last,lo=limits[a]<hi?limits[a]:hi;
            int unrestricted=lo==0 && hi==last;
            CHECK(s->info.min_lod==(float)lo/256.0f && s->info.max_lod==(unrestricted?1000.0f:hi?(float)hi/256.0f:0.25f));
            CHECK(s->info.mipmap_mode==(((hi||unrestricted) && mode==6)?SDL_GPU_SAMPLERMIPMAPMODE_LINEAR:SDL_GPU_SAMPLERMIPMAPMODE_NEAREST));
            get(2,mode,1,0x06,3,3);
            s_tex_reg[(0x1B0C+2*0x40-NV_TEX_FIRST)/4]=0x40000000u|(lo<<18)|(hi<<6);
            CHECK(sg_sampler_for_stage(2)==s); /* canonical ranges share samplers across stages */
        }
    }
    authored_levels=13;
    SDL_GPUSampler *held[3];
    for(unsigned st=1;st<4;st++) {
        get(st,6,1,0x06,3,3);s_tex_reg[(0x1B0C+st*64-NV_TEX_FIRST)/4]=0x40000000u|(64u<<18)|(64u<<6);
        held[st-1]=sg_sampler_for_stage(st);
    }
    for(unsigned raw=1;raw<=256;raw++) {
        get(0,6,1,0x06,3,3);s_tex_reg[(0x1B0C-NV_TEX_FIRST)/4]=0x40000000u|(raw<<18)|(raw<<6);
        CHECK(!sg_sampler_for_stage(0)->released);
        for(unsigned st=1;st<4;st++)CHECK(!held[st-1]->released && s_sg_lod_stage[st]->sampler==held[st-1]);
    }
    CHECK(releases>0 && releases==flushes);
    s_tex_reg[(0x1B0C-NV_TEX_FIRST)/4]=0x40000000u|(1933u<<18)|(1933u<<6);fail_next_create=1;
    CHECK(sg_sampler_for_stage(0)==s_sg.point && !fail_next_create);
    for(unsigned format=0;format<2;format++) {
        get(0,format?6:2,1,format?0x12:0x06,3,3);
        s_tex_reg[(0x1B0C-NV_TEX_FIRST)/4]=0x7FFFFFC0u;
        CHECK(sg_sampler_for_stage(0)->info.min_lod==0 && sg_sampler_for_stage(0)->info.max_lod==0.25f);
    }
    for(unsigned st=0;st<4;st++)for(unsigned raw=0;raw<8192;raw++) {
        s_tex_reg[(0x1B14+st*0x40-NV_TEX_FIRST)/4]=0x01030000u|raw;
        float expected=(float)(raw<4096?(int)raw:(int)raw-8192)/256.0f;
        CHECK(sg_texture_lod_bias(st)==expected);
    }
    puts("PASS independent min/mag filters, seven min modes, linear RTT LOD0 and sampler reuse");
    puts("PASS all 8192 signed 5.8 LOD-bias encodings on each of four stages");
    puts("PASS 5850 fractional LOD ranges, tails, inverted/oversized bounds, LOD0 overrides and cross-stage reuse");
    puts("PASS bounded fractional-sampler eviction flushes queued handles and protects assembled stages; allocation failure is recoverable");
    return 0;
}
'''
    build = root / "build-web-tests/texture-samplers"
    build.mkdir(parents=True, exist_ok=True)
    test, output = build / "test.c", build / "test.js"
    test.write_text(harness.replace("/* LIVE */", live), encoding="utf-8")
    emcc, node = shutil.which("emcc"), shutil.which("node")
    if not emcc or not node:
        raise SystemExit("Emscripten emcc and Node must be on PATH")
    subprocess.run([emcc, str(test), "-O2", "-sENVIRONMENT=node", "-o", str(output)], check=True)
    subprocess.run([node, str(output)], check=True)


if __name__ == "__main__":
    main()
