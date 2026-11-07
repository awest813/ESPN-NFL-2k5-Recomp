/* Frozen pre-optimization interpreter for differential testing. */
static uint32_t reference_vp_field(const uint32_t *t, int word, int bit, int len) {
    return (t[word] >> bit) & ((1u << len) - 1u);
}

/* One source operand: register file by mux (1 R, 2 v, 3 c), swizzle, negate.
 * `scalar` replicates the first swizzle component, which is how the ILU
 * reads its (C) operand for the scalar ops. */
static void reference_vp_src(const uint32_t *t, int mux, int reg, int neg, const int swz[4],
                   float R[13][4], float O[16][4], const float V[16][4], int a0,
                   int scalar, float out[4]) {
    const float *s;
    int i;
    float tmp[4];

    switch (mux) {
        case 1: s = reg == 12 ? O[0] : R[reg < 13 ? reg : 0];
            break;
        case 2: s = V[reference_vp_field(t, 1, 9, 4)];
            break;
        case 3: {
            int c = (int) reference_vp_field(t, 1, 13, 8);
            if (reference_vp_field(t, 3, 1, 1)) {
                c += a0;
                if (c >= 0 && c < VP_CONSTS && !s_const_written[c]) const_unwritten_note(c, a0);
            }
            if (c < 0) c = 0;
            if (c >= VP_CONSTS) c = VP_CONSTS - 1;
            s = s_vp.c[c];
            break;
        }
        default: s = R[0];
            break;
    }
    for (i = 0; i < 4; i++)
        tmp[i] = s[scalar ? swz[0] : swz[i]];
    for (i = 0; i < 4; i++)
        out[i] = neg ? -tmp[i] : tmp[i];
}

static void reference_vp_write(float *dst, const float v[4], uint32_t mask) {
    /* mask bit 3 = x ... bit 0 = w */
    if (mask & 8) dst[0] = v[0];
    if (mask & 4) dst[1] = v[1];
    if (mask & 2) dst[2] = v[2];
    if (mask & 1) dst[3] = v[3];
}

static uint32_t reference_vp_fog_write_mask(uint32_t mask) {
    /* xemu fog_mask_str: every n-component oFog write maps to the first n
     * components, making x the scalar fog output even for an oFog.w write. */
    static const uint8_t masks[16] = {
        0, 8, 8, 12, 8, 12, 12, 14, 8, 12, 12, 14, 12, 14, 14, 15
    };
    return masks[mask & 15u];
}

static void reference_vp_run(const float V[16][4], float O[16][4]) {
    float R[13][4];
    int a0 = 0, slot, i;

    memset(R, 0, sizeof R);
    for (i = 0; i < 16; i++) {
        O[i][0] = O[i][1] = O[i][2] = 0.0f;
        O[i][3] = 1.0f;
    }

    for (slot = (int) s_vp.start; slot < VP_PROG_LEN; slot++) {
        const uint32_t *t = s_vp.prog[slot];
        uint32_t ilu = reference_vp_field(t, 1, 25, 3), mac = reference_vp_field(t, 1, 21, 4);
        float A[4], B[4], C[4], mres[4] = {0, 0, 0, 0}, ires[4] = {0, 0, 0, 0};
        int sa[4], sb[4], sc[4];
        int mux_a = (int) reference_vp_field(t, 2, 26, 2), mux_b = (int) reference_vp_field(t, 2, 11, 2);
        int mux_c = (int) reference_vp_field(t, 3, 28, 2);
        int reg_a = (int) reference_vp_field(t, 2, 28, 4), reg_b = (int) reference_vp_field(t, 2, 13, 4);
        int reg_c = (int) ((reference_vp_field(t, 2, 0, 2) << 2) | reference_vp_field(t, 3, 30, 2));
        uint32_t mac_mask = reference_vp_field(t, 3, 24, 4), ilu_mask = reference_vp_field(t, 3, 16, 4);
        uint32_t o_mask = reference_vp_field(t, 3, 12, 4), out_r = reference_vp_field(t, 3, 20, 4);
        uint32_t orb = reference_vp_field(t, 3, 11, 1), out_addr = reference_vp_field(t, 3, 3, 8);
        uint32_t out_mux = reference_vp_field(t, 3, 2, 1);
        int new_a0 = a0, a0_written = 0;

        sa[0] = (int) reference_vp_field(t, 1, 6, 2);
        sa[1] = (int) reference_vp_field(t, 1, 4, 2);
        sa[2] = (int) reference_vp_field(t, 1, 2, 2);
        sa[3] = (int) reference_vp_field(t, 1, 0, 2);
        sb[0] = (int) reference_vp_field(t, 2, 23, 2);
        sb[1] = (int) reference_vp_field(t, 2, 21, 2);
        sb[2] = (int) reference_vp_field(t, 2, 19, 2);
        sb[3] = (int) reference_vp_field(t, 2, 17, 2);
        sc[0] = (int) reference_vp_field(t, 2, 8, 2);
        sc[1] = (int) reference_vp_field(t, 2, 6, 2);
        sc[2] = (int) reference_vp_field(t, 2, 4, 2);
        sc[3] = (int) reference_vp_field(t, 2, 2, 2);

        reference_vp_src(t, mux_a, reg_a, (int) reference_vp_field(t, 1, 8, 1), sa, R, O, V, a0, 0, A);
        reference_vp_src(t, mux_b, reg_b, (int) reference_vp_field(t, 2, 25, 1), sb, R, O, V, a0, 0, B);
        reference_vp_src(t, mux_c, reg_c, (int) reference_vp_field(t, 2, 10, 1), sc, R, O, V, a0,
               ilu >= 2 && ilu <= 6, C);

        switch (mac) {
            case 1: memcpy(mres, A, sizeof mres);
                break; /* MOV */
            case 2: for (i = 0; i < 4; i++) mres[i] = A[i] * B[i];
                break; /* MUL */
            case 3: for (i = 0; i < 4; i++) mres[i] = A[i] + C[i];
                break; /* ADD */
            case 4: for (i = 0; i < 4; i++) mres[i] = A[i] * B[i] + C[i];
                break; /* MAD */
            case 5: mres[0] = mres[1] = mres[2] = mres[3] = /* DP3 */
                                                  A[0] * B[0] + A[1] * B[1] + A[2] * B[2];
                break;
            case 6: mres[0] = mres[1] = mres[2] = mres[3] = /* DPH */
                                                  A[0] * B[0] + A[1] * B[1] + A[2] * B[2] + B[3];
                break;
            case 7: mres[0] = mres[1] = mres[2] = mres[3] = /* DP4 */
                                                  A[0] * B[0] + A[1] * B[1] + A[2] * B[2] + A[3] * B[3];
                break;
            case 8: mres[0] = 1.0f;
                mres[1] = A[1] * B[1];
                mres[2] = A[2];
                mres[3] = B[3];
                break; /* DST */
            case 9: for (i = 0; i < 4; i++) mres[i] = A[i] < B[i] ? A[i] : B[i];
                break; /* MIN */
            case 10: for (i = 0; i < 4; i++) mres[i] = A[i] > B[i] ? A[i] : B[i];
                break; /* MAX */
            case 11: for (i = 0; i < 4; i++) mres[i] = A[i] < B[i] ? 1.0f : 0.0f;
                break; /* SLT */
            case 12: for (i = 0; i < 4; i++) mres[i] = A[i] >= B[i] ? 1.0f : 0.0f;
                break; /* SGE */
            case 13: new_a0 = (int) floorf(A[0] + 0.001f);
                a0_written = 1; /* ARL */
                {
                    /* RECOMP_VP_A0_LOG: the address range each program start uses */
                    static int on = -1;
                    static int lo[256], hi[256], seen[256];
                    static DWORD last;
                    if (on < 0) on = getenv("RECOMP_VP_A0_LOG") != NULL;
                    if (on && s_vp.start < 256) {
                        int st = (int) s_vp.start;
                        if (!seen[st] || new_a0 < lo[st]) lo[st] = new_a0;
                        if (!seen[st] || new_a0 > hi[st]) hi[st] = new_a0;
                        seen[st] = 1;
                        if (GetTickCount() - last > 3000) {
                            int q;
                            last = GetTickCount();
                            for (q = 0; q < 256; q++)
                                if (seen[q]) fprintf(stderr, "  [VPA0] start %d a0 %d..%d (input %g)\n", q, lo[q],
                                                     hi[q], A[0]);
                        }
                    }
                }
                break;
            default: break;
        }

        switch (ilu) {
            case 1: memcpy(ires, C, sizeof ires);
                break; /* MOV */
            case 2: {
                float x = C[0]; /* RCP */
                float r = x == 1.0f ? 1.0f : (x == 0.0f ? INFINITY : 1.0f / x);
                ires[0] = ires[1] = ires[2] = ires[3] = r;
                break;
            }
            case 3: {
                float x = C[0], r; /* RCC */
                r = x == 0.0f ? 1.8446743e19f : 1.0f / x;
                if (r > 0) {
                    if (r < 5.42101e-20f) r = 5.42101e-20f;
                    if (r > 1.8446743e19f) r = 1.8446743e19f;
                } else {
                    if (r > -5.42101e-20f) r = -5.42101e-20f;
                    if (r < -1.8446743e19f) r = -1.8446743e19f;
                }
                ires[0] = ires[1] = ires[2] = ires[3] = r;
                break;
            }
            case 4: {
                float x = fabsf(C[0]); /* RSQ */
                float r = x == 1.0f ? 1.0f : (x == 0.0f ? INFINITY : 1.0f / sqrtf(x));
                ires[0] = ires[1] = ires[2] = ires[3] = r;
                break;
            }
            case 5: {
                float x = C[0], fl = floorf(x); /* EXP */
                ires[0] = exp2f(fl);
                ires[1] = x - fl;
                ires[2] = exp2f(x);
                ires[3] = 1.0f;
                break;
            }
            case 6: {
                float x = fabsf(C[0]); /* LOG */
                if (x == 0.0f) {
                    ires[0] = ires[2] = -INFINITY;
                    ires[1] = 1.0f;
                } else {
                    float e = floorf(log2f(x));
                    ires[0] = e;
                    ires[1] = x / exp2f(e);
                    ires[2] = log2f(x);
                }
                ires[3] = 1.0f;
                break;
            }
            case 7: {
                float sx = C[0] > 0 ? C[0] : 0, sy = C[1] > 0 ? C[1] : 0; /* LIT */
                float sw = C[3];
                if (sw < -127.996f) sw = -127.996f;
                if (sw > 127.996f) sw = 127.996f;
                ires[0] = 1.0f;
                ires[1] = sx;
                ires[2] = sx > 0 ? exp2f(sw * log2f(sy)) : 0.0f;
                ires[3] = 1.0f;
                break;
            }
            default: break;
        }

        /* Register writes. A MAC paired with an ILU op writes its own
         * register (except R1, which the pair gives to the ILU); the ILU
         * writes R1 when paired, its own register otherwise. */
        /* R12 is oPos, for writes as for reads. */
#define VP_REG(r) ((r) == 12 ? O[0] : R[(r) < 13 ? (r) : 0])
        if (mac && mac != 13 && mac_mask) {
            if (!(ilu && out_r == 1))
                reference_vp_write(VP_REG(out_r), mres, mac_mask);
        }
        if (ilu && ilu_mask)
            reference_vp_write(mac ? R[1] : VP_REG(out_r), ires, ilu_mask);
#undef VP_REG

        /* Output register (or writable constant). */
        if (o_mask) {
            const float *v = out_mux ? ires : mres;
            if ((out_mux == 0 && mac && mac != 13) || (out_mux == 1 && ilu)) {
                if (orb) {
                    uint32_t reg = out_addr & 15;
                    reference_vp_write(O[reg], v, reg == 5 ? reference_vp_fog_write_mask(o_mask) : o_mask);
                } else if (out_addr < VP_CONSTS) {
                    reference_vp_write(s_vp.c[out_addr], v, o_mask);
                    s_vp_cgen++;
                }
            }
        }
        if (s_vp_trace_next)
            fprintf(stderr, "  [VPI] %3d mac=%2u ilu=%u A(m%d r%d)=%.4g,%.4g,%.4g,%.4g B(m%d r%d)=%.4g,%.4g,%.4g,%.4g"
                    " C(m%d r%d)=%.4g,%.4g,%.4g,%.4g -> mres=%.4g,%.4g,%.4g,%.4g ires=%.4g"
                    " r%u m%X i%X o%s%u m%X cidx=%u\n", slot, mac, ilu,
                    mux_a, reg_a, A[0], A[1], A[2], A[3], mux_b, reg_b, B[0], B[1], B[2], B[3],
                    mux_c, reg_c, C[0], C[1], C[2], C[3], mres[0], mres[1], mres[2], mres[3], ires[0],
                    out_r, mac_mask, ilu_mask, orb ? "O" : "c", out_addr, o_mask,
                    reference_vp_field(t, 1, 13, 8));
        if (a0_written)
            a0 = new_a0;
        if (reference_vp_field(t, 3, 0, 1))
            break;
    }
    memcpy(s_vp_dbg_r, R, sizeof R);
    s_vp_dbg_a0 = a0;
}
