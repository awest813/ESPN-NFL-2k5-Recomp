// Execute the entire production VP epilogue; arithmetic-only tests omit it.
'use strict';
module.exports = async function checkPosition(page, source, layout) {
  const count = await page.evaluate(async source => {
    const values = [-640.999, -16.063, -16.0625, -16.0624, -0.063,
      -0.0625, -0.0624, -0.001, 0, 0.001, 0.0624, 0.0625, 0.063,
      16.0624, 16.0625, 16.063, 319.999, 640.999];
    const cases = [];
    for (const x of values) for (const w of [0.25, 1, 2, -2])
      cases.push([Math.fround(x), Math.fround(-x + 0.03), 12345.25, w]);
    // Keep the real main body and its position conversion, changing only
    // the entry-point annotation so a compute shader can capture the result.
    const code = source.replace('@vertex fn main(vin: VpInputs)', 'fn run(vin: VpInputs)') + `
      @group(0) @binding(0) var<storage, read> positions: array<vec4f>;
      @group(0) @binding(1) var<storage, read_write> result: array<vec4f>;
      @compute @workgroup_size(32) fn test(@builtin(global_invocation_id) id: vec3u) {
        if (id.x < arrayLength(&positions)) {
          var vin: VpInputs;
          vin.v0 = positions[id.x];
          result[id.x] = run(vin).position;
        }
      }`;
    const module = device.createShaderModule({code});
    const info = await module.getCompilationInfo();
    const errors = info.messages.filter(m => m.type === 'error');
    if (errors.length) throw Error(errors.map(e => e.message).join('\n'));
    const pipeline = await device.createComputePipelineAsync({layout: 'auto', compute: {module, entryPoint: 'test'}});
    const data = new Float32Array(cases.flat());
    const input = device.createBuffer({size: data.byteLength, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST});
    const output = device.createBuffer({size: data.byteLength, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC});
    const read = device.createBuffer({size: data.byteLength, usage: GPUBufferUsage.MAP_READ | GPUBufferUsage.COPY_DST});
    const uniform = device.createBuffer({size: 3136, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST});
    const io = device.createBindGroup({layout: pipeline.getBindGroupLayout(0), entries: [
      {binding: 0, resource: {buffer: input}}, {binding: 1, resource: {buffer: output}}]});
    const u = device.createBindGroup({layout: pipeline.getBindGroupLayout(1), entries: [
      {binding: 0, resource: {buffer: uniform}}]});
    device.queue.writeBuffer(input, 0, data);
    let checks = 0;
    try {
      for (const [width, height, offset] of [[640,480,0], [854,480,107], [1920,1080,320]]) {
        const uniforms = new Float32Array(784);
        uniforms.set([width,height,65535,offset], 768);
        device.queue.writeBuffer(uniform, 0, uniforms);
        const encoder = device.createCommandEncoder(), pass = encoder.beginComputePass();
        pass.setPipeline(pipeline);pass.setBindGroup(0, io);pass.setBindGroup(1, u);
        pass.dispatchWorkgroups(Math.ceil(cases.length / 32));pass.end();
        encoder.copyBufferToBuffer(output, 0, read, 0, data.byteLength);
        device.queue.submit([encoder.finish()]);await read.mapAsync(GPUMapMode.READ);
        const actual = new Float32Array(read.getMappedRange());
        for (let i = 0; i < cases.length; i++) {
          const [x,y,z,w] = cases[i];
          // Explicit expected screen grid; no production helper as oracle.
          // A float32 value times 16 is exact in this bounded range.
          const sx = (x < 0 ? -Math.floor(-x * 16) : Math.floor(x * 16)) / 16;
          const sy = (y < 0 ? -Math.floor(-y * 16) : Math.floor(y * 16)) / 16;
          const expected = [((sx+offset)/width*2-1)*w, (1-sy/height*2)*w, z/65535*w, w];
          for (let k = 0; k < 4; k++) {
            const a = actual[i*4+k], e = expected[k];
            // Host GPU division may differ by a few float32 ULPs. This
            // tolerance is well below one 1/16-pixel step on these surfaces.
            if (!Number.isFinite(a) || Math.abs(a-e) > 5e-7*Math.max(1,Math.abs(e)))
              throw Error(`VP position ${i} component ${k}, surface ${width}: GPU ${a}, expected ${e}; input ${cases[i]}`);
            checks++;
          }
        }
        read.unmap();
      }
    } finally { [input,output,read,uniform].forEach(b => b.destroy()); }
    if (window.gpuError) throw Error(window.gpuError);
    return checks;
  }, source);
  console.log(`PASS ${count} production VP position checks: signed subpixel grid, non-unit W and widescreen offsets`);
  const pixels = await page.evaluate(async ({source, layout}) => {
    const module = device.createShaderModule({code: source + `
      @fragment fn fragment(v: VpOutputs) -> @location(0) vec4f { return v.color; }`});
    const pipeline = await device.createRenderPipelineAsync({layout: 'auto',
      vertex: {module, entryPoint: 'main', buffers: [{arrayStride: layout.stride, attributes: layout.attributes}]},
      fragment: {module, entryPoint: 'fragment', targets: [{format: 'rgba8unorm'}]}});
    const vb = device.createBuffer({size: 6*layout.stride, usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST});
    const ub = device.createBuffer({size: 3136, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST});
    const io = device.createBindGroup({layout: pipeline.getBindGroupLayout(0), entries: []});
    const uniform = device.createBindGroup({layout: pipeline.getBindGroupLayout(1), entries: [{binding:0,resource:{buffer:ub}}]});
    let checked = 0;
    try {
      for (const offset of [0,16]) for (const w of [1,2]) {
        const width = 64+offset*2, height = 64;
        const values = new Float32Array(6*12);
        const xy = [[16.559,8.559],[48.559,8.559],[48.559,40.559],
          [16.559,8.559],[48.559,40.559],[16.559,40.559]];
        for (let k=0;k<6;k++) values.set([...xy[k],.25,w,1,1,1,1,0,0,0,1],k*12);
        const uniforms = new Float32Array(784);uniforms.set([width,height,1,offset],768);
        device.queue.writeBuffer(vb,0,values);device.queue.writeBuffer(ub,0,uniforms);
        const target = device.createTexture({size:[width,height],format:'rgba8unorm',
          usage:GPUTextureUsage.RENDER_ATTACHMENT|GPUTextureUsage.COPY_SRC});
        const pitch = Math.ceil(width*4/256)*256;
        const read = device.createBuffer({size:pitch*height,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
        try {
          const encoder = device.createCommandEncoder();
          const pass = encoder.beginRenderPass({colorAttachments:[{view:target.createView(),
            clearValue:[0,0,0,1],loadOp:'clear',storeOp:'store'}]});
          pass.setPipeline(pipeline);pass.setBindGroup(0,io);pass.setBindGroup(1,uniform);
          pass.setVertexBuffer(0,vb);pass.draw(6);pass.end();
          encoder.copyTextureToBuffer({texture:target},{buffer:read,bytesPerRow:pitch},[width,height]);
          device.queue.submit([encoder.finish()]);await read.mapAsync(GPUMapMode.READ);
          const bytes = new Uint8Array(read.getMappedRange());
          for(let y=0;y<height;y++) for(let x=0;x<width;x++) {
            const expected = x>=16+offset && x<48+offset && y>=8 && y<40 ? 255 : 0;
            const at=y*pitch+x*4;
            if(bytes[at]!==expected || bytes[at+1]!==expected || bytes[at+2]!==expected || bytes[at+3]!==255)
              throw Error(`Snapped VP coverage ${x},${y}, offset ${offset}, W ${w}: ${Array.from(bytes.slice(at,at+4))}`);
            checked++;
          }
          read.unmap();
        } finally {target.destroy();read.destroy();}
      }
    } finally {vb.destroy();ub.destroy();}
    if(window.gpuError) throw Error(window.gpuError);
    return checked;
  }, {source,layout});
  console.log(`PASS ${pixels} rendered VP edge pixels: fractional boundaries, non-unit W and widescreen offsets`);
};
