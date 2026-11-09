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
typedef struct { SDL_GPUSamplerCreateInfo info; } SDL_GPUSampler;
typedef struct { uint32_t color, addr_u, addr_v; } Texture;
static Texture tx[4];
static uint32_t s_tex_reg[256];
static struct { void *dev; SDL_GPUSampler *point; } s_sg;
static SDL_GPUSampler objects[2048];
static unsigned created;
static const Texture *sg_stage_texture(int st) { return &tx[st]; }
static int tex_size_from_format(uint32_t format) { return format == 0x06; }
static SDL_GPUSampler *SDL_CreateGPUSampler(void *dev, const SDL_GPUSamplerCreateInfo *info) {
    (void)dev; if (created == 2048) abort();
    objects[created].info = *info; return &objects[created++];
}
/* LIVE */
#define CHECK(c) do { if (!(c)) { fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#c); return 1; } } while (0)
static SDL_GPUSampler *get(int st, unsigned min, unsigned mag, unsigned format, unsigned u, unsigned v) {
    tx[st] = (Texture){format,u,v};
    s_tex_reg[(0x1B14 + st*0x40 - NV_TEX_FIRST)/4] = (mag<<24)|(min<<16);
    return sg_sampler_for_stage(st);
}
int main(void) {
    /* A bilinear, non-mipmapped font must stay at level zero even when
     * minified; a nearest magnifier must not change its minification mode. */
    SDL_GPUSampler *font = get(0,2,1,0x06,3,3);
    CHECK(font->info.min_filter == SDL_GPU_FILTER_LINEAR);
    CHECK(font->info.mag_filter == SDL_GPU_FILTER_NEAREST);
    CHECK(font->info.max_lod == 0);
    SDL_GPUSampler *mixed = get(0,1,2,0x06,3,3);
    CHECK(mixed != font && mixed->info.min_filter == SDL_GPU_FILTER_NEAREST);
    CHECK(mixed->info.mag_filter == SDL_GPU_FILTER_LINEAR && mixed->info.max_lod == 0);
    for (unsigned mode=1; mode<=7; mode++) for (unsigned mag=1; mag<=2; mag++) {
        SDL_GPUSampler *s = get(0,mode,mag,0x06,1,2);
        CHECK(s->info.min_filter == ((mode==1||mode==3||mode==5)?SDL_GPU_FILTER_NEAREST:SDL_GPU_FILTER_LINEAR));
        CHECK(s->info.mag_filter == (mag==1?SDL_GPU_FILTER_NEAREST:SDL_GPU_FILTER_LINEAR));
        CHECK(s->info.mipmap_mode == (mode==5||mode==6?SDL_GPU_SAMPLERMIPMAPMODE_LINEAR:SDL_GPU_SAMPLERMIPMAPMODE_NEAREST));
        CHECK((s->info.max_lod > 0) == (mode>=3 && mode<=6));
        CHECK(s->info.address_mode_u == SDL_GPU_SAMPLERADDRESSMODE_REPEAT);
        CHECK(s->info.address_mode_v == SDL_GPU_SAMPLERADDRESSMODE_MIRRORED_REPEAT);
        CHECK(get(2,mode,mag,0x06,1,2) == s);
    }
    SDL_GPUSampler *rect = get(0,6,2,0x12,3,3);
    CHECK(rect->info.max_lod == 0); /* linear RTTs have no guest mip chain */
    CHECK(get(0,6,2,0x06,3,3) != rect); /* format affects sampler key */
    CHECK(get(3,2,1,0x06,3,3) == font);
    puts("PASS independent min/mag filters, seven min modes, linear RTT LOD0 and sampler reuse");
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
