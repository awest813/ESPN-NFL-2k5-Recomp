"""Exercise the production handle registry with 32-bit WebAssembly pointers."""
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
source = (root / 'external/xboxrecomp/src/platform/win32_compat.c').read_text(encoding='utf-8')
registry = source[source.index('static pthread_mutex_t s_reg_lock'):source.index('static w32_object *obj_alloc')]
harness = r'''
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <assert.h>
#include <pthread.h>
/* REGISTRY */
int main(void) {
    _Static_assert(sizeof(uintptr_t) == 4, "test requires wasm32");
    enum { N = 10000, B = 1024 };
    unsigned buckets[B] = {0}, occupied = 0;
    for (unsigned i = 0; i < N; ++i) {
        uintptr_t key = 0x10000u + i * 64u;
        buckets[reg_hash(key) & (B - 1)]++;
        reg_add((void *)key);
    }
    for (unsigned i = 0; i < B; ++i) occupied += buckets[i] != 0;
    assert(occupied > B * 9 / 10);
    assert(s_reg_live == N);
    for (unsigned i = 0; i < N; ++i) {
        uintptr_t key = 0x10000u + i * 64u;
        assert(reg_contains((void *)key));
        assert(!reg_contains((void *)(key + 4)));
        if (i % 2 == 0) reg_remove((void *)key);
    }
    assert(s_reg_live == N / 2);
    for (unsigned i = 0; i < N; ++i)
        assert(reg_contains((void *)(uintptr_t)(0x10000u + i * 64u)) == (i % 2 != 0));
    for (unsigned i = 0; i < N; i += 2)
        reg_add((void *)(uintptr_t)(0x10000u + i * 64u));
    for (unsigned i = 0; i < N; ++i) {
        void *key = (void *)(uintptr_t)(0x10000u + i * 64u);
        assert(reg_contains(key));
        reg_remove(key);
    }
    assert(!s_reg_live && !reg_contains(NULL) && !reg_contains((void *)1));
    free(s_reg);
    puts("PASS wasm32 handle hashing, 10000 handles, growth, invalid lookups and tombstone reuse");
}
'''.replace('/* REGISTRY */', registry)
out = root / 'build-web-tests/handle-registry'
out.mkdir(parents=True, exist_ok=True)
(out / 'test.c').write_text(harness, encoding='utf-8')
subprocess.run([shutil.which('emcc') or 'emcc', str(out / 'test.c'), '-O2', '-Werror=shift-count-overflow', '-sENVIRONMENT=node', '-o', str(out / 'test.js')], check=True)
subprocess.run([shutil.which('node') or 'node', str(out / 'test.js')], check=True)
