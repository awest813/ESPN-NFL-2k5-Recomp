/* Web build: the game's files live in the browser's Origin Private File
 * System (OPFS), mounted at /nfl2k5 through WasmFS's OPFS backend.
 *
 * The backend maps the mount 1:1 onto the origin's OPFS root: the file the
 * game opens as /nfl2k5/original/disc/default.xbe is the OPFS entry
 * original/disc/default.xbe that the page's importer (web/import-worker.js)
 * wrote. Saves, logs and mods land beside it and persist across visits.
 *
 * Runs on the guest's main thread, which PROXY_TO_PTHREAD puts on a worker:
 * creating the backend blocks until the browser's main thread answers, which
 * the browser main thread is free to do there. */
#ifdef __EMSCRIPTEN__
#include <emscripten/wasmfs.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>

#define NFL2K5_WEB_ROOT "/nfl2k5"

int nfl2k5_web_mount(void)
{
    struct stat st;
    if (stat(NFL2K5_WEB_ROOT, &st) != 0) {
        backend_t opfs = wasmfs_create_opfs_backend();
        if (!opfs || wasmfs_create_directory(NFL2K5_WEB_ROOT, 0777, opfs) != 0) {
            fprintf(stderr, "[WEB] Could not mount the browser's private file"
                            " system (OPFS) at %s\n", NFL2K5_WEB_ROOT);
            return 0;
        }
    }
    /* The page may override either through its environment. Portable mode
     * keeps saves, logs and settings under the root rather than $HOME, so
     * they are in OPFS too. */
    setenv("NFL2K5_ROOT", NFL2K5_WEB_ROOT, 0);
    setenv("NFL2K5_PORTABLE", "1", 0);
    printf("[WEB] Game files: OPFS at %s\n", NFL2K5_WEB_ROOT);
    return 1;
}
#endif
