import { describe, expect, it } from 'vitest';
import {
  type Board,
  type Dir,
  Sfc32,
  boardCode,
  boardFromInput,
  canMove,
  engineBoard,
  fromBoardCode,
  legalDirs,
  move,
  movesBetween,
  newBoard,
  parseBoard,
  pickSpawn,
  spawnBetween,
  tileSum,
} from './rules.ts';

const B = (rows: number[][]): Board => rows.flat().map((v) => (v ? Math.log2(v) : 0));
const V = (b: Board) => b.map((r) => (r ? 2 ** r : 0));

describe('move', () => {
  it('slides and merges a row to the left like the engine', () => {
    const cases: [number[], number[], number][] = [
      [[2, 2, 2, 2], [4, 4, 0, 0], 8],
      [[2, 2, 4, 4], [4, 8, 0, 0], 12],
      [[4, 0, 4, 4], [8, 4, 0, 0], 8],
      [[4, 4, 8, 0], [8, 8, 0, 0], 8], // a merged tile does not merge again in the same move
      [[0, 0, 0, 2], [2, 0, 0, 0], 0],
      [[2, 4, 8, 16], [2, 4, 8, 16], 0],
      [[8, 8, 8, 0], [16, 8, 0, 0], 16], // the pair nearest to the side merges first
    ];
    for (const [row, want, score] of cases) {
      const b = B([row, [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]);
      const r = move(b, 3);
      expect(V(r.board).slice(0, 4)).toEqual(want);
      expect(r.score).toBe(score);
    }
  });

  it('handles all four directions', () => {
    const b = B([
      [2, 0, 0, 2],
      [0, 4, 0, 0],
      [0, 4, 0, 0],
      [2, 0, 0, 8],
    ]);
    expect(V(move(b, 0).board)).toEqual([4, 8, 0, 2, 0, 0, 0, 8, 0, 0, 0, 0, 0, 0, 0, 0]);
    expect(V(move(b, 2).board)).toEqual([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 4, 8, 0, 8]);
    expect(V(move(b, 1).board)).toEqual([0, 0, 0, 4, 0, 0, 0, 4, 0, 0, 0, 4, 0, 0, 2, 8]);
    expect(V(move(b, 3).board)).toEqual([4, 0, 0, 0, 4, 0, 0, 0, 4, 0, 0, 0, 2, 8, 0, 0]);
  });

  it('reports illegal moves and tracks every tile', () => {
    const b = B([
      [2, 4, 8, 16],
      [0, 0, 0, 0],
      [0, 0, 0, 0],
      [0, 0, 0, 0],
    ]);
    expect(move(b, 0).moved).toBe(false);
    expect(move(b, 3).moved).toBe(false);
    expect(move(b, 1).moved).toBe(false);
    const down = move(b, 2);
    expect(down.moved).toBe(true);
    expect(down.steps).toEqual([
      { from: 0, to: 12, merged: false },
      { from: 1, to: 13, merged: false },
      { from: 2, to: 14, merged: false },
      { from: 3, to: 15, merged: false },
    ]);
    const m = move(B([[2, 2, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]), 1);
    expect(m.steps).toEqual([
      { from: 1, to: 3, merged: true },
      { from: 0, to: 3, merged: true },
    ]);
  });

  it('keeps big tiles exact (no 4-bit cap)', () => {
    const b = B([[32768, 32768, 65536, 65536], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]);
    const r = move(b, 3);
    expect(V(r.board).slice(0, 4)).toEqual([65536, 131072, 0, 0]);
    expect(r.score).toBe(65536 + 131072);
  });

  it('detects dead boards', () => {
    const dead = B([
      [2, 4, 16, 2],
      [8, 32, 64, 4],
      [16, 128, 512, 8],
      [4, 2, 256, 16],
    ]);
    expect(canMove(dead)).toBe(false);
    expect(legalDirs(dead)).toEqual([]);
  });
});

describe('spawns', () => {
  it('picks a uniform empty cell and a 4 one time in ten', () => {
    const rng = Sfc32.fromNumber(12345);
    const b = B([[2, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 2]]);
    const cells = new Array(16).fill(0);
    let fours = 0;
    const n = 140000;
    for (let i = 0; i < n; i++) {
      const s = pickSpawn(b, rng)!;
      cells[s.cell]++;
      if (s.rank === 2) fours++;
    }
    expect(cells[0]).toBe(0);
    expect(cells[15]).toBe(0);
    for (let c = 1; c < 15; c++) expect(Math.abs(cells[c] / n - 1 / 14)).toBeLessThan(0.003);
    expect(Math.abs(fours / n - 0.1)).toBeLessThan(0.004);
  });

  it('starts a game with two tiles', () => {
    const rng = Sfc32.fromNumber(7);
    for (let i = 0; i < 200; i++) {
      const b = newBoard(rng);
      expect(b.filter((v) => v > 0).length).toBe(2);
      expect(tileSum(b)).toBeGreaterThanOrEqual(4);
      expect(tileSum(b)).toBeLessThanOrEqual(8);
    }
  });

  it('finds the spawn and the move between two boards', () => {
    const before = B([[2, 2, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]);
    const after = move(before, 3).board;
    const next = after.slice();
    next[15] = 1;
    expect(spawnBetween(after, next)).toEqual({ cell: 15, rank: 1 });
    expect(movesBetween(before, next)).toEqual([3]);
    expect(spawnBetween(after, after)).toBeNull();
  });

  it('sees the rare ambiguous transitions', () => {
    // left and right leave the lone 2 at either end; a spawn at the other end makes both boards equal
    const before = B([
      [0, 2, 0, 0],
      [2, 4, 2, 4],
      [4, 2, 4, 2],
      [2, 4, 2, 4],
    ]);
    const next = B([
      [2, 0, 0, 2],
      [2, 4, 2, 4],
      [4, 2, 4, 2],
      [2, 4, 2, 4],
    ]);
    expect(movesBetween(before, next).sort()).toEqual([1, 3]);
  });
});

describe('encodings', () => {
  it('parses boards like the engine', () => {
    expect(V(parseBoard('2 4 0 0 / 8 16 0 0 / 0 0 0 0 / 0 0 0 2')!)).toEqual([2, 4, 0, 0, 8, 16, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2]);
    expect(parseBoard('0001000001000000')![3]).toBe(1);
    expect(parseBoard('0 0 0 2 0 0 0 0 0 2 0 0 0 0 0 0')![3]).toBe(1); // tile list, not hex
    expect(parseBoard('1 2 3')).toBeNull();
    expect(parseBoard('3 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0')).toBeNull();
    expect(parseBoard('131072 65536 0 0 0 0 0 0 0 0 0 0 0 0 0 0')!.slice(0, 2)).toEqual([17, 16]);
  });

  it('round-trips the compact code and accepts API inputs', () => {
    const b = B([[2, 4, 8, 16], [32, 64, 128, 256], [512, 1024, 2048, 4096], [8192, 16384, 32768, 65536]]);
    expect(fromBoardCode(boardCode(b))).toEqual(b);
    expect(boardCode(B([[0, 2, 4, 8], [0, 0, 16, 32], [0, 2, 64, 128], [2, 4, 256, 512]]))).toBe('0123004501671289');
    expect(engineBoard(b)).toContain('65536');
    expect(boardFromInput([[2, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 4]])).toEqual([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2]);
    expect(boardFromInput([3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])).toBeNull();
    expect(boardFromInput([2, 0])).toBeNull();
    expect(boardFromInput('2 0 0 0 0 0 0 0 0 0 0 0 0 0 0 4')).toEqual([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2]);
    expect(boardFromInput({ a: 1 })).toBeNull();
  });

  it('plays deterministic games from a seed', () => {
    const play = (seed: number) => {
      const rng = Sfc32.fromNumber(seed);
      let b = newBoard(rng);
      const codes: string[] = [];
      for (let i = 0; i < 50; i++) {
        const d = legalDirs(b)[0] as Dir | undefined;
        if (d === undefined) break;
        b = move(b, d).board;
        const s = pickSpawn(b, rng)!;
        b[s.cell] = s.rank;
        codes.push(boardCode(b));
      }
      return codes;
    };
    expect(play(99)).toEqual(play(99));
    expect(play(99)).not.toEqual(play(100));
  });
});
