// The workbench controller: the line on the board, the analyses of its positions (requested once, cached, and kept as
// compact facts for the timeline), the coach's autoplay, and the review of the line. The screen subscribes to its
// events and renders; all game logic lives here.
import { type Board, type Dir, type DirName, type Rng, DIR_CHARS, DIR_NAMES, cryptoRng, dirFromName } from '@shared/rules.ts';
import { type AnalyzeOptions, type AutoplayBatch, ApiError, analyses, analyzeKey, requestAutoplay, requestReview } from './api.ts';
import { coachOf, costOf } from './chance.ts';
import { milestone } from './format.ts';
import { type Author, type Fact, Line, type LineRecord, type PlayResult, decodeSpawn, rememberBest, saveLineRecord } from './line.ts';
import { addSkillSample, player } from './skill.ts';
import type { Analysis, ReviewPly, ReviewResult } from './types.ts';

export const SPEEDS = [
  { label: '1/s', ms: 1000, title: 'One move a second' },
  { label: '3/s', ms: 333, title: 'Three moves a second' },
  { label: '10/s', ms: 100, title: 'Ten moves a second' },
  { label: 'Max', ms: 0, title: 'As fast as the engine answers' },
] as const;
export type Speed = 0 | 1 | 2 | 3;
export type Until = 'stop' | 'tile' | 'moves';
export const UNTIL_MOVES = 100;
/** The longest stretch one review covers (the server's limit); longer lines are reviewed from their last moves. */
export const REVIEW_MAX = 20000;
/** Reviews start by themselves at the end of a game up to this length (longer ones on request). */
const AUTO_REVIEW_MAX = 4000;
/** A replaced continuation is offered back when it held at least this many moves (shorter ones go quietly). */
export const RESTORE_MIN = 8;
/** Moves per request of fast autoplay (the server plays them; ~3 ms of engine time each). */
const BATCH = 24;

export interface AutoState {
  on: boolean;
  speed: Speed;
  until: Until;
  /** with until = 'tile': the rank to stop at (the next doubling of the largest tile when autoplay started) */
  targetRank: number;
  /** moves the coach played in this run */
  played: number;
  /** why the last run stopped, when worth saying */
  message?: string;
}

export interface ReviewData {
  lineId: string;
  /** the position the reviewed stretch starts from (0 unless the line is longer than REVIEW_MAX) */
  start: number;
  moves: string;
  data: ReviewResult;
}

export interface ReviewState {
  result?: ReviewData;
  running?: { lineId: string; start: number; moves: string; auto: boolean; startedAt: number };
  error?: string;
}

export interface Replaced {
  rec: LineRecord;
  what: 'branch' | 'new' | 'edit';
  /** moves the replaced line had beyond the point where it was left */
  dropped: number;
  at: number;
}

export type WbEvent =
  | { type: 'move'; res: PlayResult; by: Author; animate: boolean }
  | { type: 'seek' }
  | { type: 'line' }
  | { type: 'facts' }
  | { type: 'analysis' }
  | { type: 'auto' }
  | { type: 'review' }
  | { type: 'replaced' };

/** The coach's move of an analysis (what Space and autoplay play; see coachOf). */
export function bestOf(a: Analysis): DirName | null {
  return coachOf(a);
}

/**
 * The facts the timeline keeps of a position's analysis, with the cost of the move played from it (if any): your
 * chance and the share of it the move gave away where the analysis has them, else the engine's odds and real loss.
 */
export function factOf(a: Pick<Analysis, 'odds' | 'chance' | 'moves' | 'engine_move' | 'game_over' | 'coach_move' | 'judged'>, played: Dir | -1): Fact {
  const ms = milestone(a.odds);
  const name = coachOf(a);
  const best = name ? (dirFromName(name) as Dir) : -1;
  const you = !!a.chance;
  let loss: number | null | undefined;
  if (played !== -1) {
    if (a.judged === false) loss = null;
    else loss = costOf(a, DIR_NAMES[played])?.rel ?? (played === best ? 0 : null);
  }
  if (you) return { tile: a.chance!.target, p: a.chance!.now, best, loss, you };
  return { tile: ms?.tile ?? 0, p: ms ? ms.p : a.game_over ? 0 : null, best, loss };
}

export function factOfPly(p: ReviewPly): Fact {
  return factOf({ ...p, engine_move: p.engine, coach_move: p.coach_move ?? p.best ?? undefined }, dirFromName(p.played));
}

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
/** Yields to the page (input, drawing) without the 4 ms minimum of a nested setTimeout. */
function yieldTask(): Promise<void> {
  return new Promise((r) => {
    const ch = new MessageChannel();
    ch.port1.onmessage = () => r();
    ch.port2.postMessage(0);
  });
}

export class Workbench {
  line: Line;
  skill: number;
  /** prefetch the analysis of every new position (off when the analysis is not shown and the coach is idle) */
  wantAnalysis = true;
  auto: AutoState;
  review: ReviewState = {};
  replaced: Replaced | null = null;
  offline = false;
  /** the server plays batches of moves at full speed (false after an older server refused them) */
  private batches = true;
  private subs = new Set<(e: WbEvent) => void>();
  private saveTimer: ReturnType<typeof setTimeout> | null = null;
  private autoToken = 0;
  private reviewToken = 0;

  constructor(line: Line, skill: number, speed: Speed, until: Until) {
    this.line = line;
    this.skill = skill;
    this.auto = { on: false, speed, until, targetRank: 0, played: 0 };
  }

  subscribe(f: (e: WbEvent) => void): () => void {
    this.subs.add(f);
    return () => {
      this.subs.delete(f);
    };
  }
  private emit(e: WbEvent): void {
    for (const f of this.subs) f(e);
  }

  // ---- analyses ----
  opts(k = this.line.cursor, depth = 0): AnalyzeOptions {
    return { skill: this.skill, hist: this.line.hist(k), depth: depth || undefined };
  }
  key(k = this.line.cursor, depth = 0): string {
    return analyzeKey(this.line.board(k), this.opts(k, depth));
  }
  /** The analysis of position k if it is already here (never waits). */
  peek(k = this.line.cursor, depth = 0): Analysis | undefined {
    return analyses.peek(this.key(k, depth));
  }
  /** The analysis of position k (cached, shared with requests in flight); its facts are kept for the timeline. */
  analyze(k = this.line.cursor, depth = 0): Promise<Analysis> {
    const line = this.line;
    const key = this.key(k, depth);
    return analyses.get(line.board(k), this.opts(k, depth)).then(
      (a) => {
        if (this.offline) {
          this.offline = false;
          this.emit({ type: 'facts' });
        }
        if (this.line === line && k <= line.n && this.key(k, depth) === key) this.noteFact(k, a);
        this.emit({ type: 'analysis' });
        return a;
      },
      (e) => {
        if (e instanceof ApiError && (e.status === 0 || e.status >= 500) && !this.offline) {
          this.offline = true;
          this.emit({ type: 'facts' });
        }
        throw e;
      },
    );
  }
  private noteFact(k: number, a: Analysis): void {
    const old = this.line.facts[k];
    const f = factOf(a, this.line.moveAt(k));
    // keep a fact unless this one knows more: the played move's cost, or your chance where the old one had the engine's
    if (old && !(old.loss === undefined && f.loss !== undefined) && !(f.you && !old.you)) return;
    this.line.setFact(k, f);
    this.scheduleSave();
  }

  // ---- moves and the cursor ----
  /** Plays a move at the cursor (following the continuation if it is the next move there); null if illegal. */
  play(d: Dir, by: Author, animate = true): PlayResult | null {
    const line = this.line;
    const k = line.cursor;
    const a = this.peek(k);
    const res = line.play(d, by);
    if (!res) return null;
    if (a) this.noteFact(k, a);
    else if (this.wantAnalysis || this.auto.on) this.analyze(k).catch(() => {});
    if (res.replaced && res.dropped >= RESTORE_MIN) this.setReplaced(res.replaced, 'branch', res.dropped);
    rememberBest(line.score());
    this.scheduleSave(by === 'u' ? 0 : undefined);
    this.emit({ type: 'move', res, by, animate });
    const end = line.cursor === line.n;
    if (!line.over() && !this.auto.on && this.wantAnalysis) this.analyze().catch(() => {});
    if (end && line.over() && line.n <= AUTO_REVIEW_MAX) this.runReview(true);
    else if (by === 'u' && player.get().skill === null) {
      // a first reading of the player's level, 120 of their own moves into their first line (and every 200 after)
      const own = line.ownMoves();
      if (own >= 120 && (own - 120) % 200 === 0 && line.n <= AUTO_REVIEW_MAX) this.runReview(true);
    }
    return res;
  }

  /** One step along the continuation (animated like a move); false at the end of the line. */
  forward(): boolean {
    const res = this.line.forward();
    if (!res) return false;
    this.scheduleSave();
    this.emit({ type: 'move', res, by: this.line.author(res.from), animate: true });
    return true;
  }

  seek(k: number): boolean {
    if (!this.line.seek(k)) return false;
    this.scheduleSave();
    this.emit({ type: 'seek' });
    return true;
  }

  /** A new line from a board (a new game, or an edited position); the old line can be restored once. */
  newLine(board: Board, origin: 'new' | 'position', what: 'new' | 'edit', rng: Rng = cryptoRng()): void {
    this.stopAuto();
    const old = this.line;
    if (old.n > 0) this.setReplaced(old.snapshot(), what, old.n - old.cursor);
    this.line = Line.fresh(board, origin, rng);
    this.reviewToken++;
    this.review = {};
    this.scheduleSave(0);
    this.emit({ type: 'line' });
  }

  /** Brings back the line that the last new game, edit or new move replaced. */
  restore(): void {
    const r = this.replaced;
    if (!r) return;
    this.stopAuto();
    this.line = new Line(r.rec, this.line.rng);
    this.replaced = null;
    this.reviewToken++;
    this.review = {};
    this.scheduleSave(0);
    this.emit({ type: 'line' });
    this.emit({ type: 'replaced' });
  }

  dismissReplaced(): void {
    if (!this.replaced) return;
    this.replaced = null;
    this.emit({ type: 'replaced' });
  }

  private setReplaced(rec: LineRecord, what: Replaced['what'], dropped: number): void {
    this.replaced = { rec, what, dropped, at: Date.now() };
    this.emit({ type: 'replaced' });
  }

  // ---- autoplay: the coach plays its moves ----
  setSpeed(speed: Speed): void {
    this.auto = { ...this.auto, speed };
    this.emit({ type: 'auto' });
  }
  setUntil(until: Until): void {
    this.auto = { ...this.auto, until };
    this.emit({ type: 'auto' });
  }

  startAuto(): void {
    if (this.auto.on || this.line.over()) return;
    const token = ++this.autoToken;
    this.auto = { ...this.auto, on: true, played: 0, targetRank: this.line.tops[this.line.cursor] + 1, message: undefined };
    this.emit({ type: 'auto' });
    void this.autoLoop(token);
  }

  stopAuto(message?: string): void {
    if (!this.auto.on) return;
    this.autoToken++;
    this.auto = { ...this.auto, on: false, message };
    this.scheduleSave(0);
    if (this.wantAnalysis) this.analyze().catch(() => {});
    this.emit({ type: 'auto' });
  }

  private async autoLoop(token: number): Promise<void> {
    let lastAt = 0;
    let busyTries = 0;
    const live = () => this.auto.on && this.autoToken === token;
    while (live()) {
      const line = this.line;
      const k = line.cursor;
      if (line.over()) return this.stopAuto('The game is over.');
      if (this.auto.until === 'tile' && line.tops[k] >= this.auto.targetRank)
        return this.stopAuto(`The coach reached ${2 ** line.tops[k]}.`);
      if (this.auto.until === 'moves' && this.auto.played >= UNTIL_MOVES) return this.stopAuto(`The coach played ${UNTIL_MOVES} moves.`);
      // full speed at the end of the line: the server plays a batch of moves per request (one request per move would
      // spend more time on the request than on the engine)
      if (SPEEDS[this.auto.speed].ms === 0 && k === line.n && this.batches) {
        const n = Math.min(BATCH, this.auto.until === 'moves' ? UNTIL_MOVES - this.auto.played : BATCH);
        if (n >= 2) {
          let b: AutoplayBatch;
          try {
            b = await requestAutoplay(line.board(), {
              skill: this.skill,
              hist: line.hist(),
              n,
              seed: Math.floor(line.rng.next() * 2 ** 32),
              stopRank: this.auto.until === 'tile' ? this.auto.targetRank : undefined,
            });
            busyTries = 0;
          } catch (e) {
            if (!live()) return;
            if (e instanceof ApiError && (e.status === 404 || e.status === 405)) {
              this.batches = false; // an older server: one request per move
              continue;
            }
            if (e instanceof ApiError && (e.status === 429 || e.status === 503) && busyTries++ < 20) {
              await sleep(e.status === 429 ? 1000 : 2000);
              continue;
            }
            return this.stopAuto(e instanceof ApiError && e.status === 0 ? 'The coach is offline.' : `The coach stopped: ${(e as Error).message}`);
          }
          if (!live() || this.line !== line || line.cursor !== k) continue;
          for (let i = 0; i < b.moves.length; i++) {
            const d = DIR_CHARS.indexOf(b.moves[i] as 'U') as Dir;
            const f = b.facts[i];
            const res = line.play(d, 'c', decodeSpawn(b.spawns[i]));
            if (!res) return this.stopAuto('The coach stopped: a move from the server did not fit the board.');
            line.setFact(res.from, { tile: f.t, p: f.p, best: DIR_CHARS.indexOf(f.b as 'U') as Dir, loss: 0, ...(f.y ? { you: true } : {}) });
            this.auto.played++;
            this.emit({ type: 'move', res, by: 'c', animate: false });
          }
          rememberBest(line.score());
          this.scheduleSave();
          if (line.over() && line.n <= AUTO_REVIEW_MAX) void this.runReview(true);
          await yieldTask();
          continue;
        }
      }
      let a: Analysis;
      const cached = this.peek(k) !== undefined;
      try {
        a = await this.analyze(k);
        busyTries = 0;
      } catch (e) {
        if (!live()) return;
        // the server asks to slow down or is busy: wait and go on (a few times), else stop with the reason
        if (e instanceof ApiError && (e.status === 429 || e.status === 503) && busyTries++ < 20) {
          await sleep(e.status === 429 ? 1000 : 2000);
          continue;
        }
        return this.stopAuto(e instanceof ApiError && e.status === 0 ? 'The coach is offline.' : `The coach stopped: ${(e as Error).message}`);
      }
      if (!live() || this.line !== line || line.cursor !== k) continue;
      const best = bestOf(a);
      if (!best) return this.stopAuto('The game is over.');
      const ms = SPEEDS[this.auto.speed].ms;
      const wait = lastAt + ms - performance.now();
      if (wait > 0) await sleep(wait);
      else if (cached) await yieldTask(); // an answer from the cache came without a pause: let the page draw and take input
      if (!live() || this.line !== line || line.cursor !== k) continue;
      this.play(dirFromName(best) as Dir, 'c', ms >= 100);
      this.auto.played++;
      lastAt = performance.now();
    }
  }

  // ---- review ----
  /** How many of the review's plies still describe the current line (0 when it is of another line). */
  reviewValidPlies(): number {
    const r = this.review.result;
    if (!r || r.lineId !== this.line.id) return 0;
    const cur = this.line.rec.moves;
    let i = 0;
    while (i < r.moves.length && r.start + i < cur.length && cur[r.start + i] === r.moves[i]) i++;
    return i;
  }

  /** True when the review covers the line exactly as it is. */
  reviewCurrent(): boolean {
    const r = this.review.result;
    const n = this.line.n;
    return !!r && r.lineId === this.line.id && r.start === Math.max(0, n - REVIEW_MAX) && r.moves === this.line.rec.moves.slice(r.start);
  }

  async runReview(auto = false): Promise<void> {
    const line = this.line;
    const n = line.n;
    if (n === 0 || this.reviewCurrent()) return;
    const start = Math.max(0, n - REVIEW_MAX);
    const moves = line.rec.moves.slice(start);
    const run = this.review.running;
    if (run && run.lineId === line.id && run.start === start && run.moves === moves) return;
    const token = ++this.reviewToken;
    this.review = { result: this.review.result, running: { lineId: line.id, start, moves, auto, startedAt: Date.now() } };
    this.emit({ type: 'review' });
    try {
      const data = await requestReview(line.boards.slice(start, n + 1), moves, this.skill);
      if (token !== this.reviewToken) return;
      this.review = { result: { lineId: line.id, start, moves, data } };
      if (this.line === line) {
        const valid = this.reviewValidPlies();
        for (let i = 0; i < valid; i++) line.facts[start + i] = factOfPly(data.plies[i]);
        line.version++;
        this.scheduleSave();
      }
      // the player's level: only from lines the player played (nearly) alone
      const own = line.ownMoves(start, start + moves.length);
      if (data.summary.skill !== undefined && own >= 0.9 * moves.length) addSkillSample(line.id, data.summary.skill, data.summary.moves);
      this.emit({ type: 'review' });
    } catch (e) {
      if (token !== this.reviewToken) return;
      const msg =
        e instanceof ApiError && e.status === 429
          ? 'Too many reviews in a short time. Try again in a few seconds.'
          : e instanceof ApiError && e.status === 0
            ? 'The analysis server cannot be reached.'
            : (e as Error).message;
      this.review = { result: this.review.result, error: msg };
      this.emit({ type: 'review' });
    }
  }

  // ---- saving ----
  /** Saves the line now (delay 0) or soon (coalescing the saves of fast autoplay). */
  scheduleSave(delay = 1500): void {
    if (delay === 0) {
      if (this.saveTimer) clearTimeout(this.saveTimer);
      this.saveTimer = null;
      saveLineRecord(this.line.snapshot());
      return;
    }
    if (this.saveTimer) return;
    this.saveTimer = setTimeout(() => {
      this.saveTimer = null;
      saveLineRecord(this.line.snapshot());
    }, delay);
  }

  flush(): void {
    if (this.saveTimer) this.scheduleSave(0);
  }
}
