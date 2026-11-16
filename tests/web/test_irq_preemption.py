"""An interrupt must preempt translated calls even without a kernel boundary."""
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
out = root / 'build-web-tests/irq-preemption'
out.mkdir(parents=True, exist_ok=True)
code = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "kernel/xbox_ggl.c"
#include "recomp_types.h"
int g_interp_active;
uint8_t dirty[0x10000];
uint8_t *g_interp_dirty_bits=dirty;
uint32_t g_interp_dirty_limit=sizeof(dirty)*8;
RECOMP_TLS uint32_t g_eax;
static volatile LONG serviced,interpreted;
static unsigned bodies;
void recomp_interp_call(uint32_t va) { assert(va==0x1234);InterlockedIncrement(&interpreted); }
static void translated(void) { RECOMP_INTERP_GATE(0x1234u);bodies++; }
static DWORD WINAPI interrupt_thread(LPVOID unused) {
    (void)unused;xbox_ggl_set_priority(100);xbox_ggl_enter();
    g_eax=0xdeadbeefu;InterlockedExchange(&serviced,1);xbox_ggl_leave();return 0;
}
int main(void) {
    setenv("RECOMP_GGL","1",1);setenv("RECOMP_GGL_WATCHDOG","0",1);
    xbox_ggl_enter();xbox_ggl_enter();g_eax=0x12345678u;
    HANDLE thread=CreateThread(NULL,0,interrupt_thread,NULL,0,NULL);assert(thread);
    while(InterlockedCompareExchange(&g_waiters,0,0)==0)Sleep(1);
    LARGE_INTEGER start,now,freq;QueryPerformanceFrequency(&freq);QueryPerformanceCounter(&start);
    do {
        translated();QueryPerformanceCounter(&now);
    }while(!InterlockedCompareExchange(&serviced,0,0) && now.QuadPart-start.QuadPart<freq.QuadPart/5);
    int delivered=InterlockedCompareExchange(&serviced,0,0);
    assert(t_depth==2 && g_eax==0x12345678u);
    xbox_ggl_leave();xbox_ggl_leave();
    assert(WaitForSingleObject(thread,5000)==WAIT_OBJECT_0);CloseHandle(thread);
    if(!delivered) {puts("FAIL queued interrupt cannot preempt translated calls for 200 ms");return 1;}
    assert(g_eax==0x12345678u);
    xbox_ggl_enter();
    int slot=ggl_stat_slot();LONG grants=g_stat[slot].grants;
    for(unsigned i=0;i<10000;i++)translated();
    assert(g_stat[slot].grants==grants); /* No lock churn without an interrupt. */
    g_interp_active=1;dirty[0x1234>>3]|=1u<<(0x1234&7);
    unsigned before=bodies;translated();assert(interpreted==1 && bodies==before);
    xbox_ggl_leave();
    printf("PASS interrupt preemption at translated entry: %.3f ms, recursive depth/TLS preserved, idle calls and interpreter gate intact\n",
        (now.QuadPart-start.QuadPart)*1000.0/freq.QuadPart);
}
'''
(out / 'test.c').write_text(code, encoding='utf-8')
subprocess.run([shutil.which('emcc') or 'emcc', str(out / 'test.c'),
                str(root / 'external/xboxrecomp/src/platform/win32_compat.c'),
                '-I', str(root / 'external/xboxrecomp/src'),
                '-I', str(root / 'src/recomp/gen'), '-O2', '-pthread',
                '-sPTHREAD_POOL_SIZE=2', '-sINITIAL_MEMORY=128MB', '-sENVIRONMENT=node', '-o', str(out / 'test.js')], check=True)
subprocess.run([shutil.which('node') or 'node', str(out / 'test.js')], check=True, timeout=30)
