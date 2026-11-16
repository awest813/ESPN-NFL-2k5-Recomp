"""Lightweight voice logging must not scan the entire ADPCM buffer."""
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
source = (root / 'external/xboxrecomp/src/apu/apu_vp.c').read_text(encoding='utf-8')
start = source.index('    {\n        /* RECOMP_APU_VOICE_LOG=1: each voice')
block = source[start:source.index('    /* Step amplitude envelope */', start)]
harness = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include "apu_regs.h"
typedef uint64_t hwaddr;
typedef uint32_t DWORD;
typedef struct { uint32_t regs[0x20000]; } MCPXAPUState;
static unsigned payload_reads;
unsigned long g_apu_vp_frames=100;
static DWORD GetTickCount(void) { return 6001; }
static uint32_t xbox_ContiguousAllocatedBytes(void) { return 0; }
static uint32_t voice_get_mask(MCPXAPUState *d,unsigned v,hwaddr offset,uint32_t mask) {
    (void)d;(void)v;(void)mask;
    if(offset==NV_PAVS_VOICE_CFG_FMT)return 2u<<30;
    if(offset==NV_PAVS_VOICE_PAR_NEXT)return 63;
    return 0;
}
#define address_space_memory NULL
static uint32_t ldl_le_phys(void *as,hwaddr addr) { (void)as;(void)addr;return 0; }
static hwaddr get_data_ptr(uint32_t sge,uint32_t max,uint32_t offset) {
    (void)sge;(void)max;payload_reads++;return offset;
}
static const uint8_t *apu_phys(hwaddr addr) { static uint8_t bytes[72];(void)addr;return bytes; }
static void diagnostic(MCPXAPUState *d,unsigned v,int p,int ps,float rate) {
/* DIAGNOSTIC */
}
int main(int argc,char **argv) {
    int scan=argc>1 && atoi(argv[1]);
    setenv("RECOMP_APU_VOICE_LOG","1",1);
    if(scan)setenv("RECOMP_APU_VOICE_SCAN","1",1);else unsetenv("RECOMP_APU_VOICE_SCAN");
    static MCPXAPUState d;diagnostic(&d,0,0,0,1);
    if(!scan && payload_reads) {printf("FAIL lightweight voice log scanned %u payload locations\n",payload_reads);return 1;}
    assert(!scan || payload_reads>0);
    printf("PASS voice diagnostic scan=%d payload reads=%u\n",scan,payload_reads);
}
'''.replace('/* DIAGNOSTIC */', block)
out = root / 'build-web-tests/audio-diagnostics'
out.mkdir(parents=True, exist_ok=True)
(out / 'test.c').write_text(harness, encoding='utf-8')
subprocess.run([shutil.which('emcc') or 'emcc', str(out / 'test.c'), '-O2',
                '-I', str(root / 'external/xboxrecomp/src/apu'), '-sENVIRONMENT=node',
                '-o', str(out / 'test.js')], check=True)
for scan in ['0', '1']:
    subprocess.run([shutil.which('node') or 'node', str(out / 'test.js'), scan], check=True)
