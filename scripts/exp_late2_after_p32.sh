#!/bin/bash
# Workstream late2: once the p32 test of v6c has finished (its 45 threads free), run (1) the block-table check (one ph16
# seed of v6c with --block-tables weights/pdf --block-min 0.5, paired with the plain v6c seed-999 run) on 30 threads and
# (2) the claims of v6b and v6c on late's three claim sets (16 processes).
cd "$(dirname "$0")/.."
until grep -q "=== " results/late2/p32_s1o3_v20.log 2>/dev/null; do sleep 30; done
(SEEDS=999 THREADS=30 scripts/exp_late2_phase.sh ph16 s1o3_v20_blk weights/late2/v6b_s1o_3.w --leaf-view-max-sum 20480 \
   --block-tables weights/pdf --block-min 0.5 > results/late2/ph16_blk.out 2>&1
 python3 scripts/exp_late_paired.py ph16 s1o3_v20_blk s1o3_v20 results/late2 >> results/late2/eval.log
 echo "block table moves (v6c + tables, seed 999): $(grep 'block table moves' results/late2/ph16_s1o3_v20_blk_s999.log)" >> results/late2/eval.log) &
(scripts/exp_late2_claimsets.sh v6b --weights weights/best_v6b.w
 scripts/exp_late2_claimsets.sh v6c --weights weights/late2/v6b_s1o_3.w --leaf-view-max-sum 20480) &
wait
echo "[$(date '+%F %T')] after_p32 done" >> results/late2/runs.log
