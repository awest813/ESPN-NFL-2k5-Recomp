// A game session and file-management operations share one origin-wide lock.
// The game keeps its lock until the page closes: WasmFS may retain file handles.
'use strict';
window.NFL2K5Storage = (() => {
  const name = 'nfl2k5-storage';
  const busy = () => Object.assign(new Error('Another NFL 2K5 tab is using game storage. Close it and try again.'), {code: 'BUSY'});
  async function withLock(task) {
    if (!navigator.locks) return task();
    return navigator.locks.request(name, {ifAvailable: true}, lock => {
      if (!lock) throw busy();
      return task();
    });
  }
  async function acquireSession() {
    if (!navigator.locks) return () => {};
    return new Promise((resolve, reject) => {
      navigator.locks.request(name, {ifAvailable: true}, lock => {
        if (!lock) { reject(busy()); return; }
        return new Promise(release => resolve(release));
      }).catch(reject);
    });
  }
  function run(action, file, onProgress) {
    return new Promise((resolve, reject) => {
      let worker;
      const fail = e => { worker?.terminate(); reject(e); };
      try { worker = new Worker('save-worker.js'); } catch (e) { reject(e); return; }
      worker.onerror = e => { e.preventDefault(); fail(new Error(e.message || 'Save storage worker stopped.')); };
      worker.onmessageerror = () => fail(new Error('Unreadable save storage response.'));
      worker.onmessage = e => {
        if (e.data.type === 'progress') { onProgress?.(e.data.message); return; }
        worker.terminate();
        if (e.data.type === 'error') reject(Object.assign(new Error(e.data.message), {code: e.data.code}));
        else resolve(e.data.result);
      };
      try { worker.postMessage({action, file}); } catch (e) { fail(e); }
    });
  }
  return {withLock, acquireSession, run};
})();
