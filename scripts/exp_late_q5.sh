#!/bin/bash
# Workstream late, queue 5: a longer OTD schedule for the second half from the optimistic start (weights/expcpu/start.w,
# as t12 -> t18 -> t21 but twice as long): TD 0.1 x 24M -> 0.01 x 12M -> 0.001 x 6M on POOL (default: the usual
# second-half starts), starting once the control c0 has finished (core budget); then claims + judge per segment >= 2.
# usage: exp_late_q5.sh NAME [POOL]
cd "$(dirname "$0")/.."
N=${1:-u0} POOL=${2:-weights/v11c/pool2mix.bin}
L=results/late
until [ -f weights/late/c0_2.w ]; do sleep 60; done
scripts/exp_late_train.sh $N weights/expcpu/start.w $POOL "0.1:24000000:24 0.01:12000000:40 0.001:6000000:48" 24
for k in 2 3; do
  n=${N}_$k; P=weights/late/v5_$n.w
  [ -f $P ] || python3 scripts/splice_stage.py weights/best_v5.w 3 weights/late/$n.w 0 $P > /dev/null
  K=16 scripts/exp_late_claims.sh $n --weights $P
  SET=judge K=16 scripts/exp_late_claims.sh $n --weights $P
done
echo done > $L/q5_$N.done
