/* SHA-1, SHA-256 and HMAC-SHA1 for the Emscripten build, which has no
 * OpenSSL. Straight from FIPS 180-4 / RFC 2104; not constant time, which
 * does not matter here (XBE hashing and save signatures). */
#include "openssl/hmac.h"
#include <stdint.h>
#include <string.h>

#define ROL(x, n) (((x) << (n)) | ((x) >> (32 - (n))))
#define ROR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))

static uint32_t be32(const unsigned char *p)
{
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
}

static void put_be32(unsigned char *p, uint32_t v)
{
    p[0] = (unsigned char)(v >> 24); p[1] = (unsigned char)(v >> 16);
    p[2] = (unsigned char)(v >> 8);  p[3] = (unsigned char)v;
}

typedef void (*block_fn)(uint32_t *state, const unsigned char *block);

/* Merkle-Damgard driver shared by both hashes: 64-byte blocks, big-endian
 * 64-bit bit length. `prefix` (may be NULL) is hashed before `data`, which is
 * how HMAC feeds its padded key without copying the message. */
static void md_hash(block_fn fn, uint32_t *state, int words,
                    const unsigned char *prefix, size_t prefix_len,
                    const unsigned char *data, size_t len, unsigned char *out)
{
    unsigned char block[64];
    size_t fill = 0;
    uint64_t total = (uint64_t)prefix_len + len;
    const unsigned char *parts[2] = { prefix, data };
    size_t sizes[2] = { prefix ? prefix_len : 0, len };
    for (int part = 0; part < 2; ++part) {
        const unsigned char *p = parts[part];
        size_t n = sizes[part];
        while (n) {
            size_t take = 64 - fill < n ? 64 - fill : n;
            memcpy(block + fill, p, take);
            fill += take; p += take; n -= take;
            if (fill == 64) { fn(state, block); fill = 0; }
        }
    }
    block[fill++] = 0x80;
    if (fill > 56) {
        memset(block + fill, 0, 64 - fill);
        fn(state, block);
        fill = 0;
    }
    memset(block + fill, 0, 56 - fill);
    uint64_t bits = total * 8u;
    put_be32(block + 56, (uint32_t)(bits >> 32));
    put_be32(block + 60, (uint32_t)bits);
    fn(state, block);
    for (int i = 0; i < words; ++i)
        put_be32(out + i * 4, state[i]);
}

static void sha1_block(uint32_t *h, const unsigned char *b)
{
    uint32_t w[80];
    for (int i = 0; i < 16; ++i) w[i] = be32(b + i * 4);
    for (int i = 16; i < 80; ++i) w[i] = ROL(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1);
    uint32_t a = h[0], bb = h[1], c = h[2], d = h[3], e = h[4];
    for (int i = 0; i < 80; ++i) {
        uint32_t f, k;
        if (i < 20)      { f = (bb & c) | (~bb & d);           k = 0x5A827999u; }
        else if (i < 40) { f = bb ^ c ^ d;                     k = 0x6ED9EBA1u; }
        else if (i < 60) { f = (bb & c) | (bb & d) | (c & d);  k = 0x8F1BBCDCu; }
        else             { f = bb ^ c ^ d;                     k = 0xCA62C1D6u; }
        uint32_t t = ROL(a, 5) + f + e + k + w[i];
        e = d; d = c; c = ROL(bb, 30); bb = a; a = t;
    }
    h[0] += a; h[1] += bb; h[2] += c; h[3] += d; h[4] += e;
}

static const uint32_t K256[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
};

static void sha256_block(uint32_t *h, const unsigned char *b)
{
    uint32_t w[64];
    for (int i = 0; i < 16; ++i) w[i] = be32(b + i * 4);
    for (int i = 16; i < 64; ++i) {
        uint32_t s0 = ROR(w[i - 15], 7) ^ ROR(w[i - 15], 18) ^ (w[i - 15] >> 3);
        uint32_t s1 = ROR(w[i - 2], 17) ^ ROR(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    uint32_t a = h[0], bb = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
    for (int i = 0; i < 64; ++i) {
        uint32_t t1 = hh + (ROR(e, 6) ^ ROR(e, 11) ^ ROR(e, 25)) + ((e & f) ^ (~e & g)) + K256[i] + w[i];
        uint32_t t2 = (ROR(a, 2) ^ ROR(a, 13) ^ ROR(a, 22)) + ((a & bb) ^ (a & c) ^ (bb & c));
        hh = g; g = f; f = e; e = d + t1; d = c; c = bb; bb = a; a = t1 + t2;
    }
    h[0] += a; h[1] += bb; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
}

static void sha1_with_prefix(const unsigned char *prefix, size_t prefix_len,
                             const unsigned char *data, size_t len, unsigned char *md)
{
    uint32_t h[5] = { 0x67452301u, 0xEFCDAB89u, 0x98BADCFEu, 0x10325476u, 0xC3D2E1F0u };
    md_hash(sha1_block, h, 5, prefix, prefix_len, data, len, md);
}

unsigned char *SHA1(const unsigned char *data, size_t len, unsigned char *md)
{
    sha1_with_prefix(NULL, 0, data, len, md);
    return md;
}

unsigned char *SHA256(const unsigned char *data, size_t len, unsigned char *md)
{
    uint32_t h[8] = { 0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au,
                      0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u };
    md_hash(sha256_block, h, 8, NULL, 0, data, len, md);
    return md;
}

struct web_evp_md { int unused; };
static const struct web_evp_md k_sha1_md = { 1 };
const EVP_MD *EVP_sha1(void) { return &k_sha1_md; }

unsigned char *HMAC(const EVP_MD *md, const void *key, int key_len,
                    const unsigned char *data, size_t data_len,
                    unsigned char *md_out, unsigned int *md_len)
{
    if (md != &k_sha1_md || key_len < 0 || !md_out)
        return NULL;
    unsigned char k[64] = { 0 }, pad[64], inner[20];
    if (key_len > 64)
        SHA1((const unsigned char *)key, (size_t)key_len, k);
    else if (key_len)
        memcpy(k, key, (size_t)key_len);
    for (int i = 0; i < 64; ++i) pad[i] = k[i] ^ 0x36;
    sha1_with_prefix(pad, 64, data, data_len, inner);
    for (int i = 0; i < 64; ++i) pad[i] = k[i] ^ 0x5c;
    sha1_with_prefix(pad, 64, inner, 20, md_out);
    if (md_len) *md_len = 20;
    return md_out;
}
