#!/bin/bash
# Is it safe to add the block tables (p >= 0.5) to late's final engine v6b? Phase tests paired with late's v6b runs
# (same seeds and starts): ph16 3 seeds, p32 (1878 starts). 64 threads (the coordinator reports idle cores).
cd "$(dirname "$0")/.."
export THREADS=64 SEEDS="999 1001 1002"
B="--block-tables weights/pdf --block-min 0.5"
scripts/pdf_phase.sh ph16 v6b_blk weights/late/v6_bo_2.w 3,4,8,8,4 $B
scripts/pdf_phase.sh p32 v6b_blk weights/late/v6_bo_2.w 3,4,8,8,4 $B
echo "queue5 done: $(date)"
