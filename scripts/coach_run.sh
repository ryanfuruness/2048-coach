#!/bin/bash
# Coach test runs (instance ~/2048_coach, 16 threads; inputs from scripts/coach_select.py in results/coach/):
#   advice per stage group (S1 with the second milestone), then mode first ("at your level") on the positions before
#   the chosen mistakes and on ordinary positions. Progress in results/coach/run.log; results/coach/done at the end.
cd "$(dirname "$0")/.."
OUT=results/coach
mkdir -p $OUT
TS=${TS:-0.003,0.01,0.03,0.1}
CONDS=${CONDS:-alone,engine,guard:0.02,guard:0.05,guard:0.15,guard:0.4,guard:0.05:c0.5,crit:0.01,crit:0.03,crit:0.1,stakes:0.1,stakes:0.3}
TH=${TH:-16}
run() {
  local name=$1; shift
  echo "$(date -u '+%F %H:%M:%S') start $name" >> $OUT/run.log
  "$@" 2>> $OUT/run.log
  echo "$(date -u '+%F %H:%M:%S') end $name (exit $?)" >> $OUT/run.log
}
B="build/coach --preset best-notables --threads $TH"
run advice_S1 $B --mode advice --in $OUT/starts_S1.tsv --t $TS --conds $CONDS --playouts 64 --second --out $OUT/advice_S1.tsv
run first_before $B --mode first --in $OUT/before.tsv --t $TS --playouts 64 --out $OUT/first_before.tsv
run advice_S2 $B --mode advice --in $OUT/starts_S2.tsv --t $TS --conds $CONDS --playouts 48 --out $OUT/advice_S2.tsv
run first_pool $B --mode first --in $OUT/firstpool.tsv --t $TS --playouts 64 --out $OUT/first_pool.tsv
run advice_S3 $B --mode advice --in $OUT/starts_S3.tsv --t $TS --conds $CONDS --playouts 24 --out $OUT/advice_S3.tsv
touch $OUT/done
