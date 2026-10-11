import { describe, expect, it } from 'vitest';
import { Sfc32, legalDirs, move, newBoard } from '@shared/rules.ts';
import { tilesAfterMove, tilesFromBoard } from '../components/tiles.ts';
import { because, chance, cost, healthOf, lossClass, milestone, share } from './format.ts';
import { coachOf, costClass, costOf, shareClass } from './chance.ts';
import { Line, decodeFacts, encodeFacts } from './line.ts';
import { moveAccuracy, ownSummary } from './summary.ts';
import type { Analysis, ReviewPly, ReviewResult } from './types.ts';
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

describe('review of the player own moves', () => {
  const ply = (played: 'up' | 'down', best: 'up' | 'down', loss: number): ReviewPly => ({
    played,
    best,
    engine: best,
    source: 'search',
    summary: '',
    plan: '',
    moves: [
      { move: best, loss: 0, real_loss: 0, reasons: [] },
      ...(played !== best ? [{ move: played, loss: loss, real_loss: loss, reasons: [] }] : []),
    ],
  });
  const summary = (key: { ply: number; played: 'up' | 'down'; engine: 'up' | 'down'; real_loss: number }[]) =>
    ({
      moves: 4, match: 0, good: 0.5, accuracy: 70, kept: 0.8, decisive_move: 4, decisive_loss: 0.2, mean_real_loss: 0, inaccuracies: 0, mistakes: 1,
      blunders: 1, skill_t: null, mistakes_at_your_level: 0, warnings: 0, warnings_per_100: 0, hints: 0, hints_per_100: 0, hard_moments: 0, hard_found: 0,
      hard_found_plies: [], phases: [], skill: 0.1,
      key_moments: key.map((m) => ({ ...m, board: '', your_cost: 0, why: '' })),
    }) as ReviewResult['summary'];

  it('grades every own move by its cost when the player made every move', () => {
    const plies = [ply('up', 'up', 0), ply('down', 'up', 0.05), ply('up', 'up', 0), ply('down', 'up', 0.2)];
    const data: ReviewResult = { summary: summary([{ ply: 4, played: 'down', engine: 'up', real_loss: 0.2 }]), plies, engine: { networks: 'light', ms: 1 } };
    const s = ownSummary({ lineId: 'x', start: 0, moves: 'UDUD', data }, 'uuuu', 4);
    expect(s.accuracy).toBeCloseTo((2 * moveAccuracy(0) + moveAccuracy(0.05) + moveAccuracy(0.2)) / 4, 6);
    expect(s.decisive?.pos).toBe(3);
    expect(s.decisive?.cost.rel).toBe(0.2);
    expect(s.byChance).toBe(false);
    expect(s.levelApplies).toBe(true);
  });

  it("leaves out the coach's moves", () => {
    const plies = [ply('up', 'up', 0), ply('down', 'up', 0.05), ply('up', 'up', 0), ply('down', 'up', 0.2)];
    const data: ReviewResult = {
      summary: summary([
        { ply: 2, played: 'down', engine: 'up', real_loss: 0.05 },
        { ply: 4, played: 'down', engine: 'up', real_loss: 0.2 },
      ]),
      plies,
      engine: { networks: 'light', ms: 1 },
    };
    // the coach played moves 1 and 3 (both best): the player's 2 moves cost 5% and 20%
    const s = ownSummary({ lineId: 'x', start: 0, moves: 'UDUD', data }, 'cucu', 4);
    expect(s.own).toBe(2);
    expect(s.coach).toBe(2);
    expect(s.good).toBe(0);
    expect(s.mistakes).toBe(1);
    expect(s.blunders).toBe(1);
    expect(s.accuracy).toBeCloseTo((moveAccuracy(0.05) + moveAccuracy(0.2)) / 2, 6);
    expect(s.keyMoments.map((m) => m.pos)).toEqual([3, 1]); // costliest first
    expect(s.levelApplies).toBe(false);
    // a coach move with a cost (never expected) would not count either
    const s2 = ownSummary({ lineId: 'x', start: 0, moves: 'UDUD', data }, 'ucuc', 4);
    expect(s2.keyMoments).toEqual([]);
    expect(s2.good).toBe(1);
  });
});

describe('your chance', () => {
  const a = (moves: { move: 'up' | 'down' | 'left'; chance: number; loss: number; real?: number }[], best: number, coach?: 'up' | 'down' | 'left') =>
    ({
      board: [],
      hex: '',
      stage: 0,
      depth: 3,
      engine_move: 'down',
      source: 'search',
      summary: '',
      plan: '',
      chance: { target: 2048, now: best - 0.01, best, skill: -0.5 },
      coach_move: coach,
      moves: moves.map((m) => ({ move: m.move, loss: m.move === 'down' ? 0 : 100, real_loss: m.real ?? 0, chance: m.chance, chance_loss: m.loss, reasons: [] })),
    }) as Analysis;

  it("plays the coach's move, else the engine's reference move", () => {
    expect(coachOf(a([{ move: 'down', chance: 0.5, loss: 0 }], 0.5, 'up'))).toBe('up');
    expect(coachOf(a([{ move: 'down', chance: 0.5, loss: 0 }], 0.5))).toBe('down');
  });

  it('grades moves by the share of your chance they give away, with a floor in points', () => {
    const x = a(
      [
        { move: 'down', chance: 0.6, loss: 0 },
        { move: 'up', chance: 0.57, loss: 0.03 }, // 5% of 0.6 and 3 points: an inaccuracy
        { move: 'left', chance: 0.3, loss: 0.3, real: 0 }, // half of it: a blunder, although the engine calls it free
      ],
      0.6,
    );
    expect(costClass(costOf(x, 'up'))).toBe('inaccuracy');
    expect(costClass(costOf(x, 'left'))).toBe('blunder');
    expect(costOf(x, 'left')?.after).toBe(0.3);
    // a large share of a tiny chance is not a blunder: 1 point of a 2% chance
    const tiny = a([{ move: 'down', chance: 0.02, loss: 0 }, { move: 'up', chance: 0.01, loss: 0.01 }], 0.02);
    expect(costClass(costOf(tiny, 'up'))).toBe(null);
    // stored facts: the points are estimated from the position's chance
    expect(shareClass(0.5, 'chance', 0.6)).toBe('blunder');
    expect(shareClass(0.5, 'chance', 0.02)).toBe(null);
    expect(shareClass(0.05, 'engine')).toBe('mistake');
  });

  it("keeps your chance in the timeline's facts", () => {
    const x = a([{ move: 'down', chance: 0.6, loss: 0 }, { move: 'up', chance: 0.3, loss: 0.3 }], 0.6, 'down');
    const f = factOf(x, 0); // the player pressed up
    expect(f).toEqual({ tile: 2048, p: 0.59, best: 2, loss: 0.5, you: true });
    const back = decodeFacts(encodeFacts([f, undefined], 2), 2);
    expect(back[0]?.you).toBe(true);
    expect(back[0]?.best).toBe(2);
    expect(back[0]?.loss).toBeCloseTo(0.5, 4);
    expect(back[1]).toBeUndefined();
    // an engine fact (older lines) stays one
    const old = decodeFacts(encodeFacts([{ tile: 2048, p: 0.99, best: 1, loss: 0.01 }], 1), 1)[0];
    expect(old?.you).toBeUndefined();
    expect(old?.best).toBe(1);
  });
});
