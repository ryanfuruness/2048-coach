#!/bin/bash
# Workstream review: chances-curve rollouts (human move model at the stretch's skill to the stretch's target).
# usage (in ~/2048_review): scripts/review_roll_curve.sh [PARALLEL]
P=${1:-12}
ulimit -s unlimited
mkdir -p results/review/roll_c
tail -n +2 results/review/cgroups.tsv | cut -f1-3 | xargs -P $P -L 1 sh -c \
  './build/rollout --preset best-notables --weights weights/best_v6b.w --pool results/review/cgroups/$0.bin --moves all \
     --playouts 64 --horizon 0 --stop-rank $2 --human $1 --threads 1 --seed 909 --out results/review/roll_c/$0.tsv \
     2> results/review/roll_c/$0.err'
echo done > results/review/roll_c.done
