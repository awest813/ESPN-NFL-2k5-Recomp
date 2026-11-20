"""Measure production Wasm condition waits without imposing a host-specific timing gate.

Requires emcc on PATH. Browser runs also require Playwright resolvable by Node.
Example: python tools/benchmark-web-waits.py --executable "C:/Program Files/Google/Chrome/Application/chrome.exe"
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform as host_platform
import shutil
import subprocess


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=Path, default=root / 'build-web-tests/condition-waits')
    parser.add_argument('--target', choices=['browser', 'node'], default='browser')
    parser.add_argument('--executable', help='Optional browser executable; otherwise use Playwright Chromium')
    args = parser.parse_args()
    emcc, node = shutil.which('emcc'), shutil.which('node')
    if not emcc or not node:
        parser.error('emcc and Node must be on PATH')
    out = args.build_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    source = root / 'tools/benchmarks/condition-waits.c'
    platform = root / 'external/xboxrecomp/src/platform/win32_compat.c'
    inputs = [source, platform, platform.with_suffix('.h'),
              platform.with_name('xbox_winnt.h'), root / 'config/xboxrecomp-web.patch']
    manifest = {
        'target': args.target,
        'host': host_platform.platform(),
        'node': subprocess.check_output([node, '--version'], text=True).strip(),
        'sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in inputs},
        'emcc': subprocess.check_output([emcc, '--version'], text=True).splitlines()[0],
    }
    (out / 'build-evidence.json').write_bytes((json.dumps(manifest, indent=2) + '\n').encode())
    subprocess.run([emcc, str(source), str(platform), '-I', str(root / 'external/xboxrecomp/src'),
                    '-O2', '-pthread', '-sPROXY_TO_PTHREAD=1', '-sPTHREAD_POOL_SIZE=3',
                    '-sEXIT_RUNTIME=1', '-sENVIRONMENT=web,node', '-sINITIAL_MEMORY=128MB',
                    '-o', str(out / 'benchmark.js')], check=True)
    if args.target == 'node':
        result = subprocess.run([node, str(out / 'benchmark.js')], capture_output=True,
                                text=True, timeout=120)
        log = result.stdout + result.stderr
        (out / 'node.log').write_bytes(log.encode())
        print(log, end='')
        result.check_returncode()
        if 'WAITBENCH DONE' not in log:
            raise RuntimeError('Benchmark did not complete')
    else:
        subprocess.run([node, str(root / 'tools/benchmark-web-waits.cjs'), str(out),
                        *([args.executable] if args.executable else [])], check=True, timeout=150)


if __name__ == '__main__':
    main()
