#!/bin/bash
# Workstream late, queue 7 (16 cores): the candidates on cal6's expert judge (results/cal6/jx in ~/2048_cal6: 400
# curated expert positions, 250 with claims > 10% + 150 moderate claims, every move, 32 playouts, horizon 1000),
# copied to results/late/jx once all 16 chunks exist. Played moves: results/cal6/xexpert.tsv (exp_late_judge.py --meta).
cd "$(dirname "$0")/.."
L=results/late
SRC=$HOME/2048_cal6/results/cal6/jx
until [ "$(ls $SRC/xexpert_*.tsv 2>/dev/null | wc -l)" -ge 16 ]; do sleep 120; done
sleep 60
mkdir -p $L/jx
cp $SRC/xexpert_*.tsv $L/jx/
cp $HOME/2048_cal6/results/cal6/xexpert.tsv $L/jx/meta.tsv 2>/dev/null
export SET=judge JNAME=jx JMIN=0 JFILES=$(ls $L/jx/xexpert_*.tsv | paste -sd,) K=16
for n in base t21 c0_2 x50_2 xA_2 xB_2 u0_2 u0_3; do
  case $n in base) P=weights/best_v5.w ;; t21) P=weights/late/v5_t21.w ;; *) P=weights/late/v5_$n.w ;; esac
  until [ -f $P ]; do sleep 120; done
  scripts/exp_late_claims.sh $n --weights $P
done
echo done > $L/q7.done
