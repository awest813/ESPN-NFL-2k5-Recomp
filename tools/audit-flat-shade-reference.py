"""Verify pinned public Xbox shade-model captures (requires Pillow).

Usage: python tools/audit-flat-shade-reference.py <capture-directory>
Captures are not bundled; their pinned source URLs and hashes are in the manifest.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'docs/references/nv2a-flat-shading.json').read_text(encoding='utf-8'))
capture_dir = Path(sys.argv[1])
palette = [int(word, 16) for word in manifest['diffuse_words']]
source_path = capture_dir / 'shade_model_tests.cpp'
if source_path.exists():
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == manifest['source_sha256'], source_path
for capture in manifest['captures']:
    path = capture_dir / capture['file']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == capture['sha256'], path
    with Image.open(path) as picture:
        rgb = picture.convert('RGB')
        counts = Counter(rgb.get_flattened_data() if hasattr(rgb, 'get_flattened_data') else rgb.getdata())
        for x, y, expected in capture['probes']:
            r, g, b = rgb.getpixel((x, y))
            assert (0xFF000000 | r << 16 | g << 8 | b) == expected, (path, x, y)
    # The test's packed inline diffuse words put R in the low byte.
    visible = {str(i): counts[(word & 255, (word >> 8) & 255, (word >> 16) & 255)]
               for i, word in enumerate(palette)
               if counts[(word & 255, (word >> 8) & 255, (word >> 16) & 255)] > 20}
    assert visible == capture['visible_vertex_pixels'], (path, visible)
    expected = manifest['primitives'][capture['primitive']][capture['selection']]
    assert set(map(int, visible)) == set(expected), (path, expected, visible)
header = [f"/* Generated from pinned Xbox captures {manifest['capture_revision']}. */",
          'typedef struct { uint32_t primitive,count,triangles,first[6],last[6]; } FlatShadeReference;',
          'static const FlatShadeReference flat_shade_cases[] = {']
primitive_ids = {'Tri': 5, 'TriStrip': 6, 'TriFan': 7, 'Quad': 8, 'QuadStrip': 9, 'Poly': 10}
for name, case in manifest['primitives'].items():
    arrays = ','.join('{' + ','.join(map(str, case[which])) + '}' for which in ('first', 'last'))
    header.append(f"    {{{primitive_ids[name]},{len(manifest['geometry'][name])},{len(case['first'])},{arrays}}},")
header += ['};', 'static const uint32_t flat_shade_diffuse_words[] = {' + ','.join('0x' + c + 'u' for c in manifest['diffuse_words']) + '};',
           'typedef struct { int x,y;uint32_t argb; } FlatShadeProbe;',
           'typedef struct { float xy[9][2];uint32_t triangles[6][3];unsigned count;FlatShadeProbe probes[2][24]; } FlatShadeHardware;',
           'static const FlatShadeHardware flat_shade_hardware[] = {']
for name in manifest['primitives']:
    def number(value):
        text = format(value, '.9f')
        return text + 'f'
    positions = ','.join('{' + ','.join(number(v) for v in point) + '}' for point in manifest['geometry'][name])
    captures = [next(c for c in manifest['captures'] if c['primitive'] == name and c['selection'] == choice) for choice in ('last', 'first')]
    triangles = ','.join('{' + ','.join(map(str, triangle)) + '}' for triangle in manifest['triangles'][name])
    header.append('    {{' + positions + '},{' + triangles + '},' + str(len(captures[0]['probes'])) + ',{')
    for capture in captures:
        header.append('        {' + ','.join(f'{{{x},{y},0x{argb:08X}u}}' for x, y, argb in capture['probes']) + '},')
    header.append('    }},')
header += ['};', '']
generated = '\n'.join(header).encode('utf-8')
header_path = root / 'external/xboxrecomp/tests/sdlgpu_web/flat_shade_reference.h'
if '--write-header' in sys.argv:
    header_path.write_bytes(generated)
else:
    assert header_path.read_bytes().replace(b'\r\n', b'\n') == generated, 'Reference header differs; regenerate with --write-header'
print(f"PASS {len(manifest['captures'])} pinned Xbox captures and {sum(len(c['probes']) for c in manifest['captures'])} interior pixel probes")
