#!/bin/bash
# A GPU-trained early-game network (zero init, the GPU recipe) as an alternative to s0cpu (CPU-trained, 12.3M episodes),
# which plays the early game (95.7% reach 16384 in the best config) and values the 8192 build through the leaf view.
# Start: s0cpu's 2-stage file with stage 0 zeroed (stage 1 = s0cpu's bootstrap stage). Snapshots at 4/8/12M episodes.
set -e
cd "$(dirname "$0")/.."
W=weights/expearly
L=results/expearly
mkdir -p $W $L
[ -f $W/start.w ] || python3 scripts/neutralize.py weights/tup/s0cpu.w $W/start.w --fresh 0 --value 0 >> $L/log
COMMON="--stages sum:20480 --train-stage 0 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 500000"
prev=""; total=0
for seg in 4 8 12; do
  n=$(( (seg - total) * 1000000 ))
  if [ ! -f $W/e$seg.w ]; then
    src="--load $W/start.w"; [ -n "$prev" ] && src="--load $W/e$prev.w --resume $W/e$prev.ckpt"
    echo "[$(date '+%F %T')] early game to ${seg}M" >> $L/log
    ./build/gpu_train $src $COMMON --episodes $n --save $W/e$seg.w.part --checkpoint $W/e$seg.ckpt > $L/e$seg.log 2>&1
    mv $W/e$seg.w.part $W/e$seg.w
    [ -n "$prev" ] && rm -f $W/e$prev.ckpt
    grep "games  avg" $L/e$seg.log | tail -n 1 | cut -c 1-160 | sed "s/^/  e$seg /" >> $L/log
  fi
  prev=$seg; total=$seg
done
rm -f $W/e12.ckpt
echo "[$(date '+%F %T')] done" >> $L/log
