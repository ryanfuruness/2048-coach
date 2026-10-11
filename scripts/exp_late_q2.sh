#!/bin/bash
# Workstream late, queue 2 (claims, 16 cores): OTD networks and combinations on the expert disputes, then every
# candidate on the unselected late positions of the H=1000 judges (SET=judge).
cd "$(dirname "$0")/.."
L=results/late; mkdir -p $L weights/late
[ -f weights/late/v5_t18.w ] || python3 scripts/splice_stage.py weights/best_v5.w 3 weights/expotd/t18.w 0 weights/late/v5_t18.w > /dev/null
export K=16
scripts/exp_late_claims.sh t18 --weights weights/late/v5_t18.w
scripts/exp_late_claims.sh t21_d6 --weights weights/late/v5_t21.w --depth 6
scripts/exp_late_claims.sh t21_b200k --weights weights/late/v5_t21.w --budget 200000
export SET=judge
scripts/exp_late_claims.sh base
scripts/exp_late_claims.sh t21 --weights weights/late/v5_t21.w
scripts/exp_late_claims.sh t18 --weights weights/late/v5_t18.w
scripts/exp_late_claims.sh d6 --depth 6
scripts/exp_late_claims.sh t21_d6 --weights weights/late/v5_t21.w --depth 6
echo done > $L/q2.done
