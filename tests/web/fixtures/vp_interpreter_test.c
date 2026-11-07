#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define VP_CONSTS 192
#define VP_PROG_LEN 136
typedef unsigned DWORD;
static DWORD GetTickCount(void) { return 0; }
static struct { unsigned start; uint32_t prog[136][4]; float c[192][4]; } s_vp;
static unsigned char s_const_written[192];
static void const_unwritten_note(int c, int a0) {}
static unsigned s_vp_cgen;
static uint32_t vp_field(const uint32_t *t, int word, int bit, int len) {
    return (t[word] >> bit) & ((1u << len) - 1u);
}

/* LIVE_INTERPRETER */
#include "vp_reference.inc.c"

static uint32_t seed=0x5a9c183fu;
static uint32_t next(void) { seed=seed*1664525u+1013904223u;return seed; }
static int parity_check(void) {
    for(unsigned trial=0;trial<10000;trial++) {
        unsigned starts[4]={0,13,79,105}; s_vp.start=starts[trial%4];
        for(unsigned i=0;i<8;i++) {
            uint32_t *t=s_vp.prog[s_vp.start+i]; unsigned mac=1+next()%13u;
            t[0]=0;
            t[1]=(next()&255u)|((next()%16u)<<9)|((next()%192u)<<13)|(mac<<21)|((next()%8u)<<25);
            t[2]=next();
            if(mac==13) t[2]=(t[2]&~(3u<<26))|(2u<<26);
            t[3]=(next()&~0x00F007F9u)|((next()%13u)<<20)|((next()%192u)<<3)|(i==7);
        }
        for(unsigned pass=0;pass<2;pass++) {
            float full[16][4], masked[16][4], before[16][4], after[16][4];
            float constants[192][4], expected_constants[192][4], expected_registers[13][4]; int expected_a0;
            uint32_t mask=vp_input_mask(s_vp.start);
            for(unsigned i=0;i<192;i++) for(unsigned j=0;j<4;j++) s_vp.c[i][j]=((int)(next()%2001)-1000)/500.0f;
            memcpy(constants,s_vp.c,sizeof constants);
            for(unsigned i=0;i<16;i++) for(unsigned j=0;j<4;j++) {
                full[i][j]=((next()%1000u)+1)/100.0f;
                masked[i][j]=(mask>>i)&1u?full[i][j]:NAN;
            }
            reference_vp_run(full,before);
            memcpy(expected_constants,s_vp.c,sizeof expected_constants);
            memcpy(expected_registers,s_vp_dbg_r,sizeof expected_registers); expected_a0=s_vp_dbg_a0;
            memcpy(s_vp.c,constants,sizeof constants);
            vp_run(masked,after);
            if(memcmp(before,after,sizeof before)||memcmp(expected_constants,s_vp.c,sizeof expected_constants)
               ||memcmp(expected_registers,s_vp_dbg_r,sizeof expected_registers)||expected_a0!=s_vp_dbg_a0) {
                printf("FAIL decoded interpreter parity trial %u pass %u mask %04X\n",trial,pass,mask);return 1;
            }
            memcpy(s_vp.c,constants,sizeof constants);
            vp_run_prepared(masked,after,0);
            if(memcmp(before,after,sizeof before)||memcmp(expected_constants,s_vp.c,sizeof expected_constants)) {
                printf("FAIL fast interpreter parity trial %u pass %u\n",trial,pass);return 1;
            }
        }
    }
    puts("PASS 40000 decoded/interpreted comparisons including paired operations, swizzles, address registers, constant writes and cache invalidation");
    return 0;
}

#include <emscripten/emscripten.h>
int main(void) {
    if(parity_check()) return 1;
    s_vp.start=13;
    for(unsigned i=0;i<192;i++) for(unsigned j=0;j<4;j++) s_vp.c[i][j]=0.25f;
    for(unsigned i=0;i<24;i++) {
        uint32_t *t=s_vp.prog[s_vp.start+i];t[0]=0;
        t[1]=(4u<<21)|((i%6u)<<9)|(i<<13)|0x1Bu;
        t[2]=(2u<<26)|(3u<<11)|(1u<<21)|(2u<<19)|(3u<<17)|(1u<<6)|(2u<<4)|(3u<<2);
        t[3]=(1u<<28)|(15u<<24)|(15u<<12)|(1u<<11)|(3u<<3)|(i==23);
    }
    float input[16][4], output[16][4]; volatile float checksum=0;
    for(unsigned i=0;i<16;i++) for(unsigned j=0;j<4;j++) input[i][j]=(float)(i+1);
    vp_prepare_program();
    for(unsigned i=0;i<10000;i++) {reference_vp_run(input,output);vp_run_prepared(input,output,0);checksum+=output[3][0];}
    double start=emscripten_get_now();
    for(unsigned i=0;i<100000;i++) {reference_vp_run(input,output);checksum+=output[3][0];}
    double original=emscripten_get_now()-start;
    start=emscripten_get_now();
    for(unsigned i=0;i<100000;i++) {vp_run_prepared(input,output,0);checksum+=output[3][0];}
    double prepared=emscripten_get_now()-start;
    printf("Vertex interpreter benchmark original %.2f ms, prepared %.2f ms, speedup %.2fx (checksum %.0f)\n",original,prepared,original/prepared,(double)checksum);
    return 0;
}
