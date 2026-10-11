#!/bin/bash
# Workstream late, queue 4b (16 cores, short bursts): dispute claims + unselected judge positions for every trained
# second-half network as soon as it exists (phase tests only for the promising ones, by hand / queue 4).
cd "$(dirname "$0")/.."
for n in x50_1 c0_1 x50_2 c0_2; do
  until [ -f weights/late/$n.w ]; do sleep 60; done
  P=weights/late/v5_$n.w
  [ -f $P ] || python3 scripts/splice_stage.py weights/best_v5.w 3 weights/late/$n.w 0 $P > /dev/null
  K=16 scripts/exp_late_claims.sh $n --weights $P
  SET=judge K=16 scripts/exp_late_claims.sh $n --weights $P
done
echo done > results/late/q4b.done
