"""Generate paired GPU line shaders and baselines from production CPU VP/clipping."""
from pathlib import Path
import argparse
import shutil
import subprocess


def main():
    root=Path(__file__).resolve().parents[2]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir',type=Path,default=root/'build-web-tests/gpu-lines')
    args=parser.parse_args();out=args.build_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    kernel=root/'external/xboxrecomp/src/kernel'
    core=(kernel/'nv2a_pb_exec.c').read_text(encoding='utf-8')
    xf=(kernel/'sdlgpu/sdlgpu_xf.inc.c').read_text(encoding='utf-8')
    native=(kernel/'sdlgpu/sdlgpu_vp.inc.c').read_text(encoding='utf-8')
    begin=core.index('/* Decoded instruction fields');end=core.index('/* Depth buffer:',begin)
    cpu=core[begin:end]
    fetch=core[core.index('static size_t vertex_attr_bytes('):core.index('static uint32_t surface_bpp(')]
    fog=core[core.index('static float fog_factor('):core.index('#define VP_PROG_LEN',core.index('static float fog_factor('))]
    lerp=core[core.index('static void xf_lerp('):core.index('/* Near-plane clipping.',core.index('static void xf_lerp('))]
    clip=core[core.index('typedef void (*XfLineFn)'):core.index('typedef struct { XfLineFn emit;')]
    text=native[native.index('typedef struct { char *p;'):native.index('/* GLSL for the program')]
    shade=xf[xf.index('typedef struct {',xf.index('std140 mirror')):xf.index('} SgXfShade;')+len('} SgXfShade;')]
    harness=(Path(__file__).parent/'fixtures/gpu_line_cases.c').read_text(encoding='utf-8')
    topology = "\n".join(line for line in core.splitlines() if line.startswith('#define NV_PRIM_'))
    primitive=core[core.index('static int primitive_is_lines('):core.index('static int primitive_is_lines(')+core[core.index('static int primitive_is_lines('):].index('\n}')+2]
    batch=core[core.index('typedef void (*BatchLineFn)'):core.index('static void raster_line_indexed(')]
    packing=xf[xf.index('static struct {float *data;'):xf.index('static int sg_draw_line_vp(')]
    cache=(kernel/'sdlgpu/sdlgpu_vpcache.inc.c').read_text(encoding='utf-8')
    stride=cache[cache.index('static uint32_t sg_vp_input_stride('):cache.index('static struct {',cache.index('static uint32_t sg_vp_input_stride('))]
    pipeline=(kernel/'sdlgpu/sdlgpu_pipeline.inc.c').read_text(encoding='utf-8')
    layout=pipeline[pipeline.index('static uint32_t sg_linevp_attributes('):pipeline.index('static SDL_GPUGraphicsPipeline *sg_pipeline_create(')]
    harness=harness.replace('/* LIVE_CPU */',topology+'\n'+fetch+fog+cpu+lerp+clip+primitive+batch+packing+stride+layout)
    harness=harness.replace('/* LIVE_SHADER */',shade+text+f'\n#include "{(kernel/"sdlgpu/sdlgpu_vp_wgsl.inc.c").as_posix()}"\n')
    source=out/'generate.c';binary=out/'generate.js';source.write_bytes(harness.encode('utf-8'))
    compiler,node=shutil.which('emcc'),shutil.which('node')
    if not compiler or not node:parser.error('Emscripten and Node are required')
    subprocess.run([compiler,str(source),'-I',str(kernel),'-I',str(root/'external/xboxrecomp/tests/sdlgpu_web'),'-O2','-msimd128','-sENVIRONMENT=node','-sNODERAWFS=1','-o',str(binary)],check=True)
    subprocess.run([node,str(binary)],cwd=out,check=True)


if __name__=='__main__':
    main()
