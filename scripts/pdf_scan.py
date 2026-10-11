#!/usr/bin/env python3
"""Scan a player's positions for the 3x2 corner block (6 biggest tiles in a 3x2 block in a corner).
Canonical frame: biggest tile in cell 0 (top-left), block = rows 0-1 x cols 0-2 (cells 0,1,2,4,5,6).
Prints the frequency of the in-block order (which block cell holds the 1st..6th biggest tile).
usage: pdf_scan.py PLAYER [min_max_tile]"""
import json, sys, collections

def syms(g):
    # 8 symmetries of a 4x4 grid (list of rows)
    out = []
    a = [row[:] for row in g]
    for t in range(2):
        b = [list(r) for r in zip(*a)] if t else [r[:] for r in a]
        for fh in (0, 1):
            for fv in (0, 1):
                c = [r[::-1] if fh else r[:] for r in b]
                c = c[::-1] if fv else c
                out.append(c)
    return out

BLOCK = [0, 1, 2, 4, 5, 6]

def classify(g):
    """Return (order tuple, ranks) in the canonical frame or None."""
    flat = [v for r in g for v in r]
    srt = sorted(flat, reverse=True)
    top6 = srt[:6]
    if top6[5] == 0 or srt[6] >= top6[5] and srt[6] != 0 and srt[6] == top6[5]:
        pass
    for s in syms(g):
        f = [v for r in s for v in r]
        if f[0] != srt[0]: continue
        blk = [f[c] for c in BLOCK]
        if sorted(blk, reverse=True) != top6: continue
        # order: block cell index of the k-th biggest (ties broken by cell)
        order = tuple(sorted(range(6), key=lambda i: (-blk[i], i)))
        return order, f
    return None

def main():
    player = sys.argv[1]
    mn = int(sys.argv[2]) if len(sys.argv) > 2 else 16384
    cnt = collections.Counter(); n = nb = 0
    ex = {}
    for line in open('results/human_ds/analysis.jsonl'):
        if player not in line: continue
        a = json.loads(line)
        if a.get('player') != player: continue
        g = a['board']
        if max(max(r) for r in g) < mn: continue
        n += 1
        c = classify(g)
        if c is None: continue
        nb += 1
        cnt[c[0]] += 1
        ex.setdefault(c[0], (a['video'], a['ply'], c[1]))
    print(f"{player}: {n} positions with max >= {mn}, {nb} in a 3x2 corner block ({100*nb/max(n,1):.1f}%)")
    print("block cells: 0 1 2 / 4 5 6 (canonical: biggest in cell 0); order = cells of the 1st..6th biggest")
    for o, k in cnt.most_common(12):
        v, p, f = ex[o]
        print(f"  {k:6d} {100*k/nb:5.1f}%  order {[BLOCK[i] for i in o]}  e.g. {v} ply {p}: {f[0:4]} / {f[4:8]} / {f[8:12]} / {f[12:16]}")

if __name__ == '__main__':
    main()
