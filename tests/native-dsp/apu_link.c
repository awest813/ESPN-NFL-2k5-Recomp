#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stddef.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include "apu_state.h"

bool apu_hook_handle_mmio(void *context, uintptr_t address, uint32_t guest_address, int write);
extern MCPXAPUState *g_apu_state;

/* The probe never starts the voice processor. Give its linked objects the
 * guest-memory and logging functions normally supplied by the game runtime. */
ptrdiff_t xbox_GetMemoryOffset(void) { return 0; }
uint32_t xbox_ContiguousAllocatedBytes(void) { return 0; }
int xbox_verbose(void) { return 0; }
__declspec(thread) uint32_t g_esp;

int main(void)
{
    /* Use an unmapped register that reads as zero, with no audio thread or
     * host MMIO fault. Compare it with every possible immediate byte. */
    static MCPXAPUState apu;
    const uint32_t guest_address = 0xFE840000u;
    const DWORD parity_flag = 0x4;
    uint8_t opcode[] = {0x80, 0x38, 0};  /* cmp byte ptr [rax], imm8 */
    g_apu_state = &apu;
    for (unsigned immediate = 0; immediate < 256; immediate++) {
        CONTEXT ctx = {0};
        unsigned result = (0u - immediate) & 0xffu;
        unsigned ones = 0;
        for (unsigned bits = result; bits; bits >>= 1)
            ones += bits & 1u;
        opcode[2] = (uint8_t)immediate;
        ctx.Rip = (uintptr_t)opcode;
        if (!apu_hook_handle_mmio(&ctx, guest_address, guest_address, 0) ||
            ctx.Rip != (uintptr_t)(opcode + sizeof opcode) ||
            !!(ctx.EFlags & parity_flag) != !(ones & 1u)) {
            fprintf(stderr, "APU MMIO compare failed for result 0x%02X\n", result);
            return 1;
        }
    }
    puts("PASS Windows APU runtime link and MMIO parity for all 256 byte results");
    return 0;
}
