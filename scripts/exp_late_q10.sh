#!/bin/bash
# Workstream late, queue 10: weight-averaged ensembles of independent OTD second halves (an n-tuple network is linear in
# its weights: averaging = averaging the values): e2 = (t21 + u0_3) / 2, e3 = (t21 + u0_3 + u1_3) / 3, as stage 3 of
# best_v5; claims + judge + cal6's expert judge (jx), then the phase tests of e3 (48 threads).
cd "$(dirname "$0")/.."
L=results/late; W=weights/late
until [ -f $W/u0_3.w ]; do sleep 120; done
[ -f $W/v5_e2.w ] || python3 scripts/exp_late_avgstage.py $W/v5_t21.w 3 $W/u0_3.w 0 0.5 $W/v5_e2.w >> $L/train.log
JX="SET=judge JNAME=jx JMIN=0 JFILES=$(ls $L/jx/xexpert_*.tsv | paste -sd,)"
K=16 scripts/exp_late_claims.sh e2 --weights $W/v5_e2.w
SET=judge K=16 scripts/exp_late_claims.sh e2 --weights $W/v5_e2.w
env $JX K=16 scripts/exp_late_claims.sh e2 --weights $W/v5_e2.w
until [ -f $W/u1_3.w ]; do sleep 120; done
[ -f $W/v5_u1_3.w ] || python3 scripts/splice_stage.py weights/best_v5.w 3 $W/u1_3.w 0 $W/v5_u1_3.w > /dev/null
env $JX K=16 scripts/exp_late_claims.sh u1_3 --weights $W/v5_u1_3.w
[ -f $W/v5_e3.w ] || python3 scripts/exp_late_avgstage.py $W/v5_e2.w 3 $W/u1_3.w 0 0.333333 $W/v5_e3.w >> $L/train.log
K=16 scripts/exp_late_claims.sh e3 --weights $W/v5_e3.w
SET=judge K=16 scripts/exp_late_claims.sh e3 --weights $W/v5_e3.w
env $JX K=16 scripts/exp_late_claims.sh e3 --weights $W/v5_e3.w
THREADS=48 scripts/exp_late_phase.sh ph16 e3 $W/v5_e3.w 3,4,8,8,4
THREADS=48 scripts/exp_late_phase.sh p32 e3 $W/v5_e3.w 3,4,8,8,4
echo done > $L/q10.done
