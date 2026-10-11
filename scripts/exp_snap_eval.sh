#!/bin/bash
# Evaluates the exp_snap snapshots as v11c's second half: depth 3 and 4 on 600 real positions.
cd "$(dirname "$0")/.."
W=weights/exps
L=results/exps
head -c $((600*8)) weights/v11b/pool2real.bin > $W/pool600.bin
EGO="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame"
for s in e1 e2 e3 e4 e5 e6 e8 e4q; do
  until [ -f $W/$s.w ]; do sleep 30; done
  python3 scripts/splice_stage.py weights/v11c/final.w 2 $W/$s.w 0 $W/play.w > /dev/null
  for d in 3 4; do
    ( ulimit -s unlimited; ulimit -v 5000000
      ./build/play --weights $W/play.w --stages "sum:20480/14,28672,36864" --start $W/pool600.bin --games 600 \
        --threads 14 --seed 31 --quantize --depth $d --stop-sum 36864 $EGO > $L/${s}_d$d.log 2>&1 )
    echo "$s d$d: $(grep 'tile sum' $L/${s}_d$d.log)" | tee -a $L/eval.log
  done
done
rm -f $W/play.w
