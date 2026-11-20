'use strict';
const fs=require('node:fs'),path=require('node:path');
module.exports=async function checkDepth16(page,dir) {
  const reference=fs.readFileSync(path.join(dir,'depth16-reference.bin'));
  const expected=Array.from(new Uint32Array(reference.buffer,reference.byteOffset,reference.byteLength/4));
  if(expected.length!==65536)throw Error('Incomplete independent D16 reference');
  const shader=fs.readFileSync(path.join(dir,'depth16-fragment.wgsl'),'utf8');
  await page.evaluate(async({shader,expected})=>{
    const adapter=await navigator.gpu.requestAdapter();if(!adapter)throw Error('No WebGPU adapter');
    const device=await adapter.requestDevice();
    const bytes=expected.length*4;
    const output=device.createBuffer({size:bytes,usage:GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_SRC});
    const read=device.createBuffer({size:bytes,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
    try {
      const module=device.createShaderModule({code:shader+`
        @group(0) @binding(0) var<storage,read_write> d16_results:array<u32>;
        @compute @workgroup_size(64) fn check_depth16(@builtin(global_invocation_id) id:vec3u) {
          if(id.x<65536u){d16_results[id.x]=bitcast<u32>(integer_d16_normalized(f32(id.x)));}
        }`});
      const pipeline=await device.createComputePipelineAsync({layout:'auto',compute:{module,entryPoint:'check_depth16'}});
      const group=device.createBindGroup({layout:pipeline.getBindGroupLayout(0),entries:[{binding:0,resource:{buffer:output}}]});
      const encoder=device.createCommandEncoder(),pass=encoder.beginComputePass();
      pass.setPipeline(pipeline);pass.setBindGroup(0,group);pass.dispatchWorkgroups(1024);pass.end();
      encoder.copyBufferToBuffer(output,0,read,0,bytes);device.queue.submit([encoder.finish()]);
      await read.mapAsync(GPUMapMode.READ);
      const actual=new Uint32Array(read.getMappedRange());
      for(let n=0;n<expected.length;n++)if(actual[n]!==expected[n])throw Error(`D16 ${n}: bits ${actual[n].toString(16)} expected ${expected[n].toString(16)}`);
      read.unmap();
    }finally{output.destroy();read.destroy();device.destroy();}
  },{shader,expected});
  console.log('PASS all 65536 production GPU D16 encodings against independent double-precision reference');
};
