import sys, glob
sys.path.insert(0, 'scripts')
from analyze_games import apply, B32, DIRS
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
def chain_k(b, top):
    # longest strictly decreasing snake chain from the corner starting at rank top, over orientations
    best = 0
    for s in syms(b):
        if s[0] != top: continue
        k, prev = 1, top
        while k < 16 and s[PATH[k]] == prev - 1: prev -= 1; k += 1
        free_max = max(s[PATH[j]] for j in range(k, 16))
        best = max(best, k if free_max < prev else 0)
    return best
stats = {}
for f in sorted(glob.glob(sys.argv[1] + '/games*.txt')):
    for line in open(f):
        parts = line.split()
        mx, init = int(parts[2]), parts[3]
        moves = parts[4] if len(parts) > 4 else ""
        b = [B32.index(ch) for ch in init]
        seen = set()
        for i in range(0, len(moves), 3):
            d, cell, v = DIRS[moves[i]], int(moves[i+1], 16), 1 if moves[i+2] == "2" else 2
            b, g = apply(b, d); b[cell] = v
            if max(b) == 14:
                k = chain_k(b, 14)
                for kk in (4, 5, 6):
                    if k >= kk and kk not in seen: seen.add(kk)
        for kk in seen:
            stats.setdefault(kk, [0, 0]); stats[kk][0] += 1; stats[kk][1] += mx >= 32768
for kk in sorted(stats):
    n, w = stats[kk]
    print(f"reached a full consecutive k>={kk} chain (16384 down, free tiles below the chain end): {n} games, {w} reached 32768 ({100*w/n:.1f}%)")
