#!/bin/bash
# Which human skill does a softmax player of temperature t look like? Games of soft:t players (the personal-odds skill
# model: softmax over 1-ply network values) reviewed like a human game (build/analyze --review: the skill temperature
# fitted on search values, per phase) -> the map from a player's fitted skill to the soft player that plays like them.
# usage: calib_softmap.sh [GAMES_PER_T] [THREADS]   (ENGINE="engine flags" for another network)
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
G=${1:-24}; T=${2:-4}
D=results/cal6/softmap
mkdir -p $D
for t in 0.003 0.01 0.03 0.1; do
  [ -s $D/trace_$t.txt ] || ./build/messy --preset best-notables $ENGINE --policy "soft:t=$t" --games $G --per-game 0 \
    --threads $T --seed 77 --trace $D/trace_$t.txt --out $D/games_$t > $D/games_$t.log 2>&1
  # one file per game, then the review of each (JSON summary line)
  awk -v p="$D/g_${t}_" 'BEGIN{n=0} /^$/{n++; next} {print > (p n ".txt")}' $D/trace_$t.txt
  ls $D/g_${t}_*.txt | xargs -P $T -I{} sh -c './build/analyze --preset best-notables $ENGINE --review {} --json 2>/dev/null | tail -1 > {}.json'
done
echo done > $D/done
