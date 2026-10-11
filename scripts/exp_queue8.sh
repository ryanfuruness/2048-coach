#!/bin/bash
# After exp_queue7 (and exp_cpuk5 it starts): TD-decay snapshots under search; depth tests on best_v5.
cd "$(dirname "$0")/.."
L=results/expq8
mkdir -p $L
while ps -eo args | grep -q -E "^/bin/bash scripts/exp_(queue7|cpuk5).sh"; do sleep 60; done
EGO0="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
# 1. plain TD with decaying rate (weights/exptd e4 alpha 1.0, e8 0.3, e12 0.1) as v11c's second half, 600 real positions
for s in e4 e8 e12; do
  [ -f weights/exptd/$s.w ] || continue
  python3 scripts/splice_stage.py weights/v11c/final.w 2 weights/exptd/$s.w 0 weights/exptd/play.w > /dev/null
  for d in 3 4; do
    n=td_${s}_d$d
    [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && continue
    ( ulimit -s unlimited; ulimit -v 5000000
      ./build/play --weights weights/exptd/play.w --stages "sum:20480/14,28672,36864" --start weights/exps/pool600.bin \
        --games 600 --threads 14 --seed 31 --quantize --depth $d --stop-sum 36864 $EGO0 > $L/$n.log 2>&1 )
    echo "$n: $(grep 'tile sum' $L/$n.log)" | tee -a $L/eval.log
  done
  rm -f weights/exptd/play.w
done
# 2. best_v5 with depth 5 in stage 1 (the 8192 build, valued by s0cpu through the leaf view; s0cpu gains from depth)
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
LT="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5 --lt-view"
VIEW="--leaf-view 14 6 --leaf-view-max-sum 24576"
phase() {  # name stage-depths [options]: whole phase from 700 real starts
  local n=$1 sd=$2; shift 2
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 5000000; export MALLOC_ARENA_MAX=2
    ./build/play --weights weights/best_v5.w --stages "sum:20480/14,24576,28672,36864" --start weights/exps1/pool700.bin \
      --games 700 --threads 14 --seed 999 --quantize --depth 4 --stage-depth $sd --stop-sum 36864 $EGO $LT $VIEW "$@" \
      > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(grep -o 'avg [0-9.]* ms/move' $L/$n.log)" | tee -a $L/eval.log
}
phase v5_phase 3,4,4,4,4
phase v5_s1d5 3,5,4,4,4
# 3. best_v5's early game at depth 4 instead of 3 (from scratch to sum 20480, 1400 games)
early() {
  local n=$1 sd=$2
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 5000000; export MALLOC_ARENA_MAX=2
    ./build/play --weights weights/best_v5.w --stages "sum:20480/14,24576,28672,36864" --games 1400 --threads 14 --seed 4321 \
      --quantize --depth 4 --stage-depth $sd --stop-sum 20480 $EGO $LT $VIEW > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(grep 'reached  16384' $L/$n.log)" | tee -a $L/eval.log
}
early early_d3 3,4,4,4,4
early early_d4 4,4,4,4,4
echo "queue8 done" >> $L/eval.log
# 4. second halves trained from real positions (exp_realpool: real / mix) as stage 3 of best_v5
while ps -eo args | grep -q "^/bin/bash scripts/exp_realpool.sh"; do sleep 60; done
for v in real mix; do
  [ -f weights/exprp/$v.w ] || continue
  [ -f weights/exprp/p5_$v.w ] || python3 scripts/splice_stage.py weights/best_v5.w 3 weights/exprp/$v.w 0 weights/exprp/p5_$v.w > /dev/null
  n=rp_$v
  if ! { [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log; }; then
    ( ulimit -s unlimited; ulimit -v 5000000; export MALLOC_ARENA_MAX=2
      ./build/play --weights weights/exprp/p5_$v.w --stages "sum:20480/14,24576,28672,36864" --start weights/exps1/pool700.bin \
        --games 700 --threads 14 --seed 999 --quantize --depth 4 --stage-depth 3,4,4,4,4 --stop-sum 36864 $EGO $LT $VIEW \
        > $L/$n.log 2>&1 )
    echo "$n: $(grep 'tile sum' $L/$n.log)" | tee -a $L/eval.log
  fi
  rm -f weights/exprp/p5_$v.w
done
echo "queue8 rp done" >> $L/eval.log
# 5. 32768 phase with the real-pool part-B network (exp_p32b_real) vs best_v5 (same tables and options)
while ps -eo args | grep -q "^/bin/bash scripts/exp_p32b_real.sh"; do sleep 60; done
p32mem() {  # name weights stages depths [options]
  local n=$1 w=$2 st=$3 sd=$4; shift 4
  [ -f $L/$n.log ] && grep -q "=== " $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 6800000; export MALLOC_ARENA_MAX=2
    ./build/play --weights $w --stages "$st" --start weights/pool32k.bin --games 500 --threads 14 --seed 999 --quantize \
      --depth 4 --stage-depth $sd $EGO $LT "$@" > $L/$n.log 2>&1 )
  echo "$n: $(grep 'mean score' $L/$n.log)  $(grep 'reached  65536' $L/$n.log)  sums>=49152/57344/61440: $(grep '^game' $L/$n.log | awk '{n++; if ($NF>=49152) a++; if ($NF>=57344) b++; if ($NF>=61440) c++} END {printf "%.1f%% / %.1f%% / %.1f%%", 100*a/n, 100*b/n, 100*c/n}')" | tee -a $L/eval.log
}
p32mem p32_v5 weights/best_v5.w "sum:20480/14,24576,28672,36864" 3,4,4,4,4
[ -f weights/exp32br/play_e4.w ] && p32mem p32_v5_breal weights/exp32br/play_e4.w "sum:20480/14,24576,28672,36864,49152,57344" 3,4,4,4,4,4,4 --root-downgrade-skip 49152 57344
echo "queue8 p32b done" >> $L/eval.log
# 6. budgeted deepening with a probability cut (unlikely spawn lines become leaves, so the budget reaches deeper on the
# likely ones), stage B and second half
phase budpc_20k 3,4,8,8,4 --min-depth 4 --budget 20000 --prob-cut 0.0005
phase bud_20k_ref 3,4,8,8,4 --min-depth 4 --budget 20000
echo "queue8 budpc done" >> $L/eval.log
