# Workstream scorecard: analysis regression suite (REPORT)

Copied by the coordinator from results/scorecard/report.txt.

```
scorecard notes (workstream scorecard, 2026-10-07), newest last. For cal7/integ: the GAME-LEVEL CHECK comes first.

01:15 GAME-LEVEL CONSISTENCY OF THE PER-MOVE REAL LOSSES (scripts/scorecard_games.py; coordinator's request)
  Data: the curated games (dataset_build positions, split into games as calib_personal_real.py), analysed by the
  "now" engine (results/human_ds_v6b/analysis.jsonl, best-notables + best.cfg = v6b; installed model at 01:03 =
  results/scorecard/now/model.txt = model_v6b) and the "start" engine (results/human_ds/analysis.jsonl, best_v5, model
  results/calib/model_v5_humanmaps.txt). Review rules: reference move = loss 0; stage maps by the real top tile;
  played-expert map for the player's own move from a real 16384; block positions not judged ("now").
  1. Milestone stretches (first position with top M -> first with 2M = success, or an observed death; censored
     stretches left out): kept = prod(1 - est. real loss of the played moves). If the losses were exact expected
     relative losses of the engine-continuation chance V, sum_succ 1/kept = sum_all V0 (martingale): R = 1, a bit
     above 1 for success-selected videos. Results (R with kept floored at 0.01; results/scorecard/{now,start}/games.txt):
       expert 16384 (5 known stretches, all reached 32768; 14 censored): NOW kept median 0.010 (p10 0.003), R 93;
         START (lenient played-expert map) kept median 0.81, R 3.5.  -> "now" says the experts kept ~1% of their
         chances over the 16384 phase, yet all reached 32768: per-move losses x ~3000 moves do not compound.
       NOW: -ln(kept) per 100 judged moves for experts at 16384 = 0.62 (chances halve every ~110 moves); share of it by
         the played move's claimed value loss: <0.3% 1, 0.3-1% 18, 1-3% 17, 3-10% 19, 10-30% 31, 30%+ 13 (%) - more
         than a third comes from claims below 3% that the maps turn into 0.5-2.7% each.
       Other tiers / stages (small samples, 4-30 known stretches): R 0.3-5 (intermediate 1024: 4.6, strong 2048: 3.4,
         strong 4096: 1.3; expert 4096: 17 from one stretch) - roughly consistent below 16384.
  2. Bellman drift along the players' own paths (every consecutive analysed move, no outcome needed, 93k moves): the
     claimed value loss of the played move, (V_t - v_played)/max(|V_t|, 100k), vs what the next position's value says,
     e = (V_{t+1} - (v_played - reward))/scale (zero on average if the values were consistent along the path).
     e for the best move played = the search's one-step optimism (+0.27% experts top, +0.31% late, +0.77% early).
     Beyond that baseline, the next position's value RECOVERS a large share of the claimed loss (NOW, v6b values):
       experts 16384+ (30,684 moves): claims 0.3-1% -> 30% recovered, 1-3% -> 38%, 3-10% -> 44%, 10-30% -> 55%,
         30%+ -> 41%; all players early: 1-3% 54%, 3-10% 48%, 10-30% 39%; late: 39%, 41%, 38%.
     -> ~40-55% of a PLAYED move's claimed value loss is estimation error that the engine itself reverses one move
       later (regression to the mean: a claim is large partly because the played move's afterstate was undervalued).
  3. Played vs other moves on the rollout truth (unselected real positions human300 + late300 + j1200, H=1000, the
     unbiased measure (q_ref - q_move)/max(|q_ref|, 100k) against the analysis' reference move, now/v6b values):
       PLAYED moves, all stages: claim 0.3-1% -> real -0.0 +- 0.8 (n=89); 1-3% -> -0.1 +- 0.6 (91); 3-10% -> -3.3 +- 1.2
         (84); 10-30% -> +4.6 +- 2.5 (28, mean claim 16%); 30%+ -> +57 +- 4 (7). Top stage only (n 7-17 per bin):
         1-3% -> -0.6 +- 5, 3-10% -> -11 +- 6, 10-30% -> +9 +- 8: the maps give 3.0 / 5.8 / 14 there.
       OTHER (not played) moves, top stage: 1-3% -> +1.7 +- 1.2 (map 3.0), 3-10% -> +3.1 +- 1.6 (map 5.7), 10-30% ->
         +19.6 +- 1.5 (map 18.6), 30%+ -> +74 (map 68): the all-move maps fit the alternatives, not the player's choice.
     The low end of the top / played-expert maps (value loss 0.3-3% -> real 0.5-2.7%) is not supported: on played
     moves the measured loss is ~0 up to ~10% claims in every stage (the expert disputes, selected by best_v5's claims,
     are the exception: snake experts' 10-30% claims -> 14.8% real with the ENGINE continuing).
  WHY: the real losses are measured with the ENGINE continuing. For players who play their own (often different)
  plan well - experts in the 16384+ phase - the engine-continuation loss of their move is real for the engine, not
  for them: their games show it (1., 2.). Below 16384 the early/late maps are already ~0 for claims < 10%, so only the
  16384+ maps (top, played-expert) compound badly.
  SUGGESTED CORRECTION (for integ / cal7; nothing installed by me):
   a. Reviews (the PLAYER's move) need played-move maps, fitted on played moves only with the unbiased measure against
      the reference move (fit_lossmap2.py uses max-over-moves minus a constant noise floor: that leaves the low end
      inflated). On current data they are ~0 below 10% claims in all stages; keep the all-move maps for ranking the
      alternatives (what each OTHER move would cost).
   b. 16384+ played moves: shrink hard, and accept a map only if the game-level check passes. Tested on the expert
      16384 stretches (results/scorecard/now/games_candidate.txt): map 0 below 10%, 20% -> 2%, 30% -> 5%, 45% -> 12%,
      65% -> 30% gives kept median 0.66, R 3.8 (plausible with success-selected videos); the milder 0 below 3%,
      10% -> 2%, 20% -> 6%, 30% -> 12% still gives kept median 0.28, R 8.3. Only 5 known expert stretches: use the
      Bellman drift (2.) as the data-rich check (claims should be shrunk by at least its recovered share, ~40-55%).
   c. Keep a separate, clearly named "engine-continuation loss" (what the move would cost if the engine took over) -
      that is what the rollouts measure and what the near-identity v6b map gets right per move.
   d. Make the game-level check (scorecard_games.py: R per tier and stage, drift recovered share) an acceptance test
      for any new map; cal7's 128-256-playout measurements will sharpen the low end of 3.

01:40 UPDATE of the game-level check with the FULL engine (exact tables incl. block tables) on the 16384+ positions
  (scripts/scorecard_human16k.sh now "--weights weights/best_v6b.w": all 47,392 curated 16384+ positions re-analysed on
  the instance in ~1 min; scorecard_games.py --full16k results/scorecard/now/human16k.jsonl, which also applies the
  table map to table-decided moves as analyze does): expert 16384 stretches: kept median 0.004 (R 93, capped) - worse
  than without tables, because the TABLE MAP now adds losses: 11-16% of -ln(kept) comes from moves whose value loss is
  < 0.3% but whose exact-table success probability is lower than the table move's (the table map turns a 5% table
  loss into ~3.5% real). The candidate top/played map alone then only reaches kept 0.07, R 66 -> a played-move
  correction must cover the table map too (the same played-vs-other selection applies to it; it was fitted on all 411
  table move pairs). Drift with the full engine, experts top (35,746 moves): recovered 42% (claims 1-3%), 35% (3-10%),
  47% (10-30%), 38% (30%+).

01:45 THE SCORECARD (deliverable)
  scripts/scorecard_prep.py (once) -> results/scorecard/inputs (2,410 rollout-judged real positions = human300 +
    late300 + j1200 unselected + jx + jold expert decisions; 632 odds-truth positions incl. 200 fresh (truth3), the
    near-dead and a fresh board; the 210 expert decisions; 450 real + 4,553 fuzz boards for invariants / latency).
  scripts/scorecard.sh NAME "ENGINE FLAGS" MODEL PERSONAL [HUMAN_ANALYSIS] [PLAIN=1] [FORCE=1] -> results/scorecard/
    NAME.txt + NAME/{metrics,invariants,personal,games,tiers}.json; instance part ~1 min (~/2048_score), laptop part
    ~3 min. Pieces: scorecard_remote.sh (analyze with tables on the inputs), scorecard_eval.py (robustness, loss maps,
    experts' moves, raw claims, late claims, odds - all on analyze's own output and reference move, unbiased rollout
    measure), scorecard_played.py (player's move vs alternatives), scorecard_games.py (game-level check + Bellman
    drift), scorecard_personal.py (real outcomes), scorecard_invariants.py (fuzz_check answers: by-design issues of the
    new features excluded, latency without the engine-load answer), human_tiers.py, calib_personal_real.py.
  scripts/scorecard_compare.py start now > results/scorecard/compare.txt (side-by-side).
  Runs: start = best_v5 (--block-from 99: no block tables), model_v5_humanmaps, personal v1, PLAIN (no abstention /
    table-aware claims), human_ds analysis. now (01:34) = best_v6b, weights/calib/model.txt (md5 d1a4f045 = integ's
    model_v6b), personal.txt (md5 5ceafb02 = hm's personal_v3), block tables, human_ds_v6b analysis.
  START -> NOW (results/scorecard/compare.txt):
    robustness (engine move significantly worse than the rollout best, 1,800 unselected real positions): 15 -> 16
      (0.8 -> 0.9%: noise level, unchanged).
    loss maps, RMSE x100 of the estimated real loss of non-reference moves (unbiased measure; NOW is partly in-sample:
      its maps were fitted on these judges): early 6.39 -> 4.19, late 6.91 -> 6.27, top 19.2 -> 17.3, table 19.5 ->
      18.7, all 13.0 -> 11.7. Bins: start's early map said 14.8% where 71.6% was measured (big early blunders), now
      20.7 vs 5.6 in [10-30) (n=17) and 57.5 vs 69.8 above 30%; top [1-3) est 1.9 vs -0.9 measured, [3-10) 5.5 vs 2.1.
    experts' own moves at 16384+ (jx + jold, engine continuing): snake experts mean est 3.3 -> 10.8 vs measured 8.6 /
      10.5 (start hid real engine-continuation losses; now calibrated per move); blunder calls on confirmed 22/54 ->
      45/52, on refuted 8/229 -> 46/175 (refuted = within 1 se: noisy truth, selection by best_v5's claims).
    raw claims > 10% on the 210 expert decisions (H=1000): block player false 67/85 -> 6/85 (+32 abstained), snake
      experts false 22/27 -> 12/27, kept 12/12 -> 10/12. Unselected late positions: Spearman 0.679 -> 0.687.
    odds: truth3 (200 fresh real positions) P(16384) MAE 0.100 -> 0.066, log-loss 0.442 -> 0.311; tight 0.128 -> 0.079;
      P(32768) (r15) MAE 0.172 -> 0.136; near-dead 0.823 both (0.850 measured); fresh board P(32768) 0.592 vs best_v6b's
      62.9% benchmark (the base rates are still best_v5's: refit due, cal7).
    personal odds vs real outcomes (2x tile): log-loss 0.648 -> 0.434, Brier 0.222 -> 0.138, AUC 0.770 -> 0.864;
      4x: 1.379 -> 0.656, AUC 0.616 -> 0.807 (mean predicted 0.674 vs observed 0.867: still pessimistic).
    game-level check (experts, 16384 stretches): kept median 0.81 -> 0.010 (full engine 0.004), R 3.5 -> 93: NOW IS
      STRICTER ON EXPERTS THAN THEIR GAMES ALLOW (see 01:15 / 01:40).
    tiers (best/good, inacc/mist/blund per 100): expert 99.4% 0.27/0.14/0.14 -> 88.8% 8.51/1.54/1.14 (inconsistent with
      their games, as above); strong 96.2% 3.68/0.16/0.09 -> 99.6% 0.36/0.00/0.05 (the old late map overstated
      2048-8192); novice / intermediate ~unchanged; warnings/100 (now only): 1.94 / 1.15 / 1.15 / 1.97.
    invariants (real violations; fuzz_check's no_reason / real_loss_monotone / text_not_tile excluded where the new
      features cause them by design): no tables 0 (real) and 5 (fuzz: 4 boards with 16 distinct tiles "not a board",
      1 reason_merge) in both; with tables NOW 11 / 33 - NO REASON for moves without a table p in BLOCK-table
      positions (moves that break the block get real_loss from the value map but no reason; 11 of 450 real positions)
      -> small fix for integ/pdf.
    latency (per answer, the engine-load answer excluded; laptop without tables / instance with tables): p50 2.8 / 1.6
      ms, p99 25 / 26 ms, max 46-59 / 48 ms on real positions (start the same); fuzz boards with tables max 5.2-5.6 s
      (first build of a k>=6 table formation).
  OTHER FINDINGS
    - fit_lossmap2.py --heldout --compare evaluates the INSTALLED model as two-stage (predict(..., three=False)):
      for a model with lossmap_top it scores lossmap_late on the 16384+ positions. integ's switch log "top: installed
      20.5 -> 17.8" and "the installed top map predicts 3-10% where 25.5% is measured" therefore describe the late map,
      not the installed top map (scorecard_eval.py evaluates each model as analyze uses it).
    - fit_lossmap2.py's measure (rollout loss vs the max over moves minus a constant noise floor) leaves the low end
      inflated; the unbiased measure against the reference move (scorecard_eval.py / scorecard_played.py) is the one
      to fit and check maps with.
    - results/mx/ holds macroxue_src_*.txt (extracts of macroxue's GPL sources): keep them out of anything distributed
      and away from the clean-room workstreams (pdf).
```
