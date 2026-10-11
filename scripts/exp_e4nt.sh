#!/bin/bash
# Table-free fine-tuning on the GPU: resume the table-trained second half e4 (exps/e4.ckpt, 4M with tables) for +2M/+4M
# without tables (table-free training from OI takes off late or never; the whole-phase net never reached 32768).
cd "$(dirname "$0")/.."
W=weights/expnt
L=results/expnt
while ps -eo args | grep -q "^/bin/bash scripts/exp_whole_nt.sh"; do sleep 30; done
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
COMMON="--stages sum:36864 --train-stage 0 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 \
  --log 500000 --corner-lock 14 --pool weights/v11c/pool2mix.bin --pool-last $NPOOL --seed 4"
if [ ! -f $W/e4nt2.w ]; then
  ./build/gpu_train --load weights/exps/e4.w --resume weights/exps/e4.ckpt $COMMON --episodes 2000000 --save $W/e4nt2.w.part \
    --checkpoint $W/e4nt2.ckpt > $L/e4nt2.log 2>&1 && mv $W/e4nt2.w.part $W/e4nt2.w
  echo "e4nt2: $(grep 'games  avg' $L/e4nt2.log | tail -n 1 | grep -o 'stage exit: *[0-9.]*%')" >> $L/log
fi
if [ ! -f $W/e4nt4.w ]; then
  ./build/gpu_train --load $W/e4nt2.w --resume $W/e4nt2.ckpt $COMMON --episodes 2000000 --save $W/e4nt4.w.part \
    > $L/e4nt4.log 2>&1 && mv $W/e4nt4.w.part $W/e4nt4.w && rm -f $W/e4nt2.ckpt
  echo "e4nt4: $(grep 'games  avg' $L/e4nt4.log | tail -n 1 | grep -o 'stage exit: *[0-9.]*%')" >> $L/log
fi
