#!/bin/bash
# Workstream late: pull the instance results and regenerate the metric tables (results/late/*_report.txt).
cd "$(dirname "$0")/.."
scripts/aws/ws.sh pull late late > /dev/null
L=results/late
python3 scripts/exp_late_claims.py report $(ls $L/claims_*.jsonl) > $L/claims_report.txt
python3 scripts/exp_late_judge.py report $L/judge.idx $(ls $L/judge_*.jsonl) > $L/judge_report.txt
[ -f $L/jx.idx ] && python3 scripts/exp_late_judge.py report $L/jx.idx $(ls $L/jx_*.jsonl) --meta results/cal6/xexpert.tsv > $L/jx_report.txt
cat $L/eval.log
