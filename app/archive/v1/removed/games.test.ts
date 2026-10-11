import { describe, expect, it } from 'vitest';
import { DIR_CHARS, Sfc32, boardCode, legalDirs, newBoard } from '@shared/rules.ts';
import { decodeSpawn, encodeSpawn, newRecord, playMove, replay } from './games.ts';
import { milestone, chance, cost, because, share, lossClass, healthOf } from './format.ts';
import { tilesAfterMove, tilesFromBoard } from '../components/tiles.ts';
import { move } from '@shared/rules.ts';

describe('game records', () => {
  it('encode spawns in one character', () => {
    for (let cell = 0; cell < 16; cell++)
      for (const rank of [1, 2] as const) expect(decodeSpawn(encodeSpawn({ cell, rank }))).toEqual({ cell, rank });
  });

  it('replay to the same boards that were played', () => {
    const rng = Sfc32.fromNumber(42);
    const start = newBoard(rng);
    const g = newRecord(start, 'new');
    const boards = [start];
    for (let i = 0; i < 400; i++) {
      const legal = legalDirs(boards[boards.length - 1]);
      if (!legal.length) break;
      const r = playMove(g, boards[boards.length - 1], legal[Math.floor(rng.next() * legal.length)], rng)!;
      boards.push(r.board);
    }
    expect(g.moves.length).toBe(boards.length - 1);
    expect(replay(g).map(boardCode)).toEqual(boards.map(boardCode));
    expect([...g.moves].every((c) => DIR_CHARS.includes(c as 'U'))).toBe(true);
    expect(g.over).toBe(legalDirs(boards[boards.length - 1]).length === 0);
  });

  it('rejects an illegal move without changing the record', () => {
    const b = [1, 2, 3, 4, ...Array(12).fill(0)];
    const g = newRecord(b, 'position');
    expect(playMove(g, b, 0, Sfc32.fromNumber(1))).toBeNull();
    expect(g.moves).toBe('');
  });
});

describe('tile animation model', () => {
  it('ends every move with exactly the tiles of the new board', () => {
    const rng = Sfc32.fromNumber(9);
    let board = newBoard(rng);
    let tiles = tilesFromBoard(board);
    const g = newRecord(board, 'new');
    for (let i = 0; i < 300; i++) {
      const legal = legalDirs(board);
      if (!legal.length) break;
      const d = legal[Math.floor(rng.next() * legal.length)];
      const r = playMove(g, board, d, rng)!;
      tiles = tilesAfterMove(tiles, r.result.steps, r.result.board, r.spawn);
      board = r.board;
      const live = tiles.filter((t) => t.kind !== 'ghost');
      const seen = Array(16).fill(0);
      for (const t of live) seen[t.cell] = t.rank;
      expect(seen).toEqual(board);
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
