"""Verify the real AudioWorklet submission path preserves the supplied PCM."""
from pathlib import Path
import shutil
import subprocess
import re

root = Path(__file__).resolve().parents[2]
source = (root / 'external/xboxrecomp/src/apu/apu_xaudio2.c').read_text(encoding='utf-8')
constants = source[source.index('#define XA2_SAMPLE_RATE'):source.index('static SDL_AudioStream')]
submit = source[source.index('int xa2_submit_samples('):source.index('int xa2_get_buffer_size(')]
harness = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <assert.h>
typedef uint64_t Uint64;
/* CONSTANTS */
static int g_xa2_initialized=1,g_web_audio=1,g_xa2_frames_written;
static void *g_sdl_stream,*g_tap_mutex;
static FILE *g_tap;
static void (*g_capture_mix)(int16_t *,int);
static uint32_t queued,written,calls;
static int16_t output[8192];
static uint32_t web_audio_queued(void) { return queued; }
static uint32_t web_audio_put(const int16_t *samples,uint32_t count) {
    assert((written+count)*2<=sizeof output/sizeof output[0]);
    memcpy(output+written*2,samples,count*4);written+=count;calls++;return count;
}
static void SDL_LockMutex(void *m) { (void)m; }
static void SDL_UnlockMutex(void *m) { (void)m; }
static Uint64 test_ticks=1;
static Uint64 SDL_GetTicks(void) { return test_ticks; }
static int SDL_GetAudioStreamQueued(void *s) { (void)s;abort(); }
static int SDL_PutAudioStreamData(void *s,const void *p,int n) { (void)s;(void)p;(void)n;abort(); }
/* SUBMIT */
int main(int argc,char **argv) {
    int16_t pcm[1024][2];
    for(int i=0;i<1024;i++) {pcm[i][0]=(int16_t)(100+i);pcm[i][1]=(int16_t)(-100-i);}
    if(argc>1) {
        /* After startup, one retained frame is dry; two frames are readable. */
        queued=2048;
        for(int i=0;i<51;i++){written=0;assert(xa2_submit_samples(&pcm[0][0],1024));}
        const uint32_t depths[]={1,2,0};
        for(unsigned i=0;i<3;i++) {
            queued=depths[i];written=0;test_ticks+=10000;
            assert(xa2_submit_samples(&pcm[0][0],1024));
            assert(!memcmp(output,pcm,sizeof pcm));
        }
        return 0;
    }
    for(queued=0;queued<=2048;queued+=512) {
        written=calls=0;
        assert(xa2_submit_samples(&pcm[0][0],1024)==1);
        assert(written==1024 && calls==1);
        assert(!memcmp(output,pcm,sizeof pcm));
    }
    puts("ok: startup and low queues preserve exact PCM without injected silence");
    queued=XA2_MAX_QUEUED_BYTES/XA2_FRAME_BYTES;written=calls=0;
    assert(!xa2_submit_samples(&pcm[0][0],1024));
    assert(!written && !calls);
    queued=0;written=calls=0;
    assert(xa2_submit_samples(&pcm[0][0],17));
    assert(written==17 && !memcmp(output,pcm,17*4));
    puts("ok: full queues reject writes; short submissions keep their exact frame count");
}
'''.replace('/* CONSTANTS */', constants).replace('/* SUBMIT */', submit)
out = root / 'build-web-tests/audio-submission'
out.mkdir(parents=True, exist_ok=True)
(out / 'test.c').write_text(harness, encoding='utf-8')
subprocess.run([shutil.which('emcc') or 'emcc', str(out / 'test.c'), '-O2',
                '-sENVIRONMENT=node', '-o', str(out / 'test.js')], check=True)
subprocess.run([shutil.which('node') or 'node', str(out / 'test.js')], check=True)
diagnostic = subprocess.run([shutil.which('node') or 'node', str(out / 'test.js'), 'diagnostics'],
                            check=True, capture_output=True, text=True)
counts = re.findall(r'starved_submissions=(\d+) queued_bytes=(\d+)', diagnostic.stderr)
assert counts == [('1', '4'), ('1', '8'), ('2', '0')], diagnostic.stderr
print('ok: producer starvation distinguishes one retained frame from two readable frames')
