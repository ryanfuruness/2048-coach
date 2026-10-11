#!/bin/bash
# Quick SOTA test from the expert disputes: does a late-game leaf penalty for empty cells next to big tiles (what
# experts keep low where they beat the engine) raise the 16384-phase conversion? best_v5 full player (tables), 700 real
# 16384-formation starts to tile sum 36864, paired seeds (baseline best_v5 64.14% in this test, 2026-10-05).
# Leaf view sums: the 16384 phase is seen as the 8192 phase below 24576 (sums ~12k-16k) -> range 12288-65536.
cd "$(dirname "$0")/.."
L=results/expexposed
mkdir -p $L
ST5="sum:20480/14,24576,28672,36864"
EGO5="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
LT5="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5 --lt-view"
for w in 0 2000 6000; do
  n=w$w
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && continue
  PEN=""; [ $w -gt 0 ] && PEN="--exposed-pen $w 12288 65536"
  ( ulimit -s unlimited; export MALLOC_ARENA_MAX=2
    ./build/play --weights weights/best_v5.w --stages "$ST5" --start weights/exps1/pool700.bin --games 700 --threads 16 \
      --seed 999 --quantize --depth 4 --stage-depth 3,4,4,4,4 --stop-sum 36864 $EGO5 $LT5 \
      --leaf-view 14 6 --leaf-view-max-sum 24576 $PEN > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)" | tee -a $L/eval.log
done
echo done > $L/done
