#!/bin/bash
# Data for a fast personal-odds model: games of softmax players (soft:t, the skill model) recorded at tile-sum
# checkpoints with the engine's analysis value; each position's outcome is the SAME player's outcome (final max).
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
G=${G:-1000}; T=${T:-4}
CP=16,32,64,128,256,384,512,768,1024,1536,2048,3072,4096,6144,8192,10240,12288,14336,16384,20480,24576,28672
mkdir -p results/personal
until grep -q "videos" results/human/run3.out 2>/dev/null; do sleep 30; done  # one extra engine process at a time (RAM)
for t in 0.003 0.01 0.03 0.1; do
  out=results/personal/soft_$t
  [ -s $out.tsv ] && continue
  ./build/messy --preset best-notables --policy "soft:t=$t" --games $G --per-game 0 --checkpoints $CP --values \
    --threads $T --seed 501 --out $out > $out.log 2>&1
done
echo done > results/personal/done
