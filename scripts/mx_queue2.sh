#!/bin/bash
# Workstream mx queue 2 (on the instance, in ~/2048_mx): who plays which formation better? From the 300 random expert
# positions (tile >= 16384), 32 playouts of 1000 moves by macroxue (depth 4) and by our full engine (its own move,
# tables on); then macroxue's 16384-phase conversion at depth 6 (pool700, to tile sum 36864).
cd ~/2048_mx
R=results/mx
until [ -f $R/queue1.done ]; do sleep 30; done
scripts/mx_run.sh $R/fromR_d4.tasks $R/fromR_d4.out 32
ulimit -s unlimited; export MALLOC_ARENA_MAX=2
[ -s $R/random300_ours_h1000.tsv ] || ./build/rollout --preset best --pool $R/random300.bin --playouts 32 --horizon 1000 \
  --moves engine --threads 32 --out $R/random300_ours_h1000.tsv > $R/random300_ours_h1000.log 2>&1
python3 - <<'PY'
PY
scripts/mx_run.sh $R/pool700_d6.tasks $R/pool700_d6.out 32 --stop-sum 36864
echo done > $R/queue2.done
