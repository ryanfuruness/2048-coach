# Workstream late: expert-level late game (REPORT)

Copied by the coordinator from results/late/report.txt.

```
Workstream late: expert-level late game (notes; the coordinator writes REPORT.md). Newest entries last.

TOOLS (instance dir ~/2048_late; laptop copies pulled into results/late/)
- scripts/exp_late_claims.sh NAME [analyze flags]: build/analyze (best_v5bb + flags, --no-calib) on the 210 expert
  decisions of results/disputes/expert.bin (150 disputes claimed > 10% by best_v5bb + 60 controls), 16 processes
  -> results/late/claims_NAME.jsonl. SET=judge: the unselected late positions (max >= 8192) of the H=1000 judges
  results/judge/late300_h1000.tsv + human300_h1000.tsv (296 boards, 185 with 32768+) -> judge_NAME.jsonl.
  SET=judge JNAME=jx JFILES=...: any other rollout judge (cal6's expert judge: queue 7).
- Reports: scripts/exp_late_claims.py report results/late/claims_*.jsonl; scripts/exp_late_judge.py report
  results/late/judge.idx results/late/judge_*.jsonl [--meta xexpert.tsv]; scripts/exp_late_summary.sh regenerates all.
- scripts/exp_late_phase.sh ph16|p32 NAME WEIGHTS DEPTHS [flags]: ph16 = 700 real 16384 starts (pool700) to sum 36864,
  seeds 999/1001/1002 (2100 games); p32 = the 1878 boards of pool32k.bin (32768 just formed) to game over. Paired
  differences: scripts/exp_late_paired.py; 1000-game benchmark paired with best_v5bb by seeds: scripts/exp_late_bench.sh
  + scripts/exp_late_benchpair.py.
- Training: scripts/exp_late_train.sh (second-half network, TD segments), exp_late_pool.py / exp_late_mixpool.py
  (expert root-view start pools), exp_late_folds.py (2-fold split by video, cross-fit merge), exp_late_avgstage.py.
- engine.h: EngineConfig now parses --exposed-pen W LO HI (off by default; analyze/rollout/messy can use it).

2026-10-06 ~22:00 +04: DISPUTE METRIC, first candidates (refuted disputes still claimed > 10% / confirmed kept > 10% /
mean claim refuted, confirmed / Spearman over all moves / ms per analysis)
  base best_v5bb      83/105  11/12  18.5%, 41.2%  0.481    4 ms
  analysis depth 5    92/105  12/12  17.7%, 42.9%  0.481    9
  analysis depth 6    68/105  11/12  15.1%, 42.3%  0.500   66
  budget 200k         69/105  11/12  15.1%, 40.4%  0.493   73
  exposed pen 1k/3k   84, 83  11     18.4%         0.481    4
  t21 as stage 3      45/105   9/12  10.7%, 39.3%  0.545    4   <- OTD second half (weights/expotd/t21.w)
  t18 as stage 3      45/105   9/12  10.8%, 39.1%  0.529    4
  t21 + depth 6       37/105  10/12   9.2%, 39.7%  0.559   63
  avg(s6, t21) wts    60/105  11/12  14.5%, 40.0%  0.521    4
  (135 of the 150 disputes are valued by stage 3 = the second-half network; the base re-analysis claims > 10% on only
  83 of the 105 refuted ones although all were selected with > 10%: regression to the mean of the selection.)
UNSELECTED late positions (judge set, 32768+ group, 185 positions; Spearman claim vs rollout loss, claims > 10% and how
many the rollouts refute): base 0.663, 194/64; t21 0.701, 182/54; t18 0.692; depth 6 0.650 (worse); t21+d6 0.682.
Claim -> real loss on unselected 16384+ positions (all non-reference moves): base 2-5% -> 1.8%, 5-10% -> 1.0%,
10-20% -> 10.5%, 20-40% -> 36%, 40%+ -> 82%; t21 2-5% -> 5.9%, 5-10% -> 5.9%, 10-20% -> 12.9%, 20-40% -> 39%,
40%+ -> 84% (t21's claims are closer to the real losses).
Exposed-cells penalty: conversion 64.1 / 62.4 / 61.1% for W = 0 / 2000 / 6000 (laptop), no effect on claims -> DROPPED.
Deeper search: helps on the selected disputes, not on unselected positions, 15-18x the cost -> not the fix.

PHASE TESTS (instance, best_v5bb settings; paired = same starts and seeds)
  ph16 base: 63.05% +- 1.05 (1324/2100); t21: 62.67% (paired diff -0.38 +- 0.67)
  p32 base: score 265,368 +- 2,322, sums >= 49152/57344/61440 72.7/48.0/31.9%, 65536 0.05%;
  p32 t21: 268,496, 73.3/48.8/33.0%, 65536 0.11% (paired: score +3,129 +- 1,415, >=57344 +0.85 +- 0.89)
1000-GAME BENCHMARK best_v5 + t21 as stage 3 (results/bench/late_t21, seeds paired with best_v5bb_1000):
  565,970 +- 6,556, 16384 95.4%, 32768 61.5% (best_v5bb 559,754 / 95.4 / 59.8); paired: score +6,216 +- 4,217,
  32768 +1.70 +- 0.95 points (425 of 1000 games identical), 2.13 ms/move on the instance.
=> RECOMMENDATION: best_v6 = best_v5 with stage 3 = weights/expotd/t21.w (python3 scripts/splice_stage.py
   weights/best_v5.w 3 weights/expotd/t21.w 0 weights/best_v6.w; instance copy weights/late/v5_t21.w). Same settings
   (preset_best). About half the false "mistake" claims on experts' moves, better-calibrated late claims, equal or
   slightly better play. The odds model / loss maps (cal6) were fitted on best_v5's values: refit (stage 3 changes the
   value scale of 16384-phase second halves and 32768-phase views).

EXPERT-POOL TRAINING (start pools from the root views of curated expert positions; scripts/exp_late_pool.py: 47k expert
16384+ positions -> 20,891 unique second-half views, 11,949 stage-B views, 14k below 24576)
  t21 continued TD 0.01 x 6M -> 0.001 x 3M (24 threads, ~23 + 10 min):
  c0 (usual pool only, control)       disputes 44/105 (c0_1), 44/105 (c0_2); judge 32768+ Spearman 0.705, 0.698
  x50 (50% of starts = expert views)  disputes 30/105, 31/105;             judge 32768+ Spearman 0.656, 0.651
  -> fewer false claims on the disputes but worse on the unselected late positions; BOTH test sets come from the same
  videos as the training views (contaminated: every expert video with 16384+ positions contains test positions).
  Clean test running: 2-fold split by video (exp_late_folds.py; fold A 5 videos / 10.5k views, B 12 videos / 10.4k),
  xA/xB trained like x50 on one fold, claims taken from the network that did not see the position's video.

2026-10-06 ~23:40 +04: CROSS-FIT (clean) expert-pool test and SPLIT BY PLAYER TYPE (mx: 105 of the 150 disputes are the
PDF player d4Nf6Bg5, who plays macroxue's 3x2 block formation; scripts/exp_late_claims.py report --split,
scripts/exp_late_judge.py report ... --split; video -> player: results/late/video_player.tsv, hex -> video:
results/late/hex_video.tsv)
  xAB = claims of xA (trained on fold A's expert views) for fold-B positions and of xB for fold-A positions
  (results/late/claims_xAB.jsonl, judge_xAB.jsonl; scripts/exp_late_folds.py merge).
  DISPUTES, PDF player (105: 81 refuted, 4 confirmed, 20 unclear; mean real loss -2.1%):
    false > 10%: base 64/81, depth 6 52, t21 36, t21+d6 29, c0_2 36, x50_2 (contaminated) 23, xAB (clean) 33;
    Pearson claim vs real ~0 for every candidate (-0.10..0.11): our claims carry no information in PDF positions.
  DISPUTES, snake experts (45: 24 refuted, 8 confirmed, 13 unclear; mean real loss +11.0%):
    false > 10%: base 19/24, depth 6 16, t21 9, t21+d6 8, c0_2 8, x50_2 8, xAB 7; confirmed kept: 8/8 for all;
    mean claim refuted 14.3% (base) -> 9.2% (t21), confirmed 52.6 -> 53.3%; Spearman all moves 0.736 -> 0.771.
  UNSELECTED judge positions with 16384+ (139 PDF player, 76 others): Spearman PDF base 0.621 / t21 0.661 /
    c0_2 0.661 / x50_2 0.604 / xAB 0.661; snake 0.777 / 0.815 / 0.801 / 0.798 / 0.794. False big claims PDF 59 -> 49
    (t21), snake 9 -> 8 (big claims in snake positions are real: mean real loss 75%).
  => t21's gain is NOT only the PDF player: for snake experts it halves the false claims (19 -> 9 of 24 refuted) and
     keeps every true one (8/8). Expert-pool training adds nothing clean (xAB = c0_2 within noise; the contaminated
     x50 gain came from training on the test videos; mx: the pool is mostly the PDF player and TD with our policy
     learns our collapsing play there) -> DROPPED.
  => PRODUCT: in PDF/block positions our claims are uninformative (r ~ 0) even with t21: the analysis should detect
     the block formation (6 biggest tiles in a 3x2 corner block, mx's "block6") and abstain or heavily discount claims
     there until the pdf workstream's tables exist. For snake experts, t21 claims > 10% are trustworthy enough to warn.
weights/best_v6.w created (laptop: splice_stage.py best_v5.w 3 expotd/t21.w 0; instance: hard link of
weights/late/v5_t21.w; md5 prefix 004a8625724e on both). preset_best NOT changed (coordinator switches after cal6).

2026-10-06 23:40 +04: CAL6's EXPERT JUDGE (400 curated expert positions, max 76 per player: 76 PDF player + 324 snake
experts; every move, 32 playouts, H=1000; copied to results/late/jx/, played moves from results/cal6/xexpert.tsv).
`scripts/exp_late_judge.py report results/late/jx.idx results/late/jx_*.jsonl --meta results/cal6/xexpert.tsv --split`
  played move != judged engine move, verdict by the rollouts; claims > 10% on refuted (false) / confirmed (true):
                 snake experts (202 refuted, 42 confirmed)        PDF player (55 refuted, 5 confirmed)
    base         96/202 false, 40/42 kept, Spearman 0.742         35/55, 3/5, Spearman 0.224
    t21          46/202,       38/42,      0.790                  22/55, 3/5, 0.294
    c0_2         45/202,       38/42,      0.790                  22/55, 3/5, 0.284
    x50_2 (cont.) 42/202,      39/42,      0.806                  15/55, 2/5, 0.256
    xAB (clean)  45/202,       38/42,      0.794                  21/55, 3/5, 0.332
  mean claim of refuted / confirmed played moves (snake): base 12.1% / 35.7%, t21 7.1% / 34.3%.
  t21's own moves vs best_v5bb's by the H=1000 rollouts: +0.47 +- 0.43% (snake), +0.71 +- 1.53% (PDF).
  => On the largest, balanced H=1000 expert set: t21 HALVES the false "mistake" claims on snake experts' moves
     (96 -> 46 of 202) and keeps 38 of 42 real ones; the clean expert-pool network adds nothing.
  Deeper analysis with t21 (cal6 judge): depth 5: snake 45/202 false, 38/42 kept, Spearman 0.786 (no gain); depth 6:
  40/202, 38/42, 0.801; PDF 17/55 (vs 22) -> depth 6 trims another ~13% of the false claims at ~15x the cost
  (~60 ms per analysis instead of ~4): a possible "deep" option for 16384+ positions, not needed by default.

2026-10-06 23:55 +04: BLOCK-FORMATION DETECTOR for analyze's abstention (coordinator task #53):
scripts/exp_late_block6.py: block6(b) = the 6 largest tiles fill a 3x2 or 2x3 rectangle in a corner (8 rectangles).
On cal6's 400 expert positions: PDF player 53 of 76 detected (the other 23: off-corner/other shapes), snake experts
5 of 324 false positives (1.5%). Played moves that differ from the engine, claims > 10% (false = refuted / true = confirmed):
  block6 positions (58):   base 28/40 false, 3/5 true;  t21 19/40, 3/5;  t21 depth 6 16/40, 4/5
  other positions (342):   base 98/210 false, 39/41;    t21 45/210, 37/41;  t21 depth 6 38/210, 37/41
  (max tile off the corners: 12 positions, 7 refuted moves - too few to matter)
=> with t21 and abstention in block6 positions: 21% of the > 10% claims on deviating expert moves are refuted by
   the rollouts (base: 47%), 90% of the real > 10% mistakes are still flagged.

2026-10-07 00:35 +04: FUZZ FINDING (1), rank collision in map_search_board with a 65536 (coordinator request).
Flags added, all off by default: `--map-safe` (game.h g_map_safe_gap: map_search_board prefers a gap g whose rank g-1
holds <= 1 tile), `--root-view-safe` (EngineConfig::root_safe: root view = search.h downgrade_view_safe_all, same rule,
iterated), `--leaf-view-safe` (EngineConfig -> Evaluator::view_safe, as build/play). Fuzz example
16384 . 16384 . / . . 4 2048 / . 256 . 4 / 64 65536 . 32: --map-safe alone changes only the stored board (16384s as
rank 13) and the displayed reward (16384 instead of 32768: lowered units); the values stay identical because the plain
root view re-creates the collision; --map-safe --root-view-safe removes it (view [4096 . 4096 . / ... 16384]) and the
values change a lot (up 136k -> 172k, down 102k -> 169k, left 161k -> 156k; engine move left -> up).
On 800 REAL curated positions (500 with a 65536+, 300 with a 32768; results/late/mapsafe_*.jsonl): 0 boards mapped
differently, 0 engine moves changed, 0 claim flips with either flag set (exact simulation of the mapping on the 500:
0 differ). -> the collision needs two tiles just below an empty rank next to the lowered top, which real expert
65536 positions practically never have. Keep the defaults; if adopted later, the displayed reward should use real
ranks (analyze shows the search board's lowered merge reward).

2026-10-07 00:45 +04: CLAIM -> REAL LOSS FOR EXPERTS' PLAYED MOVES (cal6's H=1000 expert judge, 400 positions; real
loss = rollout value of the candidate's reference move minus the played move's, relative; "other" = not block6):
  claim bin       0-2%   2-5%   5-10%  10-15%  15-20%  20-30%  30-45%  45%+
  base, other     -0.0   -1.3   +3.0   +7.0    +12.1   +16.0   +17.5   +45.9   (n 31/72/51/77/41/29/14/27)
  t21,  other     +0.4   -1.0   +5.5   +13.0   +14.6   +28.0   +28.3   +48.2   (n 135/48/33/42/25/20/18/21)
  t21,  block6    +0.5   -4.3   +9.3   +1.2    -10.3   +9.5    +0.8    -       (no relation: abstain)
=> with best_v6 (t21) the claims on snake experts' moves are roughly calibrated (claim 10-15% -> 13% real, 20-30% ->
   28%); the current lossmap_played_expert (15% -> 0, 28% -> 4.2%, 55% -> 15.4%), fitted for best_v5 on H=300
   disputes, would hide real mistakes under v6. For v6: near-identity for claims >= 10% outside block6 positions,
   abstain in block6 positions (refit with cal6's data when switching).
STAGE B OTD (bo_2: TD 0.1 x 12M -> 0.01 x 6M from OI, SH t21) as stage 2 of best_v6: claims unchanged (PDF 32/81 vs
36, snake 9/24 vs 9; judge 32768+ 0.701 = t21); phase test pending.
  ph16 (partial, 1307 of 2100 paired games): v6 + bo_2 65.03% vs v6 63.66%: +1.38 +- 0.63 points (vs base +1.76 +- 1.01).
  -> candidate "v6b" = best_v6 with stage 2 = OTD stage B: 1000-game benchmark started 00:55 +04 (28 threads,
  results/bench/late_v6bo2 on the instance; paired with best_v5bb_1000 and late_t21), p32 next, bo_3 (0.001) training.
  u1 (second long OTD run) stopped to free the cores; the ensemble check continues with e2 = (t21 + u0_3) / 2 only
  (queue 10 then waits for u1_3 forever: kill it after e2).

2026-10-07 01:00 +04: FINAL CANDIDATE best_v6b = best_v5 with stage 3 = weights/expotd/t21.w (OTD second half) and
stage 2 = weights/late/bo_2.w stage 0 (OTD stage B: from OI, TD 0.1 x 12M -> 0.01 x 6M, starts pool24, tables in the
loop, bootstrapping from t21; scripts/exp_late_q8.sh). Same settings as preset_best (best_v5bb).
  ph16: 63.62% (vs v6 62.67: paired +0.95 +- 0.50; vs base 63.05)
  1000-game benchmark (results/bench/late_v6bo2, seeds paired): 572,948 +- 6,552, 16384 95.4%, 32768 62.9%;
    vs best_v5bb: score +13,194 +- 5,006, 32768 +3.10 +- 1.16 points; vs best_v6: +6,978 +- 3,225, +1.40 +- 0.71
    (840 of 1000 games identical to v6). 1.81 ms/move on the instance.
  claims = v6's (disputes PDF 32/81, snake 9/24 + 8/8 kept; judge 32768+ Spearman 0.701).
  weights/best_v6b.w on the laptop (splice_stage.py weights/best_v6.w 2 weights/late/bo_2.w 0; bo_2.w pulled to
  weights/late/) and the instance (hard link of weights/late/v6_bo_2.w); md5 prefix e907c0a49207 on both.
  bo_3 (+3M at TD 0.001) = bo_2: ph16 +0.14 +- 0.42, identical claims -> v6b keeps bo_2 (benchmarked).
  p32 (1878 starts): v6b 272,731 +- 2,285, sums >= 49152/57344/61440 74.7/50.8/34.0%, 65536 0.11%;
    paired vs v6: score +4,235 +- 1,298, >= 49152 +1.38 +- 0.55, >= 57344 +1.97 +- 0.66 points;
    vs best_v5bb: +7,364 +- 1,765, +1.97 +- 0.91, +2.82 +- 1.02.

2026-10-07 01:50 +04: LONGER OTD and ENSEMBLE (no gain -> stop)
  u0 = second half from OI with twice t21's schedule (TD 0.1 x 24M -> 0.01 x 12M -> 0.001 x 6M, usual pool);
  e2 = weight average of t21 and u0_3 (stage 3). Cal6's expert judge, snake experts: false / kept / Spearman:
    t21 46/202, 38/42, 0.790;  u0_3 42/202, 36/42, 0.698;  e2 44/202, 38/42, 0.770. Disputes: all ~equal (snake 9/24).
  -> neither beats t21 (u0_3's rank correlation is clearly worse); u1 (seed 2) was stopped for the v6b benchmark.
WRAP-UP: nothing of workstream late runs on the instance any more. Instance weights/late/ (53 GB) holds the
experimental networks; worth keeping: v5_t21.w (= weights/best_v6.w, hard link), v6_bo_2.w (= weights/best_v6b.w),
bo_2.w (also on the laptop: weights/late/bo_2.w); the rest are negative results (x50/xA/xB/c0/u0/e2/avg) and can be
deleted. Regenerated tables: results/late/claims_report.txt, judge_report.txt, jx_report.txt
(scripts/exp_late_summary.sh). Benchmarks: results/bench/late_t21, results/bench/late_v6bo2.
```
