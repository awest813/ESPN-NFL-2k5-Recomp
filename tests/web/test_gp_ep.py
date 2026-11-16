"""Run actual GP/EP firmware through real MMIO and the frame/memory bridge."""
from pathlib import Path
import shutil
import subprocess
root=Path(__file__).resolve().parents[2]
apu=root/'external/xboxrecomp/src/apu'
source=(apu/'apu_core.c').read_text()
def function(signature):
    start=source.index(signature)
    return source[start:source.index('\n}',start)+2]
out=root/'build-web-tests/gp-ep';out.mkdir(parents=True,exist_ok=True)
harness=(root/'tests/web/test_gp_ep.c').read_text(encoding='utf-8-sig')
harness=harness.replace('/* PRODUCTION_MMIO */','\n'.join(function(s) for s in ['void mcpx_apu_dispatch_mmio(', 'uint64_t mcpx_apu_mmio_read(', 'void mcpx_apu_mmio_write(']))
(out/'test.c').write_text(harness,encoding='utf-8')
subprocess.run([shutil.which('emcc') or 'emcc',str(out/'test.c'),str(apu/'apu_gp_ep.c'),
                *[str(apu/'dsp'/f) for f in ['dsp.c','dsp_cpu.c','dsp_dma.c']],
                '-I',str(apu),'-I',str(apu.parent),'-O1','-fsanitize=undefined',
                '-fno-sanitize-recover=undefined','-sENVIRONMENT=node','-sINITIAL_MEMORY=33554432',
                '-o',str(out/'test.js')],check=True)
subprocess.run([shutil.which('node') or 'node',str(out/'test.js')],check=True,timeout=60)
