// The player's skill on the human move model's scale (docs/guide.md, "At your level"): estimated by game reviews
// (the review's `skill`, which needs 50+ judged moves below 16384), combined over the last few reviewed games. Until
// then a default stands in. Hints and "your chances" depend on it.
import { createStore, readJson, writeJson } from './storage.ts';

/**
 * Default skill until the player's own is known: halfway between the novice median (-0.8) and intermediate players
 * (-0.2 to 0), at the engine's skill-band split (own_split -0.5). On the 15 novice stretches of the curated data it
 * gives ~0.8 hint offers per 100 moves (vs ~7 at -0.8), so a stronger newcomer is not nagged while a weaker one still
 * gets the clearest hints; the first review (or 120 moves into the first game) replaces it.
 */
export const DEFAULT_SKILL = -0.5;

export interface SkillSample {
  id: string;
  skill: number;
  moves: number;
  at: number;
}

export interface Player {
  skill: number | null;
  samples: SkillSample[];
}

export const player = createStore<Player>(readJson<Player>('player', { skill: null, samples: [] }));
player.subscribe((p) => writeJson('player', p));

export function effectiveSkill(): number {
  return player.get().skill ?? DEFAULT_SKILL;
}

/** Adds (or replaces) a game's skill reading and recomputes the estimate: moves-weighted, last 6 games. */
export function addSkillSample(id: string, skill: number | undefined, moves: number): void {
  if (skill === undefined || !Number.isFinite(skill)) return;
  const samples = [{ id, skill, moves, at: Date.now() }, ...player.get().samples.filter((s) => s.id !== id)].slice(0, 6);
  let w = 0;
  let sum = 0;
  for (const s of samples) {
    const wi = Math.min(Math.max(s.moves, 50), 600);
    w += wi;
    sum += wi * s.skill;
  }
  player.set({ skill: Math.round((sum / w) * 1000) / 1000, samples });
}

export function resetSkill(): void {
  player.set({ skill: null, samples: [] });
}

/** A plain-words level for a skill value (guide medians: novices -0.8, intermediate and strong -0.2 to 0). */
export function skillLabel(s: number | null | undefined): string {
  if (s === null || s === undefined) return 'Not estimated yet';
  if (s < -0.65) return 'Beginner';
  if (s < -0.35) return 'Improving';
  if (s < -0.1) return 'Intermediate';
  return 'Strong';
}
