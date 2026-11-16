"""Check production clip-plane decoding and native shader-cache state selection."""
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
kernel = root / 'external/xboxrecomp/src/kernel'
core = (kernel / 'nv2a_pb_exec.c').read_text(encoding='utf-8')
native = (kernel / 'nv2a_gpu_d3d11.inc.c').read_text(encoding='utf-8')
cache = (kernel / 'nv2a_gpu_ps.inc.c').read_text(encoding='utf-8')
decode = core[core.index('#define NV097_SET_COMBINER_ALPHA_ICW'):core.index('static int comb_active(')]
start = native.index('typedef struct {', native.index('/* Constant buffer the shader reads'))
constants = native[start:native.index('} GpuConsts;', start) + len('} GpuConsts;')]
start = cache.index('typedef struct {')
key_type = cache[start:cache.index('} GpuPsKey;', start) + len('} GpuPsKey;')]
start = cache.index('static void gpu_ps_make_key(')
make_key = cache[start:cache.index('static uint32_t gpu_ps_key_hash(', start)]
harness = r'''
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
/* DECODER */
/* CONSTANTS */
/* KEY */
/* MAKE_KEY */
int main(void) {
    for(unsigned word=0;word<65536;word++) {
        assert(comb_method(0x17F8,0xA5A50000u|word));
        assert(s_comb.clip_mode==word && !s_comb.set && !s_comb.control);
    }
    assert(comb_method(0x17F8,0));assert(s_comb.clip_mode==0);
    unsigned cases=0;
    for(unsigned active=0;active<16;active++)for(unsigned combiners=0;combiners<2;combiners++) {
        GpuConsts c={0};GpuPsKey base,actual;
        c.alpha[3]=combiners;c.misc[0]=1;c.show[0]=3;
        for(unsigned st=0;st<4;st++){c.mode[st]=(active&(1u<<st))?5:1;c.texon[st]=c.mode[st]==5?0:1;}
        gpu_ps_make_key(&c,&base);
        for(unsigned bit=0;bit<32;bit++) {
            c.show[3]=1u<<bit;gpu_ps_make_key(&c,&actual);
            int read=bit<16 && (active&(1u<<(bit/4)));
            assert(actual.show[3]==(read?1u<<bit:0));
            if(read){assert(memcmp(&base,&actual,sizeof base));actual.show[3]=0;}
            assert(!memcmp(&base,&actual,sizeof base));cases++;
        }
    }
    /* Comparison normalization must preserve independent texture-kill flags. */
    GpuConsts c={0};GpuPsKey before,after;c.mode[0]=1;c.texon[0]=1;
    gpu_ps_make_key(&c,&before);c.texon[0]=3;gpu_ps_make_key(&c,&after);
    assert(memcmp(&before,&after,sizeof before));
    printf("PASS clip-plane state: 65536 register values, %u active/inactive cache-bit cases, independent alpha-kill keys\n",cases);
}
'''.replace('/* DECODER */', decode).replace('/* CONSTANTS */', constants).replace('/* KEY */', key_type).replace('/* MAKE_KEY */', make_key)
out = root / 'build-web-tests/clip-plane-state'
out.mkdir(parents=True, exist_ok=True)
(out / 'test.c').write_text(harness, encoding='utf-8')
subprocess.run([shutil.which('emcc') or 'emcc', str(out / 'test.c'), '-O1',
                '-fsanitize=undefined', '-fno-sanitize-recover=undefined',
                '-sENVIRONMENT=node', '-o', str(out / 'test.js')], check=True)
subprocess.run([shutil.which('node') or 'node', str(out / 'test.js')], check=True)
