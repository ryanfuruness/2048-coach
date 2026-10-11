#!/bin/bash
# Stage B [24576, 28672) seeds (exp_split's recipe: fresh optimistic, lock, tables, pool24, bootstrapping from the 4M
# second half): b3 (seed 1) is the best snapshot of a single run (vb3 61.0%, k5vb3 61.7%). Snapshots at 3M and 4M.
set -e
cd "$(dirname "$0")/.."
W=weights/expsplit
L=results/expsplit
while ps -eo args | grep -q "^/bin/bash scripts/exp_seeds3.sh"; do sleep 30; done
ST5="sum:20480/14,24576,28672,36864"
COMMON="--stages $ST5 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --skip-lower --train-stage 2 --pool $W/pool24.bin --pool-last 1000000"
for sd in 2 3; do
  if [ ! -f $W/b3s$sd.w ]; then
    echo "[$(date '+%F %T')] B seed $sd: to 3M" >> $L/log
    ./build/gpu_train --load $W/start.w $COMMON --seed $sd --episodes 3000000 --save $W/b3s$sd.w.part --checkpoint $W/b3s$sd.ckpt > $L/b3s$sd.log 2>&1
    mv $W/b3s$sd.w.part $W/b3s$sd.w
  fi
  if [ ! -f $W/b4s$sd.w ]; then
    echo "[$(date '+%F %T')] B seed $sd: to 4M" >> $L/log
    ./build/gpu_train --load $W/b3s$sd.w --resume $W/b3s$sd.ckpt $COMMON --seed $sd --episodes 1000000 --save $W/b4s$sd.w.part > $L/b4s$sd.log 2>&1
    mv $W/b4s$sd.w.part $W/b4s$sd.w
    rm -f $W/b3s$sd.ckpt
  fi
done
echo "[$(date '+%F %T')] B seeds done" >> $L/log
