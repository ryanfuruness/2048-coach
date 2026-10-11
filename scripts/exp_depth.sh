#!/bin/bash
# Can training make the second-half network robust to deeper search? Two 1M-episode continuations
# of v11c's s2q: T1 trains every root move's afterstate toward its 2-ply backup (--train-all-root,
# TreeStrap-like), T2 uses the 2-ply policy on all moves. Then depth 3 vs 4 on real positions.
set -e
cd "$(dirname "$0")/.."
W=weights/expd
L=results/expd
mkdir -p $W $L
ST4="sum:20480/14,28672,36864"
COMMON="--stages $ST4 --train-stage 2 --resume weights/v11c/s2q.ckpt --tc-decay 0.1 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 100000 --save-every 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool weights/v11c/pool2mix.bin --pool-last 2000000 --policy-depth 2 --episodes 1000000"
for v in t1 t2; do
  [ -f $W/$v.w ] && continue
  extra="--train-all-root --policy-mix 0.25"; [ $v = t2 ] && extra="--policy-mix 1.0"
  echo "[$(date '+%F %T')] $v: $extra" >> $L/log
  ./build/gpu_train --load weights/v11c/s2q.w $COMMON $extra --save $W/$v.w.part --checkpoint $W/$v.ckpt > $L/$v.log 2>&1
  mv $W/$v.w.part $W/$v.w
done
EGO="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame"
for v in base t1 t2; do
  w=$W/$v.w; [ $v = base ] && w=weights/v11c/final.w
  for d in 3 4; do
    ( ulimit -s unlimited; ulimit -v 5500000
      ./build/play --weights $w --stages $ST4 --start weights/v11b/pool2real.bin --games 1147 --threads 14 --seed 31 \
        --quantize --depth $d --stop-sum 36864 $EGO > $L/${v}_d$d.log 2>&1 )
    echo "$v d$d: $(grep 'tile sum' $L/${v}_d$d.log)" | tee -a $L/log
  done
done
