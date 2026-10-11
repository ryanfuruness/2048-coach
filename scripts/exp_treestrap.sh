#!/bin/bash
# Expert iteration for the second half, TreeStrap variant: the full player records the searched values of its root
# afterstates AND of ~5% of the interior chance nodes of each search (positions off the played path, the ones the search
# evaluates); the stage is fitted to them; then the improved network generates the next round.
#   usage: exp_treestrap.sh ROUND BASE_STAGE_FILE ALPHA EPOCHS
# Round r writes weights/expdist/t{r}.bin (data) and weights/expdist/s6_t{r}.w (fitted 2-stage file, stage 0 = 2nd half).
cd "$(dirname "$0")/.."
R=$1 BASE=$2 AL=${3:-0.02} EP=${4:-1}
L=results/expq9
W=weights/expdist
mkdir -p $W
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
LT="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5 --lt-view"
VIEW="--leaf-view 14 6 --leaf-view-max-sum 24576"
ST5="sum:20480/14,24576,28672,36864"
# the player of this round: best_v5 with stage 3 = BASE's stage 0
python3 scripts/splice_stage.py weights/best_v5.w 3 $BASE 0 $W/gen_t$R.w > /dev/null
if [ ! -f $W/t$R.bin.done ]; then
  rm -f $W/t$R.bin
  ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
    ./build/play --weights $W/gen_t$R.w --stages "$ST5" --start weights/pool16real_rest.bin --games 2186 --threads 14 \
      --seed $((5000 + R)) --quantize --depth 4 --stage-depth 3,4,4,4,4 --stop-sum 36864 $EGO $LT $VIEW \
      --dump-train $W/t$R.bin 28672 36864 --dump-tree 3277 > $L/tree_gen$R.log 2>&1 ) && touch $W/t$R.bin.done
  echo "treestrap round $R data: $(( $(stat -c %s $W/t$R.bin) / 12 )) samples; generating player $(grep 'tile sum' $L/tree_gen$R.log)" | tee -a $L/eval.log
fi
rm -f $W/gen_t$R.w
if [ ! -f $W/s6_t$R.w ]; then
  ./build/distill --load $BASE --stage 0 --data $W/t$R.bin --out $W/s6_t$R.w --alpha $AL --epochs $EP > $L/distill_t$R.log 2>&1
  echo "treestrap round $R fit: $(grep epoch $L/distill_t$R.log | tail -1)" | tee -a $L/eval.log
fi
python3 scripts/splice_stage.py weights/best_v5.w 3 $W/s6_t$R.w 0 $W/p5_t$R.w > /dev/null
( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
  ./build/play --weights $W/p5_t$R.w --stages "$ST5" --start weights/exps1/pool700.bin --games 700 --threads 14 --seed 999 \
    --quantize --depth 4 --stage-depth 3,4,4,4,4 --stop-sum 36864 $EGO $LT $VIEW > $L/tree_eval$R.log 2>&1 )
echo "treestrap round $R eval (best_v5 64.1%): $(grep 'tile sum' $L/tree_eval$R.log)" | tee -a $L/eval.log
rm -f $W/p5_t$R.w
