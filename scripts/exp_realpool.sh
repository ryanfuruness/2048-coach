#!/bin/bash
# Second half trained from REAL positions: every position where best_v3/v4/v5 benchmark games passed a multiple of 256
# in [28672, 36864) (weights/pool2_real3k.bin, 40.7k positions, scripts/pool_from_records.py), pure and mixed 50/50 with
# pool2mix. Same recipe as the seed runs (fresh optimistic, lock, k>=6 tables, 4M episodes, seed 6).
set -e
cd "$(dirname "$0")/.."
W=weights/exprp
L=results/exprp
mkdir -p $W $L
while ps -eo args | grep -q "^/bin/bash scripts/exp_tddecay2.sh"; do sleep 30; done
if [ ! -f $W/mix.bin ]; then
  python3 - <<'PY'
import numpy as np
r = np.fromfile('weights/pool2_real3k.bin', dtype='<u8')
m = np.fromfile('weights/v11c/pool2mix.bin', dtype='<u8')
rng = np.random.default_rng(1)
k = len(m) // len(r)
mix = np.concatenate([np.tile(r, k), m])  # equal shares
rng.shuffle(mix)
mix.tofile('weights/exprp/mix.bin')
print(len(mix), 'positions in the mixed pool')
PY
fi
for v in real mix; do
  pool=weights/pool2_real3k.bin; [ $v = mix ] && pool=$W/mix.bin
  NPOOL=$(( $(stat -c %s $pool) / 8 ))
  if [ ! -f $W/$v.w ]; then
    echo "[$(date '+%F %T')] second half from the $v pool" >> $L/log
    ./build/gpu_train --load weights/expcpu/start.w --stages sum:36864 --train-stage 0 --stop-at-boundary --tc --alpha 1.0 \
      --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 \
      --endgame-full 2 --endgame-min-rank 7 --pool $pool --pool-last $NPOOL --episodes 4000000 --seed 6 \
      --save $W/$v.w.part > $L/$v.log 2>&1
    mv $W/$v.w.part $W/$v.w
    grep "games  avg" $L/$v.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  $v /" >> $L/log
  fi
done
echo "[$(date '+%F %T')] done" >> $L/log
