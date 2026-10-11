#!/bin/bash
# exp_v12b snapshots: games from scratch to sum 28700, the 8192 phase played by the snapshot (5-stage player:
# early s0cpu, 8192 phase, best_v2's first half / second half / rest). Baseline: best_v2 (4 stages).
cd "$(dirname "$0")/.."
W=weights/exp12b
L=results/exp12b
EGO="--endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big"
( ulimit -s unlimited; ulimit -v 5000000
  ./build/play --weights weights/exps/best_v2.w --stages "sum:20480/14,28672,36864" --quantize --games 700 --threads 14 \
    --seed 4321 --depth 4 --stage-depth 3,4,4,4 --stop-sum 28700 --corner-lock 14 $EGO > $L/base.log 2>&1 )
echo "base (s0cpu early game) from scratch to 28700: $(grep 'tile sum' $L/base.log)" | tee -a $L/eval.log
for s in e2 e3 e4 e6; do
  until [ -f $W/$s.w ]; do sleep 30; done
  python3 scripts/select_stages.py weights/exps/best_v2.w $W/play.tmp.w 0,0,1,2,3 > /dev/null
  python3 scripts/splice_stage.py $W/play.tmp.w 1 $W/$s.w 1 $W/play.w > /dev/null
  rm -f $W/play.tmp.w
  for d in 3 4; do
    ( ulimit -s unlimited; ulimit -v 5000000
      ./build/play --weights $W/play.w --stages "sum:10240/13,20480/14,28672,36864" --quantize --games 700 --threads 14 \
        --seed 4321 --depth 4 --stage-depth 3,$d,4,4,4 --stop-sum 28700 --corner-lock 13 $EGO > $L/${s}_d$d.log 2>&1 )
    echo "$s (8192 phase at d$d) from scratch to 28700: $(grep 'tile sum' $L/${s}_d$d.log)" | tee -a $L/eval.log
  done
done
rm -f $W/play.w
