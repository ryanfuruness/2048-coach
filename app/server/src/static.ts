// Static files of the web build (app/web/dist): hashed assets are cached for a year, the HTML is revalidated, and the
// .br / .gz copies made at build time (scripts/compress.mjs) are served to clients that accept them. Paths without a
// file extension fall back to index.html (client-side routes such as /review/abc).
import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import type { IncomingMessage, ServerResponse } from 'node:http';
import path from 'node:path';

const TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.webmanifest': 'application/manifest+json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
  '.txt': 'text/plain; charset=utf-8',
};

async function fileInfo(p: string) {
  try {
    const s = await stat(p);
    return s.isFile() ? s : null;
  } catch {
    return null;
  }
}

export async function serveStatic(root: string, req: IncomingMessage, res: ServerResponse, headers: Record<string, string>): Promise<boolean> {
  if (req.method !== 'GET' && req.method !== 'HEAD') return false;
  let pathname: string;
  try {
    pathname = decodeURIComponent(new URL(req.url ?? '/', 'http://x').pathname);
  } catch {
    return false;
  }
  if (pathname.includes('\0')) return false;
  let file = path.join(root, path.normalize(pathname));
  if (!file.startsWith(root)) return false;
  let info = pathname.endsWith('/') ? null : await fileInfo(file);
  if (!info) {
    if (path.extname(pathname)) return false; // a missing asset: 404, not the app
    file = path.join(root, 'index.html');
    info = await fileInfo(file);
    if (!info) return false;
  }
  const ext = path.extname(file);
  const type = TYPES[ext] ?? 'application/octet-stream';
  // hashed build assets and the versioned font never change under the same name
  const immutable = file.includes(`${path.sep}assets${path.sep}`) || file.includes(`${path.sep}fonts${path.sep}`);
  const accept = String(req.headers['accept-encoding'] ?? '');
  let body = file;
  let encoding: string | undefined;
  for (const [enc, suffix] of [['br', '.br'], ['gzip', '.gz']] as const) {
    if (!accept.includes(enc)) continue;
    const alt = await fileInfo(file + suffix);
    if (alt) {
      body = file + suffix;
      encoding = enc;
      info = alt;
      break;
    }
  }
  res.writeHead(200, {
    ...headers,
    'Content-Type': type,
    'Content-Length': String(info.size),
    'Cache-Control': immutable ? 'public, max-age=31536000, immutable' : 'no-cache',
    Vary: 'Accept-Encoding',
    ...(encoding ? { 'Content-Encoding': encoding } : {}),
  });
  if (req.method === 'HEAD') {
    res.end();
    return true;
  }
  createReadStream(body).pipe(res);
  return true;
}
