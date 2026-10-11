#!/bin/bash
# v11b: the second half of the corner-locked 16384 phase trained with the endgame tables in the
# loop (gpu_train --endgame-dir): in a snake ending with a known table entry that wins with
# p >= 0.5, the table's move is played, so the network learns the values of the player that
# actually plays (network + tables) and how to steer into winnable endings.
# Needs weights/v11/m1q.w and pool2q.bin (pipeline_v11.sh up to m1q).
set -e
cd "$(dirname "$0")/.."
RUN=${RUN:-v11b}  # (not NAME: WSL sets NAME to the host name)
SRC=weights/v11
S0=${S0:-weights/tup/s0cpu.w}
EG=${EG:-weights/endgame}
LOCK=${LOCK:-14}
INIT=${INIT:-320000}
S2_GAMES=${S2_GAMES:-12000000}
Q_GAMES=${Q_GAMES:-1500000}
POOL_MAX=${POOL_MAX:-1000000}
ST4="sum:20480,28672,36864"
W=weights/$RUN
L=results/$RUN
mkdir -p "$W" "$L"
T=./build/gpu_train
COMMON="--stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --save-every 2000000 --corner-lock $LOCK --endgame-dir $EG --endgame-min 0.5 --endgame-full 2"
phase() { echo "[$(date '+%F %T')] $*" | tee -a "$L/pipeline.log"; }
run() {
  local n=$1 d=$2
  shift 2
  [ -f "$W/$n.w" ] && return 0
  phase "$n: $d"
  $T "$@" --save "$W/$n.w.part" --checkpoint "$W/$n.ckpt" > "$L/$n.log" 2>&1
  mv "$W/$n.w.part" "$W/$n.w"
}
if [ ! -f $W/init4.w ]; then
  python3 scripts/select_stages.py $SRC/m1q.w $W/init4.tmp.w 0,1,1,2
  python3 scripts/splice_stage.py $W/init4.tmp.w 0 $S0 0 $W/init4.w
  rm -f $W/init4.tmp.w
fi
run s2 "second half [28672,36864), fresh optimistic, corner lock, endgame tables in the loop ($S2_GAMES games)" \
  --load $W/init4.w --stages $ST4 --train-stage 2 --fresh 2,3 --init $INIT $COMMON --log 500000 \
  --episodes $S2_GAMES --pool $SRC/pool2q.bin --pool-last $POOL_MAX
run s2q "second half, 2-ply on 25% of the moves, tables in the loop ($Q_GAMES games)" --load $W/s2.w --stages $ST4 \
  --train-stage 2 --resume $W/s2.ckpt --tc-decay 0.1 $COMMON --log 100000 --policy-depth 2 --policy-mix 0.25 \
  --episodes $Q_GAMES --pool $SRC/pool2q.bin --pool-last $POOL_MAX
cp $W/s2q.w $W/final.w
phase "done: $W/final.w ($ST4; play with --corner-lock $LOCK --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir $EG)"
