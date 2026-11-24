"""Exercise incremental WebGPU geometry uploads with a memory-backed queue."""

import argparse
from pathlib import Path
import shutil
import subprocess


root = Path(__file__).resolve().parents[2]
gpu = root / "external/xboxrecomp/src/kernel/sdlgpu"
backend = (gpu / "webgpu/sdl_gpu_webgpu.c").read_text(encoding="utf-8")
begin = backend.index("static void upload_geometry(")
upload = backend[begin:backend.index("static void replay(", begin)]
harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sg_bytes_equal.h"

typedef struct { uint8_t *buf, *uploaded; uint32_t uploaded_bytes; } WgBufferStorage;
#define SDL_min(a,b) ((a)<(b) ? (a) : (b))
#define SDL_max(a,b) ((a)>(b) ? (a) : (b))
enum { CAPACITY = 131072 };
static int s_queue, fail_allocation;
static uint32_t count, written, last_offset;

static void wgpuQueueWriteBuffer(int queue, uint8_t *dst, uint32_t offset,
                                 const uint8_t *data, uint32_t size) {
    (void)queue;
    assert(((offset|size)&3u)==0 && size<=CAPACITY && offset<=CAPACITY-size);
    memcpy(dst+offset,data,size);
    count++;
    written+=size;
    last_offset=offset;
}

static void *try_realloc(void *p, size_t n) { return fail_allocation ? NULL : realloc(p,n); }
#define realloc try_realloc
/* UPLOAD */
#undef realloc

int main(void) {
    static uint8_t source[CAPACITY], buffer[CAPACITY], expected[CAPACITY];
    WgBufferStorage storage={.buf=buffer};
    memset(buffer,0x7d,sizeof buffer);
    memset(source,0x25,5004);
    upload_geometry(&storage,0,source,5004);
    assert(count==1 && written==5004);
    count=written=0;
    upload_geometry(&storage,0,source,94004);
    assert(count==1 && written==89000 && last_offset==5004);
    assert(!memcmp(source,buffer,94004) && buffer[94004]==0x7d);

    count=written=0;
    source[3]^=1;
    upload_geometry(&storage,0,source,98004);
    assert(count==2 && written==8096 && last_offset==94004);
    assert(!memcmp(source,buffer,98004));
    source[12]^=1;
    upload_geometry(&storage,0,source,2000);
    assert(storage.uploaded_bytes==98004);
    count=written=0;
    upload_geometry(&storage,0,source,98004);
    assert(count==0 && !memcmp(source,buffer,98004));

    fail_allocation=1;
    upload_geometry(&storage,0,source,100000);
    assert(count==1 && written==100000 && storage.uploaded_bytes==0);
    fail_allocation=0;
    uint32_t seed=0x73abc13u;
    for(unsigned i=0;i<400;i++) {
        uint32_t offset=i%17==0 ? 4 : 0;
        uint32_t size=(seed%(CAPACITY-offset+1))&~3u;
        for(unsigned j=0;j<8;j++) {
            seed=1664525u*seed+1013904223u;
            source[seed%CAPACITY]^=(uint8_t)seed;
        }
        memcpy(expected,buffer,sizeof buffer);
        memcpy(expected+offset,source,size);
        fail_allocation=i%11==0;
        upload_geometry(&storage,offset,source,size);
        assert(!memcmp(buffer,expected,sizeof buffer));
    }
    free(storage.uploaded);
    puts("PASS geometry growth reuses unchanged bytes and preserves upload contents");
    return 0;
}
'''

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--build-dir", type=Path, default=root / "build-web-tests/geometry-upload")
out = parser.parse_args().build_dir.resolve()
out.mkdir(parents=True, exist_ok=True)
source = out / "test.c"
source.write_text(harness.replace("/* UPLOAD */", upload), encoding="utf-8")
for name, flags in (("simd", ["-msimd128"]), ("scalar", [])):
    output = out / (name + ".js")
    subprocess.run([shutil.which("emcc") or "emcc", str(source), "-I", str(gpu),
                    "-O2", "-sENVIRONMENT=node", *flags, "-o", str(output)], check=True)
    subprocess.run([shutil.which("node") or "node", str(output)], check=True)
