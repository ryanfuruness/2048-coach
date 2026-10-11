#!/bin/bash
# How does search strength evolve with training length? Longer greedy training made the second half
# far worse under search (4M episodes: d3 57.2% / d4 59.7%; 12M: 48.1% / 37.1%). Train the second
# half in segments (fresh optimistic, lock, tables, mixed pool) and evaluate snapshots at depths 3
# and 4 on real positions; also a 2-ply curriculum continued from the 4M snapshot.
set -e
cd "$(dirname "$0")/.."
W=weights/exps
L=results/exps
mkdir -p $W $L
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
COMMON="--stages sum:36864 --train-stage 0 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 250000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool weights/v11c/pool2mix.bin --pool-last $NPOOL"
prev=""; total=0
for seg in 1 2 3 4 5 6 8; do
  n=$(( (seg - total) * 1000000 ))
  if [ ! -f $W/e$seg.w ]; then
    if [ -z "$prev" ]; then src="--load weights/expcpu/start.w"; else src="--load $W/e$prev.w --resume $W/e$prev.ckpt"; fi
    echo "[$(date '+%F %T')] training to ${seg}M" >> $L/log
    ./build/gpu_train $src $COMMON --episodes $n --save $W/e$seg.w.part --checkpoint $W/e$seg.ckpt > $L/e$seg.log 2>&1
    mv $W/e$seg.w.part $W/e$seg.w
    grep "games  avg" $L/e$seg.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  e$seg /" >> $L/log
  fi
  prev=$seg; total=$seg
done
if [ ! -f $W/e4q.w ]; then
  echo "[$(date '+%F %T')] 2-ply curriculum from 4M" >> $L/log
  ./build/gpu_train --load $W/e4.w --resume $W/e4.ckpt --tc-decay 0.1 $COMMON --policy-depth 2 --policy-mix 0.25 \
    --episodes 1500000 --log 100000 --save $W/e4q.w.part --checkpoint $W/e4q.ckpt > $L/e4q.log 2>&1
  mv $W/e4q.w.part $W/e4q.w
fi
echo "[$(date '+%F %T')] training done" >> $L/log
