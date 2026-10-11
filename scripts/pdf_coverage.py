#!/usr/bin/env python3
"""Share of positions a block table covers (shape + caps, as blk::shape and lt::Index::sum), vs the detector
(src/block.h), on the human dataset by player group and max tile. Tables: ends 6/4, goal ranks RLO-RHI.
usage: pdf_coverage.py [RLO RHI]"""
import json, math, sys, collections
sys.path.insert(0, 'scripts')
from pdf_detect import sym
from pdf_detect2 import detect
RLO, RHI = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (3, 10)
BLOCK = (0, 1, 2, 4, 5, 6)
PATH = {6: [7, 10, 3, 11, 9, 14, 15, 8, 13, 12], 4: [8, 9, 12, 13, 10, 14, 11, 15, 7, 3]}

def covered(b):
    if max(b) > 15: return False
    for j in range(8):
        s = sym(b, j)
        for e in (6, 4):
            r = s[e]
            if not (RLO <= r <= RHI): continue
            if any(s[c] <= r for c in BLOCK if c != e): continue
            caps = [r - 1] * 9 + [r - 2]
            if all(s[c] <= cap for c, cap in zip(PATH[e], caps)): return True
    return False

c = collections.Counter(); d = collections.Counter(); n = collections.Counter(); both = collections.Counter()
for line in open('results/human_ds/analysis.jsonl'):
    a = json.loads(line)
    mx = max(max(r) for r in a['board'])
    if mx < 16384: continue
    b = [int(math.log2(v)) if v else 0 for r in a['board'] for v in r]
    k = ('block player' if a.get('player') == 'd4Nf6Bg5' else a.get('tier', '?'), min(mx, 65536))
    n[k] += 1
    cv = covered(b); dt = detect(b, 4, 6, 0)
    c[k] += cv; d[k] += dt; both[k] += cv and dt
for k in sorted(n):
    print(f"{k[0]:13s} max {k[1]:6d}: n {n[k]:6d}  table covers {100 * c[k] / n[k]:5.1f}%  detector {100 * d[k] / n[k]:5.1f}%  both {100 * both[k] / n[k]:5.1f}%")
