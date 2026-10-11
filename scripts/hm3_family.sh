#!/bin/bash
# Workstream hm3: playout families with care in danger. For each key t (value skill s = -ln(100 t), structure skill
# min(s, 0.4), as personal v3/v4) and danger-planning probability Q (on boards with <= DE empty cells the engine's move
# is played with probability Q): GAMES fresh games with the board trace (outcomes + stretch statistics), and the
# first REV of them reviewed by build/analyze (skill readings: softmax t and the human-model theta per phase).
# usage: hm3_family.sh OUTDIR "KEYS" "QS" [DE=2] [GAMES=200] [REV=60] [THREADS=8] [PAR=6]
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
OUT=$1; KEYS=$2; QS=$3; DE=${4:-2}; G=${5:-200}; REV=${6:-60}; T=${7:-8}; PAR=${8:-6}
HMODEL=${HMODEL:-results/hm/human_model_v2.txt}
mkdir -p $OUT
pol() { python3 -c "import math; s=-math.log(100*$1); print(f'human:th={s:.4f}:ths={min(s,0.4):.4f}:dq=$2:de=$DE:dm=${DM:-1}')"; }
jobs=()
for k in $KEYS; do for q in $QS; do jobs+=("$k $q"); done; done
run_one() {
  k=$1; q=$2; L=$OUT/k${k}_q${q}
  [ -s $L.tsv ] || ./build/messy --preset best-notables --human-model $HMODEL --policy "$(pol $k $q)" --games $G \
    --per-game 1 --threads $T --seed 909 --trace $L.trace --out $L > $L.log 2>&1
  mkdir -p $L.rev
  awk -v p="$L.rev/g_" -v m=$REV 'BEGIN{n=0} /^$/{n++; next} n<m {print > (p n ".txt")}' $L.trace
}
export -f run_one pol; export OUT G T DE HMODEL REV DM
printf '%s\n' "${jobs[@]}" | xargs -P $PAR -L 1 bash -c 'run_one $0 $1'
ls $OUT/*.rev/g_*.txt | xargs -P $((T * PAR)) -I{} sh -c '[ -s {}.json ] || ./build/analyze --preset best-notables --skill 0 --review {} --json 2>/dev/null | tail -1 > {}.json'
echo done > $OUT/done
