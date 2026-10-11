#!/bin/bash
# 32768-phase test (500 positions at the 32768's formation -> game over, best_v5bb settings) of best_v5 with the OTD second
# half (weights/expotd/t21.w) as stage 3. Reference p32_v5bb: 269,148 / 71.6 / 49.2 / 31.8% (sums 49152/57344/61440).
cd "$(dirname "$0")/.."
L=results/expotd
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
LT="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5 --lt-view"
VIEW="--leaf-view 14 6 --leaf-view-max-sum 24576"
ST5="sum:20480/14,24576,28672,36864"
for v in ${1:-t21}; do
  n=p32_$v
  [ -f $L/$n.log ] && grep -q "=== " $L/$n.log && continue
  python3 scripts/splice_stage.py weights/best_v5.w 3 weights/expotd/$v.w 0 $L/p32.w > /dev/null
  ( ulimit -s unlimited; ulimit -v 6800000; export MALLOC_ARENA_MAX=2
    ./build/play --weights $L/p32.w --stages "$ST5" --start weights/pool32k.bin --games 500 --threads 18 --seed 999 --quantize \
      --depth 4 --stage-depth 3,4,8,8,4 --min-depth 4 --budget 20000 $EGO $LT $VIEW > $L/$n.log 2>&1 )
  echo "$n: $(grep 'mean score' $L/$n.log)  sums>=49152/57344/61440: $(grep '^game' $L/$n.log | awk '{n++; if ($NF>=49152) a++; if ($NF>=57344) b++; if ($NF>=61440) c++} END {printf "%.1f%% / %.1f%% / %.1f%%", 100*a/n, 100*b/n, 100*c/n}')   (p32_v5bb: 269,148 / 71.6 / 49.2 / 31.8%)" | tee -a $L/eval.log
  rm -f $L/p32.w
done
