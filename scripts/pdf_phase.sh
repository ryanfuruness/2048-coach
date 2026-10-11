#!/bin/bash
# Phase tests of the full player (workstream pdf: copy of scripts/exp_late_phase.sh writing to results/pdf), best_v5bb settings + the given play flags (later flags override):
#   ph16: the whole 16384 phase, 700 real 16384-formation starts (weights/exps1/pool700.bin) to tile sum 36864, one run
#         per seed in $SEEDS (default "999 1001 1002"); success = reaching the sum.
#   p32:  the 32768 phase, the 1878 boards of weights/pool32k.bin (the 32768 just formed) to game over, seed 999;
#         score gained, sums >= 49152 / 57344 / 61440, 65536 rate.
# $THREADS threads (default 96). Logs results/late/{ph16,p32}_NAME[_sSEED].log, summaries in results/late/eval.log
# (paired comparisons: scripts/exp_late_paired.py).
# usage: exp_late_phase.sh ph16|p32 NAME WEIGHTS STAGE_DEPTHS [play flags]
cd "$(dirname "$0")/.."
T=$1 N=$2 W=$3 SD=$4; shift 4
L=results/pdf; mkdir -p $L
TH=${THREADS:-32}
ST5=${STAGES:-"sum:20480/14,24576,28672,36864"}
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
LT="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5 --lt-view"
VIEW="--leaf-view 14 6 --leaf-view-max-sum 24576"
BUD="--min-depth 4 --budget 20000"
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
if [ $T = ph16 ]; then
  SEEDS=${SEEDS:-"999 1001 1002"}
  for s in $SEEDS; do
    f=$L/ph16_${N}_s$s.log
    [ -f $f ] && grep -q "tile sum" $f && continue
    ./build/play --weights $W --stages "$ST5" --start weights/exps1/pool700.bin --games 700 --threads $TH --seed $s \
      --quantize --depth 4 --stage-depth $SD $BUD --stop-sum 36864 $EGO $LT $VIEW "$@" > $f 2>&1
  done
  echo "ph16_$N ($W $SD $*): $(cat $(for s in $SEEDS; do echo $L/ph16_${N}_s$s.log; done) | awk '/reached tile sum/ {
      gsub(/[()]/, "", $NF); r += $NF; n += 700 } END { p = r / n; printf "%.2f%% +- %.2f (%d/%d)", 100 * p, 100 * sqrt(p * (1 - p) / n), r, n }')  $(grep -ho 'avg [0-9.]* ms/move' $L/ph16_${N}_s*.log | head -1)" | tee -a $L/eval.log
else
  f=$L/p32_$N.log
  if ! { [ -f $f ] && grep -q "=== " $f; }; then
    ./build/play --weights $W --stages "$ST5" --start weights/pool32k.bin --games 1878 --threads $TH --seed 999 --quantize \
      --depth 4 --stage-depth $SD $BUD $EGO $LT $VIEW "$@" > $f 2>&1
  fi
  echo "p32_$N ($W $SD $*): $(grep 'mean score' $f | sed 's/  */ /g')  sums>=49152/57344/61440: $(grep '^game' $f | awk '{n++; if ($NF>=49152) a++; if ($NF>=57344) b++; if ($NF>=61440) c++} END {printf "%.1f%% / %.1f%% / %.1f%%", 100*a/n, 100*b/n, 100*c/n}')  $(grep 'reached  65536' $f | sed 's/  */ /g')" | tee -a $L/eval.log
fi
