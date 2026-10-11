#!/bin/bash
# Workstream late2: OTD stage 1 of best_v6b (the 16384 phase's first half [16384 formed, sum 24576); in best_v5bb's
# settings its network is never used: the leaf view (--leaf-view 14 6 --leaf-view-max-sum 24576) lets s0cpu value every
# leaf there). The recipe that gave t21 and bo_2: fresh optimistic init (5000 per weight = V 320k), plain TD with a
# decaying rate (0.1 x 12M -> 0.01 x 6M -> 0.001 x 3M), tables in the loop, corner lock, bootstrapping at sum 24576 from
# the trained next stage (bo_2), starts = weights/v11c/pool16.bin (1.23M boards at the 16384's formation).
# Evaluate: spliced as stage 1 of best_v6b, played with the leaf view off (--leaf-view 0 6) or limited.
cd "$(dirname "$0")/.."
L=results/late2; W=weights/late2; mkdir -p $L $W
TH=${THREADS:-40}
if [ ! -f $W/s1_start.w ]; then
  python3 scripts/select_stages.py weights/best_v6b.w $W/s1_tmp.w 1,2 > /dev/null
  python3 scripts/neutralize.py $W/s1_tmp.w $W/s1_start.w --fresh 0 --value 5000 > /dev/null && rm -f $W/s1_tmp.w
fi
COMMON="--stages sum:24576 --train-stage 0 --stop-at-boundary --lambda 0.5 --corner-lock 14 \
  --endgame-dir weights/endgame_big --endgame-min 0.5 --endgame-full 2 --pool weights/v11c/pool16.bin \
  --pool-last 1000000 --threads $TH --log 500000"
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
from=$W/s1_start.w; k=0
for seg in ${SEGS:-0.1:12000000 0.01:6000000 0.001:3000000}; do
  k=$((k + 1)); a=${seg%%:*}; e=${seg##*:}; out=$W/s1o_$k.w
  if [ ! -f $out ]; then
    echo "[$(date '+%F %T')] s1o_$k: $e episodes alpha $a from $from (stage 1, next stage bo_2)" >> $L/train.log
    ./build/train --load $from $COMMON --episodes $e --alpha $a --save $out.part > $L/train_s1o_$k.log 2>&1 || exit 1
    mv $out.part $out
    grep "games  avg" $L/train_s1o_$k.log | tail -n 1 | sed "s/^/  s1o_$k /" >> $L/train.log
  fi
  from=$out
done
echo "[$(date '+%F %T')] s1o done" >> $L/train.log
