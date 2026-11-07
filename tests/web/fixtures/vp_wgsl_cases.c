/* Differential inputs for the production WGSL translator and CPU oracle. */
#include <stdarg.h>
/* LIVE_GENERATOR */

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
    enum { CASES = 64, VERTICES = 32 };
    for (unsigned test = 0; test < CASES; test++) {
        s_vp.start = test % 5;
        unsigned length = test < 22 ? 1 : 12;
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
        for (unsigned i = 0; i < 192; i++)
            for (unsigned k = 0; k < 4; k++) s_vp.c[i][k] = random_float();
        float inputs[VERTICES][16][4], outputs[VERTICES][29][4];
        for (unsigned i = 0; i < VERTICES; i++) {
            for (unsigned a = 0; a < 16; a++)
                for (unsigned k = 0; k < 4; k++) inputs[i][a][k] = random_float();
            vp_run(inputs[i], outputs[i]);
            memcpy(outputs[i][16], s_vp_dbg_r, sizeof s_vp_dbg_r);
        }
        char *source = sg_vp_translate_wgsl(s_vp.start);
        if (!source) return 1;
        char name[96];
        snprintf(name, sizeof name, "case-%03u.wgsl", test); save(name, source, strlen(source)); free(source);
        snprintf(name, sizeof name, "case-%03u.constants.bin", test); save(name, s_vp.c, sizeof s_vp.c);
        snprintf(name, sizeof name, "case-%03u.inputs.bin", test); save(name, inputs, sizeof inputs);
        snprintf(name, sizeof name, "case-%03u.expected.bin", test); save(name, outputs, sizeof outputs);
    }
    compact_vertex_case();
    s_vp.start = 0;
    memset(s_vp.prog, 0, sizeof s_vp.prog);
    s_vp.prog[0][1] = 1u << 21;
    s_vp.prog[0][3] = (15u << 12) | 1u; /* MOV writes c0 */
    if (sg_vp_translate_wgsl(0)) return 2;
    if (sg_vp_translate_wgsl(VP_PROG_LEN)) return 3;
    puts("Generated 64 WGSL programs with CPU references; constant writes correctly refused");
    return 0;
}
