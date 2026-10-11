// The workbench line: one sequence of positions from a start board, with a cursor (the position on the board). The
// moves before the cursor led here; the moves after it are the line's continuation, which "forward" steps through.
// Playing the continuation's next move follows the line (with the same new tile); any other move replaces the
// continuation. Every move remembers who played it - the player ('u') or the coach ('c': autoplay, "play the coach's
// move", a taken warning suggestion) - so a review can judge the player's own moves only.
import {
  type Board,
  type Dir,
  type MoveResult,
  type Rng,
  type Spawn,
  DIR_CHARS,
  applySpawn,
  boardCode,
  canMove,
  fromBoardCode,
  maxRank,
  move,
  pickSpawn,
} from '@shared/rules.ts';
import { readJson, remove, writeJson } from './storage.ts';

export type Author = 'u' | 'c';

export interface CoachStats {
  warnings: number;
  warningsTaken: number;
  hints: number;
  hintsOpened: number;
}

export interface LineRecord {
  v: 2;
  id: string;
  startedAt: number;
  /** the first board (board code) */
  start: string;
  /** one character per move: U R D L */
  moves: string;
  /** one character per move: the new tile after it (base-32 digit: cell + 16 if it was a 4) */
  spawns: string;
  /** one character per move: who played it (u = the player, c = the coach) */
  by: string;
  origin: 'new' | 'position';
  cursor: number;
  coach: CoachStats;
  /** what the analyses said about each position, compactly (encodeFacts) */
  facts?: string;
}

/** What the analysis of a position said: the next milestone's chance, the best move, and the played move's cost. */
export interface Fact {
  /** the milestone tile its chance refers to (0: the engine gives no odds here) */
  tile: number;
  p: number | null;
  /** the coach's move */
  best: Dir | -1;
  /** cost of the move played from this position (a share): null = not judged, undefined = not known (yet) */
  loss?: number | null;
  /** p and loss are YOUR chance and the share of it the move gave away (else the engine's odds and real loss) */
  you?: boolean;
}

export interface PlayResult {
  kind: 'follow' | 'new';
  /** the position the move was played from */
  from: number;
  result: MoveResult;
  spawn: Spawn | null;
  /** the line as it was before this move replaced its continuation (null when nothing was replaced) */
  replaced: LineRecord | null;
  /** how many moves of the continuation were replaced */
  dropped: number;
}

const B32 = '0123456789abcdefghijklmnopqrstuv';
export const encodeSpawn = (s: Spawn) => B32[s.cell + (s.rank === 2 ? 16 : 0)];
export function decodeSpawn(c: string): Spawn {
  const k = B32.indexOf(c);
  return { cell: k & 15, rank: k >= 16 ? 2 : 1 };
}

export function newId(): string {
  const r = new Uint32Array(2);
  crypto.getRandomValues(r);
  return Date.now().toString(36) + r[0].toString(36).slice(0, 5);
}

/** The analysis window of the human move model: a position's request carries the 20 moves before it. */
export const HIST_LEN = 20;

export class Line {
  rec: LineRecord;
  /** boards[k]: position k (k moves played); boards[n] is the end of the line */
  boards: Board[] = [];
  /** score at position k: the points of the merges in the moves before it */
  scores: number[] = [];
  /** largest rank on the board at position k or before */
  tops: number[] = [];
  facts: (Fact | undefined)[] = [];
  rng: Rng;
  /** bumps on every change (moves, cursor, facts): a cheap key for memoized views */
  version = 0;

  constructor(rec: LineRecord, rng: Rng) {
    this.rec = rec;
    this.rng = rng;
    this.rebuild();
  }

  static fresh(start: Board, origin: 'new' | 'position', rng: Rng): Line {
    const now = Date.now();
    return new Line(
      {
        v: 2,
        id: newId(),
        startedAt: now,
        start: boardCode(start),
        moves: '',
        spawns: '',
        by: '',
        origin,
        cursor: 0,
        coach: { warnings: 0, warningsTaken: 0, hints: 0, hintsOpened: 0 },
      },
      rng,
    );
  }

  private rebuild(): void {
    const r = this.rec;
    const first = fromBoardCode(r.start);
    if (!first) throw new Error('bad line record');
    const boards = [first];
    const scores = [0];
    const tops = [maxRank(first)];
    for (let i = 0; i < r.moves.length; i++) {
      const d = DIR_CHARS.indexOf(r.moves[i] as 'U') as Dir;
      const m = move(boards[i], d);
      if (!m.moved) throw new Error(`illegal move ${i}`);
      const next = applySpawn(m.board, decodeSpawn(r.spawns[i]));
      boards.push(next);
      scores.push(scores[i] + m.score);
      tops.push(Math.max(tops[i], maxRank(next)));
    }
    this.boards = boards;
    this.scores = scores;
    this.tops = tops;
    if (r.by.length !== r.moves.length) r.by = (r.by + 'u'.repeat(r.moves.length)).slice(0, r.moves.length);
    r.cursor = Math.max(0, Math.min(r.moves.length, Number.isInteger(r.cursor) ? r.cursor : r.moves.length));
    this.facts = decodeFacts(r.facts ?? '', r.moves.length + 1);
    this.version++;
  }

  get id(): string {
    return this.rec.id;
  }
  get n(): number {
    return this.rec.moves.length;
  }
  get cursor(): number {
    return this.rec.cursor;
  }
  board(k = this.rec.cursor): Board {
    return this.boards[k];
  }
  score(k = this.rec.cursor): number {
    return this.scores[k];
  }
  over(k = this.rec.cursor): boolean {
    return !canMove(this.boards[k]);
  }
  /** the move played from position k (-1 at the end of the line) */
  moveAt(k: number): Dir | -1 {
    return k < this.n ? (DIR_CHARS.indexOf(this.rec.moves[k] as 'U') as Dir) : -1;
  }
  author(k: number): Author {
    return this.rec.by[k] === 'c' ? 'c' : 'u';
  }
  /** the moves before position k that an analysis request carries (the human move model's window) */
  hist(k = this.rec.cursor): string {
    return this.rec.moves.slice(Math.max(0, k - HIST_LEN), k);
  }
  /** number of moves the player (not the coach) made in positions [from, to) */
  ownMoves(from = 0, to = this.n): number {
    let c = 0;
    for (let i = from; i < to; i++) if (this.rec.by[i] !== 'c') c++;
    return c;
  }

  /** Moves the cursor (clamped); true when it changed. */
  seek(k: number): boolean {
    const c = Math.max(0, Math.min(this.n, Math.round(k)));
    if (c === this.rec.cursor) return false;
    this.rec.cursor = c;
    this.version++;
    return true;
  }

  /** One step along the continuation, as a move (for the slide animation); null at the end of the line. */
  forward(): PlayResult | null {
    const k = this.rec.cursor;
    if (k >= this.n) return null;
    const d = this.moveAt(k) as Dir;
    const result = move(this.boards[k], d);
    this.rec.cursor = k + 1;
    this.version++;
    return { kind: 'follow', from: k, result, spawn: decodeSpawn(this.rec.spawns[k]), replaced: null, dropped: 0 };
  }

  /**
   * Plays a move at the cursor: the continuation's own next move follows the line; any other legal move replaces the
   * continuation and gets a new random tile (or the given one, e.g. from the server's fast autoplay). Null for an
   * illegal move or a given tile that cannot appear there.
   */
  play(d: Dir, by: Author, given?: Spawn): PlayResult | null {
    const k = this.rec.cursor;
    const result = move(this.boards[k], d);
    if (!result.moved) return null;
    if (k < this.n && this.rec.moves[k] === DIR_CHARS[d]) {
      this.rec.cursor = k + 1;
      this.version++;
      return { kind: 'follow', from: k, result, spawn: decodeSpawn(this.rec.spawns[k]), replaced: null, dropped: 0 };
    }
    if (given && result.board[given.cell] !== 0) return null;
    let replaced: LineRecord | null = null;
    let dropped = 0;
    if (k < this.n) {
      replaced = this.snapshot();
      dropped = this.n - k;
      this.truncate(k);
    }
    const spawn = given ?? pickSpawn(result.board, this.rng);
    const next = spawn ? applySpawn(result.board, spawn) : result.board;
    this.rec.moves += DIR_CHARS[d];
    this.rec.spawns += spawn ? encodeSpawn(spawn) : '0';
    this.rec.by += by;
    this.boards.push(next);
    this.scores.push(this.scores[k] + result.score);
    this.tops.push(Math.max(this.tops[k], maxRank(next)));
    const f = this.facts[k];
    if (f) this.facts[k] = { ...f, loss: undefined }; // a different move from k: its cost is not known yet
    this.rec.cursor = k + 1;
    this.version++;
    return { kind: 'new', from: k, result, spawn, replaced, dropped };
  }

  private truncate(k: number): void {
    this.rec.moves = this.rec.moves.slice(0, k);
    this.rec.spawns = this.rec.spawns.slice(0, k);
    this.rec.by = this.rec.by.slice(0, k);
    this.boards.length = k + 1;
    this.scores.length = k + 1;
    this.tops.length = k + 1;
    if (this.facts.length > k + 1) this.facts.length = k + 1;
  }

  setFact(k: number, f: Fact): void {
    if (k < 0 || k > this.n) return;
    this.facts[k] = f;
    this.version++;
  }

  /** A full copy of the record (facts included), e.g. to restore this line later or to save it. */
  snapshot(): LineRecord {
    return { ...this.rec, coach: { ...this.rec.coach }, facts: encodeFacts(this.facts, this.n + 1) };
  }
}

// ---- compact facts: 8 characters per position ----
// tile rank (base 36, 0 = no odds), chance (3 base-36 digits, 'zzz' = none), best move (0-3, '-' for the engine's
// numbers; a-d, '_' for your chance), played move's cost (3 digits, 'zzz' = not judged, '...' = not known);
// '........' = no fact.
const B36 = '0123456789abcdefghijklmnopqrstuvwxyz';
const SCALE = 46654;
const NONE3 = 'zzz';
const UNKNOWN3 = '...';
const NOFACT = '........';

function enc3(x: number): string {
  const v = Math.max(0, Math.min(SCALE, Math.round(x * SCALE)));
  return B36[Math.floor(v / 1296)] + B36[Math.floor(v / 36) % 36] + B36[v % 36];
}
function dec3(s: string): number {
  return (B36.indexOf(s[0]) * 1296 + B36.indexOf(s[1]) * 36 + B36.indexOf(s[2])) / SCALE;
}

export function encodeFacts(facts: (Fact | undefined)[], len: number): string {
  let s = '';
  for (let k = 0; k < len; k++) {
    const f = facts[k];
    if (!f) {
      s += NOFACT;
      continue;
    }
    const rank = f.tile > 0 ? Math.round(Math.log2(f.tile)) : 0;
    s += B36[Math.max(0, Math.min(35, rank))];
    s += f.p === null || !Number.isFinite(f.p) ? NONE3 : enc3(f.p);
    s += f.you ? (f.best === -1 ? '_' : 'abcd'[f.best]) : f.best === -1 ? '-' : String(f.best);
    s += f.loss === undefined ? UNKNOWN3 : f.loss === null || !Number.isFinite(f.loss) ? NONE3 : enc3(f.loss);
  }
  return s;
}

export function decodeFacts(s: string, len: number): (Fact | undefined)[] {
  const out: (Fact | undefined)[] = [];
  for (let k = 0; k < len && (k + 1) * 8 <= s.length; k++) {
    const c = s.slice(k * 8, k * 8 + 8);
    if (c === NOFACT) {
      out.push(undefined);
      continue;
    }
    const rank = B36.indexOf(c[0]);
    const p = c.slice(1, 4);
    const l = c.slice(5, 8);
    out.push({
      tile: rank > 0 ? 2 ** rank : 0,
      p: p === NONE3 ? null : dec3(p),
      best: c[4] === '-' || c[4] === '_' ? -1 : 'abcd'.includes(c[4]) ? ('abcd'.indexOf(c[4]) as Dir) : (Number(c[4]) as Dir),
      loss: l === UNKNOWN3 ? undefined : l === NONE3 ? null : dec3(l),
      ...(c[4] === '_' || 'abcd'.includes(c[4]) ? { you: true } : {}),
    });
  }
  return out;
}

// ---- storage: the current line (localStorage) ----
interface V1Game {
  v: 1;
  id: string;
  startedAt: number;
  start: string;
  moves: string;
  spawns: string;
  origin: 'new' | 'position';
  coach: CoachStats;
  score: number;
}

/** The saved line, or the game of app v1 that was in progress (its history is no longer shown), or null. */
export function loadLineRecord(): LineRecord | null {
  const r = readJson<LineRecord | null>('line', null);
  if (r && r.v === 2 && typeof r.moves === 'string') return r;
  const id = readJson<string | null>('current', null);
  const g = id ? readJson<V1Game | null>(`g.${id}`, null) : null;
  if (g && g.v === 1 && typeof g.moves === 'string')
    return {
      v: 2,
      id: g.id,
      startedAt: g.startedAt,
      start: g.start,
      moves: g.moves,
      spawns: g.spawns,
      by: 'u'.repeat(g.moves.length),
      origin: g.origin,
      cursor: g.moves.length,
      coach: g.coach ?? { warnings: 0, warningsTaken: 0, hints: 0, hintsOpened: 0 },
    };
  return null;
}

/** When the storage is full: drop the games app v1 kept (oldest first). */
function dropV1Game(): boolean {
  const list = readJson<{ id: string }[]>('games', []);
  const victim = list.pop();
  if (!victim) return false;
  remove(`g.${victim.id}`);
  writeJson('games', list);
  return true;
}

export function saveLineRecord(rec: LineRecord): boolean {
  return writeJson('line', rec, dropV1Game);
}

/** The best score on this device (app v1's history counts too). */
export function bestScore(): number {
  const v1 = readJson<{ score: number }[]>('games', []).map((m) => m.score || 0);
  return Math.max(readJson<number>('best', 0), ...v1);
}

export function rememberBest(score: number): void {
  if (score > readJson<number>('best', 0)) writeJson('best', score);
}

/** The board a new game starts from: two random tiles. */
export function newGameBoard(rng: Rng): Board {
  let b: Board = new Array(16).fill(0);
  for (let k = 0; k < 2; k++) {
    const s = pickSpawn(b, rng);
    if (s) b = applySpawn(b, s);
  }
  return b;
}
