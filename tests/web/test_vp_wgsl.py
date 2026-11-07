"""Generate differential cases from the applied CPU and WGSL translators.

Requires Emscripten and Node on PATH. Run test_vp_wgsl.js on the output to
compare the actual GPU results with the CPU interpreter.
"""
from pathlib import Path
import argparse
import shutil
import subprocess


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=root / "build-web-tests/vp-wgsl")
    args = parser.parse_args()
    emcc = shutil.which("emcc")
    node = shutil.which("node")
    if not emcc or not node:
        parser.error("Emscripten emcc and Node must be on PATH")
    kernel = root / "external/xboxrecomp/src/kernel"
    runtime = (kernel / "nv2a_pb_exec.c").read_text(encoding="utf-8")
    begin = runtime.index("/* Decoded instruction fields")
    end = runtime.index("/* One transformed vertex", begin)
    native = (kernel / "sdlgpu/sdlgpu_vp.inc.c").read_text(encoding="utf-8")
    text_begin = native.index("typedef struct { char *p;")
    text_end = native.index("/* GLSL for the program", text_begin)
    fixtures = Path(__file__).parent / "fixtures"
    harness = (fixtures / "vp_interpreter_test.c").read_text(encoding="utf-8").split("/* LIVE_INTERPRETER */")[0]
    generator = (fixtures / "vp_wgsl_cases.c").read_text(encoding="utf-8")
    live = runtime[begin:end] + native[text_begin:text_end]
    cache = (kernel / "sdlgpu/sdlgpu_vpcache.inc.c").read_text(encoding="utf-8")
    stride_start = cache.index("static uint32_t sg_vp_input_stride(")
    live += cache[stride_start:cache.index("static struct {", stride_start)]
    live += f'\n#include "{(kernel / "sdlgpu/sdlgpu_vp_wgsl.inc.c").as_posix()}"\n'
    args.build_dir = args.build_dir.resolve()
    args.build_dir.mkdir(parents=True, exist_ok=True)
    source = args.build_dir / "generate.c"
    output = args.build_dir / "generate.js"
    pipeline = (kernel / "sdlgpu/sdlgpu_pipeline.inc.c").read_text(encoding="utf-8")
    layout_start = pipeline.index("    SDL_GPUVertexAttribute vp_attrs[16];")
    layout = pipeline[layout_start:pipeline.index("    const uint32_t blend", layout_start)]
    source.write_text(harness + generator.replace("/* LIVE_GENERATOR */", live)
                     .replace("/* LIVE_LAYOUT */", layout), encoding="utf-8")
    subprocess.run([emcc, str(source), "-O3", "-msimd128", "-sENVIRONMENT=node",
                    "-sNODERAWFS=1", "-o", str(output)], check=True)
    subprocess.run([node, str(output)], cwd=args.build_dir, check=True)


if __name__ == "__main__":
    main()
