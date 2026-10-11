#!/bin/bash
# Dispute judge: decisions where the engine claims the player lost > 10% of the value (human_disputes.py) are judged
# by rollouts with the full engine (tables included), plus control decisions where the player matched the engine.
# Confirmed = the engine's move really is better; refuted = the player's move is as good (engine misjudgment, e.g. a
# formation it does not play). Runs after the calibration part 3 (one table-loading process at a time).
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
until [ -f results/calib/s301_cleancp.done ] && [ -s results/human_ds/summary.json ]; do sleep 60; done
mkdir -p results/disputes
for grp in expert mid; do
  if [ $grp = expert ]; then MT=16384; else MT=0; fi
  [ -s results/disputes/$grp.bin ] || python3 scripts/human_disputes.py results/disputes/$grp --analysis results/human_ds/analysis.jsonl --min-loss 0.10 \
    --min-tile $MT --max 150 --control 60 > results/disputes/$grp.sel.txt
  [ -s results/disputes/${grp}_h300.tsv ] || ./build/rollout --preset best --pool results/disputes/$grp.bin \
    --playouts 32 --horizon 300 --threads 16 --out results/disputes/${grp}_h300.tsv > results/disputes/${grp}_h300.log 2>&1
  python3 scripts/dispute_report.py results/disputes/$grp.tsv results/disputes/${grp}_h300.tsv > results/disputes/${grp}_report.txt
done
echo done > results/disputes/done
