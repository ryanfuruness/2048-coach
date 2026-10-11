#!/bin/bash
# Full-game benchmark in resumable chunks.
# usage: bench.sh NAME WEIGHTS STAGES GAMES CHUNK THREADS [play options...]
# Chunk k plays CHUNK games with seed 1000+k and records them; finished chunks are
# skipped on a rerun. Results: results/bench/NAME/chunk*.log, games*.txt, summary.txt
set -e
cd "$(dirname "$0")/.."
NAME=$1 W=$2 ST=$3 N=$4 CH=$5 TH=$6
shift 6
D=results/bench/$NAME
mkdir -p "$D"
echo "$W $ST $*" > "$D/config.txt"
for ((k = 0; k * CH < N; k++)); do
  log=$D/chunk$k.log
  if [ -f "$log" ] && grep -q "=== " "$log"; then continue; fi
  rm -f "$D/games$k.txt"
  ./build/play --weights "$W" ${ST:+--stages "$ST"} --games "$CH" --threads "$TH" --seed $((1000 + k)) \
    --record "$D/games$k.txt" "$@" > "$log" 2>&1
  python3 scripts/summarize.py "$D"/chunk*.log | tee "$D/summary.txt" | head -n 3
done
python3 scripts/summarize.py "$D"/chunk*.log | tee "$D/summary.txt"
