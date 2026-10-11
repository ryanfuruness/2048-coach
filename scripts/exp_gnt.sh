#!/bin/bash
# Table-free second half on the GPU (s6 recipe minus the k>=6 tables, seed 6): learns later than with tables (stage exit
# 26% at 4M and rising), so snapshots at 6/8/12M (the GPU's batched regime degrades past its peak; watch for it).
cd "$(dirname "$0")/.."
W=weights/expnt
L=results/expnt
mkdir -p $W $L
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
COMMON="--stages sum:36864 --train-stage 0 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 \
  --log 500000 --corner-lock 14 --pool weights/v11c/pool2mix.bin --pool-last $NPOOL --seed 6"
prev=""; total=0
for seg in 6 8 12; do
  n=$(( (seg - total) * 1000000 ))
  if [ ! -f $W/g${seg}nt.w ]; then
    src="--load weights/expcpu/start.w"; [ -n "$prev" ] && src="--load $W/g${prev}nt.w --resume $W/g${prev}nt.ckpt"
    ./build/gpu_train $src $COMMON --episodes $n --save $W/g${seg}nt.w.part --checkpoint $W/g${seg}nt.ckpt > $L/g${seg}nt.log 2>&1 || exit 1
    mv $W/g${seg}nt.w.part $W/g${seg}nt.w
    echo "g${seg}nt: $(grep 'games  avg' $L/g${seg}nt.log | tail -n 1 | grep -o 'stage exit: *[0-9.]*%')" >> $L/log
    [ -n "$prev" ] && rm -f $W/g${prev}nt.ckpt
  fi
  prev=$seg; total=$seg
done
rm -f $W/g12nt.ckpt
echo done >> $L/log
