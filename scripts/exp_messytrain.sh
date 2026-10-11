#!/bin/bash
# Robustness training (only if the judge study shows the engine misplays messy positions): fine-tune the early-game
# network s0cpu (stage 0 of best_v5, tile sums below 20480 - where nearly all human positions live) with half of the
# training episodes starting from human-like messy positions, plain TD with a decaying rate (the OTD schedule that gave
# the best stand-alone networks; never a fresh TC tail).
#   1. pool: positions of softmax players (t = 0.003 / 0.01 / 0.03) and beginner policies, tile sums 64-20000
#   2. TD alpha 0.01 for 4M episodes, then 0.001 for 2M
#   3. tests: early game from scratch (1400 games, reach 16384; s0cpu 95.71%) and the judge on messy positions
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
T=${T:-$(nproc)}
W=weights/expmessy
L=results/expmessy
mkdir -p $W $L
POOL=$W/pool.bin
if [ ! -f $POOL ]; then
  for spec in "soft:t=0.003" "soft:t=0.01" "soft:t=0.03" "corner:eps=0.02" "greedy" "heur"; do
    n=$(echo "$spec" | tr ':=.' '___')
    ./build/messy --preset best-notables --policy "$spec" --games 40000 --per-game 8 --min-sum 64 --max-sum 20000 \
      --threads $T --seed 77 --out $L/pool_$n > $L/pool_$n.log 2>&1
    cat $L/pool_$n.bin >> $POOL.part
  done
  mv $POOL.part $POOL
fi
COMMON="--stages sum:20480 --train-stage 0 --stop-at-boundary --lambda 0.5 --threads $T --log 500000 --pool $POOL --pool-prob 0.5"
if [ ! -f $W/m01.w ]; then
  ./build/train --load weights/tup/s0cpu.w $COMMON --alpha 0.01 --episodes 4000000 --save $W/m01.w.part > $L/m01.log 2>&1 \
    && mv $W/m01.w.part $W/m01.w
fi
if [ ! -f $W/m001.w ]; then
  ./build/train --load $W/m01.w $COMMON --alpha 0.001 --episodes 2000000 --save $W/m001.w.part > $L/m001.log 2>&1 \
    && mv $W/m001.w.part $W/m001.w
fi
ST5="sum:20480/14,24576,28672,36864"
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
LT="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5 --lt-view"
VIEW="--leaf-view 14 6 --leaf-view-max-sum 24576"
for v in m01 m001; do
  [ -f $L/early_$v.log ] && grep -q "tile sum" $L/early_$v.log && continue
  python3 scripts/splice_stage.py weights/best_v5.w 0 $W/$v.w 0 $W/play_$v.w > /dev/null
  ./build/play --weights $W/play_$v.w --stages "$ST5" --games 1400 --threads $T --seed 4321 --quantize --depth 4 \
    --stage-depth 3,4,4,4,4 --stop-sum 20480 $EGO $LT $VIEW > $L/early_$v.log 2>&1
  echo "$v: $(grep 'tile sum' $L/early_$v.log)  $(grep 'reached  16384' $L/early_$v.log)   (s0cpu: 95.71%)" | tee -a $L/eval.log
done
