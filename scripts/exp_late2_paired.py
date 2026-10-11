#!/usr/bin/env python3
"""Workstream late2: paired comparison of two early-game tests of scripts/exp_late2_phase.sh (same seeds, same game ids:
the games share the spawn sequence until the first different move): reach tile 16384 and reach tile sum 20480.
usage: exp_late2_paired.py NAME BASE [DIR=results/late2]"""
import glob, math, re, sys

def games(path):
    out = {}
    for line in open(path):
        m = re.match(r'game\s+(\d+)\s+score\s+(\d+)\s+max\s+(\d+).*sum\s+(\d+)', line)
        if m:
            out[int(m.group(1))] = (int(m.group(2)), int(m.group(3)), int(m.group(4)))
    return out

def paired(xs):
    n = len(xs)
    m = sum(xs) / n
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1) / n)

def main():
    name, base = sys.argv[1:3]
    d = sys.argv[3] if len(sys.argv) > 3 else 'results/late2'
    pairs = []
    for f in sorted(glob.glob(f'{d}/early_{name}_s*.log')):
        seed = f.rsplit('_s', 1)[1][:-4]
        try:
            a, b = games(f), games(f'{d}/early_{base}_s{seed}.log')
        except FileNotFoundError:
            continue
        pairs += [(a[g], b[g]) for g in a if g in b]
    for lab, ok in (('16384', lambda x: x[1] >= 16384), ('sum 20480', lambda x: x[2] >= 20480)):
        m, se = paired([ok(x) - ok(y) for x, y in pairs])
        ra = sum(ok(x) for x, _ in pairs) / len(pairs); rb = sum(ok(y) for _, y in pairs) / len(pairs)
        print(f"early {name} vs {base}: {len(pairs)} paired games, {lab}: {100 * ra:.2f}% vs {100 * rb:.2f}%, "
              f"diff {100 * m:+.2f} +- {100 * se:.2f} points")

if __name__ == '__main__':
    main()
