#!/bin/bash
# Odds model v6 + staged loss maps (workstream cal6, 2026-10-06/07). Rerunnable for another engine: regenerate the
# data with the same scripts and engine flags (ENGINE="--weights W.w --stages ..."), then rerun this fit.
#   data: scripts/judge_cal6.sh (real-position judges: results/cal6/j1200, jx, jold), scripts/study_cal6.sh truth|lapse
#         (odds truth on real positions, late lapse + clean checkpoint games), scripts/calib_softmap.sh (skill map),
#         scripts/calib_pers_run.sh / _run2.sh (personal odds truth)
#   1. synthetic base fit: base rates from the benchmark logs (virtual checkpoints) and clean checkpoint games, value
#      slopes in 3 bands (< 4096, 4096-16384, >= 16384 tile sum), deterministic 5-fold CV for the regularisation
#   2. value slopes refit on real positions with playout truth (16384 and 32768 targets; 5-fold CV by player)
#   3. staged loss maps (early <= 1024, late 2048-8192, top >= 16384, played-expert) from all real-position judges
#   4. personal model v2 = the soft:t model + the skill map (review-fitted skill -> soft player, per phase)
# usage: scripts/fit_v6.sh [OUT_PREFIX]   (default results/calib/model_v6) ; ANALYZE=build_cal6/analyze ENGINE=...
cd "$(dirname "$0")/.."
OUT=${1:-results/calib/model_v6}
LOGS=""
for i in 0 1 2 3 4 5 6 7 8 9; do LOGS="$LOGS --base-log results/bench/best_v5bb_1000/chunk$i.log"; done
LAPSE=$(ls results/cal6/lapse/s601_*.tsv 2>/dev/null | grep -v '\.tmp\.')
CLEAN6=$([ -s results/cal6/lapse/s601_cleancp.tsv ] && echo "--clean results/cal6/lapse/s601_cleancp.tsv")
python3 scripts/fit_calib.py ${OUT}_base.json --umode-log --slope-bands 12,14 $LOGS $CLEAN6 \
  --clean results/calib/s301_cleancp.tsv --clean results/calib/s201_clean.tsv \
  results/calib/s301_cleancp.tsv results/calib/s201_*.tsv results/calib/p2_*.tsv $LAPSE | grep -v Deprecation
python3 scripts/fit_calib_real.py ${OUT}_base.json ${OUT}.txt --analyze ${ANALYZE:-build_cal6/analyze}
python3 scripts/fit_lossmap2.py --boot 200 --heldout --model ${OUT}.txt \
  results/judge/human300_h1000.tsv results/judge/late300_h1000.tsv results/cal6/j1200/judge1200_*.tsv \
  $(ls results/cal6/jx/xexpert_*.tsv results/cal6/jold/expert_*.tsv 2>/dev/null | sed 's/^/played:/')
cat weights/calib/personal.txt | grep -v '^pskillmap ' > results/calib/personal_v2.txt
python3 scripts/calib_softmap.py --append results/calib/personal_v2.txt > /dev/null
echo "odds v6 + maps -> ${OUT}.txt; personal v2 -> results/calib/personal_v2.txt"
