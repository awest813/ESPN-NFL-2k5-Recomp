// Owned headless browser runner for benchmark-web-waits.py; no game assets needed.
const fs = require('fs');
const http = require('http');
const path = require('path');
const { chromium } = require('playwright');

async function main() {
  const dir = path.resolve(process.argv[2]);
  const report = { platform: process.platform, node: process.version, completed: false, lines: [], errors: [] };
  const server = http.createServer((req, res) => {
    res.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
    res.setHeader('Cross-Origin-Embedder-Policy', 'require-corp');
    const name = new URL(req.url, 'http://localhost').pathname;
    if (name === '/') {
      res.setHeader('Content-Type', 'text/html');
      res.end('<!doctype html><meta charset="utf-8"><title>Condition wait benchmark</title><script src="benchmark.js"></script>');
    } else if (/^\/benchmark(?:\.worker)?\.(js|wasm)$/.test(name)) {
      const file = path.join(dir, name.slice(1));
      res.setHeader('Content-Type', name.endsWith('.wasm') ? 'application/wasm' : 'text/javascript');
      if (fs.existsSync(file)) res.end(fs.readFileSync(file));
      else { res.statusCode = 404; res.end(); }
    } else { res.statusCode = 404; res.end(); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser, timer;
  try {
    browser = await chromium.launch({ headless: true,
      ...(process.argv[3] ? { executablePath: process.argv[3] } : {}) });
    const page = await browser.newPage();
    const done = new Promise((resolve, reject) => {
      timer = setTimeout(() => reject(Error('Wait benchmark exceeded 120 seconds')), 120000);
      page.on('console', message => {
        const line = message.text();
        if (line.startsWith('WAITBENCH')) { report.lines.push(line); console.log(line); }
        if (line === 'WAITBENCH DONE') { report.completed = true; resolve(); }
      });
      page.on('pageerror', error => { report.errors.push(String(error)); reject(error); });
    });
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    report.browser = await page.evaluate(() => ({ userAgent: navigator.userAgent, isolated: crossOriginIsolated }));
    if (!report.browser.isolated) throw Error('Benchmark requires cross-origin isolation');
    await done;
  } finally {
    clearTimeout(timer);
    fs.writeFileSync(path.join(dir, 'browser-report.json'), JSON.stringify(report, null, 2) + '\n');
    try { if (browser) await browser.close(); }
    finally { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
