#!/bin/bash
# cal6 job queues on the research machine (each queue runs its jobs in order with its own thread count; finished
# outputs are skipped, so a queue can be restarted).
#   study_cal6.sh expert   - 400 more expert decisions (xexpert: 250 disputes > 10% + 150 claims 2-10%, 16384+) and
#                            the old 150 disputes + 60 controls again at H=1000 (all moves, 32 playouts, full engine)
#   study_cal6.sh truth    - odds ground truth on real positions: 32 engine playouts from each position to 16384
#                            (truth_r14: tiles <= 8192) or 32768 (truth_r15: 16384 positions), or death
#   study_cal6.sh personal - softmax players (t = 0.003 / 0.01 / 0.03 / 0.1) from real positions to 4x their tile
#   study_cal6.sh lapse    - late lapse games for the odds fit (engine, a human-like lapse in the 16384 / 32768
#                            phase, engine again), recorded at tile-sum checkpoints (G=1500 each), then GC=2000 clean
#                            engine games at checkpoints (base rates)
# env: T threads (16), W weights (default: the preset's), ENGINE extra engine flags; outputs under results/cal6/
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
T=${T:-16}
EX=${ENGINE:-}
case $1 in
expert)
  until [ -f results/cal6/j1200/judge1200_0_400.done ]; do sleep 30; done
  scripts/judge_cal6.sh results/cal6/xexpert.bin results/cal6/jx 0 400 25 $T $EX
  scripts/judge_cal6.sh results/disputes/expert.bin results/cal6/jold 0 210 30 $T $EX ;;
truth)
  until [ -f results/cal6/j1200/judge1200_400_800.done ]; do sleep 30; done
  mkdir -p results/cal6/truth
  for g in r14 r15; do
    f=results/cal6/truth/truth_$g.tsv
    [ -s $f ] || ./build/rollout --preset best $EX --pool results/cal6/truth_$g.bin --playouts 32 --horizon 0 \
      --stop-rank ${g#r} --moves engine --threads $T --seed 5 --out $f.tmp > ${f%.tsv}.log 2>&1 && mv $f.tmp $f
  done ;;
personal)
  until [ -f results/cal6/j1200/judge1200_800_1200.done ]; do sleep 30; done
  mkdir -p results/cal6/pers
  for t in 0.01 0.003 0.03 0.1; do
    for r in 9 10 11 12 13 14 15; do
      f=results/cal6/pers/soft${t}_r$r.tsv
      [ -s $f ] || ./build/rollout --preset best-notables $EX --pool results/cal6/pers_r$r.bin --playouts 32 \
        --horizon 0 --stop-rank $r --moves engine --soft $t --threads $T --seed 9 --out $f.tmp > ${f%.tsv}.log 2>&1 \
        && mv $f.tmp $f
    done
  done ;;
lapse)
  CP=16384,18432,20480,22528,24576,26624,28672,30720,32768,36864,40960,45056,49152,53248,57344,61440
  G=${G:-1500}; SEED=${SEED:-601}
  mkdir -p results/cal6/lapse
  run() {  # name policy
    local out=results/cal6/lapse/s${SEED}_$1
    [ -s $out.tsv ] && return
    ./build/messy --preset best $EX --policy "$2" --games $G --per-game 0 --record-switch --checkpoints $CP --values \
      --threads $T --seed $SEED --out $out.tmp > $out.log 2>&1 && mv $out.tmp.bin $out.bin && mv $out.tmp.tsv $out.tsv
  }
  run lapse16c "engine@16000-30000,soft:t=0.03@+300,engine"
  run lapse32  "engine@33000-48000,soft:t=0.01@+300,engine"
  run lapse32b "engine@33000-48000,soft:t=0.03@+600,engine"
  # clean engine games at checkpoints over the whole game (base rates P(reach T | alive at sum S), as study_calib3)
  CP=64,128,256,512,1024,2048,3072,4096,6144,8192,10240,12288,14336,$CP
  G=${GC:-2000}; run cleancp "engine" ;;
esac
echo done > results/cal6/$1.done
