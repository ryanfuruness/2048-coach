#!/bin/bash
# Instance part of the scorecard (scripts/scorecard.sh): runs build/analyze with the full engine (exact tables) and
# the configuration's model on the scorecard's fixed inputs. Run in ~/2048_score.
# usage: scorecard_remote.sh NAME "ENGINE FLAGS" MODEL PERSONAL
NAME=$1; E=$2; M=$3; P=$4
D=results/scorecard/$NAME; I=results/scorecard/inputs
mkdir -p $D; rm -f $D/remote.done
ulimit -s unlimited
A="./build/analyze --preset best $E --calib $M --personal-model $P --stdin"
echo "start $(date -u)  engine: $A" > $D/remote.log
split -n l/4 -d $I/judge_in.txt $D/judge_in.
for k in 0 1 2 3; do ($A < $D/judge_in.0$k > $D/judge.0$k.jsonl 2> $D/judge.0$k.err) & done
($A < $I/odds_in.txt > $D/odds.jsonl 2> $D/odds.err) &
($A < $I/disputes_in.txt > $D/disputes.jsonl 2> $D/disputes.err) &
# latency with the exact tables: real positions, then the fuzz boards (one process each; invariants checked too)
(python3 scripts/fuzz_check.py $I/latency_real.jsonl $D/tables_real --analyze ./build/analyze --preset best \
   --extra "$E --calib $M --personal-model $P" > /dev/null 2> $D/tables_real.err;
 python3 scripts/fuzz_check.py $I/fuzz_boards.jsonl $D/tables_fuzz --analyze ./build/analyze --preset best \
   --extra "$E --calib $M --personal-model $P" > /dev/null 2> $D/tables_fuzz.err) &
wait
cat $D/judge.0?.jsonl > $D/judge.jsonl
rm -f $D/judge_in.0?
echo "end $(date -u): judge $(wc -l < $D/judge.jsonl), odds $(wc -l < $D/odds.jsonl), disputes $(wc -l < $D/disputes.jsonl)" >> $D/remote.log
echo done > $D/remote.done
