#!/bin/bash
# Workstream late2: evaluate an OTD stage-1 snapshot (weights/late2/s1o_K.w) as stage 1 of best_v6b, in two leaf-view
# variants: "nv" = leaf view off (--leaf-view 0 6: the new network values every 16384-holding board below sum 24576),
# "v20" = leaf view only below sum 20480 (s0cpu keeps the boards right after the 16384 formed). ph16 (late's protocol,
# 3 seeds x 700 real starts) paired vs v6b (late's logs). THREADS per variant (default 30), both variants in parallel.
# usage: exp_late2_evals1.sh K [variants: "nv v20"]
cd "$(dirname "$0")/.."
K=$1; VARS=${2:-"nv v20"}
W=weights/late2; L=results/late2
P=$W/v6b_s1o_$K.w
[ -f $P ] || python3 scripts/splice_stage.py weights/best_v6b.w 1 $W/s1o_$K.w 0 $P > /dev/null
for v in $VARS; do
  case $v in
    nv) F="--leaf-view 0 6" ;;
    v20) F="--leaf-view-max-sum 20480" ;;
  esac
  THREADS=${THREADS:-30} scripts/exp_late2_phase.sh ph16 s1o${K}_$v $P $F &
done
wait
for v in $VARS; do python3 scripts/exp_late_paired.py ph16 s1o${K}_$v v6b $L | tee -a $L/eval.log; done
