"""Measure the production frame pacer with real SDL waits in an owned browser.

Requires emcc, Node, Playwright and dependencies/sdl3-wasm. No retail assets.
Timing is diagnostic, never a machine-specific CI pass/fail threshold.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=Path, default=root / 'build-web-tests/frame-pacing-host')
    parser.add_argument('--executable', help='Optional browser executable')
    args = parser.parse_args()
    emcc, node = shutil.which('emcc'), shutil.which('node')
    if not emcc or not node:
        parser.error('emcc and Node must be on PATH')
    out = args.build_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    source = root / 'external/xboxrecomp/src/kernel/sdlgpu/sdlgpu_present.inc.c'
    present = source.read_text(encoding='utf-8')
    pacer = present[present.index('static void sg_frame_pace('):present.index('static struct {')]
    sdl = root / 'dependencies/sdl3-wasm'
    library = sdl / 'lib/libSDL3.a'
    code = r'''
#include <SDL3/SDL.h>
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <emscripten/emscripten.h>
#define N 90
static int limit=30,held=1;
static unsigned released,reacquired;
static uint64_t requested;
static double actual;
static int xbox_VideoFpsLimit(void){return limit;}
/* Isolate the real host wait. These lock stubs do not measure guest contention. */
static int xbox_ggl_release_all(void){assert(held);held=0;released++;return 3;}
static void xbox_ggl_reacquire(int depth){assert(!held && depth==3);held=1;reacquired++;}
static void measured_delay(uint64_t ns){
    assert(!held);double start=emscripten_get_now();
    SDL_DelayNS(ns);actual+=emscripten_get_now()-start;requested+=ns;
}
#define SDL_DelayNS measured_delay
/* PRODUCTION */
#undef SDL_DelayNS
static int compare(const void *a,const void *b){double x=*(const double*)a,y=*(const double*)b;return (x>y)-(x<y);}
static void summary(const char *name,int scenario,double *values,int count){
    if(!count)return;
    double sum=0;for(int i=0;i<count;i++)sum+=values[i];
    qsort(values,count,sizeof *values,compare);
    printf("WAITBENCH metric=%s scenario=%d count=%d min=%.4f median=%.4f p95=%.4f max=%.4f mean=%.4f\n",
           name,scenario,count,values[0],values[count/2],values[count*95/100],values[count-1],sum/count);
}
int main(void){
    assert(SDL_Init(0));
    printf("WAITBENCH sdl_performance_frequency=%llu\n",(unsigned long long)SDL_GetPerformanceFrequency());
    const unsigned work_ms[]={0,10,20,28,40,0};
    for(int scenario=0;scenario<6;scenario++){
        double frames[N],overshoot[N],waits[N],requests[N],actuals[N];
        unsigned works[N];int slept=0;
        released=reacquired=0;
        limit=0;sg_frame_pace();limit=30;sg_frame_pace();
        double previous=emscripten_get_now(),begin=previous;
        for(int i=0;i<N;i++){
            unsigned work=scenario==5?10+(i%4)*4:work_ms[scenario];
            double start=emscripten_get_now();
            while(emscripten_get_now()-start<work){}
            requested=0;actual=0;sg_frame_pace();double completed=emscripten_get_now();
            frames[i]=completed-previous;previous=completed;
            if(requested){waits[slept]=requested/1e6;overshoot[slept++]=actual-requested/1e6;}
            works[i]=work;requests[i]=requested/1e6;actuals[i]=actual;
        }
        assert(held && released==reacquired && released==(unsigned)slept);
        /* Defer logging so main-thread stdout proxying cannot perturb pacing. */
        for(int i=0;i<N;i++){
            printf("WAITBENCH frame scenario=%d index=%d work_ms=%u interval_ms=%.4f request_ms=%.4f actual_wait_ms=%.4f\n",
                   scenario,i,works[i],frames[i],requests[i],actuals[i]);
        }
        printf("WAITBENCH scenario=%d fps=%.4f elapsed_ms=%.4f lock_pairs=%u\n",
               scenario,N*1000.0/(previous-begin),previous-begin,released);
        summary("frame_ms",scenario,frames,N);summary("requested_wait_ms",scenario,waits,slept);
        summary("wait_overshoot_ms",scenario,overshoot,slept);
    }
    SDL_Quit();puts("WAITBENCH DONE");return 0;
}
'''.replace('/* PRODUCTION */', pacer)
    generated = out / 'benchmark.c'
    generated.write_bytes(code.encode('utf-8'))
    inputs = [source, library, generated, Path(__file__).resolve(),
              root / 'tools/benchmark-web-waits.cjs', root / 'config/xboxrecomp-web.patch',
              root / 'config/sdl-web.patch']
    manifest = {
        'host': platform.platform(),
        'node': subprocess.check_output([node, '--version'], text=True).strip(),
        'emcc': subprocess.check_output([emcc, '--version'], text=True).splitlines()[0],
        'sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
        'limits': 'Synthetic work; stub guest locks; no game, rendering, audio or contention.',
        'measurement_clock': 'emscripten_get_now milliseconds, independent of production SDL ticks',
    }
    (out / 'build-evidence.json').write_bytes((json.dumps(manifest, indent=2) + '\n').encode())
    subprocess.run([emcc, str(generated), '-I', str(sdl / 'include'), str(library),
                    '-O2', '-pthread', '-sPROXY_TO_PTHREAD=1', '-sPTHREAD_POOL_SIZE=1',
                    '-sEXIT_RUNTIME=1', '-sENVIRONMENT=web,worker', '-sINITIAL_MEMORY=128MB',
                    '-o', str(out / 'benchmark.js')], check=True)
    subprocess.run([node, str(root / 'tools/benchmark-web-waits.cjs'), str(out),
                    *([args.executable] if args.executable else [])], check=True, timeout=150)


if __name__ == '__main__':
    main()
