#!/bin/bash
# 32768-phase part B as a real-board network, second try: start positions from REAL games (every multiple of 256 of the
# tile sum in [49152, 57344) with a 32768, from the best_v3/v4/v5/v5b benchmark records: weights/poolP32B_real.bin).
# The first try (relabeled 16384-phase pool starting at 53248) never saw the start of part B and failed (0.4%).
set -e
cd "$(dirname "$0")/.."
W=weights/exp32br
L=results/exp32br
mkdir -p $W $L
while [ ! -s weights/poolP32B_real.bin ] || pgrep -f "pool_from_records.py weights/poolP32B" > /dev/null; do sleep 30; done
while ps -eo args | grep -q "^/bin/bash scripts/exp_early_gpu.sh"; do sleep 60; done
NPOOL=$(( $(stat -c %s weights/poolP32B_real.bin) / 8 ))
COMMON="--stages sum:57344 --train-stage 0 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool weights/poolP32B_real.bin --pool-last $NPOOL"
if [ ! -f $W/e3.w ]; then
  echo "[$(date '+%F %T')] part B (real pool, $NPOOL positions): training to 3M" >> $L/log
  ./build/gpu_train --load weights/expcpu/start.w $COMMON --episodes 3000000 --save $W/e3.w.part --checkpoint $W/e3.ckpt > $L/e3.log 2>&1
  mv $W/e3.w.part $W/e3.w
  grep "games  avg" $L/e3.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  e3 /" >> $L/log
fi
if [ ! -f $W/e4.w ]; then
  ./build/gpu_train --load $W/e3.w --resume $W/e3.ckpt $COMMON --episodes 1000000 --save $W/e4.w.part > $L/e4.log 2>&1
  mv $W/e4.w.part $W/e4.w
  rm -f $W/e3.ckpt
  grep "games  avg" $L/e4.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  e4 /" >> $L/log
fi
# 7-stage player from best_v5: [s0cpu, first half, B, second half, OI, 32768-phase part B, OI]
if [ ! -f $W/play_e4.w ]; then
  python3 scripts/select_stages.py weights/best_v5.w $W/tmp7.w 0,1,2,3,4,4,4 > /dev/null
  python3 scripts/splice_stage.py $W/tmp7.w 5 $W/e4.w 0 $W/play_e4.w > /dev/null
  rm -f $W/tmp7.w
fi
echo "[$(date '+%F %T')] done" >> $L/log
