#!/bin/bash
# After queue14: TD annealing of the early-game network s0cpu (TC, 12.3M episodes; the decaying TD schedule gave the
# second half a much better stand-alone network): plain TD alpha 0.01 for 4M, then 0.001 for 2M episodes, from the start
# position to sum 20480; early-game test from scratch (1400 games, best_v5 with stage 0 replaced; ref 95.71% reach 16384).
cd "$(dirname "$0")/.."
W=weights/expearlytd
L=results/expearlytd
mkdir -p $W $L
while ps -eo args | grep -q "^/bin/bash scripts/exp_queue14.sh"; do sleep 60; done
COMMON="--stages sum:20480 --train-stage 0 --stop-at-boundary --lambda 0.5 --threads 18 --log 500000"
if [ ! -f $W/e01.w ]; then
  ./build/train --load weights/tup/s0cpu.w $COMMON --alpha 0.01 --episodes 4000000 --save $W/e01.w.part > $L/e01.log 2>&1 \
    && mv $W/e01.w.part $W/e01.w
  echo "e01 train: $(grep 'games  avg' $L/e01.log | tail -n 1)" >> $L/eval.log
fi
if [ ! -f $W/e001.w ]; then
  ./build/train --load $W/e01.w $COMMON --alpha 0.001 --episodes 2000000 --save $W/e001.w.part > $L/e001.log 2>&1 \
    && mv $W/e001.w.part $W/e001.w
  echo "e001 train: $(grep 'games  avg' $L/e001.log | tail -n 1)" >> $L/eval.log
fi
ST5="sum:20480/14,24576,28672,36864"
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
LT="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5 --lt-view"
VIEW="--leaf-view 14 6 --leaf-view-max-sum 24576"
for v in e01 e001; do
  n=early_$v
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && continue
  [ -f $W/$v.w ] || continue
  python3 scripts/splice_stage.py weights/best_v5.w 0 $W/$v.w 0 $L/p5.w > /dev/null
  ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
    ./build/play --weights $L/p5.w --stages "$ST5" --games 1400 --threads 18 --seed 4321 --quantize --depth 4 \
      --stage-depth 3,4,4,4,4 --stop-sum 20480 $EGO $LT $VIEW > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(grep 'reached  16384' $L/$n.log)   (s0cpu: 95.71% reach 16384)" | tee -a $L/eval.log
  rm -f $L/p5.w
done
echo "queue15 done" >> $L/eval.log
