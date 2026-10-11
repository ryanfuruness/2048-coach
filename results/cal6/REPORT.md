# Workstream cal6: calibration at scale (REPORT)

Copied by the coordinator from results/cal6/report.txt (the subagent could not create REPORT.md).

```
cal6 notes (calibration at scale), 2026-10-06/07 - progress log, newest last; the final report goes to the coordinator

22:00 Jobs on the instance (~/2048_cal6, 48 threads): real-human judge on 1200 new positions (judge_select.py,
  player round robin: early <=1024 400 / 67 players, mid 2048-8192 400 / 30, top >=16384 400 / 9; all moves, 32
  playouts, H=1000, full engine; judge_cal6.sh, chunks in results/cal6/j1200); 400 more expert decisions (xexpert:
  250 disputes >10% + 150 claims 2-10%, 16384+) and the old 150 disputes + 60 controls again at H=1000 (jold); odds
  truth on real positions (truth_r14: 220 positions, 32 engine playouts to 16384; truth_r15 + truth2_r15: 180
  16384-phase positions to 32768); personal truth (pers_r9..r15: 280 positions x soft t 0.003/0.01/0.03/0.1, to 2x and
  4x the tile); skill map (calib_softmap.sh: soft:t games reviewed by build/analyze --review); late lapse + clean games
  (study_cal6.sh lapse, G=400/500). The instance is ~6x faster per thread than the laptop (memory-bound n-tuples).
22:30 Odds: fit_calib.py was non-deterministic (Python's salted hash() split train/test -> the regularisation and the
  value slopes changed between runs: 16384 early slope 0.39 in v5 vs 2.24-3.48 in reruns) -> crc32 game ids + 5-fold
  CV by game; --slope-bands (3 bands: <4096, 4096-16384, >=16384, hat-interpolated exactly as calib.h).
  Real truth (r14, P(16384)): v5 is fine except TIGHT 4096-8192 positions: measured 0.765, v5 predicted 0.943 (MAE
  0.189). fit_calib_real.py refits the band slopes on real positions (inputs from analyze --odds-inputs: surviving
  spawns' value + survival, as analyze computes odds), 5-fold CV by PLAYER: 16384: log-loss 0.354 -> 0.285, MAE
  0.072 -> 0.052 (tight mid: 0.154 -> 0.091); 8192: 0.177 -> 0.142. 32768 (180 positions, 6 players): the refit
  does not beat the synthetic slope out of sample -> kept.
22:40 Loss maps (fit_lossmap2.py; held-out 5 folds by video vs the installed maps): early RMSE 5.38 -> 3.64, late
  5.83 -> 5.43, top 18.3 -> 17.8; the installed early map underestimated big blunders (predicted 14% vs measured
  71% in its 10-30% bin); the installed late map (fitted on 2048+ incl. 16384+ experts) overstated 2048-8192 losses
  -> 3 stages (early <=1024, late 2048-8192, top >=16384: calib.h lossmap_top, analyze stage 2).
22:50 Personal: the soft:t model transfers to REAL positions (soft playouts from 280 real positions: 4x MAE
  0.04-0.06, 2x 0.05-0.12). But the review's fitted skill t and the soft player's t are different scales (soft 0.01
  reviews as 0.015 / 0.022 / 0.018 in phases 0/1/2) -> skill map (pskillmap lines, PersonalModel::soft_t, analyze
  converts a reviewed skill before using the model; --personal-model FILE). Real outcomes (curated games, 83 games
  with known outcome): 2x milestone log-loss 0.622 -> 0.503, Brier 0.216 -> 0.164, AUC 0.77 -> 0.85; still too
  pessimistic for intermediate/strong (0.68 vs 0.94 observed) - YouTube games are selected on success (the tier IS
  the largest tile reached), so absolute levels cannot be validated on this data; novices: 0.74 vs 0.60.
23:20 Coordinator check (coach: early map too lenient for big losses): in early positions the loss in CHANCES
  tracks the score loss (30-45% value loss: score 17.2%, extra deaths within 1000 moves 17.2%; 45%+: 71.5% / 70.3%;
  max 128-512: 30-45% -> 32%, 45%+ -> 67%); the installed early map gave ~6-10% there, the new early map gives
  10% at 30%, 36% at 45%, 65% at 65% -> fixed by the refit.
23:30 judge1200 complete. Robustness on the 1200 new real positions (engine move significantly worse than the
  rollout best, z=2): early 4/400, mid 3/400, top 5/400 = 12/1200 (1.0%), at the noise level of the test.
  Maps (5-fold by video vs installed, RMSE x100): early 5.37 -> 3.45, late 5.82 -> 5.42, top 19.0 -> 18.4, all
  11.03 -> 10.50. Top map (615 positions, 9 players, 80% player-bootstrap band): 1% -> 1.5% (0.9-2.7), 3% -> 2.6%,
  10% -> 5.6% (4.2-8.9), 20% -> 14.4% (12.6-19.4), 30% -> 25.5%, 45% -> 45.7%, 65% -> 72.6%.
  New expert disputes (xexpert, H=1000, player round robin, 250 claims > 10%): refuted 158 / unclear 48 / confirmed 44,
  claimed 23.6% -> real 10.4%; strongly player-dependent: d4Nf6Bg5 21.6% -> 1.3% (5 of 55 confirmed; the block
  formation player per mx), BloodyMe77 20.8% -> 16.3%, perfect. 33.3% -> 21.8%, Let's Play 25.7% -> 6.5%,
  Stefan Popescu 18.6% -> 4.8%; claims 2-10% (125): 4.7% -> 1.3%. A played-expert map refit on all expert played
  moves (H=1000) does NOT beat the installed one out of sample (RMSE 10.95 vs 10.93) and would make experts look
  implausibly bad (best/good 79.9%, 12 inaccuracies/100) under the engine's own continuation -> KEEP the installed
  lenient map; the discount is formation-specific (block formation), not expert-general.
00:40 INSTALLED (held-out wins only): weights/calib/model.txt = results/calib/model_v6_cal6.txt (odds v6: synthetic
  base with 3 slope bands + real-position slopes for 8192/16384, 32768 synthetic; 3-stage loss maps early/late/top;
  lossmap_table; the installed lenient lossmap_played_expert KEPT), weights/calib/model.json = model_v6_cal6.json,
  weights/calib/personal.txt = results/calib/personal_v2.txt (v1 + pskillmap). Previous files:
  results/calib/model_v5_installed_before_cal6.txt, personal_v1_installed_before_cal6.txt. build/analyze rebuilt,
  --selftest 0 failures; scripts/human_tiers.py -> results/human_ds/tiers.json (copy results/cal6/tiers_v6.json).
  Code: calib.h (lossmap_top, lossmap_table + table_real_loss, interp_map, PersonalModel skillmap/soft_t, future()
  clamped >= 0), analyze.cpp (3-stage + table real loss, odds/personal on the REAL max tile and sum, --personal-model,
  --odds-inputs), fit_calib.py (deterministic crc32 ids, 5-fold CV, --slope-bands, ratio >= 0).
  Fresh held-out truth (truth3: 200 new real positions, used in no fit): P(16384) MAE v5 0.100 -> v6 0.066, log-loss
  0.442 -> 0.311 (tight 4096-8192: v5 predicted 0.944 vs measured 0.769, v6 0.789); P(8192) MAE 0.052 -> 0.041.
  Table-decided positions (411 move pairs): (p_ref - p)/p_ref through lossmap_table RMSE 13.7 vs value map 14.5.

REFIT RECIPE for a new engine (e.g. weights/best_v6.w). E="--weights weights/best_v6.w --stages <its stages>" (the
engine flags of play; analyze/rollout/messy parse the same). Run on the instance in ~/2048_cal6 (push code first);
results/... paths as below. The rollout truth is reused (measured with best_v5's continuation): only values/claims are
recomputed. CAVEAT: base rates and the late truth ARE the engine's own success rates - if the new engine converts the
16384/32768 phases better, also redo steps 1b and 2b (~1.5 h on 16 threads).
 1. odds, synthetic part:
    a. ENGINE="$E" G=400 GC=500 SEED=602 T=16 scripts/study_cal6.sh lapse   (late lapses + 500 clean checkpoint games)
    b. a 1000-game benchmark log of the new engine (scripts/bench.sh NAME W STAGES 1000 100 T): the base rates
    c. python3 scripts/fit_calib.py results/calib/model_v7_base.json --umode-log --slope-bands 12,14
         --base-log <new bench chunk logs> --clean results/cal6/lapse/s602_cleancp.tsv results/cal6/lapse/s602_*.tsv
       (the old s201/s301/p2 files carry best_v5 values and outcomes: leave them out for a new engine)
 2. odds, real slopes: a. python3 scripts/fit_calib_real.py results/calib/model_v7_base.json results/calib/model_v7.txt
       --analyze build/analyze --engine "$E"   (truth: results/cal6/truth*.tsv + truth/*.tsv, tight30; keeps a
       target's base slopes when the refit loses out of sample)
    b. (if the engine is stronger late) ENGINE="$E" T=16 scripts/study_cal6.sh truth, then repeat 2a
    check: python3 scripts/calib_truth_report.py --analyze build/analyze --engine "$E" weights/calib/model.txt
       results/calib/model_v7.txt  (+ the truth3 held-out check in the 00:40 entry)
 3. loss maps: python3 scripts/judge_revalue.py results/cal6/reval "$E" results/judge/human300_h1000.tsv
       results/judge/late300_h1000.tsv results/cal6/j1200/judge1200_*.tsv results/cal6/jx/xexpert_*.tsv
    python3 scripts/fit_lossmap2.py --boot 200 --boot-players --heldout --compare weights/calib/model.txt
       --model results/calib/model_v7.txt results/cal6/reval/human300_h1000.tsv results/cal6/reval/late300_h1000.tsv
       results/cal6/reval/judge1200_*.tsv   (then restore the lenient played-expert line:
       grep '^lossmap_played_expert' weights/calib/model.txt >> after removing the refit one; the chunk offsets need
       the original file names, which judge_revalue keeps)
    table map: ./build/analyze --preset best $E --stdin < results/cal6/table_boards.txt > results/cal6/table_v7.jsonl;
       python3 scripts/fit_lossmap_table.py results/cal6/table_v7.jsonl --model results/calib/model_v7.txt
       results/judge/late300_h1000.tsv results/cal6/j1200/judge1200_*.tsv results/cal6/jx/xexpert_*.tsv
 4. personal: ENGINE="$E" scripts/study_personal.sh-equivalent soft:t games (messy --preset best-notables $E --policy
       soft:t=X --checkpoints ... --values, X = 0.003 0.01 0.03 0.1, 1000 games each) -> python3 scripts/fit_personal.py
       results/calib/personal_v3.txt results/personal/soft_*.tsv; skill map: rm results/cal6/softmap/g_*;
       ENGINE="$E" scripts/calib_softmap.sh 72 16; python3 scripts/calib_softmap.py --append results/calib/personal_v3.txt
    check: python3 scripts/calib_pers_report.py --model results/calib/personal_v3.txt (after ENGINE="$E"
       scripts/calib_pers_run.sh 16 and _run2.sh 16 into a fresh results/cal6/pers)
 5. played-expert map: keep the lenient line. If it is ever refit: only clean played moves in 16384+ positions, and
    drop positions where blk::block_formation(b, 0, real_rank) fires (src/block.h; their claims carry no information).
 6. install: cp results/calib/model_v7.txt weights/calib/model.txt; cp results/calib/personal_v3.txt
    weights/calib/personal.txt; ./build/analyze --preset best-notables --selftest; python3 scripts/human_tiers.py
```
