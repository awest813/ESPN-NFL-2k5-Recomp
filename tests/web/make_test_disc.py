#!/usr/bin/env python3
"""A synthetic Xbox disc for testing the web importer: no game data.

    make_test_disc.py <out dir>

Writes:
  <out>/test.xiso              an XDVDFS image of the disc below
  <out>/folder/disc/...        the same disc as an extracted folder (one level
                               down, to test finding the disc root)
  <out>/expected.json          { "files": {path: sha256}, "dirs": [...],
                                 "xbe_sha256": ... }

The default.xbe starts with "XBEH" and is otherwise random, so the game reads
it and stops at its hash check -- which is the point: the check prints the
hash it computed, proving the bytes went through OPFS into the module.
"""
import hashlib
import json
import os
import random
import struct
import sys

SECTOR = 2048
MAGIC = b'MICROSOFT*XBOX*MEDIA'


def disc_contents(rng):
    xbe = b'XBEH' + bytes(rng.getrandbits(8) for _ in range(0x2000 - 4))
    big = bytes(rng.getrandbits(8) for _ in range(4096)) * (20 * 256)   # 20 MB, > 2 import chunks
    return {
        'default.xbe': xbe,
        'vc_53450030/data.bin': big,
        'vc_53450030/readme.txt': b'not game data\n',
        'vc_53450030/Media/Sound/a.wma': bytes(rng.getrandbits(8) for _ in range(3000)),
        'vc_53450030/Media/Sound/B.WMA': b'',
        'vc_53450030/Media/Movies/intro.xmv': bytes(rng.getrandbits(8) for _ in range(70000)),
        'z_last.dat': b'z' * 5,
    }, ['vc_53450030/Empty']


def build_tree(files, dirs):
    root = {}
    for path in list(files) + dirs:
        node, parts = root, path.split('/')
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        if path in files:
            node[parts[-1]] = files[path]
        else:
            node.setdefault(parts[-1], {})
    return root


def write_xiso(path, tree):
    """Directory tables as a balanced binary tree over sorted names, as
    mastering tools write them; file data after the tables."""
    out = bytearray(33 * SECTOR)
    data_queue = []

    def alloc(nbytes):
        nonlocal out
        start = len(out) // SECTOR
        out += bytes(-(-nbytes // SECTOR) * SECTOR or 0)
        return start

    def table(node):
        names = sorted(node, key=lambda n: n.upper())
        layout = {}            # name -> (offset, left name, right name)

        def place(lo, hi, order):
            if lo > hi:
                return None
            mid = (lo + hi) // 2
            order.append(names[mid])
            left = place(lo, mid - 1, order)
            right = place(mid + 1, hi, order)
            layout[names[mid]] = (left, right)
            return names[mid]
        order = []
        place(0, len(names) - 1, order)
        offsets, off = {}, 0
        for n in order:
            size = 14 + len(n)
            size += -size % 4
            if off // SECTOR != (off + size - 1) // SECTOR:
                off += -off % SECTOR          # entries never cross a sector
            offsets[n] = off
            off += size
        table_size = off
        start = alloc(table_size)
        entries = []
        for n in order:
            child = node[n]
            if isinstance(child, dict):
                if child:
                    s, sz = table(child)
                else:
                    s, sz = 0, 0               # empty directory
                attr = 0x10
            else:
                s, sz, attr = None, len(child), 0x80
            entries.append((n, s, sz, attr, child))
        for n, s, sz, attr, child in entries:
            if s is None:
                s = alloc(len(child)) if child else 0
                data_queue.append((s, child))
            left, right = layout[n]
            rec = struct.pack('<HHIIBB', offsets[left] // 4 if left else 0,
                              offsets[right] // 4 if right else 0, s, sz, attr, len(n)) + n.encode()
            rec += b'\xff' * (-len(rec) % 4)
            pos = start * SECTOR + offsets[n]
            out[pos:pos + len(rec)] = rec
        return start, table_size

    root_sector, root_size = table(tree)
    for s, blob in data_queue:
        out[s * SECTOR:s * SECTOR + len(blob)] = blob
    vd = 32 * SECTOR
    out[vd:vd + 20] = MAGIC
    out[vd + 20:vd + 28] = struct.pack('<II', root_sector, root_size)
    out[vd + 0x7EC:vd + 0x800] = MAGIC
    with open(path, 'wb') as f:
        f.write(out)


def main():
    out = sys.argv[1]
    rng = random.Random(2005)
    files, dirs = disc_contents(rng)
    os.makedirs(out, exist_ok=True)
    write_xiso(os.path.join(out, 'test.xiso'), build_tree(files, dirs))
    for p, blob in files.items():
        dest = os.path.join(out, 'folder', 'disc', *p.split('/'))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'wb') as f:
            f.write(blob)
    for d in dirs:
        os.makedirs(os.path.join(out, 'folder', 'disc', *d.split('/')), exist_ok=True)
    expected = {
        'files': {p: hashlib.sha256(b).hexdigest() for p, b in files.items()},
        'dirs': dirs,
        'xbe_sha256': hashlib.sha256(files['default.xbe']).hexdigest(),
    }
    with open(os.path.join(out, 'expected.json'), 'w') as f:
        json.dump(expected, f, indent=1)
    print('wrote', out)


if __name__ == '__main__':
    main()
