// Server configuration: every value can be set by an environment variable (see app/README.md).
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const APP_DIR = fileURLToPath(new URL('../..', import.meta.url));
const env = process.env;

function int(name: string, def: number, min: number, max: number): number {
  const v = env[name];
  if (v === undefined || v === '') return def;
  const n = Number(v);
  if (!Number.isInteger(n) || n < min || n > max) throw new Error(`${name} must be an integer in [${min}, ${max}]`);
  return n;
}

export interface Config {
  host: string;
  port: number;
  /** the engine's project directory (build/analyze, weights/) */
  engineRoot: string;
  engineBin: string;
  enginePreset: string;
  /** packed networks for the resident workers ('' = the preset's own networks) */
  enginePacked: string;
  /** the light stage-0 networks, used for reviews of games that stay in their range ('' = never) */
  enginePackedLight: string;
  workers: number;
  maxQueue: number;
  queueWaitMs: number;
  analyzeTimeoutMs: number;
  startupTimeoutMs: number;
  maxDepth: number;
  cacheSize: number;
  reviewConcurrency: number;
  reviewMaxWaiting: number;
  reviewMaxMoves: number;
  reviewTimeoutBaseMs: number;
  reviewTimeoutPerMoveMs: number;
  rateAnalyzePerSec: number;
  rateAnalyzeBurst: number;
  rateReviewPerMin: number;
  rateAutoplayPerSec: number;
  rateAutoplayBurst: number;
  autoplayMaxMoves: number;
  rateReviewBurst: number;
  trustProxy: boolean;
  corsOrigins: string[];
  staticDir: string;
  logRequests: boolean;
}

export function loadConfig(): Config {
  return {
    host: env.HOST || '127.0.0.1',
    port: int('PORT', 8048, 1, 65535),
    engineRoot: path.resolve(env.ENGINE_ROOT || path.join(APP_DIR, '..')),
    engineBin: env.ENGINE_BIN || 'build/analyze',
    enginePreset: env.ENGINE_PRESET || 'best-notables',
    enginePacked: env.ENGINE_PACKED ?? 'weights/serve/v6c_i16.wp',
    enginePackedLight: env.ENGINE_PACKED_LIGHT ?? 'weights/serve/v6c_s0only_i16.wp',
    workers: int('ENGINE_WORKERS', 1, 1, 64),
    maxQueue: int('ENGINE_MAX_QUEUE', 64, 1, 10000),
    queueWaitMs: int('ENGINE_QUEUE_WAIT_MS', 15000, 100, 600000),
    analyzeTimeoutMs: int('ANALYZE_TIMEOUT_MS', 10000, 100, 600000),
    startupTimeoutMs: int('ENGINE_STARTUP_TIMEOUT_MS', 120000, 1000, 600000),
    maxDepth: int('MAX_DEPTH', 5, 0, 6),
    cacheSize: int('ANALYZE_CACHE_SIZE', 5000, 0, 1000000),
    reviewConcurrency: int('REVIEW_CONCURRENCY', 1, 1, 64),
    reviewMaxWaiting: int('REVIEW_MAX_WAITING', 8, 0, 1000),
    reviewMaxMoves: int('REVIEW_MAX_MOVES', 20000, 1, 200000),
    reviewTimeoutBaseMs: int('REVIEW_TIMEOUT_BASE_MS', 30000, 1000, 600000),
    reviewTimeoutPerMoveMs: int('REVIEW_TIMEOUT_PER_MOVE_MS', 20, 0, 10000),
    rateAnalyzePerSec: int('RATE_ANALYZE_PER_SEC', 200, 1, 100000),
    rateAnalyzeBurst: int('RATE_ANALYZE_BURST', 400, 1, 100000),
    rateReviewPerMin: int('RATE_REVIEW_PER_MIN', 12, 1, 100000),
    rateAutoplayPerSec: int('RATE_AUTOPLAY_PER_SEC', 20, 1, 100000),
    rateAutoplayBurst: int('RATE_AUTOPLAY_BURST', 40, 1, 100000),
    autoplayMaxMoves: int('AUTOPLAY_MAX_MOVES', 64, 1, 1000),
    rateReviewBurst: int('RATE_REVIEW_BURST', 6, 1, 100000),
    trustProxy: env.TRUST_PROXY === '1',
    corsOrigins: (env.CORS_ORIGINS ?? 'http://localhost:5173,http://127.0.0.1:5173')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean),
    staticDir: path.resolve(env.STATIC_DIR || path.join(APP_DIR, 'web', 'dist')),
    logRequests: env.LOG_REQUESTS !== '0',
  };
}
