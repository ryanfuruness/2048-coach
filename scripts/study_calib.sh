#!/bin/bash
# Calibration study at scale (laptop pilot: calib_pilot2.sh). Human-like players (softmax at several temperatures),
# beginner policies and the engine with mistakes hand over to the full engine at a random tile sum; the handover
# positions and positions sampled afterwards carry the engine's real outcome. Plus clean engine games. One messy
# process per category, run in sequence, each using every core. Early handovers carry little information (the engine
# repairs early damage: odds return to the base rates), so most categories hand over mid or late.
#   G=2000 SEED=101 scripts/study_calib.sh      (per category; ~2.5 thread-minutes per game)
# Use a different SEED for every run whose files will be merged (same seed = identical games). Output:
# results/calib/s<SEED>_<cat>.{bin,tsv}; report: scripts/calib_report.py, fit: scripts/fit_calib.py
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
mkdir -p results/calib
G=${G:-2000}
T=${T:-$(nproc)}
SEED=${SEED:-101}
run() {  # name policy per_game games
  local out=results/calib/s${SEED}_$1
  [ -s $out.tsv ] && [ "$(wc -l < $out.tsv)" -gt 2 ] && return
  ./build/messy --preset best --policy "$2" --games $4 --per-game $3 --record-switch --values --threads $T \
    --seed $SEED --out $out > $out.log 2>&1
}
run clean    "engine" 16 $G
run late     "engine:second=0.05@16000-34000,engine" 8 $G
run soft001  "soft:t=0.001@4000-30000,engine" 8 $G
run soft003  "soft:t=0.003@1000-20000,engine" 8 $G
run soft01   "soft:t=0.01@500-8000,engine" 8 $G
run soft2    "soft2:t=0.01@1000-16000,engine" 8 $G
run soft03   "soft:t=0.03@300-2000,engine" 8 $((G / 2))
run corner   "corner:eps=0.02@100-400,engine" 8 $((G / 4))
run greedy   "greedy@100-300,engine" 8 $((G / 4))
echo done > results/calib/s${SEED}.done
