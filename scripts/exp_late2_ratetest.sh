#!/bin/bash
# Workstream late2: does plain TD at rate ALPHA degrade the TC-trained s0cpu? 40k episodes, in-training 1-ply stats per
# 10k window. usage: exp_late2_ratetest.sh ALPHA [THREADS]
cd "$(dirname "$0")/.."
a=$1 t=${2:-8}
ulimit -s unlimited; export MALLOC_ARENA_MAX=2
./build/train --load weights/tup/s0cpu.w --stages sum:20480 --train-stage 0 --stop-at-boundary --lambda 0.5 \
  --threads $t --episodes 40000 --alpha $a --log 10000 --save /tmp/rt_$a.w > results/late2/rate_$a.log 2>&1
rm -f /tmp/rt_$a.w
echo done >> results/late2/rate_$a.log
