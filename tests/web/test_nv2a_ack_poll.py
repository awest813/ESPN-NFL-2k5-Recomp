"""Check completion snapshots, register acknowledgements and the generated hooks."""
import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess


root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--native", action="store_true")
parser.add_argument("--build-dir", type=Path, default=root / "build-web-tests/nv2a-ack-poll")
args = parser.parse_args()
out = args.build_dir.resolve()
out.mkdir(parents=True, exist_ok=True)
runtime = (root / "external/xboxrecomp/src/kernel/xbox_memory_layout.c").read_text(encoding="utf-8")


def extract(first, last):
    start = runtime.index(first)
    return runtime[start:runtime.index(last, start)]


live = extract("static const struct { uint32_t offset; uint32_t busy_mask; } NV2A_ACK", "/*\n * PFIFO channel DMA pointers.")
live += "\n".join(line for line in runtime.splitlines() if line.startswith("#define NV2A_USER_DMA_"))
live += "\n" + extract("#define XBOX_MAX_FENCE_MIRRORS", "int xbox_Nv2aMirrorFence(")
live += extract("#define XBOX_MAX_COUNTER_MIRRORS", "/* ---- asynchronous command")
live += extract("typedef struct {\n    uint32_t put;", "static int s_async")
live += "\nstatic PbSnap s_snap_done;\nstatic int s_snap_done_valid;\n"
for name in ("void web_fence_publish", "void counter_mirrors_tick", "void fence_mirrors_tick",
             "void pb_mirrors_tick", "void nv2a_ack_registers_tick"):
    live += "\n" + extract("static " + name + "(", "\n}") + "\n}\n"

harness = r"""
#include <assert.h>
#include <limits.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#ifndef __EMSCRIPTEN__
#define __EMSCRIPTEN__ 1
#endif
#define XBOX_NV2A_BASE 0xFD000000u

static uint32_t memory[64];
static void *g_nv2a_memory;
static uintptr_t g_memory_offset;
static int async_on, behind;
static int s_snap_lock, lock_held;
static unsigned locks, wakes;
static int pb_async_on(void) { return async_on; }
static int pb_async_behind(void) { return behind; }
static int fence_readable(uint32_t addr, uint32_t size) {
    return addr >= 0x1000 && addr <= 0x1100 - size;
}
static void AcquireSRWLockShared(int *lock) {
    assert(lock == &s_snap_lock && !lock_held);
    locks++;
    lock_held = 1;
}
static void ReleaseSRWLockShared(int *lock) {
    assert(lock == &s_snap_lock && lock_held);
    lock_held = 0;
}
static int emscripten_futex_wake(void *address, int count) {
    assert(address && count == INT_MAX);
    return (int)++wakes;
}
/* LIVE */

static void mirrors(void) {
    g_memory_offset = (uintptr_t)memory - 0x1000;
    async_on = 1;
    pb_mirrors_tick();
    assert(!locks);
    g_fence_mirror_count = g_counter_mirror_count = 1;
    g_fence_mirrors[0].device_ptr_va = 0x1000;
    g_fence_mirrors[0].put_off = 0;
    g_fence_mirrors[0].get_ptr_off = 4;
    g_counter_mirrors[0].device_ptr_va = 0x1000;
    g_counter_mirrors[0].src_off = 8;
    g_counter_mirrors[0].dst_off = 12;
    memory[0] = 0x1020;
    memory[8] = 103;
    memory[9] = 0x1010;
    memory[10] = 12;
    memory[4] = 30;
    memory[11] = 8;

    pb_mirrors_tick(); /* queued PUT/counter have not completed */
    assert(locks == 1 && memory[4] == 30 && memory[11] == 8);
    s_snap_done = (PbSnap){.fput = {40}, .cnt = {9}};
    s_snap_done_valid = 1;
    pb_mirrors_tick();
    assert(locks == 2 && wakes == 1 && memory[4] == 40 && memory[11] == 9);
    pb_mirrors_tick();
    assert(locks == 3 && wakes == 1);
    web_fence_publish(memory + 4, 42);
    pb_mirrors_tick(); /* the executor's semaphore release remains visible */
    assert(locks == 4 && wakes == 2 && memory[4] == 42 && memory[11] == 9);

    memory[9] = 0x1014; /* follow the guest's pointer again on every pass */
    pb_mirrors_tick();
    assert(memory[4] == 42 && memory[5] == 40 && memory[11] == 9);
    memory[9] = 0;
    pb_mirrors_tick();
    assert(locks == 6 && wakes == 3 && memory[5] == 40);
    memory[9] = 0x1014;

    async_on = 0;
    pb_mirrors_tick();
    assert(locks == 6 && wakes == 3 && memory[5] == 103 && memory[11] == 12);
    memory[0] = 0;
    pb_mirrors_tick();
    assert(locks == 6 && memory[5] == 103 && memory[11] == 12);
}

static void registers(void) {
    uint32_t *regs = calloc(NV2A_USER_DMA_GET / 4 + 1, sizeof *regs);
    assert(regs);
    uint32_t *pmc = regs + NV2A_PMC_INTR_0_OFS / 4;
    uint32_t *pcrtc = regs + NV2A_PCRTC_INTR_0_OFS / 4;
    uint32_t *get = regs + NV2A_USER_DMA_GET / 4;
    uint32_t *put = regs + NV2A_USER_DMA_PUT / 4;
    *pmc = NV2A_PMC_INTR_PCRTC | 0x80;
    assert(!xbox_Nv2aAckVblank(XBOX_NV2A_BASE, 1));
    g_nv2a_memory = regs;
    assert(!xbox_Nv2aAckVblank(XBOX_NV2A_BASE + 4, 1));
    assert(!xbox_Nv2aAckVblank(XBOX_NV2A_BASE, 2));
    assert(*pmc == (NV2A_PMC_INTR_PCRTC | 0x80) && !*pcrtc);
    assert(xbox_Nv2aAckVblank(XBOX_NV2A_BASE, 1));
    assert(*pmc == 0x80 && !*pcrtc); /* synthetic vblank only raises PMC */
    *pmc |= NV2A_PMC_INTR_PCRTC;
    *pcrtc = 3;
    assert(xbox_Nv2aAckVblank(XBOX_NV2A_BASE, 1));
    assert(*pcrtc == 2 && *pmc == (NV2A_PMC_INTR_PCRTC | 0x80));
    *pcrtc = 0;
    *pmc = NV2A_PMC_INTR_PCRTC | 0x80;
    *put = 17;
    nv2a_ack_registers_tick(regs, 1);
    assert(*pmc == NV2A_PMC_INTR_PCRTC && !*get);
    for (size_t i = 0; i < sizeof NV2A_IDLE / sizeof NV2A_IDLE[0]; i++)
        assert(regs[NV2A_IDLE[i].offset / 4] & NV2A_IDLE[i].idle_mask);
    *pcrtc = 1;
    regs[NV2A_ACK[0].offset / 4] = NV2A_ACK[0].busy_mask | 1;
    behind = 1;
    nv2a_ack_registers_tick(regs, 1);
    assert(!*pmc && !*pcrtc && !*get);
    assert(regs[NV2A_ACK[0].offset / 4] == 1);
    for (size_t i = 0; i < sizeof NV2A_IDLE / sizeof NV2A_IDLE[0]; i++)
        assert(!(regs[NV2A_IDLE[i].offset / 4] & NV2A_IDLE[i].idle_mask));
    behind = 0;
    nv2a_ack_registers_tick(regs, 0);
    assert(*get == *put);
    g_nv2a_memory = NULL;
    free(regs);
}

int main(void) {
    mirrors();
    registers();
    puts("PASS NV2A vblank acknowledgement, register polling and shared completions");
}
"""
source = out / "test.c"
source.write_bytes(harness.replace("/* LIVE */", live).encode("utf-8"))

spec = importlib.util.spec_from_file_location("ack_gen_patches", root / "tools/apply-gen-patches.py")
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)
patcher.PATCHES = [patch for patch in patcher.PATCHES if patch[0].startswith("NV2A_VBLANK_ACK_")]
assert len(patcher.PATCHES) == 2
generated = out / "generated"
generated.mkdir(exist_ok=True)
patcher.GEN = str(generated)
chunk = generated / "recomp_0029.c"
chunk.write_bytes("".join(f"void {name}(void)\r\n{{\r\n    {anchor}\r\n}}\r\n"
                          for _, name, anchor, _, _ in patcher.PATCHES).encode())
assert patcher.main() == 0
applied = chunk.read_bytes()
assert patcher.main() == 0 and chunk.read_bytes() == applied
checked_in = (root / "src/recomp/gen/recomp_0029.c").read_text(encoding="utf-8")
for patch_id, _, anchor, _, code in patcher.PATCHES:
    assert applied.count(patcher.marker(patch_id).encode()) == 1
    assert checked_in.count(patcher.marker(patch_id)) == 1 and code.strip() in checked_in
    assert b"\r\n    " + anchor.encode() + b"\r\n" not in applied

if args.native:
    compiler = shutil.which("cc") or shutil.which("clang") or "cc"
    binary = out / ("ack_poll.exe" if os.name == "nt" else "ack_poll")
    flags = ["-fsanitize=address,undefined"]
    command = [str(binary)]
else:
    compiler = shutil.which("emcc") or "emcc"
    binary = out / "ack_poll.js"
    flags = ["-fsanitize=undefined", "-sENVIRONMENT=node"]
    command = [shutil.which("node") or "node", str(binary)]
subprocess.run([compiler, "-O2", *flags, "-fno-sanitize-recover=all", str(source), "-o", str(binary)], check=True)
subprocess.run(command, check=True, timeout=60)
