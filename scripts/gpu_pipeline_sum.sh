#!/bin/bash
# Multi-stage training with tile-sum stages (build/gpu_train).
#
# Stage k covers boards whose tile sum lies in [T_k, T_{k+1}); the tile sum never
# decreases, so a game passes through the stages in order. Each stage is trained
# on episodes that start from positions where the game first entered it and stop
# as soon as the game leaves it (bootstrapping from the next stage's value).
#
#   p1        single-stage network trained on full games from scratch
#   fwd k     stage k (k = 1..K) from its entry pool, initialised from stage k-1;
#             collects the entry pool of stage k+1
#   bwd k     stage k (k = K-1..0) refined against the trained later stages
# Every phase is skipped if its output exists, so the script can be resumed.
set -e
cd "$(dirname "$0")/.."

PATTERNS=${PATTERNS:-"8x6"}
NAME=${NAME:-sum8}
P1_GAMES=${P1_GAMES:-8000000}
FWD_GAMES=${FWD_GAMES:-2000000}
BWD_GAMES=${BWD_GAMES:-1000000}
BWD0_GAMES=${BWD0_GAMES:-2000000}
POOL_MAX=${POOL_MAX:-1000000}
GAMES=${GAMES:-32768}
THRESH=(16384 24576 32768 40960 49152 57344)
STAGES="sum:$(IFS=,; echo "${THRESH[*]}")"
K=${#THRESH[@]}

W=weights/$NAME
L=results/$NAME
mkdir -p "$W" "$L"
T=./build/gpu_train
COMMON="--tc --alpha 1.0 --lambda 0.5 --horizon 3 --games $GAMES --log 50000 --save-every 500000"

phase() { echo "[$(date '+%F %T')] $*" | tee -a "$L/pipeline.log"; }

# p1: single stage on full games
if [ ! -f "$W/p1.w" ]; then
  phase "p1: single-stage from scratch ($P1_GAMES games)"
  $T --patterns "$PATTERNS" $COMMON --episodes "$P1_GAMES" \
     --collect "$W/pool1.bin" --collect-when "sum:${THRESH[0]}" \
     --save "$W/p1.w.part" --checkpoint "$W/p1.ckpt" > "$L/p1.log" 2>&1
  mv "$W/p1.w.part" "$W/p1.w"
  cp "$W/p1.ckpt" "$W/s0.ckpt"
fi

# forward pass
prev="$W/p1.w"
for ((k = 1; k <= K; k++)); do
  out="$W/fwd$k.w"
  if [ ! -f "$out" ]; then
    phase "fwd $k: stage $k from pool$k ($FWD_GAMES games)"
    collect=""
    if ((k < K)); then collect="--collect $W/pool$((k + 1)).bin --collect-when sum:${THRESH[$k]}"; fi
    $T --load "$prev" --stages "$STAGES" --train-stage $k --resume "$W/s$((k - 1)).ckpt" --tc-decay 0.1 \
       --pool "$W/pool$k.bin" --pool-last "$POOL_MAX" --stop-at-boundary $COMMON --episodes "$FWD_GAMES" \
       $collect --save "$out.part" --checkpoint "$W/s$k.ckpt" > "$L/fwd$k.log" 2>&1
    mv "$out.part" "$out"
  fi
  prev="$out"
done

# backward pass
for ((k = K - 1; k >= 0; k--)); do
  out="$W/bwd$k.w"
  if [ ! -f "$out" ]; then
    if ((k == 0)); then
      phase "bwd 0: stage 0 from scratch ($BWD0_GAMES games)"
      $T --load "$prev" --stages "$STAGES" --train-stage 0 --resume "$W/s0.ckpt" \
         --stop-at-boundary $COMMON --episodes "$BWD0_GAMES" \
         --save "$out.part" --checkpoint "$W/s0b.ckpt" > "$L/bwd0.log" 2>&1
    else
      phase "bwd $k: stage $k from pool$k ($BWD_GAMES games)"
      $T --load "$prev" --stages "$STAGES" --train-stage $k --resume "$W/s$k.ckpt" \
         --pool "$W/pool$k.bin" --pool-last "$POOL_MAX" --stop-at-boundary $COMMON --episodes "$BWD_GAMES" \
         --save "$out.part" --checkpoint "$W/s${k}b.ckpt" > "$L/bwd$k.log" 2>&1
    fi
    mv "$out.part" "$out"
  fi
  prev="$out"
done
cp "$prev" "$W/final.w"
phase "done: $W/final.w  (stages $STAGES)"
