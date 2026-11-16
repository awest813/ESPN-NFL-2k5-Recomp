"""Validate DSP fractional multiplication against Python integers and old limbs."""
from pathlib import Path
import random
import shutil
import struct
import subprocess
import sys
root = Path(__file__).resolve().parents[2]
core = root / 'external/xboxrecomp/src/apu/dsp'
out = root / 'build-web-tests/dsp-multiply'
out.mkdir(parents=True, exist_ok=True)
edges = sorted(set([0,1,2,0x7fffff,0x800000,0x800001,0xfffffe,0xffffff]
                   + [1 << bit for bit in range(24)]
                   + [(1 << bit) - 1 for bit in range(1,25)]))
rng = random.Random(0x56300)
cases = [(a,b,sign) for a in edges for b in edges for sign in [0,1]]
cases += [(rng.randrange(1<<24),rng.randrange(1<<24),rng.randrange(2)) for _ in range(12000)]
def signed(v):
    return v - (1 << 24) if v & (1 << 23) else v
with (out / 'vectors.bin').open('wb') as f:
    for a,b,sign in cases:
        product = signed(a) * signed(b) * 2 * (-1 if sign else 1)
        f.write(struct.pack('<6I',a,b,sign,(product>>48)&255,(product>>24)&0xffffff,product&0xffffff))
subprocess.run([shutil.which('emcc') or 'emcc',str(root/'tests/web/test_dsp_multiply.c'),
                '-I',str(core),'-O3','-fsanitize=undefined','-fno-sanitize-recover=undefined',
                '--embed-file',str(out/'vectors.bin')+'@/vectors.bin','-sENVIRONMENT=node',
                '-o',str(out/'test.js')],check=True)
subprocess.run([shutil.which('node') or 'node',str(out/'test.js')],check=True,timeout=60)
if '--benchmark' in sys.argv:
    # Time an unsanitized build; instrumentation changes the relative costs.
    subprocess.run([shutil.which('emcc') or 'emcc',str(root/'tests/web/test_dsp_multiply.c'),
                    '-I',str(core),'-O3',
                    '--embed-file',str(out/'vectors.bin')+'@/vectors.bin','-sENVIRONMENT=node',
                    '-o',str(out/'benchmark.js')],check=True)
    subprocess.run([shutil.which('node') or 'node',str(out/'benchmark.js'),
                    '/vectors.bin','--benchmark'],check=True,timeout=60)
