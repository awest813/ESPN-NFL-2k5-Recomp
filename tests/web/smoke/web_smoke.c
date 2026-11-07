/* Web smoke module: the game's real presentation, input and audio paths
 * without the game. Driven by tests/web/test_web_av.js through smoke.html.
 *
 *   video  a guest framebuffer (left half red, right half blue) shown by the
 *          real presenter (xboxrecomp video/fb_present.c) on its own thread
 *   keys   the presenter's key hook, printed as "[SMOKE] key vk=<n>"
 *   pads   the gamepad pump thread (src/platform/web/web_sdl.c); connects and
 *          the south button printed as "[SMOKE] gamepads: <n>", "pad A down"
 *   audio  a 440 Hz tone through the APU's SDL output (apu_xaudio2.c)
 *   gpu    with SMOKE_GPU=1 and WebGPU: a GPU presenter written as the SDL
 *          GPU renderer's (sdlgpu_present.inc.c) takes the window over --
 *          claim, acquire, blit a green | magenta frame -- printing
 *          "[SMOKE] gpu present claimed" and presents per second
 */
#include <SDL3/SDL.h>
#include <stdlib.h>
#include "kernel/sdlgpu/webgpu/sdl_gpu_webgpu.h"
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "xinput_xbox.h"

int nfl2k5_web_mount(void);
int nfl2k5_controls_get(int port, XBOX_GAMEPAD *g, int use_pads);
void nfl2k5_controls_start(void);

/* Exercise the same C/WasmFS mount as the game, including durable close. */
static int storage_smoke(const char *mode)
{
    static const unsigned char bytes[] = {0, 255, 128, 1, 2, 13, 10, 42};
    const char *path = "/nfl2k5/saves/UDATA/53450030/0123456789ab/SAVEGAME.DAT";
    unsigned char actual[sizeof bytes + 1];
    if (!nfl2k5_web_mount()) return 1;
    if (!strcmp(mode, "write")) {
        mkdir("/nfl2k5/saves", 0777); mkdir("/nfl2k5/saves/UDATA", 0777);
        mkdir("/nfl2k5/saves/UDATA/53450030", 0777);
        mkdir("/nfl2k5/saves/UDATA/53450030/0123456789ab", 0777);
        FILE *f = fopen(path, "wb");
        if (!f || fwrite(bytes, 1, sizeof bytes, f) != sizeof bytes || fflush(f) || fsync(fileno(f)) || fclose(f)) {
            puts("[SMOKE] storage write FAILED"); return 1;
        }
        puts("[SMOKE] storage write durable");
    } else {
        FILE *f = fopen(path, "rb");
        if (!f) { puts("[SMOKE] storage read FAILED"); return 1; }
        size_t n = fread(actual, 1, sizeof actual, f); fclose(f);
        if (n != sizeof bytes || memcmp(actual, bytes, sizeof bytes)) { puts("[SMOKE] storage bytes FAILED"); return 1; }
        puts("[SMOKE] storage read exact");
    }
    return 0;
}

int  nfl2k5_web_sdl_start(void);
int  xbox_MemoryLayoutInit(const void *xbe, size_t size);
ptrdiff_t xbox_GetMemoryOffset(void);
void xbox_FramebufferWindowForceStart(void);
void xbox_FramebufferWindowSet(uint32_t fb_va, uint32_t pitch);
void xbox_FramebufferSnapshot(uint32_t fb_va, uint32_t pitch);
void xbox_FramebufferSetKeyHook(void (*hook)(unsigned vk));
int  xa2_init(void);
int  xa2_submit_samples(const int16_t *samples, int frames);
void xbox_FramebufferSetGpuPresenter(int (*fn)(void *window, int letterbox));

static SDL_GPUDevice *g_dev;
static SDL_GPUTexture *g_frame;
static int g_claimed;
static SDL_AtomicInt g_presents;

/* fb_thread, as sdlgpu_present.inc.c's sg_present_window. */
static int SDLCALL gpu_present(void *window, int letterbox)
{
    SDL_GPUCommandBuffer *cmd;
    SDL_GPUTexture *swap = NULL;
    Uint32 sw = 0, sh = 0;
    if (letterbox < 0) return 1;
    if (!g_claimed) {
        if (!SDL_ClaimWindowForGPUDevice(g_dev, (SDL_Window *)window)) return 0;
        g_claimed = 1;
        printf("[SMOKE] gpu present claimed\n");
    }
    cmd = SDL_AcquireGPUCommandBuffer(g_dev);
    if (!SDL_WaitAndAcquireGPUSwapchainTexture(cmd, (SDL_Window *)window, &swap, &sw, &sh)) {
        SDL_CancelGPUCommandBuffer(cmd);
        return 1;
    }
    SDL_GPUBlitInfo b = { .source = { .texture = g_frame, .w = 640, .h = 480 },
                          .destination = { .texture = swap, .w = sw, .h = sh },
                          .load_op = SDL_GPU_LOADOP_CLEAR, .clear_color = { 0, 0, 0, 1 },
                          .filter = SDL_GPU_FILTER_NEAREST };
    SDL_BlitGPUTexture(cmd, &b);
    SDL_SubmitGPUCommandBuffer(cmd);
    SDL_AddAtomicInt(&g_presents, 1);
    return 1;
}

static void gpu_start(void)
{
    static uint32_t px[640 * 480];
    SDL_GPUTextureCreateInfo ti = { .type = SDL_GPU_TEXTURETYPE_2D, .format = SDL_GPU_TEXTUREFORMAT_B8G8R8A8_UNORM,
        .usage = SDL_GPU_TEXTUREUSAGE_COLOR_TARGET | SDL_GPU_TEXTUREUSAGE_SAMPLER,
        .width = 640, .height = 480, .layer_count_or_depth = 1, .num_levels = 1 };
    SDL_GPUTransferBufferCreateInfo bi = { .usage = SDL_GPU_TRANSFERBUFFERUSAGE_UPLOAD, .size = sizeof px };
    if (!(g_dev = SDL_CreateGPUDevice(SDL_GPU_SHADERFORMAT_WGSL, false, NULL))) {
        printf("[SMOKE] gpu: no device (%s)\n", SDL_GetError());
        return;
    }
    g_frame = SDL_CreateGPUTexture(g_dev, &ti);
    for (int y = 0; y < 480; y++)
        for (int x = 0; x < 640; x++)
            px[y * 640 + x] = x < 320 ? 0xFF00C000u : 0xFFC000C0u;   /* BGRA bytes: green | magenta */
    SDL_GPUTransferBuffer *tb = SDL_CreateGPUTransferBuffer(g_dev, &bi);
    memcpy(SDL_MapGPUTransferBuffer(g_dev, tb, false), px, sizeof px);
    SDL_UnmapGPUTransferBuffer(g_dev, tb);
    SDL_GPUCommandBuffer *c = SDL_AcquireGPUCommandBuffer(g_dev);
    SDL_GPUCopyPass *cp = SDL_BeginGPUCopyPass(c);
    SDL_GPUTextureTransferInfo src = { .transfer_buffer = tb };
    SDL_GPUTextureRegion dst = { .texture = g_frame, .w = 640, .h = 480, .d = 1 };
    SDL_UploadToGPUTexture(cp, &src, &dst, false);
    SDL_EndGPUCopyPass(cp);
    SDL_SubmitGPUCommandBuffer(c);
    SDL_ReleaseGPUTransferBuffer(g_dev, tb);
    xbox_FramebufferSetGpuPresenter(gpu_present);
    printf("[SMOKE] gpu presenter registered\n");
}

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
    if (getenv("SMOKE_STORAGE")) return storage_smoke(getenv("SMOKE_STORAGE"));
    static uint8_t xbe[0x2000];
    SDL_Gamepad *pad = NULL;
    int last_count = -1, last_a = 0;

    if (!nfl2k5_web_sdl_start()) return 1;
    nfl2k5_controls_start();
    XBOX_GAMEPAD blank;
    memset(&blank, 0xCC, sizeof blank);
    int absent = nfl2k5_controls_get(1, &blank, 0);
    XBOX_GAMEPAD zero = {0};
    printf("[SMOKE] controls disabled neutral: %d\n", !absent && !memcmp(&blank, &zero, sizeof blank));

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
    if (getenv("SMOKE_GPU") && wg_available())
        gpu_start();
    printf("[SMOKE] ready\n");
    Uint64 last_report = SDL_GetTicks();
    XBOX_GAMEPAD previous[2] = {{0}};
    int previous_connected[2] = {-1, -1};

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
        for (int port = 0; port < 2; port++) {
            XBOX_GAMEPAD g;
            int connected = nfl2k5_controls_get(port, &g, 1);
            if (connected != previous_connected[port] || memcmp(&g, &previous[port], sizeof g)) {
                printf("[SMOKE] controls %d: connected=%d buttons=%u A=%u LT=%u RT=%u sticks=%d,%d,%d,%d\n",
                    port, connected, g.wButtons, g.bAnalogButtons[0], g.bAnalogButtons[6], g.bAnalogButtons[7],
                    g.sThumbLX, g.sThumbLY, g.sThumbRX, g.sThumbRY);
                previous[port] = g; previous_connected[port] = connected;
            }
        }
        if (g_dev && SDL_GetTicks() - last_report >= 1000) {
            printf("[SMOKE] gpu presents/s: %d\n", SDL_SetAtomicInt(&g_presents, 0));
            last_report = SDL_GetTicks();
        }
        SDL_Delay(16);
    }
}
