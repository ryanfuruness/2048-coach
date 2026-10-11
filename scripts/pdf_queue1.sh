#!/bin/bash
# Strength screen (workstream pdf), one seed (700 real 16384 starts -> sum 36864), 32 threads, after the rollouts:
#   blk       best_v5bb + block tables (snake search otherwise)
#   g4blk     + gradient search (rows, depth 4) while the root holds >= 16384, block tables first, snake tables too
#   g4blkns   the same without the snake tables
cd "$(dirname "$0")/.."
while [ ! -s results/pdf/random300_blk_h1000.tsv ]; do sleep 30; done
nohup scripts/pdf_build.sh 32 > results/pdf/build2.log 2>&1 < /dev/null   # adds the r3/r4 tables (skips the others)
export SEEDS=999 THREADS=32
B="--block-tables weights/pdf"
scripts/pdf_phase.sh ph16 blk weights/best_v5.w 3,4,8,8,4 $B
scripts/pdf_phase.sh ph16 g4blk weights/best_v5.w 3,4,8,8,4 $B --gradient 1 14 1000000 4 0.002
scripts/pdf_phase.sh ph16 g4blkns weights/best_v5.w 3,4,8,8,4 $B --gradient 1 14 1000000 4 0.002 --endgame 0 --lt-min 2
echo "queue1 done: $(date)"
