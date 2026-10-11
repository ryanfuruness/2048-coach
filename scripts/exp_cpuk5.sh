#!/bin/bash
# Second half trained with the k=5 table in the loop (CPU trainer, pread lookups): fresh optimistic, lock, k>=6 tables
# + k5r10, pool2mix, 4M episodes; compare with the CPU-trained 4M second half without it (weights/expcpu/s2.w) as
# stage 3 of the best configuration (k5vb3: b3 player, leaf view < 24576, k=5 tables; 61.7%).
cd "$(dirname "$0")/.."
W=weights/expck5
L=results/expck5
mkdir -p $W $L
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
LT10="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7"
LT9="--endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7"
if [ ! -f $W/s2.w ]; then
  echo "[$(date '+%F %T')] CPU training with k5 in the loop" >> $L/log
  ./build/train --load weights/expcpu/start.w --stages "sum:36864" --train-stage 0 --stop-at-boundary --tc --alpha 1.0 \
    --lambda 0.5 --corner-lock 14 --endgame-dir weights/endgame_big --endgame-min 0.5 --endgame-full 2 $LT10 --lt-min 0.5 \
    --pool weights/v11c/pool2mix.bin --pool-last $NPOOL --episodes 4000000 --threads 18 --log 250000 \
    --save $W/s2.w.part > $L/train.log 2>&1 && mv $W/s2.w.part $W/s2.w
fi
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
for net in k5 nok5; do
  src=$W/s2.w; [ $net = nok5 ] && src=weights/expcpu/s2.w
  [ -f $L/$net.log ] && grep -q "tile sum" $L/$net.log && continue
  python3 scripts/splice_stage.py weights/expsplit/b3_play.w 3 $src 0 $W/play.w > /dev/null
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights $W/play.w --stages "sum:20480/14,24576,28672,36864" --start weights/exps1/pool700.bin \
      --games 700 --threads 14 --seed 999 --quantize --depth 4 --stage-depth 3,4,4,4,4 --stop-sum 36864 $EGO \
      $LT10 $LT9 --lt-min 0.5 --leaf-view 14 6 --leaf-view-max-sum 24576 > $L/$net.log 2>&1 )
  echo "CPU second half ($net in the loop) in the best config: $(grep 'tile sum' $L/$net.log)" | tee -a $L/eval.log
done
rm -f $W/play.w
