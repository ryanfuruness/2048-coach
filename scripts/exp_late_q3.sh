#!/bin/bash
# Workstream late, queue 3 (48 threads): expert-pool training of the second-half network from t21 (x50: half of the
# episodes start from expert root views) and its control (c0: the usual pool only), TD 0.01 x 6M -> 0.001 x 3M.
cd "$(dirname "$0")/.."
L=results/late; mkdir -p $L weights/late
[ -f weights/late/mix50_sh.bin ] || python3 scripts/exp_late_mixpool.py weights/v11c/pool2mix.bin weights/late/xpool_sh.bin 0.5 weights/late/mix50_sh.bin >> $L/train.log
scripts/exp_late_train.sh x50 weights/expotd/t21.w weights/late/mix50_sh.bin "0.01:6000000 0.001:3000000" 24 &
scripts/exp_late_train.sh c0 weights/expotd/t21.w weights/v11c/pool2mix.bin "0.01:6000000 0.001:3000000" 24 &
wait
echo done > $L/q3.done
