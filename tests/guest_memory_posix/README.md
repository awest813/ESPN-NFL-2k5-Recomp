# Linux guest-memory regression tests

These Linux tests exercise the runtime's checked guest-memory copies with real mapped pages, protected pages, and unmapped addresses. Run them from the repo root.

```bash
cmake -S tests/guest_memory_posix -B build/guest-memory-posix
cmake --build build/guest-memory-posix
ctest --test-dir build/guest-memory-posix --output-on-failure
```

A failed copy may have transferred a prefix. Rendering callers must discard failed input and handle partial output. The tests cover memory boundaries independently of the rendering backends.

[Linux build](../../docs/LINUX.md) · [Runtime architecture](../../docs/architecture.md)
