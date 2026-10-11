# Boards at the moment the 32768 first forms (after the spawn), from benchmark records -> 64-bit boards (cell 0 lowest
# nibble), written as a pool file for play --start.
import sys, glob, struct, random
sys.path.insert(0, 'scripts')
from analyze_games import apply, B32, DIRS
out = []
for d in sys.argv[2:]:
    for f in sorted(glob.glob(d + '/games*.txt')):
        for line in open(f):
            parts = line.split()
            if int(parts[2]) < 32768: continue
            init = parts[3]; moves = parts[4] if len(parts) > 4 else ""
            b = [B32.index(ch) for ch in init]
            for i in range(0, len(moves), 3):
                dd, cell, v = DIRS[moves[i]], int(moves[i+1], 16), 1 if moves[i+2] == "2" else 2
                b, g = apply(b, dd); b[cell] = v
                if max(b) >= 15:
                    x = 0
                    for c in range(16): x |= min(b[c], 15) << (4 * c)
                    out.append(x)
                    break
random.seed(7)
random.shuffle(out)
with open(sys.argv[1], 'wb') as f:
    for x in out: f.write(struct.pack('<Q', x))
print(len(out), "positions")
