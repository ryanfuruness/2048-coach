// The coach's verdict on every move, as the engine grades it (src/analyze.cpp, grade_moves):
//   best          the coach's move, or one it cannot tell apart from it
//   good          fine, but the coach would play something else
//   questionable  the coach would never play it
//   blunder       an obvious mistake with a name: the biggest tile out of its corner, the biggest tiles pulled off the
//                 edge, a move that can end the game, or a big loss
// The first stretch of a game (largest tile up to 256) is free: leaving the corner is not graded there.
import type { DirName } from '@shared/rules.ts';
import type { GradeName } from './line.ts';
import type { Analysis, MoveInfo, ReviewPly } from './types.ts';

export type { GradeName };

export const GRADE_WORDS: Record<GradeName, string> = { best: 'Best', good: 'Good', questionable: 'Questionable', blunder: 'Blunder' };

/** The coach's move: what Space, the arrow on the board and autoplay play. */
export function coachOf(a: Pick<Analysis, 'moves' | 'engine_move' | 'game_over' | 'coach_move'>): DirName | null {
  if (a.game_over) return null;
  return a.coach_move ?? a.moves.find((m) => m.loss === 0)?.move ?? a.engine_move;
}

/** The verdict on move `name` of an analysis (null: not graded - not judged, or an older server). */
export function moveOf(a: { moves: MoveInfo[] } | ReviewPly, name: DirName): MoveInfo | undefined {
  return (a.moves as MoveInfo[]).find((m) => m.move === name);
}

export function gradeOf(a: { moves: MoveInfo[]; judged?: false } | ReviewPly, name: DirName): GradeName | null {
  if (a.judged === false) return null;
  return moveOf(a, name)?.grade ?? null;
}

/** A reason short enough for one line: the engine's longer explanations are cut at their first colon or bracket. */
export function shortWhy(why: string | undefined): string {
  if (!why) return '';
  const cut = why.search(/: | \(/);
  return cut > 0 ? why.slice(0, cut) : why;
}

export const isFlagged = (g: GradeName | null | undefined): boolean => g === 'questionable' || g === 'blunder';
