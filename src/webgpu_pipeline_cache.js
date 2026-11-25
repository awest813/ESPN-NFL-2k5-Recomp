/* Optional WebGPU pipeline preparation. This script is bundled inside the Wasm
 * launcher and started on the WebGPU device's worker before it creates layouts. */
(() => {
  'use strict';

  const MAX_RECIPES = 6;
  const MAX_SHADER = 96 * 1024;
  const MAX_STATE = 16 * 1024;
  const MAX_LAYOUT = 32 * 1024;
  const HISTORY = 48;
  const GRACE_MS = 8000;
  const PREPARE_BUDGET_MS = 1200;
  const STORE = 'recipes';
  const STORAGE_KEY = 'recent';

  const encode = value => JSON.stringify(value, (_, item) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) return item;
    return Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]]));
  });

  const identity = item => JSON.stringify([item.state, item.vertex, item.fragment]);

  async function storage(write, value) {
    const db = await new Promise((resolve, reject) => {
      const request = indexedDB.open('nfl2k5-webgpu-pipelines', 1);
      request.onupgradeneeded = () => request.result.createObjectStore(STORE);
      request.onblocked = () => reject(new Error('Pipeline storage is blocked'));
      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result);
    });
    try {
      return await new Promise((resolve, reject) => {
        const transaction = db.transaction(STORE, write ? 'readwrite' : 'readonly');
        const store = transaction.objectStore(STORE);
        const request = write ? store.put(value, STORAGE_KEY) : store.get(STORAGE_KEY);
        transaction.oncomplete = () => resolve(request.result);
        transaction.onabort = () => reject(transaction.error);
      });
    } finally { db.close(); }
  }

  function bounded(item) {
    return item && typeof item.state === 'string' && item.state.length <= MAX_STATE &&
      typeof item.vertex === 'string' && item.vertex.length <= MAX_SHADER &&
      typeof item.fragment === 'string' && item.fragment.length <= MAX_SHADER;
  }

  let observe = idle;

  function start(mode, revision, trace) {
    if (observe !== idle || !/^[a-f0-9]{64}$/.test(revision) ||
        !['1', 'learn', 'warm'].includes(mode) || !globalThis.GPUDevice ||
        !globalThis.GPURenderPassEncoder || !globalThis.indexedDB)
      return false;

    const learning = mode !== 'warm';
    const warming = mode !== 'learn';
    const report = (event, data) => {
      if (trace) console.debug('NFL_WARM ' + JSON.stringify({event, at:performance.timeOrigin + performance.now(), ...data}));
    };
    const deviceApi = GPUDevice.prototype;
    const passApi = GPURenderPassEncoder.prototype;
    const createShader = deviceApi.createShaderModule;
    const createGroup = deviceApi.createBindGroupLayout;
    const createLayout = deviceApi.createPipelineLayout;
    const create = deviceApi.createRenderPipeline;
    const prepare = deviceApi.createRenderPipelineAsync;
    const setPipeline = passApi.setPipeline;

    const shaders = new WeakMap(), groups = new WeakMap(), layouts = new WeakMap();
    const pending = new WeakMap();
    const resident = new Map(), selected = new Map();
    const recent = [];

    let active, lastSaved = '', saving = false, latestRecord;

    async function save(record) {
      latestRecord = record;
      if (saving) return;
      saving = true;
      try {
        while (latestRecord) {
          const next = latestRecord;
          latestRecord = undefined;
          await storage(true, next);
          report('stored', {count:next.items.length});
        }
      } catch { report('storage-failed', {}); }
      finally { saving = false; }
    }

    function recipe(desc) {
      if (!active || desc.layout !== active.layout || !desc.fragment ||
          desc.vertex.buffers?.[0]?.stepMode !== 'vertex') return null;
      const vertex = shaders.get(desc.vertex.module), fragment = shaders.get(desc.fragment.module);
      if (!vertex || !fragment) return null;
      const state = {...desc, vertex:{...desc.vertex}, fragment:{...desc.fragment}};
      delete state.layout;
      delete state.vertex.module;
      delete state.fragment.module;
      const item = {state:encode(state), vertex, fragment};
      return bounded(item) ? item : null;
    }

    async function warm(current) {
      try {
        const cache = await storage(false);
        const items = cache?.revision === revision && cache.layout === current.key &&
          Array.isArray(cache.items) ? cache.items.slice(0, MAX_RECIPES).filter(bounded) : [];
        report('loaded', {count:items.length});
        const modules = new Map();
        const module = source => {
          if (!modules.has(source)) modules.set(source, createShader.call(current.device, {code:source}));
          return modules.get(source);
        };
        const start = performance.now();
        for (const item of items) {
          if (current.lost || performance.now() - start >= PREPARE_BUDGET_MS) break;
          try {
            const d = JSON.parse(item.state);
            // Capture errors from this recipe. Pop before waiting so live
            // renders and other preparations keep their own error reporting.
            current.device.pushErrorScope('validation');
            let building;
            try {
              building = prepare.call(current.device, {
                ...d, layout:current.layout, vertex:{...d.vertex, module:module(item.vertex)},
                fragment:{...d.fragment, module:module(item.fragment)},
              });
            } catch (error) { building = Promise.reject(error); }
            const [pipe, validation] = await Promise.all([building, current.device.popErrorScope()]);
            if (validation) { report('prepare-failed', {}); continue; }
            if (current.lost) break;
            resident.set(identity(item), {pipe, used:false});
            report('ready', {count:resident.size});
          } catch { report('prepare-failed', {}); }
        }
      } catch { report('storage-failed', {}); }
    }

    deviceApi.createShaderModule = function(desc) {
      const result = createShader.call(this, desc);
      if (typeof desc.code === 'string' && desc.code.length <= MAX_SHADER && !desc.compilationHints?.length)
        shaders.set(result, desc.code);
      return result;
    };
    deviceApi.createBindGroupLayout = function(desc) {
      const result = createGroup.call(this, desc);
      groups.set(result, desc);
      return result;
    };
    deviceApi.createPipelineLayout = function(desc) {
      const result = createLayout.call(this, desc);
      const bindings = desc.bindGroupLayouts.map(item => groups.get(item));
      if (bindings.length && bindings.every(Boolean)) {
        const key = encode({...desc, bindGroupLayouts:bindings});
        if (key.length <= MAX_LAYOUT) layouts.set(result, key);
      }
      return result;
    };
    deviceApi.createRenderPipelineAsync = function(desc) {
      const result = prepare.call(this, desc);
      const key = layouts.get(desc.layout);
      if (active || !key) return result;
      const current = {device:this, layout:desc.layout, key, since:performance.now(), lost:false};
      active = current;
      this.lost.then(() => { current.lost = true; resident.clear(); });
      if (warming) result.then(() => setTimeout(() => warm(current), 2500), () => {});
      return result;
    };
    deviceApi.createRenderPipeline = function(desc) {
      const item = active?.device === this && !active.lost && recipe(desc);
      const entry = item && resident.get(identity(item));
      if (entry) {
        if (!entry.used) { entry.used = true; report('hit', {}); }
        return entry.pipe;
      }
      const result = create.call(this, desc);
      if (item && learning) pending.set(result, item);
      return result;
    };
    passApi.setPipeline = function(pipeline) {
      const item = pending.get(pipeline);
      if (item) {
        pending.delete(pipeline);
        const now = performance.now();
        if (now - active.since >= GRACE_MS) {
          const key = identity(item);
          if (!recent.some(entry => entry.key === key)) {
            if (recent.length === HISTORY) recent.shift();
            recent.push({key, item, first:now});
          }
        }
      }
      return setPipeline.call(this, pipeline);
    };

    observe = elapsed => {
      if (!learning || !active || active.lost) return;
      const end = performance.now(), begin = end - elapsed;
      for (const candidate of recent) {
        if (candidate.first < begin - 250 || candidate.first > end) continue;
        const score = elapsed / (1 + Math.abs(candidate.first - begin) / 90);
        const old = selected.get(candidate.key);
        if (!old || old.score < score) selected.set(candidate.key, {...candidate, score});
      }
      const ranked = [...selected.values()].sort((a, b) => b.score - a.score).slice(0, MAX_RECIPES);
      selected.clear();
      for (const candidate of ranked) selected.set(candidate.key, candidate);
      const stamp = JSON.stringify(ranked.map(candidate => candidate.key));
      if (!ranked.length || stamp === lastSaved) return;
      lastSaved = stamp;
      void save({revision, layout:active.key, items:ranked.map(candidate => candidate.item)});
    };
    return true;
  }

  function idle() {}
  globalThis['NFL2K5PipelineCache'] = {'start':start, 'observe':elapsed => observe(elapsed)};
})();
