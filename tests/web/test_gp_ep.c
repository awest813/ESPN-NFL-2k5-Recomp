/* Real GP/EP bridge, uploaded firmware, page-scattered scratch and PCM. */
#include "apu_state.h"
#include "apu.h"
#include "dsp/dsp_dma_regs.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
uint8_t *g_apu_ram_ptr;
struct McpxApuDebug g_dbg,g_dbg_cache;
volatile float g_apu_bed_gain=1.0f,g_apu_voice_gain=1.0f,g_apu_voice_level;
uint32_t xbox_ContiguousAllocatedBytes(void) { return 0; }
static MCPXAPUState *checked;
static unsigned lock_depth,reads;
static bool s_apu_lock_profile;
#ifndef _WIN32
void EnterCriticalSection(LPCRITICAL_SECTION cs) {
    (void)cs;assert(checked && checked->mmio_waiters==1);lock_depth++;
}
void LeaveCriticalSection(LPCRITICAL_SECTION cs) {
    (void)cs;assert(lock_depth==1 && !checked->mmio_waiters);lock_depth--;
}
void WakeConditionVariable(PCONDITION_VARIABLE cv) { (void)cv; }
#endif
uint64_t mcpx_apu_read(void *d,hwaddr addr,unsigned size) { (void)d;(void)addr;(void)size;reads++;return 17; }
void mcpx_apu_write(void *d,hwaddr addr,uint64_t value,unsigned size) { (void)d;(void)addr;(void)value;(void)size; }
uint64_t mcpx_apu_vp_read(void *d,hwaddr addr,unsigned size) { (void)d;(void)addr;(void)size;return 19; }
void mcpx_apu_vp_write(void *d,hwaddr addr,uint64_t value,unsigned size) { (void)d;(void)addr;(void)value;(void)size; }
/* PRODUCTION_MMIO */
/* PRODUCTION_LEVEL */
static void wr(MCPXAPUState *d,uint32_t addr,uint32_t value) { mcpx_apu_mmio_write(d,addr,value,4); }
static uint32_t rd(MCPXAPUState *d,uint32_t addr) { return (uint32_t)mcpx_apu_mmio_read(d,addr,4); }
int main(void) {
    static MCPXAPUState d;checked=&d;d.dsp_enabled=true;
#ifdef _WIN32
    qemu_mutex_init(&d.lock);qemu_cond_init(&d.cond);
#endif
    g_apu_ram_ptr=calloc(1,0x20000);assert(g_apu_ram_ptr);
    mcpx_apu_dsp_real_init(&d);assert(d.gp.dsp && d.ep.dsp);
    d.dsp_enabled=false;wr(&d,0x30010,0x654321);assert(rd(&d,0x30010)==0);
    d.dsp_enabled=true;assert(rd(&d,0x30010)==0);
    wr(&d,0x30010,0xff123456);assert(rd(&d,0x30010)==0x123456);
    wr(&d,0x36010,0xabcdef);assert(rd(&d,0x36010)==0xabcdef);
    wr(&d,0x50010,0x765432);assert(rd(&d,0x50010)==0x765432);
    wr(&d,0x56010,0x123456);assert(rd(&d,0x56010)==0x123456);
    assert(mcpx_apu_mmio_read(&d,0x30001,4)==0 && mcpx_apu_mmio_read(&d,0x30000,2)==0);
    assert(rd(&d,0)==17 && reads==1 && rd(&d,0x20000)==19);
    /* Bootstrap spans two noncontiguous guest pages. */
    stl_le_phys(NULL,0x1000,0x10000);stl_le_phys(NULL,0x1008,0x14000);
    d.regs[NV_PAPU_GPSADDR]=0x1000;d.regs[NV_PAPU_GPSMAXSGE]=1;
    uint32_t *p=(uint32_t*)(g_apu_ram_ptr+0x10000);unsigned n=0;
    for(unsigned sample=0;sample<64;sample++) {
        p[n++]=0x44f000;p[n++]=0x1400+sample; /* X:mixbuf -> X0 */
        p[n++]=0x200013;p[n++]=0x200040;p[n++]=0x200040; /* A = 2*X0 */
        p[n++]=0x567000;p[n++]=0x1400+sample; /* A -> mixbuf */
    }
    p[n++]=0x08f484;p[n++]=1;p[n++]=0x0c0000; /* idle; JMP start next frame */
    p[0]|=0xab000000;
    wr(&d,0x3fffc,3);assert(rd(&d,0x3a000)==0x44f000);
    static float bins[NUM_MIXBINS][NUM_SAMPLES_PER_FRAME];
    for(unsigned i=0;i<32;i++){bins[0][i]=0.25f;bins[1][i]=-0.125f;}
    for(unsigned frame=0;frame<64;frame++) {
        d.ep_frame_div=frame;mcpx_apu_dsp_real_frame(&d,bins);
        assert(d.gp.dsp->core.is_idle && !d.gp.dsp->save_cycles && !d.dsp_overruns);
        unsigned off=(frame%8)*32;
        for(unsigned i=0;i<32;i++)assert(d.monitor.frame_buf[off+i][0]==16384 && d.monitor.frame_buf[off+i][1]==-8192);
    }
    /* Controls act before firmware processing; the raw VP input is preserved. */
    for(unsigned i=0;i<32;i++)bins[2][i]=0.0625f;
    bins[10][0]=0.125f;
    static float unchanged[NUM_MIXBINS][NUM_SAMPLES_PER_FRAME];
    memcpy(unchanged,bins,sizeof(bins));
    xbox_AudioSetGameGain(0.5f);xbox_AudioSetCommentaryGain(0.0f);g_apu_voice_level=0;
    d.ep_frame_div=0;mcpx_apu_dsp_real_frame(&d,bins);
    assert(d.monitor.frame_buf[0][0]==8192 && d.monitor.frame_buf[0][1]==-4096);
    assert(rd(&d,0x35100)==0 && rd(&d,0x35500)==0x080000);
    assert(fabsf(xbox_AudioGameLevel()-0.01875f)<1e-7f);
    assert(!memcmp(unchanged,bins,sizeof(bins)));
    xbox_AudioSetGameGain(-1);xbox_AudioSetCommentaryGain(2);
    assert(g_apu_bed_gain==0 && g_apu_voice_gain==1);
    xbox_AudioSetCommentaryGain(0.5f);
    mcpx_apu_dsp_real_frame(&d,bins);
    assert(d.monitor.frame_buf[0][0]==0 && d.monitor.frame_buf[0][1]==0);
    assert(rd(&d,0x35100)==0x040000 && rd(&d,0x35500)==0);
    for(unsigned i=0;i<32;i++)bins[2][i]=0;
    float before=g_apu_voice_level;mcpx_apu_dsp_real_frame(&d,bins);
    assert(fabsf(g_apu_voice_level-before*0.996f)<1e-7f);
    xbox_AudioSetGameGain(2);xbox_AudioSetCommentaryGain(-1);
    assert(g_apu_bed_gain==1 && g_apu_voice_gain==0);
    xbox_AudioSetCommentaryGain(1);
    /* Deasserted reset halts execution, without overwriting uploaded X memory. */
    wr(&d,0x3fffc,0);assert(d.gp.dsp->core.pc==0);
    /* EP firmware starts DMA to its stereo PCM FIFO, then idles. */
    stl_le_phys(NULL,0x2000,0x18000);stl_le_phys(NULL,0x2008,0x1c000);
    d.regs[NV_PAPU_EPSADDR]=0x2000;d.regs[NV_PAPU_EPSMAXSGE]=1;
    const uint32_t ep_program[]={0x08f494,0x200,0x08f496,1,0x08f484,1,0x0c0000};
    memcpy(g_apu_ram_ptr+0x18000,ep_program,sizeof(ep_program));
    const uint32_t node[]={NODE_POINTER_EOL,1|NODE_CONTROL_DIRECTION|(1<<10),
                           (256<<4)|1,0x400,0,0,0};
    for(unsigned i=0;i<7;i++)wr(&d,0x50800+i*4,node[i]);
    for(unsigned i=0;i<256;i++) {
        wr(&d,0x51000+i*4,(uint32_t)((int)i-128)*256u);
        wr(&d,0x51400+i*4,(0x1234+i)*256u);
    }
    stl_le_phys(NULL,0x3000,0x8000);
    d.regs[NV_PAPU_EPFADDR]=0x3000;d.regs[NV_PAPU_EPFMAXSGE]=0;
    d.regs[NV_PAPU_EPOFBASE0]=0x100;d.regs[NV_PAPU_EPOFEND0]=0x900;
    d.regs[NV_PAPU_EPOFCUR0]=0x100;
    wr(&d,0x5fffc,3);assert(rd(&d,0x5a000)==ep_program[0]);
    memset(d.monitor.frame_buf,0x5a,sizeof(d.monitor.frame_buf));
    d.ep_frame_div=1;mcpx_apu_dsp_real_frame(&d,bins);
    assert(d.ep.dsp->core.pc==0 && d.monitor.frame_buf[0][0]==0x5a5a);
    d.ep_frame_div=0;mcpx_apu_dsp_real_frame(&d,bins);
    for(unsigned i=0;i<256;i++)assert(d.monitor.frame_buf[i][0]==(int)i-128 && d.monitor.frame_buf[i][1]==0x1234+i);
    assert(d.ep.dsp->core.is_idle && !d.ep.dsp->save_cycles);
    assert(d.regs[NV_PAPU_EPOFCUR0]==0x500 && !d.dsp_overruns);
    d.ep_frame_div=8;mcpx_apu_dsp_real_frame(&d,bins);
    assert(d.regs[NV_PAPU_EPOFCUR0]==0x100 && !d.dsp_overruns);
    mcpx_apu_dsp_reset(&d);assert(!d.gp.regs[NV_PAPU_GPRST] && !d.ep.regs[NV_PAPU_EPRST]);
    wr(&d,0x3fffc,3);wr(&d,0x3a000,0x0c0000); /* Non-idling firmware. */
    puts("EXPECT one DSP diagnostic for intentionally non-idling firmware:");
    mcpx_apu_dsp_real_frame(&d,bins);
    assert(d.dsp_overruns==1 && d.gp.dsp->core.pc==0);
    dsp_destroy(d.gp.dsp);dsp_destroy(d.ep.dsp);free(g_apu_ram_ptr);
#ifdef _WIN32
    qemu_mutex_destroy(&d.lock);qemu_cond_destroy(&d.cond);
#endif
    puts("PASS GP/EP: MMIO, firmware, PCM FIFO, gain controls, commentary meter, idle pacing and reset");
}
