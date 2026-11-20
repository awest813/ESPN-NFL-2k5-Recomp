"""Check the live committed-texture index; optionally benchmark the prior lookup."""
import argparse
from pathlib import Path
import shutil
import subprocess


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=Path, default=root / 'build-web-tests/texture-lookup')
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--benchmark', action='store_true')
    args = parser.parse_args()
    out = args.build_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    text = (root / 'external/xboxrecomp/src/kernel/sdlgpu/sdlgpu_texture.inc.c').read_text(encoding='utf-8')
    types = text[text.index('#define SG_MAX_TEXTURES'):text.index('/* Index committed textures')]
    index = text[text.index('#define SG_TEXTURE_BUCKETS'):text.index('#define SG_HASH_MEMO')]
    commit = text[text.index('static void sg_texture_commit('):]
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
typedef struct SDL_GPUTexture SDL_GPUTexture;
typedef struct SDL_GPUSampler SDL_GPUSampler;
/* TYPES */
/* INDEX */
/* COMMIT */
static uint64_t queries,random_state=0x9e3779b97f4a7c15ULL;
static uint64_t random64(void){random_state^=random_state<<13;random_state^=random_state>>7;random_state^=random_state<<17;return random_state;}
static SgCachedTexture *reference(uint64_t key,uint32_t w,uint32_t h,uint32_t layers){
    if(!key)return NULL;
    for(unsigned i=0;i<SG_MAX_TEXTURES;i++){
        SgCachedTexture *c=&s_sg_textures[i];
        if(c->key==key && c->w==w && c->h==h && c->layers==layers)return c;
    }
    return NULL;
}
static void check(uint64_t key,uint32_t w,uint32_t h,uint32_t layers){
    SgCachedTexture *actual=sg_texture_find(key,w,h,layers),*expected=reference(key,w,h,layers);
    assert(!!actual==!!expected);
    if(actual){assert(actual>=s_sg_textures && actual<s_sg_textures+SG_MAX_TEXTURES);
        assert(actual->key==key && actual->w==w && actual->h==h && actual->layers==layers);}
    queries++;
}
static void check_links(void){
    unsigned seen[SG_MAX_TEXTURES]={0};
    for(unsigned b=0;b<SG_TEXTURE_BUCKETS;b++){
        unsigned previous=0,steps=0;
        for(unsigned ref=s_sg_texture_buckets[b];ref;ref=s_sg_texture_links[ref-1].next){
            assert(ref<=SG_MAX_TEXTURES && ++steps<=SG_MAX_TEXTURES);
            unsigned i=ref-1;SgTextureLink *link=&s_sg_texture_links[i];
            assert(!seen[i]++ && link->previous==previous && link->bucket==b+1);
            assert(s_sg_textures[i].key && sg_texture_bucket(s_sg_textures[i].key)==b);
            previous=ref;
        }
        assert(steps==s_sg_texture_bucket_count[b]);
        unsigned hint=s_sg_texture_hint[b];
        if(hint)assert(hint<=SG_MAX_TEXTURES && seen[hint-1] && sg_texture_bucket(s_sg_textures[hint-1].key)==b);
    }
    for(unsigned i=0;i<SG_MAX_TEXTURES;i++)assert(!!s_sg_textures[i].key==!!seen[i]);
}
static void reset(void){for(unsigned i=0;i<SG_MAX_TEXTURES;i++)sg_texture_invalidate(&s_sg_textures[i]);check_links();}
static void publish(unsigned slot,uint64_t key,uint32_t w,uint32_t h,uint32_t layers,uint32_t epoch){
    SgCachedTexture *c=&s_sg_textures[slot];sg_texture_invalidate(c);
    c->w=w;c->h=h;c->layers=layers;c->levels=3;c->epoch_used=epoch;
    SgTextureUse use={.pending=c,.pending_key=key};
    sg_texture_commit(&use);assert(!use.pending && c->key==key);
    sg_texture_commit(&use);assert(!use.pending && c->key==key);
}
static void audit_all(void){
    check_links();
    for(unsigned i=0;i<SG_MAX_TEXTURES;i++){
        SgCachedTexture *c=&s_sg_textures[i];
        check(c->key,c->w,c->h,c->layers);
        check(c->key,c->w^8192,c->h,c->layers);
        check(c->key,c->w,c->h^8192,c->layers);
        check(c->key,c->w,c->h,c->layers^8);
    }
}
static void correctness(void){
    check(1,64,64,1);
    for(unsigned i=0;i<SG_MAX_TEXTURES;i++)publish(i,1+(uint64_t)i*SG_TEXTURE_BUCKETS,64,64,1,10);
    audit_all();
    /* Unlink head, middle and tail of a 512-node collision chain. */
    const unsigned removals[]={511,256,0};
    for(unsigned k=0;k<3;k++){
        unsigned i=removals[k];uint64_t old=s_sg_textures[i].key;
        sg_texture_invalidate(&s_sg_textures[i]);sg_texture_invalidate(&s_sg_textures[i]);
        check(old,64,64,1);audit_all();publish(i,UINT64_MAX-k,32,32,6,UINT32_MAX);audit_all();
    }
    /* Identical identities may occupy different uploaded slots. */
    const unsigned duplicates[]={14,200,499};
    for(unsigned k=0;k<3;k++)publish(duplicates[k],0x1122334455667788ULL,128,128,6,7);
    for(unsigned k=0;k<3;k++){
        SgCachedTexture *c=sg_texture_find(0x1122334455667788ULL,128,128,6);assert(c);
        sg_texture_invalidate(c);check(0x1122334455667788ULL,128,128,6);check_links();
    }
    assert(!sg_texture_find(0x1122334455667788ULL,128,128,6));
    /* A staged upload is invisible until the actual production commit. */
    SgCachedTexture *c=&s_sg_textures[17];sg_texture_invalidate(c);
    c->w=c->h=256;c->layers=1;c->epoch_used=23;
    SgTextureUse pending={.pending=c,.pending_key=0x778899aabbccddeeULL};
    assert(!sg_texture_find(pending.pending_key,256,256,1));
    sg_texture_commit(&pending);assert(!pending.pending);check(c->key,256,256,1);
    publish(18,0x778899aabbccddffULL,64,64,1,23);
    publish(19,0x8877665544332211ULL,64,64,1,UINT32_MAX);
    sg_texture_invalidate_epoch(23);assert(!s_sg_textures[17].key && !s_sg_textures[18].key);
    assert(s_sg_textures[19].key);audit_all();
    sg_texture_invalidate_epoch(UINT32_MAX);audit_all();reset();
    /* Cross the small-chain/dense-scan threshold in both directions. */
    for(unsigned i=0;i<6;i++){publish(i,1+(uint64_t)i*SG_TEXTURE_BUCKETS,64,64,1,1);audit_all();check(1+9000ULL*SG_TEXTURE_BUCKETS,64,64,1);}
    for(unsigned i=0;i<6;i++){sg_texture_invalidate(&s_sg_textures[i]);audit_all();check(1+(uint64_t)i*SG_TEXTURE_BUCKETS,64,64,1);}
    /* Equal hashes with different dimensions/layers must stay distinct. */
    for(unsigned i=0;i<6;i++)publish(i,123,64u<<(i%3),64u<<(i%3),i&1?6:1,1);
    audit_all();check(123,64,64,3);reset();
    for(unsigned iteration=0;iteration<200000;iteration++){
        uint64_t r=random64();unsigned i=(unsigned)r&(SG_MAX_TEXTURES-1);SgCachedTexture *slot=&s_sg_textures[i];
        switch((r>>12)%6){
        case 0:case 1:{
            uint64_t key=random64()|1;
            if(iteration%7==0)key=1+((uint64_t)(iteration%1024))*SG_TEXTURE_BUCKETS;
            publish(i,key,1+((r>>24)&4095),1+((r>>36)&4095),(r>>20)&1?6:1,(uint32_t)(r>>32));break;
        }
        case 2:sg_texture_invalidate(slot);break;
        case 3:check(slot->key,slot->w,slot->h,slot->layers);break;
        case 4:check(random64(),64,64,1);break;
        case 5:check(slot->key,slot->w^8192,slot->h,slot->layers);break;
        }
        if(iteration%1024==0)audit_all();
    }
    audit_all();reset();
    publish(0,0x100000001ULL,1,1,1,0);sg_texture_invalidate_epoch(0);assert(!sg_texture_find(0x100000001ULL,1,1,1));
    check_links();printf("PASS %llu texture lookups against linear oracle: collisions, duplicates, pending commits, eviction, failed epochs, wrap and churn\n",(unsigned long long)queries);
}
/* Prior direct hint plus linear fallback, retained only as a benchmark baseline. */
static uint16_t legacy_hints[2048];
static SgCachedTexture *legacy_find(uint64_t key,uint32_t w,uint32_t h,uint32_t layers){
    uint32_t b=(uint32_t)(key^(key>>32))&2047,ref=legacy_hints[b];
    if(ref){SgCachedTexture *c=&s_sg_textures[ref-1];if(c->key==key&&c->w==w&&c->h==h&&c->layers==layers)return c;}
    for(unsigned i=0;i<SG_MAX_TEXTURES;i++){SgCachedTexture *c=&s_sg_textures[i];
        if(c->key==key&&c->w==w&&c->h==h&&c->layers==layers){legacy_hints[b]=(uint16_t)(i+1);return c;}}
    return NULL;
}
typedef SgCachedTexture *(*Lookup)(uint64_t,uint32_t,uint32_t,uint32_t);
static double milliseconds(void){struct timespec ts;assert(!clock_gettime(CLOCK_MONOTONIC,&ts));return ts.tv_sec*1000.0+ts.tv_nsec/1e6;}
static volatile uint64_t observed;
static double benchmark(int current,int scenario){
    reset();memset(legacy_hints,0,sizeof legacy_hints);random_state=0x123456789abcdefULL;
    for(unsigned i=0;i<SG_MAX_TEXTURES;i++){
        uint64_t key=(scenario==2 || scenario==4)?1+(uint64_t)i*2048:random64()|1;
        if(current)publish(i,key,64,64,1,1);
        else s_sg_textures[i]=(SgCachedTexture){.key=key,.w=64,.h=64,.layers=1};
    }
    Lookup volatile lookup=current?sg_texture_find:legacy_find;
    /* Warm the same stable set before measuring. */
    for(unsigned i=0;i<SG_MAX_TEXTURES;i++){SgCachedTexture *c=&s_sg_textures[i];assert(lookup(c->key,64,64,1));}
    uint64_t sum=0;double start=milliseconds();
    for(unsigned i=0;i<200000;i++){
        unsigned slot=scenario==4?511:(i*3571u+i/17u)&(SG_MAX_TEXTURES-1);SgCachedTexture *c=&s_sg_textures[slot];
        if(scenario==3 && i%16==0){
            uint64_t key=0x7654321000000001ULL+(uint64_t)i*4097;
            if(current)publish(slot,key,64,64,1,1);else c->key=key;
        }
        uint64_t key=c->key;
        if(scenario==1 && i%20==0)key^=0xabcdeffedcba0000ULL;
        SgCachedTexture *found=lookup(key,64,64,1);sum+=found?found->key:0;
    }
    double elapsed=milliseconds()-start;observed^=sum;
    /* Compare checksums across old/new runs without including oracle work. */
    static uint64_t old_sum[5];if(!current)old_sum[scenario]=sum;else assert(sum==old_sum[scenario]);
    return elapsed;
}
int main(int argc,char **argv){
    (void)argv;correctness();
    if(argc>1)for(int scenario=0;scenario<5;scenario++){
        benchmark(0,scenario);benchmark(1,scenario);
        for(unsigned round=0;round<7;round++){
            double before,after;
            if(round&1){after=benchmark(1,scenario);before=benchmark(0,scenario);}
            else{before=benchmark(0,scenario);after=benchmark(1,scenario);}
            printf("BENCH scenario=%d round=%u legacy=%.4fms indexed=%.4fms\n",scenario,round,before,after);
        }
    }
    return 0;
}
'''.replace('/* TYPES */', types).replace('/* INDEX */', index).replace('/* COMMIT */', commit)
    source = out / 'test.c'
    source.write_bytes(code.encode('utf-8'))
    flags = ['-O3'] if args.benchmark else ['-O2', '-fsanitize=undefined', '-fno-sanitize-recover=undefined']
    if args.native:
        compiler = shutil.which('cc') or shutil.which('clang')
        if not compiler:
            parser.error('Native C compiler required')
        binary = out / 'test'
        subprocess.run([compiler, str(source), *flags, *([] if args.benchmark else ['-fsanitize=address']),
                        '-o', str(binary)], check=True)
        subprocess.run([str(binary), *(['--benchmark'] if args.benchmark else [])], check=True, timeout=90)
    else:
        compiler, node = shutil.which('emcc'), shutil.which('node')
        if not compiler or not node:
            parser.error('Emscripten and Node required')
        binary = out / 'test.js'
        subprocess.run([compiler, str(source), *flags, '-sENVIRONMENT=node', '-o', str(binary)], check=True)
        subprocess.run([node, str(binary), *(['--benchmark'] if args.benchmark else [])], check=True, timeout=90)


if __name__ == '__main__':
    main()
