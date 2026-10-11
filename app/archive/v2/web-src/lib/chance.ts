// Your chance: how a position and a move look for a player of your level who plays on themselves, rather than for
// the engine (which repairs almost anything early on). The analysis gives, up to a largest tile of 8192, the chance of
// the next milestone (2048, then each doubling) from here and after every move; the coach's move and the cost of each
// move are read from it. Beyond 8192 (no simulated players get there) the engine's numbers stand in.
import { type Board, type Dir, type DirName, maxRank, move } from '@shared/rules.ts';
import type { Analysis, ChanceInfo, MoveInfo, ReviewMove, ReviewPly } from './types.ts';

export type CostClass = 'blunder' | 'mistake' | 'inaccuracy';

/**
 * Classes by the share of your chance a move gives away (with a minimum in points, so that tiny chances do not turn
 * noise into blunders); the engine's real loss keeps its own thresholds where there is no chance.
 */
export const CHANCE_CLASSES: { cls: CostClass; rel: number; abs: number }[] = [
  { cls: 'blunder', rel: 0.25, abs: 0.04 },
  { cls: 'mistake', rel: 0.1, abs: 0.02 },
  { cls: 'inaccuracy', rel: 0.05, abs: 0.02 },
];

export interface HumanCost {
  /** the share of your chance the move gives away (chance), or the engine's real loss (engine) */
  rel: number;
  /** points of chance lost (chance only) */
  abs: number | null;
  /** your chance with the best move for you, and after this move (chance only) */
  best: number | null;
  after: number | null;
  /** the milestone tile the chance is for (chance only) */
  target: number | null;
  kind: 'chance' | 'engine';
}

type WithMoves = { chance?: ChanceInfo; moves: (MoveInfo | ReviewMove)[]; judged?: false };

/** The reference move of an analysis: the one the engine's losses are measured against (loss 0), else its move. */
export function engineBest(a: Pick<Analysis, 'moves' | 'engine_move' | 'game_over'>): DirName | null {
  if (a.game_over) return null;
  return a.moves.find((m) => m.loss === 0)?.move ?? a.engine_move;
}

/** The coach's move: what Space plays, the arrow on the board and autoplay (the engine's move on older servers). */
export function coachOf(a: Pick<Analysis, 'moves' | 'engine_move' | 'game_over' | 'coach_move'>): DirName | null {
  if (a.game_over) return null;
  return a.coach_move ?? engineBest(a);
}

/** What move `name` costs the player: by their chance where the analysis has it, else the engine's real loss. */
export function costOf(a: WithMoves, name: DirName): HumanCost | null {
  if (a.judged === false) return null;
  const m = a.moves.find((x) => x.move === name);
  if (!m) return null;
  if (a.chance && typeof m.chance === 'number' && typeof m.chance_loss === 'number') {
    const best = a.chance.best;
    return {
      rel: best > 1e-9 ? Math.min(1, m.chance_loss / best) : 0,
      abs: m.chance_loss,
      best,
      after: m.chance,
      target: a.chance.target,
      kind: 'chance',
    };
  }
  if (m.real_loss === null || m.real_loss === undefined) return null;
  return { rel: m.real_loss, abs: null, best: null, after: null, target: null, kind: 'engine' };
}

/** The class of a cost (null: as good, or within the noise). */
export function costClass(c: Pick<HumanCost, 'rel' | 'abs' | 'kind'> | null | undefined): CostClass | null {
  if (!c) return null;
  if (c.kind === 'engine') return c.rel >= 0.1 ? 'blunder' : c.rel >= 0.03 ? 'mistake' : c.rel >= 0.01 ? 'inaccuracy' : null;
  for (const t of CHANCE_CLASSES) if (c.rel >= t.rel && (c.abs ?? 0) >= t.abs) return t.cls;
  return null;
}

/**
 * The class of a stored cost (a timeline fact keeps only the share and the chance from the position): the points are
 * estimated as the share of that chance (the chance with the best move is a little higher, so the estimate errs mild).
 */
export function shareClass(rel: number | null | undefined, kind: 'chance' | 'engine' = 'chance', p?: number | null): CostClass | null {
  if (rel === null || rel === undefined) return null;
  if (kind === 'engine') return costClass({ rel, abs: null, kind });
  const abs = typeof p === 'number' ? rel * p : 1;
  for (const t of CHANCE_CLASSES) if (rel >= t.rel && abs >= t.abs) return t.cls;
  return null;
}

/** The played move's cost in a reviewed ply (0 for the coach's or the engine's own move). */
export function plyCost(p: ReviewPly): HumanCost | null {
  if (p.judged === false) return null;
  const c = costOf(p, p.played);
  if (c) return c;
  if (p.played === p.best) return { rel: 0, abs: p.chance ? 0 : null, best: null, after: null, target: null, kind: p.chance ? 'chance' : 'engine' };
  return null;
}

/** Points of chance as a short signed number: "−6 pts", "−0.5 pt". */
export function points(x: number): string {
  const v = Math.abs(x) * 100;
  const s = v >= 10 ? `${Math.round(v)}` : v >= 1 ? v.toFixed(0) : v.toFixed(1);
  return `${x < 0 ? '−' : x > 0 ? '+' : ''}${s} ${v >= 1.5 || v === 0 ? 'pts' : 'pt'}`;
}

/** The biggest tile (any copy) sits in a corner. */
export function biggestInCorner(b: Board): boolean {
  const m = maxRank(b);
  return m > 0 && (b[0] === m || b[3] === m || b[12] === m || b[15] === m);
}

/**
 * A habit worth a word in the opening: move d took the biggest tile out of its corner although `better` kept it there,
 * and it cost nothing measurable yet. Early on a player at any level repairs that (the chance of 2048 barely moves), but
 * from about 256 on it starts to cost, so the coach names the habit instead of grading it.
 */
export function cornerHabit(before: Board, d: Dir, better: Dir | -1): boolean {
  const top = maxRank(before);
  if (top < 5 || top > 9 || better === -1 || better === d || !biggestInCorner(before)) return false;
  const mine = move(before, d);
  const theirs = move(before, better);
  return mine.moved && theirs.moved && !biggestInCorner(mine.board) && biggestInCorner(theirs.board);
}
