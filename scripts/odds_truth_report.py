#!/usr/bin/env python3
"""Compare odds models with playout ground truth on the tight human positions (scripts/odds_truth.sh): measured
P(reach 16384) per position (4 copies x 30 playouts) vs each model's prediction (build/analyze --calib MODEL),
mean absolute error and log-loss of the predictions against the playout outcomes.
usage: odds_truth_report.py MODEL.txt [MODEL.txt ...]"""
import json, math, subprocess, sys, collections
pos = [l.rstrip('\n').split('\t') for l in open('results/judge/tight30.tsv')][1:]
truth = collections.defaultdict(lambda: [0.0, 0])
rows = [l.rstrip('\n').split('\t') for l in open('results/judge/tight30_16k.tsv')]
h = {k: i for i, k in enumerate(rows[0])}
for r in rows[1:]:
    i = int(r[h['pos']]) // 4  # 4 copies per position
    n = int(r[h['n']])
    truth[i][0] += float(r[h['p16384']]) * n; truth[i][1] += n
meas = {i: s / n for i, (s, n) in truth.items()}
boards = '\n'.join(p[3] for p in pos) + '\n'
for model in sys.argv[1:]:
    out = subprocess.run(['bash', '-c', f'ulimit -s unlimited; ./build/analyze --preset best-notables --no-calib --calib {model} --stdin'],
                         input=boards, capture_output=True, text=True).stdout.strip().split('\n')
    err, ll, k = 0.0, 0.0, 0
    for i, line in enumerate(out):
        a = json.loads(line)
        p = a.get('odds', {}).get('16384')
        if p is None or i not in meas: continue
        n = truth[i][1]; y = meas[i]
        err += abs(p - y); k += 1
        pc = min(max(p, 1e-4), 1 - 1e-4)
        ll += -(y * math.log(pc) + (1 - y) * math.log(1 - pc))
    print(f"{model}: {k} positions, mean |predicted - measured| P(16384) = {err / k:.3f}, log-loss {ll / k:.4f}")
print(f"measured P(16384): mean {sum(meas.values()) / len(meas):.3f}, min {min(meas.values()):.2f}, max {max(meas.values()):.2f}")
