#!/bin/bash
# Can exploration keep the second half's search strength from decaying (and raise its peak)?
# Same setup as exp_snap (v11c recipe, 2-stage file, mixed pool), with 3% and 6% exploratory moves
# (Watkins cut), snapshots at 3, 4, 6M episodes; evaluated as v11c's second half at depth 4.
# (0% = exp_snap's e3/e4/e6: d4 60.0 / 60.5 / 52.2.)
set -e
cd "$(dirname "$0")/.."
W=weights/expx
L=results/expx
mkdir -p $W $L
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
COMMON="--stages sum:36864 --train-stage 0 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool weights/v11c/pool2mix.bin --pool-last $NPOOL"
for x in 3 6; do
  prev=""; total=0
  for seg in 3 4 6; do
    n=$(( (seg - total) * 1000000 ))
    if [ ! -f $W/x${x}_e$seg.w ]; then
      if [ -z "$prev" ]; then src="--load weights/expcpu/start.w"; else src="--load $W/x${x}_e$prev.w --resume $W/x${x}_e$prev.ckpt"; fi
      echo "[$(date '+%F %T')] explore $x%: training to ${seg}M" >> $L/log
      ./build/gpu_train $src $COMMON --explore 0.0$x --episodes $n --save $W/x${x}_e$seg.w.part \
        --checkpoint $W/x${x}_e$seg.ckpt > $L/x${x}_e$seg.log 2>&1
      mv $W/x${x}_e$seg.w.part $W/x${x}_e$seg.w
    fi
    prev=$seg; total=$seg
  done
done
echo "[$(date '+%F %T')] training done" >> $L/log
