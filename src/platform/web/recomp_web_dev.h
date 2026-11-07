/* Device accessors for generated code on hosts without MMIO faults.
 *
 * tools/gen-web-devices.py rewrites the guest's DirectSound functions so
 * every memory access goes through these: an address in the APU register
 * window goes to the emulated APU, exactly what the native fault handler
 * (xboxrecomp apu/apu_mmio_hook.c) does with a faulting access, and anything
 * else is the ordinary MEM* access. The window and its exemptions match the
 * native trap: the GP and EP DSP memory windows (0x30000..0x3EFFF and
 * 0x50000..0x5EFFF) stay plain memory. Before the APU exists (no
 * RECOMP_AC97_READY) the register window is plain memory too, as natively.
 *
 * Included only by the rewritten copies of generated files, after
 * recomp_funcs.h, so MEM* and XBOX_PTR are in scope. */
#ifndef RECOMP_WEB_DEV_H
#define RECOMP_WEB_DEV_H
#include <stdint.h>
#include <string.h>

/* xboxrecomp apu/apu_mmio_hook.c. Return 0 when no APU is routed. */
int xbox_apu_guest_read(uint32_t offset, unsigned size, uint32_t *value);
int xbox_apu_guest_write(uint32_t offset, unsigned size, uint32_t value);

#define RECOMP_DEV_APU_BASE 0xFE800000u

static inline int recomp_dev_apu(uint32_t a)
{
    uint32_t o = a - RECOMP_DEV_APU_BASE;
    return o < 0x80000u && o - 0x30000u >= 0xF000u && o - 0x50000u >= 0xF000u;
}

/* 1, 2 and 4 bytes: one register access. */
#define RECOMP_DEV_SCALAR(NAME, T, BYTES)                                        \
static inline T recomp_dev_r_##NAME(uint32_t a)                                  \
{                                                                                \
    uint32_t v;                                                                  \
    if (recomp_dev_apu(a) && xbox_apu_guest_read(a - RECOMP_DEV_APU_BASE, BYTES, &v)) \
        return (T)v;                                                             \
    return *(volatile T *)XBOX_PTR(a);                                           \
}                                                                                \
static inline T recomp_dev_w_##NAME(uint32_t a, T v)                             \
{                                                                                \
    if (!(recomp_dev_apu(a) && xbox_apu_guest_write(a - RECOMP_DEV_APU_BASE, BYTES, (uint32_t)v))) \
        *(volatile T *)XBOX_PTR(a) = v;                                          \
    return v;                                                                    \
}
RECOMP_DEV_SCALAR(u8,  uint8_t,  1)
RECOMP_DEV_SCALAR(u16, uint16_t, 2)
RECOMP_DEV_SCALAR(u32, uint32_t, 4)
RECOMP_DEV_SCALAR(s8,  int8_t,   1)
RECOMP_DEV_SCALAR(s16, int16_t,  2)
RECOMP_DEV_SCALAR(s32, int32_t,  4)
#undef RECOMP_DEV_SCALAR

/* 8 bytes and floats: by their 32-bit halves, as the registers are 32-bit. */
static inline uint64_t recomp_dev_r_u64(uint32_t a)
{
    return (uint64_t)recomp_dev_r_u32(a) | ((uint64_t)recomp_dev_r_u32(a + 4) << 32);
}
static inline uint64_t recomp_dev_w_u64(uint32_t a, uint64_t v)
{
    recomp_dev_w_u32(a, (uint32_t)v);
    recomp_dev_w_u32(a + 4, (uint32_t)(v >> 32));
    return v;
}
static inline float recomp_dev_r_f(uint32_t a)
{
    uint32_t bits = recomp_dev_r_u32(a); float f; memcpy(&f, &bits, 4); return f;
}
static inline float recomp_dev_w_f(uint32_t a, float f)
{
    uint32_t bits; memcpy(&bits, &f, 4); recomp_dev_w_u32(a, bits); return f;
}
static inline double recomp_dev_r_d(uint32_t a)
{
    uint64_t bits = recomp_dev_r_u64(a); double d; memcpy(&d, &bits, 8); return d;
}
static inline double recomp_dev_w_d(uint32_t a, double d)
{
    uint64_t bits; memcpy(&bits, &d, 8); recomp_dev_w_u64(a, bits); return d;
}

/* The names the rewrite emits: RECOMP_DEV_R_<macro>(addr) for a read and
 * RECOMP_DEV_W_<macro>(addr, value) for `<macro>(addr) = value`, which keeps
 * the assignment's value. */
#define RECOMP_DEV_R_MEM8(a)       recomp_dev_r_u8((uint32_t)(a))
#define RECOMP_DEV_R_MEM16(a)      recomp_dev_r_u16((uint32_t)(a))
#define RECOMP_DEV_R_MEM32(a)      recomp_dev_r_u32((uint32_t)(a))
#define RECOMP_DEV_R_MEM64(a)      recomp_dev_r_u64((uint32_t)(a))
#define RECOMP_DEV_R_SMEM8(a)      recomp_dev_r_s8((uint32_t)(a))
#define RECOMP_DEV_R_SMEM16(a)     recomp_dev_r_s16((uint32_t)(a))
#define RECOMP_DEV_R_SMEM32(a)     recomp_dev_r_s32((uint32_t)(a))
#define RECOMP_DEV_R_SMEM64(a)     ((int64_t)recomp_dev_r_u64((uint32_t)(a)))
#define RECOMP_DEV_R_MEMF(a)       recomp_dev_r_f((uint32_t)(a))
#define RECOMP_DEV_R_MEMD(a)       recomp_dev_r_d((uint32_t)(a))
#define RECOMP_DEV_W_MEM8(a, v)    recomp_dev_w_u8((uint32_t)(a), (uint8_t)(v))
#define RECOMP_DEV_W_MEM16(a, v)   recomp_dev_w_u16((uint32_t)(a), (uint16_t)(v))
#define RECOMP_DEV_W_MEM32(a, v)   recomp_dev_w_u32((uint32_t)(a), (uint32_t)(v))
#define RECOMP_DEV_W_MEM64(a, v)   recomp_dev_w_u64((uint32_t)(a), (uint64_t)(v))
#define RECOMP_DEV_W_SMEM8(a, v)   recomp_dev_w_s8((uint32_t)(a), (int8_t)(v))
#define RECOMP_DEV_W_SMEM16(a, v)  recomp_dev_w_s16((uint32_t)(a), (int16_t)(v))
#define RECOMP_DEV_W_SMEM32(a, v)  recomp_dev_w_s32((uint32_t)(a), (int32_t)(v))
#define RECOMP_DEV_W_SMEM64(a, v)  ((int64_t)recomp_dev_w_u64((uint32_t)(a), (uint64_t)(int64_t)(v)))
#define RECOMP_DEV_W_MEMF(a, v)    recomp_dev_w_f((uint32_t)(a), (float)(v))
#define RECOMP_DEV_W_MEMD(a, v)    recomp_dev_w_d((uint32_t)(a), (double)(v))

#endif
