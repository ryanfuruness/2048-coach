#!/bin/bash
# Workstream late, queue 1 (instance, 96 cores): baselines of the metrics and cheap probes.
#   claims (16 cores, sequential): base, deeper analysis (depth 5 / 6, budget 200k), OTD second half t21 as stage 3,
#   exposed-cells penalty;  phase tests (80 threads): ph16 + p32 baselines (best_v5bb), then t21.
cd "$(dirname "$0")/.."
L=results/late; mkdir -p $L weights/late
[ -f weights/late/v5_t21.w ] || python3 scripts/splice_stage.py weights/best_v5.w 3 weights/expotd/t21.w 0 weights/late/v5_t21.w > /dev/null
(
  export K=16
  scripts/exp_late_claims.sh base
  scripts/exp_late_claims.sh d5 --depth 5
  scripts/exp_late_claims.sh t21 --weights weights/late/v5_t21.w
  scripts/exp_late_claims.sh exp1000 --exposed-pen 1000 12288 65536
  scripts/exp_late_claims.sh exp3000 --exposed-pen 3000 12288 65536
  scripts/exp_late_claims.sh b200k --budget 200000
  scripts/exp_late_claims.sh d6 --depth 6
  echo done > $L/q1_claims.done
) > $L/q1_claims.out 2>&1 &
export THREADS=80
scripts/exp_late_phase.sh ph16 base weights/best_v5.w 3,4,8,8,4
scripts/exp_late_phase.sh p32 base weights/best_v5.w 3,4,8,8,4
scripts/exp_late_phase.sh ph16 t21 weights/late/v5_t21.w 3,4,8,8,4
scripts/exp_late_phase.sh p32 t21 weights/late/v5_t21.w 3,4,8,8,4
wait
echo done > $L/q1.done
