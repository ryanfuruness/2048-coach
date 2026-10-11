# Classify best_v5bb's stage-B deaths (max 16384, death sum in [24576, 28672)) by board structure.
import sys, glob
sys.path.insert(0, '/home/ryanf/projects/2048-master/scripts')
from analyze_games import apply, B32, DIRS
from collections import Counter
PATH = [0, 1, 2, 3, 7, 6, 5, 4, 8, 9, 10, 11, 15, 14, 13, 12]
def syms(b):
    g = [b[r*4:r*4+4] for r in range(4)]
    out = []
    for t in range(2):
        m = g if t == 0 else [list(x) for x in zip(*g)]
        for fr in range(2):
            for fc in range(2):
                mm = m[::-1] if fr else m
                mm = [row[::-1] for row in mm] if fc else mm
                out.append([v for row in mm for v in row])
    return out
def chain_len(b):
    best = 0
    for s in syms(b):
        if s[0] != max(b): continue
        k, prev, gaps = 1, s[0], 0
        while k < 16:
            v = s[PATH[k]]
            if v == prev - 1: pass
            elif v == prev - 2 and gaps == 0: gaps = 1
            else: break
            prev = v; k += 1
        best = max(best, k)
    return best
lo, hi = int(sys.argv[1]), int(sys.argv[2])
cls = Counter(); empt = Counter(); n = 0
for f in sorted(glob.glob('/home/ryanf/projects/2048-master/results/bench/best_v5bb_1000/games*.txt')):
    for line in open(f):
        parts = line.split()
        mx, init = int(parts[2]), parts[3]
        moves = parts[4] if len(parts) > 4 else ""
        if mx != 16384: continue
        b = [B32.index(ch) for ch in init]
        for i in range(0, len(moves), 3):
            d, cell, v = DIRS[moves[i]], int(moves[i+1], 16), 1 if moves[i+2] == "2" else 2
            b, g = apply(b, d); b[cell] = v
        s = sum((1 << x) for x in b if x)
        if not (lo <= s < hi): continue
        n += 1
        corner = max(b) in (b[0], b[3], b[12], b[15])
        k = chain_len(b)
        key = ("max in corner" if corner else "max NOT in corner") + (", chain>=6" if k >= 6 else ", chain %d" % k)
        cls[key] += 1
        small = sum(1 for x in b if 0 < x <= 3)  # tiles <= 8
        empt[small] += 1
print(n, "deaths with sum in", lo, hi)
for k, v in sorted(cls.items(), key=lambda x: -x[1]): print("  %-35s %d" % (k, v))
print("  tiles <= 8 on the death board:", dict(sorted(empt.items())))
