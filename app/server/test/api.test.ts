// End-to-end API test with the real engine (ENGINE_TESTS=1): starts the server on a free port.
import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import type { AddressInfo } from 'node:net';
import { existsSync } from 'node:fs';
import { createApp } from '../src/index.ts';
import { loadConfig } from '../src/config.ts';
import { Sfc32, boardCode, legalDirs, move, newBoard, pickSpawn, applySpawn, DIR_CHARS } from '../../shared/rules.ts';

const cfg = { ...loadConfig(), port: 0, logRequests: false };
const enabled = process.env.ENGINE_TESTS === '1' && existsSync(`${cfg.engineRoot}/${cfg.engineBin}`);
let app: ReturnType<typeof createApp>;
let base = '';

before(async () => {
  if (!enabled) return;
  app = createApp(cfg);
  app.pool.start();
  await new Promise<void>((r) => app.server.listen(0, '127.0.0.1', r));
  base = `http://127.0.0.1:${(app.server.address() as AddressInfo).port}`;
  for (let i = 0; i < 300 && !app.pool.ready; i++) await new Promise((r) => setTimeout(r, 100));
});
after(() => {
  if (!enabled) return;
  app.pool.stop();
  app.server.close();
});

const post = (path: string, body: unknown) =>
  fetch(base + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

test('analyze answers with the engine analysis and the player fields', { skip: !enabled }, async () => {
  const r = await post('/api/analyze', { board: [[2, 4, 16, 2], [8, 32, 64, 4], [16, 128, 512, 8], [4, 2, 256, 0]], skill: -0.5, hist: 'LDLD' });
  assert.equal(r.status, 200);
  const a = await r.json();
  assert.equal(a.engine_move, 'down');
  assert.equal(a.player_skill, -0.5);
  const right = a.moves.find((m: { move: string }) => m.move === 'right');
  assert.equal(right.warn, true);
  assert.ok(typeof right.find_prob === 'number');
});

test('health reports a ready engine', { skip: !enabled }, async () => {
  const h = await (await fetch(base + '/api/health')).json();
  assert.equal(h.ok, true);
  assert.equal(h.engine.workers[0].state, 'ready');
});

test('review of a game played with the client rules', { skip: !enabled }, async () => {
  const rng = Sfc32.fromNumber(11);
  let b = newBoard(rng);
  const boards = [boardCode(b)];
  let moves = '';
  for (let i = 0; i < 120; i++) {
    const legal = legalDirs(b);
    if (!legal.length) break;
    const d = legal.includes(2) ? 2 : legal.includes(3) ? 3 : legal[0];
    const a = move(b, d).board;
    b = applySpawn(a, pickSpawn(a, rng)!);
    boards.push(boardCode(b));
    moves += DIR_CHARS[d];
  }
  const r = await post('/api/review', { boards, moves });
  assert.equal(r.status, 200);
  const rev = await r.json();
  assert.equal(rev.summary.moves, moves.length);
  assert.equal(rev.plies.length, moves.length);
  assert.equal(rev.engine.networks, 'light');
  rev.plies.forEach((p: { played: string }, i: number) => assert.equal(p.played[0].toUpperCase(), moves[i]));
});

test('autoplay plays the analysis best moves with the requested tiles', { skip: !enabled }, async () => {
  const board = [0, 2, 4, 8, 0, 0, 16, 32, 0, 2, 64, 128, 2, 4, 256, 512];
  const r = await post('/api/autoplay', { board, n: 8, seed: 42, skill: -0.5, hist: 'LDLD' });
  assert.equal(r.status, 200);
  const out = await r.json();
  assert.equal(out.moves.length, 8);
  assert.equal(out.spawns.length, 8);
  assert.equal(out.facts.length, 8);
  // the first move is the coach's move of the position's own analysis (what the panel shows as best)
  const a = await (await post('/api/analyze', { board, skill: -0.5, hist: 'LDLD' })).json();
  const best = a.coach_move ?? a.moves.find((m: { loss: number }) => m.loss === 0)?.move ?? a.engine_move;
  assert.equal(out.moves[0], best[0].toUpperCase());
  assert.equal(out.facts[0].b, out.moves[0]);
  assert.equal(out.facts[0].t, 2048);
  // the facts carry the engine's chance of the milestone
  assert.equal(out.facts[0].p, a.odds['2048']);
  // the same request plays the same moves and tiles
  const again = await (await post('/api/autoplay', { board, n: 8, seed: 42, skill: -0.5, hist: 'LDLD' })).json();
  assert.equal(again.moves + again.spawns, out.moves + out.spawns);
});

test('bad requests get 4xx answers', { skip: !enabled }, async () => {
  assert.equal((await post('/api/analyze', { board: 'x' })).status, 400);
  assert.equal((await post('/api/review', { boards: [], moves: '' })).status, 400);
  assert.equal((await fetch(base + '/api/analyze')).status, 405);
});
