#!/bin/bash
# Full-game evaluation of a spliced v6 network.
# usage: eval_v6.sh NAME S0.w S1.w S2.w GAMES THREADS [play options...]
#   stage 0 from S0.w (its stage 0), stage 1 from S1.w (its stage 1), stage 2 from S2.w (its stage 2)
set -e
cd "$(dirname "$0")/.."
NAME=$1 S0=$2 S1=$3 S2=$4 N=$5 TH=$6
shift 6
D=results/v6/full
mkdir -p $D
NET=weights/v6/$NAME.w
if [ ! -f $NET ]; then
  python3 scripts/splice_stage.py $S1 0 $S0 0 $NET.tmp1 > /dev/null
  python3 scripts/splice_stage.py $NET.tmp1 2 $S2 2 $NET > /dev/null
  rm -f $NET.tmp1
fi
./build/play --weights $NET --stages "sum:20480,36864" --quantize --games $N --threads $TH --seed 31 "$@" > $D/$NAME.log 2>&1
python3 scripts/summarize.py $D/$NAME.log
