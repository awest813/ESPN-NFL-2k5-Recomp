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

  const sameRecipe = (a, b) =>
    a.vertex === b.vertex && a.fragment === b.fragment && a.state === b.state;

  function pipelineState(desc) {
    const state = {...desc, vertex:{...desc.vertex}, fragment:{...desc.fragment}};
    delete state.layout;
    delete state.vertex.module;
    delete state.fragment.module;
    return encode(state);
  }

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
    const resident = [];
    const recent = [];

    let active, selected = [], saving = false, latestRecord;

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
      const vertex = shaders.get(desc.vertex.module), fragment = shaders.get(desc.fragment.module);
      if (!vertex || !fragment) return null;
      const item = {state:pipelineState(desc), vertex, fragment};
      return bounded(item) ? item : null;
    }

    function prepared(desc) {
      if (!resident.length) return;
      const vertex = shaders.get(desc.vertex.module), fragment = shaders.get(desc.fragment.module);
      let state;
      for (const entry of resident) {
        if (entry.item.vertex !== vertex || entry.item.fragment !== fragment) continue;
        // A shader miss does not need a canonical render descriptor.
        state ??= pipelineState(desc);
        if (entry.item.state === state) return entry;
      }
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
            resident.push({item, pipe, used:false});
            report('ready', {count:resident.length});
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
      this.lost.then(() => { current.lost = true; resident.length = 0; });
      if (warming) result.then(() => setTimeout(() => warm(current), 2500), () => {});
      return result;
    };
    deviceApi.createRenderPipeline = function(desc) {
      if (active?.device !== this || active.lost || desc.layout !== active.layout || !desc.fragment ||
          desc.vertex.buffers?.[0]?.stepMode !== 'vertex')
        return create.call(this, desc);
      const entry = prepared(desc);
      if (entry) {
        if (!entry.used) { entry.used = true; report('hit', {}); }
        return entry.pipe;
      }
      const result = create.call(this, desc);
      if (learning) {
        const item = recipe(desc);
        if (item) pending.set(result, item);
      }
      return result;
    };
    passApi.setPipeline = function(pipeline) {
      const item = pending.get(pipeline);
      if (item) {
        pending.delete(pipeline);
        const now = performance.now();
        if (now - active.since >= GRACE_MS) {
          const matches = entry => sameRecipe(entry.item, item);
          if (!recent.some(matches) && !selected.some(matches)) {
            if (recent.length === HISTORY) recent.shift();
            recent.push({item, first:now, score:0});
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
        candidate.score = Math.max(candidate.score, score);
      }
      const ranked = [...new Set([...selected, ...recent.filter(item => item.score)])]
        .sort((a, b) => b.score - a.score).slice(0, MAX_RECIPES);
      if (ranked.length === selected.length && ranked.every((item, i) => item === selected[i])) return;
      selected = ranked;
      void save({revision, layout:active.key, items:ranked.map(candidate => candidate.item)});
    };
    return true;
  }

  function idle() {}
  globalThis['NFL2K5PipelineCache'] = {'start':start, 'observe':elapsed => observe(elapsed)};
})();
