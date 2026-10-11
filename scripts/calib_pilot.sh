#!/bin/bash
# Calibration pilot: games where a flawed policy hands over to the full engine at a random tile sum; the handover
# position's outcome is the engine's outcome from a messy position. Plus clean engine games as the reference.
# Output: results/calib/pilot_<cat>.{bin,tsv} (see src/messy.cpp for the columns).
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
mkdir -p results/calib
G=${G:-60}
run() {  # name policy per_game
  [ -s results/calib/pilot_$1.tsv ] && [ "$(wc -l < results/calib/pilot_$1.tsv)" -gt 2 ] && return
  ./build/messy --preset best --policy "$2" --games $G --per-game $3 --record-switch --values --threads 16 \
    --seed 7 --out results/calib/pilot_$1 > results/calib/pilot_$1.log 2>&1
}
run clean   "engine" 4
run net3    "net:eps=0.03@500-20000,engine" 2
run second  "net:second=0.15@500-20000,engine" 2
run corner  "corner:eps=0.02@300-1500,engine" 2
run greedy  "greedy@200-800,engine" 2
echo done > results/calib/pilot.done
