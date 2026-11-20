"""Exercise the production atomic trace publisher and its serialized JS reader."""
from pathlib import Path
import argparse, shutil, subprocess
root=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--native',action='store_true')
parser.add_argument('--publisher-only',action='store_true',help='Run only the C publisher, for native sanitizer CI')
parser.add_argument('--build-dir',type=Path,default=root/'build-web-tests/apu-schedule-trace')
args=parser.parse_args();out=args.build_dir.resolve();out.mkdir(parents=True,exist_ok=True)
core=(root/'external/xboxrecomp/src/apu/apu_core.c').read_text(encoding='utf-8')
a=core.index('    int64_t stage_start =',core.index('static void se_frame('))
b=core.index('    d->ep_frame_div++;',a)
stages=core[a:b]
source=r'''
#define APU_SCHEDULE_TRACE_TEST 1
#include "apu_schedule_trace.h"
#include <assert.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
static const uint64_t epoch=1795210000000000ULL;
static _Atomic unsigned done;
typedef struct {struct {unsigned enabled,voice_wait_count;int64_t voice_wait_us,vp_us,dsp_us,output_us;} profile;} FakeApu;
static int64_t fake_time,stage_duration;
static unsigned clock_reads;
#define QEMU_CLOCK_REALTIME 0
static int64_t qemu_clock_get_us(int unused){(void)unused;clock_reads++;return fake_time;}
static void mcpx_apu_vp_frame(FakeApu*d,float bins[][1]){(void)bins;fake_time+=stage_duration;d->profile.voice_wait_count=7;}
static void mcpx_apu_dsp_frame(FakeApu*d,float bins[][1]){(void)d;(void)bins;fake_time+=stage_duration;}
static void mcpx_apu_monitor_frame(FakeApu*d){(void)d;fake_time+=stage_duration;}
static void stages(FakeApu*d){float mixbins[1][1];
/* LIVE_STAGES */
}
static void stage_tests(void){
    FakeApu d={0};fake_time=epoch;stage_duration=3000;stages(&d);
    assert(!clock_reads && !atomic_load(&s_apu_trace.published));
    d.profile.enabled=1;stage_duration=1999;stages(&d);assert(!atomic_load(&s_apu_trace.published));
    stage_duration=2000;fake_time=epoch;stages(&d);assert(atomic_load(&s_apu_trace.published)==3);
    for(unsigned i=0;i<3;i++){
        ApuTraceEntry*e=&s_apu_trace.entries[i];
        assert(atomic_load(&e->start_us)==epoch+i*2000 && atomic_load(&e->end_us)==epoch+(i+1)*2000);
        assert(atomic_load(&e->kind)==APU_TRACE_VP+i);
    }
    assert(atomic_load(&s_apu_trace.entries[0].detail)==7 && clock_reads==8);
    atomic_store(&s_apu_trace.published,0);
    puts("PASS production stage hooks: exact 2ms threshold, ordered stage spans and zero disabled-profile clock reads/publications");
}

static void *writer(void *unused){
    (void)unused;
    for(unsigned n=1;n<=50000;n++)apu_schedule_trace_record(n%8+1,epoch+(uint64_t)n*17,
        epoch+(uint64_t)n*17+2000+n%1000,n^0xa5a55a5au);
    atomic_store(&done,1);return NULL;
}
static unsigned check(uint64_t n){
    ApuTraceEntry *e=&s_apu_trace.entries[(n-1)&(APU_TRACE_CAPACITY-1)];
    if(atomic_load(&e->guard)!=n*2)return 0;
    uint64_t start=atomic_load(&e->start_us),end=atomic_load(&e->end_us);
    unsigned kind=atomic_load(&e->kind),detail=atomic_load(&e->detail);
    if(atomic_load(&e->guard)!=n*2)return 0;
    assert(start==epoch+n*17 && end==start+2000+n%1000);
    assert(kind==n%8+1 && detail==((unsigned)n^0xa5a55a5au));return 1;
}
static void dump(const char *name){FILE*f=fopen(name,"wb");assert(f);assert(fwrite(&s_apu_trace,1,sizeof s_apu_trace,f)==sizeof s_apu_trace);assert(!fclose(f));}
int main(void){
    stage_tests();
    assert(sizeof(ApuTraceEntry)==32 && sizeof s_apu_trace==16+4096*32);
    pthread_t thread;assert(!pthread_create(&thread,NULL,writer,NULL));unsigned observed=0;
    while(!atomic_load(&done)){uint64_t n=atomic_load(&s_apu_trace.published);if(n)observed+=check(n);}
    assert(!pthread_join(thread,NULL));assert(atomic_load(&s_apu_trace.published)==50000);
    for(unsigned n=50000-4096+1;n<=50000;n++)observed+=check(n);
    assert(observed>=4096);dump("trace.bin");
    atomic_store(&s_apu_trace.published,0xfffffffeULL);
    apu_schedule_trace_record(APU_TRACE_WAKE,epoch,epoch+17000,1000);
    apu_schedule_trace_record(APU_TRACE_VP,epoch+17000,epoch+22000,3);
    assert(atomic_load(&s_apu_trace.published)==0x100000000ULL);dump("trace-wrap.bin");
    puts("PASS production APU trace: 50000 concurrent publications, stable tail payloads, fixed layout and 64-bit sequence crossing");
}
'''
(out/'test.c').write_bytes(source.replace('/* LIVE_STAGES */',stages).encode('utf-8'))
compiler=(shutil.which('clang') or shutil.which('cc')) if args.native else shutil.which('emcc')
if not compiler:parser.error('C compiler is required')
flags=['-O2','-pthread','-I',str(root/'external/xboxrecomp/src/apu')]
if args.native:
    binary=out/'test';flags+=['-g','-fsanitize=address,undefined','-fno-omit-frame-pointer']
else:
    binary=out/'test.js';flags+=['-sPTHREAD_POOL_SIZE=1','-sENVIRONMENT=node','-sNODERAWFS=1']
subprocess.run([compiler,str(out/'test.c'),*flags,'-o',str(binary)],check=True)
command=[str(binary)] if args.native else [shutil.which('node') or 'node',str(binary)]
subprocess.run(command,cwd=out,check=True,timeout=60)
if not args.publisher_only:
    subprocess.run([shutil.which('node') or 'node',str(root/'tests/web/test_apu_trace.cjs'),str(out)],check=True)
