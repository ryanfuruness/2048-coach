#!/bin/bash
# Selective deeper search in the second half (best_v2's second half = exps e4; 600 real positions at sum 28672,
# seed 31; d3 58.0 / d4 60.5): budgeted iterative deepening (tight boards get searched deeper) and macroxue-style
# probability cuts.
cd "$(dirname "$0")/.."
L=results/expdeep
mkdir -p $L
# first: the k=5 snake table (chain 16384..1024, build a 1024 next to it; 11 free cells capped 9/8/7, ~3e10
# states, ~60 GB) by layered DP at full width
if [ ! -f weights/endgame_lt/k5r10.done ]; then
  ./build/layered --k 5 --rank 10 --caps 9,9,8,8,8,9,9,7,7,7,7 --out weights/endgame_lt/k5r10.lt --threads 18 \
    > results/expdeep/k5r10_solve.log 2>&1 && touch weights/endgame_lt/k5r10.done
fi
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big"
run() {  # name, options
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights weights/exps/best_v2.w --stages "sum:20480/14,28672,36864" --start weights/exps/pool600.bin \
      --games 600 --threads 14 --seed 31 --quantize --stop-sum 36864 $EGO "${@:2}" > $L/$1.log 2>&1 )
  echo "$1: $(grep 'tile sum' $L/$1.log)  $(grep -o 'avg [0-9.]* ms/move' $L/$1.log | tail -1)" | tee -a $L/eval.log
}
# the k=5 table on top of best_v2 (whole phase from 700 real starts, d4 / stage depths 3,4,4,4; best_v2 58.0%)
LT="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7"
phase() {  # name, options
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights weights/exps/best_v2.w --stages "sum:20480/14,28672,36864" --start weights/exps1/pool700.bin \
      --games 700 --threads 14 --seed 999 --quantize --depth 4 --stage-depth 3,4,4,4 --stop-sum 36864 $EGO "${@:2}" \
      > $L/$1.log 2>&1 )
  echo "$1: $(grep 'tile sum' $L/$1.log)  $(grep 'layered table moves' $L/$1.log)" | tee -a $L/eval.log
}
if [ -f weights/endgame_lt/k5r10.done ]; then
  phase k5_p50 $LT --lt-min 0.5
  phase k5_p30 $LT --lt-min 0.3
  phase k5_p0 $LT --lt-min 0.0
  # with the s0cpu leaf view while building the 8192 (59.9% alone)
  phase k5v_p50 $LT --lt-min 0.5 --leaf-view 14 6 --leaf-view-max-sum 24576
  # 5 stages: s0cpu view below 24576, stage B b3 for [24576, 28672), e4 second half, k=5 table
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights weights/expsplit/b3_play.w --stages "sum:20480/14,24576,28672,36864" \
      --start weights/exps1/pool700.bin --games 700 --threads 14 --seed 999 --quantize --depth 4 --stage-depth 3,4,4,4,4 \
      --stop-sum 36864 $EGO $LT --lt-min 0.5 --leaf-view 14 6 --leaf-view-max-sum 24576 > $L/k5vb3.log 2>&1 )
  echo "k5vb3: $(grep 'tile sum' $L/k5vb3.log)  $(grep 'layered table moves' $L/k5vb3.log)" | tee -a $L/eval.log
fi
# deeper search in the first half (macroxue's first-half losses: d3 10.5%, d4 5.2%, d5 2.9%, d8 0.8%; ours 13.1% at d4)
phase h1d5 --stage-depth 3,5,4,4
phase h1d5v --stage-depth 3,5,4,4 --leaf-view 14 6 --leaf-view-max-sum 28672
phase h1b20k --stage-depth 3,8,4,4 --min-depth 3 --budget 20000
run d4 --depth 4
run b8k --min-depth 3 --depth 8 --budget 8000
run b30k --min-depth 3 --depth 9 --budget 30000
run d5p --depth 5 --prob-cut 0.004
