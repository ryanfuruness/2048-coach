#!/bin/bash
# Workstream hm3: personal-odds data for a playout family with care in danger (scripts/hm3_family.sh's options). For
# each key t (value skill s = -ln(100 t), structure skill min(s, 0.4), danger planning Q / DE / DM): GAMES fresh games
# recorded at tile-sum checkpoints with the engine's value (scripts/fit_personal.py input: DIR/hum_KEY.tsv) and traced;
# the first REV games reviewed by build/analyze (skill readings for the skill map and the theta map: DIR/rev/g_KEY_n.txt).
# usage: hm3_personal.sh DIR Q [DE=2] [DM=2] [GAMES=600] [REV=100] [THREADS=4] [PAR=12]
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
D=$1; Q=$2; DE=${3:-2}; DM=${4:-2}; G=${5:-600}; REV=${6:-100}; T=${7:-4}; PAR=${8:-12}
KEYS=${KEYS:-"0.05 0.035 0.025 0.018 0.015 0.012 0.01 0.008 0.0065 0.0055 0.004 0.003 0.002 0.00135 0.0005"}
HMODEL=${HMODEL:-results/hm/human_model_v2.txt}
CP=16,32,64,128,256,384,512,768,1024,1536,2048,3072,4096,6144,8192,10240,12288,14336,16384,20480,24576,28672
mkdir -p $D/rev
one() {
  k=$1
  # Q = auto: the planning probability grows with the key's strength: 0 for key >= 0.035 (novice-like players,
  # who do not repair), 1 for key <= 0.012, linear in log key between; auto2: 0 for key >= 0.02, 1 for key <= 0.01;
  # auto3: 0 for key >= 0.02, 1 for key <= 0.015
  pol=$(python3 -c "
import math
k=$k; s=-math.log(100*k); q='$Q'
lo,hi=(0.035,0.012) if q=='auto' else (0.02,0.01) if q=='auto2' else (0.02,0.015) if q=='auto3' else (None,None)
q=min(1.0,max(0.0,(math.log(lo)-math.log(k))/(math.log(lo)-math.log(hi)))) if lo else float(q)
print(f'human:th={s:.4f}:ths={min(s,0.4):.4f}:dq={q:.3f}:de=$DE:dm=$DM')")
  [ -s $D/hum_$k.tsv ] || ./build/messy --preset best-notables --human-model $HMODEL --policy "$pol" --games $G \
    --per-game 0 --checkpoints $CP --values --threads $T --seed 4242 --trace $D/trace_$k.txt --out $D/hum_$k > $D/hum_$k.log 2>&1
  awk -v p="$D/rev/g_${k}_" -v m=$REV 'BEGIN{n=0} /^$/{n++; next} n<m {print > (p n ".txt")}' $D/trace_$k.txt
}
export -f one; export D Q DE DM G REV T HMODEL CP
printf '%s\n' $KEYS | xargs -P $PAR -I{} bash -c 'one {}'
ls $D/rev/g_*.txt | xargs -P $((T * PAR)) -I{} sh -c '[ -s {}.json ] || ./build/analyze --preset best-notables --review {} --json 2>/dev/null | tail -1 > {}.json'
echo done > $D/done
