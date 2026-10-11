#!/bin/bash
# Ground truth for the odds model on tight human positions (value far below the stage's typical value): 30 positions x
# 4 copies x 30 engine playouts to 16384 (or death); compare v3 vs v4 predictions (scripts/odds_truth_report.py).
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
until [ -f results/disputes/done ]; do sleep 60; done
[ -s results/judge/tight30_16k.tsv ] || ./build/rollout --preset best --pool results/judge/tight30.bin --playouts 30 \
  --horizon 0 --stop-rank 14 --moves engine --threads 16 --out results/judge/tight30_16k.tsv > results/judge/tight30_16k.log 2>&1
echo done > results/judge/tight30.done
