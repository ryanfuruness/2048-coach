#!/bin/bash
# Workstream late: how much the safe board mapping / views change the analysis of real 32768+ expert positions
# (results/late/mapsafe_in.txt: 500 random curated positions with a 65536+, 300 with a 32768, as tile values).
# usage: exp_late_mapsafe.sh NAME [analyze flags]  -> results/late/mapsafe_NAME.jsonl (16 processes)
cd "$(dirname "$0")/.."
N=$1; shift
L=results/late; T=$L/tmp_mapsafe_$N
[ -s $L/mapsafe_$N.jsonl ] && exit 0
rm -rf $T; mkdir -p $T
split -n l/16 -d -a 2 $L/mapsafe_in.txt $T/part.
ulimit -s unlimited; export MALLOC_ARENA_MAX=2
for f in $T/part.??; do ./build/analyze --no-calib "$@" --stdin < $f > $f.out 2> $f.err & done
wait
cat $T/part.??.out > $L/mapsafe_$N.jsonl && rm -rf $T
