"""Check optional APU clock waits, condition notifications and unlock-to-wait races."""
import argparse
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--native', action='store_true')
parser.add_argument('--build-dir', type=Path, default=root / 'build-web-tests/apu-audio-wake')
args = parser.parse_args()
out = args.build_dir.resolve()
out.mkdir(parents=True, exist_ok=True)
apu = root / 'external/xboxrecomp/src/apu'
audio = (apu / 'apu_web_audio.c').read_text(encoding='utf-8')
shim = (apu / 'apu_shim.h').read_text(encoding='utf-8')
base = (apu / '../nv2a/qemu_shim.h').read_text(encoding='utf-8')


def function(source, signature):
    a = source.index(signature)
    return source[a:source.index('\n}', a) + 2]


code = r'''
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "platform/xbox_winnt.h"
#include "platform/win32_compat.h"
#ifdef __EMSCRIPTEN__
#include <emscripten/threading.h>
#else
#include <linux/futex.h>
#include <sys/syscall.h>
#include <unistd.h>
static int emscripten_futex_wait(void *p,uint32_t value,double ms) {
    struct timespec t={(time_t)(ms/1000),(long)(ms*1000000)%1000000000};
    int r=syscall(SYS_futex,p,FUTEX_WAIT_PRIVATE,value,&t,NULL,0);
    return r<0?-errno:r;
}
static int emscripten_futex_wake(void *p,int count) {
    return syscall(SYS_futex,p,FUTEX_WAKE_PRIVATE,count,NULL,NULL,0);
}
#endif
typedef struct {CRITICAL_SECTION cs;} QemuMutex;
typedef struct {CONDITION_VARIABLE cv;} QemuCond;
static unsigned signals,broadcasts,fallbacks,waits;
static int race;
void web_audio_notify(void);
static void checked_unlock(PCRITICAL_SECTION cs) {
    LeaveCriticalSection(cs);
    if(race)web_audio_notify(); /* signal exactly at the unlock boundary */
}
#define LeaveCriticalSection checked_unlock
static void checked_signal(PCONDITION_VARIABLE cv){signals++;WakeConditionVariable(cv);}
static void checked_broadcast(PCONDITION_VARIABLE cv){broadcasts++;WakeAllConditionVariable(cv);}
#define WakeConditionVariable checked_signal
#define WakeAllConditionVariable checked_broadcast
/* QEMU_BASE */
#undef LeaveCriticalSection
#undef WakeConditionVariable
#undef WakeAllConditionVariable
#define RING_FRAMES 16
/* RING_TYPE */
static WebAudioRing ring,*s_ring;
static int s_clock_wake;
#define MAIN_THREAD_EM_ASM(...) ((void)0)
/* BACKEND */
#undef MAIN_THREAD_EM_ASM
static QemuMutex mutex;
static QemuCond condition;
static _Atomic int entered;
static int predicate,last_wait;
static int checked_wait(void *word,uint32_t expected,double ms) {
    assert(!mutex.cs.RecursionCount);waits++;
    atomic_store(&entered,1);
    last_wait=emscripten_futex_wait(word,expected,ms);return last_wait;
}
static BOOL checked_fallback(PCONDITION_VARIABLE cv,PCRITICAL_SECTION cs,DWORD ms) {
    fallbacks++;return SleepConditionVariableCS(cv,cs,ms);
}
#define emscripten_futex_wait checked_wait
/* CLOCK_WAIT */
#undef emscripten_futex_wait
/* SIGNAL_WRAPPERS */
#define qemu_cond_signal apu_cond_signal
#define qemu_cond_broadcast apu_cond_broadcast
#define SleepConditionVariableCS checked_fallback
/* TIMED_WAIT */
#undef SleepConditionVariableCS
static void *notify_worker(void *kind_ptr) {
    intptr_t kind=(intptr_t)kind_ptr;
    while(!atomic_load(&entered))sched_yield();
    qemu_mutex_lock(&mutex);
    if(kind==2) { /* worklet pulse: permitted spurious condition wake */
        atomic_fetch_add(&ring.wake,1);emscripten_futex_wake(&ring.wake,INT_MAX);
    } else {
        predicate=1;
        if(kind)qemu_cond_broadcast(&condition);else qemu_cond_signal(&condition);
    }
    qemu_mutex_unlock(&mutex);return NULL;
}
static void *infinite_worker(void *unused) {
    (void)unused;qemu_mutex_lock(&mutex);atomic_store(&entered,1);
    while(!predicate)qemu_cond_wait(&condition,&mutex);
    qemu_mutex_unlock(&mutex);return NULL;
}
int main(void) {
    qemu_mutex_init(&mutex);qemu_cond_init(&condition);qemu_mutex_lock(&mutex);
    s_clock_wake=0;s_ring=&ring;atomic_store(&ring.wake,1);
    assert(!web_audio_clock_word());web_audio_notify();assert(ring.wake==1);
    qemu_cond_timedwait(&condition,&mutex,1);assert(fallbacks==1 && !waits);
    s_clock_wake=1;s_ring=NULL;
    qemu_cond_timedwait(&condition,&mutex,1);assert(fallbacks==2 && !waits);
    s_ring=&ring;atomic_store(&ring.wake,0);web_audio_notify();assert(!ring.wake);
    qemu_cond_timedwait(&condition,&mutex,1);assert(fallbacks==3 && !waits);
    atomic_store(&ring.wake,1);
    assert(!apu_audio_clock_timedwait(&mutex,0));assert(!apu_audio_clock_timedwait(&mutex,-1));
    qemu_cond_timedwait(&condition,&mutex,0);assert(fallbacks==4);
    atomic_store(&ring.wake,INT_MAX);web_audio_notify();assert((uint32_t)ring.wake==0x80000000u);
    atomic_store(&ring.wake,-1);web_audio_notify();assert(!ring.wake && !web_audio_clock_word());
    atomic_store(&ring.wake,1);
    race=1;qemu_cond_timedwait(&condition,&mutex,1000);race=0;
    assert(last_wait==-EWOULDBLOCK && waits==1 && mutex.cs.RecursionCount==1);
    /* Both ordinary signals and shutdown broadcasts wake the clock wait even
     * when the audio processor produces no pulses. */
    for(int kind=0;kind<3;kind++) {
        atomic_store(&entered,0);predicate=0;pthread_t thread;
        assert(!pthread_create(&thread,NULL,notify_worker,(void *)(intptr_t)kind));
        qemu_cond_timedwait(&condition,&mutex,1000);
        assert(mutex.cs.RecursionCount==1 && predicate==(kind!=2));
        assert(last_wait==0 || last_wait==-EWOULDBLOCK);
        qemu_mutex_unlock(&mutex);assert(!pthread_join(thread,NULL));qemu_mutex_lock(&mutex);
    }
    atomic_store(&entered,0);predicate=0;pthread_t infinite;
    assert(!pthread_create(&infinite,NULL,infinite_worker,NULL));qemu_mutex_unlock(&mutex);
    while(!atomic_load(&entered))sched_yield();qemu_mutex_lock(&mutex);
    predicate=1;qemu_cond_broadcast(&condition);qemu_mutex_unlock(&mutex);
    assert(!pthread_join(infinite,NULL));qemu_mutex_lock(&mutex);
    assert(signals==1 && broadcasts==2 && fallbacks==4 && waits==4);
    qemu_cond_timedwait(&condition,&mutex,1);assert(last_wait==-ETIMEDOUT);
    /* Closing never frees the ring; saved addresses remain valid. */
    volatile int32_t *saved=web_audio_clock_word();assert(saved);web_audio_close();
    assert(!web_audio_clock_word());web_audio_notify();assert(*saved==ring.wake);
    qemu_mutex_unlock(&mutex);qemu_mutex_destroy(&mutex);
    puts("PASS APU clock wait: disabled/startup fallback, snapshot race, wrap, condition signal/broadcast, suspended-clock shutdown, spurious pulses and timeout");
}
'''
ring_start = audio.index('typedef struct {')
ring_end = audio.index('} WebAudioRing;', ring_start) + len('} WebAudioRing;')
base_start = base.index('static inline void qemu_mutex_init(')
base_end = base.index('\n/* ===', base_start)
timed = function(shim, 'static inline void qemu_cond_timedwait(')
# Compile the same Web branch in the native sanitizer harness too.
timed = timed.replace('#ifdef __EMSCRIPTEN__\n', '').replace('#endif\n', '')
for marker, value in {
    'QEMU_BASE': base[base_start:base_end],
    'RING_TYPE': audio[ring_start:ring_end],
    'BACKEND': '\n'.join(function(audio, f) for f in
                         ['volatile int32_t *web_audio_clock_word(', 'void web_audio_notify(', 'void web_audio_close(']),
    'CLOCK_WAIT': function(shim, 'static inline int apu_audio_clock_timedwait('),
    'SIGNAL_WRAPPERS': '\n'.join(function(shim, f) for f in
                                 ['static inline void apu_cond_signal(', 'static inline void apu_cond_broadcast(']),
    'TIMED_WAIT': timed,
}.items():
    code = code.replace('/* ' + marker + ' */', value)
(out / 'test.c').write_bytes(code.encode())
includes = ['-I', str(root / 'external/xboxrecomp/src')]
platform = str(root / 'external/xboxrecomp/src/platform/win32_compat.c')
if args.native:
    compiler = shutil.which('clang') or shutil.which('cc')
    if not compiler: parser.error('Native compiler required')
    binary = out / 'test'
    command = [compiler, str(out / 'test.c'), platform, *includes, '-O2', '-g', '-pthread',
               '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-ffunction-sections',
               '-fdata-sections', '-Wl,--gc-sections', '-o', str(binary), '-lm']
    runner = [str(binary)]
else:
    compiler, node = shutil.which('emcc'), shutil.which('node')
    if not compiler or not node: parser.error('Emscripten and Node required')
    binary = out / 'test.js'
    command = [compiler, str(out / 'test.c'), platform, *includes, '-O2', '-pthread',
               '-sPTHREAD_POOL_SIZE=2', '-sINITIAL_MEMORY=128MB', '-sENVIRONMENT=node', '-o', str(binary)]
    runner = [node, str(binary)]
subprocess.run(command, check=True)
subprocess.run(runner, check=True, timeout=60)
