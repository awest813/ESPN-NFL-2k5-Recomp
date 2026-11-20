"""Verify live presentation geometry and the portable match-camera callback."""
from pathlib import Path
import argparse
import shutil
import subprocess


def main():
    root = Path(__file__).resolve().parents[2]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native',action='store_true')
    parser.add_argument('--build-dir',type=Path,default=root/'build-web-tests/widescreen')
    args=parser.parse_args()
    gpu = root / "external/xboxrecomp/src/video/present_layout.h"
    code = gpu.read_text(encoding="utf-8")
    layout = code
    harness = r'''
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "platform/guest_memory.h"
enum { AR_ORIGINAL, AR_STRETCH, AR_16_9, AR_21_9, AR_32_9, AR_ZOOM };
/* LIVE_LAYOUT */
static uint8_t guest[0x1000000];
extern "C" {
ptrdiff_t xbox_GetMemoryOffset(void) { return (ptrdiff_t)guest; }
int (*xbox_present_in_match_fn)(void);
void nfl2k5_presentation_init(void);
bool xbox_guest_memory_read(uintptr_t base, uint64_t va, void *out, size_t n) {
    if (va > sizeof guest || n > sizeof guest - va) return false;
    memcpy(out, (void *)(base+va), n); return true;
}
}
static void u32(uint32_t va, uint32_t value) { memcpy(guest+va,&value,4); }
static void f32(uint32_t va, float value) { memcpy(guest+va,&value,4); }
#define CHECK(c) do { if (!(c)) { fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#c); return 1; } } while (0)
int main() {
    XboxPresentLayout r=xbox_present_layout(720,480,1920,1080,40,1,AR_ORIGINAL);
    CHECK(r.sx==40 && r.sy==16 && r.sw==640 && r.sh==448);
    CHECK(r.dx==0 && r.dy==0 && r.dw==1920 && r.dh==1080);
    r=xbox_present_layout(720,480,1280,900,40,1,AR_ORIGINAL);
    CHECK(r.dw==1280 && r.dh==720 && r.dy==90); // no squeeze into a 4:3-ish window
    r=xbox_present_layout(720,480,2560,1080,40,1,AR_16_9);
    CHECK(r.dw==1920 && r.dh==1080 && r.dx==320);
    r=xbox_present_layout(720,480,2560,1080,40,1,AR_ORIGINAL);
    CHECK(r.dw==2560 && r.dh==1080 && fabsf(r.aspect-2560.f/1080)<0.00001f);
    r=xbox_present_layout(720,480,1920,1080,40,0,AR_ORIGINAL);
    CHECK(r.sx==40 && r.sy==0 && r.sw==640 && r.sh==480);
    CHECK(r.dw==1440 && r.dh==1080 && r.dx==240);
    r=xbox_present_layout(640,480,1920,1080,40,0,AR_ORIGINAL);
    CHECK(r.sx==0 && r.sy==0 && r.sw==640 && r.sh==480);
    r=xbox_present_layout(720,480,1280,900,40,1,AR_ZOOM);
    CHECK(r.sx==104 && r.sy==16 && r.sw==512 && r.sh==448 && r.dw==1280 && r.dh==900);
    uint32_t seed=17;
    for (unsigned i=0;i<10000;i++) {
        seed=seed*1664525u+1013904223u; uint32_t w=1+seed%8192;
        seed=seed*1664525u+1013904223u; uint32_t h=1+seed%8192;
        r=xbox_present_layout(720,480,w,h,(int)(i%91)-25,i&1,i%6);
        CHECK(r.sw && r.sh && r.sx+r.sw<=720 && r.sy+r.sh<=480);
        CHECK(r.dw && r.dh && r.dx+r.dw<=w && r.dy+r.dh<=h);
    }
    CHECK(!xbox_present_layout(0,480,1920,1080,40,1,0).dw);
    nfl2k5_presentation_init();
    CHECK(xbox_present_in_match_fn && !xbox_present_in_match_fn());
    u32(0xE6028C,0x20000); f32(0x20010,300); u32(0xE602C4,0);
    u32(0xE5FC68,0x21000); u32(0xE5FC28,0x22000);
    u32(0x21000,0); u32(0x21004,3); u32(0x22000,0); u32(0x22004,3);
    u32(0xA84C18,1);u32(0xA84B20,0x4E7EC0);
    CHECK(xbox_present_in_match_fn()); // pregame world camera
    /* Menus can retain valid clock/team records from attract or a match.
     * Select the visible top mode, rather than a menu lower in the stack. */
    const uint32_t menus[]={0x515660,0x5015CC,0x529AE0,0x529D48,0x52728C,
        0x526948,0x585474,0x585048,0x5038C8,0x52C6FC,0x5408A8,0x508610,
        0x51BDD8,0x525FCC,0x529344,0x509844,0x4E9078,0x4E8D70};
    for(uint32_t menu:menus){u32(0xA84B20,menu);CHECK(!xbox_present_in_match_fn());}
    const uint32_t worlds[]={0x4E7EC0,0x509710,0x57D9B8,0x524DD8};
    for(uint32_t world:worlds){u32(0xA84B20,world);CHECK(xbox_present_in_match_fn());}
    u32(0xA84B20,0x5015CC);u32(0xA84C18,2);u32(0xA84B28,0x4E7EC0);
    CHECK(xbox_present_in_match_fn());
    u32(0xA84C18,1);CHECK(!xbox_present_in_match_fn());
    u32(0xA84C18,31);u32(0xA84C10,0x4E7EC0);CHECK(xbox_present_in_match_fn());
    u32(0xA84C18,32);CHECK(!xbox_present_in_match_fn());
    u32(0xA84C18,0xFFFFFFFF);CHECK(!xbox_present_in_match_fn());
    u32(0xA84C18,0);u32(0xA84B18,0);CHECK(!xbox_present_in_match_fn());
    u32(0xA84B18,0x4E7EC0);CHECK(xbox_present_in_match_fn());
    u32(0xA84C18,1);u32(0xA84B20,0x4E7EC0);
    u32(0xE602C4,1); CHECK(xbox_present_in_match_fn());
    u32(0xAC7444,1); CHECK(!xbox_present_in_match_fn()); u32(0xAC7444,0);
    u32(0xB38C30,1); CHECK(!xbox_present_in_match_fn()); u32(0xB38C30,0);
    u32(0x21000,251); CHECK(!xbox_present_in_match_fn()); u32(0x21000,0);
    u32(0x22004,10); CHECK(!xbox_present_in_match_fn()); u32(0x22004,3);
    u32(0xE602C4,13); CHECK(!xbox_present_in_match_fn()); u32(0xE602C4,1);
    f32(0x20010,NAN); CHECK(!xbox_present_in_match_fn()); f32(0x20010,300);
    u32(0xE6028C,0xfffffff8u); CHECK(!xbox_present_in_match_fn());
    puts("PASS widescreen crop/aspect/zoom geometry, 10000 viewport bounds, stale match data in 18 menus, visible stack depth, world/training/pregame and panel camera states");
    return 0;
}
'''
    build = args.build_dir.resolve()
    build.mkdir(parents=True, exist_ok=True)
    source = build / "test.cpp"
    source.write_text(harness.replace("/* LIVE_LAYOUT */", layout), encoding="utf-8")
    if args.native:
        compiler=shutil.which('clang++') or shutil.which('c++')
        if not compiler:parser.error('Native C++ compiler required')
        output=build/'test'
        options=['-fsanitize=address,undefined','-fno-sanitize-recover=undefined']
        command=[str(output)]
    else:
        compiler,node=shutil.which('em++'),shutil.which('node')
        if not compiler or not node:parser.error('Emscripten em++ and Node required')
        output=build/'test.js'
        options=['-fsanitize=undefined','-fno-sanitize-recover=undefined','-sENVIRONMENT=node','-sINITIAL_MEMORY=67108864']
        command=[node,str(output)]
    subprocess.run([compiler,str(source),str(root/'src/platform/posix/presentation_stub.cpp'),
                    '-I'+str(root/'src'),'-I'+str(root/'external/xboxrecomp/src'),
                    '-O2',*options,'-o',str(output)],check=True)
    subprocess.run(command,check=True,timeout=60)


if __name__ == "__main__":
    main()
