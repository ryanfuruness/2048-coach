// The workbench controller against a fake analysis server that follows the real rules (the engine's own answers are
// covered by the server's end-to-end test): autoplay per move and in batches, following the line from an earlier
// position, replacing and restoring a continuation, and how a review relates to a line that changed.
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  type Board,
  type Dir,
  DIR_CHARS,
  DIR_NAMES,
  Sfc32,
  applySpawn,
  boardFromInput,
  boardCode,
  canMove,
  legalDirs,
  maxRank,
  move,
  newBoard,
  pickSpawn,
} from '@shared/rules.ts';
import { Line } from './line.ts';
import { Workbench } from './workbench.ts';

// the fake engine's best move: down, then left, right, up (a corner player)
const ORDER: Dir[] = [2, 3, 1, 0];
const bestDir = (b: Board): Dir | -1 => ORDER.find((d) => move(b, d).moved) ?? -1;

function analysis(b: Board) {
  const best = bestDir(b);
  return {
    board: [],
    hex: boardCode(b),
    stage: 0,
    depth: 3,
    engine_move: best === -1 ? null : DIR_NAMES[best],
    source: 'search',
    odds: { '2048': 0.99 - maxRank(b) / 1000 },
    summary: 'about as good as a typical position',
    plan: '',
    ...(best === -1 ? { game_over: true } : {}),
    moves: legalDirs(b).map((d) => ({
      move: DIR_NAMES[d],
      loss: d === best ? 0 : 0.2,
      real_loss: d === best ? 0 : 0.05,
      grade: d === best ? 'best' : d === 0 ? 'blunder' : 'good',
      ...(d === 0 && d !== best ? { why: 'takes your 8 out of its corner' } : {}),
      pick: d === best ? 0.8 : 0.1,
      reasons: [],
    })),
  };
}

const B32 = '0123456789abcdefghijklmnopqrstuv';
const calls = { analyze: 0, autoplay: 0, review: 0 };

function fakeServer(path: string, body: Record<string, unknown>): unknown {
  if (path === '/api/analyze') {
    calls.analyze++;
    return analysis(boardFromInput(body.board)!);
  }
  if (path === '/api/autoplay') {
    calls.autoplay++;
    const rng = Sfc32.fromNumber(body.seed as number);
    let b = boardFromInput(body.board)!;
    let moves = '';
    let spawns = '';
    const facts: { t: number; p: number; b: string }[] = [];
    let over = false;
    for (let i = 0; i < (body.n as number); i++) {
      const d = bestDir(b);
      if (d === -1) {
        over = true;
        break;
      }
      const r = move(b, d);
      const sp = pickSpawn(r.board, rng)!;
      facts.push({ t: 2048, p: 0.99 - maxRank(b) / 1000, b: DIR_CHARS[d] });
      b = applySpawn(r.board, sp);
      moves += DIR_CHARS[d];
      spawns += B32[sp.cell + (sp.rank === 2 ? 16 : 0)];
      if (!canMove(b)) {
        over = true;
        break;
      }
      if (body.stop_rank && maxRank(b) >= (body.stop_rank as number)) break;
    }
    return { moves, spawns, facts, over };
  }
  if (path === '/api/review') {
    calls.review++;
    const moves = body.moves as string;
    const boards = (body.boards as string[]).map((c) => [...c].map((ch) => '0123456789abcdefghijklmnopqrstuvwxyz'.indexOf(ch)));
    const plies = [...moves].map((c, i) => {
      const best = bestDir(boards[i]);
      const played = DIR_NAMES[DIR_CHARS.indexOf(c as 'U')];
      return { played, best: DIR_NAMES[best as Dir], engine: DIR_NAMES[best as Dir], source: 'search', summary: '', plan: '', odds: { '2048': 0.98 }, moves: analysis(boards[i]).moves };
    });
    return { summary: { moves: moves.length, good: 1, accuracy: 100, key_moments: [], phases: [], skill: 0.2 }, plies, engine: { networks: 'light', ms: 1 } };
  }
  throw new Error(`no fake for ${path}`);
}

const realFetch = globalThis.fetch;
beforeEach(() => {
  calls.analyze = calls.autoplay = calls.review = 0;
  const store = new Map<string, string>();
  (globalThis as { localStorage?: unknown }).localStorage = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  };
  globalThis.fetch = (async (url: string, init?: RequestInit) => {
    const out = fakeServer(String(url), JSON.parse(String(init?.body ?? '{}')));
    return new Response(JSON.stringify(out), { status: 200, headers: { 'Content-Type': 'application/json' } });
  }) as typeof fetch;
});
afterEach(() => {
  globalThis.fetch = realFetch;
});

const until = async (cond: () => boolean, ms = 5000) => {
  const t0 = Date.now();
  while (!cond()) {
    if (Date.now() - t0 > ms) throw new Error('timed out');
    await new Promise((r) => setTimeout(r, 5));
  }
};

function bench(seed: number): Workbench {
  const line = Line.fresh(newBoard(Sfc32.fromNumber(seed)), 'new', Sfc32.fromNumber(seed + 1));
  return new Workbench(line, 3);
}

describe('workbench autoplay', () => {
  it('plays the coach moves in batches at full speed and stops after 100 moves', async () => {
    const wb = bench(1);
    wb.startAuto(100);
    await until(() => !wb.auto.on);
    expect(wb.line.n).toBe(100);
    expect(calls.autoplay).toBeGreaterThanOrEqual(5);
    expect(wb.line.ownMoves()).toBe(0);
    // every move is the fake engine's best, every position before a move has its fact
    for (let k = 0; k < wb.line.n; k++) {
      expect(wb.line.moveAt(k)).toBe(bestDir(wb.line.boards[k]));
      expect(wb.line.facts[k]).toEqual({ best: bestDir(wb.line.boards[k]), grade: 'best' });
    }
  });

  it('plays exactly 10 moves when asked for 10', async () => {
    const wb = bench(7);
    wb.startAuto(10);
    await until(() => !wb.auto.on);
    expect(wb.line.n).toBe(10);
  });

  it('plays one move per analysis below full speed, and stops at the next tile', async () => {
    const wb = bench(2);
    wb.setSpeed(2);
    (wb.auto as { speed: number }).speed = 3; // full speed, but per move (an older server without batches)
    (wb as unknown as { batches: boolean }).batches = false;
    const target = wb.line.tops[0] + 1;
    wb.startAuto('tile');
    await until(() => !wb.auto.on);
    expect(calls.autoplay).toBe(0);
    expect(wb.line.tops[wb.line.n]).toBe(target);
    expect(wb.line.tops[wb.line.n - 1]).toBeLessThan(target);
  });

  it('follows the line from an earlier position while the coach agrees with it', async () => {
    const wb = bench(3);
    wb.startAuto(100);
    await until(() => !wb.auto.on);
    const moves = wb.line.rec.moves;
    wb.seek(40);
    wb.startAuto('stop');
    await until(() => wb.line.n > 130);
    wb.stopAuto();
    // the first 100 moves are the same line (followed, not replaced): nothing to restore
    expect(wb.line.rec.moves.slice(0, 100)).toBe(moves);
    expect(wb.replaced).toBeNull();
  });
});

describe('workbench lines', () => {
  it('replaces a continuation by a new move and restores it', async () => {
    const wb = bench(4);
    for (let i = 0; i < 60 && canMove(wb.line.board()); i++) wb.play(legalDirs(wb.line.board())[0], 'u');
    const before = wb.line.snapshot();
    wb.seek(20);
    const other = legalDirs(wb.line.board()).find((d) => d !== wb.line.moveAt(20))!;
    wb.play(other, 'u');
    expect(wb.line.n).toBe(21);
    expect(wb.replaced?.dropped).toBe(before.moves.length - 20);
    wb.restore();
    expect(wb.line.rec.moves).toBe(before.moves);
    expect(wb.line.cursor).toBe(20);
    expect(wb.replaced).toBeNull();
  });

  it('keeps a short replaced continuation without offering it back', () => {
    const wb = bench(5);
    for (let i = 0; i < 10; i++) wb.play(legalDirs(wb.line.board())[0], 'u');
    wb.seek(7);
    wb.play(legalDirs(wb.line.board()).find((d) => d !== wb.line.moveAt(7))!, 'u');
    expect(wb.replaced).toBeNull();
  });

  it('knows how much of a review still matches the line', async () => {
    const wb = bench(6);
    for (let i = 0; i < 50 && canMove(wb.line.board()); i++) wb.play(bestDir(wb.line.board()) as Dir, 'u');
    await wb.runReview();
    expect(wb.reviewCurrent()).toBe(true);
    expect(wb.reviewValidPlies()).toBe(50);
    expect(wb.line.facts[10]).toEqual({ best: bestDir(wb.line.boards[10]), grade: 'best' });
    wb.seek(30);
    expect(wb.reviewCurrent()).toBe(true); // moving the cursor changes nothing
    wb.play(legalDirs(wb.line.board()).find((d) => d !== wb.line.moveAt(30))!, 'u');
    expect(wb.reviewCurrent()).toBe(false);
    expect(wb.reviewValidPlies()).toBe(30);
    wb.newLine(newBoard(Sfc32.fromNumber(99)), 'new', 'new');
    expect(wb.reviewValidPlies()).toBe(0);
    expect(wb.replaced?.what).toBe('new');
  });
});

describe('workbench grades', () => {
  it('keeps the grade of each move played, from the live analyses', async () => {
    const wb = bench(8);
    await wb.analyze();
    const b = wb.line.board();
    const blunder = legalDirs(b).find((d) => d === 0 && bestDir(b) !== 0);
    const d = blunder ?? (legalDirs(b).find((x) => x !== bestDir(b)) as Dir);
    wb.play(d, 'u');
    expect(wb.line.facts[0]?.grade).toBe(d === 0 ? 'blunder' : 'good');
    expect(wb.line.facts[0]?.best).toBe(bestDir(b));
  });
});
