#!/bin/bash
# Guei et al.'s recipe on our CPU trainer: optimistic TD with a decaying rate, TC only at the end (they: 100M
# episodes per stage, alpha 0.1 -> 0.01 at 50% -> 0.001 at 75%, TC for the last 10%; their networks keep gaining
# from depth). Same second-half task and evaluation as exp_cpulong2 (v11c's second half, pool600, seed 31, d3/d4),
# so it compares with the TC-from-the-start CPU snapshots c4..c24. Scaled to 24M episodes:
# TD 0.1 for 12M -> TD 0.01 for 6M -> TD 0.001 for 3M -> TC (alpha 1, fresh accumulators) for 3M.
cd "$(dirname "$0")/.."
W=weights/expotd
L=results/expotd
mkdir -p $W $L
while ps -eo args | grep -q "^/bin/bash scripts/exp_cpulong2.sh"; do sleep 60; done
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
EGO="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
# with the k>=6 tables in the loop as in c4/c12 (table-free training from OI does not take off on the CPU: n4/n8), so the
# only difference to the TC runs is the TD schedule
COMMON="--stages sum:36864 --train-stage 0 --stop-at-boundary --lambda 0.5 --corner-lock 14 --endgame-dir weights/endgame_big \
  --endgame-min 0.5 --endgame-full 2 --pool weights/v11c/pool2mix.bin --pool-last $NPOOL --threads 18 --log 500000"
evalnet() {  # name weights
  python3 scripts/splice_stage.py weights/v11c/final.w 2 $2 0 $W/play.w > /dev/null
  for d in 3 4; do
    [ -f $L/${1}_d$d.log ] && grep -q "tile sum" $L/${1}_d$d.log && continue
    ( ulimit -s unlimited; export MALLOC_ARENA_MAX=2
      ./build/play --weights $W/play.w --stages "sum:20480/14,28672,36864" --start weights/exps/pool600.bin --games 600 \
        --threads 18 --seed 31 --quantize --depth $d --stop-sum 36864 $EGO > $L/${1}_d$d.log 2>&1 )
    echo "$1 d$d: $(grep 'tile sum' $L/${1}_d$d.log)" | tee -a $L/eval.log
  done
  rm -f $W/play.w
}
seg() {  # name from episodes mode-options
  local n=$1 src=$2 eps=$3; shift 3
  if [ ! -f $W/$n.w ]; then
    echo "[$(date '+%F %T')] $n: $eps episodes from $src ($*)" >> $L/log
    ./build/train --load $src $COMMON --episodes $eps "$@" --save $W/$n.w.part > $L/$n.log 2>&1 || exit 1
    mv $W/$n.w.part $W/$n.w
    grep "games  avg" $L/$n.log | tail -n 1 | sed "s/^/  $n /" >> $L/log
  fi
  evalnet $n $W/$n.w
  # whole phase in the full player (tables at play time) and raw (no tables, d2)
  ST5="sum:20480/14,24576,28672,36864"
  python3 scripts/splice_stage.py weights/best_v5.w 3 $W/$n.w 0 $W/p5.w > /dev/null
  EGO5="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
  LT5="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5 --lt-view"
  if ! { [ -f $L/${n}_phase.log ] && grep -q "tile sum" $L/${n}_phase.log; }; then
    ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
      ./build/play --weights $W/p5.w --stages "$ST5" --start weights/exps1/pool700.bin --games 700 --threads 18 --seed 999 \
        --quantize --depth 4 --stage-depth 3,4,4,4,4 --stop-sum 36864 $EGO5 $LT5 --leaf-view 14 6 --leaf-view-max-sum 24576 \
        > $L/${n}_phase.log 2>&1 )
    echo "${n}_phase: $(grep 'tile sum' $L/${n}_phase.log)   (s6: 64.14%)" | tee -a $L/eval.log
  fi
  if ! { [ -f $L/${n}_notab_d2.log ] && grep -q "tile sum" $L/${n}_notab_d2.log; }; then
    ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
      ./build/play --weights $W/p5.w --stages "$ST5" --start weights/exps1/pool700.bin --games 700 --threads 18 --seed 999 \
        --quantize --depth 2 --stage-depth 3,2,2,2,2 --stop-sum 36864 --corner-lock 14 --root-downgrade 15 \
        --leaf-view 14 6 --leaf-view-max-sum 24576 > $L/${n}_notab_d2.log 2>&1 )
    echo "${n}_notab_d2: $(grep 'tile sum' $L/${n}_notab_d2.log)   (s6: 11.00%)" | tee -a $L/eval.log
  fi
  rm -f $W/p5.w
}
seg t12 weights/expcpu/start.w 12000000 --alpha 0.1
seg t18 $W/t12.w 6000000 --alpha 0.01
seg t21 $W/t18.w 3000000 --alpha 0.001
seg t24tc $W/t21.w 3000000 --tc --alpha 1.0
echo "exp_otd done" >> $L/eval.log
