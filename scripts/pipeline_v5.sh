#!/bin/bash
# Multi-stage training, version 5: optimistic 1-ply burn-in, then 2-ply policy training.
#
# Lessons from versions 3 and 4:
#  * a stage initialised from a network trained from zero is pessimistic about the
#    next phase and never learns it (stage 2: 0% of episodes made 32768);
#  * a stage learned from FRESH optimistic weights explores and learns the phase
#    under the greedy policy (stage 2: 31% exit), but its values are only accurate
#    on the greedy policy's own path, so expectimax search made it WORSE (depth 2:
#    17% exit);
#  * continuing that stage with a 2-ply policy (expectimax one move deeper, used to
#    choose the move; TD learning unchanged) fixes this: the network learns the
#    positions a search visits, and the stronger policy gets further (37%+ exit).
# So each late stage gets a cheap 1-ply optimistic burn-in, then a 2-ply phase;
# stage 0 (the early game) keeps the zero-initialised base network, which search
# already handles well, and gets a 2-ply phase restricted to crowded positions.
#
# Stages are tile-sum ranges: 0:[0,20480) 1:[20480,28672) 2:[28672,36864)
# 3:[36864,45056) 4:[45056,53248) 5:[53248,61440) 6:[61440,inf)
set -e
cd "$(dirname "$0")/.."

NAME=${NAME:-v5}
BASE=${BASE:-weights/p2x/s2p2.w}          # stages 0-2 trained, 3-6 fresh
S0CKPT=${S0CKPT:-weights/v3/p1.ckpt}
S1CKPT=${S1CKPT:-weights/v3/s1.ckpt}
S2CKPT=${S2CKPT:-weights/p2x/s2p2.ckpt}
POOL1=${POOL1:-weights/v3/pool1.bin}
POOL3=${POOL3:-weights/s2x/pool3all.bin}
INIT=${INIT:-320000}
BURN=${BURN:-8000000}          # 1-ply optimistic burn-in, stages 3-6
P2=${P2:-1000000}              # 2-ply phase, stages 1-6
S0_GAMES=${S0_GAMES:-10000000} # stage 0, 1-ply continuation
S0_P2=${S0_P2:-1000000}        # stage 0, 2-ply in crowded positions
S0_MAXE=${S0_MAXE:-6}
POOL_MAX=${POOL_MAX:-1000000}
THRESH=(20480 28672 36864 45056 53248 61440)
STAGES="sum:$(IFS=,; echo "${THRESH[*]}")"

W=weights/$NAME
L=results/$NAME
mkdir -p "$W" "$L"
T=./build/gpu_train
COMMON="--stages $STAGES --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --save-every 2000000"
P2OPT="--policy-depth 2"

phase() { echo "[$(date '+%F %T')] $*" | tee -a "$L/pipeline.log"; }
run() {  # run NAME DESCRIPTION args...: trains into $W/NAME.w unless it exists
  local n=$1 d=$2
  shift 2
  [ -f "$W/$n.w" ] && return 0
  phase "$n: $d"
  $T "$@" --save "$W/$n.w.part" --checkpoint "$W/$n.ckpt" > "$L/$n.log" 2>&1
  mv "$W/$n.w.part" "$W/$n.w"
}
collect() { if (($1 < 6)); then echo "--collect $2 --collect-when sum:${THRESH[$1]}"; fi; }

# 1-ply optimistic burn-in of the 32768 phase (stages 3-6), each from the previous one's pool
prev=$BASE
pool=$POOL3
for k in 3 4 5 6; do
  run b$k "stage $k fresh optimistic, 1-ply ($BURN games)" --load $prev --train-stage $k --fresh $k --init $INIT \
    $COMMON --log 500000 --episodes $BURN --pool $pool --pool-last $POOL_MAX $(collect $k $W/bpool$((k + 1)).bin)
  prev=$W/b$k.w
  pool=$W/bpool$((k + 1)).bin
done

# 2-ply phases, forward, each collecting a better-formed pool for the next stage
run q1 "stage 1, 2-ply ($P2 games)" --load $prev --train-stage 1 --resume $S1CKPT --tc-decay 0.1 $COMMON --log 100000 \
  $P2OPT --episodes $P2 --pool $POOL1 --pool-last $POOL_MAX $(collect 1 $W/qpool2.bin)
prev=$W/q1.w
for k in 2 3 4 5 6; do
  if ((k == 2)); then ck=$S2CKPT; else ck=$W/b$k.ckpt; fi
  run q$k "stage $k, 2-ply ($P2 games)" --load $prev --train-stage $k --resume $ck --tc-decay 0.1 $COMMON --log 100000 \
    $P2OPT --episodes $P2 --pool $W/qpool$k.bin --pool-last $POOL_MAX $(collect $k $W/qpool$((k + 1)).bin)
  prev=$W/q$k.w
done

# stage 0: more 1-ply training (or a stage 0 trained elsewhere, e.g. by the CPU trainer:
# S0_FROM=file.w with checkpoint S0_FROM_CKPT), then 2-ply in crowded positions
if [ -n "$S0_FROM" ] && [ ! -f $W/s0.w ]; then
  phase "s0: stage 0 spliced in from $S0_FROM"
  python3 scripts/splice_stage.py $prev 0 "$S0_FROM" 0 $W/s0.w.part
  cp "$S0_FROM_CKPT" $W/s0.ckpt
  mv $W/s0.w.part $W/s0.w
fi
run s0 "stage 0, 1-ply continuation ($S0_GAMES games)" --load $prev --train-stage 0 --resume $S0CKPT --tc-decay 0.1 \
  $COMMON --log 500000 --episodes $S0_GAMES
run q0 "stage 0, 2-ply with <= $S0_MAXE empty cells ($S0_P2 games)" --load $W/s0.w --train-stage 0 --resume $W/s0.ckpt \
  --tc-decay 0.1 $COMMON --log 100000 $P2OPT --policy-max-empty $S0_MAXE --episodes $S0_P2
cp $W/q0.w $W/final.w
phase "done: $W/final.w"
