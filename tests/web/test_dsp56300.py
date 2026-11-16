"""Run uploaded DSP instructions and real DMA paths in the standalone core."""
from pathlib import Path
import shutil
import subprocess
root = Path(__file__).resolve().parents[2]
core = root / 'external/xboxrecomp/src/apu/dsp'
out = root / 'build-web-tests/dsp56300'
out.mkdir(parents=True, exist_ok=True)
subprocess.run([shutil.which('emcc') or 'emcc', str(root / 'tests/web/test_dsp56300.c'),
                *[str(core / f) for f in ['dsp.c', 'dsp_cpu.c', 'dsp_dma.c']],
                '-I', str(core), '-O1', '-fsanitize=undefined',
                '-fno-sanitize-recover=undefined', '-sENVIRONMENT=node',
                '-o', str(out / 'test.js')], check=True)
subprocess.run([shutil.which('node') or 'node', str(out / 'test.js')], check=True)
