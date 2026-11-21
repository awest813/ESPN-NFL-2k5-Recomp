/* Differential inputs for the production WGSL translator and CPU oracle. */
#include <stdarg.h>
#include <stddef.h>
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
static void compact_line_depth_case(unsigned mask, const SgVpConstants *constants) {
    char *source=sg_vp_translate_line_wgsl(0,mask,constants);if(!source)abort();
    save("compact-line.wgsl",source,strlen(source));free(source);
    save("compact-line-fragment.wgsl",k_sg_xf_linevp_frag_wgsl,strlen(k_sg_xf_linevp_frag_wgsl));
    save("depth16-fragment.wgsl",k_sg_xf_frag_wgsl,strlen(k_sg_xf_frag_wgsl));
    static uint32_t reference[65536];
    for(unsigned n=0;n<65536;n++){float value=depth16_clear_reference(n);memcpy(&reference[n],&value,4);}
    save("depth16-reference.bin",reference,sizeof reference);
    FILE *f=fopen("compact-line-depth.json","wb");if(!f)abort();
    size_t info_offset = sg_vp_constant_slots(constants) * sizeof s_vp.c[0];
    fprintf(f,"{\"mask\":%u,\"vertexUniformBytes\":%zu,\"infoOffset\":%zu,\"shadeBytes\":%zu,\"depthOffset\":%zu,\"cases\":[",
            mask,info_offset+80,info_offset,sizeof(SgXfShade),offsetof(SgXfShade,depth));
    unsigned count=0;const unsigned probes[]={20,32,44};
    for(unsigned bits=16;bits<=24;bits+=8)for(unsigned n=0;n<sizeof depth_line_cases/sizeof *depth_line_cases;n++)
    for(unsigned w=0;w<2;w++)for(unsigned clip=0;clip<2;clip++)for(unsigned p=0;p<3;p++) {
        DepthLineCase adjusted=depth_line_case(n,bits);const DepthLineCase *c=&adjusted;int visible;
        unsigned integer=depth_line_reference(c,probes[p],w,clip,&visible);
        fprintf(f,"%s{\"bits\":%u,\"x\":[%.9g,%.9g],\"y\":[%.9g,%.9g],\"depth\":[%.9g,%.9g],\"minimum\":%.9g,\"maximum\":%.9g,\"w\":%u,\"clip\":%u,\"probe\":%u,\"probeY\":%u,\"integer\":%u,\"visible\":%d}",
                count++?",":"",bits,c->x[0],c->x[1],c->y[0],c->y[1],c->depth[0],c->depth[1],c->minimum,c->maximum,w,clip,depth_line_probe_x(c,probes[p]),depth_line_probe_y(c,probes[p]),integer,visible);
    }
    fputs("]}\n",f);fclose(f);
    f=fopen("compact-triangle-depth.json","wb");if(!f)abort();
    fprintf(f,"{\"mask\":%u,\"vertexUniformBytes\":%zu,\"infoOffset\":%zu,\"shadeBytes\":%zu,\"depthOffset\":%zu,\"cases\":[",
            mask,info_offset+64,info_offset,sizeof(SgXfShade),offsetof(SgXfShade,depth));
    count=0;
    for(unsigned bits=16;bits<=24;bits+=8)for(unsigned w=0;w<2;w++)for(unsigned clip=0;clip<2;clip++) {
        const DepthQuantizationCase *cases=bits==16?depth16_quantization_cases:depth_quantization_cases;
        unsigned length=bits==16?sizeof depth16_quantization_cases/sizeof *cases:sizeof depth_quantization_cases/sizeof *cases;
        for(unsigned n=0;n<=length;n++) {
            int varying=n==length;if(!varying && w && cases[n].input==0)continue;
            float z[3];unsigned integer;
            if(varying) {
                z[0]=w?4:1.25f;z[1]=w?16:4.75f;z[2]=w?32:8.5f;
                /* At (20.5,20.5), weights are exactly (1/2,1/4,1/4).
                 * Z = 3.9375; harmonic W = 128/19, independently floored. */
                integer=w?6:3;
            } else {z[0]=z[1]=z[2]=cases[n].input;integer=cases[n].integer;}
            fprintf(f,"%s{\"bits\":%u,\"x\":[8.5,56.5,8.5],\"y\":[8.5,8.5,56.5],\"depth\":[%.9g,%.9g,%.9g],\"minimum\":0,\"maximum\":%u,\"w\":%u,\"clip\":%u,\"probe\":20,\"probeY\":20,\"integer\":%u,\"visible\":1}",
                    count++?",":"",bits,z[0],z[1],z[2],bits==16?65535u:16777215u,w,clip,integer);
        }
    }
    fputs("]}\n",f);fclose(f);
}

static void compact_vertex_case(void) {
    typedef struct { unsigned location, buffer_slot, format, offset; } SDL_GPUVertexAttribute;
    typedef unsigned Uint32;
    enum { SDL_GPU_VERTEXELEMENTFORMAT_FLOAT4 = 0 };
    struct { unsigned inmask; } s_sg_vp[1] = {{0}};
    struct Key { unsigned vs; } key_value = {1};
    const struct Key *key = &key_value;
    const int vp = 1;
    s_vp.start = 0;
    const unsigned inputs[3] = {0, 3, 9}, outputs[3] = {0, 3, 9};
    for (unsigned i = 0; i < 3; i++) {
        uint32_t *t = s_vp.prog[i];
        t[0] = 0; t[1] = (1u << 21) | (inputs[i] << 9) | 0x1bu;
        t[2] = 2u << 26;
        t[3] = (15u << 12) | (1u << 11) | (outputs[i] << 3) | 0u;
    }
    // A terminal NOP encodes v12, which no operation actually reads.
    s_vp.prog[3][0]=0;s_vp.prog[3][1]=12u<<9;s_vp.prog[3][2]=(2u<<26)|(2u<<11);s_vp.prog[3][3]=(2u<<28)|1u;
    s_sg_vp[0].inmask=vp_input_mask(0);
    if(s_sg_vp[0].inmask!=((1u<<0)|(1u<<3)|(1u<<9)))abort();
    /* LIVE_LAYOUT */
    SgVpConstants constants;
    sg_vp_constant_layout(0, &constants, 0);
    if (constants.count != 0) abort();
    unsigned info_offset = sg_vp_constant_slots(&constants) * 16;
    FILE *f = fopen("compact.layout.json", "w");
    fprintf(f, "{\"stride\":%u,\"infoOffset\":%u,\"vertexUniformBytes\":%u,\"attributes\":[",
            sg_vp_input_stride(inmask), info_offset, info_offset + 64);
    for (unsigned a = 0; a < 16; a++)
        fprintf(f, "%s{\"shaderLocation\":%u,\"offset\":%u,\"format\":\"float32x4\"}",
                a ? "," : "", vp_attrs[a].location, vp_attrs[a].offset);
    fprintf(f, "]}"); fclose(f);
    char *source = sg_vp_translate_wgsl(0, &constants);
    if (!source) abort();
    save("compact.wgsl", source, strlen(source)); free(source);
    compact_line_depth_case(inmask, &constants);
    float vertices[3][3][4] = {
        {{0,0,0.5,1}, {0.25,0.5,0.75,1}, {0.125,0.25,0.25,0}},
        {{8,0,0.5,1}, {0.25,0.5,0.75,1}, {0.125,0.25,0.25,0}},
        {{0,8,0.5,1}, {0.25,0.5,0.75,1}, {0.125,0.25,0.25,0}},
    };
    save("compact.vertices.bin", vertices, sizeof vertices);
    float uniforms[VP_CONSTS + 4][4] = {0};
    unsigned slots = sg_vp_constant_slots(&constants);
    sg_vp_pack_constants(uniforms, &constants);
    uniforms[slots][0] = uniforms[slots][1] = 4; uniforms[slots][2] = 1;
    save("compact.uniforms.bin", uniforms, (slots + 4) * sizeof uniforms[0]);
}
int main(void) {
    enum { CASES = 90, VERTICES = 32 };
    unsigned line_programs=0;
    FILE *line_manifest=fopen("line-cases.txt","wb");
    if(!line_manifest)abort();
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
        if(test>=80 && test<86) {
            memset(s_vp.prog,0,sizeof s_vp.prog);
            s_vp.prog[0][1]=(1u<<21)|(1u<<9)|0x1bu;
            s_vp.prog[0][2]=2u<<26;s_vp.prog[0][3]=15u<<24;
            unsigned mac=test<84?11+(test&1):test-75;
            s_vp.prog[1][1]=(mac<<21)|((test==82 || test==83)?1u<<8:0)|0x1bu;
            s_vp.prog[1][2]=(2u<<26)|(1u<<11)|(1u<<21)|(2u<<19)|(3u<<17);
            s_vp.prog[1][3]=(15u<<12)|(1u<<11)|(3u<<3)|1u;
        }
        if (test >= 86) {
            memset(s_vp.prog, 0, sizeof s_vp.prog);
            /* A MOV uses A only. B encodes a relative constant in slot
             * zero but must not force the full bank. In the second case
             * the live read of c[a0+100] does require the full bank. */
            s_vp.prog[0][1] = (13u << 21) | 0x1bu; /* ARL from v0.x */
            s_vp.prog[0][2] = (2u << 26) | (3u << 11);
            s_vp.prog[0][3] = 2u;
            const unsigned indices[] = {254, 11, 191, 100};
            for (unsigned i = 0; i < 4; i++) {
                uint32_t *t = s_vp.prog[i+1];
                t[1] = (1u << 21) | (indices[i] << 13) | 0x1bu;
                t[2] = 3u << 26;
                t[3] = (15u << 12) | (1u << 11) | ((9u + i) << 3);
            }
            s_vp.prog[4][3] |= 1u | (test == 87 || test == 89 ? 2u : 0u);
            if (test == 88) {
                /* ARL reads the old a0 in its own slot. Later reads
                 * here are absolute even though a0 has changed. */
                s_vp.prog[0][1] |= 11u << 13;
                s_vp.prog[0][2] = 3u << 26;
            }
            if (test == 89)
                s_vp.prog[0][1] = 0; /* no ARL before the final relative operand */
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
            if(test>=80 && test<86) {
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
            if(test==87) inputs[i][0][0] = (float)((int)i * 9 - 140);
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
            if(test>=80 && test<86)for(unsigned k=0;k<4;k++) {
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
        SgVpConstants constants;
        sg_vp_constant_layout(s_vp.start, &constants, 0);
        if (test >= 86 && test != 87 &&
            (constants.count != 3 || constants.registers[0] != 11 ||
             constants.registers[1] != 100 || constants.registers[2] != 191)) abort();
        if (test == 87 && constants.count != VP_CONSTS) abort();
        char *source = sg_vp_translate_wgsl(s_vp.start, &constants);
        if (!source) return 1;
        char name[96];
        snprintf(name, sizeof name, "case-%03u.wgsl", test); save(name, source, strlen(source)); free(source);
        source=sg_vp_translate_line_wgsl(s_vp.start,vp_input_mask(s_vp.start),&constants);
        if(source) {
            snprintf(name,sizeof name,"line-case-%03u.wgsl",test);
            save(name,source,strlen(source));free(source);line_programs++;
            fprintf(line_manifest,"%s\n",name);
        }
        float packed[VP_CONSTS + 4][4] = {0};
        sg_vp_pack_constants(packed, &constants);
        snprintf(name, sizeof name, "case-%03u.constants.bin", test);
        save(name, packed, (sg_vp_constant_slots(&constants) + 4) * sizeof packed[0]);
        snprintf(name, sizeof name, "case-%03u.inputs.bin", test); save(name, inputs, sizeof inputs);
        snprintf(name, sizeof name, "case-%03u.expected.bin", test); save(name, outputs, sizeof outputs);
        if((test>=71 && test<=73) || test>=75) {snprintf(name,sizeof name,"case-%03u.strict",test);save(name,"",0);}
    }
    compact_vertex_case();
    fclose(line_manifest);
    s_vp.start = 0;
    memset(s_vp.prog, 0, sizeof s_vp.prog);
    s_vp.prog[0][1] = 1u << 21;
    s_vp.prog[0][3] = (15u << 12) | 1u; /* MOV writes c0 */
    SgVpConstants constants;
    sg_vp_constant_layout(0, &constants, 1);
    if (constants.count != VP_CONSTS) abort();
    if (sg_vp_translate_wgsl(0, &constants)) return 2;
    if (sg_vp_translate_wgsl(VP_PROG_LEN, &constants)) return 3;
    if(!line_programs)return 4;
    printf("Generated %u production line vertex programs\n",line_programs);
    printf("Generated %u WGSL programs with CPU references; constant writes correctly refused\n", CASES);
    return 0;
}
