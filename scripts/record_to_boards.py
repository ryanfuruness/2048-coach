#!/usr/bin/env python3
"""Turns build/play --record lines into board sequences (one board per line, 16 tile values), for analyze --review.
usage: record_to_boards.py RECORD [--game ID] [--keep-every K] > boards.txt
--keep-every K keeps every K-th board only (simulates video frames that skip moves)."""
import sys

def boards_of(line):
    parts = line.split()
    gid, cells, moves = parts[0], parts[3], parts[4] if len(parts) > 4 else ''
    r = [int(c, 32) for c in cells]
    out = [list(r)]
    for i in range(0, len(moves), 3):
        d, c, v = moves[i], int(moves[i + 1], 16), int(moves[i + 2])
        r = slide(r, 'URDL'.index(d))
        r[c] = 1 if v == 2 else 2
        out.append(list(r))
    return gid, out

def slide(r, d):
    r = list(r)
    for k in range(4):
        idx = [(j * 4 + k) if d in (0, 2) else (k * 4 + j) for j in range(4)]
        if d in (1, 2):
            idx = idx[::-1]
        vals = [r[i] for i in idx if r[i]]
        outv, j = [], 0
        while j < len(vals):
            if j + 1 < len(vals) and vals[j] == vals[j + 1]:
                outv.append(vals[j] + 1); j += 2
            else:
                outv.append(vals[j]); j += 1
        outv += [0] * (4 - len(outv))
        for i, v in zip(idx, outv):
            r[i] = v
    return r

def main():
    want = sys.argv[sys.argv.index('--game') + 1] if '--game' in sys.argv else None
    keep = int(sys.argv[sys.argv.index('--keep-every') + 1]) if '--keep-every' in sys.argv else 1
    for line in open(sys.argv[1]):
        gid, bs = boards_of(line)
        if want is not None and gid != want:
            continue
        for i, b in enumerate(bs):
            if i % keep == 0 or i == len(bs) - 1:
                print(' '.join(str(1 << v if v else 0) for v in b))
        break

if __name__ == '__main__':
    main()
