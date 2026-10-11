// Games: the compact record kept in localStorage, its replay into boards, and the history index.
import {
  type Board,
  type Dir,
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
import { readJson, remove, writeJson, createStore } from './storage.ts';
import type { ReviewSummary } from './types.ts';

export interface CoachStats {
  warnings: number;
  warningsTaken: number;
  hints: number;
  hintsOpened: number;
}

export interface ReviewLite {
  good: number;
  accuracy: number;
  skill?: number;
  decisive_move?: number;
  key: number;
  blunders: number;
  mistakes: number;
  at: number;
}

export interface GameRecord {
  v: 1;
  id: string;
  startedAt: number;
  updatedAt: number;
  /** the first board (board code) */
  start: string;
  /** one character per move: U R D L */
  moves: string;
  /** one character per move: the new tile after it (base-32 digit: cell + 16 if it was a 4) */
  spawns: string;
  score: number;
  maxRank: number;
  over: boolean;
  origin: 'new' | 'position';
  coach: CoachStats;
  review?: ReviewLite;
}

export interface GameMeta {
  id: string;
  startedAt: number;
  updatedAt: number;
  score: number;
  maxRank: number;
  moves: number;
  over: boolean;
  origin: 'new' | 'position';
  final: string;
  review?: ReviewLite;
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

/** All boards of a game: boards[i] is the position before move i; the last one is the current position. */
export function replay(g: Pick<GameRecord, 'start' | 'moves' | 'spawns'>): Board[] {
  const first = fromBoardCode(g.start);
  if (!first) throw new Error('bad game record');
  const boards = [first];
  for (let i = 0; i < g.moves.length; i++) {
    const d = DIR_CHARS.indexOf(g.moves[i] as 'U') as Dir;
    const r = move(boards[i], d);
    if (!r.moved) throw new Error(`illegal move ${i}`);
    boards.push(applySpawn(r.board, decodeSpawn(g.spawns[i])));
  }
  return boards;
}

export function newRecord(start: Board, origin: 'new' | 'position'): GameRecord {
  const now = Date.now();
  return {
    v: 1,
    id: newId(),
    startedAt: now,
    updatedAt: now,
    start: boardCode(start),
    moves: '',
    spawns: '',
    score: 0,
    maxRank: maxRank(start),
    over: !canMove(start),
    origin,
    coach: { warnings: 0, warningsTaken: 0, hints: 0, hintsOpened: 0 },
  };
}

/** Plays a move on a record (mutating it) and returns the new board and the tile movements for the animation. */
export function playMove(g: GameRecord, board: Board, d: Dir, rng: Rng) {
  const r = move(board, d);
  if (!r.moved) return null;
  const spawn = pickSpawn(r.board, rng);
  const next = spawn ? applySpawn(r.board, spawn) : r.board;
  g.moves += DIR_CHARS[d];
  g.spawns += spawn ? encodeSpawn(spawn) : '0';
  g.score += r.score;
  g.maxRank = Math.max(g.maxRank, maxRank(next));
  g.over = !canMove(next);
  g.updatedAt = Date.now();
  return { board: next, result: r, spawn };
}

// ---- history (localStorage) ----
const MAX_GAMES = 200;

function metaOf(g: GameRecord, final: Board): GameMeta {
  return {
    id: g.id,
    startedAt: g.startedAt,
    updatedAt: g.updatedAt,
    score: g.score,
    maxRank: g.maxRank,
    moves: g.moves.length,
    over: g.over,
    origin: g.origin,
    final: boardCode(final),
    review: g.review,
  };
}

export const history = createStore<GameMeta[]>(readJson<GameMeta[]>('games', []));

function dropOldest(): boolean {
  const list = history.get();
  const current = readJson<string | null>('current', null);
  const victim = [...list].reverse().find((m) => m.id !== current);
  if (!victim) return false;
  remove(`g.${victim.id}`);
  history.set(list.filter((m) => m.id !== victim.id));
  writeJson('games', history.get());
  return true;
}

export function saveGame(g: GameRecord, final: Board): void {
  if (!g.moves.length && g.origin === 'new') return; // nothing worth keeping yet
  writeJson(`g.${g.id}`, g, dropOldest);
  const meta = metaOf(g, final);
  let list = history.get().filter((m) => m.id !== g.id);
  list = [meta, ...list].sort((a, b) => b.startedAt - a.startedAt);
  while (list.length > MAX_GAMES) {
    const old = list.pop()!;
    remove(`g.${old.id}`);
  }
  history.set(list);
  writeJson('games', list, dropOldest);
}

export function loadGame(id: string): GameRecord | null {
  const g = readJson<GameRecord | null>(`g.${id}`, null);
  return g && g.v === 1 ? g : null;
}

export function deleteGame(id: string): void {
  remove(`g.${id}`);
  const list = history.get().filter((m) => m.id !== id);
  history.set(list);
  writeJson('games', list);
  if (readJson<string | null>('current', null) === id) remove('current');
}

export function clearHistory(): void {
  for (const m of history.get()) remove(`g.${m.id}`);
  history.set([]);
  writeJson('games', []);
  remove('current');
}

export function setCurrentGame(id: string | null): void {
  if (id) writeJson('current', id);
  else remove('current');
}

export function currentGameId(): string | null {
  return readJson<string | null>('current', null);
}

export function attachReview(id: string, s: ReviewSummary): ReviewLite | null {
  const g = loadGame(id);
  if (!g) return null;
  g.review = {
    good: s.good,
    accuracy: s.accuracy,
    skill: s.skill,
    decisive_move: s.decisive_move,
    key: s.key_moments.length,
    blunders: s.blunders,
    mistakes: s.mistakes,
    at: Date.now(),
  };
  const boards = replay(g);
  saveGame(g, boards[boards.length - 1]);
  return g.review;
}

export function bestScore(): number {
  return Math.max(readJson<number>('best', 0), ...history.get().map((m) => m.score));
}

export function rememberBest(score: number): void {
  if (score > readJson<number>('best', 0)) writeJson('best', score);
}
