#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "dsp_state.h"
#include "dsp_dma_regs.h"

/* DSP56300 FM: MOVE X:ea,X0; CLR A; REP #32; ADD X0,A;
 * MOVE A,X:ea; JMP. All words are 24-bit instructions. */
static const uint32_t program[]={0x44f000,0x001400,0x200013,0x0620a0,
                                0x200040,0x567000,0x000100,0x0c0007};
static uint8_t scratch[16384],fifo[4096];
static size_t fifo_bytes;
static void scratch_rw(void *opaque,uint8_t *ptr,uint32_t addr,size_t len,bool dir) {
    (void)opaque;assert(addr+len<=sizeof(scratch));
    if(dir)memcpy(scratch+addr,ptr,len);else memcpy(ptr,scratch+addr,len);
}
static void fifo_rw(void *opaque,uint8_t *ptr,unsigned index,size_t len,bool dir) {
    (void)opaque;assert(index==0 && dir && len<=sizeof(fifo));
    memcpy(fifo,ptr,len);fifo_bytes=len;
}
static void write_node(DSPState *d,uint32_t control,uint32_t count,uint32_t mem,
                       uint32_t offset,uint32_t base,uint32_t size) {
    uint32_t node[]={NODE_POINTER_EOL,control,count,mem,offset,base,size-1};
    for(unsigned i=0;i<7;i++)dsp_write_memory(d,'X',0x200+i,node[i]);
    dsp_dma_write(&d->dma,DMA_NEXT_BLOCK,0x200);
    dsp_dma_write(&d->dma,DMA_CONTROL,DMA_CONTROL_ACTION_START);
}
int main(void) {
    DSPState *d=dsp_init(NULL,scratch_rw,fifo_rw);assert(d);
    d->core.is_gp=true;
    /* Bootstrap strips unused high bytes and invalidates decoded opcodes. */
    memcpy(scratch,program,sizeof(program));scratch[3]=0xab;
    dsp_bootstrap(d);assert(dsp_read_memory(d,'P',0)==program[0]);
    for(int sign=-1;sign<=1;sign+=2) {
        dsp_reset(d);d->core.is_gp=true;
        uint32_t input=(sign*0x1000)&0xffffff;
        dsp_write_memory(d,'X',0x1400,input);
        assert(dsp_read_memory(d,'X',0xc00)==input);
        unsigned steps=0;
        while(d->core.pc!=7 && steps++<100)dsp_step(d);
        assert(steps<100 && dsp_read_memory(d,'X',0x100)==((sign*0x20000)&0xffffff));
    }
    uint32_t seed=0x56300;
    const int32_t edge[]={0,1,-1,0x3ffff,0x40000,-0x40000,0x7fffff,-0x800000};
    for(unsigned n=0;n<1032;n++) {
        seed=seed*1664525u+1013904223u;
        uint32_t bits=seed&0xffffff;
        int32_t input=n<8 ? edge[n] : (bits&0x800000 ? (int32_t)bits-0x1000000 : (int32_t)bits);
        int64_t expected=(int64_t)input*32;
        if(expected>0x7fffff)expected=0x7fffff;
        if(expected< -0x800000)expected= -0x800000;
        dsp_reset(d);dsp_write_memory(d,'X',0x1400,(uint32_t)input&0xffffff);
        unsigned steps=0;while(d->core.pc!=7 && steps++<100)dsp_step(d);
        assert(steps<100 && dsp_read_memory(d,'X',0x100)==((uint32_t)expected&0xffffff));
    }
    /* An uploaded code patch must not reuse the previously decoded ADD. */
    dsp_write_memory(d,'P',4,0x200044); /* SUB X0,A */
    dsp_reset(d);dsp_write_memory(d,'X',0x1400,0x1000);
    unsigned steps=0;while(d->core.pc!=7 && steps++<100)dsp_step(d);
    assert(steps<100 && dsp_read_memory(d,'X',0x100)==0xfe0000);
    dsp_start_frame(d);assert(dsp_read_memory(d,'X',0xffffc5)&2);
    dsp_write_memory(d,'X',0xffffc5,2);assert(!(dsp_read_memory(d,'X',0xffffc5)&2));
    dsp_write_memory(d,'X',0xffffc4,1);assert(d->core.is_idle);

    /* Scratch -> X DMA, including exact 24-bit mask. */
    const uint32_t input[]={0xab123456,0xfffedcba};memcpy(scratch+64,input,sizeof(input));
    write_node(d,(0xf<<5)|(2<<10),2,0x100,0,64,8);
    assert(dsp_read_memory(d,'X',0x100)==0x123456);
    assert(dsp_read_memory(d,'X',0x101)==0xfedcba);
    assert(d->dma.eol && (dsp_read_memory(d,'X',0xffffc5)&0x80));
    dsp_write_memory(d,'X',0xffffc5,0x80);assert(!d->dma.eol);
    /* Two planar channels -> interleaved 16-bit FIFO samples. */
    const uint32_t planar[]={0x123400,0xfedc00,0x567800,0x800000};
    for(unsigned i=0;i<4;i++)dsp_write_memory(d,'X',0x100+i,planar[i]);
    write_node(d,1|NODE_CONTROL_DIRECTION|(1<<10),(2<<4)|1,0x100,0,0,8);
    const uint16_t expected[]={0x1234,0x5678,0xfedc,0x8000};
    assert(fifo_bytes==sizeof(expected) && !memcmp(fifo,expected,sizeof(expected)));
    /* Scratch circular DMA wraps and writes the updated byte offset back. */
    write_node(d,NODE_CONTROL_DIRECTION|(0xe<<5)|(1<<10)|(1<<4),2,0x100,6,128,8);
    uint16_t a,b;memcpy(&a,scratch+134,2);memcpy(&b,scratch+128,2);
    assert(a==0x1234 && b==0xfedc && dsp_read_memory(d,'X',0x204)==2);
    /* A program-memory DMA upload must invalidate an already cached move. */
    dsp_write_memory(d,'P',0,0x44f400);dsp_write_memory(d,'P',1,1);
    dsp_reset(d);dsp_step(d);assert(d->core.registers[DSP_REG_X0]==1);
    uint32_t replacement=0x200013;memcpy(scratch+64,&replacement,4); /* CLR A */
    write_node(d,(0xf<<5)|(2<<10),1,0x2800,0,64,4);
    d->core.pc=0;d->core.registers[DSP_REG_A1]=0x123456;
    dsp_step(d);assert(d->core.registers[DSP_REG_A1]==0 && d->core.pc==1);
    dsp_destroy(d);
    puts("PASS DSP56300: uploaded signed sample program, REP, code patch, bootstrap, frame IRQ, idle, scratch/FIFO DMA and circular wrap");
}
