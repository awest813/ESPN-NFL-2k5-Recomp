"""Run actual GP/EP firmware through real MMIO and the frame/memory bridge."""
from pathlib import Path
import shutil
import subprocess
root=Path(__file__).resolve().parents[2]
apu=root/'external/xboxrecomp/src/apu'
source=(apu/'apu_core.c').read_text(encoding='utf-8')
def function(signature,text=source):
    start=text.index(signature)
    body=text.index('{',start)
    depth=1
    for end in range(body+1,len(text)):
        if text[end]=='{': depth+=1
        elif text[end]=='}': depth-=1
        if not depth: return text[start:end+1]
    raise ValueError('Unterminated fixture function: '+signature)
out=root/'build-web-tests/gp-ep';out.mkdir(parents=True,exist_ok=True)
harness=(root/'tests/web/test_gp_ep.c').read_text(encoding='utf-8-sig')
harness=harness.replace('/* PRODUCTION_MMIO */','\n'.join(function(s) for s in [
    'void mcpx_apu_dispatch_mmio(', 'static void mcpx_apu_mmio_complete(', 'uint64_t mcpx_apu_mmio_read(', 'void mcpx_apu_mmio_write(',
    'void xbox_AudioSetGameGain(', 'void xbox_AudioSetCommentaryGain(', 'float xbox_AudioGameLevel(']))
harness=harness.replace('/* PRODUCTION_LEVEL */',function('void mcpx_apu_dsp_update_level(',(apu/'apu_dsp.c').read_text(encoding='utf-8')))
(out/'test.c').write_text(harness,encoding='utf-8')
subprocess.run([shutil.which('emcc') or 'emcc',str(out/'test.c'),str(apu/'apu_gp_ep.c'),str(apu/'apu_web_audio.c'),
                *[str(apu/'dsp'/f) for f in ['dsp.c','dsp_cpu.c','dsp_dma.c']],
                '-I',str(apu),'-I',str(apu.parent),'-O1','-fsanitize=undefined',
                '-fno-sanitize-recover=undefined','-sENVIRONMENT=node','-sINITIAL_MEMORY=33554432',
                '-o',str(out/'test.js')],check=True)
subprocess.run([shutil.which('node') or 'node',str(out/'test.js')],check=True,timeout=60)
