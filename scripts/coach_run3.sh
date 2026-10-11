#!/bin/bash
# Coach test, reordered queue (replaces the rest of coach_run.sh after its S1 advice run): S2 advice, hint budgets
# (at most 1 / 3 hints per playout) on S1 + S2, "at your level" (mode first) on the positions before the mistakes and
# on ordinary positions, a more structured human model (--structured 0.5) on S1 + S2, S3 advice last (longest).
cd "$(dirname "$0")/.."
OUT=results/coach
# the S1 advice run (started by coach_run.sh) writes "done" to run.log when it finishes
until [ "$(tail -1 $OUT/run.log)" = "done" ]; do sleep 30; done
echo "$(date -u '+%F %H:%M:%S') end advice_S1 (coach_run3 took over)" >> $OUT/run.log
TS=0.003,0.01,0.03,0.1
CONDS=alone,engine,guard:0.02,guard:0.05,guard:0.15,guard:0.4,guard:0.05:c0.5,crit:0.01,crit:0.03,crit:0.1,stakes:0.1,stakes:0.3
BUD=alone,engine,guard:0.05:k1,guard:0.05:k3,guard:0.15:k1,guard:0.15:k3,crit:0.03:k1,crit:0.03:k3,stakes:0.3:k1,stakes:0.3:k3
STR=alone,engine,guard:0.05,guard:0.15,guard:0.4,crit:0.03,crit:0.1,stakes:0.3
TH=${TH:-16}
run() {
  local name=$1; shift
  echo "$(date -u '+%F %H:%M:%S') start $name" >> $OUT/run.log
  "$@" 2>> $OUT/run.log
  echo "$(date -u '+%F %H:%M:%S') end $name (exit $?)" >> $OUT/run.log
}
B="build/coach --preset best-notables --threads $TH"
run advice_S2 $B --mode advice --in $OUT/starts_S2.tsv --t $TS --conds $CONDS --playouts 48 --out $OUT/advice_S2.tsv
for g in S1 S2; do
  run budget_$g $B --mode advice --in $OUT/starts_$g.tsv --t 0.03,0.1 --conds $BUD --playouts 48 --out $OUT/budget_$g.tsv
done
run first_before $B --mode first --in $OUT/before.tsv --t $TS --playouts 64 --out $OUT/first_before.tsv
run first_pool $B --mode first --in $OUT/firstpool.tsv --t $TS --playouts 64 --out $OUT/first_pool.tsv
for g in S1 S2; do
  run struct_$g $B --mode advice --in $OUT/starts_$g.tsv --t 0.1,0.3 --structured 0.5 --conds $STR --playouts 48 --out $OUT/struct_$g.tsv
done
run advice_S3 $B --mode advice --in $OUT/starts_S3.tsv --t $TS --conds $CONDS --playouts 24 --out $OUT/advice_S3.tsv
touch $OUT/done
