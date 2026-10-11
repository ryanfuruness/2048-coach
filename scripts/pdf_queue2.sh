#!/bin/bash
# Workstream pdf, queue 2 (32 threads): (1) death within 1000 moves from mx's 300 random expert positions with the block
# tables + block lock; (2) the 16384-phase screen (seed 999) with the block lock (+ tables), and the tables at p >= 0.5.
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
[ -s results/pdf/random300_blklock_h1000.tsv ] || ./build/rollout --preset best --block-tables weights/pdf --block-lock \
  --pool results/mx/random300.bin --playouts 32 --horizon 1000 --moves engine --threads 32 \
  --out results/pdf/random300_blklock_h1000.tsv > results/pdf/random300_blklock_h1000.log 2>&1
export SEEDS=999 THREADS=32
B="--block-tables weights/pdf"
scripts/pdf_phase.sh ph16 blklock weights/best_v5.w 3,4,8,8,4 $B --block-lock
scripts/pdf_phase.sh ph16 blkmin5 weights/best_v5.w 3,4,8,8,4 $B --block-min 0.5
echo "queue2 done: $(date)"
