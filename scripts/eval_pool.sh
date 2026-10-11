#!/bin/bash
# Conditional strength from a pool of start positions (real game rules, so 65536 counts).
# usage: eval_pool.sh WEIGHTS STAGES POOL GAMES THREADS OUT [play options...]
# Samples GAMES positions spread evenly over the last part of POOL, plays each to the
# end, and prints the summary (tile reach rates are conditional on the start position).
set -e
cd "$(dirname "$0")/.."
W=$1 ST=$2 POOL=$3 N=$4 TH=$5 OUT=$6
shift 6
SAMPLE=$(mktemp "${TMPDIR:-/tmp}/pool.XXXXXX")
python3 - "$POOL" "$N" "$SAMPLE" <<'EOF'
import sys
data = open(sys.argv[1], 'rb').read()
n, k = len(data) // 8, int(sys.argv[2])
tail = min(n, 20 * k)  # the most recent positions come from the strongest policy
start = n - tail
idx = [start + (i * tail) // k for i in range(min(k, tail))]
open(sys.argv[3], 'wb').write(b''.join(data[8 * i:8 * i + 8] for i in idx))
EOF
./build/play --weights "$W" ${ST:+--stages "$ST"} --start "$SAMPLE" --games "$N" --threads "$TH" "$@" > "$OUT" 2>&1
rm -f "$SAMPLE"
grep -E "mean score|ms/move|reached" "$OUT"
