#!/bin/bash
# CPU queue after the second WSL crash (cause: the Windows C: drive is full, the WSL disk image cannot grow).
# Nothing here writes large files: tables are not saved back (--endgame-nosave), no training.
cd "$(dirname "$0")/.."
L=results/expq3
mkdir -p $L
# wait for the k=5 table (solve resumed at layer 223 after the crash)
while pgrep -f "build/[l]ayered" > /dev/null; do sleep 20; done
[ -f weights/endgame_lt/k5r10.done ] || { echo "k5 table not finished" >> $L/eval.log; exit 1; }
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
LT="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7"
phase() {  # name weights stages stage-depths [options]: whole phase from 700 real starts (best_v2: 58.0%)
  local n=$1 w=$2 st=$3 sd=$4; shift 4
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights $w --stages "$st" --start weights/exps1/pool700.bin --games 700 --threads 14 --seed 999 \
      --quantize --depth 4 --stage-depth $sd --stop-sum 36864 $EGO "$@" > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(grep 'layered table moves' $L/$n.log)" | tee -a $L/eval.log
}
B2="weights/exps/best_v2.w sum:20480/14,28672,36864 3,4,4,4"
B3="weights/expsplit/b3_play.w sum:20480/14,24576,28672,36864 3,4,4,4,4"
VIEW="--leaf-view 14 6 --leaf-view-max-sum 24576"
phase k5_p50 $B2 $LT --lt-min 0.5
phase k5_p30 $B2 $LT --lt-min 0.3
phase k5_p0 $B2 $LT --lt-min 0.0
phase k5v_p50 $B2 $LT --lt-min 0.5 $VIEW
phase vb3 $B3 $VIEW
phase k5vb3 $B3 $LT --lt-min 0.5 $VIEW
# deeper search in the first half (macroxue's first-half losses: d3 10.5%, d4 5.2%, d5 2.9%, d8 0.8%; ours 13.1%)
phase h1d5 weights/exps/best_v2.w sum:20480/14,28672,36864 3,5,4,4
phase h1d5v weights/exps/best_v2.w sum:20480/14,28672,36864 3,5,4,4 $VIEW
# the second half trained with the 2-ply policy from scratch (exp_2ply snapshots 2M/3M)
for s in e2 e3 e4; do
  while [ ! -f weights/exp2p/$s.w ] && pgrep -f "[e]xp_2ply.sh" > /dev/null; do sleep 60; done
  [ -f weights/exp2p/$s.w ] || continue
  if [ ! -f weights/exp2p/play_$s.w ]; then
    python3 scripts/splice_stage.py weights/exps/best_v2.w 2 weights/exp2p/$s.w 0 weights/exp2p/play_$s.w > /dev/null
  fi
  phase 2ply_$s weights/exp2p/play_$s.w sum:20480/14,28672,36864 3,4,4,4
  rm -f weights/exp2p/play_$s.w
done
