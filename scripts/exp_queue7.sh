#!/bin/bash
# Master CPU queue 7 (after the layered-table move-mapping fix): baseline first, then candidates.
cd "$(dirname "$0")/.."
L=results/expq7
mkdir -p $L
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

splice5() {  # out stage src src_stage (from the b3 player)
  [ -f $1 ] || python3 scripts/splice_stage.py $B3 $2 $3 $4 $1 > /dev/null
}
early() {  # name [options]: the early game from scratch to sum 20480
  local n=$1; shift
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights $B3 --stages "$ST5" --games 1400 --threads 14 --seed 4321 --quantize --depth 4 \
      --stage-depth 3,4,4,4,4 --stop-sum 20480 $EGO "$@" > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(grep 'reached  16384' $L/$n.log)  $(grep 'layered table moves' $L/$n.log)" | tee -a $L/eval.log
}
# 1. baseline: best configuration with both k=5 tables (fixed mapping: k5r9 now plays in the first half)
phase k5both_fix $B3 $ST5 3,4,4,4,4 $LT10 $LT9 --lt-min 0.5 $VIEW
# 2. 32768 phase with the layered tables matched on the root view
p32 p32_k5view $LT10 $LT9 --lt-min 0.5 --lt-view
# 2b. leaf value = network + w * nneonneo heuristic (monotonicity / empty / merges) against clogged free regions
phase shape005 $B3 $ST5 3,4,4,4,4 $LT10 $LT9 --lt-min 0.5 $VIEW --shaping 0.05
phase shape02 $B3 $ST5 3,4,4,4,4 $LT10 $LT9 --lt-min 0.5 $VIEW --shaping 0.2
# 3. second-half seeds (stage 3 of the b3 player = exps e4)
for sd in s2 s5 s6 s7; do
  [ -f weights/expseed/$sd.w ] || continue
  splice5 weights/expseed/p5_$sd.w 3 weights/expseed/$sd.w 0
  phase k5both_$sd weights/expseed/p5_$sd.w $ST5 3,4,4,4,4 $LT10 $LT9 --lt-min 0.5 $VIEW
  rm -f weights/expseed/p5_$sd.w
done
# 3b. 32768 phase with real-board networks for part B [49152, 57344) and part C [57344, 61440) (no root view there);
# all with the layered tables matched on the view (--lt-view: 69.4% / 48.0% vs base 65.8 / 43.2)
p32 p32_k5view_r $LT10 --lt-min 0.5 --lt-view
p32x() {  # name weights stages depths skip-lo skip-hi
  local n=$1 w=$2 st=$3 sd=$4 lo=$5 hi=$6
  [ -f $L/$n.log ] && grep -q "=== " $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights $w --stages "$st" --start weights/pool32k.bin --games 500 --threads 14 --seed 999 --quantize \
      --depth 4 --stage-depth $sd $EGO $LT10 --lt-min 0.5 --lt-view --root-downgrade-skip $lo $hi > $L/$n.log 2>&1 )
  echo "$n: $(grep 'mean score' $L/$n.log)  $(grep 'reached  65536' $L/$n.log)  sums>=49152/57344/61440: $(grep '^game' $L/$n.log | awk '{n++; if ($NF>=49152) a++; if ($NF>=57344) b++; if ($NF>=61440) c++} END {printf "%.1f%% / %.1f%% / %.1f%%", 100*a/n, 100*b/n, 100*c/n}')" | tee -a $L/eval.log
}
ST7="sum:20480/14,24576,28672,36864,49152,57344"
ST8="sum:20480/14,24576,28672,36864,49152,57344,61440"
p32x p32b_e4 weights/exp32b/play_e4.w $ST7 3,4,4,4,4,4,4 49152 57344
if [ -f weights/exp32c/e4.w ] && [ ! -f weights/exp32c/play_bc.w ]; then
  python3 scripts/select_stages.py weights/exp32b/play_e4.w weights/exp32c/tmp8.w 0,1,2,3,4,5,6,6 > /dev/null
  python3 scripts/splice_stage.py weights/exp32c/tmp8.w 6 weights/exp32c/e4.w 0 weights/exp32c/play_bc.w > /dev/null
  rm -f weights/exp32c/tmp8.w
fi
[ -f weights/exp32c/play_bc.w ] && p32x p32bc_e4 weights/exp32c/play_bc.w $ST8 3,4,4,4,4,4,4,4 49152 61440
# 4. stage-B seeds (stage 2)
for b in b3s2 b4s2 b3s3 b4s3; do
  [ -f weights/expsplit/$b.w ] || continue
  splice5 weights/expsplit/p5_$b.w 2 weights/expsplit/$b.w 2
  phase k5both_$b weights/expsplit/p5_$b.w $ST5 3,4,4,4,4 $LT10 $LT9 --lt-min 0.5 $VIEW
  rm -f weights/expsplit/p5_$b.w
done
# 4b. best_v4 candidate: second half s6 (63.0%), k5r10 everywhere, k5r9 only once a 32768 exists (helps there via the
# root view: 32768-phase test +4.4 points at 57344; neutral-to-harmful in the 16384 phase), tables matched on the view
BV4=weights/best_v4.w
LTV4="$LT10 $LT9 --lt-ranks 15 15 --lt-min 0.5 --lt-view"
phase v4_phase $BV4 $ST5 3,4,4,4,4 $LTV4 $VIEW
p32mem() {  # name weights stages depths [options]: 32768-phase test with room for many-stage files
  local n=$1 w=$2 st=$3 sd=$4; shift 4
  [ -f $L/$n.log ] && grep -q "=== " $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 6800000; export MALLOC_ARENA_MAX=2
    ./build/play --weights $w --stages "$st" --start weights/pool32k.bin --games 500 --threads 14 --seed 999 --quantize \
      --depth 4 --stage-depth $sd $EGO "$@" > $L/$n.log 2>&1 )
  echo "$n: $(grep 'mean score' $L/$n.log)  $(grep 'reached  65536' $L/$n.log)  sums>=49152/57344/61440: $(grep '^game' $L/$n.log | awk '{n++; if ($NF>=49152) a++; if ($NF>=57344) b++; if ($NF>=61440) c++} END {printf "%.1f%% / %.1f%% / %.1f%%", 100*a/n, 100*b/n, 100*c/n}')" | tee -a $L/eval.log
}
p32mem p32_v4 $BV4 $ST5 3,4,4,4,4 $LTV4
p32mem p32_v4_b weights/exp32b/play_e4.w "sum:20480/14,24576,28672,36864,49152,57344" 3,4,4,4,4,4,4 $LTV4 --root-downgrade-skip 49152 57344
[ -f weights/exp32c/play_bc.w ] && p32mem p32_v4_bc weights/exp32c/play_bc.w "sum:20480/14,24576,28672,36864,49152,57344,61440" 3,4,4,4,4,4,4,4 $LTV4 --root-downgrade-skip 49152 61440
# 4c. best_v4 1000-game benchmark (part B/C networks added later if they win the 32768-phase test)
if [ ! -f results/bench/best_v4_1000/summary.txt ] || ! grep -q "1000 games" results/bench/best_v4_1000/summary.txt; then
  ( ulimit -s unlimited; ulimit -v 6000000; export MALLOC_ARENA_MAX=2
    scripts/bench.sh best_v4_1000 $BV4 "$ST5" 1000 100 14 --quantize --depth 4 --stage-depth 3,4,4,4,4 $EGO $LTV4 $VIEW \
      > /dev/null 2>&1 )
  echo "best_v4 benchmark: $(head -1 results/bench/best_v4_1000/summary.txt)" | tee -a $L/eval.log
fi
# 4d. best_v5: stage-B seed 2 (4M) + second half s6, k5r9 everywhere, tables matched on the view
BV5=weights/best_v5.w
LTV5="$LT10 $LT9 --lt-min 0.5 --lt-view"
if [ -f $BV5 ] && { [ ! -f results/bench/best_v5_1000/summary.txt ] || ! grep -q "1000 games" results/bench/best_v5_1000/summary.txt; }; then
  ( ulimit -s unlimited; ulimit -v 6000000; export MALLOC_ARENA_MAX=2
    scripts/bench.sh best_v5_1000 $BV5 "$ST5" 1000 100 14 --quantize --depth 4 --stage-depth 3,4,4,4,4 $EGO $LTV5 $VIEW \
      > /dev/null 2>&1 )
  echo "best_v5 benchmark: $(head -1 results/bench/best_v5_1000/summary.txt)" | tee -a $L/eval.log
fi
# 5. the early game with the k=5 tables ([8192 4096 2048 1024 512] + 512 -> 16384)
early early_base
early early_k5 $LT10 $LT9 --lt-min 0.5
# 6. over-training test, 2048 games in flight (weights/expsq/e4/e8/e12) as v11c's second half on 600 real positions
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
# 7. 32768-phase part B as a real-board network (scripts/exp_p32b.sh): no root view in [49152, 57344)
while ps -eo args | grep -q "^/bin/bash scripts/exp_p32b.sh"; do sleep 60; done
for s in e3 e4; do
  [ -f weights/exp32b/play_$s.w ] || continue
  n=p32b_$s
  if ! { [ -f $L/$n.log ] && grep -q "=== " $L/$n.log; }; then
    ( ulimit -s unlimited; ulimit -v 5000000
      ./build/play --weights weights/exp32b/play_$s.w --stages "sum:20480/14,24576,28672,36864,49152,57344" \
        --start weights/pool32k.bin --games 500 --threads 14 --seed 999 --quantize --depth 4 --stage-depth 3,4,4,4,4,4,4 \
        $EGO $LT10 $LT9 --lt-min 0.5 --root-downgrade-skip 49152 57344 > $L/$n.log 2>&1 )
    echo "$n: $(grep 'mean score' $L/$n.log)  sums>=49152/57344: $(grep '^game' $L/$n.log | awk '{n++; if ($NF>=49152) a++; if ($NF>=57344) b++} END {printf "%.1f%% / %.1f%%", 100*a/n, 100*b/n}')" | tee -a $L/eval.log
  fi
done
# 8. budgeted deeper search in the second half
phase bud2nd_20k $B3 $ST5 3,4,4,8,4 $LT10 $LT9 --lt-min 0.5 $VIEW --min-depth 4 --budget 20000
# 9. the 2-ply second halves
for s in e2 e3 e4; do
  [ -f weights/exp2p/$s.w ] || continue
  [ -f weights/exp2p/play_$s.w ] || python3 scripts/splice_stage.py weights/exps/best_v2.w 2 weights/exp2p/$s.w 0 weights/exp2p/play_$s.w > /dev/null
  phase 2ply_$s weights/exp2p/play_$s.w sum:20480/14,28672,36864 3,4,4,4
  rm -f weights/exp2p/play_$s.w
done
# 9b. budgeted deepening (bud2nd_20k: 63.7% vs 60.6% at fixed depth 4, 2.3 ms/move): bigger budgets, and in stage B too
phase bud2nd_60k $B3 $ST5 3,4,4,8,4 $LT10 $LT9 --lt-min 0.5 $VIEW --min-depth 4 --budget 60000
phase budB2nd_20k $B3 $ST5 3,4,8,8,4 $LT10 $LT9 --lt-min 0.5 $VIEW --min-depth 4 --budget 20000
# 9c. best_v5 + budgeted second half: 1000-game benchmark
if [ ! -f results/bench/best_v5b_1000/summary.txt ] || ! grep -q "1000 games" results/bench/best_v5b_1000/summary.txt; then
  ( ulimit -s unlimited; ulimit -v 6000000; export MALLOC_ARENA_MAX=2
    scripts/bench.sh best_v5b_1000 weights/best_v5.w "$ST5" 1000 100 14 --quantize --depth 4 --stage-depth 3,4,4,8,4 \
      --min-depth 4 --budget 20000 $EGO $LT10 $LT9 --lt-min 0.5 --lt-view $VIEW > /dev/null 2>&1 )
  echo "best_v5b benchmark: $(head -1 results/bench/best_v5b_1000/summary.txt)" | tee -a $L/eval.log
fi
# 9d. budgeted deepening in stage B and the second half (whole phase 64.7%): 1000-game benchmark; and a phase test with
# budgeted deepening in every stage from depth 3 (early game and the s0cpu-view part too)
if [ ! -f results/bench/best_v5bb_1000/summary.txt ] || ! grep -q "1000 games" results/bench/best_v5bb_1000/summary.txt; then
  ( ulimit -s unlimited; ulimit -v 6000000; export MALLOC_ARENA_MAX=2
    scripts/bench.sh best_v5bb_1000 weights/best_v5.w "$ST5" 1000 100 14 --quantize --depth 4 --stage-depth 3,4,8,8,4 \
      --min-depth 4 --budget 20000 $EGO $LT10 $LT9 --lt-min 0.5 --lt-view $VIEW > /dev/null 2>&1 )
  echo "best_v5bb benchmark: $(head -1 results/bench/best_v5bb_1000/summary.txt)" | tee -a $L/eval.log
fi
phase budall_20k weights/best_v5.w $ST5 8,8,8,8,4 $LT10 $LT9 --lt-min 0.5 --lt-view $VIEW --min-depth 3 --budget 20000
echo "queue7 done" >> $L/eval.log
scripts/exp_cpuk5.sh
