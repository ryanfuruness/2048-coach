#!/bin/bash
# Second pass of calib_pers_run.sh: the same playouts stopped at 2x the position's tile (stop rank R-1), so that
# P(reach 2x) = 1 - died (the rollout's tile columns start at 2048).
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
T=${1:-4}
until [ -f results/cal6/pers/done ]; do sleep 20; done
for t in 0.01 0.003 0.03 0.1; do
  for r in 9 10 11 12 13 14 15; do
    f=results/cal6/pers/soft${t}_r${r}_2x.tsv
    [ -s $f ] || ./build/rollout --preset best-notables $ENGINE --pool results/cal6/pers_r$r.bin --playouts 32 \
      --horizon 0 --stop-rank $((r - 1)) --moves engine --soft $t --threads $T --seed 9 --out $f.tmp > ${f%.tsv}.log 2>&1 \
      && mv $f.tmp $f
  done
done
echo done > results/cal6/pers/done2
