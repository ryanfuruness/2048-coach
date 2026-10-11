#!/bin/bash
# Workstream serve: the 16384-phase test (late's protocol, as scripts/exp_late2_phase.sh ph16 with v6c's flags) for a
# weights file, one seed. Run in ~/2048_serve on the instance. usage: serve_ph16.sh NAME WEIGHTS SEED THREADS
N=$1 W=$2 S=${3:-999} TH=${4:-16}
mkdir -p results/serve
ST5="sum:20480/14,24576,28672,36864"
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
LT="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5 --lt-view"
VIEW="--leaf-view 14 6 --leaf-view-max-sum 24576"
BUD="--min-depth 4 --budget 20000"
P="--stages $ST5 --quantize --depth 4 --stage-depth 3,4,8,8,4 $BUD $EGO $LT $VIEW"
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
./build/play --weights $W $P --start weights/exps1/pool700.bin --games 700 --threads $TH --seed $S --stop-sum 36864 \
  --leaf-view-max-sum 20480 > results/serve/ph16_${N}_s$S.log 2>&1
echo done > results/serve/ph16_${N}_s$S.done
