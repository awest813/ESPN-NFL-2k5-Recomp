"""Run the production Web frame pacer and texture lookup against edge cases."""
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
kernel = root / "external/xboxrecomp/src/kernel/sdlgpu"
texture = (kernel / "sdlgpu_texture.inc.c").read_text(encoding="utf-8")
lookup = texture[texture.index("#define SG_TEXTURE_HINTS"):texture.index("/* Hashing a texture")]
present = (kernel / "sdlgpu_present.inc.c").read_text(encoding="utf-8")
pacer = present[present.index("static void sg_frame_pace("):present.index("static struct {")]
out = root / "build-web-tests/frame-pacing"
out.mkdir(parents=True, exist_ok=True)
source = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#define SG_MAX_TEXTURES 512
typedef struct { uint64_t key; uint32_t w,h,layers; } SgCachedTexture;
static SgCachedTexture s_sg_textures[SG_MAX_TEXTURES];
static uint64_t clock_ns, waited;
static int limit=30, releases, reacquires;
static uint64_t SDL_GetTicksNS(void) { return clock_ns; }
static void SDL_DelayNS(uint64_t n) { clock_ns+=n; waited+=n; }
static int xbox_VideoFpsLimit(void) { return limit; }
static int xbox_ggl_release_all(void) { releases++; return 3; }
static void xbox_ggl_reacquire(int depth) { assert(depth==3); reacquires++; }
/* PRODUCTION */
int main(void) {
    for (int i=0;i<512;i++) s_sg_textures[i]=(SgCachedTexture){1u+(uint64_t)i*2048u,64,64,1};
    for (int pass=0;pass<4;pass++) for (int i=0;i<512;i++)
        assert(sg_texture_find(s_sg_textures[i].key,64,64,1)==&s_sg_textures[i]);
    assert(!sg_texture_find(s_sg_textures[511].key,64,64,6));
    uint64_t old=s_sg_textures[511].key;
    s_sg_textures[511]=(SgCachedTexture){77777777,32,32,6};
    assert(!sg_texture_find(old,64,64,1));
    assert(sg_texture_find(77777777,32,32,6)==&s_sg_textures[511]);
    puts("ok: texture lookup handles collisions, stale eviction hints and cube dimensions");
    clock_ns=1000000000ull; sg_frame_pace();
    for (int i=0;i<300;i++) {
        uint64_t previous=clock_ns;
        clock_ns+=(10000000u+(i%4)*4000000u);
        sg_frame_pace();
        assert(clock_ns-previous==33333333u);
    }
    assert(releases==reacquires && releases==300);
    puts("ok: 300 variable-work frames maintain 30 Hz and release/reacquire the guest lock");
    clock_ns+=200000000u; sg_frame_pace();
    uint64_t previous=clock_ns;
    clock_ns+=10000000u; sg_frame_pace();
    assert(clock_ns-previous==33333333u);
    puts("ok: slow frame resets the deadline without a catch-up burst");
    limit=0; previous=waited; sg_frame_pace();
    assert(waited==previous);
    limit=30; sg_frame_pace();
    assert(waited==previous);
    puts("ok: uncapped mode and re-enabling the cap reset timing");
}
'''.replace("/* PRODUCTION */", lookup + pacer)
(out / "test.c").write_text(source, encoding="utf-8")
subprocess.run([shutil.which("emcc") or "emcc", str(out / "test.c"), "-O2", "-sENVIRONMENT=node", "-o", str(out / "test.js")],check=True)
subprocess.run([shutil.which("node") or "node", str(out / "test.js")],check=True)
