/* Web build: a thread that owns SDL's gamepad subsystem.
 *
 * Browsers report a gamepad only after one of its buttons is pressed while
 * the page has focus, through a "gamepadconnected" event. SDL subscribes to
 * that event on the thread that initialises its gamepad subsystem, and the
 * browser delivers it there as a queued call -- which a worker thread only
 * runs when it returns to its event loop or asks for its queue to be run.
 * The game initialises gamepads from whichever of its threads polls first,
 * and none of them ever does either, so a pad that appears after startup
 * would never be seen.
 *
 * So this thread initialises the subsystem before any game code can (main()
 * calls nfl2k5_web_sdl_start() first; the game's own init calls then find it
 * done) and then runs its queue forever. SDL's joystick state is global, so
 * the game's threads see the pads as usual. Window and keyboard events are
 * the presenter thread's (xboxrecomp video/fb_present.c), which runs its own
 * queue. */
#ifdef __EMSCRIPTEN__
#include <SDL3/SDL.h>
#include <emscripten/threading.h>
#include <pthread.h>
#include <semaphore.h>
#include <stdio.h>

static sem_t s_ready;

static void *web_sdl_pump(void *arg)
{
    (void)arg;
    if (!SDL_InitSubSystem(SDL_INIT_GAMEPAD))
        fprintf(stderr, "[WEB] SDL gamepad init failed: %s\n", SDL_GetError());
    else
        printf("[WEB] Gamepads: press a button on a controller to connect it\n");
    sem_post(&s_ready);
    for (;;) {
        emscripten_current_thread_process_queued_calls();
        SDL_Delay(8);
    }
    return NULL;
}

int nfl2k5_web_sdl_start(void)
{
    pthread_t thread;
    if (sem_init(&s_ready, 0, 0) != 0 || pthread_create(&thread, NULL, web_sdl_pump, NULL) != 0) {
        fprintf(stderr, "[WEB] Could not start the SDL pump thread\n");
        return 0;
    }
    pthread_detach(thread);
    sem_wait(&s_ready);
    return 1;
}
#endif
