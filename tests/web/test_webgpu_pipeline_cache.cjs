'use strict';

const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { chromium } = require('playwright');

const source = readFileSync(path.resolve(__dirname, '../../src/webgpu_pipeline_cache.js'), 'utf8');
const worker = `
const vertexSource = '@vertex fn main(@location(0) p:vec2<f32>)->@builtin(position) vec4<f32>{return vec4(p,0.0,1.0);}';
const fragmentSource = '@fragment fn main()->@location(0) vec4<f32>{return vec4(0.25,0.5,0.75,1.0);}';
const query = new URLSearchParams(location.search);
const mode = query.get('mode');
const revision = query.get('revision').repeat(64);
const now = performance.now.bind(performance);
let clockOffset = 0;
Object.defineProperty(performance, 'now', {value:() => now() + clockOffset});
if (mode === 'unavailable') Object.defineProperty(self, 'indexedDB', {value:undefined});
const limited = ['budget', 'resume', 'reset'].includes(mode);
if (limited) {
  const prepare = GPUDevice.prototype.createRenderPipelineAsync;
  GPUDevice.prototype.createRenderPipelineAsync = async function(desc) {
    const pipeline = await prepare.call(this, desc);
    if (desc.label !== 'initial') clockOffset += 1300;
    return pipeline;
  };
}
const cache = self.NFL2K5PipelineCache;
const enabled = cache.start(limited || mode === 'unavailable' || mode === 'invalid' ? 'warm' : mode, revision, true);

let device, descriptor;
onmessage = async ({data}) => {
  try {
    if (data === 'initialise') {
      device = await (await navigator.gpu.requestAdapter()).requestDevice();
      device.addEventListener('uncapturederror', event => postMessage({error:event.error.message}));
      const layout = device.createPipelineLayout({bindGroupLayouts:[device.createBindGroupLayout({entries:[]})]});
      descriptor = {
        layout,
        vertex:{module:device.createShaderModule({code:vertexSource}), entryPoint:'main',
          buffers:[{arrayStride:8, stepMode:'vertex', attributes:[{format:'float32x2', offset:0, shaderLocation:0}]}]},
        fragment:{module:device.createShaderModule({code:fragmentSource}), entryPoint:'main',
          targets:[{format:'rgba8unorm'}]},
        primitive:{topology:'triangle-list', cullMode:'none'},
      };
      await device.createRenderPipelineAsync({...descriptor, label:'initial'});
      postMessage({enabled});
      return;
    }

    if (mode === 'learn') clockOffset = 9000;
    const pipeline = device.createRenderPipeline(descriptor);
    const vertices = device.createBuffer({size:24, usage:GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST});
    device.queue.writeBuffer(vertices, 0, new Float32Array([-1,-1,3,-1,-1,3]));
    const target = device.createTexture({size:[1,1], format:'rgba8unorm',
      usage:GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.COPY_SRC});
    const read = device.createBuffer({size:256, usage:GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ});
    const encoder = device.createCommandEncoder();
    const pass = encoder.beginRenderPass({colorAttachments:[{view:target.createView(), loadOp:'clear', storeOp:'store'}]});
    pass.setPipeline(pipeline);
    pass.setVertexBuffer(0, vertices);
    pass.draw(3);
    pass.end();
    if (mode === 'learn') cache.observe(180);
    encoder.copyTextureToBuffer({texture:target}, {buffer:read, bytesPerRow:256}, [1,1]);
    device.queue.submit([encoder.finish()]);
    await read.mapAsync(GPUMapMode.READ);
    const pixel = Array.from(new Uint8Array(read.getMappedRange(), 0, 4));
    read.unmap();

    const exact = device.createRenderPipeline(descriptor) === pipeline;
    const secondLayout = device.createPipelineLayout({bindGroupLayouts:[device.createBindGroupLayout({entries:[]})]});
    const differentLayout = device.createRenderPipeline({...descriptor, layout:secondLayout}) !== pipeline;
    const module = device.createShaderModule({code:fragmentSource.replace('0.25','0.5')});
    const differentShader = device.createRenderPipeline({...descriptor, fragment:{...descriptor.fragment, module}}) !== pipeline;
    const otherState = {
      ...descriptor, primitive:{...descriptor.primitive, cullMode:'front'},
    };
    const other = device.createRenderPipeline(otherState);
    const differentState = other !== pipeline;
    const otherExact = limited && device.createRenderPipeline(otherState) === other;
    postMessage({pixel, exact, differentLayout, differentShader, differentState, otherExact});
  } catch (error) {
    postMessage({error:String(error)});
  }
};
`;

async function run() {
  const server = http.createServer((req, res) => {
    if (req.url.startsWith('/worker.js?')) {
      res.setHeader('Content-Type', 'text/javascript');
      res.end(source + '\n' + worker);
    } else {
      res.setHeader('Content-Type', 'text/html');
      res.end('<!doctype html><title>Pipeline cache test</title>');
    }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch(process.env.CHROME_BIN ? {executablePath:process.env.CHROME_BIN} : {});
    const context = await browser.newContext();
    const root = 'http://127.0.0.1:' + server.address().port;
    for (const [mode, revision, hit] of [
      ['learn','a',false], ['1','a',true], ['warm','b',false], ['unavailable','a',false],
      ['budget','a',true], ['resume','a',false], ['budget','a',true], ['reset','a',true], ['invalid','a',false],
    ]) {
      const page = await context.newPage();
      const events = [];
      page.on('console', message => {
        const text = message.text();
        if (text.startsWith('NFL_WARM ')) events.push(JSON.parse(text.slice(9)));
      });
      try {
        await page.goto(root);
        if (['budget', 'reset', 'invalid'].includes(mode)) {
          await page.evaluate(mode => new Promise((resolve,reject) => {
            const request = indexedDB.open('nfl2k5-webgpu-pipelines', 1);
            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
              const db = request.result;
              const tx = db.transaction('recipes', 'readwrite');
              tx.onabort = () => { db.close(); reject(tx.error); };
              tx.oncomplete = () => { db.close(); resolve(); };
              const store = tx.objectStore('recipes');
              const row = store.get('recent');
              row.onsuccess = () => {
                const value = row.result;
                if (mode === 'budget' && value.items.length === 1) {
                  const first = value.items[0];
                  const state = JSON.parse(first.state);
                  state.primitive.cullMode = 'front';
                  value.items.push({...first, state:JSON.stringify(state)});
                } else if (mode === 'reset') {
                  value.generation = crypto.randomUUID();
                } else if (mode === 'invalid') {
                  value.items.length = 1;
                  value.items[0].vertex = 'invalid WGSL';
                }
                store.put(value, 'recent');
              };
            };
          }), mode);
        }
        await page.evaluate(({mode,revision}) => {
          const worker = new Worker('/worker.js?mode=' + mode + '&revision=' + revision);
          window.responses = [];
          window.pipelineWorker = worker;
          worker.onmessage = event => responses.push(event.data);
          worker.onerror = event => responses.push({error:event.message});
          worker.postMessage('initialise');
        }, {mode,revision});
        const contains = async (event, count) => {
          const deadline = Date.now() + 12000;
          while (!events.some(item => item.event === event && item.count === count)) {
            if (Date.now() > deadline) throw Error('Unexpected events ' + JSON.stringify(events));
            await new Promise(resolve => setTimeout(resolve, 30));
          }
        };
        await page.waitForFunction(() => responses.length !== 0);
        assert.deepEqual(await page.evaluate(() => responses[0]), {enabled:mode !== 'unavailable'});
        if (mode === 'warm' || mode === '1') await contains(hit ? 'ready' : 'loaded', hit ? 1 : 0);
        if (['budget', 'resume', 'reset'].includes(mode)) await contains('deferred', 1);
        if (mode === 'invalid') await contains('prepare-failed', undefined);

        await page.evaluate(() => pipelineWorker.postMessage('draw'));
        await page.waitForFunction(() => responses.length > 1);
        assert.deepEqual(await page.evaluate(() => responses[1]), {
          pixel:[64,128,191,255], exact:hit, differentLayout:true, differentShader:true, differentState:true,
          otherExact:mode === 'resume',
        });
        if (mode === 'learn') await contains('stored', 1);
        assert.equal(events.some(item => item.event === 'hit'), hit || mode === 'resume');
        console.log('PASS pipeline cache', mode, revision, 'reuse', hit);
      } finally { await page.close(); }
    }
  } finally {
    await browser?.close();
    server.close();
  }
}

run().catch(error => { console.error(error); process.exitCode = 1; });
