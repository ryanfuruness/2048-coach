import { beforeEach, describe, expect, it } from 'vitest';
import { type Board, type Dir, Sfc32, boardCode, legalDirs, newBoard, move, applySpawn } from '@shared/rules.ts';
import { type Fact, Line, decodeFacts, decodeSpawn, encodeFacts, encodeSpawn, loadLineRecord } from './line.ts';

function playRandom(line: Line, n: number, seed: number, by: 'u' | 'c' = 'u'): void {
  const rng = Sfc32.fromNumber(seed);
  for (let i = 0; i < n; i++) {
    const legal = legalDirs(line.board());
    if (!legal.length) break;
    line.play(legal[Math.floor(rng.next() * legal.length)], by);
  }
}

describe('workbench line', () => {
  it('encodes spawns in one character', () => {
    for (let cell = 0; cell < 16; cell++)
      for (const rank of [1, 2] as const) expect(decodeSpawn(encodeSpawn({ cell, rank }))).toEqual({ cell, rank });
  });

  it('replays a saved line to the same boards and scores', () => {
    const line = Line.fresh(newBoard(Sfc32.fromNumber(1)), 'new', Sfc32.fromNumber(2));
    playRandom(line, 400, 3);
    const copy = new Line(line.snapshot(), Sfc32.fromNumber(9));
    expect(copy.boards.map(boardCode)).toEqual(line.boards.map(boardCode));
    expect(copy.scores).toEqual(line.scores);
    expect(copy.tops).toEqual(line.tops);
    expect(copy.cursor).toBe(line.n);
    // every board follows from the one before by its move and its new tile
    for (let k = 0; k < line.n; k++) {
      const r = move(line.boards[k], line.moveAt(k) as Dir);
      expect(boardCode(applySpawn(r.board, decodeSpawn(line.rec.spawns[k])))).toBe(boardCode(line.boards[k + 1]));
      expect(line.scores[k + 1] - line.scores[k]).toBe(r.score);
    }
  });

  it('steps back and forward without changing the line', () => {
    const line = Line.fresh(newBoard(Sfc32.fromNumber(4)), 'new', Sfc32.fromNumber(5));
    playRandom(line, 60, 6);
    const n = line.n;
    const end = boardCode(line.board());
    expect(line.seek(n - 10)).toBe(true);
    expect(line.n).toBe(n);
    for (let i = 0; i < 10; i++) {
      const before = line.board();
      const f = line.forward()!;
      expect(f.kind).toBe('follow');
      expect(boardCode(f.result.board)).toBe(boardCode(move(before, line.moveAt(line.cursor - 1) as Dir).board));
    }
    expect(line.forward()).toBeNull();
    expect(boardCode(line.board())).toBe(end);
    expect(line.seek(-5)).toBe(true);
    expect(line.cursor).toBe(0);
    expect(line.seek(0)).toBe(false);
  });

  it('follows the continuation when the same move is played, and replaces it otherwise', () => {
    const line = Line.fresh(newBoard(Sfc32.fromNumber(7)), 'new', Sfc32.fromNumber(8));
    playRandom(line, 80, 9);
    const n = line.n;
    const original = line.snapshot();
    line.seek(30);
    const same = line.moveAt(30) as Dir;
    const r1 = line.play(same, 'u')!;
    expect(r1.kind).toBe('follow');
    expect(line.n).toBe(n);
    expect(boardCode(line.board())).toBe(boardCode(new Line(original, Sfc32.fromNumber(1)).boards[31]));
    // a different legal move replaces the continuation
    const other = legalDirs(line.board()).find((d) => d !== line.moveAt(31))!;
    const r2 = line.play(other, 'c')!;
    expect(r2.kind).toBe('new');
    expect(r2.dropped).toBe(n - 31);
    expect(r2.replaced!.moves).toBe(original.moves);
    expect(line.n).toBe(32);
    expect(line.author(31)).toBe('c');
    expect(line.author(30)).toBe('u');
    expect(line.ownMoves()).toBe(31);
    // the replaced line can be restored exactly
    const back = new Line(r2.replaced!, Sfc32.fromNumber(1));
    expect(back.boards.map(boardCode)).toEqual(new Line(original, Sfc32.fromNumber(1)).boards.map(boardCode));
  });

  it('rejects an illegal move without changing the line', () => {
    const b: Board = [1, 2, 3, 4, ...Array(12).fill(0)];
    const line = Line.fresh(b, 'position', Sfc32.fromNumber(1));
    expect(line.play(0, 'u')).toBeNull();
    expect(line.n).toBe(0);
  });

  it('keeps the facts of a position but forgets the cost of a replaced move', () => {
    const line = Line.fresh(newBoard(Sfc32.fromNumber(11)), 'new', Sfc32.fromNumber(12));
    playRandom(line, 20, 13);
    for (let k = 0; k <= line.n; k++) line.setFact(k, { tile: 2048, p: 0.99 - k / 1000, best: 2, loss: k < line.n ? 0.01 * k : undefined });
    line.seek(10);
    const other = legalDirs(line.board()).find((d) => d !== line.moveAt(10))!;
    line.play(other, 'u');
    expect(line.facts.length).toBeLessThanOrEqual(12);
    expect(line.facts[10]).toEqual({ tile: 2048, p: 0.99 - 10 / 1000, best: 2, loss: undefined });
    expect(line.facts[9]!.loss).toBeCloseTo(0.09, 6);
  });

  it('encodes facts compactly and decodes them back', () => {
    const facts: (Fact | undefined)[] = [
      { tile: 2048, p: 0.99912, best: 2, loss: 0 },
      undefined,
      { tile: 4096, p: null, best: -1, loss: null },
      { tile: 0, p: 0.5, best: 3, loss: undefined },
      { tile: 65536, p: 1, best: 0, loss: 1 },
    ];
    const s = encodeFacts(facts, 6);
    expect(s.length).toBe(48);
    const d = decodeFacts(s, 6);
    expect(d[1]).toBeUndefined();
    expect(d[5]).toBeUndefined();
    expect(d[0]!.tile).toBe(2048);
    expect(d[0]!.p!).toBeCloseTo(0.99912, 4);
    expect(d[0]!.loss).toBe(0);
    expect(d[2]).toEqual({ tile: 4096, p: null, best: -1, loss: null });
    expect(d[3]!.loss).toBeUndefined();
    expect(d[3]!.tile).toBe(0);
    expect(d[4]).toEqual({ tile: 65536, p: 1, best: 0, loss: 1 });
  });
});

describe('line storage', () => {
  const store = new Map<string, string>();
  beforeEach(() => {
    store.clear();
    (globalThis as { localStorage?: unknown }).localStorage = {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
      removeItem: (k: string) => void store.delete(k),
    };
  });

  it("takes over app v1's game in progress", () => {
    const line = Line.fresh(newBoard(Sfc32.fromNumber(21)), 'new', Sfc32.fromNumber(22));
    playRandom(line, 50, 23);
    store.set('tc.current', JSON.stringify('abc'));
    store.set(
      'tc.g.abc',
      JSON.stringify({ v: 1, id: 'abc', startedAt: 1, start: line.rec.start, moves: line.rec.moves, spawns: line.rec.spawns, origin: 'new', coach: line.rec.coach, score: 0 }),
    );
    const rec = loadLineRecord()!;
    expect(rec.v).toBe(2);
    expect(rec.cursor).toBe(50);
    expect(rec.by).toBe('u'.repeat(50));
    expect(new Line(rec, Sfc32.fromNumber(1)).boards.map(boardCode)).toEqual(line.boards.map(boardCode));
  });

  it('prefers the saved line', () => {
    const line = Line.fresh(newBoard(Sfc32.fromNumber(31)), 'position', Sfc32.fromNumber(32));
    playRandom(line, 10, 33);
    line.seek(4);
    store.set('tc.line', JSON.stringify(line.snapshot()));
    const rec = loadLineRecord()!;
    expect(rec.cursor).toBe(4);
    expect(rec.moves).toBe(line.rec.moves);
  });
});
