/* Differential inputs for the production WGSL translator and CPU oracle. */
#include <stdarg.h>
/* LIVE_GENERATOR */
#include "vp_cache_collision.h"

static uint32_t random_seed = 0x8cae2193u;
static uint32_t rng(void) {
    random_seed ^= random_seed << 13;
    random_seed ^= random_seed >> 17;
    random_seed ^= random_seed << 5;
    return random_seed;
}
static float random_float(void) { return ((int)(rng() % 2001) - 1000) / 701.0f; }
static void save(const char *name, const void *data, size_t bytes) {
    FILE *f = fopen(name, "wb");
    if (!f || fwrite(data, 1, bytes, f) != bytes) abort();
    fclose(f);
}
static void compact_vertex_case(void) {
    typedef struct { unsigned location, buffer_slot, format, offset; } SDL_GPUVertexAttribute;
    typedef unsigned Uint32;
    enum { SDL_GPU_VERTEXELEMENTFORMAT_FLOAT4 = 0 };
    struct { unsigned inmask; } s_sg_vp[1] = {{(1u << 0) | (1u << 3) | (1u << 9)}};
    struct Key { unsigned vs; } key_value = {1};
    const struct Key *key = &key_value;
    const int vp = 1;
    /* LIVE_LAYOUT */
    FILE *f = fopen("compact.layout.json", "w");
    fprintf(f, "{\"stride\":%u,\"attributes\":[", sg_vp_input_stride(inmask));
    for (unsigned a = 0; a < 16; a++)
        fprintf(f, "%s{\"shaderLocation\":%u,\"offset\":%u,\"format\":\"float32x4\"}",
                a ? "," : "", vp_attrs[a].location, vp_attrs[a].offset);
    fprintf(f, "]}"); fclose(f);
    s_vp.start = 0;
    const unsigned inputs[3] = {0, 3, 9}, outputs[3] = {0, 3, 9};
    for (unsigned i = 0; i < 3; i++) {
        uint32_t *t = s_vp.prog[i];
        t[0] = 0; t[1] = (1u << 21) | (inputs[i] << 9) | 0x1bu;
        t[2] = 2u << 26;
        t[3] = (15u << 12) | (1u << 11) | (outputs[i] << 3) | (i == 2);
    }
    char *source = sg_vp_translate_wgsl(0);
    if (!source) abort();
    save("compact.wgsl", source, strlen(source)); free(source);
    float vertices[3][3][4] = {
        {{0,0,0.5,1}, {0.25,0.5,0.75,1}, {0.125,0.25,0.25,0}},
        {{8,0,0.5,1}, {0.25,0.5,0.75,1}, {0.125,0.25,0.25,0}},
        {{0,8,0.5,1}, {0.25,0.5,0.75,1}, {0.125,0.25,0.25,0}},
    };
    save("compact.vertices.bin", vertices, sizeof vertices);
    float uniforms[196][4] = {0};
    uniforms[192][0] = uniforms[192][1] = 4; uniforms[192][2] = 1;
    save("compact.uniforms.bin", uniforms, sizeof uniforms);
}
int main(void) {
    enum { CASES = 86, VERTICES = 32 };
    for (unsigned test = 0; test < CASES; test++) {
        s_vp.start = test >= 64 ? 0 : test % 5;
        unsigned length = test >= 64 ? 0 : test < 22 ? 1 : 12;
        for (unsigned i = 0; i < length; i++) {
            uint32_t *t = s_vp.prog[s_vp.start + i];
            unsigned mac = test < 14 ? test : test < 22 ? 0 : rng() % 14;
            unsigned ilu = test < 14 ? 0 : test < 22 ? test - 14 : rng() % 8;
            t[0] = 0;
            t[1] = (rng() & 0x1ffu) | ((rng() % 16) << 9) | ((rng() % 192) << 13) | (mac << 21) | (ilu << 25);
            t[2] = rng();
            t[3] = (rng() & 0xfff7f000u) | ((rng() % 16) << 3) | (1u << 11) | ((i + 1 == length) ? 1 : 0);
            /* Exercise relative addressing in longer programs and use a
             * finite input for ARL so host float-to-int is well-defined. */
            if (length > 1) t[3] |= (rng() & 1u) << 1;
            if (mac == 13) {
                t[1] &= ~(1u << 8);
                t[2] = (t[2] & ~(3u << 26)) | (2u << 26);
            }
            if (length == 1) {
                t[1] = (mac << 21) | (ilu << 25) | (2u << 13) | 0x1bu;
                t[2] = (2u << 26) | (3u << 11) | (1u << 23) | (2u << 21) | (3u << 19)
                     | (1u << 6) | (2u << 4) | (3u << 2);
                t[3] = (2u << 28) | (15u << 24) | (15u << 16) | (15u << 12) | (1u << 11)
                     | (3u << 3) | (ilu ? 4u : 0u) | 1u;
            }
        }
        if (test == 64 || test == 65) memcpy(s_vp.prog, vp_cache_collision[test - 64], sizeof vp_cache_collision[0]);
        if (test == 66) {
            uint32_t lit[4] = {0, 7u << 25, (1u << 6) | (2u << 4) | (3u << 2),
                (2u << 28) | (15u << 16) | (15u << 12) | (1u << 11) | (3u << 3) | 5u};
            memcpy(s_vp.prog[0], lit, sizeof lit);
        }
        if (test >= 67 && test <= 70) {
            uint32_t mac=test&1?2u:4u,reverse=test>=69;
            uint32_t *t=s_vp.prog[0];
            t[0]=0;t[1]=(mac<<21)|(2u<<13)|0x1bu;
            t[2]=((reverse?1u:2u)<<26)|((reverse?2u:1u)<<11)
                |(1u<<21)|(2u<<19)|(3u<<17)|0x6cu;
            t[3]=(3u<<28)|(15u<<12)|(1u<<11)|(3u<<3)|1u;
        }
        if (test >= 71 && test <= 74) {
            uint32_t ilu=test==74?7u:test-69u;
            uint32_t *t=s_vp.prog[0];t[0]=0;t[1]=ilu<<25;t[2]=0x6cu;
            t[3]=(2u<<28)|(15u<<16)|(15u<<12)|(1u<<11)|(3u<<3)|5u;
        }
        if(test>=75 && test<=78) {
            uint32_t *t=s_vp.prog[0];t[0]=0;t[1]=((test-70u)<<21)|(2u<<13)|0x1bu;
            t[2]=(2u<<26)|(1u<<11)|0x6cu;
            t[3]=(3u<<28)|(15u<<12)|(1u<<11)|(3u<<3)|1u;
        }
        if(test==79) {
            uint32_t *t=s_vp.prog[0];t[0]=0;t[1]=7u<<25;t[2]=0x6cu;
            t[3]=(2u<<28)|(15u<<16)|(15u<<12)|(1u<<11)|(3u<<3)|5u;
        }
        if(test>=80) {
            memset(s_vp.prog,0,sizeof s_vp.prog);
            s_vp.prog[0][1]=(1u<<21)|(1u<<9)|0x1bu;
            s_vp.prog[0][2]=2u<<26;s_vp.prog[0][3]=15u<<24;
            unsigned mac=test<84?11+(test&1):test-75;
            s_vp.prog[1][1]=(mac<<21)|((test==82 || test==83)?1u<<8:0)|0x1bu;
            s_vp.prog[1][2]=(2u<<26)|(1u<<11)|(1u<<21)|(2u<<19)|(3u<<17);
            s_vp.prog[1][3]=(15u<<12)|(1u<<11)|(3u<<3)|1u;
        }
        for (unsigned i = 0; i < 192; i++)
            for (unsigned k = 0; k < 4; k++) s_vp.c[i][k] = random_float();
        float inputs[VERTICES][16][4], outputs[VERTICES][29][4];
        for (unsigned i = 0; i < VERTICES; i++) {
            for (unsigned a = 0; a < 16; a++)
                for (unsigned k = 0; k < 4; k++) inputs[i][a][k] = random_float();
            if (test == 66) {
                inputs[i][0][0] = i & 1 ? -1.0f : 1.0f;
                inputs[i][0][1] = (float[]){0.0f,-1.0f,0.5f,1.0f}[(i / 2) % 4];
                inputs[i][0][3] = (float[]){-1.0f,0.0f,1.0f,127.0f}[i / 8];
            }
            if (test >= 67 && test <= 70) {
                inputs[i][0][0]=i&1?-INFINITY:INFINITY;inputs[i][0][1]=NAN;
                inputs[i][0][2]=-0.0f;inputs[i][0][3]=1.0f;
            }
            if (test >= 71 && test <= 73) {
                const float scalars[]={0.0f,-0.0f,INFINITY,-INFINITY,1.0f,-1.0f,2.0f,-2.0f,NAN};
                unsigned at=i%9;
                if(test==73) {at=i%7;if(at==6)at=8;}
                inputs[i][0][0]=scalars[at];
            }
            if (test == 74) {
                inputs[i][0][0]=1;inputs[i][0][1]=1.25f;
                inputs[i][0][3]=(float[]){128,-128,INFINITY,-INFINITY}[i%4];
            }
            if(test>=75 && test<=78) {
                inputs[i][0][0]=INFINITY;inputs[i][0][1]=NAN;inputs[i][0][2]=-0.0f;inputs[i][0][3]=1;
            }
            if(test==79) {
                inputs[i][0][0]=1;inputs[i][0][1]=(float[]){0,-1,NAN,1}[i%4];inputs[i][0][3]=0;
            }
            if(test>=80) {
                const uint32_t classes[]={0xffc00000u,0xff800000u,0xc0000000u,0x80000000u,0,0x40000000u,0x7f800000u,0x7fc00000u};
                unsigned n=test<84?8:6;
                for(unsigned k=0;k<4;k++) {
                    unsigned pair=(i*4+k)%(n*n),a=pair/n,b=pair%n;
                    /* Exclude unspecified NaN self-order. */
                    unsigned rank=(test==82 || test==83)?7-a:a;
                    if(test<84 && rank==b && (b==0 || b==7))b=3;
                    memcpy(&inputs[i][0][k],&classes[a+(test>=84)],4);
                    memcpy(&inputs[i][1][k],&classes[b+(test>=84)],4);
                }
            }
            vp_run(inputs[i], outputs[i]);
            if (test >= 67 && test <= 70) for(unsigned k=0;k<4;k++) {
                float expected=test&1?0.0f:s_vp.c[2][k];
                if(outputs[i][3][k]!=expected || ((test&1) && signbit(outputs[i][3][k]))) abort();
            }
            if(test>=75 && test<=79) {
                float expected[4]={0};
                if(test==78){expected[0]=1;expected[2]=-0.0f;}
                if(test==79)for(unsigned k=0;k<4;k++)expected[k]=1;
                if(memcmp(outputs[i][3],expected,sizeof expected))abort();
            }
            if(test>=80)for(unsigned k=0;k<4;k++) {
                float a=inputs[i][0][k],b=inputs[i][1][k],expected;
                if(test<84) {
                    unsigned pair=(i*4+k)%64,arank=pair/8,brank=pair%8;
                    if(test==82 || test==83)arank=7-arank;
                    if(arank==brank && (brank==0 || brank==7))brank=3;
                    expected=test&1?arank>=brank:arank<brank;
                } else expected=test==84?(a<b?a:b):(a>=b?a:b);
                if(memcmp(&outputs[i][3][k],&expected,4))abort();
            }
            memcpy(outputs[i][16], s_vp_dbg_r, sizeof s_vp_dbg_r);
        }
        char *source = sg_vp_translate_wgsl(s_vp.start);
        if (!source) return 1;
        char name[96];
        snprintf(name, sizeof name, "case-%03u.wgsl", test); save(name, source, strlen(source)); free(source);
        snprintf(name, sizeof name, "case-%03u.constants.bin", test); save(name, s_vp.c, sizeof s_vp.c);
        snprintf(name, sizeof name, "case-%03u.inputs.bin", test); save(name, inputs, sizeof inputs);
        snprintf(name, sizeof name, "case-%03u.expected.bin", test); save(name, outputs, sizeof outputs);
        if((test>=71 && test<=73) || test>=75) {snprintf(name,sizeof name,"case-%03u.strict",test);save(name,"",0);}
    }
    compact_vertex_case();
    s_vp.start = 0;
    memset(s_vp.prog, 0, sizeof s_vp.prog);
    s_vp.prog[0][1] = 1u << 21;
    s_vp.prog[0][3] = (15u << 12) | 1u; /* MOV writes c0 */
    if (sg_vp_translate_wgsl(0)) return 2;
    if (sg_vp_translate_wgsl(VP_PROG_LEN)) return 3;
    puts("Generated 86 WGSL programs with CPU references; constant writes correctly refused");
    return 0;
}
