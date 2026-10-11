#!/bin/bash
# Odds model v4: base rates from the 1000 benchmark games (virtual checkpoints) + the s301 clean checkpoint games, value
# slopes (early / late) from all handovers (s201 part 1 + lapses + pilot 2); then the staged H=1000 loss maps.
cd "$(dirname "$0")/.."
LOGS=""
for i in 0 1 2 3 4 5 6 7 8 9; do LOGS="$LOGS --base-log results/bench/best_v5bb_1000/chunk$i.log"; done
python3 scripts/fit_calib.py results/calib/model_v4.json $LOGS --clean results/calib/s301_cleancp.tsv \
  --clean results/calib/s201_clean.tsv results/calib/s301_cleancp.tsv results/calib/s201_*.tsv results/calib/p2_*.tsv
J=$(ls results/judge/p2_*_h1000.tsv | grep -v soft0\\.)
python3 scripts/fit_lossmap.py --model results/calib/model_v4.txt --key lossmap --max-tile 0 1024 $J > /dev/null
python3 scripts/fit_lossmap.py --model results/calib/model_v4.txt --key lossmap_late --max-tile 2048 1000000 $J > /dev/null
echo "model v4 -> results/calib/model_v4.txt"
