#!/bin/bash
# The 2-ply curriculum (1.5M episodes, 25% 2-ply) on the dedicated first half's 4M snapshot.
set -e
cd "$(dirname "$0")/.."
W=weights/exph1
L=results/exph1
ST4="sum:20480/14,28672,36864"
COMMON="--stages $ST4 --train-stage 1 --skip-lower --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 100000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool weights/v11c/pool16.bin --pool-last 1000000 --policy-depth 2 --policy-mix 0.25 --tc-decay 0.1 --episodes 1500000"
if [ ! -f $W/e4q.w ]; then
  echo "[$(date '+%F %T')] curriculum on e4" >> $L/log
  ./build/gpu_train --load $W/e4.w --resume $W/e4.ckpt $COMMON --save $W/e4q.w.part --checkpoint $W/e4q.ckpt > $L/e4q.log 2>&1
  mv $W/e4q.w.part $W/e4q.w
fi
echo "[$(date '+%F %T')] curriculum done" >> $L/log
