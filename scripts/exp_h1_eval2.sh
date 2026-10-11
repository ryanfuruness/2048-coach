#!/bin/bash
# exp_h1's snapshots through the whole phase (real 16384-formation starts -> sum 36864), each as v11c_e4's
# first half (second half = the 4M network at depth 4). Baseline: v11c_e4 itself.
cd "$(dirname "$0")/.."
W=weights/exph1
L=results/exph1
EGO="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big"
for s in base e2 e3 e4 e6; do
  if [ $s = base ]; then cp weights/exps/v11c_e4.w $W/play2.w
  else
    until [ -f $W/$s.w ]; do sleep 30; done
    python3 scripts/splice_stage.py weights/exps/v11c_e4.w 1 $W/$s.w 1 $W/play2.w > /dev/null
  fi
  for st in "3,3,4,4" "3,4,4,4"; do
    ( ulimit -s unlimited; ulimit -v 5000000
      ./build/play --weights $W/play2.w --stages "sum:20480/14,28672,36864" --start weights/exps1/pool700.bin --games 700 \
        --threads 14 --seed 999 --quantize --depth 4 --stage-depth $st --stop-sum 36864 $EGO > $L/${s}_phase_$st.log 2>&1 )
    echo "$s whole phase (stage depths $st): $(grep 'tile sum' $L/${s}_phase_$st.log)" | tee -a $L/eval2.log
  done
done
rm -f $W/play2.w
