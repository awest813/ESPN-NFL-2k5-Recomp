static int fetch_attr(const VertexAttr *a, uint32_t index, float out[4]) {
    const uint8_t *mem = (const uint8_t *) xbox_GetMemoryOffset();
    const uint8_t *p;
    uint32_t i;
    size_t bytes;
#if defined(__linux__) || defined(__EMSCRIPTEN__)
    union {
        float floats[4];
        uint8_t bytes[16];
    } sampled;
#endif

    out[0] = out[1] = out[2] = 0.0f;
    out[3] = 1.0f;
    if (!a->size) {
        ptrdiff_t k = a - s_gpu.attr;
        if (k >= 0 && k < NV_VERTEX_ATTRS)
            memcpy(out, s_attr_inline[k], sizeof s_attr_inline[k]);
        return 0;
    }
    switch (a->type) {
        case 0:
        case 6: bytes = 4;
            break;
        case 2: bytes = (a->size < 4 ? a->size : 4) * 4;
            break;
        case 1:
        case 5: bytes = (a->size < 4 ? a->size : 4) * 2;
            break;
        case 4: bytes = a->size < 4 ? a->size : 4;
            break;
        default: return 0;
    }
    if (s_gpu.inline_active) {
        /* The batch arrived as INLINE_ARRAY, so `offset` is a byte offset into
         * the buffered payload rather than a guest address -- and 0 is a legal
         * one there, which is why the offset test is on the other side of this
         * branch. */
        uint64_t at = (uint64_t) a->offset + (uint64_t) index * a->stride;
        uint64_t available = (uint64_t) s_gpu.inline_count * 4;
        if (at > available || bytes > available - at)
            return 0;
        p = (const uint8_t *) s_gpu.inline_buf + at;
    } else {
        if (!a->offset)
            return 0;
#if defined(__linux__) || defined(__EMSCRIPTEN__)
        uint64_t address = (uint64_t) a->offset + (uint64_t) index * a->stride;
        if (!xbox_guest_memory_read((uintptr_t) mem, address, sampled.bytes, bytes))
            return 0;
        p = sampled.bytes;
#else
        p = mem + a->offset + (size_t) index * a->stride;
#endif
    }

    switch (a->type) {
        case 0: /* D3DCOLOR */
            /* A DWORD 0xAARRGGBB, so little-endian bytes are B,G,R,A -- not the
             * component order of every other format here. Returned as R,G,B,A so
             * callers need not know which format the title chose. */
            /* A zero-stride array supplies a constant inline value, decoded in
             * byte order just like SET_VERTEX_DATA4UB (xemu vertex.c and
             * gl/vertex.c). BGRA conversion applies only to array fetches. */
            out[0] = (float) p[a->stride ? 2 : 0] / 255.0f;
            out[1] = (float) p[1] / 255.0f;
            out[2] = (float) p[a->stride ? 0 : 2] / 255.0f;
            out[3] = (float) p[3] / 255.0f;
            return 1;
        case 2: /* float */
            for (i = 0; i < a->size && i < 4; i++)
                out[i] = ((const float *) p)[i];
            return 1;
        case 4: /* unsigned byte, normalised */
            for (i = 0; i < a->size && i < 4; i++)
                out[i] = (float) p[i] / 255.0f;
            return 1;
        /* Signed shorts. NFL 2K5's shaders take their matrix-palette index from
         * attribute 1 as raw shorts (type 5) through ARL; read as 0, every vertex
         * of a batch transformed by an unset matrix and collapsed to one point. */
        case 1: /* short, normalised (S1) */
            for (i = 0; i < a->size && i < 4; i++) {
                float v = (float) ((const int16_t *) p)[i] / 32767.0f;
                out[i] = v < -1.0f ? -1.0f : v;
            }
            return 1;
        case 5: /* short, as is (S32K) */
            for (i = 0; i < a->size && i < 4; i++)
                out[i] = (float) ((const int16_t *) p)[i];
            return 1;
        case 6: {
            /* packed 11:11:10 signed normal (CMP) */
            uint32_t w = *(const uint32_t *) p;
            int32_t x = (int32_t) (w << 21) >> 21;
            int32_t y = (int32_t) ((w >> 11) << 21) >> 21;
            int32_t z = (int32_t) (w >> 22) << 22 >> 22;
            out[0] = (float) x / 1023.0f;
            out[1] = (float) y / 1023.0f;
            out[2] = (float) z / 511.0f;
            if (!a->stride) {
                /* Constant arrays pass through pgraph_update_inline_value,
                 * which clamps the negative endpoint of signed normal formats. */
                if (out[0] < -1.0f) out[0] = -1.0f;
                if (out[1] < -1.0f) out[1] = -1.0f;
                if (out[2] < -1.0f) out[2] = -1.0f;
            }
            return 1;
        }
        default:
            return 0;
    }
}
