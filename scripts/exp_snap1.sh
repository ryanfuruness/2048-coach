#!/bin/bash
# Training length vs search strength for the whole-phase (first-half) network: v11c's m1 recipe
# (fresh optimistic, from the 16384's formation, lock, tables), snapshots at 8..14M episodes; each
# snapshot plays the first half (real 16384-formation starts -> sum 28672) at depths 3 and 4.
set -e
cd "$(dirname "$0")/.."
W=weights/exps1
L=results/exps1
mkdir -p $W $L
ST3="sum:20480/14,36864"
[ -f $W/start.w ] || python3 scripts/neutralize.py weights/v6/s1q1.w $W/start.w --fresh 1,2 --value 5000
COMMON="--stages $ST3 --train-stage 1 --skip-lower --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool weights/v11c/pool16.bin --pool-last 1000000"
prev=""; total=0
for seg in 8 9 10 11 12 14; do
  n=$(( (seg - total) * 1000000 ))
  if [ ! -f $W/e$seg.w ]; then
    if [ -z "$prev" ]; then src="--load $W/start.w"; else src="--load $W/e$prev.w --resume $W/e$prev.ckpt"; fi
    echo "[$(date '+%F %T')] training to ${seg}M" >> $L/log
    ./build/gpu_train $src $COMMON --episodes $n --save $W/e$seg.w.part --checkpoint $W/e$seg.ckpt > $L/e$seg.log 2>&1
    mv $W/e$seg.w.part $W/e$seg.w
    grep "games  avg" $L/e$seg.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  e$seg /" >> $L/log
  fi
  prev=$seg; total=$seg
done
echo "[$(date '+%F %T')] training done" >> $L/log
