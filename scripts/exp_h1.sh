#!/bin/bash
# A dedicated first-half network (the 16384's formation -> sum 28672), the treatment that worked for
# the second half: fresh optimistic weights, lock, tables, snapshots to find the length where its
# search strength peaks. It bootstraps at 28672 from the 4M second half (exps/e4), whose
# never-trained weights are zeroed so unseen formations at the boundary do not look attractive.
set -e
cd "$(dirname "$0")/.."
W=weights/exph1
L=results/exph1
mkdir -p $W $L
ST4="sum:20480/14,28672,36864"
if [ ! -f $W/start.w ]; then
  python3 scripts/neutralize.py weights/exps/v11c_e4.w $W/start.w 2:weights/exps/e4.ckpt --fresh 1 --value 5000
fi
COMMON="--stages $ST4 --train-stage 1 --skip-lower --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --log 500000 --corner-lock 14 --endgame-dir weights/endgame --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --pool weights/v11c/pool16.bin --pool-last 1000000"
prev=""; total=0
for seg in 1 2 3 4 6; do
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
# evaluate: the first half from 700 real starts (as v11c's player with this first half; the
# boundary network at play is the un-neutralized 4M second half)
while pgrep -f "[e]xp_otd.sh" > /dev/null && ! grep -q "c7 d4" results/expo/eval.log 2>/dev/null; do sleep 30; done
EGO="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame"
for s in e1 e2 e3 e4 e6; do
  python3 scripts/splice_stage.py weights/exps/v11c_e4.w 1 $W/$s.w 1 $W/play.w > /dev/null
  for d in 3 4; do
    ( ulimit -s unlimited; ulimit -v 5000000
      ./build/play --weights $W/play.w --stages $ST4 --start weights/exps1/pool700.bin --games 700 --threads 14 \
        --seed 999 --quantize --depth $d --stop-sum 28700 $EGO > $L/${s}_d$d.log 2>&1 )
    echo "$s first half d$d: $(grep 'tile sum' $L/${s}_d$d.log)" | tee -a $L/eval.log
  done
done
rm -f $W/play.w
