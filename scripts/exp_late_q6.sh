#!/bin/bash
# Workstream late, queue 6: clean (cross-fit) test of expert-pool training. Videos split into folds A/B
# (scripts/exp_late_folds.py split weights/late/xf); xA = t21 continued on the usual pool mixed 50/50 with fold A's
# expert root views (TD 0.01 x 6M -> 0.001 x 3M, as x50), xB the same with fold B. Each network's claims count only on
# the other fold's positions (exp_late_folds.py merge) -> compare with the control c0 (same schedule, usual pool only).
cd "$(dirname "$0")/.."
L=results/late
for f in A B; do
  [ -f weights/late/mix50_$f.bin ] || python3 scripts/exp_late_mixpool.py weights/v11c/pool2mix.bin weights/late/xf_${f}_sh.bin 0.5 weights/late/mix50_$f.bin >> $L/train.log
done
scripts/exp_late_train.sh xA weights/expotd/t21.w weights/late/mix50_A.bin "0.01:6000000 0.001:3000000" 16 &
scripts/exp_late_train.sh xB weights/expotd/t21.w weights/late/mix50_B.bin "0.01:6000000 0.001:3000000" 16 &
wait
for n in xA_2 xB_2; do
  P=weights/late/v5_$n.w
  [ -f $P ] || python3 scripts/splice_stage.py weights/best_v5.w 3 weights/late/$n.w 0 $P > /dev/null
  K=16 scripts/exp_late_claims.sh $n --weights $P
  SET=judge K=16 scripts/exp_late_claims.sh $n --weights $P
done
echo done > $L/q6.done
