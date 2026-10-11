import sys, glob
sys.path.insert(0, 'scripts')
from analyze_games import apply, B32, DIRS
def show(b):
    return "\n".join(" ".join("%6d" % ((1 << v) if v else 0) for v in b[r*4:r*4+4]) for r in range(4))
lo, hi = int(sys.argv[1]), int(sys.argv[2]); nshow = int(sys.argv[3])
shown = 0
for f in sorted(glob.glob('results/bench/best_v3_1000/games*.txt')):
    for line in open(f):
        parts = line.split()
        gid, score, mx, init = parts[0], int(parts[1]), int(parts[2]), parts[3]
        moves = parts[4] if len(parts) > 4 else ""
        if mx != 16384: continue
        b = [B32.index(ch) for ch in init]
        for i in range(0, len(moves), 3):
            d, cell, v = DIRS[moves[i]], int(moves[i+1], 16), 1 if moves[i+2] == "2" else 2
            b, g = apply(b, d); b[cell] = v
        s = sum((1 << x) for x in b if x)
        if lo <= s < hi and shown < nshow:
            print(f"{f.split('/')[-1]} game {gid} sum {s}"); print(show(b)); print(); shown += 1
