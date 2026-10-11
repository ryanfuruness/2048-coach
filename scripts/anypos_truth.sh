#!/bin/bash
# Engine-continuation truth for the odd positions (workstream anypos): per stage file results/anypos/${P}_rR.bin, NP
# playouts from the engine's move to the end or to two doublings above the largest tile (one for 16384 boards: the
# odds have no 65536 target). Run on the instance in ~/2048_anypos.
# usage: [P=pos] [STAGES="8 ... 14"] [ENGINE=flags] anypos_truth.sh [NP] [SUFFIX]   -> results/anypos/truth${SUFFIX}_rR.tsv
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
NP=${1:-64}; SUF=${2:-}
P=${P:-pos}; STAGES=${STAGES:-"8 9 10 11 12 13 14"}
E=${ENGINE:-"--weights weights/best_v6b.w"}  # explicit: the instance has no weights/best.cfg
declare -A TH=([8]=4 [9]=4 [10]=4 [11]=8 [12]=16 [13]=32 [14]=32)
[ -n "$THREADS" ] && eval "declare -A TH=($THREADS)"
for R in $STAGES; do
  STOP=$((R + 2)); [ $STOP -gt 15 ] && STOP=15
  OUT=results/anypos/truth${SUF}_r$R.tsv
  [ -s $OUT ] && continue
  nohup ./build/rollout --preset best $E --pool results/anypos/${P}_r$R.bin --playouts $NP --horizon 0 --stop-rank $STOP \
    --moves engine --threads ${TH[$R]} --seed $((900 + R)) --out $OUT > results/anypos/truth${SUF}_r$R.log 2>&1 &
done
wait
echo done > results/anypos/truth$SUF.done
