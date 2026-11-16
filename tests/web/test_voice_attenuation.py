"""Check every voice attenuation input against the original gain calculation."""
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
source = (root / 'external/xboxrecomp/src/apu/apu_vp.c').read_text(encoding='utf-8')
start = source.index('static float attenuate(')
function = source[start:source.index('\n}', start) + 2]
out = root / 'build-web-tests/voice-attenuation'
out.mkdir(parents=True, exist_ok=True)
harness = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <assert.h>
#include <time.h>
#ifdef __EMSCRIPTEN__
#include <emscripten.h>
#else
static double emscripten_get_now(void) {return (double)clock()*1000.0/CLOCKS_PER_SEC;}
#endif
static unsigned exponentiations;
static float original(uint16_t vol) {
    vol &= 0xfff;
    return vol == 0xfff ? 0.0f : powf(10.0f, vol / (64.0f * -20.0f));
}
static float counted_powf(float a,float b) {exponentiations++;return powf(a,b);}
#define powf counted_powf
/* ATTENUATE */
#undef powf
static void equal(float a,float b) {assert(!memcmp(&a,&b,sizeof(a)));}
typedef float (*gain_fn)(uint16_t);
static double measure(gain_fn fn) {
    volatile gain_fn gain=fn;volatile float sum=0;
    double start=emscripten_get_now();
    for(unsigned i=0;i<2000000;i++)sum+=gain((uint16_t)(i*251u));
    assert(sum>0);return emscripten_get_now()-start;
}
int main(int argc,char **argv) {
    /* Muting never allocates a gain; upper input bits retain their mask. */
    equal(attenuate(0xffff),0.0f);assert(exponentiations==0);
    for(unsigned v=0;v<65536;v++)equal(attenuate((uint16_t)v),original((uint16_t)v));
    assert(exponentiations==4095);
    for(unsigned v=65536;v-->0;)equal(attenuate((uint16_t)v),original((uint16_t)v));
    assert(exponentiations==4095);
    /* Preserve each rounded gain in both the bin and monitor arithmetic. */
    for(unsigned v=0;v<4096;v++)for(unsigned h=0;h<8;h++) {
        float a=attenuate(v),b=original(v),headroom=(float)(1u<<h);
        for(int s=-32768;s<=32767;s+=997) {
            float sample=(float)s/32768.0f;
            equal((0.75f*a/headroom)*sample,(0.75f*b/headroom)*sample);
        }
    }
    puts("PASS voice attenuation: all 65536 inputs bit-identical, exact mix gains, 4095 lazy evaluations");
    if(argc>1)for(unsigned r=0;r<7;r++) {
        double before,after;
        if(r&1){after=measure(attenuate);before=measure(original);}
        else{before=measure(original);after=measure(attenuate);}
        printf("BENCH original=%.3fms cached=%.3fms\n",before,after);
    }
}
'''.replace('/* ATTENUATE */', function)
(out / 'test.c').write_text(harness, encoding='utf-8')
base = [shutil.which('emcc') or 'emcc', str(out / 'test.c'), '-sENVIRONMENT=node']
subprocess.run([*base, '-O1', '-fsanitize=undefined', '-fno-sanitize-recover=undefined',
                '-o', str(out / 'test.js')], check=True)
subprocess.run([shutil.which('node') or 'node', str(out / 'test.js')], check=True)
if '--benchmark' in sys.argv:
    subprocess.run([*base, '-O3', '-o', str(out / 'benchmark.js')], check=True)
    subprocess.run([shutil.which('node') or 'node', str(out / 'benchmark.js'), 'benchmark'], check=True)
