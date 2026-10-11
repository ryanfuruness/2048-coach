#!/bin/bash
# Personal-odds ground truth from real positions: softmax players (1-ply, soft:t) play on from each position of
# results/cal6/pers_rR.bin (largest tile 2^(R-2)) until 4x its tile (stop rank R) or death, 32 playouts per position.
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
T=${1:-4}
mkdir -p results/cal6/pers
for t in 0.01 0.003 0.03 0.1; do
  for r in 9 10 11 12 13 14 15; do
    f=results/cal6/pers/soft${t}_r$r.tsv
    [ -s $f ] || ./build/rollout --preset best-notables $ENGINE --pool results/cal6/pers_r$r.bin --playouts 32 \
      --horizon 0 --stop-rank $r --moves engine --soft $t --threads $T --seed 9 --out $f.tmp > ${f%.tsv}.log 2>&1 \
      && mv $f.tmp $f
  done
done
echo done > results/cal6/pers/done
