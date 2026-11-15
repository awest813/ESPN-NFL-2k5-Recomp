"""Verify live presentation geometry and the portable match-camera callback."""
from pathlib import Path
import shutil
import subprocess


def main():
    root = Path(__file__).resolve().parents[2]
    gpu = root / "external/xboxrecomp/src/kernel/sdlgpu/sdlgpu_present.inc.c"
    code = gpu.read_text(encoding="utf-8")
    layout = code[code.index("/* Presentation geometry."):code.index("/* Pace completed")]
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
    SgPresentLayout r=sg_present_layout(720,480,1920,1080,40,1,AR_ORIGINAL);
    CHECK(r.sx==40 && r.sy==16 && r.sw==640 && r.sh==448);
    CHECK(r.dx==0 && r.dy==0 && r.dw==1920 && r.dh==1080);
    r=sg_present_layout(720,480,1280,900,40,1,AR_ORIGINAL);
    CHECK(r.dw==1280 && r.dh==720 && r.dy==90); // no squeeze into a 4:3-ish window
    r=sg_present_layout(720,480,2560,1080,40,1,AR_16_9);
    CHECK(r.dw==1920 && r.dh==1080 && r.dx==320);
    r=sg_present_layout(720,480,2560,1080,40,1,AR_ORIGINAL);
    CHECK(r.dw==2560 && r.dh==1080 && fabsf(r.aspect-2560.f/1080)<0.00001f);
    r=sg_present_layout(720,480,1920,1080,40,0,AR_ORIGINAL);
    CHECK(r.sx==40 && r.sy==0 && r.sw==640 && r.sh==480);
    CHECK(r.dw==1440 && r.dh==1080 && r.dx==240);
    r=sg_present_layout(640,480,1920,1080,40,0,AR_ORIGINAL);
    CHECK(r.sx==0 && r.sy==0 && r.sw==640 && r.sh==480);
    r=sg_present_layout(720,480,1280,900,40,1,AR_ZOOM);
    CHECK(r.sx==104 && r.sy==16 && r.sw==512 && r.sh==448 && r.dw==1280 && r.dh==900);
    uint32_t seed=17;
    for (unsigned i=0;i<10000;i++) {
        seed=seed*1664525u+1013904223u; uint32_t w=1+seed%8192;
        seed=seed*1664525u+1013904223u; uint32_t h=1+seed%8192;
        r=sg_present_layout(720,480,w,h,(int)(i%91)-25,i&1,i%6);
        CHECK(r.sw && r.sh && r.sx+r.sw<=720 && r.sy+r.sh<=480);
        CHECK(r.dw && r.dh && r.dx+r.dw<=w && r.dy+r.dh<=h);
    }
    CHECK(!sg_present_layout(0,480,1920,1080,40,1,0).dw);
    nfl2k5_presentation_init();
    CHECK(xbox_present_in_match_fn && !xbox_present_in_match_fn());
    u32(0xE6028C,0x20000); f32(0x20010,300); u32(0xE602C4,0);
    u32(0xE5FC68,0x21000); u32(0xE5FC28,0x22000);
    u32(0x21000,0); u32(0x21004,3); u32(0x22000,0); u32(0x22004,3);
    CHECK(xbox_present_in_match_fn()); // pregame world camera
    u32(0xE602C4,1); CHECK(xbox_present_in_match_fn());
    u32(0xAC7444,1); CHECK(!xbox_present_in_match_fn()); u32(0xAC7444,0);
    u32(0xB38C30,1); CHECK(!xbox_present_in_match_fn()); u32(0xB38C30,0);
    u32(0x21000,251); CHECK(!xbox_present_in_match_fn()); u32(0x21000,0);
    u32(0x22004,10); CHECK(!xbox_present_in_match_fn()); u32(0x22004,3);
    u32(0xE602C4,13); CHECK(!xbox_present_in_match_fn()); u32(0xE602C4,1);
    f32(0x20010,NAN); CHECK(!xbox_present_in_match_fn()); f32(0x20010,300);
    u32(0xE6028C,0xfffffff8u); CHECK(!xbox_present_in_match_fn());
    puts("PASS widescreen crop/aspect/zoom geometry, 10000 viewport bounds, gameplay/pregame and panel camera states");
    return 0;
}
'''
    build = root / "build-web-tests/widescreen"
    build.mkdir(parents=True, exist_ok=True)
    source, output = build / "test.cpp", build / "test.js"
    source.write_text(harness.replace("/* LIVE_LAYOUT */", layout), encoding="utf-8")
    empp, node = shutil.which("em++"), shutil.which("node")
    if not empp or not node:
        raise SystemExit("Emscripten em++ and Node must be on PATH")
    subprocess.run([empp, str(source), str(root / "src/platform/posix/presentation_stub.cpp"),
                    "-I"+str(root / "src"), "-I"+str(root / "external/xboxrecomp/src"),
                    "-O2", "-sENVIRONMENT=node", "-sINITIAL_MEMORY=67108864", "-o", str(output)], check=True)
    subprocess.run([node, str(output)], check=True)


if __name__ == "__main__":
    main()
