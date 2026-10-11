#!/bin/bash
# Expert iteration, corrected (2026-10-04 evening): root-only distillation hurt (53-55% vs 64.1%): the searched values sit
# 4-6% above the network's on the played path, and fitting only those states distorts them against the off-path
# positions the search compares. (1) centered targets (per tile-sum bin), (2) TreeStrap: also interior search nodes.
cd "$(dirname "$0")/.."
L=results/expq10
W=weights/expdist
mkdir -p $L $W
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
LT="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5 --lt-view"
VIEW="--leaf-view 14 6 --leaf-view-max-sum 24576"
BUD="--min-depth 4 --budget 20000"
ST5="sum:20480/14,24576,28672,36864"
phase() {  # name weights stage-depths [options]: whole phase from 700 real starts (best_v5 at 3,4,4,4,4: 64.1%)
  local n=$1 w=$2 sd=$3; shift 3
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
    ./build/play --weights $w --stages "$ST5" --start weights/exps1/pool700.bin --games 700 --threads 14 --seed 999 \
      --quantize --depth 4 --stage-depth $sd --stop-sum 36864 $EGO $LT $VIEW "$@" > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(grep -o 'avg [0-9.]* ms/move' $L/$n.log)" | tee -a $L/eval.log
}
fit_eval() {  # tag data alpha center(0=off): fit s6's second half, evaluate as stage 3 of best_v5
  local tag=$1 data=$2 al=$3 ce=$4
  if [ ! -f $W/s6_$tag.w ]; then
    local cflag=""; [ "$ce" != 0 ] && cflag="--center $ce"
    ./build/distill --load weights/expseed/s6.w --stage 0 --data $data --out $W/s6_$tag.w --alpha $al --epochs 1 $cflag \
      > $L/distill_$tag.log 2>&1
    echo "fit $tag: $(grep epoch $L/distill_$tag.log | tail -1)" | tee -a $L/eval.log
  fi
  [ -f $W/p5_$tag.w ] || python3 scripts/splice_stage.py weights/best_v5.w 3 $W/s6_$tag.w 0 $W/p5_$tag.w > /dev/null
  phase dist_$tag $W/p5_$tag.w 3,4,4,4,4
  rm -f $W/p5_$tag.w
}
# 1. centered root-only fit on the round-1 data
fit_eval rootc02 $W/d1.bin 0.02 512
# 2. TreeStrap round 1: root afterstates + ~5% of interior chance nodes, second half, held-out starts
if [ ! -f $W/t1.bin.done ]; then
  rm -f $W/t1.bin
  ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
    ./build/play --weights weights/best_v5.w --stages "$ST5" --start weights/pool16real_rest.bin --games 2186 --threads 14 \
      --seed 5001 --quantize --depth 4 --stage-depth 3,4,4,4,4 --stop-sum 36864 $EGO $LT $VIEW \
      --dump-train $W/t1.bin 28672 36864 --dump-tree 3277 > $L/tree_gen1.log 2>&1 ) && touch $W/t1.bin.done
  echo "treestrap data 1: $(( $(stat -c %s $W/t1.bin) / 12 )) samples" | tee -a $L/eval.log
fi
fit_eval tree02c $W/t1.bin 0.02 512
# 2b. optimism neutralized: e4's barely-trained weights (|error| sum <= 1e4 / 1e5: 60% / 70%) set to their tuple's
# mean trained value; as stage 3 of best_v5, depth 4 and 5 in the second half; reference = e4 itself
for v in e4_nm4 e4_nm5; do
  [ -f weights/expnm/p5_$v.w ] || python3 scripts/splice_stage.py weights/best_v5.w 3 weights/expnm/$v.w 0 weights/expnm/p5_$v.w > /dev/null
  phase nm_$v weights/expnm/p5_$v.w 3,4,4,4,4
  phase nm_${v}_d5 weights/expnm/p5_$v.w 3,4,4,5,4
done
[ -f weights/expnm/p5_e4.w ] || python3 scripts/splice_stage.py weights/best_v5.w 3 weights/exps/e4.w 0 weights/expnm/p5_e4.w > /dev/null
phase nm_ref_e4 weights/expnm/p5_e4.w 3,4,4,4,4
phase nm_ref_e4_d5 weights/expnm/p5_e4.w 3,4,4,5,4
rm -f weights/expnm/p5_*.w
# 2c. Monte Carlo playouts re-ranking close root decisions in stage B and the second half (best_v5 at 3,4,4,4,4: 64.1%)
phase ro32 weights/best_v5.w 3,4,4,4,4 --rollouts 32 200 0.005 2
# 3. leftovers: budget + probability cut; GPU early-game nets; tight-board 2-ply second halves; locked early game
phase budpc weights/best_v5.w 3,4,8,8,4 $BUD --prob-cut 0.0005
# forward pruning (macroxue-style "pass score" with the network): interior chance nodes valued below vprune x the
# root's best afterstate value are not expanded, so the budget deepens the plausible lines
phase vp90 weights/best_v5.w 3,4,8,8,4 $BUD --vprune 0.9
phase vp95 weights/best_v5.w 3,4,8,8,4 $BUD --vprune 0.95
phase vp95b60 weights/best_v5.w 3,4,8,8,4 --min-depth 4 --budget 60000 --vprune 0.95
for v in m4 m3; do
  [ -f weights/expt2/p5_$v.w ] || python3 scripts/splice_stage.py weights/best_v5.w 3 weights/expt2/$v.w 0 weights/expt2/p5_$v.w > /dev/null
  phase t2_$v weights/expt2/p5_$v.w 3,4,4,4,4
  rm -f weights/expt2/p5_$v.w
done
early() {  # name weights [options]: early game from scratch to sum 20480 (best_v5: 95.71% reach 16384)
  local n=$1 w=$2; shift 2
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
    ./build/play --weights $w --stages "$ST5" --games 1400 --threads 14 --seed 4321 --quantize --depth 4 \
      --stage-depth 3,4,4,4,4 --stop-sum 20480 $EGO $LT $VIEW "$@" > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(grep 'reached  16384' $L/$n.log)  $(grep 'endgame table moves' $L/$n.log)" | tee -a $L/eval.log
}
for s in l1 l2; do
  [ -f weights/expel/p5_$s.w ] || python3 scripts/splice_stage.py weights/best_v5.w 0 weights/expel/$s.w 0 weights/expel/p5_$s.w > /dev/null
  early early_lock_$s weights/expel/p5_$s.w --corner-lock 13
  rm -f weights/expel/p5_$s.w
done
for s in e8 e12; do
  [ -f weights/expearly/p5_$s.w ] || python3 scripts/splice_stage.py weights/best_v5.w 0 weights/expearly/$s.w 0 weights/expearly/p5_$s.w > /dev/null
  early early_gpu_$s weights/expearly/p5_$s.w
  rm -f weights/expearly/p5_$s.w
done
echo "queue10 done" >> $L/eval.log
# 4. GPU depth-2 TreeStrap (exp_allroot: ft = e4 fine-tuned +1M, sc4 = from scratch) as stage 3 of best_v5
while ps -eo args | grep -q "^/bin/bash scripts/exp_allroot.sh"; do sleep 60; done
for v in ft sc4; do
  [ -f weights/expar/$v.w ] || continue
  [ -f weights/expar/p5_$v.w ] || python3 scripts/splice_stage.py weights/best_v5.w 3 weights/expar/$v.w 0 weights/expar/p5_$v.w > /dev/null
  phase ar_$v weights/expar/p5_$v.w 3,4,4,4,4
  rm -f weights/expar/p5_$v.w
done
# e4 itself in the same slot (reference for ft)
[ -f weights/expar/p5_e4.w ] || python3 scripts/splice_stage.py weights/best_v5.w 3 weights/exps/e4.w 0 weights/expar/p5_e4.w > /dev/null
phase ref_e4 weights/expar/p5_e4.w 3,4,4,4,4
rm -f weights/expar/p5_e4.w
echo "queue10 allroot done" >> $L/eval.log
