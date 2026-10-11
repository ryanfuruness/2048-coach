#!/bin/bash
# Workstream mx queue 3 (on the instance, in ~/2048_mx): macroxue (depth 4) from the first 500 boards of our
# 32768-phase test (weights/pool32k.bin, the moment the 32768 formed in our engine's games) to game over.
cd ~/2048_mx
R=results/mx
until [ -f $R/queue2.done ]; do sleep 30; done
scripts/mx_run.sh $R/pool32k500_d4.tasks $R/pool32k500_d4.out 32
echo done > $R/queue3.done
