#!/bin/bash
# Guei-style schedule for stage B (the 4096 build, [24576, 28672): the largest build-up death zone, 6.6% vs macroxue's
# ~1%): TD from OI with the tables in the loop, alpha 0.1 (12M) -> 0.01 (6M) -> 0.001 (3M), CPU. 3-stage training file
# [stage B (fresh OI), second half SH, OI] with stages sum:28672,36864 (episodes from pool24 stop at 28672 and bootstrap
# from SH). Each segment is evaluated as stage 2 of best_v5 (whole phase, 700 starts; best_v5 64.14%).
# usage: exp_otdB.sh [SECOND_HALF.w (2-stage file, stage 0; default weights/expseed/s6.w)]
cd "$(dirname "$0")/.."
W=weights/expotdB
L=results/expotdB
mkdir -p $W $L
SH=${1:-weights/expseed/s6.w}
if [ ! -f $W/start.w ]; then
  python3 scripts/select_stages.py weights/best_v5.w $W/tmp3.w 2,3,4 > /dev/null
  python3 scripts/splice_stage.py $W/tmp3.w 1 $SH 0 $W/tmp3b.w > /dev/null && rm -f $W/tmp3.w
  python3 scripts/neutralize.py $W/tmp3b.w $W/start.w --fresh 0 --value 5000 > /dev/null && rm -f $W/tmp3b.w
fi
COMMON="--stages sum:28672,36864 --train-stage 0 --stop-at-boundary --lambda 0.5 --corner-lock 14 \
  --endgame-dir weights/endgame_big --endgame-min 0.5 --endgame-full 2 --pool weights/expsplit/pool24.bin \
  --pool-last 1000000 --threads 18 --log 500000"
ST5="sum:20480/14,24576,28672,36864"
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
LT="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5 --lt-view"
VIEW="--leaf-view 14 6 --leaf-view-max-sum 24576"
seg() {  # name from episodes options
  local n=$1 src=$2 eps=$3; shift 3
  if [ ! -f $W/$n.w ]; then
    echo "[$(date '+%F %T')] $n: $eps episodes from $src ($*)" >> $L/log
    ./build/train --load $src $COMMON --episodes $eps "$@" --save $W/$n.w.part > $L/$n.log 2>&1 || exit 1
    mv $W/$n.w.part $W/$n.w
    grep "games  avg" $L/$n.log | tail -n 1 | sed "s/^/  $n /" >> $L/log
  fi
  if ! { [ -f $L/${n}_phase.log ] && grep -q "tile sum" $L/${n}_phase.log; }; then
    python3 scripts/splice_stage.py weights/best_v5.w 2 $W/$n.w 0 $W/p5.w > /dev/null
    ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
      ./build/play --weights $W/p5.w --stages "$ST5" --start weights/exps1/pool700.bin --games 700 --threads 18 --seed 999 \
        --quantize --depth 4 --stage-depth 3,4,4,4,4 --stop-sum 36864 $EGO $LT $VIEW > $L/${n}_phase.log 2>&1 )
    echo "${n}_phase: $(grep 'tile sum' $L/${n}_phase.log)  $(scripts/death_bins.sh $L/${n}_phase.log | cut -c24-)" | tee -a $L/eval.log
    rm -f $W/p5.w
  fi
}
seg b12 $W/start.w 12000000 --alpha 0.1
seg b18 $W/b12.w 6000000 --alpha 0.01
seg b21 $W/b18.w 3000000 --alpha 0.001
echo "exp_otdB done" >> $L/eval.log
