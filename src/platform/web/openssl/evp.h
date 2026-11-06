/* Web build: see openssl/sha.h. EVP_MD is opaque; only EVP_sha1() exists. */
#pragma once
#include "sha.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct web_evp_md EVP_MD;
const EVP_MD *EVP_sha1(void);
#ifdef __cplusplus
}
#endif
