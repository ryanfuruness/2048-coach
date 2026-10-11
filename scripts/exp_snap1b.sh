#!/bin/bash
# Continuation of exp_snap1: the whole-phase network took off late (11-12M episodes); more snapshots
# at 15, 16, 18M to find where its search strength peaks.
set -e
cd "$(dirname "$0")/.."
W=weights/exps1
L=results/exps1
ST3="sum:20480/14,36864"
COMMON="--stages $ST3 --train-stage 1 --skip-lower --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool weights/v11c/pool16.bin --pool-last 1000000"
prev=14; total=14
for seg in 15 16 18; do
  n=$(( (seg - total) * 1000000 ))
  if [ ! -f $W/e$seg.w ]; then
    echo "[$(date '+%F %T')] training to ${seg}M" >> $L/log
    ./build/gpu_train --load $W/e$prev.w --resume $W/e$prev.ckpt $COMMON --episodes $n --save $W/e$seg.w.part \
      --checkpoint $W/e$seg.ckpt > $L/e$seg.log 2>&1
    mv $W/e$seg.w.part $W/e$seg.w
    grep "games  avg" $L/e$seg.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  e$seg /" >> $L/log
  fi
  prev=$seg; total=$seg
done
echo "[$(date '+%F %T')] training b done" >> $L/log
