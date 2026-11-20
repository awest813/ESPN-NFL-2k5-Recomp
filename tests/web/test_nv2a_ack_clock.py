"""Exercise the production acknowledgement clock, maintenance cadence and wraparound."""
from pathlib import Path
import argparse
import os
import shutil
import subprocess


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", action="store_true", help="Run with a native C compiler and ASAN/UBSAN")
    parser.add_argument("--build-dir", type=Path, default=root / "build-web-tests/nv2a-ack-clock")
    args = parser.parse_args()
    runtime = (root / "external/xboxrecomp/src/kernel/xbox_memory_layout.c").read_text(encoding="utf-8")
    def function(name):
        start = runtime.index("static void " + name + "(")
        return runtime[start:runtime.index("\n}", start) + 2]
    flip_start = runtime.index("void xbox_Nv2aFrameCounterFlip(")
    flip = runtime[flip_start:runtime.index("\n}", flip_start) + 2]
    live = "\n".join([function("frame_counters_tick"), function("framebuffer_probe_tick"),
                      function("wasm_unrouted_check"), function("nv2a_ack_clock_tick"), flip])
    harness = r"""
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <assert.h>
#ifndef __EMSCRIPTEN__
#define __EMSCRIPTEN__ 1
#endif
typedef uint32_t DWORD;
typedef int32_t LONG;
#define XBOX_KERNEL_DATA_BASE 0x100u
#define KDATA_TICK_COUNT 0x20u
#define XBOX_FRAME_PERIOD_MS 16u
#define XBOX_MCPX_BASE 0xfe800000u
#define XBOX_TILED_BASE 0xf0000000u
static uint32_t memory[1024];
static intptr_t g_memory_offset;
static size_t g_memory_size=sizeof memory;
static struct { uint32_t device_ptr_va, counter_off; } g_frame_counters[4];
static int g_frame_counter_count;
static DWORD g_frame_counter_last_ms, g_frame_counter_flip_ms;
static uint32_t s_fb_va,s_fb_pitch,s_fb_height;
static int s_nv2a_trace,g_apu_mmio_trapped;
static void *g_mcpx_memory,*g_tiled_view;
static size_t g_tiled_view_size;
static DWORD clock_value;
static volatile unsigned clock_calls;
static unsigned fb_logs,apu_warnings,tiled_warnings,fb_words;
static uint32_t warning_address,warning_value,fb_sum;
static DWORD GetTickCount(void) { clock_calls++;return clock_value++; }
static int fence_readable(uint32_t va,uint32_t bytes) { return va>=0x200u && va<=0x300u-bytes; }
static int test_fprintf(FILE *stream,const char *format,...) {
    (void)stream;
    // Diagnostics must observe the already-published fresh guest tick.
    assert(memory[(XBOX_KERNEL_DATA_BASE+KDATA_TICK_COUNT)/4]==clock_value-1u);
    va_list ap;va_start(ap,format);
    if(strstr(format,"[FB]")) {
        fb_logs++;(void)va_arg(ap,unsigned);fb_sum=va_arg(ap,unsigned);
        (void)va_arg(ap,unsigned);fb_words=va_arg(ap,unsigned);(void)va_arg(ap,const char*);
    } else if(strstr(format,"WARNING")) {
        warning_address=va_arg(ap,unsigned);
        if(strstr(format,"APU")){apu_warnings++;warning_value=va_arg(ap,unsigned);}
        else tiled_warnings++;
    } else assert(!"unexpected diagnostic");
    va_end(ap);return 0;
}
#define fprintf test_fprintf
/* LIVE_MAINTENANCE */
#undef fprintf
static uint32_t *word(unsigned va) { return &memory[va/4]; }
static void tick(DWORD now) {
    clock_calls=0;clock_value=now;nv2a_ack_clock_tick();
    assert(clock_calls==1);
    assert(*word(XBOX_KERNEL_DATA_BASE+KDATA_TICK_COUNT)==now);
}
static void timers(void) {
    tick(100);assert(!g_frame_counter_count);
    g_frame_counter_count=2;
    g_frame_counters[0].device_ptr_va=0x200;g_frame_counters[0].counter_off=4;
    g_frame_counters[1].device_ptr_va=0xff00;g_frame_counters[1].counter_off=4;
    *word(0x200)=0x240;*word(0x244)=7;
    tick(100);assert(*word(0x244)==8);
    tick(115);assert(*word(0x244)==8);
    tick(116);assert(*word(0x244)==9);
    clock_calls=0;clock_value=200;xbox_Nv2aFrameCounterFlip();
    assert(clock_calls==1 && g_frame_counter_flip_ms==200 && *word(0x244)==10);
    tick(210);tick(2199);tick(2200);assert(*word(0x244)==10);
    tick(2215);assert(*word(0x244)==11);
    g_frame_counter_flip_ms=0;g_frame_counter_last_ms=0xfffffff8u;
    tick(7);assert(*word(0x244)==11);
    tick(8);assert(*word(0x244)==12);
    *word(0x200)=0xfffffff0u;tick(24);assert(*word(0x244)==12);
    assert(!fb_logs && !apu_warnings && !tiled_warnings);
}
static void diagnostics(void) {
    g_mcpx_memory=calloc(1,0x80000);g_apu_mmio_trapped=1;assert(g_mcpx_memory);
    ((uint32_t*)g_mcpx_memory)[0x30000/4]=1; // DSP windows remain exempt.
    g_tiled_view_size=3*1024*1024;g_tiled_view=calloc(1,g_tiled_view_size);assert(g_tiled_view);
    s_nv2a_trace=1;s_fb_va=0x300;s_fb_pitch=8;s_fb_height=2;
    for(unsigned i=0;i<4;i++)word(0x300)[i]=i+1;
    tick(1000);assert(fb_logs==1 && fb_words==4 && fb_sum && !apu_warnings && !tiled_warnings);
    ((uint32_t*)g_mcpx_memory)[0x100/4]=0x1234;
    ((uint64_t*)g_tiled_view)[1024*1024/8]=1;
    tick(1049);assert(!apu_warnings && !tiled_warnings && fb_logs==1);
    tick(1050);assert(apu_warnings==1 && tiled_warnings==1 && warning_address==XBOX_TILED_BASE+1024*1024);
    assert(warning_value==0x1234);
    tick(1100);assert(apu_warnings==1 && tiled_warnings==1 && fb_logs==1);
    tick(2000);assert(fb_logs==2);
    s_nv2a_trace=0;tick(3000);assert(fb_logs==2);
    s_nv2a_trace=1;s_fb_va=sizeof memory-4;tick(5000);assert(fb_logs==2);
    free(g_mcpx_memory);free(g_tiled_view);
}
static void slices(void) {
    g_tiled_view_size=1024*1024+64;g_tiled_view=calloc(1,g_tiled_view_size);assert(g_tiled_view);
    ((uint64_t*)g_tiled_view)[g_tiled_view_size/8-1]=1;
    tick(1000);assert(!tiled_warnings);
    tick(1049);assert(!tiled_warnings);
    tick(1050);assert(tiled_warnings==1 && warning_address==XBOX_TILED_BASE+1024*1024+56);
    tick(1100);assert(tiled_warnings==1);free(g_tiled_view);
}
static void wrap(void) {
    g_mcpx_memory=calloc(1,0x80000);g_apu_mmio_trapped=1;assert(g_mcpx_memory);
    tick(0);
    for(unsigned i=1;i<16;i++)tick(i*0x10000000u);
    tick(0xffffffdfu);
    ((uint32_t*)g_mcpx_memory)[0x100/4]=1;
    tick(16);assert(!apu_warnings);
    tick(17);assert(apu_warnings==1 && warning_address==XBOX_MCPX_BASE+0x100);
    free(g_mcpx_memory);
}
int main(int argc,char **argv) {
    assert(argc==2);g_memory_offset=(intptr_t)memory;
    if(!strcmp(argv[1],"timers"))timers();
    else if(!strcmp(argv[1],"diagnostics"))diagnostics();
    else if(!strcmp(argv[1],"slices"))slices();
    else if(!strcmp(argv[1],"wrap"))wrap();
    else return 1;
    printf("PASS acknowledgement clock %s: one maintenance-clock sample per entry\n",argv[1]);
}
"""
    args.build_dir.mkdir(parents=True, exist_ok=True)
    source = args.build_dir / "ack_clock.c"
    source.write_bytes(harness.replace("/* LIVE_MAINTENANCE */",live).encode("utf-8"))
    if args.native:
        compiler=shutil.which("cc") or shutil.which("clang")
        if not compiler: parser.error("Native cc or clang is required")
        output=args.build_dir/("ack_clock.exe" if os.name=="nt" else "ack_clock")
        subprocess.run([compiler,str(source),"-O2","-fsanitize=address,undefined","-fno-sanitize-recover=all","-o",str(output)],check=True)
        command=[str(output.resolve())]
    else:
        compiler,node=shutil.which("emcc"),shutil.which("node")
        if not compiler or not node: parser.error("Emscripten and Node are required")
        output=args.build_dir/"ack_clock.js"
        subprocess.run([compiler,str(source),"-O2","-fsanitize=undefined","-fno-sanitize-recover=all","-sENVIRONMENT=node","-o",str(output)],check=True)
        command=[node,str(output.resolve())]
    env={**os.environ,"ASAN_OPTIONS":"detect_leaks=0"}
    for case in ["timers","diagnostics","slices","wrap"]:
        subprocess.run([*command,case],check=True,env=env)


if __name__=="__main__":
    main()
