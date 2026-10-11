#!/bin/bash
# Personal odds v3 data (workstream hm): games of the human move model (src/human.h) from fresh boards, recorded at
# tile-sum checkpoints with the engine's analysis value (as study_personal.sh does for soft:t players), and games with
# the board trace for the skill map (each game reviewed like a human game: build/analyze --review).
# Skill family: key t = 0.01 * exp(-s) (a temperature-like number, smaller = stronger): value skill theta = s,
# structure skill theta_s = min(s, 0.4) (beyond 0.4 only the value judgement sharpens: more structure weight makes
# the generated play rigid and weaker; see results/hm/report.txt).
# usage: hm_personal.sh [THREADS_PER_SKILL=8] [GAMES=1000] [REVIEW_GAMES=48]
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
T=${1:-8}; G=${2:-1000}; GR=${3:-48}
KEYS=${KEYS:-"0.018 0.012 0.008 0.0055 0.003 0.00135 0.0005"}
HMODEL=${HMODEL:-results/hm/human_model_v2.txt}
CP=16,32,64,128,256,384,512,768,1024,1536,2048,3072,4096,6144,8192,10240,12288,14336,16384,20480,24576,28672
D=results/hm/personal; M=${SKILLMAP_DIR:-results/hm/skillmap}
mkdir -p $D $M
pol() { python3 -c "import math; s=-math.log(100*$1); print(f'human:th={s:.4f}:ths={min(s,0.4):.4f}')"; }
for k in $KEYS; do
  out=$D/hum_$k
  [ -s $out.tsv ] || ./build/messy --preset best-notables --human-model $HMODEL --policy "$(pol $k)" --games $G \
    --per-game 0 --checkpoints $CP --values --threads $T --seed 501 --out $out > $out.log 2>&1 &
done
wait
for k in $KEYS; do
  [ -s $M/trace_$k.txt ] || ./build/messy --preset best-notables --human-model $HMODEL --policy "$(pol $k)" \
    --games $GR --per-game 0 --threads $T --seed 77 --trace $M/trace_$k.txt --out $M/games_$k > $M/games_$k.log 2>&1 &
done
wait
for k in $KEYS; do
  awk -v p="$M/g_${k}_" 'BEGIN{n=0} /^$/{n++; next} {print > (p n ".txt")}' $M/trace_$k.txt
done
ls $M/g_*.txt | xargs -P $((T * 7)) -I{} sh -c '[ -s {}.json ] || ./build/analyze --preset best-notables --review {} --json 2>/dev/null | tail -1 > {}.json'
echo done > $D/done
