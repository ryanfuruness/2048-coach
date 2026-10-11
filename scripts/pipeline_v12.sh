#!/bin/bash
# v12: the 8192 phase (from the 8192's formation to the 16384's) with the recipe that worked for the
# 16384 phase: its own stage, fresh optimistic weights, corner lock (rank 13), endgame tables in the
# loop. Early-game losses before this: 3.7% of games die while building the 16384.
#
# Training file (3 stages, "sum:10240/13,20480/14"): 0 early game (s0cpu) before the 8192, 1 the
# 8192 phase (trained), 2 everything from the 16384's formation on = v11c's first-half network
# (its values at the 16384's formation are the bootstrap; never-trained weights neutralized).
set -e
cd "$(dirname "$0")/.."
RUN=${RUN:-v12}  # (not NAME: WSL sets NAME to the host name)
PH=${PH:-weights/v11c/final.w}      # 4 stages, sum:20480/14,28672,36864
PHCK=${PHCK:-weights/v11c/m1q.ckpt} # TC accumulators of PH's stage 1
EG=${EG:-weights/endgame}
INIT=${INIT:-320000}
M_GAMES=${M_GAMES:-10000000}
Q_GAMES=${Q_GAMES:-1000000}
POOL_MAX=${POOL_MAX:-1000000}
ST3="sum:10240/13,20480/14"
ST5="sum:10240/13,20480/14,28672,36864"
W=weights/$RUN
L=results/$RUN
mkdir -p "$W" "$L"
T=./build/gpu_train
COMMON="--stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --save-every 2000000 --corner-lock 13 --endgame-dir $EG --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7"
phase() { echo "[$(date '+%F %T')] $*" | tee -a "$L/pipeline.log"; }
run() {
  local n=$1 d=$2
  shift 2
  [ -f "$W/$n.w" ] && return 0
  phase "$n: $d"
  $T "$@" --save "$W/$n.w.part" --checkpoint "$W/$n.ckpt" > "$L/$n.log" 2>&1
  mv "$W/$n.w.part" "$W/$n.w"
}
if [ ! -f $W/train3.w ]; then
  python3 scripts/select_stages.py $PH $W/train3.tmp.w 0,0,1   # [early, early (pool collection), first half]
  python3 scripts/neutralize.py $W/train3.tmp.w $W/train3.w 2:$PHCK
  rm -f $W/train3.tmp.w
fi
if [ ! -f $W/pool8.bin ]; then
  phase "pool8: positions where the early-game network first makes an 8192"
  $T --load $W/train3.w --stages $ST3 --train-stage 0 --no-learn --games 32768 --log 250000 \
     --episodes 1500000 --collect $W/pool8.bin.part --collect-when 13+ > $L/pool8.log 2>&1
  mv $W/pool8.bin.part $W/pool8.bin
fi
run m1 "8192 phase, fresh optimistic, corner lock 13, tables in the loop, 1-ply ($M_GAMES games)" --load $W/train3.w \
  --stages $ST3 --train-stage 1 --fresh 1 --init $INIT $COMMON --log 500000 --episodes $M_GAMES \
  --pool $W/pool8.bin --pool-last $POOL_MAX
run m1q "8192 phase, 2-ply on 25% of the moves ($Q_GAMES games)" --load $W/m1.w --stages $ST3 --train-stage 1 \
  --resume $W/m1.ckpt --tc-decay 0.1 $COMMON --log 100000 --policy-depth 2 --policy-mix 0.25 --episodes $Q_GAMES \
  --pool $W/pool8.bin --pool-last $POOL_MAX
# 5-stage player: [early, 8192 phase, first half, second half, rest]
if [ ! -f $W/final.w ]; then
  python3 scripts/select_stages.py $PH $W/final.tmp.w 0,0,1,2,3
  python3 scripts/splice_stage.py $W/final.tmp.w 1 $W/m1q.w 1 $W/final.w
  rm -f $W/final.tmp.w
fi
phase "done: $W/final.w ($ST5; play with --corner-lock 13 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir $EG)"
