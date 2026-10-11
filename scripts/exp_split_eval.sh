#!/bin/bash
# Stage B snapshots through the whole phase (700 real starts -> 36864): 5-stage player = early, first half
# below 24576 (exph1 e4), B snapshot, the 4M second half, rest. Baseline (best_v2): 58.0%.
cd "$(dirname "$0")/.."
W=weights/expsplit
L=results/expsplit
EGO="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big"
python3 scripts/select_stages.py weights/exps/best_v2.w $W/base5.w 0,1,1,2,3 > /dev/null
for s in b2 b3 b4 b6; do
  until [ -f $W/$s.w ]; do sleep 30; done
  python3 scripts/splice_stage.py $W/base5.w 2 $W/$s.w 2 $W/play.w > /dev/null
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights $W/play.w --stages "sum:20480/14,24576,28672,36864" --start weights/exps1/pool700.bin \
      --games 700 --threads 14 --seed 999 --quantize --depth 4 --stage-depth 3,4,4,4,4 --stop-sum 36864 $EGO \
      > $L/${s}_phase.log 2>&1 )
  echo "$s whole phase: $(grep 'tile sum' $L/${s}_phase.log)" | tee -a $L/eval.log
done
rm -f $W/play.w
