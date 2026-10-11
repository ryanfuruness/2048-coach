#!/bin/bash
# The early-game network s0cpu continued with the corner lock from the 8192 on (rank 13) and the k>=6 tables in the loop,
# so it learns to keep snakes the tables can finish (the 16384 phase gained a lot from lock + tables; s0cpu was never
# trained with a lock: forcing lock 13 on it cost ~8 points). Resumes s0cpu's CPU checkpoint on the GPU; +1M and +2M.
set -e
cd "$(dirname "$0")/.."
W=weights/expel
L=results/expel
mkdir -p $W $L
while ps -eo args | grep -q "^/bin/bash scripts/exp_tight2ply.sh"; do sleep 60; done
COMMON="--stages sum:20480 --train-stage 0 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 250000 --corner-lock 13 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 6"
if [ ! -f $W/l1.w ]; then
  echo "[$(date '+%F %T')] s0cpu + lock 13 + tables: +1M" >> $L/log
  ./build/gpu_train --load weights/tup/s0cpu.w --resume weights/tup/s0cpu.ckpt $COMMON --episodes 1000000 \
    --save $W/l1.w.part --checkpoint $W/l1.ckpt > $L/l1.log 2>&1
  mv $W/l1.w.part $W/l1.w
  grep "games  avg" $L/l1.log | tail -n 1 | cut -c 1-170 | sed "s/^/  l1 /" >> $L/log
fi
if [ ! -f $W/l2.w ]; then
  echo "[$(date '+%F %T')] +2M" >> $L/log
  ./build/gpu_train --load $W/l1.w --resume $W/l1.ckpt $COMMON --episodes 1000000 --save $W/l2.w.part > $L/l2.log 2>&1
  mv $W/l2.w.part $W/l2.w
  rm -f $W/l1.ckpt
  grep "games  avg" $L/l2.log | tail -n 1 | cut -c 1-170 | sed "s/^/  l2 /" >> $L/log
fi
echo "[$(date '+%F %T')] done" >> $L/log
