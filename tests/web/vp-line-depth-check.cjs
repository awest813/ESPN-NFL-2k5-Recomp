// Render the generated instanced VP line path with its production fragment
// shader. Cases/expected integers come from the independent C double oracle.
'use strict';
const fs=require('node:fs'),path=require('node:path');
module.exports=async function checkLineDepth(page,dir) {
  const result=await page.evaluate(async ({vertex,fragment,data})=>{
    const check=async code=>{
      const module=device.createShaderModule({code});
      const errors=(await module.getCompilationInfo()).messages.filter(m=>m.type==='error');
      if(errors.length)throw Error(errors.map(e=>e.message).join('\n'));
      return module;
    };
    const vs=await check(vertex),fs=await check(fragment);
    const inputs=[];for(let i=0;i<16;i++)if(data.mask&(1<<i))inputs.push(i);
    const stride=inputs.length*2*16;
    const attributes=Array.from({length:inputs.length*2},(_,i)=>({shaderLocation:i,offset:i*16,format:'float32x4'}));
    const pipeline=await device.createRenderPipelineAsync({layout:'auto',
      vertex:{module:vs,entryPoint:'main',buffers:[{arrayStride:stride,stepMode:'instance',attributes}]},
      fragment:{module:fs,entryPoint:'main',targets:[{format:'rgba8unorm'}]},
      depthStencil:{format:'depth24plus-stencil8',depthWriteEnabled:true,depthCompare:'equal'}});
    const vb=device.createBuffer({size:stride,usage:GPUBufferUsage.VERTEX|GPUBufferUsage.COPY_DST});
    const vu=device.createBuffer({size:data.vertexUniformBytes,usage:GPUBufferUsage.UNIFORM|GPUBufferUsage.COPY_DST});
    const fu=device.createBuffer({size:data.shadeBytes+16,usage:GPUBufferUsage.UNIFORM|GPUBufferUsage.COPY_DST});
    const read=device.createBuffer({size:256,usage:GPUBufferUsage.MAP_READ|GPUBufferUsage.COPY_DST});
    const color=device.createTexture({size:[64,64],format:'rgba8unorm',usage:GPUTextureUsage.RENDER_ATTACHMENT|GPUTextureUsage.COPY_SRC});
    const depth=device.createTexture({size:[64,64],format:'depth24plus-stencil8',usage:GPUTextureUsage.RENDER_ATTACHMENT});
    const texture=device.createTexture({size:[1,1],format:'rgba8unorm',usage:GPUTextureUsage.TEXTURE_BINDING});
    const cube=device.createTexture({size:[1,1,6],format:'rgba8unorm',usage:GPUTextureUsage.TEXTURE_BINDING});
    const sampler=device.createSampler();
    const bindings=[];
    const re=/@group\(2\)\s*@binding\((\d+)\)\s*var\s+\w+\s*:\s*(texture_2d|texture_cube|sampler)\b/g;
    for(const match of fragment.matchAll(re))bindings.push({binding:Number(match[1]),resource:
      match[2]==='sampler'?sampler:match[2]==='texture_cube'?cube.createView({dimension:'cube'}):texture.createView()});
    if(bindings.length!==16)throw Error(`Expected eight production line texture/sampler pairs; got ${bindings.length}`);
    const groups=[
      device.createBindGroup({layout:pipeline.getBindGroupLayout(0),entries:[]}),
      device.createBindGroup({layout:pipeline.getBindGroupLayout(1),entries:[{binding:0,resource:{buffer:vu}}]}),
      device.createBindGroup({layout:pipeline.getBindGroupLayout(2),entries:bindings}),
      device.createBindGroup({layout:pipeline.getBindGroupLayout(3),entries:[{binding:0,resource:{buffer:fu}}]}),
    ];
    let checked=0;
    try {
      for(const c of data.cases) {
        const vertices=new Float32Array(stride/4);
        for(let side=0;side<2;side++)for(let i=0;i<inputs.length;i++) {
          const at=(side*inputs.length+i)*4;
          if(inputs[i]===0)vertices.set([c.x[side],20.5,c.w?0.5:c.depth[side],c.w?c.depth[side]:1],at);
          else if(inputs[i]===3)vertices.set([0,1,0,1],at);
        }
        const uniforms=new Float32Array(data.vertexUniformBytes/4),info=data.infoOffset/4;
        uniforms.set([64,64,16777216,0],info);
        uniforms.set([c.minimum,c.maximum,1,0],info+4);
        uniforms[info+14]=c.clip?0:1; // lightp.z: near-depth clip versus clamp
        uniforms.set([1,1,0,0],info+16); // line width and depth-enabled state
        const fragmentBytes=new ArrayBuffer(data.shadeBytes+16);
        const floats=new Float32Array(fragmentBytes),words=new Uint32Array(fragmentBytes),at=data.depthOffset/4;
        words[at]=4|c.w|(c.clip?2:0);floats[at+1]=16777216;
        floats[at+2]=c.minimum;floats[at+3]=c.maximum;
        floats[data.shadeBytes/4]=1/16777216;floats[data.shadeBytes/4+1]=1;
        device.queue.writeBuffer(vb,0,vertices);device.queue.writeBuffer(vu,0,uniforms);device.queue.writeBuffer(fu,0,fragmentBytes);
        // Correctly round the independent integer clear upward to f32.
        const normalized=new Float32Array([c.integer/16777215]);
        if(normalized[0]*16777215<c.integer)new Uint32Array(normalized.buffer)[0]++;
        const enc=device.createCommandEncoder();
        const pass=enc.beginRenderPass({colorAttachments:[{view:color.createView(),clearValue:[0,0,0,1],loadOp:'clear',storeOp:'store'}],
          depthStencilAttachment:{view:depth.createView(),depthClearValue:normalized[0],depthLoadOp:'clear',depthStoreOp:'store',
            stencilClearValue:0,stencilLoadOp:'clear',stencilStoreOp:'store'}});
        pass.setPipeline(pipeline);for(let i=0;i<groups.length;i++)pass.setBindGroup(i,groups[i]);
        pass.setVertexBuffer(0,vb);pass.setScissorRect(c.probe-1,18,3,6);pass.draw(6,1);pass.end();
        enc.copyTextureToBuffer({texture:color,origin:[c.probe,20]}, {buffer:read,bytesPerRow:256},[1,1]);
        device.queue.submit([enc.finish()]);await read.mapAsync(GPUMapMode.READ);
        const pixel=Array.from(new Uint8Array(read.getMappedRange(),0,4));read.unmap();
        const expected=c.visible?[0,255,0,255]:[0,0,0,255];
        if(pixel.some((v,i)=>v!==expected[i]))throw Error(`Instanced D24 line ${JSON.stringify(c)}: ${pixel} expected ${expected}`);
        if(window.gpuError)throw Error(window.gpuError);checked++;
      }
    } finally {[vb,vu,fu,read,color,depth,texture,cube].forEach(x=>x.destroy());}
    return checked;
  },{vertex:fs.readFileSync(path.join(dir,'compact-line.wgsl'),'utf8'),
    fragment:fs.readFileSync(path.join(dir,'compact-line-fragment.wgsl'),'utf8'),
    data:JSON.parse(fs.readFileSync(path.join(dir,'compact-line-depth.json'),'utf8'))});
  console.log(`PASS ${result} instanced GPU vertex-program D24 line pixels`);
};
