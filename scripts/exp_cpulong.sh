#!/bin/bash
# Does sequential (CPU, Hogwild) training also lose search strength past ~4M episodes? The GPU's batched-mean
# networks peak at 3-4M episodes and then decline under search (exp_snap, 600 real positions, d3/d4: 4M 58.0/60.5,
# 6M 56.5/52.2, 8M 52.8/45.2). Continue the CPU-trained 4M second half (weights/expcpu/s2.ckpt) to 6/8/12M and
# evaluate each the same way (as v11c's second half). If the CPU nets keep their strength, longer training on the
# CPU (or a more sequential GPU regime) is the way to stronger networks.
# Pass any argument containing "exp_lowrate_eval.sh" to hold back exp_2ply's eval (it waits on that name) so that
# two big CPU jobs never overlap.
cd "$(dirname "$0")/.."
W=weights/expcl
L=results/expcl
mkdir -p $W $L
until grep -q "^a1_2 whole" results/explr/eval.log 2>/dev/null; do sleep 30; done
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
prevck=weights/expcpu/s2.ckpt; total=4
for seg in 6 8 12; do
  n=$(( (seg - total) * 1000000 ))
  if [ ! -f $W/c$seg.w ]; then
    echo "[$(date '+%F %T')] CPU training to ${seg}M" >> $L/log
    ./build/train --load weights/expcpu/start.w --resume $prevck --stages "sum:36864" --train-stage 0 --stop-at-boundary \
      --tc --alpha 1.0 --lambda 0.5 --corner-lock 14 --endgame-dir weights/endgame_big --endgame-min 0.5 --endgame-full 2 \
      --pool weights/v11c/pool2mix.bin --pool-last $NPOOL --episodes $n --threads 18 --log 250000 \
      --save $W/c$seg.w.part --checkpoint $W/c$seg.ckpt > $L/c$seg.log 2>&1 || exit 1
    mv $W/c$seg.w.part $W/c$seg.w
    grep "games  avg" $L/c$seg.log | tail -n 1 | sed "s/^/  c$seg /" >> $L/log
  fi
  prevck=$W/c$seg.ckpt; total=$seg
done
ln -sf ../expcpu/s2.w $W/c4.w
EGO="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big"
for s in c4 c6 c8 c12; do
  python3 scripts/splice_stage.py weights/v11c/final.w 2 $W/$s.w 0 $W/play.w > /dev/null
  for d in 3 4; do
    ( ulimit -s unlimited; ulimit -v 5000000
      ./build/play --weights $W/play.w --stages "sum:20480/14,28672,36864" --start weights/exps/pool600.bin --games 600 \
        --threads 14 --seed 31 --quantize --depth $d --stop-sum 36864 $EGO > $L/${s}_d$d.log 2>&1 )
    echo "$s d$d: $(grep 'tile sum' $L/${s}_d$d.log)" | tee -a $L/eval.log
  done
done
rm -f $W/play.w
