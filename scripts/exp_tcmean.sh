#!/bin/bash
# GPU over-training damage: CPU (sequential) TC training does not lose search strength past 4M episodes (exp_cpulong2),
# the GPU's batched-mean TC does. Hypothesis: the GPU steps a weight touched c times per round by the MEAN error but
# accumulates the SUM of the c errors into its TC coherence (|E|/A), so common weights' rates anneal like sequential
# training while they move c x less -> they freeze under-trained and rare weights compensate (fine on the played path,
# wrong off it). --tc-mean accumulates the round's mean instead. Same recipe as the s6/e4 second half; snapshots at
# 4/6/8/12M (evaluated later, as exp_cpulong2: v11c's second half, pool600, seed 31, d3/d4).
cd "$(dirname "$0")/.."
W=weights/exptm
L=results/exptm
mkdir -p $W $L
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
COMMON="--stages sum:36864 --train-stage 0 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 \
  --log 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 \
  --pool weights/v11c/pool2mix.bin --pool-last $NPOOL --tc-mean"
prev=""; total=0
for seg in 4 6 8 12; do
  n=$(( (seg - total) * 1000000 ))
  if [ ! -f $W/g$seg.w ]; then
    src="--load weights/expcpu/start.w"; [ -n "$prev" ] && src="--load $W/g$prev.w --resume $W/g$prev.ckpt"
    echo "[$(date '+%F %T')] GPU tc-mean training to ${seg}M" >> $L/log
    ./build/gpu_train $src $COMMON --seed 11 --episodes $n --save $W/g$seg.w.part --checkpoint $W/g$seg.ckpt > $L/g$seg.log 2>&1 || exit 1
    mv $W/g$seg.w.part $W/g$seg.w
    grep "games  avg" $L/g$seg.log | tail -n 1 | sed "s/^/  g$seg /" >> $L/log
    [ -n "$prev" ] && rm -f $W/g$prev.ckpt
  fi
  prev=$seg; total=$seg
done
rm -f $W/g12.ckpt
echo "[$(date '+%F %T')] done" >> $L/log
