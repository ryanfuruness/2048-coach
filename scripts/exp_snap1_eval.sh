#!/bin/bash
cd "$(dirname "$0")/.."
W=weights/exps1
L=results/exps1
mkdir -p $W $L
head -c $((700*8)) weights/v11c/pool16real.bin > $W/pool700.bin
EGO="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame"
for s in base e8 e9 e10 e11 e12 e14; do
  w=$W/$s.w; [ $s = base ] && w=weights/v11c/m1q.w   # v11c's first half (14M + curriculum)
  until [ -f $w ]; do sleep 30; done
  for d in 3 4; do
    ( ulimit -s unlimited; ulimit -v 5000000
      ./build/play --weights $w --stages "sum:20480/14,36864" --start $W/pool700.bin --games 700 --threads 14 \
        --seed 999 --quantize --depth $d --stop-sum 28700 $EGO > $L/${s}_d$d.log 2>&1 )
    echo "$s first half d$d: $(grep 'tile sum' $L/${s}_d$d.log)" | tee -a $L/eval.log
  done
done
