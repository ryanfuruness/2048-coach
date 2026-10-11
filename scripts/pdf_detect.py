#!/usr/bin/env python3
"""Prototype of the block-formation detector (workstream pdf, 2026-10-07) and its precision / recall on the labeled
expert positions of workstream mx (results/mx/positions.tsv: player d4Nf6Bg5 = the PDF player, others = snake experts).
Boards are 16 ranks, cell 0 = top-left, row-major."""
import sys, collections

def sym(b, j):
    g = [b[4 * r:4 * r + 4] for r in range(4)]
    if j >= 4: g = [list(x) for x in zip(*g)]
    if j & 1: g = [r[::-1] for r in g]          # flip_h
    if j & 2: g = g[::-1]                       # flip_v
    return [v for r in g for v in r]

def move(b, d):
    """d: 0 up, 1 right, 2 down, 3 left; returns new board (no spawn)."""
    g = [b[4 * r:4 * r + 4] for r in range(4)]
    def slide(line):
        t = [x for x in line if x]; out = []; i = 0
        while i < len(t):
            if i + 1 < len(t) and t[i] == t[i + 1]: out.append(t[i] + 1); i += 2
            else: out.append(t[i]); i += 1
        return out + [0] * (4 - len(out))
    if d == 3: g = [slide(r) for r in g]
    elif d == 1: g = [slide(r[::-1])[::-1] for r in g]
    elif d == 0:
        cols = [slide([g[r][c] for r in range(4)]) for c in range(4)]; g = [[cols[c][r] for c in range(4)] for r in range(4)]
    else:
        cols = [slide([g[r][c] for r in range(4)][::-1])[::-1] for c in range(4)]; g = [[cols[c][r] for c in range(4)] for r in range(4)]
    return [v for r in g for v in r]

BLOCK6 = (0, 1, 2, 4, 5, 6)
CORE4 = (0, 1, 4, 5)

def top(b, k):
    return sorted(b, reverse=True)[:k]

def in_shape(b, cells, k, min_rank):
    """In some frame: cell 0 holds the max, the k biggest tiles (multiset) sit in `cells` (k = len(cells)),
    and the k-th biggest has rank >= min_rank."""
    tk = top(b, k)
    if tk[-1] < min_rank: return False
    for j in range(8):
        s = sym(b, j)
        if s[0] != tk[0]: continue
        if sorted((s[c] for c in cells), reverse=True) == tk: return True
    return False

def detect(b, variant):
    mx = max(b)
    if variant == 'block6':        # 6 biggest in the 3x2 corner block, 6th >= max/1024
        return in_shape(b, BLOCK6, 6, mx - 10)
    if variant == 'core4':         # 4 biggest in a 2x2 corner square, 4th >= max/64
        return in_shape(b, CORE4, 4, mx - 6)
    if variant == 'core4+':        # core4 here or after one legal move
        if in_shape(b, CORE4, 4, mx - 6): return True
        return any(in_shape(a, CORE4, 4, mx - 6) for a in (move(b, d) for d in range(4)) if a != b)
    if variant == 'b6|core4':
        return in_shape(b, BLOCK6, 6, mx - 10) or in_shape(b, CORE4, 4, mx - 6)
    if variant == 'b6|core4+':
        for a in [b] + [move(b, d) for d in range(4)]:
            if a == b and a is not b: continue
            if in_shape(a, BLOCK6, 6, mx - 10) or in_shape(a, CORE4, 4, mx - 6): return True
        return False
    raise ValueError(variant)

def load(path='results/mx/positions.tsv'):
    rows = [l.rstrip('\n').split('\t') for l in open(path)]
    hdr = rows[0]
    out = []
    for r in rows[1:]:
        d = dict(zip(hdr, r))
        d['b'] = [int(x) for x in d['ranks'].split(',')]
        out.append(d)
    return out

def main():
    rows = load()
    variants = sys.argv[1:] or ['block6', 'core4', 'core4+', 'b6|core4', 'b6|core4+']
    for v in variants:
        c = collections.Counter(); n = collections.Counter()
        for d in rows:
            key = ('PDF' if d['player'] == 'd4Nf6Bg5' else 'snake', d['group'])
            n[key] += 1; c[key] += detect(d['b'], v)
        cells = '  '.join(f"{k[0]}/{k[1]} {c[k]}/{n[k]}" for k in sorted(n))
        print(f"{v:10s} {cells}")

if __name__ == '__main__':
    main()
