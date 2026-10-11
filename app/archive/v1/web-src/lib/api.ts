// The analysis API client: position analyses (cached and de-duplicated, so prefetching each new position costs one
// request) and game reviews.
import { type Board, type Dir, DIR_CHARS, boardCode, toValues } from '@shared/rules.ts';
import type { Analysis, ReviewResult } from './types.ts';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    });
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e;
    throw new ApiError(0, 'The analysis server cannot be reached.');
  }
  const text = await res.text();
  let data: unknown = null;
  try {
    data = JSON.parse(text);
  } catch {
    /* not JSON */
  }
  if (!res.ok) {
    const msg = (data as { error?: string } | null)?.error ?? `The server answered ${res.status}.`;
    throw new ApiError(res.status, msg);
  }
  return data as T;
}

export interface AnalyzeOptions {
  skill?: number;
  /** the player's recent moves, oldest first (the human move model looks at the last 20) */
  hist?: string;
  depth?: number;
  played?: Dir;
}

export function analyzeKey(board: Board, o: AnalyzeOptions = {}): string {
  return [boardCode(board), o.skill?.toFixed(3) ?? '', o.hist ?? '', o.depth ?? 0, o.played ?? ''].join('|');
}

export function requestAnalysis(board: Board, o: AnalyzeOptions = {}, signal?: AbortSignal): Promise<Analysis> {
  const body: Record<string, unknown> = { board: toValues(board) };
  if (o.skill !== undefined) body.skill = Math.round(o.skill * 1000) / 1000;
  if (o.hist) body.hist = o.hist.slice(-20);
  if (o.depth) body.depth = o.depth;
  if (o.played !== undefined) body.played = DIR_CHARS[o.played];
  return post<Analysis>('/api/analyze', body, signal);
}

/** Analyses by request key: finished ones are kept (least recently used dropped), running ones are shared. */
class AnalysisCache {
  private done = new Map<string, Analysis>();
  private running = new Map<string, Promise<Analysis>>();
  private max = 400;

  peek(key: string): Analysis | undefined {
    return this.done.get(key);
  }

  get(board: Board, o: AnalyzeOptions = {}): Promise<Analysis> {
    const key = analyzeKey(board, o);
    const hit = this.done.get(key);
    if (hit) return Promise.resolve(hit);
    const run = this.running.get(key);
    if (run) return run;
    const p = requestAnalysis(board, o)
      .then((a) => {
        this.done.set(key, a);
        if (this.done.size > this.max) this.done.delete(this.done.keys().next().value as string);
        return a;
      })
      .finally(() => this.running.delete(key));
    this.running.set(key, p);
    return p;
  }
}

export const analyses = new AnalysisCache();

export function requestReview(boards: Board[], moves: string, signal?: AbortSignal): Promise<ReviewResult> {
  return post<ReviewResult>('/api/review', { boards: boards.map(boardCode), moves }, signal);
}

export async function serverHealth(): Promise<boolean> {
  try {
    const r = await fetch('/api/health');
    return r.ok;
  } catch {
    return false;
  }
}
