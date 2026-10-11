# Workstream late2: OTD stage 1 -> best_v6c (REPORT)

Copied by the coordinator from results/late2/report.txt.

```
Workstream late2 (notes; the coordinator writes REPORT.md). Newest entries last.

2026-10-07 01:55 +04: STAGE 4 IS NOT USED -> step 1 as specified is moot.
  scripts/exp_late2_stageuse.py replays recorded games (build/play --record) and assigns each move's search ROOT to the
  stage of its root view (stages sum:20480/14,24576,28672,36864, root downgrade 15 / gap 5). v6b's 1000-game benchmark
  (results/bench/late_v6bo2/games0-1.txt, 4.05M moves): stage 0 50.7%, 1 14.0%, 2 16.4%, 3 18.9%, stage 4: 7 moves
  (0.0002%); moves with a real 32768+ on the board (1.21M): stage 0 18.1%, 1 17.6%, 2 27.2%, 3 37.0%, stage 4 7.
  The root downgrade maps the whole 32768 phase onto the 16384-phase networks (32768 -> 16384 etc. while a rank gap
  >= 5 exists); stage 4 (view sums >= 36864) only sees gap-free boards right before the collapse into 65536
  (e.g. 32768 16384 8192 4096 2048 1024 512 256 128 64 32 ...). An OTD stage 4 cannot change play or claims.
  Stage 1 roots ([20480, 24576)) are valued at their leaves by stage 0 through the leaf view (--leaf-view 14 6
  --leaf-view-max-sum 24576), so stage 0 (s0cpu, TC-trained, 12.3M episodes) is the network behind ~65% of all roots
  and ~36% of the 32768 phase's roots, and it values every human early-game position.
  => late2 goes straight to step 2 with stage 0 as the target (strength AND analysis).
EARLY-GAME OTD (stage 0):
  - otd: zero-init stage 0 (s0cpu's 2-stage file, stage 0 zeroed: neutralize.py --fresh 0 --value 0; stage 1 =
    s0cpu's bootstrap stage), TD 0.1 x 12M -> 0.01 x 6M -> 0.001 x 3M, 44 threads, started 01:49 +04
    (scripts/exp_late2_train.sh otd weights/late2/start0.w "0.1:12000000 0.01:6000000 0.001:3000000" 44).
    Speed: ~900 episodes/s on 30 threads (episodes ~8,300 moves, 7.6M moves/s).
  - Continuing s0cpu with plain TD 0.01 (exp_queue15's plan) DEGRADES it fast: in-training 1-ply 16384 rate per 10k
    window 76.9% -> 67.7% -> 63.0% (30k episodes) -> rate tests at 0.003 / 0.001 / 0.0003 running.
  - Rate tests on s0cpu (40k episodes, cumulative 1-ply 16384 rate per 10k; s0cpu's own 1-ply rate ~83.5%):
    0.003: 82.8 / 83.4 / 82.6 / 83.0; 0.001: 84.0 / 83.8 / 84.8 / 84.5; 0.0003: 83.6 / 84.3 / 84.4 / 83.6 (0.01:
    76.9 / 72.3 / 69.2 at 30k) -> rates <= 0.003 keep s0cpu's level; 0.01 wrecks it (TC left small effective rates).
  - ann: s0cpu + plain TD 0.001 x 3M (15 threads), started 02:05 +04 (exp_late2_train.sh ann weights/tup/s0cpu.w
    "0.001:3000000" 15).
  (ssh note: `ws.sh run X 'nohup ... &'` hangs because "cd X && nohup ... &" backgrounds the whole list with the ssh
  channel open; launch with `ws.sh run X 'true; nohup ... > log 2>&1 < /dev/null &'`.)
ANALYSIS METRIC (scripts/exp_late2_judge.py, exp_late2_claims.sh): 1050 unselected real positions with max <= 8192 from
  results/judge/human300_h1000.tsv + results/cal6/j1200 (every move judged by 32 rollouts, H=1000, best_v5
  continuation); claims as analyze (relative value loss vs the reference move, 100k floor).
  base = best_v6b (stage 0 = s0cpu): Spearman(claim, rollout loss) <=512 0.019 (342 positions), 1024 0.159 (215),
  2048-8192 0.453 (493), all 0.274; claims > 10%: 629, of which 499 not confirmed by the rollouts; calibration (claim
  bin -> mean rollout loss): <1% -0.0, 1-3% -0.1, 3-10% 0.0, 10-30% 2.3, 30%+ 37.4 -> early claims below 30% carry
  almost no information (the engine repairs; or the early network's value differences are noise).
EVALUATION PLAN (instance ~/2048_late2): candidate stage 0 spliced into best_v6b (splice_stage.py weights/best_v6b.w 0
  weights/late2/X_k.w 0 weights/late2/v6b_X.w); scripts/exp_late2_phase.sh early|ph16|p32 NAME WEIGHTS (best_v5bb
  settings: depth 4, stage depths 3,4,8,8,4, min depth 4, budget 20000, lock 14, root downgrade 15, k>=6 + k5 tables,
  leaf view 14 6 < 24576) with paired seeds: early 2 x 1400 games from the empty board to sum 20480 (seeds 4321, 4322),
  ph16 / p32 = late's protocols (baselines: late's v6b logs copied as ph16_v6b_s*.log, p32_v6b.log); paired
  differences: scripts/exp_late2_paired.py (early), scripts/exp_late_paired.py ph16|p32 NAME v6b results/late2.
  Analysis: scripts/exp_late2_claims.sh NAME --weights W -> exp_late2_judge.py report.
2026-10-07 03:40 +04: ann_1 (s0cpu + TD 0.001 x 3M) done: in-training 1-ply 16384 rate 85.0% (s0cpu ~83.5%).
  otd_1 (zero init, TD 0.1) at 10M of 12M: 1-ply 16384 rate 49.5% (plateau since ~9M) -> far below s0cpu so far.
  Claims of v6b + ann stage 0 (weights/late2/v6b_ann.w, md5 00d511c1a124) on the 1050 early/mid judge positions:
  Spearman all 0.278 (base 0.274), <=512 0.038 (0.019), 1024 0.171 (0.159), 2048-8192 0.449 (0.453); claims > 10%
  634 (629), not confirmed 504 (499); calibration unchanged (10-30%: 2.2 vs 2.3, 30%+: 37.4 = 37.4)
  -> a slightly better early network does NOT make early claims more informative: below ~30% value loss the
  rollouts measure ~0 real loss whatever the network (the engine repairs), i.e. it is not a value-accuracy problem.
2026-10-07 04:05 +04: EARLY TEST (2 x 1400 games from the empty board to sum 20480, paired seeds 4321/4322, best_v5bb
  settings): v6b 95.71% reach 16384 / 95.21% reach sum 20480; v6b + ann stage 0: 95.68% / 95.25% -> paired diffs
  -0.04 +- 0.53 / +0.04 +- 0.56 points: the gentle annealing changes nothing under search (the +1.5-point 1-ply gain
  does not survive depth 3). otd (zero-init OTD stage 0) STOPPED after its first segment (1-ply 16384 rate 49.7% at
  12M vs s0cpu 83.5% / ann 85.0%: it cannot catch up in this run's remaining 9M episodes; the analysis question is
  answered by ann: early claims do not depend on the early network's accuracy).
NEXT: stage 1 (the 16384 phase's first half) is the one late-game stage without the OTD recipe; its network is unused
  in best_v5bb's settings (the leaf view gives every 16384-holding leaf below sum 24576 to s0cpu, which beat the old
  TC-trained dedicated first halves: first-half deaths 43 -> 25 of 700). s1o = OTD stage 1 against bo_2
  (scripts/exp_late2_s1.sh, 40 threads, ~45 min): played with the leaf view off / limited, ph16 paired vs v6b.
PRESET CHECK (coordinator's pitfall: the instance's ~/2048/weights has no best.cfg and no calib/, so `--preset best`
  there means best_v5 without maps): every late2 run passed explicit weights - claims: exp_late2_claims.sh base
  `--weights weights/best_v6b.w`, ann `--weights weights/late2/v6b_ann.w` (both --no-calib: raw value losses, maps not
  used); play: exp_late2_phase.sh always passes the weights file (best_v6b.w, v6b_ann.w, v6b_s1o_K.w); ph16/p32 v6b
  baselines = late's logs of weights/late/v6_bo_2.w (= best_v6b, explicit). (On the early judge set, max <= 8192, v5
  and v6b give identical claims anyway: they differ only in stages 2-3.)
2026-10-07 04:40 +04: ph16 of v6b + ann stage 0 (s0cpu values the first-half leaves through the leaf view): 62.81% vs
  v6b 63.62% (2100 paired games: -0.81 +- 1.02 points) -> no gain (if anything slightly worse). STAGE-0 ANNEALING
  REJECTED for play and for analysis.
  s1o_1 (OTD stage 1, TD 0.1) at 8.5M of 12M: episode length 3100 moves (from sum ~16460 toward 24576; ~3,700 = full
  stage), table moves 1.8%.
2026-10-07 05:52 +04: s1o trained (stage 1 OTD against bo_2, 40 threads): in-training episode length (from the 16384's
  formation toward sum 24576; ~3,700 = the whole stage) s1o_1 (0.1 x 12M) 3131, s1o_2 (+0.01 x 6M) 3461, s1o_3
  (+0.001 x 3M) 3511; table moves 1.8 / 2.3 / 2.4%. Training took 1 h 53 min.
2026-10-07 06:15 +04: ph16 (2100 paired games vs v6b 63.62%):
  s1o_2 (0.01), leaf view off:                 62.48%  -1.14 +- 1.30
  s1o_3 (0.001), leaf view off:                62.33%  -1.29 +- 1.24
  s1o_3, leaf view only below sum 20480 (v20): 64.90%  +1.29 +- 0.60   <- candidate "v6c"
  -> the OTD stage-1 network beats s0cpu's view in [20480, 24576) but not right after the 16384 forms (sum < 20480,
  where s0cpu's view stays better). Next: p32 (paired), 1000-game benchmark paired with late_v6bo2, claims.
2026-10-07 06:37 +04: p32 (1878 boards at the 32768's formation -> game over, paired seeds vs v6b): v6c (= v6b with
  stage 1 = s1o_3, --leaf-view-max-sum 20480) 275,837 +- 2,206, sums >= 49152 / 57344 / 61440 75.4 / 51.3 / 34.1%
  (v6b 272,731 / 74.7 / 50.8 / 34.0); paired: score +3,106 +- 1,608, >= 49152 +0.69 +- 0.64, >= 57344 +0.53 +- 0.59
  points -> small gain, consistent with the ph16 result (stage 1 views cover 17.6% of the 32768 phase's roots).
2026-10-07 06:45 +04: 1000-GAME BENCHMARK v6c (results/bench/late2_v6c on the instance, chunk seeds 1000+k = paired with
  results/bench/late_v6bo2): 586,082 +- 6,569, 16384 95.4%, 32768 64.0%, 65536 0.1% (1 game, 1,313,348 points) vs v6b
  572,948 / 95.4 / 62.9 / 0.0; paired: score +13,134 +- 3,569, 32768 +1.10 +- 0.71, 65536 +0.10 +- 0.10 points (811
  of 1000 games identical); 1.55 ms/move.
  CLAIMS (late's pipeline, both through analyze's default full preset incl. the instance's block tables; v6b vs v6c):
  disputes false > 10% 28/105 vs 27/105, kept 8/12 vs 8/12, Spearman all moves 0.552 vs 0.557; unselected late judge
  (296 positions) Spearman 0.682 vs 0.683, claims > 10% 276 vs 276 (not real 95 vs 94); cal6's expert judge jx (400)
  Spearman 0.718 vs 0.720, played refuted > 10% 57/257 vs 54/257, confirmed 39/47 vs 39/47 -> claims unchanged or
  marginally better (stage 1 rarely values these 32768+ expert positions).
2026-10-07 06:42 +04: BLOCK-TABLE CHECK (pdf's recommendation): v6c + `--block-tables weights/pdf --block-min 0.5`,
  ph16 seed 999 (700 games) paired with plain v6c seed 999: 67.86% vs 67.57%, +0.29 +- 0.40 points; block table moves
  0.14% of moves (pdf measured 0.08-0.16% with v6b) -> neutral, no drift into block shapes with the new stage 1.
RECOMMENDATION: SWITCH to v6c. Engine flags (on top of preset_best):
    --weights weights/late2/best_v6c.w --leaf-view-max-sum 20480
  best_v6c = best_v6b with stage 1 = weights/late2/s1o_3.w stage 0 (OTD stage 1: fresh optimistic init, TD 0.1 x 12M
  -> 0.01 x 6M -> 0.001 x 3M, tables in the loop, lock 14, starts weights/v11c/pool16.bin, bootstrapping from bo_2;
  scripts/exp_late2_s1.sh); `python3 scripts/splice_stage.py weights/best_v6b.w 1 weights/late2/s1o_3.w 0
  weights/late2/best_v6c.w`; md5 prefix 95c6bf08e114 on the laptop and the instance (hard link of
  ~/2048/weights/late2/v6b_s1o_3.w). The leaf-view limit (24576 -> 20480) is part of the change: without the leaf
  view the new stage 1 is worse than v6b (-1.3 points); s0cpu's view stays better right after the 16384 forms.
  Evidence (all paired vs v6b): 1000 games +13,134 +- 3,569 score, 32768 +1.10 +- 0.71; ph16 +1.29 +- 0.60; p32 score
  +3,106 +- 1,608; claims unchanged (disputes, late judge, cal6's expert judge). Only stage 1 changes (16384-phase
  first half above sum 20480 and 32768-phase roots whose view falls there), so a refit touches the late / top maps
  and the odds value term in that range only.
```
