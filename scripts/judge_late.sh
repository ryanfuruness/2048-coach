#!/bin/bash
# Late-game loss map: the 16384-phase lapse handovers (s201 lapse16 / lapse16b) judged with the full engine (tables)
# at H=1000, then the late map refit on all late positions. Runs after the dispute study.
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
until [ -f results/judge/tight30.done ]; do sleep 60; done
python3 scripts/select_positions.py results/judge/late.bin --where "switch == 1" results/calib/s201_lapse16.tsv \
  results/calib/s201_lapse16b.tsv > /dev/null
[ -s results/judge/late_h1000.tsv ] || ./build/rollout --preset best --pool results/judge/late.bin --playouts 32 \
  --horizon 1000 --threads 16 --out results/judge/late_h1000.tsv > results/judge/late_h1000.log 2>&1
python3 scripts/judge_report.py results/judge/late_h1000.tsv | head -3
python3 scripts/fit_lossmap.py --key lossmap_late --max-tile 2048 1000000 results/judge/late_h1000.tsv \
  $(ls results/judge/p2_*_h1000.tsv | grep -v soft0\\.) | tail -10
echo done > results/judge/late.done
