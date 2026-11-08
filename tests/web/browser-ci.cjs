// GPU-less Linux runners need an explicit SwiftShader WebGPU adapter. Keep
// these test-only flags away from normal launches and hardware benchmarks.
if (process.platform === 'linux') {
  const {chromium}=require('playwright');
  const launch=chromium.launch.bind(chromium);
  chromium.launch=(options={})=>{
    const args=(options.args||[]).filter(a=>!/^--(?:use-gl|use-angle|use-vulkan|use-webgpu-adapter|enable-features)=/.test(a));
    return launch({...options,channel:'chromium',headless:!process.env.DISPLAY,args:[...args,
      '--enable-unsafe-webgpu','--enable-unsafe-swiftshader','--use-gl=angle',
      '--use-angle=vulkan','--enable-features=Vulkan','--use-vulkan=swiftshader',
      '--use-webgpu-adapter=swiftshader','--disable-vulkan-surface']});
  };
}
