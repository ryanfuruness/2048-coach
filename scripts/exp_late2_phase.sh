#!/bin/bash
# Workstream late2: phase tests of the full player (best_v5bb settings = preset_best) for a 5-stage weights file.
#   early: from the empty board to tile sum 20480, 1400 games per seed in $SEEDS (default "4321 4322"): reach-16384 and
#          reach-sum-20480 rates (s0cpu in best_v5: 95.71% reach 16384, seed 4321)
#   ph16:  700 real 16384 starts (weights/exps1/pool700.bin) to sum 36864, seeds 999/1001/1002 (late's protocol)
#   p32:   the 1878 boards of weights/pool32k.bin (32768 just formed) to game over, seed 999 (late's protocol)
# Logs results/late2/{early,ph16,p32}_NAME*.log; summaries appended to results/late2/eval.log. $THREADS (default 40).
# usage: exp_late2_phase.sh early|ph16|p32 NAME WEIGHTS [play flags]
cd "$(dirname "$0")/.."
T=$1 N=$2 W=$3; shift 3
L=results/late2; mkdir -p $L
TH=${THREADS:-40}
ST5="sum:20480/14,24576,28672,36864"
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
LT="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5 --lt-view"
VIEW="--leaf-view 14 6 --leaf-view-max-sum 24576"
BUD="--min-depth 4 --budget 20000"
P="--stages $ST5 --quantize --depth 4 --stage-depth 3,4,8,8,4 $BUD $EGO $LT $VIEW"
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
summ() {  # files... -> "reached X% +- e (r/n)"
  cat "$@" | awk '/reached tile sum/ { gsub(/[()]/, "", $NF); r += $NF; n += NG } END { p = r / n; printf "%.2f%% +- %.2f (%d/%d)", 100 * p, 100 * sqrt(p * (1 - p) / n), r, n }' NG=$NG
}
if [ $T = early ]; then
  NG=${GAMES:-1400}; SEEDS=${SEEDS:-"4321 4322"}
  for s in $SEEDS; do
    f=$L/early_${N}_s$s.log
    [ -f $f ] && grep -q "tile sum" $f && continue
    ./build/play --weights $W $P --games $NG --threads $TH --seed $s --stop-sum 20480 "$@" > $f 2>&1
  done
  fs=$(for s in $SEEDS; do echo $L/early_${N}_s$s.log; done)
  echo "early_$N ($W $*): sum 20480 $(summ $fs)  16384: $(cat $fs | awk '/reached  16384/ {print}' | head -2 | tr '\n' ' ')" | tee -a $L/eval.log
elif [ $T = ph16 ]; then
  NG=700; SEEDS=${SEEDS:-"999 1001 1002"}
  for s in $SEEDS; do
    f=$L/ph16_${N}_s$s.log
    [ -f $f ] && grep -q "tile sum" $f && continue
    ./build/play --weights $W $P --start weights/exps1/pool700.bin --games 700 --threads $TH --seed $s --stop-sum 36864 "$@" > $f 2>&1
  done
  echo "ph16_$N ($W $*): $(summ $(for s in $SEEDS; do echo $L/ph16_${N}_s$s.log; done))" | tee -a $L/eval.log
else
  f=$L/p32_$N.log
  if ! { [ -f $f ] && grep -q "=== " $f; }; then
    ./build/play --weights $W $P --start weights/pool32k.bin --games 1878 --threads $TH --seed 999 "$@" > $f 2>&1
  fi
  echo "p32_$N ($W $*): $(grep 'mean score' $f | sed 's/  */ /g')  sums>=49152/57344/61440: $(grep '^game' $f | awk '{n++; if ($NF>=49152) a++; if ($NF>=57344) b++; if ($NF>=61440) c++} END {printf "%.1f%% / %.1f%% / %.1f%%", 100*a/n, 100*b/n, 100*c/n}')" | tee -a $L/eval.log
fi
