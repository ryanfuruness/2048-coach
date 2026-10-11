#!/bin/bash
# Workstream mx queue 4 (on the instance, in ~/2048_mx): the 16384-phase test at depth 4 again with the final boards
# (which formation does macroxue build from our starts?), then the 32768-phase test at depth 6.
cd ~/2048_mx
R=results/mx
scripts/mx_run.sh $R/pool700_d4.tasks $R/pool700_d4b.out 32 --stop-sum 36864
scripts/mx_run.sh $R/pool32k500_d6.tasks $R/pool32k500_d6.out 32
echo done > $R/queue4.done
