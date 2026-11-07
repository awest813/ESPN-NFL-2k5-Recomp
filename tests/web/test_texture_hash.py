"""Exercise the live texture hash memo with aligned Xbox-style allocations."""
from pathlib import Path
import shutil
import subprocess


def main():
    root = Path(__file__).resolve().parents[2]
    src = (root / "external/xboxrecomp/src/kernel/sdlgpu/sdlgpu_texture.inc.c").read_text(encoding="utf-8")
    memo = src[src.index("#define SG_HASH_MEMO"):src.index("/* One decode buffer")]
    hashing = src[src.index("static uint64_t sg_hash("):src.index("/* Decode a stage")]
    harness = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { unsigned width, height, color, pitch; } Texture;
typedef struct { uint8_t *pixels; size_t bytes; int owned; uint32_t palette[256]; } TextureSnapshot;
static Texture tx[4];
static TextureSnapshot s_texture_snapshot[4];
static struct { uint64_t texture_hash_bytes; } s_sg_stats;
static const Texture *sg_stage_texture(int st) { return &tx[st]; }
/* LIVE_HASH */
#define CHECK(c) do { if (!(c)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); return 1; } } while (0)
int main(void) {
    uint8_t *data = aligned_alloc(65536, 64 * 65536);
    CHECK(data != NULL);
    uint64_t keys[64];
    tx[0] = (Texture){32, 32, 0x12, 128};
    TextureSnapshot *s = &s_texture_snapshot[0]; s->bytes = 4096;
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
    free(data);
    puts("PASS aligned texture reuse, refresh, new frames, owned snapshots and palette changes");
    return 0;
}
'''
    build = root / "build-web-tests/texture-hash"
    build.mkdir(parents=True, exist_ok=True)
    source = build / "test.c"
    output = build / "test.js"
    source.write_text(harness.replace("/* LIVE_HASH */", memo + hashing), encoding="utf-8")
    emcc, node = shutil.which("emcc"), shutil.which("node")
    if not emcc or not node:
        raise SystemExit("Emscripten emcc and Node must be on PATH")
    subprocess.run([emcc, str(source), "-O3", "-sENVIRONMENT=node", "-o", str(output)], check=True)
    subprocess.run([node, str(output)], check=True)


if __name__ == "__main__":
    main()
