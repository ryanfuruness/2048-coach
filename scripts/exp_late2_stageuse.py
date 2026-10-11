#!/usr/bin/env python3
"""Workstream late2: which network stage evaluates the search ROOT of each move in recorded games (build/play
--record), under best_v5's settings: stages "sum:20480/14,24576,28672,36864" on the root view (root downgrade 15,
gap >= 5: while a rank >= 15 is on the board, lower every rank above the largest absent rank g >= 5 below the max).
Stage 0 also covers views below 24576 holding a 16384 through the leaf view (--leaf-view 14 6 --leaf-view-max-sum
24576), reported separately. Counts moves per stage, overall and for moves whose REAL board holds a 32768+.
usage: exp_late2_stageuse.py RECORD.txt ..."""
import sys, collections
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from record_to_boards import boards_of  # noqa: E402

def downgrade_view(r, top=15, min_gap=5):
    r = list(r)
    while True:
        mx = max(r)
        if mx < top:
            return r
        present = set(r)
        gap = -1
        for k in range(mx - 1, min_gap - 1, -1):
            if k not in present:
                gap = k
                break
        if gap < 0:
            return r
        r = [v - 1 if v > gap else v for v in r]

def tsum(r):
    return sum(1 << v for v in r if v)

def stage_of(v):
    s, mx = tsum(v), max(v)
    if s < 20480 or (mx < 14 and s < 24576):  # "20480/14": below 20480, or below the next boundary without a 16384
        return 0
    if s < 24576: return 1
    if s < 28672: return 2
    if s < 36864: return 3
    return 4

def main():
    allc, big = collections.Counter(), collections.Counter()
    examples = []
    for path in sys.argv[1:]:
        for line in open(path):
            if not line.strip(): continue
            gid, boards = boards_of(line)
            for b in boards[:-1]:
                v = downgrade_view(b)
                st = stage_of(v)
                allc[st] += 1
                if max(b) >= 15:
                    big[st] += 1
                    if st == 4 and len(examples) < 8: examples.append((b, v))
    n, nb = sum(allc.values()), sum(big.values())
    print(f"moves {n}, with a 32768+ on the board {nb}")
    for st in range(5):
        print(f"  stage {st}: all {allc[st]:9d} ({100 * allc[st] / max(1, n):5.2f}%)   32768+ boards {big[st]:8d} ({100 * big[st] / max(1, nb):5.2f}%)")
    for b, v in examples:
        print("  stage-4 example real", [1 << x if x else 0 for x in b], "view sum", tsum(v))

if __name__ == '__main__':
    main()
