#!/bin/bash
# CPU queue after the 2026-10-02 reboot: finish the k=5 table (resume), then exp_deep2.sh (k=5 evals, first-half
# depth tests, second-half selective depth) and exp_cpulong.sh. Run with an argument containing
# "exp_lowrate_eval.sh" so that exp_2ply's eval waits (one big CPU job at a time).
cd "$(dirname "$0")/.."
mkdir -p results/expdeep
if [ ! -f weights/endgame_lt/k5r10.done ]; then
  ./build/layered --k 5 --rank 10 --caps 9,9,8,8,8,9,9,7,7,7,7 --out weights/endgame_lt/k5r10.lt --threads 18 \
    --resume 352 > results/expdeep/k5r10_solve2.log 2>&1 && touch weights/endgame_lt/k5r10.done
fi
scripts/exp_deep2.sh
scripts/exp_cpulong.sh exp_lowrate_eval.sh.hold
