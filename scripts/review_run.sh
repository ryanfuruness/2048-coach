#!/bin/bash
# Workstream review: run build/analyze --review on every selected stretch (instance, ~/2048_review), P in parallel.
# usage (in ~/2048_review): scripts/review_run.sh [P]
P=${1:-40}
ulimit -s unlimited
mkdir -p results/review/rev
ls results/review/stretches/*.txt | xargs -P $P -I{} sh -c 'id=$(basename {} .txt); \
  ./build/analyze --preset best --weights weights/best_v6b.w --calib data/calib/model.txt \
    --personal-model data/calib/personal.txt --review {} --json > results/review/rev/$id.jsonl 2> results/review/rev/$id.err'
echo done > results/review/rev/done
