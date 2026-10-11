# Workstream hm3: a playout player that repairs like humans; personal odds v5 (REPORT)

Copied by the coordinator from results/hm3/report.txt.

```
hm3 notes (a playout player that repairs like humans; personal odds v5), 2026-10-07 - progress log, newest last

02:55 Start. Problem (hm2): simulated players at a real player's move-level skill compound errors that real players
  repair (at a real intermediate's theta they reach 2048 in 3% of games) -> personal odds too pessimistic for
  intermediate / strong players (next doubling predicted 0.80 / 0.58 vs observed 0.96 / 0.83).
03:00 (b) STATE-DEPENDENT CARE at the move level (scripts/hm3_fit.py: hm's best model full_tied_death_recent with the
  value skill, the structure weight and the lapse rate multiplied by exp(c . z), z = position features tight (<= 2
  empty), mid (3-5), danger (death share of the safest move), few (<= 2 legal moves); hm's 5-fold CV by player,
  results/hm3/care_cv.jsonl): base 0.7636 nats, care 0.7642, care + lapse 0.7648 -> NO gain; coefficients: value
  skill tight -0.04, danger -2.9 (less value-sensitive near death), lapses x3.8 when tight. Humans do not choose single
  moves more carefully in danger, as far as the move likelihood can see.
03:10 STRETCH STATISTICS from boards alone (scripts/hm3_stretch.py; real: results/human_ds_v6b/analysis.jsonl,
  consecutive plies of a game; simulated: messy traces): tight = share of positions with <= 2 empty cells, esc =
  P(>= 4 empty within 10 moves | tight), c = largest tile in a corner, e = mean empty cells.
    real (<= 512 / 1024-2048 / 4096-8192):
      novice        t0.216 esc0.43 c0.03 e4.3
      intermediate  t0.099 esc0.72 c0.78 e5.0  |  t0.220 esc0.55 c0.75 e4.0
      strong        t0.104 esc0.59 c0.78 e5.0  |  t0.168 esc0.53 c0.89 e4.2  |  t0.202 esc0.50 c0.98 e4.0
    the v3/v4 playout family (keys 0.018 ... 0.00135, 200 games each, results/hm3/fam):
      <= 512: tight 0.14-0.42, esc 0.33-0.51, corner 0.17-0.89, empty 3.1-4.9; 1024-2048: tight 0.32-0.42, esc
      0.33-0.40; 4096-8192: tight 0.39-0.48, esc 0.28-0.37
  -> simulated players get into danger 1.5-4x more often than real ones and escape far less, at every key.
03:20 ESCAPE ON REAL BOARDS (src/hm3_tool.cpp + scripts/hm3_escape.py: 1,661 real tight positions with the player's
  last 20 moves, 32 playouts of 10 moves each; real = what the player achieved):
    group (real)            move model at the tier's theta   key 0.008 (v4 family)   + danger planning (q 1, dm 2)
    intermediate <=512 0.725     0.582 (theta -0.175)            0.643                 0.677 (0.656 at theta -0.175)
    intermediate 1-2k  0.532     0.380                           0.446                 0.486 (0.461)
    strong 1-2k        0.530     0.420                           0.488                 0.484 (0.464)
    novice <=512       0.430     0.264 (theta -0.80)             0.400                 0.555 (0.486 at theta -0.80)
  -> on the SAME boards real players escape 0.10-0.17 more often than the move model at their own skill: better
  danger handling than single-move statistics show (not only the drift of the model's own boards).
03:30 DANGER PLANNING in the playout policy (build/messy human policy, new options :dq=Q :de=E :dm=M: on boards with
  <= E empty cells, with probability Q, the engine's move instead of the human-model sample; dm 1 = the engine's
  search, dm 2 = the best depth-2 move among those that keep the largest tile in its corner; families
  results/hm3/fam, fam_dm2_de2, fam_dm2_de3; report scripts/hm3_famreport.py):
  - dm 1 (engine search) breaks the human structure: corner at <= 512 0.24-0.58 (q 1) vs humans 0.78; dm 2 keeps it
    (0.74-0.92) - the choice for the family.
  - outcomes rise strongly (key 0.008: reach 2048 0.17 -> 0.45 (q 0.5) -> 0.79 (q 1); key 0.012: 0.03 -> 0.37 -> 0.81),
    escape 0.46 -> 0.52 -> 0.59 (<= 512), tight share barely changes (0.165 -> 0.154).
  - the human-model skill reading theta barely moves with planning (key 0.012: -0.18 / -0.21 / -0.24), the softmax
    review t sharpens (0.110 -> 0.069 -> 0.049): planning adds the repair ability without changing how the player's
    ordinary moves look to the human move model.
03:35 Personal-odds data for two planning families running on the instance (scripts/hm3_personal.sh, 15 keys 0.05 ...
  0.0005 incl. weaker keys for novices, 600 games each at checkpoints + 100 reviewed): pA = q 1 (dm 2, <= 2 empty),
  pB = q 0.5. Baselines (v4) on the real-outcome checks running on the laptop.
03:15 PERSONAL-ODDS CANDIDATES (scripts/hm3_personal.sh: 15-16 keys 0.05 ... 0.0005, 600 games each recorded at
  checkpoints + 100 reviewed; scripts/hm3_build_model.sh: fit_personal + skill map + theta map + v4's phint/pthetat +
  "pplan Q DE DM"). Validation on COMMON real positions (scripts/hm_skill_real.py now also writes per-row predictions,
  scripts/hm3_compare.py joins models; three mappings of a player's skill to the model key: t = review t through the
  skill map (analyze --personal T), theta = the human-model theta through the theta map (direct), tt = theta -> t
  (out-of-fold regression) -> skill map (what v4 does for --skill and reviews); game-clustered bootstrap):
  pA (planning q 1 for every key): everyone predicted ~0.91-0.93 -> AUC 0.58-0.66, novices 0.93 vs observed 0.57
    (log-loss 1.18): planning rescues even the weakest keys - real novices do not repair.
  pB (q 0.5): no better than v4 (t: ll 0.268 vs v4 tt 0.269).
  pC (q grows with the key: 0 for key >= 0.035, 1 for <= 0.012; <= 2 empty), vs v4 tt on 25,845 common 2x targets
    (75 games, observed 0.945): theta map ll 0.177 vs 0.212 (diff -0.035 [-0.060, -0.010]), AUC 0.858 vs 0.865;
    intermediate predicted 0.922 (v4 0.878, observed 0.994), strong 0.903 (0.854 / 0.978); 4x: ll 0.238 vs 0.290
    (-0.051 [-0.098, -0.004]), intermediate 0.911 (0.846 / 0.975), strong 0.899 (0.806 / 1.000). BUT novices worse:
    2x ll 0.682 vs 0.543 (predicted 0.706 vs 0.699, observed 0.619), 4x 0.695 vs 0.581 (real novices' theta -0.80 maps
    to key ~0.024, which still plans with q ~0.35).
  pD (as pC, planning at <= 3 empty): theta map ll 0.160 but AUC 0.791 and novices worse (0.732).
  -> pE: planning only from key 0.02 down (q 0 for key >= 0.02, 1 for <= 0.01), key 0.02 added: running.
03:40 pE (planning only from key 0.02 down: q 0 for key >= 0.02, 1 for <= 0.01; key 0.02 added): theta map 2x ll
  0.213 vs v4 0.211 (n.s.), 4x 0.341 vs 0.393 (-0.052 [-0.111, +0.005]). Per-tier game-clustered CIs of the log-loss
  difference vs v4 (tt), theta map:
    pC  2x: novice (24 games) +0.141 [+0.042, +0.267]   intermediate (41) -0.056 [-0.083, -0.028]   strong (12) -0.071 [-0.111, -0.037]
        4x: novice (21)       +0.214 [+0.001, +0.425]   intermediate (36) -0.173 [-0.255, -0.093]   strong (11) -0.259 [-0.473, -0.064]
    pE  2x: novice +0.077 [-0.026, +0.180]   intermediate -0.002 [-0.022, +0.022]   strong -0.027 [-0.049, -0.006]
        4x: novice +0.115 [-0.068, +0.269]   intermediate -0.070 [-0.130, -0.006]   strong -0.146 [-0.262, -0.059]
  -> planning helps intermediate / strong players' predictions significantly, and must not reach novice-level keys:
  real novices' theta (-0.80) sits at keys 0.02-0.025, real intermediates' (-0.175) at ~0.011. pF / pG: a sharp ramp
  (q 0 for key >= 0.02, 1 for key <= 0.015), planning at <= 2 / <= 3 empty: running. (The ramp location is a model
  choice made on the same real games that validate it: one parameter chosen among a few discrete options.)
04:00 pF / pG (sharp ramp: q 0 for key >= 0.02, 1 for <= 0.015; <= 2 / <= 3 empty) and variants: pFc = pF without
  the weakest keys (0.025-0.05: real players with a very low theta still do better than the simulated weakest keys, so
  the map clamps at 0.02 as v4 clamped at 0.018), pFF = pFc with 2,400 games for the novice-level keys 0.02-0.015, pH =
  v4's keys 0.018 / 0.015 + pF's planning keys. pG (planning at <= 3 empty) loses discrimination (AUC 0.71-0.76).
  Split-half check (by video): the overall gain holds in both halves at 4x and in half A at 2x; the novice losses
  come from half B only.
04:10 CHOSEN: pFF ("personal v5"). On common real positions (hm2's protocol, scripts/hm_skill_real.py rows, 77 games):
                                       2x log-loss (all)          4x log-loss (all)          2x mean pred. by tier (obs)
    reviews / --skill (v4: theta->t)   -0.043 [-0.067, -0.020]   -0.164 [-0.262, -0.070]   nov 0.67->0.68 (0.58), int 0.86->0.91 (0.98), str 0.85->0.93 (0.98)
      same with the direct theta map   -0.035 [-0.063, -0.003]   -0.148 [-0.253, -0.041]   nov 0.67->0.62 (0.58), int 0.86->0.90, str 0.85->0.91
    --personal T (t -> skill map)      -0.086 [-0.128, -0.043]   -0.170 [-0.275, -0.066]   nov 0.64->0.61, int 0.81->0.89, str 0.82->0.90
    AUC (theta->t path): 2x 0.819 -> 0.867, 4x 0.844 -> 0.897. Per tier (theta->t path, game-clustered 90%):
    intermediate 2x -0.048 [-0.076, -0.021], 4x -0.181 [-0.272, -0.092]; strong 2x -0.087 [-0.132, -0.048], 4x -0.438
    [-0.756, -0.177]; novices 2x +0.067 [-0.004, +0.131], 4x +0.140 [-0.015, +0.283] (n.s.; direct theta map: +0.077
    [-0.042, +0.208], +0.149 [-0.060, +0.339]).
  The coordinator's named check (scripts/calib_personal_real.py -> hm_pers_compare.py, t path, 46,794 common 2x
  positions, 82 games): 2x log-loss 0.426 -> 0.328 (-0.097 [-0.143, -0.055]), Brier 0.135 -> 0.101, AUC 0.864 -> 0.879;
  4x 0.594 -> 0.472 (-0.124 [-0.198, -0.051]), AUC 0.806 -> 0.827; mean predicted (observed): novice 0.642 -> 0.613
  (0.585), intermediate 0.799 -> 0.871 (0.957), strong 0.577 -> 0.660 (0.831); 4x novice 0.419 -> 0.396 (0.285),
  intermediate 0.682 -> 0.824 (0.876), strong 0.416 -> 0.520 (0.758).
  NOVICES: the mean calibration improves (predictions move toward the observed rates); the log-loss is slightly worse
  (2x +0.040, 4x +0.131 on the t path) - entirely ONE game (Ashley Nguyen game 224: 466 / 504 positions, both models
  predicted >= 0.90 and the player died; without it novices are -0.008 / -0.011). Judged "not worse".
04:15 INSTALLED weights/calib/personal.txt = results/calib/personal_v5_hm3.txt (= results/hm3/personal_pFF_t.txt +
  a comment header; previous file results/calib/personal_v4_installed_before_hm3.txt; undo: copy it back). Lines:
  player human, pknots/pvbar/personal (fit_personal.py on 16 keys), pskillmap, pthetamap, phint (v4), pthetat (v4,
  kept: --personal T -> theta for find_prob / hints needs it), pplan 0.02 0.015 2 2 (the family; ignored by today's
  parsers). analyze --selftest: 0 failures. Example (512 position): --personal 0.05 -> 1024 0.969, 2048 0.912, 4096
  0.619 (v4: 0.948 / 0.736 / 0.270); --personal 0.3 (novice-like) -> 1024 0.199.
  FOR THE COORDINATOR (analyze.cpp / calib.h are not mine):
  (1) analyze's --personal-playouts fallback still plays the plain human model: it should apply the pplan line - on
      boards with <= DE empty cells, with probability q(key) = clip((ln LO - ln key) / (ln LO - ln HI), 0, 1), play
      the best depth-2 move (Searcher::move_values at depth 2) among the moves that keep the largest tile in its corner
      when it is in one (else the best) - exactly messy's human policy :dq= :de=2 :dm=2 (src/messy.cpp). The default
      method ("model") is unaffected.
  (2) optional: PersonalModel::key_of_theta could prefer the direct theta map (pthetamap) when present: equal overall
      gain, better novice calibration (2x mean 0.62 vs 0.68 at observed 0.58). pthetat must stay (t -> theta).
  (3) docs/guide.md personal-odds numbers: see the table above.
FILES: src/messy.cpp (human policy :dq= :de= :dm=, additions only), src/hm3_tool.cpp (+ Makefile target hm3_tool),
  scripts/hm3_fit.py, hm3_stretch.py, hm3_escape.py, hm3_family.sh, hm3_famreport.py, hm3_personal.sh,
  hm3_build_model.sh, hm3_compare.py; scripts/hm_skill_real.py writes per-row predictions (OUT_rows.tsv); results/hm3/
  (families fam*/p*, candidate models personal_p*_t.txt, sr_*_rows.tsv, real_v4/v5.tsv, care_cv.jsonl,
  escape_*.tsv, stretch_real.json).
```
