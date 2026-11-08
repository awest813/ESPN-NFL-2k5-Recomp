"""Check production device clocks with large QPC values and rollover boundaries."""
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]

def function(path, name):
    text = (root / path).read_text(encoding='utf-8')
    start = text.index('static inline int64_t ' + name + '(')
    end = text.index('\n}', start) + 2
    return text[start:end]

harness = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
typedef struct { int64_t QuadPart; } LARGE_INTEGER;
static int64_t counter, frequency;
static int QueryPerformanceFrequency(LARGE_INTEGER *p) { p->QuadPart = frequency; return 1; }
static int QueryPerformanceCounter(LARGE_INTEGER *p) { p->QuadPart = counter; return 1; }
/* CLOCKS */
static void check(int64_t seconds, int64_t remainder) {
    counter = seconds * frequency + remainder;
    assert(qemu_clock_get_ns(0) == seconds * 1000000000LL + remainder * 1000000000LL / frequency);
    assert(qemu_clock_get_us(0) == seconds * 1000000LL + remainder * 1000000LL / frequency);
    assert(qemu_clock_get_ms(0) == qemu_clock_get_us(0) / 1000);
}
int main(void) {
    const int64_t frequencies[] = {1000000000LL, 10000000LL, 3579545LL};
    const int64_t seconds[] = {0, 9, 18, 18446, 86400, 1794100000LL};
    for (unsigned f = 0; f < sizeof frequencies / sizeof *frequencies; ++f) {
        frequency = frequencies[f];
        for (unsigned s = 0; s < sizeof seconds / sizeof *seconds; ++s) {
            check(seconds[s], 0);
            check(seconds[s], 1);
            check(seconds[s], frequency / 2);
            check(seconds[s], frequency - 1);
        }
    }
    frequency = 1000000000LL;
    /* Cross the old ns multiplication's signed-overflow boundary. */
    counter = INT64_MAX / 1000000000LL - 1000000LL;
    int64_t last = qemu_clock_get_ns(0);
    for (unsigned i = 0; i < 10000; ++i) {
        counter += 1000;
        int64_t now = qemu_clock_get_ns(0);
        assert(now - last == 1000); last = now;
    }
    /* XGSCNT exposes the ns clock in 100 ns units, wrapping at 32 bits. */
    counter = 1794100000000000000LL;
    uint32_t tick = (uint32_t)(qemu_clock_get_ns(0) / 100);
    counter += 1000000;
    assert((uint32_t)((uint32_t)(qemu_clock_get_ns(0) / 100) - tick) == 10000u);
    counter = ((int64_t)UINT32_MAX - 10) * 100;
    tick = (uint32_t)(qemu_clock_get_ns(0) / 100);
    counter += 2000;
    assert((uint32_t)((uint32_t)(qemu_clock_get_ns(0) / 100) - tick) == 20u);
    puts("PASS QEMU device clocks: epoch QPC, 3 frequencies, ns overflow boundary and 32-bit APU timer wrap");
}
'''.replace('/* CLOCKS */', '\n'.join([
    function('external/xboxrecomp/src/nv2a/qemu_shim.h', 'qemu_clock_get_ns'),
    function('external/xboxrecomp/src/apu/apu_shim.h', 'qemu_clock_get_us'),
    function('external/xboxrecomp/src/apu/apu_shim.h', 'qemu_clock_get_ms'),
]))
out = root / 'build-web-tests/qemu-clock'
out.mkdir(parents=True, exist_ok=True)
(out / 'test.c').write_text(harness, encoding='utf-8')
subprocess.run([shutil.which('emcc') or 'emcc', str(out / 'test.c'), '-O2', '-fsanitize=undefined', '-fno-sanitize-recover=undefined', '-sENVIRONMENT=node', '-o', str(out / 'test.js')], check=True)
subprocess.run([shutil.which('node') or 'node', str(out / 'test.js')], check=True)
