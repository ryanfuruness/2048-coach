# Reading the analysis (v0.3, 2026-10-10)

What the numbers mean, and what the research behind them found (details and data: NOTES.md, the 2026-10-06/07
entries, and results/<workstream>/REPORT.md).

## Move grades (app v3)

Every move gets one of four grades (results/grades/REPORT.md):

- **Best**: the coach's move, or one it cannot tell apart from it.
- **Good**: fine, but the coach would play something else.
- **Questionable**: the coach would never play it.
- **Blunder**: an obvious mistake with a name: the biggest tile out of its corner, the biggest tiles pulled off the
  edge, a move that can end the game, or a big loss.

Blunders are read from the board, not from the engine's value, which barely moves when the engine could repair the
damage. Up to a largest tile of 256 the corner and the edge are free. "Would never play it" starts at 5% value loss,
where a deeper search almost never prefers the move. Checked in real situations:

- moving the biggest tile out of its corner from 512 on: a blunder 98-100% of the time;
- random keys from 512 on: 41-47% flagged, the first after 2-3 moves;
- strong players' own moves: 0.23% blunders.

## Your chance (v0.3, workstream yc; research - the app no longer uses it)

*"Your chance of reaching 2048 if you play on: 62%."*

**Your chance** is the share of games in which a player of your skill reaches the next milestone (2048, then each
doubling of the largest tile) from this position, playing on themselves. It is not the engine's chance.

- **How it is measured.** It comes from the simulated human players of the personal odds: the human move model plus
  care in danger, outcome-matched to real players. That chance is learned into small n-tuple networks per skill key and
  recalibrated on the simulated games (src/hvalue.h, weights/calib/chance.hv).
- **Why not the engine's odds.** The engine repairs almost anything early on. Its odds stay near 100% and its losses
  near 0 for moves that cost a person a lot: with a 2048 or a 4096, moving it out of its corner costs a simulated
  player about a fifth of their chance of the next tile, while the engine calls it free. Results:
  results/yc/REPORT.md.
- **Accuracy.**
  - Against rollouts from 210 real positions: within 0.01-0.03 on average.
  - Each move's chance, relative to the others in its position: correlation 0.86 with the rollouts.
  - On real games, the cost of a played move predicts the player's actual outcome beyond the position (coefficient
    -1.2, about what a calibrated cost gives).
  - It is pessimistic for strong players, as the personal odds were.
- **What it covers.** It applies up to a largest tile of 8192. It uses the player's skill (the app's default -0.5 until
  a review measures it, never lower: novice-level simulated players never reach 2048).
- **Cost of a move.** The best move's chance minus this move's, in points. A move is costly (warned about) at 20% of
  your chance and at least 2 points. In the app: inaccuracy 5% / 2 points, mistake 10% / 2 points, blunder 25% / 4
  points.
- **The very early game.** Even 76 random moves from the start do not lower a simulated player's chance of 2048 (600
  rollouts per move): small tiles are easily cleaned up. The corner starts to matter from 256 (about 2-3 points) and
  is worth 17-20 points with a 2048.
- **The coach's move** (`coach_move`).
  - Up to 512: the corner strategy's move, i.e. the human move model at a strong skill with the player's recent moves:
    biggest tile in its corner, the edge line, three directions.
  - It is chosen among moves that cost nothing (real loss at most 0.5%, at most 1 point of your chance). The engine's
    own early moves do not care where the biggest tile is.
  - From 1024 on it is the engine's move, which keeps the corner itself there.

## The verdict and the odds

*"With best play from here, the 16384 tile comes 82% of the time (in trouble compared with a typical position at this
stage)."*

- **Engine odds** are the chances of reaching each bigger tile if the engine played on from this position: the
  engine's own success rates at this stage of the game (1000 benchmark games), adjusted by the position's value
  (fitted on real human positions played out by the engine), times the chance that the next random tile does not end
  the game. Checked on 200 fresh real positions that no fit saw: the 16384 odds are off by 6.6 points on average
  (the previous model: 10 points). Tight mid-game positions (largest tile 4096-8192, value well below typical): the
  model says 79%, playouts measured 77% (the previous model said 94%).
- **Unusual positions** (workstream anypos: 804 odd-but-legal boards - biggest tile in the middle, two corners used,
  scattered big tiles, checkerboards - played out 64 times each): up to a 2048 every shape is fine (the engine
  repairs it), but from 4096 on odd formations are over-predicted (at 8192 the error is 0.29 vs 0.04 for sane
  shapes; e.g. a "center" board said 86% where 38% was measured). A formation correction helps a little; the main
  safeguard is `odds_caveat` with the summary's "Odds are less certain here: this formation is unusual for the
  stage." (it fires on 86% of odd boards from 4096, 12% of sane ones, 18% of real positions).
- Why they rarely move: the engine repairs most damage a human does. Odds drop sharply only in real danger (few free
  cells, no merges: the near-dead board above, 82% predicted vs 85% measured) or after heavy late-game damage.
- **Personal odds** (`--personal T`, T = the skill from a review, or `--skill THETA`) are the same question for a
  human-like player of that skill: much lower, and the more useful number for most players. The simulated player is
  a **human move model** fitted on 115,000 real decisions of 80 players (src/human.h): besides the engine's values it
  knows what humans actually weigh (keeping the corner, the edge line, big tiles off the edge, the danger of the next
  tile, habits such as never pressing one direction) and predicts held-out players' moves far better than a plain
  softmax over values (0.76 vs 1.01 nats per move). Real players also take more care than their single moves show
  when the board is nearly full (simulated players reached 2 or fewer empty cells 1.5-4x as often and escaped far
  less often), so from intermediate level up the simulated player plays a careful corner-keeping move on such boards.
  On real games with a known outcome (82 games): next doubling log-loss 0.33 (softmax-based model 0.50), AUC 0.88;
  two doublings 0.47 (0.96). Next doubling predicted vs observed: intermediate 0.87 vs 0.96, strong 0.66 vs 0.83 -
  still somewhat pessimistic, partly because the videos are selected for success - novices 0.61 vs 0.59.

## Moves and losses

- **value / loss**: the engine's estimate of the points still to come after each move, and the gap to the best move.
  Differences are what matter; the scale is the network's.
- **real loss**: what a move really costs, as a share of the expected future score with good play afterwards.
  Measured with rollouts (the engine playing each move out 1000 moves ahead, 32 times) on 2,200 real positions of 80
  players. The engine repairs moderate damage, early positions more than late ones:

  | value loss | up to 1024 | 2048-8192 | 16384+ |
  |---|---|---|---|
  | 6% | ~0% | 0.6% | 3% |
  | 14% | 0.4% | 1.8% | 8% |
  | 27-30% | 5% | 7% | 26% |
  | 57-70% | 58% | 54% | 79% |

  Where an exact endgame table decides the position, the table's success chances are used instead (a move that
  lowers the chance of building the next tile from 100% to 85% costs ~10%; failing the table's sub-goal is partly
  repaired). In positions with a 16384 or bigger, a player's own move is judged by what it costs *the player*: small
  claims (below ~10% value loss) cost nothing measurable, larger ones much less than the engine says (20% -> ~2%,
  45% -> ~12%). The reason (workstream cal7, 2026-10-07): with 128 playouts per move from 200 real expert decisions,
  a claimed loss is real when the engine plays on (6-10% claims cost 6.7%, 10-20% cost 11.4%), but such losses do not
  add up over an expert's game - the engine undervalues the expert's position and then plays it worse than the
  expert would. Judged this way, experts' stretches that reached 32768 keep ~66% of their chances (the engine-based
  map said 1%). Reviews also give `real_loss_engine`: the same move's cost if the engine took over from there.
- **your cost** (`your_cost`): what the move costs a human-like player: the share of *your own* chances of reaching
  the next tile (the next doubling of your largest tile) that the move gives away, measured with simulated players of
  every skill playing on (the coach study: they repair less than the engine; the share barely depends on skill):

  | value loss | up to 512 | 1024-2048 | 4096-8192 |
  |---|---|---|---|
  | 12% | 3.5% | 5.4% | 7.8% |
  | 24% | 9% | 10% | 14% |
  | 36% | 17% | 21% | 29% |
  | 53% | 35% | 52% | 53% |

  With personal odds, `your_cost_abs` is the same in absolute terms (the drop in your probability of the next tile).
  When your skill is known (`--skill`, or `--personal T`), the cost comes from a map for your skill band, fitted on
  real games measured with 256 playouts per move (workstream cal8): for novice-level players a move costs about three
  times the table above (10-15% value loss: ~15% of your chances), for everyone else small losses cost ~nothing.
  Without a skill (single positions, reviews without `--skill`) the table above is used.
  From 16384 on (no simulated players get there) it equals the real loss.
- **warn**: whether an app should warn before this move is committed (with the engine's move offered instead). The
  coach study found that a warning just before a bad move helps far more per intervention than hints shown in advance:
  from real bad positions, simulated novices reached the next tile 52% of the time alone, 83% with ~2 warnings per 100
  moves, 92% with the engine playing. Thresholds (relative value loss, the model's `warn` line): 15% with a largest
  tile up to 512, 5% from 1024 to 8192 (damage there comes from many small errors), 20% from 16384 (strong players
  repair small late-game losses the engine would not). Real players would see 0-0.4 warnings
  per 100 moves (median intermediate and strong players), novices ~3.
- **Classes**: inaccuracy = real loss 1-3%, mistake 3-10%, blunder >= 10%.
- **breaks the corner**: the engine never moves its biggest tile out of the corner once it is 16384 or more; such a move
  may still show a high raw value, which the engine does not trust (loss "n/a").

## The block formation (strong players' 3x2 block)

Some strong players keep their biggest tiles in a 3x2 block in a corner instead of a snake along an edge (one expert
in our data plays it throughout the 32768 phase; 105 of the 150 expert moves the engine had called big mistakes were
theirs, and rollouts refuted almost all: claimed 21% loss, real -1%). The engine plays snakes, and its values say
nothing about moves in block positions. So, from a real 16384 on, when the block detector fires (`"formation":
"block"`; 97 of that expert's 105 disputed positions, 2 of 185 snake experts' positions, ~1% of the engine's own late
positions):

- if the **exact block tables** (`weights/pdf/`, 53 GB, built by our own solver) decide the position, moves are judged
  by the tables' success chances (`source: block`, reasons such as "leaves a 33% chance to build the tile your block
  needs next (exact table; 100% after left)");
- otherwise the engine **does not judge** (`"judged": false`): no losses, warnings or verdicts, the engine's move is
  shown as a suggestion only, and reviews count these moves as "not judged". With the tables, 187 of 201 moves of a
  32768-phase block segment are judged (the player: 98.9% best or good moves).

## Reasons

Reasons are concepts that were checked against 14,000 human position/move pairs (losing chain length, opening cells
next to big tiles, big tiles in the middle, the biggest tile leaving or staying away from a corner, missing a big
merge, the risk of the next tile: "lets the next tile end the game in 90% of cases"; free cells and the number of
merges did *not* predict losses). Since 2026-10-07 every reason of a clearly worse move is also **checked in the
position itself** (workstream expl): the move's afterstate is edited to remove exactly the stated defect (e.g. the
biggest tile put back into its corner) and re-evaluated; the share of the loss this recovers is the reason's `share`.
Reasons that recover under 10% are dropped and the rest are ordered by it, so the first reason is the main cause: on
646 real worse moves it now explains at least half of the loss in 68% of cases (before: 45%) and is the biggest cause
in 93% (before: 43%); played out by the engine, the first reason's median share is 0.82 (before: 0.70). "Small tile
trapped between big ones" was no better than a random edit and is no longer given. When no concept applies, the
reason points to where the engine's evaluation drops (per-cell attribution: "weakens the bottom-left area around
your 256 and 32") or says plainly that it is the engine's look-ahead. For a language layer later: say "mainly
because" for share >= 0.5, "partly because" for 0.1-0.5; reasons without a share (small losses, the non-played
moves in reviews), "later" and "shape" are hints, not causes.

## At your level: what a player like you would play

With a skill (`--skill THETA`, the `skill` of a game review; or `--personal T`, converted) the analysis adds what a
player of that skill is likely to do here. It uses the **human move model** (src/human.h): fitted on 115,000 real
decisions of 80 players, it predicts held-out players' moves far better than a softmax over the engine's values
(0.76 vs 1.01 nats per move), because it knows what people actually weigh - the corner, the edge line, big tiles off
the edge, the danger of the next tile, habits such as never pressing one direction. From a tile sum of 20480 on it
reads the engine's search losses instead of one-move values (experts look deeper; refit on the current networks:
held-out players' log-loss there 0.80 -> 0.77 nats per move).

- **find_prob** (per move): how likely a player of that skill is to play the move (with the player's recent moves in a
  review).
- **error risk** (per position): the share of your own chances of the next tile that the move you are likely to make
  costs on average (`find_prob` x `your_cost`, summed over the moves). Most positions are ~0; it rises where the
  natural-looking moves are bad.
- **hint**: an app would show the engine's move *before* you move, because you are likely to go wrong here. It does
  not need to know the move you intend (a warning does). Thresholds: error risk 5% with a largest tile up to 512, 8%
  from 1024 to 8192, no hints from 16384 (the human model is weakest there). Measured in the coach test with
  human-model players from real positions: early, a 5% hint closes 63-90% of the gap to the engine at 1.3-3 hints per
  100 moves (0.06-0.12 more chance of the next tile per hint; warnings: 0.10-0.16 per warning); at 1024-2048, an 8%
  hint closes 23-47% at 0.8-2.8 per 100 moves (0.04-0.09 per hint; warnings 0.07-0.10); at 4096-8192 hints help little
  (12-20% of the gap) - many small errors decide there, and warnings do better. Real players would see hints rarely:
  novices ~2.7 per 100 moves, the median intermediate or strong player ~0 (a few up to ~10).
- **skill** (reviews): the skill under which the human move model makes your moves most likely (higher = stronger;
  medians: novices -0.8, intermediate and strong players about -0.2 to 0). It is far more stable than the softmax
  `skill_t`: the first and second half of a player's moves give nearly the same skill (correlation 0.75-0.87 by
  phase, vs -0.05 to 0.60 for `skill_t`). For personal odds it is converted to the softmax scale the personal model
  was built on (on real games as good as the reviewed `skill_t`: log-loss 0.26 vs 0.29 for the next doubling). A
  direct use of the simulated players with your skill would be far too pessimistic: at a real intermediate's skill
  they reach 2048 in 3% of games, because they compound their errors where real players repair them. Not reported from 16384 on: there the human move model over-predicts big errors and the engine
  misjudges strong players' late moves, so an expert's late-game reading would come out below a novice's.
- **hard moments** (reviews): risky positions (error risk >= 1%) whose best move players at your skill find less
  than 20% of the time (habits aside), and how many of them you found.

## Game review

- **best or good moves**: share of moves with a real loss below 1% (players who reach 1024: ~99%; the engine-match rate
  ~41% understates them because many moves are equally good).
- **decisive moment**: the largest loss from a still-healthy position.
- **skill**: your skill on the human move model's scale (see "At your level"; higher = stronger). **skill_t** (the
  older reading): the softmax player that best explains your moves (lower = stronger) - noisy, compare it only within
  a phase.
- **chances kept**: the product over the moves of (1 - real loss), until the position was lost.
- **mistakes at your level**: moves that cost at least 3% of your own chances of the next tile (`your_cost`; replaces
  the earlier experimental skill-based losses). **warnings**: how many times an app would have warned (per 100 moves).
- **key moments**: ranked by the larger of the real loss and your cost, each with its reasons; only moments of 3% or
  more are listed (smaller ones are at the noise level of the measurements; a review may have none).

**What a review can be trusted for** (workstream review, 2026-10-07: 100 real stretches of 64 players, every flagged
move and 1,000 random ones measured by playouts, at the player's level and with the engine playing on):

- **Novices**: what the review flags is real. 30% of key moments and 43% of warnings cost at least a fifth of the
  player's chances of the next tile (random moves: 2.4%), and flagged moves hold 80% of all the measured damage - but
  the flags catch only about a third of the individual big losses: a review is not a complete list of mistakes.
- **Intermediate and strong players** rarely make moves that cost them much (about 1-3 per 10,000 moves), so their
  reviews mostly confirm good play; "your cost" is rough at this level (it does not yet depend on skill).
- **The decisive moment** holds up: 10 of 15 were real losses of 10% or more of the player's chances (novices 7 of 7).
- **Experts**: key moments and warnings point at real losses when the engine plays on (29-32% lose 10% or more,
  random moves 1.6%), but a player's own big late-game errors are shown smaller than the engine's continuation
  measures (claims of 20-40%: shown ~7%, measured 24% with the engine playing on) - by design, since experts repair
  much of what the engine would not (see "real loss"); `real_loss_engine` gives the engine's view.
- **Warnings in exact-table positions** now need the table's own verdict of a 10% real loss (a table loss of ~15%);
  before, tiny table losses triggered a third of all warnings, at the false-alarm rate of random moves.
- **Hints** are shown only in the opening (largest tile up to 512), where they were confirmed on real games; at higher
  levels no measured hint pointed at a big loss. **Hard moments** are hard-to-find best moves, not errors: missing
  one cost almost nothing on average.

## Speed and limits

- An analysis takes ~1.3 ms at the engine's own depth without the exact tables (worst case 45 ms over 4,500 odd test
  boards), 35 ms at depth 5; depth is capped at 6 (deeper searches can take minutes on open boards). Every request is
  independent (same board, same answer and cost, whatever came before).
- With the tables, the first time a big snake formation (6+ chain tiles) appears its table is built on demand (4-5 s);
  later lookups are instant.
- Tested on ~4,500 unusual boards (huge tiles up to 2^30, impossible boards, all rotations): no crashes, odds and
  losses always in range, and the 8 rotations/reflections of a position give the same answer.
