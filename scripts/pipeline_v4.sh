#!/bin/bash
# Multi-stage training, version 4: every late stage learns from FRESH optimistic weights.
#
# Version 3 initialised stage k from stage k-1. That carries over the pessimism of
# a network trained from zero: positions of the next phase were only ever seen in
# games that died there, so their weights are low and the greedy policy never
# ventures into them (stage 2 then never made a single 32768 in 3M episodes).
# Here a stage starts with every weight at INIT/F (optimistic initialisation,
# Guei et al.), and so do the untrained later stages it bootstraps from. With that,
# stage 2 went from 0% to 19% of episodes reaching 32768+4096 within 4M episodes.
#
# Stages are tile-sum ranges (boundaries at "a big tile plus 4096"):
#   0: [0, 20480)  1: [20480, 28672)  2: [28672, 36864)  3: [36864, 45056)
#   4: [45056, 53248)  5: [53248, 61440)  6: [61440, inf)
#
# Phases (each skipped if its output exists):
#   s1   stage 1 fresh, from pool1, bootstrapping from the trained stage 2; collects pool2
#   s2   stage 2 continued (own TC state) from the new pool2; collects pool3
#   s3..s6  stage k fresh from pool k; collects pool k+1
#   s0   stage 0 continued from the base network, more episodes (early game)
set -e
cd "$(dirname "$0")/.."

NAME=${NAME:-v4}
BASE=${BASE:-weights/s2x/otc2.w}          # 7-stage file with a trained stage 2
BASE_S2CKPT=${BASE_S2CKPT:-weights/s2x/otc2.ckpt}
S0CKPT=${S0CKPT:-weights/v3/p1.ckpt}
POOL1=${POOL1:-weights/v3/pool1.bin}
INIT=${INIT:-320000}
S1_GAMES=${S1_GAMES:-15000000}
S2_GAMES=${S2_GAMES:-10000000}
SK_GAMES=${SK_GAMES:-10000000}
S0_GAMES=${S0_GAMES:-15000000}
POOL_MAX=${POOL_MAX:-1000000}
THRESH=(20480 28672 36864 45056 53248 61440)
STAGES="sum:$(IFS=,; echo "${THRESH[*]}")"

W=weights/$NAME
L=results/$NAME
mkdir -p "$W" "$L"
T=./build/gpu_train
COMMON="--stages $STAGES --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 250000 --save-every 2000000"

phase() { echo "[$(date '+%F %T')] $*" | tee -a "$L/pipeline.log"; }
run() {  # run OUT LOG args...: trains into OUT (via OUT.part) unless OUT exists
  local out=$1 log=$2
  shift 2
  [ -f "$out" ] && return 0
  $T "$@" --save "$out.part" > "$log" 2>&1
  mv "$out.part" "$out"
}

phase "s1: stage 1 fresh from pool1 ($S1_GAMES games)"
run $W/s1.w $L/s1.log --load "$BASE" --train-stage 1 --fresh 1 --init $INIT $COMMON --episodes $S1_GAMES \
  --pool "$POOL1" --pool-last $POOL_MAX --collect $W/pool2.bin --collect-when sum:${THRESH[1]} --checkpoint $W/s1.ckpt

phase "s2: stage 2 continued from the new pool2 ($S2_GAMES games)"
run $W/s2.w $L/s2.log --load $W/s1.w --train-stage 2 --resume "$BASE_S2CKPT" $COMMON --episodes $S2_GAMES \
  --pool $W/pool2.bin --pool-last $POOL_MAX --collect $W/pool3.bin --collect-when sum:${THRESH[2]} --checkpoint $W/s2.ckpt

prev=$W/s2.w
for k in 3 4 5 6; do
  collect=""
  if ((k < 6)); then collect="--collect $W/pool$((k + 1)).bin --collect-when sum:${THRESH[$k]}"; fi
  phase "s$k: stage $k fresh from pool$k ($SK_GAMES games)"
  run $W/s$k.w $L/s$k.log --load $prev --train-stage $k --fresh $k --init $INIT $COMMON --episodes $SK_GAMES \
    --pool $W/pool$k.bin --pool-last $POOL_MAX $collect --checkpoint $W/s$k.ckpt
  prev=$W/s$k.w
done

phase "s0: stage 0 continued from the base network ($S0_GAMES games)"
run $W/s0.w $L/s0.log --load $prev --train-stage 0 --resume "$S0CKPT" --tc-decay 0.1 $COMMON --episodes $S0_GAMES \
  --checkpoint $W/s0.ckpt
cp $W/s0.w $W/final.w
phase "done: $W/final.w ($STAGES)"
