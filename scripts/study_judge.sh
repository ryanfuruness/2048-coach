#!/bin/bash
# Robustness study: is the engine's move the best move on messy positions? For handover positions of the calibration
# study (human-like play up to there) and clean engine positions, every legal move is judged by K playouts of H engine
# moves + the network value at the cut-off (common random numbers across moves); scripts/judge_report.py counts the
# positions where the engine's move is significantly worse than the rollout-best move.
#   N=300 K=32 H=200 scripts/study_judge.sh [PREFIX]   (PREFIX of the calibration files, default results/calib/s_)
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
P=${1:-results/calib/s_}
N=${N:-300}; K=${K:-32}; H=${H:-200}; T=${T:-$(nproc)}
mkdir -p results/judge
for f in ${P}*.tsv; do
  cat=$(basename $f .tsv)
  out=results/judge/${cat}_h${H}.tsv
  [ -s $out ] && continue
  if [ "$cat" = "$(basename ${P})clean" ]; then where="True"; else where="switch == 1"; fi
  python3 scripts/select_positions.py results/judge/$cat.bin --where "$where" --max $N $f > /dev/null
  ./build/rollout --preset best --pool results/judge/$cat.bin --playouts $K --horizon $H --threads $T \
    --out $out > results/judge/${cat}_h${H}.log 2>&1
  python3 scripts/judge_report.py $out | head -12 | tee -a results/judge/summary_h${H}.txt
done
