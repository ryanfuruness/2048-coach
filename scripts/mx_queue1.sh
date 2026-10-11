#!/bin/bash
# Workstream mx queue 1 (on the instance, in ~/2048_mx): macroxue depth-8 analysis of the 510 positions, the
# 16384-phase test from our pool700 starts (depth 4, to tile sum 36864), playouts after the expert's and our engine's
# moves (depth 4, to the end) for the 150 disputes and the random expert positions where they differ.
cd ~/2048_mx
R=results/mx
scripts/mx_run.sh $R/eval_d8.tasks $R/eval_d8.out 32
scripts/mx_run.sh $R/pool700_d4.tasks $R/pool700_d4.out 32 --stop-sum 36864
scripts/mx_run.sh $R/play_d4_h100000.tasks $R/play_d4_h100000.out 32
scripts/mx_run.sh $R/playR_d4_h100000.tasks $R/playR_d4_h100000.out 32
echo done > $R/queue1.done
