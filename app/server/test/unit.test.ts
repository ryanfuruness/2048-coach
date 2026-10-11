import assert from 'node:assert/strict';
import { test } from 'node:test';
import { Lru } from '../src/lru.ts';
import { RateLimiter } from '../src/ratelimit.ts';
import { BadRequest, engineLine, parseAnalyze, parseAutoplay, parseReview } from '../src/validate.ts';
import { fitsLight, slimPly } from '../src/review.ts';
import { Sfc32, boardCode, legalDirs, move, newBoard, pickSpawn, applySpawn, DIR_CHARS } from '../../shared/rules.ts';

test('analyze requests become engine lines', () => {
  const r = parseAnalyze({ board: [[2, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 65536]], skill: -0.5, hist: 'lldr', depth: 2, played: 'left' }, 5);
  assert.equal(engineLine(r), 'skill=-0.500 hist=LLDR depth=2 played=L | 2 0 0 0 0 0 0 0 0 0 0 0 0 0 0 65536');
  assert.equal(engineLine(parseAnalyze({ board: '2 4 0 0 0 0 0 0 0 0 0 0 0 0 0 0' }, 5)), ' | 1200000000000000');
  assert.equal(parseAnalyze({ board: '2 4 0 0 0 0 0 0 0 0 0 0 0 0 0 0', skill: 99 }, 5).skill, 3);
  assert.equal(parseAnalyze({ board: '2 4 0 0 0 0 0 0 0 0 0 0 0 0 0 0', hist: 'U'.repeat(30) }, 5).hist, 'U'.repeat(20));
});

test('bad analyze requests are rejected with a reason', () => {
  const ok = '2 4 0 0 0 0 0 0 0 0 0 0 0 0 0 0';
  for (const body of [null, [], 'x', { board: 'nope' }, { board: [3, ...Array(15).fill(0)] }, { board: ok, depth: 6 },
    { board: ok, depth: 1.5 }, { board: ok, skill: 'high' }, { board: ok, hist: 'UXD' }, { board: ok, played: 'north' },
    { board: ok, risk: 4 }, { board: ok, line: 51 }, { board: Array.from({ length: 16 }, (_, i) => 2 ** (i + 1)) }])
    assert.throws(() => parseAnalyze(body, 5), BadRequest, JSON.stringify(body));
  assert.throws(() => parseAnalyze({ board: Array(16).fill(2 ** 31) }, 5), BadRequest);
});

function game(seed: number, n: number) {
  const rng = Sfc32.fromNumber(seed);
  let b = newBoard(rng);
  const boards = [boardCode(b)];
  let moves = '';
  for (let i = 0; i < n; i++) {
    const legal = legalDirs(b);
    if (!legal.length) break;
    const d = legal[Math.floor(rng.next() * legal.length)];
    const a = move(b, d).board;
    b = applySpawn(a, pickSpawn(a, rng)!);
    boards.push(boardCode(b));
    moves += DIR_CHARS[d];
  }
  return { boards, moves };
}

test('review requests must be a real game', () => {
  const g = game(1, 40);
  const r = parseReview(g, 100);
  assert.equal(r.moves.length, 40);
  assert.equal(r.boards.length, 41);
  assert.throws(() => parseReview({ ...g, moves: g.moves.slice(1) }, 100), BadRequest);
  assert.throws(() => parseReview(g, 10), /at most 10/);
  const broken = { boards: [...g.boards], moves: g.moves };
  broken.boards[20] = broken.boards[19];
  assert.throws(() => parseReview(broken, 100), /does not lead/);
  assert.throws(() => parseReview({ boards: g.boards, moves: g.moves.replace(/./, 'X') }, 100), BadRequest);
  assert.throws(() => parseReview({ boards: 'x', moves: 'U' }, 100), BadRequest);
  // the player's skill: clamped to the human model's range, absent when not given
  assert.equal(parseReview({ ...g, skill: -0.25 }, 100).skill, -0.25);
  assert.equal(parseReview({ ...g, skill: 9 }, 100).skill, 3);
  assert.equal('skill' in r, false);
  assert.throws(() => parseReview({ ...g, skill: 'x' }, 100), BadRequest);
});

test('autoplay requests are checked', () => {
  const board = [0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0];
  const r = parseAutoplay({ board, n: 24, seed: 7, skill: -0.5, hist: 'lddr', stop_rank: 12 }, 64);
  assert.equal(r.n, 24);
  assert.equal(r.seed, 7);
  assert.equal(r.hist, 'LDDR');
  assert.equal(r.stopRank, 12);
  assert.throws(() => parseAutoplay({ board, n: 65, seed: 1 }, 64), BadRequest);
  assert.throws(() => parseAutoplay({ board, n: 0, seed: 1 }, 64), BadRequest);
  assert.throws(() => parseAutoplay({ board, n: 4 }, 64), BadRequest);
  assert.throws(() => parseAutoplay({ board, n: 4, seed: -1 }, 64), BadRequest);
  // a dead board has no moves to play
  assert.throws(() => parseAutoplay({ board: [2, 4, 2, 4, 4, 2, 4, 2, 2, 4, 2, 4, 4, 2, 4, 2], n: 4, seed: 1 }, 64), /no move/);
});

test('light networks only for games in their range', () => {
  const small = Array(16).fill(0);
  small[0] = 13; // 8192
  assert.equal(fitsLight([small]), true);
  const big = [...small];
  big[1] = 13;
  big[2] = 12; // sum 20480
  assert.equal(fitsLight([big]), false);
  const k16 = Array(16).fill(0);
  k16[0] = 14;
  assert.equal(fitsLight([k16]), false);
});

test('slimPly keeps what the review screen needs', () => {
  const p = slimPly({
    board: [[2]], hex: 'x', played: 'up', engine_move: 'down', source: 'search', summary: 's', plan: 'p', plan_info: { type: 'none' },
    odds: { 2048: 0.9 }, evals: 5, ms: 1,
    moves: [
      { move: 'up', loss: 10, real_loss: 0.02, warn: true, your_cost: 0.05, reasons: [{ code: 'risk', text: 't', share: 0.8 }], after: 'h', value: 1 },
      { move: 'down', loss: 0, real_loss: 0, warn: false, your_cost: 0, reasons: [], after: 'h', value: 2 },
    ],
  });
  assert.equal(p.best, 'down');
  assert.equal(p.played, 'up');
  assert.deepEqual(Object.keys((p.moves as object[])[0]).sort(), ['loss', 'move', 'real_loss', 'reasons', 'warn']);
  assert.equal('hex' in p, false);
  // the grades and the coach's move travel with the ply
  const q = slimPly({
    played: 'down', engine_move: 'down', coach_move: 'up', coach_why: 'keeps your 128 in its corner', source: 'search', summary: '', plan: '',
    moves: [
      { move: 'up', loss: 5, real_loss: 0, grade: 'best', pick: 0.7, hint_cells: [1, 2], reasons: [] },
      { move: 'down', loss: 0, real_loss: 0, grade: 'blunder', why: 'takes your 2048 out of its corner', pick: 0.01, fault_cells: [4, 0], reasons: [] },
    ],
  });
  assert.equal(q.coach_move, 'up');
  assert.equal(q.coach_why, 'keeps your 128 in its corner');
  const qm = q.moves as { grade: string; why?: string; fault_cells?: number[]; hint_cells?: number[] }[];
  assert.equal(qm[1].grade, 'blunder');
  assert.equal(qm[1].why, 'takes your 2048 out of its corner');
  assert.deepEqual(qm[1].fault_cells, [4, 0]);
  assert.equal('hint_cells' in qm[0], false); // a review needs the played move's verdict, not the hints
});

test('rate limiter refills over time', () => {
  let now = 0;
  const rl = new RateLimiter(2, 1000, 3, () => now);
  assert.equal(rl.take('a'), 0);
  assert.equal(rl.take('a'), 0);
  assert.equal(rl.take('a'), 0);
  assert.ok(rl.take('a') > 0);
  assert.equal(rl.take('b'), 0);
  now += 500;
  assert.equal(rl.take('a'), 0);
  assert.ok(rl.take('a') > 0);
  now += 120000;
  rl.take('c');
  assert.equal(rl.size, 1); // full buckets are forgotten
});

test('lru evicts the least recently used entry', () => {
  const c = new Lru<number>(2);
  c.set('a', 1);
  c.set('b', 2);
  c.get('a');
  c.set('c', 3);
  assert.equal(c.get('b'), undefined);
  assert.equal(c.get('a'), 1);
  assert.equal(c.size, 2);
});
