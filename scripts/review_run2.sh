#!/bin/bash
# Workstream review, pass 2: the same reviews with the stretch's fitted human-model skill (--skill), so that every
# per-move line carries find_prob / error_risk / hint. usage (in ~/2048_review): scripts/review_run2.sh [P]
P=${1:-40}
ulimit -s unlimited
mkdir -p results/review/rev2
while IFS=$'\t' read -r id sk; do echo "$id $sk"; done < results/review/skills.tsv | xargs -P $P -L 1 sh -c \
  './build/analyze --preset best --weights weights/best_v6b.w --calib data/calib/model.txt \
    --personal-model data/calib/personal.txt --skill $1 --review results/review/stretches/$0.txt --json \
    > results/review/rev2/$0.jsonl 2> results/review/rev2/$0.err'
echo done > results/review/rev2/done
