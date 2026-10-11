# Workstream hm2: per-move human probabilities, human-model skill, late refit (REPORT)

Copied by the coordinator from results/hm2/report.txt.

```
hm2 notes (follow-ups of workstream hm: per-move human probabilities, skill by the human move model), 2026-10-07 -
progress log, newest last; the final report goes to the coordinator

01:40 src/human.h: probs() split into the skill-free terms (hm::Terms: value part V, structure part S, habits H per
  move) + probs_from_terms() + loglik(); identical results (old vs new hm_tool --probs on 83 real positions with random
  histories and skills: max abs diff 0). A player's skill can now be fitted over thousands of positions cheaply.
01:55 build/analyze (with a skill: --skill THETA, or --personal T converted by the personal model's pthetat line):
  per move "find_prob" (the human move model's probability that a player of that skill plays it, with the player's
  recent moves in reviews), per position "player_skill", "error_risk" (sum of find_prob x your_cost: the expected share
  of the player's own chances of the next tile the move they make costs) and "hint" (error_risk >= the phase's
  threshold, personal model line "phint"); text output "[played by N% of players at your level]" and an error-risk
  line. Reviews: "skill" = theta fitted by maximum likelihood of the played moves under the human move model (grid
  -3..3 step 0.025, as the softmax t: over the game and per phase >= 50 moves with a bootstrap 80% interval),
  "hints" / "hints_per_100" at the fitted skill, "hard_moments" (error risk >= 1% and the best move found by < 20% of
  players at that skill, judged without the player's direction habits) and "hard_found" (+ plies). Existing outputs
  unchanged. Selftest +3 checks (terms = probs exactly; find_prob sums to 1, risk = weighted cost, hint follows the
  threshold; the skill fit recovers theta 0 from 600 moves drawn from the model): 15/15... (all pass).
02:00 THETA MAP of the simulated players (scripts/hm_thetamap.sh on the instance: the 2,400 skill-map games of hm,
  200 per key, reviewed by the new analyze; scripts/hm_thetamap.py): the fitted theta rises with the key's strength up
  to key 0.0065 (theta +0.37) and FALLS for stronger keys (0.003 +0.35, 0.00135 +0.29, 0.0005 +0.20): the playout
  family caps the structure skill at 0.4, so its strong players move less like the tied move model ("strength without
  human structure"); within a key the sd is 0.03-0.10, keys 0.018 ... 0.0065 are separated by 1.9-6.2 sd.
02:05 REAL PLAYERS (scripts/hm_skill_real.py on hm's data.npz: theta and the softmax t per player and phase, >= 100
  moves):
  split-half reliability (first vs second half of a player's moves in the phase, Pearson): theta 0.84 / 0.81 / 0.87 /
  0.75 in phases 0-3 vs log t -0.05 / 0.59 / 0.12 / 0.60 -> the softmax t is mostly noise early in a game; theta is a
  stable skill reading.
  tier separation (phase 0, 55 players): theta Spearman +0.45, eta2 0.53; -log t +0.52, 0.52 (equal); later phases:
  neither separates intermediate from strong (n small).
  personal odds on real outcomes (41k position-targets, 77 games): key from the DIRECT theta map (simulated players
  with the player's theta): 2x log-loss 0.87 vs 0.29 for the softmax key (diff +0.58 [+0.47, +0.67]) - far too
  pessimistic: simulated players at a real intermediate's theta (-0.2, key ~0.012) reach 2048 in 3% of games (they
  compound their errors; real players repair them) -> NOT used for real players. Key from t PREDICTED FROM THETA
  (log t = a + b theta per phase, out of fold by player; phases with < 30 player-phases use phase 1's line) through the
  existing skill map: 2x log-loss 0.262 vs 0.292 (diff -0.030 [-0.116, +0.054]), AUC 0.820 vs 0.846; 4x 0.482 vs
  0.542 (-0.060 [-0.188, +0.072]), AUC 0.831 vs 0.789 -> at least as good (point estimates better, CIs include 0),
  from a far more reliable reading -> pthetat lines: phase 0 log t = -3.078 - 2.327 theta, phase 1 -3.994 - 3.103
  theta (+ the reverse regressions for --personal T -> theta).
02:10 HINT THRESHOLDS (scripts/hm_hint.sh on the instance: coach advice mode, human-model players keys 0.012 / 0.003 /
  0.00135, the coach's real start positions S1 (128-512, 89) / S2 (1024-2048, 100) / S3 (4096-8192, 60), 32 playouts,
  new coach condition risk:R = analyze's hint: error risk at the player's theta (the family's theta map of its key)
  with Calib::own_cost; scripts/coach_report.py -> results/hm2/coach/report_advice*.txt):
  S1 (all positions): risk:0.05 closes 63 / 82 / 64% of the gap to the engine (keys 0.00135 / 0.003 / 0.012) at 1.3 /
    1.8 / 3.1 hints per 100 moves, gain per hint 0.058 / 0.123 / 0.117 (guard:0.15 warnings 0.099 / 0.143 / 0.157,
    hm's crit:0.1 0.061 / 0.100 / 0.102); risk:0.03 74-90% at 2.3-5.0 per 100, 0.04-0.09 per hint.
  S2: risk:0.05 0.043 / 0.067 / 0.035 per hint at 1.4-4.4 per 100; risk:0.08 0.058 / 0.085 / 0.041 at 0.8 / 1.2 /
    2.8 per 100 (35 / 47 / 23% of the gap); risk:0.12 0.066 / 0.097 / 0.048 (warnings 0.096 / 0.098 / 0.065).
  S3: every advice is weak per intervention (many small errors): risk:0.08 0.016 / 0.017 / 0.014 per hint, 12-20% of
    the gap; warnings guard:0.05 0.009-0.017 per warning but 50% of the gap at 3-8 per 100 moves.
  -> phint 0.05 (<= 512), 0.08 (1024-2048), 0.08 (4096-8192, low value), none from 16384.
  Real players at these thresholds (scripts/hm_hint_rates.py: each player's own theta per phase): hints per 100 moves,
  median: novices 2.7 (phase 0), intermediate 0.0 / 0.0 (phases 0 / 1; up to ~10 for a few), strong 0.0 / 0.0 / 0.14.
02:15 INSTALLED weights/calib/personal.txt = results/calib/personal_v4_hm2.txt (= v3 + pthetat 0/1, pthetamap 0/1,
  phint 0.05 0.08 0.08 -1; old file results/calib/personal_v3_installed_before_hm2.txt). The --personal T odds are
  unchanged (same skill map); new: --skill THETA (key = skill map of exp(a + b theta)), find_prob / error_risk / hint,
  the review's skill / hints / hard moments. Main build rebuilt (make -j8): selftest 15/15... 0 failures. Docs: api.md
  (fields, review summary, personal.txt lines), guide.md (section "At your level").
02:35 LATE-GAME REFIT of the move model on best_v6b values (task 3). results/hm2/v6b/data.npz = hm's data rebuilt
  from results/human_ds_v6b (HM_DIR/HM_TOOL options added to scripts/hm_build.py): identical below tile sum 20480,
  42,259 late decisions (sum >= 20480) with new 1-ply values (mean |change of the relative 1-ply loss| 0.24!) and
  search losses. Held-out players (scripts/hm_late_eval.py / hm_late_refit.py: skill on the first half of each
  player's decisions, scored on the second half): the unchanged v2 weights do slightly BETTER on v6b values (late
  0.8067 -> 0.7986 nats). A separate 1-ply value hinge for late positions: no gain (0.8003, unstable weights). The
  SEARCH loss as the late value input (analyze's scale): swapping the input alone 0.7813, refitting its hinge 0.7691
  (-0.030 vs 0.7986; whole data 0.7522 -> 0.7415); experts' moves losing >= 15% at 16384+: predicted 4.03 -> 3.06 per
  100 (observed 1.50: still too many - experts avoid big losses better than any of these models). -> src/human.h:
  Model::wv_late (hinge on the search losses, used where the caller passes them: analyze for tile sums >= 20480;
  playouts keep the 1-ply hinge, their probabilities unchanged: hm_tool --probs max diff 0), file key "wv_late"
  (results/hm2/human_model_late_search.txt). Selftest +1 check (16 total, 0 failures).
02:45 Hard moments on real players (scripts/hm_hint_rates.py, each player's own theta per phase): 0.2-6 per 100 moves
  (median by tier and phase), found 2-28% of the time (pooled) - as defined ("< 20% of players at your level").
  Example reviews (one long real game per tier): novice skill -0.50, 3.2 hints / 100 moves (warnings 3.7), 15 hard
  moments, 7 found; intermediate -0.13, 8 hard moments, 0 found; strong -0.15 (phase 1 0.00, phase 2 -0.18), 5 / 2.
  Fuzz boards with --skill -0.3 (486 positions): find_prob sums to 1, error_risk = sum of find_prob x your_cost, in
  [0, 1] everywhere; latency unchanged (p50 1.2 ms, max 49 ms).
FILES: src/human.h (Terms / probs_from_terms / loglik; wv_late), src/calib.h (PersonalModel: player, thetamap,
  thetat, hint; key_of_theta / theta_of_key / t_of_theta / theta_of_t), src/analyze.cpp (--skill, find_prob,
  player_skill, error_risk, hint; review skill / hints / hard moments; 4 selftest checks), src/coach.cpp (condition
  risk:R; --calib, --personal-model), scripts/hm_thetamap.sh/.py, hm_skill_real.py, hm_hint.sh, hm_hint_rates.py,
  hm_late_eval.py, hm_late_refit.py, hm_build.py (HM_DIR / HM_TOOL); weights/calib/personal.txt = personal_v4_hm2.txt;
  docs/api.md, docs/guide.md ("At your level"); results/hm2/ (thetamap reviews, coach runs, skill_real, v6b data).
```
