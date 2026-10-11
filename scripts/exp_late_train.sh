#!/bin/bash
# Workstream late: second-half networks (stage 3 of best_v5, view tile sums [28672, 36864)) continued from the OTD
# network t21 with plain TD (alpha 0.01 -> 0.001, never a TC tail) on start pools that mix the usual second-half starts
# (weights/v11c/pool2mix.bin, 1.06M boards at the phase start) with the root views of curated expert positions
# (weights/late/xpool_sh.bin, 20.9k boards spread over the phase; scripts/exp_late_pool.py).
# usage: exp_late_train.sh NAME SRC.w POOL.bin "ALPHA:EPISODES[:THREADS] ..." [THREADS]   -> weights/late/NAME_<k>.w per segment
# (env EXTRA: more trainer flags, e.g. "--seed 2")
cd "$(dirname "$0")/.."
N=$1 SRC=$2 POOL=$3 SEGS=$4 TH=${5:-48}
L=results/late; mkdir -p $L weights/late
COMMON="--stages sum:36864 --train-stage 0 --stop-at-boundary --lambda 0.5 --corner-lock 14 --endgame-dir weights/endgame_big \
  --endgame-min 0.5 --endgame-full 2 --pool $POOL --log 500000"
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
k=0; from=$SRC
for seg in $SEGS; do
  k=$((k + 1)); IFS=: read -r a e t <<< "$seg"; t=${t:-$TH}
  out=weights/late/${N}_$k.w
  if [ ! -f $out ]; then
    echo "[$(date '+%F %T')] ${N}_$k: $e episodes alpha $a from $from (pool $POOL, $t threads)" >> $L/train.log
    ./build/train --load $from $COMMON --threads $t --episodes $e --alpha $a $EXTRA --save $out.part > $L/train_${N}_$k.log 2>&1 || exit 1
    mv $out.part $out
    grep "games  avg" $L/train_${N}_$k.log | tail -n 1 | sed "s/^/  ${N}_$k /" >> $L/train.log
  fi
  from=$out
done
