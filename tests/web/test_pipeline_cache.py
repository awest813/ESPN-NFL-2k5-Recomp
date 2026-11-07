"""Exercise the production pipeline cache beyond the old 1,024-state limit."""
from pathlib import Path
import re
import shutil
import subprocess


def main():
    root = Path(__file__).resolve().parents[2]
    gpu = root / "external/xboxrecomp/src/kernel/sdlgpu"
    core = (gpu / "sdlgpu.inc.c").read_text(encoding="utf-8")
    maximum = int(re.search(r"#define SG_MAX_PIPELINES (\d+)", core)[1])
    pipeline = (gpu / "sdlgpu_pipeline.inc.c").read_text(encoding="utf-8")
    live = pipeline[pipeline.index("#define SG_PIPE_TABLE"):]
    harness = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define SG_MAX_PIPELINES LIMIT
typedef struct { uint32_t color, depth, stencil, masks, vs; } SgPipeKey;
typedef struct { uint32_t unused; } SDL_GPUGraphicsPipeline;
typedef struct { SgPipeKey key; SDL_GPUGraphicsPipeline *pipe; } SgPipeline;
static struct { SgPipeline pipes[SG_MAX_PIPELINES]; unsigned pipe_count; } s_sg;
static SgPipeKey requested;
static unsigned created, fail_once;
static const char *SDL_GetError(void) { return "intentional test failure"; }
static int sg_pipeline_key(int xf, uint32_t vs, SgPipeKey *key) { *key = requested; key->vs = vs; return 1; }
static SDL_GPUGraphicsPipeline *sg_pipeline_create(const SgPipeKey *key) {
    if (fail_once) { fail_once = 0; return NULL; }
    return (SDL_GPUGraphicsPipeline *)(uintptr_t)(++created);
}
/* LIVE_CACHE */
#define CHECK(c) do { if (!(c)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); return 1; } } while (0)
static SDL_GPUGraphicsPipeline *lookup(unsigned i) {
    requested = (SgPipeKey){i * 3u, i % 16u, i % 7u, i % 256u, 0};
    return sg_pipeline_current(1, i % 1024u);
}
int main(void) {
    CHECK(SG_MAX_PIPELINES > 1024);
    for (unsigned i = 0; i < SG_MAX_PIPELINES; i++) CHECK(lookup(i) != NULL);
    CHECK(created == SG_MAX_PIPELINES);
    for (unsigned pass = 0; pass < 8; pass++)
        for (unsigned i = SG_MAX_PIPELINES; i-- > 0;) CHECK((uintptr_t)lookup(i) == i + 1);
    CHECK(created == SG_MAX_PIPELINES);
    CHECK(lookup(SG_MAX_PIPELINES) == NULL);
    CHECK((uintptr_t)lookup(0) == 1); /* full pool still serves existing states */
    memset(&s_sg, 0, sizeof s_sg); memset(s_sg_pipe_table, 0, sizeof s_sg_pipe_table);
    fail_once = 1;
    CHECK(lookup(7) == NULL);
    CHECK(s_sg.pipe_count == 0);
    CHECK(lookup(7) != NULL);
    CHECK(s_sg.pipe_count == 1);
    printf("PASS %u pipeline states, collision lookup, full pool and failed-creation retry\n", SG_MAX_PIPELINES);
    return 0;
}
'''
    build = root / "build-web-tests/pipeline-cache"
    build.mkdir(parents=True, exist_ok=True)
    source, output = build / "test.c", build / "test.js"
    source.write_text(harness.replace("LIMIT", str(maximum)).replace("/* LIVE_CACHE */", live), encoding="utf-8")
    emcc, node = shutil.which("emcc"), shutil.which("node")
    if not emcc or not node:
        raise SystemExit("Emscripten emcc and Node must be on PATH")
    subprocess.run([emcc, str(source), "-O3", "-sENVIRONMENT=node", "-o", str(output)], check=True)
    subprocess.run([node, str(output)], check=True)


if __name__ == "__main__":
    main()
