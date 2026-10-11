#!/bin/bash
# Workstream late2: early-game network (stage 0 of best_v6b = s0cpu, tile sums < 20480; it also values the 16384
# phase's first half and ~36% of the 32768 phase's roots through the root/leaf views) with the OTD schedule (plain TD,
# decaying alpha, never a TC tail). Episodes run from the empty board to sum 20480 and bootstrap from stage 1 of the
# 2-stage file (s0cpu's bootstrap stage), exactly as s0cpu was trained.
# usage: exp_late2_train.sh NAME SRC.w "ALPHA:EPISODES[:THREADS] ..." [THREADS]  -> weights/late2/NAME_<k>.w per segment
cd "$(dirname "$0")/.."
N=$1 SRC=$2 SEGS=$3 TH=${4:-30}
L=results/late2; mkdir -p $L weights/late2
COMMON="--stages sum:20480 --train-stage 0 --stop-at-boundary --lambda 0.5 --log 500000"
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
k=0; from=$SRC
for seg in $SEGS; do
  k=$((k + 1)); IFS=: read -r a e t <<< "$seg"; t=${t:-$TH}
  out=weights/late2/${N}_$k.w
  if [ ! -f $out ]; then
    echo "[$(date '+%F %T')] ${N}_$k: $e episodes alpha $a from $from ($t threads)" >> $L/train.log
    ./build/train --load $from $COMMON --threads $t --episodes $e --alpha $a $EXTRA --save $out.part > $L/train_${N}_$k.log 2>&1 || exit 1
    mv $out.part $out
    grep "games  avg" $L/train_${N}_$k.log | tail -n 1 | sed "s/^/  ${N}_$k /" >> $L/train.log
  fi
  from=$out
done
echo "[$(date '+%F %T')] ${N} done" >> $L/train.log
