# Workstream hm: human move model and personal odds v3 (REPORT)

Copied by the coordinator from results/hm/report.txt.

```
hm notes (human move model), 2026-10-07 - progress log, newest last; the final report goes to the coordinator

00:20 Data (scripts/hm_build.py -> results/hm/data.npz): 114,970 clean decisions (human_tiers.py filters), 80 players;
  per move: 1-ply value exactly as soft_move (build_hm/hm_tool), relative 1-ply loss (soft_move's scale), 2-ply value
  (spawn expectation of the best reply), death share (spawns with no reply), concept features (explain.h) of the
  afterstate and the position, the analysis' search loss, previous two moves of the player.
00:45 Models (scripts/hm_fit.py; conditional logit over legal moves + lapse eps; skill theta per player with a N(0,1)
  prior; CV: 5 folds by player, test players' skill fitted on the first half of their decisions, NLL on the second):
    model                 nll/decision   by stage (<=512, 1024-2048, 4096-8192, 16384+)    by tier (nov, int, str, exp)
    soft (1-ply softmax)     1.0099      1.146 0.928 0.909 1.132                          1.176 0.944 0.902 1.127
    soft on search losses    0.9575      1.184 0.997 0.945 0.900                          1.190 1.018 0.938 0.902
    soft on 2-ply losses     1.0675      (2-ply explains human moves WORSE than 1-ply)
    hinge (non-linear 1-ply) 1.0162      (alone no gain)
    full (hinge+structure+habits, one skill)          0.8058
    full2 (separate structure skill per player)       0.7831
    full_tied (structure skill = exp(ga + gb*theta))  0.7723
    full_tied_death (+ death share after the move)    0.7713  <- BEST (1.007 0.733 0.687 0.830; 1.115 0.743 0.675 0.831)
    stage-specific variants: no gain (0.775-0.785); 2-ply value instead of 1-ply: no gain (0.7732)
  -> 24% lower NLL than the softmax player; the structure/habit features carry most of it: corner_lost -2.1,
  perp_away (pulling the wall line off its wall) -2.0, big_off_edge -1.6, death -5.4, merge_size +4.5, trapped -0.9,
  moved -0.9, chain_len +0.8, alternate +0.43, repeat +0.11; the value part flattens above 3% loss (slopes 6.3, 10.1,
  11.1, 8.9, 6.0, 0 per unit loss on the hinge segments 0/0.3/1/3/10/30%): humans hardly separate a 10% from a 40%
  1-ply loss - they avoid big losses through structure, not value. Skill: structure weight exp(0.47 + 2.61 theta),
  value weight exp(theta); tier medians theta: novice -0.86, intermediate -0.24, strong -0.25, expert -0.46.
  Big-mistake rates (moves losing >= 15% by the search, per 100 decisions; predicted / observed): novice 2.36/2.23;
  intermediate 0.51/0.38 (<=512), 1.28/1.06 (1024-2048); strong 0.76/0.80, 0.35/0.30, 0.50/0.42; expert 4.09/2.57
  (4096-8192), 3.34/1.37 (16384+: experts see deeper than any 1-ply model; the late game stays the weak spot).
  Near ties (top-2 within 0.2%): P(engine's best) predicted 0.405 vs observed 0.452 (softmax 0.375).
  C++ policy src/human.h (hm::probs / hm::move; weights = results/hm/human_model_v1.txt, scripts/hm_sync_header.py)
  matches the Python fit to 1e-5 on 3,000 positions (build_hm/hm_tool --probs). Bug found and fixed on the way: the
  tool's 2-ply 'death' counted spawns whose best reply had a NEGATIVE network value as deaths.
01:00 GENERATIVE CHECK (the real test of a playout model; scripts/hm_gen.sh + hm_genstats.py: fresh games, board
  statistics by stage, outcomes). Human boards per tier (largest tile 128/256/512/1024/2048): intermediate corner
  0.74/0.88/0.77/0.70/0.90, chain 2.9/3.7/3.3/3.3/4.2, empty 5.5/5.0/4.7/4.1/3.9; strong similar; NOVICES never hold
  the corner (0.00-0.06). The SOFTMAX players never hold the corner early either (corner 0.00 at 128-512, empty
  2.2-2.9: a different style that survives by sharp 1-ply play; own-trajectory moves losing >= 3%: 4.7 per 100 vs
  humans' 17.7) -> the soft:t skill model is not human-like. The human model at its move-level ML skill dies early
  (covariate shift: on its own trajectory it makes 1.5-2.6 big mistakes per 100 moves vs humans' 0.4-1.1); at a
  higher skill (theta 0.3) its boards look like intermediates' (corner 0.85-0.92, chain 3.5-3.9, empty 3.5-5.7) and
  its own-trajectory mistake rates match (>= 3%: 19.7 vs 17.7 / 8.6 vs 6.8; >= 15%: 0.93 vs 0.44 / 0.87 vs 1.06).
  Two habit findings: (1) intermediate/strong/expert players almost never press one direction (median share of the
  least-used direction 0.0-0.3%, legal in 99% of positions; novices 14.5%) but per-player direction biases do NOT
  generalise across a player's videos (CV 0.806 vs 0.771): the habit is per game -> features "share of the move in
  the last 20 moves" (+0.65) and "unused in the last 20 (>= 10 known)" (-1.45): CV 0.7637 (model v2,
  results/hm/human_model_v2.txt, built into src/human.h); (2) more structure weight than the fit makes play rigid and
  WEAKER; strength comes from sharper value judgement -> playout family: value skill s, structure skill min(s, 0.4).
01:20 PERSONAL ODDS v3 (scripts/hm_personal.sh on the instance, ~2 min: 7 skills x 1000 fresh games at checkpoints
  with values + 48 reviewed games per skill for the skill map; scripts/fit_personal.py -> results/calib/
  personal_v3_hm.txt, scripts/hm_skillmap.py adds the pskillmap lines). Keys t = 0.01 exp(-s): 0.018 / 0.012 / 0.008 /
  0.0055 / 0.003 / 0.00135 / 0.0005 reach 2048 in 0/3/15/20/42/73/85% and 8192 in 0/0/0/0/0/2/18% of games. Skill
  map (review-fitted t, phase 0): 0.35 / 0.091 / [0.076] / 0.083 / 0.072 / 0.057 / 0.020 - the range of real players
  (soft players review at 0.006-0.25: sharper per move than humans).
  Real outcomes (scripts/calib_personal_real.py on both models, compared on the 43,580 / 22,727 common positions by
  scripts/hm_pers_compare.py; 80 / 71 games, game-clustered bootstrap):
    2x milestone: log-loss v2 0.452 -> v3 0.374 (diff -0.080, 90% [-0.131, -0.032]), Brier 0.142 -> 0.117, AUC 0.850 ->
      0.862; mean predicted 0.649 -> 0.713 (observed 0.884, success-selected videos)
    4x milestone: log-loss 0.888 -> 0.618 (diff -0.271, [-0.373, -0.165]), Brier 0.317 -> 0.214, AUC 0.622 -> 0.752
    by tier (2x): intermediate 0.350 -> 0.280, strong 0.533 -> 0.431, novice 0.566 -> 0.590 (v3 a bit optimistic for
      novices: predicted 0.632 vs observed 0.585)
01:00 Transfer check (scripts/hm_pers_run.sh on the instance: human-model players continue from cal6's 280 real
  positions to 2x / 4x their tile, 32 playouts, first move = the engine's; scripts/hm_pers_report.py): v3's
  predictions (fitted on fresh-game checkpoints) vs these playouts: MAE 2x 0.057-0.114, 4x 0.044-0.071 by key
  (v2 vs soft playouts: 0.046-0.118 / 0.041-0.059) -> transfers to real positions as well as v2 did.
  Caveat: the phase-0 skill map is steep (review-fitted t 0.057-0.091 spans keys 0.00135-0.012): the softmax review
  statistic separates human-model players poorly early in the game -> rerun with 200 reviewed games per key and a
  finer key grid (skillmap2). Follow-up idea for the analysis: estimate the user's skill with the human model itself
  (ML theta over the user's moves: the model fits moves 24% better than the softmax) instead of the softmax t.
  Code: --human S / --human-model in build/rollout (playouts by the human model), src/coach.cpp --human (players =
  human model, --t values = personal-model keys).
01:15 v3b (final, INSTALLED): 12 keys (adds 0.015 / 0.01 / 0.0065 / 0.004 / 0.002), skill map from 200 reviewed games
  per key (scripts/hm_skillmap.py --dir results/hm/skillmap2, trimmed geometric means instead of grid medians):
  phase 0 0.0005 -> 0.017, 0.00135 -> 0.055, 0.003 -> 0.072, 0.0055 -> 0.089, 0.012 -> 0.123, 0.015 -> 0.244,
  0.018 -> 0.392; phase 1 0.024 ... 0.104; phase 2 0.028 ... 0.083 (still steep in the middle of phase 0).
  v3b vs v3 (common positions): 2x log-loss -0.014 [-0.028, -0.001], 4x -0.034 [-0.052, -0.019] -> v3b installed:
  weights/calib/personal.txt = results/calib/personal_v3.txt (= personal_v3b_hm.txt + "player human" line; old
  file results/calib/personal_v2_installed_before_hm.txt); no plossmap lines (replaced by model.txt lossmap_own).
  REAL OUTCOMES, v2 -> v3 (scripts/hm_pers_compare.py, common positions; observed = the same player in the same game):
    2x milestone (46,974 positions, 82 games, observed 0.869): log-loss 0.497 -> 0.425 (diff -0.073 [-0.122, -0.029]),
      Brier 0.160 -> 0.134, AUC 0.850 -> 0.865; mean predicted 0.618 -> 0.680
      novice       observed 0.585: predicted v2 0.733 -> v3 0.642  (log-loss 0.566 -> 0.586)
      intermediate observed 0.957: predicted v2 0.705 -> v3 0.801  (0.375 -> 0.285)
      strong       observed 0.831: predicted v2 0.524 -> v3 0.577  (0.598 -> 0.528)
    4x milestone (24,410 positions, 71 games, observed 0.793): log-loss 0.964 -> 0.685 (diff -0.280 [-0.376, -0.185]),
      Brier 0.340 -> 0.229, AUC 0.614 -> 0.749
      novice       observed 0.272: predicted 0.461 -> 0.400;  intermediate 0.880: 0.430 -> 0.661;  strong 0.844: 0.366 -> 0.452
    (videos are selected for success: absolute levels stay pessimistic for intermediate/strong; v3 halves the gap.)
  Family board statistics (fresh games; keys 0.012 / 0.008 / 0.003 / 0.00135 / 0.0005): corner at 256 0.54 / 0.82 /
  0.79 / 0.70 / 0.05, chain 2.1 / 3.3 / 3.2 / 2.9 / 0.2 (intermediate humans 0.88, 3.7) - the middle keys look human;
  the strongest key plays the network's early style (no corner) - strength without human structure is out of reach
  for this feature set. Personal-odds transfer to real positions: as v2 (see 01:00).
01:20 COACH SLICE with human-model players (scripts/hm_coach.sh; S1 and S2 starts of results/coach, keys 0.012 /
  0.003 / 0.00135, conds alone / engine / guard:0.05 / guard:0.15 / crit:0.1 / stakes:0.3, 32 playouts; report
  results/hm/coach/report_advice.txt via COACH_DIR=results/hm/coach scripts/coach_report.py --advice):
  the coach's conclusions HOLD: warnings (guard) are on the efficient frontier in every stratum; the stakes hint is
  the least efficient (gain per hint 0.005-0.03 vs 0.06-0.27 for guard:0.15). Examples: S1 tight key 0.003: alone
  0.670, engine 0.996, guard:0.15 0.935 (81% of the gap at 1.7 warnings / 100 moves), stakes:0.3 0.765 (29%);
  S2 tight key 0.00135: alone 0.552, engine 0.966, guard:0.15 0.763 (51% at 0.7 / 100), guard:0.05 0.887 (81%).
  New: the expected-loss hint computed with the HUMAN MODEL's own probabilities (crit:0.1) is nearly as efficient
  as warnings for mid/strong players (S1 key 0.003: 87% of the gap at 2.8 hints / 100) -> an app can predict "you are
  likely to go wrong here" without seeing the player's intended move. S2 is harsher for human-model players than
  for softmax players (alone 0.07-0.55 from tight positions), so late-mid thresholds of 0.05 close 77-87% of the gap.
```
