// Game reviews: `build/analyze --review FILE --json` in a short-lived process per review. The app knows every board and
// move exactly, so the file holds "BOARD MOVE" lines and the engine runs with --review-moves (no move inference: 0.7%
// of consecutive board pairs could be explained by two different moves) and --max-gap 1. Games that never leave the
// light networks' range (no 16384, tile sum below 20480) are reviewed with them: identical answers at ~150 MB and
// ~0.2 s start-up instead of ~775 MB and ~1 s.
import { spawn } from 'node:child_process';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createInterface } from 'node:readline';
import { type Board, type Dir, DIR_CHARS, DIR_NAMES, engineBoard, maxRank, tileSum } from '../../shared/rules.ts';
import { EngineBusy, EngineTimeout, EngineUnavailable, engineCommand } from './engine.ts';
import { log } from './log.ts';

export interface ReviewSpec {
  root: string;
  bin: string;
  preset: string;
  packed: string;
  packedLight: string;
  concurrency: number;
  maxWaiting: number;
  timeoutBaseMs: number;
  timeoutPerMoveMs: number;
}

/** Light networks answer identically for positions without a 16384 and with a tile sum below 20480 (docs/api.md). */
export function fitsLight(boards: Board[]): boolean {
  return boards.every((b) => maxRank(b) < 14 && tileSum(b) < 20480);
}

type Json = Record<string, unknown>;

/** One reviewed move, slimmed for the app (the client already has the boards). */
export function slimPly(a: Json): Json {
  const moves = (a.moves as Json[] | undefined) ?? [];
  const ref = moves.find((m) => m.loss === 0);
  const out: Json = {
    played: a.played ?? null,
    best: (ref?.move as string | undefined) ?? a.engine_move ?? null,
    engine: a.engine_move ?? null,
    ...(a.coach_move ? { coach_move: a.coach_move } : {}),
    ...(a.coach_why ? { coach_why: a.coach_why } : {}),
    source: a.source,
    summary: a.summary,
    plan: a.plan,
    plan_info: a.plan_info,
    moves: moves.map((m) => {
      const s: Json = { move: m.move, loss: m.loss, real_loss: m.real_loss, reasons: m.reasons };
      for (const k of ['real_loss_engine', 'grade', 'why', 'pick', 'fault_cells', 'warn', 'breaks_corner', 'p'] as const) if (k in m) s[k] = m[k];
      return s;
    }),
  };
  for (const k of ['odds', 'odds_caveat', 'formation', 'judged', 'table_p', 'game_over'] as const) if (k in a) out[k] = a[k];
  return out;
}

export class ReviewRunner {
  private running = 0;
  private waiting: (() => void)[] = [];
  reviews = 0;
  failures = 0;
  private spec: ReviewSpec;

  constructor(spec: ReviewSpec) {
    this.spec = spec;
  }

  status() {
    return { running: this.running, waiting: this.waiting.length, reviews: this.reviews, failures: this.failures };
  }

  async review(boards: Board[], moves: Dir[], skill?: number): Promise<Json> {
    if (this.running >= this.spec.concurrency && this.waiting.length >= this.spec.maxWaiting)
      throw new EngineBusy('too many reviews are waiting; try again in a moment');
    if (this.running >= this.spec.concurrency) await new Promise<void>((r) => this.waiting.push(r));
    this.running++;
    try {
      return await this.run(boards, moves, skill);
    } catch (e) {
      this.failures++;
      throw e;
    } finally {
      this.running--;
      this.waiting.shift()?.();
    }
  }

  private async run(boards: Board[], moves: Dir[], skill?: number): Promise<Json> {
    const t0 = Date.now();
    const dir = await mkdtemp(path.join(tmpdir(), 'tilecoach-review-'));
    const file = path.join(dir, 'game.txt');
    try {
      const lines = boards.map((b, i) => (i < moves.length ? `${engineBoard(b)} ${DIR_CHARS[moves[i]]}` : engineBoard(b)));
      await writeFile(file, lines.join('\n') + '\n');
      const light = this.spec.packedLight !== '' && fitsLight(boards);
      const packed = light ? this.spec.packedLight : this.spec.packed;
      const args = ['--preset', this.spec.preset, ...(packed ? ['--packed', packed] : []), '--review', file, '--json', '--max-gap', '1', '--review-moves'];
      if (skill !== undefined) args.push('--skill', skill.toFixed(3));
      const timeoutMs = this.spec.timeoutBaseMs + this.spec.timeoutPerMoveMs * moves.length;
      const out = await this.exec(args, timeoutMs);
      const summaryLine = out.pop();
      const summary = summaryLine ? (JSON.parse(summaryLine) as Json).review : undefined;
      if (!summary) throw new EngineUnavailable('the engine returned no review summary');
      const plies = out.map((l) => JSON.parse(l) as Json);
      if (plies.length !== moves.length) throw new EngineUnavailable(`the engine reviewed ${plies.length} of ${moves.length} moves`);
      plies.forEach((p, i) => {
        if (p.played !== DIR_NAMES[moves[i]]) throw new EngineUnavailable(`move ${i + 1} was read as ${String(p.played)}`);
      });
      const ms = Date.now() - t0;
      this.reviews++;
      log('review.done', { moves: moves.length, ms, networks: light ? 'light' : 'full' });
      return { summary, plies: plies.map(slimPly), engine: { networks: light ? 'light' : 'full', ms } };
    } finally {
      rm(dir, { recursive: true, force: true }).catch(() => {});
    }
  }

  private exec(args: string[], timeoutMs: number): Promise<string[]> {
    return new Promise((resolve, reject) => {
      const { cmd, args: a } = engineCommand({ bin: this.spec.bin, args });
      const proc = spawn(cmd, a, {
        cwd: this.spec.root,
        env: { ...process.env, MALLOC_ARENA_MAX: '2' },
        stdio: ['ignore', 'pipe', 'pipe'],
      });
      const lines: string[] = [];
      const errTail: string[] = [];
      let timedOut = false;
      const timer = setTimeout(() => {
        timedOut = true;
        proc.kill('SIGKILL');
      }, timeoutMs);
      createInterface({ input: proc.stdout! }).on('line', (l) => {
        if (l.startsWith('{')) lines.push(l);
      });
      createInterface({ input: proc.stderr! }).on('line', (l) => {
        errTail.push(l);
        if (errTail.length > 10) errTail.shift();
      });
      proc.on('error', (e) => {
        clearTimeout(timer);
        reject(new EngineUnavailable(`cannot start the engine: ${e.message}`));
      });
      proc.on('close', (code) => {
        clearTimeout(timer);
        if (timedOut) return reject(new EngineTimeout(`the review took longer than ${timeoutMs} ms`));
        if (code !== 0) {
          log('review.engine_failed', { code, stderr: errTail });
          return reject(new EngineUnavailable(`the engine stopped with code ${code}`));
        }
        resolve(lines);
      });
    });
  }
}
