#!/bin/bash
# Sequential (Hogwild CPU) vs batched-mean (GPU) training. Hypothesis: the GPU trainer's averaged
# batched updates make networks lean on rare, position-specific features (they generalize poorly
# and degrade under deeper search); the CPU trainer applies every update at once, as in the
# literature. Same task as v11c's s2: the second half [28672, 36864) from fresh optimistic weights,
# corner lock, tables in the loop, mixed pool; 4M episodes. Then depth 3 vs 4 on real positions,
# against the GPU network trained the same way for 4M episodes (weights/expu/mean.w).
set -e
cd "$(dirname "$0")/.."
W=weights/expcpu
L=results/expcpu
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
if [ ! -f $W/s2.w ]; then
  echo "[$(date '+%F %T')] CPU training" >> $L/log
  ./build/train --load $W/start.w --stages "sum:36864" --train-stage 0 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 \
    --corner-lock 14 --endgame-dir weights/endgame_big --endgame-min 0.5 --endgame-full 2 \
    --pool weights/v11c/pool2mix.bin --pool-last $NPOOL --episodes 4000000 --threads 18 --log 250000 \
    --save $W/s2.w.part --checkpoint $W/s2.ckpt > $L/train.log 2>&1
  mv $W/s2.w.part $W/s2.w
fi
# player: v11c with this second half (CPU file stage 0 -> v11c stage 2)
[ -f $W/final.w ] || python3 scripts/splice_stage.py weights/v11c/final.w 2 $W/s2.w 0 $W/final.w
ST4="sum:20480/14,28672,36864"
EGO="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame"
for net in cpu gpu; do
  w=$W/final.w; [ $net = gpu ] && w=weights/expu/mean.w
  for d in 3 4; do
    ( ulimit -s unlimited; ulimit -v 5500000
      ./build/play --weights $w --stages $ST4 --start weights/v11b/pool2real.bin --games 1147 --threads 14 --seed 31 \
        --quantize --depth $d --stop-sum 36864 $EGO > $L/${net}_d$d.log 2>&1 )
    echo "$net-trained second half (4M episodes), real positions, depth $d: $(grep 'tile sum' $L/${net}_d$d.log)" | tee -a $L/log
  done
done
