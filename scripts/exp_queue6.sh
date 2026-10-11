#!/bin/bash
# Master CPU queue (replaces queues 3-5 after h1d5): decisions for the next benchmark first.
cd "$(dirname "$0")/.."
L=results/expq6
mkdir -p $L
# let exp_queue3 finish h1d5, then stop it (its remaining tests are re-queued below)
until grep -q "tile sum" results/expq3/h1d5.log 2>/dev/null; do sleep 20; done
for p in $(ps -eo pid,args | awk '$2=="/bin/bash" && $3=="scripts/exp_queue3.sh" {print $1}'); do kill $p; done
sleep 2
for p in $(ps -eo pid,args | grep "build/play" | grep "expq3/" | awk '{print $1}'); do kill $p; done
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
LT10="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7"
LT9="--endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7"
VIEW="--leaf-view 14 6 --leaf-view-max-sum 24576"
ST5="sum:20480/14,24576,28672,36864"
B3=weights/expsplit/b3_play.w
phase() {  # name weights stages stage-depths [options]: whole phase from 700 real starts
  local n=$1 w=$2 st=$3 sd=$4; shift 4
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights $w --stages "$st" --start weights/exps1/pool700.bin --games 700 --threads 14 --seed 999 \
      --quantize --depth 4 --stage-depth $sd --stop-sum 36864 $EGO "$@" > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(grep 'layered table moves' $L/$n.log)" | tee -a $L/eval.log
}
p32() {  # name [options]: 32768 phase from 500 positions to game over (b3 player)
  local n=$1; shift
  [ -f $L/$n.log ] && grep -q "=== " $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights $B3 --stages "$ST5" --start weights/pool32k.bin --games 500 --threads 14 --seed 999 \
      --quantize --depth 4 --stage-depth 3,4,4,4,4 $EGO "$@" > $L/$n.log 2>&1 )
  echo "$n: $(grep 'mean score' $L/$n.log)  $(grep 'reached  65536' $L/$n.log)  $(grep 'layered table moves' $L/$n.log)  sums>=49152/57344: $(grep '^game' $L/$n.log | awk '{n++; if ($NF>=49152) a++; if ($NF>=57344) b++} END {printf "%.1f%% / %.1f%%", 100*a/n, 100*b/n}')" | tee -a $L/eval.log
}
splice5() {  # out stage src src_stage (from the b3 player)
  [ -f $1 ] || python3 scripts/splice_stage.py $B3 $2 $3 $4 $1 > /dev/null
}
# 1. both k=5 tables on the best configuration (k5vb3 = 61.7% with k5r10 only)
phase k5both_vb3 $B3 $ST5 3,4,4,4,4 $LT10 $LT9 --lt-min 0.5 $VIEW
# 1b. 1000-game benchmark of the best configuration (both tables if they did not hurt)
LTB="$LT10"
r=$(grep "^k5both_vb3" $L/eval.log | grep -o "[0-9.]*%" | head -1 | tr -d %)
[ -n "$r" ] && awk -v r=$r 'BEGIN {exit !(r >= 61.0)}' && LTB="$LT10 $LT9"
if [ ! -f results/bench/best_v3_1000/summary.txt ] || ! grep -q "1000 games" results/bench/best_v3_1000/summary.txt; then
  ( ulimit -s unlimited; ulimit -v 5000000
    scripts/bench.sh best_v3_1000 $B3 "$ST5" 1000 100 14 --quantize --depth 4 --stage-depth 3,4,4,4,4 $EGO $LTB \
      --lt-min 0.5 $VIEW > /dev/null 2>&1 )
  echo "best_v3 benchmark: $(head -1 results/bench/best_v3_1000/summary.txt)" | tee -a $L/eval.log
fi
# 2. the 32768 phase: base / k=5 tables / k=6 tables matched on the real board
p32 p32_base
p32 p32_k5 $LT10 $LT9 --lt-min 0.5
p32 p32_k5real $LT10 $LT9 --lt-min 0.5 --endgame-real
# 3. second-half seeds in the best configuration (stage 3 of the b3 player = exps e4)
for sd in s2 s5 s6 s7; do
  [ -f weights/expseed/$sd.w ] || continue
  splice5 weights/expseed/p5_$sd.w 3 weights/expseed/$sd.w 0
  phase k5vb3_$sd weights/expseed/p5_$sd.w $ST5 3,4,4,4,4 $LT10 $LT9 --lt-min 0.5 $VIEW
  rm -f weights/expseed/p5_$sd.w
done
# 4. stage B seeds (stage 2)
for b in b3s2 b4s2 b3s3 b4s3; do
  while [ ! -f weights/expsplit/$b.w ] && ps -eo args | grep -q "^/bin/bash scripts/exp_bseeds.sh"; do sleep 60; done
  [ -f weights/expsplit/$b.w ] || continue
  splice5 weights/expsplit/p5_$b.w 2 weights/expsplit/$b.w 2
  phase k5v_$b weights/expsplit/p5_$b.w $ST5 3,4,4,4,4 $LT10 $LT9 --lt-min 0.5 $VIEW
  rm -f weights/expsplit/p5_$b.w
done
# 5. budgeted deeper search
phase bud2nd_20k $B3 $ST5 3,4,4,8,4 $LT10 $LT9 --lt-min 0.5 $VIEW --min-depth 4 --budget 20000
# 6. leftovers: d5 first half with the view, the 2-ply second halves
phase h1d5v weights/exps/best_v2.w sum:20480/14,28672,36864 3,5,4,4 $VIEW
for s in e2 e3 e4; do
  [ -f weights/exp2p/$s.w ] || continue
  [ -f weights/exp2p/play_$s.w ] || python3 scripts/splice_stage.py weights/exps/best_v2.w 2 weights/exp2p/$s.w 0 weights/exp2p/play_$s.w > /dev/null
  phase 2ply_$s weights/exp2p/play_$s.w sum:20480/14,28672,36864 3,4,4,4
  rm -f weights/exp2p/play_$s.w
done
echo "queue6 done" >> $L/eval.log
# 7. the early game with the k5r9 table ([8192 4096 2048 1024 512] + 512 -> 16384): from scratch to sum 20480
early() {  # name [options]
  local n=$1; shift
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights $B3 --stages "$ST5" --games 1400 --threads 14 --seed 4321 --quantize --depth 4 \
      --stage-depth 3,4,4,4,4 --stop-sum 20480 $EGO "$@" > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(grep 'reached  16384' $L/$n.log)  $(grep 'layered table moves' $L/$n.log)" | tee -a $L/eval.log
}
early early_base
early early_k5 $LT10 $LT9 --lt-min 0.5
echo "queue6 early done" >> $L/eval.log
# 8. re-runs with the fixed layered-table move mapping (gap chains: k5r9 in the first half, k5r10 in the 32768 phase)
phase k5both_vb3_fix $B3 $ST5 3,4,4,4,4 $LT10 $LT9 --lt-min 0.5 $VIEW
echo "queue6 fix done" >> $L/eval.log
# 9. over-training test, GPU with 2048 games in flight (weights/expsq/e4/e8/e12): as v11c's second half on 600 real
# positions at d3/d4 (32768 games in flight: 4M 58.0/60.5, 8M 52.8/45.2, 12M ~48/37)
EGO0="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
for s in e4 e8 e12; do
  [ -f weights/expsq/$s.w ] || continue
  python3 scripts/splice_stage.py weights/v11c/final.w 2 weights/expsq/$s.w 0 weights/expsq/play.w > /dev/null
  for d in 3 4; do
    n=sq_${s}_d$d
    [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && continue
    ( ulimit -s unlimited; ulimit -v 5000000
      ./build/play --weights weights/expsq/play.w --stages "sum:20480/14,28672,36864" --start weights/exps/pool600.bin \
        --games 600 --threads 14 --seed 31 --quantize --depth $d --stop-sum 36864 $EGO0 > $L/$n.log 2>&1 )
    echo "$n: $(grep 'tile sum' $L/$n.log)" | tee -a $L/eval.log
  done
  rm -f weights/expsq/play.w
done
echo "queue6 sq done" >> $L/eval.log
# 10. 32768 phase: the layered tables matched on the root view (absorbs the top gap of 32768-phase chains)
p32 p32_k5view $LT10 $LT9 --lt-min 0.5 --lt-view
echo "queue6 p32view done" >> $L/eval.log
