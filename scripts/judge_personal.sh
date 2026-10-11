#!/bin/bash
# Losses at a player's skill: the p2 handover positions judged with playouts by softmax players (t = 0.003 / 0.01 /
# 0.03) instead of the engine, H=1000 (fast: the soft players are 1-ply). One loss map per t.
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
T=${T:-4}
for t in 0.003 0.01 0.03; do
  for c in corner greedy soft003 soft01 soft03; do
    out=results/judge/p2_${c}_soft${t}_h1000.tsv
    [ -s $out ] && continue
    ./build/rollout --preset best-notables --pool results/judge/p2_$c.bin --playouts 32 --horizon 1000 --soft $t \
      --threads $T --out $out > ${out%.tsv}.log 2>&1
  done
  echo "== t=$t"; python3 scripts/fit_lossmap.py results/judge/p2_*_soft${t}_h1000.tsv | tail -10
done
