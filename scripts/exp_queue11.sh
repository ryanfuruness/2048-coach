#!/bin/bash
# After exp_cpulong2: (1) GPU tc-mean snapshots in the exp_cpulong2 protocol, (2) depth scaling of the best networks
# without tables vs Guei et al. (conversion 16384->32768 at 1/2/3/4 move levels: 35.4/59.8/68.9/72.9%), (3) Guei-style
# OTD on the CPU (exp_otd.sh), (4) CPU snapshots as stage 3 of best_v5 (whole phase; s6 = 64.1% at 3,4,4,4,4).
cd "$(dirname "$0")/.."
L=results/expq11
mkdir -p $L
while ps -eo args | grep -q "^/bin/bash scripts/exp_cpulong2.sh"; do sleep 60; done
EGOV="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
v11c_eval() {  # name weights (second half): v11c player, pool600, seed 31, d3/d4
  python3 scripts/splice_stage.py weights/v11c/final.w 2 $2 0 $L/play.w > /dev/null
  for d in 3 4; do
    [ -f $L/${1}_d$d.log ] && grep -q "tile sum" $L/${1}_d$d.log && continue
    ( ulimit -s unlimited; export MALLOC_ARENA_MAX=2
      ./build/play --weights $L/play.w --stages "sum:20480/14,28672,36864" --start weights/exps/pool600.bin --games 600 \
        --threads 18 --seed 31 --quantize --depth $d --stop-sum 36864 $EGOV > $L/${1}_d$d.log 2>&1 )
    echo "$1 d$d: $(grep 'tile sum' $L/${1}_d$d.log)" | tee -a $L/eval.log
  done
  rm -f $L/play.w
}
# 0. free ensembles: n-tuple networks are linear in their weights, so averaging the weights of same-recipe seeds gives
#    the mean of their values at no evaluation cost (scripts/avg_stages.py). Second half = mean of s6, s2, s5, e4.
ST5="sum:20480/14,24576,28672,36864"
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
LT="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5 --lt-view"
VIEW="--leaf-view 14 6 --leaf-view-max-sum 24576"
phase5() {  # name weights stage-depths [options]: whole phase, 700 real starts (best_v5 at 3,4,4,4,4: 64.1%)
  local n=$1 w=$2 sd=$3; shift 3
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
    ./build/play --weights $w --stages "$ST5" --start weights/exps1/pool700.bin --games 700 --threads 18 --seed 999 \
      --quantize --depth 4 --stage-depth $sd --stop-sum 36864 $EGO $LT $VIEW "$@" > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(grep -o 'avg [0-9.]* ms/move' $L/$n.log)" | tee -a $L/eval.log
}
phase5 ens_sh4 weights/expens/p5_sh4.w 3,4,4,4,4
phase5 ens_sh4t weights/expens/p5_sh4t.w 3,4,4,4,4   # averages skip weights still at 5000 (untrained in that seed)
phase5 ref_v5 weights/best_v5.w 3,4,4,4,4
# 1. GPU tc-mean snapshots
for g in 4 6 8 12; do
  until [ -f weights/exptm/g$g.w ] || ! ps -eo args | grep -q "^/bin/bash scripts/exp_tcmean.sh"; do sleep 60; done
  [ -f weights/exptm/g$g.w ] && v11c_eval tm_g$g weights/exptm/g$g.w
done
# 1b. annealing: is the TC plateau noise-limited? c12 (TC, flat at d4 ~58-60% from 4M on) continued with plain TD at a
#     small constant rate (averages each weight over ~1/alpha visits), 4M episodes each
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
for a in 0.001 0.01; do
  n=c12td$a
  if [ ! -f weights/expcl/$n.w ]; then
    ./build/train --load weights/expcl/c12.w --stages "sum:36864" --train-stage 0 --stop-at-boundary --alpha $a --lambda 0.5 \
      --corner-lock 14 --endgame-dir weights/endgame_big --endgame-min 0.5 --endgame-full 2 --pool weights/v11c/pool2mix.bin \
      --pool-last $NPOOL --episodes 4000000 --threads 18 --log 500000 --save weights/expcl/$n.w.part > $L/$n.log 2>&1 || exit 1
    mv weights/expcl/$n.w.part weights/expcl/$n.w
    echo "$n train: $(grep 'games  avg' $L/$n.log | tail -n 1)" >> $L/eval.log
  fi
  v11c_eval $n weights/expcl/$n.w
done
# 2. depth scaling without tables (lock, root downgrade and leaf view kept: they are part of how the networks play)
ST5="sum:20480/14,24576,28672,36864"
for d in 1 2 3 4; do
  n=notab_d$d
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && continue
  ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
    ./build/play --weights weights/best_v5.w --stages "$ST5" --start weights/exps1/pool700.bin --games 700 --threads 18 \
      --seed 999 --quantize --depth $d --stage-depth 3,$d,$d,$d,$d --stop-sum 36864 --corner-lock 14 --root-downgrade 15 \
      --leaf-view 14 6 --leaf-view-max-sum 24576 > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(grep -o 'avg [0-9.]* ms/move' $L/$n.log)" | tee -a $L/eval.log
done
# 2b. second-half candidates in the best player (tight 2-ply, lambda variants): scripts/exp_queue12.sh
QUEUE12_INLINE=1 scripts/exp_queue12.sh
# 3. Guei-style OTD
scripts/exp_otd.sh
# 4. CPU snapshots in the best player
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
LT="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5 --lt-view"
VIEW="--leaf-view 14 6 --leaf-view-max-sum 24576"
for c in c8 c12 c16 c24; do
  [ -f weights/expcl/$c.w ] || continue
  n=p5_$c
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && continue
  python3 scripts/splice_stage.py weights/best_v5.w 3 weights/expcl/$c.w 0 $L/p5.w > /dev/null
  ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
    ./build/play --weights $L/p5.w --stages "$ST5" --start weights/exps1/pool700.bin --games 700 --threads 18 --seed 999 \
      --quantize --depth 4 --stage-depth 3,4,4,4,4 --stop-sum 36864 $EGO $LT $VIEW > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(grep -o 'avg [0-9.]* ms/move' $L/$n.log)" | tee -a $L/eval.log
  rm -f $L/p5.w
done
echo "queue11 done" >> $L/eval.log
