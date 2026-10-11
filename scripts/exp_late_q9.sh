#!/bin/bash
# Workstream late, queue 9: a second independent long OTD run of the second half (seed 2; same schedule as u0) for a
# weight-averaged ensemble of independent OTD networks (t21, u0, u1); claims + judge per segment >= 2.
cd "$(dirname "$0")/.."
L=results/late
EXTRA="--seed 2" scripts/exp_late_train.sh u1 weights/expcpu/start.w weights/v11c/pool2mix.bin "0.1:24000000:28 0.01:12000000:32 0.001:6000000:40" 28
for k in 2 3; do
  n=u1_$k; P=weights/late/v5_$n.w
  [ -f $P ] || python3 scripts/splice_stage.py weights/best_v5.w 3 weights/late/$n.w 0 $P > /dev/null
  K=16 scripts/exp_late_claims.sh $n --weights $P
  SET=judge K=16 scripts/exp_late_claims.sh $n --weights $P
done
echo done > $L/q9.done
