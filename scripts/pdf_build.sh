#!/bin/bash
# Solve the exact block tables (src/block.h: 3x2 block locked, the next tile built next to its end) on the instance.
#   cd ~/2048_pdf && nohup scripts/pdf_build.sh [threads] > results/pdf/build.log 2>&1 &
T=${1:-32}
set -e
mkdir -p weights/pdf results/pdf build
g++ -O3 -march=native -std=c++17 -pthread src/block_tool.cpp src/board.cpp -o build/block_tool
for e in 6 4; do
  for r in 3 4 5 6 7 8 9 10; do
    f=weights/pdf/block_e${e}_r${r}.lt
    [ -f $f.done ] && continue
    echo "== end $e rank $r: $(date)"
    ./build/layered $(./build/block_tool spec $e $r) --out $f --threads $T > results/pdf/solve_e${e}_r${r}.log 2>&1
    grep -E "sub-game" results/pdf/solve_e${e}_r${r}.log
    tail -1 results/pdf/solve_e${e}_r${r}.log
    touch $f.done
  done
done
echo "build done: $(date)"
