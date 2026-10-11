#!/bin/bash
# 32768 phase, part D (build the 2048 next to [32768 16384 8192 4096] and collapse into 65536, real sum [61440, 65536)) as a real-board network.
# Pool: positions where the 4096 first appears next to [16384 8192] in 1-ply second-half play (GPU, no learning),
# relabeled one rank up -> [32768 16384 8192 + small]. Same recipe as part B.
set -e
cd "$(dirname "$0")/.."
W=weights/exp32d
L=results/exp32d
mkdir -p $W $L
NP2=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
if [ ! -f $W/pool2k.bin ]; then
  echo "[$(date '+%F %T')] collecting [16384 8192 4096 2048] positions" >> $L/log
  ./build/gpu_train --load weights/exps/v11c_e4.w --stages "sum:20480/14,28672,36864" --train-stage 2 --no-learn \
    --games 32768 --log 250000 --episodes 1200000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 \
    --endgame-full 2 --endgame-min-rank 7 --pool weights/v11c/pool2mix.bin --pool-last $NP2 \
    --collect $W/pool2k.bin.part --collect-when "11&12&13&14" > $L/collect.log 2>&1
  mv $W/pool2k.bin.part $W/pool2k.bin
fi
[ -f weights/pool32E.bin ] || python3 /home/ryanf/.claude/jobs/ae76afac/tmp/relabel.py $W/pool2k.bin weights/pool32E.bin 11 >> $L/log
NPOOL=$(( $(stat -c %s weights/pool32E.bin) / 8 ))
COMMON="--stages sum:65536 --train-stage 0 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool weights/pool32E.bin --pool-last $NPOOL"
if [ ! -f $W/e3.w ]; then
  echo "[$(date '+%F %T')] part D: training to 3M" >> $L/log
  ./build/gpu_train --load weights/expcpu/start.w $COMMON --episodes 3000000 --save $W/e3.w.part --checkpoint $W/e3.ckpt > $L/e3.log 2>&1
  mv $W/e3.w.part $W/e3.w
  grep "games  avg" $L/e3.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  e3 /" >> $L/log
fi
if [ ! -f $W/e4.w ]; then
  echo "[$(date '+%F %T')] part D: training to 4M" >> $L/log
  ./build/gpu_train --load $W/e3.w --resume $W/e3.ckpt $COMMON --episodes 1000000 --save $W/e4.w.part > $L/e4.log 2>&1
  mv $W/e4.w.part $W/e4.w
  rm -f $W/e3.ckpt
  grep "games  avg" $L/e4.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  e4 /" >> $L/log
fi
echo "[$(date '+%F %T')] done" >> $L/log
