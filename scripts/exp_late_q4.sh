#!/bin/bash
# Workstream late, queue 4 (48 threads): the remaining baselines (p32 base, t21 phase tests), then every trained
# network of queue 3 as it appears.
cd "$(dirname "$0")/.."
L=results/late
until grep -q "=== " $L/p32_base.log 2>/dev/null; do sleep 30; done
sleep 30
export THREADS=48
scripts/exp_late_phase.sh ph16 t21 weights/late/v5_t21.w 3,4,8,8,4
scripts/exp_late_phase.sh p32 t21 weights/late/v5_t21.w 3,4,8,8,4
for n in x50_1 c0_1 x50_2 c0_2; do
  until [ -f weights/late/$n.w ]; do sleep 60; done
  scripts/exp_late_evalnet.sh $n weights/late/$n.w all
done
echo done > $L/q4.done
