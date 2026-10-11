#!/bin/bash
# cal9 job queues on the research machine (resumable: finished outputs are skipped): fresh calibration data with the
# installed engine best_v6c, given explicitly (the instance has no weights/best.cfg).
#   study_cal9.sh truth   - P(32768) truth with v6c continuing from the real 16384-phase positions of cal6 (truth_r15,
#                           truth2_r15) and cal7 (truth4_r15, the held-out set): 32 playouts to 32768 or death
#   study_cal9.sh lapse   - late lapse games + clean checkpoint games of v6c (as study_cal7.sh lapse)
#   study_cal9.sh all     - both, in parallel
# env: T threads per job (20), ENGINE, G / GC games, SEED
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
T=${T:-20}
EX=${ENGINE:---weights weights/late2/best_v6c.w --leaf-view-max-sum 20480}
mkdir -p results/cal9
truth() {
  mkdir -p results/cal9/truth
  for g in cal6/truth_r15 cal6/truth2_r15 cal7/truth4_r15; do
    f=results/cal9/truth/$(basename $g).tsv
    ( [ -s $f ] || ./build/rollout --preset best $EX --pool results/$g.bin --playouts 32 --horizon 0 \
        --stop-rank 15 --moves engine --threads $T --seed 5 --out $f.tmp > ${f%.tsv}.log 2>&1 && mv $f.tmp $f ) &
  done
  wait
}
lapse() {
  CP=16384,18432,20480,22528,24576,26624,28672,30720,32768,36864,40960,45056,49152,53248,57344,61440
  G=${G:-800}; SEED=${SEED:-901}
  mkdir -p results/cal9/lapse
  run() {  # name policy
    local out=results/cal9/lapse/s${SEED}_$1
    [ -s $out.tsv ] && return
    ./build/messy --preset best $EX --policy "$2" --games $G --per-game 0 --record-switch --checkpoints $CP --values \
      --threads $T --seed $SEED --out $out.tmp > $out.log 2>&1 && mv $out.tmp.bin $out.bin && mv $out.tmp.tsv $out.tsv
  }
  run lapse16c "engine@16000-30000,soft:t=0.03@+300,engine" &
  run lapse32  "engine@33000-48000,soft:t=0.01@+300,engine" &
  run lapse32b "engine@33000-48000,soft:t=0.03@+600,engine" &
  CP=64,128,256,512,1024,2048,3072,4096,6144,8192,10240,12288,14336,$CP
  G=${GC:-800}; run cleancp "engine" &
  wait
}
case $1 in
truth) truth ;;
lapse) lapse ;;
all) truth & lapse & wait ;;
esac
echo done > results/cal9/$1.done
