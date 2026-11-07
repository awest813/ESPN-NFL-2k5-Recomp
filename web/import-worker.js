// Disc import: the player's own NFL 2K5 disc -> the origin's private file
// system (OPFS), where the game reads it (src/platform/web/web_fs.c).
//
// Two sources:
//   { kind: 'image', file }             an Xbox disc image (.iso / .xiso),
//                                       read as XDVDFS (as tools/xiso_read.py)
//   { kind: 'folder', files: [File] }   an extracted disc folder, from an
//                                       <input webkitdirectory>
//
// Layout written (relative to the OPFS root, which the game mounts at /nfl2k5):
//   original/disc/...        the disc, names as on the disc
//   web-import.json          written last: what was imported, and the XBE hash
//
// Nothing is uploaded anywhere; files go from the chosen File straight into
// OPFS through sync access handles (workers only), a chunk at a time.
'use strict';

const SECTOR = 2048;
const MAGIC = 'MICROSOFT*XBOX*MEDIA';
// Where the game partition starts: an XISO at 0, redump-style full images at
// one of the others (the same list as tools/xiso_read.py).
const PARTITION_OFFSETS = [0, 0x18300000, 0xFD90000, 0x2090000, 0x89D80000, 0x2080000];
const CHUNK = 8 * 1024 * 1024;
const MARKER = 'web-import.json';

const post = (msg) => self.postMessage(msg);

async function readAt(file, offset, length) {
  return new Uint8Array(await file.slice(offset, offset + length).arrayBuffer());
}

// ---- XDVDFS -----------------------------------------------------------------

async function findPartition(file) {
  for (const base of PARTITION_OFFSETS) {
    if (base + 33 * SECTOR > file.size) continue;
    const head = await readAt(file, base + 32 * SECTOR, 28);
    if (String.fromCharCode(...head.subarray(0, 20)) === MAGIC) {
      const dv = new DataView(head.buffer);
      return { base, rootSector: dv.getUint32(20, true), rootSize: dv.getUint32(24, true) };
    }
  }
  throw new Error('This is not an Xbox disc image (no XDVDFS volume found).');
}

// Directory tables are binary trees of entries; offsets are in 4-byte units.
async function listImage(file) {
  const part = await findPartition(file);
  const entries = [];           // { path, dir, start, size }
  const walk = async (sector, size, prefix, depth) => {
    if (depth > 64) throw new Error('Disc directory tree is too deep (corrupt image?)');
    if (!size) return;
    const data = await readAt(file, part.base + sector * SECTOR, size);
    const dv = new DataView(data.buffer);
    const seen = new Set();
    const stack = [0];
    const subdirs = [];
    while (stack.length) {
      const off = stack.pop();
      if (seen.has(off) || off + 14 > data.length) continue;
      seen.add(off);
      const left = dv.getUint16(off, true), right = dv.getUint16(off + 2, true);
      const start = dv.getUint32(off + 4, true), fsize = dv.getUint32(off + 8, true);
      const attr = data[off + 12], nlen = data[off + 13];
      if (left === 0xFFFF && right === 0xFFFF && start === 0xFFFFFFFF) continue;
      if (off + 14 + nlen > data.length) continue;
      const name = String.fromCharCode(...data.subarray(off + 14, off + 14 + nlen));
      if (!name || name.includes('/') || name === '.' || name === '..')
        throw new Error('Disc has an unusable file name: ' + JSON.stringify(name));
      const path = prefix + name;
      if (attr & 0x10) {
        entries.push({ path, dir: true });
        subdirs.push([start, fsize, path + '/']);
      } else {
        entries.push({ path, dir: false, start, size: fsize });
      }
      if (left) stack.push(left * 4);
      if (right) stack.push(right * 4);
    }
    for (const [s, n, p] of subdirs) await walk(s, n, p, depth + 1);
  };
  await walk(part.rootSector, part.rootSize, '', 0);
  return { part, entries };
}

// ---- OPFS writing -----------------------------------------------------------

async function dirFor(root, path, cache) {
  const parts = path.split('/');
  parts.pop();
  let key = '', dir = root;
  for (const p of parts) {
    key += p + '/';
    if (!cache.has(key)) cache.set(key, await dir.getDirectoryHandle(p, { create: true }));
    dir = cache.get(key);
  }
  return dir;
}

async function writeFile(discRoot, path, size, readChunk, cache, progress) {
  const dir = await dirFor(discRoot, path, cache);
  const name = path.split('/').pop();
  const handle = await dir.getFileHandle(name, { create: true });
  const sync = await handle.createSyncAccessHandle();
  let keep = null;
  try {
    sync.truncate(0);
    const wantBytes = name.toLowerCase() === 'default.xbe' && path === name;
    if (wantBytes) keep = new Uint8Array(size);
    for (let at = 0; at < size; at += CHUNK) {
      const n = Math.min(CHUNK, size - at);
      const buf = await readChunk(at, n);
      if (buf.length !== n) throw new Error('Short read in ' + path);
      let w = 0;
      while (w < n) w += sync.write(buf.subarray(w), { at: at + w });
      if (keep) keep.set(buf, at);
      progress(n, path);
    }
    sync.flush();
  } finally {
    sync.close();
  }
  return keep;
}

async function sha256Hex(bytes) {
  const d = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
  return Array.from(d, (b) => b.toString(16).padStart(2, '0')).join('');
}

// ---- import ------------------------------------------------------------------

async function importDisc(msg) {
  const root = await navigator.storage.getDirectory();
  // The marker goes first and comes back last: an interrupted import is
  // never mistaken for a finished one. Saves and logs elsewhere are kept.
  await root.removeEntry(MARKER).catch(() => {});
  const original = await root.getDirectoryHandle('original', { create: true });
  await original.removeEntry('disc', { recursive: true }).catch(() => {});
  const discRoot = await original.getDirectoryHandle('disc', { create: true });

  let items, source;
  if (msg.kind === 'image') {
    const { part, entries } = await listImage(msg.file);
    const file = msg.file;
    items = entries.map((e) => e.dir ? e : {
      path: e.path, size: e.size,
      read: (at, n) => readAt(file, part.base + e.start * SECTOR + at, n),
    });
    source = { kind: 'image', name: file.name, size: file.size, partition: part.base };
  } else {
    // webkitRelativePath is "<chosen folder>/<path>". The disc root is the
    // shallowest folder that holds default.xbe, so choosing either the disc
    // folder or the folder above it works.
    const files = msg.files.map((f) => ({ f, parts: f.webkitRelativePath.split('/') }));
    const xbes = files.filter((x) => x.parts[x.parts.length - 1].toLowerCase() === 'default.xbe')
                      .sort((a, b) => a.parts.length - b.parts.length);
    if (!xbes.length) throw new Error('That folder has no default.xbe. Choose the extracted disc folder.');
    const depth = xbes[0].parts.length - 1;
    const prefix = xbes[0].parts.slice(0, depth).join('/');
    items = files
      .filter((x) => x.parts.length > depth && x.parts.slice(0, depth).join('/') === prefix)
      .map((x) => ({ path: x.parts.slice(depth).join('/'), size: x.f.size,
                     read: (at, n) => readAt(x.f, at, n) }));
    source = { kind: 'folder', name: prefix || '(chosen folder)' };
  }

  const files = items.filter((i) => !i.dir);
  if (!files.some((i) => i.path.toLowerCase() === 'default.xbe'))
    throw new Error('The disc has no default.xbe at its root.');
  const total = files.reduce((s, i) => s + i.size, 0);
  const est = await navigator.storage.estimate().catch(() => null);
  if (est && est.quota && est.usage !== undefined && total > est.quota - est.usage)
    throw new Error(`Not enough browser storage: the disc needs ${mb(total)}, ` +
                    `${mb(est.quota - est.usage)} is available.`);

  const cache = new Map();
  for (const d of items.filter((i) => i.dir)) await dirFor(discRoot, d.path + '/x', cache);
  let done = 0, lastPost = 0, xbe = null;
  const progress = (n, path) => {
    done += n;
    const now = Date.now();
    if (now - lastPost > 100 || done === total) {
      lastPost = now;
      post({ type: 'progress', done, total, file: path });
    }
  };
  post({ type: 'progress', done: 0, total, file: '' });
  for (const f of files) {
    const kept = await writeFile(discRoot, f.path, f.size, f.read, cache, progress);
    if (kept) xbe = kept;
  }

  const info = {
    version: 1,
    importedAt: new Date().toISOString(),
    source,
    files: files.length,
    directories: items.length - files.length,
    bytes: total,
    xbeSha256: await sha256Hex(xbe),
    hasVc53450030: items.some((i) => i.path.toLowerCase().split('/')[0] === 'vc_53450030'),
  };
  const mh = await root.getFileHandle(MARKER, { create: true });
  const ms = await mh.createSyncAccessHandle();
  try {
    const bytes = new TextEncoder().encode(JSON.stringify(info, null, 2));
    ms.truncate(0);
    ms.write(bytes, { at: 0 });
    ms.flush();
  } finally {
    ms.close();
  }
  return info;
}

function mb(n) { return (n / (1024 * 1024)).toFixed(0) + ' MB'; }

self.onmessage = async (e) => {
  try {
    post({ type: 'done', info: await importDisc(e.data) });
  } catch (err) {
    post({ type: 'error', message: err && err.message ? err.message : String(err) });
  }
};
