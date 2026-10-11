#!/bin/bash
# Workstream late: evaluate a second-half network as stage 3 of best_v5 (2-stage training file, its stage 0):
# dispute claims + unselected late judge positions (K=16 analyze processes), then the phase tests (THREADS, default 48):
# ph16 (3 seeds) and p32 (1878 starts). Spliced player: weights/late/v5_NAME.w.
# usage: exp_late_evalnet.sh NAME NET.w [ph16|p32|all|claims]
cd "$(dirname "$0")/.."
N=$1 NET=$2 WHAT=${3:-all}
P=weights/late/v5_$N.w
[ -f $P ] || python3 scripts/splice_stage.py weights/best_v5.w 3 $NET 0 $P > /dev/null
K=16 scripts/exp_late_claims.sh $N --weights $P
SET=judge K=16 scripts/exp_late_claims.sh $N --weights $P
export THREADS=${THREADS:-48}
case $WHAT in
  ph16|all) scripts/exp_late_phase.sh ph16 $N $P 3,4,8,8,4 ;;
esac
case $WHAT in
  p32|all) scripts/exp_late_phase.sh p32 $N $P 3,4,8,8,4 ;;
esac
