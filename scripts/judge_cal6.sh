#!/bin/bash
# cal6 rollout judge runner (real human positions): every legal move, 32 playouts, horizon 1000, full engine (tables),
# on chunks of a pool; one TSV per chunk (named by its first pool index; resumable: finished chunks are skipped).
# usage: judge_cal6.sh POOL.bin OUTDIR FIRST LAST CHUNK THREADS [extra rollout args, e.g. engine flags / --weights]
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
POOL=$1; OUT=$2; A=$3; B=$4; C=$5; T=$6; shift 6
mkdir -p $OUT
for ((s = A; s < B; s += C)); do
  n=$(( s + C > B ? B - s : C ))
  f=$OUT/$(basename $POOL .bin)_$(printf %05d $s).tsv
  [ -s $f ] && continue
  ./build/rollout --preset best --pool $POOL --skip $s --first $n --playouts 32 --horizon 1000 --threads $T \
    --seed $((s + 1)) "$@" --out $f.tmp > ${f%.tsv}.log 2>&1 && mv $f.tmp $f
done
echo done > $OUT/$(basename $POOL .bin)_${A}_${B}.done
