#!/bin/bash
# Coach test, replication on fresh positions (results/coach/rep2, scripts/coach_select.py --seed 2 --exclude set 1):
# the main advice design for S1, S2, S3 after the first queue (coach_run3.sh) is done.
cd "$(dirname "$0")/.."
OUT=results/coach/rep2
until [ -f results/coach/done ]; do sleep 30; done
TS=0.003,0.01,0.03,0.1
CONDS=alone,engine,guard:0.02,guard:0.05,guard:0.15,guard:0.4,guard:0.05:c0.5,crit:0.01,crit:0.03,crit:0.1,stakes:0.1,stakes:0.3
TH=${TH:-16}
run() {
  local name=$1; shift
  echo "$(date -u '+%F %H:%M:%S') start $name" >> $OUT/run.log
  "$@" 2>> $OUT/run.log
  echo "$(date -u '+%F %H:%M:%S') end $name (exit $?)" >> $OUT/run.log
}
B="build/coach --preset best-notables --threads $TH --seed 2"
run advice_S1 $B --mode advice --in $OUT/starts_S1.tsv --t $TS --conds $CONDS --playouts 64 --second --out $OUT/advice_S1.tsv
run advice_S2 $B --mode advice --in $OUT/starts_S2.tsv --t $TS --conds $CONDS --playouts 48 --out $OUT/advice_S2.tsv
run advice_S3 $B --mode advice --in $OUT/starts_S3.tsv --t $TS --conds $CONDS --playouts 24 --out $OUT/advice_S3.tsv
touch $OUT/done
