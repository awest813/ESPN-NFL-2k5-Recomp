/* src/platform/web/recomp_web_dev.h: APU-window accesses reach the APU, the
 * DSP memory windows and everything else stay memory, and with no APU the
 * window is plain memory. Builds natively or with emcc (run under node). */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static uint8_t fake_mem[1u << 20];
/* Guest address -> fake memory, low 20 bits (enough for distinct test addresses). */
#define XBOX_PTR(a) ((uintptr_t)fake_mem + ((uint32_t)(a) & 0xFFFFFu))
#include "recomp_web_dev.h"

static int apu_on = 1, reads, writes;
static uint32_t last_off, last_val, last_size, reg_value = 0x12345678u;

int xbox_apu_guest_read(uint32_t offset, unsigned size, uint32_t *value)
{
    if (!apu_on) return 0;
    reads++; last_off = offset; last_size = size; *value = reg_value; return 1;
}
int xbox_apu_guest_write(uint32_t offset, unsigned size, uint32_t value)
{
    if (!apu_on) return 0;
    writes++; last_off = offset; last_size = size; last_val = value; return 1;
}

static int failures;
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); failures++; } } while (0)

int main(void)
{
    /* Register reads and writes go to the APU with offset and size. */
    CHECK(RECOMP_DEV_R_MEM32(0xFE820010u) == 0x12345678u && reads == 1 && last_off == 0x20010u && last_size == 4);
    CHECK(RECOMP_DEV_W_MEM32(0xFE8202F8u, 0xABCDu) == 0xABCDu && writes == 1 && last_off == 0x202F8u && last_val == 0xABCDu);
    RECOMP_DEV_W_MEM8(0xFE801000u, 0x1FF);        /* truncated as a byte store would be */
    CHECK(writes == 2 && last_size == 1 && last_val == 0xFFu);
    CHECK(RECOMP_DEV_R_MEM16(0xFE800002u) == 0x5678u && last_size == 2);
    CHECK(RECOMP_DEV_R_SMEM8(0xFE800000u) == 0x78);
    /* The window's last byte routes; the next address does not. */
    reads = 0;
    (void)RECOMP_DEV_R_MEM8(0xFE87FFFFu);
    CHECK(reads == 1);
    (void)RECOMP_DEV_R_MEM32(0xFE880000u);
    CHECK(reads == 1);
    /* DSP memory windows stay memory; their trapped last pages route. */
    writes = 0;
    RECOMP_DEV_W_MEM32(0xFE830000u, 0x11111111u);
    RECOMP_DEV_W_MEM32(0xFE83EFFCu, 0x22222222u);
    RECOMP_DEV_W_MEM32(0xFE850000u, 0x33333333u);
    CHECK(writes == 0);
    CHECK(RECOMP_DEV_R_MEM32(0xFE830000u) == 0x11111111u && RECOMP_DEV_R_MEM32(0xFE83EFFCu) == 0x22222222u);
    RECOMP_DEV_W_MEM32(0xFE83F000u, 1);
    RECOMP_DEV_W_MEM32(0xFE85F000u, 1);
    CHECK(writes == 2);
    /* Ordinary memory never reaches the APU. */
    reads = writes = 0;
    RECOMP_DEV_W_MEM32(0x00012340u, 0xCAFEF00Du);
    CHECK(RECOMP_DEV_R_MEM32(0x00012340u) == 0xCAFEF00Du && reads == 0 && writes == 0);
    /* 64-bit and floating-point accesses go by 32-bit halves. */
    writes = 0;
    RECOMP_DEV_W_MEMD(0xFE800100u, 1.0);
    CHECK(writes == 2 && last_off == 0x104u);
    float f = 2.5f; uint32_t bits; memcpy(&bits, &f, 4);
    reg_value = bits;
    CHECK(RECOMP_DEV_R_MEMF(0xFE800200u) == 2.5f);
    /* No APU: the window is plain memory, as when it is not trapped natively. */
    apu_on = 0; reads = writes = 0;
    RECOMP_DEV_W_MEM32(0xFE820010u, 0x55AA55AAu);
    CHECK(RECOMP_DEV_R_MEM32(0xFE820010u) == 0x55AA55AAu && reads == 0 && writes == 0);

    if (failures) { printf("%d failure(s)\n", failures); return 1; }
    printf("recomp_web_dev: all checks passed\n");
    return 0;
}
