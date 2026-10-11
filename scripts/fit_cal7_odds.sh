#!/bin/bash
# cal7: odds refit for best_v6b (cal6's REFIT RECIPE steps 1c + 2a with the new engine's own data):
#  base rates: late's v6b 1000-game benchmark logs; synthetic rows: cal7's v6b lapse + clean checkpoint games (s701);
#  real slopes: cal6's P(16384) truth (unchanged: v6b = best_v5 below tile sum 24576) + cal7's P(32768) truth with v6b
#  continuing. Output: results/calib/model_v7_odds.txt (odds lines only; the maps are added by the caller).
set -e
cd "$(dirname "$0")/.."
E=${ENGINE:---weights weights/best_v6b.w}
BL=""; for f in results/bench/late_v6bo2/chunk*.log; do BL="$BL --base-log $f"; done  # one file per flag
python3 scripts/fit_calib.py results/calib/model_v7_base.json --umode-log --slope-bands 12,14 $BL \
  --clean results/cal7/lapse/s701_cleancp.tsv results/cal7/lapse/s701_cleancp.tsv \
  results/cal7/lapse/s701_lapse16c.tsv results/cal7/lapse/s701_lapse32.tsv results/cal7/lapse/s701_lapse32b.tsv
python3 scripts/fit_calib_real.py results/calib/model_v7_base.json results/calib/model_v7_odds.txt \
  --analyze build/analyze --engine "$E" --truth \
  r14:16384:results/cal6/truth.tsv:results/cal6/truth/truth_r14.tsv \
  r14:8192:results/cal6/truth.tsv:results/cal6/truth/truth_r14.tsv \
  t30:16384:results/cal6/tight30_sel.tsv:results/cal6/tight30_truth.tsv \
  r15:32768:results/cal6/truth.tsv:results/cal7/truth/truth_r15.tsv \
  r15:32768:results/cal6/truth2.tsv:results/cal7/truth/truth2_r15.tsv
