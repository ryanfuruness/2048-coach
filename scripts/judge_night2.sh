#!/bin/bash
# Night 2 calibration on REAL human positions: (1) skill-level loss maps (softmax continuations t = 0.003 / 0.01 /
# 0.03 on the 300 random curated positions, H=1000), (2) 300 more late positions (strong/expert tiers, max >= 2048)
# judged by the engine (H=1000) for the late loss map.
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
for t in 0.003 0.01 0.03; do
  out=results/judge/human300_soft${t}_h1000.tsv
  [ -s $out ] || ./build/rollout --preset best-notables --pool results/judge/human300.bin --playouts 32 --horizon 1000 \
    --soft $t --threads 16 --out $out > ${out%.tsv}.log 2>&1
  echo "== t=$t (real positions)"; python3 scripts/fit_lossmap.py $out | tail -10
done
[ -s results/judge/late300_h1000.tsv ] || ./build/rollout --preset best --pool results/judge/late300.bin --playouts 32 \
  --horizon 1000 --threads 16 --out results/judge/late300_h1000.tsv > results/judge/late300_h1000.log 2>&1
python3 scripts/judge_report.py results/judge/late300_h1000.tsv | head -1
echo "== late map on human300 + late300"; python3 scripts/fit_lossmap.py --max-tile 2048 1000000 \
  results/judge/human300_h1000.tsv results/judge/late300_h1000.tsv | tail -10
echo done > results/judge/night2.done
