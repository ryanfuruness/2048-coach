#!/bin/bash
# Serving check: latency per analysis (single thread) at the engine's own depth and deeper, peak memory, and the
# native (BMI2/PEXT) build against a portable x86-64-v2 build (the code path used on ARM/WASM/Zen 2).
#   scripts/serving_bench.sh POSITIONS.txt   (one board per line; default: 200 pilot positions)
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
J=${CLAUDE_JOB_DIR:-/tmp}/tmp
mkdir -p $J
POS=${1:-$J/serving_pos.txt}
if [ ! -s "$POS" ]; then
  for f in results/calib/pilot_clean.tsv results/calib/p2_soft03.tsv results/calib/p2_soft003.tsv; do
    awk -F'\t' 'NR==1{for(i=1;i<=NF;i++) if($i=="board") b=i} NR>1 {print $b}' $f | head -70
  done > $POS
fi
[ -x $J/analyze_portable ] || g++ -O3 -march=x86-64-v2 -std=c++17 -pthread src/analyze.cpp src/board.cpp -o $J/analyze_portable
stats() {  # jsonl -> mean / p50 / p90 / max ms
  python3 -c "
import json,sys
ms=sorted(json.loads(l)['ms'] for l in open('$1') if '\"ms\"' in l)
n=len(ms); print(f'{n} positions: mean {sum(ms)/n:.1f} ms, p50 {ms[n//2]:.1f}, p90 {ms[int(.9*n)]:.1f}, max {ms[-1]:.1f}')"
}
for preset in best-notables best; do
  for d in 0 4 5; do
    out=$J/serve_${preset}_d$d.jsonl
    /usr/bin/time -f "%M" -o $J/serve_rss.txt ./build/analyze --preset $preset --stdin --depth $d < $POS > $out 2>/dev/null
    echo "$preset depth $([ $d = 0 ] && echo engine || echo $d): $(stats $out), peak RSS $(( $(cat $J/serve_rss.txt) / 1024 )) MB"
  done
done
out=$J/serve_portable.jsonl
$J/analyze_portable --preset best-notables --stdin < $POS > $out 2>/dev/null
echo "portable build (no PEXT), best-notables depth engine: $(stats $out)"
