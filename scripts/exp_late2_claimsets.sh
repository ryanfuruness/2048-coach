#!/bin/bash
# Workstream late2: claims of a candidate on late's three claim sets (scripts/exp_late_claims.sh: the 210 expert
# disputes/controls, the unselected late judge positions, cal6's 400-position expert judge jx), K processes each, run
# one set after another. usage: exp_late2_claimsets.sh NAME [analyze flags]
cd "$(dirname "$0")/.."
N=$1; shift
K=${K:-16} scripts/exp_late_claims.sh $N "$@"
SET=judge K=${K:-16} scripts/exp_late_claims.sh $N "$@"
SET=judge JNAME=jx JMIN=0 JFILES=$(ls results/late/jx/xexpert_*.tsv | paste -sd,) K=${K:-16} scripts/exp_late_claims.sh $N "$@"
echo "[$(date '+%F %T')] claimsets $N done" >> results/late2/runs.log
