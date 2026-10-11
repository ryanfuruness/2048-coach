// A review's numbers for the player's own moves, by what each move cost the player: the share of their own chance of
// the next milestone it gave away (your chance, up to a largest tile of 8192), else the engine's real loss. Moves the
// coach played (autoplay, its suggested moves) are left out: they cost nothing and would flatter the numbers. The
// level (skill) is the engine's, measured only on lines the player played (nearly) alone.
import { type HumanCost, costClass, plyCost } from './chance.ts';
import type { DirName } from '@shared/rules.ts';
import type { ReviewPly, ReviewSummary } from './types.ts';
import type { ReviewData } from './workbench.ts';

export interface OwnMoment {
  /** position index in the line (the position the move was played from) */
  pos: number;
  played: DirName;
  /** the better move: the coach's move there */
  better: DirName | null;
  cost: HumanCost;
  /** the played move's main reason, if the engine checked one */
  why: string;
}

export interface OwnSummary {
  /** the player's judged moves in the reviewed stretch */
  own: number;
  /** moves the coach played in the stretch */
  coach: number;
  /** moves the review covers that are still in the line */
  covered: number;
  good: number;
  accuracy: number;
  inaccuracies: number;
  mistakes: number;
  blunders: number;
  /** the product of (1 - share lost) over the player's moves: how much of their chance they kept */
  kept: number;
  /** the costliest of the player's moves (a mistake or worse) */
  decisive?: OwnMoment;
  /** the player's costliest moves (mistakes and blunders, up to 5, costliest first) */
  keyMoments: OwnMoment[];
  /** the costs are the player's chance (else the engine's real loss: positions from 16384 on, older servers) */
  byChance: boolean;
  /** the engine's level estimate applies: the player made 90%+ of the moves */
  levelApplies: boolean;
  notJudged: number;
  summary: ReviewSummary;
}

export function playedLoss(p: ReviewPly): number | null {
  return plyCost(p)?.rel ?? null;
}

/** lichess's accuracy of one move from the share it lost (0-1), as the engine's review computes it on real loss */
export function moveAccuracy(rel: number): number {
  return 103.1668 * Math.exp(-0.04354 * 100 * rel) - 3.1669;
}

/** How a cost compares with another for ranking moments: points of chance first, else the share. */
function weight(c: HumanCost): number {
  return c.kind === 'chance' && c.abs !== null ? c.abs : c.rel * 0.5;
}

/** The review over the plies that still match the line (`covered` of them), counting the player's moves only. */
export function ownSummary(r: ReviewData, by: string, covered: number): OwnSummary {
  const s = r.data.summary;
  let own = 0;
  let coach = 0;
  let good = 0;
  let acc = 0;
  let inacc = 0;
  let mist = 0;
  let blun = 0;
  let notJudged = 0;
  let keptLog = 0;
  let byChance = 0;
  const moments: OwnMoment[] = [];
  for (let i = 0; i < covered; i++) {
    const ply = r.data.plies[i];
    const pos = r.start + i;
    if (by[pos] === 'c') {
      coach++;
      continue;
    }
    const c = plyCost(ply);
    if (c === null) {
      notJudged++;
      continue;
    }
    own++;
    if (c.kind === 'chance') byChance++;
    const cls = costClass(c);
    if (!cls) good++;
    acc += moveAccuracy(c.rel);
    if (cls === 'blunder') blun++;
    else if (cls === 'mistake') mist++;
    else if (cls === 'inaccuracy') inacc++;
    keptLog += Math.log(Math.max(1e-6, 1 - Math.min(c.rel, 0.999999)));
    if (cls === 'mistake' || cls === 'blunder') {
      const m = ply.moves.find((x) => x.move === ply.played);
      const reason = m?.reasons.find((x) => x.code !== 'later' && x.code !== 'shape') ?? m?.reasons[0];
      moments.push({ pos, played: ply.played, better: ply.coach_move ?? ply.best, cost: c, why: reason?.text ?? '' });
    }
  }
  moments.sort((a, b) => weight(b.cost) - weight(a.cost));
  return {
    own,
    coach,
    covered,
    good: own ? good / own : 0,
    accuracy: own ? Math.min(100, Math.max(0, acc / own)) : 0,
    inaccuracies: inacc,
    mistakes: mist,
    blunders: blun,
    kept: Math.exp(keptLog),
    decisive: moments[0],
    keyMoments: moments.slice(0, 5),
    byChance: own > 0 && byChance >= own / 2,
    levelApplies: coach <= 0.1 * (own + coach) && covered === r.data.plies.length,
    notJudged,
    summary: s,
  };
}
