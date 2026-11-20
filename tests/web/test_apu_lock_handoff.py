"""Reproduce queued MMIO writers behind a mixer which never reaches its throttle."""
from pathlib import Path
import argparse
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--native',action='store_true')
parser.add_argument('--runtime',type=Path,default=root/'external/xboxrecomp')
parser.add_argument('--build-dir',type=Path,default=root/'build-web-tests/apu-lock-handoff')
args=parser.parse_args()
source = (args.runtime / 'src/apu/apu_core.c').read_text(encoding='utf-8')

def function(signature):
    start = source.index(signature)
    return source[start:source.index('\n}', start) + 2]

harness = r'''
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <stdio.h>
#include <pthread.h>
#ifdef __EMSCRIPTEN__
#include <emscripten/emscripten.h>
#include <emscripten/threading.h>
#else
#include <time.h>
static double emscripten_get_now(void) {
    struct timespec t;assert(!clock_gettime(CLOCK_MONOTONIC,&t));return t.tv_sec*1000.0+t.tv_nsec/1000000.0;
}
static void emscripten_thread_sleep(double ms) {
    struct timespec t={(time_t)(ms/1000),(long)(ms*1000000)%1000000000};nanosleep(&t,NULL);
}
#endif
#define XBOX_THREAD_LOCAL _Thread_local
#define QEMU_CLOCK_REALTIME 0
#define qatomic_read(p) __atomic_load_n((p), __ATOMIC_ACQUIRE)
#define qatomic_fetch_add(p,v) __sync_fetch_and_add((p),(v))
typedef uint64_t hwaddr;
typedef struct {
    pthread_mutex_t lock;
    pthread_cond_t cond;
    volatile int mmio_waiters;
    uint32_t mmio_completed;
    bool exiting;
} MCPXAPUState;
static bool s_apu_lock_profile=true;
/* PROFILE */
static int in_frame, writes, frames, started, waits, signals;
static MCPXAPUState *simulated_flood;
static unsigned simulated_waits;
static void qemu_mutex_lock(pthread_mutex_t *m) { assert(!pthread_mutex_lock(m)); }
static void qemu_mutex_unlock(pthread_mutex_t *m) { assert(!pthread_mutex_unlock(m)); }
static void qemu_cond_signal(pthread_cond_t *c) { __atomic_fetch_add(&signals,1,__ATOMIC_RELAXED);assert(!pthread_cond_signal(c)); }
static void qemu_cond_wait(pthread_cond_t *c,pthread_mutex_t *m) {
    __atomic_fetch_add(&waits,1,__ATOMIC_RELAXED);
    if(simulated_flood) {
        /* New writers replace each completed writer, so the pending count
         * never drains. The mixer must regain its frame after its cohort. */
        assert(++simulated_waits<=3);
        if(simulated_waits>1)simulated_flood->mmio_completed++; /* first wake is spurious */
        return;
    }
    assert(!pthread_cond_wait(c,m));
}
static int64_t qemu_clock_get_us(int type) { (void)type; return (int64_t)(emscripten_get_now()*1000.0); }
static unsigned GetCurrentThreadId(void) { return 1; }
static void mcpx_apu_dispatch_mmio(MCPXAPUState *d,hwaddr a,uint64_t v,unsigned n,bool write) {
    (void)d;(void)a;(void)v;(void)n;
    assert(write && !in_frame);
    writes++;
}
/* HANDOFF */
/* WRITE */
static void *mixer(void *arg) {
    MCPXAPUState *d=arg;
    qemu_mutex_lock(&d->lock);
    in_frame=1;
    __atomic_store_n(&started,1,__ATOMIC_RELEASE);
    /* Keep ownership until both writers have announced themselves, just
     * as a continuously catching-up audio thread owns the mutex. */
    while(qatomic_fetch_add(&d->mmio_waiters,0)<2) emscripten_thread_sleep(0.1);
    in_frame=0;
    while(!qatomic_read(&d->exiting)) {
        mcpx_apu_service_mmio_waiters(d);
        if(qatomic_read(&d->exiting)) break;
        in_frame=1;
        for(volatile int i=0;i<100;i++) {} /* a non-preemptible voice frame */
        __atomic_fetch_add(&frames,1,__ATOMIC_RELEASE);
        in_frame=0;
    }
    qemu_mutex_unlock(&d->lock);
    return NULL;
}
static void *writer(void *arg) {
    MCPXAPUState *d=arg;
    for(unsigned i=0;i<5000;i++) {
        mcpx_apu_mmio_write(d,0x20000,i,4);
        if(i==2500) emscripten_thread_sleep(5);
    }
    return NULL;
}
int main(void) {
    MCPXAPUState d={0};
    pthread_mutexattr_t attr;assert(!pthread_mutexattr_init(&attr));
    assert(!pthread_mutexattr_settype(&attr,PTHREAD_MUTEX_RECURSIVE));
    assert(!pthread_mutex_init(&d.lock,&attr));assert(!pthread_cond_init(&d.cond,NULL));
    qemu_mutex_lock(&d.lock);mcpx_apu_service_mmio_waiters(&d);qemu_mutex_unlock(&d.lock);
    assert(!waits); /* no contention adds no sleep */
    d.mmio_waiters=2;d.mmio_completed=UINT32_MAX;simulated_flood=&d;
    qemu_mutex_lock(&d.lock);mcpx_apu_service_mmio_waiters(&d);qemu_mutex_unlock(&d.lock);
    assert(simulated_waits==3 && d.mmio_waiters==2 && d.mmio_completed==1);
    simulated_flood=NULL;d.mmio_waiters=1;d.mmio_completed=0;
    int old_signals=signals;mcpx_apu_mmio_write(&d,0x20000,0,4);
    assert(d.mmio_waiters==1 && d.mmio_completed==1 && signals==old_signals+1);
    d.mmio_waiters=0;d.mmio_completed=0;writes=0;
    pthread_t mix,a,b;
    assert(!pthread_create(&mix,NULL,mixer,&d));
    while(!__atomic_load_n(&started,__ATOMIC_ACQUIRE)) emscripten_thread_sleep(0.1);
    assert(!pthread_create(&a,NULL,writer,&d));assert(!pthread_create(&b,NULL,writer,&d));
    assert(!pthread_join(a,NULL));assert(!pthread_join(b,NULL));
    while(__atomic_load_n(&frames,__ATOMIC_ACQUIRE)<2) emscripten_thread_sleep(0.1);
    __atomic_store_n(&d.exiting,true,__ATOMIC_RELEASE);qemu_cond_signal(&d.cond);
    assert(!pthread_join(mix,NULL));
    assert(writes==10000 && d.mmio_completed==10000 && !d.mmio_waiters && waits>2 && !in_frame);
    /* Shutdown does not park behind a pending writer. */
    int previous=waits;d.mmio_waiters=1;
    qemu_mutex_lock(&d.lock);mcpx_apu_service_mmio_waiters(&d);qemu_mutex_unlock(&d.lock);
    assert(waits==previous);
    pthread_cond_destroy(&d.cond);pthread_mutex_destroy(&d.lock);pthread_mutexattr_destroy(&attr);
    puts("PASS APU handoff: bounded continuous arrivals, spurious wakes, per-write notifications, completion wrap, 10000 contended writes, frame-boundary exclusion, continued mixing and shutdown");
}
'''.replace('/* PROFILE */',source[source.index('/* APU schedule profile:'):source.index('/* Forward declarations')]).replace('/* HANDOFF */', function('static void mcpx_apu_service_mmio_waiters(')).replace('/* WRITE */', function('void mcpx_apu_mmio_write('))
out=args.build_dir.resolve()
out.mkdir(parents=True,exist_ok=True)
(out/'test.c').write_text(harness,encoding='utf-8')
if args.native:
    compiler=shutil.which('clang') or shutil.which('cc')
    if not compiler:parser.error('A native C compiler is required')
    output=out/'test'
    subprocess.run([compiler,str(out/'test.c'),'-O2','-g','-pthread','-fsanitize=address,undefined',
                    '-fno-omit-frame-pointer','-o',str(output)],check=True)
    subprocess.run([str(output)],check=True,timeout=60)
else:
    subprocess.run([shutil.which('emcc') or 'emcc',str(out/'test.c'),'-O2','-pthread',
                    '-sPTHREAD_POOL_SIZE=3','-sENVIRONMENT=node','-o',str(out/'test.js')],check=True)
    subprocess.run([shutil.which('node') or 'node',str(out/'test.js')],check=True,timeout=60)
