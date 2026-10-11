#!/bin/bash
# Does the "moderate value losses are mostly repaired" finding hold at a longer horizon? Re-judges the pilot-2
# handover positions with H=1000 (vs 200) and prints both loss maps. Waits for the calibration study (SEED 201) first.
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
until [ -f results/calib/s201_part2.done ]; do sleep 60; done
for c in corner greedy soft003 soft01 soft03; do
  out=results/judge/p2_${c}_h1000.tsv
  [ -s $out ] && continue
  ./build/rollout --preset best --pool results/judge/p2_$c.bin --playouts 32 --horizon 1000 --threads 16 \
    --out $out > results/judge/p2_${c}_h1000.log 2>&1
done
echo "== H=200";  python3 scripts/fit_lossmap.py results/judge/p2_*_h200.tsv
echo "== H=1000"; python3 scripts/fit_lossmap.py results/judge/p2_*_h1000.tsv
for c in corner greedy soft003 soft01 soft03; do python3 scripts/judge_report.py results/judge/p2_${c}_h1000.tsv | head -1; done
