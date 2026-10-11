#!/bin/bash
# Evaluates a v11-style 4-stage network (sum:20480,28672,36864): its second half from a pool, at
# depths 2 and 3 with tables, then full games. usage: eval_v11.sh WEIGHTS POOL2 OUTDIR [GAMES]
set -e
cd "$(dirname "$0")/.."
W=$1 POOL2=$2 OUT=$3 N=${4:-280}
mkdir -p $OUT
ST4=${ST4:-"sum:20480,28672,36864"}  # v11c: sum:20480/14,28672,36864
EGO="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame"
ulimit -s unlimited
ulimit -v 6000000
for d in 2 3; do
  scripts/eval_pool.sh $W "$ST4" $POOL2 420 14 $OUT/half2_d$d.log --depth $d --stop-sum 36864 --quantize $EGO > /dev/null
  echo "second half, depth $d: $(grep -E 'tile sum' $OUT/half2_d$d.log)"
done
./build/play --weights $W --stages "$ST4" --quantize --games $N --threads 14 --seed 999 --depth 3 --root-downgrade 15 \
  $EGO --record $OUT/full_games.txt > $OUT/full.log 2>&1
grep -A 10 "===" $OUT/full.log | grep -E "mean|table|16384|32768|65536"
