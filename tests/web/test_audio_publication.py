"""Compare production Web/native monitor publication under the same ready-block schedule."""
from pathlib import Path
import argparse,shutil,subprocess
root=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build-dir',type=Path,default=root/'build-web-tests/audio-publication-blocks')
parser.add_argument('--runtime',type=Path,default=root/'external/xboxrecomp')
args=parser.parse_args();out=args.build_dir.resolve();out.mkdir(parents=True,exist_ok=True)
core=(args.runtime/'src/apu/apu_core.c').read_text(encoding='utf-8')
backend=(args.runtime/'src/apu/apu_xaudio2.c').read_text(encoding='utf-8')
a=core.index('void mcpx_apu_monitor_frame(');b=core.index('    if (!g_waveout.initialized) return;',a)
monitor=core[a:b]+'}\n'
a=backend.index('int xa2_get_buffer_size(');getter=backend[a:backend.index('\n}',a)+2]
constants=backend[backend.index('#define XA2_SAMPLE_RATE'):backend.index('static SDL_AudioStream')]
code=r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <assert.h>
#define MIXER_FRAME_SAMPLES 256
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
/* CONSTANTS */
typedef struct {unsigned ep_frame_div;struct {int16_t frame_buf[256][2],submit_buf[1024][2];int submit_n;} monitor;} MCPXAPUState;
static struct {int active;double phase,phase_inc,amplitude;} g_test_tone;
static int g_audio_muted,g_web_audio;
static float g_game_gain=1,g_game_level;
static FILE *packets,*pcm;
static unsigned ready_frame,published,packet_count;
static void mixer_render(int16_t b[][2],int n){(void)b;(void)n;}
static int xa2_is_active(void){return 1;}
static int xa2_submit_samples(const int16_t *data,int frames){
    fprintf(packets,"%s{\"readyFrame\":%u,\"frames\":%d}",packet_count++?",":"",ready_frame,frames);
    assert(fwrite(data,4,frames,pcm)==(size_t)frames);published+=frames;return 1;
}
/* GETTER */
/* MONITOR */
int main(int argc,char **argv){
    if(argc==2){
        MCPXAPUState old={0},fresh={0};packets=fopen("restart.json","w+b");pcm=fopen("restart.pcm","w+b");assert(packets&&pcm);
        g_web_audio=0;
        for(unsigned n=0;n<2;n++){
            old.ep_frame_div=n*8+7;
            for(unsigned i=0;i<256;i++)old.monitor.frame_buf[i][0]=old.monitor.frame_buf[i][1]=-30000;
            mcpx_apu_monitor_frame(&old);
        }
        assert(!published);g_web_audio=!strcmp(argv[1],"restart-web");
        unsigned blocks=g_web_audio?1:4;
        for(unsigned n=0;n<blocks;n++){
            fresh.ep_frame_div=n*8+7;
            for(unsigned i=0;i<256;i++){int16_t s=(int16_t)(n*256+i+1);fresh.monitor.frame_buf[i][0]=s;fresh.monitor.frame_buf[i][1]=-s;}
            mcpx_apu_monitor_frame(&fresh);
        }
        assert(published==blocks*256);rewind(pcm);
        for(unsigned i=0;i<published;i++){int16_t pair[2];assert(fread(pair,4,1,pcm)==1);assert(pair[0]==i+1 && pair[1]==-(int)(i+1));}
        puts("PASS fresh APU instance does not inherit pending PCM from the previous output stream");return 0;
    }
    assert(argc==4);g_web_audio=!strcmp(argv[1],"web");
    unsigned stall=(unsigned)strtoul(argv[2],NULL,10),phase=(unsigned)strtoul(argv[3],NULL,10);
    char name[64];snprintf(name,sizeof name,"%s.json",argv[1]);packets=fopen(name,"wb");assert(packets);
    snprintf(name,sizeof name,"%s.pcm",argv[1]);pcm=fopen(name,"wb");assert(pcm);fputs("[",packets);
    MCPXAPUState d={0};
    for(unsigned batch=0;batch<64;batch++){
        // Identical ready-block schedule: 256 frames per APU batch, with a
        // controlled producer pause followed by release of completed blocks.
        ready_frame=batch*256;if(batch>=phase && ready_frame<phase*256+stall)ready_frame=phase*256+stall;
        for(unsigned i=0;i<256;i++){int16_t s=(int16_t)((batch*256+i)%8191+1);d.monitor.frame_buf[i][0]=s;d.monitor.frame_buf[i][1]=-s;}
        for(unsigned sub=0;sub<8;sub++){
            d.ep_frame_div=batch*8+sub;unsigned before=published;mcpx_apu_monitor_frame(&d);
            if(sub<7)assert(published==before);
        }
        for(unsigned i=0;i<256;i++)assert(!d.monitor.frame_buf[i][0]&&!d.monitor.frame_buf[i][1]);
    }
    assert(published==16384);fputs("]\n",packets);assert(!fclose(packets));assert(!fclose(pcm));
    printf("PASS production monitor %s: %u exact frames, %u packets, buffer target %d\n",argv[1],published,packet_count,xa2_get_buffer_size());
}
'''.replace('/* CONSTANTS */',constants).replace('/* GETTER */',getter).replace('/* MONITOR */',monitor)
(out/'test.c').write_bytes(code.encode('utf-8'))
subprocess.run([shutil.which('emcc') or 'emcc',str(out/'test.c'),'-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',
                '-sENVIRONMENT=node','-sNODERAWFS=1','-o',str(out/'test.js')],check=True)
node=shutil.which('node') or 'node'
for mode in ('restart-web','restart-native'):subprocess.run([node,str(out/'test.js'),mode],cwd=out,check=True)
for stall_ms in (0,8,16,24,28,40,56):
    for phase in (8,9,10,11):
        case=out/f'stall-{stall_ms}-phase-{phase}';case.mkdir(exist_ok=True)
        for mode in ('native','web'):
            subprocess.run([node,str(out/'test.js'),mode,str(stall_ms*48),str(phase)],cwd=case,check=True)
        subprocess.run([node,str(root/'tests/web/test_audio_publication.cjs'),str(case),str(stall_ms),str(phase)],check=True)
print('PASS 28 controlled stall/phase pairs; 458752 stereo frames preserved per monitor path')
