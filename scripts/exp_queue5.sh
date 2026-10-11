#!/bin/bash
# After exp_queue4: deeper selective search on top of the best whole-phase configuration (k5vb3 = 5-stage b3 player,
# s0cpu leaf view below 24576, k=5 tables; 61.7%): budgeted iterative deepening in the second half (tight boards
# get depth 5-8), and in both halves.
cd "$(dirname "$0")/.."
L=results/expq5
mkdir -p $L
while ps -eo args | grep -q "^/bin/bash scripts/exp_queue[34].sh"; do sleep 30; done
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
LT="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5"
VIEW="--leaf-view 14 6 --leaf-view-max-sum 24576"
phase() {  # name stage-depths [options]
  local n=$1 sd=$2; shift 2
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights weights/expsplit/b3_play.w --stages "sum:20480/14,24576,28672,36864" \
      --start weights/exps1/pool700.bin --games 700 --threads 14 --seed 999 --quantize --depth 4 --stage-depth $sd \
      --stop-sum 36864 $EGO $LT $VIEW "$@" > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(grep -o 'avg [0-9.]* ms/move' $L/$n.log)" | tee -a $L/eval.log
}
phase bud2nd_20k 3,4,4,8,4 --min-depth 4 --budget 20000
phase bud_all_20k 3,8,8,8,4 --min-depth 4 --budget 20000
