#!/bin/bash
# Workstream mx: run the macroxue judge driver (~/macroxue/judge on the research machine, see
# /home/ryanf/projects/2048-macroxue-judge/README.md) on a task file in N parallel single-threaded shards (the lookup
# tables are mmap'd from ~/macroxue and shared between the processes).
# usage (on the instance, in ~/2048_mx): scripts/mx_run.sh TASKS OUT N [judge options, e.g. --stop-sum 36864]
TASKS=$(readlink -f "$1"); OUT=$(readlink -f "$2"); N=$3; shift 3
cd ~/macroxue || exit 1
for k in $(seq 0 $((N - 1))); do
  ./judge --shard $k $N "$@" < "$TASKS" > "$OUT.part$k" 2> "$OUT.err$k" &
done
wait
cat "$OUT".part* | grep -aoE '(E|P)	.*' > "$OUT" && rm -f "$OUT".part* && echo done > "$OUT.done"
