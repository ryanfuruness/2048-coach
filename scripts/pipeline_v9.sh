#!/bin/bash
# Multi-stage training, version 9: a second half of the 16384 phase trained on GOOD formations.
#
# The first half of the 16384 phase decides the formation the second half has to work with.
# A network trained from zero weights builds the 8192 in the far corner (0 of 286 positions
# with it next to the 16384), which leaves two 16384s at opposite ends to be merged; the
# optimistic network of v6 keeps it next to the 16384 (298 of 298) but is weaker as a whole.
# So: the first half is played by v6's network, and the second half gets a dedicated stage
# trained only on the formations that network produces.
#
# Stages (tile sum, Matsuzaki tuples): 0 [0,20480) early game, 1 [20480,28672) first half,
# 2 [28672,36864) second half, 3 [36864,inf) (played through root downgrading).
set -e
cd "$(dirname "$0")/.."

NAME=${NAME:-v9}
S0=${S0:-weights/tup/s0cpu.w}             # early game (its stage 0)
S1=${S1:-weights/v6/s1q1.w}               # first half: v6's 16384-phase stage (its stage 1)
POOL1=${POOL1:-weights/v6/pool1.bin}
INIT=${INIT:-320000}
POOL_GAMES=${POOL_GAMES:-1200000}
S2_GAMES=${S2_GAMES:-12000000}
S2Q_GAMES=${S2Q_GAMES:-1500000}
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

# 4-stage file: stage 0 from S0, stage 1 from S1, stages 2-3 placeholders (made fresh below)
if [ ! -f $W/init.w ]; then
  python3 scripts/select_stages.py $S1 $W/init.tmp.w 0,1,1,1
  python3 scripts/splice_stage.py $W/init.tmp.w 0 $S0 0 $W/init.w
  rm -f $W/init.tmp.w
fi

# stage-2 pool: positions where v6's network (2-ply on half the moves) first reaches 28672
if [ ! -f $W/pool2g.bin ]; then
  phase "pool2g: stage-2 entries from v6's first half (good formations)"
  $T --load $W/init.w --stages $ST --train-stage 1 --fresh 2,3 --init $INIT --no-learn --policy-depth 2 --policy-mix 0.5 \
     --pool $POOL1 --pool-last $POOL_MAX --stop-at-boundary --games 32768 --log 250000 --episodes $POOL_GAMES \
     --collect $W/pool2g.bin.part --collect-when sum:28672 > $L/pool2g.log 2>&1
  mv $W/pool2g.bin.part $W/pool2g.bin
fi

run s2 "stage 2 [28672,36864) fresh optimistic, 1-ply, good formations ($S2_GAMES games)" --load $W/init.w \
  --train-stage 2 --fresh 2,3 --init $INIT $COMMON --log 500000 --episodes $S2_GAMES --pool $W/pool2g.bin --pool-last $POOL_MAX
run s2q "stage 2, 2-ply on 25% of the moves ($S2Q_GAMES games)" --load $W/s2.w --train-stage 2 --resume $W/s2.ckpt \
  --tc-decay 0.1 $COMMON --log 100000 --policy-depth 2 --policy-mix 0.25 --episodes $S2Q_GAMES \
  --pool $W/pool2g.bin --pool-last $POOL_MAX
cp $W/s2q.w $W/final.w
phase "done: $W/final.w ($ST; play with --root-downgrade 15, stage depths 3,2,2,2)"
