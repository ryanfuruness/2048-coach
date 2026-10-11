#!/bin/bash
cd "$(dirname "$0")/.."
W=weights/explr
L=results/explr
EGO="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big"
for s in a3_1 a3_2 a1_1 a1_2; do
  until [ -f $W/$s.w ]; do sleep 30; done
  python3 scripts/splice_stage.py weights/exps/best_v2.w 2 $W/$s.w 0 $W/play.w > /dev/null
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights $W/play.w --stages "sum:20480/14,28672,36864" --start weights/exps1/pool700.bin --games 700 \
      --threads 14 --seed 999 --quantize --depth 4 --stage-depth 3,4,4,4 --stop-sum 36864 $EGO > $L/${s}_phase.log 2>&1 )
  echo "$s whole phase: $(grep 'tile sum' $L/${s}_phase.log)" | tee -a $L/eval.log
done
rm -f $W/play.w
