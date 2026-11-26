# Experimental native reconstruction viewer

The reconstruction viewer investigated asset formats independently of the game build. It is an optional Windows target named `NFL2K5_Rebuild`; normal builds leave `NFL2K5_BUILD_REBUILD` disabled. Use the main Windows build for gameplay. [Windows build](../README.md#build-for-windows)

## Verified asset decode

The viewer opened the extracted retail XBE and 16 data archives. The early fallback scene demonstrated its Windows loop and input. The later decode displayed the original NFL/Players Inc. legal screen directly from archive 0.

[`src/rebuild/legal_texture.c`](../src/rebuild/legal_texture.c) checks entry `EDD549BD`, locates the HITX payload, validates its dimensions and length, and converts the 512×512 Morton-ordered P8 indices through the embedded BGRA palette. The original experiment exported the result with `NFL2K5_Rebuild.exe --export-legal` to the local analysis directory. Use the archive checkpoint for the exact offsets and record format. [Archive findings](ARCHIVE-FINDINGS.md)

The optional target remains incomplete. The historical decode result describes the viewer at that checkpoint and supplies a reference for asset research. [Original handoff](GEMINI-HANDOFF.md)
