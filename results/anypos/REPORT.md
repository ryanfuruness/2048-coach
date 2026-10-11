# Workstream anypos: odds on odd-but-legal positions (REPORT)

Copied by the coordinator from results/anypos/report.txt.

```
Workstream anypos: odds on odd-but-legal positions (2026-10-07 04:10-05:20 +04)

QUESTION: are analyze's engine odds calibrated on positions that look nothing like human or engine play?
DATA: set A = 504 positions, 12 categories x 7 stages (largest tile 256..16384, 6 each, random orientation;
scripts/anypos_gen.py --seed 7): snake (control), center, edge, two_corners, checker, full_merges, scattered, reversed
(chain growing away from the corner), typewriter (rows left-to-right), sparse, heavy_sum (far more big tiles than real
games have), random. Set B = 300 positions, other seed, largest tile 1024..16384, the same 12 + 3
UNSEEN categories (near_corner, twin_max, diagonal) = independent test set. Truth: 64 engine playouts per position
from the engine's move (best_v6b + tables, explicit --weights: the instance has no weights/best.cfg) to two doublings
above the largest tile (one for 16384 boards: no 65536 target) -> P(next doubling), P(two doublings). Real-position
truth: the cal6/cal7 sets (790 positions; scripts/anypos_human.py). Predictions: analyze --odds-inputs (Python copy of
calib.h's odds in scripts/anypos_odds.py reproduces all 1,800 odds to < 0.0015).

FINDINGS (installed model v7; MAE of predicted vs measured odds, sets A+B):
  largest tile  sane formations   odd formations   (sane: snake, checker, full_merges, sparse, typewriter, twin_max)
  512-1024      0.004-0.006       0.007-0.017      the engine repairs anything: odds reliable for every shape
  2048          0.008             0.064
  4096          0.014             0.151            odd shapes over-predicted (e.g. 0.95 predicted vs 0.85 measured)
  8192          0.036             0.290            badly over-predicted: center 0.86 vs 0.38, two_corners 0.96 vs 0.29
  16384         0.110 (noise)     0.367            P(32768): scattered 0.41 vs 0.005, two_corners 0.54 vs 0.01
  real positions (790): MAE 0.094 overall (0.055-0.066 for P(16384), 0.13-0.15 for P(32768) - partly 32-playout noise)
WHY: from 4096 on the odds lean on the stage base rates, and the value term's slope there was fitted on real
positions whose u = log(value / typical) spans the same range but whose outcomes are luck-dominated; the late networks
are table players and do not see how hopeless a broken late formation is (u ~ -0.3 for two_corners at 8192). Real
tight positions (low u) ARE calibrated - so a steeper value slope, which helps odd boards, hurts real ones (tested:
value slope / hinge fits worsen real MAE 0.094 -> 0.096-0.104 out of sample).

FIX (gated formation correction; scripts/anypos_fit2.py --no-value --feats exposed_g,corner_g,far_g3 --lam 0.01):
  z_T += B(s)·c_j x_j, same shift for every target, chain-rule base ratios unchanged, corrections only from log2 sum 12;
  x from the best move's afterstate, gated to be ZERO where real games live: exposed_g = max(0, exposed - 2)/2,
  corner_g = max(0, corner_dist - 1)/2 x clip(1 - empty/12, 0, 1), far_g3 = max(0, far - 2)/3 (far: big tiles of rank
  >= max-3, each adding its distance - 1 to the nearest bigger-or-equal big tile; scripts/anypos_feats.py).
  Validation: odd A leave-one-category-out MAE 0.096 -> 0.087, LL 0.358 -> 0.332 (scattered 0.192 -> 0.153, center
  0.152 -> 0.134, two_corners 0.204 -> 0.183; sane categories unchanged); real positions 5-fold CV MAE 0.094 -> 0.094,
  LL 0.465 -> 0.465 (no harm); odd B (independent, 540 pairs) 0.101 -> 0.098, LL 0.384 -> 0.365 (unseen categories:
  near_corner LL 0.332 -> 0.318, diagonal 0.349 -> 0.348, twin_max 0.126 -> 0.137). End to end with the patched
  analyze: odd B MAE 0.1011 -> 0.0976, LL 0.385 -> 0.365; real MAE 0.0942 -> 0.0939, LL 0.4652 -> 0.4644.
  Example (8192 in the middle row, [[0,2,4,0],[2,0,0,0],[2048,8192,1024,2],[2,4096,2,0]]): P(16384) installed 0.855,
  corrected 0.61, measured 0.36; P(32768) 0.305 / 0.104 / 0.23 -> the remaining error is why the CAVEAT matters.
CAVEAT RULE (odds_caveat, shown when the odds are less reliable): largest real tile >= 4096 and any of: 3+ exposed
  cells next to big tiles, 2+ trapped small tiles, the biggest tile 2+ steps from its corner with <= 6 empty cells, big
  tiles stranded apart (far >= 2); from 8192 also the biggest tile out of its corner. Fires on 86% of odd positions
  >= 4096 (12% of sane ones) and on 18% of the real truth positions (enriched in tight / late ones). Unflagged positions
  are well calibrated (odd: MAE 0.053; real 0.077); flagged ones 2-3x worse even after the correction (odd ~0.17-0.29;
  real 0.168, where the model is on average slightly PESSIMISTIC: 0.45 predicted vs 0.51 measured) -> show "odds less
  certain for an unusual formation" rather than trusting a number there.

INSTALLED: weights/calib/model.txt = results/calib/model_v8_anypos.txt (md5 a4a87be0) = the previous model
  (results/calib/model_before_anypos.txt, md5 d1f8c214, incl. cal8's own-cost lines) + 3 "ocorr" lines. INERT until
  the coordinator applies results/anypos/anypos_odds.patch (calib.h: ocorr parsing, shape_shift, odds/prob shift;
  analyze.cpp: far_of, shape_shift, odds_caveat, odds_of uses the shift, JSON "odds_caveat" and odds_in "shape").
  Patch tested: builds against the source as of 05:09 (incl. expl's changes), selftest 0 failures, C++ = Python odds
  (720 pairs: mean |diff| 0.0003). Suggested text for summary() when odds_caveat fires: "Odds are less certain here:
  this formation is unusual for the stage."
FILES: scripts/anypos_gen.py, anypos_truth.sh (P= STAGES= THREADS= ENGINE=), anypos_report.py, anypos_odds.py,
  anypos_human.py, anypos_fit.py (value-only variants, not used), anypos_fit2.py (final), anypos_feats.py;
  results/anypos/: pos*.tsv/.bin/.idx, truth_r*.tsv, truthB_r*.tsv, pred*.jsonl, human_truth.tsv, human_pred.jsonl,
  pairs.tsv, fit_final.txt, trust_table.txt, model_v8_candidate.txt, anypos_odds.patch.
```
