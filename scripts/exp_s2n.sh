#!/bin/bash
# The second half retrained on positions from the new dedicated first half (exph1 e4): the 4M second half
# (exps e4) was trained on positions from v11c's first half. Pool: where exph1 e4 (1-ply + tables, GPU)
# first reaches sum 28672, mixed with the old mixed pool; 4M episodes from fresh optimistic weights.
set -e
cd "$(dirname "$0")/.."
W=weights/exps2n
L=results/exps2n
mkdir -p $W $L
ST4="sum:20480/14,28672,36864"
if [ ! -f $W/pool.bin ]; then
  echo "[$(date '+%F %T')] collecting positions at 28672 from exph1 e4" >> $L/log
  ./build/gpu_train --load weights/exps/best_v2.w --stages $ST4 --train-stage 1 --no-learn --games 32768 --log 250000 \
    --episodes 1200000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 \
    --pool weights/v11c/pool16.bin --pool-last 1000000 --collect $W/pool_new.bin --collect-when sum:28672 > $L/pool.log 2>&1
  python3 - $W/pool_new.bin weights/v11c/pool2mix.bin $W/pool.bin <<'PY'
import sys, numpy as np
new = np.fromfile(sys.argv[1], dtype=np.uint64)
old = np.fromfile(sys.argv[2], dtype=np.uint64)
mix = np.concatenate([old[-len(new) // 2:], new])  # 2/3 new formations
mix.tofile(sys.argv[3])
print(f"pool: {len(new)} new + {len(new) // 2} old = {len(mix)}")
PY
fi
NPOOL=$(( $(stat -c %s $W/pool.bin) / 8 ))
COMMON="--stages sum:36864 --train-stage 0 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool $W/pool.bin --pool-last $NPOOL"
prev=""; total=0
for seg in 3 4 5; do
  n=$(( (seg - total) * 1000000 ))
  if [ ! -f $W/e$seg.w ]; then
    if [ -z "$prev" ]; then src="--load weights/expcpu/start.w"; else src="--load $W/e$prev.w --resume $W/e$prev.ckpt"; fi
    echo "[$(date '+%F %T')] training to ${seg}M" >> $L/log
    ./build/gpu_train $src $COMMON --episodes $n --save $W/e$seg.w.part --checkpoint $W/e$seg.ckpt > $L/e$seg.log 2>&1
    mv $W/e$seg.w.part $W/e$seg.w
  fi
  prev=$seg; total=$seg
done
echo "[$(date '+%F %T')] training done" >> $L/log
