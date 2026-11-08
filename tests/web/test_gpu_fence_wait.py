"""Exercise browser GPU fence publication and waits with real Wasm pthreads."""
from pathlib import Path
import importlib.util
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
source = (root / 'external/xboxrecomp/src/kernel/xbox_memory_layout.c').read_text(encoding='utf-8')
start = source.index('static void web_fence_publish(')
end = source.index('\n#endif', start)
fences = source[start:end]
harness = r'''
#include <stdint.h>
#include <limits.h>
#include <assert.h>
#include <stdio.h>
#include <pthread.h>
#include <emscripten/threading.h>
static uint32_t memory[16];
static intptr_t g_memory_offset;
static int async_enabled = 1;
static int releases, reacquires;
static _Thread_local int guest_depth = 3;
static int pb_async_on(void) { return async_enabled; }
static int fence_readable(uint32_t va, uint32_t n) { return va >= 0x1000 && va <= 0x1040 - n; }
static int xbox_ggl_release_all(void) {
    int d = guest_depth; assert(d == 3); guest_depth = 0;
    __atomic_fetch_add(&releases, 1, __ATOMIC_RELAXED); return d;
}
static void xbox_ggl_reacquire(int d) {
    assert(guest_depth == 0 && d == 3); guest_depth = d;
    __atomic_fetch_add(&reacquires, 1, __ATOMIC_RELAXED);
}
/* FENCES */
static void *producer(void *arg) {
    emscripten_thread_sleep(5);
    /* A wake without completion must not release the fence waiter. */
    emscripten_futex_wake(memory, INT_MAX);
    emscripten_thread_sleep(5);
    web_fence_publish(memory, (uint32_t)(uintptr_t)arg);
    return NULL;
}
static void *consumer(void *arg) {
    assert(xbox_Nv2aWaitFence(0x1000, (uint32_t)(uintptr_t)arg));
    assert((int32_t)(__atomic_load_n(memory, __ATOMIC_ACQUIRE) - (uint32_t)(uintptr_t)arg) >= 0);
    assert(guest_depth == 3);
    return NULL;
}
static int producers_done;
static void *racing_producer(void *arg) {
    for (uint32_t i = 10000 + (uint32_t)(uintptr_t)arg; i <= 20000; i += 2)
        web_fence_publish(memory, i);
    __atomic_fetch_add(&producers_done, 1, __ATOMIC_RELEASE);
    return NULL;
}
int main(void) {
    g_memory_offset = (intptr_t)memory - 0x1000;
    memory[0] = 10;
    assert(xbox_Nv2aWaitFence(0x1000, 9));
    assert(releases == 0 && reacquires == 0);
    async_enabled = 0; assert(!xbox_Nv2aWaitFence(0x1000, 20)); async_enabled = 1;
    assert(!xbox_Nv2aWaitFence(0x1001, 20));
    assert(!xbox_Nv2aWaitFence(0xffc, 20));
    assert(releases == 0);
    pthread_t p;
    assert(!pthread_create(&p, NULL, producer, (void *)20));
    assert(xbox_Nv2aWaitFence(0x1000, 20));
    assert(__atomic_load_n(memory, __ATOMIC_ACQUIRE) == 20);
    assert(!pthread_join(p, NULL));
    assert(memory[0] == 20 && guest_depth == 3 && releases == 1 && reacquires == 1);
    web_fence_publish(memory, 19); assert(memory[0] == 20);
    web_fence_publish(memory, 50); web_fence_publish(memory, 22);
    assert(memory[0] == 50 && xbox_Nv2aWaitFence(0x1000, 49));
    assert(releases == 1); /* completion before wait */
    __atomic_store_n(memory, 0xfffffffeu, __ATOMIC_RELEASE);
    assert(!pthread_create(&p, NULL, producer, (void *)2));
    assert(xbox_Nv2aWaitFence(0x1000, 1));
    assert(!pthread_join(p, NULL));
    web_fence_publish(memory, 0xffffffffu); assert(memory[0] == 2);
    /* Both waiters must wake, including when publication races their sleep. */
    pthread_t a, b;
    assert(!pthread_create(&a, NULL, consumer, (void *)7));
    assert(!pthread_create(&b, NULL, consumer, (void *)7));
    emscripten_thread_sleep(5);
    web_fence_publish(memory, 9);
    assert(!pthread_join(a, NULL)); assert(!pthread_join(b, NULL));
    assert(guest_depth == 3 && releases == reacquires);
    for (uint32_t i = 10; i < 10000; ++i) {
        web_fence_publish(memory, i);
        web_fence_publish(memory, i - 5); /* an old completed-kick snapshot */
        assert(memory[0] == i && xbox_Nv2aWaitFence(0x1000, i));
    }
    assert(!pthread_create(&a, NULL, racing_producer, (void *)0));
    assert(!pthread_create(&b, NULL, racing_producer, (void *)1));
    uint32_t previous = 9999;
    while (__atomic_load_n(&producers_done, __ATOMIC_ACQUIRE) != 2) {
        uint32_t now = __atomic_load_n(memory, __ATOMIC_ACQUIRE);
        assert(now >= previous); previous = now;
        emscripten_thread_sleep(0.1);
    }
    assert(!pthread_join(a, NULL)); assert(!pthread_join(b, NULL));
    assert(memory[0] == 20000);
    puts("PASS Wasm GPU fences: notified waits, spurious wakes, multiple waiters, wrap, stale snapshots and guest-lock restoration");
}
'''.replace('/* FENCES */', fences)
out = root / 'build-web-tests/gpu-fence-wait'
out.mkdir(parents=True, exist_ok=True)
# Regeneration must restore the hook exactly once, without changing the
# original register cleanup or enabling this browser wait in native builds.
spec = importlib.util.spec_from_file_location('fence_gen_patches', root / 'tools/apply-gen-patches.py')
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)
patcher.PATCHES = [p for p in patcher.PATCHES if p[0] == 'WEB_GPU_FENCE_WAIT']
assert len(patcher.PATCHES) == 1
patcher.GEN = str(out / 'generated')
Path(patcher.GEN).mkdir(exist_ok=True)
fixture = Path(patcher.GEN) / 'recomp_0000.c'
fixture.write_text('void sub_004262F0(void)\n{\nloc_00426427: ;\nloc_00426431: ;\n}\n', encoding='utf-8')
assert patcher.main() == 0 and patcher.main() == 0
patched = fixture.read_text(encoding='utf-8')
assert patched.count('NFL2K5-GENPATCH:WEB_GPU_FENCE_WAIT') == 1
assert '#ifdef __EMSCRIPTEN__' in patched and 'goto loc_00426431;' in patched
(out / 'test.c').write_text(harness, encoding='utf-8')
subprocess.run([shutil.which('emcc') or 'emcc', str(out / 'test.c'), '-O2', '-pthread', '-sPTHREAD_POOL_SIZE=2', '-sENVIRONMENT=node', '-o', str(out / 'test.js')], check=True)
subprocess.run([shutil.which('node') or 'node', str(out / 'test.js')], check=True, timeout=60)
