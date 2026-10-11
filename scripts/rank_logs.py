#!/usr/bin/env python3
"""Rank training logs by the average score of the last logged window(s)."""
import re
import sys
from pathlib import Path

def last_avgs(path, k):
    rows = []
    for line in Path(path).read_text().splitlines():
        m = re.match(r"\s*(\d+) games\s+avg\s+(\d+)", line)
        if m:
            rows.append((int(m.group(1)), int(m.group(2))))
    return rows[-k:], (rows[-1][0] if rows else 0)

k = 1
args = sys.argv[1:]
if args and args[0].startswith("-k"):
    k = int(args[0][2:]); args = args[1:]
res = []
for p in args:
    rows, n = last_avgs(p, k)
    if rows:
        res.append((sum(a for _, a in rows) / len(rows), n, Path(p).stem))
res.sort(reverse=True)
base = next((a for a, _, name in res if name.startswith("none")), None)
for a, n, name in res:
    rel = f"{100 * (a / base - 1):+6.1f}%" if base else ""
    print(f"{name:10s} {n:8d} games  avg {a:9.0f}  {rel}")
