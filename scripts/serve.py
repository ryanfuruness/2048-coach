#!/usr/bin/env python3
"""HTTP API for the analysis engine: one resident build/analyze --stdin process per worker (the engine loads once,
~17 s), requests served in order per worker.

  python3 scripts/serve.py [--port 8048] [--workers 1] [--preset best-notables|best]

  POST /analyze  {"board": [[2,4,0,0],[...],[...],[...]] or "2 4 0 0 ..." or "hex16",
                  "depth": 0-6 (0 = the engine's own; larger values are capped at 6), "risk": 0-3, "line": 0-200, "played": "U|R|D|L"}
  -> the analysis JSON (fields: docs/api.md; e.g. moves[].real_loss, warn, your_cost, formation)
  GET /health -> {"ok": true, "workers": N}
"""
import json, os, queue, subprocess, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Worker:
    def __init__(self, preset):
        env = dict(os.environ, MALLOC_ARENA_MAX='2')
        self.p = subprocess.Popen(['bash', '-c', f'ulimit -s unlimited; exec ./build/analyze --preset {preset} --stdin'],
                                  cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True, bufsize=1, env=env)

    def ask(self, line):
        self.p.stdin.write(line + '\n')
        self.p.stdin.flush()
        return self.p.stdout.readline()


def request_line(req):
    b = req.get('board')
    if isinstance(b, list):
        b = ' '.join(str(v) for row in b for v in (row if isinstance(row, list) else [row]))
    if not isinstance(b, str) or not b.strip():
        raise ValueError('board missing')
    opts = []
    for k in ('depth', 'risk', 'line'):
        if k in req:
            opts.append(f"{k}={int(req[k])}")
    if req.get('played') in ('U', 'R', 'D', 'L', 'up', 'right', 'down', 'left'):
        opts.append(f"played={req['played'][0].upper()}")
    if any(c in b for c in '|\n'):
        raise ValueError('bad board')
    return (' '.join(opts) + ' | ' if opts else '') + b


def main():
    args = sys.argv[1:]
    port = int(args[args.index('--port') + 1]) if '--port' in args else 8048
    n = int(args[args.index('--workers') + 1]) if '--workers' in args else 1
    preset = args[args.index('--preset') + 1] if '--preset' in args else 'best-notables'
    pool = queue.Queue()
    for _ in range(n):
        pool.put(Worker(preset))

    class Handler(BaseHTTPRequestHandler):
        def reply(self, code, obj):
            body = (obj if isinstance(obj, str) else json.dumps(obj)).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == '/health':
                self.reply(200, {'ok': True, 'workers': n})
            else:
                self.reply(404, {'error': 'not found'})

        def do_POST(self):
            if self.path != '/analyze':
                return self.reply(404, {'error': 'not found'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if size > 10000:
                    raise ValueError('request too large')
                line = request_line(json.loads(self.rfile.read(size) or b'{}'))
            except Exception as e:  # noqa: BLE001 - any bad input is a 400
                return self.reply(400, {'error': str(e)})
            w = pool.get()
            try:
                out = w.ask(line)
            finally:
                pool.put(w)
            self.reply(200 if '"error"' not in out else 400, out.strip())

        def log_message(self, *a):
            pass

    print(f"serving on :{port} with {n} engine worker(s), preset {preset}", flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()


if __name__ == '__main__':
    main()
