#!/bin/bash
# cal7 job queues on the research machine (resumable: finished outputs are skipped). The engine is given explicitly
# (the instance has no weights/best.cfg): ENGINE="--weights weights/best_v6b.w" by default.
#   study_cal7.sh lowend  - the low-end measurement: every legal move of results/cal7/lowend.bin (200 top-stage human
#                           decisions, scripts/judge_lowend_select.py), 4 replicate runs x 32 playouts (seeds R1-R4;
#                           common random numbers across the moves within a run), horizon 1000, full engine
#   study_cal7.sh truth   - odds truth with the new engine continuing: P(32768) from cal6's 16384-phase real positions
#                           (truth_r15, truth2_r15), 32 playouts to 32768 or death
#   study_cal7.sh lapse   - late lapse games + clean checkpoint games of the new engine (as study_cal6.sh lapse)
# env: T threads per job (12), ENGINE, G / GC games, SEED
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
T=${T:-12}
EX=${ENGINE:---weights weights/best_v6b.w}
mkdir -p results/cal7
case $1 in
lowend)
  for r in 1 2 3 4; do
    f=results/cal7/lowend_r$r.tsv
    ( [ -s $f ] || ./build/rollout --preset best $EX --pool results/cal7/lowend.bin --playouts 32 --horizon 1000 \
        --moves all --threads $T --seed $((1000 + r)) --out $f.tmp > ${f%.tsv}.log 2>&1 && mv $f.tmp $f ) &
  done
  wait ;;
truth)
  mkdir -p results/cal7/truth
  for g in truth_r15 truth2_r15; do
    f=results/cal7/truth/$g.tsv
    ( [ -s $f ] || ./build/rollout --preset best $EX --pool results/cal6/$g.bin --playouts 32 --horizon 0 \
        --stop-rank 15 --moves engine --threads $T --seed 5 --out $f.tmp > ${f%.tsv}.log 2>&1 && mv $f.tmp $f ) &
  done
  wait ;;
lapse)
  CP=16384,18432,20480,22528,24576,26624,28672,30720,32768,36864,40960,45056,49152,53248,57344,61440
  G=${G:-800}; SEED=${SEED:-701}
  mkdir -p results/cal7/lapse
  run() {  # name policy
    local out=results/cal7/lapse/s${SEED}_$1
    [ -s $out.tsv ] && return
    ./build/messy --preset best $EX --policy "$2" --games $G --per-game 0 --record-switch --checkpoints $CP --values \
      --threads $T --seed $SEED --out $out.tmp > $out.log 2>&1 && mv $out.tmp.bin $out.bin && mv $out.tmp.tsv $out.tsv
  }
  run lapse16c "engine@16000-30000,soft:t=0.03@+300,engine" &
  run lapse32  "engine@33000-48000,soft:t=0.01@+300,engine" &
  run lapse32b "engine@33000-48000,soft:t=0.03@+600,engine" &
  CP=64,128,256,512,1024,2048,3072,4096,6144,8192,10240,12288,14336,$CP
  G=${GC:-1000}; run cleancp "engine" &
  wait ;;
esac
echo done > results/cal7/$1.done
