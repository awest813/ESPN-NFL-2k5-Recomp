#!/usr/bin/env python3
"""Serve the web build locally, cross-origin isolated.

    python3 tools/serve-web.py [directory] [--port 8080] [--host 127.0.0.1]
                               [--no-isolation]

Serves `directory` (default build-web/, which tools/build-web.sh fills) with
the headers the game needs for SharedArrayBuffer:

    Cross-Origin-Opener-Policy: same-origin
    Cross-Origin-Embedder-Policy: require-corp

and no caching, so a rebuild is picked up on reload. --no-isolation leaves
those headers out, which is what a static host does; the page then falls back
to its service worker (web/coi-sw.js). localhost is a secure context, so OPFS
and service workers work without HTTPS.
"""
import argparse
import functools
import http.server
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Handler(http.server.SimpleHTTPRequestHandler):
    isolation = True
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        '.wasm': 'application/wasm',
        '.js': 'text/javascript',
        '.json': 'application/json',
    }

    def end_headers(self):
        if self.isolation:
            self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
            self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
            self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def log_message(self, fmt, *args):
        if os.environ.get('NFL2K5_SERVE_QUIET') != '1':
            super().log_message(fmt, *args)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('directory', nargs='?', default=os.path.join(ROOT, 'build-web'))
    ap.add_argument('--port', type=int, default=8080)
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--no-isolation', action='store_true')
    a = ap.parse_args()
    if not os.path.isdir(a.directory):
        sys.exit(f'{a.directory} does not exist: run tools/build-web.sh first')
    if not os.path.exists(os.path.join(a.directory, 'index.html')):
        print(f'note: {a.directory} has no index.html', file=sys.stderr)
    Handler.isolation = not a.no_isolation
    handler = functools.partial(Handler, directory=a.directory)
    with http.server.ThreadingHTTPServer((a.host, a.port), handler) as httpd:
        print(f'Serving {a.directory} at http://{a.host}:{httpd.server_address[1]}/'
              f'{"" if Handler.isolation else " (no COOP/COEP headers)"}', flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
