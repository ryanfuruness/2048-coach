#!/bin/bash
# Stage A = [16384 formation, 24576), bootstrapping from stage B (b4, never-trained weights zeroed), the 4M
# second half behind it. Pool: pool16 (GPU 1-ply positions at the 16384's formation) mixed with the real
# depth-3 positions (30%). Snapshots 2/3/4/6M.
set -e
cd "$(dirname "$0")/.."
W=weights/expsplit
L=results/expsplit
B=${B:-b4}
ST5="sum:20480/14,24576,28672,36864"
if [ ! -f $W/startA.w ]; then
  python3 scripts/splice_stage.py $W/start.w 2 $W/$B.w 2 $W/startA.tmp.w > /dev/null
  python3 scripts/neutralize.py $W/startA.tmp.w $W/startA.w 2:$W/$B.ckpt
  rm -f $W/startA.tmp.w
fi
if [ ! -f $W/pool16mix.bin ]; then
  python3 - weights/v11c/pool16.bin weights/v11c/pool16real.bin $W/pool16mix.bin <<'PY'
import sys, numpy as np
q = np.fromfile(sys.argv[1], dtype=np.uint64)[-1000000:]
r = np.fromfile(sys.argv[2], dtype=np.uint64)
k = max(1, int(round(0.3 / 0.7 * len(q) / len(r))))
np.concatenate([q] + [r] * k).tofile(sys.argv[3])
print(f"pool16mix: {len(q)} + {len(r)} x {k}")
PY
fi
NPOOL=$(( $(stat -c %s $W/pool16mix.bin) / 8 ))
COMMON="--stages $ST5 --train-stage 1 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --skip-lower --pool $W/pool16mix.bin --pool-last $NPOOL"
prev=""; total=0
for seg in 2 3 4 6; do
  n=$(( (seg - total) * 1000000 ))
  if [ ! -f $W/a$seg.w ]; then
    src="--load $W/startA.w"; [ -n "$prev" ] && src="--load $W/a$prev.w --resume $W/a$prev.ckpt"
    echo "[$(date '+%F %T')] a: training to ${seg}M (B = $B)" >> $L/log
    ./build/gpu_train $src $COMMON --episodes $n --save $W/a$seg.w.part --checkpoint $W/a$seg.ckpt > $L/a$seg.log 2>&1
    mv $W/a$seg.w.part $W/a$seg.w
    grep "games  avg" $L/a$seg.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  a$seg /" >> $L/log
  fi
  prev=$seg; total=$seg
done
echo "[$(date '+%F %T')] A done" >> $L/log
