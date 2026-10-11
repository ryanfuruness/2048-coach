// Request validation: every input becomes either a clean engine request or a 400 with a plain message.
import {
  type Board,
  type Dir,
  DIR_CHARS,
  boardFromInput,
  canMove,
  distinctRanks,
  engineBoard,
  fromBoardCode,
  dirFromName,
  move,
  spawnBetween,
} from '../../shared/rules.ts';

export class BadRequest extends Error {}

function isObject(x: unknown): x is Record<string, unknown> {
  return typeof x === 'object' && x !== null && !Array.isArray(x);
}

function optInt(o: Record<string, unknown>, key: string, min: number, max: number): number | undefined {
  const v = o[key];
  if (v === undefined || v === null) return undefined;
  if (typeof v !== 'number' || !Number.isInteger(v) || v < min || v > max)
    throw new BadRequest(`${key} must be an integer from ${min} to ${max}`);
  return v;
}

export const SKILL_MIN = -3;
export const SKILL_MAX = 3;
export const HIST_LEN = 20; // the human move model's window (src/human.h History::kLen)

export interface AnalyzeRequest {
  board: Board;
  skill?: number;
  hist?: string;
  depth?: number;
  risk?: number;
  line?: number;
  played?: Dir;
}

/** Validates the body of POST /api/analyze. */
export function parseAnalyze(body: unknown, maxDepth: number): AnalyzeRequest {
  if (!isObject(body)) throw new BadRequest('expected a JSON object');
  const board = boardFromInput(body.board);
  if (!board) throw new BadRequest('board must be 16 tile values (0 = empty; powers of two from 2 to 2^30) or a board string');
  if (distinctRanks(board) > 15) throw new BadRequest('board has more than 15 different tile values');
  const req: AnalyzeRequest = { board };
  if (body.skill !== undefined && body.skill !== null) {
    if (typeof body.skill !== 'number' || !Number.isFinite(body.skill)) throw new BadRequest('skill must be a number');
    req.skill = Math.min(SKILL_MAX, Math.max(SKILL_MIN, body.skill));
  }
  if (body.hist !== undefined && body.hist !== null) {
    if (typeof body.hist !== 'string' || !/^[URDL]{0,200}$/i.test(body.hist))
      throw new BadRequest('hist must be a string of up to 200 moves (U, R, D, L)');
    req.hist = body.hist.toUpperCase().slice(-HIST_LEN);
  }
  req.depth = optInt(body, 'depth', 0, maxDepth);
  req.risk = optInt(body, 'risk', 0, 3);
  req.line = optInt(body, 'line', 0, 50);
  if (body.played !== undefined && body.played !== null) {
    const d = typeof body.played === 'string' ? dirFromName(body.played) : -1;
    if (d < 0) throw new BadRequest('played must be one of U, R, D, L (or up, right, down, left)');
    req.played = d as Dir;
  }
  return req;
}

/** The engine's --stdin line for a request (also the cache key: requests are independent and deterministic). */
export function engineLine(r: AnalyzeRequest): string {
  const opts: string[] = [];
  if (r.skill !== undefined) opts.push(`skill=${r.skill.toFixed(3)}`);
  if (r.hist) opts.push(`hist=${r.hist}`);
  if (r.depth) opts.push(`depth=${r.depth}`);
  if (r.risk) opts.push(`risk=${r.risk}`);
  if (r.line) opts.push(`line=${r.line}`);
  if (r.played !== undefined) opts.push(`played=${DIR_CHARS[r.played]}`);
  return `${opts.join(' ')} | ${engineBoard(r.board)}`;
}

export interface AutoplayRequest {
  board: Board;
  skill?: number;
  hist?: string;
  /** moves to play (at most `maxMoves`) */
  n: number;
  /** seed of the new tiles' random numbers */
  seed: number;
  /** stop once the largest tile reaches this rank */
  stopRank?: number;
}

/** Validates the body of POST /api/autoplay: {board, skill?, hist?, n, seed, stop_rank?}. */
export function parseAutoplay(body: unknown, maxMoves: number): AutoplayRequest {
  const a = parseAnalyze(body, 0);
  const o = body as Record<string, unknown>;
  const n = optInt(o, 'n', 1, maxMoves);
  if (n === undefined) throw new BadRequest(`n must be an integer from 1 to ${maxMoves}`);
  const seed = optInt(o, 'seed', 0, 2 ** 32 - 1);
  if (seed === undefined) throw new BadRequest('seed must be an integer from 0 to 4294967295');
  if (!canMove(a.board)) throw new BadRequest('no move is possible on this board');
  return { board: a.board, skill: a.skill, hist: a.hist, n, seed, stopRank: optInt(o, 'stop_rank', 2, 30) };
}

export interface ReviewRequest {
  boards: Board[];
  moves: Dir[];
  /** the player's skill (human move model scale): reviews measure moves against their own chance at that level */
  skill?: number;
}

/**
 * Validates the body of POST /api/review: {boards: [code, ...], moves: "URDL..."}, boards as 16-character board codes
 * (one base-36 rank per cell) or 16 tile values; boards[i + 1] must follow from boards[i] by moves[i] and one new tile.
 */
export function parseReview(body: unknown, maxMoves: number): ReviewRequest {
  if (!isObject(body)) throw new BadRequest('expected a JSON object');
  const { boards: rawBoards, moves: rawMoves, skill: rawSkill } = body;
  let skill: number | undefined;
  if (rawSkill !== undefined && rawSkill !== null) {
    if (typeof rawSkill !== 'number' || !Number.isFinite(rawSkill)) throw new BadRequest('skill must be a number');
    skill = Math.min(SKILL_MAX, Math.max(SKILL_MIN, rawSkill));
  }
  if (!Array.isArray(rawBoards)) throw new BadRequest('boards must be an array');
  if (typeof rawMoves !== 'string' || !/^[URDL]*$/i.test(rawMoves)) throw new BadRequest('moves must be a string of U, R, D, L');
  if (rawMoves.length < 1) throw new BadRequest('a review needs at least one move');
  if (rawMoves.length > maxMoves) throw new BadRequest(`a review can cover at most ${maxMoves} moves`);
  if (rawBoards.length !== rawMoves.length + 1) throw new BadRequest('boards must hold one board more than moves');
  const boards: Board[] = [];
  for (let i = 0; i < rawBoards.length; i++) {
    const x = rawBoards[i];
    const b = typeof x === 'string' && x.length === 16 ? fromBoardCode(x) : boardFromInput(x);
    if (!b || b.some((v) => v > 30)) throw new BadRequest(`board ${i} is not a board`);
    if (distinctRanks(b) > 15) throw new BadRequest(`board ${i} has more than 15 different tile values`);
    boards.push(b);
  }
  const moves = [...rawMoves.toUpperCase()].map((c) => DIR_CHARS.indexOf(c as 'U') as Dir);
  for (let i = 0; i < moves.length; i++) {
    const r = move(boards[i], moves[i]);
    if (!r.moved || !spawnBetween(r.board, boards[i + 1]))
      throw new BadRequest(`move ${i + 1} (${DIR_CHARS[moves[i]]}) does not lead from board ${i} to board ${i + 1}`);
  }
  return skill === undefined ? { boards, moves } : { boards, moves, skill };
}
