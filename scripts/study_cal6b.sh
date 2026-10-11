#!/bin/bash
# cal6 queue A (replaces study_cal6.sh expert -> personal): the new expert decisions (xexpert), then the personal-odds
# playouts, then the old expert disputes again at H=1000. Threads: T (16).
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
T=${T:-16}
until [ -f results/cal6/j1200/judge1200_0_400.done ]; do sleep 30; done
scripts/judge_cal6.sh results/cal6/xexpert.bin results/cal6/jx 0 400 25 $T
mkdir -p results/cal6/pers
for t in 0.01 0.003 0.03 0.1; do
  for r in 9 10 11 12 13 14 15; do
    f=results/cal6/pers/soft${t}_r$r.tsv
    [ -s $f ] || ./build/rollout --preset best-notables --pool results/cal6/pers_r$r.bin --playouts 32 \
      --horizon 0 --stop-rank $r --moves engine --soft $t --threads $T --seed 9 --out $f.tmp > ${f%.tsv}.log 2>&1 \
      && mv $f.tmp $f
  done
done
echo done > results/cal6/personal.done
scripts/judge_cal6.sh results/disputes/expert.bin results/cal6/jold 0 210 30 $T
echo done > results/cal6/queueA.done
