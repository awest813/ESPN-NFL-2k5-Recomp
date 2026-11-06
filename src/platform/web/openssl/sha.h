/* Web build: the two OpenSSL entry points the game uses (SHA256 in main.c,
 * HMAC-SHA1 in nfl2k5_save_library.cpp), implemented in web_crypto.c.
 * Only on the Emscripten include path; Linux keeps the real OpenSSL. */
#pragma once
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
#define SHA256_DIGEST_LENGTH 32
#define SHA_DIGEST_LENGTH 20
unsigned char *SHA256(const unsigned char *data, size_t len, unsigned char *md);
unsigned char *SHA1(const unsigned char *data, size_t len, unsigned char *md);
#ifdef __cplusplus
}
#endif
