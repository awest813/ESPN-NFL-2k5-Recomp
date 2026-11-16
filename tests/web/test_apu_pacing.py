"""Exercise the production APU throttle with a deterministic wall clock."""
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
source = (root / 'external/xboxrecomp/src/apu/apu_core.c').read_text(encoding='utf-8')
start = source.index('static void throttle(')
function = source[start:source.index('\n}', start) + 2]
harness = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <assert.h>
#include "apu_regs.h"
#define QEMU_CLOCK_REALTIME 0
typedef struct {
    int ep_frame_div,cond,lock,sleep_acc_us;
    bool pause_requested;
    int64_t next_frame_time_us;
    unsigned next_frame_remainder;
} MCPXAPUState;
static int64_t now_us;
static unsigned waits;
static int64_t qemu_clock_get_us(int clock) { (void)clock; return now_us; }
static void qemu_cond_timedwait(int *cond,int *lock,int ms) {
    (void)cond;(void)lock;assert(ms>0);now_us+=(int64_t)ms*1000;waits++;
}
/* THROTTLE */
int main(void) {
    const int64_t epoch=1000000000000LL;
    MCPXAPUState d={0};now_us=epoch;
    for(unsigned i=0;i<675000;i++) {
        now_us=d.next_frame_time_us ? d.next_frame_time_us : epoch;
        throttle(&d);
        int64_t expected=epoch+((int64_t)(i+1)*256000000)/48000;
        if(d.next_frame_time_us!=expected) {
            printf("FAIL batch %u deadline drift %lld us\n",i+1,(long long)(d.next_frame_time_us-expected));return 1;
        }
    }
    assert(d.next_frame_time_us==epoch+3600000000LL); /* One hour, 48 kHz. */
    assert(!d.next_frame_remainder && !waits);
    int64_t before=d.next_frame_time_us;
    d.ep_frame_div=1;throttle(&d);assert(d.next_frame_time_us==before);
    d.ep_frame_div=0;now_us=before+64000;
    throttle(&d);assert(d.next_frame_time_us==before+5333); /* Bounded catch-up. */
    now_us=d.next_frame_time_us+64001;before=now_us;
    throttle(&d);assert(d.next_frame_time_us==before+5333); /* Rebase phase too. */
    throttle(&d);assert(waits && now_us<d.next_frame_time_us); /* Actually waits. */
    puts("PASS APU throttle: exact one-hour pacing, frame divisor, catch-up, rebase and wait");
}
'''.replace('/* THROTTLE */', function)
out = root / 'build-web-tests/apu-pacing'
out.mkdir(parents=True, exist_ok=True)
(out / 'test.c').write_text(harness, encoding='utf-8')
subprocess.run([shutil.which('emcc') or 'emcc', str(out / 'test.c'), '-O2',
                '-I', str(root / 'external/xboxrecomp/src/apu'),
                '-fsanitize=undefined', '-fno-sanitize-recover=undefined',
                '-sENVIRONMENT=node', '-o', str(out / 'test.js')], check=True)
subprocess.run([shutil.which('node') or 'node', str(out / 'test.js')], check=True)
