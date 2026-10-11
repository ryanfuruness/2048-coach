#!/bin/bash
# Dispute metric with the block tables (workstream pdf; same pipeline as scripts/exp_late_claims.sh, own output dir):
# build/analyze (full engine + the given flags, no calibration) on the 210 expert decisions of results/disputes/expert.bin
# -> results/pdf/claims_NAME.jsonl in idx order. Metrics: scripts/exp_late_claims.py report results/pdf/claims_*.jsonl
# usage: pdf_claims.sh NAME [analyze flags, e.g. --block-tables weights/pdf --weights weights/late/v5_t21.w]
cd "$(dirname "$0")/.."
N=$1; shift
K=${K:-16}
L=results/pdf
T=$L/tmp_claims_$N
[ -s $L/claims_$N.jsonl ] && exit 0
rm -rf $T; mkdir -p $T
python3 scripts/exp_late_claims.py prep $T/in.txt
NIN=$(wc -l < $T/in.txt)
split -n l/$K -d -a 2 $T/in.txt $T/part.
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
for f in $T/part.??; do
  ./build/analyze --no-calib "$@" --stdin < $f > $f.out 2> $f.err &
done
wait
cat $T/part.??.out > $L/claims_$N.jsonl
n=$(wc -l < $L/claims_$N.jsonl)
[ "$n" = "$NIN" ] && rm -rf $T || echo "claims_$N: only $n of $NIN lines (see $T)"
echo "[$(date '+%F %T')] claims_$N ($*): $n boards" >> $L/runs.log
