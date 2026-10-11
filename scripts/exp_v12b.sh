#!/bin/bash
# The 8192 phase again, with the recipe that works: v12's network (10M + 1M curriculum) was far past its
# peak. Stage "sum:10240/13,20480/14" (8192 formed -> 16384 formed), fresh optimistic, corner lock 13,
# tables, snapshots at 2/3/4/6M; bootstrap at the 16384's formation from the dedicated first half
# (exph1 e4, never-trained weights zeroed). Evaluated from scratch through sum 28672 (so the 16384's
# formation quality counts), against the current early game (s0cpu).
set -e
cd "$(dirname "$0")/.."
W=weights/exp12b
L=results/exp12b
mkdir -p $W $L
ST3="sum:10240/13,20480/14"
if [ ! -f $W/start.w ]; then
  python3 scripts/select_stages.py weights/exps/best_v2.w $W/start.tmp.w 0,0,1   # [early, (new), first half]
  python3 scripts/neutralize.py $W/start.tmp.w $W/start.w 2:weights/exph1/e4.ckpt --fresh 1 --value 5000
  rm -f $W/start.tmp.w
fi
COMMON="--stages $ST3 --train-stage 1 --skip-lower --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 13 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool weights/v12/pool8.bin --pool-last 1000000"
prev=""; total=0
for seg in 2 3 4 6; do
  n=$(( (seg - total) * 1000000 ))
  if [ ! -f $W/e$seg.w ]; then
    if [ -z "$prev" ]; then src="--load $W/start.w"; else src="--load $W/e$prev.w --resume $W/e$prev.ckpt"; fi
    echo "[$(date '+%F %T')] training to ${seg}M" >> $L/log
    ./build/gpu_train $src $COMMON --episodes $n --save $W/e$seg.w.part --checkpoint $W/e$seg.ckpt > $L/e$seg.log 2>&1
    mv $W/e$seg.w.part $W/e$seg.w
    grep "games  avg" $L/e$seg.log | tail -n 1 | grep -o "stage exit: *[0-9.]*%" | sed "s/^/  e$seg /" >> $L/log
  fi
  prev=$seg; total=$seg
done
echo "[$(date '+%F %T')] training done" >> $L/log
