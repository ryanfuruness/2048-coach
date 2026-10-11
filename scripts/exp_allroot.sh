#!/bin/bash
# GPU TreeStrap at depth 2: --policy-depth 2 --train-all-root trains EVERY candidate move's afterstate toward its 2-ply
# expectimax backup (not only the played one), i.e. the off-path siblings the search compares.
#  (a) fine-tune the original 4M second half (exps/e4 + its checkpoint) for +1M episodes
#  (b) second half from scratch to 4M, 2-ply (and all-root training) only on boards with <= 6 empty cells, seed 6
set -e
cd "$(dirname "$0")/.."
W=weights/expar
L=results/expar
mkdir -p $W $L
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
COMMON="--stages sum:36864 --train-stage 0 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 250000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool weights/v11c/pool2mix.bin --pool-last $NPOOL --policy-depth 2 --train-all-root"
if [ ! -f $W/ft.w ]; then
  echo "[$(date '+%F %T')] (a) e4 + 1M all-root" >> $L/log
  ./build/gpu_train --load weights/exps/e4.w --resume weights/exps/e4.ckpt $COMMON --policy-mix 1.0 --episodes 1000000 \
    --save $W/ft.w.part > $L/ft.log 2>&1
  mv $W/ft.w.part $W/ft.w
  grep "games  avg" $L/ft.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  ft /" >> $L/log
fi
if [ ! -f $W/sc4.w ]; then
  echo "[$(date '+%F %T')] (b) from scratch, all-root on <= 6 empty, 4M" >> $L/log
  ./build/gpu_train --load weights/expcpu/start.w $COMMON --policy-mix 1.0 --policy-max-empty 6 --episodes 4000000 --seed 6 \
    --save $W/sc4.w.part > $L/sc4.log 2>&1
  mv $W/sc4.w.part $W/sc4.w
  grep "games  avg" $L/sc4.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  sc4 /" >> $L/log
fi
echo "[$(date '+%F %T')] done" >> $L/log
