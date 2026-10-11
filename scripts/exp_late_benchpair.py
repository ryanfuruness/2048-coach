#!/usr/bin/env python3
"""Paired comparison of two 1000-game benchmarks run by scripts/bench.sh with the same chunk seeds (chunk k = seed
1000+k): per (chunk, game id) the score and the largest tile; mean differences with the paired standard error.
usage: exp_late_benchpair.py results/bench/NAME results/bench/BASE"""
import glob, math, re, sys

def games(d):
    out = {}
    for f in glob.glob(f'{d}/chunk*.log'):
        k = int(re.search(r'chunk(\d+)', f).group(1))
        for line in open(f):
            m = re.match(r'game\s+(\d+)\s+score\s+(\d+)\s+max\s+(\d+)', line)
            if m: out[(k, int(m.group(1)))] = (int(m.group(2)), int(m.group(3)))
    return out

def pm(xs):
    n = len(xs); m = sum(xs) / n
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1) / n)

a, b = games(sys.argv[1]), games(sys.argv[2])
keys = [k for k in a if k in b]
print(f"{len(keys)} paired games; identical: {sum(a[k] == b[k] for k in keys)}")
m, se = pm([a[k][0] - b[k][0] for k in keys])
print(f"score: {sum(a[k][0] for k in keys) / len(keys):,.0f} vs {sum(b[k][0] for k in keys) / len(keys):,.0f}, diff {m:+,.0f} +- {se:,.0f}")
for t in (16384, 32768, 65536):
    m, se = pm([(a[k][1] >= t) - (b[k][1] >= t) for k in keys])
    ra = sum(a[k][1] >= t for k in keys) / len(keys); rb = sum(b[k][1] >= t for k in keys) / len(keys)
    print(f"reached {t}: {100 * ra:.1f}% vs {100 * rb:.1f}%, diff {100 * m:+.2f} +- {100 * se:.2f}")
