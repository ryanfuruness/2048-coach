#!/bin/bash
# Workstream late, queue 8 (40 threads): OTD stage B for best_v6 (= best_v5 with the OTD second half t21): the
# exp_otdB.sh recipe with t21 as the second half it bootstraps from. 3-stage training file [stage B fresh OI, t21, OI],
# stages sum:28672,36864, starts weights/expsplit/pool24.bin (sum 24576), tables in the loop, TD 0.1 x 12M -> 0.01 x 6M
# -> 0.001 x 3M. Each segment from the second on: claims + judge + ph16 as stage 2 of best_v5+t21.
cd "$(dirname "$0")/.."
L=results/late; W=weights/late
mkdir -p $L $W
if [ ! -f $W/b_start.w ]; then
  python3 scripts/select_stages.py weights/best_v5.w $W/b_tmp3.w 2,3,4 > /dev/null
  python3 scripts/splice_stage.py $W/b_tmp3.w 1 weights/expotd/t21.w 0 $W/b_tmp3b.w > /dev/null && rm -f $W/b_tmp3.w
  python3 scripts/neutralize.py $W/b_tmp3b.w $W/b_start.w --fresh 0 --value 5000 > /dev/null && rm -f $W/b_tmp3b.w
fi
COMMON="--stages sum:28672,36864 --train-stage 0 --stop-at-boundary --lambda 0.5 --corner-lock 14 \
  --endgame-dir weights/endgame_big --endgame-min 0.5 --endgame-full 2 --pool weights/expsplit/pool24.bin \
  --pool-last 1000000 --threads 40 --log 500000"
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
from=$W/b_start.w; k=0
for seg in 0.1:12000000 0.01:6000000 0.001:3000000; do
  k=$((k + 1)); a=${seg%%:*}; e=${seg##*:}; out=$W/bo_$k.w
  if [ ! -f $out ]; then
    echo "[$(date '+%F %T')] bo_$k: $e episodes alpha $a from $from (stage B, SH t21)" >> $L/train.log
    ./build/train --load $from $COMMON --episodes $e --alpha $a --save $out.part > $L/train_bo_$k.log 2>&1 || exit 1
    mv $out.part $out
    grep "games  avg" $L/train_bo_$k.log | tail -n 1 | sed "s/^/  bo_$k /" >> $L/train.log
  fi
  from=$out
  if [ $k -ge 2 ]; then
    P=$W/v6_bo_$k.w
    [ -f $P ] || python3 scripts/splice_stage.py weights/late/v5_t21.w 2 $out 0 $P > /dev/null
    K=16 scripts/exp_late_claims.sh v6bo_$k --weights $P
    SET=judge K=16 scripts/exp_late_claims.sh v6bo_$k --weights $P
    THREADS=40 scripts/exp_late_phase.sh ph16 v6bo_$k $P 3,4,8,8,4
  fi
done
echo done > $L/q8.done
