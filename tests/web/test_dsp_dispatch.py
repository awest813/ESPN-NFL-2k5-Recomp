"""Compare cached DSP execution with the original dispatcher and retirement."""
from pathlib import Path
import shutil
import subprocess
import sys
root = Path(__file__).resolve().parents[2]
core = root / 'external/xboxrecomp/src/apu/dsp'
out = root / 'build-web-tests/dsp-dispatch'
out.mkdir(parents=True, exist_ok=True)
base = [shutil.which('emcc') or 'emcc',str(root/'tests/web/test_dsp_dispatch.c'),'-I',str(core)]
subprocess.run([*base,'-O1','-fsanitize=undefined','-fno-sanitize-recover=undefined',
                '-sENVIRONMENT=node','-sINITIAL_MEMORY=33554432','-o',str(out/'test.js')],check=True)
subprocess.run([shutil.which('node') or 'node',str(out/'test.js')],check=True,timeout=120)
if '--benchmark' in sys.argv:
    subprocess.run([*base,'-O3','-sENVIRONMENT=node','-sINITIAL_MEMORY=33554432',
                    '-o',str(out/'benchmark.js')],check=True)
    subprocess.run([shutil.which('node') or 'node',str(out/'benchmark.js'),'--benchmark'],check=True,timeout=120)
