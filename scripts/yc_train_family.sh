#!/bin/bash
# Workstream yc: train the your-chance networks for every key (src/hvalue.h; build/hv_tool train), then merge them into
# one family file. usage: yc_train_family.sh OUTDIR [STEPS_MILLIONS=100] [KEYS...]
cd "$(dirname "$0")/.."
D=$1; S=${2:-100}; shift 2
KEYS=${*:-"0.02 0.016 0.012 0.008 0.004 0.002 0.0005"}
mkdir -p $D
for k in $KEYS; do
  [ -s $D/k$k.hv ] && grep -q saved $D/k$k.log 2>/dev/null && continue
  ./build/hv_tool train --key $k --out $D/k$k.hv --steps $S --lr 1.0,0.5,0.25,0.1,0.05 --lambda 0.95 --horizon 64 \
    --eps 0 --side 0.25 --pool results/yc/pool_real.txt --pool-frac 0.5 --threads 16 --report 20 \
    --packed weights/serve/v6c_s0only_i16.wp > $D/k$k.log 2>&1
done
echo done > $D/done
