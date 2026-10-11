#!/bin/bash
# exp_cpulong without the wait, more snapshots, and each snapshot evaluated right after it is trained.
# Question: does sequential (CPU, Hogwild) training also lose search strength past ~4M episodes? The GPU's batched-mean
# networks peak at 3-4M episodes and then decline under search (exp_snap, 600 real positions, seed 31, d3/d4:
# 4M 58.0/60.5, 6M 56.5/52.2, 8M 52.8/45.2). Continues the CPU-trained 4M second half (weights/expcpu/s2.ckpt).
cd "$(dirname "$0")/.."
W=weights/expcl
L=results/expcl
mkdir -p $W $L
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
EGO="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
evalnet() {  # name weights
  python3 scripts/splice_stage.py weights/v11c/final.w 2 $2 0 $W/play.w > /dev/null
  for d in 3 4; do
    [ -f $L/${1}_d$d.log ] && grep -q "tile sum" $L/${1}_d$d.log && continue
    ( ulimit -s unlimited; export MALLOC_ARENA_MAX=2
      ./build/play --weights $W/play.w --stages "sum:20480/14,28672,36864" --start weights/exps/pool600.bin --games 600 \
        --threads 18 --seed 31 --quantize --depth $d --stop-sum 36864 $EGO > $L/${1}_d$d.log 2>&1 )
    echo "$1 d$d: $(grep 'tile sum' $L/${1}_d$d.log)" | tee -a $L/eval.log
  done
  rm -f $W/play.w
}
evalnet c4 weights/expcpu/s2.w
prevck=weights/expcpu/s2.ckpt; total=4
for seg in 6 8 12 16 24; do
  n=$(( (seg - total) * 1000000 ))
  if [ ! -f $W/c$seg.w ]; then
    echo "[$(date '+%F %T')] CPU training to ${seg}M" >> $L/log
    ./build/train --load weights/expcpu/start.w --resume $prevck --stages "sum:36864" --train-stage 0 --stop-at-boundary \
      --tc --alpha 1.0 --lambda 0.5 --corner-lock 14 --endgame-dir weights/endgame_big --endgame-min 0.5 --endgame-full 2 \
      --pool weights/v11c/pool2mix.bin --pool-last $NPOOL --episodes $n --threads 18 --log 250000 \
      --save $W/c$seg.w.part --checkpoint $W/c$seg.ckpt > $L/c$seg.log 2>&1 || exit 1
    mv $W/c$seg.w.part $W/c$seg.w
    grep "games  avg" $L/c$seg.log | tail -n 1 | sed "s/^/  c$seg /" >> $L/log
    # keep only the newest checkpoint (1.6 GB each)
    [ "$prevck" != weights/expcpu/s2.ckpt ] && rm -f $prevck
  fi
  evalnet c$seg $W/c$seg.w
  prevck=$W/c$seg.ckpt; total=$seg
done
echo "exp_cpulong2 done" >> $L/eval.log
