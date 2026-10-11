#!/bin/bash
# Workstream late, queue 4c (48 threads; replaces the tail of queue 4): after the running ph16 test of t21, the p32
# test of t21, then the 1000-game benchmark of best_v5 + t21 (paired with results/bench/best_v5bb_1000 by seeds).
cd "$(dirname "$0")/.."
L=results/late
until grep -q "ph16_t21" $L/eval.log 2>/dev/null; do sleep 30; done
export THREADS=48
scripts/exp_late_phase.sh p32 t21 weights/late/v5_t21.w 3,4,8,8,4
scripts/exp_late_bench.sh late_t21 weights/late/v5_t21.w 48
echo done > $L/q4c.done
