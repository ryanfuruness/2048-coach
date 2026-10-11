#!/bin/bash
# Claims on mx's 300 random expert positions (unselected; results/pdf/random_in.txt, ids random_in.ids) for one engine
# config: build/analyze --no-calib FLAGS --stdin, K processes -> results/pdf/rclaims_NAME.jsonl (input order).
# usage: pdf_claims_random.sh NAME [analyze flags]
cd "$(dirname "$0")/.."
N=$1; shift
K=${K:-8}
L=results/pdf
T=$L/tmp_rclaims_$N
[ -s $L/rclaims_$N.jsonl ] && exit 0
rm -rf $T; mkdir -p $T
split -n l/$K -d -a 2 $L/random_in.txt $T/part.
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
for f in $T/part.??; do ./build/analyze --no-calib "$@" --stdin < $f > $f.out 2> $f.err & done
wait
cat $T/part.??.out > $L/rclaims_$N.jsonl
n=$(wc -l < $L/rclaims_$N.jsonl)
[ "$n" = 300 ] && rm -rf $T || echo "rclaims_$N: only $n lines"
