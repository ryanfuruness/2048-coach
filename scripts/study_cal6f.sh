#!/bin/bash
# cal6 queue E: once the judge1200 runner of the 16384+ positions is done, the last chunks of the old-dispute re-judge
# (results/cal6/jold) in reverse order, so that queue A (ascending) and this queue meet in the middle.
cd "$(dirname "$0")/.."
until [ -f results/cal6/j1200/judge1200_800_1200.done ]; do sleep 30; done
for s in 180 150 120 90; do
  [ -s results/cal6/jold/expert_$(printf %05d $s).tsv ] || [ -f results/cal6/jold/expert_$(printf %05d $s).tsv.tmp ] || \
    scripts/judge_cal6.sh results/disputes/expert.bin results/cal6/jold $s $((s + 30 > 210 ? 210 : s + 30)) 30 16
done
echo done > results/cal6/queueE.done
