"""Verify optional IRQ signal-age timing using production helpers and fake QPC."""
from pathlib import Path
import argparse
import shutil
import subprocess

root=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--native',action='store_true')
parser.add_argument('--build-dir',type=Path,default=root/'build-web-tests/irq-profile')
args=parser.parse_args();out=args.build_dir.resolve();out.mkdir(parents=True,exist_ok=True)
source=(root/'external/xboxrecomp/src/kernel/kernel_bridge.c').read_text(encoding='utf-8')
a=source.index('void xbox_kernel_irq_wake(void)');b=source.index('}',a)+1
code=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include "platform/xbox_winnt.h"
#include "platform/win32_compat.h"
static int64_t fake_us;
static unsigned clocks,frequencies,events;
static BOOL fake_qpc(LARGE_INTEGER *v){__atomic_fetch_add(&clocks,1,__ATOMIC_RELAXED);v->QuadPart=fake_us*1000;return TRUE;}
static BOOL fake_freq(LARGE_INTEGER *v){frequencies++;v->QuadPart=1000000000;return TRUE;}
#define QueryPerformanceCounter fake_qpc
#define QueryPerformanceFrequency fake_freq
#include "kernel/irq_profile.h"
#undef QueryPerformanceCounter
#undef QueryPerformanceFrequency
static HANDLE bridge_irq_event(void){return (HANDLE)(uintptr_t)1234;}
static BOOL checked_event(HANDLE h){assert(h==(HANDLE)(uintptr_t)1234);__atomic_fetch_add(&events,1,__ATOMIC_RELAXED);return TRUE;}
#define SetEvent checked_event
/* ACTUAL_WAKE */
#undef SetEvent
static void *producer(void *p){(void)p;xbox_kernel_irq_wake();return NULL;}
static void reset_stats(void){memset(&s_irq_profile_stats,0,sizeof s_irq_profile_stats);}
int main(int argc,char **argv){
    (void)argv;int enabled=argc<2;
    if(enabled)setenv("RECOMP_IRQ_PROFILE","1",1);else unsetenv("RECOMP_IRQ_PROFILE");
    fake_us=1000000000000LL;const int64_t epoch=fake_us;
    if(!enabled){
        BridgeIrqTimes t={1,2,3};
        for(unsigned i=0;i<6;i++){
            bridge_irq_profile_phase(i);assert(!bridge_irq_profile_stamp(i));
            xbox_kernel_irq_wake();assert(!bridge_irq_profile_take());
            bridge_irq_profile_record(0,&t,4,1);bridge_irq_profile_discard(1);bridge_irq_profile_finish(0);
        }
        assert(!clocks && !frequencies && events==6 && !s_irq_profile_stats.calls && !s_irq_profile_pending);
        puts("PASS disabled IRQ profile: actual wake still signals; zero added QPC/frequency queries");return 0;
    }
    bridge_irq_profile_phase(IRQ_PROFILE_WAIT);xbox_kernel_irq_wake();
    fake_us=epoch+1000;BridgeIrqTimes t={0};t.asked=bridge_irq_profile_stamp(IRQ_PROFILE_GGL);
    fake_us=epoch+5000;t.locked=bridge_irq_profile_stamp(IRQ_PROFILE_VBLANK);
    fake_us=epoch+6000;t.isr_begin=bridge_irq_profile_stamp(IRQ_PROFILE_ISR);
    LONGLONG token=bridge_irq_profile_take();assert(token && !(token&7));
    fake_us=epoch+7000;int64_t end=bridge_irq_profile_stamp(IRQ_PROFILE_ISR);
    bridge_irq_profile_record(token,&t,end,1);
    assert(s_irq_profile_stats.age==6000 && s_irq_profile_stats.prelock==1000);
    assert(s_irq_profile_stats.ggl==4000 && s_irq_profile_stats.vblank==1000 && s_irq_profile_stats.isr==1000);
    reset_stats();
    bridge_irq_profile_phase(IRQ_PROFILE_GGL);fake_us=epoch+10000;xbox_kernel_irq_wake();
    t=(BridgeIrqTimes){epoch+9000,epoch+13000,epoch+15000};
    bridge_irq_profile_record(bridge_irq_profile_take(),&t,epoch+17000,1);
    assert(s_irq_profile_stats.age==5000 && !s_irq_profile_stats.prelock);
    assert(s_irq_profile_stats.ggl==3000 && s_irq_profile_stats.vblank==2000 && s_irq_profile_stats.isr==2000);
    reset_stats();
    bridge_irq_profile_phase(IRQ_PROFILE_VBLANK);fake_us=epoch+24000;xbox_kernel_irq_wake();
    t=(BridgeIrqTimes){epoch+20000,epoch+23000,epoch+25000};
    bridge_irq_profile_record(bridge_irq_profile_take(),&t,epoch+26000,1);
    assert(s_irq_profile_stats.age==1000 && !s_irq_profile_stats.prelock && !s_irq_profile_stats.ggl);
    assert(s_irq_profile_stats.vblank==1000 && s_irq_profile_stats.raised_stage==IRQ_PROFILE_VBLANK);
    reset_stats();
    bridge_irq_profile_phase(IRQ_PROFILE_DPC);fake_us=epoch+30000;xbox_kernel_irq_wake();
    bridge_irq_profile_phase(IRQ_PROFILE_WAIT);fake_us=epoch+32000;xbox_kernel_irq_wake();
    token=bridge_irq_profile_take();assert((token&7)==IRQ_PROFILE_DPC);
    t=(BridgeIrqTimes){epoch+40000,epoch+42000,epoch+43000};
    bridge_irq_profile_record(token,&t,epoch+45000,1);
    assert(s_irq_profile_stats.age==13000 && s_irq_profile_stats.prelock==10000 && s_irq_profile_stats.ggl==2000);
    assert(s_irq_profile_stats.vblank==1000 && s_irq_profile_stats.raised_stage==IRQ_PROFILE_DPC);
    /* A faster notification with a slower ISR must not mix its stage
     * components into the earlier worst signal-age sample. */
    fake_us=epoch+46000;bridge_irq_profile_phase(IRQ_PROFILE_WAIT);xbox_kernel_irq_wake();
    BridgeIrqTimes quick={epoch+46100,epoch+46200,epoch+46300};
    bridge_irq_profile_record(bridge_irq_profile_take(),&quick,epoch+56300,1);
    assert(s_irq_profile_stats.age==13000 && s_irq_profile_stats.prelock==10000);
    assert(s_irq_profile_stats.ggl==2000 && s_irq_profile_stats.vblank==1000 && s_irq_profile_stats.isr==2000);
    assert(s_irq_profile_stats.max_isr==10000 && s_irq_profile_stats.raised_stage==IRQ_PROFILE_DPC);
    fake_us=epoch+58000;bridge_irq_profile_phase(IRQ_PROFILE_DPC);
    pthread_t threads[4];for(unsigned i=0;i<4;i++)assert(!pthread_create(&threads[i],NULL,producer,NULL));
    for(unsigned i=0;i<4;i++)assert(!pthread_join(threads[i],NULL));
    token=bridge_irq_profile_take();assert((token&7)==IRQ_PROFILE_DPC);
    assert(((uint64_t)token>>3)-1==(uint64_t)fake_us && !bridge_irq_profile_take());
    assert(InterlockedCompareExchange(&s_irq_profile_coalesced,0,0)==4);
    bridge_irq_profile_discard(token);assert(s_irq_profile_stats.discarded==1);
    bridge_irq_profile_record(0,&t,epoch+46000,-1);bridge_irq_profile_record(0,&t,epoch+46000,0);
    assert(s_irq_profile_stats.missing==2 && s_irq_profile_stats.uncallable==1 && s_irq_profile_stats.declined==1);
    fake_us=epoch+67000;bridge_irq_profile_finish(epoch+60000);
    assert(s_irq_profile_stats.max_dpc==7000 && s_irq_profile_stats.started);
    fake_us+=5000000;bridge_irq_profile_phase(IRQ_PROFILE_WAIT);xbox_kernel_irq_wake();
    bridge_irq_profile_finish(fake_us-3000);
    assert(!s_irq_profile_stats.calls && s_irq_profile_stats.since==fake_us && s_irq_profile_stats.started);
    assert(!InterlockedCompareExchange(&s_irq_profile_coalesced,0,0));
    assert(frequencies==1 && events==11);
    token=bridge_irq_profile_take();assert(token && (token&7)==IRQ_PROFILE_WAIT);
    puts("PASS IRQ profile: exact stage overlaps, matching worst signal, DPC raises, atomic coalescing, missing/discarded notifications and report reset");
}
'''.replace('/* ACTUAL_WAKE */',source[a:b])
(out/'test.c').write_bytes(code.encode('utf-8'))
includes=['-I',str(root/'external/xboxrecomp/src')]
platform=str(root/'external/xboxrecomp/src/platform/win32_compat.c')
if args.native:
    compiler=shutil.which('clang') or shutil.which('cc')
    if not compiler:parser.error('A native compiler is required')
    binary=out/'test'
    subprocess.run([compiler,str(out/'test.c'),platform,*includes,'-O2','-g','-pthread',
                    '-fsanitize=address,undefined','-fno-omit-frame-pointer','-ffunction-sections','-fdata-sections',
                    '-Wl,--gc-sections','-o',str(binary),'-lm'],check=True)
    prefix=[str(binary)]
else:
    compiler,node=shutil.which('emcc'),shutil.which('node')
    if not compiler or not node:parser.error('Emscripten and Node are required')
    binary=out/'test.js'
    subprocess.run([compiler,str(out/'test.c'),platform,*includes,'-O2','-pthread',
                    '-sPTHREAD_POOL_SIZE=4','-sINITIAL_MEMORY=128MB','-sENVIRONMENT=node',
                    '-o',str(binary)],check=True)
    prefix=[node,str(binary)]
for extra in ([],['--off']):subprocess.run([*prefix,*extra],check=True,timeout=60)
