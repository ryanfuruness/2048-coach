#!/bin/bash
# Batched update rule experiment. In a round, a weight touched c times gets one update of the mean
# error; sequential TD (as in the literature) would apply all c. Shared features (the big-tile
# chain, common to most games) therefore learn up to c times slower than rare ones, which may push
# the network toward position-specific features (poor generalization). Variants: mean (baseline),
# sum (sequential-like; TC's adaptive rates should damp overshoot), cap8 (min(c, 8) x mean), sqrt.
# Same setup as v11c's s2 (fresh optimistic second half, tables, lock, mixed pool), 4M episodes.
set -e
cd "$(dirname "$0")/.."
W=weights/expu
L=results/expu
mkdir -p $W $L
ST4="sum:20480/14,28672,36864"
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
COMMON="--load weights/v11c/init4.w --stages $ST4 --train-stage 2 --fresh 2,3 --init 320000 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 500000 --save-every 2000000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --skip-lower --pool weights/v11c/pool2mix.bin --pool-last $NPOOL --episodes 4000000"
for v in mean sum cap8 sqrt; do
  [ -f $W/$v.w ] && continue
  echo "[$(date '+%F %T')] $v" >> $L/log
  ./build/gpu_train $COMMON --update-scale $v --save $W/$v.w.part --checkpoint $W/$v.ckpt > $L/$v.log 2>&1
  mv $W/$v.w.part $W/$v.w
  grep "games  avg" $L/$v.log | grep -o "^ *[0-9]* games\|stage exit: *[0-9.]*%\|c: *[0-9.]*" | paste - - - | tail -n 4 >> $L/log
done
echo "[$(date '+%F %T')] training done" >> $L/log
EGO="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame"
for v in mean sum cap8 sqrt; do
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights $W/$v.w --stages $ST4 --start weights/v11c/pool16real.bin --games 2886 --threads 14 \
      --seed 999 --quantize --depth 3 --stop-sum 36864 $EGO > $L/${v}_phase.log 2>&1 )
  echo "$v real-start phase (seed 999; v11c final 46.0%): $(grep 'tile sum' $L/${v}_phase.log)" | tee -a $L/log
done
