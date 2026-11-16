/*
 * DSP56300 emulator
 *
 * Copyright (c) 2015 espes
 * Copyright (c) 2020-2025 Matt Borgerson
 *
 * Adapted from Hatari DSP M56001 emulation
 * (C) 2003-2008 ARAnyM developer team
 * Adaption to Hatari (C) 2008 by Thomas Huth
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 */


/* Original xemu multiplication retained as an independent limb reference.
 * Production implementation is included so its static helper is exercised. */
#include "dsp_cpu.c"
#include <time.h>
#ifdef __EMSCRIPTEN__
#include <emscripten/emscripten.h>
#endif
static void old_mul56(uint32_t source1, uint32_t source2, uint32_t *dest, uint8_t signe)
{
    uint32_t part[4], zerodest[3], value;

    /* Multiply: D = S1*S2 */
    if (source1 & (1<<23)) {
        signe ^= 1;
        source1 = (1<<24) - source1;
    }
    if (source2 & (1<<23)) {
        signe ^= 1;
        source2 = (1<<24) - source2;
    }

    /* bits 0-11 * bits 0-11 */
    part[0]=(source1 & BITMASK(12))*(source2 & BITMASK(12));
    /* bits 12-23 * bits 0-11 */
    part[1]=((source1>>12) & BITMASK(12))*(source2 & BITMASK(12));
    /* bits 0-11 * bits 12-23 */
    part[2]=(source1 & BITMASK(12))*((source2>>12)  & BITMASK(12));
    /* bits 12-23 * bits 12-23 */
    part[3]=((source1>>12) & BITMASK(12))*((source2>>12) & BITMASK(12));

    /* Calc dest 2 */
    dest[2] = part[0];
    dest[2] += (part[1] & BITMASK(12)) << 12;
    dest[2] += (part[2] & BITMASK(12)) << 12;

    /* Calc dest 1 */
    dest[1] = (part[1]>>12) & BITMASK(12);
    dest[1] += (part[2]>>12) & BITMASK(12);
    dest[1] += part[3];

    /* Calc dest 0 */
    dest[0] = 0;

    /* Add carries */
    value = (dest[2]>>24) & BITMASK(8);
    if (value) {
        dest[1] += value;
        dest[2] &= BITMASK(24);
    }
    value = (dest[1]>>24) & BITMASK(8);
    if (value) {
        dest[0] += value;
        dest[1] &= BITMASK(24);
    }

    /* Get rid of extra sign bit */
    dsp_asl56(dest, 1);

    if (signe) {
        zerodest[0] = zerodest[1] = zerodest[2] = 0;

        dsp_sub56(dest, zerodest);

        dest[0] = zerodest[0];
        dest[1] = zerodest[1];
        dest[2] = zerodest[2];
    }
}
static double milliseconds(void) {
#ifdef __EMSCRIPTEN__
    return emscripten_get_now();
#else
    return (double)clock()*1000.0/CLOCKS_PER_SEC;
#endif
}
typedef void (*multiply_fn)(uint32_t,uint32_t,uint32_t *,uint8_t);
#ifdef _MSC_VER
#define NO_INLINE __declspec(noinline)
#else
#define NO_INLINE __attribute__((noinline))
#endif
static NO_INLINE uint32_t bench(multiply_fn multiply,unsigned count) {
    uint32_t seed=0x56300,sum=0,result[3];
    for(unsigned i=0;i<count;i++) {
        seed=seed*1664525u+1013904223u;uint32_t a=seed&0xffffff;
        seed=seed*1664525u+1013904223u;uint32_t b=seed&0xffffff;
        multiply(a,b,result,(uint8_t)((seed>>24)&1));
        sum+=result[0]^result[1]^result[2];
    }
    return sum;
}
int main(int argc,char **argv) {
    FILE *f=fopen(argc>1?argv[1]:"/vectors.bin","rb");assert(f);
    uint8_t bytes[24];unsigned golden=0;uint32_t result[3],reference[3];
    while(fread(bytes,1,sizeof(bytes),f)==sizeof(bytes)) {
        uint32_t a=ldl_le_p(bytes),b=ldl_le_p(bytes+4),sign=ldl_le_p(bytes+8);
        dsp_mul56(a,b,result,(uint8_t)sign);old_mul56(a,b,reference,(uint8_t)sign);
        for(unsigned j=0;j<3;j++)assert(result[j]==ldl_le_p(bytes+12+4*j) && reference[j]==result[j]);
        golden++;
    }
    fclose(f);assert(golden>10000);
    uint32_t seed=0x56300;
    for(unsigned i=0;i<2000000;i++) {
        seed=seed*1664525u+1013904223u;uint32_t a=seed&0xffffff;
        seed=seed*1664525u+1013904223u;uint32_t b=seed&0xffffff;
        uint8_t sign=(uint8_t)((seed>>24)&1);
        dsp_mul56(a,b,result,sign);old_mul56(a,b,reference,sign);
        assert(!memcmp(result,reference,sizeof(result)));
    }
    printf("PASS DSP multiply: %u Python integer vectors and 2000000 limb-reference cases\n",golden);
    for(unsigned i=0;argc>2 && !strcmp(argv[2],"--benchmark") && i<5;i++) {
        double begin=milliseconds();uint32_t x=bench(old_mul56,2000000);double old_ms=milliseconds()-begin;
        begin=milliseconds();uint32_t y=bench(dsp_mul56,2000000);double new_ms=milliseconds()-begin;
        assert(x==y);printf("BENCH original=%.3fms current=%.3fms checksum=%08X\n",old_ms,new_ms,x);
    }
}
