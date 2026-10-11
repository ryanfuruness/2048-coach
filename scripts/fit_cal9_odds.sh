#!/bin/bash
# cal9: odds refit for best_v6c (cal7's recipe, scripts/fit_cal7_odds.sh, with the new engine's own data):
#  base rates: late2's v6c 1000-game benchmark logs (results/bench/late2_v6c); synthetic rows: cal9's v6c lapse + clean
#  checkpoint games (s901); real slopes: cal6's P(16384) truth (r14, tight30: v6c = v6b below tile sum 20480, where
#  P(16384) is decided) + cal9's P(32768) truth with v6c continuing (truth_r15, truth2_r15; truth4 is held out).
#  Output: results/calib/model_v10_odds.txt (odds lines only; the caller merges them into the installed model).
set -e
cd "$(dirname "$0")/.."
E=${ENGINE:---weights weights/late2/best_v6c.w --leaf-view-max-sum 20480}
BL=""; for f in results/bench/late2_v6c/chunk*.log; do BL="$BL --base-log $f"; done  # one file per flag
L=results/cal9/lapse
python3 scripts/fit_calib.py results/calib/model_v10_base.json --umode-log --slope-bands 12,14 $BL \
  --clean $L/s901_cleancp.tsv $L/s901_cleancp.tsv $L/s901_lapse16c.tsv $L/s901_lapse32.tsv $L/s901_lapse32b.tsv
python3 scripts/fit_calib_real.py results/calib/model_v10_base.json results/calib/model_v10_odds.txt \
  --analyze build/analyze --engine "$E" --truth \
  r14:16384:results/cal6/truth.tsv:results/cal6/truth/truth_r14.tsv \
  r14:8192:results/cal6/truth.tsv:results/cal6/truth/truth_r14.tsv \
  t30:16384:results/cal6/tight30_sel.tsv:results/cal6/tight30_truth.tsv \
  r15:32768:results/cal6/truth.tsv:results/cal9/truth/truth_r15.tsv \
  r15:32768:results/cal6/truth2.tsv:results/cal9/truth/truth2_r15.tsv
