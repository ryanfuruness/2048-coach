#!/bin/bash
# Over-training test, GPU side: the second half (exps e4 recipe) with 2048 instead of 32768 games in flight, i.e. far
# fewer updates averaged per weight per round (closer to sequential training). Snapshots at 4/8/12M episodes;
# evaluated like exp_snap (as v11c's second half, 600 real positions, d3/d4). Reference (32768 games in flight):
# 4M 58.0/60.5, 6M 56.5/52.2, 8M 52.8/45.2, 12M ~48/37.
set -e
cd "$(dirname "$0")/.."
W=weights/expsq
L=results/expsq
mkdir -p $W $L
while ps -eo args | grep -q "^/bin/bash scripts/exp_bseeds.sh"; do sleep 30; done
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
COMMON="--stages sum:36864 --train-stage 0 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 2048 --log 250000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool weights/v11c/pool2mix.bin --pool-last $NPOOL"
prev=""; total=0
for seg in 4 8 12; do
  n=$(( (seg - total) * 1000000 ))
  if [ ! -f $W/e$seg.w ]; then
    src="--load weights/expcpu/start.w"; [ -n "$prev" ] && src="--load $W/e$prev.w --resume $W/e$prev.ckpt"
    echo "[$(date '+%F %T')] training to ${seg}M (2048 games in flight)" >> $L/log
    ./build/gpu_train $src $COMMON --episodes $n --save $W/e$seg.w.part --checkpoint $W/e$seg.ckpt > $L/e$seg.log 2>&1
    mv $W/e$seg.w.part $W/e$seg.w
    [ -n "$prev" ] && rm -f $W/e$prev.ckpt
    grep "games  avg" $L/e$seg.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  e$seg /" >> $L/log
  fi
  prev=$seg; total=$seg
done
rm -f $W/e12.ckpt
echo "[$(date '+%F %T')] training done" >> $L/log
