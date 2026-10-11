#!/bin/bash
# Workstream review: stage-2 rollouts (human move model, all moves, 256 CRN playouts, to the next milestone), slices
# of 100 positions. usage (in ~/2048_review): scripts/review_roll_s2.sh [PARALLEL]
P=${1:-14}
ulimit -s unlimited
mkdir -p results/review/roll_s2
tail -n +2 results/review/s2groups.tsv | cut -f1-4 | while read g s R n; do
  for ((k = 0; k < n; k += 100)); do echo "$g $s $R $k"; done
done | xargs -P $P -L 1 sh -c \
  './build/rollout --preset best-notables --weights weights/best_v6b.w --pool results/review/s2groups/$0.bin --skip $3 --first 100 \
     --moves all --playouts 256 --horizon 0 --stop-rank $2 --human $1 --threads 1 --seed 271828 \
     --out results/review/roll_s2/$0_$3.tsv 2> results/review/roll_s2/$0_$3.err'
echo done > results/review/roll_s2.done
