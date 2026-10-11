#!/bin/bash
# 32768 phase, part B (build the 8192 next to [32768 16384], real sum [49152, 57344)) as a real-board network: today it
# is played through the root view, whose dynamics break when the 8192 forms (part B converts 66% vs macroxue's 83%).
# Start positions: pool2mix (16384-phase second-half starts [16384 8192 + small]) relabeled one rank up ->
# [32768 16384 + small] at sum 53248 (weights/pool32C.bin). Recipe of the 4M second half: fresh optimistic, lock,
# k>=6 tables in the loop (real-frame matching), bootstrapping at 57344 from the optimistic constant.
set -e
cd "$(dirname "$0")/.."
W=weights/exp32b
L=results/exp32b
mkdir -p $W $L
NPOOL=$(( $(stat -c %s weights/pool32C.bin) / 8 ))
COMMON="--stages sum:57344 --train-stage 0 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool weights/pool32C.bin --pool-last $NPOOL"
if [ ! -f $W/e3.w ]; then
  echo "[$(date '+%F %T')] part B: training to 3M" >> $L/log
  ./build/gpu_train --load weights/expcpu/start.w $COMMON --episodes 3000000 --save $W/e3.w.part --checkpoint $W/e3.ckpt > $L/e3.log 2>&1
  mv $W/e3.w.part $W/e3.w
  grep "games  avg" $L/e3.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  e3 /" >> $L/log
fi
if [ ! -f $W/e4.w ]; then
  echo "[$(date '+%F %T')] part B: training to 4M" >> $L/log
  ./build/gpu_train --load $W/e3.w --resume $W/e3.ckpt $COMMON --episodes 1000000 --save $W/e4.w.part > $L/e4.log 2>&1
  mv $W/e4.w.part $W/e4.w
  rm -f $W/e3.ckpt
  grep "games  avg" $L/e4.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  e4 /" >> $L/log
fi
# 7-stage players: [s0cpu, first half, B, second half, OI 36864-49152, 32768-phase part B, OI] from the b3 player
for s in e3 e4; do
  if [ ! -f $W/play_$s.w ]; then
    python3 scripts/select_stages.py weights/expsplit/b3_play.w $W/tmp7.w 0,1,2,3,4,4,4 > /dev/null
    python3 scripts/splice_stage.py $W/tmp7.w 5 $W/$s.w 0 $W/play_$s.w > /dev/null
    rm -f $W/tmp7.w
  fi
done
echo "[$(date '+%F %T')] done" >> $L/log
