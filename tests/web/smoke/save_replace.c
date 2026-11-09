/* Exercise Xbox save replacement through the real Nt file API and OPFS. */
#include "kernel.h"
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

int nfl2k5_web_mount(void);

static NTSTATUS open_save(HANDLE root, const char *path, int directory, HANDLE *out)
{
    XBOX_ANSI_STRING name = {(USHORT)strlen(path), (USHORT)(strlen(path)+1), (char *)path};
    XBOX_OBJECT_ATTRIBUTES attrs = {root, &name, 0};
    XBOX_IO_STATUS_BLOCK ios = {0};
    return xbox_NtCreateFile(out, XBOX_GENERIC_READ | XBOX_DELETE, &attrs, &ios,
        NULL, 0, 7, XBOX_FILE_OPEN, directory ? XBOX_FILE_DIRECTORY_FILE : 0);
}

#define REQUIRE(test) do { if (!(test)) { \
    printf("[SMOKE] storage replace FAILED line %d\n", __LINE__); return 1; } } while (0)

int save_replace_smoke(void)
{
    const char *base = "/nfl2k5/saves/replacement-test";
    const char *data = "/nfl2k5/saves/replacement-test/SaveGame.DAT";
    const char *meta = "/nfl2k5/saves/replacement-test/SaveMeta.xbx";
    HANDLE dir = NULL, file = NULL;
    XBOX_IO_STATUS_BLOCK ios = {0};
    XBOX_FILE_DISPOSITION_INFORMATION remove = {1};
    struct stat st;
    REQUIRE(nfl2k5_web_mount());
    /* Sparse disk images need OPFS too; an in-memory WasmFS backend would
     * allocate their full console-sized lengths. Keep them outside saves. */
    xbox_path_init("/nfl2k5/original/disc", "/nfl2k5/kernel-replace-runtime");
    mkdir("/nfl2k5/saves", 0777);
    mkdir(base, 0777);
    FILE *f = fopen(data, "wb");
    REQUIRE(f && fwrite("old", 1, 3, f) == 3 && fclose(f) == 0);
    f = fopen(meta, "wb");
    REQUIRE(f && fwrite("metadata", 1, 8, f) == 8 && fclose(f) == 0);
    REQUIRE(open_save(NULL, base, 1, &dir) == STATUS_SUCCESS);
    /* A nonempty directory must not report successful deletion. */
    REQUIRE(xbox_NtSetInformationFile(dir, &ios, &remove, sizeof remove,
        XboxFileDispositionInformation) != STATUS_SUCCESS);
    REQUIRE(stat(data, &st) == 0);
    /* FATX relative names are case-insensitive. */
    REQUIRE(open_save(dir, "savegame.dat", 0, &file) == STATUS_SUCCESS);
    XBOX_ANSI_STRING name = {12, 13, "savegame.dat"};
    XBOX_OBJECT_ATTRIBUTES attrs = {dir, &name, 0};
    XBOX_FILE_NETWORK_OPEN_INFORMATION info;
    REQUIRE(xbox_NtQueryFullAttributesFile(&attrs, &info) == STATUS_SUCCESS && info.EndOfFile.QuadPart == 3);
    REQUIRE(xbox_NtSetInformationFile(file, &ios, &remove, sizeof remove,
        XboxFileDispositionInformation) == STATUS_SUCCESS);
    XBOX_FILE_STANDARD_INFORMATION standard;
    REQUIRE(xbox_NtQueryInformationFile(file, &ios, &standard, sizeof standard,
        XboxFileStandardInformation) == STATUS_SUCCESS && standard.DeletePending);
    REQUIRE(stat(data, &st) == 0);
    remove.DeleteFile = 0;
    REQUIRE(xbox_NtSetInformationFile(file, &ios, &remove, sizeof remove,
        XboxFileDispositionInformation) == STATUS_SUCCESS);
    REQUIRE(xbox_NtQueryInformationFile(file, &ios, &standard, sizeof standard,
        XboxFileStandardInformation) == STATUS_SUCCESS && !standard.DeletePending);
    remove.DeleteFile = 1;
    REQUIRE(xbox_NtSetInformationFile(file, &ios, &remove, sizeof remove,
        XboxFileDispositionInformation) == STATUS_SUCCESS);
    HANDLE duplicate = NULL;
    REQUIRE(DuplicateHandle(GetCurrentProcess(), file, GetCurrentProcess(),
        &duplicate, 0, FALSE, DUPLICATE_SAME_ACCESS));
    REQUIRE(xbox_NtClose(file) == STATUS_SUCCESS);
    REQUIRE(stat(data, &st) == 0);
    REQUIRE(xbox_NtClose(duplicate) == STATUS_SUCCESS);
    REQUIRE(stat(data, &st) != 0);
    name.Length = 12; name.MaximumLength = 13; name.Buffer = "savemeta.xbx";
    REQUIRE(xbox_NtDeleteFile(&attrs) == STATUS_SUCCESS);
    REQUIRE(stat(meta, &st) != 0);
    REQUIRE(xbox_NtSetInformationFile(dir, &ios, &remove, sizeof remove,
        XboxFileDispositionInformation) == STATUS_SUCCESS);
    REQUIRE(xbox_NtClose(dir) == STATUS_SUCCESS && stat(base, &st) != 0);
    /* Recreate the same save name and verify replacement bytes durably. */
    REQUIRE(mkdir(base, 0777) == 0);
    f = fopen(data, "wb");
    REQUIRE(f && fwrite("new-save", 1, 8, f) == 8 && fclose(f) == 0);
    char bytes[8];
    f = fopen(data, "rb");
    REQUIRE(f && fread(bytes, 1, sizeof bytes, f) == sizeof bytes && fclose(f) == 0);
    REQUIRE(memcmp(bytes, "new-save", sizeof bytes) == 0);
    REQUIRE(unlink(data) == 0 && rmdir(base) == 0);
    for (int i = 0; i < 7; i++) {
        char image[128];
        snprintf(image, sizeof image, "/nfl2k5/kernel-replace-runtime/Partition%d.img", i);
        unlink(image);
    }
    const char *folders[] = {"TitleData", "UserData", "Cache", "SystemData"};
    for (unsigned i = 0; i < sizeof folders / sizeof *folders; i++) {
        char folder[128];
        snprintf(folder, sizeof folder, "/nfl2k5/kernel-replace-runtime/%s", folders[i]);
        rmdir(folder);
    }
    rmdir("/nfl2k5/kernel-replace-runtime");
    puts("[SMOKE] storage replace exact");
    return 0;
}
