# Workstream pdf: exact tables for the 3x2 block formation (REPORT)

Copied by the coordinator from results/pdf/report.txt.

```
Workstream pdf (2026-10-07): exact tables for the 3x2 block formation ("PDF") in our own engine + block detector.

== 1. Block-formation detector (coordinator's extra deliverable, 00:50) ==
src/block.h (header-only): blk::block_formation(board_t b, int moves_ahead = 0, const int* real_rank = nullptr,
int k = 4, int gap = 6): true when the 4 biggest tiles (with multiplicity) all lie in one 3x2 block touching a corner
(8 placements, blk::kPlacements) and the 4th biggest is >= max/64 (gap 6 ranks); moves_ahead = 1 also accepts a
legal move into it. real_rank: optional search-rank -> real-rank map (analyze's display map for 65536+ boards), used
for the gap test. blk::block_placement(int r[16], k, gap) works on real ranks directly. Snake chains fail it (their 4
biggest run along one edge). Tool: build_pdf/block_tool (src/block_tool.cpp; detect | pool), prototype
scripts/pdf_detect.py, pdf_detect2.py (variants). C++ = Python on all 510 labeled positions.
Variant choice (results of scripts/pdf_detect2.py): k=6 needs a loose gap to reach recall and then fires on our
engine's fresh-16384 boards (6 biggest small); k=5 gap 10: 93/105 but 12.6% of engine late positions; k=4 gap 6
is the best trade-off (gap 7: 97/105 but 7.6% engine, 4/117 snake random).
Labeled expert positions (results/mx/positions.tsv), k=4 gap=6:
                          moves_ahead 0     moves_ahead 1
  PDF player disputes        93/105            93/105
  PDF player random          41/183            41/183   (by max: the player is a block player at 8192-32768 and
  PDF player controls        13/37             14/37     mostly snake-like at 65536; see the dataset rates below)
  snake experts disputes      1/45              1/45    (d6: a genuine block shape, 32k-16k-4k-2k in a corner block)
  snake experts random        1/117             1/117   (r144: same game as d6)
  snake experts controls      0/23              1/23
  precision (PDF player vs snake experts, all groups): 147/149 = 98.7%; recall on disputes 88.6%.
Human dataset (results/human_ds/analysis.jsonl), share of positions in the formation (moves_ahead 0):
  PDF player:   max 8192 33.8%, 16384 27.0%, 32768 56.6%, 65536 3.7%
  other experts: 8192 0.0%, 16384 0.0% (2/5369), 32768 0.3% (29/10346), 65536 0.0%
  strong tier:  8192 4.0% (short early chains can sit in a corner block) -> suggest using it only at max >= 16384.
Our engine's own positions: pool700 (16384 formation) 0/700, pool32k (32768 formation) 0/1878, pool16real_rest
0/2186; replayed best_v5+t21 games (results/bench/late_t21/games*.txt, max >= 16384, every 25th move, 3000 boards
from 60 games): 1.0% (moves_ahead 1: 2.0%).

== 2. Exact block tables (01:00) ==
Design (data: scripts/pdf_scan.py, pdf_ends.py on the block player's 29k positions with max >= 16384): 7,838 have the
6 biggest tiles in a 3x2 corner block; in the block's canonical frame (block = cells 0 1 2 / 4 5 6) the smallest
block tile (the END, where the next tile is built) sits at cell 6 in 92% (goal cells 7 and 10) and at cell 4 in 7.5%
(goal cell 8); end ranks 64-512 dominate (1024: 478 positions, 2048: 4). In-block orders vary (column zigzag
0,4,1,5,2,6 55%, others 10-15%) but the sub-game does not depend on them (locked tiles only must not move).
Sub-game (as our snake tables): the 6 block cells locked; build a tile equal to the end in a goal cell (success
doubles the end tile), using only moves that leave the block in place. src/block.h: blk::block_spec(end, r) =
lt::snake_spec(6, r, caps, path) with path = block cells (end last) + free cells (nearest the goal first); free caps
r-1 (r-2 for the free cell farthest from the goal); blk::shape (end cell holds the goal rank, the other 5 block
cells larger; free caps checked by the lookup), blk::Tables::load(dir), blk::suggest, blk::move_values (per-move
afterstate success, as lt_move_values). Solved with the existing layered solver (build/layered --path/--caps; args
from `block_tool spec E R`; scripts/pdf_build.sh): ends 6 and 4, goal ranks 5-10 (64-1024), 12 tables, 52 GB on the
instance (weights/pdf/block_e{6,4}_r{5..10}.lt; r10 18 GB each, r9 6.2 GB), solved in ~5 min on 32 threads
(9e9 states in ~2 min).
Validation (layered --sim: the table's own policy from random states vs the table's p): e6 r10 0.737 +- 0.008 vs
0.732; e6 r9 0.603 vs 0.605; e6 r8 0.686 vs 0.679; e4 r10 0.762 vs 0.761; e4 r9 0.486 vs 0.489; r5/r6 (laptop)
0.949 vs 0.951, 0.935 vs 0.939 -> consistent. Independent check vs macroxue's own table probabilities (mx's
pdf_breaks.tsv, p per move): identical sub-game in several positions (d25: ours .792/.713/-/.793 vs mx .787/.709/0/
.788; d98 .010/.020 vs .010/.020); in others mx's tables answer a different sub-goal (d130: ours ~.79 vs mx .10).
Engine hooks (flag, default off): EngineConfig/--block-tables DIR, --block-min P (engine.h: EngineThread::choose
plays the block-table move when no snake table decided, source "block"; analyze() fills per-move table_p from the
block tables; so analyze, rollout, messy accept the flags); build/play --block-tables DIR --block-min P (same hook,
"block table moves" in the summary).

Coverage on mx's labeled positions (build/block_tool query): a block table decides 74/105 of the block player's
disputes (macroxue's tables: 70), 35/183 random, 8/37 controls; snake experts 0/185 (never fires). In the 74
decided disputes the expert's move is table-optimal in 65 (88%), our search move in 53 (72%); our search move loses
more than half the table's success chance in 12 (the formation breaks mx found: 16%).

== 3. Analysis effect on the expert disputes (01:05) ==
build/analyze --block-tables weights/pdf on the 210 expert decisions (scripts/pdf_claims.sh NAME FLAGS ->
results/pdf/claims_NAME.jsonl; metrics scripts/exp_late_claims.py report --split; TABLE-AWARE claims
scripts/pdf_claims_report.py: where a block table decided, a move's claim = its loss in the sub-game success
probability max(0, p_best - p_move) instead of the network's value loss).
Block player (81 refuted, 4 confirmed, 20 unclear disputes, 37 controls); claims > 10% on refuted = FALSE claims:
  engine                          value claims (as analyze)    table-aware claims     Spearman claim~real, all moves
  best_v5bb (late: claims_base)        64/81 (kept 3/4)              -                      0.289
  + block tables (blk_base)            38/81 (kept 1/4)          26/81 (kept 0/4)       0.360 / 0.442 (table-aware)
  t21 = late's best_v6 (claims_t21)    36/81 (kept 1/4)              -                      0.351
  t21 + block tables (blk_t21)         21/81 (kept 0/4)          16/81 (kept 0/4)       0.396 / 0.471
  controls: 0/37 claims > 10% everywhere. Snake experts (24 refuted, 8 confirmed): unchanged (tables never apply):
  base 19/24 false, 8/8 kept; t21 9/24 false, 8/8 kept.
-> with the tables the false "mistake" claims on the block player drop 64 -> 26 (base) and 36 -> 16 (t21), and the
claims rank the real losses better (Spearman 0.29 -> 0.44, 0.35 -> 0.47). The few real block-player mistakes (4)
are no longer flagged > 10%: their rollout losses are moderate. Recommendation for analyze (coordinator): when the
source is "block", grade moves by the table's probability loss (the p per move is already in the JSON) and keep the
detector-based abstention (src/block.h) for block positions no table covers (31 of the 105 disputes).
Coverage on the human dataset (scripts/pdf_coverage.py: shape + caps of the tables, goal ranks 3-10; vs the detector):
  block player max 16384: table covers 16.1% (detector 27.0%), max 32768: 46.8% (56.6%; both 45.6%), max 65536: 0%
  (3.7%; the player is snake-like there); other experts: tables 0.0-0.1%, detector 0.0-0.3%.
  -> tables + detector: the detector marks the block positions, the tables judge ~80% of the marked ones exactly.

== 4. Our engine playing on from the block player's positions (01:15) ==
Death within 1000 moves from mx's 300 random expert positions (build/rollout --preset best --block-tables
weights/pdf --moves engine --playouts 32 --horizon 1000 -> results/pdf/random300_blk_h1000.tsv; before: mx's
random300_ours_h1000.tsv; scripts/pdf_survival.py; tables r5-r10 only, r3/r4 were built later):
  | positions                   | n   | died before | with block tables | first move by a table | clearly better/worse |
  | block player, max 16384     | 9   | 0.354       | 0.163             | 3                     | 3 / 0                |
  | block player, max 32768     | 57  | 0.756       | 0.652             | 28                    | 15 / 1               |
  | block player, max 65536     | 117 | 0.072       | 0.061             | 4                     | 3 / 0                |
  | block player, all           | 183 | 0.299       | 0.250             | 35                    | 21 / 1               |
  | snake experts, all          | 117 | 0.167       | 0.167             | 0                     | 0 / 0                |
  (macroxue d4 from the same positions: block player at 32768 0.467.) -> the tables close ~1/3 of the gap to macroxue
  in the block positions; the rest: between table moves our snake search breaks the block (tables only cover states
  whose end tile has the goal rank and whose free tiles stay below it).

== 1b. Detector v2 (01:35): + block core (the 3 biggest in a corner 2x2 square, 3rd >= max/8) ==
blk::block_formation(b, moves_ahead, real_rank, k = 4, gap = 6, core_gap = 3) = 3x2-block test OR core test
(blk::block_core; core_gap -1 turns it off). It catches block positions whose 4th tile is still small (8192 32768 /
256 16384). Labeled positions (moves_ahead 0): block player disputes 97/105 (v1 93), random 42/183, controls 13/37;
snake experts disputes 1/45, random 1/117, controls 0/23 (unchanged: the d6/r144 game is a genuine block). Engine
late positions 1.0% (unchanged), pools 0/700, 0/1878, 0/2186. Dataset: block player 8192 33.8%, 16384 27.2%, 32768
59.0%, 65536 3.7%; other experts 0.0/0.0/0.3/0.0%; strong tier at 8192 4.0% (use at max >= 16384).
The 8 block-player disputes it still misses: 3 snake-row positions at 65536 (2k 4k 8k 64k), 3 with the biggest tile
off the corner, 2 with the 3rd tile < max/8.
Against macroxue's judgment (the better judge in block positions: mx's playouts with macroxue continuing,
results/mx/for_late.txt; scripts/pdf_vs_mx.py -> results/pdf/claims_vs_mx.txt), block player's 105 disputes, claims
> 10% (macroxue confirms only 1 dispute as a real engine-better case):
  base 83 (82 false) | t21 46 (45) | base + block tables, table-aware 32 (32) | t21 + block tables, table-aware 19 (19).
  Where the 19 come from (t21 + tables): table decided 4 (of 74), search with the detector firing 6 (abstain), search
  without detector 9 (3 snake rows at 65536, 3 biggest tile off the corner, ...). -> t21 + block tables + detector
  abstention: ~13 false claims of 105 (from 82).
Uncovered block positions (block player at 32768, detector fires, 7,045): tables cover 4,224; 1,915 have the 6th
biggest tile outside the block (mostly transitional: the 5th biggest still in the free region: a 5-locked table
family would add only ~5%), 459 a free tile equal to the end (caps r-1 treat that as failure), 144 a non-unique end.
Symmetry check (laptop tables, block_tool query on the 8 rotations/reflections of 6 table-decided expert positions:
d25, d49, d82, d94, d104, r192): identical p in every frame and the correspondingly transformed move (48/48).

== 5. Strength screen (01:45; 16384 phase, 700 real starts, seed 999, scripts/pdf_phase.sh = exp_late_phase.sh) ==
  base (late, ph16_base_s999)                                   62.57% (438/700)
  + block tables (ph16_blk)                                     61.57% (431/700); block-table moves 0.16% of moves;
      paired: 632 games identical, in the 68 that differ base reached 52, block tables 45 (-7: no help, maybe harm)
  gradient search d4 + block tables, 16384+ (ph16_g4blk)        12.43% (87/700), 0.31 ms/move
  the same without snake tables (ph16_g4blkns)                  12.43% (87/700)
-> our snake engine never builds the block from its own starts (detector 0/700 at the start, ~1% of its late
positions), so the tables rarely fire and do not help its own play; a macroxue-like player (our 2-D gradient
heuristic + our block tables) fails badly (12% vs macroxue d4 70.6% on the same starts; our earlier heuristic-only
test: 7.1%): reproducing macroxue's strength needs more than its two published ideas (its heuristic details, more
table shapes, and its search cut-offs) - a project, not a quick win. Dropped for now.
Laptop copy: weights/pdf/block_e{6,4}_r{3..10}.lt, 16 tables, 53.4 GB, built locally (6 threads, ~35 min); first and
last 64 MB of e6_r10 and e4_r9 identical to the instance's (md5 2a52fb4b79b4/a98f809c3c2d, 8ff6ceedb11a/15ffe283f287).

== 6. Block lock (01:55): --block-lock (engine.h / play.cpp; blk::lock_choice, blk::block_level) ==
In the block formation, play the best searched root move whose afterstate keeps the block level (6: the 6 biggest
in the corner 3x2 block, 4: block_formation), as the corner lock. Death within 1000 moves from mx's 300 random
expert positions (tables + lock, results/pdf/random300_blklock_h1000.tsv): block player 0.274 (tables only 0.250),
at 32768 0.677 (0.652), at 16384 0.389 (0.163, n = 9), snake experts 0.177 (0.167) -> no help: keeping the block
with snake-trained values does not make the play block-aware. Not recommended (flag stays, default off).

== 7. Do the tables' verdicts agree with the independent judge? (02:00) ==
74 table-decided block-player disputes (results/pdf/claims_blk_t21.jsonl, per-move table p) vs macroxue's playouts
(mx: expert's move vs best_v5bb's move, significant difference or not):
  table prefers the expert's move (p gap > 0.01): 20 -> macroxue: expert significantly better 9, no sig. difference
      11, engine better 0
  table: tie (|gap| <= 0.01): 47 -> macroxue: none 46, engine better 1
  table prefers the old engine's move: 7 -> macroxue: none 7
  All 9 positions where macroxue finds the expert significantly better are among the table's expert preferences; no
  contradiction in either direction. Pearson(table p gap, macroxue playout loss) 0.26; vs our rollouts 0.27 (n 74).
-> the tables' per-move probabilities are a trustworthy basis for grading moves in block positions.
Block lock in our own play (16384 phase, seed 999, + tables): 47.00% (329/700) vs 62.57% base - it changed 0.9% of
the moves and pulled the snake engine into block shapes (block-table moves 0.68% vs 0.16%): harmful. Keep it off.
Block tables only when p >= 0.5 (--block-min 0.5; as --lt-min for the snake tables): 62.57% (438/700) = base;
paired: 647 games identical, the 53 that differ: base reached 38, block 38 -> neutral in our own play (p >= 0: 61.57%,
-7 in the 68 differing games). -> safe default: --block-tables weights/pdf --block-min 0.5.

== 8. Unselected positions: claims on the expert's own move in mx's 300 random expert positions (02:50) ==
(scripts/pdf_claims_random.sh NAME FLAGS -> results/pdf/rclaims_NAME.jsonl; scripts/pdf_random_report.py; mx found
126 of 133 expert-vs-engine disagreements there show no significant difference with macroxue continuing, so nearly
every claim is false):
  config (claims on the expert's move)      block player (183): > 3%   > 10%   table decides | snake experts (117): >3% >10%
  best_v5bb                                                     18      6        0         |                     3    2
  + block tables (table-aware grading)                          10      3       35         |                     3    2
  t21                                                           14      7        0         |                     3    2
  t21 + block tables (table-aware)                               7      3       35         |                     3    2
-> on ordinary block-player positions the tables cut "mistake" claims on the expert's move by ~60% (18 -> 7); snake
experts unaffected.

== 9. Recommendations and files (03:00) ==
Analysis engine: run with `--block-tables weights/pdf --block-min 0.5` (laptop copy and instance copy exist, 53 GB,
read with pread like the k5 tables). Where the source is "block", grade moves by the table's probability loss
(p_best - p_move; the per-move p is in the JSON) - the tables' verdicts agree with macroxue's in every significant
case (section 7). Elsewhere in block positions (detector, max >= 16384): abstain (already wired in analyze).
Combined with late's t21 network: false "mistake" claims on the block player's disputes 82 -> ~13 of 105;
on ordinary block-player positions mistake claims on the expert's move 18 -> 7 of 183; snake experts unchanged.
Engine strength: no gain from snake starts (tables neutral at p >= 0.5; gradient route 12%; block lock harmful).
In human block positions our continuation dies less with the tables (75.6% -> 65.2% at 32768; macroxue 46.7%):
the rest needs block-aware values (e.g. networks trained from block start pools with the tables as the teacher).
Files: src/block.h (detector, block_level/lock_choice, block tables: spec, shape, Tables, suggest, move_values),
src/block_tool.cpp (detect | pool | spec | query; Makefile target build/block_tool), engine.h and play.cpp hooks
(--block-tables, --block-min, --block-lock; defaults off), scripts/pdf_* (scan, ends, detect, detect2, build,
claims, claims_report, vs_mx, phase, survival, coverage, claims_random, random_report, queue1-4),
results/pdf/ (claims_*.jsonl, rclaims_*.jsonl, random300_*_h1000.tsv, ph16_*.log, claims_vs_mx.txt, solve logs).
Death within 1000 moves with the tables at p >= 0.5 (results/pdf/random300_blkmin5_h1000.tsv): block player 0.256
(p >= 0: 0.250; none: 0.299), at 32768 0.669 (0.652; 0.756), 18 clearly better / 1 worse; snake experts 0.168 (0.167)
-> p >= 0.5 keeps most of the benefit and is neutral in our own play: the recommended setting.

== 10. Stretch assessment (coordinator's question, 02:45): a BLOCK-FORMATION PLAYER ==
Engineering: train.cpp's policy is greedy r + V(afterstate) after corner_filter, replaced by a table move (k6 peek,
k5 lt::suggest). A block lock = one filter call with blk::block_level (as corner_filter, ~15 lines) and block tables
= blk::suggest replacing the choice at p >= block_min (~25 lines + flags/loading): ~1 h incl. tests. In search.h the
lock would have to apply at every max node (corner_filter does) to keep search lines in the formation: block_level
is a sort over 8 placements per afterstate (~100-200 ns) -> a noticeable slowdown, or root-only as now (play/engine).
Start pools: pool700 is snakes; block starts must be synthesised (each board's 6 biggest tiles rearranged into the
block in the experts' zigzag order 0,4,1,5,2,6, the rest scattered in the free cells: ~1 h), later stages from
boundary pools collected from the block policy's own play (as pool32B-E were for the snake). The human block
player's ~7k block positions are one player's style and too few as the only source.
Training time on ~100 cores: TD is cheap (late: 9M continuation episodes in ~33 min on 24 threads); from scratch the
snake late networks needed ~4M episodes per stage x 3 stages plus the OTD tail - a few hours of wall time; the real
cost is design iterations (stage split, lock semantics, table coverage, starts), not compute.
Chance to beat v6b's 63.6% on the 16384-phase test within ~12 h: low, ~5-10%. (1) The test starts from snake
formations: a block network trained from block starts never learns the conversion (with the lock, greedy TD does not
discover the block by itself), and our snake play beats macroxue in snake positions (mx: death 16.7% vs 50.7%) - a
switch at the 16384 must pay for the conversion; (2) our tables cover only the full-block sub-games (47% of the block
player's 32768 positions; macroxue's tables decide 54-67% of its late moves, with more shapes); (3) history: the
snake late networks went from ~46-52% (v11b/c) to 63% over several days of iterations; a first block network would
likely land in the 40s-50s; (4) today's two cheap probes of block play from our side both failed (gradient + tables
12%; block lock 47%). A formation choice at the 16384's formation by table probability does not work either: the
tables value only a completed block, not the conversion to it.
Recommendation: do not run it in this window (I would not run it myself). For analysis the block positions are
already handled (tables judge exactly where they apply, the detector abstains elsewhere: ~13/105 false claims left);
the remaining gain is strength, which needs the multi-day project (block-aware networks + more table shapes +
conversion policy). Better use of idle cores now: confirm the block tables are safe in the final engine (running:
v6b + block tables p >= 0.5, ph16 3 seeds + p32, paired with late's v6b runs).

== 11. Safe in the final engine? v6b + block tables (p >= 0.5), paired with late's v6b runs (03:15) ==
ph16, 3 seeds (2100 games): v6b 63.62% -> v6b + block tables 63.67% (paired +0.05 +- 0.25 points; 1959 of 2100
games identical; block-table moves 0.13%): neutral.
p32 (1878 starts, 32768 just formed -> game over, seed 999): v6b 272,731 -> v6b + block tables 273,029 (paired +298
+- 724; 1814 of 1878 games identical; block-table moves 0.08%); sums >= 49152/57344/61440 74.7/50.8/34.0% ->
74.8/50.8/34.1%; 65536 0.11% both: neutral.
v6c (late2: v6b + OTD stage-1 network): the block tables act at the root, only in block shapes at p >= 0.5, and
fire in 0.08-0.16% of our engine's moves; a new stage-1 network matters only if it makes our own play drift into
block shapes more often (block-table share well above ~0.15% in its phase-test logs). Cheap check if v6c is
adopted: one ph16 seed of v6c + block tables, paired with late2's run.
```
