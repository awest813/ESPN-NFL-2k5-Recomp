// Compare generated production WGSL on WebGPU with the CPU reference.
// NODE_PATH must provide playwright. Use installed Chrome for a hardware run.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const {chromium} = require('playwright');
const dir = path.resolve(process.argv[2] || 'build-web-tests/vp-wgsl');
const server = http.createServer((req, res) => { res.end('<!doctype html><title>Vertex program tests</title>'); });
(async () => {
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  try {
    const page = await browser.newPage();
    await page.goto(`http://127.0.0.1:${server.address().port}`);
    await page.evaluate(async () => {
      const adapter = await navigator.gpu.requestAdapter();
      if (!adapter) throw Error('No WebGPU adapter');
      window.device = await adapter.requestDevice();
      device.addEventListener('uncapturederror', e => { window.gpuError = e.error.message; });
    });
    let count = 0;
    for (const file of fs.readdirSync(dir).filter(n => /^case-\d+\.wgsl$/.test(n)).sort()) {
      console.log('Checking', file);
      const base = path.join(dir, file.replace('.wgsl', ''));
      const floats = suffix => Array.from(new Float32Array(Uint8Array.from(fs.readFileSync(base + suffix)).buffer));
      const result = await page.evaluate(async ({source, constants, inputs, expected}) => {
        const check = async code => {
          const module = device.createShaderModule({code});
          const info = await module.getCompilationInfo();
          const errors = info.messages.filter(m => m.type === 'error');
          if (errors.length) throw Error(errors.map(e => e.message).join('\n'));
          return module;
        };
        // Validate the actual vertex entry point as well as running its arithmetic.
        await check(source);
        let code = source.slice(0, source.lastIndexOf('    let p = O[0];'));
        code = code.replace('@vertex fn main(vin: VpInputs) -> VpOutputs', 'fn run(vin: VpInputs) -> TestOutput');
        code += '    return TestOutput(O, R);\n}\n';
        code += `struct TestOutput { o: array<vec4f, 16>, r: array<vec4f, 13> }
          @group(0) @binding(0) var<storage, read> inputs: array<VpInputs>;
          @group(0) @binding(1) var<storage, read_write> outputs: array<TestOutput>;
          @compute @workgroup_size(32) fn test(@builtin(global_invocation_id) id: vec3u) {
            if (id.x < arrayLength(&inputs)) { outputs[id.x] = run(inputs[id.x]); }
          }`;
        const module = await check(code);
        const pipeline = await device.createComputePipelineAsync({layout: 'auto', compute: {module, entryPoint: 'test'}});
        const buffer = (data, usage, minSize = 0) => {
          const b = device.createBuffer({size: Math.max(minSize, data.length * 4), usage: usage | GPUBufferUsage.COPY_DST});
          if (data.length) device.queue.writeBuffer(b, 0, new Float32Array(data));
          return b;
        };
        const input = buffer(inputs, GPUBufferUsage.STORAGE);
        const output = buffer([], GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC, expected.length * 4);
        const uniform = buffer(constants, GPUBufferUsage.UNIFORM, 3136);
        const read = device.createBuffer({size: expected.length * 4, usage: GPUBufferUsage.MAP_READ | GPUBufferUsage.COPY_DST});
        const io = device.createBindGroup({layout: pipeline.getBindGroupLayout(0), entries: [
          {binding: 0, resource: {buffer: input}}, {binding: 1, resource: {buffer: output}}]});
        const u = device.createBindGroup({layout: pipeline.getBindGroupLayout(1), entries: [{binding: 0, resource: {buffer: uniform}}]});
        const enc = device.createCommandEncoder(); const pass = enc.beginComputePass();
        pass.setPipeline(pipeline); pass.setBindGroup(0, io); pass.setBindGroup(1, u);
        pass.dispatchWorkgroups(Math.ceil(inputs.length / 64 / 32)); pass.end();
        enc.copyBufferToBuffer(output, 0, read, 0, expected.length * 4); device.queue.submit([enc.finish()]);
        await read.mapAsync(GPUMapMode.READ);
        const actual = new Float32Array(read.getMappedRange());
        for (let i = 0; i < expected.length; i++) {
          const a = actual[i], e = expected[i];
          if (Object.is(a, e) || (Number.isNaN(a) && Number.isNaN(e))) continue;
          if (Number.isFinite(a) && Number.isFinite(e) && Math.abs(a - e) <= 2e-5 + 3e-4 * Math.abs(e)) continue;
          throw Error(`value ${i}: GPU ${a}, CPU ${e}`);
        }
        read.unmap(); [input, output, uniform, read].forEach(b => b.destroy());
        if (window.gpuError) throw Error(window.gpuError);
        return inputs.length / 64;
      }, {source: fs.readFileSync(base + '.wgsl', 'utf8'), constants: floats('.constants.bin'), inputs: floats('.inputs.bin'), expected: floats('.expected.bin')});
      count += result;
    }
    if (!count) throw Error('No cases found; run test_vp_wgsl.py first');
    console.log(`PASS ${count} GPU vertex executions, outputs and temporary registers match CPU reference`);
    await page.evaluate(async ({source, layout, vertices, uniforms}) => {
      const module = device.createShaderModule({code: source + `
        @fragment fn fragment(v: VpOutputs) -> @location(0) vec4f {
          return vec4f(v.color.rgb + v.t0.rgb, 1.0);
        }`});
      const pipeline = await device.createRenderPipelineAsync({layout: 'auto',
        vertex: {module, entryPoint: 'main', buffers: [{arrayStride: layout.stride, attributes: layout.attributes}]},
        fragment: {module, entryPoint: 'fragment', targets: [{format: 'rgba8unorm'}]}});
      const vb = device.createBuffer({size: vertices.length, usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST});
      const ub = device.createBuffer({size: uniforms.length, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST});
      device.queue.writeBuffer(vb, 0, Uint8Array.from(vertices));
      device.queue.writeBuffer(ub, 0, Uint8Array.from(uniforms));
      const target = device.createTexture({size: [4, 4], format: 'rgba8unorm', usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.COPY_SRC});
      const read = device.createBuffer({size: 1024, usage: GPUBufferUsage.MAP_READ | GPUBufferUsage.COPY_DST});
      const enc = device.createCommandEncoder();
      const pass = enc.beginRenderPass({colorAttachments: [{view: target.createView(), clearValue: [0,0,0,0], loadOp: 'clear', storeOp: 'store'}]});
      pass.setPipeline(pipeline);
      pass.setBindGroup(0, device.createBindGroup({layout: pipeline.getBindGroupLayout(0), entries: []}));
      pass.setBindGroup(1, device.createBindGroup({layout: pipeline.getBindGroupLayout(1), entries: [{binding: 0, resource: {buffer: ub}}]}));
      pass.setVertexBuffer(0, vb); pass.draw(3); pass.end();
      enc.copyTextureToBuffer({texture: target}, {buffer: read, bytesPerRow: 256}, [4, 4]);
      device.queue.submit([enc.finish()]); await read.mapAsync(GPUMapMode.READ);
      const bytes = new Uint8Array(read.getMappedRange());
      for (let y = 0; y < 4; y++) for (let x = 0; x < 4; x++) {
        const at = y * 256 + x * 4;
        if (Math.abs(bytes[at] - 96) > 1 || Math.abs(bytes[at+1] - 191) > 1 || bytes[at+2] !== 255 || bytes[at+3] !== 255)
          throw Error(`Packed attribute layout failed at ${x},${y}: ${Array.from(bytes.slice(at, at+4))}`);
      }
      read.unmap(); [vb, ub, target, read].forEach(b => b.destroy());
      if (window.gpuError) throw Error(window.gpuError);
    }, {source: fs.readFileSync(path.join(dir, 'compact.wgsl'), 'utf8'),
      layout: JSON.parse(fs.readFileSync(path.join(dir, 'compact.layout.json'), 'utf8')),
      vertices: Array.from(fs.readFileSync(path.join(dir, 'compact.vertices.bin'))),
      uniforms: Array.from(fs.readFileSync(path.join(dir, 'compact.uniforms.bin')))});
    console.log('PASS compact vertex attributes use the production pipeline layout');
  } finally { await browser.close(); }
})().catch(e => {console.error(e); process.exitCode = 1;}).finally(() => server.close());
