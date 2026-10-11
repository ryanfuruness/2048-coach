// The app's HTTP server: the analysis API in front of a pool of resident engine processes, game reviews, and the web
// build's static files. Local by default (127.0.0.1:8048).
//
//   POST /api/analyze  {board, skill?, hist?, depth?, risk?, line?, played?}  -> the engine's analysis (docs/api.md)
//   POST /api/review   {boards: [code...], moves: "URDL..."}                  -> {summary, plies[], engine}
//   POST /api/autoplay {board, skill?, hist?, n, seed, stop_rank?}            -> the coach's next n moves (fast autoplay)
//   GET  /api/health                                                         -> engine pool and review status
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { promisify } from 'node:util';
import { gzip } from 'node:zlib';
import { type Config, loadConfig } from './config.ts';
import { EngineBusy, EnginePool, EngineTimeout, EngineUnavailable } from './engine.ts';
import { log } from './log.ts';
import { Lru } from './lru.ts';
import { RateLimiter } from './ratelimit.ts';
import { ReviewRunner } from './review.ts';
import { serveStatic } from './static.ts';
import { BadRequest, engineLine, parseAnalyze, parseAutoplay, parseReview } from './validate.ts';
import { DIR_CHARS, applySpawn, canMove, dirFromName, maxRank, move, pickSpawn, Sfc32 } from '../../shared/rules.ts';

const gzipAsync = promisify(gzip);
const VERSION = '0.1.0';

class HttpError extends Error {
  readonly status: number;
  readonly headers: Record<string, string>;
  constructor(status: number, message: string, headers: Record<string, string> = {}) {
    super(message);
    this.status = status;
    this.headers = headers;
  }
}

const SECURITY_HEADERS: Record<string, string> = {
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
  'X-Frame-Options': 'DENY',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
  'Content-Security-Policy':
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; " +
    "font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
};

export function createApp(cfg: Config) {
  const engineArgs = ['--preset', cfg.enginePreset, ...(cfg.enginePacked ? ['--packed', cfg.enginePacked] : []), '--stdin', '--stdin-player'];
  const pool = new EnginePool(
    cfg.workers,
    { root: cfg.engineRoot, bin: cfg.engineBin, args: engineArgs, startupTimeoutMs: cfg.startupTimeoutMs },
    cfg.maxQueue,
    cfg.queueWaitMs,
  );
  const reviews = new ReviewRunner({
    root: cfg.engineRoot,
    bin: cfg.engineBin,
    preset: cfg.enginePreset,
    packed: cfg.enginePacked,
    packedLight: cfg.enginePackedLight,
    concurrency: cfg.reviewConcurrency,
    maxWaiting: cfg.reviewMaxWaiting,
    timeoutBaseMs: cfg.reviewTimeoutBaseMs,
    timeoutPerMoveMs: cfg.reviewTimeoutPerMoveMs,
  });
  const cache = new Lru<string>(cfg.cacheSize);
  const analyzeLimit = new RateLimiter(cfg.rateAnalyzePerSec, 1000, cfg.rateAnalyzeBurst);
  const reviewLimit = new RateLimiter(cfg.rateReviewPerMin, 60000, cfg.rateReviewBurst);
  const autoplayLimit = new RateLimiter(cfg.rateAutoplayPerSec, 1000, cfg.rateAutoplayBurst);
  const started = Date.now();
  const counters = { analyze: 0, cache_hits: 0, review: 0, autoplay: 0, autoplay_moves: 0, errors: 0 };

  function clientIp(req: IncomingMessage): string {
    if (cfg.trustProxy) {
      const f = String(req.headers['x-forwarded-for'] ?? '').split(',')[0].trim();
      if (f) return f;
    }
    return req.socket.remoteAddress ?? 'unknown';
  }

  function corsHeaders(req: IncomingMessage): Record<string, string> {
    const origin = req.headers.origin;
    if (!origin || !cfg.corsOrigins.includes(origin)) return {};
    return {
      'Access-Control-Allow-Origin': origin,
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Max-Age': '600',
      Vary: 'Origin',
    };
  }

  async function readJson(req: IncomingMessage, limit: number): Promise<unknown> {
    const type = String(req.headers['content-type'] ?? '');
    if (!type.startsWith('application/json')) throw new HttpError(415, 'send JSON (Content-Type: application/json)');
    const declared = Number(req.headers['content-length'] ?? 0);
    if (declared > limit) throw new HttpError(413, `request body larger than ${limit} bytes`);
    const chunks: Buffer[] = [];
    let size = 0;
    for await (const chunk of req) {
      size += (chunk as Buffer).length;
      if (size > limit) throw new HttpError(413, `request body larger than ${limit} bytes`);
      chunks.push(chunk as Buffer);
    }
    try {
      return JSON.parse(Buffer.concat(chunks).toString('utf8') || 'null');
    } catch {
      throw new HttpError(400, 'the body is not valid JSON');
    }
  }

  async function sendJson(req: IncomingMessage, res: ServerResponse, status: number, body: string | object, extra: Record<string, string> = {}) {
    let data: Buffer = Buffer.from(typeof body === 'string' ? body : JSON.stringify(body));
    const headers: Record<string, string> = {
      ...SECURITY_HEADERS,
      ...corsHeaders(req),
      ...extra,
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
    };
    if (data.length > 1024 && String(req.headers['accept-encoding'] ?? '').includes('gzip')) {
      data = await gzipAsync(data, { level: 6 });
      headers['Content-Encoding'] = 'gzip';
      headers.Vary = headers.Vary ? `${headers.Vary}, Accept-Encoding` : 'Accept-Encoding';
    }
    headers['Content-Length'] = String(data.length);
    res.writeHead(status, headers);
    res.end(data);
  }

  function limit(rl: RateLimiter, req: IncomingMessage, what: string) {
    const wait = rl.take(`${what}:${clientIp(req)}`);
    if (wait > 0)
      throw new HttpError(429, 'too many requests; slow down a little', { 'Retry-After': String(Math.ceil(wait / 1000)) });
  }

  function engineError(e: unknown): HttpError {
    if (e instanceof BadRequest) return new HttpError(400, e.message);
    if (e instanceof EngineBusy) return new HttpError(503, e.message, { 'Retry-After': '2' });
    if (e instanceof EngineTimeout) return new HttpError(504, e.message);
    if (e instanceof EngineUnavailable) return new HttpError(503, e.message, { 'Retry-After': '2' });
    if (e instanceof HttpError) return e;
    return new HttpError(500, 'internal error');
  }

  async function handleAnalyze(req: IncomingMessage, res: ServerResponse) {
    limit(analyzeLimit, req, 'analyze');
    const body = await readJson(req, 4096);
    const line = engineLine(parseAnalyze(body, cfg.maxDepth));
    counters.analyze++;
    let out = cache.get(line);
    let cached = true;
    if (out === undefined) {
      cached = false;
      out = await pool.run(line, cfg.analyzeTimeoutMs);
      if (!out.startsWith('{') || out.includes('"error"')) {
        const msg = out.includes('not a board') ? 'the engine could not read this board' : 'the engine could not analyze this board';
        throw new HttpError(400, msg);
      }
      cache.set(line, out);
    } else counters.cache_hits++;
    await sendJson(req, res, 200, out, { 'X-Cache': cached ? 'hit' : 'miss' });
  }

  /** One analysis through the cache (the same lines as /api/analyze, so the client's later requests hit it). */
  async function analyzeLine(line: string): Promise<string> {
    let out = cache.get(line);
    if (out !== undefined) {
      counters.cache_hits++;
      return out;
    }
    out = await pool.run(line, cfg.analyzeTimeoutMs);
    if (!out.startsWith('{') || out.includes('"error"')) throw new HttpError(400, 'the engine could not analyze a position of this line');
    cache.set(line, out);
    return out;
  }

  // Fast autoplay: the coach's next n moves in one request, each the reference move (loss 0) of the position's
  // analysis - the move the analysis panel shows as best - with the new tiles drawn from the request's seed. Every
  // analysis is a separate engine job, so other requests are served in between.
  async function handleAutoplay(req: IncomingMessage, res: ServerResponse) {
    limit(autoplayLimit, req, 'autoplay');
    const r = parseAutoplay(await readJson(req, 4096), cfg.autoplayMaxMoves);
    counters.autoplay++;
    const rng = Sfc32.fromNumber(r.seed);
    let board = r.board;
    let hist = r.hist ?? '';
    let moves = '';
    let spawns = '';
    const facts: { t: number; p: number | null; b: string; y?: 1 }[] = [];
    let over = false;
    for (let i = 0; i < r.n; i++) {
      const a = JSON.parse(await analyzeLine(engineLine({ board, skill: r.skill, hist: hist || undefined }))) as {
        odds?: Record<string, number>;
        chance?: { target: number; now: number };
        moves: { move: string; loss: number | null }[];
        engine_move: string | null;
        coach_move?: string;
        game_over?: boolean;
      };
      // the coach's move (the corner strategy's in the opening, else the engine's), as the panel shows it
      const best = a.game_over ? null : (a.coach_move ?? a.moves.find((m) => m.loss === 0)?.move ?? a.engine_move);
      const d = best ? dirFromName(best) : -1;
      if (d === -1) {
        over = true;
        break;
      }
      const m = move(board, d);
      if (!m.moved) break;
      const sp = pickSpawn(m.board, rng)!;
      board = applySpawn(m.board, sp);
      if (a.chance) facts.push({ t: a.chance.target, p: a.chance.now, b: DIR_CHARS[d], y: 1 });
      else {
        let t = 0;
        for (const k of Object.keys(a.odds ?? {})) if (/^\d+$/.test(k) && (t === 0 || Number(k) < t)) t = Number(k);
        facts.push({ t, p: t ? a.odds![String(t)] : null, b: DIR_CHARS[d] });
      }
      moves += DIR_CHARS[d];
      spawns += '0123456789abcdefghijklmnopqrstuv'[sp.cell + (sp.rank === 2 ? 16 : 0)];
      hist = (hist + DIR_CHARS[d]).slice(-20);
      if (!canMove(board)) {
        over = true;
        break;
      }
      if (r.stopRank && maxRank(board) >= r.stopRank) break;
    }
    counters.autoplay_moves += moves.length;
    await sendJson(req, res, 200, { moves, spawns, facts, over });
  }

  async function handleReview(req: IncomingMessage, res: ServerResponse) {
    limit(reviewLimit, req, 'review');
    const body = await readJson(req, 64 + cfg.reviewMaxMoves * 40);
    const { boards, moves, skill } = parseReview(body, cfg.reviewMaxMoves);
    counters.review++;
    const result = await reviews.review(boards, moves, skill);
    await sendJson(req, res, 200, result);
  }

  function health() {
    const engine = pool.status();
    return {
      ok: pool.ready,
      version: VERSION,
      uptime_s: Math.round((Date.now() - started) / 1000),
      engine: { preset: cfg.enginePreset, packed: cfg.enginePacked || null, ...engine },
      reviews: reviews.status(),
      cache: { entries: cache.size },
      counters,
    };
  }

  async function handle(req: IncomingMessage, res: ServerResponse) {
    const t0 = Date.now();
    const url = req.url ?? '/';
    const pathname = url.split('?')[0];
    res.on('finish', () => {
      if (cfg.logRequests && pathname.startsWith('/api/'))
        log('http', { method: req.method, path: pathname, status: res.statusCode, ms: Date.now() - t0 });
    });
    try {
      if (pathname.startsWith('/api/')) {
        if (req.method === 'OPTIONS') {
          res.writeHead(204, { ...corsHeaders(req) });
          return res.end();
        }
        if (pathname === '/api/health' && req.method === 'GET') {
          const h = health();
          return await sendJson(req, res, h.ok ? 200 : 503, h);
        }
        if (pathname === '/api/analyze') {
          if (req.method !== 'POST') throw new HttpError(405, 'use POST', { Allow: 'POST' });
          return await handleAnalyze(req, res);
        }
        if (pathname === '/api/autoplay') {
          if (req.method !== 'POST') throw new HttpError(405, 'use POST', { Allow: 'POST' });
          return await handleAutoplay(req, res);
        }
        if (pathname === '/api/review') {
          if (req.method !== 'POST') throw new HttpError(405, 'use POST', { Allow: 'POST' });
          return await handleReview(req, res);
        }
        throw new HttpError(404, 'no such endpoint');
      }
      if (await serveStatic(cfg.staticDir, req, res, SECURITY_HEADERS)) return;
      throw new HttpError(404, 'not found');
    } catch (e) {
      const err = engineError(e);
      if (err.status >= 500) {
        counters.errors++;
        log('http.error', { path: pathname, status: err.status, error: String(e instanceof Error ? e.message : e) });
      }
      if (res.headersSent) return res.destroy();
      if (!pathname.startsWith('/api/') && err.status === 404) {
        res.writeHead(404, { ...SECURITY_HEADERS, 'Content-Type': 'text/plain; charset=utf-8' });
        return res.end('Not found');
      }
      await sendJson(req, res, err.status, { error: err.message }, err.headers);
    }
  }

  const server = createServer((req, res) => {
    handle(req, res).catch(() => res.destroy());
  });
  server.requestTimeout = 120000;
  server.headersTimeout = 20000;
  server.keepAliveTimeout = 5000;

  return { server, pool, reviews, health };
}

function main() {
  const cfg = loadConfig();
  const bin = path.join(cfg.engineRoot, cfg.engineBin);
  if (!existsSync(bin)) {
    console.error(`engine not found at ${bin}: build it with "make -j8" in ${cfg.engineRoot}`);
    process.exit(1);
  }
  for (const f of [cfg.enginePacked, cfg.enginePackedLight])
    if (f && !existsSync(path.join(cfg.engineRoot, f))) console.error(`warning: ${f} not found in ${cfg.engineRoot}`);
  if (!existsSync(path.join(cfg.staticDir, 'index.html')))
    console.error(`warning: no web build in ${cfg.staticDir} (run "npm run build"); serving the API only`);
  const app = createApp(cfg);
  app.server.on('error', (e: NodeJS.ErrnoException) => {
    console.error(
      e.code === 'EADDRINUSE'
        ? `port ${cfg.port} on ${cfg.host} is in use: is the app already running? (stop it with "npm run stop", or set PORT)`
        : `cannot listen on ${cfg.host}:${cfg.port}: ${e.message}`,
    );
    app.pool.stop();
    process.exit(1);
  });
  // the engines start only once the port is ours (no stray engine process when the port is taken)
  app.server.listen(cfg.port, cfg.host, () => {
    app.pool.start();
    log('server.listening', { url: `http://${cfg.host}:${cfg.port}/`, workers: cfg.workers, preset: cfg.enginePreset, packed: cfg.enginePacked });
  });
  let stopping = false;
  const stop = (sig: string) => {
    if (stopping) return;
    stopping = true;
    log('server.stopping', { signal: sig });
    app.pool.stop();
    app.server.close(() => process.exit(0));
    setTimeout(() => process.exit(0), 3000).unref();
  };
  process.on('SIGINT', () => stop('SIGINT'));
  process.on('SIGTERM', () => stop('SIGTERM'));
  process.on('SIGHUP', () => stop('SIGHUP'));
}

if (import.meta.url === `file://${process.argv[1]}`) main();
