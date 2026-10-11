#!/usr/bin/env python3
"""Paired comparison of two phase-test runs of scripts/exp_late_phase.sh (workstream late): both players start from the
same boards with the same seeds, so their games share the spawn sequence until the first different move. Per game id:
ph16 success (tile sum >= 36864), p32 score gained and final sum >= 57344; mean difference with the standard error of
the paired differences.
usage: exp_late_paired.py ph16|p32 NAME BASE [DIR=results/late]"""
import glob, math, re, sys

def games(path):
    out = {}
    for line in open(path):
        m = re.match(r'game\s+(\d+)\s+score\s+(\d+).*sum\s+(\d+)', line)
        if m:
            out[int(m.group(1))] = (int(m.group(2)), int(m.group(3)))
    return out

def paired(xs):
    n = len(xs)
    if n < 2: return float('nan'), float('nan')
    m = sum(xs) / n
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1) / n)

def main():
    kind, name, base = sys.argv[1:4]
    d = sys.argv[4] if len(sys.argv) > 4 else 'results/late'
    pairs = []
    if kind == 'ph16':
        for f in sorted(glob.glob(f'{d}/ph16_{name}_s*.log')):
            seed = f.rsplit('_s', 1)[1][:-4]
            fb = f'{d}/ph16_{base}_s{seed}.log'
            try:
                a, b = games(f), games(fb)
            except FileNotFoundError:
                continue
            pairs += [(a[g], b[g]) for g in a if g in b]
        ds = [(x[1] >= 36864) - (y[1] >= 36864) for x, y in pairs]
        m, se = paired(ds)
        ra = sum(x[1] >= 36864 for x, _ in pairs) / max(1, len(pairs))
        rb = sum(y[1] >= 36864 for _, y in pairs) / max(1, len(pairs))
        print(f"ph16 {name} vs {base}: {len(pairs)} paired games, {100 * ra:.2f}% vs {100 * rb:.2f}%, "
              f"diff {100 * m:+.2f} +- {100 * se:.2f} points")
    else:
        a, b = games(f'{d}/p32_{name}.log'), games(f'{d}/p32_{base}.log')
        pairs = [(a[g], b[g]) for g in a if g in b]
        m, se = paired([x[0] - y[0] for x, y in pairs])
        m2, se2 = paired([(x[1] >= 57344) - (y[1] >= 57344) for x, y in pairs])
        m3, se3 = paired([(x[1] >= 49152) - (y[1] >= 49152) for x, y in pairs])
        print(f"p32 {name} vs {base}: {len(pairs)} paired games, score diff {m:+,.0f} +- {se:,.0f}, "
              f"sum>=49152 {100 * m3:+.2f} +- {100 * se3:.2f}, sum>=57344 {100 * m2:+.2f} +- {100 * se2:.2f} points")

if __name__ == '__main__':
    main()
