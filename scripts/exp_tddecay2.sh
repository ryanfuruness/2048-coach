#!/bin/bash
# Continue the plain-TD second half (exp_tddecay) for longer: alpha 0.1 to 20M, then 0.03 to 28M.
set -e
cd "$(dirname "$0")/.."
W=weights/exptd
L=results/exptd
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
COMMON="--stages sum:36864 --train-stage 0 --stop-at-boundary --td --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool weights/v11c/pool2mix.bin --pool-last $NPOOL"
prev=12
for seg in "20 0.1" "28 0.03"; do
  set -- $seg; m=$1; a=$2
  if [ ! -f $W/e$m.w ]; then
    echo "[$(date '+%F %T')] TD alpha $a to ${m}M" >> $L/log
    ./build/gpu_train --load $W/e$prev.w $COMMON --alpha $a --episodes 8000000 --save $W/e$m.w.part > $L/e$m.log 2>&1
    mv $W/e$m.w.part $W/e$m.w
    grep "games  avg" $L/e$m.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  e$m /" >> $L/log
  fi
  prev=$m
done
echo "[$(date '+%F %T')] training 2 done" >> $L/log
