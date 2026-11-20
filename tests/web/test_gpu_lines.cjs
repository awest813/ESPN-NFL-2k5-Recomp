// Differential production GPU line rendering against CPU-prepared endpoints.
'use strict';
const fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {chromium}=require('playwright');
const dir=path.resolve(process.argv[2]||'build-web-tests/gpu-lines');
const server=http.createServer((req,res)=>res.end('<!doctype html><title>GPU line differential</title>'));
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage();await page.goto(`http://127.0.0.1:${server.address().port}`);
  const sources=Object.fromEntries(['line.wgsl','matrix-line.wgsl','line.frag.wgsl','baseline.vert.wgsl','baseline.frag.wgsl'].map(n=>[n,fs.readFileSync(path.join(dir,n),'utf8')]));
  await page.evaluate(async sources=>{
   const adapter=await navigator.gpu.requestAdapter();if(!adapter)throw Error('No WebGPU adapter');
   window.dev=await adapter.requestDevice();window.gpuErrors=[];dev.addEventListener('uncapturederror',e=>gpuErrors.push(e.error.message));
   window.modules={};
   window.inputLayout=sources.__layout;delete sources.__layout;
   for(const [name,code] of Object.entries(sources)){
    const m=dev.createShaderModule({code});const info=await m.getCompilationInfo();
    const errors=info.messages.filter(x=>x.type==='error');if(errors.length)throw Error(name+': '+errors.map(x=>x.message).join('\n'));
    modules[name]=m;
   }
   window.empty=dev.createBindGroupLayout({entries:[]});
   window.vlayout=dev.createBindGroupLayout({entries:[{binding:0,visibility:GPUShaderStage.VERTEX,buffer:{type:'uniform'}}]});
   window.flayout=dev.createBindGroupLayout({entries:[{binding:0,visibility:GPUShaderStage.FRAGMENT,buffer:{type:'uniform'}}]});
   window.tlayout=dev.createBindGroupLayout({entries:[...Array.from({length:8},(_,i)=>({binding:i,visibility:GPUShaderStage.FRAGMENT,texture:{sampleType:'float',viewDimension:i<4?'2d':'cube'}})),...Array.from({length:8},(_,i)=>({binding:i+8,visibility:GPUShaderStage.FRAGMENT,sampler:{type:'filtering'}}))]});
   window.layout=dev.createPipelineLayout({bindGroupLayouts:[empty,vlayout,tlayout,flayout]});
   const sampler=dev.createSampler({minFilter:'nearest',magFilter:'nearest'});
   const tex=dev.createTexture({size:[2,2,1],format:'rgba8unorm',usage:GPUTextureUsage.TEXTURE_BINDING|GPUTextureUsage.COPY_DST});
   dev.queue.writeTexture({texture:tex},new Uint8Array([255,255,255,0,255,255,255,255,255,255,255,0,255,255,255,255]),{bytesPerRow:8},[2,2,1]);
   const white=dev.createTexture({size:[2,2,6],format:'rgba8unorm',usage:GPUTextureUsage.TEXTURE_BINDING|GPUTextureUsage.COPY_DST});
   dev.queue.writeTexture({texture:white},new Uint8Array(96).fill(255),{bytesPerRow:8,rowsPerImage:2},[2,2,6]);
   const w2=white.createView({dimension:'2d',baseArrayLayer:0,arrayLayerCount:1}),cube=white.createView({dimension:'cube'});
   window.textures=dev.createBindGroup({layout:tlayout,entries:[...Array.from({length:8},(_,i)=>({binding:i,resource:i===0?tex.createView():i<4?w2:cube})),...Array.from({length:8},(_,i)=>({binding:i+8,resource:sampler}))]});
   window.pipes=new Map();
   window.getPipe=async(newPath,blend,depth,matrix)=>{
    const key=[newPath,blend,depth,!!matrix].join();if(pipes.has(key))return pipes.get(key);
    const targets=[{format:'rgba8unorm',...(blend?{blend:{color:{srcFactor:'src-alpha',dstFactor:'one-minus-src-alpha'},alpha:{srcFactor:'src-alpha',dstFactor:'one-minus-src-alpha'}}}:{})}];
    const buffers=newPath?[{arrayStride:inputLayout.stride,stepMode:'instance',attributes:inputLayout.attributes}]:[{arrayStride:12,stepMode:'vertex',attributes:[{shaderLocation:0,offset:0,format:'float32x2'},{shaderLocation:1,offset:8,format:'float32'}]}];
    const p=await dev.createRenderPipelineAsync({layout,vertex:{module:modules[newPath?(matrix?'matrix-line.wgsl':'line.wgsl'):'baseline.vert.wgsl'],entryPoint:'main',buffers},fragment:{module:modules[newPath?'line.frag.wgsl':'baseline.frag.wgsl'],entryPoint:'main',targets},primitive:{topology:'triangle-list',cullMode:'none'},depthStencil:{format:'depth24plus-stencil8',depthWriteEnabled:!!depth,depthCompare:depth?'less':'always'}});
    pipes.set(key,p);return p;
   };
  },{...sources,__layout:JSON.parse(fs.readFileSync(path.join(dir,'layout.json'),'utf8'))});
  let count=0,goldenCount=0;
  for(const row of JSON.parse(fs.readFileSync(path.join(dir,'cases.json'),'utf8'))){
   const base=path.join(dir,`case-${String(row.id).padStart(3,'0')}`);
   const payload={row,inputs:[...fs.readFileSync(base+'.inputs.bin')],uniforms:[...fs.readFileSync(base+'.uniforms.bin')],shade:[...fs.readFileSync(base+'.shade.bin')],baseline:JSON.parse(fs.readFileSync(base+'.baseline.json','utf8'))};
   if(row.golden){payload.golden=JSON.parse(fs.readFileSync(base+'.golden.json','utf8'));payload.mask=[...fs.readFileSync(base+'.golden.mask.bin')];payload.rgb=[...fs.readFileSync(path.join(dir,'golden.rgb.bin'))];}
   const result=await page.evaluate(async ({row,inputs,uniforms,shade,baseline,golden,mask,rgb})=>{
    dev.pushErrorScope('validation');
    const owned=[];const buffer=(bytes,usage)=>{const b=dev.createBuffer({size:Math.max(16,bytes.byteLength),usage:usage|GPUBufferUsage.COPY_DST});dev.queue.writeBuffer(b,0,bytes);owned.push(b);return b;};
    const ub=(data,l)=>dev.createBindGroup({layout:l,entries:[{binding:0,resource:{buffer:buffer(data,GPUBufferUsage.UNIFORM)}}]});
    const floats=v=>new Float32Array(v);
    const endpoints=buffer(Uint8Array.from(inputs),GPUBufferUsage.VERTEX);
    const vertex=ub(Uint8Array.from(uniforms),vlayout);
    const view=ub(floats([640,480,0,0]),vlayout);
    const fsbytes=new Uint8Array(shade.length+16);fsbytes.set(shade);new Float32Array(fsbytes.buffer,shade.length,4).set([1,row.width,0,0]);
    const fragment=ub(fsbytes,flayout);
    const baselineBindings=baseline.map(line=>{
     const bytes=new Uint8Array(shade.length+272);bytes.set(shade);
     new Float32Array(bytes.buffer,shade.length,64).set(line.endpoints);
     new Float32Array(bytes.buffer,shade.length+256,4).set([1,row.width,0,0]);
     return {vb:buffer(floats(line.quad),GPUBufferUsage.VERTEX),uniform:ub(bytes,flayout)};
    });
    const images=[0,1].map(()=>dev.createTexture({size:[640,480],format:'rgba8unorm',usage:GPUTextureUsage.RENDER_ATTACHMENT|GPUTextureUsage.COPY_SRC}));
    const depth=dev.createTexture({size:[640,480],format:'depth24plus-stencil8',usage:GPUTextureUsage.RENDER_ATTACHMENT});
    const reads=[0,1].map(()=>dev.createBuffer({size:640*480*4,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ}));
    const pipelines=await Promise.all([getPipe(true,row.blend,row.depth,row.matrix),getPipe(false,row.blend,row.depth,false)]);
    const encoder=dev.createCommandEncoder();
    for(let which=0;which<2;which++){
     const pass=encoder.beginRenderPass({colorAttachments:[{view:images[which].createView(),loadOp:'clear',storeOp:'store',clearValue:[32/255,34/255,36/255,1]}],depthStencilAttachment:{view:depth.createView(),depthLoadOp:'clear',depthStoreOp:'store',depthClearValue:1,stencilLoadOp:'clear',stencilStoreOp:'store',stencilClearValue:0}});
     pass.setPipeline(pipelines[which]);pass.setBindGroup(2,textures);
     if(which===0){pass.setBindGroup(1,vertex);pass.setBindGroup(3,fragment);pass.setVertexBuffer(0,endpoints);pass.draw(6,row.instances);}
     else {pass.setBindGroup(1,view);for(const line of baselineBindings){pass.setBindGroup(3,line.uniform);pass.setVertexBuffer(0,line.vb);pass.draw(6);}}
     pass.end();encoder.copyTextureToBuffer({texture:images[which]},{buffer:reads[which],bytesPerRow:2560},[640,480]);
    }
    dev.queue.submit([encoder.finish()]);await Promise.all(reads.map(r=>r.mapAsync(GPUMapMode.READ)));
    const a=new Uint8Array(reads[0].getMappedRange()),b=new Uint8Array(reads[1].getMappedRange());
    let coverageErrors=0,colorErrors=0,covered=0;
    const isCovered=(data,i)=>data[i]!==32||data[i+1]!==34||data[i+2]!==36;
    for(let i=0;i<a.length;i+=4){const ac=isCovered(a,i),bc=isCovered(b,i);covered+=ac;if(ac!==bc)coverageErrors++;else if(ac&&[0,1,2,3].some(k=>Math.abs(a[i+k]-b[i+k])>2))colorErrors++;}
    if(!baseline.length && covered)throw Error('Rejected CPU line unexpectedly rendered pixels');
    if(coverageErrors||colorErrors)throw Error(`case ${row.id}: ${coverageErrors} coverage and ${colorErrors} color errors against production CPU preparation`);
    if(row.id===54){const i=(20*640+20)*4;if(Math.abs(a[i]-171)>2||Math.abs(a[i+1]-84)>2||a[i+2]!==0)throw Error('65 alternating translucent instances lost draw order or one-hit blending: '+Array.from(a.slice(i,i+4)));}
    if(row.id===55 && !(covered>0&&covered<48))throw Error('Texture alpha-kill case did not exercise both kept and rejected fragments');
    if(row.id===70){const i=(20*640+20)*4;if(a[i]!==0||a[i+1]!==255||a[i+2]!==0)throw Error('Layered line depth did not select the nearest green instance');}
    if(row.id===73 && !(covered>0&&covered<48))throw Error('Alpha test did not exercise kept and rejected fragments');
    if(golden){
     let missing=0,extra=0,rgbErrors=0,at=0;
     for(let y=0;y<golden.h;y++)for(let x=0;x<golden.w;x++){
      const bit=y*golden.w+x,expected=(mask[bit>>3]>>(bit&7))&1,i=((golden.y+y)*640+golden.x+x)*4,actual=isCovered(a,i);
      missing+=expected&&!actual;extra+=!expected&&actual;
      if(expected&&golden.width===8){rgbErrors+=[0,1,2].some(k=>Math.abs(a[i+k]-rgb[at+k])>2);at+=3;}
     }
     for(const [x,y,r,g,bl]of golden.probes){const i=(y*640+x)*4;rgbErrors+=[r,g,bl].some((v,k)=>Math.abs(a[i+k]-v)>2);}
     if(missing||extra||rgbErrors)throw Error(`case ${row.id}: Xbox capture missing ${missing}, extra ${extra}, RGB errors ${rgbErrors}`);
    }
    for(const r of reads){r.unmap();r.destroy();}images.forEach(t=>t.destroy());depth.destroy();owned.forEach(b=>b.destroy());
    const validation=await dev.popErrorScope();if(validation)throw Error(validation.message);
    if(gpuErrors.length)throw Error(gpuErrors.join('\n'));
    return {covered,baseline:baseline.length};
   },payload);
   count++;goldenCount+=row.golden?1:0;console.log('PASS GPU line case',row.id,result);
  }
  console.log(`PASS ${count} GPU line cases, ${goldenCount} pinned Xbox widths, CPU VP/clipping differential and ordered instanced blending`);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>server.close());
