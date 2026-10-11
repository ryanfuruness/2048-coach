#!/bin/bash
# Calibration pilot 2: human-like softmax players (and beginner policies) hand over to the full engine at a random tile
# sum below where they usually die; the handover position's outcome is the engine's outcome from that messy position.
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
mkdir -p results/calib
G=${G:-60}
run() {  # name policy per_game
  [ -s results/calib/p2_$1.tsv ] && [ "$(wc -l < results/calib/p2_$1.tsv)" -gt 2 ] && return
  ./build/messy --preset best --policy "$2" --games $G --per-game $3 --record-switch --values --threads 16 \
    --seed 11 --out results/calib/p2_$1 > results/calib/p2_$1.log 2>&1
}
run soft03  "soft:t=0.03@300-2000,engine" 2
run soft01  "soft:t=0.01@500-8000,engine" 2
run soft003 "soft:t=0.003@1000-20000,engine" 2
run corner  "corner:eps=0.02@100-400,engine" 2
run greedy  "greedy@100-300,engine" 2
echo done > results/calib/p2.done
