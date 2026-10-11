#!/bin/bash
# Resumed after the disk cleanup (2026-10-04 12:30). Best config = best_v5bb: weights/best_v5.w, budgeted deepening in
# stage B and the second half, k5r10 + k5r9 (view-matched), leaf view < 24576.
cd "$(dirname "$0")/.."
L=results/expq9
mkdir -p $L
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
LT="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5 --lt-view"
K6R10="--endgame-lt weights/endgame_lt/k6r10.lt --lt-k 6 --lt-rank 10 --lt-caps 9,9,8,8,9,9,7,7,7,7 --lt-real"
VIEW="--leaf-view 14 6 --leaf-view-max-sum 24576"
BUD="--min-depth 4 --budget 20000"
ST5="sum:20480/14,24576,28672,36864"
p32() {  # name weights stages depths [options]: 32768 phase, 500 positions at the 32768's formation -> game over
  local n=$1 w=$2 st=$3 sd=$4; shift 4
  [ -f $L/$n.log ] && grep -q "=== " $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 6800000; export MALLOC_ARENA_MAX=2
    ./build/play --weights $w --stages "$st" --start weights/pool32k.bin --games 500 --threads 14 --seed 999 --quantize \
      --depth 4 --stage-depth $sd $EGO $LT $VIEW $BUD "$@" > $L/$n.log 2>&1 )
  echo "$n: $(grep 'mean score' $L/$n.log)  $(grep 'reached  65536' $L/$n.log)  sums>=49152/57344/61440: $(grep '^game' $L/$n.log | awk '{n++; if ($NF>=49152) a++; if ($NF>=57344) b++; if ($NF>=61440) c++} END {printf "%.1f%% / %.1f%% / %.1f%%", 100*a/n, 100*b/n, 100*c/n}')" | tee -a $L/eval.log
}
phase() {  # name weights stage-depths [options]: whole 16384 phase from 700 real starts
  local n=$1 w=$2 sd=$3; shift 3
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
    ./build/play --weights $w --stages "$ST5" --start weights/exps1/pool700.bin --games 700 --threads 14 --seed 999 \
      --quantize --depth 4 --stage-depth $sd --stop-sum 36864 $EGO $LT $VIEW "$@" > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(grep -o 'avg [0-9.]* ms/move' $L/$n.log)" | tee -a $L/eval.log
}
# 1. 32768 phase: best_v5bb vs + real-pool part-B network vs + k6r10 on the real board (65536 collapse)
if [ ! -f weights/exp32br/play_e4.w ]; then
  python3 scripts/select_stages.py weights/best_v5.w weights/exp32br/tmp7.w 0,1,2,3,4,4,4 > /dev/null
  python3 scripts/splice_stage.py weights/exp32br/tmp7.w 5 weights/exp32br/e4.w 0 weights/exp32br/play_e4.w > /dev/null
  rm -f weights/exp32br/tmp7.w
fi
p32 p32_v5bb weights/best_v5.w $ST5 3,4,8,8,4
p32 p32_v5bb_breal weights/exp32br/play_e4.w "sum:20480/14,24576,28672,36864,49152,57344" 3,4,8,8,4,8,4 --root-downgrade-skip 49152 57344
p32 p32_v5bb_k6r10 weights/best_v5.w $ST5 3,4,8,8,4 $K6R10
# 2. second halves trained from real positions as stage 3 (best_v5bb whole phase: ~64-65%)
phase v5bb_phase weights/best_v5.w 3,4,8,8,4 $BUD
p32 p32_v5bb_k6r10first weights/best_v5.w $ST5 3,4,8,8,4 $K6R10
for v in real mix; do
  [ -f weights/exprp/$v.w ] || continue
  [ -f weights/exprp/p5_$v.w ] || python3 scripts/splice_stage.py weights/best_v5.w 3 weights/exprp/$v.w 0 weights/exprp/p5_$v.w > /dev/null
  phase rp_$v weights/exprp/p5_$v.w 3,4,8,8,4 $BUD
  rm -f weights/exprp/p5_$v.w
done
# 2b. search-bootstrapped training ("distillation") of the second half: the full player (best_v5, depth 4, no budget)
# plays the whole phase from the held-out real starts 701-2886 and records the searched value of every second-half root
# afterstate; stage s6 is fitted to them; evaluated as stage 3 of best_v5 on starts 1-700 (best_v5 whole phase 64.1%).
mkdir -p weights/expdist
if [ ! -f weights/expdist/d1.bin.done ]; then
  rm -f weights/expdist/d1.bin
  ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
    ./build/play --weights weights/best_v5.w --stages "$ST5" --start weights/pool16real_rest.bin --games 2186 --threads 14 \
      --seed 4242 --quantize --depth 4 --stage-depth 3,4,4,4,4 --stop-sum 36864 $EGO $LT $VIEW \
      --dump-train weights/expdist/d1.bin 28672 36864 > $L/dist_gen1.log 2>&1 ) && touch weights/expdist/d1.bin.done
  echo "distill data 1: $(( $(stat -c %s weights/expdist/d1.bin) / 12 )) samples; $(grep 'tile sum' $L/dist_gen1.log)" | tee -a $L/eval.log
fi
for cfg in "a05 0.05 1" "a02 0.02 1" "a05e2 0.05 2"; do
  set -- $cfg; tag=$1; al=$2; ep=$3
  if [ ! -f weights/expdist/s6_$tag.w ]; then
    ./build/distill --load weights/expseed/s6.w --stage 0 --data weights/expdist/d1.bin --out weights/expdist/s6_$tag.w \
      --alpha $al --epochs $ep > $L/distill_$tag.log 2>&1
    echo "distill $tag: $(grep epoch $L/distill_$tag.log | tail -1)" | tee -a $L/eval.log
  fi
  [ -f weights/expdist/p5_$tag.w ] || python3 scripts/splice_stage.py weights/best_v5.w 3 weights/expdist/s6_$tag.w 0 weights/expdist/p5_$tag.w > /dev/null
  phase dist_$tag weights/expdist/p5_$tag.w 3,4,4,4,4
  rm -f weights/expdist/p5_$tag.w
done
# 3. budget with a probability cut
phase budpc weights/best_v5.w 3,4,8,8,4 $BUD --prob-cut 0.0005
# 4. GPU early-game networks in place of s0cpu's stage 0: early game from scratch to sum 20480 (s0cpu: 95.71% reach 16384)
early() {
  local n=$1 w=$2
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
    ./build/play --weights $w --stages "$ST5" --games 1400 --threads 14 --seed 4321 --quantize --depth 4 \
      --stage-depth 3,4,8,8,4 $BUD --stop-sum 20480 $EGO $LT $VIEW > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(grep 'reached  16384' $L/$n.log)" | tee -a $L/eval.log
}
for s in e8 e12; do
  [ -f weights/expearly/$s.w ] || continue
  [ -f weights/expearly/p5_$s.w ] || python3 scripts/splice_stage.py weights/best_v5.w 0 weights/expearly/$s.w 0 weights/expearly/p5_$s.w > /dev/null
  early early_gpu_$s weights/expearly/p5_$s.w
  rm -f weights/expearly/p5_$s.w
done
echo "queue9 done" >> $L/eval.log
# 5. second halves trained with 2-ply on tight boards only (exp_tight2ply: m4 = <= 4 empty, m3 = <= 3) as stage 3
while ps -eo args | grep -q "^/bin/bash scripts/exp_tight2ply.sh"; do sleep 60; done
for v in m4 m3; do
  [ -f weights/expt2/$v.w ] || continue
  [ -f weights/expt2/p5_$v.w ] || python3 scripts/splice_stage.py weights/best_v5.w 3 weights/expt2/$v.w 0 weights/expt2/p5_$v.w > /dev/null
  phase t2_$v weights/expt2/p5_$v.w 3,4,8,8,4 $BUD
  rm -f weights/expt2/p5_$v.w
done
echo "queue9 t2 done" >> $L/eval.log
# 6. s0cpu continued with lock 13 + tables (exp_early_lock: l1, l2) as stage 0: early game with --corner-lock 13
while ps -eo args | grep -q "^/bin/bash scripts/exp_early_lock.sh"; do sleep 60; done
early13() {
  local n=$1 w=$2
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
    ./build/play --weights $w --stages "$ST5" --games 1400 --threads 14 --seed 4321 --quantize --depth 4 \
      --stage-depth 3,4,8,8,4 $BUD --stop-sum 20480 $EGO $LT $VIEW --corner-lock 13 > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(grep 'reached  16384' $L/$n.log)  $(grep 'endgame table moves' $L/$n.log)" | tee -a $L/eval.log
}
early13 early_s0cpu_lock13 weights/best_v5.w
for s in l1 l2; do
  [ -f weights/expel/$s.w ] || continue
  [ -f weights/expel/p5_$s.w ] || python3 scripts/splice_stage.py weights/best_v5.w 0 weights/expel/$s.w 0 weights/expel/p5_$s.w > /dev/null
  early13 early_$s weights/expel/p5_$s.w
  rm -f weights/expel/p5_$s.w
done
echo "queue9 early-lock done" >> $L/eval.log
# 7. k6r10 on the real board taking precedence over view-matched tables (first run: never played, outranked by the view)
p32 p32_v5bb_k6r10first weights/best_v5.w $ST5 3,4,8,8,4 $K6R10
echo "queue9 k6r10first done" >> $L/eval.log
