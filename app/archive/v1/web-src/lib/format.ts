// Turning the engine's numbers into plain words.
import { type Dir, type DirName, DIR_NAMES, dirFromName } from '@shared/rules.ts';
import type { Analysis, Reason } from './types.ts';

export const ARROWS = ['↑', '→', '↓', '←'] as const;

export function arrowOf(d: DirName | Dir | null | undefined): string {
  if (d === null || d === undefined) return '·';
  const k = typeof d === 'number' ? d : dirFromName(d);
  return k === -1 ? '·' : ARROWS[k];
}

export function dirIndex(name: DirName | null | undefined): Dir | -1 {
  return name ? dirFromName(name) : -1;
}

export const cap = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s);

/** A chance as a percentage: one decimal near the ends (99.8%), whole numbers elsewhere. */
export function chance(p: number | null | undefined): string {
  if (p === null || p === undefined || !Number.isFinite(p)) return '–';
  const v = p * 100;
  if (v >= 99.95) return '>99.9%';
  if (v < 0.05) return '<0.1%';
  if (v >= 99 || v < 1) return `${v.toFixed(1)}%`;
  return `${Math.round(v)}%`;
}

/** A cost (share of chances, 0-1) in words: "about 26%", "less than 1%". */
export function cost(p: number | null | undefined): string {
  if (p === null || p === undefined || !Number.isFinite(p)) return 'an unknown share';
  const v = p * 100;
  if (v < 1) return 'less than 1%';
  if (v >= 99.5) return 'all';
  return `about ${v < 10 ? v.toFixed(v < 3 ? 1 : 0) : Math.round(v)}%`;
}

/** A loss as a short percentage for tables: "0.4%", "12%", "–". */
export function pctShort(p: number | null | undefined): string {
  if (p === null || p === undefined || !Number.isFinite(p)) return '–';
  const v = p * 100;
  if (v < 0.05) return '0%';
  if (v < 10) return `${v.toFixed(1)}%`;
  return `${Math.round(v)}%`;
}

export function int(n: number): string {
  return n.toLocaleString('en-US');
}

/** The next milestone tile and its chance: the smallest tile the engine gives odds for (2048, then 4096, ...). */
export function milestone(odds: Record<string, number> | undefined): { tile: number; p: number } | null {
  if (!odds) return null;
  let best: { tile: number; p: number } | null = null;
  for (const [k, v] of Object.entries(odds)) {
    const t = Number(k);
    if (Number.isFinite(t) && (!best || t < best.tile)) best = { tile: t, p: v };
  }
  return best;
}

/** The chance of a given tile from an odds object (null if absent). */
export function oddsOf(odds: Record<string, number> | undefined, tile: number): number | null {
  const v = odds?.[String(tile)];
  return typeof v === 'number' ? v : null;
}

export type Health = 'good' | 'warning' | 'critical' | 'unknown';

/** The position's health against a typical position at its stage, as the engine's verdict says it. */
export function healthOf(a: Pick<Analysis, 'summary'> | null | undefined): Health {
  const s = a?.summary ?? '';
  if (s.includes('about as good as a typical')) return 'good';
  if (s.includes('a bit worse than a typical')) return 'warning';
  if (s.includes('in trouble compared')) return 'critical';
  return 'unknown';
}

export const HEALTH_WORDS: Record<Health, string> = {
  good: 'as good as a typical position',
  warning: 'a bit worse than typical',
  critical: 'in trouble',
  unknown: '',
};

/** "Mainly because it ..." for checked reasons that explain most of the loss, "partly" for smaller shares. */
export function because(r: Reason): string {
  if (r.share === undefined) return `It ${r.text}.`;
  if (r.share >= 0.5) return `Mainly because it ${r.text}.`;
  return `Partly because it ${r.text}.`;
}

/** The best move's main strength as a sentence: "Down keeps your biggest tile in its corner." */
export function strength(d: DirName, r: Reason | undefined): string {
  return r ? `${cap(d)} ${r.text}.` : '';
}

/** The next doubling of the largest tile (what "your chances" in your_cost refer to). */
export function nextTile(maxRankOnBoard: number): number {
  return 2 ** (maxRankOnBoard + 1);
}

export function relTime(t: number): string {
  const s = (Date.now() - t) / 1000;
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  const d = new Date(t);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export function dirName(d: Dir): DirName {
  return DIR_NAMES[d];
}

export function lossClass(rl: number | null | undefined): 'blunder' | 'mistake' | 'inaccuracy' | null {
  if (rl === null || rl === undefined) return null;
  if (rl >= 0.1) return 'blunder';
  if (rl >= 0.03) return 'mistake';
  if (rl >= 0.01) return 'inaccuracy';
  return null;
}

export const CLASS_WORDS = { blunder: 'Blunder', mistake: 'Mistake', inaccuracy: 'Inaccuracy' } as const;

/** A share of moves as a percentage: one decimal from 99.5% (so 99.7% does not read as 100%). */
export function share(x: number): string {
  const v = x * 100;
  return v >= 99.5 && v < 100 ? `${v.toFixed(1)}%` : `${Math.round(v)}%`;
}
