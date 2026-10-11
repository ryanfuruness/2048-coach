#!/bin/bash
# Backward refinement after pipeline_v4.sh: stages 5..1 are trained further (their own TC
# state, decayed), now bootstrapping from the trained later stages instead of optimistic
# constants. Start positions come from the pools of the forward pass.
set -e
cd "$(dirname "$0")/.."

NAME=${NAME:-v4}
IN=${IN:-weights/$NAME/final.w}
GAMES=${GAMES:-5000000}
POOL_MAX=${POOL_MAX:-1000000}
POOL1=${POOL1:-weights/v3/pool1.bin}
FIRST=${FIRST:-5}
LAST=${LAST:-1}
THRESH=(20480 28672 36864 45056 53248 61440)
STAGES="sum:$(IFS=,; echo "${THRESH[*]}")"

W=weights/$NAME
L=results/$NAME
T=./build/gpu_train
COMMON="--stages $STAGES --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 250000 --save-every 2000000 --tc-decay 0.1"

phase() { echo "[$(date '+%F %T')] $*" | tee -a "$L/pipeline.log"; }

prev=$IN
for ((k = FIRST; k >= LAST; k--)); do
  out=$W/b$k.w
  pool=$W/pool$k.bin
  ((k == 1)) && pool=$POOL1
  if [ ! -f "$out" ]; then
    phase "b$k: stage $k refined against the trained later stages ($GAMES games)"
    $T --load "$prev" --train-stage $k --resume $W/s$k.ckpt $COMMON --episodes $GAMES \
       --pool "$pool" --pool-last $POOL_MAX --save "$out.part" --checkpoint $W/b$k.ckpt > "$L/b$k.log" 2>&1
    mv "$out.part" "$out"
  fi
  prev=$out
done
cp "$prev" $W/final_b.w
phase "backward done: $W/final_b.w"
