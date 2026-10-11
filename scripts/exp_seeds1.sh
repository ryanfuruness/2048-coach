#!/bin/bash
# Seed search for the dedicated first half (exph1 recipe: fresh optimistic, lock, tables, pool16, bootstrap
# from the 4M second half with never-trained weights zeroed), 4M episodes, seeds 2/3/4.
set -e
cd "$(dirname "$0")/.."
W=weights/expseed
L=results/expseed
COMMON="--stages sum:20480/14,28672,36864 --train-stage 1 --skip-lower --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool weights/v11c/pool16.bin --pool-last 1000000 --episodes 4000000"
for sd in 2 3 4; do
  [ -f $W/h$sd.w ] && continue
  echo "[$(date '+%F %T')] first half, seed $sd" >> $L/log
  ./build/gpu_train --load weights/exph1/start.w $COMMON --seed $sd --save $W/h$sd.w.part --checkpoint $W/h$sd.ckpt > $L/h$sd.log 2>&1
  mv $W/h$sd.w.part $W/h$sd.w
  grep "games  avg" $L/h$sd.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  h$sd /" >> $L/log
done
echo "[$(date '+%F %T')] first halves done" >> $L/log
