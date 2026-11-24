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

/* DSP dispatch equivalence against the pre-handler-cache retirement path.
 * Reference dispatcher adapted from xemu, GPL-2.0-or-later;
 * Copyright (c) 2015 espes, 2020-2025 Matt Borgerson. */
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#endif
#include "dsp_cpu.c"
#include "fixtures/dsp_pm5_reference.inc.c"
#include <stddef.h>
#include <time.h>
#ifdef __EMSCRIPTEN__
#include <emscripten/emscripten.h>
#endif
static const OpcodeEntry *reference_cache[DSP_PRAM_SIZE];
static void reference_step(dsp_core_t *dsp) {
    dsp->disasm_memory_ptr=0;
    dsp->cur_inst=read_memory_p(dsp,dsp->pc);
    dsp->cur_inst_len=1;dsp->instr_cycle=2;
    if(dsp->cur_inst<0x100000) {
        const OpcodeEntry *op=reference_cache[dsp->pc];
        if(!op)op=reference_cache[dsp->pc]=lookup_opcode(dsp->cur_inst);
        if(op->emu_func)op->emu_func(dsp);else emu_undefined(dsp);
    } else if(dsp->cur_inst>=0x400000 && dsp->cur_inst<0x800000 &&
              (dsp->cur_inst&0xf40000)!=0x400000) reference_pm_5(dsp);
    else opcodes_parmove[(dsp->cur_inst>>20)&15](dsp);
    dsp_postexecute_update_pc(dsp);dsp_postexecute_interrupts(dsp);
    dsp->num_inst+=dsp->instr_cycle;
}
static dsp_core_t initial,actual,expected;
static uint32_t seed=0x56300;
static uint32_t random24(void) { seed=seed*1664525u+1013904223u;return seed&0xffffff; }
static void initialize(dsp_core_t *dsp) {
    memset(dsp,0,sizeof(*dsp));dsp56k_reset_cpu(dsp);dsp->is_gp=true;
    for(unsigned i=0;i<DSP_XRAM_SIZE;i++)dsp->xram[i]=random24();
    for(unsigned i=0;i<DSP_YRAM_SIZE;i++)dsp->yram[i]=random24();
    for(unsigned i=0;i<DSP_MIXBUFFER_SIZE;i++)dsp->mixbuffer[i]=random24();
    for(unsigned i=0;i<8;i++){dsp->registers[DSP_REG_R0+i]=0x100+16*i;dsp->registers[DSP_REG_N0+i]=1;}
    for(unsigned i=DSP_REG_X0;i<=DSP_REG_B1;i++)dsp->registers[i]=random24();
    dsp->registers[DSP_REG_A2]&=255;dsp->registers[DSP_REG_B2]&=255;
    dsp->registers[DSP_REG_SR]=random24()&0xcff;
}
static void equal_state(void) {
    size_t start=offsetof(dsp_core_t,pram_opcache),after=start+sizeof(actual.pram_opcache);
    if(memcmp(&actual,&expected,start) || memcmp((char*)&actual+after,(char*)&expected+after,sizeof(actual)-after)) {
        fprintf(stderr,"FAIL dispatch at opcode %06X pc %X/%X\n",actual.cur_inst,actual.pc,expected.pc);abort();
    }
}
static unsigned cases;
static void one(uint32_t word,uint32_t extension) {
    initial.pc=0;initial.pram[0]=word;initial.pram[1]=extension;
    memset((void *)reference_cache,0,sizeof(reference_cache));
    unsigned char cached[sizeof(actual.pram_opcache[0])];
    for(unsigned warm=0;warm<2;warm++) {
        initial.registers[DSP_REG_X0]=random24();initial.registers[DSP_REG_Y0]=random24();
        initial.registers[DSP_REG_SR]=random24()&0xcff;
        memcpy(&actual,&initial,sizeof(actual));memcpy(&expected,&initial,sizeof(expected));
        if(warm)memcpy(&actual.pram_opcache[0],cached,sizeof(cached));
        reference_step(&expected);dsp56k_execute_instruction(&actual);equal_state();
        memcpy(cached,&actual.pram_opcache[0],sizeof(cached));cases++;
    }
}
static double ms(void) {
#ifdef __EMSCRIPTEN__
    return emscripten_get_now();
#elif defined(_WIN32)
    LARGE_INTEGER frequency, counter;
    assert(QueryPerformanceFrequency(&frequency));
    assert(QueryPerformanceCounter(&counter));
    return (double)counter.QuadPart*1000.0/(double)frequency.QuadPart;
#else
    return (double)clock()*1000.0/CLOCKS_PER_SEC;
#endif
}
static void make_program(dsp_core_t *dsp,unsigned kind) {
    initialize(dsp);unsigned n=0;
    if(kind==0) {
        const uint32_t code[]={0x44f400,0x1000,0x46f400,0x2000,0x200013,0x0620a0,0x2000d2,0x567000,0x100,0x0c0000};
        for(unsigned i=0;i<ARRAY_SIZE(code);i++)dsp56k_write_memory(dsp,DSP_SPACE_P,n++,code[i]);
    } else {
        for(unsigned i=0;i<64;i++) {
            const uint32_t code[]={0x44f000,0x1400+i,0x200013,0x200040,0x200040,0x567000,0x1400+i};
            for(unsigned j=0;j<ARRAY_SIZE(code);j++)dsp56k_write_memory(dsp,DSP_SPACE_P,n++,code[j]);
        }
        dsp56k_write_memory(dsp,DSP_SPACE_P,n,0x0c0000);
    }
}
typedef void (*step_fn)(dsp_core_t *);
#ifdef _MSC_VER
#define NO_INLINE __declspec(noinline)
#else
#define NO_INLINE __attribute__((noinline))
#endif
static NO_INLINE void run(dsp_core_t *dsp,step_fn function,unsigned count) {
    volatile step_fn step=function;
    for(unsigned i=0;i<count;i++)step(dsp);
}
int main(int argc,char **argv) {
    initialize(&initial);
    const unsigned registers[]={4,5,6,7,14,15,16,24};
    for(unsigned alu=0;alu<256;alu++) {
        if(opcodes_alu[alu]==emu_undefined)continue;
        one(0x200000|alu,0); /* Pure ALU. */
        /* Overlap the destination with each possible ALU source register. */
        for (unsigned dst = 0; dst < 4; dst++)
            one(0x4cd800u | (dst << 16) | alu, 0);
        for (unsigned dst = 0; dst < 4; dst++)
            one(0xf08800u | ((dst & 2u) << 17) | ((dst & 1u) << 16) | alu, 0);
        for(unsigned mode=0;mode<32;mode++)one(0x204000|(mode<<8)|alu,0);
        for(unsigned src=4;src<16;src++)for(unsigned dst=4;dst<16;dst++)
            one(0x200000|(src<<13)|(dst<<8)|alu,0);
        for(unsigned r=0;r<ARRAY_SIZE(registers);r++) {
            unsigned reg=registers[r];
            one(0x200000|(reg<<16)|(0x55<<8)|alu,0); /* Short immediate. */
            unsigned bits=((reg&7)<<16)|((reg&24)<<17);
            for(unsigned write=0;write<2;write++) {
                one(0x400000|bits|(write<<15)|(0x10<<8)|alu,0);
                one(0x480000|bits|(write<<15)|(0x10<<8)|alu,0);
                one(0x404000|bits|(write<<15)|(0x30<<8)|alu,0x100);
            }
            one(0x40c000|bits|(0x34<<8)|alu,0x123456);
        }
        for(unsigned mode=0;mode<8;mode++)for(unsigned write=0;write<2;write++)
            one(0x400000|((mode&3)<<16)|((mode&4)<<17)|(write<<15)|(0x10<<8)|alu,0);
        for(unsigned group=0;group<16;group++)
            one(0x108000|(group<<16)|(0x20<<8)|alu,0);
        for(unsigned group=8;group<16;group++)
            one((group<<20)|0x80a0|alu,0); /* Dual X/Y moves. */
    }
    one(0,0);one(0x0c0000,0);one(0x0af080,0);one(0x0620a0,0);
    for(unsigned cond=0;cond<16;cond++)one(0x0e0000|(cond<<12),0);
    /* Software-interrupt retirement/prefetch remains identical. */
    initialize(&actual);memset(actual.pram,0,sizeof(actual.pram));actual.registers[DSP_REG_SR]=0;
    memcpy(&expected,&actual,sizeof(expected));memset((void *)reference_cache,0,sizeof(reference_cache));
    dsp56k_add_interrupt(&actual,DSP_INTER_SWI);dsp56k_add_interrupt(&expected,DSP_INTER_SWI);
    for(unsigned i=0;i<12;i++){reference_step(&expected);dsp56k_execute_instruction(&actual);equal_state();}
    /* Cached X-memory moves preserve addressing, saturation and sign extension.
     * Check all operand encodings and non-linear M modes. */
    const uint32_t modifiers[] = {0xffff, 0, 7, 0x8000};
    const uint32_t addresses[] = {0x107, 0xc07, 0x1407};
    const uint32_t signs[] = {0, 0xff, 0x80};
    for(unsigned m=0;m<ARRAY_SIZE(modifiers);m++) {
        for(unsigned a=0;a<ARRAY_SIZE(addresses);a++) {
            for(unsigned r=0;r<8;r++) {
                initial.registers[DSP_REG_R0 + r] = addresses[a];
                initial.registers[DSP_REG_M0 + r] = modifiers[m];
                if (a == 0) {
                    for (unsigned dst = 0; dst < 4; dst++)
                        one(0x4cd8d2u | (dst << 16) | (r << 8), 0);
                }
                for(unsigned d=0;d<4;d++)one(0x44d800u | (d<<16) | (r<<8),0);
                for (unsigned acc = 0; acc < 2; acc++) {
                    unsigned operands = (acc << 16) | (r << 8);
                    one(0x56e000u | operands, 0);
                    for (unsigned extension = 0; extension < ARRAY_SIZE(signs); extension++) {
                        initial.registers[DSP_REG_A2 + acc] = signs[extension];
                        initial.registers[DSP_REG_A1 + acc] = extension ? 0x7fffff : 0x800000;
                        initial.registers[DSP_REG_A0 + acc] = 0x800000;
                        one(0x565800u | operands, 0);
                    }
                }
            }
        }
    }
    /* Dual loads cover both register banks, N-based updates and X aliases. */
    initialize(&initial);
    for (unsigned xr = 0; xr < 8; xr++) {
        for (unsigned yr = 0; yr < 4; yr++) {
            unsigned y = yr | ((xr ^ 4u) & 4u);
            for (unsigned m = 0; m < ARRAY_SIZE(modifiers); m++) {
                initial.registers[DSP_REG_R0 + y] = 0x107;
                initial.registers[DSP_REG_M0 + y] = modifiers[m];
                initial.registers[DSP_REG_M0 + xr] = modifiers[m];
                initial.registers[DSP_REG_N0 + xr] = 3;
                for (unsigned a = 0; a < ARRAY_SIZE(addresses); a++) {
                    initial.registers[DSP_REG_R0 + xr] = addresses[a];
                    one(0xf088dau | (xr << 8) | (yr << 13), 0);
                }
            }
        }
    }
    /* Uploads must invalidate handlers when the family changes too. */
    initialize(&actual);actual.pram[0]=0x200013;dsp56k_execute_instruction(&actual);
    dsp56k_write_memory(&actual,DSP_SPACE_P,0,0x44f400);dsp56k_write_memory(&actual,DSP_SPACE_P,1,0x123456);
    actual.pc=0;dsp56k_execute_instruction(&actual);assert(actual.registers[DSP_REG_X0]==0x123456 && actual.pc==2);
    dsp56k_write_memory(&actual,DSP_SPACE_P,1,0x654321);
    actual.pc=0;dsp56k_execute_instruction(&actual);assert(actual.registers[DSP_REG_X0]==0x654321);
    /* Uploading only the ALU byte must invalidate the no-op specialization. */
    dsp56k_write_memory(&actual,DSP_SPACE_P,0,0x44f413);
    actual.registers[DSP_REG_A1]=0x123456;actual.pc=0;dsp56k_execute_instruction(&actual);
    assert(actual.registers[DSP_REG_X0]==0x654321 && actual.registers[DSP_REG_A1]==0);
    dsp56k_write_memory(&actual,DSP_SPACE_P,0,0x44f400);
    actual.registers[DSP_REG_A1]=0x123456;actual.pc=0;dsp56k_execute_instruction(&actual);
    assert(actual.registers[DSP_REG_X0]==0x654321 && actual.registers[DSP_REG_A1]==0x123456);
    dsp56k_write_memory(&actual,DSP_SPACE_P,0,0x0c0000);actual.pc=0;dsp56k_execute_instruction(&actual);assert(actual.pc==0);
    dsp56k_write_memory(&actual,DSP_SPACE_P,0,0x200013);actual.pc=0;dsp56k_execute_instruction(&actual);
    assert(actual.pc==1 && actual.registers[DSP_REG_A1]==0);
    initialize(&actual);actual.registers[DSP_REG_X0]=0x200013;
    dsp56k_write_memory(&actual,DSP_SPACE_P,0,0x077084); /* MOVEM X0,P:abs */
    dsp56k_write_memory(&actual,DSP_SPACE_P,1,0);
    dsp56k_write_memory(&actual,DSP_SPACE_P,2,0x0c0000);
    dsp56k_execute_instruction(&actual);assert(actual.pc==2 && actual.pram[0]==0x200013);
    dsp56k_execute_instruction(&actual);dsp56k_execute_instruction(&actual);
    assert(actual.pc==1 && actual.registers[DSP_REG_A1]==0);
    for(unsigned program=0;program<2;program++) {
        make_program(&actual,program);memcpy(&expected,&actual,sizeof(expected));memset((void *)reference_cache,0,sizeof(reference_cache));
        for(unsigned i=0;i<2000;i++){reference_step(&expected);dsp56k_execute_instruction(&actual);equal_state();}
    }
    printf("PASS DSP dispatch: %u cold/warm full-state cases, software IRQ retirement and cross-family code upload\n",cases);
    if(argc>1 && !strcmp(argv[1],"--benchmark"))for(unsigned program=0;program<2;program++) {
      make_program(&actual,program);memcpy(&expected,&actual,sizeof(expected));memset((void *)reference_cache,0,sizeof(reference_cache));
      run(&expected,reference_step,200000);run(&actual,dsp56k_execute_instruction,200000);equal_state();
      for(unsigned round=0;round<5;round++) {
        make_program(&actual,program);memcpy(&expected,&actual,sizeof(expected));memset((void *)reference_cache,0,sizeof(reference_cache));
        double old_ms,new_ms,begin;
        if(round&1) {
            begin=ms();run(&actual,dsp56k_execute_instruction,2000000);new_ms=ms()-begin;
            begin=ms();run(&expected,reference_step,2000000);old_ms=ms()-begin;
        } else {
            begin=ms();run(&expected,reference_step,2000000);old_ms=ms()-begin;
            begin=ms();run(&actual,dsp56k_execute_instruction,2000000);new_ms=ms()-begin;
        }
        equal_state();printf("BENCH program=%u original=%.3fms current=%.3fms\n",program,old_ms,new_ms);
      }
    }
}
