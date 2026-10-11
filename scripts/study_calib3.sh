#!/bin/bash
# Calibration study, part 3: clean engine games recorded at fixed tile-sum checkpoints (each game counts once per stage
# it reaches: unbiased base rates P(reach T | alive at sum S)), after part 2 and the horizon judge (one table-loading
# process at a time on the laptop).
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
G=${G:-500}; T=${T:-$(nproc)}; SEED=${SEED:-301}
until grep -q "p2_soft03_h1000.tsv:" results/judge/horizon.out 2>/dev/null; do sleep 60; done
CP=64,128,256,512,1024,2048,3072,4096,6144,8192,10240,12288,14336,16384,18432,20480,22528,24576,26624,28672,30720,32768,36864,40960,45056,49152,53248,57344,61440
out=results/calib/s${SEED}_cleancp
[ -s $out.tsv ] || ./build/messy --preset best --policy engine --games $G --per-game 0 --checkpoints $CP --values \
  --threads $T --seed $SEED --out $out > $out.log 2>&1
echo done > results/calib/s${SEED}_cleancp.done
