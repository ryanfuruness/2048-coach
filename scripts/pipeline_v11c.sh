#!/bin/bash
# v11c: the whole corner-locked 16384 phase trained with the endgame tables in the loop, then a
# dedicated second half from its formations (also with the tables). Same recipe as v11 + v11b,
# but the first half now also learns with the tables (they apply to its final collapse,
# [16384 4096 2048 1024 512 256] + 256 -> 8192 next to the 16384), and the phase starts as soon
# as the 16384 forms (stage spec "20480/14": sum >= 20480 or a 16384 on the board), so its network
# also plays the messy positions right after the merge (3% of games died there with the early-game
# network). Its pool: positions where the early-game network first makes a 16384.
set -e
cd "$(dirname "$0")/.."
RUN=${RUN:-v11c}  # (not NAME: WSL sets NAME to the host name)
S0=${S0:-weights/tup/s0cpu.w}
BASE3=${BASE3:-weights/v6/s1q1.w}
POOL1=${POOL1:-weights/v6/pool1.bin}
EG=${EG:-weights/endgame}
LOCK=${LOCK:-14}
INIT=${INIT:-320000}
M1_GAMES=${M1_GAMES:-14000000}
S2_GAMES=${S2_GAMES:-12000000}
Q_GAMES=${Q_GAMES:-1500000}
POOL_MAX=${POOL_MAX:-1000000}
ST3="sum:20480/14,36864"
ST4="sum:20480/14,28672,36864"
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
# pool: the first position with a 16384, from the early-game network's greedy play (stage 0 of
# FULL3 is the CPU-trained early game)
FULL3=${FULL3:-weights/v11/m1q_full.w}
if [ ! -f $W/pool16.bin ]; then
  phase "pool16: positions where the early-game network first makes a 16384"
  $T --load $FULL3 --stages $ST3 --train-stage 0 --no-learn --games 32768 --log 250000 \
     --episodes 1500000 --collect $W/pool16.bin.part --collect-when 14+ > $L/pool16.log 2>&1
  mv $W/pool16.bin.part $W/pool16.bin
fi
POOL1=$W/pool16.bin
run m1 "16384 phase from the 16384's formation, fresh optimistic, corner lock, tables in the loop, 1-ply ($M1_GAMES games)" \
  --load $BASE3 --stages $ST3 --train-stage 1 --fresh 1,2 --init $INIT $COMMON --log 500000 --episodes $M1_GAMES \
  --pool $POOL1 --pool-last $POOL_MAX --collect $W/pool2.bin --collect-when sum:28672
run m1q "16384 phase, 2-ply on 25% of the moves, tables ($Q_GAMES games)" --load $W/m1.w --stages $ST3 \
  --train-stage 1 --resume $W/m1.ckpt --tc-decay 0.1 $COMMON --log 100000 --policy-depth 2 --policy-mix 0.25 \
  --episodes $Q_GAMES --pool $POOL1 --pool-last $POOL_MAX --collect $W/pool2q.bin --collect-when sum:28672
if [ ! -f $W/init4.w ]; then
  python3 scripts/select_stages.py $W/m1q.w $W/init4.tmp.w 0,1,1,2
  python3 scripts/splice_stage.py $W/init4.tmp.w 0 $S0 0 $W/init4.w
  rm -f $W/init4.tmp.w
fi
run s2 "second half, fresh optimistic, corner lock, tables, from m1q's formations ($S2_GAMES games)" \
  --load $W/init4.w --stages $ST4 --train-stage 2 --fresh 2,3 --init $INIT $COMMON --log 500000 \
  --episodes $S2_GAMES --pool $W/pool2q.bin --pool-last $POOL_MAX
run s2q "second half, 2-ply on 25% of the moves, tables ($Q_GAMES games)" --load $W/s2.w --stages $ST4 \
  --train-stage 2 --resume $W/s2.ckpt --tc-decay 0.1 $COMMON --log 100000 --policy-depth 2 --policy-mix 0.25 \
  --episodes $Q_GAMES --pool $W/pool2q.bin --pool-last $POOL_MAX
cp $W/s2q.w $W/final.w
phase "done: $W/final.w ($ST4; play with --corner-lock $LOCK --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir $EG)"
