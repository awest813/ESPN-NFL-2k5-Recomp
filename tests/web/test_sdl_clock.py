"""Check the linked SDL Wasm clock against monotonic time and wall-clock jumps."""
import argparse
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build-dir', type=Path, default=root / 'build-web-tests/sdl-clock')
parser.add_argument('--browser', action='store_true')
parser.add_argument('--executable', help='Optional browser executable with --browser')
args = parser.parse_args()
out = args.build_dir.resolve()
out.mkdir(parents=True, exist_ok=True)
sdl = root / 'dependencies/sdl3-wasm'
source = r'''
#include <SDL3/SDL.h>
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <time.h>
#include <emscripten/emscripten.h>
EM_JS(void, shift_wall_clock, (double offset), {
    if (!Module['savedDateNow']) Module['savedDateNow'] = Date.now;
    const original = Module['savedDateNow'];
    Date.now = () => original() + offset;
});
EM_JS(void, restore_wall_clock, (), {
    Date.now = Module['savedDateNow'];
});
static uint64_t monotonic_ns(void){
    struct timespec ts;assert(!clock_gettime(CLOCK_MONOTONIC,&ts));
    return (uint64_t)ts.tv_sec*1000000000ULL+ts.tv_nsec;
}
static uint64_t worker_counter;
static int SDLCALL check_worker(void *unused){
    (void)unused;worker_counter=SDL_GetPerformanceCounter();
    assert(SDL_GetPerformanceFrequency()==1000000000ULL);
    uint64_t before=monotonic_ns(),value=SDL_GetPerformanceCounter(),after=monotonic_ns();
    assert(before<=value && value<=after);return 73;
}
int main(void){
    assert(SDL_Init(0));
    /* A 1 MHz frequency identifies SDL's gettimeofday fallback on this port. */
    assert(SDL_GetPerformanceFrequency()==1000000000ULL);
    uint64_t before_worker=SDL_GetPerformanceCounter();
    SDL_Thread *thread=SDL_CreateThread(check_worker,"clock_check",NULL);
    if(!thread)fprintf(stderr,"SDL clock worker creation failed: %s\n",SDL_GetError());
    assert(thread);int result=0;SDL_WaitThread(thread,&result);assert(result==73);
    assert(before_worker<=worker_counter && worker_counter<=SDL_GetPerformanceCounter());
    const double offsets[]={0,3600000,-3600000,86400000,-86400000,0};
    uint64_t previous=SDL_GetPerformanceCounter(),ticks=SDL_GetTicksNS();
    for(unsigned step=0;step<sizeof offsets/sizeof *offsets;step++){
        shift_wall_clock(offsets[step]);
        for(unsigned i=0;i<1000;i++){
            uint64_t before=monotonic_ns(),value=SDL_GetPerformanceCounter(),after=monotonic_ns();
            assert(before<=value && value<=after && value>=previous);previous=value;
            uint64_t next=SDL_GetTicksNS();assert(next>=ticks);ticks=next;
        }
    }
    restore_wall_clock();SDL_Quit();
    puts("WAITBENCH PASS linked SDL monotonic clock: live SDL thread/common origin, 6000 brackets, forward/backward hour/day wall-clock changes, monotonic ticks");
    puts("WAITBENCH DONE");return 0;
}
'''
(out / 'benchmark.c').write_bytes(source.encode('utf-8'))
emcc, node = shutil.which('emcc'), shutil.which('node')
if not emcc or not node:
    parser.error('emcc and Node must be on PATH')
subprocess.run([emcc, str(out / 'benchmark.c'), '-I', str(sdl / 'include'),
                str(sdl / 'lib/libSDL3.a'), '-O2', '-pthread',
                '-sPROXY_TO_PTHREAD=1', '-sPTHREAD_POOL_SIZE=1', '-sEXIT_RUNTIME=1',
                '-sINITIAL_MEMORY=128MB', '-sENVIRONMENT=web,worker,node',
                '-o', str(out / 'benchmark.js')], check=True)
if args.browser:
    subprocess.run([node, str(root / 'tools/benchmark-web-waits.cjs'), str(out),
                    *([args.executable] if args.executable else [])], check=True, timeout=150)
else:
    subprocess.run([node, str(out / 'benchmark.js')], check=True, timeout=30)
