#!/bin/bash
# Seed search for the second half: the 4M recipe (exps e4: fresh optimistic, lock, tables, pool2mix) with
# other random seeds; optimistic runs vary a lot between runs. Evaluated later through the whole phase.
set -e
cd "$(dirname "$0")/.."
W=weights/expseed
L=results/expseed
mkdir -p $W $L
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
COMMON="--stages sum:36864 --train-stage 0 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool weights/v11c/pool2mix.bin --pool-last $NPOOL --episodes 4000000"
for sd in 2 3 4; do
  [ -f $W/s$sd.w ] && continue
  echo "[$(date '+%F %T')] seed $sd" >> $L/log
  ./build/gpu_train --load weights/expcpu/start.w $COMMON --seed $sd --save $W/s$sd.w.part --checkpoint $W/s$sd.ckpt > $L/s$sd.log 2>&1
  mv $W/s$sd.w.part $W/s$sd.w
  grep "games  avg" $L/s$sd.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  s$sd /" >> $L/log
done
echo "[$(date '+%F %T')] training done" >> $L/log
