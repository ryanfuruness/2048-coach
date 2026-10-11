#!/bin/bash
# Multi-stage training, version 6.
#
#  * Matsuzaki's systematically selected 8x6 tuples (TDL2048+ "8x6patt"): far better than the
#    screened set used before (GPU, 600k games: 69% vs 41% of greedy games reach 16384).
#  * Three tile-sum stages: early game [0, 20480), the whole 16384 phase [20480, 36864), and
#    the 32768 phase [36864, inf). One stage per phase, because a boundary inside the 16384
#    phase kept the first half from learning what the second half needs (the 8192 must stay
#    next to the 16384).
#  * The early game keeps the zero-initialised base network (search handles it well).
#  * The late stages start from fresh optimistic weights (the only way they learned the right
#    strategy), then get a 2-ply curriculum: the deeper policy is used on a growing fraction of
#    moves, so the network learns the positions a search visits while episodes still succeed
#    (a straight switch to 2-ply collapsed: the untrained 2-ply policy never reached 32768).
set -e
cd "$(dirname "$0")/.."

NAME=${NAME:-v6}
BASE=${BASE:-weights/tup/mz.w}
INIT=${INIT:-320000}
S1_GAMES=${S1_GAMES:-20000000}
S2_GAMES=${S2_GAMES:-12000000}
CURR=${CURR:-"0.25:1000000 0.5:1000000 1.0:1000000"}  # 2-ply curriculum, "mix:episodes ..."
POOL_MAX=${POOL_MAX:-1000000}
ST="sum:20480,36864"

W=weights/$NAME
L=results/$NAME
mkdir -p "$W" "$L"
T=./build/gpu_train
COMMON="--stages $ST --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --save-every 2000000"

phase() { echo "[$(date '+%F %T')] $*" | tee -a "$L/pipeline.log"; }
run() {  # run NAME DESCRIPTION args...: trains into $W/NAME.w unless it exists
  local n=$1 d=$2
  shift 2
  [ -f "$W/$n.w" ] && return 0
  phase "$n: $d"
  $T "$@" --save "$W/$n.w.part" --checkpoint "$W/$n.ckpt" > "$L/$n.log" 2>&1
  mv "$W/$n.w.part" "$W/$n.w"
}

if [ ! -f $W/pool1.bin ]; then
  phase "pool1: stage-1 entries from the base network's greedy play"
  $T --load $BASE --no-learn --episodes 2000000 --log 500000 --games 32768 \
     --collect $W/pool1.bin.part --collect-when sum:20480 > $L/pool1.log 2>&1
  mv $W/pool1.bin.part $W/pool1.bin
fi

# stage 1: the 16384 phase, fresh optimistic, greedy burn-in; then the 2-ply curriculum
run s1 "16384 phase, fresh optimistic, 1-ply ($S1_GAMES games)" --load $BASE --train-stage 1 --fresh 1,2 --init $INIT \
  $COMMON --log 500000 --episodes $S1_GAMES --pool $W/pool1.bin --pool-last $POOL_MAX \
  --collect $W/pool2.bin --collect-when sum:36864
prev=s1
i=0
for c in $CURR; do
  i=$((i + 1))
  mix=${c%%:*}
  n=${c##*:}
  run s1q$i "16384 phase, 2-ply on $mix of the moves ($n games)" --load $W/$prev.w --train-stage 1 --resume $W/$prev.ckpt \
    --tc-decay 0.1 $COMMON --log 100000 --policy-depth 2 --policy-mix $mix --episodes $n --pool $W/pool1.bin \
    --pool-last $POOL_MAX --collect $W/pool2q.bin --collect-when sum:36864
  prev=s1q$i
done
s1final=$prev

# stage 2: the 32768 phase (to the end of the game), fresh optimistic, from the best stage-2 pool
pool2=$W/pool2q.bin
[ -s "$pool2" ] || pool2=$W/pool2.bin
run s2 "32768 phase, fresh optimistic, 1-ply ($S2_GAMES games)" --load $W/$s1final.w --train-stage 2 --fresh 2 \
  --init $INIT $COMMON --log 500000 --episodes $S2_GAMES --pool $pool2 --pool-last $POOL_MAX
prev=s2
i=0
for c in $CURR; do
  i=$((i + 1))
  mix=${c%%:*}
  n=${c##*:}
  run s2q$i "32768 phase, 2-ply on $mix of the moves ($n games)" --load $W/$prev.w --train-stage 2 --resume $W/$prev.ckpt \
    --tc-decay 0.1 $COMMON --log 100000 --policy-depth 2 --policy-mix $mix --episodes $n --pool $pool2 --pool-last $POOL_MAX
  prev=s2q$i
done
cp $W/$prev.w $W/final.w
phase "done: $W/final.w ($ST)"
