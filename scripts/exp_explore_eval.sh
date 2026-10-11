#!/bin/bash
cd "$(dirname "$0")/.."
W=weights/expx
L=results/expx
mkdir -p $W $L
EGO="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame"
for s in x3_e3 x3_e4 x3_e6 x6_e3 x6_e4 x6_e6; do
  until [ -f $W/$s.w ]; do sleep 30; done
  python3 scripts/splice_stage.py weights/v11c/final.w 2 $W/$s.w 0 $W/play.w > /dev/null
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights $W/play.w --stages "sum:20480/14,28672,36864" --start weights/exps/pool600.bin --games 600 \
      --threads 14 --seed 31 --quantize --depth 4 --stop-sum 36864 $EGO > $L/${s}_d4.log 2>&1 )
  echo "$s d4: $(grep 'tile sum' $L/${s}_d4.log)" | tee -a $L/eval.log
done
rm -f $W/play.w
