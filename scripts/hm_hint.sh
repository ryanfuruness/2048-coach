#!/bin/bash
# Hint threshold (workstream hm2): the coach test with human-model players (keys 0.012 / 0.003 / 0.00135) from the
# coach's real start positions, comparing analyze's hint (condition risk:R - the position's error risk at the
# player's level >= R, the player's theta from the personal model's theta map of its key) with warnings (guard:0.15)
# and the human-model expected-loss hint of workstream hm (crit:0.1). Runs on the instance in ~/2048_hm2.
#   usage: scripts/hm_hint.sh [THREADS] [STRATA]
cd "$(dirname "$0")/.."
TH=${1:-36}
STRATA=${2:-"S1 S2"}
OUT=results/hm2/coach
mkdir -p $OUT
TS=${TS:-0.012,0.003,0.00135}
CONDS=${CONDS:-alone,engine,guard:0.15,crit:0.1,risk:0.005,risk:0.01,risk:0.02,risk:0.03,risk:0.05}
PREFIX=${PREFIX:-advice}
for S in $STRATA; do
  build/coach --preset best-notables --threads $TH --human --personal-model data/personal_theta_candidate.txt --calib data/model.txt \
    --mode advice --in data/starts_$S.tsv --t $TS --conds $CONDS --playouts 32 --out $OUT/${PREFIX}_$S.tsv > $OUT/${PREFIX}_$S.log 2>&1
done
touch $OUT/done_${PREFIX}_$(echo $STRATA | tr ' ' '_')
