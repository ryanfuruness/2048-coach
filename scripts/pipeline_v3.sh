#!/bin/bash
# Multi-stage training, version 3 (build/gpu_train):
#   * optimistic values for never-visited weights (Guei et al.'s optimistic
#     initialisation, applied where it matters): the base network may be trained
#     from zero, and every weight still exactly 0 starts at OPT_FILL/F in the
#     stage phases, so unexplored late-game configurations look attractive;
#   * tile-sum stages whose boundaries sit at "calm" points (a big tile plus
#     4096 of small tiles), not in the middle of a merge cascade.
#
# Stage k covers boards whose tile sum lies in [T_k, T_{k+1}); the sum never
# decreases, so a game passes through the stages in order. Stage k >= 1 is
# trained on episodes starting where games first entered it; they stop when the
# game leaves it, bootstrapping from the next stage's value.
#
#   p1        single stage, full games, optimistic init; collects the stage-1 pool
#   p1tc      (optional) TC fine-tuning of p1
#   fwd k     stage k from its entry pool, initialised from stage k-1 (weights and
#             TC state); collects the entry pool of stage k+1
#   bwd k     stage k refined against the trained later stages (k = K-1 .. 0)
# Every phase is skipped if its output exists, so the script can be resumed.
set -e
cd "$(dirname "$0")/.."

PATTERNS=${PATTERNS:-"012345 456789 012456 45689a 012348 014567 012346 01267b"}
NAME=${NAME:-v3}
P1_ARGS=${P1_ARGS:-"--tc --alpha 1.0 --init 320000"}
P1_GAMES=${P1_GAMES:-10000000}
P1TC_GAMES=${P1TC_GAMES:-0}
FWD_GAMES=${FWD_GAMES:-3000000}
BWD_GAMES=${BWD_GAMES:-2000000}
BWD0_GAMES=${BWD0_GAMES:-3000000}
POOL_MAX=${POOL_MAX:-1000000}
OPT_FILL=${OPT_FILL:-320000}  # never-visited weights start optimistic in the stage phases
GAMES=${GAMES:-32768}
read -r -a THRESH <<< "${THRESH:-20480 28672 36864 45056 53248 61440}"
STAGES="sum:$(IFS=,; echo "${THRESH[*]}")"
K=${#THRESH[@]}

W=weights/$NAME
L=results/$NAME
mkdir -p "$W" "$L"
T=./build/gpu_train
LAM="--lambda 0.5 --horizon 3 --games $GAMES --log 100000"
COMMON="--tc --alpha 1.0 $LAM --save-every 1000000"
SCOMMON="$COMMON --opt-fill $OPT_FILL"

phase() { echo "[$(date '+%F %T')] $*" | tee -a "$L/pipeline.log"; }

if [ ! -f "$W/p1.w" ]; then
  phase "p1: single stage from scratch ($P1_GAMES games, $P1_ARGS)"
  $T --patterns "$PATTERNS" $P1_ARGS $LAM --save-every 1000000 --episodes "$P1_GAMES" \
     --collect "$W/pool1.bin" --collect-when "sum:${THRESH[0]}" \
     --save "$W/p1.w.part" --checkpoint "$W/p1.ckpt" > "$L/p1.log" 2>&1
  mv "$W/p1.w.part" "$W/p1.w"
fi
base="$W/p1.w"
if ((P1TC_GAMES > 0)); then
  if [ ! -f "$W/p1tc.w" ]; then
    phase "p1tc: TC fine-tuning ($P1TC_GAMES games)"
    $T --load "$W/p1.w" --resume "$W/p1.ckpt" --tc-decay 0 $COMMON --episodes "$P1TC_GAMES" \
       --collect "$W/pool1.bin" --collect-when "sum:${THRESH[0]}" \
       --save "$W/p1tc.w.part" --checkpoint "$W/p1tc.ckpt" > "$L/p1tc.log" 2>&1
    mv "$W/p1tc.w.part" "$W/p1tc.w"
  fi
  base="$W/p1tc.w"
  [ -f "$W/s0.ckpt" ] || cp "$W/p1tc.ckpt" "$W/s0.ckpt"
else
  [ -f "$W/s0.ckpt" ] || cp "$W/p1.ckpt" "$W/s0.ckpt"
fi

# forward pass
prev="$base"
for ((k = 1; k <= K; k++)); do
  out="$W/fwd$k.w"
  if [ ! -f "$out" ]; then
    phase "fwd $k: stage $k from pool$k ($FWD_GAMES games)"
    collect=""
    if ((k < K)); then collect="--collect $W/pool$((k + 1)).bin --collect-when sum:${THRESH[$k]}"; fi
    $T --load "$prev" --stages "$STAGES" --train-stage $k --resume "$W/s$((k - 1)).ckpt" --tc-decay 0.1 \
       --pool "$W/pool$k.bin" --pool-last "$POOL_MAX" --stop-at-boundary $SCOMMON --episodes "$FWD_GAMES" \
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
      phase "bwd 0: stage 0 from the initial position ($BWD0_GAMES games)"
      $T --load "$prev" --stages "$STAGES" --train-stage 0 --resume "$W/s0.ckpt" --tc-decay 0.1 \
         --stop-at-boundary $SCOMMON --episodes "$BWD0_GAMES" \
         --save "$out.part" --checkpoint "$W/s0b.ckpt" > "$L/bwd0.log" 2>&1
    else
      phase "bwd $k: stage $k from pool$k ($BWD_GAMES games)"
      $T --load "$prev" --stages "$STAGES" --train-stage $k --resume "$W/s$k.ckpt" --tc-decay 0.1 \
         --pool "$W/pool$k.bin" --pool-last "$POOL_MAX" --stop-at-boundary $SCOMMON --episodes "$BWD_GAMES" \
         --save "$out.part" --checkpoint "$W/s${k}b.ckpt" > "$L/bwd$k.log" 2>&1
    fi
    mv "$out.part" "$out"
  fi
  prev="$out"
done
cp "$prev" "$W/final.w"
phase "done: $W/final.w  (stages $STAGES)"
