#!/bin/bash
# Second half split at 32768: player = early, dedicated first half (exph1 e4), C1 snapshot, C2 snapshot, rest;
# whole phase from 700 real starts (baseline best_v2 58.0%).
cd "$(dirname "$0")/.."
W=weights/expsplit2
L=results/expsplit2
EGO="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big"
run() {  # run C1 C2
  python3 scripts/select_stages.py weights/exps/best_v2.w $W/play.tmp.w 0,1,2,2,3 > /dev/null
  python3 scripts/splice_stage.py $W/play.tmp.w 2 $W/$1.w 2 $W/play.tmp2.w > /dev/null
  python3 scripts/splice_stage.py $W/play.tmp2.w 3 $W/$2.w 3 $W/play.w > /dev/null
  rm -f $W/play.tmp.w $W/play.tmp2.w
  ( ulimit -s unlimited; ulimit -v 5000000
    ./build/play --weights $W/play.w --stages "sum:20480/14,28672,32768,36864" --start weights/exps1/pool700.bin \
      --games 700 --threads 14 --seed 999 --quantize --depth 4 --stage-depth 3,4,4,4,4 --stop-sum 36864 $EGO \
      > $L/${1}_${2}.log 2>&1 )
  echo "$1+$2 whole phase: $(grep 'tile sum' $L/${1}_${2}.log)" | tee -a $L/eval.log
}
for d in d2 d3 d4 d6; do run $d c4; done
rm -f $W/play.w
