#!/bin/bash
# After queue11: second-half candidates as stage 3 of best_v5, whole phase from 700 real starts (s6 = 64.1% at 3,4,4,4,4):
# tight-board 2-ply networks (exp_tight2ply, seed 6 like s6), lambda/horizon variants (exp_lambda, seed 6).
cd "$(dirname "$0")/.."
L=results/expq12
mkdir -p $L
[ -n "$QUEUE12_INLINE" ] || while ps -eo args | grep -q "^/bin/bash scripts/exp_queue11.sh"; do sleep 60; done
ST5="sum:20480/14,24576,28672,36864"
EGO="--corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
LT="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5 --lt-view"
VIEW="--leaf-view 14 6 --leaf-view-max-sum 24576"
phase_sh() {  # name second-half-weights (2-stage file, stage 0)
  local n=$1
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && return
  [ -f $2 ] || { echo "$n: missing $2" >> $L/eval.log; return; }
  python3 scripts/splice_stage.py weights/best_v5.w 3 $2 0 $L/p5.w > /dev/null
  ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
    ./build/play --weights $L/p5.w --stages "$ST5" --start weights/exps1/pool700.bin --games 700 --threads 18 --seed 999 \
      --quantize --depth 4 --stage-depth 3,4,4,4,4 --stop-sum 36864 $EGO $LT $VIEW > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(grep -o 'avg [0-9.]* ms/move' $L/$n.log)" | tee -a $L/eval.log
  rm -f $L/p5.w
}
phase_sh t2_m4 weights/expt2/m4.w
phase_sh t2_m3 weights/expt2/m3.w
while ps -eo args | grep -q "^/bin/bash scripts/exp_lambda.sh"; do sleep 60; done
phase_sh lam_l80 weights/explam/l80.w
phase_sh lam_l95 weights/explam/l95.w
# layered tables below --lt-min 0.5: does the table's (sub-game-optimal) move beat the network's search there too?
# (--lt-min is a global option, so the k5r9 group gets the same threshold)
# (the realized success after a k5r10 handover, 76.6%, exceeds the table's P, 0.66: the sub-game's locked chain and caps
# cost ~10 points, so the search may also beat the table at moderate P -> try a higher threshold too)
for m in 0.05 0.8; do
  n=ltmin$m
  if ! { [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log; }; then
    LTM="${LT/--lt-min 0.5/--lt-min $m}"
    ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
      ./build/play --weights weights/best_v5.w --stages "$ST5" --start weights/exps1/pool700.bin --games 700 --threads 18 --seed 999 \
        --quantize --depth 4 --stage-depth 3,4,4,4,4 --stop-sum 36864 $EGO $LTM $VIEW > $L/$n.log 2>&1 )
    echo "$n: $(grep 'tile sum' $L/$n.log)  $(grep -o 'avg [0-9.]* ms/move' $L/$n.log)  $(grep 'layered table moves' $L/$n.log)" | tee -a $L/eval.log
  fi
done
# build-up deaths (sum < 31744) are the gap to macroxue (we 15.7%, they 2.8% at d8 / 5.8% at d5; stage B 6.6% vs 1.0%):
# does deep search in stage B (min depth 5, up to 8 within 200k leaves) cut them? (best_v5 at 3,4,4,4,4: 64.1%, stage B 6.6%)
n=deepB5
if ! { [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log; }; then
  ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
    ./build/play --weights weights/best_v5.w --stages "$ST5" --start weights/exps1/pool700.bin --games 700 --threads 18 --seed 999 \
      --quantize --depth 4 --stage-depth 3,4,8,4,4 --min-depth 5 --budget 200000 --stop-sum 36864 $EGO $LT $VIEW > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(grep -o 'avg [0-9.]* ms/move' $L/$n.log)" | tee -a $L/eval.log
  scripts/death_bins.sh $L/$n.log | tee -a $L/eval.log
fi
# snake-order leaf penalty (play --snake-pen W K LO HI; macroxue's inversion penalty along our snake path, first 8 cells)
# for stage B and the second half's build-up (view tile sum 24576-31744): the network seems to overvalue broken snakes
for w in 1 4 16; do
  n=pen$w
  if ! { [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log; }; then
    ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
      ./build/play --weights weights/best_v5.w --stages "$ST5" --start weights/exps1/pool700.bin --games 700 --threads 18 --seed 999 \
        --quantize --depth 4 --stage-depth 3,4,4,4,4 --stop-sum 36864 $EGO $LT $VIEW --snake-pen $w 8 24576 31744 > $L/$n.log 2>&1 )
    echo "$n: $(grep 'tile sum' $L/$n.log)  $(scripts/death_bins.sh $L/$n.log | cut -c24-)" | tee -a $L/eval.log
  fi
done
# early game with the corner lock from the 8192 on (s0cpu fine-tuned on the GPU with lock 13 + k>=6 tables, +1M/+2M;
# 1-ply 16384 rate 74.5/76.6% vs s0cpu 83.5% unlocked), from scratch to sum 20480 (best_v5: 95.71% reach 16384)
early() {  # name weights [options]
  local n=$1 w=$2; shift 2
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && return
  ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
    ./build/play --weights $w --stages "$ST5" --games 1400 --threads 18 --seed 4321 --quantize --depth 4 \
      --stage-depth 3,4,4,4,4 --stop-sum 20480 $EGO $LT $VIEW "$@" > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(grep 'reached  16384' $L/$n.log)  $(grep 'endgame table moves' $L/$n.log)" | tee -a $L/eval.log
}
early early_ref weights/best_v5.w
for v in l1 l2; do
  python3 scripts/splice_stage.py weights/best_v5.w 0 weights/expel/$v.w 0 $L/p5e.w > /dev/null
  early early_lock_$v $L/p5e.w --corner-lock 13
  rm -f $L/p5e.w
done
# side-branch training (train --branch P L): CPU second half as exp_cpu's c4 (TC, OI start, 4M) plus branches from a random
# non-chosen move (10% of steps, 8 greedy moves, own TD(lambda) sweep): trains the off-policy positions a search compares
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
mkdir -p weights/expbr
if [ ! -f weights/expbr/br10.w ]; then
  ./build/train --load weights/expcpu/start.w --stages "sum:36864" --train-stage 0 --stop-at-boundary --tc --alpha 1.0 \
    --lambda 0.5 --corner-lock 14 --endgame-dir weights/endgame_big --endgame-min 0.5 --endgame-full 2 \
    --pool weights/v11c/pool2mix.bin --pool-last $NPOOL --episodes 4000000 --threads 18 --log 500000 --branch 0.1 8 \
    --save weights/expbr/br10.w.part > $L/br10_train.log 2>&1 && mv weights/expbr/br10.w.part weights/expbr/br10.w
  echo "br10 train: $(grep 'games  avg' $L/br10_train.log | tail -n 1)" >> $L/eval.log
fi
EGOV="--corner-lock 14 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame_big --endgame-nosave"
python3 scripts/splice_stage.py weights/v11c/final.w 2 weights/expbr/br10.w 0 $L/v11.w > /dev/null
for d in 3 4; do
  [ -f $L/br10_d$d.log ] && grep -q "tile sum" $L/br10_d$d.log && continue
  ( ulimit -s unlimited; export MALLOC_ARENA_MAX=2
    ./build/play --weights $L/v11.w --stages "sum:20480/14,28672,36864" --start weights/exps/pool600.bin --games 600 \
      --threads 18 --seed 31 --quantize --depth $d --stop-sum 36864 $EGOV > $L/br10_d$d.log 2>&1 )
  echo "br10 d$d: $(grep 'tile sum' $L/br10_d$d.log)   (CPU c4 without branches: d3 56.17, d4 59.50)" | tee -a $L/eval.log
done
rm -f $L/v11.w
phase_sh br10 weights/expbr/br10.w
# the same on the GPU (train --branch in gpu_train; s6 recipe, seed 6, 4M): wait for it
while ps -eo args | grep -q "^./build/gpu_train.*--branch"; do sleep 60; done
phase_sh gbr10 weights/expbr/gbr10.w
phase_sh cpu_c4 weights/expcpu/s2.w
# RAW NETWORK QUALITY: without tables our networks convert 3.4% (d1) / 11.0% (d2) / 19.4% (d3) of the whole phase; Guei
# et al.'s table-free network: 35.4 / 59.8 / 68.9%. Our late networks are trained with the k>=6 tables in the loop and never
# learn table positions. Train the second half WITHOUT tables (CPU, TC, OI start.w, as c4 otherwise), snapshots 4M and 8M;
# evaluate raw (no tables, d2/d3, as stage 3 of best_v5) and in the full player (tables, d4) vs s6.
mkdir -p weights/expnt
NTC="--stages sum:36864 --train-stage 0 --stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --corner-lock 14 \
  --pool weights/v11c/pool2mix.bin --pool-last $(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 )) --threads 18 --log 500000"
if [ ! -f weights/expnt/n4.w ]; then
  ./build/train --load weights/expcpu/start.w $NTC --episodes 4000000 --save weights/expnt/n4.w.part \
    --checkpoint weights/expnt/n4.ckpt > $L/n4_train.log 2>&1 && mv weights/expnt/n4.w.part weights/expnt/n4.w
  echo "n4 train: $(grep 'games  avg' $L/n4_train.log | tail -n 1)" >> $L/eval.log
fi
if [ ! -f weights/expnt/n8.w ]; then
  ./build/train --load weights/expcpu/start.w --resume weights/expnt/n4.ckpt $NTC --episodes 4000000 \
    --save weights/expnt/n8.w.part > $L/n8_train.log 2>&1 && mv weights/expnt/n8.w.part weights/expnt/n8.w
  echo "n8 train: $(grep 'games  avg' $L/n8_train.log | tail -n 1)" >> $L/eval.log
fi
notab() {  # name second-half-weights depth: whole phase without tables, network as stage 3 of best_v5
  local n=$1 d=$3
  [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && return
  python3 scripts/splice_stage.py weights/best_v5.w 3 $2 0 $L/p5n.w > /dev/null
  ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
    ./build/play --weights $L/p5n.w --stages "$ST5" --start weights/exps1/pool700.bin --games 700 --threads 18 --seed 999 \
      --quantize --depth $d --stage-depth 3,$d,$d,$d,$d --stop-sum 36864 --corner-lock 14 --root-downgrade 15 \
      --leaf-view 14 6 --leaf-view-max-sum 24576 > $L/$n.log 2>&1 )
  echo "$n: $(grep 'tile sum' $L/$n.log)  $(scripts/death_bins.sh $L/$n.log | cut -c24-)" | tee -a $L/eval.log
  rm -f $L/p5n.w
}
# table-free fine-tuning instead of table-free training from OI (which does not take off quickly): resume the CPU c12
# checkpoint (TC 12M with tables) for 4M episodes without tables
if [ ! -f weights/expnt/c12nt.w ]; then
  ./build/train --load weights/expcpu/start.w --resume weights/expcl/c12.ckpt $NTC --episodes 4000000 \
    --save weights/expnt/c12nt.w.part > $L/c12nt_train.log 2>&1 && mv weights/expnt/c12nt.w.part weights/expnt/c12nt.w
  echo "c12nt train: $(grep 'games  avg' $L/c12nt_train.log | tail -n 1)" >> $L/eval.log
fi
notab s6_notab_d2 weights/expseed/s6.w 2
while ps -eo args | grep -q "^/bin/bash scripts/exp_e4nt.sh"; do sleep 60; done   # GPU table-free fine-tune of e4
for v in e4nt2 e4nt4 g8nt g12nt; do   # (c12nt collapsed: len 210 without tables) g*nt: table-free from OI on the GPU
  [ -f weights/expnt/$v.w ] || continue
  notab ${v}_notab_d2 weights/expnt/$v.w 2
  phase_sh $v weights/expnt/$v.w
done
# Guei-style single table-free network for the whole 16384 phase (GPU, exp_whole_nt.sh): 3-stage player [s0cpu, w*, OI],
# with tables at play time, with and without the s0cpu leaf view for the first half
while ps -eo args | grep -q "^/bin/bash scripts/exp_whole_nt.sh"; do sleep 60; done
for v in; do   # whole-phase table-free nets never reached 32768 (w4, w8: 0% stage exit): skipped
  [ -f weights/expwh/$v.w ] || continue
  for lv in view noview; do
    n=whole_${v}_$lv
    [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log && continue
    VV=""; [ $lv = view ] && VV="$VIEW"
    ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
      ./build/play --weights weights/expwh/$v.w --stages "sum:20480/14,36864" --start weights/exps1/pool700.bin --games 700 \
        --threads 18 --seed 999 --quantize --depth 4 --stage-depth 3,4,4 --stop-sum 36864 $EGO $LT $VV > $L/$n.log 2>&1 )
    echo "$n: $(grep 'tile sum' $L/$n.log)  $(scripts/death_bins.sh $L/$n.log | cut -c24-)" | tee -a $L/eval.log
  done
done
# CPU-trained second halves with tables (c12 = TC 12M; c12 + TD 0.01 for 4M: +2 at d4 in the v11c protocol)
phase_sh cpu_c12 weights/expcl/c12.w
phase_sh cpu_c12td01 weights/expcl/c12td0.01.w
# table-free stage B (GPU, exp_gntb.sh) + table-free second half g8nt as stages 2+3 of best_v5
while ps -eo args | grep -q "^/bin/bash scripts/exp_gntb"; do sleep 60; done
for b in b8nt bx16nt; do
  [ -f weights/expnt/$b.w ] || continue
  n=combo_$b
  if ! { [ -f $L/$n.log ] && grep -q "tile sum" $L/$n.log; }; then
    # table-free stage B with best_v5's own second half (s6): the table-free second half g8nt lost 2.5 points in the full
    # player (61.6 vs 64.1) despite far better raw play (no tables, d2: 29.9 vs 11.0)
    python3 scripts/splice_stage.py weights/best_v5.w 2 weights/expnt/$b.w 0 $L/c2.w > /dev/null
    ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
      ./build/play --weights $L/c2.w --stages "$ST5" --start weights/exps1/pool700.bin --games 700 --threads 18 --seed 999 \
        --quantize --depth 4 --stage-depth 3,4,4,4,4 --stop-sum 36864 $EGO $LT $VIEW > $L/$n.log 2>&1 )
    echo "$n: $(grep 'tile sum' $L/$n.log)  $(scripts/death_bins.sh $L/$n.log | cut -c24-)" | tee -a $L/eval.log
    ( ulimit -s unlimited; ulimit -v 5500000; export MALLOC_ARENA_MAX=2
      ./build/play --weights $L/c2.w --stages "$ST5" --start weights/exps1/pool700.bin --games 700 --threads 18 --seed 999 \
        --quantize --depth 2 --stage-depth 3,2,2,2,2 --stop-sum 36864 --corner-lock 14 --root-downgrade 15 \
        --leaf-view 14 6 --leaf-view-max-sum 24576 > $L/${n}_notab_d2.log 2>&1 )
    echo "${n}_notab_d2: $(grep 'tile sum' $L/${n}_notab_d2.log)   (best_v5 networks: 11.00%)" | tee -a $L/eval.log
    rm -f $L/c2.w
  fi
done
# exact sub-game bootstrapping (train --lt-boot C0 C1 MINP): the afterstate before an episode's first k5r10 state gets the
# target C0 + C1 * P(table) instead of the lambda-return through the network's own post-handover values. Calibrate C0/C1
# with the trained c12 network in the training setup (k6 tables + k5r10 in the loop), then train as c4 (+ k5r10 in loop).
NPOOL=$(( $(stat -c %s weights/v11c/pool2mix.bin) / 8 ))
LT10="--endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --lt-min 0.5"
TRN="--stages sum:36864 --train-stage 0 --stop-at-boundary --lambda 0.5 --corner-lock 14 --endgame-dir weights/endgame_big \
  --endgame-min 0.5 --endgame-full 2 $LT10 --pool weights/v11c/pool2mix.bin --pool-last $NPOOL --threads 18"
if [ ! -f $L/calib.log ] || ! grep -q "lt-calib" $L/calib.log; then
  ./build/train --load weights/expcl/c12.w $TRN --no-learn --lt-calib --episodes 60000 --log 20000 > $L/calib.log 2>&1
  echo "calib: $(grep lt-calib $L/calib.log)" >> $L/eval.log
fi
C0=$(grep -o "return ~ [-0-9]* + [-0-9]* \* P" $L/calib.log | awk '{print $3}')
C1=$(grep -o "return ~ [-0-9]* + [-0-9]* \* P" $L/calib.log | awk '{print $5}')
for v in boot k5loop; do
  [ -f weights/expbr/$v.w ] && continue
  extra=""; [ $v = boot ] && extra="--lt-boot $C0 $C1 0"
  ./build/train --load weights/expcpu/start.w $TRN --tc --alpha 1.0 --episodes 4000000 --log 500000 $extra \
    --save weights/expbr/$v.w.part > $L/${v}_train.log 2>&1 && mv weights/expbr/$v.w.part weights/expbr/$v.w
  echo "$v train ($extra): $(grep 'games  avg' $L/${v}_train.log | tail -n 1)" >> $L/eval.log
done
phase_sh ltboot weights/expbr/boot.w
phase_sh k5loop weights/expbr/k5loop.w
echo "queue12 done" >> $L/eval.log
