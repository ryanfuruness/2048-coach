#!/usr/bin/env python3
"""Do value losses predict real losses? For each judged (position, move): value loss = best value - move value (engine
analysis), rollout loss = best rollout q - move q. Bins by value loss (relative to the best value) and reports the mean
rollout loss (relative), so mistake thresholds can be set on a scale that means something.
usage: judge_loss_fit.py FILE.tsv ..."""
import sys, collections
pos = collections.defaultdict(list)
for path in sys.argv[1:]:
    with open(path) as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            r = dict(zip(hdr, line.rstrip('\n').split('\t')))
            pos[(path, r['pos'])].append(r)
bins = [0, 0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 10]
acc = collections.defaultdict(lambda: [0, 0.0, 0.0])
for key, rows in pos.items():
    vb = max(float(r['value']) for r in rows)
    qb = max(float(r['q']) for r in rows)
    for r in rows:
        dv = (vb - float(r['value'])) / max(1.0, abs(vb))
        dq = (qb - float(r['q'])) / max(1.0, abs(qb))
        for i in range(len(bins) - 1):
            if bins[i] <= dv < bins[i + 1]:
                a = acc[i]; a[0] += 1; a[1] += dv; a[2] += dq
                break
print(f"{len(pos)} positions")
print("  value loss bin      n   mean value loss   mean rollout loss")
for i in range(len(bins) - 1):
    n, sv, sq = acc[i]
    if n:
        print(f"  [{100*bins[i]:5.1f}%, {100*bins[i+1]:5.1f}%) {n:5d}   {100*sv/n:8.2f}%        {100*sq/n:8.2f}%")
