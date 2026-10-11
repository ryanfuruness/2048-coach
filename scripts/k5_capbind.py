# Which k5r10 constraint stops the table in real games? For every position after a game's first k5r10 match (chain of 5
# from the max tile along the snake path, <= 1 two-rank drop, ending at rank 10, free cells within caps), classify later
# positions where the chain still matches but the table does not apply: which free cell exceeds its cap (canonical frame).
import sys, glob
sys.path.insert(0, '/home/ryanf/projects/2048-master/scripts')
from analyze_games import apply, B32, DIRS
from collections import Counter
PATH = [0, 1, 2, 3, 7, 6, 5, 4, 8, 9, 10, 11, 15, 14, 13, 12]
CAPS = [9, 9, 8, 8, 8, 9, 9, 7, 7, 7, 7]  # free cells PATH[5:] = 6,5,4,8,9,10,11,15,14,13,12
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
def chain_ok(s):
    prev = s[PATH[0]]
    if prev != max(s): return False
    gaps = 0
    for j in range(1, 5):
        v = s[PATH[j]]
        if prev - v == 2: gaps += 1
        elif prev - v != 1: return False
        prev = v
    return prev == 10 and gaps <= 1
def classify(b):
    # 'table' if some orientation matches with all caps ok; else ('cap', cell, rank) for the orientation with a chain match
    over = None
    for s in syms(b):
        if not chain_ok(s): continue
        bad = [(PATH[5 + i], s[PATH[5 + i]]) for i in range(11) if s[PATH[5 + i]] > CAPS[i]]
        if not bad: return ('table',)
        if over is None or len(bad) < len(over): over = bad
    return ('cap', over) if over else ('nochain',)
stats = Counter(); cells = Counter(); combos = Counter()
games = 0
for f in sorted(glob.glob('/home/ryanf/projects/2048-master/results/bench/best_v5bb_1000/games*.txt')):
    for line in open(f):
        parts = line.split()
        init = parts[3]; moves = parts[4] if len(parts) > 4 else ""
        b = [B32.index(ch) for ch in init]
        started = False
        games += 1
        for i in range(0, len(moves), 3):
            d, cell, v = DIRS[moves[i]], int(moves[i+1], 16), 1 if moves[i+2] == "2" else 2
            b, g = apply(b, d); b[cell] = v
            if max(b) != 14: 
                if started: break
                continue
            c = classify(b)
            if c[0] == 'table': started = True
            if not started: continue
            stats[c[0]] += 1
            if c[0] == 'cap':
                for (cc, r) in c[1]: cells[(cc, r)] += 1
                combos[len(c[1])] += 1
print("games", games, "positions after first k5r10 match (16384 phase):", sum(stats.values()), dict(stats))
print("cap violations by (canonical cell, rank):")
for (k, n) in sorted(cells.items(), key=lambda x: -x[1])[:20]: print("  cell %2d rank %2d (%5d): %d" % (k[0], k[1], 1 << k[1], n))
print("number of over-cap cells:", dict(combos))
