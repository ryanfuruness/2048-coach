#!/bin/bash
# Dispute metric run (instance, workstream late): build/analyze with the full engine (best_v5bb settings + the given
# flags; no calibration) on the 210 expert decisions of results/disputes/expert.bin, $K processes in parallel (default
# 16) -> results/late/claims_NAME.jsonl in idx order. Metrics: scripts/exp_late_claims.py report results/late/claims_*.jsonl
# SET=judge: instead the unselected late positions of the H=1000 judges (scripts/exp_late_judge.py) ->
# results/late/judge_NAME.jsonl (+ results/late/judge.idx); with JFILES=a.tsv,b.tsv (other rollout judges) and
# JNAME=xx: results/late/xx_NAME.jsonl (+ xx.idx).
# usage: exp_late_claims.sh NAME [analyze flags, e.g. --depth 6, --budget 200000, --weights W]
cd "$(dirname "$0")/.."
N=$1; shift
K=${K:-16}
L=results/late
P=${SET:-claims}
[ $P = judge ] && P=${JNAME:-judge}
T=$L/tmp_${P}_$N
[ -s $L/${P}_$N.jsonl ] && exit 0
rm -rf $T; mkdir -p $T
if [ "$SET" = judge ]; then
  python3 scripts/exp_late_judge.py prep $T/in.txt ${JFILES:+--files $JFILES} --min-max ${JMIN:-8192} && cp $T/in.txt.idx $L/$P.idx
else
  python3 scripts/exp_late_claims.py prep $T/in.txt
fi
NIN=$(wc -l < $T/in.txt)
split -n l/$K -d -a 2 $T/in.txt $T/part.
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
for f in $T/part.??; do
  ./build/analyze --no-calib "$@" --stdin < $f > $f.out 2> $f.err &
done
wait
cat $T/part.??.out > $L/${P}_$N.jsonl
n=$(wc -l < $L/${P}_$N.jsonl)
[ "$n" = "$NIN" ] && rm -rf $T || echo "${P}_$N: only $n of $NIN lines (see $T)"
echo "[$(date '+%F %T')] ${P}_$N ($*): $n boards" >> $L/runs.log
