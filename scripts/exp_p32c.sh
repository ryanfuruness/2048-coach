#!/bin/bash
# 32768 phase, part C (build the 4096 next to [32768 16384 8192], real sum [57344, 61440)) as a real-board network.
# Pool: positions where the 4096 first appears next to [16384 8192] in 1-ply second-half play (GPU, no learning),
# relabeled one rank up -> [32768 16384 8192 + small]. Same recipe as part B.
set -e
cd "$(dirname "$0")/.."
W=weights/exp32c
L=results/exp32c
mkdir -p $W $L
NP2=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
if [ ! -f $W/pool4k.bin ]; then
  echo "[$(date '+%F %T')] collecting [16384 8192 4096] positions" >> $L/log
  ./build/gpu_train --load weights/exps/v11c_e4.w --stages "sum:20480/14,28672,36864" --train-stage 2 --no-learn \
    --games 32768 --log 250000 --episodes 1200000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 \
    --endgame-full 2 --endgame-min-rank 7 --pool weights/v11c/pool2mix.bin --pool-last $NP2 \
    --collect $W/pool4k.bin.part --collect-when "12&13&14" > $L/collect.log 2>&1
  mv $W/pool4k.bin.part $W/pool4k.bin
fi
[ -f weights/pool32D.bin ] || python3 scripts/relabel_pool.py $W/pool4k.bin weights/pool32D.bin 12 >> $L/log
NPOOL=$(( $(stat -c %s weights/pool32D.bin) / 8 ))
COMMON="--stages sum:61440 --train-stage 0 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool weights/pool32D.bin --pool-last $NPOOL"
if [ ! -f $W/e3.w ]; then
  echo "[$(date '+%F %T')] part C: training to 3M" >> $L/log
  ./build/gpu_train --load weights/expcpu/start.w $COMMON --episodes 3000000 --save $W/e3.w.part --checkpoint $W/e3.ckpt > $L/e3.log 2>&1
  mv $W/e3.w.part $W/e3.w
  grep "games  avg" $L/e3.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  e3 /" >> $L/log
fi
if [ ! -f $W/e4.w ]; then
  echo "[$(date '+%F %T')] part C: training to 4M" >> $L/log
  ./build/gpu_train --load $W/e3.w --resume $W/e3.ckpt $COMMON --episodes 1000000 --save $W/e4.w.part > $L/e4.log 2>&1
  mv $W/e4.w.part $W/e4.w
  rm -f $W/e3.ckpt
  grep "games  avg" $L/e4.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  e4 /" >> $L/log
fi
echo "[$(date '+%F %T')] done" >> $L/log
