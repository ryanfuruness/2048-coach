#!/bin/bash
# Multi-stage training, version 7: the best structure so far (v5's split of the 16384 phase)
# rebuilt with Matsuzaki's tuples.
#
# Stages (tile sum): 0 [0, 20480) early game, 1 [20480, 28672) first half of the 16384 phase
# (building the 8192), 2 [28672, 36864) second half (the second 16384 and the 32768 merge),
# 3 [36864, inf) the 32768 phase. At play time stage 3 is not used: boards with a 32768 are
# searched in the downgraded view (play --root-downgrade 15), where stages 1-2 apply.
#
#   s1   stage 1 from the full-game base network (zero-initialised lineage: learns fast and
#        works well under search), from the stage-1 pool; collects the stage-2 pool
#   s2   stage 2 from fresh optimistic weights (the only way it learns the 32768 merge)
#   s2q  stage 2, 2-ply on 25% of the moves (makes it usable under search)
#   s1b  stage 1 refined against the trained stage 2
set -e
cd "$(dirname "$0")/.."

NAME=${NAME:-v7}
BASE=${BASE:-weights/tup/mz.w}            # full-game base network (Matsuzaki tuples)
BASECK=${BASECK:-weights/tup/mz.ckpt}
S0=${S0:-weights/tup/s0cpu.w}             # early-game stage (its stage 0)
POOL1=${POOL1:-weights/v6/pool1.bin}
INIT=${INIT:-320000}
S1_GAMES=${S1_GAMES:-4000000}
S2_GAMES=${S2_GAMES:-12000000}
S2Q_GAMES=${S2Q_GAMES:-1500000}
S1B_GAMES=${S1B_GAMES:-2000000}
POOL_MAX=${POOL_MAX:-1000000}
ST="sum:20480,28672,36864"

W=weights/$NAME
L=results/$NAME
mkdir -p "$W" "$L"
T=./build/gpu_train
COMMON="--stages $ST --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --save-every 2000000"

phase() { echo "[$(date '+%F %T')] $*" | tee -a "$L/pipeline.log"; }
run() {
  local n=$1 d=$2
  shift 2
  [ -f "$W/$n.w" ] && return 0
  phase "$n: $d"
  $T "$@" --save "$W/$n.w.part" --checkpoint "$W/$n.ckpt" > "$L/$n.log" 2>&1
  mv "$W/$n.w.part" "$W/$n.w"
}

# 4-stage starting file: stage 0 from S0, stages 1-3 copies of the base network
if [ ! -f $W/init.w ]; then
  python3 scripts/select_stages.py $BASE $W/init.tmp.w 0,0,0,0
  python3 scripts/splice_stage.py $W/init.tmp.w 0 $S0 0 $W/init.w
  rm -f $W/init.tmp.w
fi

run s1 "stage 1 [20480,28672) from the base network ($S1_GAMES games)" --load $W/init.w --train-stage 1 \
  --resume $BASECK --tc-decay 0.1 --fresh 2,3 --init $INIT $COMMON --log 250000 --episodes $S1_GAMES \
  --pool $POOL1 --pool-last $POOL_MAX --collect $W/pool2.bin --collect-when sum:28672
run s2 "stage 2 [28672,36864) fresh optimistic, 1-ply ($S2_GAMES games)" --load $W/s1.w --train-stage 2 --fresh 2 \
  --init $INIT $COMMON --log 500000 --episodes $S2_GAMES --pool $W/pool2.bin --pool-last $POOL_MAX
run s2q "stage 2, 2-ply on 25% of the moves ($S2Q_GAMES games)" --load $W/s2.w --train-stage 2 --resume $W/s2.ckpt \
  --tc-decay 0.1 $COMMON --log 100000 --policy-depth 2 --policy-mix 0.25 --episodes $S2Q_GAMES \
  --pool $W/pool2.bin --pool-last $POOL_MAX
run s1b "stage 1 refined against the trained stage 2 ($S1B_GAMES games)" --load $W/s2q.w --train-stage 1 \
  --resume $W/s1.ckpt --tc-decay 0.1 $COMMON --log 250000 --episodes $S1B_GAMES --pool $POOL1 --pool-last $POOL_MAX
cp $W/s1b.w $W/final.w
phase "done: $W/final.w ($ST; play with --root-downgrade 15)"
