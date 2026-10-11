#!/bin/bash
# Multi-stage training, version 11: the 16384 phase with a corner lock.
#
# Every network so far learned to move the 16384 out of its corner: the first half merges
# along the edge away from the corner ([16384 4096 2048 2048] -> [_ 16384 4096 4096]) in 129
# of 139 games, leaving the 8192 in the corner and the 16384 beside it, with more big tiles
# growing on its far side. Most losses are in the second half of the phase, in exactly these
# two-sided formations. Forcing the old network to keep the 16384 in its corner at play time
# breaks it (79% -> 0.7% of first halves completed), so the phase is retrained under the lock
# (gpu_train/play --corner-lock 14: moves that take the max tile out of its corner are not
# played unless every move does).
#
# Recipe of v6 + v9 under the lock: m1 the whole phase [20480, 36864) from fresh optimistic
# weights, m1q a 2-ply curriculum; then s2, a dedicated second half [28672, 36864) trained on
# the positions where m1q completes the first half, and its 2-ply curriculum s2q.
set -e
cd "$(dirname "$0")/.."

RUN=${RUN:-v11}  # (not NAME: WSL sets NAME to the host name)
S0=${S0:-weights/tup/s0cpu.w}             # early game (its stage 0)
BASE3=${BASE3:-weights/v6/s1q1.w}         # any 3-stage file (sum:20480,36864); stages 1-2 start fresh
POOL1=${POOL1:-weights/v6/pool1.bin}
LOCK=${LOCK:-14}
INIT=${INIT:-320000}
M1_GAMES=${M1_GAMES:-14000000}
S2_GAMES=${S2_GAMES:-12000000}
Q_GAMES=${Q_GAMES:-1500000}
POOL_MAX=${POOL_MAX:-1000000}
ST3="sum:20480,36864"
ST4="sum:20480,28672,36864"

W=weights/$RUN
L=results/$RUN
mkdir -p "$W" "$L"
T=./build/gpu_train
COMMON="--stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --save-every 2000000 --corner-lock $LOCK"

phase() { echo "[$(date '+%F %T')] $*" | tee -a "$L/pipeline.log"; }
run() {
  local n=$1 d=$2
  shift 2
  [ -f "$W/$n.w" ] && return 0
  phase "$n: $d"
  $T "$@" --save "$W/$n.w.part" --checkpoint "$W/$n.ckpt" > "$L/$n.log" 2>&1
  mv "$W/$n.w.part" "$W/$n.w"
}

run m1 "16384 phase [20480,36864), fresh optimistic, corner lock, 1-ply ($M1_GAMES games)" --load $BASE3 \
  --stages $ST3 --train-stage 1 --fresh 1,2 --init $INIT $COMMON --log 500000 --episodes $M1_GAMES \
  --pool $POOL1 --pool-last $POOL_MAX --collect $W/pool2.bin --collect-when sum:28672
run m1q "16384 phase, 2-ply on 25% of the moves ($Q_GAMES games)" --load $W/m1.w --stages $ST3 --train-stage 1 \
  --resume $W/m1.ckpt --tc-decay 0.1 $COMMON --log 100000 --policy-depth 2 --policy-mix 0.25 --episodes $Q_GAMES \
  --pool $POOL1 --pool-last $POOL_MAX --collect $W/pool2q.bin --collect-when sum:28672

# 4-stage file: early game from S0, both halves start as m1q's phase network, stage 3 optimistic
if [ ! -f $W/init4.w ]; then
  python3 scripts/select_stages.py $W/m1q.w $W/init4.tmp.w 0,1,1,2
  python3 scripts/splice_stage.py $W/init4.tmp.w 0 $S0 0 $W/init4.w
  rm -f $W/init4.tmp.w
fi
run s2 "second half [28672,36864), fresh optimistic, corner lock, from m1q's formations ($S2_GAMES games)" \
  --load $W/init4.w --stages $ST4 --train-stage 2 --fresh 2,3 --init $INIT $COMMON --log 500000 \
  --episodes $S2_GAMES --pool $W/pool2q.bin --pool-last $POOL_MAX
run s2q "second half, 2-ply on 25% of the moves ($Q_GAMES games)" --load $W/s2.w --stages $ST4 --train-stage 2 \
  --resume $W/s2.ckpt --tc-decay 0.1 $COMMON --log 100000 --policy-depth 2 --policy-mix 0.25 --episodes $Q_GAMES \
  --pool $W/pool2q.bin --pool-last $POOL_MAX
cp $W/s2q.w $W/final.w
phase "done: $W/final.w ($ST4; play with --corner-lock $LOCK --root-downgrade 15)"
