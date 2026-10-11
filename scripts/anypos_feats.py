#!/usr/bin/env python3
"""Board-level formation features for the odds check (workstream anypos), from the engine hex board (cell 0 =
top-left, 4-bit ranks), counting only BIG tiles (rank >= the biggest's - 3, i.e. at least 1/8 of it):
  far  = summed Manhattan distance beyond 1 of the big tiles to their nearest bigger-or-equal big tile (0 for a chain
         where every big tile touches a bigger one; a big tile stranded far from the others adds its distance - 1)
  bigs = number of big tiles besides the biggest."""
def dist(a, b): return abs(a // 4 - b // 4) + abs(a % 4 - b % 4)
def feats(hx):
    r = [int(c, 16) for c in hx]
    R = max(r)
    big = sorted([c for c in range(16) if r[c] >= R - 3 and r[c] > 0], key=lambda c: -r[c])
    far = 0
    for i, c in enumerate(big[1:], 1):
        d = min(dist(c, o) for o in big[:i])  # to the nearest bigger-or-equal big tile placed before it
        far += max(0, d - 1)
    return dict(far=far, bigs=len(big) - 1)
