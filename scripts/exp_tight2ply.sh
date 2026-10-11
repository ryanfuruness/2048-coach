#!/bin/bash
# Second half trained with the 2-ply policy only on tight boards (<= 4 or <= 3 empty cells), the positions where
# budgeted deepening helps at play time; elsewhere greedy as usual. Recipe of seed s6 otherwise (fresh optimistic, lock,
# k>=6 tables, pool2mix, 4M episodes, seed 6). Evaluate as stage 3 of best_v5bb.
set -e
cd "$(dirname "$0")/.."
W=weights/expt2
L=results/expt2
mkdir -p $W $L
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
for e in 4 3; do
  if [ ! -f $W/m$e.w ]; then
    echo "[$(date '+%F %T')] 2-ply when <= $e empty" >> $L/log
    ./build/gpu_train --load weights/expcpu/start.w --stages sum:36864 --train-stage 0 --stop-at-boundary --tc --alpha 1.0 \
      --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 \
      --endgame-full 2 --endgame-min-rank 7 --pool weights/v11c/pool2mix.bin --pool-last $NPOOL --episodes 4000000 --seed 6 \
      --policy-depth 2 --policy-max-empty $e --policy-mix 1.0 --save $W/m$e.w.part > $L/m$e.log 2>&1
    mv $W/m$e.w.part $W/m$e.w
    grep "games  avg" $L/m$e.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  m$e /" >> $L/log
  fi
done
echo "[$(date '+%F %T')] done" >> $L/log
