// Portable browser backup format. Retail disc files are never part of a backup.
'use strict';
globalThis.NFL2K5SaveFormat = (() => {
  const settings = ['controls.ini', 'nfl2k5_game.ini', 'nfl2k5_video.ini'];
  const MAX_BYTES = 128 * 1024 * 1024, MAX_FILE = 32 * 1024 * 1024, MAX_FILES = 4096;
  function validPath(path) {
    if (typeof path !== 'string' || path.length > 512 || /[\\:\x00-\x1f\x7f]/.test(path)) return false;
    const parts = path.split('/');
    return parts.length <= 20 && parts.every(p => p && p !== '.' && p !== '..') &&
      ((parts[0] === 'saves' && parts.length > 1) || settings.includes(path));
  }
  function validate(archive) {
    if (!archive || archive.type !== 'nfl2k5-browser-save' || archive.version !== 1 || !Array.isArray(archive.files))
      throw Error('Choose an NFL 2K5 browser save backup (.json).');
    if (!archive.files.length || archive.files.length > MAX_FILES) throw Error('Backup file count is invalid.');
    const paths = new Set(), spelling = new Map(); let total = 0;
    for (const f of archive.files) {
      if (!f || !validPath(f.path) || paths.has(f.path.toLowerCase())) throw Error('Backup contains an unsafe or duplicate path.');
      paths.add(f.path.toLowerCase());
      const parts = f.path.split('/');
      for (let n = 1; n <= parts.length; n++) {
        const prefix = parts.slice(0,n).join('/'), key = prefix.toLowerCase();
        if (spelling.has(key) && spelling.get(key) !== prefix) throw Error('Backup contains conflicting filename capitalization.');
        spelling.set(key, prefix);
      }
      if (!Number.isSafeInteger(f.size) || f.size < 0 || f.size > MAX_FILE || (total += f.size) > MAX_BYTES)
        throw Error('Backup exceeds the supported size limits.');
      const padding = (3 - f.size % 3) % 3;
      if (!/^[0-9a-f]{64}$/.test(f.sha256) || typeof f.data !== 'string' ||
          f.data.length !== Math.ceil(f.size / 3) * 4 ||
          (padding && !f.data.endsWith('='.repeat(padding))) ||
          /[^A-Za-z0-9+/]/.test(f.data.slice(0, f.data.length - padding)))
        throw Error('Backup contains invalid file data.');
    }
    // A file cannot also be the parent directory of a different file.
    for (const f of archive.files) {
      const parts = f.path.toLowerCase().split('/'); parts.pop();
      while (parts.length) { if (paths.has(parts.join('/'))) throw Error('Backup has conflicting file paths.'); parts.pop(); }
    }
    return {files: archive.files.length, bytes: total, createdAt: archive.createdAt || ''};
  }
  async function digest(bytes) {
    return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), x => x.toString(16).padStart(2, '0')).join('');
  }
  function encode(bytes) {
    const chunks = [];
    for (let i = 0; i < bytes.length; i += 32768) chunks.push(String.fromCharCode(...bytes.subarray(i, i + 32768)));
    return btoa(chunks.join(''));
  }
  function decode(data) { return Uint8Array.from(atob(data), c => c.charCodeAt(0)); }
  return {settings, MAX_BYTES, MAX_FILE, MAX_FILES, validPath, validate, digest, encode, decode};
})();
