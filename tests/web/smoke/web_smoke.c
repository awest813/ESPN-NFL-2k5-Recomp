/* Web smoke module: the game's real presentation, input and audio paths
 * without the game. Driven by tests/web/test_web_av.js through smoke.html.
 *
 *   video  a guest framebuffer (left half red, right half blue) shown by the
 *          real presenter (xboxrecomp video/fb_present.c) on its own thread
 *   keys   the presenter's key hook, printed as "[SMOKE] key vk=<n>"
 *   pads   the gamepad pump thread (src/platform/web/web_sdl.c); connects and
 *          the south button printed as "[SMOKE] gamepads: <n>", "pad A down"
 *   audio  a 440 Hz tone through the APU's SDL output (apu_xaudio2.c)
 */
#include <SDL3/SDL.h>
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

int  nfl2k5_web_sdl_start(void);
int  xbox_MemoryLayoutInit(const void *xbe, size_t size);
ptrdiff_t xbox_GetMemoryOffset(void);
void xbox_FramebufferWindowForceStart(void);
void xbox_FramebufferWindowSet(uint32_t fb_va, uint32_t pitch);
void xbox_FramebufferSnapshot(uint32_t fb_va, uint32_t pitch);
void xbox_FramebufferSetKeyHook(void (*hook)(unsigned vk));
int  xa2_init(void);
int  xa2_submit_samples(const int16_t *samples, int frames);

#define FB_VA    0x00100000u
#define FB_W     640u
#define FB_H     480u
#define FB_PITCH (FB_W * 4u)

static void on_key(unsigned vk) { printf("[SMOKE] key vk=%u\n", vk); }

static void put32(uint8_t *p, uint32_t v) { memcpy(p, &v, 4); }

static int SDLCALL audio_thread(void *arg)
{
    (void)arg;
    static int16_t block[1024][2];
    double phase = 0;
    if (!xa2_init()) { printf("[SMOKE] audio init failed\n"); return 0; }
    printf("[SMOKE] audio open\n");
    for (;;) {
        for (int i = 0; i < 1024; i++) {
            int16_t s = (int16_t)(sin(phase) * 12000);
            phase += 2 * M_PI * 440.0 / 48000.0;
            block[i][0] = block[i][1] = s;
        }
        while (!xa2_submit_samples(&block[0][0], 1024))
            SDL_Delay(5);
    }
    return 0;
}

int main(void)
{
    static uint8_t xbe[0x2000];
    SDL_Gamepad *pad = NULL;
    int last_count = -1, last_a = 0;

    if (!nfl2k5_web_sdl_start()) return 1;

    /* Minimal XBE so the real memory layout exists (guest RAM at its VA). */
    memcpy(xbe, "XBEH", 4);
    put32(xbe + 0x104, 0x10000); put32(xbe + 0x108, 0x1000); put32(xbe + 0x10C, 0x2000);
    put32(xbe + 0x11C, 1); put32(xbe + 0x120, 0x10200);
    put32(xbe + 0x204, 0x11000); put32(xbe + 0x208, 0x1000);
    put32(xbe + 0x20C, 0x1000); put32(xbe + 0x210, 0x100);
    if (!xbox_MemoryLayoutInit(xbe, sizeof xbe)) { printf("[SMOKE] layout failed\n"); return 1; }

    uint32_t *fb = (uint32_t *)(uintptr_t)(FB_VA + xbox_GetMemoryOffset());
    for (uint32_t y = 0; y < FB_H; y++)
        for (uint32_t x = 0; x < FB_W; x++)
            fb[y * FB_W + x] = x < FB_W / 2 ? 0xFFFF0000u : 0xFF0000FFu;

    xbox_FramebufferSetKeyHook(on_key);
    xbox_FramebufferWindowSet(FB_VA, FB_PITCH);
    xbox_FramebufferWindowForceStart();
    SDL_DetachThread(SDL_CreateThread(audio_thread, "smoke_audio", NULL));
    printf("[SMOKE] ready\n");

    for (;;) {
        xbox_FramebufferSnapshot(FB_VA, FB_PITCH);   /* what a flip does */
        int count = 0;
        SDL_JoystickID *ids = SDL_GetGamepads(&count);
        if (count != last_count) {
            printf("[SMOKE] gamepads: %d\n", count);
            last_count = count;
            if (count > 0 && !pad) {
                pad = SDL_OpenGamepad(ids[0]);
                printf("[SMOKE] opened %s\n", pad ? SDL_GetGamepadName(pad) : SDL_GetError());
            }
        }
        SDL_free(ids);
        if (pad) {
            SDL_UpdateGamepads();
            int a = SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_SOUTH);
            if (a != last_a) { printf("[SMOKE] pad A %s\n", a ? "down" : "up"); last_a = a; }
        }
        SDL_Delay(16);
    }
}
