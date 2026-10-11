#!/bin/bash
# Workstream review: full-coverage player-level screen (human move model, all moves, 32 CRN playouts, to the next
# milestone). Big groups are split into slices of 400 positions so the work spreads over the processes.
# usage (in ~/2048_review): scripts/review_roll_full.sh [PARALLEL]
P=${1:-12}
ulimit -s unlimited
mkdir -p results/review/roll_f
tail -n +2 results/review/fgroups.tsv | cut -f1-4 | while read g s R n; do
  for ((k = 0; k < n; k += 400)); do echo "$g $s $R $k"; done
done | xargs -P $P -L 1 sh -c \
  './build/rollout --preset best-notables --weights weights/best_v6b.w --pool results/review/fgroups/$0.bin --skip $3 --first 400 \
     --moves all --playouts 32 --horizon 0 --stop-rank $2 --human $1 --threads 1 --seed 31337 \
     --out results/review/roll_f/$0_$3.tsv 2> results/review/roll_f/$0_$3.err'
echo done > results/review/roll_f.done
