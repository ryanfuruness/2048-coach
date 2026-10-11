#!/bin/bash
# Split the second half at 32768: C2 = [32768, 36864) (mostly the table-played collapse), C1 = [28672, 32768)
# (building the chain; most second-half losses). Trained backwards with the peak recipe: C2 from where
# best_v2's second half (GPU, 1-ply + tables) first reaches 32768, then C1 from the mixed pool at 28672,
# bootstrapping from C2 (c4, never-trained weights zeroed). Snapshots 2/3/4/6M.
set -e
cd "$(dirname "$0")/.."
W=weights/expsplit2
L=results/expsplit2
mkdir -p $W $L
ST5="sum:20480/14,28672,32768,36864"
if [ ! -f $W/start.w ]; then   # [early, first half, C1 (fresh), C2 (fresh), rest]
  python3 scripts/select_stages.py weights/exps/best_v2.w $W/start.tmp.w 0,1,2,2,3
  python3 scripts/neutralize.py $W/start.tmp.w $W/start.w --fresh 2,3 --value 5000
  rm -f $W/start.tmp.w
fi
if [ ! -f $W/pool32.bin ]; then
  echo "[$(date '+%F %T')] collecting positions at 32768 from best_v2's second half" >> $L/log
  NP=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
  ./build/gpu_train --load weights/exps/best_v2.w --stages "sum:20480/14,28672,36864" --train-stage 2 --no-learn \
    --games 32768 --log 250000 --episodes 1500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 \
    --endgame-full 2 --endgame-min-rank 7 --pool weights/v11c/pool2mix.bin --pool-last $NP \
    --collect $W/pool32.bin.part --collect-when sum:32768 > $L/pool32.log 2>&1
  mv $W/pool32.bin.part $W/pool32.bin
fi
COMMON="--stages $ST5 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --skip-lower"
train() {  # train PREFIX STAGE LOADFILE POOL SEGMENTS...
  local p=$1 st=$2 load=$3 pool=$4; shift 4
  local np=$(( $(stat -c %s $pool) / 8 )) prev="" total=0
  for seg in "$@"; do
    local n=$(( (seg - total) * 1000000 ))
    if [ ! -f $W/$p$seg.w ]; then
      local src="--load $load"; [ -n "$prev" ] && src="--load $W/$p$prev.w --resume $W/$p$prev.ckpt"
      echo "[$(date '+%F %T')] $p: training to ${seg}M" >> $L/log
      ./build/gpu_train $src $COMMON --train-stage $st --pool $pool --pool-last $np --episodes $n \
        --save $W/$p$seg.w.part --checkpoint $W/$p$seg.ckpt > $L/$p$seg.log 2>&1
      mv $W/$p$seg.w.part $W/$p$seg.w
      grep "games  avg" $L/$p$seg.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  $p$seg /" >> $L/log
    fi
    prev=$seg; total=$seg
  done
}
train c 3 $W/start.w $W/pool32.bin 2 3 4 6
if [ ! -f $W/startC1.w ]; then
  python3 scripts/splice_stage.py $W/start.w 3 $W/c4.w 3 $W/startC1.tmp.w > /dev/null
  python3 scripts/neutralize.py $W/startC1.tmp.w $W/startC1.w 3:$W/c4.ckpt
  rm -f $W/startC1.tmp.w
fi
train d 2 $W/startC1.w weights/v11c/pool2mix.bin 2 3 4 6
echo "[$(date '+%F %T')] training done" >> $L/log
