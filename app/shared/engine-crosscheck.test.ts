// Cross-check of the client's rules against build/analyze on random boards: for every board, the set of legal moves,
// each move's board afterwards and its points must equal the engine's (moves[].after, moves[].reward). Needs the built
// engine; runs with ENGINE_TESTS=1 (npm run test:engine). Uses the light stage-0 networks (157 MB): move results do
// not depend on the networks.
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { type Board, DIR_NAMES, DIRS, Sfc32, boardCode, legalDirs, move, newBoard, pickSpawn, applySpawn } from './rules.ts';

const ROOT = fileURLToPath(new URL('../..', import.meta.url));
const BIN = `${ROOT}build/analyze`;
const LIGHT = `${ROOT}weights/serve/v6c_s0only_i16.wp`;
const enabled = process.env.ENGINE_TESTS === '1' && existsSync(BIN) && existsSync(LIGHT);

function randomBoard(rng: Sfc32, maxRank: number, fill: number): Board {
  const b: Board = [];
  for (let i = 0; i < 16; i++) b.push(rng.next() < fill ? 1 + Math.floor(rng.next() * maxRank) : 0);
  return b;
}

// boards from real-looking play too (random legal moves from a fresh game), not only uniform noise
function playedBoards(rng: Sfc32, n: number): Board[] {
  const out: Board[] = [];
  let b = newBoard(rng);
  while (out.length < n) {
    const legal = legalDirs(b);
    if (!legal.length) {
      b = newBoard(rng);
      continue;
    }
    b = move(b, legal[Math.floor(rng.next() * legal.length)]).board;
    b = applySpawn(b, pickSpawn(b, rng)!);
    out.push(b);
  }
  return out;
}

describe.skipIf(!enabled)('rules vs build/analyze', () => {
  it('agree on legal moves, afterstates and points for 3000 boards', async () => {
    const rng = Sfc32.fromNumber(2048);
    const boards: Board[] = [];
    for (let i = 0; i < 1500; i++) boards.push(randomBoard(rng, 1 + (i % 14), 0.35 + 0.6 * rng.next()));
    boards.push(...playedBoards(rng, 1500));
    // boards whose tiles exceed 32768 are stored lowered by the engine's search board; 32768 + 32768 merges are capped
    // there (src/board.h), so keep ranks below 15 for an exact afterstate comparison
    const usable = boards.filter((b) => Math.max(...b) <= 14);

    const proc = spawn(BIN, ['--preset', 'best-notables', '--packed', LIGHT, '--stdin'], {
      cwd: ROOT,
      stdio: ['pipe', 'pipe', 'ignore'],
    });
    const rl = createInterface({ input: proc.stdout! });
    const lines: string[] = [];
    const done = new Promise<void>((resolve) => {
      rl.on('line', (l) => {
        lines.push(l);
        if (lines.length === usable.length) resolve();
      });
    });
    proc.stdin!.write(usable.map((b) => boardCode(b)).join('\n') + '\n');
    proc.stdin!.end();
    await done;
    proc.kill();

    let compared = 0;
    for (let i = 0; i < usable.length; i++) {
      const b = usable[i];
      const a = JSON.parse(lines[i]);
      const engineMoves = new Map<string, { after: string; reward: number }>();
      for (const m of a.moves ?? []) engineMoves.set(m.move, { after: m.after, reward: m.reward });
      const ours = new Set(legalDirs(b).map((d) => DIR_NAMES[d]));
      expect([...engineMoves.keys()].sort(), `legal moves of ${boardCode(b)}`).toEqual([...ours].sort());
      for (const d of DIRS) {
        const e = engineMoves.get(DIR_NAMES[d]);
        if (!e) continue;
        const r = move(b, d);
        expect(boardCode(r.board), `afterstate of ${boardCode(b)} ${DIR_NAMES[d]}`).toBe(e.after);
        expect(r.score, `points of ${boardCode(b)} ${DIR_NAMES[d]}`).toBe(e.reward);
        compared++;
      }
      expect(Boolean(a.game_over), `game over of ${boardCode(b)}`).toBe(ours.size === 0);
    }
    expect(compared).toBeGreaterThan(5000);
  });
});
