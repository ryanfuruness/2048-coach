import { describe, expect, it } from 'vitest';
import { Sfc32, legalDirs, move, newBoard } from '@shared/rules.ts';
import { tilesAfterMove, tilesFromBoard } from '../components/tiles.ts';
import { because, chance, cost, healthOf, lossClass, milestone, share } from './format.ts';
import { coachOf, gradeOf, shortWhy } from './grades.ts';
import { Line } from './line.ts';
import type { Analysis } from './types.ts';
import { factOf } from './workbench.ts';

describe('tile animation model', () => {
  it('ends every move with exactly the tiles of the new board', () => {
    const rng = Sfc32.fromNumber(9);
    const line = Line.fresh(newBoard(rng), 'new', rng);
    let tiles = tilesFromBoard(line.board());
    for (let i = 0; i < 300; i++) {
      const legal = legalDirs(line.board());
      if (!legal.length) break;
      const r = line.play(legal[Math.floor(rng.next() * legal.length)], 'u')!;
      tiles = tilesAfterMove(tiles, r.result.steps, r.result.board, r.spawn);
      const live = tiles.filter((t) => t.kind !== 'ghost');
      const seen = Array(16).fill(0);
      for (const t of live) seen[t.cell] = t.rank;
      expect(seen).toEqual(line.board());
      expect(new Set(live.map((t) => t.id)).size).toBe(live.length);
    }
  });

  it('slides merging tiles onto the merged cell as ghosts', () => {
    const b = [1, 1, 0, 0, ...Array(12).fill(0)];
    const r = move(b, 3);
    const t = tilesAfterMove(tilesFromBoard(b), r.steps, r.board, null);
    expect(t.filter((x) => x.kind === 'ghost').map((x) => x.cell)).toEqual([0, 0]);
    expect(t.filter((x) => x.kind === 'merged')).toEqual([expect.objectContaining({ cell: 0, rank: 2 })]);
  });
});

describe('plain words', () => {
  it('formats chances and costs', () => {
    expect(chance(0.9995)).toBe('>99.9%');
    expect(chance(0.998)).toBe('99.8%');
    expect(chance(0.63)).toBe('63%');
    expect(chance(0.004)).toBe('0.4%');
    expect(cost(0.0566)).toBe('about 6%');
    expect(cost(0.024)).toBe('about 2.4%');
    expect(cost(0.26)).toBe('about 26%');
    expect(cost(0.004)).toBe('less than 1%');
    expect(share(0.997)).toBe('99.7%');
    expect(share(0.93)).toBe('93%');
  });

  it('picks the next milestone and says why', () => {
    expect(milestone({ '4096': 0.99, '2048': 0.999, '32768': 0.6 })).toEqual({ tile: 2048, p: 0.999 });
    expect(milestone(undefined)).toBeNull();
    expect(because({ code: 'risk', text: 'is riskier', share: 0.7 })).toBe('Mainly because it is riskier.');
    expect(because({ code: 'center', text: 'brings a big tile into the middle', share: 0.3 })).toBe('Partly because it brings a big tile into the middle.');
    expect(because({ code: 'area', text: 'weakens the top-left area' })).toBe('It weakens the top-left area.');
    expect(lossClass(0.12)).toBe('blunder');
    expect(lossClass(0.05)).toBe('mistake');
    expect(lossClass(0.015)).toBe('inaccuracy');
    expect(lossClass(0.002)).toBeNull();
    expect(healthOf({ summary: 'With best play ... (in trouble compared with a typical position at this stage).' })).toBe('critical');
  });
});

describe('grades', () => {
  const a = {
    board: [],
    hex: '',
    stage: 0,
    depth: 3,
    engine_move: 'down',
    source: 'search',
    summary: '',
    plan: '',
    coach_move: 'right',
    moves: [
      { move: 'down', loss: 0, grade: 'best', pick: 0.3, reasons: [] },
      { move: 'right', loss: 10, grade: 'best', pick: 0.6, reasons: [] },
      { move: 'up', loss: 900, grade: 'blunder', why: 'can end the game: 40% of new tiles leave no move', pick: 0.01, reasons: [] },
    ],
  } as unknown as Analysis;

  it("plays the coach's move, else the engine's reference move", () => {
    expect(coachOf(a)).toBe('right');
    expect(coachOf({ ...a, coach_move: undefined })).toBe('down');
    expect(coachOf({ ...a, game_over: true })).toBeNull();
  });

  it('reads a move grade and a short reason', () => {
    expect(gradeOf(a, 'up')).toBe('blunder');
    expect(gradeOf({ ...a, judged: false }, 'up')).toBeNull();
    expect(shortWhy('can end the game: 40% of new tiles leave no move')).toBe('can end the game');
    expect(shortWhy('is riskier (vs 0% after right)')).toBe('is riskier');
    expect(shortWhy('takes your 2048 out of its corner')).toBe('takes your 2048 out of its corner');
  });

  it('keeps the coach move and the played grade in the facts', () => {
    expect(factOf(a, 0)).toEqual({ best: 1, grade: 'blunder' });
    expect(factOf(a, -1)).toEqual({ best: 1 });
  });
});
