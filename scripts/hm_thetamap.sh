#!/bin/bash
# Theta map of the personal model (workstream hm2): every game of the human-model players of each personal-model key
# (results/hm/skillmap2: 200 games per key, scripts/hm_personal.sh) reviewed by build/analyze, which fits the player's
# skill theta under the human move model per phase (src/human.h); scripts/hm_thetamap.py turns the fits into the
# "pthetamap" lines. Runs on the instance in ~/2048_hm2 (data/skillmap2 pushed there); P parallel reviews.
#   usage: scripts/hm_thetamap.sh [P]
cd "$(dirname "$0")/.."
P=${1:-40}
OUT=results/hm2/thetamap
mkdir -p $OUT
ls data/skillmap2/g_*.txt | xargs -P $P -I{} sh -c \
  'f={}; b=$(basename $f); [ -s results/hm2/thetamap/$b.json ] || ./build/analyze --preset best-notables --review $f --json 2>/dev/null | tail -1 > results/hm2/thetamap/$b.json'
touch $OUT/done
