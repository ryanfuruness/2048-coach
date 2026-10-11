#!/bin/bash
# Greedy (1-ply) strength of a network on the GPU, from the initial position or a pool.
# usage: eval_gpu.sh WEIGHTS STAGES EPISODES [POOL]
# Games run to the end (no stage stops); prints one summary line. Uses 4-bit boards,
# where a 65536 is stored as rank 15, so the 32768 column counts 32768-or-better.
cd "$(dirname "$0")/.."
W=$1 ST=$2 N=$3 POOL=$4
./build/gpu_train --load "$W" ${ST:+--stages "$ST"} --no-learn ${POOL:+--pool "$POOL" --pool-last 1000000} \
  --episodes "$N" --log "$N" --games 32768 --seed 99 | grep "games  avg"
