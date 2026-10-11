# Workstream cal7: odds refit for v6b + the expert puzzle (REPORT)

Copied by the coordinator from results/cal7/report.txt.

```
cal7 notes (odds refit for v6b + expert low-end puzzle), 2026-10-07 - newest last
01:15 Jobs on the instance (~/2048_cal7, explicit --weights weights/best_v6b.w: the instance has no best.cfg),
  scripts/study_cal7.sh:
  - lowend (48 threads): results/cal7/lowend.bin = 200 top-stage human decisions (real max >= 16384, block excluded,
    clean; scripts/judge_lowend_select.py on results/human_ds_v6b, round robin over 9 players) stratified by v6b's
    claim of the played move: ctl < 0.05% 40, 0.1-0.3% 30, 0.3-1% 40, 1-3% 40, 3-10% 30, >= 10% 20 (candidates:
    26,822 / 2,338 / 1,997 / 1,192 / 593 / 309 of ~33k top-stage decisions); every legal move, 4 replicate runs x 32
    playouts (CRN across moves within a run), H=1000. Report: scripts/judge_lowend_report.py (FIXED reference = the
    analysis' engine move, paired per replicate: unbiased, no max-selection / noise-floor correction needed).
  - truth (24): P(32768) truth with v6b continuing on cal6's 16384-phase real positions (truth_r15 120, truth2_r15 60);
    P(16384) truth (truth_r14, truth3_r14) needs no rerun: v6b changes only stages 2-3 (sums >= 24576).
  - lapse (28): v6b late lapse games (lapse16c / lapse32 / lapse32b, 800 each) + 600 clean checkpoint games, seed 701.
  Base rates: late's v6b 1000-game benchmark logs (results/bench/late_v6bo2/chunk*.log).
01:20 Scorecard already ran the game-level check (results/scorecard/report.txt 01:15): with the v6b maps the expert
  16384 stretches keep median 1% of their chances (R 93) though all 5 known ones reached 32768 (the start's lenient
  map: 0.81, R 3.5); Bellman drift: 40-55% of a played move's claim is recovered by the next position's value
  (regression to the mean); on unbiased rollout truth, PLAYED moves' real loss is ~0 for claims < 10% in all stages
  (top stage: tiny samples). The lowend run measures the top stage's played moves precisely.
01:22 fit_lossmap2.py --fixed-ref (new; scripts/fit_lossmap2.py): rollout loss against the FIXED reference move (best
  value), unclipped, no noise floor (the max-over-noisy-means measure inflates the low end). Preview on the judge data
  re-valued with v6b (results/integ/reval_v6b: human300 + late300 + j1200 + jx/jold played, block excluded; 80%
  player-bootstrap bands): played_expert 1% -> 0.04% (0-0.9), 3% -> 0.12% (0-2.1), 6% -> 0.12% (0-4.7), 10% -> 6.4%,
  15% -> 13.6%, 20% -> 14.5%, 30%+ -> 16-17% (installed: 1% -> 1.95%, 3% -> 2.68%); top (all non-reference moves)
  1% -> 0.6%, 3% -> 1.75%, 6% -> 2.2%, 10% -> 5.3%, 15% -> 9.3%, 20% -> 18.1%, 30% -> 35% (installed 1.9 / 4.0 / 5.9
  / 8.2 / 11.2 / 19.5 / 35.3); late 1-6% -> 0.08% (installed ~0.6%), early unchanged (~0). Baseline odds truth on
  P(16384) (450 real positions incl. cal6's held-out truth3): installed MAE 0.059, log-loss 0.300 (tight mid
  positions mT/mT3: predicted 0.81/0.79 vs measured 0.77/0.77; v6b changes nothing below sum 24576).
01:28 Game-level check (scripts/scorecard_games.py, results/cal7/games_*.txt) of the expert 16384 milestone (5 known
  stretches, all reached 32768; 14 censored): installed maps kept median 0.010, R 93; with the fixed-ref preview
  maps (override results/cal7/override_preview.txt: played-expert 0 below ~2%, 0.12% at 2-6%, 13.4% at 14%, 16%
  from 28%) kept 0.191, R 8.9 - the low end is fixed (its share of -ln kept drops from 54% to 2%), the remaining
  inflation comes from claims >= 10% (86% of -ln kept). Bellman drift (30,684 expert top moves): 41-56% of a played
  move's claim is recovered by the next position's value at every claim size (3-10%: 2.62 of 5.35; 10-30%: 9.14 of
  16.22; 30%+: 20.2 of 49.3) -> claims of played moves carry regression-to-the-mean inflation of ~half.
01:30 BUG in fit_lossmap2.py's held-out comparison (fixed): the compared ("installed") model was always scored
  2-stage, i.e. with its LATE map in 16384+ positions, even when it has a lossmap_top. So integ's switch log
  (results/integ/switch_v6b.log) "top: installed 20.5 -> new 17.8" and "the installed top map predicts 3-10% where
  25.5% is measured" compared against cal6's LATE map, not its top map. Re-scored on unbiased fixed-ref targets (judge
  data re-valued with v6b): installed (= integ's v6b top map) RMSE 19.0 (fixed-ref refit 19.5); by predicted bin
  [0-1) 0.09 vs 0.26, [1-3) 1.96 vs -0.31 (n=85: low end too high), [3-10) 5.35 vs 4.13, [10-30) 18.8 vs 18.4,
  [30+) 73.9 vs 76.7 -> keep it, lower its low end. Played-expert (installed = integ's near-identity v6b map): [1-3)
  2.05 vs -0.14 (n=95), [3-10) 5.58 vs 1.64 (70), [10-30) 17.3 vs 12.3 (149) -> overpredicts everywhere; the
  fixed-ref refit: [0-1) 0.05 vs -0.03 (330), [3-10) 6.3 vs 9.7 (40), [10-30) 14.2 vs 14.7 (155).
01:38 Coordinator added the code hook: lossmap_table_played (calib.h table_real_loss(p_ref, p_move, played); analyze
  passes played = the reviewed move). Python mirrors: scorecard_eval.py table_map(maps, played) (expert-moves verdicts),
  scorecard_games.py (the player's moves), human_tiers.py (table-decided entries of caches made with tables).
  Played-move table points (scorecard judge set with the full engine, unbiased vs the reference): table loss < 3% ->
  real ~0 (n=130); 3-10% -> 3.4 +- 2.6 (27); 10-30% -> 15.2 +- 1.8 (58, mostly the selected disputes); 30%+ -> 18.9 +-
  4.1 (26); other moves: < 10% ~0, 10-30% 8.5 +- 1.8, 30%+ 31 +- 4.
  Game check (expert 16384 stretches, R / kept median; "full" = with tables, scorecard's human16k.jsonl):
    installed 93 / 0.010 (full 93 / 0.004); fixed-ref played map 8.9 / 0.19; C4 (half the claim above 6%) 5.3 / 0.24,
    full + T1 table map 7.1 / 0.21; C3 4.0 / 0.34, full + T1 5.9 / 0.23; S (played 0 below 10%, 20% -> 2%, 30% -> 5%,
    45% -> 12%, 65% -> 30%; table played 0 below 10%, 20% -> 2%, 30% -> 5%, 50% -> 12%, 100% -> 35%) 2.48 / 0.66,
    full 3.09 / 0.54; M (milder: 0 below 8%, 15% -> 2%, 20% -> 4%, 30% -> 8%, 45% -> 15%; table 15% -> 2%, 30% -> 6%,
    50% -> 14%) 2.85 / 0.52, full 3.73 / 0.42.
01:42 Expert-move verdicts (scorecard_eval section C on jx + jold, engine-continuation truth; scripts/calib_cand_eval.sh
  reuses the "now" analyses with a candidate model): snake experts' blunder calls, false alarms on refuted / detections
  on confirmed: start (v5 lenient) 8/229, 22/54; installed now 46/175, 45/52 (mean est 10.8 vs measured 10.5: the
  engine-continuation loss is calibrated per move); S 8/175, 19/52 (mean est 3.9); M 9/175, 20/52 (4.6). The
  played maps cannot be both: per move, big claims on experts' played moves are real for the ENGINE continuing (10-30%
  claims -> ~15% on the selected disputes), but they do not compound along the experts' own paths (R 93 with the
  near-identity map). For reviews of the player's own moves the game-consistent maps (S) are the right ones; the
  engine-continuation loss belongs to "what if the engine took over" (alternatives: top / table maps).
01:50 Draft review maps "S" (results/cal7/override_final_maps.txt): lossmap_played_expert 0 below 10%, 20% -> 2%, 30% ->
  5%, 45% -> 12%, 65% -> 30%, 100% -> 60%; lossmap_table_played 0 below 10%, 20% -> 2%, 30% -> 5%, 50% -> 12%, 100%
  -> 35%; warn 16384+ 0.05 -> 0.20. Tiers with S (human_ds_v6b): expert best/good 99.3%, 0.36 / 0.14 / 0.10 inacc /
  mist / blund per 100, warnings 0.48/100 (installed: 88.8%, 8.51 / 1.54 / 1.14, warnings 1.97); other tiers unchanged.
  analyze --selftest passes with it. Odds: P(32768) truth on cal6's truth2_r15 (60 real 16384-phase positions) with
  v6b continuing 0.556 vs 0.498 with v5 (+5.8 points) -> the installed odds (v5 base rates, vbar only rescaled) are
  too low for v6b at the 32768 target: the refit is needed.
02:05 P(32768) truth with v6b continuing done (results/cal7/truth/truth_r15.tsv 120 + truth2_r15.tsv 60 real 16384-phase
  positions, 32 playouts each): measured 0.589 / 0.556 vs 0.546 / 0.498 with v5 continuing (+4.2 / +5.8 points).
  Installed odds on it: mean predicted 0.538 vs measured 0.578, MAE 0.137, log-loss 0.643 (tight lT2: 0.399 vs 0.484;
  predicted < 0.5: 0.299 vs 0.395).
02:25 LOW-END MEASUREMENT (preliminary, 3 of 4 replicates; scripts/judge_lowend_report.py): 200 unselected top-stage human
  decisions stratified by v6b's claim, paired rollouts vs a FIXED reference (no max-selection), 96 playouts per move.
  PLAYED moves: claims 0.1-0.3% -> +0.3% (80% band -0.6..1.2), 0.3-0.6% -> +0.1, 1-2% -> +0.0, 2-3% -> -0.2,
  3-6% -> +1.7 (-0.3..4.1), 6-10% -> +7.4 (4.2..10.6), 10-20% -> +12.0 (4.7..20.1). ALL non-reference moves: < 3% ~0,
  3-6% 1.4, 6-10% 7.7, 10-20% 12.2, 20-40% 34.7, 40%+ 73.8 (installed top map: 2.6 at 1.5%, 4.6 at 4%, 10.7 at 14.5%,
  32.5 at 28%, 80.9 at 70%). => the low end of the top and played-expert maps (claims < 3%) is ~0: the installed
  0.5-2.7% was the max-over-noisy-means bias. Beyond ~6% the ENGINE-continuation loss of an expert's played move is
  ~the claim (unselected moves too) - per move the near-identity map is right for "if the engine took over"; at the
  game level it is not (R 8.9 with the fixed-ref map): experts' own continuation recovers what the engine's does not.
02:30 Top map (alternatives): the installed (integ's v6b) top map is better held-out than a fixed-ref refit (judge +
  low-end data, RMSE 20.69 vs 21.66: the refit underpredicts 10-30%), but its low end is too high ([1-3) predicted
  1.98 vs measured -0.04, n=103). Candidate top2 = installed with the low end zeroed (knots 0.56% -> 0, 1.8% -> 0.4%,
  5.7% -> 4.5%, rest unchanged): RMSE 20.70, bins [1-3) 1.94 vs 1.72, [3-10) 6.28 vs 4.43, [10-30) 19.5 vs 20.7.
  FINAL CANDIDATE results/cal7/model_v7_final_candidate.txt = v7 odds + top2 + S played maps + warn 16384+ 0.20 (the
  rest as installed): selftest 0 failures; game check expert 16384 R 2.48 / kept 0.66 (no tables), R 3.09 / 0.54 (with
  tables); other tiers unchanged (they use the early/late maps); snake experts' blunder calls: false alarms 8/175,
  detections 19/52 (start 8/229, 22/54; installed 46/175, 45/52).
02:36 LOW-END FINAL (4 replicates = 128 paired playouts per move; results/cal7/lowend_report.txt; merged judge file
  results/cal7/lowend_merged.tsv): PLAYED top-stage moves (166, unselected, stratified by v6b's claim): < 3% -> ~0
  (bins -0.5..+0.2%, one noisy bin), 3-6% -> 1.75% (-0.1..3.7), 6-10% -> 6.7% (3.4..10.0), 10-20% -> 11.4% (4.0..19.6);
  all non-reference moves: < 3% ~0, 3-6% 1.6, 6-10% 7.0, 10-20% 12.1, 20-40% 34.7, 40%+ 73.3. Top map candidate top2
  (installed with the low end zeroed) held-out on judge + low-end data: RMSE 20.71 (installed 20.71), bins [1-3) 1.94
  vs 1.76 (installed 1.98 vs -0.02), [3-10) 6.28 vs 4.49 (5.33 vs 3.71), [10-30) 19.5 vs 20.6 (19.1 vs 20.4).
WHY PER-MOVE LOSSES DO NOT COMPOUND FOR EXPERTS (the explanation): (1) the rollouts measure the ENGINE-continuation loss:
  how much worse the engine does when it takes over after the player's move instead of its own; unbiased and unselected,
  for experts' top-stage moves it is ~0 below a 3% claim and ~the claim from ~6% on. (2) The game check asks whether the
  engine's own odds along the expert's path fall by the claimed losses: they do not - with the per-move map the experts
  "kept" a median 19% of their chances in stretches they all won (R 8.9). (3) The Bellman drift explains the gap: after
  a played move with a claimed loss, the next position's own value recovers 35-55% of it - the engine undervalued the
  expert's afterstate, and in the rollouts the engine then plays that unfamiliar position worse than the expert does.
  So for players who carry out their own plan well (experts, 16384+), the engine-continuation loss is a statement about
  the engine, not about the player. Reviews of the player's own 16384+ moves therefore use game-consistent maps (S:
  0 below 10%, 20% -> 2%, 30% -> 5%, 45% -> 12%; table S), and the engine-continuation loss stays in the alternatives'
  maps (top / table) - "what this move would cost if the engine took over".
02:38 65536 target: none fitted - in 2,898 v6b games (600 clean, 2,298 lapse continuations from the 16384 / 32768
  phases) and the 1000-game benchmark, no game reached 65536: the engine's own P(65536) is < 0.1% from any position in
  the data, so an engine-odds target for 65536 would carry no information (expert-level 65536 odds would need a player
  that converts the 32768 phase).
02:45 HELD-OUT P(32768) (results/cal7/truth4: 160 NEW real 16384-phase positions, v6b continuing, 32 playouts; used in no
  fit): installed LL 0.764 / MAE 0.148 -> v7 0.737 / 0.145 (tight lT4: 0.903 -> 0.849; predicted 0.375 / 0.394 vs
  measured 0.474). Both still under-predict tight 16384-phase positions (predicted < 0.5: 0.28 vs 0.45-0.47 measured).
  A real-position refit of the 32768 slope on all 340 truth positions (cal6 sets with v6b + truth4) loses out of sample
  (player CV: LL 0.684 -> 0.745) -> base slopes kept (open issue: tight late positions, only 6 players reach 16384).
  Fresh board: P(32768) 0.592 -> 0.609 (v6b benchmark 0.629); P(16384) and lower targets unchanged (MAE 0.059 / LL
  0.300 on 450 real positions incl. held-out truth3); near-dead board P(16384) 0.823 -> 0.824 (measured 0.850).
02:45 INSTALLED weights/calib/model.txt = results/calib/model_v7_cal7.txt (md5 27387cf6; previous model:
  results/calib/model_before_cal7.txt = integ's model_v6b, md5 d1a4f045): odds v7 for best_v6b (base rates from v6b's
  1000-game benchmark + 2,898 v6b lapse / clean checkpoint games (results/cal7/lapse/s701_*); value slopes: 8192 / 16384
  refit on real positions (16384 player-CV log-loss 0.352 -> 0.286), 32768 synthetic); lossmap_top = integ's with the
  low end zeroed; lossmap_played_expert and lossmap_table_played = the game-consistent review maps S (reviews of the
  player's own 16384+ moves); warn 0.15 0.05 0.05 0.20 (16384+ 0.05 -> 0.20); lossmap, lossmap_late, lossmap_own,
  lossmap_table unchanged. analyze --selftest 0 failures; tiers -> results/human_ds_v6b/tiers.json.
  Scorecard rerun (FORCE=1 scripts/scorecard.sh now "--weights weights/best_v6b.w" weights/calib/model.txt
  weights/calib/personal.txt results/human_ds_v6b/analysis.jsonl; results/scorecard/now.txt, compare.txt; the 01:34
  "now" is kept as results/scorecard/now_0134*): game check experts' 16384 stretches kept median 0.657, R 2.5 (full
  engine with tables: 0.544, R 3.09; installed before: 0.010 / 0.004, R 93); snake experts' blunder calls false alarms
  8/175, detections 19/52 (before 46/175, 45/52; start 8/229, 22/54); loss-map RMSE all 11.68 (start 13.00); odds r15
  MAE 0.139 / LL 0.622 (start 0.172 / 0.706), truth3 0.066 / 0.311; tiers expert 99.3% best/good, 0.36 / 0.14 / 0.10
  inacc / mist / blund, 0.48 warnings per 100 (before 88.8%, 8.51 / 1.54 / 1.14, 1.97). No cal7 job left running.
```
