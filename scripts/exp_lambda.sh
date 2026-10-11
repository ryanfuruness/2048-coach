#!/bin/bash
# Seeds share their errors (free ensembles do nothing) and TC plateaus -> the errors are systematic to the recipe. TD(lambda)
# with small lambda and a short horizon bootstraps from the network itself (TD's fixed point can sit far from the best
# approximation); more Monte-Carlo-like targets may reach a different, better function. s6 recipe (GPU, 4M, seed 6)
# with lambda 0.8 / horizon 8 and lambda 0.95 / horizon 16.
cd "$(dirname "$0")/.."
W=weights/explam
L=results/explam
mkdir -p $W $L
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
COMMON="--stages sum:36864 --train-stage 0 --stop-at-boundary --tc --alpha 1.0 --games 32768 --log 500000 --corner-lock 14 \
  --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool weights/v11c/pool2mix.bin \
  --pool-last $NPOOL --episodes 4000000 --seed 6"
for cfg in "l80 0.8 8" "l95 0.95 16"; do
  set -- $cfg
  [ -f $W/$1.w ] && continue
  echo "[$(date '+%F %T')] $1: lambda $2 horizon $3" >> $L/log
  ./build/gpu_train --load weights/expcpu/start.w $COMMON --lambda $2 --horizon $3 --save $W/$1.w.part > $L/$1.log 2>&1 || exit 1
  mv $W/$1.w.part $W/$1.w
  grep "games  avg" $L/$1.log | tail -n 1 | sed "s/^/  $1 /" >> $L/log
done
echo "[$(date '+%F %T')] done" >> $L/log
