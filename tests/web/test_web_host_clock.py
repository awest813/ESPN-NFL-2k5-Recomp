"""Check Web host clocks against the SDK's JavaScript nanosecond conversion."""
import argparse
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--benchmark', action='store_true')
parser.add_argument('--build-dir', type=Path, default=root / 'build-web-tests/web-host-clock')
args = parser.parse_args()
out = args.build_dir.resolve()
out.mkdir(parents=True, exist_ok=True)
source = (root / 'external/xboxrecomp/src/platform/win32_compat.c').read_text(encoding='utf-8')


def function(signature):
    start = source.index(signature)
    body = source.index('{', start)
    depth = 1
    for end in range(body + 1, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if not depth: return source[start:end + 1]
    raise ValueError(signature)


code = r'''
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <pthread.h>
#include <emscripten/emscripten.h>
typedef uint64_t ULONGLONG;
typedef uint32_t DWORD;
typedef int64_t LONGLONG;
typedef int BOOL;
#define TRUE 1
typedef struct {LONGLONG QuadPart;} LARGE_INTEGER,*PLARGE_INTEGER;
static _Thread_local double fake_ms;
static _Thread_local unsigned clock_calls;
static double controlled_clock(void){clock_calls++;return fake_ms;}
EM_JS(uint64_t, sdk_reference_ns, (double now), {
    return BigInt(Math.round(now * 1000 * 1000));
});
#define emscripten_get_now controlled_clock
/* PRODUCTION */
#undef emscripten_get_now
#define web_monotonic_ns actual_web_monotonic_ns
#define GetTickCount64 actual_GetTickCount64
#define GetTickCount actual_GetTickCount
#define QueryPerformanceCounter actual_QueryPerformanceCounter
#define QueryPerformanceFrequency actual_QueryPerformanceFrequency
/* PRODUCTION_REAL */
#undef web_monotonic_ns
#undef GetTickCount64
#undef GetTickCount
#undef QueryPerformanceCounter
#undef QueryPerformanceFrequency
static uint64_t checks;
static void check(double value) {
    fake_ms=value;uint64_t expected=sdk_reference_ns(value);LARGE_INTEGER qpc,freq;
    unsigned before=clock_calls;
    assert(QueryPerformanceCounter(&qpc) && QueryPerformanceFrequency(&freq));
    assert(freq.QuadPart==1000000000LL && (uint64_t)qpc.QuadPart==expected);
    assert(GetTickCount64()==expected/1000000ULL);
    assert(GetTickCount()==(uint32_t)(expected/1000000ULL));
    assert(clock_calls-before==3);checks++;
}
static void check_live(void);
static uint64_t direct_qpc(void);
static uint64_t worker_qpc;
static void *worker(void *unused) {
    (void)unused;worker_qpc=direct_qpc();const double epoch=1795160000000.0;
    for(unsigned i=0;i<2000;i++)check(epoch+i/16.0);
    check_live();
    return NULL;
}
static uint64_t legacy_ticks(void) {
    struct timespec ts;assert(!clock_gettime(CLOCK_MONOTONIC,&ts));
    return (uint64_t)ts.tv_sec*1000+(uint64_t)ts.tv_nsec/1000000;
}
static uint64_t direct_ticks(void) {
    return actual_GetTickCount64();
}
static uint64_t legacy_qpc(void) {
    struct timespec ts;assert(!clock_gettime(CLOCK_MONOTONIC,&ts));
    return (uint64_t)ts.tv_sec*1000000000ULL+ts.tv_nsec;
}
static uint64_t direct_qpc(void) {
    LARGE_INTEGER t;assert(actual_QueryPerformanceCounter(&t));return (uint64_t)t.QuadPart;
}
static void check_live(void) {
    uint64_t previous=0;
    for(unsigned i=0;i<1000;i++) {
        uint64_t before=legacy_qpc(),value=direct_qpc(),after=legacy_qpc();
        assert(before<=value && value<=after && value>=previous);previous=value;
        uint64_t a=legacy_ticks(),b=direct_ticks(),c=legacy_ticks();
        assert(a<=b && b<=c);
    }
}
static volatile uint64_t observed;
__attribute__((noinline)) static double measure(uint64_t (*function)(void)) {
    uint64_t sum=0;double start=emscripten_get_now();
    typedef uint64_t (*ClockFunction)(void);
    volatile ClockFunction call=function;
    for(unsigned i=0;i<200000;i++)sum+=call();
    observed^=sum;return emscripten_get_now()-start;
}
int main(int argc,char **argv) {
    (void)argv;const double values[]={0,-0.0,0.0000005,0.0000015,0.0000025,
        0.9999995,1.0,4294967295.9999995,4294967296.0,1795160000000.0,
        4503599627.370497,9000000000000.0};
    for(unsigned i=0;i<sizeof values/sizeof values[0];i++)check(values[i]);
    uint64_t state=0x9e3779b97f4a7c15ULL;
    for(unsigned i=0;i<100000;i++) {
        state^=state<<13;state^=state>>7;state^=state<<17;
        double mantissa=(double)(state>>11)/9007199254740992.0;
        check(ldexp(mantissa,(int)(i%64)-20));
    }
    /* Probe representable neighbors around half nanoseconds, millisecond
     * boundaries, DWORD wrap and the SDK's epoch-sized pthread origin. */
    for(unsigned i=0;i<sizeof values/sizeof values[0];i++) {
        if(values[i]<=0)continue;
        double lo=values[i],hi=values[i];
        for(unsigned j=0;j<64;j++){check(lo);check(hi);lo=nextafter(lo,0);hi=nextafter(hi,INFINITY);}
    }
    check_live();
    uint64_t sequential=checks,before_worker=direct_qpc();pthread_t thread;assert(!pthread_create(&thread,NULL,worker,NULL));
    assert(!pthread_join(thread,NULL));assert(checks==sequential+2000);
    assert(before_worker<=worker_qpc && worker_qpc<=direct_qpc());
    printf("PASS %llu Web clock values against SDK JS rounding: half-ns, precision boundaries, DWORD wrap and worker calls\n",(unsigned long long)checks);
    if(argc>1) {
        uint64_t (*old[])(void)={legacy_ticks,legacy_qpc},(*new[])(void)={direct_ticks,direct_qpc};
        for(unsigned kind=0;kind<2;kind++) {
            measure(old[kind]);measure(new[kind]);
            for(unsigned round=0;round<7;round++) {
                double a,b;if(round&1){b=measure(new[kind]);a=measure(old[kind]);}
                else{a=measure(old[kind]);b=measure(new[kind]);}
                printf("BENCH %s round=%u legacy=%.4fms direct=%.4fms\n",kind?"qpc":"ticks",round,a,b);
            }
        }
    }
}
'''
production = '\n'.join(function(s) for s in ['static ULONGLONG web_monotonic_ns(',
    'ULONGLONG GetTickCount64(', 'DWORD GetTickCount(', 'BOOL QueryPerformanceCounter(',
    'BOOL QueryPerformanceFrequency('])
code = code.replace('/* PRODUCTION */', production).replace('/* PRODUCTION_REAL */', production)
(out / 'test.c').write_bytes(code.encode())
compiler, node = shutil.which('emcc'), shutil.which('node')
if not compiler or not node: parser.error('Emscripten and Node required')
flags = ['-O3'] if args.benchmark else ['-O2', '-fsanitize=undefined', '-fno-sanitize-recover=undefined']
subprocess.run([compiler, str(out / 'test.c'), *flags, '-pthread', '-sPTHREAD_POOL_SIZE=1',
                '-sINITIAL_MEMORY=128MB', '-sENVIRONMENT=node', '-o', str(out / 'test.js')], check=True)
subprocess.run([node, str(out / 'test.js'), *(['--benchmark'] if args.benchmark else [])], check=True, timeout=60)
