#!/bin/bash
# Sequential CPU evaluations (one at a time: memory), after the best_v2 benchmark.
cd "$(dirname "$0")/.."
L=results/evalq1
mkdir -p $L
ST4="sum:20480/14,28672,36864"
EGO="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big"
phase() {  # phase NAME WEIGHTS STAGE_DEPTHS: whole phase from 700 real starts
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights $2 --stages $ST4 --start weights/exps1/pool700.bin --games 700 --threads 14 --seed 999 \
      --quantize --depth 4 --stage-depth $3 --stop-sum 36864 $EGO > $L/$1.log 2>&1 )
  echo "$1 whole phase (stage depths $3): $(grep 'tile sum' $L/$1.log)" | tee -a $L/eval.log
}
until [ -f results/bench/best_v2_1000/summary.txt ] && grep -q "^1000 games" results/bench/best_v2_1000/summary.txt; do sleep 30; done
# 1. the curriculum on the dedicated first half
until [ -f weights/exph1/e4q.w ]; do sleep 30; done
python3 scripts/splice_stage.py weights/exps/v11c_e4.w 1 weights/exph1/e4q.w 1 $L/h1q.w > /dev/null
phase h1q_d4 $L/h1q.w 3,4,4,4
phase h1q_d3 $L/h1q.w 3,3,4,4
# 2. second halves retrained on the new first half's positions (first half = exph1 e4)
for s in e3 e4 e5; do
  until [ -f weights/exps2n/$s.w ]; do sleep 30; done
  python3 scripts/splice_stage.py weights/exps/best_v2.w 2 weights/exps2n/$s.w 0 $L/s2n.w > /dev/null
  phase s2n_$s $L/s2n.w 3,4,4,4
done
rm -f $L/h1q.w $L/s2n.w
# 3. the 8192 phase
scripts/exp_v12b_eval.sh
