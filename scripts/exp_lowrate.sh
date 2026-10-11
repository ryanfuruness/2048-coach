#!/bin/bash
# Can a lower rate after the peak keep improving instead of drifting? The 4M second half (exps e4) continued
# with TC meta-rate 0.3 and 0.1 (instead of 1.0) for 1M and 2M more episodes.
set -e
cd "$(dirname "$0")/.."
W=weights/explr
L=results/explr
mkdir -p $W $L
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
COMMON="--stages sum:36864 --train-stage 0 --stop-at-boundary --tc --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool weights/v11c/pool2mix.bin --pool-last $NPOOL --episodes 1000000"
for a in 0.3 0.1; do
  t=${a#0.}
  [ -f $W/a${t}_1.w ] || { echo "[$(date '+%F %T')] alpha $a +1M" >> $L/log; ./build/gpu_train --load weights/exps/e4.w --resume weights/exps/e4.ckpt $COMMON --alpha $a --save $W/a${t}_1.w.part --checkpoint $W/a${t}_1.ckpt > $L/a${t}_1.log 2>&1; mv $W/a${t}_1.w.part $W/a${t}_1.w; }
  [ -f $W/a${t}_2.w ] || { echo "[$(date '+%F %T')] alpha $a +2M" >> $L/log; ./build/gpu_train --load $W/a${t}_1.w --resume $W/a${t}_1.ckpt $COMMON --alpha $a --save $W/a${t}_2.w.part --checkpoint $W/a${t}_2.ckpt > $L/a${t}_2.log 2>&1; mv $W/a${t}_2.w.part $W/a${t}_2.w; }
done
echo "[$(date '+%F %T')] training done" >> $L/log
