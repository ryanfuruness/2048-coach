#!/bin/bash
# Seed farm for free ensembles (scripts/avg_stages.py): more 4M-episode GPU seeds of the second half (s6 recipe) and of
# stage B (b4s2 recipe, bootstrapping from s6 at 28672), stored as single-stage files to save disk.
cd "$(dirname "$0")/.."
W=weights/expens
L=results/expens
mkdir -p $W $L
while ps -eo args | grep -q "^/bin/bash scripts/exp_tcmean.sh"; do sleep 30; done
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
SH="--stages sum:36864 --train-stage 0 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 500000 \
  --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 \
  --pool weights/v11c/pool2mix.bin --pool-last $NPOOL --episodes 4000000"
ST5="sum:20480/14,24576,28672,36864"
SB="--stages $ST5 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 \
  --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --skip-lower --train-stage 2 \
  --pool weights/expsplit/pool24.bin --pool-last 1000000 --episodes 4000000"
[ -f $W/startB.w ] || python3 scripts/neutralize.py weights/best_v5.w $W/startB.w --fresh 2 --value 5000 > /dev/null
for sd in ${SEEDS:-21 22 23 24 25 26 27 28}; do
  if [ ! -f $W/sh_s$sd.w ]; then
    echo "[$(date '+%F %T')] second half seed $sd" >> $L/log
    ./build/gpu_train --load weights/expcpu/start.w $SH --seed $sd --save $W/tmp_sh.w > $L/sh_s$sd.log 2>&1 || exit 1
    python3 scripts/select_stages.py $W/tmp_sh.w $W/sh_s$sd.w 0 > /dev/null && rm -f $W/tmp_sh.w
    grep "games  avg" $L/sh_s$sd.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  sh_s$sd /" >> $L/log
  fi
  if [ ! -f $W/b_s$sd.w ]; then
    echo "[$(date '+%F %T')] stage B seed $sd" >> $L/log
    ./build/gpu_train --load $W/startB.w $SB --seed $sd --save $W/tmp_b.w > $L/b_s$sd.log 2>&1 || exit 1
    python3 scripts/select_stages.py $W/tmp_b.w $W/b_s$sd.w 2 > /dev/null && rm -f $W/tmp_b.w
    grep "games  avg" $L/b_s$sd.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  b_s$sd /" >> $L/log
  fi
done
echo "[$(date '+%F %T')] seed farm done" >> $L/log
