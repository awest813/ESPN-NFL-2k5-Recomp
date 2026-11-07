// Cross-origin isolation for hosts that cannot set response headers (GitHub
// Pages and similar static hosting).
//
// The game needs SharedArrayBuffer (its threads share one wasm memory), which
// browsers only expose to a cross-origin isolated page: served with
//   Cross-Origin-Opener-Policy: same-origin
//   Cross-Origin-Embedder-Policy: require-corp
// tools/serve-web.py sends those itself. Where the server cannot, the page
// registers this service worker, which adds them to every same-origin
// response, and reloads once (web/app.js). Cross-origin requests are passed
// through untouched; the page makes none.
'use strict';

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (new URL(req.url).origin !== self.location.origin) return;
  if (req.cache === 'only-if-cached' && req.mode !== 'same-origin') return;
  e.respondWith((async () => {
    const res = await fetch(req);
    if (res.status === 0) return res;   // opaque: nothing to annotate
    const headers = new Headers(res.headers);
    headers.set('Cross-Origin-Opener-Policy', 'same-origin');
    headers.set('Cross-Origin-Embedder-Policy', 'require-corp');
    headers.set('Cross-Origin-Resource-Policy', 'same-origin');
    return new Response(res.body, { status: res.status, statusText: res.statusText, headers });
  })());
});
