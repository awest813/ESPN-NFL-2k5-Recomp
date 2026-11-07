"""Compare the applied runtime's vertex interpreter with its original version.

Run with Emscripten and Node on PATH after applying xboxrecomp-web.patch.
The benchmark is informational; correctness is checked byte for byte.
"""

from pathlib import Path
import argparse
import shutil
import subprocess


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=root / "build-web-tests/vp-parity")
    args = parser.parse_args()
    emcc = shutil.which("emcc")
    node = shutil.which("node")
    if not emcc or not node:
        parser.error("Emscripten emcc and Node must be on PATH")

    runtime = (root / "external/xboxrecomp/src/kernel/nv2a_pb_exec.c").read_text(encoding="utf-8")
    begin = runtime.index("/* Decoded instruction fields")
    end = runtime.index("/* One transformed vertex", begin)
    mask_begin = runtime.index("static uint32_t vp_input_mask(", end)
    mask_end = runtime.index("static uint32_t s_xf_input_mask", mask_begin)
    live = runtime[begin:end] + runtime[mask_begin:mask_end]
    fixtures = Path(__file__).parent / "fixtures"
    harness = (fixtures / "vp_interpreter_test.c").read_text(encoding="utf-8")
    args.build_dir.mkdir(parents=True, exist_ok=True)
    source = args.build_dir / "vp_parity.c"
    output = args.build_dir / "vp_parity.js"
    source.write_text(harness.replace("/* LIVE_INTERPRETER */", live), encoding="utf-8")
    subprocess.run([emcc, str(source), "-I", str(fixtures), "-O3", "-msimd128",
                    "-sENVIRONMENT=node", "-o", str(output)], check=True)
    subprocess.run([node, str(output)], check=True)


if __name__ == "__main__":
    main()
