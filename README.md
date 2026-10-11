# 2048 Coach

A coach for human 2048 players. You play, and a strong engine grades every move: best, good, questionable or
blunder. It also says why, can stop you before a blunder, and can play on from any position. No account, no payment.
The web app is in [`app/`](app/README.md); the engine ("Afterstate") and the research behind it are the rest of this
repo.

**Not in this repo:**
- The trained networks (`weights/`, hundreds of GB of experiments). The files the app serves (~0.9 GB) will be
  published as a release.
- Run outputs (`results/` keeps only the reports).
- The human-games dataset (moves read from YouTube videos).

Without the networks the engine builds and its tests run, but it can't analyze positions.

License: [MIT](LICENSE).

## Afterstate, the engine

A 2048 AI built from a learned value function and expectimax search:

1. **A fast bitboard engine** (`src/board.h`): the board is one 64-bit integer (16 cells × 4 bits);
   moves are table lookups per row/column, verified against a naive reference implementation
   (`build/test_board`). Two 32768s merge into a 65536 stored one rank down (as tile downgrading
   would), so the 4-bit board supports the whole road to 65536; `src/game.h` tracks the real game.
2. **An n-tuple network value function** (`src/ntuple.h`): eight 6-cell patterns, each read with
   `PEXT` on all 8 symmetries of the board (64 table lookups per evaluation), estimating the expected
   future score of an *afterstate* (the board right after a move, before the random tile appears).
   The weights are split into **stages by tile sum** (the sum of all tiles grows by 2 or 4 every
   move and never decreases, so a game passes through the stages in order).
3. **Expectimax search** (`src/search.h`) with a transposition table, iterative deepening under a
   budget of network evaluations, a larger budget for close calls, and optionally a per-stage depth.
   With `--corner-lock 14`, moves that take the largest tile (16384 or more) out of its corner are
   not considered unless every move does.
4. **Exact endgame tables** (`src/endgame.h`): late in a game the big tiles form a snake from the
   corner (row 0 left to right, row 1 right to left, ...). Once the chain is 6 tiles long, what is left
   is a small sub-game: make a tile equal to the chain's smallest next to it, without moving the
   chain, after which the whole chain collapses into the corner. Dynamic programming over the 10
   free cells gives the exact probability of success and the best move (memoised expectimax,
   computed on demand and saved to `weights/endgame/`, ~2 GB). The idea is the one behind
   macroxue/2048-ai's lookup tables; the implementation is independent.

## Analysis engine (work in progress, since 2026-10-06)

The goal now is an analysis engine for human players, "the Stockfish of 2048": odds for any position (messy human
positions first), every move ranked with its loss against the best, the plan, game review, plain-word reasons, cheap
to serve. It runs the same engine as the player above (`src/engine.h`). API: docs/api.md; how to read it:
docs/guide.md.

```
build/analyze --preset best "2 4 16 2 / 8 32 64 4 / 16 128 512 8 / 4 2 256 0"      # tile values row by row
build/analyze --preset best-notables --risk 1 --line 10 --json BOARD                # without the exact tables
build/analyze --preset best --review game.txt                                       # one board per line
build/analyze --preset best --stdin                                                 # board per line -> JSON line
python3 scripts/serve.py --port 8048                                                # HTTP: POST /analyze
```

```
summary: With best play from here, the 16384 tile comes 82% of the time (in trouble compared with a typical
         position at this stage). Best move: down. Avoid right: it lets the next tile end the game in 90% of cases
         (vs 10% after down).
odds (engine plays on):  2048: 89.8%  4096: 89.4%  8192: 86.2%  16384: 82.3%  32768: 50.8%
  down  value      98993  loss         0  (real ~0.0%)
  right value          1  loss     98993  (real ~99.5%, your chances ~100.0%)  WARN
        - lets the next tile end the game in 90% of cases (vs 10% after down)
```

Per position: a one-line verdict; calibrated odds of reaching the next tiles with best play (the engine's base rates
at the stage, adjusted by the position's value - fitted on real human positions played out by the engine - times the
chance that the next tile does not end the game; on 200 fresh real positions the 16384 odds are off by 6.6 points on
average); the engine's move and what decided it (search, or an exact endgame or block table); every legal move's
value and loss; the estimated *real* loss (rollouts of 2,200 real positions map value losses to what they really cost,
in three stages: up to 1024, 2048-8192, 16384+; exact table chances where a table decides); what the move costs the
player's *own* chances of the next tile (`your_cost`, from simulated human-like players); whether an app should warn
before the move (`warn`: the coach study found warnings just before bad moves are the most effective advice); the plan;
reasons chosen from concepts validated on human games (corner, chain, tiles exposed next to big tiles, big tiles in
the middle, missed big merges, the risk of the next tile, per-cell attribution of the network's value), each checked
in the position itself by a counterfactual edit (`share`: the part of the loss that removing exactly that defect
recovers; unfaithful reasons are dropped, the main cause comes first); `plan_info` (the plan as data); with a skill
(`--skill`, `--personal T`): how likely a player at that level finds each move (`find_prob`, from a human move model
fitted on 115,000 real decisions), the position's `error_risk` and a `hint`; an `odds_caveat` where the formation is
unusual for the stage; optional risk of the next tile, sample continuation, value heat map and personal odds for a
player of a given skill (simulated by the human move model). Positions in the 3x2 block formation of some experts
(the engine plays snakes) are judged only by exact block tables, otherwise not at all.

Game review: the moves between consecutive boards are inferred (video frames may skip moves), every move is analysed,
and the summary gives the share of best-or-good moves, inaccuracies / mistakes / blunders by estimated real loss (a
player's own late-game moves judged by what players lose, with the engine-continuation cost alongside), the decisive
moment, key moments (>= 3%) with reasons and each move's cost to the player's own chances, the warnings and hints an
app would have shown, hard-to-find moves, and the player's skill (human move model, below 16384) per phase. Checked on
100 real game stretches: for novices what the review flags is real (30-43% of flagged moves cost a fifth of their
chances, 2.4% of random ones), the decisive moment holds up (10 of 15 real losses of 10%+).

Findings so far (details in NOTES.md and results/*/REPORT.md): the engine's move is as good as the rollout-best move
within noise on real human positions (16 of 1,800 significantly worse, the noise level); the engine repairs most human
damage, so its odds are mostly the stage's base rate; real human positions repair less than synthetic ones and human
players less than the engine; advice helps: from real bad positions, simulated players closed 40-90% of the gap to the
engine with 1-2 warnings per 100 moves; in expert positions the engine's big claims were mostly wrong for one expert's
block formation (now handled by exact block tables or not judged) and, for snake experts, losses the engine measures
when it continues but that do not add up over an expert's game (experts repair them). A scorecard
(`scripts/scorecard.sh`) re-measures all of this for any engine configuration.

Supporting tools: `build/messy` (positions from imperfect human-like players), `build/rollout` (ground-truth move
values by playouts), `build/coach` (advice experiments), the fit scripts (`scripts/fit_calib.py`, `fit_lossmap2.py`,
`fit_lossmap_table.py`, `fit_owncost.py`, `fit_personal.py`), `scripts/human_review.py` (batch review of human games),
`scripts/switch_engine.sh` (move the analysis to new networks and refit what depends on their values).

## Where it stands

| Player (200 games unless noted) | Avg score | 16384 | 32768 |
|---|---|---|---|
| v5 network, depth 2 everywhere | 419,018 | 85.5% | 34.5% |
| v5 network, depth 3 in the first two stages, 2 later | 433,733 | 93.0% | 40.0% |
| v6 early game (Matsuzaki tuples) + v5 later stages, same depths | 459,615 | 97.0% | 39.0% |
| the same player, 1000 games (`results/bench/hybrid1000`) | 447,181 ± 5,161 | 95.2% | 36.8% |
| + root downgrading after 32768, newer early game, 1000 games (`results/bench/hybrid_rd1000`) | 460,857 ± 5,458 | 96.5% | 37.0% |
| corner-locked 16384-phase network + endgame tables, 1000 games (`results/bench/m1q_eg1000`) | 466,748 ± 6,051 | 95.0% | 40.8% |
| + tables in the training loop, phase from the 16384's formation, 1000 games (`results/bench/v11c1000`) | 488,691 ± 6,260 | 94.9% | 45.5% |
| + second half trained 4M episodes (not 12M), searched at depth 4, 1000 games (`results/bench/v11c_e4_1000`) | 506,542 ± 6,610 | 94.9% | 48.8% (0.1% 65536) |
| + dedicated first half, also 4M episodes and depth 4, 1000 games (`results/bench/best_v2_1000`) | 524,809 ± 6,477 | 94.9% | 52.7% |
| + k=5 endgame table (60 GB, on disk), early-game network valuing the 8192 build through a downgraded view, separate stage for building the 4096, 1000 games (`results/bench/best_v3_1000`) | 547,525 ± 6,475 | 95.4% | 57.4% |
| + better seeds for the second half and the 4096 stage, second k=5 table, tables matched on the root view after 32768, 1000 games (`results/bench/best_v5_1000`) | 552,742 ± 6,481 | 95.4% | 59.8% (0.1% 65536) |
| + budgeted iterative deepening (tight boards searched deeper) in the 4096 stage and the second half, 1000 games (`results/bench/best_v5bb_1000`) | 559,754 ± 6,552 | 95.4% | 59.8% |
| + networks trained with a decaying TD rate (OTD) for the 16384 phase's second half and the stage before it, 1000 games (`results/bench/late_v6bo2`, best_v6b) | 572,948 ± 6,552 | 95.4% | 62.9% |
| + an OTD network for the 16384 phase's first half (leaf view limited to sums below 20480), **1000 games** (`results/bench/late2_v6c`, best_v6c) | **586,082 ± 6,569** | **95.4%** | **64.0%** (0.1% 65536) |
| *Guei et al. 2022 (n-tuple, 3-ply, 10k games)* | *563,316* | *96.9%* | *57.9%* |
| *Guei et al. 2022 (6-ply, 100 games)* | *625,377* | *98.8%* | *72.0%* |
| *macroxue/2048-ai (depth 8 + endgame tables, 1000 games)* | *711,769* | *98.7%* | *80.5%* (3.5% 65536) |

The state of the art is not beaten yet. `NOTES.md` describes the current line of work and logs every
experiment.

**Where the gap is.** Binning the 16384-phase deaths by tile sum (`scripts/death_bins.sh`; macroxue's published
outputs give the same numbers for their player) separates two problems. While the next big tiles are built into the
formation (sum below 31744), this player loses 15.7% of the games that reach the 16384, macroxue loses 2.8% at
depth 8 and 5.8% at depth 5. These deaths are broken formations in positions the network plays (the tables rarely
apply), and neither deeper search nor a formation penalty reduces them: unlike a hand-made heuristic, the learned
evaluation does not get better with depth there. In the final phase (the k=5 table's territory) about 25% of the
games that arrive die, against 16% for macroxue at every depth. The table plays this phase optimally within its
sub-game, so the 25% is a property of the snake formation (the table's own number for the last step, 78.2%, matches
macroxue's snake analysis; their block formation gets 81.2%, and the gap compounds over the phase's steps). The late
networks are also "table players": without tables they convert 3.4/11.0/19.4/23.9% at 1–4 move levels (Guei et al.'s
table-free network: 35.4/59.8/68.9/72.9%), and a table-free network that plays far better alone (29.9% vs 11.0% at
depth 2) is worse inside the full player (61.6% vs 64.1%).

**Layered endgame tables** (`src/layered.h`, `build/layered`). The memoised tables above stop at 6 locked
tiles (10 free cells, ~2 GB in RAM). With 5 locked tiles the sub-game has 11 free cells and ~3·10¹⁰
states. The free cells' tile sum never changes in a move and grows by 2 or 4 with each spawn, so the
DP can run one tile-sum layer at a time, from the largest sum down, keeping only the two layers above
in memory. Every configuration within per-cell rank caps is solved and written to disk (2 bytes per
state, combinatorial rank inside each layer), and play reads single entries with `pread`. The k=5 table
for a 16384…1024 chain (build a 1024 next to it) is 60 GB and took ~35 minutes on 18 threads; it is
verified against the memoised solver (identical on all 560k entries of a k=8 table) and by simulation
(table probability 0.452 vs simulated success 0.452 ± 0.004). In play it is matched for any chain from the
largest tile with at most one missing rank, which also covers the 32768 phase.

**Leaf view.** The early-game network (zero-initialised, trained on whole early games) gains from search
much more than the optimistic late-stage networks. With `--leaf-view 14 6 --leaf-view-max-sum 24576`,
search leaves in the first part of the 16384 phase are valued by that network on a downgraded copy of
the board (16384 → 8192 and so on), so it plays the 8192 build as the 4096 build it mirrors. That cut
deaths there from 43 to 23 of 700 and nearly removed deaths right after the 16384 forms. Later in the
phase the view misleads it: two tiles just below the view's gap look as if they will merge into the
lowered chain end.

## Training

Self-play temporal-difference learning — TD(λ=0.5, truncated after 3 steps) with temporal-coherence
(TC) per-weight learning rates — on the GPU (`src/gpu_train.cu`): 32768 games in flight, one CUDA
thread per game, synchronous batched updates, ~13M moves/s for 8×6 tuples on an RTX 4070 Laptop GPU.
Late stages are trained from **pools** of positions where games entered the stage; episodes **stop at
the stage boundary** and bootstrap from the next stage's value. The trainer can also choose moves by
a 2-ply expectimax (`--policy-depth 2`, optionally on a fraction of moves, `--policy-mix`), follow a
teacher network (`--teacher`), or explore (`--explore`, with Watkins-style trace cutting).

What the experiments showed:

* **Tuples matter most.** Matsuzaki's systematically selected 8×6 set (TDL2048+ `8x6patt`) learns far
  better than a set screened one tuple at a time: after 600k GPU games 69% vs 41% of greedy games
  reach 16384, and the plateau is higher (75% vs 64%).
* **The pessimism trap.** A network trained from zero weights values the 16384 phase by the games
  that died there. It learns the wrong strategy for it — in 0 of 286 positions right after the 8192
  forms is the 8192 next to the 16384 (it builds it in the opposite corner) — and a stage trained
  on top of it made 0 32768s in 3M episodes.
* **Optimistic initialisation finds the right strategy** (8192 next to 16384 in 273 of 274
  positions; 0% → 17-31% of episodes reaching 32768) **but is fragile under search**: greedy play
  15% of full games reach 32768, depth 2 only 1%. Move values show why: a move off the greedy path
  gets a nonsensical value (even −80k), while one move later the positions look normal again; the
  search averages over these never-trained positions and prefers bad moves. Plain TD instead of TC,
  a zero-initialised student learning the optimistic network's values, and 3% exploratory moves did
  not fix it. What did help is **training with the policy you search with**: a stage continued with
  a 2-ply policy got 44.6% of depth-2 games through (vs 33% for its best greedy play).
* **One stage per game phase.** With a boundary inside the 16384 phase, the first half cannot learn
  what the second half needs; the whole phase is now one stage.
* Hand-made heuristics (nneonneo's, a snake gradient) as shaping potentials are far too weak at
  these search depths (30-66k average at depth 3), and tile downgrading at the root lets a network
  that never trained past 16384 reach 32768 in 10.5% of games (vs 1%), but no more.

**Pipeline v6** (`scripts/pipeline_v6.sh`, in progress): Matsuzaki tuples; three stages — early game
`[0, 20480)` from a zero-initialised base network, the 16384 phase `[20480, 36864)` and the 32768
phase `[36864, ∞)` from fresh optimistic weights, each followed by a 2-ply curriculum (the deeper
policy on 25%, 50%, then 100% of moves).

**Corner lock and endgame tables** (pipelines v11, v11b, v11c). Every network trained so far moved
the 16384 out of its corner (merging along the edge away from it, in 129 of 139 games), which leaves
big tiles on both sides of it; most games were lost that way. Under `--corner-lock` the network
learns the classic snake instead, and then 68-95% of the positions late in the 16384 phase are snake
endings the tables solve exactly. Tables help when their success means the whole chain collapses
(`--endgame-full 2`); used for every snake ending they hurt (the sub-game ignores the position left
after a partial collapse). With the tables also playing their moves during GPU training
(`gpu_train --endgame-dir`), the second half of the 16384 phase learns far faster (29.9% of episodes
completed after 2M episodes vs 0% without, plateau 47% vs 27%).

**Greedy over-training hurts search.** Trained with a greedy (1-ply) policy, a late-stage network's own
training metric keeps creeping up long after its value under search has peaked: for the second half
of the 16384 phase, the fraction of real positions completed at depth 3 / depth 4 was 58.0 / 60.5% after
4M episodes but 52.8 / 45.2% after 8M and 48.1 / 37.1% after 12M (the training metric meanwhile went
from 45% to 48%). The network learns the trajectories its own greedy policy takes and loses the values
of the positions a deeper search looks at. Stopped near the peak, the networks gain from depth 4
instead of degrading.

## Build

```
make            # CPU tools: build/train, build/play, build/test_board
make gpu        # GPU trainer: build/gpu_train (needs nvcc)
./build/test_board
```

## Play

```
# watch one game in the terminal (add the table and view options below for full strength)
./build/play --weights weights/best_v5.w --stages "sum:20480/14,24576,28672,36864" --quantize --depth 4 \
  --stage-depth 3,4,4,4,4 --corner-lock 14 --root-downgrade 15 --watch 0
# benchmark in resumable chunks (records every game for the replay viewer)
# the current best (best_v5bb): corner lock, root downgrading, k>=6 and k=5 endgame tables, leaf view, budgeted deepening
scripts/bench.sh NAME weights/best_v5.w "sum:20480/14,24576,28672,36864" 1000 100 14 --quantize --depth 4 \
  --stage-depth 3,4,8,8,4 --min-depth 4 --budget 20000 --corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 \
  --endgame-dir weights/endgame_big --endgame-nosave \
  --endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 \
  --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5 --lt-view \
  --leaf-view 14 6 --leaf-view-max-sum 24576
# solve a layered table: build/layered --k 5 --rank 10 --caps 9,9,8,8,8,9,9,7,7,7,7 --out FILE --threads 18
```

Search options: `--depth D`, `--budget N` (leaf evaluations per move for iterative deepening),
`--budget-hi N --close F` (larger budget when the two best moves are within F·value),
`--stage-depth d0,d1,...` (max depth per stage), `--root-downgrade R`, `--prob-cut P`,
`--quantize` (16-bit weights), `--corner-lock R`, `--endgame K` (tables for snake endings with at
least K locked tiles) with `--endgame-full 1|2`, `--endgame-min P`, `--endgame-dir DIR`. Analysis: `--analyze HEX` prints move values at each depth for one
board; `--disagree N` prints positions where depth 1 and depth 2 choose differently; `--stop-sum S`
ends games at a tile sum (to measure one stage); `--start pool.bin` starts from recorded positions.
