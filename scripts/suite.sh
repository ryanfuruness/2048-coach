#!/bin/bash
# Runs one search configuration over a suite of start positions and prints a summary line.
# usage: suite.sh NAME WEIGHTS STAGES POSITIONS GAMES THREADS [play options...]
set -e
cd "$(dirname "$0")/.."
NAME=$1 W=$2 ST=$3 POS=$4 N=$5 TH=$6
shift 6
mkdir -p results/suite
OUT=results/suite/$NAME.log
./build/play --weights "$W" --stages "$ST" --start "$POS" --games "$N" --threads "$TH" --quiet "$@" > "$OUT" 2>&1
python3 - "$OUT" "$NAME" <<'EOF'
import re, sys
t = open(sys.argv[1]).read()
mean = re.search(r"mean score (\d+) \(\+- (\d+)\)", t)
ms = re.search(r"avg ([\d.]+) ms/move", t)
rates = dict((int(a), float(b)) for a, b in re.findall(r"reached\s+(\d+):\s+([\d.]+)%", t))
print(f"{sys.argv[2]:28s} mean {mean.group(1):>8s} +- {mean.group(2):>6s}  "
      + "  ".join(f"{k}:{rates.get(k, 0):5.1f}%" for k in (16384, 32768, 65536))
      + f"  {ms.group(1)} ms/move")
EOF
