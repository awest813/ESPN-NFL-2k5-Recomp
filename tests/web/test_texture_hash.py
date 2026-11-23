"""Exercise the live texture hash memo with aligned Xbox-style allocations."""
from pathlib import Path
import argparse
import shutil
import subprocess


def main():
    root = Path(__file__).resolve().parents[2]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,default=root/'external/xboxrecomp')
    parser.add_argument('--build-dir',type=Path,default=root/'build-web-tests/texture-hash')
    parser.add_argument('--native',action='store_true')
    parser.add_argument('--scalar',action='store_true')
    args=parser.parse_args()
    src = (args.runtime / "src/kernel/sdlgpu/sdlgpu_texture.inc.c").read_text(encoding="utf-8")
    memo = src[src.index("#define SG_HASH_MEMO"):src.index("/* One decode buffer")]
    start=src.find("static int sg_texture_bytes_equal(")
    if "s_sg_hash_copy_cursor" in memo:memo="#define TEST_PERSISTENT_COPY 1\n"+memo
    hashing=src[start if start>=0 else src.index("static uint64_t sg_hash("):src.index("/* Decode each DXT block")]
    if start<0:hashing='static int sg_texture_bytes_equal(const uint8_t*a,const uint8_t*b,size_t n){return memcmp(a,b,n)==0;}\n'+hashing
    if 'static int sg_texture_copy_equal(' in hashing:
        hashing = '#define TEST_PATTERN_COPY 1\n' + hashing
    harness = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef __wasm_simd128__
#include <wasm_simd128.h>
#endif
typedef struct { unsigned width, height, color, pitch; } Texture;
typedef struct { uint8_t *pixels; size_t bytes; int owned; uint32_t palette[256]; } TextureSnapshot;
static Texture tx[4];
static TextureSnapshot s_texture_snapshot[4];
static struct { uint64_t texture_hash_bytes,texture_compare_bytes,texture_compare_ticks; } s_sg_stats;
static uint64_t sg_profile_now(void) { return 0; }
static const Texture *sg_stage_texture(int st) { return &tx[st]; }
static uint32_t levels[4] = {1,1,1,1};
static uint32_t texture_mip_levels(int st, const Texture *texture) { (void)texture; return levels[st]; }
static int fail_hash_allocation;
static void *hash_test_allocate(size_t bytes) {return fail_hash_allocation?NULL:malloc(bytes);}
#define malloc hash_test_allocate
/* LIVE_HASH */
#undef malloc
#define CHECK(c) do { if (!(c)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); return 1; } } while (0)
int main(void) {
#ifdef TEST_PATTERN_COPY
    /* A nonuniform prefix and tail surround two different periodic runs.
     * Check every byte in the retained image, including both boundaries. */
    {
        enum { length = 10 * 1024 + 3 };
        uint8_t *stored = malloc(length + 1), *guest = malloc(length + 1);
        CHECK(stored && guest);
        SgHashMemo m = {.checked=stored+1, .bytes=length};
        for(unsigned i=0;i<length;i++)
            m.checked[i] = i<1024 || i>=9*1024 ? (uint8_t)(i^(i>>4))
                : (uint8_t)((i&15)+(i>=5*1024 ? 37 : 0));
        memcpy(guest+1,m.checked,length);
        sg_texture_pattern(&m,m.checked,length);
#ifdef __wasm_simd128__
        CHECK(m.pattern_offset==1024 && m.pattern_bytes==4096);
#endif
        CHECK(sg_texture_copy_equal(&m,guest+1));
        for(unsigned i=0;i<length;i++) {
            guest[1+i]^=128; CHECK(!sg_texture_copy_equal(&m,guest+1)); guest[1+i]^=128;
        }
        sg_texture_pattern(&m,NULL,length); CHECK(!m.pattern_bytes);
        free(stored);free(guest);
    }
#endif
    /* Misalignment, vector boundaries, tails and exact allocation ends. */
    for(unsigned length=0;length<=131;length++)for(unsigned offset=0;offset<16;offset++) {
        uint8_t *a=malloc(length+offset+1),*b=malloc(length+offset+1);
        CHECK(a && b);memset(a,0x5A,length+offset+1);memset(b,0x5A,length+offset+1);
        CHECK(sg_texture_bytes_equal(a+offset,b+offset,length));
        for(unsigned k=0;k<length;k++) {
            b[offset+k]^=1;CHECK(!sg_texture_bytes_equal(a+offset,b+offset,length));b[offset+k]^=1;
        }
        b[offset+length]^=1;CHECK(sg_texture_bytes_equal(a+offset,b+offset,length));
        free(a);free(b);
        size_t exact=length+offset;if(!exact)exact=1;
        a=malloc(exact);b=malloc(exact);CHECK(a && b);
        memset(a,0x5A,exact);memset(b,0x5A,exact);
        CHECK(sg_texture_bytes_equal(a+offset,b+offset,length));
        if(length){b[offset+length-1]^=1;CHECK(!sg_texture_bytes_equal(a+offset,b+offset,length));}
        free(a);free(b);
    }
    uint8_t *data = aligned_alloc(65536, 64 * 65536);
    CHECK(data != NULL);
    uint64_t keys[64];
    tx[0] = (Texture){32, 32, 0x12, 128};
    TextureSnapshot *s = &s_texture_snapshot[0]; s->bytes = 4096;
    /* Failure to allocate memo copies must retain coherent uncached hashes. */
    s->pixels=data;memset(data,0,4096);fail_hash_allocation=1;
    uint64_t uncached=sg_texture_key(0,0);data[2053]=1;
    CHECK(sg_texture_key(0,0)!=uncached);
    data[2053]=0;CHECK(sg_texture_key(0,0)==uncached);
    fail_hash_allocation=0;s_sg_frame++;memset(&s_sg_stats,0,sizeof s_sg_stats);
    for (unsigned i = 0; i < 64; i++) {
        s->pixels = data + i * 65536;
        memset(s->pixels, i, 4096);
        keys[i] = sg_texture_key(0, 0);
    }
    CHECK(s_sg_stats.texture_hash_bytes == 64 * 4096);
    for (unsigned draw = 0; draw < 4096; draw++) {
        unsigned i = (draw * 17) & 63;
        s->pixels = data + i * 65536;
        CHECK(sg_texture_key(0, 0) == keys[i]);
    }
    CHECK(s_sg_stats.texture_hash_bytes == 64 * 4096);
    for(unsigned frame=0;frame<32;frame++) {
        s_sg_frame++;
        for(unsigned i=0;i<64;i++) {
            s->pixels=data+(63-i)*65536;
            CHECK(sg_texture_key(0,0)==keys[63-i]);
        }
        CHECK(s_sg_stats.texture_hash_bytes==64*4096);
    }
    s->pixels = data; s->pixels[0] ^= 1;
    CHECK(sg_texture_key(0, 1) != keys[0]); /* refresh after GPU download */
    CHECK(s_sg_stats.texture_hash_bytes == 65 * 4096);
    s->pixels[0] ^= 1; s_sg_frame++;
    CHECK(sg_texture_key(0, 0) == keys[0]);
    CHECK(s_sg_stats.texture_hash_bytes == 66 * 4096);
    s->owned = 1;
    uint64_t before = sg_texture_key(0, 0); s->pixels[0] ^= 1;
    CHECK(sg_texture_key(0, 0) != before); /* malloc snapshots can reuse addresses */
    s->owned = 0; tx[0].color = 0x0b;
    before = sg_texture_key(0, 0); uint64_t bytes = s_sg_stats.texture_hash_bytes;
    s->palette[17] = 0xff0088ffu;
    CHECK(sg_texture_key(0, 0) != before);
    CHECK(s_sg_stats.texture_hash_bytes == bytes); /* palette checked independently */
    tx[0].pitch = 256;
    CHECK(sg_texture_key(0, 0) != before);
    before = sg_texture_key(0, 0); levels[0] = 2;
    CHECK(sg_texture_key(0, 0) != before); /* level count participates in memo shape */
    /* Every byte, including interior/padding/mip data, must be observed within
     * the same frame. Repeated unchanged binds must still reuse the hash. */
    tx[0]=(Texture){32,32,0x12,128};levels[0]=1;s->pixels=data;s->bytes=4096;
    before=sg_texture_key(0,0);
    for(unsigned at=0;at<4096;at++) {
        data[at]^=1u<<(at&7);
        if(!(at&63))s_sg_frame++;
        uint64_t changed=sg_texture_key(0,0);CHECK(changed!=before);
        bytes=s_sg_stats.texture_hash_bytes;
        CHECK(sg_texture_key(0,0)==changed && s_sg_stats.texture_hash_bytes==bytes);
        data[at]^=1u<<(at&7);CHECK(sg_texture_key(0,0)==before);
    }
    /* Stage aliases must not hide each other's writes. */
    tx[1]=tx[0];s_texture_snapshot[1]=*s;
    CHECK(sg_texture_key(1,0)==before);data[2061]^=0x80;
    uint64_t alias=sg_texture_key(1,0);CHECK(alias!=before && sg_texture_key(0,0)==alias);
    /* Churn beyond bounded copy capacity. Rebinding evicted spans and frame
     * advancement must retain content coherence. */
    s_sg_frame++;tx[0]=(Texture){1024,512,0x12,4096};s->bytes=2*1024*1024;
    for(unsigned i=0;i<17;i++) {
        s->pixels=data+i*16;before=sg_texture_key(0,0);
        s->pixels[s->bytes-1]^=1;CHECK(sg_texture_key(0,0)!=before);
        s->pixels[s->bytes-1]^=1;CHECK(sg_texture_key(0,0)==before);
    }
    s_sg_frame++;s->pixels=data;before=sg_texture_key(0,0);
    s->pixels[17]^=2;CHECK(sg_texture_key(0,0)!=before);
    s_sg_frame=UINT32_MAX;before=sg_texture_key(0,0);s_sg_frame=0;
    s->pixels[32]^=4;CHECK(sg_texture_key(0,0)!=before);
#ifdef TEST_PERSISTENT_COPY
    /* Persistent lookup must find an identity beyond cold colliding entries. */
    tx[0]=(Texture){2,1,0x12,8};s->bytes=8;
    uint8_t *collisions[17];unsigned found=0;
    for(size_t i=0;i+8<64*65536 && found<17;i+=16)
        if(sg_hash_memo_bucket(data+i,2,1)==0)collisions[found++]=data+i;
    CHECK(found==17);
    uint64_t collision_keys[17];
    for(unsigned i=0;i<16;i++) {
        memset(collisions[i],i+17,8);s->pixels=collisions[i];collision_keys[i]=sg_texture_key(0,0);
    }
    bytes=s_sg_stats.texture_hash_bytes;s_sg_frame++;
    for(unsigned i=0;i<16;i++){s->pixels=collisions[15-i];CHECK(sg_texture_key(0,0)==collision_keys[15-i]);}
    CHECK(s_sg_stats.texture_hash_bytes==bytes);
    memset(collisions[16],71,8);s->pixels=collisions[16];collision_keys[16]=sg_texture_key(0,0);
    for(unsigned i=0;i<17;i++){s->pixels=collisions[i];CHECK(sg_texture_key(0,0)==collision_keys[i]);}
    /* Force partial ring overwrite, with overwritten copy bytes deliberately
     * equal to changed guest bytes. An invalid serial must never yield a hit. */
    uint8_t *large=malloc(SG_HASH_COPY_BYTES+1);CHECK(large);memset(large,2,SG_HASH_COPY_BYTES+1);
    memset(s_sg_hash_memo,0,sizeof s_sg_hash_memo);s_sg_hash_copy_cursor=0;
    s->pixels=data;s->bytes=8;memset(data,1,8);(void)sg_texture_key(0,0);
    s->pixels=large;s->bytes=SG_HASH_COPY_BYTES-4;(void)sg_texture_key(0,0);
    s->pixels=data;s->bytes=8;memset(data,2,8);
    s->owned=1;uint64_t expected=sg_texture_key(0,0);s->owned=0;CHECK(sg_texture_key(0,0)==expected);
    s->pixels=large;s->bytes=SG_HASH_COPY_BYTES+1;before=sg_texture_key(0,0);
    bytes=s_sg_stats.texture_hash_bytes;CHECK(sg_texture_key(0,0)==before);
    CHECK(s_sg_stats.texture_hash_bytes==bytes+s->bytes); /* oversize stays uncached */
    large[SG_HASH_COPY_BYTES]^=4;CHECK(sg_texture_key(0,0)!=before);
    s->pixels=data;s->bytes=8;s_sg_hash_copy_cursor=UINT64_MAX-7;
    CHECK(sg_texture_key(0,0)==expected && s_sg_hash_copy_cursor<=SG_HASH_COPY_BYTES);
    data[7]^=1;CHECK(sg_texture_key(0,0)!=expected);
    memset(data,15,8);SgTextureKey frozen=sg_texture_key_snapshot(0,0);
    data[0]=16;CHECK(frozen.pixels!=data && frozen.pixels[0]==15);
    CHECK(sg_texture_key(0,0)!=frozen.key);free(large);
#endif
    free(data);
    puts("PASS aligned texture reuse, refresh, new frames, owned snapshots, palette and mip-count changes, every-byte same-frame rewrites, aliases, allocation failure, bounded ring eviction, oversized images, frame/cursor wrap and cross-frame reuse");
    return 0;
}
'''
    build = args.build_dir.resolve()
    build.mkdir(parents=True, exist_ok=True)
    source = build / "test.c"
    output = build / ("test" if args.native else "test.js")
    source.write_text(harness.replace("/* LIVE_HASH */", memo + hashing), encoding="utf-8")
    if args.native:
        compiler=shutil.which('clang') or shutil.which('cc')
        if not compiler:parser.error('A native C compiler is required')
        subprocess.run([compiler,str(source),'-I',str(args.runtime.resolve()/'src/kernel/sdlgpu'),'-O2','-g','-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer','-o',str(output)],check=True)
        subprocess.run([str(output)],check=True)
    else:
        emcc,node=shutil.which('emcc'),shutil.which('node')
        if not emcc or not node:parser.error('Emscripten emcc and Node must be on PATH')
        subprocess.run([emcc,str(source),'-I',str(args.runtime.resolve()/'src/kernel/sdlgpu'),'-O3',*([] if args.scalar else ['-msimd128']),'-sALLOW_MEMORY_GROWTH=1','-sENVIRONMENT=node','-o',str(output)],check=True)
        subprocess.run([node,str(output)],check=True)



if __name__ == "__main__":
    main()
