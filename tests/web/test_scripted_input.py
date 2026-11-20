"""Check real file-queued controller pulses with a controlled SDL clock."""
import argparse
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--native', action='store_true')
parser.add_argument('--build-dir', type=Path, default=root / 'build-web-tests/scripted-input')
args = parser.parse_args()
out = args.build_dir.resolve()
out.mkdir(parents=True, exist_ok=True)
text = (root / 'src/nfl2k5_input_hle.c').read_text(encoding='utf-8')
production = text[text.index('static Uint64 g_last_script_press;'):text.index('static volatile Uint64 s_inject_a_until;')]
source = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint64_t Uint64;
typedef uint16_t WORD;
typedef uint8_t BYTE;
static Uint64 now;
static const char *configured_path="press.txt";
static Uint64 SDL_GetTicks(void){return now;}
static const char *script_getenv(const char *name){assert(!strcmp(name,"NFL2K5_PRESS_FILE"));return configured_path;}
#define getenv script_getenv
#define SDL_strtok_r strtok_r
/* PRODUCTION */
#undef getenv
static void queue(const char *text){FILE *f=fopen("press.txt","w");assert(f);assert(fputs(text,f)>=0);assert(!fclose(f));}
static unsigned poll(void){
    BYTE analog[8]={0};WORD buttons=file_press(analog);unsigned value=buttons;
    for(unsigned i=0;i<8;i++){assert(analog[i]==0 || analog[i]==255);if(analog[i])value|=1u<<(16+i);}
    return value;
}
static void idle(unsigned milliseconds){
    Uint64 end=now+milliseconds;for(;now<end;now+=17)assert(!poll());
}
static void repeated_triggers(unsigned interval){
    queue("rt rt rt rt rt rt rt rt rt rt rt rt rt rt rt rt rt rt rt");
    unsigned edges=0,previous=0;Uint64 began=0,end=now+30000;
    for(;now<end;now+=interval){
        unsigned value=poll();assert(!value || value==(1u<<23));
        if(value){if(!previous){edges++;began=now;}assert(now-began<100);}
        previous=value;
    }
    assert(edges==19 && !previous);
    FILE *f=fopen("press.txt","r");assert(!f);
}
int main(int argc,char **argv){
    (void)argv;remove("press.txt");now=1000;
    if(argc>1){
        configured_path=NULL;queue("a rt start");
        for(;now<5000;now+=17)assert(!poll());
        assert(!g_last_script_press);FILE *f=fopen("press.txt","r");assert(f);fclose(f);remove("press.txt");
        puts("PASS unset script path leaves controller and file untouched");return 0;
    }
    queue("rt");assert(!poll());now=1249;assert(!poll());
    now=1250;assert(poll()==(1u<<23));now=1349;assert(poll()==(1u<<23));
    now=1350;assert(!poll());now=1400;assert(!poll());
    queue("lt rt");now=1500;assert(!poll());now=1600;assert(poll()==(1u<<22));
    /* No stale final pressed sample after a long gap in guest polling. */
    now=5000;assert(!poll());now=5249;assert(!poll());now=5250;assert(poll()==(1u<<23));
    now=5350;assert(!poll());idle(1000);
    const unsigned intervals[]={7,16,33,55,105,333};
    for(unsigned i=0;i<sizeof intervals/sizeof *intervals;i++){repeated_triggers(intervals[i]);idle(1000);}
    const unsigned expected[]={0x10,0x20,1,2,4,8,1u<<16,1u<<17,1u<<18,1u<<19,1u<<20,1u<<21,1u<<22,1u<<23,0x40,0x80,1u<<20,1u<<21};
    queue("start,back up\ndown\tleft right a b x y black white lt rt l3 r3 rb lb");
    unsigned count=0,previous=0;Uint64 end=now+15000;
    for(;now<end;now+=17){unsigned value=poll();if(value && !previous){assert(count<18 && value==expected[count]);count++;}previous=value;}
    assert(count==18 && !previous);idle(1000);
    /* A queued command adds its button without clearing physical input. */
    queue("a");now+=1000;BYTE analog[8]={0};analog[6]=127;
    WORD buttons=file_press(analog);assert(!buttons && analog[0]==255 && analog[6]==127);
    now+=100;analog[0]=0;assert(!file_press(analog) && !analog[0] && analog[6]==127);idle(1000);
    /* Excess words stay bounded by the existing 63-slot queue capacity. */
    char many[512]={0};for(unsigned i=0;i<90;i++)strcat(many,"rt ");queue(many);
    count=previous=0;end=now+30000;
    for(;now<end;now+=17){unsigned value=poll();if(value && !previous)count++;previous=value;}
    assert(count==63 && !previous);
    puts("PASS scripted controller pulses: exact expiry, polling stalls, six cadences, 19-trigger sequences, all mappings, physical input and queue bounds");return 0;
}
'''.replace('/* PRODUCTION */', production)
(out / 'test.c').write_bytes(source.encode('utf-8'))
flags = ['-O2', '-fsanitize=undefined', '-fno-sanitize-recover=undefined']
if args.native:
    compiler = shutil.which('cc') or shutil.which('clang')
    if not compiler:
        parser.error('Native C compiler required')
    binary = out / 'test'
    subprocess.run([compiler, str(out / 'test.c'), *flags, '-fsanitize=address', '-o', str(binary)], check=True)
    command = [str(binary)]
else:
    compiler, node = shutil.which('emcc'), shutil.which('node')
    if not compiler or not node:
        parser.error('Emscripten and Node required')
    binary = out / 'test.js'
    subprocess.run([compiler, str(out / 'test.c'), *flags, '-sENVIRONMENT=node', '-o', str(binary)], check=True)
    command = [node, str(binary)]
subprocess.run(command, cwd=out, check=True, timeout=30)
subprocess.run([*command, '--disabled'], cwd=out, check=True, timeout=30)
