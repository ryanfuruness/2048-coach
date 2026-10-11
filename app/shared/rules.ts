// 2048 rules, matching the engine exactly (src/board.h, src/game.h):
//   - a board is 16 cells, row-major, cell 0 = top-left; a cell holds a rank (0 = empty, r = the tile 2^r);
//   - a move slides every line towards the move's side and merges equal neighbours once per move, nearest to the
//     side first; merging two 2^r tiles scores 2^(r+1) points;
//   - a move is legal iff it changes the board;
//   - after a legal move one tile appears on a uniformly chosen empty cell: a 2 with p = 0.9, a 4 with p = 0.1;
//   - a game starts with two such tiles on an empty board.
// Ranks are unbounded here (like the engine's Game, not its 4-bit search board), so 65536 and beyond are exact.
// Directions use the engine's numbering: 0 up, 1 right, 2 down, 3 left.

export type Dir = 0 | 1 | 2 | 3;
export type Board = number[];

export const DIRS: readonly Dir[] = [0, 1, 2, 3];
export const DIR_NAMES = ['up', 'right', 'down', 'left'] as const;
export const DIR_CHARS = ['U', 'R', 'D', 'L'] as const;
export type DirName = (typeof DIR_NAMES)[number];

export function dirFromName(s: string): Dir | -1 {
  const t = s.trim().toLowerCase();
  for (const d of DIRS) if (DIR_NAMES[d] === t || DIR_CHARS[d].toLowerCase() === t) return d;
  return -1;
}

/** One tile's way during a move: the cell it left, the cell it ends on, and whether it merged there. */
export interface SlideStep {
  from: number;
  to: number;
  merged: boolean;
}

export interface MoveResult {
  board: Board;
  score: number;
  moved: boolean;
  steps: SlideStep[];
}

// cells of line k (0..3) in slide order: the first cell is the one tiles slide towards
function lineCells(dir: Dir, k: number): number[] {
  const cells: number[] = [];
  for (let j = 0; j < 4; j++) {
    let row: number, col: number;
    switch (dir) {
      case 0: row = j; col = k; break; // up
      case 2: row = 3 - j; col = k; break; // down
      case 3: row = k; col = j; break; // left
      default: row = k; col = 3 - j; break; // right
    }
    cells.push(row * 4 + col);
  }
  return cells;
}
const LINES: number[][][] = DIRS.map((d) => [0, 1, 2, 3].map((k) => lineCells(d, k)));

/** Applies a move. The input board is not modified. */
export function move(board: Board, dir: Dir): MoveResult {
  const out = board.slice();
  let score = 0;
  let moved = false;
  const steps: SlideStep[] = [];
  for (const cells of LINES[dir]) {
    const src: { v: number; cell: number }[] = [];
    for (const c of cells) if (board[c]) src.push({ v: board[c], cell: c });
    const vals = [0, 0, 0, 0];
    let m = 0;
    for (let i = 0; i < src.length; i++) {
      if (i + 1 < src.length && src[i].v === src[i + 1].v) {
        vals[m] = src[i].v + 1;
        score += 2 ** (src[i].v + 1);
        steps.push({ from: src[i].cell, to: cells[m], merged: true }, { from: src[i + 1].cell, to: cells[m], merged: true });
        i++;
      } else {
        vals[m] = src[i].v;
        steps.push({ from: src[i].cell, to: cells[m], merged: false });
      }
      m++;
    }
    for (let j = 0; j < 4; j++) {
      if (out[cells[j]] !== vals[j]) moved = true;
      out[cells[j]] = vals[j];
    }
  }
  return { board: out, score, moved, steps };
}

export function isLegal(board: Board, dir: Dir): boolean {
  return move(board, dir).moved;
}

export function legalDirs(board: Board): Dir[] {
  return DIRS.filter((d) => isLegal(board, d));
}

export function canMove(board: Board): boolean {
  for (const d of DIRS) if (isLegal(board, d)) return true;
  return false;
}

export function emptyCells(board: Board): number[] {
  const e: number[] = [];
  for (let i = 0; i < 16; i++) if (!board[i]) e.push(i);
  return e;
}

/** A source of uniform numbers in [0, 1). */
export interface Rng {
  next(): number;
}

export interface Spawn {
  cell: number;
  rank: 1 | 2;
}

/** Picks the new tile as the engine does: a uniformly chosen empty cell, then a 4 with p = 0.1, else a 2. */
export function pickSpawn(board: Board, rng: Rng): Spawn | null {
  const e = emptyCells(board);
  if (!e.length) return null;
  const cell = e[Math.min(e.length - 1, Math.floor(rng.next() * e.length))];
  const rank = rng.next() < 0.1 ? 2 : 1;
  return { cell, rank };
}

export function applySpawn(board: Board, s: Spawn): Board {
  if (board[s.cell]) throw new Error(`spawn on a full cell ${s.cell}`);
  const b = board.slice();
  b[s.cell] = s.rank;
  return b;
}

export function newBoard(rng: Rng): Board {
  let b: Board = new Array(16).fill(0);
  for (let k = 0; k < 2; k++) {
    const s = pickSpawn(b, rng);
    if (s) b = applySpawn(b, s);
  }
  return b;
}

/** If `next` is `after` plus exactly one new 2 or 4 on an empty cell, that spawn; else null. */
export function spawnBetween(after: Board, next: Board): Spawn | null {
  let found: Spawn | null = null;
  for (let i = 0; i < 16; i++) {
    if (after[i] === next[i]) continue;
    if (found || after[i] !== 0 || (next[i] !== 1 && next[i] !== 2)) return null;
    found = { cell: i, rank: next[i] as 1 | 2 };
  }
  return found;
}

/** The moves that lead from `before` to `next` with one spawn (usually one; two in rare ambiguous cases). */
export function movesBetween(before: Board, next: Board): Dir[] {
  const out: Dir[] = [];
  for (const d of DIRS) {
    const r = move(before, d);
    if (r.moved && spawnBetween(r.board, next)) out.push(d);
  }
  return out;
}

export function maxRank(board: Board): number {
  let m = 0;
  for (const v of board) if (v > m) m = v;
  return m;
}

export function tileSum(board: Board): number {
  let s = 0;
  for (const v of board) if (v) s += 2 ** v;
  return s;
}

export function tileValue(rank: number): number {
  return rank ? 2 ** rank : 0;
}

export function toValues(board: Board): number[] {
  return board.map(tileValue);
}

// ---- text encodings ----
// The compact board code: one base-36 character per cell (rank 0-35), cell 0 first. For boards whose tiles are at most
// 32768 it is exactly the engine's 16-digit hex encoding.
const B36 = '0123456789abcdefghijklmnopqrstuvwxyz';

export function boardCode(board: Board): string {
  let s = '';
  for (let i = 0; i < 16; i++) s += B36[board[i]];
  return s;
}

export function fromBoardCode(code: string): Board | null {
  if (!/^[0-9a-z]{16}$/i.test(code)) return null;
  return [...code.toLowerCase()].map((c) => B36.indexOf(c));
}

/** The engine's hex encoding (ranks up to 15), or null if a tile is bigger than 32768. */
export function boardHex(board: Board): string | null {
  return maxRank(board) <= 15 ? boardCode(board) : null;
}

/** The board as the engine reads it: 16 hex digits when possible, else 16 tile values. */
export function engineBoard(board: Board): string {
  return boardHex(board) ?? toValues(board).join(' ');
}

export const MAX_RANK = 30; // the engine accepts tiles up to 2^30

/**
 * Parses a board the way the engine does: 16 tile values with any separators ("2 4 0 0 / 8 ..."), 0 = empty, or one
 * 16-character token of hex rank digits. Returns null if the text is not a board.
 */
export function parseBoard(text: string): Board | null {
  const t = text.trim();
  if (/^[0-9a-f]{16}$/i.test(t)) return [...t.toLowerCase()].map((c) => parseInt(c, 16));
  const nums = t.match(/\d+/g);
  if (!nums || nums.length !== 16) return null;
  const b: Board = [];
  for (const s of nums) {
    if (s.length > 12) return null;
    const v = Number(s);
    if (v === 0) {
      b.push(0);
      continue;
    }
    const r = Math.log2(v);
    if (!Number.isInteger(r) || r < 1 || r > MAX_RANK) return null;
    b.push(r);
  }
  return b;
}

/** Validates a board given as 16 tile values, a 4x4 array of tile values, or a string; returns ranks or null. */
export function boardFromInput(input: unknown): Board | null {
  if (typeof input === 'string') return input.length <= 400 ? parseBoard(input) : null;
  if (!Array.isArray(input)) return null;
  const flat: unknown[] = input.length === 4 && input.every((r) => Array.isArray(r)) ? (input as unknown[][]).flat() : input;
  if (flat.length !== 16) return null;
  const b: Board = [];
  for (const v of flat) {
    if (typeof v !== 'number' || !Number.isInteger(v) || v < 0) return null;
    if (v === 0) {
      b.push(0);
      continue;
    }
    const r = Math.log2(v);
    if (!Number.isInteger(r) || r < 1 || r > MAX_RANK) return null;
    b.push(r);
  }
  return b;
}

/** Number of distinct tile values (the engine maps at most 15 onto its search board). */
export function distinctRanks(board: Board): number {
  return new Set(board.filter((v) => v > 0)).size;
}

// ---- random numbers ----
/** sfc32: a small, fast, well-tested 32-bit generator, seeded with four 32-bit words. */
export class Sfc32 implements Rng {
  private a: number;
  private b: number;
  private c: number;
  private d: number;
  constructor(seed: [number, number, number, number]) {
    [this.a, this.b, this.c, this.d] = seed.map((x) => x >>> 0) as [number, number, number, number];
    for (let i = 0; i < 12; i++) this.u32();
  }
  static fromNumber(n: number): Sfc32 {
    return new Sfc32([0x9e3779b9, n >>> 0, Math.floor(n / 2 ** 32) >>> 0, 0x85ebca6b ^ (n >>> 0)]);
  }
  u32(): number {
    const a = this.a | 0, b = this.b | 0, c = this.c | 0, d = this.d | 0;
    const t = (((a + b) | 0) + d) | 0;
    this.d = (d + 1) | 0;
    this.a = b ^ (b >>> 9);
    this.b = (c + (c << 3)) | 0;
    const cr = (c << 21) | (c >>> 11);
    this.c = (cr + t) | 0;
    return t >>> 0;
  }
  next(): number {
    return this.u32() / 4294967296;
  }
}

/** A generator seeded from the platform's cryptographic random source. */
export function cryptoRng(): Sfc32 {
  const s = new Uint32Array(4);
  globalThis.crypto.getRandomValues(s);
  return new Sfc32([s[0], s[1], s[2], s[3]]);
}
