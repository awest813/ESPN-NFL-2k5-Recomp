// Explicit public-file allowlist: disc images, saves, profiles and build logs
// must never enter a deployment artifact.
import {readFile,writeFile,mkdir,copyFile,readdir,stat} from 'node:fs/promises';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const build=resolve(process.argv[2]||resolve(root,'build-web'));
const output=resolve(root,'dist-pages');
const launcher=['index.html','style.css','app.js','launch.js','storage.js','save-worker.js',
  'save-format.js','import-worker.js','audio-worklet.js','coi-sw.js'];
const runtime=['NFL2K5.js','NFL2K5.wasm'];
const allowed=new Set([...launcher,...runtime,'.nojekyll','runtime.json']);
await mkdir(output,{recursive:true});
for(const name of await readdir(output)) if(!allowed.has(name)) throw Error('Unexpected deployment file: '+name);
const wasm=await readFile(resolve(build,'NFL2K5.wasm'));
if(wasm.length<8||wasm.subarray(0,4).toString('hex')!=='0061736d') throw Error('Invalid WebAssembly runtime.');
for(const name of launcher) await copyFile(resolve(root,'web',name),resolve(output,name));
for(const name of runtime) await copyFile(resolve(build,name),resolve(output,name));
await writeFile(resolve(output,'.nojekyll'),'');
await writeFile(resolve(output,'runtime.json'),JSON.stringify({version:1,wasmBytes:wasm.length,
  sha256:createHash('sha256').update(wasm).digest('hex')},null,2)+'\n');
let total=0;
for(const name of allowed) total+=(await stat(resolve(output,name))).size;
if(total>1024**3) throw Error('Pages artifact exceeds 1 GiB.');
console.log(`Pages package: ${allowed.size} allowlisted files, ${total} bytes. No disc or save data included.`);
