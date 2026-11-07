// Save backups and crash-recoverable restore, isolated from the game runtime.
'use strict';
importScripts('save-format.js');
const F = NFL2K5SaveFormat;
const STAGE = '.nfl2k5-save-restore';
const progress = message => postMessage({type: 'progress', message});
const missing = e => e.name === 'NotFoundError';

async function directory(root, path, create = false) {
  for (const part of path.split('/').filter(Boolean)) root = await root.getDirectoryHandle(part, {create});
  return root;
}
async function fileHandle(root, path, create = false) {
  const parts = path.split('/'); const name = parts.pop();
  return (await directory(root, parts.join('/'), create)).getFileHandle(name, {create});
}
async function write(handle, data) {
  const stream = await handle.createWritable();
  try { await stream.write(data); await stream.close(); }
  catch (e) { await stream.abort().catch(() => {}); throw e; }
}
async function copy(from, to) {
  await (await from.getFile()).stream().pipeTo(await to.createWritable());
}
async function removeFile(root, path) {
  const parts = path.split('/'); const name = parts.pop();
  try { await (await directory(root, parts.join('/'))).removeEntry(name); }
  catch (e) { if (!missing(e)) throw e; }
}
async function journal(stage, value) {
  await write(await stage.getFileHandle('journal.json', {create: true}), JSON.stringify(value));
}
async function recover(root) {
  let stage;
  try { stage = await root.getDirectoryHandle(STAGE); } catch (e) { if (missing(e)) return; throw e; }
  try {
    let j;
    try { j = JSON.parse(await (await (await stage.getFileHandle('journal.json')).getFile()).text()); }
    catch (e) { if (!missing(e)) throw e; }
    if (j && (j.type !== 'nfl2k5-restore' || j.version !== 1 || !['preparing', 'writing', 'committed'].includes(j.state)))
      throw Error('Invalid restore journal. The local recovery files have been retained.');
    if (j?.state === 'writing') {
      if (!Array.isArray(j.files) || j.files.length > F.MAX_FILES ||
          !j.files.every(f => F.validPath(f.path) && typeof f.hadOriginal === 'boolean') ||
          !Array.isArray(j.directories) || !j.directories.every(p => p === 'saves' || F.validPath(p)))
        throw Error('Unsafe restore journal. Recovery files have been retained.');
      for (let i = 0; i < j.files.length; i++) {
        const entry = j.files[i];
        if (entry.hadOriginal) await copy(await fileHandle(stage, 'old/' + i), await fileHandle(root, entry.path, true));
        else await removeFile(root, entry.path);
      }
      for (const path of [...j.directories].sort((a,b) => b.split('/').length - a.split('/').length)) {
        try {
          const dir = await directory(root, path); let empty = true;
          for await (const entry of dir.values()) { empty = false; break; }
          if (empty) await removeFile(root, path);
        } catch (e) { if (!missing(e)) throw e; }
      }
    }
    await root.removeEntry(STAGE, {recursive: true});
  } catch (e) { throw Object.assign(new Error(e.message), {code: 'RECOVERY'}); }
}

async function entries(root) {
  const files = [];
  async function walk(dir, prefix, depth = 0) {
    if (depth > 18) throw Error('Save folders are nested too deeply.');
    for await (const [name, handle] of dir.entries()) {
      const path = prefix + name;
      if (!F.validPath(path)) throw Error('Unsupported save filename: ' + path);
      if (handle.kind === 'directory') await walk(handle, path + '/', depth + 1);
      else {
        if (files.length >= F.MAX_FILES) throw Error('Too many save files for one backup.');
        files.push({path, file: await handle.getFile()});
      }
    }
  }
  try { await walk(await root.getDirectoryHandle('saves'), 'saves/'); }
  catch (e) { if (!missing(e)) throw e; }
  for (const path of F.settings) {
    try { files.push({path, file: await (await root.getFileHandle(path)).getFile()}); }
    catch (e) { if (!missing(e)) throw e; }
  }
  return files.sort((a,b) => a.path.localeCompare(b.path));
}
async function parse(file) {
  if (!file || file.size > 180 * 1024 * 1024) throw Error('Backup is missing or larger than 180 MB.');
  let archive;
  try { archive = JSON.parse(await file.text()); } catch { throw Error('The selected file is not a readable save backup.'); }
  F.validate(archive);
  return archive;
}
async function backup(root) {
  const found = await entries(root);
  if (!found.length) throw Error('No saves or settings have been stored yet.');
  let total = 0;
  for (const item of found)
    if (item.file.size > F.MAX_FILE || (total += item.file.size) > F.MAX_BYTES) throw Error('Save data exceeds the 128 MB backup limit (32 MB per file).');
  const archive = {type: 'nfl2k5-browser-save', version: 1, createdAt: new Date().toISOString(), files: []};
  for (const item of found) {
    progress('Backing up ' + item.path);
    const data = new Uint8Array(await item.file.arrayBuffer());
    archive.files.push({path: item.path, size: data.length, sha256: await F.digest(data), data: F.encode(data)});
  }
  F.validate(archive);
  return {blob: new Blob([JSON.stringify(archive)], {type: 'application/json'}), files: found.length, bytes: total};
}
async function restore(root, archive) {
  // Stage and verify every new byte before touching existing saves.
  const stage = await root.getDirectoryHandle(STAGE, {create: true});
  await journal(stage, {type: 'nfl2k5-restore', version: 1, state: 'preparing'});
  let writing = false;
  try {
    const records = [], dirs = new Set();
    for (let i = 0; i < archive.files.length; i++) {
      const entry = archive.files[i]; progress('Checking ' + entry.path);
      const data = F.decode(entry.data);
      if (data.length !== entry.size || await F.digest(data) !== entry.sha256)
        throw Error('Backup integrity check failed for ' + entry.path + '. Existing saves were kept.');
      await write(await fileHandle(stage, 'new/' + i, true), data);
      let old;
      try { old = await fileHandle(root, entry.path); } catch (e) { if (!missing(e)) throw e; }
      if (old) await copy(old, await fileHandle(stage, 'old/' + i, true));
      records.push({path: entry.path, hadOriginal: !!old});
      const parts = entry.path.split('/'); parts.pop();
      for (let n = 1; n <= parts.length; n++) {
        const path = parts.slice(0, n).join('/');
        try { await directory(root, path); } catch (e) { if (!missing(e)) throw e; dirs.add(path); }
      }
    }
    const j = {type: 'nfl2k5-restore', version: 1, state: 'writing', files: records, directories: [...dirs]};
    await journal(stage, j); writing = true;
    for (let i = 0; i < records.length; i++) {
      progress('Restoring ' + records[i].path);
      await copy(await fileHandle(stage, 'new/' + i), await fileHandle(root, records[i].path, true));
    }
    await journal(stage, {...j, state: 'committed'});
    // A committed journal is safe to clean up on the next visit if cleanup
    // alone fails. The restored saves are already complete at this point.
    await root.removeEntry(STAGE, {recursive: true}).catch(() => {});
    return F.validate(archive);
  } catch (e) {
    // The journal also rolls back an interrupted commit on the next launch.
    try { await recover(root); }
    catch (recovery) { throw Object.assign(new Error(e.message + ' Reload the launcher to recover the retained originals. ' + recovery.message), {code: 'RECOVERY'}); }
    throw new Error(e.message + (writing ? ' Previous saves have been restored.' : ''));
  }
}
onmessage = async ({data}) => {
  try {
    const root = await navigator.storage.getDirectory();
    await recover(root);
    let result;
    switch (data.action) {
      case 'recover': result = {ok: true}; break;
      case 'status': {
        const found = await entries(root);
        result = {files: found.length, bytes: found.reduce((n,f) => n + f.file.size, 0), latest: Math.max(0, ...found.map(f => f.file.lastModified))}; break;
      }
      case 'export': result = await backup(root); break;
      case 'inspect': result = F.validate(await parse(data.file)); break;
      case 'restore': result = await restore(root, await parse(data.file)); break;
      default: throw Error('Unknown save operation.');
    }
    postMessage({type: 'done', result});
  } catch (e) { postMessage({type: 'error', message: e.message, code: typeof e.code === 'string' ? e.code : 'STORAGE'}); }
};
