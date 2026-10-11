#!/usr/bin/env python3
"""Replays `play --record` files and summarises how games progress and end.

usage: analyze_games.py record.txt [...] [--boards N]
Prints: max-tile distribution, milestone move numbers, and (with --boards) the
final boards of the N lowest-scoring games that reached 16384.
"""
import sys
from collections import Counter
from pathlib import Path

B32 = "0123456789abcdefghijklmnopqrstuv"
DIRS = {"U": 0, "R": 1, "D": 2, "L": 3}


def line_cells(d, k):
    out = []
    for j in range(4):
        if d == 0: r, c = j, k
        elif d == 2: r, c = 3 - j, k
        elif d == 3: r, c = k, j
        else: r, c = k, 3 - j
        out.append(r * 4 + c)
    return out


def apply(b, d):
    nb = b[:]
    gained = 0
    for k in range(4):
        cells = line_cells(d, k)
        vals = [b[i] for i in cells if b[i]]
        out = []
        i = 0
        while i < len(vals):
            if i + 1 < len(vals) and vals[i] == vals[i + 1]:
                out.append(vals[i] + 1)
                gained += 1 << (vals[i] + 1)
                i += 2
            else:
                out.append(vals[i])
                i += 1
        out += [0] * (4 - len(out))
        for ci, v in zip(cells, out):
            nb[ci] = v
    return nb, gained


def replay(init, moves):
    b = [B32.index(ch) for ch in init]
    score = 0
    firsts = {}
    mx = max(b)
    for i in range(0, len(moves), 3):
        d, cell, v = DIRS[moves[i]], int(moves[i + 1], 16), 1 if moves[i + 2] == "2" else 2
        b, g = apply(b, d)
        score += g
        b[cell] = v
        m = max(b)
        if m > mx:
            mx = m
            firsts[m] = i // 3 + 1
    return b, score, firsts


def show(b):
    rows = []
    for r in range(4):
        rows.append(" ".join(f"{(1 << v) if v else 0:6d}" for v in b[r * 4:r * 4 + 4]))
    return "\n".join(rows)


def main():
    args = sys.argv[1:]
    nboards = 0
    if "--boards" in args:
        i = args.index("--boards")
        nboards = int(args[i + 1])
        del args[i:i + 2]
    games = []
    for path in args:
        for line in Path(path).read_text().splitlines():
            p = line.split()
            if len(p) >= 5:
                b, score, firsts = replay(p[3], p[4])
                games.append((score, max(b), b, firsts, len(p[4]) // 3))
    n = len(games)
    print(f"{n} games, mean score {sum(g[0] for g in games) / n:.0f}")
    cnt = Counter(g[1] for g in games)
    for r in sorted(cnt):
        reached = sum(c for rr, c in cnt.items() if rr >= r)
        print(f"  max {1 << r:6d}: {cnt[r]:4d}   reached {1 << r}: {100 * reached / n:5.1f}%")
    for r in range(11, 18):
        ms = [g[3][r] for g in games if r in g[3]]
        if ms:
            print(f"  first {1 << r:6d}: median move {sorted(ms)[len(ms) // 2]}")
    if nboards:
        failed = sorted([g for g in games if g[1] >= 14], key=lambda g: g[0])[:nboards]
        for g in failed:
            print(f"\nscore {g[0]}  moves {g[4]}  max {1 << g[1]}\n{show(g[2])}")


if __name__ == "__main__":
    main()
