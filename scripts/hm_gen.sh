#!/bin/bash
# Human move model (workstream hm): generative check of a policy - fresh games with the board trace, then board
# statistics by stage and outcome rates (scripts/hm_genstats.py). usage: hm_gen.sh LABEL "POLICY" [GAMES] [THREADS]
cd "$(dirname "$0")/.."
L=$1; POL=$2; G=${3:-120}; T=${4:-6}
mkdir -p results/hm/gen
./build_hm/messy --preset best-notables --human-model ${HMODEL:-results/hm/human_model_v2.txt} --policy "$POL" \
  --games $G --per-game 1 --threads $T --seed ${SEED:-7} --out results/hm/gen/$L --trace results/hm/gen/$L.trace \
  > results/hm/gen/$L.log 2>&1
python3 scripts/hm_genstats.py "$L" results/hm/gen/$L.tsv results/hm/gen/$L.trace
