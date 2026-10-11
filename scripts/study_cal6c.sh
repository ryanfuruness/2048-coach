#!/bin/bash
# cal6 queue B (replaces study_cal6.sh truth -> lapse once the truth runs are going): after the r15 truth, the old
# 150 expert disputes + 60 controls again at H=1000 (horizon check against their H=300 judge), then the lapse study.
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
T=${T:-16}
until [ -s results/cal6/truth/truth_r15.tsv ]; do sleep 30; done
scripts/judge_cal6.sh results/disputes/expert.bin results/cal6/jold 0 210 30 $T
scripts/study_cal6.sh lapse
