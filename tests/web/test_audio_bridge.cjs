// Execute the production EM_ASM bridge with deferred worklet loading.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../external/xboxrecomp/src/apu/apu_web_audio.c'), 'utf8');
const openBody = source.match(/MAIN_THREAD_EM_ASM_INT\(\{([\s\S]*?)\n    \}, ring\);/)[1];
const closeBody = source.match(/void web_audio_close[\s\S]*?MAIN_THREAD_EM_ASM\(\{([\s\S]*?)\n    \}\);/)[1];
const flush = () => new Promise(resolve => setImmediate(resolve));

function fixture({failMonitor = false} = {}) {
  const pending = [], nodes = [], errors = [];
  const ctx = {sampleRate: 48000, destination: {}, audioWorklet: {
    addModule: () => new Promise((resolve, reject) => pending.push({resolve, reject})),
  }};
  class Node {
    constructor(context, name, options) {
      if (failMonitor && name === 'nfl2k5-audio-clock') throw Error('monitor construction failed');
      this.context = context; this.name = name; this.options = options;
      this.connections = []; this.messages = []; this.disconnects = 0;
      this.port = {postMessage: value => this.messages.push(value)};
      nodes.push(this);
    }
    connect(destination) { this.connections.push(destination); }
    disconnect() { this.connections = []; this.disconnects++; }
  }
  const Module = {SDL3: {audioContext: ctx}};
  const args = [Module, {}, Node, {buffer: new SharedArrayBuffer(1024)}, 0, error => errors.push(error)];
  const names = ['Module', 'globalThis', 'AudioWorkletNode', 'HEAPU8', '$0', 'err'];
  const open = new Function(...names, openBody), close = new Function(...names, closeBody);
  return {Module, pending, nodes, errors, ctx, open: () => open(...args), close: () => close(...args)};
}

(async () => {
  {
    const f = fixture(); assert.equal(f.open(), 1);
    f.close(); f.pending[0].resolve(); await flush();
    assert.equal(f.Module.nfl2k5Audio.state, 'closed');
    assert.equal(f.nodes.length, 0, 'closing during load must not resurrect output');
  }
  {
    const f = fixture(); f.open(); const old = f.Module.nfl2k5Audio;
    f.close(); f.open(); f.pending[0].resolve(); await flush();
    assert.equal(f.nodes.length, 0, 'an old load must not attach to a replacement ring');
    f.pending[1].resolve(); await flush();
    const s = f.Module.nfl2k5Audio;
    assert.equal(s.state, 'running'); assert.equal(old.state, 'closed');
    assert.deepEqual(s.node.connections, [s.clockNode, f.ctx.destination]);
    assert.equal(s.clockNode.options.numberOfOutputs, 0);
    s.node.port.onmessage({data: {played: 2048}});
    s.clockNode.port.onmessage({data: {rendered: 4096}});
    assert.equal(s.played, 2048); assert.equal(s.rendered, 4096);
    f.close();
    for (const node of f.nodes) { assert.equal(node.disconnects, 1); assert.deepEqual(node.messages, ['stop']); }
    s.clockNode.onprocessorerror(); assert.equal(s.state, 'closed'); assert.deepEqual(f.errors, []);
  }
  {
    const f = fixture({failMonitor: true}); f.open(); f.pending[0].resolve(); await flush();
    assert.equal(f.Module.nfl2k5Audio.state, 'failed');
    assert.equal(f.nodes.length, 1); assert.equal(f.nodes[0].disconnects, 1);
    assert.deepEqual(f.nodes[0].messages, ['stop']); assert.equal(f.errors.length, 1);
  }
  {
    const f = fixture(); f.open(); f.close(); f.pending[0].reject(Error('late failure')); await flush();
    assert.equal(f.Module.nfl2k5Audio.state, 'closed'); assert.deepEqual(f.errors, []);
  }
  console.log('audio bridge: deferred loads, replacement rings, monitor wiring and shutdown passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
