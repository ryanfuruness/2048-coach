#!/bin/bash
# After exp_queue3: (1) both k=5 tables (r10 + r9) in the whole-phase test; (2) the 32768 phase alone: from 500
# positions where the 32768 just formed (weights/pool32k.bin, from earlier benchmarks) to game over.
cd "$(dirname "$0")/.."
L=results/expq4
mkdir -p $L
while pgrep -f "[e]xp_queue3.sh" > /dev/null; do sleep 30; done
while pgrep -f "build/[l]ayered" > /dev/null; do sleep 30; done
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
LT10="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7"
LT9="--endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7"
[ -f weights/endgame_lt/k5r9.done ] || LT9=""
VIEW="--leaf-view 14 6 --leaf-view-max-sum 24576"
phase() {  # name weights stages stage-depths [options]: whole phase from 700 real starts (best_v2: 58.0%)
  local n=$1 w=$2 st=$3 sd=$4; shift 4
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights $w --stages "$st" --start weights/exps1/pool700.bin --games 700 --threads 14 --seed 999 \
      --quantize --depth 4 --stage-depth $sd --stop-sum 36864 $EGO "$@" > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(grep 'layered table moves' $L/$n.log)" | tee -a $L/eval.log
}
p32() {  # name weights stages stage-depths [options]: 32768 phase from 500 positions to game over
  local n=$1 w=$2 st=$3 sd=$4; shift 4
  [ -f $L/$n.log ] && grep -q "=== " $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights $w --stages "$st" --start weights/pool32k.bin --games 500 --threads 14 --seed 999 \
      --quantize --depth 4 --stage-depth $sd $EGO "$@" > $L/$n.log 2>&1 )
  echo "$n: $(grep 'mean score' $L/$n.log)  $(grep 'reached  65536' $L/$n.log)  $(grep 'layered table moves' $L/$n.log)  sums>=49152/57344: $(grep '^game' $L/$n.log | awk '{n++; if ($NF>=49152) a++; if ($NF>=57344) b++} END {printf "%.1f%% / %.1f%%", 100*a/n, 100*b/n}')" | tee -a $L/eval.log
}
B2="weights/exps/best_v2.w sum:20480/14,28672,36864 3,4,4,4"
B3="weights/expsplit/b3_play.w sum:20480/14,24576,28672,36864 3,4,4,4,4"
[ -n "$LT9" ] && phase k5both_v $B2 $LT10 $LT9 --lt-min 0.5 $VIEW
[ -n "$LT9" ] && phase k5both_vb3 $B3 $LT10 $LT9 --lt-min 0.5 $VIEW
# second-half seed s2 (59.3% vs e4's 58.0% without the k=5 table) with the tables
if [ ! -f weights/expseed/play_s2.w ]; then
  python3 scripts/splice_stage.py weights/exps/best_v2.w 2 weights/expseed/s2.w 0 weights/expseed/play_s2.w > /dev/null
fi
phase k5_s2 weights/expseed/play_s2.w sum:20480/14,28672,36864 3,4,4,4 $LT10 $LT9 --lt-min 0.5
p32 p32_base $B2
p32 p32_k5 $B2 $LT10 $LT9 --lt-min 0.5
p32 p32_k5real $B2 $LT10 $LT9 --lt-min 0.5 --endgame-real
