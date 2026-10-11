#!/bin/bash
# Over-training test, learning-rule side: the second half (exps e4 recipe: fresh optimistic, lock, tables, pool2mix) with
# PLAIN TD and a decaying rate (alpha 1.0 for 4M, 0.3 for 4M, 0.1 for 4M) instead of TC alpha 1.0 throughout. Guei et al.
# train the same tuples 100M episodes with decaying TD and keep improving; our TC nets peak at 3-4M then degrade under
# search (exp_snap: 4M 58.0/60.5, 8M 52.8/45.2, 12M ~48/37 at d3/d4 on 600 real positions as v11c's second half).
set -e
cd "$(dirname "$0")/.."
W=weights/exptd
L=results/exptd
mkdir -p $W $L
while ps -eo args | grep -q "^/bin/bash scripts/exp_seeds4.sh"; do sleep 30; done
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
COMMON="--stages sum:36864 --train-stage 0 --stop-at-boundary --td --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool weights/v11c/pool2mix.bin --pool-last $NPOOL"
prev=""
for seg in "4 1.0" "8 0.3" "12 0.1"; do
  set -- $seg; m=$1; a=$2
  if [ ! -f $W/e$m.w ]; then
    src="--load weights/expcpu/start.w"; [ -n "$prev" ] && src="--load $W/e$prev.w"
    echo "[$(date '+%F %T')] TD alpha $a to ${m}M" >> $L/log
    ./build/gpu_train $src $COMMON --alpha $a --episodes 4000000 --save $W/e$m.w.part > $L/e$m.log 2>&1
    mv $W/e$m.w.part $W/e$m.w
    grep "games  avg" $L/e$m.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  e$m /" >> $L/log
  fi
  prev=$m
done
echo "[$(date '+%F %T')] training done" >> $L/log
