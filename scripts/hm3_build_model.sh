#!/bin/bash
# Workstream hm3: assemble a personal-odds model from a playout-family run (scripts/hm3_personal.sh DIR): the outcome
# model (scripts/fit_personal.py on DIR/hum_*.tsv), the skill map (review t -> key, scripts/hm_skillmap.py), the theta
# map (review theta -> key, scripts/hm_thetamap.py), the hint thresholds of v4, and the family's danger planning
# ("pplan Q DE DM": analyze's playout fallback must play the same family). MAPPING = t (pthetat lines of v4: theta ->
# t -> skill map) or theta (no pthetat lines: analyze maps theta to the key directly through pthetamap).
# usage: hm3_build_model.sh DIR OUT.txt Q DE DM MAPPING
set -e
cd "$(dirname "$0")/.."
D=$1; OUT=$2; Q=$3; DE=$4; DM=$5; MAP=$6
BASE=results/hm3/personal_v4_baseline.txt
python3 scripts/fit_personal.py $OUT $D/hum_*.tsv > $OUT.fit.out
python3 scripts/hm_skillmap.py --dir $D/rev --append $OUT > $OUT.skillmap.out
python3 scripts/hm_thetamap.py --dir $D/rev --append $OUT > $OUT.thetamap.out
grep '^phint ' $BASE >> $OUT
[ "$MAP" = t ] && grep '^pthetat ' $BASE >> $OUT
case $Q in auto) R="0.035 0.012";; auto2) R="0.02 0.01";; auto3) R="0.02 0.015";; hybrid) R="0.015 0.012";; *) R="";; esac
[ -n "$R" ] && echo "pplan $R $DE $DM" >> $OUT || echo "pplan 1e9 1e9 $DE $DM # constant q $Q" >> $OUT
grep -c '^personal ' $OUT
