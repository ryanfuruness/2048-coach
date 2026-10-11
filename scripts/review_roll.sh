#!/bin/bash
# Workstream review: rollout truth for the review study (instance, ~/2048_review).
#  E: engine continuing (best_v6b + tables), all moves, 32 CRN playouts, horizon 1000 -> results/review/roll_e_*.tsv
#     (4 chunks, so partial results survive)
#  P: human move model continuing at the position's playout skill until the next milestone (stop rank) or death,
#     all moves, 64 CRN playouts -> results/review/roll_p/gNNN.tsv
# usage: scripts/review_roll.sh E THREADS | P PARALLEL
ulimit -s unlimited
W="--weights weights/best_v6b.w"
if [ "$1" = E ]; then
  T=${2:-36}
  N=$(( $(stat -c %s results/review/pool.bin) / 8 ))
  C=$(( (N + 3) / 4 ))
  for k in 0 1 2 3; do
    ./build/rollout --preset best $W --pool results/review/pool.bin --skip $((k * C)) --first $C --moves all \
      --playouts 32 --horizon 1000 --threads $T --seed 4242 --out results/review/roll_e_$k.tsv 2> results/review/roll_e_$k.err
  done
  echo done > results/review/roll_e.done
else
  P=${2:-14}
  mkdir -p results/review/roll_p
  tail -n +2 results/review/pgroups.tsv | cut -f1-3 | xargs -P $P -L 1 sh -c \
    './build/rollout --preset best-notables '"$W"' --pool results/review/pgroups/$0.bin --moves all --playouts 64 \
       --horizon 0 --stop-rank $2 --human $1 --threads 1 --seed 777 --out results/review/roll_p/$0.tsv 2> results/review/roll_p/$0.err'
  echo done > results/review/roll_p.done
fi
