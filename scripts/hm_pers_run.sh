#!/bin/bash
# Personal odds v3 transfer check (workstream hm): human-model players (src/human.h, the hm_personal.sh skill family)
# play on from cal6's real positions (results/cal6/pers_rR.bin, largest tile 2^(R-2)) until 4x (stop rank R) or 2x
# (R-1) its tile or death, 32 playouts per position, first move = the engine's (as calib_pers_run.sh for soft:t).
# Output results/hm/pers/soft<KEY>_r<R>[_2x].tsv (named like cal6's files, so the report reads them the same way).
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
T=${1:-8}
KEYS=${KEYS:-"0.012 0.008 0.003 0.00135 0.0005"}
HMODEL=${HMODEL:-results/hm/human_model_v2.txt}
mkdir -p results/hm/pers
run() {  # key r stop suffix
  local s; s=$(python3 -c "import math; print(f'{-math.log(100*$1):.4f}')")
  local f=results/hm/pers/soft$1_r$2$4.tsv
  [ -s $f ] || ./build/rollout --preset best-notables --pool results/cal6/pers_r$2.bin --playouts 32 --horizon 0 \
    --stop-rank $3 --moves engine --human $s --human-model $HMODEL --threads $T --seed 9 --out $f.tmp \
    > ${f%.tsv}.log 2>&1 && mv $f.tmp $f
}
for k in $KEYS; do
  ( for r in 9 10 11 12 13 14 15; do run $k $r $r ""; run $k $r $((r - 1)) _2x; done ) &
done
wait
echo done > results/hm/pers/done
