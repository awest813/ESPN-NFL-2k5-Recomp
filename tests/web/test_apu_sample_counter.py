"""Check the actual APU MMIO counter against samples executed by its pipeline."""
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
source = (root / 'external/xboxrecomp/src/apu/apu_core.c').read_text(encoding='utf-8')


def function(signature):
    start = source.index(signature)
    return source[start:source.index('\n}', start) + 2]


harness = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <assert.h>
#include "apu_regs.h"
#include "apu_schedule_trace.h"
typedef int32_t LONG;
typedef uint64_t hwaddr;
struct DSP { struct { uint8_t pram_opcache[8]; } core; };
typedef struct {
    uint32_t regs[0x20000];
    volatile LONG sample_count;
    bool pause_requested;
    bool set_irq;
    int cond,ep_frame_div,sleep_acc_us,frame_count;
    int64_t frame_count_time_ms;
    struct { bool enabled; int64_t vp_us,dsp_us,output_us,voice_wait_us; unsigned voice_wait_count; } profile;
    struct { bool realtime; struct DSP *dsp; } gp,ep;
} MCPXAPUState;
static struct { bool gp_realtime,ep_realtime; float utilization; int frames_processed; } g_dbg;
static int64_t now_ns=1000000000LL;
static unsigned vp_frames,dsp_frames,monitor_frames;
#define QEMU_CLOCK_VIRTUAL 0
#define QEMU_CLOCK_REALTIME 1
#define qatomic_read(p) __atomic_load_n((p),__ATOMIC_ACQUIRE)
#define qatomic_set(p,v) __atomic_store_n((p),(v),__ATOMIC_RELEASE)
#define qatomic_and(p,v) __atomic_fetch_and((p),(v),__ATOMIC_ACQ_REL)
#define address_space_memory NULL
static LONG InterlockedCompareExchange(volatile LONG *p,LONG value,LONG compare) {
    __atomic_compare_exchange_n(p,&compare,value,false,__ATOMIC_SEQ_CST,__ATOMIC_SEQ_CST);return compare;
}
static LONG InterlockedExchange(volatile LONG *p,LONG value) { return __atomic_exchange_n(p,value,__ATOMIC_SEQ_CST); }
static LONG InterlockedExchangeAdd(volatile LONG *p,LONG value) { return __atomic_fetch_add(p,value,__ATOMIC_SEQ_CST); }
static int64_t qemu_clock_get_ns(int clock) { (void)clock;return now_ns; }
static int64_t qemu_clock_get_ms(int clock) { return qemu_clock_get_ns(clock)/1000000; }
static int64_t qemu_clock_get_us(int clock) { return qemu_clock_get_ns(clock)/1000; }
static void update_irq(MCPXAPUState *d) { (void)d; }
static void qemu_cond_broadcast(int *c) { (void)c; }
static void stl_le_phys(void *memory,uint32_t addr,uint32_t value) { (void)memory;(void)addr;(void)value; }
static void mcpx_apu_update_dsp_preference(MCPXAPUState *d) { (void)d; }
static void mcpx_apu_vp_reset(MCPXAPUState *d) { (void)d; }
static void mcpx_apu_dsp_reset(MCPXAPUState *d) { (void)d; }
static void mcpx_debug_begin_frame(void) {}
static void mcpx_debug_end_frame(void) {}
static void mcpx_apu_vp_frame(MCPXAPUState *d,float bins[NUM_MIXBINS][NUM_SAMPLES_PER_FRAME]) { (void)d;(void)bins;vp_frames++; }
static void mcpx_apu_dsp_frame(MCPXAPUState *d,float bins[NUM_MIXBINS][NUM_SAMPLES_PER_FRAME]) { (void)d;(void)bins;dsp_frames++; }
static void mcpx_apu_monitor_frame(MCPXAPUState *d) { (void)d;monitor_frames++; }
/* READ */
/* WRITE */
/* FRAME */
/* RESET */
static uint32_t sample_time(MCPXAPUState *d) { return (uint32_t)mcpx_apu_read(d,NV_PAPU_XGSCNT,4); }
int main(void) {
    static MCPXAPUState d;
    uint32_t actual=sample_time(&d);
    if(actual) {printf("FAIL reset sample counter is %u instead of 0 at host time 1 s\n",actual);return 1;}
    for(unsigned i=0;i<1500;i++)se_frame(&d);
    assert(sample_time(&d)==48000);
    assert(vp_frames==1500 && dsp_frames==1500 && monitor_frames==1500);
    now_ns+=10000000000LL;d.ep_frame_div+=800;
    assert(sample_time(&d)==48000); /* Host/idle monitor time is not sequencer time. */
    mcpx_apu_write(&d,NV_PAPU_XGSCNT,123,4);
    assert(sample_time(&d)==123);
    se_frame(&d);assert(sample_time(&d)==155);
    mcpx_apu_write(&d,NV_PAPU_XGSCNT,0xfffffff0u,4);
    se_frame(&d);assert(sample_time(&d)==16);
    mcpx_apu_write(&d,NV_PAPU_XGSCNT,0x7ffffff0u,4);
    se_frame(&d);assert(sample_time(&d)==0x80000010u);
    mcpx_apu_write(&d,NV_PAPU_XGSCNT,0x100000007ULL,4);
    assert(sample_time(&d)==7); /* Hardware register is 32 bits. */
    mcpx_apu_reset_locked(&d);assert(sample_time(&d)==0);
    puts("PASS APU sample counter: 48 kHz pipeline time, host-clock independence, writes and 32-bit wrap");
}
'''.replace('/* READ */', function('uint64_t mcpx_apu_read(')).replace('/* WRITE */', function('void mcpx_apu_write(')).replace('/* FRAME */', function('static void se_frame(')).replace('/* RESET */', function('static void mcpx_apu_reset_locked('))
out = root / 'build-web-tests/apu-sample-counter'
out.mkdir(parents=True, exist_ok=True)
(out / 'test.c').write_text(harness, encoding='utf-8')
subprocess.run([shutil.which('emcc') or 'emcc', str(out / 'test.c'), '-O2',
                '-I', str(root / 'external/xboxrecomp/src/apu'),
                '-fsanitize=undefined', '-fno-sanitize-recover=undefined',
                '-sENVIRONMENT=node', '-o', str(out / 'test.js')], check=True)
subprocess.run([shutil.which('node') or 'node', str(out / 'test.js')], check=True)
