/* Web build: see openssl/sha.h. HMAC() supports EVP_sha1() only. */
#pragma once
#include "evp.h"
#ifdef __cplusplus
extern "C" {
#endif
unsigned char *HMAC(const EVP_MD *md, const void *key, int key_len,
                    const unsigned char *data, size_t data_len,
                    unsigned char *md_out, unsigned int *md_len);
#ifdef __cplusplus
}
#endif
