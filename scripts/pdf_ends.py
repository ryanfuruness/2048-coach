#!/usr/bin/env python3
"""For the block player's positions with the 6 biggest tiles in a 3x2 corner block: in the block's canonical frame
(block = cells 0,1,2,4,5,6), where is the smallest block tile (the end, where the next tile is built) and its rank;
and the largest free tile relative to it. usage: pdf_ends.py [player]"""
import json, sys, math, collections
sys.path.insert(0, 'scripts')
from pdf_detect import sym
BLOCK = (0, 1, 2, 4, 5, 6)
FREE = (3, 7, 8, 9, 10, 11, 12, 13, 14, 15)
player = sys.argv[1] if len(sys.argv) > 1 else 'd4Nf6Bg5'
ends = collections.Counter(); ranks = collections.Counter(); gapc = collections.Counter(); n = 0; nb = 0
uniq_end = collections.Counter()
for line in open('results/human_ds/analysis.jsonl'):
    if player not in line: continue
    a = json.loads(line)
    if a.get('player') != player: continue
    b = [int(math.log2(v)) if v else 0 for r in a['board'] for v in r]
    if max(b) < 14: continue
    n += 1
    top6 = sorted(b, reverse=True)[:6]
    for j in range(8):
        s = sym(b, j)
        blk = sorted((s[c] for c in BLOCK), reverse=True)
        if blk != top6: continue
        if max(s[c] for c in FREE) >= top6[5] and top6[5] in [s[c] for c in FREE]:
            pass
        e = min(BLOCK, key=lambda c: (s[c], -c))
        # is the smallest block tile unique?
        uniq_end[sum(1 for c in BLOCK if s[c] == s[e]) == 1] += 1
        ends[e] += 1; ranks[s[e]] += 1
        gapc[s[e] - max(s[c] for c in FREE)] += 1
        nb += 1
        break
print(f"{player}: {n} positions with max >= 16384, {nb} with the 6 biggest in a corner 3x2 block")
print("end cell (canonical):", dict(ends.most_common()))
print("end rank:", dict(sorted(ranks.items())))
print("end rank - largest free rank:", dict(sorted(gapc.items())))
print("unique smallest block tile:", dict(uniq_end))
