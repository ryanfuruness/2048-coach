#!/bin/bash
# after queue 2: claims on the 300 random expert positions, 4 engine configs (8 processes each)
cd "$(dirname "$0")/.."
while ! grep -q "queue2 done" results/pdf/queue2.out 2>/dev/null; do sleep 30; done
B="--block-tables weights/pdf"
T21="--weights weights/late/v5_t21.w"
scripts/pdf_claims_random.sh base
scripts/pdf_claims_random.sh blk $B
scripts/pdf_claims_random.sh t21 $T21
scripts/pdf_claims_random.sh blk_t21 $B $T21
echo "queue3 done: $(date)"
