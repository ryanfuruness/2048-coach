#!/bin/bash
# Workstream late: 1000-game benchmark of a candidate player with the best_v5bb settings (scripts/bench.sh: chunks of
# 100 games, seeds 1000+k -> paired with results/bench/best_v5bb_1000, games identical until the changed stage is used).
# usage: exp_late_bench.sh NAME WEIGHTS THREADS [extra play flags]
cd "$(dirname "$0")/.."
N=$1 W=$2 TH=$3; shift 3
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
scripts/bench.sh $N $W "sum:20480/14,24576,28672,36864" 1000 100 $TH --quantize --depth 4 --stage-depth 3,4,8,8,4 \
  --min-depth 4 --budget 20000 --corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 \
  --endgame-dir weights/endgame_big --endgame-nosave --endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 \
  --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 \
  --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5 --lt-view --leaf-view 14 6 --leaf-view-max-sum 24576 "$@"
