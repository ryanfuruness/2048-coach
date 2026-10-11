#!/bin/bash
# Leaf view, round 2 (round 1: s0cpu via the view in the first half = 58.3% vs best_v2 58.0%; first-half deaths
# 92 -> 67 but the second half converts worse; view in the second half too: 11.3%). Variants: the distortion-safe
# gap choice (no pair of tiles just below the gap), the view only while building the 8192 (sum < 24576, where
# s0cpu cut deaths 43 -> 23), and the safe view everywhere. Then the k=5 table solve and evals (exp_deep2.sh)
# and exp_cpulong.sh. Holds exp_2ply's eval (name trick) until done.
cd "$(dirname "$0")/.."
L=results/expview
mkdir -p $L
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big"
run() {  # name, extra options
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights weights/exps/best_v2.w --stages "sum:20480/14,28672,36864" --start weights/exps1/pool700.bin \
      --games 700 --threads 14 --seed 999 --quantize --depth 4 --stage-depth 3,4,4,4 --stop-sum 36864 $EGO "${@:2}" \
      > $L/$1.log 2>&1 )
  echo "$1: $(grep 'tile sum' $L/$1.log)" | tee -a $L/eval.log
}
run s6h1 --leaf-view 14 6 --leaf-view-max-sum 28672 --leaf-view-safe
run v6q --leaf-view 14 6 --leaf-view-max-sum 24576
run s6 --leaf-view 14 6 --leaf-view-safe
scripts/exp_deep2.sh
scripts/exp_cpulong.sh exp_lowrate_eval.sh.hold
