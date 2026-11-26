"""Validate production runtime-specialized WGSL fragment shaders across NV2A modes."""
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
sdlgpu = root / "external/xboxrecomp/src/kernel/sdlgpu"
xf_text = (sdlgpu / "sdlgpu_xf.inc.c").read_text(encoding="utf-8")
vp_text = (sdlgpu / "sdlgpu_vp.inc.c").read_text(encoding="utf-8")
fs_text = (sdlgpu / "sdlgpu_fs_wgsl.inc.c").read_text(encoding="utf-8")

sg_text_def = vp_text[vp_text.index("/* A growing text buffer"):vp_text.index("/* One source operand:")]
shade_def = xf_text[xf_text.index("typedef struct {\n    uint32_t prog[4];"):xf_text.index("typedef struct {SgXfShade base;")]

out = root / "build-web-tests/fs-wgsl"
out.mkdir(parents=True, exist_ok=True)

harness = r'''
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint8_t Uint8;
typedef uint32_t Uint32;
typedef struct SDL_GPUDevice SDL_GPUDevice;
typedef struct SDL_GPUShader { int id; } SDL_GPUShader;
typedef enum { SDL_GPU_SHADERFORMAT_WGSL = 1 } SDL_GPUShaderFormat;
typedef enum { SDL_GPU_SHADERSTAGE_FRAGMENT = 1 } SDL_GPUShaderStage;
typedef struct {
    const Uint8 *code;
    size_t code_size;
    const char *entrypoint;
    SDL_GPUShaderFormat format;
    SDL_GPUShaderStage stage;
    Uint32 num_samplers;
    Uint32 num_uniform_buffers;
} SDL_GPUShaderCreateInfo;

static struct { SDL_GPUDevice *dev; SDL_GPUShader *xf_fs; } s_sg;
static SDL_GPUShader s_dummy_shaders[512];
static int s_created;

static SDL_GPUShader *SDL_CreateGPUShader(SDL_GPUDevice *d, const SDL_GPUShaderCreateInfo *info)
{
    (void)d;
    assert(info && info->code && info->code_size > 0);
    assert(info->format == SDL_GPU_SHADERFORMAT_WGSL);
    assert(info->stage == SDL_GPU_SHADERSTAGE_FRAGMENT);
    assert(info->num_samplers == 8 && info->num_uniform_buffers == 1);
    int idx = s_created++;
    assert(idx < 512);
    char path[512];
    snprintf(path, sizeof path, "shader_%03d.wgsl", idx);
    FILE *f = fopen(path, "wb");
    assert(f != NULL);
    fwrite(info->code, 1, info->code_size, f);
    fclose(f);
    s_dummy_shaders[idx].id = idx + 1;
    return &s_dummy_shaders[idx];
}

/* SG_TEXT */
/* SG_XF_SHADE */
/* SG_FS_WGSL */

static void set_f32(uint32_t *dst, float v) { memcpy(dst, &v, sizeof v); }

int main(void)
{
    /* 1. Combiners off: untextured, textured 2D, rect+border+opaque+kill */
    SgXfShade sh = {0};
    uint32_t s0 = sg_fs_program(&sh, 0);
    assert(s0 > 0);

    /* Dedup check: changing depth flags/offset when !need_depth && !depth_clip reuses same shader. */
    sh.depth[0] = 1u | 4u;
    sh.depth_offset[0] = 2.0f;
    sh.depth_offset[1] = 1.5f;
    assert(sg_fs_program(&sh, 0) == s0);

    /* Depth clip without need_depth must produce a distinct shader. */
    sh.depth[0] = 1u | 2u | 4u;
    uint32_t s_clip = sg_fs_program(&sh, 0);
    assert(s_clip > 0 && s_clip != s0);

    /* Depth output variants: Z-buffer float, Z-buffer D24, Z-buffer D16, W-buffer D24+slope+bias, W-buffer D16 */
    uint32_t depth_modes[] = { 0u, 4u, 8u, 1u | 4u, 1u | 8u, 1u | 2u | 4u, 2u | 8u };
    for (size_t i = 0; i < sizeof depth_modes / sizeof depth_modes[0]; i++) {
        memset(&sh, 0, sizeof sh);
        sh.depth[0] = depth_modes[i];
        set_f32(&sh.depth[1], 16777215.0f);
        set_f32(&sh.depth[3], 16777215.0f);
        sh.depth_offset[0] = (i & 1) ? 1.0f : 0.0f;
        sh.depth_offset[1] = (i & 2) ? 2.0f : 0.0f;
        assert(sg_fs_program(&sh, 1) > 0);
    }

    /* Textured 2D with rect, border, opaque alpha, alpha kill, and all 8 alpha test functions. */
    for (uint32_t af = 0x0200u; af <= 0x0207u; af++) {
        memset(&sh, 0, sizeof sh);
        sh.mode[0] = 1u;
        sh.misc[2] = 1u;
        sh.misc[3] = (1u << 8) | (1u << 16);
        sh.rect[0] = 1u | 2u | 4u | (15u << 8) | (4u << 16) | (1u << 28);
        sh.alpha[0] = 1u;
        sh.alpha[1] = af;
        sh.alpha[2] = 128u;
        assert(sg_fs_program(&sh, 1) > 0);
    }

    /* 8-stage combiner exercising all input mappings (0x00..0xE0), all output scale/bias,
     * dot products, MUX_MSB/LSB, UNIQUE_C0/C1, blue-to-alpha (0x80/0x40), r14/r15, final combiner. */
    for (int variant = 0; variant < 2; variant++) {
        memset(&sh, 0, sizeof sh);
        sh.mode[0] = 1u; sh.mode[1] = 2u; sh.mode[2] = 4u; sh.mode[3] = 5u;
        sh.misc[2] = 3u;
        sh.alpha[3] = 0xA000u;
        sh.prog[0] = 8u | (variant ? (0x100u | 0x1000u | 0x10000u) : 0u);
        uint32_t maps[8] = { 0x00u, 0x20u, 0x40u, 0x60u, 0x80u, 0xA0u, 0xC0u, 0xE0u };
        uint32_t omaps[6] = { 0x00u, 0x08u, 0x10u, 0x18u, 0x20u, 0x30u };
        for (uint32_t st = 0; st < 8u; st++) {
            uint32_t m0 = maps[st], m1 = maps[(st + 1u) & 7u], m2 = maps[(st + 2u) & 7u], m3 = maps[(st + 3u) & 7u];
            sh.color_icw[st] = ((m0 | 0x08u) << 24) | ((m1 | 0x04u | 0x10u) << 16) | ((m2 | 0x0Cu) << 8) | (m3 | 0x01u);
            sh.alpha_icw[st] = ((m0 | 0x08u | 0x10u) << 24) | ((m1 | 0x03u) << 16) | ((m2 | 0x0Du | 0x10u) << 8) | (m3 | 0x02u);
            uint32_t fl = omaps[st % 6u] | ((st & 1u) ? 7u : 0u) | ((st == 0) ? 0xC0u : 0u);
            sh.color_ocw[st] = (fl << 12) | (0xCu << 8) | (0xDu << 4) | (st == 7 ? 0xEu : 0x5u);
            sh.alpha_ocw[st] = ((omaps[(st + 1u) % 6u] | (st & 4u)) << 12) | (0xCu << 8) | (0xDu << 4) | 0x4u;
        }
        sh.prog[2] = (0x03u << 24) | (0x0Eu << 16) | (0x0Fu << 8) | 0x0Cu;
        sh.prog[3] = (0x04u << 24) | (0x08u << 16) | (0x1Cu << 8) | (variant ? 0xE0u : 0x00u);
        assert(sg_fs_program(&sh, 1) > 0);
    }

    /* Texture stage shader modes: cube, 2D remap, bump env/lum, dot2d, dot cube/reflect/normal, dep AR/GB, dotproduct. */
    {
        /* Mode 3 (cube + 2D fallback), 6 (bump env), 7 (bump lum) */
        for (int cube = 0; cube < 2; cube++) {
            memset(&sh, 0, sizeof sh);
            sh.mode[0] = 3u; sh.mode[1] = 6u; sh.mode[2] = 7u; sh.mode[3] = 0x0Fu;
            sh.misc[2] = 0xFu;
            sh.misc[3] = cube ? 1u : 0u;
            sh.tex[2][3] = 1u; sh.tex[3][3] = 2u;
            sh.prog[0] = 1u; sh.color_ocw[0] = 0xCu << 8; sh.alpha_ocw[0] = 0xCu << 8;
            assert(sg_fs_program(&sh, 1) > 0);
        }
        /* Mode 0x11 (dotproduct), 0x09 (dot2d), 0x0B (dot cube/2d on st2), 0x10 (dep GB) */
        for (uint32_t dmap = 0; dmap < 4u; dmap++) {
            memset(&sh, 0, sizeof sh);
            sh.mode[0] = 1u; sh.mode[1] = 0x11u; sh.mode[2] = 0x0Bu; sh.mode[3] = 0x10u;
            sh.misc[2] = 0xFu;
            sh.misc[3] = (dmap & 1u) ? (1u << 2) : 0u;
            sh.tex[1][2] = dmap; sh.tex[2][2] = dmap; sh.tex[3][2] = dmap;
            sh.tex[2][3] = 0u; sh.tex[3][3] = 0u;
            assert(sg_fs_program(&sh, 1) > 0);
        }
        /* Mode 0x09 on st1, 0x0C (reflect) and 0x0D/0x0E (normal) on st3 */
        uint32_t st3_modes[] = { 0x0Cu, 0x0Du, 0x0Eu };
        for (size_t i = 0; i < 3; i++) {
            for (int cube = 0; cube < 2; cube++) {
                memset(&sh, 0, sizeof sh);
                sh.mode[0] = 1u; sh.mode[1] = 0x09u; sh.mode[2] = 0x11u; sh.mode[3] = st3_modes[i];
                sh.misc[2] = 0xFu;
                sh.misc[3] = cube ? (1u << 3) : 0u;
                sh.tex[1][2] = 1u; sh.tex[2][2] = 2u; sh.tex[3][2] = 3u;
                assert(sg_fs_program(&sh, 1) > 0);
            }
        }
    }

    printf("GENERATED=%d\n", s_created);
    return 0;
}
'''.replace("/* SG_TEXT */", sg_text_def).replace("/* SG_XF_SHADE */", shade_def).replace("/* SG_FS_WGSL */", fs_text)

for old in out.glob("shader_*.wgsl"):
    old.unlink()
(out / "test.c").write_text(harness, encoding="utf-8")
subprocess.run(
    [shutil.which("emcc") or "emcc", str(out / "test.c"), "-O2", "-sENVIRONMENT=node", "-sNODERAWFS=1", "-o", str(out / "test.js")],
    check=True,
)
res = subprocess.run([shutil.which("node") or "node", str(out / "test.js")], cwd=str(out), check=True, capture_output=True, text=True)
print(res.stdout.strip())

shaders = sorted(out.glob("shader_*.wgsl"))
assert len(shaders) >= 25, f"expected >=25 generated shaders, got {len(shaders)}"

naga = shutil.which("naga")
if naga:
    for p in shaders:
        r = subprocess.run([naga, str(p)], capture_output=True, text=True)
        if r.returncode != 0:
            raise AssertionError(f"naga validation failed on {p.name}:\n{r.stderr}\n{r.stdout}")
    print(f"PASS runtime-specialized WGSL FS: {len(shaders)} shaders generated and validated by naga")
else:
    print(f"PASS runtime-specialized WGSL FS: {len(shaders)} shaders generated (naga not on PATH)")
