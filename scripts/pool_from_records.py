#!/usr/bin/env python3
"""Training-start pools from recorded benchmark games: every position where the tile sum first passes one of the
given thresholds (e.g. 28672,29184,...), optionally only positions holding a given rank. Writes uint64 boards.

usage: pool_from_records.py OUT.bin LO HI STEP REQRANK DIR [DIR...]
  thresholds LO, LO+STEP, ... < HI; REQRANK: required max rank (e.g. 14 = max tile 16384), 0 = any
"""
import sys, glob, struct, random
sys.path.insert(0, 'scripts')
from analyze_games import apply, B32, DIRS
out_path, lo, hi, step, req = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
thr = list(range(lo, hi, step))
out = []
for d in sys.argv[6:]:
    for f in sorted(glob.glob(d + '/games*.txt')):
        for line in open(f):
            parts = line.split(); init = parts[3]; moves = parts[4] if len(parts) > 4 else ""
            b = [B32.index(ch) for ch in init]
            s = sum((1 << x) for x in b if x)
            k = 0
            while k < len(thr) and thr[k] <= s: k += 1
            for i in range(0, len(moves), 3):
                dd, cell, v = DIRS[moves[i]], int(moves[i+1], 16), 1 if moves[i+2] == "2" else 2
                b, g = apply(b, dd); b[cell] = v
                s += 2 * v
                if k < len(thr) and s >= thr[k]:
                    while k < len(thr) and thr[k] <= s: k += 1
                    if req == 0 or max(b) == req:
                        x = 0
                        for c in range(16): x |= min(b[c], 15) << (4 * c)
                        out.append(x)
                if k >= len(thr) or s >= hi: break
random.seed(5)
random.shuffle(out)
with open(out_path, 'wb') as fo:
    for x in out: fo.write(struct.pack('<Q', x))
print(len(out), "positions ->", out_path)
