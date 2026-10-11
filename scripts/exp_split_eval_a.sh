#!/bin/bash
# Stage A snapshots with stage B (b4, the one A trained against) through the whole phase: 5-stage player =
# early, A, B, the 4M second half, rest. Baseline best_v2 58.0%.
cd "$(dirname "$0")/.."
W=weights/expsplit
L=results/expsplit
B=${B:-b4}
EGO="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big"
python3 scripts/select_stages.py weights/exps/best_v2.w $W/base5.w 0,1,1,2,3 > /dev/null
python3 scripts/splice_stage.py $W/base5.w 2 $W/$B.w 2 $W/baseB.w > /dev/null
for s in a2 a3 a4 a6; do
  python3 scripts/splice_stage.py $W/baseB.w 1 $W/$s.w 1 $W/playA.w > /dev/null
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights $W/playA.w --stages "sum:20480/14,24576,28672,36864" --start weights/exps1/pool700.bin \
      --games 700 --threads 14 --seed 999 --quantize --depth 4 --stage-depth 3,4,4,4,4 --stop-sum 36864 $EGO \
      > $L/${s}_${B}_phase.log 2>&1 )
  echo "$s+$B whole phase: $(grep 'tile sum' $L/${s}_${B}_phase.log)" | tee -a $L/eval.log
done
rm -f $W/playA.w $W/baseB.w
