#!/bin/bash
# v14: a zero-initialised (pessimistic) 16384-phase network under the corner lock, with the endgame
# tables in the loop. Optimistic weights were needed to escape the displaced/far-corner formation
# trap, which the lock now prevents; zero-initialised networks are the ones that gain from deeper
# search (the CPU early game: depth 2 85.7% -> depth 3 96.4%), while every optimistic one degrades
# beyond depth 3. Same setup as v11c's m1 (from the 16384's formation, stage spec "20480/14"); the
# boundary at 36864 keeps the fresh optimistic stage (constant 320k), so completing the phase pays.
set -e
cd "$(dirname "$0")/.."
RUN=${RUN:-v14}  # (not NAME: WSL sets NAME to the host name)
BASE3=${BASE3:-weights/v6/s1q1.w}
POOL=${POOL:-weights/v11c/pool16.bin}
EG=${EG:-weights/endgame}
UPD=${UPD:-mean}
M_GAMES=${M_GAMES:-14000000}
Q_GAMES=${Q_GAMES:-1500000}
ST3="sum:20480/14,36864"
W=weights/$RUN
L=results/$RUN
mkdir -p "$W" "$L"
T=./build/gpu_train
COMMON="--stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --save-every 2000000 --corner-lock 14 --endgame-dir $EG --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --update-scale $UPD"
phase() { echo "[$(date '+%F %T')] $*" | tee -a "$L/pipeline.log"; }
run() {
  local n=$1 d=$2
  shift 2
  [ -f "$W/$n.w" ] && return 0
  phase "$n: $d"
  $T "$@" --save "$W/$n.w.part" --checkpoint "$W/$n.ckpt" > "$L/$n.log" 2>&1
  mv "$W/$n.w.part" "$W/$n.w"
}
# stage 2 (after 36864) optimistic: every weight 320000 / 64 features; stage 1 is zeroed by --fresh 1 --init 0
if [ ! -f $W/base3.w ]; then
  python3 scripts/neutralize.py $BASE3 $W/base3.w --fresh 2 --value 5000
fi
run m1 "16384 phase from zero weights, lock, tables, 1-ply, update $UPD ($M_GAMES games)" --load $W/base3.w \
  --stages $ST3 --train-stage 1 --fresh 1 --init 0 $COMMON --log 500000 --episodes $M_GAMES \
  --pool $POOL --pool-last 1000000
run m1q "16384 phase, 2-ply on 25% of the moves ($Q_GAMES games)" --load $W/m1.w --stages $ST3 --train-stage 1 \
  --resume $W/m1.ckpt --tc-decay 0.1 $COMMON --log 100000 --policy-depth 2 --policy-mix 0.25 --episodes $Q_GAMES \
  --pool $POOL --pool-last 1000000
if [ ! -f $W/m1q_full.w ]; then
  python3 scripts/splice_stage.py $W/m1q.w 0 weights/tup/s0cpu.w 0 $W/m1q_full.w
fi
phase "done: $W/m1q_full.w ($ST3)"
# depth test on real starts: the whole phase at depth 2, 3, 4
EGO="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir $EG"
for d in 2 3 4; do
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights $W/m1q_full.w --stages $ST3 --start weights/v11c/pool16real.bin --games 1400 --threads 14 \
      --seed 999 --quantize --depth $d --stop-sum 36864 $EGO > $L/phase_d$d.log 2>&1 )
  echo "v14 whole phase from real starts, depth $d: $(grep 'tile sum' $L/phase_d$d.log)" | tee -a $L/pipeline.log
done
