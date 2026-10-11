// The engine's answers as the app receives them (docs/api.md; reviews slimmed by app/server/src/review.ts).
import type { DirName } from '@shared/rules.ts';

export type { DirName };

export interface Reason {
  code: string;
  text: string;
  /** 0-1: the part of the move's loss that removing exactly this defect recovers (checked reasons only) */
  share?: number;
}

export interface MoveInfo {
  move: DirName;
  reward?: number;
  value?: number;
  loss: number | null;
  p?: number;
  odds?: Record<string, number>;
  real_loss?: number | null;
  real_loss_engine?: number;
  warn?: boolean;
  your_cost?: number | null;
  your_cost_abs?: number;
  find_prob?: number;
  breaks_corner?: boolean;
  /** your chance of the milestone after this move (a player of your level playing on) */
  chance?: number;
  /** the best move's chance minus this move's */
  chance_loss?: number;
  reasons: Reason[];
  after?: string;
}

/** Your chance: the milestone (2048, then each doubling) for a player of your level playing on from here. */
export interface ChanceInfo {
  target: number;
  /** from here, with the moves a player of your level makes */
  now: number;
  /** with the best move for you */
  best: number;
  /** the skill it was computed for (the in-between default -0.5 until a review measures you) */
  skill: number;
  key?: number;
}

export interface PlanInfo {
  type: string;
  step?: string;
  corner_cell?: number;
  chain?: number[];
  tiles?: number[];
  next_cell?: number;
  needs?: number;
  there?: number;
  merges_into?: number;
  biggest_cell?: number;
}

export interface Analysis {
  board: number[][];
  hex: string;
  stage: number;
  depth: number;
  engine_move: DirName | null;
  source: string;
  table_p?: number;
  formation?: 'block';
  judged?: false;
  game_over?: true;
  odds?: Record<string, number>;
  odds_caveat?: true;
  expected_future?: number;
  summary: string;
  plan: string;
  plan_info?: PlanInfo;
  moves: MoveInfo[];
  personal_odds?: Record<string, number | string>;
  /** your chance (up to a largest tile of 8192) */
  chance?: ChanceInfo;
  /** the coach's move: the corner strategy's move in the opening when it costs nothing, else the engine's */
  coach_move?: DirName;
  /** why the coach's move differs from the engine's ("keeps your 128 in its corner") */
  coach_why?: string;
  player_skill?: number;
  error_risk?: number;
  hint?: boolean;
  played?: DirName;
  evals?: number;
  ms?: number;
}

export interface KeyMoment {
  ply: number;
  board: string;
  played: DirName;
  engine: DirName | '-';
  real_loss: number;
  your_cost: number;
  why: string;
}

export interface ReviewPhase {
  phase: string;
  moves: number;
  mistakes: number;
  blunders: number;
  kept: number;
  skill_t?: number;
  skill?: number;
  skill_80?: [number, number];
}

export interface ReviewSummary {
  moves: number;
  match: number;
  good: number;
  accuracy: number;
  kept: number;
  lost_at?: number;
  decisive_move?: number;
  decisive_loss?: number;
  mean_real_loss: number;
  inaccuracies: number;
  mistakes: number;
  blunders: number;
  skill_t: number | null;
  mistakes_at_your_level: number;
  warnings: number;
  warnings_per_100: number;
  skill?: number;
  hints: number;
  hints_per_100: number;
  hard_moments: number;
  hard_found: number;
  hard_found_plies: number[];
  not_judged?: number;
  phases: ReviewPhase[];
  key_moments: KeyMoment[];
}

export interface ReviewMove {
  move: DirName;
  loss: number | null;
  real_loss: number | null;
  real_loss_engine?: number;
  your_cost?: number | null;
  chance?: number;
  chance_loss?: number;
  warn?: boolean;
  breaks_corner?: boolean;
  p?: number;
  reasons: Reason[];
}

export interface ReviewPly {
  played: DirName;
  best: DirName | null;
  engine: DirName | null;
  chance?: ChanceInfo;
  coach_move?: DirName;
  coach_why?: string;
  source: string;
  summary: string;
  plan: string;
  plan_info?: PlanInfo;
  moves: ReviewMove[];
  odds?: Record<string, number>;
  odds_caveat?: true;
  formation?: 'block';
  judged?: false;
  table_p?: number;
}

export interface ReviewResult {
  summary: ReviewSummary;
  plies: ReviewPly[];
  engine: { networks: string; ms: number };
}
