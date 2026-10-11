#!/bin/bash
# Table-free stage B on the GPU (b4s2 recipe minus tables), bootstrapping at 28672 from the table-free second half g8nt.
# Snapshots 4/6/8M stored as single-stage files (weights/expnt/b{4,6,8}nt.w). Then a 5-stage player = best_v5 with stage 2 =
# b*nt and stage 3 = g8nt can be tested in the full player (tables at play time).
cd "$(dirname "$0")/.."
W=weights/expnt
L=results/expnt
while ps -eo args | grep -q "^/bin/bash scripts/exp_gnt.sh"; do sleep 30; done
[ -f $W/g8nt.w ] || { echo "no g8nt" >> $L/log; exit 1; }
if [ ! -f $W/startBnt.w ]; then
  python3 scripts/neutralize.py weights/best_v5.w $W/tmpB.w --fresh 2 --value 5000 > /dev/null
  python3 scripts/splice_stage.py $W/tmpB.w 3 $W/g8nt.w 0 $W/startBnt.w > /dev/null && rm -f $W/tmpB.w
fi
ST5="sum:20480/14,24576,28672,36864"
SB="--stages $ST5 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 \
  --skip-lower --train-stage 2 --pool weights/expsplit/pool24.bin --pool-last 1000000 --seed 2"
prev=""; total=0
for seg in 4 6 8; do
  n=$(( (seg - total) * 1000000 ))
  if [ ! -f $W/b${seg}nt.w ]; then
    src="--load $W/startBnt.w"; [ -n "$prev" ] && src="--load $W/tmpb${prev}.w --resume $W/b${prev}nt.ckpt"
    ./build/gpu_train $src $SB --episodes $n --save $W/tmpb$seg.w --checkpoint $W/b${seg}nt.ckpt > $L/b${seg}nt.log 2>&1 || exit 1
    python3 scripts/select_stages.py $W/tmpb$seg.w $W/b${seg}nt.w 2 > /dev/null
    echo "b${seg}nt: $(grep 'games  avg' $L/b${seg}nt.log | tail -n 1 | grep -o 'stage exit: *[0-9.]*%')" >> $L/log
    [ -n "$prev" ] && rm -f $W/b${prev}nt.ckpt $W/tmpb$prev.w
  fi
  prev=$seg; total=$seg
done
rm -f $W/b8nt.ckpt $W/tmpb8.w
echo "stage B done" >> $L/log
