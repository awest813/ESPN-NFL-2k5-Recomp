# Original Xbox game files

Extract the full USA Xbox disc into `original/disc/`. Keep the disc's folder structure intact.

```text
original/
└── disc/
    ├── default.xbe
    └── vc_53450030/
```

The native runtime reads local game files from this layout. For browser play, import the ISO/XISO or its extracted folder through **Game files** in the launcher. Your local game files stay out of Git.

[Windows build](../README.md#build-for-windows) · [Browser quick start](../README.md#get-on-the-field) · [Linux build](../docs/LINUX.md)
