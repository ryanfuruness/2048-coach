#!/bin/bash
# Calibration study, part 2: mid/late-game damage. A clean engine game gets a lapse of human-like play (softmax
# player) at a random point, then the engine takes over again; the position after the lapse carries the engine's
# real outcome (the engine-with-mistakes category of part 1 died at 2048-8192: its second-best moves are often bad).
#   G=250 SEED=201 scripts/study_calib2.sh   (waits for part 1 of the same SEED to finish)
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
G=${G:-2000}
T=${T:-$(nproc)}
SEED=${SEED:-101}
until [ -f results/calib/s${SEED}.done ]; do sleep 30; done
run() {  # name policy per_game games
  local out=results/calib/s${SEED}_$1
  [ -s $out.tsv ] && [ "$(wc -l < $out.tsv)" -gt 2 ] && return
  ./build/messy --preset best --policy "$2" --games $4 --per-game $3 --record-switch --values --threads $T \
    --seed $SEED --out $out > $out.log 2>&1
}
run lapse8   "engine@6000-14000,soft:t=0.01@+300,engine" 8 $G
run lapse16  "engine@16000-30000,soft:t=0.01@+300,engine" 8 $G
run lapse16b "engine@16000-30000,soft:t=0.03@+600,engine" 8 $G
echo done > results/calib/s${SEED}_part2.done
