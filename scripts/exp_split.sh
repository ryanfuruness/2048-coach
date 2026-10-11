#!/bin/bash
# Split the first half at 24576 (the 8192's formation): B = [24576, 28672) (building the 4096 next to the
# 8192), bootstrapping from the 4M second half (never-trained weights zeroed); A = [16384 formation,
# 24576), bootstrapping from B. Each trained to ~4M episodes with snapshots (the recipe that worked for
# both halves). Pool for B: where best_v2's first half (1-ply + tables, GPU) first reaches 24576.
set -e
cd "$(dirname "$0")/.."
W=weights/expsplit
L=results/expsplit
mkdir -p $W $L
ST5="sum:20480/14,24576,28672,36864"
# 5-stage start: [early, A (fresh), B (fresh), C = 4M second half (neutralized), rest]
if [ ! -f $W/start.w ]; then
  python3 scripts/select_stages.py weights/exps/best_v2.w $W/start.tmp.w 0,1,1,2,3
  python3 scripts/neutralize.py $W/start.tmp.w $W/start.w 3:weights/exps/e4.ckpt --fresh 1,2 --value 5000
  rm -f $W/start.tmp.w
fi
if [ ! -f $W/pool24.bin ]; then
  echo "[$(date '+%F %T')] collecting positions at 24576 from best_v2's first half" >> $L/log
  ./build/gpu_train --load weights/exps/best_v2.w --stages "sum:20480/14,28672,36864" --train-stage 1 --no-learn \
    --games 32768 --log 250000 --episodes 1200000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 \
    --endgame-full 2 --endgame-min-rank 7 --pool weights/v11c/pool16.bin --pool-last 1000000 \
    --collect $W/pool24.bin.part --collect-when sum:24576 > $L/pool24.log 2>&1
  mv $W/pool24.bin.part $W/pool24.bin
fi
COMMON="--stages $ST5 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --skip-lower"
train() {  # train PREFIX STAGE LOADFILE POOL SEGMENTS...
  local p=$1 st=$2 load=$3 pool=$4; shift 4
  local prev="" total=0
  for seg in "$@"; do
    local n=$(( (seg - total) * 1000000 ))
    if [ ! -f $W/$p$seg.w ]; then
      local src="--load $load"; [ -n "$prev" ] && src="--load $W/$p$prev.w --resume $W/$p$prev.ckpt"
      echo "[$(date '+%F %T')] $p: training to ${seg}M" >> $L/log
      ./build/gpu_train $src $COMMON --train-stage $st --pool $pool --pool-last 1000000 --episodes $n \
        --save $W/$p$seg.w.part --checkpoint $W/$p$seg.ckpt > $L/$p$seg.log 2>&1
      mv $W/$p$seg.w.part $W/$p$seg.w
      grep "games  avg" $L/$p$seg.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  $p$seg /" >> $L/log
    fi
    prev=$seg; total=$seg
  done
}
train b 2 $W/start.w $W/pool24.bin 2 3 4 6
echo "[$(date '+%F %T')] B done" >> $L/log
