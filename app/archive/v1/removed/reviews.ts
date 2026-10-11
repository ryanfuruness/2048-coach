// Reviews in memory for this visit (the server recomputes them quickly; only the summary is kept in localStorage).
import { DIR_CHARS, type Dir } from '@shared/rules.ts';
import { requestReview } from './api.ts';
import { attachReview, loadGame, replay } from './games.ts';
import { addSkillSample } from './skill.ts';
import type { ReviewResult } from './types.ts';

const cache = new Map<string, { moves: number; p: Promise<ReviewResult> }>();

/** The review of a stored game (cached per game and length), recording its summary and the player's skill. */
export function reviewGame(id: string, opts: { partial?: boolean } = {}): Promise<ReviewResult> {
  const g = loadGame(id);
  if (!g) return Promise.reject(new Error('This game is not in your history any more.'));
  if (!g.moves.length) return Promise.reject(new Error('This game has no moves to review yet.'));
  const hit = cache.get(id);
  if (hit && hit.moves === g.moves.length) return hit.p;
  const boards = replay(g);
  const p = requestReview(boards, g.moves).then((r) => {
    if (!opts.partial || g.over) attachReview(id, r.summary);
    addSkillSample(id, r.summary.skill, r.summary.moves);
    return r;
  });
  cache.set(id, { moves: g.moves.length, p });
  p.catch(() => {
    if (cache.get(id)?.p === p) cache.delete(id);
  });
  return p;
}

export function cachedReview(id: string, moves: number): Promise<ReviewResult> | null {
  const hit = cache.get(id);
  return hit && hit.moves === moves ? hit.p : null;
}

export const dirChar = (d: Dir) => DIR_CHARS[d];
