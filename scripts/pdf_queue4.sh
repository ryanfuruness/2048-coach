#!/bin/bash
# after queue 3: death within 1000 moves from mx's 300 random expert positions with the block tables at p >= 0.5
cd "$(dirname "$0")/.."
while ! grep -q "queue3 done" results/pdf/queue3.out 2>/dev/null; do sleep 30; done
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
./build/rollout --preset best --block-tables weights/pdf --block-min 0.5 --pool results/mx/random300.bin --playouts 32 \
  --horizon 1000 --moves engine --threads 32 --out results/pdf/random300_blkmin5_h1000.tsv > results/pdf/random300_blkmin5_h1000.log 2>&1
echo "queue4 done: $(date)"
