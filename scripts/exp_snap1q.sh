#!/bin/bash
# The 2-ply curriculum on first-half snapshots: v11c's first half (14M + curriculum) reaches 81% from
# real starts at depth 3, while the best plain snapshot of a new run peaks at 74% (14M). Curriculum
# (1.5M episodes, 25% 2-ply) on the 14M and 18M snapshots; first half evaluated at depth 3 and 4.
set -e
cd "$(dirname "$0")/.."
W=weights/exps1
L=results/exps1
COMMON="--stages sum:20480/14,36864 --train-stage 1 --skip-lower --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 100000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool weights/v11c/pool16.bin --pool-last 1000000 --policy-depth 2 --policy-mix 0.25 --tc-decay 0.1 --episodes 1500000"
for s in e14 e18; do
  if [ ! -f $W/${s}q.w ]; then
    echo "[$(date '+%F %T')] curriculum on $s" >> $L/log
    ./build/gpu_train --load $W/$s.w --resume $W/$s.ckpt $COMMON --save $W/${s}q.w.part --checkpoint $W/${s}q.ckpt > $L/${s}q.log 2>&1
    mv $W/${s}q.w.part $W/${s}q.w
  fi
done
echo "[$(date '+%F %T')] curriculum done" >> $L/log
