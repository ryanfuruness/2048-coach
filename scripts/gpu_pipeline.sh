#!/bin/bash
# Multi-stage training pipeline on the GPU (build/gpu_train).
#
#   stage 0: boards without a 16384 tile
#   stage 1: a 16384 tile (and no 8192)
#   stage 2: 16384 + 8192
# Boards holding 32768+ are evaluated through tile downgrading, so they reuse
# the stage 1/2 weights.
#
# Phases (each is skipped if its output already exists, so the script resumes):
#   p1  single-stage TC(lambda) from scratch; collects stage-1 entry positions
#   p2  stage 1 from the 16384 pool (init: p1 incl. TC state); collects stage-2 entries
#   p3  stage 2 from the 16384+8192 pool (init: stage 1 incl. TC state)
#   p4  stage 1 again, now bootstrapping from the trained stage 2
#   p5  stage 0 fine-tuning against the trained stages 1-2
set -e
cd "$(dirname "$0")/.."

PATTERNS=${PATTERNS:-"8x6"}
NAME=${NAME:-gmain}
P1_GAMES=${P1_GAMES:-5000000}
P2_GAMES=${P2_GAMES:-3000000}
P3_GAMES=${P3_GAMES:-3000000}
P4_GAMES=${P4_GAMES:-1000000}
P5_GAMES=${P5_GAMES:-1000000}
POOL_MAX=${POOL_MAX:-1000000}
STAGES=${STAGES:-"14+,14+&13"}
GAMES=${GAMES:-32768}

W=weights/$NAME
L=results/$NAME
mkdir -p "$W" "$L"
T=./build/gpu_train
COMMON="--tc --alpha 1.0 --lambda 0.5 --horizon 3 --games $GAMES --log 50000 --save-every 500000"

phase() { echo "[$(date '+%F %T')] $*" | tee -a "$L/pipeline.log"; }

if [ ! -f "$W/p1.w" ]; then
  phase "p1: single-stage from scratch ($P1_GAMES games)"
  $T --patterns "$PATTERNS" $COMMON --episodes "$P1_GAMES" \
     --collect "$W/pool_s1.bin" --collect-when "14+" \
     --save "$W/p1.w.part" --checkpoint "$W/p1.ckpt" > "$L/p1.log" 2>&1
  mv "$W/p1.w.part" "$W/p1.w"
fi

if [ ! -f "$W/p2.w" ]; then
  phase "p2: stage 1 from pool ($P2_GAMES games)"
  $T --load "$W/p1.w" --stages "$STAGES" --train-stage 1 --resume "$W/p1.ckpt" --tc-decay 0.1 \
     --pool "$W/pool_s1.bin" --pool-last "$POOL_MAX" $COMMON --episodes "$P2_GAMES" \
     --collect "$W/pool_s2.bin" --collect-when "14+&13" \
     --save "$W/p2.w.part" --checkpoint "$W/s1.ckpt" > "$L/p2.log" 2>&1
  mv "$W/p2.w.part" "$W/p2.w"
fi

if [ ! -f "$W/p3.w" ]; then
  phase "p3: stage 2 from pool ($P3_GAMES games)"
  $T --load "$W/p2.w" --stages "$STAGES" --train-stage 2 --resume "$W/s1.ckpt" --tc-decay 0.1 \
     --pool "$W/pool_s2.bin" --pool-last "$POOL_MAX" $COMMON --episodes "$P3_GAMES" \
     --collect "$W/pool_s3.bin" --collect-when "15+" \
     --save "$W/p3.w.part" --checkpoint "$W/s2.ckpt" > "$L/p3.log" 2>&1
  mv "$W/p3.w.part" "$W/p3.w"
fi

if [ ! -f "$W/p4.w" ]; then
  phase "p4: stage 1 refresh ($P4_GAMES games)"
  $T --load "$W/p3.w" --stages "$STAGES" --train-stage 1 --resume "$W/s1.ckpt" \
     --pool "$W/pool_s1.bin" --pool-last "$POOL_MAX" $COMMON --episodes "$P4_GAMES" \
     --save "$W/p4.w.part" --checkpoint "$W/s1b.ckpt" > "$L/p4.log" 2>&1
  mv "$W/p4.w.part" "$W/p4.w"
fi

if [ ! -f "$W/p5.w" ]; then
  phase "p5: stage 0 fine-tune ($P5_GAMES games)"
  $T --load "$W/p4.w" --stages "$STAGES" --train-stage 0 --resume "$W/p1.ckpt" \
     $COMMON --episodes "$P5_GAMES" \
     --save "$W/p5.w.part" --checkpoint "$W/s0.ckpt" > "$L/p5.log" 2>&1
  mv "$W/p5.w.part" "$W/p5.w"
fi

phase "done: $W/p5.w"
