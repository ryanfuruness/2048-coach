#!/bin/bash
# Loss maps from REAL human positions (the product's distribution): 300 random positions of the curated dataset,
# stratified by tier, every legal move judged with 32 engine playouts x 1000 moves (full engine). Runs after odds_truth.
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
until [ -f results/judge/tight30.done ]; do sleep 60; done
[ -s results/judge/human300_h1000.tsv ] || ./build/rollout --preset best --pool results/judge/human300.bin --playouts 32 \
  --horizon 1000 --threads 16 --out results/judge/human300_h1000.tsv > results/judge/human300_h1000.log 2>&1
python3 scripts/judge_report.py results/judge/human300_h1000.tsv | head -12
echo "== early (max <= 1024)"; python3 scripts/fit_lossmap.py --max-tile 0 1024 results/judge/human300_h1000.tsv | tail -9
echo "== late (max >= 2048)"; python3 scripts/fit_lossmap.py --max-tile 2048 1000000 results/judge/human300_h1000.tsv | tail -9
echo done > results/judge/human300.done
