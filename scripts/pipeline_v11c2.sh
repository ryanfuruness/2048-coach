#!/bin/bash
# v11c, second part: the second half trained on a pool that mixes the GPU training policy's
# positions at sum 28672 (pool2q) with positions where the real player (depth 3, tables, lock)
# reaches 28672. A second half trained only on pool2q was much weaker on real positions (v11b:
# 63% on pool2q, 57% on real ones).
set -e
cd "$(dirname "$0")/.."
RUN=${RUN:-v11c}  # (not NAME: WSL sets NAME to the host name)
W=weights/$RUN
L=results/$RUN
S0=${S0:-weights/tup/s0cpu.w}
EG=${EG:-weights/endgame}
LOCK=${LOCK:-14}
INIT=${INIT:-320000}
S2_GAMES=${S2_GAMES:-12000000}
Q_GAMES=${Q_GAMES:-1500000}
PASSES=${PASSES:-4}     # real first halves played from each real 16384-formation start
REAL_WEIGHT=${REAL_WEIGHT:-0.3}  # share of training starts drawn from the real positions
ST3="sum:20480/14,36864"
ST4="sum:20480/14,28672,36864"
T=./build/gpu_train
COMMON="--stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --save-every 2000000 --corner-lock $LOCK --endgame-dir $EG --endgame-min 0.5 --endgame-full 2"
EGO="--corner-lock $LOCK --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir $EG"
phase() { echo "[$(date '+%F %T')] $*" | tee -a "$L/pipeline.log"; }
run() {
  local n=$1 d=$2
  shift 2
  [ -f "$W/$n.w" ] && return 0
  phase "$n: $d"
  $T "$@" --save "$W/$n.w.part" --checkpoint "$W/$n.ckpt" > "$L/$n.log" 2>&1
  mv "$W/$n.w.part" "$W/$n.w"
}
if [ ! -f $W/pool2real.bin ]; then
  phase "pool2real: m1q plays the first half at depth 3 from real 16384-formation starts ($PASSES passes)"
  N=$(( $(stat -c %s $W/pool16real.bin) / 8 * PASSES ))
  ( ulimit -s unlimited; ulimit -v 6000000
    ./build/play --weights $W/m1q.w --stages $ST3 --start $W/pool16real.bin --games $N --threads 14 --quantize \
      --depth 3 --stop-sum 28700 $EGO --collect $W/pool2real.bin.part --collect-when sum:28672 > $L/pool2real.log 2>&1 )
  mv $W/pool2real.bin.part $W/pool2real.bin
  grep -E "collected|tile sum" $L/pool2real.log | tee -a $L/pipeline.log
fi
if [ ! -f $W/pool2mix.bin ]; then
  python3 - $W/pool2q.bin $W/pool2real.bin $W/pool2mix.bin $REAL_WEIGHT <<'PY'
import sys, numpy as np
q = np.fromfile(sys.argv[1], dtype=np.uint64)[-1000000:]
r = np.fromfile(sys.argv[2], dtype=np.uint64)
w = float(sys.argv[4])
k = max(1, int(round(w / (1 - w) * len(q) / len(r))))  # copies of each real position
mix = np.concatenate([q] + [r] * k)
mix.tofile(sys.argv[3])
print(f"pool2mix: {len(q)} training-policy + {len(r)} real x {k} = {len(mix)} ({k * len(r) / len(mix) * 100:.0f}% real)")
PY
fi
if [ ! -f $W/init4.w ]; then
  python3 scripts/select_stages.py $W/m1q.w $W/init4.tmp.w 0,1,1,2
  python3 scripts/splice_stage.py $W/init4.tmp.w 0 $S0 0 $W/init4.w
  rm -f $W/init4.tmp.w
fi
NMIX=$(( $(stat -c %s $W/pool2mix.bin) / 8 ))
run s2 "second half, fresh optimistic, lock, tables, pool mixed with real positions ($S2_GAMES games)" \
  --load $W/init4.w --stages $ST4 --train-stage 2 --fresh 2,3 --init $INIT $COMMON --log 500000 \
  --episodes $S2_GAMES --pool $W/pool2mix.bin --pool-last $NMIX
run s2q "second half, 2-ply on 25% of the moves, tables, mixed pool ($Q_GAMES games)" --load $W/s2.w --stages $ST4 \
  --train-stage 2 --resume $W/s2.ckpt --tc-decay 0.1 $COMMON --log 100000 --policy-depth 2 --policy-mix 0.25 \
  --episodes $Q_GAMES --pool $W/pool2mix.bin --pool-last $NMIX
cp $W/s2q.w $W/final.w
phase "done: $W/final.w ($ST4; play with $EGO --root-downgrade 15)"
