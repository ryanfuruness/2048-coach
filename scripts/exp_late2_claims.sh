#!/bin/bash
# Workstream late2: claims of a candidate engine (build/analyze, preset best + flags, no calibration) on the early/mid
# judge positions (scripts/exp_late2_judge.py prep), K processes (default 8) -> results/late2/early_NAME.jsonl.
# usage: exp_late2_claims.sh NAME [analyze flags, e.g. --weights W]
cd "$(dirname "$0")/.."
N=$1; shift
K=${K:-8}
L=results/late2
[ -s $L/early_$N.jsonl ] && exit 0
T=$L/tmp_early_$N; rm -rf $T; mkdir -p $T
[ -f $L/early.idx ] || python3 scripts/exp_late2_judge.py prep $L/early_in.txt && cp $L/early_in.txt.idx $L/early.idx 2>/dev/null
NIN=$(wc -l < $L/early_in.txt)
split -n l/$K -d -a 2 $L/early_in.txt $T/part.
ulimit -s unlimited; export MALLOC_ARENA_MAX=2
for f in $T/part.??; do ./build/analyze --preset best --no-calib "$@" --stdin < $f > $f.out 2> $f.err & done
wait
cat $T/part.??.out > $L/early_$N.jsonl
n=$(wc -l < $L/early_$N.jsonl)
[ "$n" = "$NIN" ] && rm -rf $T || echo "early_$N: only $n of $NIN lines (see $T)"
echo "[$(date '+%F %T')] early_$N ($*): $n boards" >> $L/runs.log
