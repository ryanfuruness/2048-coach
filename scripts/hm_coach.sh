#!/bin/bash
# Coach test slice with the human move model as the player (workstream hm): do the coach's conclusions (warnings beat
# hints; 1-2 warnings per 100 moves close most of the gap to the engine) hold for a more human-like player?
# Players: human model at personal-model keys (skill s = -ln(100 k)); conditions as scripts/coach_run.sh (subset).
cd "$(dirname "$0")/.."
OUT=results/hm/coach
mkdir -p $OUT
TS=${TS:-0.012,0.003,0.00135}
CONDS=${CONDS:-alone,engine,guard:0.05,guard:0.15,crit:0.1,stakes:0.3}
TH=${TH:-24}
B="build/coach --preset best-notables --threads $TH --human --human-model results/hm/human_model_v2.txt"
$B --mode advice --in results/coach/starts_S1.tsv --t $TS --conds $CONDS --playouts 32 --out $OUT/advice_S1.tsv > $OUT/S1.log 2>&1
$B --mode advice --in results/coach/starts_S2.tsv --t $TS --conds $CONDS --playouts 32 --out $OUT/advice_S2.tsv > $OUT/S2.log 2>&1
touch $OUT/done
