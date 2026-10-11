#!/bin/bash
# Guei-style single network for the whole 16384 phase (from the 16384's formation to view sum 36864), table-free, GPU:
# stages "sum:20480/14,36864" = [s0cpu, whole phase (OI, trained), OI]; pool = 16384 formations (expsplit/pool16mix.bin).
# Snapshots 4/8/12M (whole-phase episodes are ~3x longer than second-half ones). Evaluated later as a 3-stage player.
cd "$(dirname "$0")/.."
W=weights/expwh
L=results/expwh
mkdir -p $W $L
[ -f $W/start.w ] || python3 scripts/select_stages.py weights/best_v5.w $W/start.w 0,4,4 > /dev/null
COMMON="--stages sum:20480/14,36864 --train-stage 1 --skip-lower --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 \
  --games 32768 --log 250000 --corner-lock 14 --pool weights/expsplit/pool16mix.bin --pool-last 2000000 --seed 1"
prev=""; total=0
for seg in 4 8 12; do
  n=$(( (seg - total) * 1000000 ))
  if [ ! -f $W/w$seg.w ]; then
    src="--load $W/start.w"; [ -n "$prev" ] && src="--load $W/w$prev.w --resume $W/w$prev.ckpt"
    ./build/gpu_train $src $COMMON --episodes $n --save $W/w$seg.w.part --checkpoint $W/w$seg.ckpt > $L/w$seg.log 2>&1 || exit 1
    mv $W/w$seg.w.part $W/w$seg.w
    echo "w$seg: $(grep 'games  avg' $L/w$seg.log | tail -n 1 | grep -o 'stage exit: *[0-9.]*%')" >> $L/log
    [ -n "$prev" ] && rm -f $W/w$prev.ckpt
  fi
  prev=$seg; total=$seg
done
echo done >> $L/log
