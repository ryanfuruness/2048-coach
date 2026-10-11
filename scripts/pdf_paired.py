#!/usr/bin/env python3
"""Paired comparison of two phase-test logs (same starts and seeds): ph16 success (sum >= 36864) or p32 score.
usage: pdf_paired.py BASE.log NEW.log [ph16|p32]"""
import re, sys, math

def load(p):
    out = {}
    for line in open(p):
        m = re.match(r'game\s+(\d+)\s+score\s+(\d+)\s+max\s+(\d+)\s+moves\s+(\d+).*sum\s+(\d+)', line)
        if m: out[int(m.group(1))] = (int(m.group(2)), int(m.group(5)))
    return out

a, b = load(sys.argv[1]), load(sys.argv[2])
mode = sys.argv[3] if len(sys.argv) > 3 else 'ph16'
g = sorted(set(a) & set(b))
same = sum(a[i] == b[i] for i in g)
if mode == 'ph16':
    d = [(b[i][1] >= 36864) - (a[i][1] >= 36864) for i in g]
else:
    d = [b[i][0] - a[i][0] for i in g]
m = sum(d) / len(d)
se = math.sqrt(sum((x - m) ** 2 for x in d) / (len(d) - 1) / len(d))
print(f"{len(g)} games, {same} identical; paired mean difference {m:+.4f} +- {se:.4f}" + (" (success rate)" if mode == 'ph16' else " (score)"))
