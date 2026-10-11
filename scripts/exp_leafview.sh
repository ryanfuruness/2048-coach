#!/bin/bash
# Leaf view: evaluate 16384-phase leaves in their downgraded view (16384 -> 8192, ...) so that the early-game
# network s0cpu (stage 0, zero-init, CPU-trained, gains from search) values them as the 8192-phase boards they
# mirror. The search still runs on real boards (lock and tables unchanged). Whole phase from 700 real starts,
# best_v2 otherwise (58.0%). Variants: smallest gap rank 6/8/10; view only in the first half (sum < 28672).
# Then runs exp_deep2.sh and exp_cpulong.sh. Holds exp_2ply's eval (name trick) until done.
cd "$(dirname "$0")/.."
L=results/expview
mkdir -p $L
until grep -q "^a1_2 whole" results/explr/eval.log 2>/dev/null; do sleep 30; done
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big"
run() {  # name, extra options
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights weights/exps/best_v2.w --stages "sum:20480/14,28672,36864" --start weights/exps1/pool700.bin \
      --games 700 --threads 14 --seed 999 --quantize --depth 4 --stage-depth 3,4,4,4 --stop-sum 36864 $EGO "${@:2}" \
      > $L/$1.log 2>&1 )
  echo "$1: $(grep 'tile sum' $L/$1.log)" | tee -a $L/eval.log
}
run v6 --leaf-view 14 6
run v6h1 --leaf-view 14 6 --leaf-view-max-sum 28672
run v10 --leaf-view 14 10
run v8 --leaf-view 14 8
scripts/exp_deep2.sh
scripts/exp_cpulong.sh exp_lowrate_eval.sh.hold
