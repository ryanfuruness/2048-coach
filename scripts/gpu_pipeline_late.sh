#!/bin/bash
# Extends a 3-stage network from gpu_pipeline.sh with two stages for the 32768 phase:
#   stage 3: a 32768 tile (no 16384)      stage 4: 32768 + 16384
# These are trained on real 32768 positions (no tile downgrading, --min-gap 15),
# starting from the stage-2 weights and TC state.
set -e
cd "$(dirname "$0")/.."

NAME=${NAME:-gmain}
BASE=${BASE:-p5}
P6_GAMES=${P6_GAMES:-2000000}
P7_GAMES=${P7_GAMES:-2000000}
P8_GAMES=${P8_GAMES:-1000000}
POOL_MAX=${POOL_MAX:-1000000}
GAMES=${GAMES:-32768}
STAGES="14+,14+&13,15+,15+&14"

W=weights/$NAME
L=results/$NAME
T=./build/gpu_train
COMMON="--tc --alpha 1.0 --lambda 0.5 --horizon 3 --games $GAMES --log 50000 --save-every 500000 --min-gap 15"

phase() { echo "[$(date '+%F %T')] $*" | tee -a "$L/pipeline.log"; }

if [ ! -f "$W/p6.w" ]; then
  phase "p6: stage 3 (32768) from pool ($P6_GAMES games)"
  $T --load "$W/$BASE.w" --stages "$STAGES" --train-stage 3 --resume "$W/s2.ckpt" --tc-decay 0.1 \
     --pool "$W/pool_s3.bin" --pool-last "$POOL_MAX" $COMMON --episodes "$P6_GAMES" \
     --collect "$W/pool_s4.bin" --collect-when "15+&14" \
     --save "$W/p6.w.part" --checkpoint "$W/s3.ckpt" > "$L/p6.log" 2>&1
  mv "$W/p6.w.part" "$W/p6.w"
fi

if [ ! -f "$W/p7.w" ]; then
  phase "p7: stage 4 (32768+16384) from pool ($P7_GAMES games)"
  $T --load "$W/p6.w" --stages "$STAGES" --train-stage 4 --resume "$W/s3.ckpt" --tc-decay 0.1 \
     --pool "$W/pool_s4.bin" --pool-last "$POOL_MAX" $COMMON --episodes "$P7_GAMES" \
     --save "$W/p7.w.part" --checkpoint "$W/s4.ckpt" > "$L/p7.log" 2>&1
  mv "$W/p7.w.part" "$W/p7.w"
fi

if [ ! -f "$W/p8.w" ]; then
  phase "p8: stage 3 refresh ($P8_GAMES games)"
  $T --load "$W/p7.w" --stages "$STAGES" --train-stage 3 --resume "$W/s3.ckpt" \
     --pool "$W/pool_s3.bin" --pool-last "$POOL_MAX" $COMMON --episodes "$P8_GAMES" \
     --save "$W/p8.w.part" --checkpoint "$W/s3b.ckpt" > "$L/p8.log" 2>&1
  mv "$W/p8.w.part" "$W/p8.w"
fi

phase "late done: $W/p8.w"
