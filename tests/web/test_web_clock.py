"""Check Win32-compatible web clock units, monotonicity and hot-call cost."""
from pathlib import Path
import shutil
import subprocess
root=Path(__file__).resolve().parents[2]
text=(root/'external/xboxrecomp/src/platform/win32_compat.c').read_text(encoding='utf-8')
clock=text[text.index('ULONGLONG GetTickCount64(void)'):text.index('/* ===================================================================== */\n/* Misc',text.index('ULONGLONG GetTickCount64(void)'))]
harness=r'''
#include <emscripten/emscripten.h>
#include <stdint.h>
#include <time.h>
#include <assert.h>
#include <math.h>
#include <stdio.h>
typedef uint64_t ULONGLONG;
typedef int64_t LONGLONG;
typedef uint32_t DWORD;
typedef int BOOL;
typedef struct {int64_t QuadPart;} LARGE_INTEGER,*PLARGE_INTEGER;
#define TRUE 1
static int virtual_time;
static double now_ms;
static double test_now(void){return virtual_time?now_ms:emscripten_get_now();}
#define emscripten_get_now test_now
/* CLOCK */
#undef emscripten_get_now
static LONGLONG reference(void){struct timespec ts;clock_gettime(CLOCK_MONOTONIC,&ts);return (LONGLONG)ts.tv_sec*1000000000LL+ts.tv_nsec;}
int main(void){
    LARGE_INTEGER value,freq;
    assert(QueryPerformanceFrequency(&freq) && freq.QuadPart==1000000000LL);
    virtual_time=1;now_ms=1.25;assert(QueryPerformanceCounter(&value) && value.QuadPart==1250000);
    assert(GetTickCount64()==1 && GetTickCount()==1);
    now_ms=86400000.5;QueryPerformanceCounter(&value);assert(value.QuadPart==86400000500000LL);
    assert(GetTickCount64()==86400000ULL);
    virtual_time=0;LONGLONG before=reference(),last=0;
    for(int i=0;i<10000;i++){QueryPerformanceCounter(&value);assert(value.QuadPart>=last);last=value.QuadPart;}
    LONGLONG after=reference();assert(before<=last && last<=after);
    assert(llabs((LONGLONG)GetTickCount64()-last/1000000)<250);
    puts("PASS web QPC nanoseconds, millisecond tick counts, one-day precision and 10000 monotonic reads");
    volatile LONGLONG sink=0;enum{N=100000};
    double start=emscripten_get_now();for(int i=0;i<N;i++)sink^=reference();double old=emscripten_get_now()-start;
    start=emscripten_get_now();for(int i=0;i<N;i++){QueryPerformanceCounter(&value);sink^=value.QuadPart;}double fast=emscripten_get_now()-start;
    printf("Web QPC benchmark: timespec %.2f ms, direct %.2f ms, %.2fx (sink %lld)\n",old,fast,old/fast,(long long)sink);
}
'''.replace('/* CLOCK */',clock).replace('#include <math.h>','#include <math.h>\n#include <stdlib.h>')
out=root/'build-web-tests/web-clock';out.mkdir(parents=True,exist_ok=True)
(out/'test.c').write_text(harness,encoding='utf-8')
subprocess.run([shutil.which('emcc') or 'emcc',str(out/'test.c'),'-O2','-sENVIRONMENT=node','-o',str(out/'test.js')],check=True)
subprocess.run([shutil.which('node') or 'node',str(out/'test.js')],check=True)
