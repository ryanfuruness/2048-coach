#!/bin/bash
# The tail of exp_queue12 that never ran (queue12 died: an in-place edit of a line bash had already passed shifted the
# file under it). Runs after queue11 (OTD + its CPU-snapshot tests): table-free stage B with s6, c12 + TD 0.01 in the full
# player, exact-table bootstrapping (lt-boot) vs its control (k5loop).
cd "$(dirname "$0")/.."
L=results/expq13
mkdir -p $L
while ps -eo args | grep -q "^/bin/bash scripts/exp_queue11.sh"; do sleep 60; done
ST5="sum:20480/14,24576,28672,36864"
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
LT="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5 --lt-view"
VIEW="--leaf-view 14 6 --leaf-view-max-sum 24576"
phase() {  # name weights(5-stage)
  local n=$1
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
    ./build/play --weights $2 --stages "$ST5" --start weights/exps1/pool700.bin --games 700 --threads 18 --seed 999 \
      --quantize --depth 4 --stage-depth 3,4,4,4,4 --stop-sum 36864 $EGO $LT $VIEW > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(scripts/death_bins.sh $L/$n.log | cut -c24-)" | tee -a $L/eval.log
}
splice_phase() {  # name stage src-weights(stage 0)
  [ -f $L/$1.log ] && grep -q "tile sum" $L/$1.log && return
  [ -f $3 ] || { echo "$1: missing $3" >> $L/eval.log; return; }
  python3 scripts/splice_stage.py weights/best_v5.w $2 $3 0 $L/p5.w > /dev/null
  phase $1 $L/p5.w
  rm -f $L/p5.w
}
# 1. table-free stage B (GPU b8nt / bx16nt) with best_v5's own second half
splice_phase combo_b8nt 2 weights/expnt/b8nt.w
splice_phase combo_bx16nt 2 weights/expnt/bx16nt.w
# 2. c12 + TD 0.01 (v11c protocol d4 +2) as stage 3
splice_phase cpu_c12td01 3 weights/expcl/c12td0.01.w
# 3. exact-table bootstrapping at the k5r10 handover
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
LT10="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --lt-min 0.5"
TRN="--stages sum:36864 --train-stage 0 --stop-at-boundary --lambda 0.5 --corner-lock 14 --endgame-dir weights/endgame_big \
  --endgame-min 0.5 --endgame-full 2 $LT10 --pool weights/v11c/pool2mix.bin --pool-last $NPOOL --threads 18"
mkdir -p weights/expbr
if [ ! -f $L/calib.log ] || ! grep -q "lt-calib" $L/calib.log; then
  ./build/train --load weights/expcl/c12.w $TRN --no-learn --lt-calib --episodes 60000 --log 20000 > $L/calib.log 2>&1
  grep "lt-calib" $L/calib.log | sed "s/^/calib: /" >> $L/eval.log
fi
C0=$(grep -o "return ~ [-0-9]* + [-0-9]* \* P" $L/calib.log | awk '{print $3}')
C1=$(grep -o "return ~ [-0-9]* + [-0-9]* \* P" $L/calib.log | awk '{print $5}')
for v in boot k5loop; do
  [ -f weights/expbr/$v.w ] && continue
  extra=""; [ $v = boot ] && extra="--lt-boot $C0 $C1 0"
  ./build/train --load weights/expcpu/start.w $TRN --tc --alpha 1.0 --episodes 4000000 --log 500000 $extra \
    --save weights/expbr/$v.w.part > $L/${v}_train.log 2>&1 && mv weights/expbr/$v.w.part weights/expbr/$v.w
  echo "$v train ($extra): $(grep 'games  avg' $L/${v}_train.log | tail -n 1)" >> $L/eval.log
done
splice_phase ltboot 3 weights/expbr/boot.w
splice_phase k5loop 3 weights/expbr/k5loop.w
echo "queue13 done" >> $L/eval.log
